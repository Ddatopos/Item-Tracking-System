"""基于神经网络的物品示踪系统 V1.0：兼容旧查询的运行 API。"""
from pathlib import Path
from urllib.parse import quote
from flask import Blueprint, Response, abort, current_app, jsonify, request, send_file
from .contracts import timestamp
from .repository import safe_path
from .runtime import RuntimeConflict
from . import APP_NAME, VERSION

api = Blueprint("api", __name__)


def services():
    runtime = current_app.extensions["runtime"]
    if runtime.closed or runtime.closing:
        raise RuntimeConflict("runtime is shut down")
    return runtime, runtime.repository


def image_url(relative, event_id=None, annotated=False):
    if not relative:
        return None
    if event_id:
        return "/api/events/" + quote(event_id, safe="") + ("/annotation" if annotated else "/image")
    return "/media/" + quote(relative, safe="/")


def item_result(category, repo):
    rows, _ = repo.events(category=category, limit=1)
    if not rows:
        abort(404, description="item not found")
    row = rows[0]
    return {"category": category, "image_path": image_url(row["raw_image_path"], row["event_id"]),
            "processed_image_path": image_url(row["annotated_image_path"], row["event_id"], True),
            "timestamp": row["last_seen"], "event_id": row["event_id"],
            "room": row["room"], "camera_id": row["camera_id"], "bbox": row["bbox"],
            "confidence": row["confidence"], "model_version": row["model_version"]}


@api.get("/api/health")
def health():
    runtime = current_app.extensions["runtime"]
    state = runtime.status()
    online = state["camera_state"] == "online"
    preview_state = "playing" if online and runtime.preview_enabled else "stopped"
    inference_state = {"running": "inferencing", "starting": "idle", "waiting_for_frame": "idle", "stopping": "stopped"}.get(state["inference_state"], state["inference_state"])
    with runtime.condition:
        frame = runtime.latest
        resolution = f"{frame.width}x{frame.height}" if frame else "unknown"
    return jsonify(name=APP_NAME, version=VERSION, service_status="shutdown" if runtime.closed else "ok", state=runtime.state,
                   status="online" if online else ("connecting" if state["camera_state"] == "connecting" else "offline"),
                   cameras=[{"camera_id": runtime.config["CAMERA_ID"], "room": runtime.config["ROOM"], "status": "online" if online else "offline", "source_type": runtime.camera.source_type, "resolution": resolution}],
                   stream={"preview_url": "/api/stream/preview", "status": preview_state},
                   inference={"status": inference_state, "model_version": runtime.detector.model_version, "fps": state["inference_fps"]})


@api.get("/api/status")
def status():
    return jsonify(current_app.extensions["runtime"].status())


@api.get("/api/cameras")
def cameras():
    runtime, repo = services()
    return jsonify(cameras=repo.cameras(), active_camera_id=runtime.config["CAMERA_ID"], state=runtime.status()["camera_state"])


@api.post("/api/runtime/start")
def runtime_start():
    runtime, _ = services()
    changed = runtime.start()
    return jsonify(changed=changed, status=runtime.status())


@api.post("/api/runtime/stop")
def runtime_stop():
    runtime, _ = services()
    runtime.stop()
    return jsonify(status=runtime.status())


@api.post("/api/inference/start")
def inference_start():
    runtime, _ = services()
    changed = runtime.start_inference()
    return jsonify(changed=changed, status=runtime.status())


@api.post("/api/inference/stop")
def inference_stop():
    runtime, _ = services()
    runtime.stop_inference()
    return jsonify(status=runtime.status())


@api.route("/api/settings", methods=["GET", "PUT", "PATCH"])
def settings():
    runtime, _ = services()
    if request.method != "GET":
        values = request.get_json()
        if not isinstance(values, dict):
            raise ValueError("settings must be a JSON object")
        values = dict(values)
        for readonly, active in [("model", runtime.detector.model_version), ("camera_id", runtime.config["CAMERA_ID"])]:
            if readonly in values and values.pop(readonly) != active:
                raise ValueError(f"{readonly} is read-only; configure the adapter when starting the process")
        for old, new in [("confidence", "confidence_threshold"), ("inference_frequency", "inference_fps")]:
            if old in values:
                value = values.pop(old)
                if new in values and values[new] != value:
                    raise ValueError(f"conflicting {old} and {new}")
                values[new] = value
        if "category" in values:
            category = values.pop("category")
            if not isinstance(category, str):
                raise ValueError("category must be a string")
            selected = [] if category == "all" else [category]
            if "selected_classes" in values and values["selected_classes"] != selected:
                raise ValueError("conflicting category and selected_classes")
            values["selected_classes"] = selected
        runtime.update_settings(values)
    result = runtime.get_settings()
    # 多类别使用 selected_classes；category 仅供旧单类别页面。
    return jsonify(**result, category=result["selected_classes"][0] if len(result["selected_classes"]) == 1 else "all",
                   confidence=result["confidence_threshold"], inference_frequency=result["inference_fps"],
                   model=runtime.detector.model_version, camera_id=runtime.config["CAMERA_ID"])


@api.get("/api/stream")
@api.get("/api/preview")
@api.get("/api/stream/preview")
def stream():
    runtime, _ = services()
    generation = runtime.reserve_preview()
    response = Response(runtime.stream(generation), content_type="multipart/x-mixed-replace; boundary=frame")
    # 即使请求在第一次迭代前断开，也释放已占用的客户端名额。
    response.call_on_close(runtime.release_preview)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@api.post("/api/stream/start")
