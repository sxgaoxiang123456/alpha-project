# 实施进度 · F7 AI 早盘简报

## 当前任务
[>] Code Review 修复 #6 · 全量测试通过并 merge 回 develop

## 已完成
- [x] T001 · 创建 `backend/app/templates/prompts/briefing.j2` Prompt 模板
- [x] T002 · 创建 `backend/app/schemas/briefing.py` schema
- [x] T003 · 创建 `backend/app/services/prompt_loader.py`
- [x] T004 · 创建 `backend/app/services/briefing_llm_client.py`
- [x] T005 · 创建 `backend/app/services/top_mover_service.py`
- [x] T006 · 创建 `backend/app/services/briefing_service.py`
- [x] T007 · 更新 `backend/app/core/quote_scheduler.py` 集成定时简报
- [x] T008 · 扩展 `backend/app/services/push_service.py` 简报渲染
- [x] T009 · 实现 LLM 失败降级路径
- [x] T010 · PushLog metadata 记录降级原因
- [x] T011 · 非交易日跳过简报生成
- [x] T012 · 创建 `backend/app/routers/briefing.py` 手动刷新 API
- [x] T013 · 创建 `GET /api/briefing/latest` 端点
- [x] T014 · 在 `backend/app/main.py` 注册 `briefing_router`
- [x] T015 · 更新 frontend dashboard 手动刷新按钮
- [x] T016 · 更新 briefing_card.html 展示 insights/top_movers 与 A-share 红绿语义
- [x] T017 · 全量测试通过 + curl 手动触发验证
- [x] CR-Fix #1 · BriefingService 60s 总超时强制降级
- [x] CR-Fix #2 · top_mover_service 异动阈值判定
- [x] CR-Fix #3 · 清理 briefing 推送 metadata 冗余
- [x] CR-Fix #4 · 简化 briefing.js 大盘指数处理
- [x] CR-Fix #5 · 使用 threading.Event 优化 wait_for_quote_refresh

## 阻塞项
（无）

## 最后更新
2026-06-23
