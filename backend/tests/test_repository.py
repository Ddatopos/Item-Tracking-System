"""基于神经网络的物品示踪系统 V1.0：去重、CSV、完整备份恢复和数据目录锁。"""
import csv
from dataclasses import replace
import io
import json
from pathlib import Path
import time
import uuid
import zipfile
import pytest
from tracking.contracts import DetectionEvent, timestamp
from tracking.config import DEFAULT_SETTINGS
from tracking.process_lock import DataDirectoryLock
from tracking.repository import Repository, safe_path
from manage import backup, migrate, restore
from conftest import wait_for

LEGACY = 'timestamp,class_name,location,image_id\n2026-03-05 10:00:00,cup,"[1,2,3,4]",capture.jpg\n'


def example(when="2026-10-18T01:00:00Z", **changes):
    return replace(DetectionEvent(str(uuid.uuid4()), "1", "camera-1", "客厅", "cup", .8, [1, 2, 3, 4], timestamp(when), "fake-test"), **changes)


def test_event_session_dedup_and_gap(runtime):
    repo = runtime.repository
    save = lambda e: ("", "")
    first, created = repo.record(example(), DEFAULT_SETTINGS, save)
    assert created
    second, created = repo.record(example("2026-10-18T01:00:10Z"), DEFAULT_SETTINGS, save)
    assert first == second and not created
    row = repo.event(first)
    assert row["observations"] == 2 and row["first_seen"] < row["last_seen"]
    third, created = repo.record(example("2026-10-18T01:01:00Z"), DEFAULT_SETTINGS, save)
    assert created and third != first
    assert repo.events()[1] == 2


def test_camera_and_class_separate_events(runtime):
    repo = runtime.repository
    save = lambda e: ("", "")
    for change in [{}, {"camera_id": "camera-2"}, {"class_name": "backpack"}, {"room": "卧室"}]:
        repo.record(example(**change), DEFAULT_SETTINGS, save)
    assert repo.events()[1] == 4
    assert repo.events(camera_id="camera-2")[1] == 1
    assert repo.events(category="backpack")[1] == 1


def test_duplicate_upstream_event_id_cannot_overwrite_other_class(runtime):
    event = example()
    runtime.repository.record(event, DEFAULT_SETTINGS, lambda e: ("", ""))
    with pytest.raises(ValueError):
        runtime.repository.record(replace(event, class_name="backpack"), DEFAULT_SETTINGS, lambda e: ("", ""))
    assert runtime.repository.items() == ["cup"]


def test_live_dedup_keeps_two_images_only(runtime):
    runtime.start_inference()
    wait_for(lambda: runtime.status()["events_merged"] >= 4)
    runtime.stop_inference()
    assert runtime.repository.events()[1] == 1
    assert len(list(runtime.config["DATA_DIR"].glob("images/*.jpg"))) == 1
    assert len(list(runtime.config["DATA_DIR"].glob("processed_images/*.jpg"))) == 1


def test_legacy_csv_idempotent_and_timezone(runtime):
    repo = runtime.repository
    assert repo.import_csv(LEGACY) == {"rows": 1, "inserted": 1, "skipped": 0}
    assert repo.import_csv(LEGACY)["skipped"] == 1
    row = repo.events()[0][0]
    assert row["captured_at"] == "2026-03-05T02:00:00.000+00:00"
    assert row["model_version"] == "legacy-csv"
    assert row["raw_image_path"] == "images/capture.jpg"


def test_csv_export_import_full_fidelity(runtime, tmp_path):
    repo = runtime.repository
    repo.record(example(), DEFAULT_SETTINGS, lambda e: ("images/a.jpg", "processed_images/b.jpg"))
    text = repo.export_csv()
    target = Repository(tmp_path / "other")
    try:
        assert target.import_csv(text)["inserted"] == 1
        assert target.events()[0] == repo.events()[0]
        assert target.import_csv(text)["skipped"] == 1
    finally:
        target.close()


