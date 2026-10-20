# 基于神经网络的物品示踪系统 V1.0 后端第二版交付报告

交付日期：2026年10月18日。岗位：王琪臻。依据第二版任务书，保留 Flask 与旧查询合同，在本地完成后端改进、模拟链路验证和操作文档。原 GitHub 仓库基线为 `16cde2f704e9237bf74e9b30de1de3ee75df0ffb`。没有执行 git add、commit、push、远程发布或创建 Pull Request；源任务书未修改。

## 完成内容

| 任务 | 状态 | 交付与验收 |
| --- | --- | --- |
| C1 运行架构 | 后端已完成 | 应用工厂、唯一公共合同、RuntimeManager、单源和单推理线程、顺序关闭、隔离测试及数据目录进程锁 |
| C2 视频预览 | 后端已完成 实机待联调 | 共享最新帧和缓存 JPEG、多客户端 MJPEG、snapshot、流名额释放、断线重连；模拟与真实 HTTP 均通过 |
| C3 后台推理 | 调度已完成 真实模型待接入 | DetectorService 工厂边界、单后台调用线程、最新帧策略、频率控制、重复启停与慢模型和异常测试；未实现 YOLO 内部 |
| C4 数据事件 | 已完成 | cameras/detection_events/settings、会话去重、代表图更新、最后出现、筛选历史、旧 CSV 迁移与完整备份恢复 |
| C5 API 与测试 | 后端验证已完成 整机验收部分完成 | 82 项自动测试全部通过、双客户端三十分钟稳定性记录、路径与来源限制、接口说明、部署和上传操作手册；真实硬件与完整前端仍待验收 |

未开始的外部事项为真实摄像头对比实验、真实 YOLO/DetectorService 集成、前端新增交互、桌面安装包和真实环境上线。它们需要成员代码、设备和模型，不将模拟测试作为完成证据。本版能力为按类别记录最后出现，不区分同类个体、不预测消失位置。

## 修改文件

| 路径 | 类型 | 主要作用 |
| --- | --- | --- |
| `.gitignore` | 修改 | 新增运行目录与环境排除项，并保留第一版常见忽略规则 |
| `README.md` | 修改 | 更新第二版启动入口与文档索引 |
| `pytest.ini` | 新增 | 统一后端测试目录与模块搜索路径 |
| `backend/app.py` | 修改 | 兼容启动入口与应用工厂导出 |
| `backend/config.py` | 修改 | 关闭旧配置 DEBUG，并补统一版本说明 |
| `backend/requirements.txt` | 修改 | 固定直接生产依赖，移除主流程不使用的 pandas/CORS |
| `backend/requirements-lock.txt` | 新增 | 固定实际验证的全部生产依赖版本 |
| `backend/requirements-dev.txt` | 新增 | 测试与进程测量依赖 |
| `backend/run.py` | 新增 | 单进程 Waitress、适配器工厂、进程锁与安全退出 |
| `backend/manage.py` | 新增 | 旧数据迁移、CSV 导出、完整备份恢复、日志导出 |
| `backend/tracking/__init__.py` | 新增 | 统一软件名称与版本 |
| `backend/tracking/contracts.py` | 新增 | 唯一 CameraFrame、DetectionEvent 与服务协议 |
| `backend/tracking/config.py` | 新增 | 环境配置及推理参数验证 |
| `backend/tracking/adapters.py` | 新增 | MockCamera、FakeDetector、OpenCV 与未配置检测器 |
| `backend/tracking/repository.py` | 新增 | SQLite schema、事务、会话去重、CSV 和受限路径 |
| `backend/tracking/runtime.py` | 新增 | 单源缓存、后台调度、重连、预览与关闭顺序 |
| `backend/tracking/api.py` | 新增 | 运行控制、历史、图片与旧接口兼容 |
| `backend/tracking/app_factory.py` | 新增 | 隔离工厂、统一错误、本机访问限制与静态构建服务 |
| `backend/tracking/process_lock.py` | 新增 | 跨平台单数据目录进程互斥 |
| `backend/scripts/soak_test.py` | 新增 | 双客户端实际 HTTP 稳定性测量脚本 |
| `backend/tests/conftest.py` | 新增 | 临时数据目录和模拟源 fixture |
| `backend/tests/test_api.py` | 新增 | API 合同、输入、Origin、媒体与路径联接测试 |
| `backend/tests/test_runtime.py` | 新增 | 共享源、重复启停、慢推理、异常恢复与退出测试 |
| `backend/tests/test_repository.py` | 新增 | 去重、CSV、数据库版本、维护和进程锁测试 |
| `scripts/Start-Backend.ps1` | 新增 | Windows 单窗口启动辅助脚本 |
| `scripts/Stop-Backend.ps1` | 新增 | Windows 安全停止辅助脚本 |

