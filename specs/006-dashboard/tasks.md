# Tasks: 基础 Dashboard

**Input**: Design documents from `specs/006-dashboard/`
**Prerequisites**: plan.md, spec.md

---

## Phase 0: 配置管理基础设施（横向模块，被 F4/F5/F6 复用）

**Purpose**: 创建统一的配置管理服务，支持用户级配置的持久化和敏感字段加密

- [ ] **T0a** 创建 AppSetting 数据模型：`app/models/app_setting.py`（key, value, category, is_encrypted, updated_at，含 category 索引）
  - [依赖: F1 基础设施就绪] [出参验证: `AppSetting.__table__.create()` 成功，表含 5 字段 + category 索引]

- [ ] **T0b** 创建 Setting Pydantic schemas：`app/schemas/settings.py`（SettingRequest, SettingResponse, SettingCategory）
  - [依赖: T0a] [出参验证: 无效 category 触发 pydantic.ValidationError]

- [ ] **T0c** [P] 创建 SettingsService：`app/services/settings_service.py`（`get_setting(key)`, `set_setting(key, value, encrypt=False)`, `get_all_by_category(category)`，敏感字段使用 Fernet 加密）
  - [依赖: T0b] [出参验证: 单元测试 — 写入/读取普通字段和加密字段 → 验证明文存储和加密解密正确]

---

## Phase 1: Schema 与接口骨架

**Purpose**: 定义 Dashboard 数据模型和服务接口

- [ ] **T1** 创建 Dashboard Pydantic schemas：`app/schemas/dashboard.py`（DashboardViewResponse, MarketSnapshot, StockCardData, BriefingData, AlertSummary, PushHistoryItem, ChannelStatusItem）
  - [FR-001~FR-010] [依赖: F1/F2/F3/F4 基础设施就绪, T0b] [出参验证: 无效字段触发 pydantic.ValidationError]

- [ ] **T2** 创建 DashboardService 接口骨架：`app/services/dashboard_service.py`（类定义 + 聚合方法签名 + 上游服务依赖注入接口）
  - [FR-001~FR-010] [依赖: T1] [出参验证: `DashboardService` 类可实例化，方法签名完整]

---

## Phase 2: 核心聚合服务（US-1）

**Purpose**: 实现数据聚合和页面路由

- [ ] **T3** 实现 DashboardService 数据聚合：`app/services/dashboard_service.py`（asyncio.gather 并行调用 5 个上游服务 → 统一响应模型 → 单个服务超时降级）
  - [FR-001~FR-005, FR-009, FR-010] [依赖: T2, F1/F2/F3/F4 服务就绪] [出参验证: 单元测试 — mock 5 个上游服务 → 验证并行调用、超时降级、聚合结果完整]

- [ ] **T4** 实现 Dashboard 首页路由：`app/routers/dashboard.py`（GET / → 聚合服务 → 渲染 dashboard.html；GET /market_data → 返回行情 Partial HTML）
  - [FR-001, FR-003, FR-006] [依赖: T3] [出参验证: 集成测试 — mock 数据 → 验证页面 HTTP 200、含大盘/自选股/简报模块]

---

## Phase 3: 首页模板组件（US-1，Group A 并行）

**Purpose**: 渲染低密度首页的各模块

- [ ] **T5** [P] 创建基础布局模板：`app/templates/base.html`（HTML5 骨架 + HTMX CDN + Tailwind CDN + 响应式 meta）+ `app/templates/dashboard.html`（首页主布局，含各组件插槽）
  - [FR-001, FR-006] [依赖: T4] [出参验证: 浏览器访问 / → 返回完整 HTML，含 HTMX 和 Tailwind 加载]

- [ ] **T6** [P] 创建大盘指数组件：`app/templates/components/market_index.html`（上证/深证/创业 → 点位 + 涨跌幅 + 涨跌额 + 更新时间）
  - [FR-001] [依赖: T5] [出参验证: 集成测试 — mock 大盘数据 → 验证 3 个指数正确渲染]

- [ ] **T7** [P] 创建自选股卡片组件：`app/templates/components/stock_card.html`（股票名称/代码/当前价/涨跌幅/涨跌额 + SVG 迷你趋势图）
  - [FR-002, FR-010] [依赖: T5] [出参验证: 集成测试 — mock 5 只自选股 → 验证卡片字段完整、趋势图 SVG 存在]

- [ ] **T8** [P] 创建简报卡片组件：`app/templates/components/briefing_card.html`（日期 + 简报标题 + 摘要内容 + "今日暂无简报"占位态）
  - [FR-001] [依赖: T5] [出参验证: 集成测试 — mock 简报数据 → 验证卡片渲染；无简报时显示占位态]

- [ ] **T9** [P] 创建预警汇总横幅：`app/templates/components/alert_banner.html`（今日触警股票列表 + 触发条件 + 预警级别图标）
  - [FR-001] [依赖: T5] [出参验证: 集成测试 — mock 今日预警 → 验证横幅展示触警股票和图标]

---

## Phase 4: 推送历史与通道状态（US-5）

**Purpose**: 展示推送历史和通道健康

- [ ] **T10** 创建推送历史组件：`app/templates/components/push_history.html`（消息类型/标题/时间/通道/状态/失败原因列表 + 最近 100 条限制）
  - [FR-007] [依赖: T5] [出参验证: 集成测试 — mock 10 条推送记录 → 验证列表正确渲染]

- [ ] **T11** 创建通道状态组件：`app/templates/components/channel_status.html`（飞书/Telegram 状态 + 限流提示 + 颜色标记：绿/黄/红）
  - [FR-008] [依赖: T5] [出参验证: 集成测试 — mock 通道状态 → 验证正确颜色和提示文本]

---

