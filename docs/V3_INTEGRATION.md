# 第三版后端接入说明

本轮可在自己的电脑上用模拟画面验收；后端、页面和数据保存都是真实运行的，画面和识别结果由程序生成。还没有树莓派视频地址，也没有接入真实 YOLO。

## 先运行一次

在项目根目录打开 PowerShell，已安装环境的电脑可直接执行启动部分。安装测试依赖时同时使用生产锁文件，避免安装到另一套版本。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -X utf8 -m pip install -r backend/requirements-lock.txt -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -X utf8 -m pip check
```

用新目录试跑，和自己已有的历史数据分开：

```powershell
$demoData = 'reports/demo-v3-' + [guid]::NewGuid().ToString('N') + '-data'
.\.venv\Scripts\python.exe -X utf8 backend/run.py --data-dir $demoData --camera mock --demo --start --infer
```

浏览器打开 `http://127.0.0.1:5000/api/preview` 看画面；`/api/model/classes` 应显示 `available: true`、`simulated: true` 和 `classes: ["cup"]`。访问 `/api/items/cup` 可查看最后出现记录。关闭时按 `Ctrl+C`；从控制器关闭时用 `POST /api/shutdown` 并等待进程退出。

要使用现有页面，在 `frontend` 执行 `npm ci`，把 PowerShell 中的 `$env:REACT_APP_USE_MOCK` 设为 `'false'`，运行 `npm run build`。回到项目根目录，在上面的后端命令末尾加 `--frontend-dir frontend/build`，打开 `http://127.0.0.1:5000/ui/`。这样页面调用真正的后端 HTTP 接口，仍使用模拟画面和识别。若网页显示打不开，先确认后端命令窗口仍在运行，端口和地址一致。

## 公共类型和工厂

- `CameraSource.open/read/close` 由唯一取帧线程调用，必须在关闭超时内返回。`read()` 返回 BGR `uint8`、`H×W×3` 数组；从 RGB 数据接入时应在源适配层转换。`RuntimeManager` 生成 `CameraFrame`，提供字符串帧号、摄像头、房间、UTC ISO 采集时间、宽高和 `source_type`。HTTP 传输 JPEG，不传内存数组。
- `DetectorService.detect(frame, settings)` 返回同一 `tracking.contracts` 中的 `DetectionEvent` 序列。事件复用输入帧的 `frame_id`、`camera_id`、`room` 和 `captured_at`。`bbox=[x1,y1,x2,y2]` 是原帧像素坐标；模型内部缩放或补边后需反变换。图片路径由后端生成。模型在工厂中加载一次；`detect` 不打开摄像头或数据库。真实适配器声明 `simulated=False`，并在加载时提供 `class_names`，供类别目录读取。
- 两个可运行的无参数工厂在 `backend/examples/v3_adapters.py`。以下命令直接调用工厂，仍然是模拟：

```powershell
$env:TRACKING_CAMERA_KIND = 'mock'
$demoData = 'reports/factory-v3-' + [guid]::NewGuid().ToString('N') + '-data'
.\.venv\Scripts\python.exe -X utf8 backend/run.py --data-dir $demoData `
  --camera-factory examples.v3_adapters:camera --detector-factory examples.v3_adapters:detector --start --infer
```

示例相机工厂从环境读取 `TRACKING_CAMERA_KIND` 和 `TRACKING_CAMERA_SOURCE`。普通设备接入优先使用现有 `--camera opencv --source`，无须复制工厂。

## 有树莓派地址后怎么验收

王韵哲提供树莓派 4B + Camera Module 3 Wide 的**实际持续视频流**地址、协议和分辨率。先让电脑能访问该流，再执行以下命令。不要填网页首页、单张 JPEG 抓拍地址或推测的地址。

```powershell
$piSource = Read-Host '输入树莓派持续视频流地址'
$piData = 'reports/pi-v3-' + [guid]::NewGuid().ToString('N') + '-data'
.\.venv\Scripts\python.exe -X utf8 backend/run.py --data-dir $piData `
  --camera opencv --source $piSource --start
```

