# 基于神经网络的物品示踪系统 V1.0 后端设计

任务书版本：第二版。第一版来源提交：`16cde2f704e9237bf74e9b30de1de3ee75df0ffb`。本设计覆盖王琪臻的后端岗位，不实现模型内部或 React 页面。

## 第一版基线

第一版 backend/app.py 在模块加载时创建 Flask 和 Processor；数据来自 CSV，每次查询用 pandas 读取、排序，并可能在请求线程用 OpenCV 生成框图。没有摄像头线程、共享帧、后台 DetectorService、SQLite、统一状态或自动测试。配置开启 DEBUG，监听 0.0.0.0；Flask-Cors 默认开放跨源。图片接口直接提供原代码目录下的文件。

静态检查还发现旧 `/api/search` 用 `items:` 作为键。原图缺失时仍可能返回不存在的框图路径。第一版没有摄像头/模型公共 Python 模块，因此本版将唯一合同放在 `tracking/contracts.py`，后续适配器必须导入它，不应各自复制 dataclass。

## 模块关系

```text
Flask application factory
  ├─ API → RuntimeManager → 单个 CameraSource 实例
  │                        ├─ capture worker → 最新 CameraFrame + JPEG 缓存
  │                        └─ inference worker → DetectorService → DetectionEvent
  ├─ API → Repository ← inference worker
  │         └─ SQLite + 原图 + 标注图
  └─ MJPEG request workers → 仅等待和读取缓存 JPEG
```

应用工厂可注入摄像头、检测器和独立数据目录；构造时不启动线程、不打开设备。生产入口使用数据目录进程锁，创建一个应用、一个源对象、一个取帧线程和至多一个推理线程。禁止 reloader、多 WSGI 进程和每客户端自行打开摄像头。不同运行目录仍可能连接同一真实设备，部署者必须避免这种配置。

运行控制用 RLock 串行化启停；最新帧及计数用 Condition 保护。图像在取帧时复制并设为只读，JPEG 只编码一次，多个预览请求共享 bytes。推理接收自己持有的图像副本，不能污染预览。

无待处理帧队列。共享缓存最多保存一个最新帧，另有一个正在推理的副本；推理完成后跳过中间帧，读取当前最新帧。`queue_capacity=1`，`queue_length` 表示最新缓存是否含尚未被推理领取的新帧，`in_flight` 独立表示当前调用。缓存不是历史视频队列。

## 公共合同

唯一类型定义在 `backend/tracking/contracts.py`。当前仓库未包含其他成员的真实摄像头和模型模块，此合同是待团队确认并复用的接入版本，不声称已完成跨成员联调。

| 对象 | 字段和类型 |
| --- | --- |
| CameraFrame | frame_id 字符串、camera_id 字符串、room 字符串、captured_at UTC ISO 时间、width/height 整数、source_type 字符串、image BGR uint8 ndarray |
| DetectionEvent | event_id 字符串、frame_id 字符串、camera_id 字符串、room 字符串、class_name 字符串、confidence 数值、bbox 四个数、captured_at UTC ISO 时间、model_version 字符串、raw_image_path/annotated_image_path 字符串 |

`frame_id` 使用字符串，与已有 TypeScript 类型一致。运行后端当前生成递增十进制帧编号，唯一性范围为一次运行实例；事件使用独立全局标识，不将帧编号作为跨进程唯一键。`image` 是 Python 内存对象，不直接 JSON 序列化；HTTP 预览使用 JPEG。检测框采用像素坐标 `[xmin,ymin,xmax,ymax]`，右下角必须大于左上角且在帧尺寸内。

CameraSource 提供 `source_type`、`open()`、`read()`、`close()`；read 返回 BGR ndarray 或在错误时抛异常，由运行后端统一填充 CameraFrame。该方法签名与设备适配职责需要王韵哲、孙正群确认；若已有设备代码返回 CameraFrame，应写薄适配层提取其图像并统一元数据配置，不另建字段不同的类型。所有设备方法都必须有界返回，并只在同一个取帧线程内调用。

