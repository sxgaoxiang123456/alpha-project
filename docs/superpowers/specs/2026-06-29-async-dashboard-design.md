# Dashboard 行情异步解耦设计

## 1. 背景与目标

当前 Dashboard 页面在 `/` 和 `/market_data` 请求路径上可能同步调用 AkShare/BaoStock 数据源，导致：

- 页面切换或首次加载时响应慢（BaoStock 备源可达数秒）。
- 数据源超时/降级时用户体验受损。

本设计目标：

- **Dashboard 渲染只读本地缓存/数据库**，请求路径永不触发外部数据源同步抓取。
- **行情抓取由后端后台进程负责**（现有 3 分钟定时任务 + 新增按需触发）。
- **前端通过轮询 + 首次触发后台刷新**获取最新数据，实现高耗时数据获取与快速页面渲染解耦。

## 2. 设计原则

- **最小改动**：复用现有 `QuoteService`、`MarketIndexService`、`CacheService`、`RedisCache` 和 `QuoteScheduler`。
- **向后兼容**：其他页面（自选股管理、预警规则）保持现有行为不变。
- **不引入新数据源**：继续使用 Redis/SQLite 缓存，不新增持久化表。
- **单用户 MVP**：不考虑多用户并发隔离；仅通过简单并发控制避免重复后台刷新。

## 3. 方案选型

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|:---|:---|:---|:---|:---|
| A. 复用现有缓存 | 新增只读缓存方法，新增 `/market_data/refresh` 触发后台刷新 | 改动最小，与现有架构一致 | 缓存键语义不够“数据库表”直观 | **采用** |
| B. 新增最新行情表 | 新增 `latest_quote` / `latest_market_index` 表 | 语义清晰，前端“监听数据库”更直接 | 模型/迁移增多，与历史表/缓存并存 | 不适用 |
| C. SSE 主动推送 | 在 A 的基础上增加 SSE 流 | 实时性最好 | 长连接管理复杂，MVP 过重 | 不适用 |

## 4. 架构与数据流

### 4.1 组件职责

- `QuoteService` / `MarketIndexService`
  - 新增**只读缓存方法**：`get_cached_watchlist_quotes()` / `get_cached_indices()`。
  - 优先读 Redis，Redis 不可用时读 SQLite `CacheService`，无缓存则返回 `None`。
  - 保留原有 `get_watchlist_quotes()` / `get_indices()` 供后台 scheduler 抓取时调用。
- `DashboardService`
  - `_get_market_indices()` / `_get_watchlist_data()` 改为调用只读缓存方法。
  - 无缓存时降级返回空列表或基础自选股列表（不触发外部抓取）。
- `QuoteScheduler`
  - 保留 3 分钟定时刷新。
  - 新增/暴露非阻塞触发入口，供 `/market_data/refresh` 调用。
- `routers/dashboard.py`
  - `GET /market_data`：只读缓存，永不调用外部数据源。
  - `POST /market_data/refresh`：触发一次后台刷新，立即返回 `202 Accepted`。
- 前端 `dashboard.js`
  - 初始加载后发送一次 `POST /market_data/refresh`（fire-and-forget）。
  - 继续 60s 轮询 `GET /market_data`。
  - 手动“同步”按钮同样调用 `POST /market_data/refresh`。

### 4.2 数据流

```
首次打开 Dashboard：
  浏览器 GET /           → DashboardService 只读缓存 → 返回页面（可能为空/骨架屏）
  浏览器 POST /market_data/refresh
       → 后端后台线程执行 QuoteScheduler.refresh_if_trading_day()
       → 抓取数据写入 Redis + SQLite Cache
  浏览器 60s 轮询 GET /market_data
       → DashboardService 只读缓存 → 返回最新 HTML partial

定时刷新：
  APScheduler (3min) → QuoteScheduler.refresh_if_trading_day()
       → 抓取数据写入 Redis + SQLite Cache
```

