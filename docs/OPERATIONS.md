# 物品示踪系统后端操作手册

本手册用于王琪臻负责的后端交付，软件名称为“基于神经网络的物品示踪系统”，版本 V1.0，对应第三版任务书。后端实现单一摄像头取帧、共享最新帧、MJPEG 预览、后台识别调度、SQLite 事件存储和查询。识别结果表示某类别最后出现的信息，不区分同类别的具体物品，不预测消失位置。

第三版只在本地交付。真实树莓派、真实 YOLO 和最终桌面启动器待团队接入。模拟识别结果只用于验证程序链路，具体验收和团队接口见 [第三版接入说明](V3_INTEGRATION.md)。

## 一 文件位置和阅读顺序

交付项目为工作目录下的 `Item-Tracking-System-v2`。先阅读本手册完成模拟运行，再阅读 `docs/API.md` 对接页面，最后用 `docs/ARCHITECTURE.md` 和 `docs/DELIVERY_V3.md` 核对设计与验收。测试原始证据保存在 `reports`。第三版保留主分支已有前端源码。

| 文件或目录 | 用途 |
| --- | --- |
| backend/run.py | 本机正式服务器入口 使用 Waitress |
| backend/app.py | 保留 python app.py 的启动方式 |
| backend/tracking | 运行调度 公共合同 数据库和 API |
| backend/manage.py | 旧数据迁移 完整备份 恢复和日志导出 |
| backend/tests | 不依赖真实硬件的自动验收 |
| backend/scripts/soak_test.py | 双客户端真实 HTTP 持续运行测试 |
| scripts | Windows 启动和停止辅助脚本 |
| docs | 接口 设计 交付和操作文档 |
| runtime | 默认运行数据 自动生成且不上传 |

## 二 Windows 准备环境

安装 64 位 Python 3.12 和 Git。第一次运行需要联网下载 Python 依赖；后续使用已有虚拟环境启动。以下命令在 PowerShell 中执行，先进入交付项目根目录。路径应按实际保存位置调整。

```powershell
Set-Location 'D:\学习资料\大创\Item-Tracking-System-v2'
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check
```

`requirements-lock.txt` 固定本次运行验证使用的全部后端生产依赖。只运行服务不需要安装 pytest。需要复现测试时，再执行以下命令。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pip install -r backend/requirements-lock.txt -r backend/requirements-dev.txt
$qa = 'reports/pytest-local-' + [guid]::NewGuid().ToString('N') + '-data'
.\.venv\Scripts\python.exe -X utf8 -m pytest -q -p no:cacheprovider --basetemp=$qa
```

不需要激活虚拟环境，所有命令直接调用其 Python。不要把开发电脑的虚拟环境复制到另一台电脑；在目标电脑重新创建。默认数据目录是项目根目录下的 `runtime`，也可通过 `--data-dir` 或 `TRACKING_DATA_DIR` 指定。

`-X utf8` 让 Python 的控制台与 CLI 输出使用 UTF-8；CSV 请另存为 UTF-8 或 UTF-8 BOM，旧 GBK 文件应在编辑器中另存转换。若 pytest 在 Windows 的 `Temp\pytest-of-...` 报 `WinError 5`，使用上方新建的测试目录即可避开旧目录权限。`--basetemp` 只传新测试路径，它不能指向现存数据。

## 三 先运行模拟链路

在第一个 PowerShell 窗口执行以下命令。保留窗口以观察日志。

```powershell
.\.venv\Scripts\python.exe backend/run.py --camera mock --demo --start --infer
```

`--camera mock` 使用模拟画面，`--demo` 使用 FakeDetector，不加载 YOLO。`--start` 启动取帧，`--infer` 启动后台推理。服务只监听 `127.0.0.1:5000`，调试模式关闭。浏览器打开以下地址查看预览和状态。

```text
http://127.0.0.1:5000/api/preview
http://127.0.0.1:5000/api/status
http://127.0.0.1:5000/api/events?envelope=1
http://127.0.0.1:5000/api/items/cup
```

模拟画面会显示 SIMULATION；类别 cup、置信度 0.9 和模型版本 fake-demo-1 都是测试数据。可用第二个窗口验证控制接口。

```powershell
$base = 'http://127.0.0.1:5000'
Invoke-RestMethod "$base/api/health"
Invoke-RestMethod -Method Post "$base/api/inference/stop"
Invoke-RestMethod "$base/api/status"
Invoke-RestMethod -Method Post "$base/api/inference/start"
```

停止推理后预览应继续更新。停止预览使用 `/api/stream/stop`，只关闭预览输出，后台推理继续工作。停止整个取帧与推理链路使用 `/api/runtime/stop`，再次启动使用 `/api/runtime/start` 和 `/api/inference/start`。

## 四 查询和设置

设置通过 SQLite 持久化，重启后继续使用。修改类别、阈值和推理频率可以在服务运行时完成。以下示例仅记录 cup，置信度至少 0.4，每秒最多推理 2 次。

```powershell
$body = @{
  selected_classes = @('cup')
  confidence_threshold = 0.4
  inference_fps = 2
  dedup_seconds = 30
  input_size = 640
} | ConvertTo-Json
Invoke-RestMethod -Method Patch -Uri "$base/api/settings" `
  -ContentType 'application/json' -Body $body
Invoke-RestMethod "$base/api/settings"
```

