# 基于神经网络的物品示踪系统 V1.0 API

后端根地址 `http://127.0.0.1:5000`。所有运行实例通过 app_factory 创建，正式启动使用 `python backend/run.py`。控制请求使用 POST，设置使用 PUT/PATCH；JSON 应声明 `Content-Type: application/json`。此文档的路径和字段由自动测试验证，不表示真实硬件和真实模型已经联调。

## 健康和状态

| 方法 | 路径 | 返回 |
| --- | --- | --- |
| GET | /api/health | name version service_status state status cameras stream inference |
| GET | /api/status | 运行状态 摄像头/推理错误 帧率 队列 计数和模拟标志 |
| GET | /api/cameras | cameras 数组 active_camera_id 和当前源状态 |

`health.service_status=ok` 表示进程和接口存活；`status=online/connecting/offline` 表示摄像头状态，兼容当前前端。`health.stream={preview_url,status}`，`health.inference={status,model_version,fps}`。停止取帧时进程仍可健康，不把没有设备等同于进程崩溃。

`/api/status` 的主要字段为 state、camera_state、inference_state、camera_error、inference_error、frame_id、frame_age_ms、capture_fps、inference_fps、queue_length、queue_capacity、in_flight、preview_clients、preview_enabled、last_inference_ms、detector_version、detector_simulated、camera_simulated、uptime_seconds；另有 captured_frames、inference_calls、inference_errors、camera_errors、skipped_frames、events_created、events_merged、preview_parts。

capture_fps/inference_fps 是最近至多三百次样本的窗口频率，不是承诺值；停止或超过三秒没有样本后显示零。status_latency 由持续测试外部测量。queue_length 只能是 0 或 1，正在执行的推理另外统计为 in_flight。

## 运行和预览

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| POST | /api/runtime/start | 幂等启动唯一取帧线程 changed 表示是否新启动 |
| POST | /api/runtime/stop | 先停止推理 再停止取帧 可再次启动 |
| POST | /api/stream/start | 开启预览 必要时启动取帧 |
| POST | /api/stream/stop | 停止预览输出 保留后台推理 |
| GET | /api/stream | MJPEG multipart/x-mixed-replace |
| GET | /api/preview | MJPEG 同义路径 |
| GET | /api/stream/preview | 当前前端预览兼容路径 |
| GET | /api/snapshot | 单张 JPEG X-Frame-Id 和 X-Captured-At 响应头 |
| GET | /snapshot | 兼容单张预览路径 |
| POST | /api/inference/start | 必要时启动取帧 幂等启动后台识别 |
| POST | /api/inference/stop | 停止后台识别 预览继续 |
| POST | /api/shutdown | 关闭所有运行资源 正式入口同时退出服务器 |

打开流之前先 start；没有运行或被关闭预览时返回 409。默认四个预览客户端上限，超限返回 409，断开释放名额。snapshot 没有新鲜帧返回 503，绝不在请求线程调用检测器。MJPEG 每个部分含 Content-Type、Content-Length、X-Frame-Id。摄像头暂时断线时流等待重连，并约每半秒发送 multipart 空白心跳，以便服务器检测已经断开的客户端；不把旧画面重发成新帧。主动 stop 或 shutdown 结束流。

没有配置真实检测器且未启用 demo 时，inference/start 返回 409，并明确提示 DetectorService 未配置。重复 inference/start 返回 changed=false，不产生第二个模型调用线程。

## 设置

GET `/api/settings` 返回以下五个规范字段，并附带旧单类别前端的别名和只读信息。PUT/PATCH 为合并更新，未知键、非法类型、NaN、无效数值和冲突的别名均返回 400，不会部分保存。

```json
{
  "inference_fps": 2.0,
  "confidence_threshold": 0.25,
  "selected_classes": [],
  "dedup_seconds": 30.0,
  "input_size": 640
}
```

旧字段映射：confidence → confidence_threshold，inference_frequency → inference_fps，category=all → 空类别数组，单个 category → 单元素类别数组。model 和 camera_id 是当前工厂和配置的只读值；可以原值回传，不能在线更换。多类别应只更新 selected_classes，不同时回传含糊的 category=all。

## 事件和最后出现查询