@pytest.mark.parametrize("text", ["wrong\n1", LEGACY + 'bad,cup,"[1,2,3,4]",test.jpg\n',
    LEGACY.replace("[1,2,3,4]", "[4,3,1,2]"), LEGACY.replace("[1,2,3,4]", "__import__('os').system('x')"),
    LEGACY.replace("capture.jpg", "../../outside.jpg")])
def test_csv_rejects_bad_input_atomically(runtime, text):
    with pytest.raises(ValueError):
        runtime.repository.import_csv(text)
    assert runtime.repository.events()[1] == 0


def test_csv_api_import_and_export(client):
    assert client.post("/api/events/import", data=LEGACY.encode(), content_type="text/csv").json["inserted"] == 1
    exported = client.get("/api/events/export")
    assert exported.status_code == 200 and "text/csv" in exported.content_type
    assert "event_id" in exported.data.decode("utf-8-sig")
    assert client.post("/api/events/import", data=b"\xff", content_type="text/csv").status_code == 400


def test_legacy_migration_copies_images_and_boxes(runtime, tmp_path):
    import cv2
    import numpy as np
    source = tmp_path / "legacy"
    (source / "data").mkdir(parents=True)
    (source / "images").mkdir()
    (source / "data" / "recognition.csv").write_text(LEGACY, encoding="utf-8")
    ok, image = cv2.imencode(".jpg", np.zeros((10, 10, 3), dtype=np.uint8))
    (source / "images" / "capture.jpg").write_bytes(image.tobytes())
    result = migrate(runtime.repository, source)
    assert result["inserted"] == 1
    row = runtime.repository.events()[0][0]
    assert (runtime.config["DATA_DIR"] / row["raw_image_path"]).is_file()
    assert (runtime.config["DATA_DIR"] / row["annotated_image_path"]).is_file()


def test_backup_restore_includes_database_settings_and_images(runtime, tmp_path):
    runtime.start_inference()
    wait_for(lambda: runtime.status()["events_created"])
    runtime.stop()
    before = runtime.repository.events()[0]
    destination = tmp_path.parent / (tmp_path.name + "-backup.zip")
    recovery = tmp_path / "recovered"
    try:
        assert backup(runtime.repository, destination)["files"] >= 3
        restore(destination, recovery)
        other = Repository(recovery)
        try:
            assert other.events()[0] == before
            assert other.get_settings() == runtime.get_settings()
            assert safe_path(recovery, before[0]["raw_image_path"]).is_file()
        finally:
            other.close()
        with pytest.raises(ValueError):
            restore(destination, recovery)
    finally:
        destination.unlink(missing_ok=True)


def test_restore_rejects_traversal_and_bad_hash(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("tracking.sqlite3", b"bad")
        z.writestr("../escape.jpg", b"bad")
        z.writestr("manifest.json", json.dumps({"tracking.sqlite3": "x", "../escape.jpg": "x"}))
    with pytest.raises(ValueError):
        restore(archive, tmp_path / "recovered")
    assert not (tmp_path / "recovered").exists()


def test_data_directory_lock_prevents_second_process_owner(tmp_path):
    with DataDirectoryLock(tmp_path):
        with pytest.raises(RuntimeError):
            DataDirectoryLock(tmp_path)
    with DataDirectoryLock(tmp_path):
        pass


def test_future_schema_is_not_downgraded(tmp_path):
    import sqlite3
    db = sqlite3.connect(tmp_path / "tracking.sqlite3")
    db.execute("PRAGMA user_version=99")
    db.close()
    with pytest.raises(ValueError):
        Repository(tmp_path)
    db = sqlite3.connect(tmp_path / "tracking.sqlite3")
    try:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 99
    finally:
        db.close()


@pytest.mark.parametrize("name", ["../secret.jpg", "C:/secret.jpg", "..\\secret.jpg", "/secret.jpg"])
def test_safe_path_rejects_outside_root(tmp_path, name):
    with pytest.raises(ValueError):
        safe_path(tmp_path, name)
