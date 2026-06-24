# Tasks: F8 自然语言设预警

**Input**: Design documents from `/specs/010-natural-language-alert/`  
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [data-model.md](data-model.md), [contracts/api.md](contracts/api.md), [quickstart.md](quickstart.md)

---

## Format

- `[P]`：可与其他 [P] 任务并行执行（无文件/依赖冲突）
- `[USx]`：所属用户故事
- 描述中末尾标注：`[FR-xxx 来源] | [依赖: Txxx] | [验证: xxx]`

---

## Phase 1: Setup

**Purpose**: 创建 LLM 兜底 Prompt 模板

- [x] T001 [BE] Create `backend/app/templates/prompts/nl_alert.j2` with system role, parsing instructions, condition type mapping and structured JSON output format  
  `[FR-001/FR-002/FR-003/FR-004 来源] | [依赖: 无] | [验证: 模板可渲染，输出包含 stock_code/condition_type/threshold/confidence 占位符]`

---

## Phase 2: Foundational

**Purpose**: 核心基础设施：schema、规则解析器、股票匹配、LLM 兜底编排  
**⚠️ CRITICAL**: 本阶段完成前不可开始 user story 实现

- [x] T002 [P] [BE] Create `backend/app/schemas/nl_alert.py` with `NaturalLanguageAlertRequest`, `NaturalLanguageAlertResponse`, `StockCandidate`, `AlertRuleSummary` schemas  
  `[FR-010/FR-013 来源] | [依赖: 无] | [验证: schema 实例化通过，候选列表字段校验生效]`

- [x] T003 [P] [BE] Create `backend/app/services/rule_based_parser.py` to extract stock/condition_type/threshold and compute per-dimension confidence from core Chinese patterns  
  `[FR-002/FR-003/FR-004/FR-006 来源] | [依赖: 无] | [验证: 输入「茅台跌破1500」返回 price_below/1500/置信度1.0]`

- [x] T004 [P] [BE] Extend `backend/app/services/stock_search.py` to return sorted candidate list (match_score desc, then market_cap desc) with `sector` and `market_cap` fields  
  `[FR-005 来源] | [依赖: 无] | [验证: 输入「银行」返回至少2只候选，按规则排序]`

- [x] T005 [BE] Create `backend/app/services/nl_alert_parser.py` orchestrating `RuleBasedParser` → LLM fallback via `BriefingLLMClient` → normalized `ParsedAlertIntent`  
  `[FR-001/FR-006/FR-007 来源] | [依赖: T001, T003] | [验证: mock 规则命中返回高置信度；mock 规则未命中调用 LLM；mock LLM 失败返回低置信度降级]`

**Checkpoint**: Foundation ready — 解析器可独立运行并返回结构化意图或降级标记

---

## Phase 3: User Story 1 — 一句话创建价格预警（Priority: P1） 🎯 MVP

**Goal**: 用户输入标准自然语言指令，3 秒内成功创建价格/涨跌幅预警规则  
**Independent Test**: `curl` 调用标准句式，返回 success=true 与规则摘要

- [x] T006 [US1] [BE] Create `backend/app/routers/alerts_nl.py` with `POST /alerts/natural-language` endpoint (input validation → parse → rule validation → create AlertRule)  
  `[FR-008/FR-009/FR-010/FR-011 来源] | [依赖: T002, T005] | [验证: 200 返回成功创建 price_above/price_below/change_pct_above/change_pct_below]`

- [x] T007 [US1] [BE] Register `alerts_nl_router` in `backend/app/main.py` under `/alerts/natural-language`  
  `[FR-012 来源] | [依赖: T006] | [验证: 服务启动后 endpoint 可访问]`

- [x] T008 [P] [US1] [FE] Create `frontend/src/templates/components/nl_alert_input.html` with input box, submit button and result/candidate container  
  `[FR-012 来源] | [依赖: 无] | [验证: 组件独立渲染，占位文案为中文]`

- [x] T009 [P] [US1] [FE] Integrate `nl_alert_input` component into `frontend/src/templates/dashboard.html`, `watchlist.html` and `alert_rules.html`  
  `[FR-012 来源] | [依赖: T008] | [验证: 三个页面均可见独立输入框]`

- [x] T010 [US1] [INT] Validate standard natural language alert creation via backend unit/integration tests and `quickstart.md` curl commands  
  `[FR-001-FR-013] | [依赖: T006, T007, T009] | [验证: pytest 通过；curl 返回 success=true]`

**Checkpoint**: US1 完整闭环——标准句式可解析、可创建、前端入口可见

