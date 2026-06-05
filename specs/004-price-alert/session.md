# 会话交接 · 价格/涨跌幅预警

## 上次做到哪
Feature 004 已全部完成。18 个 task 全绿（324 tests passed），已 merge 到 develop，tag v0.1.0-004-price-alert。

## 工作流改进教训
1. **Code Review 不可跳过**：TDD GREEN ≠ 架构无缺口。review 必须在 merge 前做，已在 LEARNINGS 追加 process-gap 记录。
2. **receiving-code-review 不可跳过**：不只是质疑工具，核心产出是逐条评估表（接受/有意识选择/push back）。已在 LEARNINGS 追加记录。
3. 详见 `LEARNINGS.md` 新增两条 process-gap。

## 交付内容

### 业务功能
- 5 种预警条件类型：price_above/below, change_pct_above/below, volume_above
- 规则 CRUD API + 50 条上限 + toggle 状态管理
- 冷却期机制（持久化到 CooldownTracker，跨交易日自动重置）
- 同股票多规则触发自动合并（保留审计记录）
- 已满足不触发状态机（FR-010）
- 股票移除 → 自动暂停关联规则（FR-014）
- 数据源中断时跳过检测（FR-013）

### 集成点
- **上游**：F3 quote_scheduler.refresh_if_trading_day() → _run_alert_detection() 回调
- **下游**：AlertTrigger(push_status="pending") 入库 → 等待 F5 推送 feature 消费
- **展示**：/alerts API → F6 Dashboard

### 尚未贯通的链路
- F3→F4→F5（推送通知）: F5 尚未实现，AlertTrigger 的 push_status 永远为 "pending"
- 等 F5 完成后建议路由到 `full-chain-testing` 做端到端安全网验证

## 下次开发 F5 时的注意事项
1. F5 推送通知需读取 AlertTrigger 表（push_status="pending"）+ 按 merged_rule_ids 合并推送
2. push_status 流转：pending → sent / failed
3. 推送级别区分：alert 级 = 强提醒，watch 级 = 标准推送
4. 不要重复推送同一 trigger（用 push_status 状态机防重）
5. F5 完成后：F3→F4→F5 首次全链路贯通 → 路由到 `full-chain-testing` 补端到端安全网

## 禁止重新规划
plan.md / tasks.md 已完成，spec 目录冻结。后续新增预警相关功能请新开 feature 编号。
