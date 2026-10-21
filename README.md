# 基于神经网络的物品示踪系统 V1.0

本地后端第二版交付。以现有 Flask 查询代码为基础，完成单一视频源、共享最新帧、MJPEG 预览、后台 DetectorService 调度、SQLite 事件、类别会话去重、CSV 兼容、备份恢复与接口测试。**本次没有向 GitHub 上传或创建提交。**

先读 [Word 操作手册](docs/物品示踪系统第二版操作手册.docx) 或 [同内容 Markdown 操作手册](docs/OPERATIONS.md)。本机快速验证：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
.\.venv\Scripts\python.exe backend/run.py --camera mock --demo --start --infer
```

浏览器打开 `http://127.0.0.1:5000/api/preview` 查看模拟预览；访问 `/api/status`、`/api/events?envelope=1` 和 `/api/items/cup` 查询。模拟画面和假检测明确标记为模拟，不代表真实 YOLO 或硬件已联调。正式入口使用 Waitress，只监听 127.0.0.1，关闭 debug。停止可按 Ctrl+C 或 POST `/api/shutdown`。

| 文档 | 内容 |
| --- | --- |
| [API](docs/API.md) | 完整路由 字段 错误和旧版兼容 |
| [架构](docs/ARCHITECTURE.md) | 共享合同 线程 数据库 去重和关闭顺序 |
| [交付报告](docs/DELIVERY.md) | C1 至 C5 状态 文件清单 实测结果和剩余工作 |
| [依赖说明](docs/DEPENDENCIES.md) | 固定版本 第三方许可和原创边界 |
| [测试摘要](reports/test-summary.md) | 自动测试 持续运行和复现命令 |

旧数据需要显式迁移到运行数据目录，先停机，再运行 `python backend/manage.py migrate-legacy`。原 CSV、原图和原前端保留；旧 `backend/data/processor.py` 是历史参考，不再被主流程调用。

**前端接入注意**：现有 `frontend/src/api/cameraApi.ts` 的 `USE_MOCK` 包含 `|| true`，总览页始终使用模拟。此交付未修改 React；需邓单关闭强制模拟并继续完成设置和识别控制交互。开发代理联调时后端加 `--dev-proxy`，正式同源部署不加该参数。真实模型工厂与摄像头验收由相应成员接入。

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q --junitxml=reports/pytest.xml
.\.venv\Scripts\python.exe backend/scripts/soak_test.py --seconds 1800 --output reports/soak-recheck.json
```

运行数据位于默认 `runtime` 或指定的 `--data-dir`，不上传。上传仓库、正式部署、备份与回退步骤见操作手册；上传命令必须由本人审阅后自行执行。未完成的硬件比较、真实模型性能、桌面安装包和完整前端联调在交付报告中单独列出。

第一版说明已保留于 [历史 README](docs/README-v1-reference.md)，仅供基线参考，当前启动与接口约定以本页及 docs 中的第二版文档为准。