---

## Phase 4: User Story 2 — 处理股票名称歧义（Priority: P1）

**Goal**: 歧义名称返回候选列表，用户选择后自动完成创建  
**Independent Test**: 输入「银行跌破10元」，返回 candidates；选择后成功创建

- [x] T011 [US2] [BE] Implement ambiguity candidate response and `selected_stock_code` auto-resubmit support in `backend/app/services/nl_alert_parser.py` and `backend/app/routers/alerts_nl.py`  
  `[FR-005/FR-013 来源] | [依赖: T004, T006] | [验证: 输入歧义名称返回 candidates；携带 selected_stock_code 后成功创建]`

- [x] T012 [US2] [FE] Render candidate list and auto-resubmit UI in `frontend/src/templates/components/nl_alert_input.html` and validate ambiguity flow in browser  
  `[FR-005/FR-013 来源] | [依赖: T008, T011] | [验证: 点击候选后自动重提交并显示创建成功]`

**Checkpoint**: US2 验证通过——歧义交互闭环

---

## Phase 5: User Story 3 — 拒绝低置信度解析（Priority: P2）

**Goal**: 无法确定意图时明确拒绝并引导重试/手动配置  
**Independent Test**: 输入「帮我看着点茅台」，返回 success=false 与明确提示

- [x] T013 [US3] [BE] Implement confidence threshold guard in `backend/app/services/nl_alert_parser.py` and map low-confidence response in `backend/app/routers/alerts_nl.py`, validate rejection  
  `[FR-006 来源] | [依赖: T005, T006] | [验证: 输入模糊语句返回 success=false 与手动配置引导]`

**Checkpoint**: US3 验证通过——低置信度不创建规则

---

## Phase 6: User Story 4 — 不支持条件类型的提示（Priority: P2）

**Goal**: 识别到成交量等不支持条件时给出明确提示  
**Independent Test**: 输入「茅台成交量突破10万手」，返回暂不支持成交量

- [x] T014 [US4] [BE] Implement unsupported condition detection in `backend/app/services/rule_based_parser.py` and LLM prompt, add error message in `backend/app/routers/alerts_nl.py`, validate response  
  `[FR-007 来源] | [依赖: T003, T005, T006] | [验证: 输入成交量条件返回 success=false 与「暂不支持成交量条件」]`

**Checkpoint**: US4 验证通过——不支持条件明确拒绝

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 端到端回归与文档收尾

- [ ] T015 [INT] Run full backend test suite (`tests/unit/`, `tests/integration/`) and validate `quickstart.md` manual flows  
  `[FR-001-FR-013] | [依赖: T010, T012, T013, T014] | [验证: pytest 全量通过；curl 覆盖标准/歧义/低置信度/不支持条件]`

- [ ] T016 [INT] Update `state.md` and finalize `tasks.md` checkboxes after all previous tasks complete  
  `[FR-001-FR-013] | [依赖: T015] | [验证: tasks.md 全部勾选；state.md 状态与当前任务一致]`

**Checkpoint**: F8 全量功能可演示

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
| Phase 6 US4 | Phase 3 | Phase 7 |
| Phase 7 Polish | Phase 3-6 | 无 |

### Within-Phase Parallel Opportunities

- **Phase 2**: T002 schema、T003 RuleBasedParser、T004 StockResolver 可并行；T005 依赖 T001/T003
- **Phase 3**: T008 FE 组件 与 T006/T007 BE endpoint 可并行
- **Phase 4-6**: 在 US1 完成后可独立推进

### Story-to-Requirement Traceability

| Story | Primary FRs |
|---|---|
| US1 | FR-001, FR-002, FR-003, FR-004, FR-008, FR-009, FR-010, FR-011, FR-012 |
| US2 | FR-005, FR-013 |
| US3 | FR-006 |
| US4 | FR-007 |

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1 + Phase 2
2. Complete Phase 3 (US1) — 核心标准句式创建
3. Complete Phase 4 (US2) — 歧义候选闭环
4. **STOP and VALIDATE**: 独立测试 US1 + US2

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → 标准句式创建可用
3. US2 → 歧义处理可用
4. US3 → 低置信度拒绝可用
5. US4 → 不支持条件提示可用
6. Polish → 全量回归 + 文档收尾

---

## Notes

- 任务数量：16 条（符合 12-18 条要求）
- 所有任务可在 2-5 分钟内独立完成
- 不跨 Phase 提前实现
- TDD 由实现阶段执行；本 tasks.md 不预写测试文件路径
