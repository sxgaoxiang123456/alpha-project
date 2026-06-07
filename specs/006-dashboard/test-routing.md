# 006-dashboard 收尾测试路由报告

> **边界声明**：本报告只做判类与路由；具体工具由对应类别 skill 按栈实例化，CI 闸和护栏化 agent 才负责验证。

---

## 1. 本 feature 判定属于哪一类

**主类：局部前后端** + **次类：完整功能链路**

**判类依据**：
- **任务标签**：23 个任务中 `[BE]` 占 12 个（Schema、Service、路由、设置服务）、`[FE]` 占 12 个（模板、CSS、JS 轮询）、`[INT]` 占 4 个（测试验证），前后端在同个 feature 内均有实质性改动。
- **依赖图**：`dashboard_service.py` 聚合 F1(自选股)->F2(行情缓存)->F3(预警/简报)->F4(推送历史/通道状态)，本 feature 是数据展示层，前端模板与后端聚合服务之间存在**模板渲染契约**（Pydantic -> dict -> Jinja2 -> HTML Partial）。
- **契约声明**：`DashboardViewResponse` Pydantic 模型是前后端之间的显式契约；`GET /` 和 `GET /market_data` 是两个接口契约点。

---

## 2. 路由到哪个类别 skill

| 判定维度 | 路由去向 | 状态 |
|---|---|---|
| **局部前后端**（主类） | -> `fullstack-slice-testing` skill | 执行器已建 |
| **完整功能链路**（次类） | -> `full-chain-testing` skill | 执行器已建 |
| **单后端子集**（Schema/Service 层） | -> `backend-testing` skill | 执行器已建 |
| **单前端子集**（模板/CSS/JS 层） | -> `frontend-testing` skill | 执行器已建 |

**为什么**：本 feature 同时触及前后端且接缝在 feature 内部，先走 `fullstack-slice-testing` 起真栈对账；但它又首次贯通了浏览器->F1->F2->F3->F4 的跨 feature 旅程，必须同步走 `full-chain-testing` 挖通路、设安全网。

---

## 3. 是否补全了某条完整功能链路

**是** -- 本 feature 补全了 MVP 系统最核心的端到端用户旅程：

```
用户浏览器打开 Dashboard
    -> GET / (dashboard.py)
    -> DashboardService.build_dashboard_view()
        -> asyncio.gather 并行调用 F1 watchlist_service（自选股）
        -> F2 cache_service / data_source_facade（行情缓存 + 健康检测）
        -> F3 quote_service / alert_service（大盘指数 + 今日预警）
        -> F3 quote_scheduler（简报生成状态）
        -> F4 push_service（推送历史 + 通道状态）
    -> DashboardViewResponse Pydantic 聚合
    -> Jinja2 模板渲染 (dashboard.html + 8 个组件模板)
    -> 浏览器展示完整页面
    -> dashboard.js 60 秒轮询 /market_data -> Partial HTML 局部刷新
```

这是 MVP 中首次将 F1->F2->F3->F4 串联成用户可见的完整旅程。**路由 -> `full-chain-testing`**，从这条刚贯通的链路起步做通路挖掘。

---

## 4. 逐类待补清单（覆盖状态 + 路由去向）

### 4.1 单后端子集

| 缺口维度 | 覆盖状态 | TDD/现有测试证据 | 路由去向 | 现成/需自建 |
|---|---|---|---|---|
| 真库数据层 / 迁移 / 约束 | **已被 backend-testing 闭环补测** | `test_dashboard_service.py` 用 `sqlite:///:memory:` 内存库；`test_dashboard.py` 虽用临时文件库但 `_get_dashboard_service` 被 monkeypatch 成 mock，未触发真库写入路径。**已补**：`tests/integration/test_database_real.py` 8 个回归测试覆盖文件级 SQLite 的建表、约束、事务回滚、迁移往返、SettingsService 文件库往返、updated_at 自动更新、目录创建。见 [补测报告](test-routing-closure.md) | -> `backend-testing` | 现成 |
| 并发 / 限频 / 原子性 | 已被 superpowers/spec-kit 覆盖（跳过） | 无多用户/共享资源/限频场景；MVP 单用户系统 | -- | -- |
| 韧性 / 降级 / 超时 | 已被 superpowers/spec-kit 覆盖（跳过） | `test_dashboard_service.py::test_timeout_degradation` 已覆盖单服务超时降级 | -- | -- |
| 越权 BOLA/BFLA | 已被 superpowers/spec-kit 覆盖（跳过） | MVP 单用户无认证，无对象隔离需求 | -- | -- |

### 4.2 单前端子集

