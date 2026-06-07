# Tasks: 基础 Dashboard

**Input**: Design documents from `specs/006-dashboard/`
**Prerequisites**: plan.md, spec.md
**Frontend Reference**: `design-reference/DESIGN.md`, `design-reference/stitch-export/dashboard_a_share_ai_monitor/code.html`

---

## Phase 0: 配置管理基础设施（横向模块，被 F4/F5/F6 复用）

**Purpose**: 创建统一的配置管理服务，支持用户级配置的持久化和敏感字段加密

- [x] **T0a [BE]** 创建 AppSetting 数据模型：`backend/app/models/app_setting.py`（key, value, category, is_encrypted, updated_at，含 category 索引）
  - [依赖: F1 基础设施就绪] [出参验证: `AppSetting.__table__.create()` 成功，表含 5 字段 + category 索引]

- [x] **T0b [BE]** 创建 Setting Pydantic schemas：`backend/app/schemas/settings.py`（SettingRequest, SettingResponse, SettingCategory）
  - [依赖: T0a] [出参验证: 无效 category 触发 pydantic.ValidationError]

- [x] **T0c [BE] [P]** 创建 SettingsService：`backend/app/services/settings_service.py`（`get_setting(key)`, `set_setting(key, value, encrypt=False)`, `get_all_by_category(category)`，敏感字段使用 Fernet 加密）
  - [依赖: T0b] [出参验证: 单元测试 — 写入/读取普通字段和加密字段 → 验证明文存储和加密解密正确]

---

## Phase 1: Schema 与接口骨架

**Purpose**: 定义 Dashboard 数据模型和服务接口

- [x] **T1 [BE]** 创建 Dashboard Pydantic schemas：`backend/app/schemas/dashboard.py`（DashboardViewResponse, MarketSnapshot, StockCardData, BriefingData, AlertSummary, PushHistoryItem, ChannelStatusItem）
  - [FR-001~FR-010] [依赖: F1/F2/F3/F4 基础设施就绪, T0b] [出参验证: 无效字段触发 pydantic.ValidationError]

- [x] **T2 [BE]** 创建 DashboardService 接口骨架：`backend/app/services/dashboard_service.py`（类定义 + 聚合方法签名 + 上游服务依赖注入接口）
  - [FR-001~FR-010] [依赖: T1] [出参验证: `DashboardService` 类可实例化，方法签名完整]

---

## Phase 2: 核心聚合服务（US-1）

**Purpose**: 实现数据聚合和页面路由

- [x] **T3 [BE]** 实现 DashboardService 数据聚合：`backend/app/services/dashboard_service.py`（asyncio.gather 并行调用 5 个上游服务 → 统一响应模型 → 单个服务超时降级）
  - [FR-001~FR-005, FR-009, FR-010] [依赖: T2, F1/F2/F3/F4 服务就绪] [出参验证: 单元测试 — mock 5 个上游服务 → 验证并行调用、超时降级、聚合结果完整]

- [x] **T4 [BE]** 实现 Dashboard 首页路由：`backend/app/routers/dashboard.py`（GET / → 聚合服务 → 渲染 dashboard.html；GET /market_data → 返回行情 Partial HTML）
  - [FR-001, FR-003, FR-006] [依赖: T3] [出参验证: 集成测试 — mock 数据 → 验证页面 HTTP 200、含大盘/自选股/简报模块]

---

## Phase 3: 首页模板组件（US-1，Group A [FE] 并行）

**Purpose**: 渲染低密度首页的各模块

- [x] **T5 [FE] [P]** 创建基础布局模板：`frontend/src/templates/base.html`（HTML5 骨架 + Tailwind CDN + Google Fonts + Material Symbols）+ `frontend/src/templates/dashboard.html`（首页主布局，12 列网格，含各组件插槽）
  - [DESIGN.md §Layout & Spacing, §Colors, §Typography] [参考 HTML: `dashboard_a_share_ai_monitor/code.html` L1-106（base 配置）, L171（main grid）] [Tailwind: `darkMode: "class"`, `max-w-[1280px] mx-auto`, `grid grid-cols-12 gap-container-gap`, custom colors/fonts/spacing] [依赖: T4] [出参验证: 浏览器访问 `/` 返回完整 HTML，含 Tailwind 和字体加载]

- [x] **T6 [FE] [P]** 创建 SideNavBar 组件：`frontend/src/templates/components/side_nav.html`（Logo + 导航菜单 + AI 简报按钮）
  - [DESIGN.md §Layout & Spacing（导航栏）, §Colors（surface-container-lowest, primary-container）] [参考 HTML: `dashboard_a_share_ai_monitor/code.html` L108-144] [Tailwind: `w-64 h-screen fixed left-0`, `bg-surface-container-lowest border-r border-outline-variant`, `hidden md:flex`, nav item active `bg-surface-container-high border-r-2 border-primary-container`, AI 简报按钮 `bg-primary-container`] [依赖: T5] [出参验证: 页面含固定左侧导航栏，含 Logo、4 个菜单项和 AI 简报按钮]

