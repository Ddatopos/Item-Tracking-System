"""可运行的适配器工厂示例；工厂只构造对象，线程仍由后端管理。"""
from tracking.adapters import FakeDetector, MockCamera, OpenCVCamera
from tracking.config import load_config
from tracking.contracts import CameraSource, DetectorService


def camera() -> CameraSource:
    config = load_config()
    if config["CAMERA_KIND"] == "opencv":
        return OpenCVCamera(config["CAMERA_SOURCE"])
    return MockCamera()


def detector() -> DetectorService:
    return FakeDetector()