空的 `selected_classes` 表示接受检测器返回的全部类别，不保证模型支持任意名称。`input_size` 是传给模型适配器的参数，由适配器执行。当前模型和摄像头标识为只读，切换设备或模型需要停止服务并更改启动配置。

事件支持按类别、摄像头和时间过滤。时间使用带时区 ISO 8601；导入第一版无时区 CSV 时按北京时间解释，输出统一为 UTC。前端显示时应转换为本地时间。

```powershell
Invoke-RestMethod "$base/api/items"
Invoke-RestMethod "$base/api/items/cup"
Invoke-RestMethod "$base/api/events?envelope=1&class_name=cup&limit=20"
Invoke-RestMethod "$base/api/events?camera_id=camera-1&envelope=1"
Invoke-WebRequest "$base/api/events/export" -OutFile '.\events-export.csv'
```

`/api/events` 默认返回数组以兼容已有前端；加 `envelope=1` 才返回含 total、limit、offset 的分页对象。查询返回的 `image_path`、`processed_image_path` 或 `image_url` 是稳定图片接口，应直接使用，不应自行拼接磁盘路径。

## 五 迁移第一版 CSV 和图片

先关闭正在运行的后端。项目保留了第一版的 `backend/data/recognition.csv` 和样例图片。迁移工具把数据导入 SQLite，把原图复制到运行目录，并按旧框坐标生成标注图。

```powershell
.\.venv\Scripts\python.exe backend/manage.py migrate-legacy
```

默认严格模式，有坏行时整个批次不写入。需要保留有效记录时，显式加 `--mode skip_invalid`；终端会报告 `inserted`、`skipped`、`rows` 和 `errors`，错误含原 CSV 行号。迁移完成后重启服务，访问 `/api/items`，应能查到旧类别。重复导入相同记录会跳过，不重复增加事件。历史数据标记为 `legacy-camera` 和 `legacy-csv`。缺失的原图不能通过 CSV 恢复；只有数据、没有图片时，图片请求返回 404。

自有旧后端可以使用以下命令。源目录应包含 `data/recognition.csv` 和 `images`。

```powershell
.\.venv\Scripts\python.exe backend/manage.py `
  --data-dir '.\runtime' migrate-legacy `
  --source-backend 'C:\旧项目\backend'
```

已有运行目录中的 CSV 可在线导入，上传内容为 UTF-8 CSV，不允许通过 API 指定任意磁盘文件。在线导入不附带图片，需先由离线迁移或完整恢复工具将图片放入受限的数据目录。

```powershell
Invoke-RestMethod -Method Post -Uri "$base/api/events/import" `
  -ContentType 'text/csv; charset=utf-8' -InFile '.\events-export.csv'
