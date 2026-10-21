"""基于神经网络的物品示踪系统 V1.0：完全隔离的模拟测试环境。"""
import time
import pytest
from tracking.adapters import FakeDetector, MockCamera
from tracking.app_factory import create_app


def wait_for(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.01)
    raise AssertionError("condition did not become true before timeout")


@pytest.fixture
def app(tmp_path):
    instance = create_app({"DATA_DIR": tmp_path, "TESTING": True, "CAPTURE_FPS": 40.0,
                           "RECONNECT_SECONDS": .03, "SHUTDOWN_TIMEOUT": .5}, camera=MockCamera(), detector=FakeDetector())
    instance.extensions["runtime"].update_settings({"inference_fps": 20.0})
    yield instance
    instance.extensions["runtime"].shutdown()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runtime(app):
    return app.extensions["runtime"]