DetectorService 提供 `model_version`、`simulated`、`detect(frame,settings)`、`close()`。detect 返回共享 DetectionEvent 的序列；帧号、摄像头、房间、采集时间必须与传入帧完全一致。模型在工厂中加载一次，detect 只能在后台工作线程调用。模型必须在 shutdown timeout 内返回；Python 线程无法安全强制中断永久阻塞的第三方模型调用。

工厂接口为本机显式配置的 `module:function`，返回实例。不接受通过 HTTP 传入模块名、模型路径或摄像头地址。未提供检测器时允许预览和历史查询，但启动识别返回 409；只有明确 `--demo` 才启用 FakeDetector。

适配器结构示意，真实模型调用由孙正群补入：

```python
from tracking.contracts import CameraFrame, DetectionEvent

class ProjectDetector:
    model_version = '团队实际确认的模型版本'
    simulated = False

    def detect(self, frame: CameraFrame, settings: dict):
        # 调用已加载模型；将结果转为共用 DetectionEvent。
        # 使用 frame 的元数据，不重新打开视频源。
        # 路径由后端生成，模型返回空字符串即可。
        return self.detect_with_existing_model(frame, settings)

    def close(self):
        # 释放本模型拥有的资源。
        pass

def create_detector():
    return ProjectDetector()
```

## 状态和故障恢复

| 层面 | 状态 |
| --- | --- |
| runtime | stopped、running、shutdown、shutdown_failed |
| camera | stopped、connecting、online、offline |
| inference | stopped、starting、waiting_for_frame、running、error、stopping |

摄像头异常时清空旧帧并标为 offline，释放当前连接，默认一秒后用同一 CameraSource 实例重试。网络 OpenCV 源设置两秒打开和读取超时；UVC 原生驱动的阻塞行为必须实机验证。没有新鲜帧时 snapshot 返回 503，推理等待新帧，状态查询保持可用。默认新鲜度为三秒。

推理异常记入错误计数、日志和状态，后续帧自动重试。推理变慢时丢弃中间帧；`skipped_frames` 统计两次领取帧之间被跳过的数量，不代表取帧失败。设置 inference_fps 是目标调用上限，慢模型的实际频率会更低。

MJPEG 默认最多四个客户端，Waitress 设十二个线程。响应关闭时释放名额，包括尚未开始迭代就断开的响应。停止预览通过递增生成号结束现有流，不停止后台识别；停止识别保留预览。离线时客户端等待重连，源不因单个客户端断开而关闭。

## SQLite 设计

数据库文件位于数据目录 `tracking.sqlite3`，使用 WAL、外键、FULL synchronous、五秒 busy timeout 和串行 RLock。单连接允许后台线程访问；所有 SQL 访问受锁保护，事务完成后才暴露新事件。schema 当前为 user_version 1，拒绝较新版本数据库以避免降级破坏。

| 表 | 主键与字段 |
| --- | --- |
| cameras | camera_id 主键；room、source_type |
| settings | key 主键；value 为 JSON |
| detection_events | event_id 主键；完整 DetectionEvent 字段；first_seen、last_seen、observations、inference_params |

`bbox` 和 `inference_params` 为 JSON 文本。按 `(camera_id,class_name,last_seen)` 和 last_seen 建索引。查询只用参数绑定；字段筛选由服务固定，不允许用户拼接 SQL。原始推理参数随代表图一起记录，便于复现。

## 去重和代表图

同摄像头、同房间、同类别，距离上一观测的采集时间不超过 dedup_seconds 时更新同一事件；保持 first_seen，更新 last_seen、captured_at、frame_id、confidence、bbox、图片和参数，并递增 observations。连续出现可以长期保持一条事件；间隔超过窗口后创建新事件。它是类别出现会话去重，不是同类个体识别。

同一帧同类别多个框只选置信度最高的一个作为代表，不能据此声称区分同类物品。跨摄像头、不同房间或不同类别分别存储。去重减少重复事件 INSERT，但仍要更新最后出现时间和代表图，因此不等于每帧零磁盘写入；写入频率受 inference_fps 限制。

