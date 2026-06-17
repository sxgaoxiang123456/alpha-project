# Tasks: F9 成交量异动检测

**Input**: Design documents from `/specs/011-volume-surge-alert/`  
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [data-model.md](data-model.md), [contracts/api.md](contracts/api.md), [quickstart.md](quickstart.md)

---

## Format

- `[P]`：可与其他 [P] 任务并行执行（无文件/依赖冲突）
- `[USx]`：所属用户故事
- 描述中末尾标注：`[FR-xxx 来源] | [依赖: Txxx] | [验证: xxx]`

---

## Phase 1: Setup

**Purpose**: 创建成交量异动事件表

- [ ] T001 [BE] Create Alembic migration for `volume_surge_events` table with `(stock_code, date)` unique constraint  
  `[FR-005 来源] | [依赖: 无] | [验证: 表结构包含 volume/avg_volume/ratio/data_quality，唯一约束生效]`

---

## Phase 2: Foundational

**Purpose**: 核心基础设施：schema、模型、检测器、编排服务  
**⚠️ CRITICAL**: 本阶段完成前不可开始 user story 实现

- [ ] T002 [P] [BE] Create `backend/app/schemas/volume_surge.py` with `VolumeSurgeEventResponse`, `VolumeSurgeDetectRequest`, `TodayVolumeSurgeResponse` schemas  
  `[FR-005/FR-008 来源] | [依赖: 无] | [验证: schema 实例化通过，枚举字段校验生效]`

- [ ] T003 [P] [BE] Create `backend/app/models/volume_surge_event.py` SQLAlchemy model and export it in `backend/app/models/__init__.py`  
  `[FR-005 来源] | [依赖: T001] | [验证: 模型可创建，唯一约束生效]`

- [ ] T004 [P] [BE] Create `backend/app/services/volume_surge_detector.py` with single-stock surge detection, halt inference and limited-data flag  
  `[FR-002/FR-004/FR-006 来源] | [依赖: 无] | [验证: 输入 mock 日 K，返回 ratio/是否触发/数据质量]`

- [ ] T005 [BE] Create `backend/app/services/volume_surge_service.py` orchestrating watchlist → history fetch → detect → persist → push  
  `[FR-001/FR-006/FR-007 来源] | [依赖: T003, T004] | [验证: mock 5 只自选股返回正确事件数并写入 DB]`

**Checkpoint**: Foundation ready — 检测服务可独立运行并生成事件

---

## Phase 3: User Story 1 — 自选股成交量异动自动推送（Priority: P1） 🎯 MVP

**Goal**: 每个交易日 15:15 自动检测自选股成交量异动并推送 Top 5  
**Independent Test**: 模拟交易日运行检测任务，飞书/Telegram 收到异动通知

- [ ] T006 [US1] [BE] Register `detect_volume_surge_if_trading_day` job at 15:15 in `backend/app/core/quote_scheduler.py`  
  `[FR-002 来源] | [依赖: T005] | [验证: 启动服务后 APScheduler 显示 15:15 定时任务]`

- [ ] T007 [US1] [INT] Extend `backend/app/services/push_service.py` with `volume_surge` message formatter and validate end-to-end auto-detection + push  
  `[FR-007 来源] | [依赖: T005, T006] | [验证: mock 触发 3 只，收到包含 Top 3 的推送消息]`

**Checkpoint**: US1 完整闭环——交易日自动检测、推送成功

---

## Phase 4: User Story 2 — 自定义异动阈值（Priority: P2）

**Goal**: 用户可调整 window_days / multiplier / cooldown_days  
**Independent Test**: 修改阈值后检测结果按新阈值生效

- [ ] T008 [US2] [BE] Extend `backend/app/services/settings_service.py` to read/write/validate `volume_surge_enabled`, `window_days`, `multiplier`, `cooldown_days`  
  `[FR-009/FR-010/FR-012 来源] | [依赖: 无] | [验证: PUT /api/settings/volume-surge 保存后 GET 返回一致；非法值返回 422]`

- [ ] T009 [US2] [INT] Validate threshold/window/cooldown adjustments affect detection results  
  `[FR-010 来源] | [依赖: T004, T008] | [验证: multiplier 从 2.0 调到 3.0 后，2.5 倍不再触发]`

**Checkpoint**: US2 验证通过——阈值可配置且生效

---

## Phase 5: User Story 3 — Dashboard 查看今日异动（Priority: P2）

**Goal**: Dashboard 展示今日异动 Top 5，支持手动触发检测  
**Independent Test**: 点击「立即检测」后卡片显示 Top 5，超出显示「查看全部」

