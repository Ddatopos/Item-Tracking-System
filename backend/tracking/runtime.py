"""基于神经网络的物品示踪系统 V1.0：单源最新帧缓存和有界后台推理。"""
from collections import deque
from dataclasses import replace
import json
import logging
import os
from pathlib import Path
import threading
import time
import uuid
import cv2
from .contracts import CameraFrame, DetectionEvent, timestamp
from .repository import safe_path

LOG = logging.getLogger("tracking.runtime")


class RuntimeConflict(RuntimeError):
    pass


class RuntimeManager:
    def __init__(self, config, repository, camera, detector):
        self.config, self.repository = config, repository
        self.camera, self.detector = camera, detector
        self.control = threading.RLock()
        self.condition = threading.Condition(threading.RLock())
        self.settings_lock = threading.RLock()
        self.settings = repository.get_settings()
        self.capture_stop, self.inference_stop = threading.Event(), threading.Event()
        self.capture_thread = self.inference_thread = None
        self.latest = None
        self.jpeg = None
        self.latest_monotonic = 0
        self.sequence = 0
        self.state = "stopped"
        self.camera_state = "stopped"
        self.inference_state = "stopped"
        self.camera_error = self.inference_error = None
        self.closed = False
        self.closing = False
        self.preview_clients = 0
        self.preview_enabled = True
        self.stream_generation = 0
        self.in_flight = False
        self.last_inferred = 0
        self.started = time.monotonic()
        self.capture_times = deque(maxlen=300)
        self.inference_times = deque(maxlen=300)
        self.counters = {"captured_frames": 0, "inference_calls": 0, "inference_errors": 0, "camera_errors": 0,
                         "skipped_frames": 0, "events_created": 0, "events_merged": 0, "preview_parts": 0}
        self.last_inference_ms = 0.0
        repository.camera(config["CAMERA_ID"], config["ROOM"], camera.source_type)

    def get_settings(self):
        with self.settings_lock:
            return json.loads(json.dumps(self.settings))

    def update_settings(self, changes):
        from .config import validate_settings
        with self.control, self.settings_lock:
            self._ensure_open()
            values = validate_settings(changes, self.settings)
            self.repository.set_settings(values)
            self.settings = values
            return self.get_settings()

    def _ensure_open(self):
        if self.closed or self.closing:
            raise RuntimeConflict("runtime has been shut down; restart the process")

    def start(self):
        with self.control:
            self._ensure_open()
            if self.capture_thread and self.capture_thread.is_alive():
                return False
            self.capture_stop.clear()
            with self.condition:
                self.state, self.camera_state = "running", "connecting"
            self.capture_thread = threading.Thread(target=self._capture_loop, name="tracking-capture", daemon=True)
            self.capture_thread.start()
            return True

    def start_inference(self):
        with self.control:
            self._ensure_open()
            if not getattr(self.detector, "available", True):
                raise RuntimeConflict("DetectorService is not configured; use --demo only for simulation")
            self.start()
            if self.inference_thread and self.inference_thread.is_alive():
                if self.inference_stop.is_set():
                    raise RuntimeConflict("previous inference call is still stopping")
                return False
            self.inference_stop.clear()
            self.inference_state = "starting"
            self.inference_thread = threading.Thread(target=self._inference_loop, name="tracking-inference", daemon=True)
            self.inference_thread.start()
            return True

    def stop_inference(self):
        with self.control:
            self.inference_stop.set()
            with self.condition:
                self.condition.notify_all()
            if self.inference_thread and self.inference_thread.is_alive():
                self.inference_state = "stopping"
                self.inference_thread.join(self.config["SHUTDOWN_TIMEOUT"])
                if self.inference_thread.is_alive():
                    raise RuntimeConflict("DetectorService did not return before shutdown timeout")
            self.inference_state = "stopped"

    def stop(self):
        with self.control:
            self.stop_inference()
            self.capture_stop.set()
            with self.condition:
                self.stream_generation += 1
                self.condition.notify_all()
            if self.capture_thread and self.capture_thread.is_alive():
                self.capture_thread.join(self.config["SHUTDOWN_TIMEOUT"])
                if self.capture_thread.is_alive():
                    raise RuntimeConflict("CameraSource did not return before shutdown timeout")
            with self.condition:
                self.latest = self.jpeg = None
                self.state = self.camera_state = "stopped"

    def shutdown(self):
        with self.control:
            if self.closed:
                return
            self.closing = True
            try:
                self.stop()
                self.detector.close()
                self.repository.close()
                self.closed = True
                self.state = "shutdown"
            except Exception:
                self.state = "shutdown_failed"
                # 不在活跃线程仍会使用资源时强关数据库；允许再次请求 shutdown。
                raise

    def _capture_loop(self):
        opened = False
        try:
            while not self.capture_stop.is_set():
                tick = time.monotonic()
                try:
                    if not opened:
                        self.camera.open()
                        opened = True
                    image = self.camera.read()
                    if image is None or image.ndim != 3 or image.shape[2] != 3 or str(image.dtype) != "uint8":
                        raise ValueError("CameraSource.read must return BGR uint8 HxWx3")
                    image = image.copy()
                    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if not ok:
                        raise ValueError("JPEG encoding failed")
                    image.setflags(write=False)
                    with self.condition:
                        self.sequence += 1
                        self.latest = CameraFrame(str(self.sequence), self.config["CAMERA_ID"], self.config["ROOM"], timestamp(), image.shape[1], image.shape[0], self.camera.source_type, image)
                        self.jpeg = encoded.tobytes()
                        self.latest_monotonic = time.monotonic()
                        self.capture_times.append(self.latest_monotonic)
                        self.counters["captured_frames"] += 1
                        self.camera_state, self.camera_error = "online", None
                        self.condition.notify_all()
                    self.capture_stop.wait(max(0, 1 / self.config["CAPTURE_FPS"] - (time.monotonic() - tick)))
                except Exception as exc:
                    LOG.exception("Camera failure; reconnecting")
                    with self.condition:
                        self.camera_state, self.camera_error = "offline", type(exc).__name__
                        self.latest = self.jpeg = None
                        self.counters["camera_errors"] += 1
                        self.condition.notify_all()
                    try:
                        self.camera.close()
                    except Exception:
                        LOG.exception("Camera release failed")
                    opened = False
                    self.capture_stop.wait(self.config["RECONNECT_SECONDS"])
        finally:
            try:
                self.camera.close()
            except Exception:
                LOG.exception("Final camera release failed")
            with self.condition:
                self.camera_state = "stopped"
                self.condition.notify_all()

    def frame(self, after=0, timeout=0):
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                if self.capture_stop.is_set() or self.closed:
                    return None, None
                if self.latest and int(self.latest.frame_id) > int(after) and time.monotonic() - self.latest_monotonic < self.config["FRAME_STALE_SECONDS"]:
                    return self.latest, self.jpeg
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None, None
                self.condition.wait(min(remaining, .5))

    def _inference_loop(self):
        previous = 0
        try:
            while not self.inference_stop.is_set():
                started = time.monotonic()
                frame, _ = self.frame(after=previous, timeout=.25)
                if frame is None:
                    self.inference_state = "waiting_for_frame"
                    self.inference_stop.wait(.02)
                    continue
                params = self.get_settings()
                with self.condition:
                    self.counters["skipped_frames"] += max(0, int(frame.frame_id) - previous - 1) if previous else 0
                    self.last_inferred = previous = int(frame.frame_id)
                    self.in_flight = True
                    self.inference_state = "running"
                try:
                    # 检测器可修改自己持有的副本，不会污染预览帧。
                    detector_frame = replace(frame, image=frame.image.copy())
                    results = list(self.detector.detect(detector_frame, params))
                    if len(results) > 1000:
                        raise ValueError("DetectorService returned too many events")
                    best = {}
                    for event in results:
                        if not isinstance(event, DetectionEvent):
                            raise ValueError("DetectorService must return shared DetectionEvent objects")
                        event.validate()
                        if (event.frame_id, event.camera_id, event.room, timestamp(event.captured_at)) != (frame.frame_id, frame.camera_id, frame.room, frame.captured_at):
                            raise ValueError("detection event does not belong to the supplied CameraFrame")
                        if event.bbox[2] > frame.width or event.bbox[3] > frame.height:
                            raise ValueError("bbox exceeds frame dimensions")
                        if event.confidence < params["confidence_threshold"] or (params["selected_classes"] and event.class_name not in params["selected_classes"]):
                            continue
                        if event.class_name not in best or event.confidence > best[event.class_name].confidence:
                            best[event.class_name] = event
                    if not self.inference_stop.is_set():
                        for event in best.values():
                            _, created = self.repository.record(event, params, lambda e: self._save_images(frame, e))
                            with self.condition:
                                self.counters["events_created" if created else "events_merged"] += 1
                    self.inference_error = None
                except Exception as exc:
                    LOG.exception("Inference failed; next frame will be retried")
                    with self.condition:
                        self.counters["inference_errors"] += 1
                        self.inference_error = type(exc).__name__
                        self.inference_state = "error"
                finally:
                    with self.condition:
                        self.in_flight = False
                        self.counters["inference_calls"] += 1
                        self.inference_times.append(time.monotonic())
                        self.last_inference_ms = round((time.monotonic() - started) * 1000, 3)
                self.inference_stop.wait(max(0, 1 / params["inference_fps"] - (time.monotonic() - started)))
        finally:
            self.inference_state = "stopped"

    def _save_images(self, frame, event):
        name = uuid.uuid4().hex
        raw, annotated = f"images/{name}.jpg", f"processed_images/{name}.jpg"
        drawn = frame.image.copy()
        x1, y1, x2, y2 = map(int, event.bbox)
        cv2.rectangle(drawn, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(drawn, f"{event.class_name} {event.confidence:.2f}", (x1, max(20, y1 - 7)), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 0, 255), 2)
        written = []
        try:
            for relative, image in [(raw, frame.image), (annotated, drawn)]:
                path = safe_path(self.config["DATA_DIR"], relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                ok, data = cv2.imencode(".jpg", image)
                if not ok:
                    raise OSError("event JPEG encoding failed")
                temporary = path.with_suffix(".tmp")
                written.append(temporary)
                temporary.write_bytes(data.tobytes())
                os.replace(temporary, path)
                written.append(path)
            return raw, annotated
        except Exception:
            for path in written:
                path.unlink(missing_ok=True)
            raise

    def reserve_preview(self):
        with self.condition:
            if self.preview_clients >= self.config["MAX_STREAM_CLIENTS"]:
                raise RuntimeConflict("preview client limit reached")
            if self.state != "running" or self.closing or not self.preview_enabled:
                raise RuntimeConflict("start runtime before opening preview")
            self.preview_clients += 1
            return self.stream_generation

    def release_preview(self):
        with self.condition:
            self.preview_clients -= 1

    def set_preview(self, enabled):
        with self.control:
            self._ensure_open()
            if enabled:
                self.start()
            with self.condition:
                if not enabled:
                    self.stream_generation += 1
                self.preview_enabled = enabled
                self.condition.notify_all()

    def stream(self, generation):
        last = 0
        while not self.closed and not self.capture_stop.is_set() and generation == self.stream_generation and self.preview_enabled:
            frame, data = self.frame(after=last, timeout=.5)
            if frame is None:
                # multipart 空白心跳让服务器即使在断线期间也有机会检测客户端断开。
                # 不重发旧画面，不生成虚假的摄像头帧。
                yield b"\r\n"
                continue
            last = frame.frame_id
            with self.condition:
                self.counters["preview_parts"] += 1
            yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(data)).encode() + b"\r\nX-Frame-Id: " + str(last).encode() + b"\r\n\r\n" + data + b"\r\n"

    @staticmethod
    def _rate(times):
        if len(times) < 2:
            return 0.0
        return round((len(times) - 1) / max(.001, times[-1] - times[0]), 3) if time.monotonic() - times[-1] < 3 else 0.0

    def status(self):
        with self.condition:
            fresh = self.latest is not None and time.monotonic() - self.latest_monotonic < self.config["FRAME_STALE_SECONDS"]
            pending = int(fresh and int(self.latest.frame_id) > self.last_inferred)
            return {"state": self.state, "camera_state": self.camera_state,
                    "camera_error": self.camera_error, "inference_state": self.inference_state,
                    "inference_error": self.inference_error, "frame_id": self.latest.frame_id if fresh else None,
                    "frame_age_ms": round((time.monotonic() - self.latest_monotonic) * 1000, 1) if fresh else None,
                    "capture_fps": self._rate(self.capture_times), "inference_fps": self._rate(self.inference_times),
                    "queue_length": pending, "queue_capacity": 1, "in_flight": self.in_flight,
                    "preview_clients": self.preview_clients, "preview_enabled": self.preview_enabled, "last_inference_ms": self.last_inference_ms,
                    "detector_version": self.detector.model_version, "detector_simulated": getattr(self.detector, "simulated", False),
                    "camera_simulated": self.camera.source_type == "mock",
                    "uptime_seconds": round(time.monotonic() - self.started, 3), **self.counters}
