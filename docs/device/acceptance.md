# 设备端验收记录

本记录用于 A1 到 A6 的设备端验收。实际结果、结论、时间和提交号必须由执行人在实机测试后填写，禁止预先填写或照抄他人结果。A1 至 A4 及 A5 的服务重启部分已于 2026-11-08 在实机（Pi 4B + IMX708，Debian 13）执行并记录，其余项仍为“待成员实机执行”。

## 一 A1-A6 验收记录表

| 编号 | 任务 | 命令 | 预期 | 实际结果 | 结论 | 时间 | 提交号 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | 安装依赖并识别摄像头 | `cd device/raspberry_pi && ./scripts/install.sh`；`rpicam-hello --list-cameras` | 依赖安装成功，能列出 IMX708 摄像头及其原生模式 | `rpicam-hello --list-cameras` 输出 `imx708 [4608x2592 10-bit]`，模式 1536x864、2304x1296、4608x2592 均 30fps；python3-picamera2、python3-opencv 4.10.0、python3-numpy 已预装，未重复执行 install.sh | 通过 | 2026-11-08 12:28 | 待提交 |
| A2 | 启动服务并检查健康状态 | `cp configs/camera.example.json configs/camera.json`；`./scripts/start.sh`；`curl http://127.0.0.1:8080/health` | 返回 JSON，`state` 为 `running`，`camera_state` 为 `online`，`resolution` 与实际配置一致 | `/health` 返回 `state=running`、`camera_state=online`、`resolution=1280x720`、`measured_fps=15.0`、`errors=0`；systemd 启动后 3.6 秒内恢复 online | 通过 | 2026-11-08 13:07 | 待提交 |
| A3 | 浏览器与电脑端后端取流 | 浏览器打开 `http://<树莓派IP>:8080/video`；电脑端执行 `py -3 backend/run.py --camera opencv --source http://<树莓派IP>:8080/video --start --demo` | 浏览器看到实时画面；后端 `camera_state` 为 `online`，预览正常 | 后端以 `--source http://192.168.137.40:8080/video` 启动后 `/api/status` 返回 `camera_state=online`、`capture_fps=13.674`、`camera_simulated=false`，`/api/snapshot` 返回 82683 字节 JPEG；浏览器预览未人工确认 | 通过（浏览器项待确认） | 2026-11-08 13:00 | 待提交 |
| A4 | 30 分钟连续运行 | 保持 A3 链路，每 5 分钟记录 `curl http://<树莓派IP>:8080/health` | 30 分钟内 `frames` 持续增长，`errors` 不增加，`measured_fps` 接近 `configured_fps`，无内存持续增长或过热降频 | 连续运行 36 分 14 秒：`frames=32248`、`errors=0`、`measured_fps=15.1`、CPU 42.8%、RSS 181 MB、温度 34.5℃、`throttled=0x0` | 通过 | 2026-11-08 13:05 | 待提交 |
| A5 | 短时断网恢复与服务重启恢复 | 断网约 30 秒后恢复；执行 `sudo systemctl restart item-tracking-camera` | 断网期间后端 `camera_state` 变为 `offline`，恢复后自动回到 `online`；重启服务后后端自动恢复取流，无需重启整机 | `systemctl restart` 后 3.6 秒恢复 `online` 且 `frames` 重新增长；断网 30 秒项未执行 | 部分通过 | 2026-11-08 13:07 | 待提交 |
| A6 | 换 IP 后重新配置接入 | 树莓派获得新 IP 后，电脑端用新地址重新执行 `py -3 backend/run.py --camera opencv --source http://<新IP>:8080/video --start --demo` | 旧地址失效，新地址可正常取流；设备端配置无需修改 | 待成员实机执行 | 待填写 | 待填写 | 待填写 |

## 二 自动测试

在仓库根目录执行（Windows 使用 `py -3`，Linux 树莓派使用 `python3`）：

```powershell
py -3 -m pytest device/raspberry_pi/tests -q
```

```bash
python3 -m pytest device/raspberry_pi/tests -q
```

预期：全部用例通过，无跳过、无告警导致的挂起。测试只使用模拟摄像头，不依赖 picamera2 和真实硬件。开发机结果不作为实机验收结论，实机复跑后需另行记录。

## 三 设备端测试清单

| 类别 | 检查项 | 方法 | 预期 |
| --- | --- | --- | --- |
| 配置 | 默认值完整 | `load_config()`（默认配置缺失） | 返回全部 17 个字段及文档默认值 |
| 配置 | 读取 JSON 与覆盖优先级 | 指定 `--config` 或 `PI_CAMERA_CONFIG` | 文件值生效，显式覆盖值优先，`None` 覆盖被忽略 |
| 配置 | 非法字段 | 未知字段、越界值、错误类型、非法对焦和日志级别 | 抛出中文 `ConfigError` |
| 配置 | 配置文件不存在 | `--config` 指向不存在的文件 | 中文错误，进程退出码 2 |
| 采集 | 正常取帧 | 启动后访问 `/health` | `camera_state` 为 `online`，`resolution` 为 `1280x720` |
| 采集 | 快照 | `curl -o snapshot.jpg http://127.0.0.1:8080/snapshot` | 200，JPEG 以 `FF D8` 开头 |
| 采集 | 单摄像头单次占用 | 两个客户端同时打开 `/video` | 摄像头只打开一次，两个流都能收到数据 |
| 采集 | 客户端上限 | `max_clients=1` 时打开第二个 `/video` | 第二个请求返回 503 JSON |
| 采集 | 无帧时快照 | 服务未启动 | `/snapshot` 返回 503 JSON |
| 采集 | 非法帧 | 摄像头返回二维数组 | `camera_state` 变为 `offline` 或 `error`，`errors` 大于 0 |
| 采集 | 打开失败耗尽重试 | 连续打开失败且 `open_attempts=2` | 最终 `state` 为 `error`，`last_error` 非空 |
| 服务 | 停止与再次启动 | 停止后连接端口，再启动 | 端口拒绝连接，摄像头已关闭；再次启动后 `frames` 继续增长 |
| 服务 | 未知路径 | `curl http://127.0.0.1:8080/not-found` | 404 JSON |
| 实机 | 断线重连 | 断开并恢复网络 | 由电脑端后端负责重连，设备端恢复后继续提供新帧 |
