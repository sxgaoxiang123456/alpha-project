# Tasks: 自选股管理

**Input**: Design documents from `specs/001-stock-management/`  
**Prerequisites**: plan.md, spec.md

---

## Phase 1: Setup（共享基础设施）

**Purpose**: 项目初始化与容器化配置

- [ ] **T1** 创建项目骨架：`requirements.txt` + `Dockerfile` + `docker-compose.yml` + `.env.example`
  - [FR-001~FR-012 全局基础设施] [无依赖] [出参验证: `docker build -t stock-mgt .` 成功]
  - 包含：FastAPI + SQLAlchemy + Pydantic + AkShare + pytest + httpx 等全部依赖

---

## Phase 2: Foundational（阻塞性前提）

**Purpose**: 核心基础设施，必须在任何用户故事实现前完成

**⚠️ CRITICAL**: 所有用户故事依赖此阶段完成

- [ ] **T2** 创建配置与数据库层：`app/config.py`（环境变量加载）+ `app/database.py`（SQLAlchemy 引擎/SessionLocal/建表）+ `app/main.py`（FastAPI 入口）
  - [架构设计 DD-001] [依赖: T1] [出参验证: `uvicorn app.main:app` 启动无报错，访问 `/docs` 显示 Swagger UI]

- [ ] **T3** [P] 创建 Stock 数据模型：`app/models/stock.py`
  - [FR-002] [依赖: T2] [出参验证: `Stock.__table__.create()` 成功，表含 code/name/market/sector/status 字段]

- [ ] **T4** [P] 创建 Group 数据模型：`app/models/group.py`，含默认分组"默认分组"自动初始化逻辑
  - [FR-004] [依赖: T2] [出参验证: 启动时自动创建 id=1 的默认分组记录]

- [ ] **T5** 创建 WatchlistItem 数据模型：`app/models/watchlist.py`，含与 Stock/Group 的外键关联 + stock_code 唯一约束
  - [FR-003, FR-004, FR-008] [依赖: T3, T4] [出参验证: 插入重复 stock_code 触发 IntegrityError]

- [ ] **T6** [P] 创建 Pydantic schemas：`app/schemas/stock.py` + `app/schemas/watchlist.py` + `app/schemas/group.py`
  - [FR-001~FR-012 API 契约] [依赖: T5] [出参验证: 无效数据（如 cost_price="abc"）触发 pydantic.ValidationError]

**Checkpoint**: Foundation ready — 数据库可连接、表结构正确、schema 校验生效

---

## Phase 3: User Story 1 - 添加单只自选股 (Priority: P1) 🎯 MVP

**Goal**: 用户通过代码/名称搜索股票，验证后添加到指定分组

**Independent Test**: 单独测试时，可以搜索股票、添加到列表、查看列表，无需其他功能

### Implementation

- [ ] **T7** [P] 实现股票搜索服务：`app/services/stock_search.py`（AkShare 查询 + BaoStock 备用降级 + 代码格式校验）
  - [FR-001, FR-002, FR-010] [依赖: T6] [出参验证: 单元测试 — 输入"600519"返回贵州茅台对象；输入"999999"返回 None；输入"60051A"返回格式错误]

- [ ] **T8** 实现 watchlist 路由（添加/搜索/列表）：`app/routers/watchlist.py`（POST /watchlist, GET /watchlist/search, GET /watchlist）
  - [FR-001, FR-002, FR-003, FR-004, FR-009] [依赖: T7] [出参验证: API 测试 — 添加成功返回 201；重复添加返回 409；无效代码返回 404；超限（101只）返回 429]

**Checkpoint**: US1 可独立运行 — 用户能搜索、添加、查看自选股

---

## Phase 4: User Story 2 - 批量导入自选股 (Priority: P1) 🎯 MVP

**Goal**: 用户上传 CSV 文件批量导入，支持部分成功

**Independent Test**: 单独测试时，可以上传 CSV、查看导入结果，无需 US3/US4/US5

### Implementation

- [ ] **T9** [P] 实现 CSV 导入服务：`app/services/csv_import.py`（解析 + 逐行校验：格式/代码有效性/去重/上限 + 部分成功处理）
  - [FR-005, FR-006] [依赖: T6] [出参验证: 单元测试 — 20行有效CSV返回成功数=20；含2行错误返回成功18+失败明细；101行CSV返回超限错误]

- [ ] **T10** [P] 实现 CSV 导出服务：`app/services/csv_export.py`（查询当前自选股 + 生成 CSV 字节流）
  - [FR-012] [依赖: T6] [出参验证: 单元测试 — 导出 CSV 包含 code/name/group/cost_price/shares 列，与上传格式一致]

- [ ] **T11** 实现导入导出路由：`app/routers/import_export.py`（POST /watchlist/import 文件上传, GET /watchlist/export 下载）
  - [FR-005, FR-006, FR-012] [依赖: T9, T10] [出参验证: API 测试 — 上传有效CSV返回200+成功明细；上传超100行返回400；下载返回文件流]

**Checkpoint**: US2 可独立运行 — 用户能批量导入/导出自选股

---

## Phase 5: User Story 3 - 分组管理与展示 (Priority: P2)

