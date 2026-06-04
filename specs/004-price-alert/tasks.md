# Tasks: 价格/涨跌幅预警

**Input**: Design documents from `specs/004-price-alert/`
**Prerequisites**: plan.md, spec.md

---

## Phase 1: 数据模型与 Schema

**Purpose**: 定义预警规则、触发记录、冷却期跟踪的数据结构

- [x] **T1 [BE]** 创建 AlertRule 数据模型：`backend/app/models/alert_rule.py`（规则 ID、股票代码、条件类型、阈值、冷却时间、触达级别、状态、last_evaluated_result，含股票代码索引）
  - [FR-004, FR-005, FR-009] [依赖: F1 基础设施就绪] [出参验证: `AlertRule.__table__.create()` 成功，表含 10 字段 + 索引]

- [x] **T2 [BE]** [P] 创建 AlertTrigger 数据模型：`backend/app/models/alert_trigger.py`（触发 ID、规则 ID、股票代码、触发条件、触发值、触发时间、触达级别、推送状态、合并规则列表）
  - [FR-012] [依赖: T1] [出参验证: 表创建成功，可写入触发记录并关联 AlertRule]

- [x] **T3 [BE]** [P] 创建 CooldownTracker 数据模型：`backend/app/models/cooldown_tracker.py`（规则 ID、最近触发时间、冷却时长，含规则 ID 唯一索引）
  - [FR-007] [依赖: T1] [出参验证: 表创建成功，支持按规则 ID 快速查询]

- [x] **T4 [BE]** [P] 创建 Alert Pydantic schemas：`backend/app/schemas/alert.py`（AlertRuleRequest, AlertRuleResponse, AlertTriggerResponse, CooldownStatus）
  - [FR-004] [依赖: T1, T2, T3] [出参验证: 无效条件类型/触达级别触发 pydantic.ValidationError]

---

## Phase 2: 规则管理（US-3）

**Purpose**: 预警规则的 CRUD 和状态管理

- [x] **T5 [BE]** [P] 实现规则 CRUD 路由：`backend/app/routers/alerts.py`（GET /alerts 列表, POST /alerts 创建, PUT /alerts/{id} 修改, DELETE /alerts/{id} 删除，含 50 条上限校验）
  - [FR-004, FR-009] [依赖: T4] [出参验证: API 测试 — 创建规则 → 查询列表 → 修改 → 删除 → 验证 50 条上限拒绝]

- [x] **T6 [BE]** [P] 实现规则状态管理：`backend/app/routers/alerts.py`（PATCH /alerts/{id}/toggle 启用/暂停切换）+ 扩展 `alert_service.py`（股票移除监听 → 自动暂停关联规则）
  - [FR-005, FR-014] [依赖: T5] [出参验证: 单元测试 — 暂停后检测跳过；mock 股票移除事件 → 规则自动 paused]

---

## Phase 3: 核心检测引擎（US-1 + US-2）

**Purpose**: 行情匹配、条件评估、触发判定

- [ ] **T7 [BE]** 实现检测引擎核心：`backend/app/services/alert_service.py`（读取 active 规则 → 获取最新行情 → 逐条评估 → 返回候选触发列表）
  - [FR-001~FR-003, FR-006] [依赖: T1, T4] [出参验证: 单元测试 — mock 2 条规则 + mock 行情 → 正确返回触发/未触发结果]

- [ ] **T8 [BE]** [P] 实现条件评估器：扩展 `alert_service.py`（price_above/below, change_pct_above/below, volume_above 的评估逻辑）
  - [FR-001~FR-003] [依赖: T7] [出参验证: 单元测试 — 5 种条件类型边界值覆盖，含边界精确值测试]

- [ ] **T9 [BE]** [P] 实现"已满足不触发"逻辑：扩展 `alert_service.py`（创建时初始化 last_evaluated_result，仅从不满足→满足才触发）
  - [FR-010] [依赖: T7] [出参验证: 单元测试 — 创建时行情已满足条件 → 不触发；行情变化后满足 → 触发]

---

## Phase 4: 冷却期与合并推送（US-4）

**Purpose**: 防刷屏机制和分级触达

- [ ] **T10 [BE]** 实现冷却期检查：扩展 `alert_service.py`（读取 CooldownTracker → 判断是否冷却中 → 触发后更新记录）
  - [FR-007] [依赖: T3, T7] [出参验证: 单元测试 — freezegun 模拟时间 → 冷却期内不触发；冷却期结束后触发]

- [ ] **T11 [BE]** [P] 实现合并推送逻辑：扩展 `alert_service.py`（同一股票多规则触发合并为一条，触达级别取最高 alert > watch）
  - [FR-008, FR-011] [依赖: T7] [出参验证: 单元测试 — 同一股票 2 条规则同时触发 → 合并为 1 条，级别取 alert]