- [x] **T7 [FE] [P]** 创建 TopNavBar + CommandBar 组件：`frontend/src/templates/components/top_nav.html`（顶部栏 + 搜索框 + 通知 + 用户头像）
  - [DESIGN.md §Layout & Spacing（顶部栏）, §Components / Input Forms (Command Bar)] [参考 HTML: `dashboard_a_share_ai_monitor/code.html` L146-170] [Tailwind: `bg-surface/80 backdrop-blur-md sticky z-50`, CommandBar `bg-surface-raised border-outline-variant rounded focus:border-primary focus:ring-1 focus:ring-primary`, notification dot `bg-market-up rounded-full`] [依赖: T5] [出参验证: 页面含 sticky 顶部栏，搜索框占位符为 "Search stock code, name, or natural language query..."]

- [x] **T8 [FE] [P]** 创建 MarketIndexCard 组件：`frontend/src/templates/components/market_index.html`（上证/深证/创业 → 点位 + 涨跌幅 + 涨跌额）
  - [DESIGN.md §Components / Metric Cards] [参考 HTML: `dashboard_a_share_ai_monitor/code.html` L176-207] [Tailwind: `bg-surface-base border-outline-variant rounded p-card-padding`, 标题 `font-headline-md`, 价格 `font-display-price`, 涨跌幅 badge `bg-market-up/10` / `bg-market-down/10`] [依赖: T5] [出参验证: 集成测试 — mock 大盘数据 → 验证 3 个指数正确渲染，价格使用 JetBrains Mono 字体]

- [x] **T9 [FE] [P]** 创建 WatchlistSnapshot 组件：`frontend/src/templates/components/watchlist_snapshot.html`（自选股快照表格：代码/名称/价格/涨跌幅/趋势方向）
  - [DESIGN.md §Components / Stock Data Tables] [参考 HTML: `dashboard_a_share_ai_monitor/code.html` L212-286] [Tailwind: `bg-surface-base border-outline-variant rounded`, thead `bg-surface-raised/50 font-label-caps`, 行高 `h-table-row-height`, hover `bg-surface-variant/30`, 趋势箭头 Material Symbols `trending_up`/`trending_down`/`trending_flat`] [依赖: T5] [出参验证: 集成测试 — mock 5 只自选股 → 验证表格字段完整、趋势图标正确着色]

- [x] **T10 [FE] [P]** 创建 AI Briefing Card 组件：`frontend/src/templates/components/briefing_card.html`（每日 AI 简报：insight 列表 + 查看完整按钮）
  - [DESIGN.md §Colors（primary-container glow）, §Elevation & Depth] [参考 HTML: `dashboard_a_share_ai_monitor/code.html` L307-336] [Tailwind: `bg-surface-base border-primary-container/30 rounded`, AI glow `bg-primary-container/10 blur-3xl`, insight card `bg-surface-raised border-l-4 border-l-market-up`/`border-l-market-warning`/`border-l-primary-container`, NEW badge `bg-primary-container text-on-primary-container`] [依赖: T5] [出参验证: 集成测试 — mock 简报数据 → 验证卡片渲染；无简报时显示占位态]

---

## Phase 4: 扩展状态组件（US-5，可并行）

**Purpose**: 展示推送历史、通道健康、今日预警

- [x] **T11 [FE] [P]** 创建 AlertBanner 组件：`frontend/src/templates/components/alert_banner.html`（今日触警股票列表 + 触发条件 + 预警级别图标，可折叠）
  - [DESIGN.md §Components / Alert Badges] [参考 HTML: 设计样本未直接展示，由 DESIGN.md §Alert Badges 推导] [Tailwind: Level 1 `border-primary`, Level 2 `bg-market-warning`, Level 3 `bg-market-up pulsing`, 折叠按钮 `hover:bg-surface-variant`] [依赖: T5] [出参验证: 集成测试 — mock 今日预警 → 验证横幅展示触警股票和级别图标]

- [x] **T12 [FE] [P]** 创建 PushHistory 组件：`frontend/src/templates/components/push_history.html`（消息类型/标题/时间/通道/状态列表，最近 100 条限制）
  - [DESIGN.md §Components / Stock Data Tables（列表样式参考）] [参考 HTML: 设计样本未直接展示] [Tailwind: `bg-surface-base border-outline-variant rounded`, 状态标签 `bg-market-up/10`/`bg-market-down/10`, 时间戳 `font-data-table text-on-surface-variant`] [依赖: T5] [出参验证: 集成测试 — mock 10 条推送记录 → 验证列表正确渲染]