## 5. 接口变更

### 5.1 `GET /market_data`

- 行为变更：由“缓存缺失时同步抓取”改为“只读缓存，永不抓取”。
- 响应：与当前一致的 HTML partial；`etag` 机制继续保留。
- 降级：无缓存时返回空市场指数 / 基础自选股列表，并标记 `degraded=true`。

### 5.2 `POST /market_data/refresh`

- 功能：非阻塞触发一次行情刷新。
- 成功：`202 Accepted`，响应体可包含 `{"status":"accepted"}`。
- 并发控制：若上一次刷新仍在运行，返回 `429 Too Many Requests` 或 `202 Accepted`（忽略本次）。
- 非交易日：后端自动跳过，仍返回 `202`。

## 6. 前端改动

### 6.1 `frontend/public/js/dashboard.js`

- 在 `startPolling()` 之前发送一次 `POST /market_data/refresh`。
- 保留 60s 轮询 `/market_data` 和 `If-None-Match` / `etag` 机制。
- 保留降级检测与暂停/恢复逻辑。
- 为手动同步按钮绑定 `POST /market_data/refresh`（若按钮尚未绑定）。

### 6.2 首次无缓存展示

- 若服务端无缓存，Dashboard 模板继续渲染 `components/skeleton_screen.html` 或 `components/onboarding.html`。
- 可在骨架屏区域增加提示文案“数据准备中，请稍候…”。

## 7. 错误处理与降级

| 场景 | 行为 |
|:---|:---|
| 后台刷新失败 | 仅影响缓存新鲜度；页面仍返回已有缓存或空数据；下次定时任务/手动刷新重试。 |
| Redis 不可用 | 只读缓存方法回退到 SQLite `CacheService`；若 SQLite 也无数据，返回空/基础列表。 |
| 首次无缓存且后台刷新未完成 | 展示骨架屏/“数据准备中”，60s 后轮询自动更新。 |
| 重复触发 refresh | 通过 `QuoteScheduler._quote_refresh_done` 判断，避免并发抓取。 |

## 8. 测试策略

### 8.1 单元测试

- `test_quote_service_cached.py`
  - Redis 命中时返回缓存数据。
  - Redis 缺失、SQLite 命中时返回 SQLite 数据。
  - 两者皆缺失时返回 `None`。
- `test_market_index_cached.py`
  - 同上，覆盖 `get_cached_indices()`。

### 8.2 集成测试

- `test_dashboard_cached_only.py`
  - `GET /market_data` 在外部数据源被 mock 为异常/慢时仍快速返回（不触发抓取）。
  - `POST /market_data/refresh` 返回 202，并触发 scheduler 任务。
  - 并发调用 `POST /market_data/refresh` 不会导致重复抓取。

### 8.3 E2E / 真浏览器（可选）

- 打开 Dashboard，验证首次加载无长时间白屏。
- 验证后台刷新完成后，轮询自动更新市场数据。

## 9. 影响范围与排除项

- **影响范围**：仅 Dashboard 页面（`/` 和 `/market_data`、`POST /market_data/refresh`）。
- **排除项**：
  - 自选股管理页、预警规则页保持现有同步/手动刷新行为。
  - 不新增数据库表。
  - 不引入 WebSocket/SSE。
  - 不改变 3 分钟定时任务频率。

## 10. 待实现清单（Plan 输入）

1. `QuoteService.get_cached_watchlist_quotes()` / `MarketIndexService.get_cached_indices()` 实现。
2. `DashboardService` 改为调用只读缓存方法。
3. `POST /market_data/refresh` 路由实现（含并发控制）。
4. `GET /market_data` 确认只读缓存行为。
5. 前端 `dashboard.js` 首次加载触发 refresh、手动同步按钮绑定。
6. 新增/更新单元与集成测试。
7. 端到端验证：首次打开、后台刷新、轮询更新。
