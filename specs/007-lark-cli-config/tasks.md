# Tasks: 飞书 lark-cli 环境配置

**Input**: Design documents from `/specs/007-lark-cli-config/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: 本项目要求 TDD；每个用户故事的测试任务必须先写并确认失败，再进行实现任务。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] [BE|FE|INT] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- **[BE]/[FE]/[INT]**: Backend, frontend, or integration/documentation validation task
- Every task includes exact file paths

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the implementation environment without changing feature behavior.

- [x] T001 [BE] Verify backend environment using `backend/setup.sh` before implementation work in `backend/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared Feishu runtime configuration before user-story implementation.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T002 [P] [BE] Add failing tests for Feishu env fields, optional `FEISHU_BRAND` default `feishu`, and completeness rules in `backend/tests/unit/test_config_database_main.py`
- [x] T003 [BE] Add Feishu runtime config fields, optional brand default, and completeness helper in `backend/app/config.py`

**Checkpoint**: Runtime config can represent complete/incomplete Feishu `.env` state without exposing secret values.

---

## Phase 3: User Story 1 - 使用 .env 配置飞书主通道 (Priority: P1) 🎯 MVP

**Goal**: When Feishu app credentials and chat id are complete in `.env`, the system uses Feishu as the primary push channel and records the send result.

**Independent Test**: With test-provided Feishu env variables and a monkeypatched Feishu client, trigger a push and verify the runtime factory creates the Feishu primary channel; with incomplete env variables, verify no legacy webhook is used.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**

- [x] T004 [US1] [BE] Add failing `_push_service_factory()` wiring tests for complete required env, missing required env, missing optional `FEISHU_BRAND` defaulting to `feishu`, and ignored `lark_webhook` in `backend/tests/unit/test_config_database_main.py`
- [x] T005 [P] [US1] [BE] Add failing alert-to-push integration test for Feishu-primary dispatch in `backend/tests/integration/test_full_chain_alert_to_push.py`

### Implementation for User Story 1

- [x] T006 [US1] [BE] Instantiate `FeishuClient` from complete required Feishu env config, default `FEISHU_BRAND` to `feishu`, and preserve Telegram wiring in `backend/app/main.py`
- [x] T007 [US1] [INT] Run US1 focused checks from `backend/tests/unit/test_config_database_main.py` and `backend/tests/integration/test_full_chain_alert_to_push.py`

**Checkpoint**: User Story 1 works independently: Feishu env config controls primary-channel creation and historical webhook config is ignored.

---

## Phase 4: User Story 2 - 设置页不再误导用户填写 webhook (Priority: P1)

**Goal**: The settings page no longer collects Feishu webhook, clearly explains Feishu is configured by `.env`, and keeps Telegram/settings saves unchanged.

**Independent Test**: Open settings page and verify no Feishu webhook input exists; submit settings with Telegram and preference fields and verify no `lark_webhook` is created or updated.

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**

- [x] T008 [P] [US2] [BE] Add failing GET/POST settings tests for no webhook input, env status text, no secret output, and ignored `lark_webhook` in `backend/tests/integration/test_settings.py`

### Implementation for User Story 2

- [x] T009 [US2] [BE] Remove active Feishu webhook save handling and add non-sensitive Feishu status context in `backend/app/routers/settings.py`
- [x] T010 [US2] [FE] Replace Feishu webhook input with read-only `.env` status and restart/reload hint in `frontend/src/templates/settings.html`
- [x] T011 [US2] [INT] Run settings-page validation from `backend/tests/integration/test_settings.py` and inspect rendered template behavior in `frontend/src/templates/settings.html`

**Checkpoint**: User Story 2 works independently: settings UI points users to `.env`, does not expose secrets, and does not save webhook values.

---

## Phase 5: User Story 3 - 保持现有推送降级与日志体验 (Priority: P2)

**Goal**: Missing config, Feishu send failure, or missing `lark-cli` continues to use existing Telegram fallback and local push-log diagnostics without breaking other functions.

**Independent Test**: Simulate missing Feishu config, Feishu client failure, missing `lark-cli`, Telegram available/unavailable, and verify push logs and fallback states remain consistent.

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.**

