"""基于神经网络的物品示踪系统 V1.0：SQLite 存储、会话去重和 CSV 兼容。"""
import csv
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import threading
import uuid
from dataclasses import asdict, replace
from .contracts import DetectionEvent, timestamp, seconds_between
from .config import DEFAULT_SETTINGS, validate_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS cameras (
 camera_id TEXT PRIMARY KEY, room TEXT NOT NULL, source_type TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
 key TEXT PRIMARY KEY, value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS detection_events (
 event_id TEXT PRIMARY KEY, frame_id TEXT NOT NULL,
 camera_id TEXT NOT NULL REFERENCES cameras(camera_id), room TEXT NOT NULL,
 class_name TEXT NOT NULL, confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
 bbox TEXT NOT NULL, captured_at TEXT NOT NULL, model_version TEXT NOT NULL,
 raw_image_path TEXT NOT NULL, annotated_image_path TEXT NOT NULL,
 first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
 observations INTEGER NOT NULL DEFAULT 1, inference_params TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_lookup ON detection_events(camera_id,class_name,last_seen DESC);
CREATE INDEX IF NOT EXISTS events_time ON detection_events(last_seen DESC);
PRAGMA user_version=1;
"""

CSV_REQUIRED_FIELDS = {"timestamp", "class_name", "location", "image_id"}
CSV_MODES = ("strict", "skip_invalid")


class CSVRowError(ValueError):
    def __init__(self, rows, errors):
        self.rows, self.errors = rows, errors
        first = errors[0]
        super().__init__(f"CSV row {first['line']}: {first['reason']}")


def safe_path(root, name):
    root = Path(root).resolve()
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ValueError("invalid relative file path")
    path = (root / name).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("file must be inside the data directory")
    return path


class Repository:
    def __init__(self, data_dir):
        self.root = Path(data_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.closed = False
        self.db = sqlite3.connect(self.root / "tracking.sqlite3", check_same_thread=False, timeout=5)
        self.db.row_factory = sqlite3.Row
        if self.db.execute("PRAGMA user_version").fetchone()[0] > 1:
            self.db.close()
            raise ValueError("database schema is newer than this backend; use a matching version")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(SCHEMA)
        self.set_settings(self.get_settings())

    def get_settings(self):
        with self.lock:
            rows = self.db.execute("SELECT key,value FROM settings").fetchall()
            return validate_settings({r["key"]: json.loads(r["value"]) for r in rows}, DEFAULT_SETTINGS)

    def set_settings(self, values):
        values = validate_settings(values)
        with self.lock, self.db:
            self.db.executemany("INSERT OR REPLACE INTO settings VALUES (?,?)", [(k, json.dumps(v)) for k, v in values.items()])

    def camera(self, camera_id, room, source_type):
        with self.lock, self.db:
            self.db.execute("INSERT INTO cameras VALUES (?,?,?) ON CONFLICT(camera_id) DO UPDATE SET room=excluded.room,source_type=excluded.source_type", (camera_id, room, source_type))

    def cameras(self):
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM cameras ORDER BY camera_id")]

    @staticmethod
    def decode(row):
        if row is None:
            return None
        data = dict(row)
        data["bbox"] = json.loads(data["bbox"])
        data["inference_params"] = json.loads(data["inference_params"])
        return data

    def record(self, event, params, save_images):
        """同摄像头同类别在间隔窗口内更新一行；每次保存最新代表帧。"""
        event.validate()
        when = timestamp(event.captured_at)
        with self.lock:
            previous = self.db.execute(
                "SELECT * FROM detection_events WHERE camera_id=? AND class_name=? AND room=? ORDER BY last_seen DESC LIMIT 1",
                (event.camera_id, event.class_name, event.room)).fetchone()
            merged = previous is not None and 0 <= seconds_between(when, previous["last_seen"]) <= params["dedup_seconds"]
            if merged:
                event = replace(event, event_id=previous["event_id"])
            elif self.db.execute("SELECT 1 FROM detection_events WHERE event_id=?", (event.event_id,)).fetchone():
                raise ValueError("DetectorService event_id must be unique for a new event")
            # 图片先写入新文件，事务成功后删除被替代图片，避免旧数据库引用半写文件。
            raw, annotated = save_images(event)
            values = asdict(event)
            values.update(captured_at=when, raw_image_path=raw, annotated_image_path=annotated,
                          bbox=json.dumps(list(event.bbox)), first_seen=previous["first_seen"] if merged else when,
                          last_seen=when, observations=previous["observations"] + 1 if merged else 1,
                          inference_params=json.dumps(params))
            try:
                with self.db:
                    self.db.execute("INSERT OR IGNORE INTO cameras VALUES (?,?,?)", (event.camera_id, event.room, "imported"))
                    self._insert(values, update=True)
            except Exception:
                self._delete_images([raw, annotated])
                raise
            if merged:
                self._delete_images([previous["raw_image_path"], previous["annotated_image_path"]])
            return values["event_id"], not merged

    def _delete_images(self, names):
        for name in names:
            if name:
                path = safe_path(self.root, name)
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass  # 崩溃或读文件占用最多遗留无引用图片，可离线清理

    def _insert(self, values, update=False):
        columns = list(values)
        sql = f"INSERT INTO detection_events ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})"
        if update:
            sql += " ON CONFLICT(event_id) DO UPDATE SET " + ",".join(f"{k}=excluded.{k}" for k in columns if k != "event_id")
        else:
            sql += " ON CONFLICT(event_id) DO NOTHING"
        return self.db.execute(sql, list(values.values())).rowcount

    def events(self, category=None, camera_id=None, since=None, until=None, limit=100, offset=0):
        clauses, args = [], []
        for field, value, op in [("class_name", category, "="), ("camera_id", camera_id, "="), ("last_seen", since, ">="), ("last_seen", until, "<=")]:
            if value is not None:
                clauses.append(f"{field} {op} ?")
                args.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.lock:
            count = self.db.execute("SELECT COUNT(*) FROM detection_events" + where, args).fetchone()[0]
            rows = self.db.execute("SELECT * FROM detection_events" + where + " ORDER BY last_seen DESC,event_id LIMIT ? OFFSET ?", args + [limit, offset]).fetchall()
            return [self.decode(r) for r in rows], count

    def event(self, event_id):
        with self.lock:
            return self.decode(self.db.execute("SELECT * FROM detection_events WHERE event_id=?", (event_id,)).fetchone())

    def items(self):
        with self.lock:
            return [r[0] for r in self.db.execute("SELECT DISTINCT class_name FROM detection_events ORDER BY class_name")]

    def export_csv(self):
        output = io.StringIO(newline="")
        fields = ["timestamp", "class_name", "location", "image_id", "event_id", "frame_id", "camera_id", "room", "confidence", "captured_at", "model_version", "raw_image_path", "annotated_image_path", "first_seen", "last_seen", "observations", "inference_params"]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        with self.lock:
            for row in self.db.execute("SELECT * FROM detection_events ORDER BY last_seen,event_id"):
                values = dict(row)
                bbox = values.pop("bbox")
                values.update(timestamp=values["last_seen"], location=bbox, image_id=Path(values["raw_image_path"]).name)
                writer.writerow(values)
        return output.getvalue()

    def _csv_event(self, row):
        when = timestamp(row.get("captured_at") or row["timestamp"])
        raw = row.get("raw_image_path") or ("images/" + row["image_id"] if row["image_id"] else "")
        ann = row.get("annotated_image_path") or ""
        for name in (raw, ann):
            if name:
                safe_path(self.root, name)
        identity = json.dumps([row["timestamp"], row["class_name"], row["location"], row["image_id"]], ensure_ascii=False)
        event_id = row.get("event_id") or str(uuid.uuid5(uuid.NAMESPACE_URL, identity))
        event = DetectionEvent(event_id, str(row.get("frame_id") or "0"), row.get("camera_id") or "legacy-camera",
                               row.get("room") or "历史导入", row["class_name"], float(row.get("confidence") or 1),
                               json.loads(row["location"]), when, row.get("model_version") or "legacy-csv", raw, ann)
        event.validate()
        data = asdict(event)
        data.update(bbox=json.dumps(list(event.bbox)), first_seen=timestamp(row.get("first_seen") or when),
                    last_seen=timestamp(row.get("last_seen") or row["timestamp"]),
                    observations=int(row.get("observations") or 1),
                    inference_params=json.dumps(validate_settings(json.loads(row.get("inference_params") or "{}"))))
        if not 1 <= data["observations"] <= 2**63 - 1 or data["first_seen"] > data["last_seen"]:
            raise ValueError("invalid event interval or observations")
        return data

    def prepare_csv(self, text, mode="strict", *, legacy_prepare=None):
        """仅准备记录，不写数据库；离线旧图片可由调用方在临时目录准备。"""
        if mode not in CSV_MODES:
            raise ValueError("CSV mode must be strict or skip_invalid")
        reader = csv.reader(io.StringIO(text.lstrip("\ufeff"), newline=""), strict=True)
        rows, errors = [], []
        try:
            header = next(reader, [])
            if not CSV_REQUIRED_FIELDS <= set(header) or len(header) != len(set(header)):
                raise ValueError("CSV needs unique columns timestamp,class_name,location,image_id")
            while True:
                line = reader.line_num + 1
                fields = next(reader, None)
                if fields is None:
                    break
                if not fields:  # 空白行不计作记录，物理行号仍继续累加
                    continue
                if len(rows) + len(errors) >= 10000:
                    raise ValueError("CSV exceeds 10000 rows")
                try:
                    row = dict(zip(header, fields))
                    if len(fields) > len(header) or not CSV_REQUIRED_FIELDS <= row.keys():
                        raise ValueError("wrong number of CSV columns")
                    if legacy_prepare is not None:
                        row = {key: row[key] for key in CSV_REQUIRED_FIELDS}
                    data = self._csv_event(row)
                    if legacy_prepare is not None:
                        legacy_prepare(row, data)
                    rows.append(data)
                except (ValueError, TypeError, KeyError, OverflowError) as exc:
                    errors.append({"line": line, "reason": str(exc)})
        except csv.Error as exc:
            # 引号损坏可能吞掉后续物理行，不能可靠重新识别记录边界。
            raise ValueError(f"invalid CSV structure near line {reader.line_num}: {exc}") from exc
        if errors and mode == "strict":
            raise CSVRowError(len(rows) + len(errors), errors)
        return rows, errors

    def commit_csv(self, rows, errors):
        inserted = 0
        with self.lock, self.db:
            for data in rows:
                self.db.execute("INSERT OR IGNORE INTO cameras VALUES (?,?,?)", (data["camera_id"], data["room"], "imported"))
                inserted += self._insert(data)
        return {"inserted": inserted, "skipped": len(rows) - inserted,
                "rows": len(rows) + len(errors), "errors": errors}

    def import_csv(self, text, mode="strict"):
        return self.commit_csv(*self.prepare_csv(text, mode))

    def backup_database(self, destination):
        with self.lock:
            target = sqlite3.connect(destination)
            try:
                self.db.backup(target)
            finally:
                target.close()

    def close(self):
        with self.lock:
            if not self.closed:
                self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self.db.close()
                self.closed = True
