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

> 若看到 `WARNING: This is a development server. Do not use it in a production deployment.` 属正常提示，本地开发可忽略；**正式部署**请使用 Gunicorn、uWSGI 等 WSGI 服务器。

后端默认运行在 **http://localhost:5000**，提供：

- `GET /api/items` → 物品类别列表（数组）
- `GET /api/items/<类别名>` → 该物品最后一次出现：`{ category, image_path, processed_image_path, timestamp }`（带框图为 `processed_image_path`）
- `GET /images/<文件名>` → 原图静态文件
- `GET /processed/<文件名>` → 带检测框的图片（后端根据 CSV 的 `location` 画框生成）

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
- 请求 `/images/xxx`、`/processed/xxx` 会转发到后端，用于显示原图与带框图

### 3. 使用方式

1. 浏览器打开 http://localhost:3000  
2. 下拉选择物品（数据来自后端 CSV 的 `class_name` 列）  
3. 点击「查询最后出现位置」  
4. 右侧会显示该物品最后一次出现的**带检测框的图片**与时间（有框图则显示框图，否则显示原图）  


---

## 二、数据约定

- **CSV**（`backend/data/recognition.csv`）：列名与 `backend/config.py` 一致，即 `timestamp`、`class_name`、`location`、`image_id`；图片放在 `backend/images/`，文件名与 CSV 中 `image_id` 一致；`location` 为检测框坐标，格式如 `"[xmin, ymin, xmax, ymax]"`，后端据此生成带框图到 `backend/processed_images/`。  
- **接口**：  
  - 列表：`GET /api/items` 返回 `["backpack","cup",...]`  
  - 详情：`GET /api/items/<类别>` 返回 `{ "category", "image_path", "processed_image_path", "timestamp" }`，前端优先用 `processed_image_path` 显示带框图。  
- 前端经 proxy 请求 `/images/`、`/processed/` 显示图片。

---

## 三、已做的对接修改

- 后端 `/api/items` 直接返回**数组**，前端可直接当列表用。  
- `GET /api/items/<path:category>` 返回 `category` / `image_path` / `processed_image_path` / `timestamp`；前端优先显示 `processed_image_path`（带框图）。  
- 后端根据 CSV 的 `location` 在原图上画检测框，生成图存于 `processed_images/`，通过 `GET /processed/<文件名>` 提供。  

