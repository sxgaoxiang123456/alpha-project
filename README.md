# A股自动盯盘AI助手

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-00a393.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> 一款可私有部署的 A 股盯盘助手，聚焦「自选股管理 + 分钟级行情监控 + 价格/涨跌幅预警 + 推送通知」，替代手工刷新行情和手动设预警。

---

## 目录

- [功能特性](#功能特性)
- [技术架构](#技术架构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [项目结构](#项目结构)
- [API 概览](#api-概览)
- [开发指南](#开发指南)
- [测试](#测试)
- [部署](#部署)
- [产品规划](#产品规划)
- [免责声明](#免责声明)

---

## 功能特性

### 已实现（MVP v1.0）

| 功能 | 描述 | 状态 |
|------|------|:----:|
| **自选股管理** | 添加/删除/分组/CSV 批量导入导出自选股 | ✅ |
| **实时行情** | 大盘指数 + 自选股价格/涨跌幅快照，1-5 分钟刷新 | ✅ |
| **价格/涨跌幅预警** | 设置条件（高于/低于/涨幅/跌幅），触发后推送通知 | ✅ |
| **推送通知** | 飞书卡片（主通道）+ Telegram（备用通道）双通道冗余 | ✅ |
| **Dashboard** | 低密度首页：大盘指数 + 自选股速览 + AI 简报 + 快捷入口 | ✅ |
| **数据多源容灾** | AkShare 主数据源 + BaoStock 备用，自动切换 | ✅ |
| **系统设置** | 数据源偏好、推送通道配置、刷新间隔、告警冷却 | ✅ |

### 规划中（v1.1+）

| 功能 | 描述 | 计划 |
|------|------|------|
| AI 早盘简报 | 每日开盘前自动生成市场概览 + 异动 TOP 5 | v1.1 |
| 自然语言设预警 | "茅台跌破 1500 提醒我"一句话创建规则 | v1.1 |
| 成交量异动检测 | 自动检测成交量突增/价格异动并推送 | v1.1 |
| PWA 移动端 | 手机浏览器轻量版 Dashboard | v1.2 |
| 智能选股 | 自然语言转筛选条件 | v1.2 |

---

## 技术架构

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | [FastAPI](https://fastapi.tiangolo.com) | 高性能异步 Python Web 框架 |
| ORM | [SQLAlchemy 2.0](https://docs.sqlalchemy.org) | 数据库对象关系映射 |
| 数据校验 | [Pydantic v2](https://docs.pydantic.dev) | 请求/响应模型校验 |
| 模板引擎 | [Jinja2](https://jinja.palletsprojects.com) | SSR 服务端渲染 |
| 样式框架 | [Tailwind CSS](https://tailwindcss.com) (CDN) | 暗色主题，无构建步骤 |
| 数据源 | [AkShare](https://www.akshare.xyz) / [BaoStock](http://baostock.com) | 零成本 A 股数据源 |
| 任务调度 | [APScheduler](https://apscheduler.readthedocs.io) | 行情刷新/预警检测/简报生成 |
| 推送通道 | 飞书 Open API (lark-cli) / Telegram Bot API | 主备双通道 |
| 数据库 | SQLite (默认) / PostgreSQL | 单用户轻量部署 |
| 测试 | pytest + pytest-playwright | 单元/集成/E2E 测试 |
| 部署 | Docker Compose + Nginx | 容器化一键部署 |

### 架构特点

- **单用户架构**：MVP 假设单用户，无认证/权限系统，降低复杂度
- **零成本数据源**：AkShare + BaoStock 免费接入，年运营成本 <= 1000 元
- **服务端渲染 (SSR)**：Jinja2 模板 + Tailwind CSS CDN，无需前端构建工具
- **数据多源容灾**：主源故障时自动切换到备用源，保障行情连续性
- **边缘触发预警**：仅在条件从"不满足"变为"满足"时触发，避免持续告警
- **冷却期机制**：同一规则触发后 N 分钟内不重复推送，防止信息轰炸

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        用户浏览器                            │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │  Dashboard  │  │  预警规则页   │  │  自选股 / 设置页    │ │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬──────────┘ │
└─────────┼────────────────┼─────────────────────┼────────────┘
          │                │                     │
          └────────────────┴─────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   FastAPI   │
                    │   (Jinja2)  │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌─────▼──────┐
    │ Dashboard   │ │ Alert       │ │ Watchlist  │
    │ Service     │ │ Service     │ │ Service    │
    └──────┬──────┘ └──────┬──────┘ └─────┬──────┘
           │               │               │
           └───────────────┼───────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼─────┐ ┌────▼─────┐ ┌───▼────┐
       │  SQLite    │ │  Cache   │ │ Push   │
       │  (ORM)     │ │  (内存)  │ │ Service│
       └────────────┘ └────┬─────┘ └───┬────┘
                           │           │
                    ┌──────┴───┐   ┌───┴────────┐
                    │ AkShare  │   │ 飞书 / TG  │
                    │ BaoStock │   └────────────┘
                    └──────────┘
```

---

## 快速开始

### 环境要求

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)（Python 包管理器）
- Git

### 一键启动

```bash
# 克隆仓库
git clone <repo-url> && cd alpha-project

# 启动（自动检测环境、安装依赖、启动服务）
bash start.sh
```

服务启动后访问 http://127.0.0.1:8000/

### 手动安装

```bash
cd backend

# 创建虚拟环境并安装依赖
bash setup.sh

# 启动服务
.venv/bin/uvicorn app.main:app --reload
```

### Docker 部署

```bash
# 复制环境配置
cp infrastructure/.env.example backend/.env

# 启动服务
docker-compose -f infrastructure/docker-compose.yml up -d
```

---

## 配置说明

### 环境变量

创建 `backend/.env` 文件：

```env
# 应用配置
DATABASE_URL=sqlite:///./data/watchlist.db
ENCRYPTION_KEY=your-encryption-key-here

# 行情配置（默认即可）
QUOTE_REFRESH_INTERVAL_MINUTES=3
QUOTE_CACHE_TTL_SECONDS=300
HEALTH_CHECK_INTERVAL_MINUTES=5

# 飞书主推送通道（可选，三项均非空时启用）
FEISHU_APP_ID=cli_xxxxxxxxxxxx
FEISHU_APP_SECRET=your-app-secret
FEISHU_BRAND=feishu          # 可选，默认 feishu
FEISHU_CHAT_ID=oc_xxxxxxxxxxxx
```

### 推送通道配置

| 通道 | 配置方式 | 说明 |
|------|---------|------|
| **飞书** | `.env` 环境变量 | 提供飞书自建应用的 `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_CHAT_ID`；修改后需重启服务生效 |
| **Telegram** | 系统设置页 | 在设置页（`/settings`）配置 Bot Token + Chat ID |

> 飞书主通道配置状态可在系统设置页查看。推送通道为可选配置，未配置时预警触发仍会记录本地推送日志。

---

## 项目结构

```
alpha-project/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── main.py             # FastAPI 应用入口
│   │   ├── config.py           # 应用配置
│   │   ├── database.py         # 数据库连接
│   │   ├── routers/            # API 路由
│   │   │   ├── dashboard.py    # Dashboard 首页
│   │   │   ├── watchlist.py    # 自选股管理
│   │   │   ├── alerts.py       # 预警规则 CRUD
│   │   │   ├── settings.py     # 系统设置
│   │   │   ├── quotes.py       # 行情数据
│   │   │   ├── push.py         # 推送日志
│   │   │   ├── groups.py       # 分组管理
│   │   │   ├── import_export.py # CSV 导入导出
│   │   │   └── system.py       # 系统状态
│   │   ├── services/           # 业务服务层
│   │   │   ├── dashboard_service.py   # Dashboard 数据聚合
│   │   │   ├── quote_service.py       # 行情获取与缓存
│   │   │   ├── alert_service.py       # 预警检测引擎
│   │   │   ├── push_service.py        # 推送服务
│   │   │   ├── data_source.py         # 数据源适配器
│   │   │   ├── data_source_facade.py  # 数据源门面
│   │   │   ├── settings_service.py    # 配置管理
│   │   │   ├── feishu_client.py       # 飞书客户端
│   │   │   └── telegram_client.py     # Telegram 客户端
│   │   ├── models/             # 数据库模型
│   │   ├── schemas/            # Pydantic 数据模型
│   │   └── core/               # 核心工具
│   ├── tests/                  # 测试
│   │   ├── unit/               # 单元测试
│   │   ├── integration/        # 集成测试
│   │   └── e2e/                # E2E 测试 (Playwright)
│   ├── setup.sh                # 环境构建脚本
│   └── requirement.txt         # Python 依赖
│
├── frontend/                   # 前端模板
│   └── src/templates/          # Jinja2 模板
│       ├── base.html           # 基础布局
│       ├── dashboard.html      # Dashboard 首页
│       ├── alerts.html         # 预警规则页
│       ├── settings.html       # 系统设置页
│       └── components/         # 可复用组件
│           ├── side_nav.html   # 侧边导航
│           ├── market_index_card.html
│           ├── watchlist_snapshot.html
│           └── ...
│
├── specs/                      # 产品规格文档
│   ├── prd.md                  # 产品需求文档
│   └── 001-006-{feature}/      # 各功能规格
│
├── infrastructure/             # 部署配置
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── .env.example
│
├── start.sh                    # 一键启动脚本
└── README.md                   # 本文档
```

---

## API 概览

### 页面路由 (HTML)

| 路径 | 说明 |
|------|------|
| `GET /` | Dashboard 首页 |
| `GET /watchlist-page` | 自选股管理页 |
| `GET /alerts-page` | 预警规则页 |
| `GET /settings` | 系统设置页 |

### REST API

| 路径 | 方法 | 说明 |
|------|------|------|
| `/watchlist` | GET/POST | 自选股列表/添加 |
| `/watchlist/{code}` | PUT/DELETE | 编辑/删除自选股 |
| `/watchlist/import` | POST | CSV 批量导入 |
| `/alerts` | GET/POST | 预警规则列表/创建 |
| `/alerts/{id}` | PUT/DELETE | 编辑/删除规则 |
| `/alerts/{id}/toggle` | PATCH | 启用/停用规则 |
| `/quotes` | GET | 获取实时行情 |
| `/groups` | GET/POST | 分组列表/创建 |
| `/push/logs` | GET | 推送历史 |
| `/health` | GET | 健康检查 |

完整 API 文档见启动后的 `/docs` (Swagger UI) 或 `/redoc`。

---

## 开发指南

### 添加新功能

本项目采用 [spec-kit](specs/) 工作流：

1. 在 `specs/XXX-{feature}/` 目录创建规格文档 (`spec.md`, `plan.md`, `tasks.md`)
2. 按 Phase 顺序执行任务，每个 Task 产出 1-3 个文件
3. 先写测试（FAIL），再实现（PASS），最后重构
4. 全量测试通过后，更新 `state.md`，创建 commit

### 代码规范

- 涨红跌绿：A 股惯例，红色表示上涨，绿色表示下跌
- 暗色模式唯一：不维护亮色模式主题
- 中文界面：所有用户可见文字必须为中文
- 设计 Token：颜色/字号/间距统一使用 `design-reference/DESIGN.md` 规范

### 关键约束

- **不做交易功能**：仅信息展示，不提供下单/交易
- **单用户架构**：MVP 无多用户支持
- **零成本数据源**：AkShare + BaoStock 优先，验证失败前不升级付费源

---

## 测试

### 运行测试

```bash
cd backend

# 全量测试
.venv/bin/python -m pytest tests/

# 单元测试
.venv/bin/python -m pytest tests/unit/

# 集成测试
.venv/bin/python -m pytest tests/integration/

# E2E 测试（需 Chromium）
.venv/bin/python -m pytest tests/e2e/
```

### 测试覆盖

| 类型 | 文件 | 覆盖范围 |
|------|------|---------|
| 单元测试 | `tests/unit/` | Service 层、数据模型、工具函数 |
| 集成测试 | `tests/integration/` | 数据库真实层、API 契约、数据流 |
| E2E 测试 | `tests/e2e/` | 前端结构、全链路旅程、前后端切片 |
| 视觉回归 | `tests/e2e/test_frontend_structural.py` | 桌面端/移动端截图基线 |
| 可访问性 | `tests/e2e/test_frontend_structural.py` | axe-core 扫描 |

---

## 部署

### Docker Compose（推荐）

```bash
# 1. 准备环境配置
cp infrastructure/.env.example backend/.env
# 编辑 backend/.env，填入加密密钥和推送配置

# 2. 构建并启动
docker-compose -f infrastructure/docker-compose.yml up -d --build

# 3. 查看日志
docker-compose -f infrastructure/docker-compose.yml logs -f
```

### 手动部署

```bash
# 1. 克隆代码
git clone <repo-url> && cd alpha-project

# 2. 构建环境
cd backend && bash setup.sh

# 3. 配置环境变量
vim .env

# 4. 启动服务（生产模式）
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 产品规划

### 版本路线图

| 版本 | 时间 | 核心功能 |
|------|------|---------|
| **v1.0 (MVP)** | 2026.06 | 自选股 + 行情 + 预警 + 推送 + Dashboard |
| **v1.1** | 2026.07 | AI 早盘简报 + 自然语言预警 + 异动检测 |
| **v1.2** | 2026.08 | 智能选股 + PWA + 多数据源升级 |
| **v2.0** | 2026.09+ | Agent 编排 + 回测引擎 + 移动端 |

### MVP 验证假设

1. 用户愿意为"自动盯盘"接受 1-5 分钟的数据延迟
2. 飞书卡片推送的打开率 > 70%
3. 零成本数据源（AkShare + BaoStock）的稳定性 >= 80%

---

## 免责声明

> **本工具仅供个人学习研究使用，所有行情数据、预警信息、简报内容仅供参考，不构成任何投资建议。**
>
> 使用本工具进行的投资决策风险由用户自行承担。股市有风险，入市需谨慎。

---

## 相关文档

- [产品需求文档 (PRD)](specs/prd.md)
- [架构基线决策](specs/research/06-架构基线决策.md)
- [设计规范](design-reference/DESIGN.md)
- [LEARNINGS 沉淀](LEARNINGS.md)

---

## License

MIT License - 详见 [LICENSE](LICENSE) 文件。
