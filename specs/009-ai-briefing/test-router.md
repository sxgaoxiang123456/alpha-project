# 009-ai-briefing 收尾测试路由报告

> 生成时间：2026-06-23
> 对应 commit：`4f2edcc` (docs(009-011): 统一 v1.1 LLM 方案为 DeepSeek-V4-Flash 并配置环境变量)
> 方法论遵循 `testing-system-blueprint` skill

---

## 1. 本 feature 判定属于哪一类

**主类：完整功能链路**
**次类：局部前后端、单后端、单前端**

判类依据：

- 任务标签分布：`[BE]` 占 14 条（T001–T014）、`[FE]` 2 条（T015、T016）、`[INT]` 1 条（T017）。
- 本 feature 在依赖拓扑上补全了一条跨 feature 的用户旅程：
  `APScheduler 8:50 → QuoteScheduler（等待行情刷新）→ MarketIndex/Quote/历史行情/Alert 数据准备 → TopMoverService → PromptLoader → BriefingLLMClient（DeepSeek）→ BriefingService → PushService → 飞书/Telegram 推送 + Redis/SQLite 缓存 → Dashboard GET /api/briefing/latest`。
- 同一 feature 内还有一条前端↔后端切片：`Dashboard 手动刷新按钮 → POST /api/briefing/generate → 后端后台生成 → 前端轮询 /api/briefing/latest → UI 更新`。
- 因此主类归为「完整功能链路」，手动刷新入口归为「局部前后端」，后端服务与前端卡片分别归「单后端」「单前端」。

---

## 2. 路由去向

| 类别 | 路由去向 | 状态 |
|---|---|---|
| 单后端 | → `backend-testing` skill（按 Python/FastAPI 栈实例化具体工具） | ✅ 执行器已建 |
| 单前端 | → `frontend-testing` skill（接成熟工具 + 配置 + 翻译视觉契约） | ✅ 执行器已建 |
| 局部前后端 | → `fullstack-slice-testing` skill（起真栈 + 接缝断言） | ✅ 执行器已建 |
| 完整功能链路 | → `full-chain-testing` skill（挖通路 + 全系统编排 + 异步/时间/跨通道编排驱动） | ✅ 执行器已建 |
| 跨模块契约（候选类） | → 对应类别 skill | 🔧 占位·待建 |

---

## 3. 是否补全了某条完整功能链路

**是。** 本 feature 让以下跨 feature 旅程首次端到端可达：

> 交易日 8:50 定时触发 → 行情刷新等待 → 大盘/自选股/历史行情/预警数据聚合 → LLM 生成解读 → 简报推送（飞书/Telegram）+ 缓存 → Dashboard 展示最新简报 / 手动刷新入口。

建议把这条旅程作为 `full-chain-testing`「通路挖掘」的起点，只取最高优先级的一小撮 P0 路径做安全网（非穷举）。

---

## 4. 逐类待补清单

### 单后端 → `backend-testing`

| 判定维度 | 覆盖状态 | 说明 / 路由 |
|---|---|---|
| 基础单元（BriefingService、TopMoverService、BriefingLLMClient、PromptLoader、schema） | ✅ 已被 TDD 覆盖 | `test_briefing_service.py`、`test_top_mover_service.py`、`test_briefing_llm_client.py`、`test_prompt_loader.py`、`test_briefing_schemas.py` 已覆盖 |
| 韧性 / 超时 / 降级（LLM 失败、60s 总超时、数据源 fallback） | 🔧 结构性缺口 | 单元测试使用 mock，未对真实 HTTP 边界做故障注入。路由到 `backend-testing`，按栈用 `respx` / `pytest-httpx` 等注入超时/异常序列；现成 ✅ |
| 并发 / 限频原子性（30s 冷却、同一分钟内不重复生成） | ✅ 已决策：轻量版 | 确认做轻量版并发测试：并发发送两个 `POST /api/briefing/generate`，断言至少有一个返回 429 或后端只生成一次简报。路由到 `backend-testing`；现成 ✅ |
| 真库 / 迁移 / 约束 | — | 本 feature 未新增持久化表，仅使用运行时缓存与既有 `HistoricalQuote` / `AlertTrigger`，无需额外迁移测试 |
| 对象级越权（BOLA·BFLA） | — | 单用户架构，无特权接口，不适用 |

### 局部前后端 → `fullstack-slice-testing`

