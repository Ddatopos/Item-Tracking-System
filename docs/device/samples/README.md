# 宿舍实拍样例

本目录存放王韵哲在宿舍实机拍摄的少量样例，仅用于证明摄像头与视频源工作正常，不构建测试数据集。

| 文件 | 来源 | 说明 |
|---|---|---|
| `pi_still_reference.jpg` | `rpicam-still --width 1280 --height 720 -t 2500` | 用于校对颜色和服务输出的参考图 |
| `pi_service_snapshot.jpg` | `GET http://<树莓派IP>:8080/snapshot` | 修复 RGB/BGR 通道顺序后由服务输出的 JPEG |

拍摄参数：

- 设备：树莓派 4B 4GB + Camera Module 3 Wide（IMX708）
- 系统：Debian GNU/Linux 13 (trixie)，aarch64，libcamera 0.7.2
- 分辨率：1280×720，帧率 15fps，JPEG 质量 80
- 对焦：continuous 自动对焦
- 环境：宿舍，室内灯光，2026-11-08

说明：早期版本曾出现红蓝通道互换（标签显示为橙色、木色墙面显示为蓝色），已通过去掉多余的 RGB→BGR 转换修复；`pi_service_snapshot.jpg` 为修复后的输出。