| 缺口维度 | 覆盖状态 | TDD/现有测试证据 | 路由去向 | 现成/需自建 |
|---|---|---|---|---|
| **L0/L1 测试地基** | **已被 frontend-testing 闭环补测** | 前端 JS/CSS 无独立测试运行器。**已补**：安装 `pytest-playwright` + Chromium 浏览器，在 `tests/e2e/` 建立 L0/L1 地基；trivial 测试验证浏览器+服务协同跑通。见 [补测报告](test-routing-closure.md) | -> `frontend-testing` | 需自建（接工具+配置） |
| L2 视觉回归 | **已被 frontend-testing 闭环补测** | T23 标记完成但未找到实际实现。**已补**：`tests/e2e/test_frontend_structural.py::TestVisualRegression` 生成 Desktop (1280x800) 和 Mobile (375x812) 基线截图，存放于 `tests/e2e/visual_baselines/`。基线裁决人审节点：首次运行已建立基线，后续 PR diff 需人确认。见 [补测报告](test-routing-closure.md) | -> `frontend-testing` | 现成（接 Playwright/Screenshot） |
| L3 可访问性 a11y | **已被 frontend-testing 闭环补测** | 零覆盖。**已补**：axe-core CDN 注入扫描 Dashboard 首页，断言无 critical/serious 违规；img alt 检查；交互元素可访问名称检查。见 [补测报告](test-routing-closure.md) | -> `frontend-testing` | 现成（接 axe） |
| L4 跨浏览器 + 响应式 | **已被 frontend-testing 闭环补测** | T22 `test_responsive.py` 有 viewport 断言但无浏览器引擎。**已补**：Playwright 真浏览器覆盖 375px/768px/1280px 三视口；断言无横向滚动条、核心信息可见、移动端 sidebar 隐藏、desktop 卡片横向排列。Chromium 内核已覆盖；多浏览器内核（Firefox/WebKit）待扩展。见 [补测报告](test-routing-closure.md) | -> `frontend-testing` | 现成（接 Playwright 多浏览器） |
| L6 前后端契约 mock | **已被 frontend-testing 闭环补测** | `dashboard.js` 直接 `fetch('/market_data')` 调真后端，无消费者端 mock。**已补**：Playwright `page.route` 拦截 `/market_data` 返回受控 Partial HTML，验证前端正确渲染 mock 数据；拦截返回 500 验证前端不空白；拦截返回降级标记验证降级提示。见 [补测报告](test-routing-closure.md) | -> `frontend-testing` | 现成（接 MSW） |

### 4.3 局部前后端（主类）

| 缺口维度 | 覆盖状态 | TDD/现有测试证据 | 路由去向 | 现成/需自建 |
|---|---|---|---|---|
| **环境编排**（两侧+依赖真实同起） | **已被 fullstack-slice-testing 闭环补测** | `test_dashboard.py` 全部 monkeypatch `_get_dashboard_service` 为 mock，未与真 DashboardService、真上游服务、真数据库同时跑通。**已补**：`tests/e2e/test_fullstack_slice.py` 起真栈（临时 SQLite + seed 真实数据 + 启动 uvicorn + 健康检查），真浏览器访问真后端，零 mock。见 [补测报告](test-routing-closure.md) | -> `fullstack-slice-testing` | 需自建（docker-compose / testcontainers / 进程内组装） |
| 契约真实性（mock vs 真提供者对账） | **已被 fullstack-slice-testing 闭环补测** | 前端 JS 消费 `/market_data` 返回 HTML Partial，现有测试未验证 mock 与真后端是否一致。**已补**：`tests/e2e/test_fullstack_slice.py::TestContractReality` 验证大盘指数、自选股、简报、预警、推送历史均来自真实后端查询（非 mock），真实渲染到 HTML。外部数据源超时降级的真实行为也被验证。见 [补测报告](test-routing-closure.md) | -> `fullstack-slice-testing` | 需自建 |
| 接缝粘合（序列化 / 错误->UI 映射） | **已被 fullstack-slice-testing 闭环补测** | 降级提示在集成测试中有断言，但真栈下未验证。**已补**：`tests/e2e/test_fullstack_slice.py::TestSeamBonding` 验证 (a) 真栈下 HTTP 200 不 500；(b) 外部数据源超时时 DashboardService 降级触发，页面不崩溃且有降级提示/空占位；(c) Pydantic datetime 经 `mode="json"` -> Jinja2 后无大面积裸 ISO 格式暴露。见 [补测报告](test-routing-closure.md) | -> `fullstack-slice-testing` | 需自建 |
| 真实时序 / 实时 | 已被 superpowers/spec-kit 覆盖（跳过） | 60 秒轮询是前端 `setInterval`，非流式/SSE/WebSocket；无实时推送场景 | -- | -- |

### 4.4 完整功能链路（次类）

