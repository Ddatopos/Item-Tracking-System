"""基于神经网络的物品示踪系统 V1.0：线程、帧共享、异常恢复与退出测试。"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading
import time
import pytest
from tracking.adapters import FakeDetector, MockCamera
from tracking.app_factory import create_app
from tracking.runtime import RuntimeConflict
from conftest import wait_for


def test_factory_isolated_and_no_threads(tmp_path):
    a = create_app({"DATA_DIR": tmp_path / "a"})
    b = create_app({"DATA_DIR": tmp_path / "b"})
    try:
        ra, rb = a.extensions["runtime"], b.extensions["runtime"]
        assert ra is not rb and ra.camera is not rb.camera
        assert ra.capture_thread is None and rb.capture_thread is None
        ra.update_settings({"confidence_threshold": .7})
        assert rb.get_settings()["confidence_threshold"] == .25
    finally:
        a.extensions["runtime"].shutdown()
        b.extensions["runtime"].shutdown()


def test_concurrent_start_opens_one_camera(runtime):
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(lambda _: runtime.start(), range(20))) == 1
    wait_for(lambda: runtime.latest)
    assert runtime.camera.opens == 1
    assert runtime.capture_thread.is_alive()


def test_repeat_inference_start_uses_one_worker(runtime):
    assert runtime.start_inference()
    thread = runtime.inference_thread
    assert not runtime.start_inference()
    assert runtime.inference_thread is thread
    wait_for(lambda: runtime.status()["events_created"])
    runtime.stop_inference()
    runtime.stop_inference()
    assert not thread.is_alive()
    assert runtime.start_inference()
    assert runtime.inference_thread is not thread


def test_multi_preview_share_source_and_disconnect(client, runtime):
    runtime.start()
    wait_for(lambda: runtime.latest)
    a = client.get("/api/stream", buffered=False)
    b = client.get("/api/stream/preview", buffered=False)
    assert a.status_code == b.status_code == 200
    assert b"Content-Type: image/jpeg" in next(a.response)
    assert b"Content-Type: image/jpeg" in next(b.response)
    assert runtime.status()["preview_clients"] == 2
    assert runtime.camera.opens == 1 and runtime.detector.calls == 0
    a.close()
    b.close()
    assert runtime.status()["preview_clients"] == 0


def test_close_response_before_first_iteration_releases_slot(app, runtime):
    from tracking.api import stream
    runtime.start()
    with app.test_request_context("/api/stream"):
        response = stream()
        assert runtime.preview_clients == 1
        response.close()
    assert runtime.preview_clients == 0


def test_preview_limit_keeps_control_available(client, runtime):
    runtime.start()
    wait_for(lambda: runtime.latest)
    responses = [client.get("/api/stream", buffered=False) for _ in range(4)]
    try:
        denied = client.get("/api/stream", buffered=False)
        assert denied.status_code == 409
        assert client.get("/api/status").status_code == 200
    finally:
        for response in responses:
            response.close()


def test_slow_detector_does_not_block_preview_or_api(app, runtime):
    runtime.detector = FakeDetector(delay=.2)
    runtime.start_inference()
    wait_for(lambda: runtime.in_flight)
    before = runtime.sequence
    client = app.test_client()
    started = time.monotonic()
    assert client.get("/api/status").status_code == 200
    assert client.get("/api/snapshot").status_code == 200
    assert time.monotonic() - started < .15
    wait_for(lambda: runtime.status()["inference_calls"] >= 3)
    status = runtime.status()
    assert runtime.sequence > before + 10
    assert status["queue_length"] <= 1 and status["skipped_frames"] > 0
    assert runtime.camera.opens == 1


def test_detector_exception_then_recovery(runtime):
    class Flaky(FakeDetector):
        attempts = 0
        def detect(self, frame, settings):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("model failure")
            return super().detect(frame, settings)
    runtime.detector = Flaky()
    runtime.start_inference()
    wait_for(lambda: runtime.status()["events_created"])
    assert runtime.status()["inference_errors"] == 1
    assert runtime.inference_error is None


def test_camera_disconnect_then_recovery(runtime):
    class Flaky(MockCamera):
        attempts = 0
        def read(self):
            self.attempts += 1
            if self.attempts == 2:
                raise OSError("disconnected")
            return super().read()
    runtime.camera = Flaky()
    runtime.start()
    wait_for(lambda: runtime.camera.opens == 2 and runtime.sequence >= 3)
    assert runtime.status()["camera_errors"] == 1
    assert runtime.status()["camera_state"] == "online"


def test_offline_camera_has_no_stale_snapshot(client, runtime):
    class Offline(MockCamera):
        def read(self):
            raise OSError("offline")
    runtime.camera = Offline()
    runtime.start()
    wait_for(lambda: runtime.status()["camera_state"] == "offline")
    assert client.get("/api/snapshot").status_code == 503
    assert client.get("/api/status").status_code == 200


def test_offline_preview_still_yields_and_releases_disconnected_client(client, runtime):
    class Offline(MockCamera):
        def read(self):
            raise OSError("offline")
    runtime.camera = Offline()
    runtime.start()
    wait_for(lambda: runtime.status()["camera_state"] == "offline")
    response = client.get("/api/stream", buffered=False)
    assert response.status_code == 200
    assert next(response.response) == b"\r\n"
    assert runtime.preview_clients == 1
    response.close()
    assert runtime.preview_clients == 0


def test_stop_clears_cache_and_restarts(runtime):
    runtime.start_inference()
    wait_for(lambda: runtime.detector.calls)
    capture, inference = runtime.capture_thread, runtime.inference_thread
    runtime.stop()
    assert runtime.latest is None and runtime.jpeg is None
    assert not capture.is_alive() and not inference.is_alive()
    assert runtime.camera.closes == 1
    runtime.stop()
    runtime.start()
    wait_for(lambda: runtime.latest)
    assert runtime.camera.opens == 2


def test_shutdown_closes_resources_and_is_idempotent(client, runtime):
    runtime.start_inference()
    wait_for(lambda: runtime.latest)
    assert client.post("/api/shutdown").status_code == 200
    assert runtime.repository.closed and not runtime.camera.opened
    assert not runtime.capture_thread.is_alive() and not runtime.inference_thread.is_alive()
    assert client.post("/api/shutdown").status_code == 200
    assert client.get("/api/status").json["state"] == "shutdown"
    assert client.get("/api/items").status_code == 409
    assert client.post("/api/runtime/start").status_code == 409


def test_stop_timeout_retains_database_and_prevents_duplicate_worker(runtime):
    gate = threading.Event()
    class Blocked(FakeDetector):
        def detect(self, frame, settings):
            gate.wait(3)
            return []
    runtime.detector = Blocked()
    runtime.start_inference()
    wait_for(lambda: runtime.in_flight)
    try:
        with pytest.raises(RuntimeConflict):
            runtime.shutdown()
        assert not runtime.repository.closed
        with pytest.raises(RuntimeConflict):
            runtime.start_inference()
    finally:
        gate.set()
        runtime.inference_thread.join(2)
        runtime.shutdown()
    assert runtime.closed


def test_inference_stop_keeps_preview_running(client, runtime):
    runtime.start_inference()
    wait_for(lambda: runtime.latest)
    runtime.stop_inference()
    assert client.get("/api/snapshot").status_code == 200
    assert runtime.capture_thread.is_alive()


def test_preview_stop_keeps_inference_running(client, runtime):
    runtime.start_inference()
    wait_for(lambda: runtime.detector.calls)
    assert client.post("/api/stream/stop").status_code == 200
    assert client.get("/api/stream").status_code == 409
    before = runtime.detector.calls
    wait_for(lambda: runtime.detector.calls > before)
    assert client.post("/api/stream/start").status_code == 200
    response = client.get("/api/stream", buffered=False)
    assert response.status_code == 200
    response.close()


def test_detector_receives_copy_and_cannot_corrupt_preview(runtime):
    class Mutating(FakeDetector):
        def detect(self, frame, settings):
            frame.image[:] = 0
            return super().detect(frame, settings)
    runtime.detector = Mutating()
    runtime.start_inference()
    wait_for(lambda: runtime.detector.calls > 0)
    assert runtime.latest.image.sum() > 0
    assert not runtime.latest.image.flags.writeable


def test_wrong_frame_contract_rejected(runtime):
    class Wrong(FakeDetector):
        def detect(self, frame, settings):
            return [replace(super().detect(frame, settings)[0], camera_id="wrong-camera")]
    runtime.detector = Wrong()
    runtime.start_inference()
    wait_for(lambda: runtime.status()["inference_errors"])
    assert runtime.repository.items() == []


def test_confidence_and_class_filter(runtime):
    runtime.update_settings({"selected_classes": ["backpack"]})
    runtime.start_inference()
    wait_for(lambda: runtime.detector.calls >= 2)
    assert runtime.repository.items() == []
    runtime.update_settings({"selected_classes": ["cup"], "confidence_threshold": .95})
    before = runtime.detector.calls
    wait_for(lambda: runtime.detector.calls > before + 1)
    assert runtime.repository.items() == []
    runtime.update_settings({"confidence_threshold": .5})
    wait_for(lambda: runtime.repository.items() == ["cup"])
