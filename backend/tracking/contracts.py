"""基于神经网络的物品示踪系统 V1.0：唯一的公共数据合同。"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Protocol, Sequence
import math

LOCAL_TZ = timezone(timedelta(hours=8))


def timestamp(value=None):
    """统一为 UTC ISO 8601；第一版无时区时间按北京时间解释。"""
    dt = datetime.now(timezone.utc) if value is None else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def seconds_between(newer, older):
    return (datetime.fromisoformat(timestamp(newer)) - datetime.fromisoformat(timestamp(older))).total_seconds()


@dataclass(frozen=True)
class CameraFrame:
    frame_id: str
    camera_id: str
    room: str
    captured_at: str
    width: int
    height: int
    source_type: str
    image: Any  # BGR uint8 ndarray；缓存中只读，适配器不得修改


@dataclass(frozen=True)
class DetectionEvent:
    event_id: str
    frame_id: str
    camera_id: str
    room: str
    class_name: str
    confidence: float
    bbox: Sequence[float]
    captured_at: str
    model_version: str
    raw_image_path: str = ""
    annotated_image_path: str = ""

    def validate(self):
        for key, value in [("frame_id", self.frame_id), ("camera_id", self.camera_id), ("room", self.room)]:
            if not isinstance(value, str) or not value or len(value) > 200:
                raise ValueError(f"{key} must contain 1..200 characters")
        if not isinstance(self.class_name, str) or not self.class_name.strip() or len(self.class_name) > 100:
            raise ValueError("class_name must contain 1..100 characters")
        if not isinstance(self.event_id, str) or not self.event_id or len(self.event_id) > 200:
            raise ValueError("invalid event_id")
        if not isinstance(self.model_version, str) or not self.model_version or len(self.model_version) > 200:
            raise ValueError("invalid model_version")
        if type(self.confidence) not in {int, float} or not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if not isinstance(self.bbox, (list, tuple)) or len(self.bbox) != 4 or any(type(v) not in {int, float} or not math.isfinite(v) for v in self.bbox):
            raise ValueError("bbox must contain four finite coordinates")
        x1, y1, x2, y2 = self.bbox
        if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1:
            raise ValueError("bbox must be [xmin, ymin, xmax, ymax]")
        timestamp(self.captured_at)


class CameraSource(Protocol):
    """open/read/close 必须有界返回；由一个取帧线程独占调用。"""
    source_type: str
    def open(self) -> None: ...
    def read(self) -> Any: ...
    def close(self) -> None: ...


class DetectorService(Protocol):
    """只在一个推理线程调用；必须在关闭超时内返回，不在这里实现 YOLO。"""
    model_version: str
    simulated: bool
    def detect(self, frame: CameraFrame, settings: dict) -> Sequence[DetectionEvent]: ...
    def close(self) -> None: ...
