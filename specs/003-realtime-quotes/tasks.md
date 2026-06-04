# Tasks: 基础实时行情

**Input**: Design documents from `specs/003-realtime-quotes/`
**Prerequisites**: plan.md, spec.md

---

## Phase 1: 数据模型与 Schema

**Purpose**: 定义历史数据和行情响应的数据结构

- [x] **T1 [BE]** 创建 HistoricalQuote 数据模型：`backend/app/models/historical_quote.py`（stock_code, date, open, close, high, low, volume, turnover，含日期+代码复合索引）
  - [FR-007] [依赖: F1 基础设施就绪] [出参验证: `HistoricalQuote.__table__.create()` 成功，表含 8 字段 + 复合索引]

- [x] **T2 [BE]** 创建 Quote Pydantic schemas：`backend/app/schemas/quote.py`（Quote, MarketIndex, HistoricalQuote 请求/响应模型）
  - [FR-001, FR-003, FR-010] [依赖: T1] [出参验证: 无效价格/涨跌幅触发 pydantic.ValidationError]

---

## Phase 2: 核心服务层（可并行）

**Purpose**: 数据清洗、大盘指数、行情获取三个独立服务

- [x] **T3 [BE] [P]** 实现数据清洗服务：`backend/app/services/data_cleaner.py`（异常值检测：价格为负/0、涨跌幅超阈值、停牌识别；返回标准化 Quote）
  - [FR-005, FR-008] [依赖: T2] [出参验证: 单元测试 — 价格为-10→标记异常；涨跌幅+25%（非科创）→标记异常；停牌股票→status="suspended"]

- [x] **T4 [BE] [P]** 实现大盘指数服务：`backend/app/services/market_index.py`（固定 3 个指数获取 + 缓存 + 返回 MarketIndex）
  - [FR-003] [依赖: T2] [出参验证: 单元测试 — mock facade 返回 3 个指数数据，清洗后返回标准化 MarketIndex 列表]

- [ ] **T5 [BE] [P]** 实现行情服务核心逻辑：`backend/app/services/quote_service.py`（读取 WatchlistItem → 批量调用 facade → 清洗 → 返回 Quote 列表）
  - [FR-001, FR-004, FR-005] [依赖: T3] [出参验证: 单元测试 — mock facade + mock 自选股列表 → 返回标准化 Quote 列表]

---

## Phase 3: 缓存与落盘集成

**Purpose**: 行情数据写入实时缓存和历史表

- [ ] **T6 [BE]** 实现行情缓存集成：扩展 `quote_service.py`（清洗后写入 F2 CacheService，缓存键 `quote:{code}`，过期时间 5 分钟）
  - [FR-006, A-006] [依赖: T5] [出参验证: 单元测试 — 写入后通过 CacheService 查询命中，过期后查询返回 None]

- [ ] **T7 [BE]** 实现异步落盘：扩展 `quote_service.py`（使用 asyncio.create_task 将 HistoricalQuote 异步写入 SQLite，不阻塞主线程）
  - [FR-007] [依赖: T5] [出参验证: 单元测试 — 落盘任务完成后数据库包含 HistoricalQuote 记录]

---

## Phase 4: 定时任务与路由

**Purpose**: APScheduler 自动刷新 + Dashboard API 查询

- [ ] **T8 [BE]** 实现行情定时任务：`backend/app/core/quote_scheduler.py`（APScheduler 任务：交易日判断 → 每 3 分钟触发 quote_service 刷新 → 大盘指数刷新）
  - [FR-002, A-004, A-008] [依赖: T6, T7] [出参验证: 单元测试 — mock 交易日 → 任务执行刷新；mock 非交易日 → 任务跳过]

- [ ] **T9 [BE]** 实现行情查询路由：`backend/app/routers/quotes.py`（GET /quotes 返回自选股行情，优先读缓存；GET /quotes/market 返回大盘指数）
  - [FR-001, FR-003, FR-010] [依赖: T6] [出参验证: API 测试 — 缓存命中返回 < 200ms；缓存未命中触发获取后返回]