| 方法 | 路径 | 返回 |
| --- | --- | --- |
| GET | /api/items | 类别字符串数组 保留第一版格式 |
| GET | /api/items/{category} | 最后出现记录 保留原字段并扩展元数据 |
| GET | /api/search?item_name=类别 | 旧搜索兼容 success items 以及 items: |
| GET | /api/events | DetectionEvent 扩展对象数组 |
| GET | /api/events?envelope=1 | 分页对象 events total limit offset |
| GET | /api/events/{event_id} | 一条完整事件记录 |
| GET | /api/events/{event_id}/image | 当前原图 稳定 URL |
| GET | /api/events/{event_id}/annotation | 当前标注图 稳定 URL |

category 和 event_id 放入 URL 路径时必须编码。`/api/items/{category}` 的旧字段为 category、image_path、processed_image_path、timestamp；新增 event_id、room、camera_id、bbox、confidence、model_version。timestamp 表示 last_seen，输出 UTC ISO 时间，不再使用无时区字符串。图片字段保持可直接访问的 URL 格式。

事件过滤参数：class_name（兼容 category）、camera_id、since、until、limit（1 到 1000，默认 100）、offset（默认 0）。时间按 last_seen 过滤，since/until 包含边界，按 last_seen 降序排列。envelope=1 时 total 为过滤后总数，适合分页界面。类别不存在、事件不存在返回 404；空事件列表返回 200 和空数组。

事件必需字段：event_id、frame_id、camera_id、room、class_name、confidence、bbox、captured_at、model_version、raw_image_path、annotated_image_path。另有 first_seen、last_seen、observations、inference_params；列表附加稳定 image_url 和 annotated_image_url。frame_id 为字符串，bbox 为四个像素坐标，路径为数据目录内的相对路径。

同类别的连续观测只保留一个会话事件并更新代表图；observations 反映合并次数。不要以事件条数代替检测帧数，也不要把同类别多个物品解释为已区分的独立实体。

## 图片和 CSV

GET `/images/{filename}` 与 `/processed/{filename}` 保留第一版路径，但读取位置改为运行数据目录；用 migrate-legacy 导入原图片。GET `/media/{relative_path}` 仅允许 data/images 或 data/processed_images 下的 JPG/PNG。路径穿越、目录联接逃逸、非图片类型或不存在文件返回 404。

前端优先使用稳定事件图片 URL。磁盘文件名会随代表图更新而替换，旧的 `/media` 版本路径可能返回 404；该行为避免无限保留每次检测的图片。

GET `/api/events/export` 导出 UTF-8 BOM CSV，前四列为第一版 timestamp、class_name、location、image_id，后续包含完整事件元数据。POST `/api/events/import` 接收原始 UTF-8 CSV body，Content-Type 必须是 text/csv，最大四 MiB、一万行。整批验证成功才写入，返回 `{inserted,skipped,rows}`。相同 event_id 或相同第一版记录重复导入会跳过。

CSV 内 location 必须是 JSON 数组，如 `"[1,2,3,4]"`，不执行 Python 表达式。无时区旧时间按 UTC+8 解释。CSV 不承载图片文件；完整备份恢复使用 manage.py，不应依靠 CSV 保证图片和设置齐全。

## 错误和访问限制

```json
{
  "error": {
    "code": "invalid_request",
    "message": "inference_fps must be between 0.1 and 30",
    "request_id": "请求标识"
  },
  "message": "inference_fps must be between 0.1 and 30"
}
```

顶层 message 为旧前端兼容字段；响应头 X-Request-Id 与 error.request_id 一致。常见状态码：400 参数，403 Host/来源，404 不存在，405 方法，409 运行冲突或关闭超时，413 上传过大，415 媒体类型错误，500 内部故障，503 无新鲜视频帧。500 响应不返回堆栈，原因记在本地日志。

只接受 localhost/127.0.0.1 Host 与本机客户端。浏览器控制请求默认必须同源，不开放通配 CORS。原 React 开发代理联调需显式使用 --dev-proxy，额外信任 http://localhost:3000 和 http://127.0.0.1:3000 的来源，解决代理重写 Host 的情况；正式部署不使用该开关。桌面壳应加载本机 HTTP 页面，不能依赖 Origin null 或任意第三方网页控制服务。shutdown 后 health/status 仍可读取关闭状态，其余需要资源的 API 返回 409；正式进程将随后退出。