- [x] **T13 [FE] [P]** 创建 ChannelStatus 组件：`frontend/src/templates/components/channel_status.html`（飞书/Telegram 状态 + 限流提示 + 颜色标记：绿/黄/红）
  - [DESIGN.md §Colors（market-up / market-warning / market-down 语义色）] [参考 HTML: 设计样本未直接展示] [Tailwind: 状态圆点 `bg-market-up`/`bg-market-warning`/`bg-market-down`, 卡片 `bg-surface-base border-outline-variant rounded`] [依赖: T5] [出参验证: 集成测试 — mock 通道状态 → 验证正确颜色和提示文本]

---

## Phase 5: 引导与响应式（US-2 + US-4）

**Purpose**: 首次使用引导和移动端自适应

- [x] **T14 [FE] [P]** 创建 QuickActions + Onboarding 组件：`frontend/src/templates/components/quick_actions.html`（4 个快捷入口按钮：添加股票/设置预警/市场复盘/系统设置）+ `frontend/src/templates/components/onboarding.html`（空自选股引导卡片）
  - [DESIGN.md §Components / Metric Cards（QuickActions 按钮样式参考）] [参考 HTML: `dashboard_a_share_ai_monitor/code.html` L288-305（QuickActions）] [Tailwind: QuickActions `bg-surface-base border-outline-variant rounded p-4 hover:bg-surface-raised hover:border-primary group`, icon `group-hover:scale-110 transition-transform`; Onboarding `bg-surface-base border-outline-variant rounded`, CTA 按钮 `bg-primary-container shadow-lg`] [依赖: T5] [出参验证: 集成测试 — 空自选股 → 验证引导页展示；添股票后 → 引导消失；QuickActions 4 个按钮正常渲染]

- [x] **T15 [FE] [P]** 实现响应式样式和刷新逻辑：`frontend/public/css/dashboard.css`（移动端单列/PC 端多列布局 + Tailwind 响应式类补充）+ `frontend/public/js/dashboard.js`（60 秒 fetch 轮询 + DOM innerHTML 替换 + 数据源恢复检测 + 暂停/恢复控制）
  - [DESIGN.md §Layout & Spacing（响应式断点）] [参考 HTML: `dashboard_a_share_ai_monitor/code.html` L107 `flex`, L146 `md:ml-64`, L172 `grid grid-cols-12`, L174 `md:grid-cols-3`, L210 `lg:col-span-8`, L308 `lg:col-span-4`] [Tailwind: responsive prefixes `md:`, `lg:`, `hidden md:flex`, `col-span-12 lg:col-span-8`] [JS: `setInterval(60000, fetchMarketData)`, `response.text().then(html => container.innerHTML = html)`, `IntersectionObserver` 检测降级标记后暂停定时器] [依赖: T5] [出参验证: 浏览器开发者工具切换 375px viewport → 验证单列布局；JS 加载后 → 验证定时请求存在；数据源降级时 → 验证定时器暂停]

---

## Phase 6: 设置页与集成

**Purpose**: 设置页路由、配置读写、路由注册

- [x] **T16 [FE] [P]** 创建设置页模板：`frontend/src/templates/settings.html`（按 category 分组表单：lark / telegram / datasource / preference，敏感字段 `<input type="password">`）
  - [DESIGN.md §Components / Input Forms] [参考 HTML: `design-reference/stitch-export/settings_a_share_ai_monitor/code.html`] [Tailwind: 表单卡片 `bg-surface-base border-outline-variant rounded`, 输入框 `bg-surface-raised border-outline-variant focus:border-primary-container`, 分组标题 `font-headline-md`] [依赖: T0c, T5] [出参验证: 集成测试 — 提交飞书配置 → 验证数据库写入；读取配置 → 验证敏感字段解密正确]

- [x] **T17 [BE]** 实现设置页路由：`backend/app/routers/settings.py`（GET /settings → 渲染设置表单；POST /settings → 接收表单数据 → 调用 `settings_service.set_setting()` 持久化；按 category 分组展示配置项）
  - [依赖: T0c, T16] [出参验证: 集成测试 — 提交飞书配置 → 验证数据库写入；读取配置 → 验证敏感字段解密正确]

- [x] **T18 [BE]** 更新路由注册：更新 `backend/app/main.py`（注册 dashboard 路由、settings 路由、静态文件挂载）
  - [FR-003] [依赖: T4, T17] [出参验证: `uvicorn app.main:app` 启动后 Dashboard 和 Settings 路由均可用，静态文件可访问]