| 判定维度 | 覆盖状态 | 说明 / 路由 |
|---|---|---|
| ① 环境编排（前端 + 后端 + 依赖真实同起） | ✅ 已被 E2E 覆盖 | `full_chain_stack` fixture 已能拉起真后端 + 浏览器前端 |
| ② 契约真实性（API 响应 shape vs 前端解析） | 🔧 结构性缺口 | 契约写在 `contracts/api.md`，但无消费者 mock ↔ 真提供者对账 / OpenAPI diff。路由到 `fullstack-slice-testing` |
| ③ 接缝粘合（错误态 → UI / 冷却中提示 / 非交易日提示 / 轮询超时） | 🔧 结构性缺口 | 现有测试未点击「重新生成简报」按钮并断言冷却/成功/错误态 UI。路由到 `fullstack-slice-testing` |
| ④ 真实时序 / 实时 | 🔧 结构性缺口 | 手动刷新后前端轮询 `/api/briefing/latest` 是异步路径，现有 E2E 未覆盖。路由到 `fullstack-slice-testing`，用 poll-retry 断言 |

### 单前端 → `frontend-testing`

| 判定维度 | 覆盖状态 | 说明 / 路由 |
|---|---|---|
| L0/L1 测试地基 | 🔧 结构性缺口 | 项目无前端组件/单元测试运行器，前端改动仅靠 E2E 与手测。路由到 `frontend-testing` 立地基 |
| L2 视觉回归（像素 / 深色 / A-share 红绿契约） | ✅ 已被 E2E 覆盖 | `tests/e2e/visual_baselines/dashboard_after_load.png` 已随本 feature 更新并回归通过 |
| L3 可访问性 a11y | ✅ 已被 E2E 覆盖 | `test_dashboard_no_critical_a11y_violations` 等会扫到 Dashboard 新增按钮与弹窗 |
| L4 跨浏览器 + 响应式 | ✅ 已被 E2E 覆盖 | `TestResponsive` 已覆盖多 viewport |
| L6 前后端契约 mock | 🔧 结构性缺口 | 前端未用 MSW / 契约生成 mock，单独前端开发依赖真后端。路由到 `frontend-testing`（可降级或延后） |
| 设计 token / 硬编码颜色 | ✅ 走 lint 门 | 卡片使用 Tailwind token，未引入硬编码色值（由 code review / lint 覆盖） |

### 完整功能链路 → `full-chain-testing`

| 判定维度 | 覆盖状态 | 说明 / 路由 |
|---|---|---|
| ① 通路挖掘 | ✅ 已被 spec/plan 文档化 | 端到端路径在 `spec.md`、`plan.md`、`data-model.md` 中已明确 |
| ② 关键性分级 + 选少（P0 安全网） | ✅ 已决策 | 选定 P0 路径：P0-1 正常交易日自动简报完整链路、P0-2 LLM 降级仍推送模板简报、P0-3 非交易日零触发。手动刷新相关路径（P0-4/P0-5）暂不纳入完整功能链路测试，由局部前后端切片覆盖。 |
| ③ 全系统编排 + 外部边界 stub | ✅ 已补齐 | 新增 `backend/tests/e2e/test_full_chain_briefing.py`：Redis 容器 + 临时 SQLite + 真实 uvicorn 进程同起；DeepSeek 在 P0-2 用本地 503 桩，飞书/Telegram 用空 env stub |
| ④ 异步 / 时间 / 跨通道贯穿 | ✅ 已补齐 | 用子进程手动触发 `QuoteScheduler.send_briefing_if_trading_day()` 编排驱动 cron 跳步；P0-2/P0-3 覆盖降级与非交易日分支；全程 poll-retry，无 sleep |
| ⑤ journey 级可追溯 + 安全网定位 | ✅ 已补齐 | 每条 P0 旅程按 TR-009-FC-001~006 编号，断言覆盖 cron→生成→缓存→PushLog→Dashboard 每个交接点 |

### 跨模块契约（候选可增类）

| 判定维度 | 覆盖状态 | 说明 / 路由 |
|---|---|---|
| API 契约生产者 ↔ 消费者漂移 | 🔧 结构性缺口 | `contracts/api.md` 存在，但无 codegen / diff / 消费者回归。消费者为 Dashboard 前端；缓存 schema 消费者为 `DashboardService`。路由到跨模块契约执行器（🔧 占位·待建） |

---

## 5. 状态标注

- ✅ 已决策并更新至本报告（P0 路径、并发测试范围）
- ✅ 完整功能链路结构性缺口已补齐（TR-009-FC-001~006，E2E 全绿）
- 🔧 跨模块契约执行器 skill 尚未建立，当前为占位状态

> **边界提醒**：本报告仅做判类与路由；具体工具由被路由到的执行器 skill 按项目技术栈实例化。测试是否真实编写与通过，由 CI 闸与护栏化自愈 agent 等确定性机制负责验证，本 skill 不替代它们。
