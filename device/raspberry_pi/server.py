"""设备端 MJPEG 视频源：帧缓存、单线程采集服务与标准库 HTTP 服务器。"""
import json
import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import cv2
import numpy as np

if __package__:
    from . import VERSION
else:
    from __init__ import VERSION

LOG = logging.getLogger("device.camera")

ENDPOINTS = ["/health", "/status", "/snapshot", "/video", "/stream"]


class ClientLimitError(RuntimeError):
    """同时观看视频流的客户端超过上限。"""


def _utc_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class FrameStore:
    """线程安全地保存最新一帧 JPEG，供快照和多个视频客户端共享。"""

    def __init__(self):
        self._condition = threading.Condition()
        self._sequence = 0
        self._jpeg = None
        self._width = 0
        self._height = 0
        self._published_at = 0.0

    def publish(self, sequence, jpeg, width, height):
        with self._condition:
            self._sequence = int(sequence)
            self._jpeg = jpeg
            self._width = int(width)
            self._height = int(height)
            self._published_at = time.monotonic()
            self._condition.notify_all()

    def latest(self, max_age=None):
        """返回 (sequence, jpeg, age) ；无帧或超过 max_age 时返回 None。"""
        with self._condition:
            if self._jpeg is None:
                return None
            age = time.monotonic() - self._published_at
            if max_age is not None and age > max_age:
                return None
            return self._sequence, self._jpeg, age

    def wait_next(self, after, timeout):
        """等待序号大于 after 的新帧，超时返回 None。"""
        with self._condition:
            if self._jpeg is not None and self._sequence > after:
                return self._sequence, self._jpeg
            self._condition.wait(timeout)
            if self._jpeg is not None and self._sequence > after:
                return self._sequence, self._jpeg
            return None

    def size(self):
        with self._condition:
            if self._jpeg is None:
                return None
            return self._width, self._height

    def wake_all(self):
        with self._condition:
            self._condition.notify_all()


class CameraService:
    """单采集线程的摄像头服务，负责取帧、编码、重试与状态统计。"""

    def __init__(self, config, source_factory=None, on_fatal=None):
        self.config = dict(config)
        self.source_factory = source_factory
        self.on_fatal = on_fatal
        self.frames = FrameStore()
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread = None
        self._source = None
        self._source_type = "unknown"
        self._state = "stopped"
        self._camera_state = "stopped"
        self._frame_count = 0
        self._error_count = 0
        self._last_error = None
        self._clients = 0
        self._frame_times = deque(maxlen=30)
        self._started_at = None

    def start(self):
        """启动采集线程；已在运行时返回 False。"""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop_event = threading.Event()
            self._state = "running"
            self._camera_state = "offline"
            self._last_error = None
            self._started_at = time.monotonic()
            thread = threading.Thread(target=self._capture_loop, name="camera-capture", daemon=True)
            self._thread = thread
        thread.start()
        LOG.info("采集线程已启动：%s", self.config.get("camera_id"))
        return True

    def stop(self):
        """停止采集并关闭摄像头；有界等待，可重复调用。"""
        with self._lock:
            self._stop_event.set()
            thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(5.0)
        source = None
        with self._lock:
            source, self._source = self._source, None
            self._thread = None
            self._state = "stopped"
            self._camera_state = "stopped"
            self._started_at = None
            self._frame_times.clear()
        if source is not None:
            self._close_source(source)
        self.frames.wake_all()
        LOG.info("采集服务已停止")

    def is_streaming(self):
        """采集是否在运行；视频流处理线程据此决定是否继续输出。"""
        with self._lock:
            return self._state == "running"

    def acquire_client(self):
        with self._lock:
            limit = int(self.config.get("max_clients", 4))
            if self._clients >= limit:
                raise ClientLimitError("同时观看视频的客户端已达到上限 %d" % limit)
            self._clients += 1
            return self._clients

    def release_client(self):
        with self._lock:
            self._clients = max(0, self._clients - 1)

    def status(self):
        """返回加锁读取的状态字典，字段供 /health、/status 和 / 使用。"""
        with self._lock:
            state = self._state
            camera_state = self._camera_state
            frames = self._frame_count
            errors = self._error_count
            last_error = self._last_error
            clients = self._clients
            started_at = self._started_at
            frame_times = list(self._frame_times)
            source_type = self._source_type
        latest = self.frames.latest(None)
        size = self.frames.size()
        resolution = "%dx%d" % size if size else "unknown"
        frame_age_ms = round(latest[2] * 1000) if latest else None
        measured_fps = 0.0
        if len(frame_times) >= 2:
            span = frame_times[-1] - frame_times[0]
            if span > 0:
                measured_fps = round((len(frame_times) - 1) / span, 1)
        uptime = round(time.monotonic() - started_at, 1) if started_at else 0.0
        return {
            "state": state,
            "camera_state": camera_state,
            "camera_id": self.config.get("camera_id"),
            "room": self.config.get("room"),
            "source_type": source_type,
            "resolution": resolution,
            "configured_fps": self.config.get("fps"),
            "measured_fps": measured_fps,
            "frames": frames,
            "errors": errors,
            "last_error": last_error,
            "clients": clients,
            "max_clients": self.config.get("max_clients"),
            "uptime_seconds": uptime,
            "frame_age_ms": frame_age_ms,
            "timestamp": _utc_timestamp(),
        }

    def _capture_loop(self):
        config = self.config
        period = 1.0 / float(config["fps"])
        open_attempts = int(config["open_attempts"])
        backoff = float(config["retry_backoff_seconds"])
        max_backoff = float(config["max_backoff_seconds"])
        quality = int(config["jpeg_quality"])
        stop_event = self._stop_event
        failures = 0
        opened = False
        try:
            while not stop_event.is_set():
                tick = time.monotonic()
                try:
                    if not opened:
                        self._open_source()
                        opened = True
                    image = self._source.read()
                    if image is None or getattr(image, "ndim", 0) != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
                        raise ValueError("摄像头返回的帧格式不正确，需要 BGR uint8 HxWx3")
                    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
                    if not ok:
                        raise ValueError("JPEG 编码失败")
                    jpeg = encoded.tobytes()
                    height, width = int(image.shape[0]), int(image.shape[1])
                    with self._lock:
                        self._frame_count += 1
                        sequence = self._frame_count
                        self._camera_state = "online"
                        self._last_error = None
                        self._frame_times.append(time.monotonic())
                    self.frames.publish(sequence, jpeg, width, height)
                    failures = 0
                    backoff = float(config["retry_backoff_seconds"])
                    stop_event.wait(max(0.0, period - (time.monotonic() - tick)))
                except Exception as exc:
                    opened = False
                    self._release_source()
                    failures += 1
                    fatal = failures >= open_attempts
                    with self._lock:
                        self._error_count += 1
                        self._last_error = "%s: %s" % (type(exc).__name__, exc)
                        self._camera_state = "error" if fatal else "offline"
                        if fatal:
                            self._state = "error"
                    LOG.warning("摄像头异常（第 %d 次）：%s", failures, self._last_error)
                    if fatal:
                        LOG.error("摄像头连续失败达到上限 %d，采集线程结束，HTTP 服务继续可用", open_attempts)
                        self._notify_fatal(exc)
                        return
                    stop_event.wait(backoff)
                    backoff = min(max_backoff, backoff * 2)
        finally:
            self._release_source()
            self.frames.wake_all()

    def _open_source(self):
        with self._lock:
            if self._source is None:
                if self.source_factory is not None:
                    self._source = self.source_factory(self.config)
                else:
                    self._source = self._create_default_source()
                self._source_type = getattr(self._source, "source_type", "unknown")
            source = self._source
        source.open()

    def _create_default_source(self):
        if __package__:
            from .source import Picamera2Source
        else:
            from source import Picamera2Source
        return Picamera2Source(
            width=self.config["width"],
            height=self.config["height"],
            fps=self.config["fps"],
            autofocus=self.config["autofocus"],
            lens_position=self.config["lens_position"],
        )

    def _release_source(self):
        with self._lock:
            source, self._source = self._source, None
        if source is not None:
            self._close_source(source)

    @staticmethod
    def _close_source(source):
        try:
            source.close()
        except Exception:
            LOG.exception("关闭摄像头失败")

    def _notify_fatal(self, error):
        if self.on_fatal is None:
            return
        try:
            self.on_fatal(error)
        except Exception:
            LOG.exception("on_fatal 回调执行失败")


