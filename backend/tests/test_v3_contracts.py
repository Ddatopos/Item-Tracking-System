"""第三版增量：可用类别、四类状态、CSV 容错与事务边界。"""
import cv2
import numpy as np
import pytest
from tracking.app_factory import create_app
from tracking.repository import CSVRowError
from manage import migrate
from conftest import wait_for
from test_repository import LEGACY


BAD = 'bad,cup,"[1,2,3,4]",bad.jpg\n'
MIXED = LEGACY + '\n' + BAD + '2026-03-05 10:01:00,bag,"[1,2,3,4]",bag.jpg\n'


def test_model_classes_are_not_history(client, runtime):
    runtime.repository.import_csv(LEGACY.replace(",cup,", ",backpack,"))
    assert client.get("/api/items").json == ["backpack"]
    assert client.get("/api/model/classes").json == {
        "model_version": "fake-demo-1", "available": True, "simulated": True, "classes": ["cup"],
    }
    assert runtime.detector.calls == 0


def test_unconfigured_model_class_response(tmp_path):
    app = create_app({"DATA_DIR": tmp_path, "TESTING": True})
    try:
        client = app.test_client()
        assert client.get("/api/model/classes").json == {
            "model_version": "not-configured", "available": False, "simulated": False, "classes": [],
        }
        assert client.post("/api/inference/start").status_code == 409
    finally:
        app.extensions["runtime"].shutdown()


def test_service_camera_preview_inference_are_independent(client, runtime):
    health = client.get("/api/health").json
    assert health["service_status"] == "ok" and health["status"] == "offline"
    assert health["stream"]["status"] == "stopped"
    assert client.post("/api/stream/start").status_code == 200
    wait_for(lambda: client.get("/api/status").json["camera_state"] == "online")
    assert client.post("/api/inference/start").status_code == 200
    wait_for(lambda: client.get("/api/health").json["inference"]["status"] == "inferencing")
    assert client.post("/api/stream/stop").status_code == 200
    health = client.get("/api/health").json
    assert (health["service_status"], health["status"], health["stream"]["status"], health["inference"]["status"]) == (
        "ok", "online", "stopped", "inferencing")
    assert client.post("/api/inference/stop").status_code == 200
    assert client.get("/api/health").json["inference"]["status"] == "stopped"
    assert runtime.camera.opens == 1


def upload(client, text, query=""):
    return client.post("/api/events/import" + query, data=text.encode("utf-8"), content_type="text/csv")


def test_csv_default_strict_rolls_back_and_reports_line(client, runtime):
    reply = upload(client, MIXED)
    assert reply.status_code == 400
    assert reply.json["rows"] == 3 and reply.json["inserted"] == 0
    assert reply.json["errors"][0]["line"] == 4 and reply.json["errors"][0]["reason"]
    assert runtime.repository.events()[1] == 0


def test_csv_tolerant_distinguishes_valid_duplicates_and_errors(client, runtime):
    for inserted, skipped in [(2, 0), (0, 2)]:
        reply = upload(client, MIXED, "?mode=skip_invalid")
        assert reply.status_code == 200
        assert (reply.json["rows"], reply.json["inserted"], reply.json["skipped"]) == (3, inserted, skipped)
        assert reply.json["errors"][0]["line"] == 4 and len(reply.json["errors"]) == 1
    assert runtime.repository.items() == ["bag", "cup"]


def test_csv_tolerant_all_invalid_and_invalid_mode(client, runtime):
    reply = upload(client, LEGACY.splitlines(keepends=True)[0] + BAD, "?mode=skip_invalid")
    assert reply.status_code == 200
    assert reply.json["inserted"] == reply.json["skipped"] == 0
    assert reply.json["rows"] == 1 and reply.json["errors"][0]["line"] == 2
    assert upload(client, LEGACY, "?mode=other").status_code == 400
    assert upload(client, LEGACY + '"unclosed\n', "?mode=skip_invalid").status_code == 400
    assert runtime.repository.events()[1] == 0


def test_csv_tolerant_reports_physical_line_after_multiline_record(runtime):
    header = LEGACY.splitlines(keepends=True)[0].strip() + ',room\n'
    record = LEGACY.splitlines(keepends=True)[1].strip() + ',"楼上\n客厅"\n'
    result = runtime.repository.import_csv(header + record + '\n' + BAD, "skip_invalid")
    assert result["inserted"] == 1 and result["errors"][0]["line"] == 5


def test_migration_strict_preserves_files_then_tolerant_imports(runtime, tmp_path):
    source = tmp_path / "legacy"
    (source / "data").mkdir(parents=True)
    (source / "images").mkdir()
    (source / "data" / "recognition.csv").write_text(MIXED, encoding="utf-8-sig")
    ok, image = cv2.imencode(".jpg", np.zeros((10, 10, 3), dtype=np.uint8))
    assert ok
    for name in ("capture.jpg", "bad.jpg", "bag.jpg"):
        (source / "images" / name).write_bytes(image.tobytes())
    repo = runtime.repository
    with pytest.raises(CSVRowError, match="CSV row 4"):
        migrate(repo, source)
    assert repo.events()[1] == 0 and not list((repo.root / "images").glob("*.jpg"))
    result = migrate(repo, source, "skip_invalid")
    assert result["inserted"] == 2 and result["errors"][0]["line"] == 4
    assert not (repo.root / "images/bad.jpg").exists()
    for event in repo.events()[0]:
        assert (repo.root / event["raw_image_path"]).is_file()
        assert (repo.root / event["annotated_image_path"]).is_file()
    assert migrate(repo, source, "skip_invalid")["skipped"] == 2