在 `/api/status` 确认 `camera_state=online`，在 `/api/health` 核对分辨率，并用 `/api/snapshot` 检查是现场画面。开两个预览窗口后确认仍由同一个源读取。经设备负责人同意后短时断开视频流，核对摄像头离线而服务仍正常，恢复后应收到新帧。无设备或地址时只报告模拟结果。通过预览后可加 `--demo --infer` 验证调度和入库，这仍是模拟识别；真正识别应改用孙正群验证过的 `--detector-factory`。

## 前端与桌面交接

邓单：当前 `SettingsPage.tsx` 使用 `getItemCategories()` 从 `/api/items` 加载历史类别。设置页的模型候选应改用 `GET /api/model/classes` 的 `classes`，显示 `simulated` 和 `available`；已有自定义或已保存的值单独标为设置值。历史过滤仍可使用 `/api/items`。继续分别读服务、摄像头、预览与推理状态，见 [API 说明](API.md)。现有界面源码由本轮保留。

桌面桥接由邓单、孙正群在相应层实现。统一返回 `{ok, message, data}`，无额外数据时为 `null`；现有 TypeScript 也允许省略 `data`。业务按钮使用以下职责：

| 控制器调用 | 合同 |
| --- | --- |
| `start()` | 启动本软件拥有的一个后端进程，待健康接口响应后再显示在线，重复调用不新增进程 |
| `stop()` | 请求 `/api/shutdown` 并等待自己启动的进程退出；保留设置，下次允许再启动 |
| `open_data_dir()` | 由桌面壳打开当前生效的数据目录，不让 HTTP 调用任意路径 |
| `export_logs(destination)` | 目的地来自原生保存对话框；如果同目录后端在运行，先停并等锁释放；导出结束按之前运行状态决定是否重启 |
| `set_data_dir(path)` | 保存下次启动使用的目录，不切换当前 SQLite 或移动历史数据 |
| `shutdown()` | 应用退出时释放自己拥有的后端；超时显示失败并保留日志，不能报告为正常退出 |

`select_data_dir()` 和 `select_export_destination()` 是现有页面的原生对话框桥接入口，成功时返回 `data.path`；取消时不执行保存或导出。预览和识别启停继续使用 HTTP。无桥接时用手动启动的后端演示页面，不能把 MockController 用例通过写成已打包成功。

## CSV 与离线维护

只有确实希望略过坏行时才选择容错模式。下面将仓库样例导入新的隔离目录，默认模式可去掉最后两个参数：

```powershell
$migrationData = 'reports/migration-v3-' + [guid]::NewGuid().ToString('N') + '-data'
.\.venv\Scripts\python.exe -X utf8 backend/manage.py --data-dir $migrationData migrate-legacy --mode skip_invalid
```

`inserted` 是新记录，`skipped` 是重复记录，`errors` 是每个坏行及原因。坏行行号从原 CSV 的首行算起，标题是第 1 行。严格模式发现坏行时，命令返回退出码 2 和 JSON 错误行列表；已有记录和图片不会被覆盖。CSV 需是 UTF-8（可以有 BOM），只包含记录；迁移脚本可从第一版 `images` 目录补齐对应图片。

离线命令需要与后端使用相同的 `--data-dir`，且后端已退出。按 [操作手册](OPERATIONS.md) 备份、恢复、导出日志或 CSV；输出用新的文件名。桌面控制器调用时建议使用 `python -X utf8 backend/manage.py --data-dir <当前目录> export-logs --output <新ZIP>`，检查进程退出码并读取 JSON；遇到数据锁冲突时等待或显示失败，不绕过锁。

## 在自己的电脑复现测试

```powershell
$qa = 'reports/pytest-v3-' + [guid]::NewGuid().ToString('N') + '-data'
.\.venv\Scripts\python.exe -X utf8 -m pytest -q -p no:cacheprovider --basetemp=$qa
.\.venv\Scripts\python.exe -X utf8 backend/scripts/soak_test.py --seconds 1800 --output reports/soak-v3-your-run.json
```

`$qa` 每次都使用新目录，解决 Windows 默认测试目录拒绝访问的情况；不要传现有数据目录。持续测试使用模拟摄像头、模拟识别和两个真实 HTTP 预览客户端，报告名称如已存在，请换一个新名字。真实设备与后续整体验收单列，见 [第三版交付报告](DELIVERY_V3.md)。
