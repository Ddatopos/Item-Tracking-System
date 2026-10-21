"""基于神经网络的物品示踪系统 V1.0：API 合同、安全和兼容性测试。"""
import json
from pathlib import Path
import pytest
from tracking.app_factory import create_app
from conftest import wait_for


def test_health_frontend_contract(client):
    result = client.get("/api/health")
    assert result.status_code == 200
    data = result.json
    assert data["version"] == "1.0.0" and data["service_status"] == "ok"
    assert data["stream"]["preview_url"] == "/api/stream/preview"
    assert set(data["inference"]) == {"status", "model_version", "fps"}
    assert set(data["cameras"][0]) == {"camera_id", "room", "status", "source_type", "resolution"}


def test_items_keep_array_and_old_fields(client, runtime):
    assert client.get("/api/items").json == []
    runtime.start_inference()
    wait_for(lambda: runtime.repository.items())
    assert client.get("/api/items").json == ["cup"]
    data = client.get("/api/items/cup").json
    assert {"category", "image_path", "processed_image_path", "timestamp"} <= data.keys()
    assert client.get(data["image_path"]).status_code == 200
    assert client.get(data["processed_image_path"]).status_code == 200
    assert client.get("/api/search?item_name=cup").json["items:"]["item_name"] == "cup"


def test_image_url_survives_representative_frame_replacement(client, runtime):
    runtime.start_inference()
    wait_for(lambda: runtime.repository.items())
    data = client.get("/api/items/cup").json
    before = runtime.status()["events_merged"]
    wait_for(lambda: runtime.status()["events_merged"] > before + 1)
    assert client.get(data["image_path"]).status_code == 200
    assert client.get(data["processed_image_path"]).status_code == 200


def test_events_array_and_paginated_envelope(client, runtime):
    runtime.start_inference()
    wait_for(lambda: runtime.repository.items())
    rows = client.get("/api/events").json
    assert isinstance(rows, list) and isinstance(rows[0]["frame_id"], str)
    page = client.get("/api/events?envelope=1&class_name=cup&camera_id=camera-1&limit=1").json
    assert page["total"] == 1 and page["limit"] == 1
    row = client.get("/api/events/" + rows[0]["event_id"]).json
    assert row["class_name"] == "cup"
    assert client.get("/api/events?category=absent").json == []
    assert client.get("/api/events?since=2099-01-01T00:00:00Z").json == []


@pytest.mark.parametrize("path,status", [("/api/missing", 404), ("/api/items/missing", 404), ("/api/search", 400),
    ("/api/events/missing", 404), ("/api/events?limit=0", 400), ("/api/events?limit=abc", 400),
    ("/api/events?offset=-1", 400), ("/api/events?since=wrong", 400),
    ("/api/events?since=2026-01-02&until=2026-01-01", 400)])
def test_json_errors(client, path, status):
    response = client.get(path)
    assert response.status_code == status
    assert response.is_json and response.json["error"]["code"]
    assert response.json["error"]["request_id"] == response.headers["X-Request-Id"]


@pytest.mark.parametrize("values", [{"inference_fps": 0}, {"confidence_threshold": True}, {"confidence_threshold": float("nan")},
    {"dedup_seconds": -1}, {"input_size": 33}, {"selected_classes": "cup"}, {"selected_classes": [""]},
    {"arbitrary": 1}, {"camera_id": "other"}, {"model": "unknown"}, [], None])
def test_settings_reject_invalid(client, values):
    response = client.put("/api/settings", data=json.dumps(values), content_type="application/json")
    assert response.status_code == 400


def test_settings_legacy_alias_and_persistence(client, runtime, tmp_path):
    assert client.put("/api/settings", json={"category": "cup", "confidence": .4, "inference_frequency": 3}).status_code == 200
    data = client.get("/api/settings").json
    assert data["selected_classes"] == ["cup"] and data["inference_fps"] == 3
    assert client.put("/api/settings", json=data).status_code == 200
    runtime.shutdown()
    another = create_app({"DATA_DIR": tmp_path})
    try:
        assert another.extensions["runtime"].get_settings()["confidence_threshold"] == .4
    finally:
        another.extensions["runtime"].shutdown()