**Goal**: 用户创建自定义分组，将股票移动分组，删除分组

**Independent Test**: 单独测试时，可以 CRUD 分组、移动股票，无需 US4/US5

### Implementation

- [ ] **T12** [P] 实现分组业务服务：`app/services/group_service.py`（删除分组时：组内股票移入默认分组 / 一并删除）
  - [FR-011] [依赖: T6] [出参验证: 单元测试 — 删除含3只股票的分组，选择"移入默认"则默认分组+3；选择"一并删除"则股票全部移除]

- [ ] **T13** 实现 groups 路由：`app/routers/groups.py`（POST /groups 创建, GET /groups 列表, PUT /groups/{id} 重命名, DELETE /groups/{id} 删除）
  - [FR-011] [依赖: T12] [出参验证: API 测试 — 创建成功返回201+分组信息；重名返回409；删除默认分组返回403；删除含股票分组返回确认选项]

**Checkpoint**: US3 可独立运行 — 用户能管理分组

---

## Phase 6: User Story 4 - 删除与批量操作 (Priority: P2)

**Goal**: 用户删除单只或批量删除股票，清理列表

**Independent Test**: 单独测试时，可以删除股票，无需 US5

### Implementation

- [ ] **T14** 扩展 watchlist 路由（编辑/删除）：`app/routers/watchlist.py` 追加 PUT /watchlist/{code}（编辑成本/股数）、DELETE /watchlist/{code}（单删）、POST /watchlist/batch-delete（批量删）
  - [FR-007, FR-008] [依赖: T8] [出参验证: API 测试 — 编辑成本返回200；单删返回204；批量删5只返回"已删除5只"；删除后列表不再包含]

**Checkpoint**: US4 可独立运行 — 用户能编辑持仓信息、删除股票

---

## Phase 7: User Story 5 - 持仓成本与盈亏展示 (Priority: P3)

**Goal**: Dashboard 展示持仓成本和盈亏计算

**Independent Test**: 添加/编辑成本后，Dashboard 展示盈亏

### Implementation

- [ ] **T15** [P] 创建前端模板 - watchlist 列表页：`app/templates/watchlist/list.html`（分组筛选切换 + 股票卡片含价格/涨跌幅/成本/盈亏）
  - [FR-004, FR-008, SC-004] [依赖: T8, T14] [出参验证: 浏览器访问 `/watchlist` 渲染正确，含成本的股票显示盈亏字段，无成本的不显示]

- [ ] **T16** [P] 创建前端模板 - 添加弹窗与分组管理：`app/templates/watchlist/add.html`（搜索下拉 + 分组选择）+ `app/templates/groups/manage.html`（分组 CRUD 界面）
  - [FR-001, FR-011] [依赖: T13] [出参验证: HTMX 交互正常 — 搜索框输入触发候选列表；分组删除弹窗显示归属选项]

**Checkpoint**: US5 可独立运行 — Dashboard 展示完整自选股信息

---

## Phase 8: 测试与验证

**Purpose**: 全量测试覆盖，确保所有验收场景通过

- [ ] **T17** [P] 单元测试套件：`tests/unit/test_models.py` + `tests/unit/test_schemas.py` + `tests/unit/test_services.py`
  - [FR-001~FR-012] [依赖: T3~T12] [出参验证: `pytest tests/unit/` 全部通过（≥ 30 个测试用例）]

- [ ] **T18** [P] 集成测试套件：`tests/integration/test_watchlist_api.py` + `tests/integration/test_groups_api.py` + `tests/integration/test_import_export.py`
  - [FR-001~FR-012] [依赖: T8, T11, T13, T14] [出参验证: `pytest tests/integration/` 全部通过（覆盖所有 AC 场景）]

**Checkpoint**: 全部测试通过，feature 可交付

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)     ──► Phase 2 (Foundational) ──► Phase 3/4/5/6 (User Stories) ──► Phase 8 (Tests)
     T1                    T2 ──► T3/T4 ──► T5 ──► T6                              T17/T18
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
| **Group D** | T15, T16 | 前端模板可并行 |
| **Group E** | T17, T18 | 测试套件可并行（单元不依赖集成） |

### Critical Path

```
T1 → T2 → T3/T4(并行) → T5 → T6 → [T7/T9/T10/T12(并行)] → [T8/T11/T13/T14(并行)] → [T15/T16(并行)] → [T17/T18(并行)]
```

最短完成路径估算（串行节点之和）：T1 + T2 + max(T3,T4) + T5 + T6 + max(T7,T9,T10,T12) + max(T8,T11,T13,T14) + max(T15,T16) + max(T17,T18) ≈ 9 个串行步骤

---

## Notes

- `[P]` 标记 = Parallelizable，与其他 `[P]` 任务无依赖冲突，可并发执行
- 所有路由层任务（T8, T11, T13, T14）共享同一个 router 文件时需串行，避免代码冲突
- TDD 建议：T17/T18 可在对应服务/路由完成后提前编写，但应在实现前确保测试 FAIL
- 每条任务标注了 `[FR-X 来源]`，实现时可追溯至 spec.md 的具体需求
- 任务粒度控制：每条任务产出 1-3 个文件，AI 辅助编程下单次生成可控在 2-5 分钟
