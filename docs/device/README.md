# 设备端视频源协议与联调说明

本目录说明树莓派摄像头设备端（`device/raspberry_pi`）对外提供的 HTTP 视频源协议、电脑端后端接入方式、A5 实机测试步骤和排障方法。设备端只负责采集与分发画面，不做识别，不定义后端公共类型。

## 一 协议

服务默认监听 `0.0.0.0:8080`，只提供 GET 接口，全部为 HTTP/1.0 语义（响应结束即关闭连接，不使用 keep-alive）。

| 端点 | 响应 | 说明 |
| --- | --- | --- |
| `/` | `200 application/json` | 状态字段 + `version` + `endpoints` |
| `/health` | `200 application/json` | 健康状态，字段与 `/status` 相同 |
| `/status` | `200 application/json` | 运行状态 |
| `/snapshot` | `200 image/jpeg` | 最新一帧；无新鲜帧返回 `503` JSON |
| `/video` | `200 multipart/x-mixed-replace; boundary=frame` | MJPEG 视频流 |
| `/stream` | 同上 | `/video` 的别名 |
| 其它路径 | `404 application/json` | `{"error": "未知路径：..."}` |

### 1 状态 JSON 字段

| 字段 | 说明 |
| --- | --- |
| state | 服务状态：`stopped`、`running`、`error` |
| camera_state | 摄像头状态：`stopped`、`offline`、`online`、`error` |
| camera_id | 配置的摄像头标识 |
| room | 配置的房间名称 |
| source_type | 取帧实现，实机为 `picamera2` |
| resolution | 最近一帧的 `宽x高`，尚无帧时为 `unknown` |
| configured_fps | 配置的帧率 |
| measured_fps | 最近 30 帧的实测帧率，保留 1 位小数 |
| frames | 成功发布的帧总数 |
| errors | 采集或编码失败次数 |
| last_error | 最近一次错误，格式为 `异常类名: 消息`，无错误时为 `null` |
| clients | 当前视频流客户端数 |
| max_clients | 允许的视频流客户端上限 |
| uptime_seconds | 本次运行时长（秒） |
| frame_age_ms | 最近一帧距今毫秒数，无帧时为 `null` |
| timestamp | UTC 时间，ISO 格式并带毫秒和 `Z` |

`/` 额外返回 `version`（设备端版本，当前 `1.0.0`）与 `endpoints`（可用路径列表）。

### 2 快照

`GET /snapshot` 返回 `image/jpeg`，带 `Cache-Control: no-store` 与 `X-Frame-Id`。帧龄超过 `frame_stale_seconds` 时返回 `503`：

```json
{"error": "当前没有可用的视频帧"}
```

### 3 MJPEG 视频流

`GET /video` 与 `GET /stream` 返回 `multipart/x-mixed-replace; boundary=frame`，不设置 `Content-Length`，连接关闭即结束。每一部分格式固定为：

```text
--frame\r\n
Content-Type: image/jpeg\r\n
Content-Length: <字节数>\r\n
X-Frame-Id: <帧序号>\r\n
\r\n
<jpeg 数据>\r\n
```

无新帧时服务端写入 `\r\n` 作为心跳，避免客户端误判断流。客户端主动断开时服务端结束该处理线程并释放客户端名额。超过 `max_clients` 时返回 `503` JSON。

### 4 权限与编码

所有 JSON 均为 UTF-8 且不转义中文（`ensure_ascii=False`）。服务端只记录日志，不向终端打印。

## 二 电脑端后端接入

在电脑端仓库根目录执行（地址必须替换为树莓派实际 IP，示例地址来自本次实验网络配置）：

```powershell
py -3 backend/run.py --camera opencv --source http://192.168.137.40:8080/video --start --demo
```

参数说明：

| 参数 | 说明 |
| --- | --- |
| `--camera opencv` | 后端使用 `OpenCVCamera`，内部以 FFmpeg 打开网络源，打开和读取超时各 2 秒 |
| `--source` | 设备端 MJPEG 地址，通常为 `http://<树莓派IP>:8080/video` |
| `--start` | 启动后立即开始取帧 |
| `--demo` | 使用模拟识别器，仅验证取流链路，不代表真实识别结果 |

验证：浏览器打开 `http://127.0.0.1:5000/api/preview` 应看到画面，`http://127.0.0.1:5000/api/status` 的 `camera_state` 应为 `online`。

