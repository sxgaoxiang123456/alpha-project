# 实施进度 · 价格/涨跌幅预警

## 当前状态
✅ Feature 004 已收尾 — merged to develop, tag v0.1.0-004-price-alert

## 已完成 (18/18 tasks)

### Phase 1: 数据模型与 Schema
- [x] T1: AlertRule 模型 (CHECK 约束/Index/10 字段)
- [x] T2: AlertTrigger 模型 (FK→alert_rules)
- [x] T3: CooldownTracker 模型 (UNIQUE rule_id)
- [x] T4: Alert Pydantic schemas (Request/Response/Update/Trigger/CooldownStatus)

### Phase 2: 规则管理 (US-3)
- [x] T5: CRUD 路由 (POST/GET/PUT/DELETE /alerts, 50 条上限)
- [x] T6: 状态管理 (PATCH toggle + 股票移除自动暂停)

### Phase 3: 核心检测引擎 (US-1 + US-2)
- [x] T7: detect_alerts 核心 (规则加载→行情匹配→返回候选触发)
- [x] T8: 条件评估器 (5 种条件类型边界值覆盖)
- [x] T9: 已满足不触发逻辑 (last_evaluated_result 状态机)

### Phase 4: 冷却期与合并推送 (US-4)
- [x] T10: 冷却期检查 (is_in_cooldown + update_cooldown)
- [x] T11: 合并推送 (merge_triggers, 保留全部审计记录)
- [x] T12: 跨交易日冷却期重置 (reset_all_cooldowns)

### Phase 5: 集成与配置
- [x] T13: F3 QuoteScheduler 集成 (on_quotes_refreshed 回调)
- [x] T14: config.py + main.py 配置和路由注册

### Phase 6: 测试验证
- [x] T15: 检测引擎单元测试 (15 cases)
- [x] T16: 冷却期单元测试 (12 cases, freezegun)
- [x] T17: 规则 CRUD 单元测试 (37 cases 模型+schema+API)
- [x] T18: 集成测试 — 端到端 (16 cases)

## Code Review 修复 (2026-06-05)
- [x] FR-013: _run_alert_detection 数据源中断检测 (全 unavailable 时跳过)
- [x] falsy: _is_condition_satisfied 显式 None 检查替代 or 短路
- [x] merge_triggers: 保留全部 trigger 入库 (FR-012 审计)，仅标记合并关系
- [x] reset_all_cooldowns: 交易日变更时自动重置冷却期

## 后端结构性缺口补测 (backend-testing)
- [x] BE-G1: FK/UNIQUE/NOT NULL 约束违反测试 (4 cases)
- [x] BE-G2: 并发 50 条上限原子性验证 (2 cases, ThreadPoolExecutor)

## 基础设施修复
- [x] 5 处集成测试 module_clear 从精确匹配升级为前缀匹配 (test_watchlist_edit_delete / test_import_export / test_watchlist_api / test_concurrent_watchlist_limit / test_groups_api)
- [x] LEARNINGS.md 追加流程避坑复盘 (2 条 process-gap)

## 测试结果
324 passed, 0 regression failures (1 pre-existing flaky test unrelated)

## 新增文件
- `backend/app/models/alert_rule.py`
- `backend/app/models/alert_trigger.py`
- `backend/app/models/cooldown_tracker.py`
- `backend/app/schemas/alert.py`
- `backend/app/services/alert_service.py`
- `backend/app/routers/alerts.py`
- `backend/tests/unit/test_alert_models.py`
- `backend/tests/unit/test_alert_schemas.py`
- `backend/tests/unit/test_alert_service.py`
- `backend/tests/unit/test_cooldown.py`
- `backend/tests/unit/test_alert_constraints.py`
- `backend/tests/unit/test_alert_concurrency.py`
- `backend/tests/integration/test_alerts_api.py`

## 修改文件
- `backend/app/models/__init__.py` — 注册 3 个新模型
- `backend/app/schemas/__init__.py` — 注册 5 个新 schema
- `backend/app/config.py` — max_alert_rules / default_cooldown_minutes
- `backend/app/main.py` — 注册 alerts 路由 + _run_alert_detection 回调 + 跨交易日冷却期重置
- `backend/app/core/quote_scheduler.py` — on_quotes_refreshed 回调参数
- `backend/app/routers/watchlist.py` — pause_rules_for_stock 集成
- `LEARNINGS.md` — 2 条 process-gap
- 5 处集成测试 module_clear 模式修复

## 最后更新
2026-06-05
