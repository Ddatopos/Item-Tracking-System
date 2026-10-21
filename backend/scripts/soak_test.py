"""基于神经网络的物品示踪系统 V1.0：真实 HTTP 双预览连续运行测量。"""
import argparse
import json
import os
from pathlib import Path
import socket
import statistics
import subprocess
import sys
import threading
import time
from urllib.request import Request, urlopen
import psutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=1800)
    parser.add_argument("--output", default="reports/soak-30min.json")
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("seconds must be positive")
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_dir = output.parent / (output.stem + "-data")
    if data_dir.exists():
        raise RuntimeError("use a new output filename; data directory already exists")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    log = output.with_suffix(".server.txt").open("w", encoding="utf-8")
    command = [sys.executable, str(Path(__file__).resolve().parents[1] / "run.py"), "--data-dir", str(data_dir), "--port", str(port), "--camera", "mock", "--demo", "--start", "--infer"]
    child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    process = psutil.Process(child.pid)
    errors = []
    counts = [0, 0]
    done = threading.Event()
    latencies, captures, inference, memory, threads, queues, clients, snapshots = [], [], [], [], [], [], [], 0
    start = None
    initial = final = None
    exit_code = None

    def call(path, method="GET"):
        request = Request(base + path, method=method)
        with urlopen(request, timeout=10) as response:
            return response.read()

    def preview(index):
        try:
            with urlopen(base + "/api/stream", timeout=10) as response:
                while not done.is_set():
                    line = response.readline()
                    if not line:
                        break
                    if line.rstrip() != b"--frame":
                        continue
                    length = None
                    while True:
                        header = response.readline()
                        if header in {b"\r\n", b"\n", b""}:
                            break
                        if header.lower().startswith(b"content-length:"):
                            length = int(header.split(b":", 1)[1])
                    if length is None:
                        raise AssertionError("MJPEG missing Content-Length")
                    data = response.read(length)
                    if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
                        raise AssertionError("invalid JPEG frame")
                    counts[index] += 1
                if not done.is_set():
                    errors.append(f"preview {index} ended early")
        except Exception as exc:
            if not done.is_set():
                errors.append(f"preview {index}: {exc}")

    readers = []
    try:
        for _ in range(100):
            try:
                initial = json.loads(call("/api/status"))
                if initial["captured_frames"]:
                    break
            except Exception:
                pass
            if child.poll() is not None:
                raise RuntimeError("server exited during startup")
            time.sleep(.1)
        else:
            raise RuntimeError("server did not become ready")
        call("/api/settings")
        start = time.monotonic()
        wall_start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        readers = [threading.Thread(target=preview, args=(i,), daemon=True) for i in range(2)]
        for reader in readers:
            reader.start()
        next_snapshot, next_progress = 0.0, 0.0
        while time.monotonic() - start < args.seconds:
            tick = time.monotonic()
            status = json.loads(call("/api/status"))
            latencies.append((time.monotonic() - tick) * 1000)
            final = status
            if status["camera_state"] != "online" or status["inference_errors"] or status["camera_errors"]:
                errors.append("unexpected runtime error: " + json.dumps(status))
            queues.append(status["queue_length"])
            captures.append(status["capture_fps"])
            inference.append(status["inference_fps"])
            clients.append(status["preview_clients"])
            # Windows 虚拟环境 python.exe 可能是启动转发器；统计完整进程树。
            service_processes = [process] + process.children(recursive=True)
            memory.append(sum(p.memory_info().rss for p in service_processes if p.is_running()) / 1024 / 1024)
            threads.append(sum(p.num_threads() for p in service_processes if p.is_running()))
            elapsed = time.monotonic() - start
            if elapsed >= next_snapshot:
                if not call("/api/snapshot").startswith(b"\xff\xd8"):
                    raise AssertionError("snapshot not JPEG")
                snapshots += 1
                call("/api/events?limit=10")
                item = json.loads(call("/api/items/cup"))
                if not call(item["image_path"]).startswith(b"\xff\xd8"):
                    raise AssertionError("event image not JPEG")
                next_snapshot += 5
            if elapsed >= next_progress:
                print(json.dumps({"elapsed_seconds": round(elapsed, 1), "preview_frames": counts, "queue": status["queue_length"], "rss_mb": round(memory[-1], 2)}, ensure_ascii=False), flush=True)
                next_progress += 60
            done.wait(max(0, 1 - (time.monotonic() - tick)))
        final = json.loads(call("/api/status"))
        events = json.loads(call("/api/events?envelope=1"))
        event_count = events["total"]
        if event_count != 1 or events["events"][0]["observations"] < 2:
            errors.append("continuous same-class event was not merged")
        done.set()
        for reader in readers:
            reader.join(3)
        call("/api/shutdown", "POST")
        child.wait(timeout=15)
        exit_code = child.returncode
        if exit_code != 0:
            errors.append(f"server exit code {exit_code}")
    except Exception as exc:
        errors.append(str(exc))
        event_count = None
    finally:
        elapsed = time.monotonic() - start if start is not None else 0
        done.set()
        if child.poll() is None:
            try:
                call("/api/shutdown", "POST")
                child.wait(timeout=10)
            except Exception:
                child.terminate()
                child.wait(timeout=5)
        for reader in readers:
            reader.join(2)
        log.close()
        def summary(values):
            if not values:
                return None
            ordered = sorted(values)
            return {"min": round(min(values), 3), "median": round(statistics.median(values), 3), "p95": round(ordered[min(len(ordered) - 1, int(len(ordered) * .95))], 3), "max": round(max(values), 3)}
        result = {"scenario": "MockCamera + FakeDetector, real Waitress HTTP, two MJPEG clients",
                  "requested_seconds": args.seconds, "elapsed_seconds": round(elapsed, 3),
                  "started_at_utc": wall_start if start else None,
                  "preview_frames": counts, "preview_fps_per_client": [round(c / max(.001, args.seconds), 3) for c in counts],
                  "status_latency_ms": summary(latencies), "capture_fps": summary(captures), "inference_fps": summary(inference),
                  "rss_mb": summary(memory), "rss_first_mb": round(memory[0], 3) if memory else None,
                  "resource_scope": "server process tree including any Windows virtualenv launcher",
                  "rss_last_mb": round(memory[-1], 3) if memory else None,
                  "os_threads": summary(threads), "queue_length": summary(queues), "preview_clients": summary(clients),
                  "snapshots_checked": snapshots, "event_count": event_count, "initial_status": initial,
                  "final_status": final, "errors": errors, "server_exit_code": exit_code,
                  "passed": elapsed >= args.seconds and not errors and min(counts) > 0 and exit_code == 0,
                  "limitations": "Simulated images and detector only. No hardware, YOLO accuracy, packaging or full React integration validation."}
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"report": str(output), "passed": result["passed"], "errors": errors}, ensure_ascii=False), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
