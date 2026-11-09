# 第三版后端交付报告

2026 年 11 月 9 日 · 王琪臻 · 基于神经网络的物品示踪系统 V1.0

本轮保留现有 Flask、RuntimeManager、单源取帧和 SQLite 架构，新增模型类别查询和 CSV 容错导入。使用模拟画面、FakeDetector 和本机视频流完成可独立的验收。项目记录的是所选类别最后出现的时间、房间和图片，未验证同类物品区分或真实检测精度。

本地分支 `feature/wangqizhen-backend-v3` 从最新 `origin/main` 的 `25cad5d` 开始，包含任务书提及的 `3f4b30c` 及后续前端修复。第二版后端已随主分支合入，原本地分支保留。后端实现提交 `d246416f5564bfee227ade3821159fe4361320ce`；完整测试用例提交 `42a13abe45ebc0fa812d52b566f729be7d2c6dbc`。本轮没有推送或创建 Pull Request。

## 任务结果

| 编号 | 状态 | 实际结果和剩余项 |
| --- | --- | --- |
| C1 合同确认 | 后端完成 | 复用原公共类型；新增模型类别查询和可运行的两种工厂，分别验证未配置与演示响应。待邓单把设置页候选接到新接口。 |
| C2 设备接入 | 模拟网络链路通过，实机待验 | 本机 HTTP MJPEG 通过 OpenCV 读取 160×90 画面，两个预览共享一次读取，断开后摄像头离线、服务在线，流恢复后收到新帧，关闭后释放源。尚未收到真实树莓派地址。 |
| C3 前端和桌面 | 后端与浏览器通过，桌面待验 | 现有 React 页面调用实际 HTTP，已验证四类状态、预览停止与恢复、查询图片和保存类别。现有 MockController 界面测试通过；后端独立进程退出、释放锁和重新启动已测。真正 pywebview 桥接及统一启动器仍待集成。 |
| C4 CSV | 完成 | 默认严格，有坏行不写整批；容错只写有效记录，报告物理行号和原因。HTTP 与 CLI 均验证混合记录、重复导入和错误报告；保留已有历史与文件。 |
| C5 回归维护 | 完成 | 锁定依赖符合要求，后端 93 项通过。复核配置持久化、备份恢复、日志导出、新数据目录启动和 Windows UTF-8 命令。 |
| C6 交接 | 本地交付 | 更新接口、架构、运行和交接文档；30 分钟模拟连续测试通过，实机结果单列。远程提交与合并申请待本人审阅后操作。 |

## 文件与兼容性

- `backend/tracking/api.py`：新增 `GET /api/model/classes`，返回 `model_version`、`available`、`simulated`、`classes`。已配置与未配置均返回 200；类别不从 `/api/items` 推断。CSV 路由新增 `mode`，保留原计数与错误格式。
- `backend/tracking/contracts.py`、`adapters.py`、`backend/examples/v3_adapters.py`：既有 DetectorService 可选提供类别清单；工厂示例复用公共类型。模拟检测框按原帧尺寸缩放，适用较小的本机模拟视频。
- `backend/tracking/repository.py`、`backend/manage.py`：共享严格与容错校验，报告行号和原因；有效行事务写入。离线迁移在验证完成前不写目标图片，文件不覆盖。日志导出仍持有原数据锁，限定目录并使用新输出文件。
- `backend/tests/test_v3_contracts.py`、`test_v3_integration.py`：新增 11 项。已有用例保留，原 CSV 成功响应断言随新增 `errors` 字段更新。没有更改前端源码、公共类型字段或 SQLite 表结构。
- [API](API.md)、[架构](ARCHITECTURE.md)、[操作手册](OPERATIONS.md)、[接入说明](V3_INTEGRATION.md)：列出四类状态、接口参数、工厂、设备接入、桌面控制器合同及故障处理。仓库保留的第二版 Word 手册与旧报告是历史材料。

## 本轮验证证据

Windows 11 x64（系统版本 10.0.26200）、Python 3.12.14、pytest 8.4.2，OpenCV 4.12.0.88、Flask 3.1.2、Waitress 3.0.2；已核对安装版本满足 `backend/requirements-lock.txt`，`pip check` 无冲突。前端 Node.js v24.14.0、npm 11.9.0；沿用已有锁文件。

后端基线 82 项通过，第三版 93 项通过、0 跳过、0 失败，耗时 16.61 秒。[pytest 原始报告](../reports/pytest-v3.xml)。Windows 默认测试临时目录权限有问题时，按下面命令使用新目录，保持旧数据不动。