| 缺口维度 | 覆盖状态 | TDD/现有测试证据 | 路由去向 | 现成/需自建 |
|---|---|---|---|---|
| **通路挖掘** | **已被 full-chain-testing 闭环补测** | `test_full_chain.py` 头部含完整 path inventory，标注三源证据（源A `dashboard.py:30` / 源B test_fullstack_slice 已验证 / 源C `spec.md` US-1~US-5）。挖出 3 条跨 feature 旅程。见 [补测报告](test-routing-closure.md) | -> `full-chain-testing` | 需自建 |
| **关键性分级 + 选少** | **已被 full-chain-testing 闭环补测** | US-1(P1) / US-2(P1) / US-5(P2) 已分级；旅程为 P1（非 P0），发布门告警级。安全网少而精，仅 3 条旅程织成 E2E。见 [补测报告](test-routing-closure.md) | -> `full-chain-testing` | 需自建 |
| **全系统编排 + 外部边界 stub** | **已被 full-chain-testing 闭环补测** | `full_chain_stack` fixture 一键起停：临时 SQLite + seed F1-F4 全量数据 + uvicorn + 健康检查。只 stub 外部第三方（AkShare/BaoStock/飞书/Telegram）。见 [补测报告](test-routing-closure.md) | -> `full-chain-testing` | 需自建 |
| 异步 / 时间 / 跨通道贯穿 | **已被 full-chain-testing 闭环补测** | `test_quote_scheduler_generates_briefing_push_log` 手动触发 `send_briefing_if_trading_day()`（编排驱动，不等 cron），验证 PushLog 记录生成。命中异步/时间维度。见 [补测报告](test-routing-closure.md) | -> `full-chain-testing` | 需自建 |
| **journey 级可追溯 + 安全网定位** | **已被 full-chain-testing 闭环补测** | `TestJourneyUS1_ViewDashboard` 以"用户步骤1~5"组织断言（打开→大盘→自选股→简报→预警），挂 TR-006-FC-002~006。见 [补测报告](test-routing-closure.md) | -> `full-chain-testing` | 需自建 |

### 4.5 跨模块契约（可增类）

| 缺口维度 | 覆盖状态 | TDD/现有测试证据 | 路由去向 | 现成/需自建 |
|---|---|---|---|---|
| `settings_service.py` 横向模块契约 | 结构性缺口 | `settings_service.py` 被 F4/F5/F6 复用，提供 `get_setting()` / `set_setting()` / `get_all_by_category()` 接口；本 feature 改动了该契约（新建 app_settings 表 + 加密逻辑），但**未验证下游消费者（F4 推送通知等）是否仍兼容** | -> 占位待建（跨模块契约类暂无执行器） | 需自建 |

---

## 5. 状态标注汇总

| 缺口项 | 状态 | 路由去向 | 现成/需自建 |
|---|---|---|---|
| 真库数据层验证 | **已被 backend-testing 闭环补测** | `backend-testing` | 现成 |
| 前端 L0/L1 测试地基 | **已被 frontend-testing 闭环补测** | `frontend-testing` | 需自建 |
| L2 视觉回归 | **已被 frontend-testing 闭环补测** | `frontend-testing` | 现成 |
| L3 可访问性 a11y | **已被 frontend-testing 闭环补测** | `frontend-testing` | 现成 |
| L4 跨浏览器 + 响应式 | **已被 frontend-testing 闭环补测** | `frontend-testing` | 现成 |
| L6 前后端契约 mock | **已被 frontend-testing 闭环补测** | `frontend-testing` | 现成 |
| 局部前后端 环境编排 | **已被 fullstack-slice-testing 闭环补测** | `fullstack-slice-testing` | 需自建 |
| 局部前后端 契约真实性 | **已被 fullstack-slice-testing 闭环补测** | `fullstack-slice-testing` | 需自建 |
| 局部前后端 接缝粘合 | **已被 fullstack-slice-testing 闭环补测** | `fullstack-slice-testing` | 需自建 |
| 完整链路 通路挖掘 | **已被 full-chain-testing 闭环补测** | `full-chain-testing` | 需自建 |
| 完整链路 关键性分级 | **已被 full-chain-testing 闭环补测** | `full-chain-testing` | 需自建 |
| 完整链路 全系统编排 | **已被 full-chain-testing 闭环补测** | `full-chain-testing` | 需自建 |
| 完整链路 journey 可追溯 | **已被 full-chain-testing 闭环补测** | `full-chain-testing` | 需自建 |
| 跨模块契约回归 | 结构性缺口 | 占位待建 | 需自建 |
| T23 视觉回归实际是否落地 | 需人工决策 | `frontend-testing` | -- |
| L4 跨浏览器（仅响应式有） | 需人工决策 | `frontend-testing` | 现成 |
| 局部前后端 接缝粘合（真栈下） | 需人工决策 | `fullstack-slice-testing` | 需自建 |
| 完整链路 异步/时间（仅 quote_scheduler） | **已被 full-chain-testing 闭环补测** | `full-chain-testing` | 需自建 |

---

## 6. 收尾状态汇总

| 执行器 | 状态 | 产出 |
|---|---|---|
| `backend-testing` | **已闭环** | `tests/integration/test_database_real.py`（8 个回归） |
| `frontend-testing` | **已闭环** | `tests/e2e/test_frontend_structural.py`（17 个回归 + 2 张基线截图） |
| `fullstack-slice-testing` | **已闭环** | `tests/e2e/test_fullstack_slice.py`（10 个回归） |
| `full-chain-testing` | **已闭环** | `tests/e2e/test_full_chain.py`（13 个回归 + 通路清单） |

**剩余待决策项**：
- 跨模块契约（`settings_service.py` 横向模块契约）— 结构性缺口，暂无执行器，占位待建
- 13 个已有 flaky 测试 — 非本 feature 引入，需单独排期修复