- [ ] T010 [US3] [BE] Create `backend/app/routers/volume_surge.py` with `POST /api/volume-surge/detect`, `GET /api/volume-surge/today`, `GET /api/volume-surge/events` endpoints  
  `[FR-003/FR-008 来源] | [依赖: T002, T005] | [验证: 手动检测返回正确 total/top_5/has_more]`

- [ ] T011 [US3] [BE] Register `volume_surge_router` in `backend/app/main.py`  
  `[FR-008 来源] | [依赖: T010] | [验证: 服务启动后 endpoints 可访问]`

- [ ] T012 [P] [US3] [FE] Create `frontend/src/templates/components/volume_surge_card.html` with Top 5 list, empty state, 「立即检测」button and 「查看全部」link  
  `[FR-008 来源] | [依赖: 无] | [验证: 组件独立渲染，文案为中文]`

- [ ] T013 [US3] [FE] Integrate `volume_surge_card` into `frontend/src/templates/dashboard.html` and validate manual detect + display flow in browser  
  `[FR-008 来源] | [依赖: T011, T012] | [验证: 点击立即检测后卡片刷新显示 Top 5]`

**Checkpoint**: US3 验证通过——Dashboard 展示与手动触发可用

---

## Phase 6: User Story 4 — 排除停牌与数据不足股票（Priority: P3）

**Goal**: 停牌股跳过，数据不足股票标记 limited 后仍按规则判断  
**Independent Test**：停牌股不生成事件，次新股标记 limited 后可触发

- [ ] T014 [US4] [INT] Validate halt detection and limited-data handling via unit/integration tests  
  `[FR-004 来源] | [依赖: T004] | [验证: 停牌 mock 返回不触发；数据不足 mock 返回 limited 并按可用天数计算]`

**Checkpoint**: US4 验证通过——边界情况处理正确

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 设置页入口与端到端回归

- [ ] T015 [FE] Add volume_surge settings UI to `frontend/src/templates/alert_rules.html` with on/off toggle and window/multiplier/cooldown selectors  
  `[FR-009/FR-010 来源] | [依赖: T008] | [验证: 设置页可开关、可调整阈值并保存]`

- [ ] T016 [INT] Run full backend test suite (`tests/unit/`, `tests/integration/`) and validate `quickstart.md` manual flows  
  `[FR-001-FR-012] | [依赖: T007, T009, T013, T014, T015] | [验证: pytest 全量通过；curl 覆盖自动/手动/阈值/列表]`

- [ ] T017 [INT] Update `state.md` and finalize `tasks.md` checkboxes after all previous tasks complete  
  `[FR-001-FR-012] | [依赖: T016] | [验证: tasks.md 全部勾选；state.md 状态与当前任务一致]`

**Checkpoint**: F9 全量功能可演示

---

## Dependencies & Execution Order

### Phase Dependencies

| Phase | Depends On | Blocks |
|---|---|---|
| Phase 1 Setup | 无 | Phase 2 |
| Phase 2 Foundational | Phase 1 | Phase 3-6 |
| Phase 3 US1 | Phase 2 | Phase 7 |
| Phase 4 US2 | Phase 2 | Phase 7 |
| Phase 5 US3 | Phase 2 | Phase 7 |
| Phase 6 US4 | Phase 2 | Phase 7 |
| Phase 7 Polish | Phase 3-6 | 无 |

### Within-Phase Parallel Opportunities

- **Phase 2**: T002 schema、T003 model、T004 detector 可并行；T005 依赖 T003/T004
- **Phase 5**: T012 FE 组件 与 T010/T011 BE endpoint 可并行

### Story-to-Requirement Traceability

| Story | Primary FRs |
|---|---|
| US1 | FR-001, FR-002, FR-006, FR-007 |
| US2 | FR-009, FR-010, FR-012 |
| US3 | FR-003, FR-008 |
| US4 | FR-004 |

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1 + Phase 2
2. Complete Phase 3 (US1) — 核心自动检测推送
3. Complete Phase 4 (US2) — 阈值可配置
4. **STOP and VALIDATE**: 独立测试 US1 + US2

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → 自动检测推送可用
3. US2 → 阈值配置可用
4. US3 → Dashboard 展示与手动触发可用
5. US4 → 停牌/数据不足容错可用
6. Polish → 设置页 + 全量回归

---

## Notes

- 任务数量：17 条（符合 12-18 条要求）
- 所有任务可在 2-5 分钟内独立完成
- 不跨 Phase 提前实现
- TDD 由实现阶段执行；本 tasks.md 不预写测试文件路径