class CameraRequestHandler(BaseHTTPRequestHandler):
    """只读的 HTTP 接口：状态、快照与 MJPEG 视频流。"""

    protocol_version = "HTTP/1.0"

    def do_GET(self):
        path = urlsplit(self.path).path.rstrip("/") or "/"
        try:
            if path == "/":
                self._send_index()
            elif path in ("/health", "/status"):
                self._send_json(200, self.server.service.status())
            elif path == "/snapshot":
                self._send_snapshot()
            elif path in ("/video", "/stream"):
                self._send_stream()
            else:
                self._send_json(404, {"error": "未知路径：%s" % path})
        except (BrokenPipeError, ConnectionResetError):
            LOG.debug("客户端提前断开：%s", self.client_address)

    def log_message(self, format, *args):
        LOG.debug("%s %s", self.address_string(), format % args)

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _send_index(self):
        payload = self.server.service.status()
        payload["version"] = VERSION
        payload["endpoints"] = list(ENDPOINTS)
        self._send_json(200, payload)

    def _send_snapshot(self):
        frame = self.server.service.frames.latest(self.server.config["frame_stale_seconds"])
        if frame is None:
            self._send_json(503, {"error": "当前没有可用的视频帧"})
            return
        sequence, jpeg, _ = frame
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(jpeg)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Id", str(sequence))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(jpeg)

    def _send_stream(self):
        service = self.server.service
        try:
            service.acquire_client()
        except ClientLimitError as exc:
            self._send_json(503, {"error": str(exc)})
            return
        try:
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            last = 0
            while service.is_streaming():
                frame = service.frames.wait_next(last, 0.5)
                if frame is None:
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                    continue
                sequence, jpeg = frame
                header = ("--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\nX-Frame-Id: %d\r\n\r\n"
                          % (len(jpeg), sequence)).encode("ascii")
                self.wfile.write(header)
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
                last = sequence
        except (BrokenPipeError, ConnectionResetError):
            LOG.debug("视频客户端断开：%s", self.client_address)
        except OSError as exc:
            LOG.debug("视频流写入中止：%s", exc)
        finally:
            service.release_client()


class CameraHTTPServer(ThreadingHTTPServer):
    """每个请求独立线程；进程退出时不等待长连接。"""

    daemon_threads = True
    allow_reuse_address = True


def create_server(service, config):
    """按配置绑定端口并返回 HTTP 服务器实例。"""
    server = CameraHTTPServer((config["host"], int(config["port"])), CameraRequestHandler)
    server.service = service
    server.config = config
    return server
