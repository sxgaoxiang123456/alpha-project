# Tasks: 数据多源容灾

**Input**: Design documents from `specs/002-data-failover/`
**Prerequisites**: plan.md, spec.md

---

## Phase 1: 数据模型与 Schema

**Purpose**: 定义缓存和状态持久化所需的数据结构

- [x] **T1 [BE]** 创建 CacheEntry 数据模型：`backend/app/models/cache_entry.py`（key, content, cached_at, expires_at，含过期查询索引）
  - [FR-005] [依赖: F1 基础设施就绪] [出参验证: `CacheEntry.__table__.create()` 成功，表含 4 字段 + expires_at 索引]

- [x] **T2 [BE]** 创建 DataSourceStatus 数据模型：`backend/app/models/data_source_status.py`（name, status, consecutive_failures, last_success_at, last_failure_at, last_error）
  - [FR-004, FR-008] [依赖: F1 基础设施就绪] [出参验证: 表创建成功，可读写状态记录]

- [x] **T3 [BE]** 创建 DataFetch Pydantic schemas：`backend/app/schemas/data_fetch.py`（DataFetchRequest, DataFetchResult）
  - [FR-011] [依赖: T1, T2] [出参验证: 无效 status 值触发 pydantic.ValidationError]

---

## Phase 2: 核心基础设施（可并行）

**Purpose**: 熔断器和缓存服务，不依赖数据源适配器

- [x] **T4 [BE] [P]** 实现熔断器：`backend/app/core/circuit_breaker.py`（状态机 Closed/Open/Half-Open + 连续失败计数 + 状态持久化到 DataSourceStatus）
  - [FR-004, FR-008] [依赖: T2] [出参验证: 单元测试 — 连续3次失败→Open；连续2次成功→Closed；Half-Open 状态仅允许探测]

- [x] **T5 [BE] [P]** 实现缓存服务：`backend/app/services/cache_service.py`（写入缓存、查询缓存含过期判断、批量清理过期条目）
  - [FR-005, FR-006] [依赖: T1] [出参验证: 单元测试 — 写入后查询命中；过期后查询返回 None；批量清理删除过期条目]

---

## Phase 3: 数据源适配层

**Purpose**: 封装 AkShare/BaoStock 差异，统一接口

- [x] **T6 [BE]** 实现 DataSource 抽象基类 + AkShareDataSource：`backend/app/services/data_source.py`（基类定义 `fetch_realtime(codes)` + AkShare 具体实现 + 异常映射）
  - [FR-001, FR-002] [依赖: T3] [出参验证: 单元测试 — mock AkShare 返回标准化数据；mock 超时/限流异常映射为 DataSourceError]

- [x] **T7 [BE]** 实现 BaoStockDataSource：扩展 `backend/app/services/data_source.py`（BaoStock 具体实现 + 异常映射）
  - [FR-001, FR-003] [依赖: T6] [出参验证: 单元测试 — mock BaoStock 返回与 AkShare 格式一致的标准化数据]

---

## Phase 4: Facade 层（核心）

**Purpose**: 对外统一接口，内部管理切换/缓存/熔断

- [x] **T8 [BE]** 实现 DataSourceFacade：`backend/app/services/data_source_facade.py`（统一接口 `fetch_realtime(codes)`，内部逻辑：检查熔断→尝试主源→失败降级→写入缓存→返回 DataFetchResult）
  - [FR-002~FR-006, FR-011] [依赖: T4, T5, T6, T7] [出参验证: 单元测试 — 主源正常返回 primary；主源故障→备源返回 fallback；双源故障→缓存返回 cached；无缓存→unavailable]

---

## Phase 5: 定时健康检查与调度

**Purpose**: 自动探测数据源可用性，恢复主源

- [ ] **T9 [BE]** 实现 HealthChecker：`backend/app/core/health_checker.py`（APScheduler 任务，每 5 分钟探测 AkShare/BaoStock，更新熔断器状态，输出结构化日志）
  - [FR-007, FR-008] [依赖: T4] [出参验证: 单元测试 — mock 数据源成功/失败，验证熔断器状态变化 + 日志输出]

