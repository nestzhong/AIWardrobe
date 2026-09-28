<div align="center">

# AI 智能衣橱

[![GitHub Stars](https://img.shields.io/github/stars/leoz9/AIWardrobe?style=social)](https://github.com/leoz9/AIWardrobe/stargazers)
[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://ghcr.io/leoz9/aiwardrobe)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-20+-339933?logo=node.js&logoColor=white)](https://nodejs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)

**面向日常穿搭的 AI 衣橱管理、天气感知推荐与本地隐私抠图工具。**

上传衣物照片后，系统可以自动去除背景、识别衣物类别与风格语义，并结合天气、星座运势、场景目标和衣橱库存生成可解释穿搭建议。

[简体中文](./README.md) | [English](./README.en.md) | [日本語](./README.ja.md)

---

<img src="docs/images/screenshot_landing.jpg" width="760" alt="AI 智能衣橱首页截图" />

</div>

## 项目亮点

| 能力 | 说明 |
| :--- | :--- |
| 智能录入 | 上传衣物图片后自动抠图，并用视觉模型分析类别、颜色、风格、季节和使用场景 |
| 多件服装录入（实验） | 上传真人照，自动拆分每件服饰（含分类/规格/bbox），逐件生成 canonical 商品图后入库；默认关闭，可在设置页开启 |
| 本地离线抠图 | 支持 `rembg + onnxruntime` 本地服务端推理，图片不需要发到第三方抠图服务 |
| remove.bg 兜底 | 未安装本地依赖或需要第三方效果时，可切换到 remove.bg API |
| 天气感知推荐 | 使用 Open-Meteo 免费天气接口，按实时温度、体感、湿度、风力辅助穿搭 |
| 地点与天气缓存 | 缓存文本地点解析、小时级天气与星座记录，减少重复等待和外部请求 |
| 今日星座运势 | 根据设置中的星座生成今日运势、幸运色、幸运数字和穿搭提示 |
| 多模式推荐 | `balanced`、`goal_first`、`wardrobe_first` 三种策略，适配均衡、目标优先和库存优先 |
| 可解释选择 | 推荐结果会展示上装、下装、鞋履和配饰的选择理由 |
| 语音目标输入 | 可用语音输入通勤、约会、运动、面试等场景目标 |
| AI 试穿 | 上传本人照片后，用与商品图相同的生图模型，把衣柜单品以图生图试穿到本人照片上 |
| OS 26 风格 UI | 采用 Liquid Glass 方向的透明、浮层、柔和边框与响应式移动端体验 |

## 架构图

```mermaid
flowchart LR
    User["用户 / 浏览器"] --> FE["React + Vite 前端\nTailwind CSS / i18next / Lucide"]
    FE --> API["FastAPI 后端\nREST API / 静态资源服务"]

    API --> Upload["上传与衣物管理\n/upload /wardrobe /clothes"]
    API --> Reco["穿搭推荐\n/recommendation"]
    API --> Weather["天气与城市\n/weather /cities"]
    API --> Horoscope["星座运势\n/horoscope/daily"]
    API --> Config["配置中心\n/config /models /install-rembg"]
    API --> TryOn["AI 试穿\n/tryon /person-image"]
    API --> Capture["多件服装录入（实验）\n/capture/analyze · generate · commit"]

    Upload --> Rembg["本地 rembg\nonnxruntime 推理"]
    Upload --> RemoveBg["remove.bg API\n可选云端抠图"]
    Upload --> LLMVision["视觉模型\n衣物语义识别"]

    Capture --> LLMVision
    Capture --> ImageGen["生图模型\nqwen-image / doubao-seedream"]
    Capture --> Rembg

    Reco --> LLMText["OpenAI 兼容接口 / Gemini\n推荐文案与解释"]
    Reco --> DB
    Weather --> OpenMeteo["Open-Meteo\n地理编码 + 天气"]
    Horoscope --> Aztro["Aztro / fallback\n基础运势来源"]

    API --> DB[("SQLite\n衣物 / 配置 / 天气缓存 / 地点缓存 / 星座缓存")]
    API --> Files[("本地文件\nuploads / data / static")]
```

## 核心数据流

### 衣物录入

```mermaid
sequenceDiagram
    participant U as 用户
    participant F as 前端
    participant B as FastAPI
    participant R as rembg/remove.bg
    participant L as 视觉模型
    participant D as SQLite + uploads

    U->>F: 上传衣物照片
    F->>B: POST /api/upload
    B->>R: 背景移除
    B->>L: 识别类别、颜色、风格语义
    B->>D: 保存图片和衣物记录
    B-->>F: 返回结构化衣物信息
```

### 多件服装录入（实验特性）

```mermaid
sequenceDiagram
    participant F as 前端
    participant B as FastAPI
    participant V as 视觉模型
    participant G as 生图模型
    participant R as rembg
    participant D as SQLite + uploads

    F->>B: POST /api/capture/analyze（真人照）
    B->>V: 识别服饰列表（类别/规格/bbox）
    B->>B: 按 bbox 裁剪服装参考图
    B-->>F: session_id + 服饰列表
    F->>B: POST /api/capture/generate（逐件）
    B->>G: 双图参考生成 canonical 商品图
    B->>R: 抠成透明 PNG
    B-->>F: 生成图 URL + 透明图 URL
    F->>B: POST /api/capture/commit
    B->>V: 语义分析（中文风格/季节/场景/颜色/描述）
    B->>D: 写入衣物记录（含溯源列）
```

### 今日推荐

```mermaid
sequenceDiagram
    participant F as 前端
    participant B as FastAPI
    participant W as 天气/地点缓存
    participant H as 星座缓存
    participant L as LLM
    participant D as 衣橱数据

    F->>B: GET /api/recommendation?mode=&goal=&location=
    B->>W: 读取地点解析与小时级天气缓存
    B->>H: 读取今日星座记录
    B->>D: 拉取衣橱候选衣物
    B->>L: 生成推荐文案与选择解释
    B-->>F: 返回天气、星座、搭配和选择理由
```

## 技术栈

| 层级 | 技术 |
| :--- | :--- |
| 前端框架 | React 19、Vite 7、React Router |
| UI 与样式 | Tailwind CSS 4、Lucide React、OS 26 / Liquid Glass 风格 |
| 国际化 | i18next、react-i18next、语言检测 |
| 后端框架 | FastAPI、Uvicorn、Pydantic |
| 数据存储 | SQLite、aiosqlite、本地 uploads/data 持久化 |
| AI 能力 | OpenAI 兼容接口、Google Gemini、视觉识别、LLM 推荐 |
| 抠图能力 | 本地 `rembg + onnxruntime`、可选 remove.bg API |
| 天气能力 | Open-Meteo 天气与地理编码、地点解析缓存、天气缓存 |
| 测试 | Vitest、React Testing Library、unittest、FastAPI TestClient |
| 部署 | Docker、Docker Compose、GHCR 镜像 |

## 目录结构

```text
AIWardrobe/
├── backend/
│   ├── api/                 # FastAPI 路由：上传、衣柜、配置、天气、推荐、星座、试穿
│   ├── domain/              # 配置、衣物和提示词领域模型
│   ├── services/            # 天气、推荐、抠图、LLM、试穿等服务
│   ├── storage/             # SQLite 表结构、CRUD、配置文件
│   ├── uploads/             # 本地上传图片与处理结果
│   └── main.py              # 后端入口与静态资源托管
├── frontend/
│   ├── src/components/      # 设置、上传、底部导航等通用组件
│   ├── src/pages/           # 首页、录入、衣柜、推荐、试穿、详情页
│   ├── src/contexts/        # 上传、推荐、主题上下文
│   ├── src/i18n/            # 中英日文案
│   └── src/__tests__/       # 前端回归测试
├── docs/images/             # README 截图资源
├── Dockerfile
├── docker-compose.yml
├── start.sh
└── start.bat
```

## 快速开始

### 环境要求

- Node.js `20+`
- Python `3.10+`
- 可选：OpenAI 兼容接口 Key 或 Google Gemini API Key
- 可选：remove.bg API Key

### 本地开发启动

```bash
git clone https://github.com/leoz9/AIWardrobe.git
cd AIWardrobe

# 后端
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..

# 前端
cd frontend
npm install
cd ..
```

一键启动：

```bash
# macOS / Linux
chmod +x start.sh
./start.sh

# Windows
start.bat
```

手动启动：

```bash
# 终端 1：后端
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --reload --port 8000

# 终端 2：前端
cd frontend
npm run dev
```

默认访问：

- 前端开发服务：http://localhost:5173
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

## Docker 部署

### 本地构建

```bash
docker build -t aiwardrobe:local .
docker run -d --name ai_wardrobe -p 8000:8000 \
  -v $(pwd)/backend/uploads:/app/backend/uploads \
  -v $(pwd)/backend/data:/app/backend/data \
  aiwardrobe:local
```

### Docker Compose

```bash
docker compose up --build -d
```

Compose 会挂载：

- `backend/uploads`：衣物图片、抠图结果、试穿结果
- `backend/data`：容器内 SQLite 数据库

### 使用预构建镜像

```bash
docker pull ghcr.io/leoz9/aiwardrobe:latest
docker run -d --name ai_wardrobe -p 8000:8000 \
  -v $(pwd)/backend/uploads:/app/backend/uploads \
  -v $(pwd)/backend/data:/app/backend/data \
  ghcr.io/leoz9/aiwardrobe:latest
```

容器模式下访问：http://localhost:8000

## 配置说明

启动后进入前端设置页完成配置：

| 配置项 | 说明 |
| :--- | :--- |
| API Base | OpenAI 兼容接口地址，例如 `https://api.openai.com/v1` |
| API Key | 用于视觉识别、推荐文案、星座推理等模型调用 |
| Model | 当前使用的模型名称 |
| 默认城市 | 天气和首页信息使用的地点，建议使用“城市, 省/州, 国家”格式 |
| 星座 | 今日星座运势和幸运色推荐使用 |
| 本地 rembg | 一键安装 `rembg` 与 `onnxruntime`，安装后按钮显示“rembg 已安装” |
| remove.bg API | 可选云端抠图服务，适合不想安装本地推理依赖的部署 |
| 本人照片 | 在设置页上传，作为 AI 试穿的参考人像，仅保存在本地服务器 |
| 多件服装录入（实验） | 开启后上传真人照会走「识别 → 逐件生成 → 确认入库」流程 |
| 识别模型 | 多模态服饰识别模型，默认 `qwen3.8-flash` |
| 生图模型 | canonical 商品图模型，默认 `qwen-image-3.0-pro`，可切换 `doubao-seedream-5.0-lite` |
| 生图 API Base / Key | 留空则复用上方 LLM 的 API Base / Key |
| 参考图传输方式 | `base64`（本地图片推荐）或 `url` |

## 常用 API

| 接口 | 说明 |
| :--- | :--- |
| `POST /api/upload` | 上传衣物图片、抠图并生成语义信息 |
| `POST /api/capture/analyze` | （实验）上传真人照，识别服饰列表并生成参考 crop |
| `POST /api/capture/generate` | （实验）对单件服饰生成 canonical 商品图并抠图 |
| `POST /api/capture/commit` | （实验）把选中的服饰批量写入衣柜 |
| `GET /api/wardrobe` | 获取衣橱列表 |
| `GET /api/clothes/{id}` | 获取衣物详情 |
| `GET /api/weather` | 获取当前天气 |
| `GET /api/cities` | 搜索城市与地点 |
| `GET /api/horoscope/daily` | 获取今日星座运势 |
| `GET /api/recommendation` | 获取今日穿搭推荐 |
| `POST /api/config` | 保存模型、天气、星座、抠图、生图配置 |
| `POST /api/install-rembg` | 安装或检测本地 rembg 依赖 |
| `POST /api/person-image` | 上传或替换本人照片（供 AI 试穿使用） |
| `DELETE /api/person-image` | 移除本人照片 |
| `POST /api/tryon` | 以本人照片 + 单品服饰为参考图生成试穿图，body 为 `{ "garment_ids": [1, 2, 3] }` |

推荐接口示例：

```bash
curl "http://localhost:8000/api/recommendation?location=Shanghai,Shanghai,China&mode=goal_first&goal=commute"
```

## 测试与验证

```bash
# 后端回归测试
cd backend
venv/bin/python -m unittest test_recommendation_api
venv/bin/python -m unittest test_capture_pipeline

# 多件服装录入真实网关冒烟（非 CI，会消耗额度）
venv/bin/python test_garment_capture.py

# 前端测试
cd ../frontend
npm test

# 前端 lint
npm run lint

# 前端生产构建
npm run build
```

当前测试覆盖了：

- 设置保存时避免无关天气/星座重复刷新
- 星座变化只刷新星座，不重新请求天气
- 本地 rembg 安装状态展示
- 天气缓存和地点解析缓存
- 推荐模式、目标和可解释选择理由
- 多件服装录入：生图请求体分支、响应解析、bbox 裁剪、生图失败降级、analyze/commit 接口

## 截图

<div align="center">
  <img src="docs/images/screenshot_landing.jpg" width="820" alt="首页" />
</div>

<div align="center">
<table>
<tr>
<td align="center"><img src="docs/images/screenshot_input.jpg" width="280" /><br /><b>录入新衣</b></td>
<td align="center"><img src="docs/images/screenshot_wardrobe.jpg" width="280" /><br /><b>我的衣橱</b></td>
</tr>
<tr>
<td align="center"><img src="docs/images/screenshot_recommendation.jpg" width="280" /><br /><b>AI 推荐</b></td>
<td align="center"><img src="docs/images/screenshot_detail.jpg" width="280" /><br /><b>衣物详情</b></td>
</tr>
</table>
</div>

## 许可证

[MIT](LICENSE) © 2024 leoz9
