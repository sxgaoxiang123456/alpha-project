# Implementation Plan: 基础 Dashboard

**Feature**: 006-dashboard | **Date**: 2026-05-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/006-dashboard/spec.md`

---

## Summary

基础 Dashboard 是系统的用户主界面，负责将所有后台数据（自选股、行情、预警、简报、推送历史、通道状态）整合为一个低密度、易读的首页。核心实现：用户打开页面 → 后端聚合多个上游模块数据 → Jinja2 模板渲染 → HTMX 驱动局部刷新 → 浏览器展示。同时支持移动端自适应、首次使用引导、数据源降级提示。

---

## Technical Context

**Language/Version**: Python 3.11+
**Primary Framework**: FastAPI 0.110+（复用 F1）
**ORM**: SQLAlchemy 2.0+（复用 F1）
**Data Validation**: Pydantic 2.0+（复用 F1）
**Storage**: SQLite 3.39+（复用 F1）
**Template Engine**: Jinja2 3.1+（复用 F1/F4，新增 Dashboard 模板）
**Frontend**: HTMX 1.9+（复用 F1 架构基线）
**CSS**: Tailwind CSS 3.4+（新增，通过 CDN）
**Testing**: pytest 8.0+ + httpx 0.27+ + pytest-asyncio 0.23+（复用 F1）
**Target Platform**: Linux Docker 容器
**Project Type**: Web application — 数据展示层
**Performance Goals**: 首屏加载 < 3 秒，缓存渲染 < 1 秒，行情刷新不闪屏
**Constraints**: 单用户系统（MVP 无认证），移动端 viewport < 768px 自适应，自选股上限 50 只
**Scale/Scope**: 1 个首页 + 3 个模板组件 + 1 个聚合服务

---

## Constitution Check

*本项目暂无有效 constitution.md，跳过宪法检查。*

---

## Project Structure

### Documentation (this feature)

```text
specs/006-dashboard/
├── spec.md
├── plan.md
└── checklists/
```

### Source Code (新增与复用)

本 feature 为数据展示层，**新建**前端模板和 Dashboard 聚合模块，**复用** F1-F4 基础设施：

```text
# 复用已有模块（不修改，仅依赖调用）
app/config.py                 # 复用 — Dashboard 配置项（刷新间隔、自选股上限）
app/database.py               # 复用 — SQLite 连接（读取 PushLog、Stock 等已有表）
app/main.py                   # 复用 — 注册 dashboard 路由
app/models/
│   ├── base.py               # 复用 F1
│   ├── stock.py              # 复用 F1 — 自选股数据
│   ├── alert_rule.py         # 复用 F3 — 预警规则状态
│   ├── price_history.py      # 复用 F3 — 历史行情（用于迷你趋势图）
│   ├── push_log.py           # 复用 F4 — 推送日志
│   ├── push_channel.py       # 复用 F4 — 通道状态
│   └── app_setting.py        # 新建：AppSetting 模型（运行时 KV 配置表，key/value/category/is_encrypted）
│
app/schemas/
│   ├── __init__.py           # 复用 F1
│   └── stock.py              # 复用 F1 — 自选股 schema
│
app/services/
│   ├── watchlist_service.py  # 复用 F1 — 自选股列表和分组
│   ├── data_source_facade.py # 复用 F2 — 数据源健康状态
│   ├── cache_service.py      # 复用 F2 — 行情缓存读取
│   ├── quote_service.py      # 复用 F3 — 大盘指数和个股行情
│   ├── alert_service.py      # 复用 F3 — 今日预警触发记录
│   └── push_service.py       # 复用 F4 — 推送历史和通道状态
│
app/routers/
│   ├── watchlist.py          # 复用 F1 — 自选股管理 API
│   ├── push.py               # 复用 F4 — 推送历史查询 API
│   └── alert.py              # 复用 F3 — 预警相关 API
│
app/core/
│   └── quote_scheduler.py    # 复用 F3 — 定时任务状态（判断简报是否生成）
│
# 本 feature 新建模块
app/routers/
│   ├── dashboard.py          # 新建：Dashboard 首页路由（GET /，聚合所有数据）
│   └── settings.py           # 新建：设置页路由（GET/POST /settings，读写推送通道/数据源/偏好配置）
│
app/services/
│   ├── dashboard_service.py  # 新建：Dashboard 数据聚合服务（协调多个上游服务）
│   └── settings_service.py   # 新建：配置管理服务（读写 app_settings 表，敏感字段加密/解密）
│
app/schemas/
│   ├── dashboard.py          # 新建：DashboardViewResponse Pydantic 模型
│   └── settings.py           # 新建：SettingRequest, SettingResponse Pydantic 模型
│
app/templates/
│   ├── dashboard.html        # 新建：Dashboard 主页面模板
│   ├── components/
│   │   ├── market_index.html    # 新建：大盘指数组件
│   │   ├── stock_card.html      # 新建：自选股卡片组件（含迷你趋势图）
│   │   ├── briefing_card.html   # 新建：简报卡片组件
│   │   ├── alert_banner.html    # 新建：今日预警汇总横幅
│   │   ├── push_history.html    # 新建：推送历史组件
│   │   ├── channel_status.html  # 新建：通道状态组件
│   │   ├── quick_actions.html   # 新建：快捷入口组件
│   │   └── onboarding.html      # 新建：首次使用引导组件
│   └── base.html             # 新建：基础布局模板（含 HTMX、Tailwind CDN）
│
app/static/
│   ├── css/
│   │   └── dashboard.css     # 新建：Dashboard 专用样式（响应式布局）
│   └── js/
│       └── dashboard.js      # 新建：定时刷新逻辑（60 秒轮询）和数据源恢复检测
│
# 测试（新增）
tests/
│   ├── conftest.py           # 复用 F1 fixtures
│   ├── unit/
│   │   └── test_dashboard_service.py  # Dashboard 聚合服务测试（mock 上游）
│   ├── integration/
│   │   └── test_dashboard.py          # 端到端测试：页面渲染 + 刷新 + 降级
│   └── e2e/
│       └── test_responsive.py         # 响应式布局测试（多 viewport）
```

**结构决策说明**:
- `dashboard_service.py` 是本 feature 核心，负责聚合所有上游数据（F1 自选股、F2 行情缓存、F3 预警/简报、F4 推送历史/通道状态），对外提供统一的 `get_dashboard_data()` 接口
- `dashboard.py` 路由只负责：接收请求 → 调用聚合服务 → 渲染模板，不直接访问任何上游模块
- 前端采用 HTMX + Jinja2 服务器端渲染（SSR），MVP 不做 SPA。HTMX 负责局部刷新（行情数据、推送历史）
- 迷你趋势图采用 SVG 内联渲染（当日分时数据），不引入图表库，降低加载开销
- 首次使用引导通过检查自选股数量判断，无独立状态表
- 移动端自适应通过 CSS 媒体查询 + Tailwind 响应式类实现，后端只返回同一套数据
- 快捷入口固定 4 个，前端硬编码，不做配置表
- `settings_service.py` 是独立的横向模块，被 F4/F5/F6 复用，负责所有用户级配置的持久化（`app_settings` 表）和敏感字段加解密

---

## Data Flow

### Dashboard 首页加载

```mermaid
graph LR
    Browser[用户浏览器] --"GET /"--> Router[dashboard.py]
    Router --"调用"--> Service[dashboard_service.py]
    Service --"① 自选股"--> F1[watchlist_service<br/>F1]
    Service --"② 行情"--> F2[cache_service<br/>F2]
    Service --"③ 预警"--> F3[alert_service<br/>F3]
    Service --"④ 简报"--> F3b[quote_scheduler<br/>F3]
    Service --"⑤ 推送历史"--> F4[push_service<br/>F4]
    Service --"⑥ 通道状态"--> F4b[push_channel<br/>F4]
    F1 --> Data1[(SQLite<br/>stocks)]
    F2 --> Data2[(SQLite<br/>cache)]
    F3 --> Data3[(SQLite<br/>alerts)]
    F3b --> Data4[(SQLite<br/>briefing)]
    F4 --> Data5[(SQLite<br/>push_logs)]
    F4b --> Data6[(SQLite<br/>push_channels)]
    Service --"聚合"--> Model[DashboardViewResponse]
    Model --"传入"--> Template[Jinja2<br/>dashboard.html]
    Template --"渲染"--> HTML[完整 HTML]
    HTML --"返回"--> Browser
