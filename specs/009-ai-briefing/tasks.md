# Tasks: F7 AI 早盘简报

**Input**: Design documents from `/specs/009-ai-briefing/`  
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [data-model.md](data-model.md), [contracts/api.md](contracts/api.md), [quickstart.md](quickstart.md)

---

## Format

- `[P]`：可与其他 [P] 任务并行执行（无文件/依赖冲突）
- `[USx]`：所属用户故事
- 描述中末尾标注：`[FR-xxx 来源] | [依赖: Txxx] | [验证: xxx]`

---

## Phase 1: Setup

**Purpose**: 创建 Prompt 模板文件和目录结构

- [x] T001 [BE] Create `backend/app/templates/prompts/briefing.j2` with system role, data input slots and structured output instructions  
  `[FR-005 来源] | [依赖: 无] | [验证: 模板文件可渲染，输出包含大盘/异动/解读占位符]`

---

## Phase 2: Foundational

**Purpose**: 核心基础设施：schema、Prompt 加载、LLM 客户端  
**⚠️ CRITICAL**: 本阶段完成前不可开始 user story 实现

- [x] T002 [BE] [P] Create `backend/app/schemas/briefing.py` with `BriefingResponse`, `TopMover`, `BriefingGenerateRequest` schemas  
  `[FR-006 来源] | [依赖: 无] | [验证: schema 实例化通过，必填字段校验生效]`

- [x] T003 [BE] [P] Create `backend/app/services/prompt_loader.py` to load and render `briefing.j2` with provided market data  
  `[FR-005 来源] | [依赖: T001] | [验证: 给定测试数据，输出字符串包含大盘指数和异动 TOP 5]`

- [x] T004 [BE] Create `backend/app/services/briefing_llm_client.py` with timeout (30s), retry (2 times, 5s interval), structured output parsing and degradation flag  
  `[FR-005/FR-008/FR-011 来源] | [依赖: T003] | [验证: mock LLM 成功返回解析后的 dict；mock 失败 3 次返回 is_degraded=True]`

**Checkpoint**: Foundation ready — LLM 客户端可独立运行并返回结构化结果或降级标记

---

## Phase 3: User Story 1 — 交易日自动接收 AI 简报 (Priority: P1) 🎯 MVP

**Goal**: 每个交易日 8:50 自动生成并推送含大盘指数、异动 TOP 5 和 AI 解读的简报  
**Independent Test**: 模拟交易日运行简报生成任务，飞书/Telegram 收到完整卡片/文本

- [x] T005 [BE] [US1] Create `backend/app/services/top_mover_service.py` to compute top 5 movers from watchlist first, then all-market fallback; handle insufficient history  
  `[FR-004 来源] | [依赖: T002] | [验证: 输入 10 只自选股返回 5 条 TopMover；输入 2 只自选股返回 2 自选 + 3 全市场]`

- [x] T006 [BE] [US1] Create `backend/app/services/briefing_service.py::generate()` orchestrating data fetch → top movers → LLM → briefing result  
  `[FR-001/FR-002/FR-003/FR-006 来源] | [依赖: T004, T005] | [验证: mock 交易日生成 briefing dict，包含 market_indices/top_movers/insights 且 is_degraded=False]`

- [x] T007 [BE] [US1] Update `backend/app/core/quote_scheduler.py` `send_briefing_if_trading_day()` to call `BriefingService.generate()` and pass result to `PushService`  
  `[FR-001/FR-007 来源] | [依赖: T006] | [验证: 启动服务后 8:50 定时任务执行，PushLog 新增 briefing 记录]`

- [x] T008 [BE] [US1] Ensure `backend/app/services/push_service.py` renders `briefing` message with market indices and top movers (extend if needed)  
  `[FR-007 来源] | [依赖: T006] | [验证: PushMessageRequest(message_type="briefing") 成功渲染并发送（mock 通道）]`

**Checkpoint**: US1 完整闭环——交易日自动生成、LLM 解读、推送成功

---

## Phase 4: User Story 2 — LLM 失败时收到降级简报 (Priority: P1)

**Goal**: LLM 连续失败时发送模板简报，状态标记降级  
**Independent Test**: mock LLM 失败，确认仍收到模板简报且 PushLog 含降级标记

- [x] T009 [BE] [US2] Implement degradation path in `BriefingService.generate()`: when `BriefingLLMClient` returns degraded, build template-only briefing without AI insights  
  `[FR-008 来源] | [依赖: T006] | [验证: mock LLM 失败 3 次，返回 briefing.is_degraded=True 且 insights 为空/None，top_movers 仍完整]`

- [x] T010 [BE] [US2] Update `BriefingService` to pass degraded reason to `PushService` and log `degraded_reason` in `PushLog` metadata  
  `[FR-009 来源] | [依赖: T009] | [验证: 降级简报推送后，PushLog 记录 status=sent 且 content 含 "模板降级" 或 degraded 标记]`

