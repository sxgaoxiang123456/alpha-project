# Tasks: Dashboard 性能优化

**Input**: Design documents from `specs/008-redis-adjust/`  
**Prerequisites**: [spec.md](spec.md), [plan.md](plan.md), [brainstorming.md](brainstorming.md)  
**Related Feature**: `specs/006-dashboard/`（本优化为 Dashboard 性能增强）

---

## Phase 1: 基础设施（Redis + 异步工具）

**Purpose**: 搭建 Redis 缓存层和异步持久化工具，为上层服务提供能力支撑

- [x] **T1 [BE] [P]** Redis 缓存封装模块：`backend/app/core/redis_cache.py`（连接管理、get/set/delete/expire、JSON 序列化、连接异常降级为返回 None）
  - [FR-001, FR-007] [依赖: 无] [出参验证: 单元测试 — Redis 可用时正常读写；Redis 不可用时所有操作返回 None 且不抛异常]

- [x] **T2 [BE] [P]** 异步历史落盘工具：`backend/app/core/async_persistence.py`（`async_persist(quotes, session_factory)` — 使用 `asyncio.to_thread()` 将同步 SQLite 写入移出事件循环，异常时记录日志不抛到用户层）
  - [FR-004] [依赖: 无] [出参验证: 单元测试 — mock 行情数据 → 验证后台线程执行写入、主线程不阻塞、异常时记录日志]

- [x] **T3 [BE]** Docker Compose Redis 配置：更新 `docker-compose.yml`（新增 Redis 7.0+ 容器，暴露 6379 端口，通过 `REDIS_URL` 环境变量注入后端）
  - [FR-001] [依赖: T1] [出参验证: `docker compose up redis` 启动成功，`redis-cli ping` 返回 PONG]

---

## Phase 2: 服务层改造（缓存优先 + 并行化）

**Purpose**: 改造数据读取和聚合逻辑，消除外部 I/O 阻塞和串行查询瓶颈

- [x] **T4 [BE]** quote_service 缓存优先改造：`backend/app/services/quote_service.py`（`get_watchlist_quotes(use_cache=False)` / `get_market_indices(use_cache=False)` — 新增 `use_cache` 参数；`True` 时先读 Redis，miss 再调外部接口并写入 Redis TTL=60s；`False` 时保持原有实时调用行为）
  - [FR-001] [依赖: T1, T3] [出参验证: 单元测试 — use_cache=True + Redis hit → 验证外部接口未被调用；use_cache=True + Redis miss → 验证外部接口被调用且 Redis 被写入；use_cache=False → 验证行为与改造前一致]

- [x] **T5 [BE]** dashboard_service 并行化数据库查询：`backend/app/services/dashboard_service.py`（将 `_get_today_alerts()` / `_get_push_history()` / `_get_channel_status()` 从串行改为使用独立 session + `asyncio.gather()` 并行执行）
  - [FR-002] [依赖: 无] [出参验证: 单元测试 — mock 3 个 DB 查询各耗时 100ms → 验证总耗时 < 150ms（而非 300ms）]

- [x] **T6 [BE]** dashboard_service Redis 接入：`backend/app/services/dashboard_service.py`（`build_dashboard_view()` 中行情数据调用改为 `quote_service.get_*(use_cache=True)`；简报数据使用 `redis.get("latest_briefing")`）
  - [FR-001, FR-002] [依赖: T4, T5] [出参验证: 单元测试 — mock Redis 有缓存 → 验证 quote_service 以 use_cache=True 被调用；mock Redis 不可用 → 验证自动降级到外部接口]

---

## Phase 3: 路由层改造（裁剪 + ETag）

**Purpose**: 裁剪刷新端点、支持 ETag/304，消除无效渲染和传输

- [x] **T7 [BE]** dashboard 路由 Partial 裁剪：`backend/app/routers/dashboard.py`（`GET /market_data` 只调用 `dashboard_service.get_market_data()` — 仅返回大盘指数 + 自选股行情，不查询预警/推送历史/通道状态/简报）
  - [FR-003] [依赖: T6] [出参验证: 集成测试 — GET /market_data → 验证响应 HTML 只含行情相关模块，不含 alert_banner / push_history / channel_status]

- [x] **T8 [BE]** dashboard 路由 ETag 支持：`backend/app/routers/dashboard.py`（`/market_data` 响应头增加 ETag — 基于行情数据核心字段 MD5 hash；请求携带 If-None-Match 且匹配时返回 304 无 body；不匹配时返回 200 + HTML + 新 ETag）
  - [FR-005] [依赖: T7] [出参验证: 集成测试 — 首次请求 → 验证响应含 ETag 头；带 If-None-Match 请求且数据未变 → 验证 304 无 body；带 If-None-Match 请求且数据已变 → 验证 200 + 新 ETag]

---

## Phase 4: 前端改造（骨架屏 + ETag 消费）

**Purpose**: 前端配合 ETag 机制，首屏展示骨架屏消除空白等待

- [x] **T9 [FE] [P]** 骨架屏 HTML：`frontend/src/templates/dashboard.html`（大盘指数区域、自选股表格区域、简报卡片区域插入骨架屏占位；使用 Tailwind CSS `animate-pulse` + 暗色模式配色；服务端渲染时骨架屏随首屏 HTML 返回，数据到达后替换）
  - [FR-006] [依赖: 无] [出参验证: 浏览器访问 `/` → 验证首屏 HTML 含骨架屏元素（类名/结构）；数据渲染后 → 验证骨架屏被替换为真实内容]