```

### 行情自动刷新

```mermaid
graph LR
    JS[dashboard.js<br/>60秒定时器] --"HTMX GET"--> Router2[dashboard.py
/market_data]
    Router2 --"调用"--> Service2[dashboard_service
get_market_data]
    Service2 --"行情"--> Cache[cache_service]
    Service2 --"预警"--> AlertSvc[alert_service]
    Cache --> CacheDB[(SQLite<br/>cache)]
    AlertSvc --> AlertDB[(SQLite<br/>alerts)]
    Service2 --"返回"--> Partial[HTML Partial<br/>market_index + stock_cards]
    Partial --"HTMX swap"--> Browser2[浏览器<br/>局部更新]
```

### 数据源异常降级

```mermaid
graph LR
    Service3[dashboard_service] --"请求行情"--> DS[data_source_facade]
    DS --"不可用"--> Cache3[cache_service<br/>读取缓存]
    Cache3 --"有缓存"--> Cached[返回缓存数据<br/>+ is_cached=true]
    Cache3 --"无缓存"--> Empty[返回占位符<br/>+ is_empty=true]
    Cached --> Router3[dashboard.py]
    Empty --> Router3
    Router3 --"有缓存"--> Template3[模板渲染<br/>+ 黄色延迟提示条]
    Router3 --"无缓存"--> Template4[模板渲染<br/>+ 空值占位符]
