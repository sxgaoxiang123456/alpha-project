# Tasks: 推送通知

**Input**: Design documents from `specs/005-push-notification/`
**Prerequisites**: plan.md, spec.md

---

## Phase 1: 数据模型与 Schema

**Purpose**: 定义推送日志和通道状态的数据结构

- [ ] **T1 [BE]** 创建 PushLog 数据模型：`app/models/push_log.py`（日志 ID、消息 ID、消息类型、通道、状态、失败原因、耗时、创建时间，含时间索引）
  - [FR-009, FR-010] [依赖: F1 基础设施就绪] [出参验证: `PushLog.__table__.create()` 成功，表含 7 字段 + 时间索引]

- [ ] **T2 [BE]** [P] 创建 PushChannel 数据模型：`app/models/push_channel.py`（通道名、状态、配置参数、连续失败次数、限流状态、更新时间）
  - [FR-012] [依赖: F1 基础设施就绪] [出参验证: 表创建成功，可读写通道状态]

- [ ] **T3 [BE]** [P] 创建 Push Pydantic schemas：`app/schemas/push.py`（PushMessageRequest, PushLogResponse, PushChannelStatus）
  - [FR-005, FR-010] [依赖: T1, T2] [出参验证: 无效消息类型/状态触发 pydantic.ValidationError]

---

## Phase 2: 通道客户端实现（US-1 + US-2）

**Purpose**: 飞书和 Telegram 的 HTTP 客户端

- [ ] **T4 [BE]** [P] 实现飞书客户端：`app/services/feishu_client.py`（lark-cli 卡片发送 + subprocess 调用 + 限流/错误识别）
  - [FR-001, FR-012] [依赖: T3] [出参验证: 单元测试 — mock lark-cli 成功/失败/限流响应 → 正确返回状态]

- [ ] **T5 [BE]** [P] 实现 Telegram 客户端：`app/services/telegram_client.py`（Bot API 文本发送 + 可选代理 + Token 过期检测）
  - [FR-002] [依赖: T3] [出参验证: 单元测试 — mock Bot API 成功/失败响应 → 正确返回状态]

---

## Phase 3: 核心推送服务（US-1 + US-2 + US-3）

**Purpose**: 格式化渲染、通道降级、异步发送、日志记录

- [ ] **T6 [BE]** 实现 PushService 核心：`app/services/push_service.py`（通道状态检查 → 主通道尝试 → 重试 → 降级 → 异步发送 → 日志记录）
  - [FR-003~FR-006, FR-011] [依赖: T3, T4, T5] [出参验证: 单元测试 — mock 双通道 → 验证降级逻辑、重试次数、日志写入]

- [ ] **T7 [BE]** [P] 实现预警卡片格式化：扩展 `push_service.py`（预警数据 → 飞书卡片 JSON / Telegram 文本）
  - [FR-006] [依赖: T6] [出参验证: 单元测试 — 输入预警数据 → 验证卡片字段完整、Telegram 文本含关键信息]

- [ ] **T8 [BE]** [P] 实现简报模板格式化：扩展 `push_service.py`（Jinja2 模板：大盘指数 + 自选股概览 → 飞书卡片 / Telegram 文本）
  - [FR-007] [依赖: T6] [出参验证: 单元测试 — mock 大盘数据 → 验证简报内容含指数和 TOP 3]

- [ ] **T9 [BE]** [P] 实现内容截断逻辑：扩展 `push_service.py`（超长内容智能截断，保留关键信息）
  - [FR-008] [依赖: T6] [出参验证: 单元测试 — 超长内容 → 截断后关键信息不丢失]

---

## Phase 4: 推送历史查询（US-4）

**Purpose**: Dashboard 查询推送历史

- [ ] **T10 [BE]** 实现推送历史查询路由：`app/routers/push.py`（GET /push/logs，支持按时间范围、消息类型、状态过滤）
  - [FR-010] [依赖: T1] [出参验证: API 测试 — 写入 10 条日志 → 查询返回正确过滤结果]