- [x] T012 [P] [US3] [BE] Add failing `lark-cli` unavailable and secret-redaction tests in `backend/tests/unit/test_feishu_client.py`
- [x] T013 [P] [US3] [BE] Add failing Feishu-failure Telegram-fallback and push-log reason regression tests in `backend/tests/unit/test_push_service.py`
- [x] T014 [P] [US3] [INT] Add regression coverage for missing Feishu config and local log fallback in `backend/tests/e2e/test_full_chain.py`

### Implementation for User Story 3

- [x] T015 [US3] [BE] Preserve or minimally adjust Feishu client failure classification without leaking secrets in `backend/app/services/feishu_client.py`
- [x] T016 [US3] [INT] Run fallback/log regression checks from `backend/tests/unit/test_feishu_client.py`, `backend/tests/unit/test_push_service.py`, and `backend/tests/e2e/test_full_chain.py`

**Checkpoint**: User Story 3 works independently: Feishu failures are diagnosable, Telegram fallback remains available, and logs do not leak secrets.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Update user-facing deployment documentation and run the final regression loop.

- [x] T017 [INT] Update Feishu/Telegram push-channel configuration documentation in `README.md`
- [x] T018 [INT] Run full backend regression suite defined by `backend/tests/` and verify quickstart expectations in `specs/007-lark-cli-config/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion; blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion; MVP slice.
- **User Story 2 (Phase 4)**: Depends on Foundational completion; can run after or in parallel with US1 if file conflicts are managed.
- **User Story 3 (Phase 5)**: Depends on Foundational completion and benefits from US1 factory wiring.
- **Polish (Phase 6)**: Depends on desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Requires Feishu runtime config foundation; no dependency on US2.
- **US2 (P1)**: Requires Feishu runtime config status; no dependency on US1 send success.
- **US3 (P2)**: Depends on Feishu runtime wiring behavior from US1 for complete fallback/log validation.

### Within Each User Story

- Tests MUST be written and observed failing before implementation.
- Runtime config before factory wiring.
- Router context before template rendering changes.
- Feishu client error classification before fallback/log validation.
- Each story checkpoint must pass before moving to the next priority unless explicitly parallelized.

### Parallel Opportunities

- T002 can run independently before T003.
- T005 can run in parallel with T004 because it edits a different test file.
- T008 can run in parallel with US1 tests after Foundational completion.
- T012, T013, and T014 can run in parallel because they target different test files.
- T017 can run after implementation decisions are stable and does not block backend tests.

---

## Parallel Example: User Story 1

```bash
# Parallel test authoring after Foundational phase:
Task: "Add _push_service_factory wiring tests in backend/tests/unit/test_config_database_main.py"
Task: "Add alert-to-push Feishu-primary integration test in backend/tests/integration/test_full_chain_alert_to_push.py"
```

## Parallel Example: User Story 2

```bash
# Backend route tests and frontend template implementation can be split after the expected context shape is agreed:
Task: "Add settings route tests in backend/tests/integration/test_settings.py"
Task: "Replace Feishu webhook input in frontend/src/templates/settings.html"
```

## Parallel Example: User Story 3

```bash
# Failure-mode tests target separate files:
Task: "Add lark-cli unavailable tests in backend/tests/unit/test_feishu_client.py"
Task: "Add fallback regression tests in backend/tests/unit/test_push_service.py"
Task: "Add full-chain missing-config regression in backend/tests/e2e/test_full_chain.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete US1 tests T004-T005 and confirm they fail.
3. Implement T006.
4. Run T007 and validate Feishu env config creates the primary channel while incomplete env does not use webhook.

### Incremental Delivery

1. Deliver US1 to restore Feishu main-channel runtime wiring.
2. Deliver US2 to remove misleading webhook UI and protect settings saves.
3. Deliver US3 to prove fallback, local logs, and runtime-missing diagnostics still behave correctly.
4. Finish with README and full regression checks.

### Scope Guardrails

- Do not edit existing feature documents under `specs/001-*` through `specs/006-*`.
- Do not read or print real `.env` secret values.
- Do not migrate or delete historical `lark_webhook` database records.
- Do not change Telegram configuration source or behavior.
- Do not introduce trading, multi-user, paid service, or unrelated Dashboard changes.
