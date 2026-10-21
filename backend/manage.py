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
from tracking.repository import Repository, safe_path


def migrate(repo, source):
    source = Path(source).resolve()
    data = (source / "data" / "recognition.csv").read_text(encoding="utf-8-sig")
    # 只导入 CSV 引用的安全图片；不信任 CSV 里的相对路径。
    import csv
    import io
    import json as json_module
    pending = []
    for row in csv.DictReader(io.StringIO(data)):
        name = row["image_id"]
        if not name or Path(name).name != name or "\\" in name or ":" in name:
            raise ValueError("legacy image_id must be a filename")
        original = safe_path(source / "images", name)
        target = safe_path(repo.root, "images/" + name)
        if original.is_file() and original.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != original.read_bytes():
                raise ValueError("legacy image filename conflicts with existing data")
            shutil.copy2(original, target)
            image = cv2.imdecode(np.frombuffer(original.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is not None:
                x1, y1, x2, y2 = map(int, json_module.loads(row["location"]))
                cv2.rectangle(image, (x1, y1), (x2, y2), (0, 0, 255), 3)
                boxed = safe_path(repo.root, "processed_images/boxed_" + name)
                boxed.parent.mkdir(parents=True, exist_ok=True)
                ok, encoded = cv2.imencode(boxed.suffix, image)
                if ok:
                    boxed.write_bytes(encoded.tobytes())
                    row["annotated_image_path"] = "processed_images/boxed_" + name
        pending.append(row)
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=["timestamp", "class_name", "location", "image_id", "annotated_image_path"])
    writer.writeheader()
    writer.writerows(pending)
    return repo.import_csv(out.getvalue())


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
                with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                    for path in (root / "logs").glob("*.log*"):
                        archive.write(path, path.name)
                result = {"logs": str(output)}
            else:
                repo = Repository(root)
                try:
                    if args.command == "migrate-legacy":
                        result = migrate(repo, args.source_backend)
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
    main()
