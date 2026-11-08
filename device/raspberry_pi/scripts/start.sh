#!/usr/bin/env bash
# 前台启动摄像头 MJPEG 服务。
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

CONFIG="${PI_CAMERA_CONFIG:-configs/camera.json}"
if [ ! -f "$CONFIG" ]; then
  echo "配置文件不存在：$CONFIG" >&2
  echo "请先执行：cp configs/camera.example.json configs/camera.json" >&2
  exit 2
fi

mkdir -p run
exec python3 camera_server.py --config "$CONFIG" --pid-file run/camera.pid