- [ ] **T12 [BE]** 实现跨交易日冷却期重置：扩展 `alert_service.py`（交易日变更时清空全部 CooldownTracker）
  - [A-007] [依赖: T10] [出参验证: 单元测试 — freezegun 跨交易日 → 冷却期重置，原规则可再次触发]

---

## Phase 5: 集成与配置

**Purpose**: 与 F3 行情刷新集成，注册路由和配置

- [ ] **T13 [BE]** 与 F3 行情刷新集成：更新 `backend/app/core/quote_scheduler.py`（行情刷新完成后调用 `alert_service.evaluate()`）
  - [FR-006] [依赖: T7, T10, T11] [出参验证: 集成测试 — mock 行情刷新 → 触发 alert_service → 验证检测执行并生成触发记录]

- [ ] **T14 [BE]** 更新配置与路由注册：更新 `backend/app/config.py`（新增规则数上限 50、默认冷却期 30 分钟配置）+ 更新 `backend/app/main.py`（注册 alerts 路由）
  - [A-003, A-005] [依赖: T5, T13] [出参验证: `uvicorn app.main:app` 启动后路由和配置正常加载]

---

## Phase 6: 测试验证

**Purpose**: 全量测试覆盖

- [ ] **T15 [INT]** [P] 单元测试 — 检测引擎：`backend/tests/unit/test_alert_service.py`（条件评估、触发逻辑、合并推送、已满足不触发）
  - [FR-001~FR-011] [依赖: T7~T11] [出参验证: pytest 全部通过]

- [ ] **T16 [INT]** [P] 单元测试 — 冷却期：`backend/tests/unit/test_cooldown.py`（冷却期计算、跨交易日重置、修改后重置、持久化验证）
  - [FR-007] [依赖: T10, T12] [出参验证: pytest 全部通过（使用 freezegun 冻结时间）]

- [ ] **T17 [INT]** [P] 单元测试 — 规则 CRUD：`backend/tests/unit/test_alert_rules.py`（创建、查询、修改、删除、暂停、上限校验、股票移除自动暂停）
  - [FR-004, FR-005, FR-009, FR-014] [依赖: T5, T6] [出参验证: pytest 全部通过]

- [ ] **T18 [INT]** 集成测试 — 端到端：`backend/tests/integration/test_alerts_api.py`（创建规则 → 模拟行情 → 触发 → 冷却期 → 再触发 → 合并推送 → 跨交易日重置）
  - [FR-001~FR-014] [依赖: T13, T14] [出参验证: pytest 全部通过，覆盖 US-1~US-4 全部 AC]

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Model)     ──► Phase 2 (US-3 CRUD) ──► Phase 3 (Engine) ──► Phase 4 (Cooldown)
     T1/T2/T3/T4           T5/P → T6/P              T7 → T8/P/T9/P        T10 → T11/P → T12
                                                          │
Phase 5 (Integration) ◄───────────────────────────────────┘
     T13 → T14

Phase 6 (Test) ◄── 全部完成
     T15/P → T16/P → T17/P → T18
```

### Parallel Groups

| 组 | 任务 | 说明 |
|:---|:---|:---|
| **Group A [BE]** | T2, T3, T4 | 三个独立模型/schema 可并行 |
| **Group B [BE]** | T5, T6 | 规则 CRUD 和状态管理互相无依赖 |
| **Group C [BE]** | T8, T9 | 条件评估和已满足逻辑互相无依赖 |
| **Group D [BE]** | T11 | 合并推送可独立开发（依赖 T7 接口）|
| **Group E [INT]** | T15, T16, T17 | 三类单元测试可并行 |

### Critical Path

```
T1 → T4 → T5 → T7 → T8 → T10 → T12 → T13 → T14 → T18
```

最短完成路径估算：10 个串行步骤

---

## Notes

- `[BE]` = Backend（后端/API/Service/Model/Config 任务）
- `[INT]` = Integration/Testing（集成与测试任务，含单元测试、集成测试、端到端测试）
- `[P]` 标记 = Parallelizable，无依赖冲突可并发执行
- T8 条件评估器支持 5 种条件类型，单元测试需覆盖每种条件的边界值
- T10 冷却期持久化到 SQLite，单元测试使用 freezegun 模拟时间推进和跨交易日场景
- T13 集成点：F3 `quote_scheduler.py` 在行情刷新完成后调用 `alert_service.evaluate(quotes)`
- T18 集成测试使用 mock 行情数据（不依赖实际数据源），验证完整检测链路
- 本 feature 无前端模板任务（规则管理 UI 由 F5 Dashboard 负责）
