# 树莓派摄像头设备端（V1.0）

在树莓派上把 Camera Module 3 采集的画面编码为 JPEG，并通过 HTTP MJPEG 提供给电脑端后端取流。

## 一 依赖与安装

硬件为树莓派 4B 4GB + Camera Module 3 Wide（IMX708），系统为 Debian 13 trixie aarch64，需要 `python3-picamera2`、`python3-opencv`、`python3-numpy`。安装脚本会更新软件包索引、安装依赖并列出已识别摄像头。

```bash
cd device/raspberry_pi
chmod +x scripts/*.sh
./scripts/install.sh
```

安装脚本只做环境准备，不会自动创建 `configs/camera.json`。首次部署需要复制示例配置：

```bash
cp configs/camera.example.json configs/camera.json
```

`configs/camera.json` 已在 `configs/.gitignore` 中忽略，不会提交到仓库。

## 二 配置项

配置为 JSON 对象，默认读取 `configs/camera.json`。路径优先级为 `--config` 参数 > 环境变量 `PI_CAMERA_CONFIG` > 默认路径。显式指定的文件不存在或字段非法时，进程以退出码 2 结束。

| 字段 | 默认值 | 取值范围或说明 |
| --- | --- | --- |
| camera_id | `pi-cam-1` | 非空字符串，标识摄像头 |
| room | `未设置房间` | 非空字符串，房间名称 |
| host | `0.0.0.0` | 非空字符串，监听地址 |
| port | `8080` | 1024 到 65535 的整数 |
| width | `1280` | 64 到 4608 的偶数 |
| height | `720` | 64 到 4608 的偶数 |
| fps | `15` | 1 到 60 的数字 |
| jpeg_quality | `80` | 50 到 95 的整数 |
| autofocus | `continuous` | 只能是 `continuous` 或 `manual` |
| lens_position | `1.0` | 数字；`manual` 时必须在 0 到 32 之间 |
| max_clients | `4` | 1 到 16 的整数，同时观看视频的客户端上限 |
| open_attempts | `5` | 1 到 20 的整数，连续失败上限 |
| retry_backoff_seconds | `1.0` | 0.1 到 60，初始重试间隔 |
| max_backoff_seconds | `30.0` | 不小于 `retry_backoff_seconds` 且不大于 300 |
| frame_stale_seconds | `3.0` | 0.5 到 60，快照可接受的最大帧龄 |
| log_level | `INFO` | `DEBUG`、`INFO`、`WARNING`、`ERROR` |
| log_file | 空字符串 | 为空时输出到 stderr；非空时写入轮转日志文件 |

未知字段、类型错误（布尔值不算数字）都会报错，错误信息为中文。

## 三 启动与停止

前台启动（脚本会检查配置并在 `run/camera.pid` 写入进程号）：

```bash
cd device/raspberry_pi
./scripts/start.sh
```

后台启动：

```bash
cd device/raspberry_pi
mkdir -p run
nohup ./scripts/start.sh > run/camera.out 2>&1 &
./scripts/stop.sh
```

`scripts/stop.sh` 读取 `run/camera.pid` 并发送 SIGTERM，最多等待 10 秒，超时会提示使用 `kill -9`。

安装为 systemd 服务（服务文件默认 `User=pi`，部署账号不是 `pi` 时需先改成实际用户，例如 `nick`）：

```bash
sudo mkdir -p /etc/item-tracking
sudo cp device/raspberry_pi/configs/camera.example.json /etc/item-tracking/camera.json
sudo cp device/raspberry_pi/systemd/item-tracking-camera.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now item-tracking-camera
sudo systemctl status item-tracking-camera
sudo journalctl -u item-tracking-camera -f
```

## 四 验证

```bash
curl http://127.0.0.1:8080/health
curl -o snapshot.jpg http://127.0.0.1:8080/snapshot
```

- 浏览器打开 `http://<树莓派IP>:8080/video`，应看到实时画面。
- 电脑端后端取流（地址以实际配置为准，示例为 `192.168.137.40`）：

```powershell
py -3 backend/run.py --camera opencv --source http://192.168.137.40:8080/video --start --demo
```

在浏览器打开 `http://127.0.0.1:5000/api/preview` 检查后端预览，打开 `http://127.0.0.1:5000/api/status` 确认 `camera_state` 为 `online`。

## 五 目录结构

```text
device/raspberry_pi/
├── __init__.py                 版本号
├── config.py                   配置默认值、加载与校验
├── source.py                   Picamera2 取帧实现
├── server.py                   帧缓存、采集服务与 HTTP 服务
├── camera_server.py            命令行入口
├── configs/
│   ├── camera.example.json     配置示例
│   └── .gitignore              忽略 camera.json
├── scripts/
│   ├── install.sh              安装依赖
│   ├── start.sh                前台启动
│   └── stop.sh                 按 pid 文件停止
├── systemd/
│   └── item-tracking-camera.service
├── tests/
│   ├── conftest.py             模拟摄像头与夹具
│   ├── test_config.py          配置测试
│   └── test_server.py          HTTP 服务测试
└── README.md
```

## 六 实测参数

实测环境为树莓派 4B 4GB + IMX708，Debian 13 trixie aarch64。数据来自 2026-11-08 实机运行，详细记录见 `docs/device/acceptance.md`。

| 分辨率 | 实际输出 | JPEG 质量 | 平均帧率 | 首帧延迟 | 内存占用 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| 1280x720 | 1280x720 | 80 | 设备端 15.1 fps；电脑后端取流 13.7 fps | 未单独测量 | 181 MB（连续 36 分钟） | 连续自动对焦，CPU 42.8%，温度 34.5℃ |

原始模式为 1536x864、2304x1296、4608x2592（30fps），仅用于摄像头能力确认，未作为视频输出实测，不承诺满像素帧率。