---

## Phase 7: 测试验证

**Purpose**: 全量测试覆盖

- [x] **T19 [INT] [P]** 单元测试 — DashboardService：`backend/tests/unit/test_dashboard_service.py`（mock 5 个上游服务 → 验证并行聚合、超时降级、空数据降级）
  - [FR-001~FR-005] [依赖: T3] [出参验证: pytest 全部通过]

- [x] **T20 [INT] [P]** 单元测试 — SettingsService：`backend/tests/unit/test_settings_service.py`（写入/读取普通配置、加密配置 → 验证明文/密文存储正确；mock 无加密密钥 → 验证报错）
  - [依赖: T0c] [出参验证: pytest 全部通过]

- [x] **T21 [INT] [P]** 集成测试 — 页面渲染：`backend/tests/integration/test_dashboard.py`（GET / → 验证完整页面含所有模块；GET /market_data → 验证 Partial HTML；模拟数据源异常 → 验证降级提示）
  - [FR-001~FR-010] [依赖: T4, T5~T15] [出参验证: pytest 全部通过]

- [x] **T22 [INT]** 响应式测试 — 多 viewport：`frontend/src/__tests__/test_responsive.py`（模拟 375px/768px/1200px → 验证布局切换、核心信息完整展示）
  - [FR-006] [依赖: T15] [出参验证: pytest 全部通过]

- [x] **T23 [INT]** 前端视觉回归测试：验证 `/` 页面各组件渲染与设计参考一致
  - [依赖: T5~T15] [出参验证: 浏览器截图对比 — SideNavBar/TopNavBar/MarketIndexCard/WatchlistSnapshot/AIBriefingCard/QuickActions 布局、配色、字体与设计参考偏差 < 5%]

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 0 (Settings) ──► Phase 1 (Schema) ──► Phase 2 (Service) ──► Phase 3 (Templates)
     T0a → T0b → T0c        T1 → T2              T3 → T4              T5/P → T6/P → T7/P
                                                               T8/P → T9/P → T10/P
                                                          │
Phase 6 (Settings/Dash) ◄─────────────────────────────────┘
     T16/P → T17 → T18
                                                          │
Phase 4 (Status) ◄────────────────────────────────────────┘
     T11/P → T12/P → T13/P
                                                          │
Phase 5 (Guide/Responsive) ◄──────────────────────────────┘
     T14/P → T15/P
                                                          │
Phase 7 (Test) ◄──────────────────────────────────────────┘
     T19/P → T20/P → T21/P → T22 → T23
```

### Parallel Groups

| 组 | 任务 | 说明 |
|:---|:---|:---|
| **Group A [FE]** | T5, T6, T7, T8, T9, T10 | 6 个首页核心组件模板互相无依赖 |
| **Group B [FE]** | T11, T12, T13 | 3 个扩展状态组件互相无依赖 |
| **Group C [FE]** | T14, T15, T16 | QuickActions/Onboarding、响应式 CSS/JS、设置页模板互相独立 |
| **Group D [INT]** | T19, T20, T21 | Dashboard 测试、Settings 测试、集成测试可并行 |

### Critical Path

```
T0a → T0b → T0c → T1 → T2 → T3 → T4 → T5 → [T6~T10(并行)] → [T11~T13(并行)] → [T14~T16(并行)] → T17 → T18 → T21 → T22 → T23
```

最短完成路径估算：18 个串行步骤

---

## Notes

- `[BE]` = Backend，后端/API/数据库/服务层任务
- `[FE]` = Frontend，前端模板/CSS/JS 任务，每条标注：① DESIGN.md 章节 ② 参考 HTML 文件及行号 ③ Tailwind 组件/类
- `[INT]` = Integration/Testing，测试与集成验证任务
- `[P]` 标记 = Parallelizable，与其他 `[P]` 任务无依赖冲突，可并发执行
- T7 趋势方向使用 Material Symbols `trending_up`/`trending_down`/`trending_flat`，替代原计划的 SVG 迷你图（设计样本未使用 SVG 迷你图）
- T15 JS 轮询逻辑：`fetch('/market_data') → response.text() → container.innerHTML = html`，不使用 HTMX
- T16 设置页视觉参考 `settings_a_share_ai_monitor/code.html`，与 Dashboard 共享 base.html 布局
- T23 视觉回归测试使用浏览器截图对比，覆盖 Desktop (1200px) 和 Mobile (375px) 两种 viewport
- Dashboard 路由路径为 `/`，作为系统默认首页
- 静态文件通过 FastAPI `StaticFiles` 挂载到 `/static`