```

在线容错导入把 URL 换成 `$base/api/events/import?mode=skip_invalid`。返回的 `skipped` 只统计重复记录，坏行看 `errors`。

## 六 接入真实摄像头和模型

先进行仅预览验收，再接入模型。电脑 USB 摄像头可尝试设备号 0；如果有多个摄像头，按实际编号调整。

```powershell
.\.venv\Scripts\python.exe backend/run.py `
  --camera opencv --source 0 --room '客厅' --start
```

网络 MJPEG 或 RTSP 视频可传入王韵哲提供的实际持续流地址。第三版设备固定为树莓派 4B 和 Camera Module 3 Wide。只提供单张 JPEG 的抓拍接口不能直接当作持续流，应先与设备负责人确认输出形式。

```powershell
.\.venv\Scripts\python.exe backend/run.py `
  --camera opencv --source 'http://设备地址:端口/stream' --start
```

网络源使用 OpenCV FFmpeg 的两秒打开和读取超时。USB 后端是否能在时限内结束读取取决于驱动，必须用最终设备验证。断线会更新为 offline 并重试；恢复后重新提供新帧，不把旧缓存伪装为实时画面。

孙正群提供一个无参数工厂，例如 `integration.detector_adapter:create_detector`，返回符合 `backend/tracking/contracts.py` 的 DetectorService。适配器只负责调用模型和构造共享 DetectionEvent；不得另外打开摄像头、创建数据库或接管页面。模型在工厂创建时加载一次，在一个后台推理线程中复用。

```powershell
.\.venv\Scripts\python.exe backend/run.py `
  --camera opencv --source 0 --start --infer `
  --detector-factory integration.detector_adapter:create_detector
```

上面的 integration 模块名是接入示例，当前交付没有真实 YOLO 适配器和模型权重。只有成员提供真实模块后才执行该命令；不要给正式启动命令加 `--demo`。王韵哲提供自定义视频源时，使用 `--camera-factory 模块名:工厂名`。详细字段与线程约束见架构文档。

## 七 前端接入与正式本机部署

正式部署指目标电脑上的单进程本机服务，使用 Waitress，端口只绑定 127.0.0.1。用户可以通过本机浏览器访问，后续桌面壳也可调用同一 API。本交付不包含桌面安装包和开机自启注册。

当前前端默认访问实际后端，只有显式设置 `REACT_APP_USE_MOCK=true` 才使用前端自己的模拟数据。总览、历史和设置页面已经存在。第三版新增 `/api/model/classes`；当前设置页仍从历史取得类别候选，后续由邓单切换到新目录接口。历史搜索继续使用 `/api/items`。

联调时先关闭之前的后端，并以 `--dev-proxy` 重新启动，显式信任 localhost:3000 的开发代理来源；该开关不用于正式部署。另一个窗口在前端目录启动原项目。代理可能改写 Host 而保留 Origin，因此不能省略此开关。

```powershell
.\.venv\Scripts\python.exe backend/run.py `
  --camera mock --demo --start --infer --dev-proxy
```

```powershell
Set-Location frontend
npm ci
$env:REACT_APP_USE_MOCK = 'false'
npm start
```

前端依赖按既有锁文件安装。本轮验收区分浏览器页面、模拟桌面控制器和实际桌面程序；能在浏览器操作不表示最终启动器已交付。

可构建静态文件，再由本后端同源提供模拟演示页面。以下命令从项目根目录执行。

```powershell
Push-Location frontend
$env:REACT_APP_USE_MOCK = 'false'
npm run build
Pop-Location
.\.venv\Scripts\python.exe backend/run.py `
  --data-dir '.\reports\v3-ui-demo-data' --camera mock --demo --start --infer `
  --frontend-dir '.\frontend\build'
```

浏览器访问 `http://127.0.0.1:5000/ui/`，可用现有页面调用实际后端的模拟源。没有 pywebview 桥接时桌面专用按钮不会接管后台进程。不要用 Flask debug/reloader 启动正式摄像头，不要开启多个 WSGI 进程。后端的运行入口会锁定数据目录，防止同目录被多个进程同时占用；仍应避免两个不同目录的进程连接同一真实设备。