新增文档为 docs/API.md、ARCHITECTURE.md、DEPENDENCIES.md、OPERATIONS.md、Word 操作手册和本交付报告；docs/README-v1-reference.md 保存原 README；docs/third-party-licenses 保存实际依赖版权声明。reports 包含测试原始输出、维护验证、环境信息和实际浏览器截图。完整逐文件 SHA256 变更表见 docs/CHANGE_MANIFEST.csv。

frontend、原 CSV、原样例图片和 backend/data/processor.py 保持原样。旧 Processor 仅作历史参考，不进入新主流程；第一版启动时自动查询 CSV 的行为改为显式迁移到 SQLite。新建空目录启动不自动导入测试数据。

## 验证结果

实际在 Windows x64、Python 3.12.14、固定依赖环境运行。基线采用静态检查：第一版没有自动测试，初始环境缺少 Flask/OpenCV，未虚构第一版性能。新版本先在隔离依赖目录验证，再建立项目 .venv，安装 requirements-lock.txt 和 requirements-dev.txt，pip check 无冲突。

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q --junitxml=reports/pytest.xml
.\.venv\Scripts\python.exe backend/scripts/soak_test.py --seconds 60 --output reports/http-release-smoke.json
```

三十分钟测试实际使用打包 Python 调用 backend/scripts/soak_test.py --seconds 1800 --output reports/soak-final-30min.json，依赖隔离到工作区 .runtime-packages，与环境清单的后端版本一致；临时目录设置到工作区 .test-tmp。测试程序没有将这些本机路径写入后端实现。最终 82 项通过，0 跳过；干净后端源码副本同样 82 项通过；最后一分钟发布环境 HTTP 检查也通过。三十分钟测试与最后兼容及离线清理加固的验证时点区别见 reports/test-summary.md。

| 测量项 | 实际结果 |
| --- | --- |
| 连续测试 | 1800.969 秒；两个 MJPEG 客户端；passed=true |
| 双客户端预览 | 每客户端 13.312 / 13.312 FPS；共 23961 / 23961 帧 |
| 采集频率 | 中位数 13.298 FPS；样本范围 12.793 至 13.582 |
| 后台推理 | 中位数 1.969 次每秒；目标设置 2 次每秒 |
| 状态接口延迟 | 中位数 15.0 ms；P95 16.0 ms；最大 32.0 ms |
| 最新帧待处理数 | 最大 1；容量 1；正在推理的副本另计 |
| 进程内存 RSS | 范围 61.879 至 95.504 MiB；首末 63.496 / 80.391 MiB |
| 操作系统线程数 | 范围 39 至 45；包含数值库线程 |
| 推理调用 | 3545 次；模型错误 0 |
| 摄像头状态 | 累计采集 23966 帧；源错误 0 |
| 事件合并 | 1 条连续 cup 事件；合并 3544 次 |
| 周期快照检查 | 360 次；同时检查历史与事件图片 |
| 安全退出 | 子服务器退出码 0；错误数组为空 |


原 CSV 三行导入及重复导入符合预期，完整七文件备份恢复后两类别标注图片均返回 200，Windows 启停辅助脚本退出码均为 0。Word 操作手册共九页，已后台渲染并逐页检查。没有执行真实模型准确率测试、真实设备性能测试、前端完整构建、桌面打包或远程部署，原因是对应代码与硬件不属于本次已提供的验证条件。

## 接口变化

旧 /api/items 继续返回字符串数组，/api/items/类别 保留 category、image_path、processed_image_path、timestamp；/api/search 保留 items: 并提供规范 items；旧图片路由继续存在，但读取新数据目录，需要先迁移旧图片。最后出现时间改为明确时区的 UTC ISO 字符串。

新增 health、status、cameras、runtime/start/stop、stream/start/stop、stream/preview、preview、snapshot、inference/start/stop、settings、events、事件稳定图片、CSV import/export、shutdown。/api/events 默认返回数组以兼容现有前端，envelope=1 才返回分页对象；class_name 同时兼容 category 过滤名。

设置规范字段为 inference_fps、confidence_threshold、selected_classes、dedup_seconds、input_size；保留 confidence、inference_frequency、category 别名；model 和 camera_id 只读。公共 frame_id 使用字符串，与原 TypeScript 一致；Python 图像为内存 BGR ndarray，HTTP 则使用 JPEG。详情见 API 和架构文档。

图片路径由后端持久化时生成，模型返回合同字段但不决定磁盘写入位置。新增 first_seen、last_seen、observations 和 inference_params 用于会话与复现。后端以固定数据合同对接模型工厂，成员应导入共享类型，并由孙正群确认实际 CameraSource.read 签名与薄适配方式。

## 性能与剩余风险

上述帧率和延迟仅来自 640×360 模拟源与 FakeDetector。没有 YOLO 精度、真实相机帧率或第一版同环境性能对照，不能据此声称模型提升。默认采集目标 15 FPS，Windows 调度下实测约如上；实际设备分辨率、驱动和模型开销会改变结果。

真实网络打开/读取采用两秒超时；UVC 原生驱动和真实 detect 的有界返回仍需设备验收。Python 不能安全杀死永久阻塞的工作线程，关闭超时会保留仍被使用的数据库并报告冲突；不能把这种故障判为正常退出。不同数据目录的两个服务仍可能同时连接同一物理摄像头，应只部署一个服务实例。

现有前端 cameraApi.ts 的 USE_MOCK 含 || true，总览始终模拟；前端设置页尚为占位，原页头仍显示家庭寻物系统，登记材料前还需统一软件名称。需邓单修正并联调。本次没有修改 React，真实整机体验未被宣称完成。当前没有自动事件保留期限，长期使用需观察磁盘空间并先备份再确定清理策略。突然中断或 Windows 文件占用可能留下无引用图片，不能直接按文件时间删掉仍被数据库引用的图片。

## 第三方依赖与原创边界

自编写部分为运行调度、缓存、API、数据仓库、会话合并、维护工具和测试。依赖版本及 LICENSE 见 DEPENDENCIES.md；未修改 Flask/OpenCV/NumPy/Waitress 等第三方源码，未安装或打包 Ultralytics 与权重。原前端依赖、第三方库、模型、构建产物、自动生成文档与报告不计入原创代码。王琪臻应审阅变更与证据，再由孙正群汇总登记材料。

## 交接说明

先读九页 Word 操作手册，在项目根目录创建虚拟环境并安装固定依赖；本机已有经验证的 .venv 可直接运行 `python backend/run.py --camera mock --demo --start --infer`。浏览器打开 /api/preview 和 /api/status，等待 /api/items/cup 可查。停止用 Ctrl+C 或 POST /api/shutdown。

迁移旧数据和完整备份前先停止服务，使用 manage.py；恢复到新目录并核对历史与图片后再切换。王韵哲提供视频源工厂，孙正群提供真实检测器工厂；邓单接入真实 API。开发代理使用 --dev-proxy，正式页面同源托管使用 --frontend-dir。上传仓库与正式部署的全部逐步命令位于操作手册，本次仅保存在本地。
