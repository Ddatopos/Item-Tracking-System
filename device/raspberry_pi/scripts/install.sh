#!/usr/bin/env bash
# 安装树莓派摄像头服务依赖，并提示生成配置文件。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEVICE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
EXAMPLE_CONFIG="$DEVICE_DIR/configs/camera.example.json"
CONFIG_FILE="$DEVICE_DIR/configs/camera.json"

echo "==> 更新软件包索引"
sudo apt-get update

echo "==> 安装 python3-picamera2、python3-opencv、python3-numpy"
sudo apt-get install -y python3-picamera2 python3-opencv python3-numpy

echo "==> 检测摄像头"
rpicam-hello --list-cameras || true

if [ -f "$CONFIG_FILE" ]; then
  echo "==> 配置文件已存在：$CONFIG_FILE"
else
  echo "==> 尚未创建配置文件，请执行："
  echo "    cp $EXAMPLE_CONFIG $CONFIG_FILE"
fi

echo "==> 启动服务（前台）："
echo "    cd $DEVICE_DIR && ./scripts/start.sh"
echo "==> 安装为 systemd 服务："
echo "    sudo cp $DEVICE_DIR/systemd/item-tracking-camera.service /etc/systemd/system/"
echo "    sudo systemctl daemon-reload && sudo systemctl enable --now item-tracking-camera"