def preview_start():
    runtime, _ = services()
    runtime.set_preview(True)
    return jsonify(status=runtime.status())


@api.post("/api/stream/stop")
def preview_stop():
    runtime, _ = services()
    runtime.set_preview(False)
    return jsonify(status=runtime.status())


@api.get("/api/snapshot")
@api.get("/snapshot")
def snapshot():
    runtime, _ = services()
    frame, data = runtime.frame()
    if frame is None:
        abort(503, description="no fresh camera frame; start runtime and check camera status")
    return Response(data, content_type="image/jpeg", headers={"Cache-Control": "no-store", "X-Frame-Id": str(frame.frame_id), "X-Captured-At": frame.captured_at})


def event_filters():
    def integer(name, default, lo, hi):
        value = int(request.args.get(name, default))
        if not lo <= value <= hi:
            raise ValueError(f"{name} must be between {lo} and {hi}")
        return value
    since = timestamp(request.args["since"]) if "since" in request.args else None
    until = timestamp(request.args["until"]) if "until" in request.args else None
    if since and until and since > until:
        raise ValueError("since must not exceed until")
    return dict(category=request.args.get("class_name", request.args.get("category")), camera_id=request.args.get("camera_id"), since=since, until=until,
                limit=integer("limit", 100, 1, 1000), offset=integer("offset", 0, 0, 10000000))


@api.get("/api/events")
def events():
    _, repo = services()
    filters = event_filters()
    rows, count = repo.events(**filters)
    for row in rows:
        row["image_url"], row["annotated_image_url"] = image_url(row["raw_image_path"], row["event_id"]), image_url(row["annotated_image_path"], row["event_id"], True)
    if request.args.get("envelope") == "1":
        return jsonify(events=rows, total=count, limit=filters["limit"], offset=filters["offset"])
    return jsonify(rows)


@api.get("/api/events/<event_id>")
def event(event_id):
    _, repo = services()
    row = repo.event(event_id)
    if row is None:
        abort(404, description="event not found")
    return jsonify(row)


@api.get("/api/events/<event_id>/image")
@api.get("/api/events/<event_id>/annotation")
def event_image(event_id):
    runtime, repo = services()
    # 查询最后出现到请求图片之间可能发生代表帧更新；稳定事件 URL 总是读取当前代表图。
    with repo.lock:
        row = repo.event(event_id)
        field = "annotated_image_path" if request.path.endswith("/annotation") else "raw_image_path"
        if not row or not row[field]:
            abort(404, description="event image not found")
        try:
            path = safe_path(repo.root, row[field])
            if path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                abort(404)
            data = path.read_bytes()
        except (ValueError, FileNotFoundError):
            abort(404, description="event image not found")
    return Response(data, content_type="image/png" if path.suffix.lower() == ".png" else "image/jpeg", headers={"Cache-Control": "no-store"})


@api.get("/api/events/export")
def export_csv():
    _, repo = services()
    return Response("\ufeff" + repo.export_csv(), content_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=events.csv", "Cache-Control": "no-store"})


@api.post("/api/events/import")
def import_csv():
    _, repo = services()
    if request.mimetype != "text/csv":
        abort(415, description="upload UTF-8 CSV with Content-Type text/csv")
    try:
        text = request.get_data().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8") from exc
    return jsonify(repo.import_csv(text))


@api.get("/api/items")
def items():
    return jsonify(services()[1].items())


@api.get("/api/items/<path:category>")
def item(category):
    return jsonify(item_result(category, services()[1]))


@api.get("/api/search")
def search():
    category = request.args.get("item_name")
    if not category:
        raise ValueError("item_name is required")
    result = item_result(category, services()[1])
    legacy = {"item_name": category, "timestamp": result["timestamp"], "image_url": result["image_path"], "processed_image_url": result["processed_image_path"], "location": result["bbox"]}
    return jsonify(success=True, items=legacy, **{"items:": legacy})


@api.get("/images/<path:filename>")
def legacy_image(filename):
    return media("images/" + filename)


@api.get("/processed/<path:filename>")
def legacy_processed(filename):
    return media("processed_images/" + filename)


@api.get("/media/<path:filename>")
def media(filename):
    runtime, _ = services()
    parts = Path(filename).parts
    if not parts or parts[0] not in {"images", "processed_images"}:
        abort(404)
    try:
        path = safe_path(runtime.config["DATA_DIR"], filename)
    except ValueError:
        abort(404)
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png"} or not path.is_file():
        abort(404)
    try:
        return send_file(path, conditional=True, max_age=0)
    except FileNotFoundError:
        abort(404, description="image was replaced; use stable event image URL")


@api.post("/api/shutdown")
def shutdown():
    runtime = current_app.extensions["runtime"]
    runtime.shutdown()
    callback = current_app.extensions.get("shutdown_server")
    if callback:
        # 响应有机会发送，再由主线程关闭 Waitress。
        import threading
        timer = threading.Timer(.5, callback)
        timer.daemon = True
        timer.start()
    return jsonify(status=runtime.status(), server_exit_scheduled=bool(callback))


@api.get("/")
def index():
    return jsonify(name=APP_NAME, version=VERSION, usage="POST /api/runtime/start then GET /api/preview", status="/api/status", docs="docs/API.md")
