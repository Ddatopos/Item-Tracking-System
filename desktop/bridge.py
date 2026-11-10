"""Desktop controller bridge; process lifecycle remains owned by the shared launcher."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else PROJECT_ROOT
BACKEND_URL = os.environ.get("TRACKING_BACKEND_URL", "http://127.0.0.1:5000")
BACKEND_PORT = int(os.environ.get("TRACKING_PORT", "5000"))


def result(ok, message, data=None):
    return {"ok": ok, "message": message, "data": data}


class DesktopController:
    """Own and manage only the backend process started by this desktop application."""

    def __init__(
        self,
        preferences_path=None,
        backend_url=BACKEND_URL,
        backend_command=None,
        launch_log_path=None,
    ):
        self.preferences_path = Path(preferences_path) if preferences_path else self._default_preferences_path()
        self.backend_url = backend_url.rstrip("/")
        self.backend_command = backend_command or self._default_backend_command()
        self.launch_log_path = Path(launch_log_path) if launch_log_path else None
        self._process = None
        self._lock = threading.RLock()

    @staticmethod
    def _default_preferences_path():
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "ItemTrackingSystem" / "desktop.json"
        return Path.home() / ".config" / "item-tracking-system" / "desktop.json"

    @staticmethod
    def _default_backend_command():
        if not getattr(sys, "frozen", False):
            return None
        executable = APP_ROOT / "runtime" / "ItemTrackingBackend" / "ItemTrackingBackend.exe"
        return [str(executable)]

    @staticmethod
    def _default_maintenance_command():
        if not getattr(sys, "frozen", False):
            return [sys.executable, str(PROJECT_ROOT / "backend" / "manage.py")]
        executable = APP_ROOT / "runtime" / "ItemTrackingMaintenance" / "ItemTrackingMaintenance.exe"
        return [str(executable)]

    def _backend_launch_log(self):
        if self.launch_log_path is not None:
            self.launch_log_path.parent.mkdir(parents=True, exist_ok=True)
            return self.launch_log_path
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / ".config"
        path = base / "ItemTrackingSystem" / "logs" / "backend-launch.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _saved_data_dir(self):
        if self.preferences_path.is_file():
            saved = json.loads(self.preferences_path.read_text(encoding="utf-8"))
            directory = saved.get("data_dir")
            if isinstance(directory, str) and directory:
                return Path(directory).expanduser().resolve()
        configured = os.environ.get("TRACKING_DATA_DIR")
        if configured:
            return Path(configured).expanduser().resolve()
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "ItemTrackingSystem" / "data"
        return APP_ROOT / "data"

    def _health(self):
        with urlopen(self.backend_url + "/api/health", timeout=1) as response:
            return json.loads(response.read().decode("utf-8"))

    def _wait_until_ready(self, timeout=20):
        deadline = time.monotonic() + timeout
        last_error = None
        while time.monotonic() < deadline:
            if self._process is None or self._process.poll() is not None:
                return False, f"后端进程已退出：{self._process.returncode if self._process else '未启动'}"
            try:
                health = self._health()
                if health.get("service_status") == "ok":
                    return True, ""
                return False, f"后端服务状态异常：{health.get('service_status', 'unknown')}"
            except (OSError, URLError, TimeoutError, json.JSONDecodeError) as error:
                last_error = error
                time.sleep(0.25)
        return False, f"等待后端就绪超时：{last_error or '未收到健康响应'}"

    def start(self):
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return result(True, "本桌面应用的后台服务已在运行。", {"pid": self._process.pid})
            if self._process is not None:
                self._process = None
            if not self.backend_command:
                return result(False, "开发模式不会启动或接管后台进程；请先手动启动后端。")
            executable = Path(self.backend_command[0])
            if not executable.is_file():
                return result(False, f"未找到打包的后台程序：{executable}")
            try:
                self._saved_data_dir().mkdir(parents=True, exist_ok=True)
                frontend_dir = APP_ROOT / "frontend"
                command = [
                    *self.backend_command,
                    "--camera",
                    os.environ.get("TRACKING_CAMERA_KIND", "mock"),
                    "--data-dir",
                    str(self._saved_data_dir()),
                    "--port",
                    str(BACKEND_PORT),
                    "--frontend-dir",
                    str(frontend_dir),
                ]
                if os.environ.get("TRACKING_CAMERA_KIND", "mock") == "mock":
                    command.extend(["--demo", "--start", "--infer"])
                else:
                    command.extend(["--source", os.environ.get("TRACKING_CAMERA_SOURCE", "0"), "--start"])
                    detector_factory = os.environ.get("TRACKING_DETECTOR_FACTORY")
                    if detector_factory:
                        command.extend(["--detector-factory", detector_factory, "--infer"])
                    camera_factory = os.environ.get("TRACKING_CAMERA_FACTORY")
                    if camera_factory:
                        command.extend(["--camera-factory", camera_factory])
                with self._backend_launch_log().open("a", encoding="utf-8") as launch_log:
                    launch_log.write(f"\nStarting backend: {command[0]}\n")
                    launch_log.flush()
                    self._process = subprocess.Popen(
                        command,
                        cwd=APP_ROOT,
                        stdin=subprocess.DEVNULL,
                        stdout=launch_log,
                        stderr=subprocess.STDOUT,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self._process = None
                return result(False, f"启动后台失败：{error}")

            ready, message = self._wait_until_ready()
            if not ready:
                try:
                    details = self._backend_launch_log().read_text(encoding="utf-8", errors="replace")
                    details = "\n".join(details.splitlines()[-20:])
                except OSError:
                    details = ""
                process = self._process
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                self._process = None
                if details:
                    message += f"；后台启动日志：{details}"
                return result(False, message)
            return result(True, "后台服务已启动。", {"pid": self._process.pid})

    def stop(self):
        with self._lock:
            process = self._process
            if process is None:
                return result(True, "本桌面应用没有启动后台进程，无需停止。")
            if process.poll() is not None:
                self._process = None
                return result(True, "后台进程已退出。")

            try:
                request = Request(self.backend_url + "/api/shutdown", data=b"", method="POST")
                with urlopen(request, timeout=5) as response:
                    response.read()
            except HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")
                return result(False, f"后端拒绝安全停止；进程保持运行：{detail or error.reason}")
            except (OSError, URLError, TimeoutError) as error:
                return result(False, f"无法确认后端已安全停止；进程保持运行：{error}")

            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                return result(False, "后端尚未退出；为保护数据未强制终止进程。")
            self._process = None
            return result(True, "后台已安全停止。")

    def open_data_dir(self):
        try:
            directory = self._saved_data_dir()
            directory.mkdir(parents=True, exist_ok=True)
            if not hasattr(os, "startfile"):
                return result(False, "打开数据目录仅支持 Windows 桌面环境。")
            os.startfile(str(directory))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            return result(False, f"打开数据目录失败：{error}")
        return result(True, "已打开数据目录。", {"path": str(directory)})

    def export_logs(self, destination):
        try:
            output = Path(destination).expanduser().resolve()
            data_dir = self._saved_data_dir()
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            return result(False, f"日志导出路径无效：{error}")
        if output.suffix.lower() != ".zip":
            return result(False, "日志导出文件必须使用 .zip 扩展名。")
        if output.exists():
            return result(False, "目标文件已存在，请选择一个新文件名。")
        if output == data_dir or data_dir in output.parents:
            return result(False, "日志导出目标必须位于数据目录之外。")

        was_running = self._process is not None and self._process.poll() is None
        if was_running:
            stopped = self.stop()
            if not stopped["ok"]:
                return result(False, f"无法在数据安全状态下导出日志：{stopped['message']}")
        command = [
            *self._default_maintenance_command(),
            "--data-dir",
            str(data_dir),
            "export-logs",
            "--output",
            str(output),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=APP_ROOT if getattr(sys, "frozen", False) else PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            export_result = result(False, f"日志导出失败：{error}")
        else:
            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip()
                export_result = result(False, f"日志导出失败：{detail or '维护工具返回错误'}")
            else:
                export_result = result(True, "日志已导出。", {"path": str(output)})

        if was_running:
            restarted = self.start()
            if not restarted["ok"]:
                return result(
                    False,
                    f"{export_result['message']}；但后台恢复失败：{restarted['message']}",
                    export_result.get("data"),
                )
        return export_result

    def set_data_dir(self, path):
        try:
            directory = Path(path).expanduser().resolve()
        except (OSError, TypeError, ValueError) as error:
            return result(False, f"数据目录无效：{error}")
        if not directory.is_dir():
            return result(False, "数据目录必须是已存在的文件夹。")
        try:
            self.preferences_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.preferences_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps({"data_dir": str(directory)}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(self.preferences_path)
        except OSError as error:
            return result(False, f"保存数据目录失败：{error}")
        return result(
            True,
            "数据目录已保存，将在统一启动器下次启动后端时生效。",
            {"path": str(directory), "restart_required": True},
        )

    def shutdown(self):
        return self.stop()


class DesktopBridge:
    """Expose the agreed controller methods and native-dialog selectors to pywebview."""

    def __init__(self, controller=None):
        self.controller = controller or DesktopController()
        self.window = None
        self._shutdown_result = None

    def attach_window(self, window):
        self.window = window

    def start(self):
        return self.controller.start()

    def stop(self):
        return self.controller.stop()

    def open_data_dir(self):
        return self.controller.open_data_dir()

    def export_logs(self, destination):
        return self.controller.export_logs(destination)

    def set_data_dir(self, path):
        return self.controller.set_data_dir(path)

    def shutdown(self):
        if self._shutdown_result is None or not self._shutdown_result["ok"]:
            self._shutdown_result = self.controller.shutdown()
        return self._shutdown_result

    def select_data_dir(self):
        if self.window is None:
            return result(False, "桌面窗口尚未就绪。")
        import webview

        selected = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        if not selected:
            return result(False, "已取消选择数据目录。")
        return result(True, "已选择数据目录。", {"path": selected[0]})

    def select_export_destination(self):
        if self.window is None:
            return result(False, "桌面窗口尚未就绪。")
        import webview

        selected = self.window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename="tracking-logs.zip",
            file_types=("ZIP files (*.zip)",),
        )
        if not selected:
            return result(False, "已取消选择导出位置。")
        path = selected if isinstance(selected, str) else selected[0]
        return result(True, "已选择日志导出位置。", {"path": path})

    def on_window_closing(self):
        shutdown_result = self.shutdown()
        if not shutdown_result["ok"]:
            print(shutdown_result["message"], file=sys.stderr)


DemoController = DesktopController
