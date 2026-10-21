"""基于神经网络的物品示踪系统 V1.0：无摄像头副作用的 Flask 应用工厂。"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import uuid
from urllib.parse import urlsplit
from flask import Flask, abort, g, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
from .adapters import MockCamera, OpenCVCamera, UnavailableDetector
from .api import api
from .config import load_config
from .repository import Repository, safe_path
from .runtime import RuntimeManager, RuntimeConflict


def create_app(config=None, *, camera=None, detector=None):
    values = load_config(config)
    app = Flask(__name__, static_folder=None)
    app.config.update(values)
    app.json.ensure_ascii = False
    repo = Repository(values["DATA_DIR"])
    camera = camera if camera is not None else (MockCamera() if values["CAMERA_KIND"] == "mock" else OpenCVCamera(values["CAMERA_SOURCE"]))
    detector = detector if detector is not None else UnavailableDetector()
    runtime = RuntimeManager(values, repo, camera, detector)
    app.extensions["runtime"] = runtime
    app.register_blueprint(api)

    @app.before_request
    def local_request_guard():
        g.request_id = uuid.uuid4().hex
        # 防 DNS rebinding；仅允许本机访问。桌面壳或同源前端无需 CORS。
        if request.host.split(":")[0].lower() not in {"localhost", "127.0.0.1"}:
            abort(403, description="local host only")
        if request.remote_addr not in {None, "127.0.0.1", "::1"}:
            abort(403, description="loopback clients only")
        origin = request.headers.get("Origin")
        if origin:
            parts = urlsplit(origin)
            if parts.hostname not in {"localhost", "127.0.0.1"} or parts.scheme not in {"http", "https"}:
                abort(403, description="untrusted browser origin")
            if request.method not in {"GET", "HEAD", "OPTIONS"} and parts.netloc != request.host and origin not in values["TRUSTED_ORIGINS"]:
                abort(403, description="control requests require the same origin")

    @app.after_request
    def headers(response):
        response.headers["X-Request-Id"] = getattr(g, "request_id", "")
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    def error(code, message, status):
        return jsonify(error={"code": code, "message": message, "request_id": getattr(g, "request_id", "")}, message=message), status

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return error(exc.name.lower().replace(" ", "_"), exc.description, exc.code)

    @app.errorhandler(ValueError)
    def invalid_input(exc):
        return error("invalid_request", str(exc), 400)

    @app.errorhandler(RuntimeConflict)
    def conflict(exc):
        return error("runtime_conflict", str(exc), 409)

    @app.errorhandler(Exception)
    def internal_error(exc):
        app.logger.exception("Unhandled request error")
        return error("internal_error", "internal operation failed; inspect local logs", 500)

    # 生产时将现有 React 构建输出放到同源，保留前端代码，不额外引入页面实现。
    if values["FRONTEND_DIR"]:
        frontend = Path(values["FRONTEND_DIR"]).resolve()
        if not (frontend / "index.html").is_file():
            runtime.shutdown()
            raise ValueError("FRONTEND_DIR needs a compiled index.html")

        @app.get("/ui/")
        @app.get("/ui/<path:filename>")
        def ui(filename="index.html"):
            try:
                path = safe_path(frontend, filename)
            except ValueError:
                abort(404)
            if not path.is_file():
                abort(404)
            return send_from_directory(frontend, filename)

        @app.get("/static/<path:filename>")
        def frontend_static(filename):
            return send_from_directory(frontend / "static", filename)

    return app


def configure_logging(data_dir):
    folder = Path(data_dir) / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(folder / "backend.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()], force=True)