def test_bad_json_and_wrong_method(client):
    assert client.put("/api/settings", data="{broken", content_type="application/json").status_code == 400
    assert client.get("/api/shutdown").status_code == 405
    assert client.post("/api/events/import", data="x").status_code == 415


def test_missing_detector_returns_conflict(tmp_path):
    app = create_app({"DATA_DIR": tmp_path})
    try:
        result = app.test_client().post("/api/inference/start")
        assert result.status_code == 409
        assert app.extensions["runtime"].capture_thread is None
    finally:
        app.extensions["runtime"].shutdown()


@pytest.mark.parametrize("path", ["/images/../../tracking.sqlite3", "/processed/../../secret.jpg", "/media/tracking.sqlite3",
    "/media/images/../../secret.jpg", "/media/images/..%5C..%5Csecret.jpg", "/media/images/C:/secret.jpg",
    "/media/images/missing.jpg", "/media/images/../logs/secret.txt"])
def test_media_paths_are_restricted(client, path):
    response = client.get(path)
    assert response.status_code == 404 and response.is_json


def test_symlink_escape(client, runtime, tmp_path):
    import os
    import subprocess
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    (outside / "secret.jpg").write_bytes(b"secret")
    link = tmp_path / "images" / "linked"
    link.parent.mkdir(exist_ok=True)
    try:
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                raise
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True)
        assert client.get("/media/images/linked/secret.jpg").status_code == 404
        from tracking.repository import safe_path
        with pytest.raises(ValueError):
            safe_path(tmp_path, "images/linked/new-image.jpg")
    finally:
        if link.exists():
            if link.is_symlink():
                link.unlink()
            else:
                link.rmdir()
        (outside / "secret.jpg").unlink()
        outside.rmdir()


def test_browser_origin_and_host_guards(client):
    assert client.post("/api/runtime/start", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.get("/api/items", headers={"Host": "evil.example"}).status_code == 403
    assert client.post("/api/runtime/start", headers={"Origin": "http://localhost:3000"}).status_code == 403
    assert client.get("/api/status", environ_base={"REMOTE_ADDR": "192.168.1.2"}).status_code == 403
    assert client.post("/api/runtime/start", headers={"Origin": "http://localhost"}).status_code == 200


def test_request_body_size_limit(client):
    response = client.post("/api/events/import", data="x" * (4 * 1024 * 1024 + 1), content_type="text/csv")
    assert response.status_code == 413 and response.is_json


def test_no_debug_or_wildcard_cors(client, app):
    assert not app.debug
    assert "Access-Control-Allow-Origin" not in client.get("/api/health").headers


def test_explicit_development_proxy_origin(tmp_path):
    app = create_app({"DATA_DIR": tmp_path, "TRUSTED_ORIGINS": ["http://localhost:3000"]})
    try:
        client = app.test_client()
        assert client.post("/api/runtime/start", headers={"Host": "localhost:5000", "Origin": "http://localhost:3000"}).status_code == 200
        assert client.post("/api/runtime/stop", headers={"Host": "localhost:5000", "Origin": "http://localhost:3001"}).status_code == 403
    finally:
        app.extensions["runtime"].shutdown()


def test_frontend_static_optional_and_safe(tmp_path):
    build = tmp_path / "build"
    (build / "static").mkdir(parents=True)
    (build / "index.html").write_text("<html>test</html>", encoding="utf-8")
    (build / "static" / "main.js").write_text("console.log('test')", encoding="utf-8")
    app = create_app({"DATA_DIR": tmp_path / "data", "FRONTEND_DIR": str(build)})
    try:
        c = app.test_client()
        assert c.get("/ui/").status_code == 200
        assert c.get("/static/main.js").status_code == 200
        assert c.get("/ui/../../secret.txt").status_code == 404
    finally:
        app.extensions["runtime"].shutdown()
