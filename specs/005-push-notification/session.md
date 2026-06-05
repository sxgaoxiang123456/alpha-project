# 会话交接 · 推送通知

## Feature 状态
✅ 已完成 — 2026-06-05

## 产出清单

### 数据模型
- `backend/app/models/push_log.py` — PushLog（message_id, message_type, channel, status, error_reason, elapsed_ms, created_at + 索引）
- `backend/app/models/push_channel.py` — PushChannel（name PK, status, consecutive_failures, rate_limited, updated_at）

### Schema
- `backend/app/schemas/push.py` — PushMessageRequest, PushLogResponse, PushChannelStatus

### 服务层
- `backend/app/services/push_service.py` — 核心推送服务（通道选择 → 重试 → 降级 → 异步发送 → 日志记录）
- `backend/app/services/feishu_client.py` — 飞书 OpenAPI 客户端
- `backend/app/services/telegram_client.py` — Telegram Bot API 客户端

### API 路由
- `backend/app/routers/push.py` — GET /push/logs（支持按时间范围、消息类型、状态过滤）

### 集成
- `backend/app/core/quote_scheduler.py` — 简报定时触发（交易日 9:00）
- `backend/app/main.py` — 路由注册 + AlertTrigger→PushService 链路贯通（F4→F5）

### 测试（42 项推送测试 + 389 全量通过）
- `backend/tests/unit/test_push_service.py` — 降级、重试、异步、格式化、截断
- `backend/tests/unit/test_push_models.py` — 模型基础
- `backend/tests/unit/test_push_schemas.py` — Pydantic 校验
- `backend/tests/unit/test_push_constraints.py` — 真库约束（文件模式 SQLite）
- `backend/tests/unit/test_push_concurrency.py` — 并发竞态（原子 UPDATE）
- `backend/tests/integration/test_push_api.py` — API 端点
- `backend/tests/integration/test_full_chain_alert_to_push.py` — F3→F4→F5 全链路

## 关键架构决策

1. **异步发送不阻塞调用方**：`PushService.send()` 检测 running loop，有则 `create_task()`，无则同步 fallback。调用方立即拿到 message_id，结果通过 PushLog 查询。
2. **通道降级策略**：feishu（主）→ telegram（备）。主通道 degraded/unavailable 时自动切备通道；双通道均失败记 failed。
3. **原子 UPDATE 防竞态**：`_record_channel_failure` / `_reset_channel_success` 使用 SQLAlchemy `update()` 原子操作，避免 read-modify-write 丢失更新。
4. **F4→F5 链路贯通**：`_run_alert_detection()` 中 `detect_alerts()` 返回 triggers 后，遍历每个 trigger 构建 `PushMessageRequest` 并调用 `PushService.send()`。

## 已知问题 / 注意事项

- `AlertTrigger.push_status` 字段当前为占位（始终 "pending"），无代码消费。后续若需追踪单条 trigger 的推送状态，需在 `push_service.send()` 返回后更新此字段。
- 飞书/ Telegram 客户端当前为 stub 实现（仅返回结构化 dict），真实 HTTP 调用待接入。
- 简报模板使用纯 Python dict 构建（非 Jinja2），因内容结构简单。
- 多处 `datetime.utcnow()` 警告（F3/F4 遗留），不影响功能。

## 后续 Feature 依赖

- **F6 Dashboard** 消费 `GET /push/logs` 展示推送历史
- **F7 设置页** 需配置飞书 app_id/app_secret 和 Telegram token

## spec 冻结声明

本目录（`specs/005-push-notification/`）已冻结。需求变更请新开编号，勿修改本文档。