```

---

## Dependency List

### 运行时依赖（新增）

| 依赖 | 版本 | 用途 |
|------|------|------|
| Jinja2 | 3.1+ | 模板渲染（Dashboard 页面） |
| python-multipart | 0.0.9+ | FastAPI 表单解析 |
| cryptography | 42.0+ | 敏感配置字段加密（Fernet 对称加密） |

### 运行时依赖（复用 F1-F4）

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 运行时语言 |
| FastAPI | 0.110+ | Web 框架（路由、请求处理） |
| SQLAlchemy | 2.0+ | ORM（读取已有表） |
| Pydantic | 2.0+ | 响应模型校验 |
| Uvicorn | 0.27+ | ASGI 服务器 |
| APScheduler | 3.10+ | 定时任务状态读取 |
| python-dotenv | 1.0+ | 环境变量加载 |
| HTMX | 1.9+ | 前端局部刷新（CDN 引入） |
| Tailwind CSS | 3.4+ | 响应式样式（CDN 引入） |

### 开发/测试依赖（复用 F1）

| 依赖 | 版本 | 用途 |
|------|------|------|
| pytest | 8.0+ | 测试框架 |
| pytest-asyncio | 0.23+ | 异步测试支持 |
| httpx | 0.27+ | HTTP 测试客户端 |
| pytest-mock | 3.14+ | mock 工具 |
| beautifulsoup4 | 4.12+ | 测试 HTML 解析 |

---

## Integration Points

### 与现有/已规划系统的集成

| 本 feature 新建模块 | 被复用方 | 复用方式 |
|--------------------|---------|---------|
| `services/dashboard_service.py` | F1 自选股管理 | 调用 `watchlist_service.get_watchlists()` 获取自选股列表和分组 |
| `services/dashboard_service.py` | F2 数据源容灾 | 调用 `cache_service.get_latest_quotes()` 获取行情缓存；调用 `data_source_facade.get_health()` 获取数据源健康状态 |
| `services/dashboard_service.py` | F3 实时行情/预警 | 调用 `quote_service.get_market_indices()` 获取大盘指数；调用 `alert_service.get_today_alerts()` 获取今日预警；读取 quote_scheduler 简报状态 |
| `services/dashboard_service.py` | F4 推送通知 | 调用 `push_service.get_recent_logs()` 获取推送历史；调用 `push_service.get_channel_status()` 获取通道健康状态 |
| `services/settings_service.py` | F4/F5/F6 | 提供统一的配置读写接口（`get_setting()`, `set_setting()`, `get_all_by_category()`），敏感字段自动加解密 |
| `routers/dashboard.py` | F5 Dashboard | 本模块，注册路由到 FastAPI app |
| `routers/settings.py` | F5 Dashboard | 设置页路由，注册到 FastAPI app |

### 复用已有模块

| 复用模块 | 本 feature 使用场景 |
|---------|-------------------|
| `services/watchlist_service.py` (F1) | 获取用户自选股列表和分组 |
| `services/cache_service.py` (F2) | 读取最新行情缓存数据 |
| `services/data_source_facade.py` (F2) | 检测数据源是否可用 |
| `services/quote_service.py` (F3) | 获取大盘指数（上证/深证/创业） |
| `services/alert_service.py` (F3) | 获取今日已触发预警记录 |
| `services/push_service.py` (F4) | 获取最近推送历史和通道状态 |
| `core/quote_scheduler.py` (F3) | 读取今日简报生成状态 |
| `models/push_log.py` (F4) | 查询推送日志 |
| `models/push_channel.py` (F4) | 查询通道健康状态 |
| `services/settings_service.py` (本模块新建) | 读写用户配置（推送通道、数据源、偏好），敏感字段加密 |

---

## Risk Register

| ID | 风险描述 | 严重度 | 概率 | 缓解方案 |
|:---|:---|:------:|:----:|:---|
| R-PLAN-01 | 聚合多个上游服务导致页面加载缓慢（串行调用） | 高 | 中 | ① 使用 `asyncio.gather()` 并行调用独立的上游服务；② 对不经常变化的数据（分组、通道状态）做短时内存缓存；③ 设置各上游调用超时（2 秒），超时返回降级数据 |
| R-PLAN-02 | HTMX 局部刷新与全局状态不一致 | 中 | 中 | ① 每个刷新请求返回完整的 Partial HTML（含当前状态标记）；② 使用 HTMX `hx-swap-oob` 更新多个独立区域；③ 服务端状态变更时推送 `HX-Trigger` 事件 |
| R-PLAN-03 | 迷你趋势图 SVG 渲染性能差（50 只股票 × 240 个数据点） | 中 | 低 | ① 后端只返回趋势图必需的简化数据（开盘/最高/最低/收盘 + 6 个关键时点）；② 使用纯 SVG path 渲染，不做动画；③ 自选股超过 20 只时只渲染前 20 只趋势图 |
| R-PLAN-04 | 移动端自适应 CSS 覆盖不完整，部分元素溢出 | 低 | 中 | ① 使用 Tailwind 响应式前缀（md:、lg:）系统化处理；② 测试矩阵覆盖 320px/375px/414px/768px 四种宽度；③ 大盘指数区域在移动端允许横向滚动 |
| R-PLAN-05 | 上游模块（F1-F4）未就绪导致 Dashboard 无法开发 | 高 | 低 | ① Dashboard 开发使用 mock 服务层；② 定义 DashboardService 接口契约，上游只需满足接口即可集成；③ 并行开发，接口先行 |
| R-PLAN-06 | 定时刷新导致服务器负载过高 | 低 | 低 | ① 刷新只返回变化的数据（HTMX 局部替换）；② 行情数据走缓存不直接查数据源；③ 刷新接口返回 ETag，无变化返回 304 |

---

## Design Decisions

### DD-001: Dashboard 采用服务端渲染（SSR）而非 SPA

**决策**: Dashboard 使用 Jinja2 模板 + HTMX 实现服务器端渲染，不做 React/Vue SPA。

**理由**:
- 系统架构基线已选定 HTMX + Jinja2，保持一致性
- Dashboard 是信息展示页，交互以读取为主，SSR 加载更快、SEO 友好
- SPA 需要额外构建步骤（npm/bundler），增加部署复杂度
- HTMX 局部刷新足以满足行情更新需求

**反决策**: React/Vue SPA 能提供更丰富的客户端交互，但 MVP 阶段收益不足以抵消复杂度。

### DD-002: 迷你趋势图采用 SVG 内联而非图表库

**决策**: 自选股卡片的迷你趋势图使用 SVG `<path>` 内联渲染，不引入 Chart.js/ECharts。

**理由**:
- 避免引入额外的 JS/CSS 资源，降低首屏加载时间
- 趋势图只需展示当日走势轮廓，SVG path 足够表达
- 后端只需返回一组价格点，前端 SVG 是静态渲染，无运行时开销
- 移动端性能和包大小更可控

**反决策**: 图表库功能更丰富（tooltip、缩放），但 Dashboard 迷你图不需要交互。

### DD-003: Dashboard 数据聚合使用并行异步调用

**决策**: `dashboard_service.py` 使用 `asyncio.gather()` 并行获取自选股、行情、预警、简报、推送历史等数据。

**理由**:
- 各上游数据之间无依赖关系，串行调用会显著增加页面加载时间
- 并行调用将加载时间从 `sum(各服务耗时)` 降低到 `max(各服务耗时)`
- FastAPI 原生支持 async，实现成本低
- 单个服务超时不会阻塞其他数据返回

**反决策**: 串行调用实现简单，但 3-5 个上游服务各 200ms 就会累积到 1 秒以上。

### DD-004: 行情刷新采用服务端渲染 Partial 而非 JSON API

**决策**: 60 秒定时刷新通过 HTMX 请求返回 HTML Partial（大盘指数 + 自选股卡片），而非 JSON 数据。

**理由**:
- HTMX 设计哲学：HTML 超媒体作为应用状态引擎
- 服务端渲染 Partial 比 JSON + 客户端模板渲染更简单，前后端只用一种模板语言（Jinja2）
- 无需维护两套渲染逻辑（SSR 初始加载 + CSR 刷新）
- 失败降级时服务端可以直接在 Partial 中嵌入错误提示 HTML

**反决策**: JSON API 更通用（便于未来移动端 App 复用），但 MVP 阶段无此需求。

### DD-005: 用户配置由 settings_service 统一持久化

**决策**: Dashboard 设置页（/settings）的后端通过独立的 `settings_service.py` 管理所有用户级配置。配置数据持久化到数据库 `app_settings` 表（key-value 结构），敏感字段（app_secret、Telegram Bot Token）使用 Fernet 对称加密存储。加密密钥通过环境变量 `SETTINGS_ENCRYPTION_KEY` 注入。

**理由**:
- PRD 明确要求配置加密存储，满足安全合规
- 用户通过 UI 修改配置后需要持久化，容器化部署中 `.env` 文件不可写
- `app_settings` 表的 key-value 结构灵活，新增配置项无需修改表结构
- 各 feature（F4 推送、F5 Dashboard、F6 设置页）统一通过 `settings_service` 读写配置，避免重复实现加密逻辑
- 系统级配置（数据库连接、日志级别）仍保留在 `config.py` / `.env`，与用户级配置职责分离

**反决策**: 配置直接写入 `.env` 或本地 JSON 文件，会导致敏感信息明文存储，且容器重启后配置丢失。

---

## Next Step

Plan is ready for `/speckit.tasks` to generate the task breakdown.