---

## Phase 5: 集成与配置

**Purpose**: 简报定时触发、配置更新、路由注册

- [ ] **T11 [BE]** 实现简报定时触发：更新 `app/core/quote_scheduler.py`（交易日 9:00 获取行情 → 渲染简报模板 → 调用 push_service）
  - [FR-007, A-005] [依赖: T8] [出参验证: 单元测试 — mock 交易日 → 简报任务执行；mock 非交易日 → 跳过]

- [ ] **T12 [BE]** 路由注册与配置读取：更新 `app/main.py`（注册 push 路由）；推送通道配置从 `settings_service.get_settings()` 读取（飞书 app_id/app_secret/brand/chat_id、Telegram Token、代理配置）
  - [A-001~A-004] [依赖: T10] [出参验证: `uvicorn app.main:app` 启动后配置加载正确，路由可用]

---

## Phase 6: 测试验证

**Purpose**: 全量测试覆盖

- [ ] **T13 [INT]** [P] 单元测试 — PushService：`tests/unit/test_push_service.py`（降级逻辑、重试、异步发送、日志记录）
  - [FR-003~FR-012] [依赖: T6~T9] [出参验证: pytest 全部通过]

- [ ] **T14 [INT]** [P] 单元测试 — 客户端：`tests/unit/test_feishu_client.py` + `tests/unit/test_telegram_client.py`（mock subprocess 执行、错误处理、限流检测）
  - [FR-001, FR-002, FR-012] [依赖: T4, T5] [出参验证: pytest 全部通过]

- [ ] **T15 [INT]** 集成测试 — 端到端：`tests/integration/test_push_api.py`（发送预警 → 降级 → 查询历史 → 简报定时触发）
  - [FR-001~FR-012] [依赖: T11, T12] [出参验证: pytest 全部通过，覆盖 US-1~US-4 全部 AC]

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Model)     ──► Phase 2 (Clients) ──► Phase 3 (Service) ──► Phase 4 (API)
     T1/T2/T3           T4/P → T5/P           T6 → T7/P/T8/P/T9/P     T10
                                                          │
Phase 5 (Integration) ◄───────────────────────────────────┘
     T11 → T12

Phase 6 (Test) ◄── 全部完成
     T13/P → T14/P → T15
```

### Parallel Groups

| 组 | 任务 | 说明 |
|:---|:---|:---|
| **Group A [BE]** | T2, T3 | PushChannel 和 schemas 可并行 |
| **Group B [BE]** | T4, T5 | 两个客户端互相无依赖 |
| **Group C [BE]** | T7, T8, T9 | 格式化逻辑互相独立 |
| **Group D [INT]** | T13, T14 | 两类单元测试可并行 |

### Critical Path

```
T1 → T3 → T4 → T6 → T7 → T10 → T11 → T12 → T15
```

最短完成路径估算：9 个串行步骤

---

## Notes

- `[BE]` = Backend（后端/API/服务/模型/配置类任务）
- `[INT]` = Integration/Testing（集成测试、单元测试、端到端测试类任务）
- `[P]` 标记 = Parallelizable，无依赖冲突可并发执行
- T4 飞书客户端需识别限流/认证错误码（根据 lark-cli 返回的退出码或 stderr 错误信息）
- T5 Telegram 客户端代理为可选配置，未配置时直连
- T6 PushService 使用 `asyncio.create_task()` 异步发送，不阻塞调用方
- T8 简报模板使用 Jinja2，模板文件存放于 `app/templates/briefing_card.md`
- T11 简报定时任务复用 F3 `quote_scheduler.py` 的 APScheduler 配置
- T15 集成测试使用 pytest-mock mock subprocess 调用，覆盖 lark-cli/Telegram API 交互
- 本 feature 无前端模板任务（推送展示由 F5 Dashboard 负责历史查询）
