"""设备端测试夹具：使用模拟摄像头，不依赖真实硬件与 picamera2。"""
import json
import sys
import threading
import time
import urllib.request
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from device.raspberry_pi.config import DEFAULTS
from device.raspberry_pi.server import CameraService, create_server


class FakeCamera:
    """模拟取帧设备，可配置打开失败、读取失败与非法帧。"""

    source_type = "fake"

    def __init__(self, fail_opens=0, invalid_frame=False, read_errors=0):
        self.fail_opens = int(fail_opens)
        self.invalid_frame = bool(invalid_frame)
        self.read_errors = int(read_errors)
        self.opens = 0
        self.closes = 0
        self.frames = 0
        self.opened = False
        self._read_failures = 0
        self._counter = 0

    def open(self):
        self.opens += 1
        if self.opens <= self.fail_opens:
            raise OSError("模拟打开失败")
        self.opened = True

    def read(self):
        if not self.opened:
            raise OSError("模拟摄像头未打开")
        if self._read_failures < self.read_errors:
            self._read_failures += 1
            raise OSError("模拟读取失败")
        if self.invalid_frame:
            return np.zeros((480, 640), dtype=np.uint8)
        self.frames += 1
        self._counter += 1
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        image[:, :, 0] = (np.arange(1280) % 256).astype(np.uint8)
        image[:, :, 1] = self._counter % 256
        return image

    def close(self):
        if self.opened:
            self.closes += 1
        self.opened = False


def make_config(**overrides):
    """测试用的完整配置，端口为 0 以便随机分配。"""
    config = dict(DEFAULTS)
    config.update({
        "host": "127.0.0.1",
        "port": 0,
        "fps": 30,
        "retry_backoff_seconds": 0.05,
        "max_backoff_seconds": 0.1,
        "frame_stale_seconds": 0.3,
    })
    config.update(overrides)
    return config


def wait_until(predicate, timeout=5.0):
    """轮询直到条件为真，超时抛 AssertionError。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.01)
    raise AssertionError("等待条件超时")


def get_json(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


class ServerHarness:
    """把采集服务、HTTP 服务器和测试摄像头组合在一起，便于 finally 清理。"""

    def __init__(self, service, server, thread, camera):
        self.service = service
        self.server = server
        self.thread = thread
        self.camera = camera
        self._closed = False

    def url(self, path):
        return "http://127.0.0.1:%d%s" % (self.server.server_port, path)

    def health(self):
        return get_json(self.url("/health"))

    def wait_online(self, timeout=5.0):
        return wait_until(lambda: self.health()["camera_state"] == "online", timeout)

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.service.stop()
        finally:
            if self.thread.is_alive():
                self.server.shutdown()
            self.server.server_close()
            self.thread.join(5)


@pytest.fixture
def make_service():
    created = []

    def factory(camera=None, **overrides):
        camera = FakeCamera() if camera is None else camera
        service = CameraService(make_config(**overrides), source_factory=lambda config: camera)
        created.append(service)
        return service, camera

    yield factory
    for service in created:
        service.stop()


@pytest.fixture
def make_server(make_service):
    harnesses = []

    def factory(camera=None, start=True, **overrides):
        service, camera = make_service(camera, **overrides)
        server = create_server(service, service.config)
        thread = threading.Thread(target=server.serve_forever, name="test-camera-http", daemon=True)
        thread.start()
        harness = ServerHarness(service, server, thread, camera)
        harnesses.append(harness)
        if start:
            service.start()
        return harness

    yield factory
    for harness in harnesses:
        harness.close()