先把新原图和标注图写入临时文件并原子替换为随机文件名，随后提交数据库；提交成功后删除旧代表图，提交失败则清理新图。突然断电可能遗留未引用图片，不应自动删除仍被数据库引用的文件。删除遇到文件占用时保留旧图，不影响事件查询；可在停机备份后离线核对并清理孤立文件。

查询返回稳定的 `/api/events/{event_id}/image` 和 annotation 地址。图片读取在仓库锁内取得当前代表图内容，防止查询后换图造成链接失效。磁盘相对路径保留在记录和 CSV 内供备份使用，不应当作稳定前端 URL。

## 配置和设置

| 配置 | 默认值与用途 |
| --- | --- |
| TRACKING_DATA_DIR 或 --data-dir | 项目根 runtime；SQLite 图片 日志 |
| TRACKING_CAMERA_KIND 或 --camera | mock；也可 opencv |
| TRACKING_CAMERA_SOURCE 或 --source | 0；设备号或网络流地址 |
| TRACKING_ROOM 或 --room | 未设置房间 |
| TRACKING_FRONTEND_DIR 或 --frontend-dir | 空；可选已有前端构建目录 |
| --detector-factory | 空；真实 DetectorService 工厂 |
| --camera-factory | 空；自定义 CameraSource 工厂 |
| --demo | 关闭；明确启用模拟识别 |
| --start 和 --infer | 默认不自动采集或推理 |
| --port | 5000；主机固定 127.0.0.1 |
| --dev-proxy | 默认关闭；开发时显式信任 localhost/127.0.0.1 的 3000 端口来源 |

运行内设置：inference_fps 默认 2，允许 0.1 到 30；confidence_threshold 默认 0.25，范围 0 到 1；selected_classes 默认空数组；dedup_seconds 默认 30，范围 0 到 3600；input_size 默认 640，允许 32 到 2048 的 32 倍数。设备、模型、采集帧率及关闭超时不是 HTTP 可任意修改项。

## 关闭与恢复顺序

1. shutdown 标记 closing，拒绝新的运行操作。
2. 设置推理停止信号并等待当前 detect 返回；退出时不再保存新事件。
3. 设置取帧停止信号，唤醒并结束预览生成器。
4. 等待取帧线程结束，由其 finally 释放摄像头。
5. 调用 detector.close，检查点合并 WAL，关闭 SQLite。
6. 正式运行入口发送关闭响应后关闭 Waitress，释放数据目录锁。

重复 start/stop 不增加设备或线程。shutdown 幂等，shutdown 后必须新建运行实例。关闭超时时不在仍有活跃线程使用数据库时强行关闭连接，返回 409 或记录失败；适配器恢复返回后可再次关闭。不可将永久阻塞的设备/模型适配器作为已通过的正式接入。

完整备份必须先停机并取得数据目录锁，使用 SQLite backup API，再复制图片和日志，输出 ZIP 和 SHA256 清单。恢复只到不存在的新目录，校验全部路径、摘要及数据库完整性。代码和数据分开保存，更新前备份，故障时改回旧目录与匹配代码。

## 安全边界和剩余工作

图片访问经过 resolve 后必须位于数据目录内，只允许原图和标注图目录及图片后缀，拒绝路径穿越和目录联接逃逸。API 只接受本机 Host/客户端，控制请求校验浏览器 Origin，不开放通配 CORS。CSV 最大四 MiB、一万行，全部行验证成功后再提交。

这是一套本机单用户后端，没有互联网账户授权。当前有日志轮转，没有图片和事件的自动保留期限；长期部署需要观察磁盘空间，先备份再由团队确定清理策略。真实硬件对比、真实 YOLO 性能与授权、前端强制模拟开关、桌面打包和桌面 open_data_dir/export_logs 按钮由对应成员继续集成；日志导出目前通过离线 CLI 提供。

## 原创功能与依赖

原创模块为运行调度、共享帧缓存、控制 API、SQLite 仓库、类别会话去重、CSV 兼容、维护工具和测试。Flask、Werkzeug、OpenCV、NumPy、Waitress 等以第三方依赖方式使用；不修改其源码，不将其源码、权重、构建产物和自动生成文档计入原创代码。详细版本和许可证见 `DEPENDENCIES.md`。
