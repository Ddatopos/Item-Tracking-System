# 树莓派视频源交接报告

- 负责人：王韵哲
- 项目：基于神经网络的物品示踪系统 V1.0
- 日期：2026-11-08
- 分支：`feature/wang-camera`（基于 main `25cad5d`）
- 提交：`ed79391`（设备模块、文档与样例）、`c9f9066`（回填验收记录）、`cff68f1`（交接报告与本文件）

## 一 任务结果

| 编号 | 任务 | 状态 | 说明 |
| --- | --- | --- | --- |
| A1 | 代码交付 | 部分完成 | 代码、依赖说明、配置示例、启停脚本、README 已提交；另一位成员按 README 复现尚未执行；分支尚未推送到远端 |
| A2 | 网络接入 | 完成（待确认） | 电脑后端用现有 `OpenCVCamera` 直连实际视频地址，持续取得有效帧；待王琪臻确认接入结论 |
| A3 | 参数配置 | 完成 | 地址、端口、分辨率、帧率、JPEG 质量和自动对焦均在配置文件中，改参数不改源码；浏览器人工确认待做 |
| A4 | 可靠性 | 完成 | 设备端单实例占用摄像头，提供状态、日志、停止与资源释放；systemd 托管，服务重启 3.6 秒恢复 |
| A5 | 实机验收 | 完成（有方法偏差） | 30 分钟连续运行、服务重启、断网恢复、换地址重配均已实测；断网用电脑侧 TCP 中断模拟，未物理拔线 |
| A6 | 交接材料 | 部分完成 | 部署与排障说明、示例配置、宿舍样例图已提交；短视频未提供；MockCamera 复用后端已有实现 |

## 二 文件与接口

### 新增文件

| 路径 | 用途 |
| --- | --- |
| `device/raspberry_pi/server.py` | 单采集线程、最新帧缓存、MJPEG HTTP 服务 |
| `device/raspberry_pi/source.py` | Picamera2 取帧，连续/手动对焦 |
| `device/raspberry_pi/config.py` | 配置默认值、加载与 17 项字段校验 |
| `device/raspberry_pi/camera_server.py` | 命令行入口、信号退出、pid 文件 |
| `device/raspberry_pi/scripts/` | `install.sh`、`start.sh`、`stop.sh` |
| `device/raspberry_pi/systemd/item-tracking-camera.service` | systemd 单元模板 |
| `device/raspberry_pi/configs/camera.example.json` | 配置示例（实例文件被 gitignore） |
| `device/raspberry_pi/tests/` | 配置与 HTTP 服务自动测试（48 例） |
| `device/raspberry_pi/README.md` | 部署、配置、启停、排障 |
| `docs/device/README.md` | 设备模块说明与链路 |
| `docs/device/acceptance.md` | A1–A6 实机验收记录 |
| `docs/device/samples/` | 宿舍样例图与参数说明 |

### HTTP 接口

| 路径 | 说明 |
| --- | --- |
| `GET /health`、`GET /status` | 状态 JSON：`state`、`camera_state`、`camera_id`、`room`、`resolution`、`configured_fps`、`measured_fps`、`frames`、`errors`、`last_error`、`clients`、`uptime_seconds`、`frame_age_ms` |
| `GET /snapshot` | 单帧 JPEG；无可用帧时返回 503 JSON |
| `GET /video`、`GET /stream` | `multipart/x-mixed-replace` MJPEG 流，供后端和浏览器使用 |

后端取流地址：`http://192.168.137.40:8080/video`（IP 以现场配置为准，不写入源码）。

### 兼容影响

- 复用后端 `OpenCVCamera` 与 `CameraFrame` 合同，未修改 `backend/`、`frontend/` 和根 README。
- 未新增公共类型，未改动 `backend/tracking/contracts.py`。
- 断线重连由电脑后端负责；设备端恢复后继续输出新帧，不做双向心跳。

## 三 验证证据

### 环境

- 设备：树莓派 4B 4GB + Camera Module 3 Wide（IMX708）
- 系统：Debian GNU/Linux 13 (trixie)，`aarch64`
- 摄像头栈：libcamera 0.7.2+rpt20260817，系统包 `python3-picamera2`、`python3-opencv` 4.10.0、`python3-numpy`
- 电脑：Windows，`py -3`；网络为校园网 Wi-Fi 经 ICS 共享到以太网，网段 `192.168.137.0/24`
- 实际输出参数：1280×720、15 fps、JPEG 质量 80、连续自动对焦、最大 4 个客户端

### 自动测试

```powershell
py -3 -m pytest device/raspberry_pi/tests -q
# 48 passed in 5.95s
```

测试只使用模拟摄像头，不依赖 picamera2 和真实硬件。

### 实机数据

设备端 `/health`：

```json
{"state":"running","camera_state":"online","camera_id":"pi-cam-1","room":"宿舍",
 "resolution":"1280x720","configured_fps":15,"measured_fps":15.1,"frames":32248,
 "errors":0,"last_error":null,"clients":0,"max_clients":4,"uptime_seconds":2154.5,
 "frame_age_ms":30}
```

电脑端后端：