```powershell
$qa = 'reports/pytest-v3-rerun-' + [guid]::NewGuid().ToString('N') + '-data'
.\.venv\Scripts\python.exe -X utf8 -m pip check
.\.venv\Scripts\python.exe -X utf8 -m pytest -q -p no:cacheprovider --basetemp=$qa
```

旧仓库三条样例，离线严格模式在新目录插入 3 条，生成 3 张原图和 3 张标注图；随后在同目录容错模式重复导入，`inserted=0, skipped=3, rows=3, errors=[]`。混合好坏行、全坏行、非法模式、无法识别的 CSV 结构和多行字段位置用合成输入单独检查，原样例与个人数据未修改。

前端在 `frontend` 中执行 `npm ci`，使用 `tsc --noEmit`、`npm test -- --watchAll=false --runInBand --no-cache`、`npm run build`。类型检查通过，4 个测试套件、5 项通过，构建成功。用 `REACT_APP_USE_MOCK=false` 构建并通过后端 `/ui/` 加载页面，实测停预览时仍在推理，恢复后实时画面正常，历史“最后出现”返回图片和时间，页面保存 `cup` 后由 `GET /api/settings` 独立核对。截图保留在本轮浏览器验证记录，仓库另存[实际模拟预览帧](../reports/screenshots/v3-preview-sample.jpg)。不表示真实硬件、真实 YOLO 或桌面打包通过。

### 30 分钟模拟连续测试

2026 年 11 月 9 日 15:18（北京时间）开始，在后端实现提交 `d246416` 上使用 MockCamera、FakeDetector 和两个实际 HTTP MJPEG 客户端运行。测试期间没有变更后端实现。运行目录是 `reports/soak-v3-d246416-30min-data`，不提交其中的数据库、图片和运行日志。

```powershell
.\.venv\Scripts\python.exe -X utf8 backend/scripts/soak_test.py --seconds 1800 --output reports/soak-v3-d246416-30min.json
```

上面是本轮实际命令；复现时请改用新的输出名。原始证据：[测量 JSON](../reports/soak-v3-d246416-30min.json)、[服务器输出](../reports/soak-v3-d246416-30min.server.txt)。

| 测量项 | 实际结果 |
| --- | --- |
| 连续运行与结束 | 1800.859 秒；`passed=true`，错误数组为空；退出码 0 |
| 双客户端预览 | 23,998 / 23,999 帧；13.332 / 13.333 FPS |
| 状态接口 | 延迟中位数 15 ms，P95 16 ms，最大 32 ms |
| 推理与缓存 | 3,535 次推理，窗口频率中位数 1.964 次/秒；待处理缓存最大 1 |
| 快照、查询和入库 | 360 次周期检查；1 条连续 cup 事件，更新合并 3,534 次 |
| 异常与进程内存 | 摄像头错误 0、推理错误 0；进程树 RSS 49.227–106.844 MiB |

这些数值仅描述本机 640×360 模拟环境，不推断真实树莓派、YOLO 或桌面包的性能。

## 本人复现和后续交接

先按 [第三版接入说明](V3_INTEGRATION.md) 启动模拟环境，复核 `cup`、画面和查询；退出使用 `Ctrl+C` 或 `POST /api/shutdown`，待退出后用相同数据目录调用 `manage.py` 做离线维护。

1. 王韵哲提供实际树莓派持续视频地址后，先只验证预览及断线恢复，再用 FakeDetector 联调。未提供地址，本轮未执行实机读流。
2. 邓单将设置页候选改用 `/api/model/classes`，保持 `/api/items` 用于历史；与孙正群接上桌面桥接。现有仓库未提供最终 `desktop/` 启动器和打包输入，本轮未制作桌面安装包。
3. 孙正群提供真实 YOLO 检测器工厂、模型类别清单与统一启动器后，共同验证真实模型、设备和新电脑安装。真实视频和真实模型的证据分别记录。
4. 本地审阅通过后，可按 [上传步骤](OPERATIONS.md#十一-审阅后自行上传-github) 将个人分支推送并发起合并申请。审阅说明可用：“第三版新增模型类别目录与 CSV 可选容错导入，保留既有 API 和数据架构；附自动回归、本机视频断流恢复、页面与桌面生命周期及模拟连续运行证据。真实树莓派、YOLO、最终启动器待接入。”