## Phase 5: 引导与响应式（US-2 + US-4）

**Purpose**: 首次使用引导和移动端自适应

- [ ] **T12** [P] 创建首次使用引导组件：`app/templates/components/onboarding.html`（自选股为空时展示引导卡片 + "手动添加"入口 + 搜索展开）
  - [FR-004] [依赖: T5] [出参验证: 集成测试 — 空自选股 → 验证引导页展示；添加股票后 → 引导消失]

- [ ] **T13** [P] 实现响应式样式和刷新逻辑：`app/static/css/dashboard.css`（移动端单列/PC 端多列布局 + Tailwind 响应式类）+ `app/static/js/dashboard.js`（60 秒 HTMX 轮询 + 数据源恢复检测）
  - [FR-003, FR-005, FR-006] [依赖: T5] [出参验证: 浏览器开发者工具切换 375px viewport → 验证单列布局；JS 加载后 → 验证定时请求存在]

---

## Phase 6: 设置页与集成

**Purpose**: 设置页路由、配置读写、路由注册

- [ ] **T14** 实现设置页路由：`app/routers/settings.py`（GET /settings → 渲染设置表单；POST /settings → 接收表单数据 → 调用 `settings_service.set_setting()` 持久化；按 category 分组展示配置项）
  - [依赖: T0c] [出参验证: 集成测试 — 提交飞书配置 → 验证数据库写入；读取配置 → 验证敏感字段解密正确]

- [ ] **T15** 更新路由注册：更新 `app/main.py`（注册 dashboard 路由、settings 路由、静态文件挂载）
  - [FR-003] [依赖: T4, T14] [出参验证: `uvicorn app.main:app` 启动后 Dashboard 和 Settings 路由均可用，静态文件可访问]

---

## Phase 7: 测试验证

**Purpose**: 全量测试覆盖

- [ ] **T16** [P] 单元测试 — DashboardService：`tests/unit/test_dashboard_service.py`（mock 5 个上游服务 → 验证并行聚合、超时降级、空数据降级）
  - [FR-001~FR-005] [依赖: T3] [出参验证: pytest 全部通过]

- [ ] **T17** [P] 单元测试 — SettingsService：`tests/unit/test_settings_service.py`（写入/读取普通配置、加密配置 → 验证明文/密文存储正确；mock 无加密密钥 → 验证报错）
  - [依赖: T0c] [出参验证: pytest 全部通过]

- [ ] **T18** [P] 集成测试 — 页面渲染：`tests/integration/test_dashboard.py`（GET / → 验证完整页面含所有模块；GET /market_data → 验证 Partial HTML；模拟数据源异常 → 验证降级提示）
  - [FR-001~FR-010] [依赖: T4, T5~T13] [出参验证: pytest 全部通过]

- [ ] **T19** 响应式测试 — 多 viewport：`tests/e2e/test_responsive.py`（模拟 375px/768px/1200px → 验证布局切换、核心信息完整展示）
  - [FR-006] [依赖: T13] [出参验证: pytest 全部通过]

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 0 (Settings) ──► Phase 1 (Schema) ──► Phase 2 (Service) ──► Phase 3 (Templates)
     T0a → T0b → T0c        T1 → T2              T3 → T4              T5/P → T6/P → T7/P
                                                               T8/P → T9/P
                                                          │
Phase 6 (Settings/Dash) ◄─────────────────────────────────┘
     T14 → T15
                                                          │
Phase 4 (Push/Channel) ◄──────────────────────────────────┘
     T10 → T11
                                                          │
Phase 5 (Guide/Responsive) ◄──────────────────────────────┘
     T12/P → T13/P
                                                          │
Phase 7 (Test) ◄──────────────────────────────────────────┘
     T16/P → T17/P → T18/P → T19
```

### Parallel Groups

| 组 | 任务 | 说明 |
|:---|:---|:---|
| **Group A** | T0a, T0b, T0c | Settings 基础设施可与 Dashboard Schema 并行 |
| **Group B** | T5, T6, T7, T8, T9 | 5 个模板组件互相无依赖 |
| **Group C** | T12, T13 | 引导组件和响应式互相独立 |
| **Group D** | T16, T17, T18 | Dashboard 测试、Settings 测试、集成测试可并行 |

### Critical Path

```
T0a → T0b → T0c → T1 → T2 → T3 → T4 → T5 → T6 → T10 → T14 → T15 → T18 → T19
```

最短完成路径估算：10 个串行步骤

---

## Notes

- `[P]` 标记 = Parallelizable，无依赖冲突可并发执行
- T7 迷你趋势图使用 SVG `<path>` 内联渲染，后端返回简化数据点序列（开盘/最高/最低/收盘 + 6 个时点），前端用 Jinja2 宏生成 SVG path
- T13 定时刷新通过 `dashboard.js` 中 `setInterval(60000)` + HTMX `hx-get` 实现，数据源异常时 JS 检测到降级标记后暂停定时器
- T0c SettingsService 加密密钥通过环境变量 `SETTINGS_ENCRYPTION_KEY` 注入，未配置时 raise ConfigurationError
- T14 设置页表单按 category 分组渲染（lark / telegram / datasource / preference），敏感字段使用 `<input type="password">`
- T12 首次使用引导通过检查 `watchlist_service.get_watchlists()` 返回数量判断，无独立状态表
- T18 集成测试使用 `httpx` + `beautifulsoup4` 解析响应 HTML，验证各组件是否存在
- T17 响应式测试使用 `pytest-playwright` 或 `httpx` + 自定义 User-Agent 和 viewport header 模拟不同设备
- Dashboard 路由路径为 `/`，作为系统默认首页
- 静态文件通过 FastAPI `StaticFiles` 挂载到 `/static`
