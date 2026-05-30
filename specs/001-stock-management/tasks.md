# Tasks: 自选股管理

**Input**: Design documents from `specs/001-stock-management/`
**Prerequisites**: plan.md, spec.md
**Frontend Reference**: `design-reference/DESIGN.md`, `design-reference/stitch-export/watchlist_management_a_share_ai_monitor/code.html`

---

## Phase 1: Setup（共享基础设施）

**Purpose**: 项目初始化与容器化配置

- [X] **T1 [BE]** 创建项目骨架：`requirements.txt` + `Dockerfile` + `docker-compose.yml` + `.env.example`
  - [FR-001~FR-012 全局基础设施] [无依赖] [出参验证: `docker build -t stock-mgt .` 成功]
  - 包含：FastAPI + SQLAlchemy + Pydantic + AkShare + pytest + httpx 等全部依赖

---

## Phase 2: Foundational（阻塞性前提）

**Purpose**: 核心基础设施，必须在任何用户故事实现前完成

**⚠️ CRITICAL**: 所有用户故事依赖此阶段完成

- [X] **T2 [BE]** 创建配置与数据库层：`app/config.py`（环境变量加载）+ `app/database.py`（SQLAlchemy 引擎/SessionLocal/建表）+ `app/main.py`（FastAPI 入口）
  - [架构设计 DD-001] [依赖: T1] [出参验证: `uvicorn app.main:app` 启动无报错，访问 `/docs` 显示 Swagger UI]

- [ ] **T3 [BE] [P]** 创建 Stock 数据模型：`app/models/stock.py`
  - [FR-002] [依赖: T2] [出参验证: `Stock.__table__.create()` 成功，表含 code/name/market/sector/status 字段]

- [ ] **T4 [BE] [P]** 创建 Group 数据模型：`app/models/group.py`，含默认分组"默认分组"自动初始化逻辑
  - [FR-004] [依赖: T2] [出参验证: 启动时自动创建 id=1 的默认分组记录]

- [ ] **T5 [BE]** 创建 WatchlistItem 数据模型：`app/models/watchlist.py`，含与 Stock/Group 的外键关联 + stock_code 唯一约束
  - [FR-003, FR-004, FR-008] [依赖: T3, T4] [出参验证: 插入重复 stock_code 触发 IntegrityError]

- [ ] **T6 [BE] [P]** 创建 Pydantic schemas：`app/schemas/stock.py` + `app/schemas/watchlist.py` + `app/schemas/group.py`
  - [FR-001~FR-012 API 契约] [依赖: T5] [出参验证: 无效数据（如 cost_price="abc"）触发 pydantic.ValidationError]

**Checkpoint**: Foundation ready — 数据库可连接、表结构正确、schema 校验生效

---

## Phase 3: User Story 1 - 添加单只自选股 (Priority: P1) 🎯 MVP

**Goal**: 用户通过代码/名称搜索股票，验证后添加到指定分组

**Independent Test**: 单独测试时，可以搜索股票、添加到列表、查看列表，无需其他功能

### Implementation

- [ ] **T7 [BE] [P]** 实现股票搜索服务：`app/services/stock_search.py`（AkShare 查询 + BaoStock 备用降级 + 代码格式校验）
  - [FR-001, FR-002, FR-010] [依赖: T6] [出参验证: 单元测试 — 输入"600519"返回贵州茅台对象；输入"999999"返回 None；输入"60051A"返回格式错误]

- [ ] **T8 [BE]** 实现 watchlist 路由（添加/搜索/列表）：`app/routers/watchlist.py`（POST /watchlist, GET /watchlist/search, GET /watchlist）
  - [FR-001, FR-002, FR-003, FR-004, FR-009] [依赖: T7] [出参验证: API 测试 — 添加成功返回 201；重复添加返回 409；无效代码返回 404；超限（101只）返回 429]

**Checkpoint**: US1 可独立运行 — 用户能搜索、添加、查看自选股

---

## Phase 4: User Story 2 - 批量导入自选股 (Priority: P1) 🎯 MVP

**Goal**: 用户上传 CSV 文件批量导入，支持部分成功

**Independent Test**: 单独测试时，可以上传 CSV、查看导入结果，无需 US3/US4/US5

### Implementation

- [ ] **T9 [BE] [P]** 实现 CSV 导入服务：`app/services/csv_import.py`（解析 + 逐行校验：格式/代码有效性/去重/上限 + 部分成功处理）
  - [FR-005, FR-006] [依赖: T6] [出参验证: 单元测试 — 20行有效CSV返回成功数=20；含2行错误返回成功18+失败明细；101行CSV返回超限错误]

