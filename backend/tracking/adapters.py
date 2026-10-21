"""基于神经网络的物品示踪系统 V1.0：模拟源与硬件适配边界。"""
import time
import uuid
import cv2
import numpy as np
from .contracts import DetectionEvent


class MockCamera:
    source_type = "mock"

    def __init__(self):
        self.opens = 0
        self.closes = 0
        self.frames = 0
        self.opened = False

    def open(self):
        self.opens += 1
        self.opened = True

    def read(self):
        if not self.opened:
            raise OSError("camera is closed")
        self.frames += 1
        image = np.zeros((360, 640, 3), dtype=np.uint8)
        image[:] = (40, 32, 24)
        cv2.rectangle(image, (100, 90), (220, 240), (70, 190, 220), -1)
        cv2.putText(image, f"SIMULATION frame {self.frames}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, .7, (255, 255, 255), 2)
        return image

    def close(self):
        if self.opened:
            self.closes += 1
        self.opened = False


class OpenCVCamera:
    """UVC 或 HTTP/MJPEG/RTSP；网络源使用 FFmpeg 打开和读取超时。"""
    source_type = "opencv"

    def __init__(self, source):
        self.source = int(source) if str(source).isdigit() else str(source)
        self.capture = None

    def open(self):
        if self.capture is not None:
            return
        if isinstance(self.source, int):
            cap = cv2.VideoCapture(self.source)
        else:
            cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG, [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 2000,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC, 2000,
            ])
        if not cap.isOpened():
            cap.release()
            raise OSError("camera could not be opened")
        self.capture = cap

    def read(self):
        ok, image = self.capture.read()
        if not ok:
            raise OSError("camera read failed")
        return image

    def close(self):
        if self.capture is not None:
            self.capture.release()
            self.capture = None


class UnavailableDetector:
    model_version = "not-configured"
    simulated = False
    available = False

    def detect(self, frame, settings):
        raise RuntimeError("DetectorService is not configured")

    def close(self):
        pass


class FakeDetector:
    """仅供演示和测试，不代表真实识别结果或准确率。"""
    model_version = "fake-demo-1"
    simulated = True
    available = True

    def __init__(self, delay=0):
        self.delay = delay
        self.calls = 0

    def detect(self, frame, settings):
        time.sleep(self.delay)
        self.calls += 1
        return [DetectionEvent(str(uuid.uuid4()), frame.frame_id, frame.camera_id, frame.room,
                               "cup", .9, [100, 90, 220, 240], frame.captured_at, self.model_version)]

    def close(self):
        pass
