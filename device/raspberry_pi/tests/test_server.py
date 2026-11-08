"""设备端 HTTP 服务测试：全部使用模拟摄像头，不依赖真实硬件。"""
import json
import socket
import threading
import urllib.error
import urllib.request

import pytest

from conftest import FakeCamera, wait_until


def test_health_reports_online(make_server):
    harness = make_server()
    try:
        harness.wait_online()
        payload = harness.health()
        assert payload["state"] == "running"
        assert payload["camera_state"] == "online"
        assert payload["resolution"] == "1280x720"
        assert payload["configured_fps"] == 30
        assert payload["camera_id"] == "pi-cam-1"
    finally:
        harness.close()


def test_snapshot_returns_jpeg(make_server):
    harness = make_server()
    try:
        harness.wait_online()
        with urllib.request.urlopen(harness.url("/snapshot"), timeout=5) as response:
            assert response.status == 200
            assert response.headers["Content-Type"] == "image/jpeg"
            assert response.headers["Cache-Control"] == "no-store"
            data = response.read()
        assert data.startswith(b"\xff\xd8")
    finally:
        harness.close()


def test_two_stream_clients_open_camera_once(make_server):
    harness = make_server()
    try:
        harness.wait_online()
        payloads = []
        errors = []

        def reader():
            try:
                with urllib.request.urlopen(harness.url("/video"), timeout=5) as response:
                    payloads.append(response.read(4096))
            except Exception as exc:  # 记录异常供断言，避免线程静默失败
                errors.append(exc)

        threads = [threading.Thread(target=reader) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        assert not errors
        assert len(payloads) == 2
        assert all(b"--frame" in payload for payload in payloads)
        assert harness.camera.opens == 1
        assert harness.service.status()["frames"] >= 1
    finally:
        harness.close()


def test_stream_rejects_extra_client(make_server):
    harness = make_server(max_clients=1)
    first = None
    try:
        harness.wait_online()
        first = urllib.request.urlopen(harness.url("/video"), timeout=5)
        first.read(1024)
        with pytest.raises(urllib.error.HTTPError) as info:
            urllib.request.urlopen(harness.url("/video"), timeout=5)
        assert info.value.code == 503
        info.value.close()
    finally:
        if first is not None:
            first.close()
        harness.close()


def test_snapshot_without_frames_returns_503(make_server):
    harness = make_server(start=False)
    try:
        with pytest.raises(urllib.error.HTTPError) as info:
            urllib.request.urlopen(harness.url("/snapshot"), timeout=5)
        assert info.value.code == 503
        info.value.close()
    finally:
        harness.close()


def test_invalid_frame_marks_camera_offline(make_server):
    harness = make_server(camera=FakeCamera(invalid_frame=True))
    try:
        wait_until(lambda: harness.health()["errors"] > 0)
        payload = harness.health()
        assert payload["camera_state"] in ("offline", "error")
        assert payload["errors"] > 0
    finally:
        harness.close()


def test_open_failures_become_fatal(make_server):
    harness = make_server(camera=FakeCamera(fail_opens=99), open_attempts=2)
    try:
        wait_until(lambda: harness.health()["state"] == "error")
        payload = harness.health()
        assert payload["camera_state"] == "error"
        assert payload["last_error"]
        assert "OSError" in payload["last_error"]
    finally:
        harness.close()


def test_stop_then_restart_continues(make_server):
    harness = make_server()
    try:
        harness.wait_online()
        before = harness.service.status()["frames"]
        harness.service.stop()
        harness.server.shutdown()
        harness.thread.join(5)
        harness.server.server_close()
        with pytest.raises(OSError):
            socket.create_connection(("127.0.0.1", harness.server.server_port), timeout=1)
        assert harness.camera.closes >= 1
        assert harness.service.start() is True
        wait_until(lambda: harness.service.status()["frames"] > before)
    finally:
        harness.close()


def test_unknown_path_returns_404(make_server):
    harness = make_server(start=False)
    try:
        with pytest.raises(urllib.error.HTTPError) as info:
            urllib.request.urlopen(harness.url("/not-found"), timeout=5)
        assert info.value.code == 404
        body = json.loads(info.value.read().decode("utf-8"))
        assert "error" in body
        info.value.close()
    finally:
        harness.close()
