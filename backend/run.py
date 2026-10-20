"""基于神经网络的物品示踪系统 V1.0：单进程本机正式启动入口。"""
import argparse
import atexit
import importlib
import logging
import signal
import threading
from waitress import create_server
from tracking.app_factory import create_app, configure_logging
from tracking.adapters import FakeDetector
from tracking.config import load_config
from tracking.process_lock import DataDirectoryLock


def load_plugin(spec):
    module, name = spec.split(":", 1)
    # 显式本机命令行指定的 Python 工厂，不接受 HTTP 动态加载。
    return getattr(importlib.import_module(module), name)()


def main():
    parser = argparse.ArgumentParser(description="基于神经网络的物品示踪系统 V1.0")
    parser.add_argument("--data-dir")
    parser.add_argument("--camera", choices=["mock", "opencv"], default=None)
    parser.add_argument("--source")
    parser.add_argument("--room")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--demo", action="store_true", help="explicit simulated detector")
    parser.add_argument("--detector-factory", help="module:function provided by the model integrator")
    parser.add_argument("--camera-factory", help="module:function provided by the camera integrator")
    parser.add_argument("--frontend-dir")
    parser.add_argument("--dev-proxy", action="store_true", help="trust localhost:3000 origins for the existing React development proxy")
    parser.add_argument("--start", action="store_true", help="start capture at launch")
    parser.add_argument("--infer", action="store_true", help="start inference at launch")
    args = parser.parse_args()
    if args.demo and args.detector_factory:
        parser.error("choose --demo or --detector-factory")
    overrides = {key: value for key, value in {"DATA_DIR": args.data_dir, "CAMERA_KIND": args.camera,
                 "CAMERA_SOURCE": args.source, "ROOM": args.room, "FRONTEND_DIR": args.frontend_dir}.items() if value is not None}
    config = load_config(overrides)
    if args.dev_proxy:
        config["TRUSTED_ORIGINS"] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    directory_lock = DataDirectoryLock(config["DATA_DIR"])
    atexit.register(directory_lock.close)
    configure_logging(config["DATA_DIR"])
    detector = FakeDetector() if args.demo else (load_plugin(args.detector_factory) if args.detector_factory else None)
    camera = load_plugin(args.camera_factory) if args.camera_factory else None
    app = create_app(config, camera=camera, detector=detector)
    runtime = app.extensions["runtime"]
    atexit.register(runtime.shutdown)
    server = create_server(app, host="127.0.0.1", port=args.port, threads=12, channel_timeout=15, expose_tracebacks=False)
    exit_requested = threading.Event()
    app.extensions["shutdown_server"] = exit_requested.set

    def request_exit(*_):
        exit_requested.set()

    signal.signal(signal.SIGINT, request_exit)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_exit)
    server_thread = threading.Thread(target=server.run, name="tracking-http", daemon=True)
    try:
        if args.start or args.infer:
            runtime.start()
        if args.infer:
            runtime.start_inference()
        server_thread.start()
        logging.info("Listening on http://127.0.0.1:%s (single process, debug disabled)", args.port)
        while not exit_requested.wait(.25):
            if not server_thread.is_alive():
                raise RuntimeError("HTTP server stopped unexpectedly")
    finally:
        runtime.shutdown()
        server.close()
        server_thread.join(2)
        directory_lock.close()


if __name__ == "__main__":
    main()
