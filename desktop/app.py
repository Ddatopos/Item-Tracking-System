"""Run the production React build in a local pywebview window."""
import time
import os
import sys
from pathlib import Path
import subprocess
from urllib.error import URLError
from urllib.request import urlopen

from desktop.bridge import BACKEND_URL, APP_ROOT, DesktopBridge


def frontend_directory():
    if getattr(sys, "frozen", False):
        return APP_ROOT / "frontend"
    return APP_ROOT / "frontend" / "build"


def wait_for_backend(timeout=15):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            with urlopen(BACKEND_URL + "/api/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, URLError) as error:
            last_error = error
        time.sleep(0.25)
    raise RuntimeError(
        f"后端未就绪：{BACKEND_URL}。请按 desktop/README.md 中的命令手动启动后端。"
        + (f" 最后错误：{last_error}" if last_error else "")
    )


def main():
    frontend_root = frontend_directory()
    if not (frontend_root / "index.html").is_file():
        raise RuntimeError(f"未找到生产构建资源：{frontend_root}")

    import webview

    bridge = DesktopBridge()
    if getattr(sys, "frozen", False):
        started = bridge.start()
        if not started["ok"]:
            raise RuntimeError(started["message"])
    else:
        wait_for_backend()
    try:
        window = webview.create_window(
            "基于神经网络的物品示踪系统 V1.0",
            BACKEND_URL + "/ui/",
            js_api=bridge,
            width=1366,
            height=768,
            min_size=(1024, 640),
            confirm_close=False,
        )
        bridge.attach_window(window)
        window.events.closing += bridge.on_window_closing
        webview.start(debug=False)
    finally:
        bridge.shutdown()


def show_startup_error(error):
    message = f"桌面应用启动失败：{error}"
    local_app_data = os.environ.get("LOCALAPPDATA")
    log_path = None
    if local_app_data:
        log_path = Path(local_app_data) / "ItemTrackingSystem" / "logs" / "desktop-startup.log"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(message + "\n", encoding="utf-8")
        except OSError:
            log_path = None
    if getattr(sys, "frozen", False) and sys.platform == "win32":
        try:
            import ctypes

            detail = f"{message}\n\n诊断日志：{log_path}" if log_path else message
            ctypes.windll.user32.MessageBoxW(None, detail, "物品示踪系统", 0x10)
            return
        except (ImportError, OSError, AttributeError):
            pass
        if log_path:
            try:
                os.startfile(str(log_path))
                return
            except OSError:
                pass
        try:
            subprocess.Popen(["notepad.exe"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError:
            print(message, file=sys.stderr)
    else:
        print(message, file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        show_startup_error(error)
        raise SystemExit(1) from error