在目标电脑建议将代码与持久数据分开，例如代码保存在 `C:\ItemTracking`，运行数据保存在 `$env:LOCALAPPDATA\ItemTracking`。复制项目源码后重新创建虚拟环境，以下示例显式指定数据目录。

```powershell
$data = Join-Path $env:LOCALAPPDATA 'ItemTracking'
.\.venv\Scripts\python.exe backend/run.py `
  --data-dir $data --camera opencv --source 0 --start
```

确认真实预览正常后，再加入经过验证的 detector-factory 和 infer 参数。四个预览客户端是默认上限，十二个服务线程给控制接口留出空间。V1.0 不提供互联网访问、账户和多摄像头融合；不应把本服务端口直接暴露到公网。

## 八 正常停止与异常处理

在第二个窗口执行关闭请求，或在运行窗口按 Ctrl+C。运行入口先停止后台推理，再结束取帧并释放摄像头，随后关闭模型和 SQLite，最后退出服务器。

```powershell
Invoke-RestMethod -Method Post 'http://127.0.0.1:5000/api/shutdown'
```

单独创建的 Flask 测试应用中，shutdown 只关闭运行资源；通过 `backend/run.py` 启动时，会同时安排服务器退出。已关闭的运行实例不能再次启动，需要重新启动进程。`/api/runtime/stop` 则可再次启动。

| 现象 | 处理步骤 |
| --- | --- |
| 端口被占用 | 先关闭旧进程 或使用 --port 5001 并同步页面地址 |
| data directory is in use | 关闭同数据目录旧后端 不能靠删除锁文件绕过 |
| no fresh camera frame | 检查 runtime/start 设备编号 视频地址和 /api/status |
| DetectorService is not configured | 提供真实模型工厂 演示时才使用 --demo |
| camera_state offline | 检查设备连接 程序会自动重试 原因见本地日志 |
| 返回 400 | 检查 JSON 类型 时间范围 类别数组和输入尺寸 |
| 返回 409 shutdown timeout | 适配器未及时返回 保留数据库以避免活跃线程使用已关闭资源 检查驱动或模型后再次关闭 |
| 返回 403 | 使用 localhost 或 127.0.0.1 地址 控制请求从同源页面发起 |
| 旧 CSV 图片 404 | 核对迁移源图片是否存在 CSV 本身不包含图片 |

日志位于数据目录下的 `logs/backend.log`，采用轮转，最多一个当前日志和三个历史日志，每个约 2 MiB。若关闭超时持续存在，记录日志并修复适配器；强制结束进程只能作为故障处置，之后检查 SQLite 和最新事件，不视为正常退出验收。

## 九 完整备份与恢复

CSV 用于交换数据，不是完整备份。完整备份包含 SQLite、原图、标注图、设置和现存日志，并生成 SHA256 校验清单。先正常关闭服务，再执行备份。备份输出必须是数据目录外的新文件。

```powershell
New-Item -ItemType Directory -Force '.\backups' | Out-Null
.\.venv\Scripts\python.exe backend/manage.py `
  --data-dir '.\runtime' backup `
  --output '.\backups\itemtracking-before-update.zip'
```

恢复到一个尚不存在的新目录，不覆盖旧目录。工具检查路径、文件校验和和 SQLite 完整性；恢复成功后把服务的数据目录指向新目录，先检查历史，再启动实时识别。

```powershell
.\.venv\Scripts\python.exe backend/manage.py restore `
  --archive '.\backups\itemtracking-before-update.zip' `
  --destination '.\runtime-restored'
.\.venv\Scripts\python.exe backend/run.py `
  --data-dir '.\runtime-restored'
```

打开 `/api/items` 和 `/api/events?envelope=1`，核对类别、事件数、最后时间与图片。确认无误再加 start 和正式模型参数。回退时关闭当前服务，再将启动参数改回原数据目录和匹配版本的代码。不要仅复制运行中的 SQLite 主文件，WAL 文件可能包含尚未合并的数据。

离线导出日志和 CSV 的命令如下；输出文件应使用新文件名。

