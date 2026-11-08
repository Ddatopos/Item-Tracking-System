"""树莓派摄像头服务配置：默认值、JSON 加载与字段校验。"""
import json
import math
import os
from pathlib import Path


class ConfigError(ValueError):
    """配置内容不合法。"""


DEFAULTS = {
    "camera_id": "pi-cam-1",
    "room": "未设置房间",
    "host": "0.0.0.0",
    "port": 8080,
    "width": 1280,
    "height": 720,
    "fps": 15,
    "jpeg_quality": 80,
    "autofocus": "continuous",
    "lens_position": 1.0,
    "max_clients": 4,
    "open_attempts": 5,
    "retry_backoff_seconds": 1.0,
    "max_backoff_seconds": 30.0,
    "frame_stale_seconds": 3.0,
    "log_level": "INFO",
    "log_file": "",
}

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
AUTOFOCUS_MODES = ("continuous", "manual")


def default_config_path():
    """返回默认配置文件路径 device/raspberry_pi/configs/camera.json。"""
    return Path(__file__).resolve().parent / "configs" / "camera.json"


def _read_json(path):
    if not path.exists():
        raise ConfigError("配置文件不存在：%s" % path)
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except ValueError as exc:
        raise ConfigError("配置文件不是合法的 JSON：%s（%s）" % (path, exc))
    if not isinstance(data, dict):
        raise ConfigError("配置文件顶层必须是 JSON 对象：%s" % path)
    return data


def _is_number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _int_field(name, value, low, high):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError("%s 必须是整数" % name)
    if not low <= value <= high:
        raise ConfigError("%s 必须在 %d 到 %d 之间，当前为 %d" % (name, low, high, value))
    return value


def _even_field(name, value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError("%s 必须是整数" % name)
    if value < 64 or value > 4608 or value % 2:
        raise ConfigError("%s 必须是 64 到 4608 之间的偶数，当前为 %d" % (name, value))
    return value


def _number_field(name, value, low, high):
    if not _is_number(value):
        raise ConfigError("%s 必须是数字" % name)
    if not low <= value <= high:
        raise ConfigError("%s 必须在 %s 到 %s 之间，当前为 %s" % (name, low, high, value))
    return value


def _text_field(name, value, allow_empty=False):
    if not isinstance(value, str):
        raise ConfigError("%s 必须是字符串" % name)
    if not allow_empty and not value.strip():
        raise ConfigError("%s 不能为空" % name)
    return value


def validate_config(values):
    """校验完整配置字典并返回副本；任何非法字段都抛 ConfigError。"""
    if not isinstance(values, dict):
        raise ConfigError("配置必须是 JSON 对象")
    unknown = sorted(set(values) - set(DEFAULTS))
    if unknown:
        raise ConfigError("未知配置字段：%s" % "、".join(unknown))
    missing = sorted(set(DEFAULTS) - set(values))
    if missing:
        raise ConfigError("缺少配置字段：%s" % "、".join(missing))
    result = dict(values)
    result["camera_id"] = _text_field("camera_id", result["camera_id"])
    result["room"] = _text_field("room", result["room"])
    result["host"] = _text_field("host", result["host"])
    result["port"] = _int_field("port", result["port"], 1024, 65535)
    result["width"] = _even_field("width", result["width"])
    result["height"] = _even_field("height", result["height"])
    result["fps"] = _number_field("fps", result["fps"], 1, 60)
    result["jpeg_quality"] = _int_field("jpeg_quality", result["jpeg_quality"], 50, 95)
    result["max_clients"] = _int_field("max_clients", result["max_clients"], 1, 16)
    result["open_attempts"] = _int_field("open_attempts", result["open_attempts"], 1, 20)
    result["retry_backoff_seconds"] = _number_field("retry_backoff_seconds", result["retry_backoff_seconds"], 0.1, 60)
    result["max_backoff_seconds"] = _number_field("max_backoff_seconds", result["max_backoff_seconds"], 0.1, 300)
    result["frame_stale_seconds"] = _number_field("frame_stale_seconds", result["frame_stale_seconds"], 0.5, 60)

    if result["max_backoff_seconds"] < result["retry_backoff_seconds"]:
        raise ConfigError("max_backoff_seconds 不能小于 retry_backoff_seconds")
    if result["autofocus"] not in AUTOFOCUS_MODES:
        raise ConfigError("autofocus 只能是 continuous 或 manual，当前为 %s" % result["autofocus"])
    if not _is_number(result["lens_position"]):
        raise ConfigError("lens_position 必须是数字")
    if result["autofocus"] == "manual" and not 0 <= result["lens_position"] <= 32:
        raise ConfigError("manual 对焦时 lens_position 必须在 0 到 32 之间，当前为 %s" % result["lens_position"])
    if result["log_level"] not in LOG_LEVELS:
        raise ConfigError("log_level 只能是 DEBUG、INFO、WARNING 或 ERROR，当前为 %s" % result["log_level"])
    result["log_file"] = _text_field("log_file", result["log_file"], allow_empty=True)
    return result


def load_config(path=None, overrides=None):
    """默认值 + 配置文件 + 非 None 覆盖值，返回校验后的配置字典。

    路径优先级：显式 path > 环境变量 PI_CAMERA_CONFIG > 默认路径。
    显式参数或环境变量指定的文件必须存在；默认路径缺失时只使用默认值。
    """
    if path is not None:
        config_path = Path(path).expanduser()
        required = True
    else:
        env_path = os.environ.get("PI_CAMERA_CONFIG", "").strip()
        if env_path:
            config_path = Path(env_path).expanduser()
            required = True
        else:
            config_path = default_config_path()
            required = False
    values = dict(DEFAULTS)
    if required or config_path.exists():
        values.update(_read_json(config_path))
    if overrides is not None:
        if not isinstance(overrides, dict):
            raise ConfigError("覆盖配置必须是字典")
        values.update({key: value for key, value in overrides.items() if value is not None})
    return validate_config(values)
