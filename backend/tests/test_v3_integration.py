"""用本机网络流和独立进程验收接入、生命周期与离线维护。"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener
import zipfile

import cv2
import numpy as np

from tracking.adapters import FakeDetector, OpenCVCamera
from tracking.app_factory import create_app
from conftest import wait_for


def test_opencv_loopback_mjpeg_disconnect_and_reconnect(tmp_path):
    """实际通过 FFmpeg/OpenCV 读取 HTTP；视频内容与断线均由本机模拟。"""
    ok, image = cv2.imencode(".jpg", np.full((90, 160, 3), (24, 64, 128), dtype=np.uint8))
    assert ok
    jpeg = image.tobytes()
    part = b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n"
    enabled, closing = threading.Event(), threading.Event()
    accepted = []

    class Feed(BaseHTTPRequestHandler):
        def do_GET(self):
            if not enabled.is_set():
                self.send_error(503)
                return
            accepted.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while enabled.is_set() and not closing.is_set():
                    self.wfile.write(part)
                    self.wfile.flush()
                    closing.wait(.02)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def log_message(self, *_):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Feed) as feed:
        enabled.set()
        thread = threading.Thread(target=feed.serve_forever, daemon=True)
        thread.start()
        camera = OpenCVCamera(f"http://127.0.0.1:{feed.server_port}/mjpeg")
        app = create_app({"DATA_DIR": tmp_path, "TESTING": True, "RECONNECT_SECONDS": .1,
                          "SHUTDOWN_TIMEOUT": 4, "CAPTURE_FPS": 30}, camera=camera, detector=FakeDetector())
        runtime = app.extensions["runtime"]
        client = app.test_client()
        streams = []
        try:
            assert client.post("/api/stream/start").status_code == 200
            wait_for(lambda: runtime.status()["camera_state"] == "online", timeout=10)
            assert client.post("/api/inference/start").status_code == 200
            for _ in range(2):
                preview = app.test_client().get("/api/stream/preview", buffered=False)
                streams.append(preview)
                assert preview.status_code == 200 and b"\xff\xd8" in next(iter(preview.response))
            assert accepted == ["/mjpeg"] and runtime.status()["preview_clients"] == 2
            wait_for(lambda: runtime.repository.items() == ["cup"], timeout=6)
            assert runtime.status()["inference_errors"] == 0
            assert client.get("/api/health").json["cameras"][0]["resolution"] == "160x90"
            enabled.clear()
            wait_for(lambda: runtime.status()["camera_state"] == "offline", timeout=10)
            assert client.get("/api/health").json["service_status"] == "ok"
            enabled.set()
            wait_for(lambda: runtime.status()["camera_state"] == "online" and len(accepted) >= 2, timeout=10)
            assert client.get("/api/snapshot").data.startswith(b"\xff\xd8")
        finally:
            for stream in streams:
                stream.close()
            closing.set()
            try:
                runtime.shutdown()
            finally:
                feed.shutdown()
                thread.join(2)
        assert camera.capture is None and runtime.status()["state"] == "shutdown"


def test_real_process_shutdown_unlocks_data_for_maintenance_and_restart(tmp_path):
    """桌面调用端所需的真实进程、HTTP 和 CLI；不实现另一个启动器。"""
    backend = Path(__file__).resolve().parents[1]
    root, restored = tmp_path / "data", tmp_path / "restored"
    temp = tmp_path / "process-temp"
    temp.mkdir()
    env = dict(os.environ, TMP=str(temp), TEMP=str(temp), TRACKING_CAMERA_KIND="mock")
    opener = build_opener(ProxyHandler({}))
    child = None

    def start(data_dir):
        nonlocal child, base
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        child = subprocess.Popen([sys.executable, "-X", "utf8", str(backend / "run.py"),
                                  "--port", str(port), "--data-dir", str(data_dir),
                                  "--camera-factory", "examples.v3_adapters:camera",
                                  "--detector-factory", "examples.v3_adapters:detector"],
                                 env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

        def ready():
            assert child.poll() is None, "backend exited during startup"
            try:
                return json.loads(call("/api/health"))["service_status"] == "ok"
            except URLError:
                return False

        wait_for(ready, timeout=10)

    def call(path, method="GET", payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(base + path, method=method, data=data,
                          headers={"Content-Type": "application/json"} if data else {})
        with opener.open(request, timeout=3) as response:
            return response.read()

    def stop():
        result = json.loads(call("/api/shutdown", "POST"))
        assert result["server_exit_scheduled"] and result["status"]["state"] == "shutdown"
        assert child.wait(timeout=10) == 0

    def cli(data_dir, *args, check=True):
        return subprocess.run([sys.executable, "-X", "utf8", str(backend / "manage.py"),
                               "--data-dir", str(data_dir), *map(str, args)], env=env,
                              capture_output=True, text=True, encoding="utf-8", timeout=15, check=check)

    base = ""
    log_archive, backup, csv_export = (tmp_path / name for name in ("logs.zip", "backup.zip", "events.csv"))
    try:
        start(root)
        assert json.loads(call("/api/model/classes"))["classes"] == ["cup"]
        assert json.loads(call("/api/health"))["status"] == "offline"
        assert json.loads(call("/api/stream/start", "POST"))["status"]["preview_enabled"]
        call("/api/stream/start", "POST")
        call("/api/settings", "PATCH", {"inference_fps": 4, "selected_classes": ["cup"]})
        call("/api/inference/start", "POST")
        assert not json.loads(call("/api/inference/start", "POST"))["changed"]
        wait_for(lambda: json.loads(call("/api/events?envelope=1"))["total"] > 0, timeout=6)
        row = json.loads(call("/api/events?envelope=1"))["events"][0]
        assert call(row["annotated_image_url"]).startswith(b"\xff\xd8")
        locked = cli(root, "export-logs", "--output", log_archive, check=False)
        assert locked.returncode != 0 and "data directory is in use" in locked.stderr and not log_archive.exists()
        stop()
        cli(root, "export-logs", "--output", log_archive)
        with zipfile.ZipFile(log_archive) as logs:
            assert b"Listening on" in logs.read("backend.log")
        assert cli(root, "export-logs", "--output", log_archive, check=False).returncode != 0
        cli(root, "export-csv", "--output", csv_export)
        assert "cup" in csv_export.read_text(encoding="utf-8-sig")
        cli(root, "backup", "--output", backup)
        cli(root, "restore", "--archive", backup, "--destination", restored)
        start(restored)
        assert json.loads(call("/api/settings"))["inference_fps"] == 4
        assert json.loads(call("/api/events?envelope=1"))["events"][0]["event_id"] == row["event_id"]
        assert call(row["image_url"]).startswith(b"\xff\xd8")
        stop()
    finally:
        if child is not None and child.poll() is None:
            try:
                call("/api/shutdown", "POST")
                child.wait(timeout=10)
            except (URLError, OSError, subprocess.TimeoutExpired):
                child.terminate()
                child.wait(timeout=5)


def test_legacy_migration_cli_reports_strict_and_tolerant_results(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    source = tmp_path / "旧数据"
    (source / "data").mkdir(parents=True)
    (source / "data" / "recognition.csv").write_text(
        'timestamp,class_name,location,image_id\n'
        '2026-03-05 10:00:00,杯子,"[1,2,3,4]",sample.jpg\n'
        'bad,cup,"[1,2,3,4]",bad.jpg\n', encoding="utf-8-sig")
    command = [sys.executable, "-X", "utf8", str(backend / "manage.py"), "--data-dir", str(tmp_path / "new"),
               "migrate-legacy", "--source-backend", str(source)]

    def run(*args):
        return subprocess.run(command + list(args), capture_output=True, text=True, encoding="utf-8", timeout=15)

    strict = run()
    assert strict.returncode == 2 and json.loads(strict.stdout)["inserted"] == 0
    assert json.loads(strict.stdout)["errors"][0]["line"] == 3
    for inserted, skipped in [(1, 0), (0, 1)]:
        tolerant = run("--mode", "skip_invalid")
        assert tolerant.returncode == 0, tolerant.stderr
        result = json.loads(tolerant.stdout)
        assert (result["inserted"], result["skipped"], result["rows"]) == (inserted, skipped, 2)
        assert result["errors"][0]["line"] == 3
    assert run("--mode", "other").returncode == 2