- [ ] **T10 [BE] [P]** 实现 CSV 导出服务：`app/services/csv_export.py`（查询当前自选股 + 生成 CSV 字节流）
  - [FR-012] [依赖: T6] [出参验证: 单元测试 — 导出 CSV 包含 code/name/group/cost_price/shares 列，与上传格式一致]

- [ ] **T11 [BE]** 实现导入导出路由：`app/routers/import_export.py`（POST /watchlist/import 文件上传, GET /watchlist/export 下载）
  - [FR-005, FR-006, FR-012] [依赖: T9, T10] [出参验证: API 测试 — 上传有效CSV返回200+成功明细；上传超100行返回400；下载返回文件流]

**Checkpoint**: US2 可独立运行 — 用户能批量导入/导出自选股

---

## Phase 5: User Story 3 - 分组管理与展示 (Priority: P2)

**Goal**: 用户创建自定义分组，将股票移动分组，删除分组

**Independent Test**: 单独测试时，可以 CRUD 分组、移动股票，无需 US4/US5

### Implementation

- [ ] **T12 [BE] [P]** 实现分组业务服务：`app/services/group_service.py`（删除分组时：组内股票移入默认分组 / 一并删除）
  - [FR-011] [依赖: T6] [出参验证: 单元测试 — 删除含3只股票的分组，选择"移入默认"则默认分组+3；选择"一并删除"则股票全部移除]

- [ ] **T13 [BE]** 实现 groups 路由：`app/routers/groups.py`（POST /groups 创建, GET /groups 列表, PUT /groups/{id} 重命名, DELETE /groups/{id} 删除）
  - [FR-011] [依赖: T12] [出参验证: API 测试 — 创建成功返回201+分组信息；重名返回409；删除默认分组返回403；删除含股票分组返回确认选项]

**Checkpoint**: US3 可独立运行 — 用户能管理分组

---

## Phase 6: User Story 4 - 删除与批量操作 (Priority: P2)

**Goal**: 用户删除单只或批量删除股票，清理列表

**Independent Test**: 单独测试时，可以删除股票，无需 US5

### Implementation

- [ ] **T14 [BE]** 扩展 watchlist 路由（编辑/删除）：`app/routers/watchlist.py` 追加 PUT /watchlist/{code}（编辑成本/股数）、DELETE /watchlist/{code}（单删）、POST /watchlist/batch-delete（批量删）
  - [FR-007, FR-008] [依赖: T8] [出参验证: API 测试 — 编辑成本返回200；单删返回204；批量删5只返回"已删除5只"；删除后列表不再包含]

**Checkpoint**: US4 可独立运行 — 用户能编辑持仓信息、删除股票

---

## Phase 7: User Story 5 - 前端界面实现 (Priority: P3)

**Goal**: 基于 `design-reference/stitch-export/watchlist_management_a_share_ai_monitor/code.html` 视觉参考，实现自选股管理完整前端界面

**Independent Test**: 浏览器访问 `/watchlist` 渲染正确，各组件样式与设计参考一致

### Implementation — 基础布局组件（可并行）

- [ ] **T15 [FE] [P]** 创建基础布局模板：`app/templates/base.html`（HTML5 骨架 + Tailwind CDN + Google Fonts + Material Symbols）
  - [DESIGN.md §Layout & Spacing, §Colors, §Typography] [参考 HTML: `watchlist_management_a_share_ai_monitor/code.html` L1-119] [Tailwind: `darkMode: "class"`, custom colors/fonts/spacing] [依赖: T2] [出参验证: 浏览器访问 `/watchlist` 返回完整 HTML，含 Tailwind 和字体加载]

- [ ] **T16 [FE] [P]** 创建 SideNavBar 组件：`app/templates/components/side_nav.html`（导航菜单 + AI 简报按钮）
  - [DESIGN.md §Layout & Spacing（导航栏）, §Colors（surface-container-lowest, primary-container）] [参考 HTML: `watchlist_management_a_share_ai_monitor/code.html` L121-153] [Tailwind: `bg-surface-container-lowest`, `border-r border-outline-variant`, `w-64 h-screen fixed`, Material Symbols icons] [依赖: T15] [出参验证: 页面含固定左侧导航栏，含"控制面板"/"自选股"/"预警规则"/"设置"菜单项和 AI 简报按钮]

