# 家庭寻物系统前端

React + TypeScript 前端。接口合同以仓库根目录的 [`docs/API.md`](../docs/API.md) 为准，前端接口说明见 [`docs/HTTP接口协议草案.md`](docs/HTTP接口协议草案.md)。

## 本机启动

先在另一个终端从仓库根目录启动后端。CRA 开发代理需要后端信任 localhost:3000 来源：

```powershell
.\.venv\Scripts\python.exe backend/run.py --camera mock --demo --start --infer --dev-proxy
```

在 `frontend` 目录安装依赖并启动：

```powershell
npm install
npm start
```

默认连接真实后端。仅做界面演示时，可显式开启本地 Mock：

```powershell
$env:REACT_APP_USE_MOCK = "true"
npm start
```

环境变量修改后需重启开发服务器。Mock 模式不验证真实后端、摄像头或模型。

## 常用脚本

```powershell
npx tsc --noEmit
npm test -- --watchAll=false
npm run build
```

## 功能入口

- **总览**：实时预览、系统/设备状态和最近检测事件。
- **历史**：检测事件筛选、分页、原图/标注图查看和 CSV 导出；可按类别查询最后出现记录。
- **设置**：检测类别、置信度、推理频率、事件合并间隔、模型输入尺寸及推理启停。
