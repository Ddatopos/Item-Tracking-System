"""基于神经网络的物品示踪系统 V1.0：环境与可持久化推理设置。"""
import math
import os
from pathlib import Path

DEFAULT_SETTINGS = {
    "inference_fps": 2.0,
    "confidence_threshold": 0.25,
    "selected_classes": [],
    "dedup_seconds": 30.0,
    "input_size": 640,
}


def validate_settings(changes, current=None):
    if not isinstance(changes, dict) or set(changes) - set(DEFAULT_SETTINGS):
        raise ValueError("unknown settings or invalid JSON object")
    result = {**(current or DEFAULT_SETTINGS), **changes}
    for key, lo, hi in [("inference_fps", 0.1, 30), ("confidence_threshold", 0, 1), ("dedup_seconds", 0, 3600)]:
        value = result[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f"{key} must be between {lo} and {hi}")
    if type(result["input_size"]) is not int or result["input_size"] < 32 or result["input_size"] > 2048 or result["input_size"] % 32:
        raise ValueError("input_size must be a multiple of 32 between 32 and 2048")
    classes = result["selected_classes"]
    if not isinstance(classes, list) or len(classes) > 200 or any(not isinstance(c, str) or not c.strip() or len(c) > 100 for c in classes):
        raise ValueError("selected_classes must be a list of class names")
    return result


def load_config(overrides=None):
    config = {
        "DATA_DIR": os.environ.get("TRACKING_DATA_DIR", str(Path(__file__).resolve().parents[2] / "runtime")),
        "CAMERA_KIND": os.environ.get("TRACKING_CAMERA_KIND", "mock"),
        "CAMERA_SOURCE": os.environ.get("TRACKING_CAMERA_SOURCE", "0"),
        "CAMERA_ID": "camera-1",
        "ROOM": os.environ.get("TRACKING_ROOM", "未设置房间"),
        "CAPTURE_FPS": 15.0,
        "RECONNECT_SECONDS": 1.0,
        "FRAME_STALE_SECONDS": 3.0,
        "SHUTDOWN_TIMEOUT": 5.0,
        "MAX_STREAM_CLIENTS": 4,
        "FRONTEND_DIR": os.environ.get("TRACKING_FRONTEND_DIR", ""),
        "TRUSTED_ORIGINS": [],
        "TESTING": False,
        "MAX_CONTENT_LENGTH": 4 * 1024 * 1024,
        "DEBUG": False,
    }
    config.update(overrides or {})
    config["DATA_DIR"] = Path(config["DATA_DIR"]).expanduser().resolve()
    if config["CAMERA_KIND"] not in {"mock", "opencv"}:
        raise ValueError("CAMERA_KIND must be mock or opencv")
    return config