- [x] **T10 [FE] [P]** ETag/304 JS 支持：`frontend/public/js/dashboard.js`（fetch `/market_data` 时携带 `If-None-Match` 头；304 响应时跳过 DOM 更新；200 响应时更新 innerHTML 并记录新 ETag；保留现有降级检测和暂停逻辑）
  - [FR-005] [依赖: T8] [出参验证: 浏览器开发者工具 → 验证请求头含 If-None-Match；304 响应时 → 验证 DOM 无变化；200 响应时 → 验证 DOM 更新且新 ETag 被记录]

---

## Phase 5: 测试验证

**Purpose**: 全量测试覆盖，验证性能目标达成

- [x] **T11 [INT] [P]** 单元测试 — Redis 缓存：`backend/tests/unit/test_redis_cache.py`（正常读写、TTL 过期、连接失败降级、JSON 序列化/反序列化）
  - [FR-001, FR-007] [依赖: T1] [出参验证: pytest 全部通过]

- [x] **T12 [INT] [P]** 单元测试 — 异步持久化：`backend/tests/unit/test_async_persistence.py`（正常落盘、异常时记录日志、主线程不阻塞）
  - [FR-004] [依赖: T2] [出参验证: pytest 全部通过]

- [x] **T13 [INT] [P]** 单元测试 — quote_service 缓存：`backend/tests/unit/test_quote_service_cache.py`（use_cache=True hit/miss、use_cache=False 行为不变、降级策略）
  - [FR-001] [依赖: T4] [出参验证: pytest 全部通过]

- [x] **T14 [INT] [P]** 单元测试 — dashboard_service 并行化 + ETag：`backend/tests/unit/test_dashboard_service_perf.py`（并行查询耗时、ETag hash 计算正确性、缓存接入）
  - [FR-002, FR-005] [依赖: T5, T6, T8] [出参验证: pytest 全部通过]

- [x] **T15 [INT]** 集成测试 — 性能验收：`backend/tests/integration/test_dashboard_perf.py`（
  - 有缓存时首响应 < 1s（mock Redis 有数据，测量 TTFB）
  - 冷启动 < 2s（清空 Redis，测量完整加载）
  - 304 响应 < 50ms（连续请求相同 ETag，测量 TTFB）
  - 200 刷新 < 300ms（数据变化后请求，测量 TTFB）
  - 50 只自选股首响应 < 1s（mock 50 只自选股数据）
  - 降级场景：Redis 不可用 + 外部接口超时 → 验证 < 3s 且页面正常展示）
  - [SC-001~SC-008] [依赖: T3, T6, T8, T9, T10] [出参验证: pytest 全部通过]

- [x] **T16 [INT]** 集成测试 — 兼容性与回归：`backend/tests/integration/test_dashboard_regression.py`（
  - F3 调用 quote_service 不传 use_cache → 验证行为与优化前一致
  - Dashboard 刷新不闪屏、不丢失分组状态
  - 多标签页并发刷新 → 验证 ETag 正常、无 304 误判
  - 骨架屏布局与真实内容一致，替换无跳动）
  - [FR-003, FR-006] [依赖: T4, T9, T10] [出参验证: pytest 全部通过]

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Infra) ──► Phase 2 (Service) ──► Phase 3 (Router) ──► Phase 4 (FE) ──► Phase 5 (Test)
     T1/P → T2/P → T3        T4 → T5 → T6        T7 → T8        T9/P → T10/P    T11/P → T12/P → T13/P → T14/P
                                                                                          │
                                                                                          ▼
                                                                                    T15 → T16
```

### Parallel Groups

| 组 | 任务 | 说明 |
|:---|:---|:---|
| **Group A [BE]** | T1, T2 | Redis 缓存和异步持久化互相无依赖 |
| **Group B [FE]** | T9, T10 | 骨架屏 HTML 和 ETag JS 互相无依赖 |
| **Group C [INT]** | T11, T12, T13, T14 | 各单元测试互相无依赖 |

### Critical Path

```
T1 → T3 → T4 → T6 → T7 → T8 → T10 → T15 → T16
      └→ T5 ─┘      └→ T9 ─┘
```

最短完成路径估算：9 个串行步骤

---

## Notes

- `[BE]` = Backend，后端/API/数据库/服务层任务
- `[FE]` = Frontend，前端模板/CSS/JS 任务
- `[INT]` = Integration/Testing，测试与集成验证任务
- `[P]` 标记 = Parallelizable，与其他 `[P]` 任务无依赖冲突，可并发执行
- T4 `use_cache` 参数默认 `False`，确保对 F3/F2 等现有调用方零侵入
- T8 ETag 计算使用 `hashlib.md5`，数据量极小（50 只股票 × 2 字段），CPU 开销可忽略
- T9 骨架屏使用 Tailwind `animate-pulse bg-surface-raised/50`，颜色与 DESIGN.md 暗色模式一致
- T15 性能测试使用 `time.perf_counter()` 测量，非 `time.time()`，避免系统时间跳变影响
- T16 回归测试必须验证 F3 调用 quote_service 时不传 use_cache，确保预警检测实时性不受影响