**Checkpoint**: US2 验证通过——LLM 失败不影响简报触达

---

## Phase 5: User Story 3 — 非交易日跳过生成 (Priority: P2)

**Goal**: 非交易日不调用 LLM、不推送、仅记录日志  
**Independent Test**: 设置非交易日日期，确认 8:50 任务跳过

- [x] T011 [BE] [US3] Add non-trading-day guard in `BriefingService.generate()` and `send_briefing_if_trading_day()` to skip generation and write log  
  `[FR-002 来源] | [依赖: T006] | [验证: 非交易日调用 generate() 返回 None 且不调用 LLM，日志含 "非交易日跳过"]`

**Checkpoint**: US3 验证通过——非交易日零 LLM 调用

---

## Phase 6: User Story 4 — 手动刷新简报 (Priority: P2)

**Goal**: Dashboard 提供手动刷新入口，30 秒冷却期  
**Independent Test**: 点击按钮后 60 秒内收到新简报，30 秒内重复点击被拦截

- [x] T012 [BE] [P] [US4] Create `backend/app/routers/briefing.py` with `POST /api/briefing/generate` endpoint (validates cooldown, trading day, triggers background task)  
  `[FR-010/FR-012 来源] | [依赖: T006, T011] | [验证: 200 触发成功；429 冷却期；422 非交易日；测试覆盖]`

- [x] T013 [BE] [P] [US4] Add `GET /api/briefing/latest` endpoint in `backend/app/routers/briefing.py` to return cached latest briefing  
  `[FR-010 来源] | [依赖: T006] | [验证: 缓存命中返回 briefing；未生成返回 404]`

- [x] T014 [BE] [US4] Register `briefing_router` in `backend/app/main.py`  
  `[FR-010 来源] | [依赖: T012, T013] | [验证: 服务启动后 /api/briefing/generate 和 /api/briefing/latest 可访问]`

- [ ] T015 [FE] [US4] Update `frontend/src/templates/dashboard.html` to add「重新生成简报」button with cooldown UI and wire JS to call `POST /api/briefing/generate`  
  `[FR-010 来源] | [依赖: T014] | [验证: 点击按钮后页面显示刷新中/成功/冷却中状态]`

**Checkpoint**: US4 验证通过——手动刷新可控、有冷却、有反馈

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 前端展示完善与端到端回归

- [ ] T016 [FE] [P] Update `frontend/src/templates/components/briefing_card.html` to display `insights` and `top_movers` with A-share red/green semantics  
  `[FR-006 来源] | [依赖: T015] | [验证: Dashboard 渲染最新简报，涨红跌绿，点击「查看详情」按钮可用]`

- [ ] T017 [INT] Run full backend test suite (`tests/unit/`, `tests/integration/`) and validate `quickstart.md` manual trigger flow  
  `[FR-001-FR-013] | [依赖: T007-T016] | [验证: pytest 全量通过；curl /api/briefing/generate 触发并在 /api/briefing/latest 看到结果]`

**Checkpoint**: F7 全量功能可演示

---

## Dependencies & Execution Order

### Phase Dependencies

| Phase | Depends On | Blocks |
|---|---|---|
| Phase 1 Setup | 无 | Phase 2 |
| Phase 2 Foundational | Phase 1 | Phase 3-6 |
| Phase 3 US1 | Phase 2 | Phase 7 |
| Phase 4 US2 | Phase 3 | Phase 7 |
| Phase 5 US3 | Phase 3 | Phase 7 |
| Phase 6 US4 | Phase 3, Phase 5 | Phase 7 |
| Phase 7 Polish | Phase 3-6 | 无 |

### Within-Phase Parallel Opportunities

- **Phase 2**: T002 schema 与 T003 PromptLoader 可并行；T004 依赖 T003
- **Phase 3**: T005 TopMover 与 T006 BriefingService 内部可拆分，但 T006 依赖 T005
- **Phase 6**: T012 POST endpoint 与 T013 GET endpoint 可并行
- **Phase 7**: T016 FE 与 T017 测试不能并行（测试依赖 FE 完成）

### Story-to-Requirement Traceability

| Story | Primary FRs |
|---|---|
| US1 | FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007 |
| US2 | FR-008, FR-009 |
| US3 | FR-002 |
| US4 | FR-010, FR-011, FR-012, FR-013 |

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1 + Phase 2
2. Complete Phase 3 (US1) — 核心交易日自动简报
3. Complete Phase 4 (US2) — LLM 降级兜底
4. **STOP and VALIDATE**: 独立测试 US1 + US2

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → 自动简报推送可用
3. US2 → 降级保护可用
4. US3 → 非交易日跳过可用
5. US4 → 手动刷新可用
6. Polish → 前端展示 + 全量回归

---

## Notes

- 任务数量：17 条（符合 12-18 条要求）
- 所有任务可在 2-5 分钟内独立完成
- 不跨 Phase 提前实现
- TDD 由实现阶段执行；本 tasks.md 不预写测试文件路径
