# 基于神经网络的物品示踪系统 V1.0

家庭本地物品检测与最后出现记录系统。后端提供摄像头运行控制、MJPEG 预览、后台推理、SQLite 检测事件、类别查询和 CSV 兼容；React + TypeScript 前端提供运行总览、实时预览、识别设置、检测历史和最后出现查询。

系统通过统一 HTTP API 与后端交互。前端不直接访问摄像头、运行检测模型或读取后端数据库/CSV。真实摄像头和真实检测模型是否可用，取决于本机设备及后端适配器配置；Mock 演示不代表真实硬件或模型已完成验收。

## 本机启动

### 后端

在仓库根目录打开 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
.\.venv\Scripts\python.exe backend/run.py --camera mock --demo --start --infer --dev-proxy
```

这会启动模拟摄像头和显式启用的演示检测器，并信任 CRA 开发代理。默认服务地址为 `http://127.0.0.1:5000`。关闭服务可在终端按 `Ctrl+C`；API 也提供 `POST /api/shutdown`。

真实设备/模型由后端通过配置或工厂适配器接入，具体选项参阅[后端操作手册](docs/OPERATIONS.md)和[API 文档](docs/API.md)。不带 `--demo` 且未配置检测器时，推理启动会明确报错，而不是模拟成功。

### 前端

另开 PowerShell 终端：

```powershell
cd frontend
npm install
npm start
```

浏览器打开 `http://localhost:3000`。CRA proxy 将 `/api/...` 请求转发到本地 Flask 服务；后端开发联调时需启用 `--dev-proxy`。

前端默认请求真实后端。若只需演示界面，可在启动前显式启用 Mock：

```powershell
$env:REACT_APP_USE_MOCK = "true"
npm start
```

关闭 Mock 或修改环境变量后，需重启前端开发服务器。Mock 模式使用本地模拟状态、设置、事件和图片，不验证后端连通性、真实视频源或检测器。

### 前端验证命令

在 `frontend` 目录运行：

```powershell
npx tsc --noEmit
npm test -- --watchAll=false
npm run build
```

## 前端功能

- **总览**：后端、摄像头、预览和推理状态；MJPEG 预览启停、错误反馈和重试；最近事件自动刷新。
- **设置**：检测类别、置信度阈值、推理频率、事件合并间隔和模型输入尺寸；显示只读模型/摄像头配置；控制后台识别。
- **历史**：类别、摄像头和时间筛选；分页浏览检测事件；查看原图/标注图；导出 CSV。
- **寻物查询**：按类别查询最后一次出现记录和图片。

详细接口以[后端 API 文档](docs/API.md)为准；前端接口说明见[前端 HTTP 接口说明](frontend/docs/HTTP接口协议草案.md)。

## 其他文档

| 文档 | 内容 |
| --- | --- |
| [操作手册](docs/OPERATIONS.md) | 安装、启动、数据管理、备份和故障排查 |
| [API](docs/API.md) | 路由、字段、错误格式和兼容说明 |
| [架构](docs/ARCHITECTURE.md) | 视频链路、线程、数据库和关闭流程 |
| [交付报告](docs/DELIVERY.md) | 交付状态、测试结果和未完成事项 |
| [依赖说明](docs/DEPENDENCIES.md) | 固定版本、第三方许可和原创边界 |
| [历史 README](docs/README-v1-reference.md) | 第一版基线参考 |

运行数据保存在默认 `runtime` 目录或 `--data-dir` 指定目录，不应提交到仓库。旧 CSV 和图片迁移方式见[操作手册](docs/OPERATIONS.md)。