## 三 A5 实机测试步骤

测试前准备：树莓派已完成 `scripts/install.sh`，已复制并修改 `configs/camera.json`；电脑与树莓派在同一网段；记录树莓派 IP。

1. 30 分钟连续运行
   - 启动设备端服务，电脑端按上文命令接入。
   - 连续运行 30 分钟，每 5 分钟记录一次 `curl http://<树莓派IP>:8080/health` 的 `frames`、`measured_fps`、`errors`、`frame_age_ms`。
   - 同时记录后端 `/api/status` 的 `camera_state` 与预览页面是否正常。
   - 记录开始和结束时的树莓派内存与温度（`free -m`、`vcgencmd measure_temp`），观察是否持续增长或过热降频。
2. 短时断网恢复
   - 断开电脑与树莓派之间的网络（拔网线或关闭交换机端口）约 30 秒后恢复。
   - 观察设备端 `frames` 是否继续增长、`errors` 是否增加；观察电脑端 `camera_state` 从 `offline` 恢复为 `online` 所需时间（后端重连周期由 `RECONNECT_SECONDS` 控制，默认 1 秒）。
3. 重启服务恢复
   - 执行 `sudo systemctl restart item-tracking-camera`（或 `./scripts/stop.sh && ./scripts/start.sh`）。
   - 记录后端自动恢复取流所需时间，确认为重启服务而不是重启整机后仍能恢复。
4. 换 IP 后重新配置
   - 让树莓派通过 DHCP 获得新 IP（或在路由器重新分配），确认旧地址失效。
   - 在电脑端用新地址重新执行后端启动命令，验证取流恢复；设备端配置不需要修改（监听 `0.0.0.0`）。

记录要求：每条测试记录时间、操作命令、设备端 `/health` 原始 JSON、后端 `/api/status` 关键字段、观察到的现象与结论；失败时保留 `journalctl -u item-tracking-camera` 或 `run/camera.out` 日志。结果填写到 `docs/device/acceptance.md`，未实测的项目不得填写通过。

## 四 排障

| 现象 | 排查方法 |
| --- | --- |
| `/dev/video` 被占用 | libcamera 与 V4L2 程序互斥。用 `sudo fuser -v /dev/video*` 或 `lsof /dev/video*` 找到占用进程并停止；不要同时运行 `libcamera-vid`、`rpicam-vid` 或其它打开摄像头的程序。 |
| libcamera 报错 | 执行 `rpicam-hello --list-cameras` 确认摄像头被识别；`dmesg | grep -i imx708` 查看驱动日志；检查排线是否插紧、是否在关机状态插拔；必要时重启设备。 |
| 帧率低 | 比较 `configured_fps` 与 `measured_fps`；降低 `width`/`height` 或 `jpeg_quality`；优先使用网线；检查 Wi-Fi 信号与同时使用网络的其它程序。 |
| MJPEG 打不开 | 先用 `/snapshot` 判断采集是否正常；`curl -v http://<IP>:8080/video` 查看响应头；确认客户端支持 `multipart/x-mixed-replace`；确认未超过 `max_clients`。 |
| 无法访问 8080 | 检查监听 `ss -ltnp | grep 8080`；放行防火墙 `sudo ufw allow 8080/tcp`；确认电脑与树莓派在同一网段，用 `curl http://<IP>:8080/health` 从电脑端验证。 |
| Wi-Fi/网线双网卡选路 | 用 `ip route` 查看默认路由，确认电脑访问的地址与树莓派回包走同一网卡；可临时关闭不用的网卡（`sudo ip link set wlan0 down`）或用 `curl --interface` 指定出口验证；需要固定地址时在路由器做静态分配。 |

## 五 职责边界

- 设备端只保证：摄像头单次占用、进程可重启、状态可查询、帧可通过 HTTP 获取。
- 设备端不实现断线重连、重试调度和识别逻辑；电脑端后端的取流重连由 `RECONNECT_SECONDS` 负责，设备端只在本进程内按 `open_attempts` 重试摄像头打开。
- 设备端不生成后端公共类型（如 `CameraFrame`），不加载 YOLO，不写入数据库。
- 设备端启动阶段配置错误退出码为 2，采集致命错误退出码为 1，systemd 通过 `Restart=on-failure` 拉起。
