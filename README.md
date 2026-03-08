# 家庭寻物系统 — 前后端联调说明

## 一、前后端如何跑通

### 1. 启动后端（Flask）

```bash
cd backend
# 建议使用虚拟环境
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate

pip install -r requirements.txt
python app.py
```

后端默认运行在 **http://localhost:5000**，提供：

- `GET /api/items` → 物品类别列表（数组）
- `GET /api/items/<类别名>` → 该物品最后一次出现：`{ category, image_path, timestamp }`
- `GET /images/<文件名>` → 图片静态文件

### 2. 启动前端（React）

**新开一个终端**：

```bash
cd frontend
npm install
npm start
```

前端会跑在 **http://localhost:3000**。  
`package.json` 里已配置 `"proxy": "http://localhost:5000"`，所以：

- 请求 `/api/items`、`/api/items/xxx` 会转发到后端 5000 端口
- 请求 `/images/xxx` 也会转发到后端，用于显示图片

### 3. 使用方式

1. 浏览器打开 http://localhost:3000  
2. 下拉选择物品（数据来自后端 `recognition.csv` 的 `item_name`）  
3. 点击「查询最后出现位置」  
4. 右侧会显示该物品最后一次出现的图片与时间  

只要先启后端、再启前端，即可前后端跑通。

---

## 二、数据约定

- **CSV**（`backend/data/recognition.csv`）：列 `timestamp`、`item_name`、`location`、`image_filename`；图片文件放在 `backend/images/`，文件名与 CSV 中 `image_filename` 一致。  
- **接口**：  
  - 列表：`GET /api/items` 返回 `["backpack","cup",...]`  
  - 详情：`GET /api/items/<类别>` 返回 `{ "category": "backpack", "image_path": "/images/capture_001.jpg", "timestamp": "2026-03-05 10:00:00" }`  
- 前端用 `image_path` 请求图片（经 proxy 到后端），故能正确显示。

---

## 三、已做的对接修改

- 后端 `/api/items` 改为直接返回**数组**（不再包在 `{"items:": ...}` 里），前端可直接当列表用。  
- 新增 `GET /api/items/<path:category>`，返回 `category` / `image_path` / `timestamp`，与前端约定一致。  
- 后端 `processor` 里图片路径由 `/iamges/` 改为 `/images/`。  

按上述顺序启动后端和前端即可联调。
