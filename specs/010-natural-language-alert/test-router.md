# 测试路由报告：010-natural-language-alert（F8 自然语言设预警）

> **边界声明**：本报告只做判类与路由；具体工具由对应类别 skill 按栈实例化，CI 闸和护栏化 agent 才负责验证。

---

## 1. 本 feature 判定属于哪一类

**主类：局部前后端** | **次类：单后端 + 单前端**

| 判类依据 | 说明 |
|---|---|
| 任务标签 | `[BE]` T001–T007：Prompt 模板、schema、规则解析器、LLM 编排、endpoint；`[FE]` T008–T009：`nl_alert_input` 组件与三页面集成；`[INT]` T010–T016：API/回归/文档收尾 |
| 依赖图 | F8 复用 MVP 的 `AlertRule` 模型、`alerts.py` router、`stock_search.py`、F7 的 `BriefingLLMClient`；不引入新的跨 feature 端到端链路 |
| 契约声明 | `contracts/api.md` 定义了 `POST /api/alerts/natural-language` 的请求/响应/错误码/候选弹窗契约，但消费者为同一 feature 内的前端组件，**不启用「跨模块契约」候选类** |

---

## 2. 路由到哪个类别 skill

| 类别 | 路由去向 | 状态 | 原因 |
|---|---|---|---|
| 单后端 | → `backend-testing` skill | ✅ 执行器已建 | 解析器、endpoint、schema、LLM 兜底、规则上限/重复校验 |
| 单前端 | → `frontend-testing` skill | ✅ 执行器已建 | `nl_alert_input.html` 组件独立渲染、候选弹窗、错误态 UI |
| 局部前后端 | → `fullstack-slice-testing` skill | ✅ 执行器已建 | 新增 API + 新组件在同一 feature 内首次拼成真栈 |
| 完整功能链路 | —（不命中） | — | 本次没有让某条跨 feature 链路首次贯通 |

---

## 3. 是否补全了某条完整功能链路

**本次没有补全新链路。**

F8 只是现有 `F3/F4 预警规则 → F5 推送` 链路的**新入口**（自然语言创建），而非让该链路首次端到端可达。现有 full-chain 测试 `backend/tests/integration/test_full_chain_alert_to_push.py` 已覆盖手动创建规则 → 预警检测 → 推送的 P0 旅程，但**未覆盖以 NL 输入为起点的变体**。

- 若团队希望把 NL 入口纳入 P0 安全网，可作为现有链路的**可选变体**追加到 `full-chain-testing`（非结构性缺口，不做强制路由）。

---

## 4. 逐类待补清单（覆盖状态 + 路由去向）

### 4.1 单后端（→ `backend-testing`）

| 判定维度 | 覆盖状态 | 路由去向 | 现成/需自建 | 命中理由 |
|---|---|---|---|---|
| 真库 / 迁移 / 约束 | ✅ 已被 superpowers/spec-kit 覆盖（跳过） | — | — | 无新增表；`AlertRule` 约束/上限/重复已由 `test_alert_constraints.py` + `test_alerts_nl_api.py` 覆盖 |
| 并发 / 竞态 / 限频原子性 | 🔧 结构性缺口 | `backend-testing` | ✅ 现成 | 规则上限 50 条 + 重复创建使用进程内锁，但 NL endpoint 未做并发压力验证 |
| 韧性 / 重试 / 超时 / 降级 | 🔧 结构性缺口 | `backend-testing` | ✅ 现成 | LLM 兜底（DeepSeek）和股票数据源（akshare/baostock）是外部依赖；`test_briefing_llm_client_http_faults.py` 未与 NL 解析路径集成 |
| 对象级越权 BOLA·BFLA | —（不命中） | — | — | MVP 单用户架构，无多用户隔离/特权接口 |

### 4.2 单前端（→ `frontend-testing`）