---

## Phase 5: 配置集成

**Purpose**: 注册定时任务和配置参数

- [ ] **T10 [BE]** 更新配置与入口：更新 `backend/app/config.py`（新增行情刷新周期、缓存过期时间、交易日历配置）+ 更新 `backend/app/main.py`（注册 quote_scheduler APScheduler 任务）
  - [FR-002, A-004, A-006] [依赖: T8] [出参验证: `uvicorn app.main:app` 启动后定时任务正常运行，日志显示行情刷新执行]

---

## Phase 6: 测试验证

**Purpose**: 全量测试覆盖

- [ ] **T11 [INT] [P]** 单元测试 — 数据清洗：`backend/tests/unit/test_data_cleaner.py`（异常值规则、停牌识别、科创板阈值）
  - [FR-005, FR-008] [依赖: T3] [出参验证: pytest 全部通过]

- [ ] **T12 [INT] [P]** 单元测试 — 行情服务：`backend/tests/unit/test_quote_service.py` + `backend/tests/unit/test_market_index.py`（mock facade、缓存集成、落盘验证）
  - [FR-001~FR-007] [依赖: T5, T6, T7] [出参验证: pytest 全部通过]

- [ ] **T13 [INT] [P]** 单元测试 — 定时任务：`backend/tests/unit/test_quote_scheduler.py`（交易日判断、调度逻辑、非交易时段跳过）
  - [FR-002, A-008] [依赖: T8] [出参验证: pytest 全部通过（使用 freezegun 冻结时间）]

- [ ] **T14 [INT]** 集成测试 — 主动查询 API：`backend/tests/integration/test_quotes_api.py`（GET /quotes、GET /quotes/market、缓存命中/未命中）
  - [FR-001, FR-003, SC-001, SC-002] [依赖: T9] [出参验证: pytest 全部通过，首屏加载 < 3 秒]

- [ ] **T15 [INT]** 集成测试 — 定时刷新与落盘：`backend/tests/integration/test_quote_scheduler.py`（定时触发 → 数据获取 → 清洗 → 缓存更新 → 历史落盘）
  - [FR-002, FR-005~FR-007] [依赖: T8, T10] [出参验证: pytest 全部通过，覆盖 US-2 全部 AC]

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Model)     ──► Phase 2 (Service) ──► Phase 3 (Cache/Disk)
     T1/T2              T3/P/T4/P/T5/P         T6 → T7
                                          │
Phase 4 (Scheduler) ◄─────────────────────┘
     T8 → T9

Phase 5 (Config) ◄── Phase 4
     T10

Phase 6 (Test) ◄── 全部完成
     T11/P → T12/P → T13/P → T14 → T15
```

### Parallel Groups

| 组 | 任务 | 说明 |
|:---|:---|:---|
| **Group A [BE]** | T1, T2 | 模型和 schema 可并行 |
| **Group B [BE]** | T3, T4, T5 | 三个服务互相无依赖 |
| **Group C [INT]** | T11, T12, T13 | 三类单元测试可并行 |

### Critical Path

```
T1/T2(并行) → T3/T4/T5(并行) → T6 → T7 → T8 → T9 → T10 → T15
```

最短完成路径估算：8 个串行步骤

---

## Notes

- `[BE]` = Backend，后端/API/服务/模型/配置类任务
- `[INT]` = Integration/Testing，集成测试与测试类任务（含单元测试、集成测试、端到端测试）
- `[P]` 标记 = Parallelizable，无依赖冲突可并发执行
- T3、T4、T5 为独立服务，可并行开发，互不阻塞
- 所有单元测试使用 mock 隔离外部依赖（facade、数据库）
- T14 集成测试验证首屏加载性能，使用 `pytest-benchmark` 或时间断言
- T15 集成测试使用 `freezegun` 冻结时间模拟交易时段/非交易时段
- 本 feature 无前端模板任务（行情展示由 F5 Dashboard 负责）
