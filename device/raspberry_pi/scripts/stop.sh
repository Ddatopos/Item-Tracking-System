#!/usr/bin/env bash
# 根据 run/camera.pid 停止后台启动的服务。
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

PID_FILE="run/camera.pid"
if [ ! -f "$PID_FILE" ]; then
  echo "未找到 $PID_FILE；如果服务由 systemd 管理，请使用：sudo systemctl stop item-tracking-camera"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if ! kill -0 "$PID" 2>/dev/null; then
  echo "进程 $PID 不存在，清理 pid 文件"
  rm -f "$PID_FILE"
  exit 0
fi

kill -TERM "$PID"
for _ in $(seq 1 20); do
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "服务已停止"
    exit 0
  fi
  sleep 0.5
done

echo "进程 $PID 在 10 秒内未退出，可执行：kill -9 $PID" >&2
exit 1