```powershell
py -3 backend/run.py --camera opencv --source http://192.168.137.40:8080/video --start --demo
```

- `/api/status`：`camera_state=online`、`capture_fps=13.674`、`camera_simulated=false`
- `/api/snapshot`：82683 字节 JPEG，画面与设备端一致

结果汇总：

| 项目 | 结果 |
| --- | --- |
| 30 分钟连续运行 | 36 分 14 秒，`frames=32248`，`errors=0`，15.1 fps，CPU 42.8%，RSS 181 MB，温度 34.5℃，`throttled=0x0` |
| 服务重启 | `systemctl restart` 后 3.6 秒恢复 online，帧号继续增长 |
| 短时断网 | 中断 1.0 秒后后端 offline，恢复后 1.6 秒自动 online，恢复后 12.9 fps（中断前 13.6 fps） |
| 更换地址 | 新增 `192.168.137.77/24` 后用新地址取流，13.8 fps、88 帧，设备端配置未修改 |

过程问题：首次接入时画面红蓝通道对调。原因是本机 `capture_array` 返回顺序为 BGR，代码多做了一次 `RGB2BGR`；已在 `source.py` 修正并实机复验。

完整记录见 `docs/device/acceptance.md`，样例见 `docs/device/samples/`。

## 四 运行说明

### 部署

```powershell
# 仓库根目录，把设备模块拷到树莓派
scp -r device/raspberry_pi nick@192.168.137.40:~/
```

```bash
cd ~/raspberry_pi
cp configs/camera.example.json configs/camera.json
```

### 启动与停止

```bash
cd ~/raspberry_pi
./scripts/start.sh          # 前台
./scripts/stop.sh           # 按 run/camera.pid 停止
```

### systemd（现场已启用）

```bash
sudo mkdir -p /etc/item-tracking
sudo cp configs/camera.example.json /etc/item-tracking/camera.json
sudo cp systemd/item-tracking-camera.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now item-tracking-camera
sudo journalctl -u item-tracking-camera -f
```

仓库内的单元模板默认 `User=pi`，且 `WorkingDirectory` 指向仓库路径；现场部署账号为 `nick`、模块位于 `/home/nick/raspberry_pi`，安装时已按实际路径修改。其他成员按自己路径调整。

### 验证

```bash
curl http://127.0.0.1:8080/health
curl -o snapshot.jpg http://127.0.0.1:8080/snapshot
```

```powershell
py -3 backend/run.py --camera opencv --source http://<树莓派IP>:8080/video --start --demo
```

### 常见异常

| 现象 | 原因与处理 |
| --- | --- |
| `Device or resource busy` | 摄像头被其他进程占用（旧服务、`rpicam-hello`、残留 python）。先 `ps -ef \| grep -Ei 'rpicam\|libcamera\|camera'` 找到并停止，确认只保留一个实例 |
| 画面红蓝对调 | 取帧数组顺序与预期不符，`source.py` 中不可再对 `capture_array` 结果做 RGB→BGR 转换 |
| 电脑端 timeout | 电脑与树莓派不在同一网段；ICS 下应为 `192.168.137.x`，WSL 终端访问不到该网段，需用 Windows PowerShell |
| 重启后 IP 变化 | 用 `Get-NetNeighbor -InterfaceAlias "以太网"` 重新查地址，或改为固定地址后重配后端 `--source` |
| `.local` 无法解析 | 主机名非默认值，直接使用 IP |

## 五 剩余事项

| 类别 | 事项 | 责任 |
| --- | --- | --- |
| 本岗位未完成 | 分支推送与 PR：token 所属账号 `Nick666-666` 对 `Ddatopos/Item-Tracking-System` 无写权限（403），需仓库负责人授权或改用有权限账号 | 王韵哲 / 孙正群 |
| 本岗位未完成 | 另一位成员按 README 独立复现并重启设备服务取流 | 王韵哲 / 指定成员 |
| 待确认 | 与王琪臻确认 `OpenCVCamera` 接入结论（技术验证已完成） | 王琪臻 |
| 待确认 | 浏览器人工确认 `/video` 画面 | 王韵哲 |
| 可选 | 物理拔网线 30 秒复测（当前用 TCP 中断模拟） | 王韵哲 |
| 待确认 | `docs/device/samples/` 两张宿舍实拍是否可公开进仓库 | 王韵哲 |
| 后续整体验收 | 真实 YOLO 适配、统一启动器、安装包与整体回归 | 孙正群 |

## 六 交付位置

- 本地分支：`feature/wang-camera`，提交 `ed79391`、`c9f9066`、`cff68f1`
- 远端状态：尚未推送。当前 remote `ghproxy` 为只读镜像；`github` remote 已配置，推送返回 `403 Permission to Ddatopos/Item-Tracking-System.git denied to Nick666-666`
- 仓库：`https://github.com/Ddatopos/Item-Tracking-System`
- 建议 PR 标题：`feat: 树莓派视频源交付与可靠性（A1-A6）`
- 需要配合：孙正群处理仓库写权限并审查合并申请；王琪臻确认后端接入；另一位成员执行复现
- 提交内容不含密码、密钥、虚拟环境、模型权重和实例配置 `configs/camera.json`
