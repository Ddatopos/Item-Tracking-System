"""设备端配置加载与校验测试。"""
import json

import pytest

from device.raspberry_pi import config as device_config
from device.raspberry_pi.config import DEFAULTS, ConfigError, load_config


def _write_config(tmp_path, data):
    path = tmp_path / "camera.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _use_missing_default(tmp_path, monkeypatch):
    monkeypatch.delenv("PI_CAMERA_CONFIG", raising=False)
    monkeypatch.setattr(device_config, "default_config_path", lambda: tmp_path / "missing.json")


def test_defaults_are_complete(tmp_path, monkeypatch):
    _use_missing_default(tmp_path, monkeypatch)
    config = load_config()
    assert set(config) == set(DEFAULTS)
    assert config == DEFAULTS
    assert config["camera_id"] == "pi-cam-1"
    assert config["room"] == "未设置房间"
    assert config["port"] == 8080
    assert config["frame_stale_seconds"] == 3.0


def test_load_json_file(tmp_path):
    path = _write_config(tmp_path, {"port": 9000, "room": "实验室", "width": 1920, "height": 1080})
    config = load_config(path)
    assert config["port"] == 9000
    assert config["room"] == "实验室"
    assert config["width"] == 1920
    assert config["height"] == 1080
    assert config["camera_id"] == DEFAULTS["camera_id"]


def test_overrides_win_over_file(tmp_path):
    path = _write_config(tmp_path, {"port": 9000, "fps": 10})
    config = load_config(path, {"port": 9100, "fps": 20, "room": None})
    assert config["port"] == 9100
    assert config["fps"] == 20
    assert config["room"] == DEFAULTS["room"]


def test_unknown_field_rejected(tmp_path):
    path = _write_config(tmp_path, {"unknown_field": 1})
    with pytest.raises(ConfigError) as info:
        load_config(path)
    assert "未知配置字段" in str(info.value)


def test_unknown_override_rejected(tmp_path, monkeypatch):
    _use_missing_default(tmp_path, monkeypatch)
    with pytest.raises(ConfigError):
        load_config(None, {"nope": 1})


def test_invalid_json_rejected(tmp_path):
    path = tmp_path / "camera.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError) as info:
        load_config(path)
    assert "JSON" in str(info.value)


def test_missing_file_reports_chinese_error(tmp_path):
    with pytest.raises(ConfigError) as info:
        load_config(tmp_path / "absent.json")
    assert "不存在" in str(info.value)


@pytest.mark.parametrize("overrides", [
    {"port": 80},
    {"port": 70000},
    {"port": "8080"},
    {"width": 63},
    {"width": 1280.0},
    {"width": 1281},
    {"width": 4610},
    {"height": 62},
    {"height": 721},
    {"fps": 0},
    {"fps": 61},
    {"fps": True},
    {"jpeg_quality": 49},
    {"jpeg_quality": 96},
    {"max_clients": 0},
    {"max_clients": 17},
    {"open_attempts": 0},
    {"open_attempts": 21},
    {"retry_backoff_seconds": 0.05},
    {"retry_backoff_seconds": 61},
    {"retry_backoff_seconds": 5, "max_backoff_seconds": 1},
    {"max_backoff_seconds": 301},
    {"frame_stale_seconds": 0.4},
    {"frame_stale_seconds": 61},
    {"autofocus": "auto"},
    {"autofocus": "Continuous"},
    {"log_level": "TRACE"},
    {"log_level": "info"},
    {"log_level": "WARN"},
])
def test_invalid_values_rejected(tmp_path, monkeypatch, overrides):
    _use_missing_default(tmp_path, monkeypatch)
    with pytest.raises(ConfigError):
        load_config(None, overrides)


def test_manual_autofocus_lens_position(tmp_path, monkeypatch):
    _use_missing_default(tmp_path, monkeypatch)
    config = load_config(None, {"autofocus": "manual", "lens_position": 8})
    assert config["autofocus"] == "manual"
    assert config["lens_position"] == 8
    with pytest.raises(ConfigError):
        load_config(None, {"autofocus": "manual", "lens_position": 40})
    with pytest.raises(ConfigError):
        load_config(None, {"autofocus": "manual", "lens_position": -1})


def test_env_config_path(tmp_path, monkeypatch):
    path = _write_config(tmp_path, {"port": 8200})
    monkeypatch.setenv("PI_CAMERA_CONFIG", str(path))
    monkeypatch.setattr(device_config, "default_config_path", lambda: tmp_path / "other.json")
    config = load_config()
    assert config["port"] == 8200


def test_explicit_path_beats_env(tmp_path, monkeypatch):
    env_path = _write_config(tmp_path, {"port": 8200})
    explicit = tmp_path / "explicit.json"
    explicit.write_text(json.dumps({"port": 8300}), encoding="utf-8")
    monkeypatch.setenv("PI_CAMERA_CONFIG", str(env_path))
    assert load_config(explicit)["port"] == 8300
