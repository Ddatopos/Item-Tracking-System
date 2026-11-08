"""树莓派摄像头 HTTP 服务入口：加载配置、托管 MJPEG 视频源并优雅退出。"""
import argparse
import logging
import os
import signal
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

if __package__:
    from .config import ConfigError, load_config
    from .server import CameraService, create_server
    from .source import Picamera2Source
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from config import ConfigError, load_config
    from server import CameraService, create_server
    from source import Picamera2Source

LOG = logging.getLogger("device.camera")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="基于神经网络的物品示踪系统：树莓派摄像头 MJPEG 视频源")
    parser.add_argument("--config", help="JSON 配置文件路径，默认 configs/camera.json")
    parser.add_argument("--host", help="监听地址，默认 0.0.0.0")
    parser.add_argument("--port", type=int, help="监听端口，默认 8080")
    parser.add_argument("--width", type=int, help="画面宽度，默认 1280")
    parser.add_argument("--height", type=int, help="画面高度，默认 720")
    parser.add_argument("--fps", type=float, help="采集帧率，默认 15")
    parser.add_argument("--quality", type=int, dest="quality", help="JPEG 质量 50 到 95，默认 80")
    parser.add_argument("--autofocus", choices=("continuous", "manual"), help="对焦模式")
    parser.add_argument("--camera-id", dest="camera_id", help="摄像头标识，默认 pi-cam-1")
    parser.add_argument("--room", help="房间名称")
    parser.add_argument("--log-level", dest="log_level", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    parser.add_argument("--pid-file", dest="pid_file", help="写入进程号的文件，退出时删除")
    return parser.parse_args(argv)


def build_overrides(args):
    """把命令行参数转为配置覆盖值，未提供的参数保持 None。"""
    return {
        "host": args.host,
        "port": args.port,
        "width": args.width,
        "height": args.height,
        "fps": args.fps,
        "jpeg_quality": args.quality,
        "autofocus": args.autofocus,
        "camera_id": args.camera_id,
        "room": args.room,
        "log_level": args.log_level,
    }


def setup_logging(config):
    """按配置输出到 stderr 或轮转日志文件。"""
    handler = None
    if config["log_file"]:
        log_path = Path(config["log_file"]).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(str(log_path), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    logging.basicConfig(
        level=getattr(logging, config["log_level"], logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[handler] if handler is not None else None,
        force=True,
    )


def install_signal_handlers(stop_event):
    def handle(signum, frame):
        LOG.info("收到信号 %s，准备退出", signum)
        stop_event.set()

    for name in ("SIGINT", "SIGTERM"):
        signum = getattr(signal, name, None)
        if signum is None:
            continue
        try:
            signal.signal(signum, handle)
        except (ValueError, OSError):
            LOG.debug("无法注册信号处理：%s", name)


def write_pid_file(path):
    if not path:
        return
    pid_path = Path(path).expanduser()
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()), encoding="utf-8")


def remove_pid_file(path):
    if not path:
        return
    pid_path = Path(path).expanduser()
    try:
        if pid_path.read_text(encoding="utf-8").strip() == str(os.getpid()):
            pid_path.unlink()
    except OSError:
        pass


def main(argv=None):
    args = parse_args(argv)
    try:
        config = load_config(args.config, build_overrides(args))
    except ConfigError as exc:
        print("配置错误：%s" % exc, file=sys.stderr)
        return 2
    setup_logging(config)
    LOG.info("配置已加载：camera_id=%s，分辨率=%dx%d，fps=%s",
             config["camera_id"], config["width"], config["height"], config["fps"])

    stop_event = threading.Event()
    fatal = {}

    def on_fatal(error):
        fatal["error"] = error
        stop_event.set()

    service = CameraService(config, on_fatal=on_fatal)
    try:
        server = create_server(service, config)
    except OSError as exc:
        LOG.error("HTTP 服务器启动失败：%s", exc)
        return 1
    http_thread = threading.Thread(target=server.serve_forever, name="camera-http", daemon=True)
    http_thread.start()
    install_signal_handlers(stop_event)
    write_pid_file(args.pid_file)
    service.start()
    display_host = "127.0.0.1" if config["host"] in ("0.0.0.0", "::") else config["host"]
    LOG.info("视频流地址 http://%s:%d/video", display_host, server.server_port)
    LOG.info("健康检查地址 http://%s:%d/health", display_host, server.server_port)

    exit_code = 0
    try:
        while not stop_event.wait(0.5):
            pass
        if fatal.get("error") is not None:
            exit_code = 1
            LOG.error("采集线程致命错误，进程退出：%s", fatal["error"])
    except KeyboardInterrupt:
        LOG.info("收到 Ctrl+C，准备退出")
    finally:
        service.stop()
        if http_thread.is_alive():
            server.shutdown()
        http_thread.join(5)
        server.server_close()
        remove_pid_file(args.pid_file)
        LOG.info("服务已退出")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