- [ ] **T17 [FE] [P]** 创建 TopNavBar + CommandBar 组件：`app/templates/components/top_nav.html`（顶部栏 + 搜索框 + 通知 + 用户头像）
  - [DESIGN.md §Layout & Spacing（顶部栏）, §Components / Input Forms (Command Bar)] [参考 HTML: `watchlist_management_a_share_ai_monitor/code.html` L157-179] [Tailwind: `bg-surface backdrop-blur-md`, `border-b border-outline-variant`, `sticky top-0 z-50`, CommandBar `bg-surface-raised border-outline-variant rounded`] [依赖: T15] [出参验证: 页面含 sticky 顶部栏，搜索框占位符为 "Command (e.g., /add 600519)"]

### Implementation — 数据展示组件（可并行）

- [ ] **T18 [FE] [P]** 创建 FilterSidebar 组件：`app/templates/components/filter_sidebar.html`（分组列表 + 计数 + 新建分组按钮）
  - [DESIGN.md §Layout & Spacing（侧边栏）, §Colors（surface-base, surface-container-high）] [参考 HTML: `watchlist_management_a_share_ai_monitor/code.html` L196-219] [Tailwind: `bg-surface-base border-outline-variant rounded`, `sticky top-0`, 分组项 hover `bg-surface-variant`] [依赖: T15] [出参验证: 侧边栏显示"全部资产"/分组列表及计数，新建分组按钮]

- [ ] **T19 [FE] [P]** 创建 StockDataTable 组件：`app/templates/components/stock_table.html` + `stock_table_row.html`（表头控制 + 数据行 + 迷你趋势图 + 操作按钮）
  - [DESIGN.md §Components / Stock Data Tables, §Components / Mini-Charts] [参考 HTML: `watchlist_management_a_share_ai_monitor/code.html` L247-359] [Tailwind: `font-data-table text-data-table`, sticky thead `bg-surface-container-low font-label-caps`, 行高 `h-table-row-height`, hover `bg-surface-variant/50`, 复选框 `rounded-[0.125rem]`, 迷你趋势图 CSS bar chart] [依赖: T15] [出参验证: 表格含 股票/分组/价格/成本/盈亏比/信号/操作 列，盈亏比按市场红涨绿跌着色，hover 显示编辑/删除按钮]

- [ ] **T20 [FE] [P]** 创建辅助状态组件：`app/templates/components/empty_state.html` + `alert_badge.html` + `metric_tag.html`
  - [DESIGN.md §Components / Alert Badges, §Components / Metric Cards（标签变体）] [参考 HTML: `watchlist_management_a_share_ai_monitor/code.html` L349（AlertBadge）, L275-276（MetricTag）, L365-378（EmptyState 注释区）] [Tailwind: AlertBadge `text-market-warning border-market-warning/50 bg-market-warning/10`; MetricTag `bg-secondary-container/30 text-secondary-fixed border-secondary-container`; EmptyState `bg-surface-base border-outline-variant rounded`, 主按钮 `bg-primary-container shadow-lg`] [依赖: T15] [出参验证: 空自选股时显示 EmptyState 引导页；触及目标股票显示 AlertBadge；分组显示 MetricTag]

### Implementation — 页面组装与交互

- [ ] **T21 [FE]** 创建自选股列表主页面：`app/templates/watchlist/list.html`（组装 SideNavBar + TopNavBar + FilterSidebar + StockDataTable + EmptyState）
  - [DESIGN.md §Layout & Spacing（12 列网格）] [参考 HTML: `watchlist_management_a_share_ai_monitor/code.html` L181-362] [Tailwind: `grid grid-cols-12 gap-container-gap`, FilterSidebar `col-span-12 md:col-span-3 lg:col-span-2`, Table `col-span-12 md:col-span-9 lg:col-span-10`] [依赖: T16, T17, T18, T19, T20] [出参验证: 浏览器访问 `/watchlist` 渲染完整页面，所有组件正确组装，响应式布局生效]

- [ ] **T22 [FE] [P]** 创建添加/编辑弹窗组件：`app/templates/watchlist/add_modal.html` + `edit_modal.html`（CommandBar 搜索下拉 + 分组选择 + 成本/股数编辑）
  - [DESIGN.md §Components / Input Forms] [参考 HTML: `watchlist_management_a_share_ai_monitor/code.html` L159-161（CommandBar 样式参考）] [Tailwind: 弹窗 `bg-surface-raised border-outline-variant rounded`, 输入框 focus `border-primary-container focus:ring-1 focus:ring-primary-container`] [依赖: T21] [出参验证: 点击"添加股票"弹窗正常显示，含搜索框和分组下拉；点击行内编辑弹窗显示成本/股数输入]

