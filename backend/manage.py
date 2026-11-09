"""基于神经网络的物品示踪系统 V1.0：离线迁移、完整备份、恢复与日志导出。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile
import cv2
import numpy as np
from tracking.config import load_config
from tracking.process_lock import DataDirectoryLock
from tracking.repository import CSV_MODES, CSVRowError, Repository, safe_path


def migrate(repo, source, mode="strict"):
    source = Path(source).resolve()
    text = (source / "data" / "recognition.csv").read_text(encoding="utf-8-sig")
    with tempfile.TemporaryDirectory(dir=repo.root) as temporary:
        staging = Path(temporary)
        pending = {}

        def prepare(row, data):
            name = row["image_id"]
            if not name or Path(name).name != name or "\\" in name or ":" in name:
                raise ValueError("legacy image_id must be a filename")
            original = safe_path(source / "images", name)
            suffix = original.suffix.lower()
            if not original.is_file() or suffix not in {".jpg", ".jpeg", ".png"}:
                return  # 旧记录可没有可用图片
            raw = original.read_bytes()
            images = {safe_path(repo.root, data["raw_image_path"]): raw}
            if repo.event(data["event_id"]) is None:
                image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR) if raw else None
                if image is not None:
                    h, w = image.shape[:2]
                    x1, y1, x2, y2 = (int(min(v, bound - 1)) for v, bound in zip(json.loads(data["bbox"]), (w, h, w, h)))
                    cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 3)
                    ok, encoded = cv2.imencode(suffix, image)
                    if ok:
                        key = hashlib.sha256(data["event_id"].encode()).hexdigest()
                        data["annotated_image_path"] = f"processed_images/legacy-{key}{suffix}"
                        images[safe_path(repo.root, data["annotated_image_path"])] = encoded.tobytes()
            for target, content in images.items():
                existing = pending.get(target, target)
                if existing.exists() and (not existing.is_file() or existing.read_bytes() != content):
                    raise ValueError("legacy image filename conflicts with existing data")
            for target, content in images.items():
                if target not in pending and not target.exists():
                    staged = staging / str(len(pending))
                    staged.write_bytes(content)
                    pending[target] = staged

        rows, errors = repo.prepare_csv(text, mode, legacy_prepare=prepare)
        created = []
        try:
            for target, staged in pending.items():
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as file:
                    created.append(target)
                    with staged.open("rb") as source_file:
                        shutil.copyfileobj(source_file, file)
            return repo.commit_csv(rows, errors)
        except Exception:
            for target in created:
                target.unlink(missing_ok=True)
            raise


def backup(repo, destination):
    destination = Path(destination).resolve()
    if destination.exists() or destination.is_relative_to(repo.root):
        raise ValueError("backup destination must be a new file outside data directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        database = Path(temp) / "tracking.sqlite3"
        repo.backup_database(database)
        files = {"tracking.sqlite3": database}
        for folder in ["images", "processed_images", "logs"]:
            for path in (repo.root / folder).rglob("*"):
                if path.is_file():
                    name = path.relative_to(repo.root).as_posix()
                    safe_path(repo.root, name)
                    files[name] = path
        manifest = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()}
        partial = destination.with_suffix(destination.suffix + ".partial")
        try:
            with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, path in files.items():
                    archive.write(path, name)
                archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            partial.replace(destination)
        finally:
            partial.unlink(missing_ok=True)
    return {"backup": str(destination), "files": len(files)}


def restore(archive_path, destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("restore destination must not exist; restore beside the old directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staging = Path(temporary)
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or "manifest.json" not in names:
                raise ValueError("invalid backup manifest")
            manifest = json.loads(archive.read("manifest.json"))
            if set(names) != set(manifest) | {"manifest.json"} or "tracking.sqlite3" not in manifest:
                raise ValueError("backup entries do not match manifest")
            for name, digest in manifest.items():
                path = safe_path(staging, name)
                if name != "tracking.sqlite3" and Path(name).parts[0] not in {"images", "processed_images", "logs"}:
                    raise ValueError("unsupported backup entry")
                data = archive.read(name)
                if hashlib.sha256(data).hexdigest() != digest:
                    raise ValueError("backup checksum mismatch")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        import sqlite3
        connection = sqlite3.connect(staging / "tracking.sqlite3")
        try:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("database integrity check failed")
        finally:
            connection.close()
        shutil.copytree(staging, destination)
    return {"restored": str(destination), "files": len(manifest)}


def main():
    parser = argparse.ArgumentParser(description="基于神经网络的物品示踪系统 V1.0 数据维护")
    parser.add_argument("--data-dir", default=str(load_config()["DATA_DIR"]))
    sub = parser.add_subparsers(dest="command", required=True)
    migration = sub.add_parser("migrate-legacy")
    migration.add_argument("--source-backend", default=str(Path(__file__).parent))
    migration.add_argument("--mode", choices=CSV_MODES, default="strict")
    save = sub.add_parser("backup")
    save.add_argument("--output", required=True)
    recover = sub.add_parser("restore")
    recover.add_argument("--archive", required=True)
    recover.add_argument("--destination", required=True)
    export = sub.add_parser("export-csv")
    export.add_argument("--output", required=True)
    logs = sub.add_parser("export-logs")
    logs.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "restore":
        result = restore(args.archive, args.destination)
    else:
        root = Path(args.data_dir).resolve()
        with DataDirectoryLock(root):
            if args.command == "export-logs":
                output = Path(args.output).resolve()
                if output.exists() or output.is_relative_to(root):
                    raise ValueError("choose a new log archive outside data directory")
                output.parent.mkdir(parents=True, exist_ok=True)
                paths = [safe_path(root, "logs/" + path.name) for path in (root / "logs").glob("*.log*") if path.is_file()]
                with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
                    for path in paths:
                        archive.write(path, path.name)
                result = {"logs": str(output)}
            else:
                repo = Repository(root)
                try:
                    if args.command == "migrate-legacy":
                        try:
                            result = migrate(repo, args.source_backend, args.mode)
                        except CSVRowError as exc:
                            print(json.dumps({"inserted": 0, "skipped": 0, "rows": exc.rows,
                                              "errors": exc.errors}, ensure_ascii=False))
                            return 2
                    elif args.command == "backup":
                        result = backup(repo, args.output)
                    else:
                        output = Path(args.output)
                        with output.open("x", encoding="utf-8-sig", newline="") as file:
                            file.write(repo.export_csv())
                        result = {"csv": str(output.resolve())}
                finally:
                    repo.close()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
