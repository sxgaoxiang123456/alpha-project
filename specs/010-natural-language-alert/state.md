# 实施进度 · F8 自然语言设预警

## 当前任务
F8 全部 task 与结构性缺口补测均已完成，等待 merge 回 develop

## 已完成
[x] T001 · 创建 `backend/app/templates/prompts/nl_alert.j2` Prompt 模板
[x] T002 · 创建 `backend/app/schemas/nl_alert.py` 请求/响应 schema
[x] T003 · 实现 `backend/app/services/rule_based_parser.py` 规则解析器
[x] T004 · 扩展 `backend/app/services/stock_search.py` 候选排序与市值字段
[x] T005 · 实现 `backend/app/services/nl_alert_parser.py` 解析编排器
[x] T006 · 创建 `backend/app/routers/alerts_nl.py` 自然语言预警 endpoint
[x] T007 · 在 `backend/app/main.py` 注册 `alerts_nl_router`
[x] T008 · 创建前端 `nl_alert_input` 组件
[x] T009 · 将 `nl_alert_input` 集成到 dashboard / watchlist / alerts 页面
[x] T010 · 验证标准自然语言预警创建（pytest 630 通过 + curl success）
[x] T011 · 实现歧义候选响应与 `selected_stock_code` 自动重提交
[x] T012 · 前端候选列表渲染与自动重提交 UI
[x] T013 · 实现低置信度拒绝提示
[x] T014 · 实现不支持条件类型提示
[x] T015 · 全量后端回归与 quickstart manual flow 验证
[x] T016 · 更新 `state.md` 与 `tasks.md` 完成状态
[x] Code Review 修复（invalid 兜底、selected_stock_code 条件校验、排序稳定键、锁注释）
[x] 结构性缺口补测 · 单后端（并发/韧性）
[x] 结构性缺口补测 · 单前端（L0/L1 + a11y + 契约 mock + 视觉基线）
[x] 结构性缺口补测 · 局部前后端（真栈环境编排 + 接缝粘合）

## 阻塞项
（无）

## 阻塞项
（无）

## 阻塞项
（无）

## 测试资产
- `backend/tests/integration/test_alerts_nl_concurrency.py` — NL endpoint 并发上限/重复约束
- `backend/tests/integration/test_alerts_nl_resilience.py` — LLM/股票数据源韧性降级
- `frontend/src/__tests__/nl_alert_input.test.js` — 组件 L0/L1 + a11y + MSW 契约 mock
- `frontend/e2e/take-baseline.js` + `frontend/e2e/__screenshots__/*` — 视觉回归基线
- `backend/tests/e2e/test_fullstack_slice_nl_alert.py` — 真浏览器 + 真后端 + 真 DB 接缝测试
- `backend/tests/e2e/nl_alert_fullstack_app.py` — fullstack 测试专用 app（stub 外部股票数据源）

## 最后更新
2026-06-24