- [ ] **T23 [FE] [P]** 创建分组管理页面：`app/templates/groups/manage.html` + 创建分组管理 CSS/JS：`app/static/css/watchlist.css` + `app/static/js/watchlist.js`
  - [DESIGN.md §Layout & Spacing, §Components / Checkboxes] [参考 HTML: `watchlist_management_a_share_ai_monitor/code.html` L196-219（FilterSidebar 样式参考）] [Tailwind CSS: 响应式布局媒体查询，hover transition, 批量选择 checkbox 动画] [JS: 批量选择状态管理，分组切换 AJAX，行内编辑 toggle] [依赖: T21] [出参验证: 分组管理页可 CRUD 分组；JS 批量选择正常；移动端布局正确]

**Checkpoint**: US5 可独立运行 — Dashboard 展示完整自选股信息，视觉与设计参考一致

---

## Phase 8: 测试与验证

**Purpose**: 全量测试覆盖，确保所有验收场景通过

- [ ] **T24 [INT] [P]** 单元测试套件：`tests/unit/test_models.py` + `tests/unit/test_schemas.py` + `tests/unit/test_services.py`
  - [FR-001~FR-012] [依赖: T3~T12] [出参验证: `pytest tests/unit/` 全部通过（≥ 30 个测试用例）]

- [ ] **T25 [INT] [P]** 集成测试套件：`tests/integration/test_watchlist_api.py` + `tests/integration/test_groups_api.py` + `tests/integration/test_import_export.py`
  - [FR-001~FR-012] [依赖: T8, T11, T13, T14] [出参验证: `pytest tests/integration/` 全部通过（覆盖所有 AC 场景）]

- [ ] **T26 [INT]** 前端视觉回归测试：验证 `/watchlist` 页面各组件渲染与设计参考一致
  - [依赖: T21] [出参验证: 浏览器截图对比 — SideNavBar/TopNavBar/FilterSidebar/StockDataTable/EmptyState 布局、配色、字体与设计参考偏差 < 5%]

**Checkpoint**: 全部测试通过，feature 可交付

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)     ──► Phase 2 (Foundational) ──► Phase 3/4/5/6 (User Stories) ──► Phase 7 (FE) ──► Phase 8 (Tests)
     T1                    T2 ──► T3/T4 ──► T5 ──► T6                              T15~T23         T24/T25/T26
                                      │        │
                                      └────────┘
                              T3/T4 可并行；T5 依赖 T3+T4；T6 依赖 T5
```

### Parallel Groups

| 组 | 任务 | 说明 |
|:---|:---|:---|
| **Group A** | T3, T4 | 两个独立模型可并行 |
| **Group B** | T7, T9, T10, T12 | 四个服务互相无依赖，可并行 |
| **Group C** | T8, T11, T13, T14 | 四个路由在各自服务完成后可并行 |
| **Group D [FE]** | T15, T16, T17, T18, T19, T20 | 6 个前端组件模板互相无依赖，可并行 |
| **Group E [FE]** | T22, T23 | 弹窗和分组管理页/样式可并行 |
| **Group F [INT]** | T24, T25, T26 | 测试套件可并行（单元不依赖集成） |

### Critical Path

```
T1 → T2 → T3/T4(并行) → T5 → T6 → [T7/T9/T10/T12(并行)] → [T8/T11/T13/T14(并行)] → [T15~T20(并行)] → T21 → [T22/T23(并行)] → [T24/T25/T26(并行)]
```

最短完成路径估算（串行节点之和）：T1 + T2 + max(T3,T4) + T5 + T6 + max(T7,T9,T10,T12) + max(T8,T11,T13,T14) + max(T15~T20) + T21 + max(T22,T23) + max(T24,T25,T26) ≈ 11 个串行步骤

---

## Notes

- `[BE]` = Backend，后端/API/数据库任务
- `[FE]` = Frontend，前端模板/CSS/JS 任务，每条标注：① DESIGN.md 章节 ② 参考 HTML 文件 ③ Tailwind 组件/类
- `[INT]` = Integration/Testing，测试与集成验证任务
- `[P]` 标记 = Parallelizable，与其他 `[P]` 任务无依赖冲突，可并发执行
- 所有路由层任务（T8, T11, T13, T14）共享同一个 router 文件时需串行，避免代码冲突
- TDD 建议：T24/T25 可在对应服务/路由完成后提前编写，但应在实现前确保测试 FAIL
- 每条任务标注了 `[FR-X 来源]`，实现时可追溯至 spec.md 的具体需求
- 任务粒度控制：每条任务产出 1-3 个文件，AI 辅助编程下单次生成可控在 2-5 分钟