```powershell
.\.venv\Scripts\python.exe backend/manage.py export-logs `
  --output '.\backups\backend-logs.zip'
.\.venv\Scripts\python.exe backend/manage.py export-csv `
  --output '.\backups\events-offline.csv'
```

使用自定义数据目录时，每条维护命令都要在子命令前加相同的 `--data-dir`，否则会读取默认 runtime。备份恢复不包含真实模型权重、摄像头地址、命令行配置和前端构建，请另行保存实际部署参数。

## 十 复现验收与连续运行测试

在项目根目录运行以下命令。测试使用临时数据目录、模拟摄像头或本机模拟视频流和 FakeDetector，不访问真实设备，也不要求固定 D 盘。

```powershell
$qa = 'reports/pytest-local-' + [guid]::NewGuid().ToString('N') + '-data'
.\.venv\Scripts\python.exe -X utf8 -m pytest -q -p no:cacheprovider --basetemp=$qa
.\.venv\Scripts\python.exe backend/scripts/soak_test.py `
  --seconds 1800 --output reports/soak-recheck.json
```

持续测试会启动独立本机服务器，建立两个真实 MJPEG 连接，每秒采集状态，每五秒检查快照、查询和事件图片，最后请求安全退出。输出文件名要换新名字，因为脚本拒绝复用已有测试数据目录。结果 JSON 中的 passed 必须为 true，errors 必须为空，server_exit_code 应为 0。

自动测试覆盖共享源、重复启停、摄像头断线恢复、慢推理、模型异常、类别过滤、去重、图片并发更新、CSV 原子导入、路径穿越、Windows 目录联接逃逸、备份恢复和安全关闭。本次真实测量结果、运行命令和限制见交付报告，不将模拟帧率解释为真实摄像头或 YOLO 性能。

真实设备接入后，应使用树莓派实际地址记录分辨率、预览帧率、推理频率、延迟和断线恢复；之后再用真实 YOLO、最终桌面启动器和目标电脑进行整体验收。模拟连续测试不能替代这些步骤。

## 十一 审阅后自行上传 GitHub

第三版在本地 `feature/wangqizhen-backend-v3` 分支，开始基线为 `25cad5d`。本轮不推送，也没有创建 Pull Request。日后由本人审阅和执行：

1. 在项目根目录检查 `git status` 和 `git remote -v`。已有第三版分支时切换到该分支，不重复建分支。
2. 执行 `git fetch origin`，检查 `git log --oneline origin/main..HEAD` 和 `git diff --stat origin/main...HEAD`。主分支如果有新提交，先在本人分支执行 `git merge --no-edit origin/main`，处理冲突后重新验证。
3. 检查拟交付的文件，排除 `.venv`、`runtime`、`node_modules`、私人日志、模型权重和构建产物。已有本地提交且没有新改动时无需重复暂存、提交。
4. 审阅完成后，由本人执行 `git push -u origin feature/wangqizhen-backend-v3`，在 GitHub 发起指向 `main` 的 Pull Request 并交给孙正群审查。说明模拟验证、真实设备待测以及前端类别目录和桌面桥接的剩余事项。

## 十二 团队交接检查

| 接收人 | 应完成的下一步 |
| --- | --- |
| 王琪臻 | 审阅后端修改 复现自动测试 核对旧数据和手册命令 |
| 王韵哲 | 提供树莓派持续流地址和输出规格，配合真实读帧、断线与恢复 |
| 孙正群 | 提供真实 DetectorService、类别清单和统一启动器，完成打包与整体验收 |
| 邓单 | 设置页接入 `/api/model/classes`，配合桌面桥接与页面验收 |

下一位成员应从模拟模式开始复现，再替换一个适配器进行验证。不要同时替换摄像头、模型和页面后只凭截图判断成功；应核对状态接口、SQLite 事件、实际图片和退出日志。

## 参考资料

第一版仓库：https://github.com/Ddatopos/Item-Tracking-System

Flask 的 Waitress 部署说明：https://flask.palletsprojects.com/en/stable/deploying/waitress/

Python SQLite 备份说明：https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup
