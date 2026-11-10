# Windows 桌面应用

桌面包使用 pywebview 加载 React 生产构建，并包含独立的后端和维护工具。正常启动时只需双击 `ItemTrackingSystem.exe`，应用会启动它自己打包的后台；关闭窗口时请求安全关闭，并且只等待/管理本应用创建的后台进程。

当前打包配置默认使用 MockCamera 和 FakeDetector 演示链路。真实摄像头及真实模型需要相应适配器和依赖一并集成后再构建，不能将当前演示包视为真实硬件或模型验收。

## 构建环境

- Windows x64。
- 使用项目 `.venv` 中的 Python；若不存在，构建脚本会通过 `py -3.12` 创建。也可通过 `-PythonExe` 显式指定 Python 3.12 环境。仓库当前锁定依赖以 Python 3.12 Windows x64 为测试基线。
- Node.js/npm。
- 目标电脑须安装 Microsoft Edge WebView2 Runtime；应用包暂不内嵌该 Runtime。

在仓库根目录 PowerShell 执行：

```powershell
.\scripts\Build-Desktop.ps1
```

脚本执行 `npm ci`、React 生产构建、安装固定后端及桌面构建依赖，并用 PyInstaller 分别生成桌面主程序、后台程序和维护工具。完整目录输出为：

```text
desktop\dist\ItemTrackingSystem\
  ItemTrackingSystem.exe
  frontend\
  runtime\ItemTrackingBackend\
  runtime\ItemTrackingMaintenance\
  使用说明.md
```

把整个 `ItemTrackingSystem` 文件夹复制到目标 Windows 电脑，双击其中的 `ItemTrackingSystem.exe`。这是一种免安装目录包，不是单文件 exe 或安装向导。每次构建时，脚本会自动删除输出位置下已有的 `ItemTrackingSystem` 文件夹并重新生成；如需保留旧包，请先将它移到其他位置。

也可显式指定 Python 或输出位置：

```powershell
.\scripts\Build-Desktop.ps1 -PythonExe '.\.venv\Scripts\python.exe' -OutputDirectory '.\artifacts'
```

已安装全部依赖时可跳过依赖安装（仍会执行前端构建和打包）：

```powershell
.\scripts\Build-Desktop.ps1 -SkipInstall
```

不要把 `.venv`、`node_modules`、模型权重或运行数据复制到交付包中。PyInstaller 打包不等同于最终安装程序；如果需要桌面快捷方式、卸载器、签名和自动安装 WebView2 Runtime，应另行制作安装器。

## 使用及控制器合同

桌面操作区调用 `start()`、`stop()`、`open_data_dir()`、`export_logs(destination)`、`set_data_dir(path)` 和 `shutdown()`，返回格式统一为 `{ok, message, data}`。目录选择和日志保存位置选择由原生对话框提供。预览和识别启停仍由 HTTP API 控制。

- 打包模式下 `start()` 启动随包提供的后台进程；`stop()` 向该后台请求 `/api/shutdown`，等待进程正常退出。不会按端口查找或终止其他程序。
- 开发模式不创建后台进程，也不接管手动启动的服务。需要另开终端运行后端进行开发联调。
- 默认数据目录为 `%LOCALAPPDATA%\ItemTrackingSystem\data`。选择其他已存在目录后，路径保存在 `%LOCALAPPDATA%\ItemTrackingSystem\desktop.json`，下次启动应用时生效；不会在线迁移数据库。
- 日志导出会先安全停止本应用后台，再调用随包维护工具获取数据目录锁完成导出，之后按原状态重启后台。导出应选择数据目录以外的新 `.zip` 文件。
- 如需更改演示源，可在启动应用前设置 `TRACKING_CAMERA_KIND`（`mock` 或 `opencv`）、`TRACKING_CAMERA_SOURCE` 和 `TRACKING_PORT`。当前包的实际摄像头、模型适配器能力仍取决于打包时包含的后端实现。

## 验证

前端测试和类型检查见仓库根目录 README。`python -m pytest desktop/test_bridge.py -q` 验证控制器；只有在 Windows 图形桌面环境中双击打包 exe 并检查 1366×768 窗口、预览、目录选择、日志导出和安全关闭，才算完成桌面烟雾验收。