| 判定维度 | 覆盖状态 | 路由去向 | 现成/需自建 | 命中理由 |
|---|---|---|---|---|
| L0/L1 测试地基 | 🔧 结构性缺口 | `frontend-testing` | 🔧 第一动作 | `frontend/package.json` 已安装 Vitest+jsdom+MSW，但 `nl_alert_input.html` 无任何组件/单元测试 |
| L2 视觉回归 | 🔧 结构性缺口 | `frontend-testing` | ✅ 现成 | 新增输入框嵌入 dashboard/watchlist/alerts 三页，尚未建立截图基线 |
| L3 可访问性 a11y | 🔧 结构性缺口 | `frontend-testing` | ✅ 现成 | 输入框、按钮、候选列表未做 axe 审计 |
| L4 跨浏览器 + 响应式 | —（不命中） | — | — | 项目仅支持 1280px+ 桌面端，MVP 约束明确 |
| L6 前后端契约 mock | 🔧 结构性缺口 | `frontend-testing` | ✅ 现成 | 前端直接 `fetch('/api/alerts/natural-language')`，无 OpenAPI/契约生成的 MSW handler |
| 设计 token / 硬编码颜色 | 走 lint 门 | — | — | 组件已使用 Tailwind token 类名，建议由 stylelint 门上拦截 |

### 4.3 局部前后端（→ `fullstack-slice-testing`）

| 判定维度 | 覆盖状态 | 路由去向 | 现成/需自建 | 命中理由 |
|---|---|---|---|---|
| ① 环境编排（两侧+依赖真实同起） | 🔧 结构性缺口 | `fullstack-slice-testing` | ✅ 现成 | 有 `test_alerts_nl_api.py`（mock 了 resolver/LLM），但无真浏览器 + 真后端 + 真 DB 的 fullstack 切片 |
| ② 契约真实性（mock vs 真提供者对账） | —（不命中） | — | — | 前端侧暂无消费者 mock；真栈对账可在环境编排测试中自然覆盖 |
| ③ 接缝粘合（身份/序列化/错误→UI） | 🔧 结构性缺口 | `fullstack-slice-testing` | ✅ 现成 | 单测无法验证 `success=false` 各类 message 是否正确渲染到页面、候选列表点击后是否自动重提交 |
| ④ 真实时序·实时 | —（不命中） | — | — | 普通请求-响应，无 SSE/WebSocket/流式 |

### 4.4 完整功能链路（→ `full-chain-testing`）

| 判定维度 | 覆盖状态 | 路由去向 | 现成/需自建 | 命中理由 |
|---|---|---|---|---|
| ①~⑤ 全部链路缺口 | —（不命中） | — | — | 本次未补全新链路；NL 入口只是现有 alert→push 链路的变体 |

---

## 5. 状态标注汇总

| # | 缺口项 | 状态 | 路由去向 | 现成/需自建 | 备注 |
|---|---|---|---|---|---|
| 1 | NL endpoint 并发上限/重复创建 | 🔧 结构性缺口 | `backend-testing` | ✅ 现成 | 并发打请求验证规则上限与重复约束不被击穿 |
| 2 | LLM / 股票数据源韧性 | 🔧 结构性缺口 | `backend-testing` | ✅ 现成 | 注入超时/异常序列验证降级路径 |
| 3 | `nl_alert_input` 组件 L0/L1 地基 | 🔧 结构性缺口 | `frontend-testing` | 🔧 第一动作 | 在现有 Vitest+jsdom 上补最小渲染/交互测试 |
| 4 | 三页嵌入的视觉回归 | 🔧 结构性缺口 | `frontend-testing` | ✅ 现成 | 建立/对比 dashboard/watchlist/alerts 含输入框的截图基线 |
| 5 | 输入框/候选列表 a11y | 🔧 结构性缺口 | `frontend-testing` | ✅ 现成 | axe 审计 input、button、候选弹窗 |
| 6 | 前后端契约 mock | 🔧 结构性缺口 | `frontend-testing` | ✅ 现成 | 从 API 契约生成 MSW handler，防 shape 漂移 |
| 7 | NL 真栈 fullstack 切片 | 🔧 结构性缺口 | `fullstack-slice-testing` | ✅ 现成 | 真浏览器输入 → 真后端 → 真 DB，覆盖成功/歧义/低置信度/错误态 UI |

其余项为 ✅ 已被覆盖或 — 不命中。

---

**本报告只做判类与路由；具体工具由对应类别 skill 按栈实例化，CI 闸和护栏化 agent 才负责验证。**