- [ ] **T10 [BE]** 注册定时任务 + 配置更新：更新 `backend/app/main.py`（注册 APScheduler + HealthChecker 任务）+ 更新 `backend/app/config.py`（数据源超时/重试/检查间隔配置）
  - [FR-007, A-006, A-007] [依赖: T9] [出参验证: `uvicorn app.main:app` 启动后 APScheduler 正常运行，日志显示健康检查执行]

---

## Phase 6: 可观测性接口

**Purpose**: 为 Dashboard 提供数据源状态查询

- [ ] **T11 [BE]** 数据源状态查询 API：新建 `backend/app/routers/system.py` 或扩展现有路由，暴露 GET `/system/data-sources` 返回当前各源健康状态、当前活跃源、最近切换时间
  - [FR-009, US-3] [依赖: T8] [出参验证: API 测试 — 返回 JSON 含 akshare/baostock 状态、当前活跃源、切换历史]

---

## Phase 7: 测试验证

**Purpose**: 全量测试覆盖

- [ ] **T12 [INT] [P]** 单元测试 — 熔断器：`backend/tests/unit/test_circuit_breaker.py`（状态转换、持久化恢复、并发安全）
  - [FR-004, FR-008] [依赖: T4] [出参验证: pytest 全部通过]

- [ ] **T13 [INT] [P]** 单元测试 — 缓存服务：`backend/tests/unit/test_cache_service.py`（读写、过期、清理、批量操作）
  - [FR-005, FR-006] [依赖: T5] [出参验证: pytest 全部通过]

- [ ] **T14 [INT] [P]** 单元测试 — 适配器 + Facade：`backend/tests/unit/test_data_source.py` + `backend/tests/unit/test_facade.py`（mock 双源切换、缓存命中、异常处理）
  - [FR-001~FR-006] [依赖: T6, T7, T8] [出参验证: pytest 全部通过]

- [ ] **T15 [INT]** 集成测试 — 容灾端到端：`backend/tests/integration/test_failover.py`（模拟 AkShare 故障→验证切换→模拟恢复→验证切回→模拟双故障→验证缓存）
  - [FR-001~FR-011] [依赖: T8, T10, T11] [出参验证: pytest 全部通过，覆盖 US-1/US-2 全部 AC]

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Model)     ──► Phase 2 (Infra) ──► Phase 3 (Adapter) ──► Phase 4 (Facade)
     T1/T2/T3              T4/P/T5/P           T6 → T7              T8
                                                          │
Phase 5 (Health) ◄───────────────────────────────────────┘
     T9 → T10

Phase 6 (API) ◄── Phase 4
     T11

Phase 7 (Test) ◄── 全部完成
     T12/P → T13/P → T14/P → T15
```

### Parallel Groups

| 组 | 任务 | 说明 |
|:---|:---|:---|
| **Group A [BE]** | T1, T2 | 两个独立模型可并行 |
| **Group B [BE]** | T4, T5 | 熔断器和缓存服务互相无依赖 |
| **Group C [INT]** | T12, T13, T14 | 三类单元测试可并行 |

### Critical Path

```
T1/T2(并行) → T3 → T4/T5(并行) → T6 → T7 → T8 → T9 → T10 → T11 → T15
```

最短完成路径估算：7 个串行步骤

---

## Notes

- `[BE]` = Backend，后端/服务/API/模型/配置类任务
- `[INT]` = Integration/Testing，集成测试与测试验证类任务
- `[P]` 标记 = Parallelizable，无依赖冲突可并发执行
- T6 和 T7 共享 `backend/app/services/data_source.py`，必须串行（T7 编辑同一文件）
- 所有单元测试使用 mock 隔离外部数据源，不依赖网络
- T15 集成测试使用 `responses` 库 mock HTTP 请求，模拟完整的故障→切换→恢复流程
- 本 feature 无前端模板任务（纯服务层），T11 的 API 为 Dashboard 提供数据
