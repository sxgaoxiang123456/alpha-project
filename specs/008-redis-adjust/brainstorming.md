# Dashboard 性能优化方案 — Brainstorming 纪要

**Feature Directory**: `specs/008-redis-adjust/`  
**Created**: 2026-06-09  
**Status**: Approved — 方案 1（Redis 缓存优先 + 并行聚合 + Partial 裁剪）  
**Scope**: Dashboard 首响应性能优化（006-dashboard 的性能增强）  
**Performance Target**: 有缓存时首响应 < 1s，冷启动 < 2s

---

## 1. 问题背景

MVP 阶段完成后，Dashboard 页面（`/`）每次打开均出现明显卡滞，与其他页面响应速度差异显著。用户猜测为数据读取渲染导致的延迟。

**Success Criteria（来自 006-dashboard/spec.md）**:
- SC-001: 首次加载 < 3s
- SC-002: 非首次（本地渲染）< 1s

**当前实际表现**（基于源码分析）:
- 有缓存时：约 2-4s（不稳定，取决于外部接口响应）
- 冷启动：约 3-5s

---

## 2. 性能根因分析

基于 `backend/app/services/dashboard_service.py`、`quote_service.py`、`cache_service.py`、`routers/dashboard.py`、`frontend/public/js/dashboard.js` 等文件的源码分析，识别出五大根因：

| 层级 | 问题 | 影响 |
|------|------|------|
| **外部服务** | 自选股行情每次请求都实时调用外部接口（AkShare/BaoStock），缓存只写不读 | 网络 I/O 延迟直接叠加到首屏，不可控 |
| **数据库** | 推送历史全表排序取 100 条（无日期索引）；历史行情在主线程同步落盘 | SQLite 查询和写入阻塞响应 |
| **聚合逻辑** | 同一个 session 内预警/推送历史/通道状态串行查询；`/market_data` Partial 端点未裁剪，也执行完整聚合 | 后端处理时间长 |
| **模板渲染** | 全量 SSR，自选股表格无上限、无虚拟滚动；无骨架屏 | 服务端 CPU 渲染耗时随数据量增长，用户感知空白等待 |
| **前端刷新** | 固定 60 秒轮询完整 HTML，无 ETag/304/增量更新 | 刷新请求重复消耗服务端资源，即使数据无变化也返回 200 + 完整 HTML |

---

## 3. 方案决策过程

### 3.1 澄清问题与结论

| # | 问题 | 选项 | 结论 |
|---|------|------|------|
| 1 | 缓存基础设施 | A. 引入 Redis / B. 仅进程内缓存 / C. 仅 SQLite 优化 | **A — 引入 Redis** |
| 2 | 优化范围 | A. 仅 Dashboard / B. Dashboard + 上游局部优化 / C. 全局优化 | **B — Dashboard + 上游相关接口局部优化**（推荐，直击根因且风险可控） |
| 3 | 性能目标定义 | A. 有缓存 < 1s，冷启动 < 2s / B. 所有场景 < 1s / C. 仅 TTFB < 1s | **A — 有缓存 < 1s，冷启动 < 2s**（冷启动外部 I/O 不可控，允许稍慢） |

### 3.2 方案对比

| 维度 | 方案 1：Redis 缓存优先 + 并行聚合 + Partial 裁剪（**选定**） | 方案 2：服务端 HTML 缓存 + 数据预聚合 | 方案 3：轻量级（仅进程内优化） |
|:---|:---|:---|:---|
| **核心策略** | 引入 Redis 缓存行情数据；并行化数据库查询；裁剪 Partial 端点；异步化历史落盘 | 在方案 1 基础上，增加服务端 HTML Partial 缓存 + 后台定时预聚合 | 不引入 Redis，仅用 `lru_cache` + 局部并行化 |
| **Redis 用途** | 行情数据缓存（TTL 60s）、通道状态缓存（TTL 300s） | 行情数据 + 预聚合 Dashboard 数据 + 渲染后 HTML 缓存 | 不使用 |
| **改动文件数** | ~7 个文件 | ~10 个文件 | ~4 个文件 |
| **预期效果（有缓存）** | **~400-800ms** | ~200-500ms | ~1.5-2.5s（不达标） |
| **冷启动** | ~1.5-2s | ~1-1.5s | ~2.5-4s（无本质改善） |
| **风险** | 低 | 中（缓存一致性复杂） | 低（但效果不达标） |
| **维护复杂度** | 低 | 中 | 最低 |

**选定方案 1 的理由**：直击性能根因（外部实时调用 + 同步落盘），开发量适中（~7 个文件），风险可控，能稳定达成 1s 目标。方案 2 过度设计（HTML 缓存失效粒度难控制），方案 3 治标不治本。

---

## 4. 详细设计（方案 1）

### 4.1 架构调整

```text
新增模块：
backend/app/core/redis_cache.py          # Redis 封装（get/set/delete/expire，带序列化）
backend/app/core/async_persistence.py    # 异步历史落盘（线程池封装）

改造模块：
backend/app/services/quote_service.py      # 增加缓存优先读取模式
backend/app/services/dashboard_service.py  # 并行化 DB 查询 + 使用 Redis 缓存
backend/app/routers/dashboard.py           # Partial 端点裁剪 + ETag 支持
frontend/src/templates/dashboard.html      # 骨架屏占位
frontend/public/js/dashboard.js            # ETag/If-None-Match + 304 处理
```

### 4.2 核心优化点

| # | 优化点 | 当前问题 | 改造后 |
|---|--------|----------|--------|
| 1 | **行情数据 Redis 缓存** | `quote_service` 每次实时调外部接口，缓存只写不读 | 先读 Redis，miss 再调外部接口，写入 Redis TTL=60s |
| 2 | **并行化数据库查询** | `dashboard_service` 内 DB 查询串行（同一个 session） | 使用独立 session / `asyncio.gather` 并行查预警+推送历史+通道状态 |
| 3 | **Partial 端点裁剪** | `/market_data` 执行完整聚合（含推送历史、通道状态） | 只返回行情相关数据（大盘+自选股），其他数据不查 |
| 4 | **历史落盘异步化** | `quote_service` 主线程同步写入 `HistoricalQuote` | 改为 `asyncio.to_thread()` 后台线程写入，不阻塞响应 |
| 5 | **ETag/304 支持** | 前端每次刷新返回完整 HTML，无变化也 200 | `/market_data` 返回 ETag（基于数据 hash），无变化返回 304，前端不更新 DOM |
| 6 | **骨架屏** | 首屏空白等待 | 首屏渲染骨架屏占位，数据到达后局部替换 |

### 4.3 数据流（有缓存时）

```
Browser → GET /
  → dashboard_service.build_dashboard_view()
    → asyncio.gather(
        redis.get("market_indices"),      # ~5ms
        redis.get("watchlist_quotes"),    # ~5ms
        redis.get("latest_briefing"),     # ~5ms
        _get_today_alerts(db),            # ~30ms（并行）
        _get_push_history(db),            # ~50ms（并行，已加日期索引）
        _get_channel_status(db)           # ~10ms（并行）
      )
    → 最大耗时 ≈ max(50ms, 外部 I/O 已消除)
  → Jinja2 渲染（骨架屏已预渲染，只需填充数据）
  → TTFB ≈ 100-200ms + 渲染 ≈ 200-400ms
  → 总首响应 ≈ 400-800ms ✅
```

### 4.4 冷启动数据流

```
Browser → GET /
  → redis.get("market_indices") → miss
  → redis.get("watchlist_quotes") → miss
  → asyncio.gather(
      quote_service.get_market_indices(),    # ~200-800ms（调外部接口）
      quote_service.get_watchlist_quotes(),  # ~200-800ms（调外部接口）
      _get_today_alerts(db),                 # ~30ms
      _get_push_history(db),                 # ~50ms
      _get_channel_status(db)                # ~10ms
    )
  → 写入 Redis（TTL=60s）
  → Jinja2 渲染
  → 总首响应 ≈ 800ms-1.5s（外部接口正常时）✅
```

### 4.5 前端刷新优化

```
JS setInterval(60s) → fetch('/market_data', {headers: {'If-None-Match': etag}})
  → 服务端计算数据 hash → 与 ETag 比对
    → 无变化: 返回 304（无 body，~10ms）
    → 有变化: 返回 200 + 新 HTML + 新 ETag（~100-300ms）
  → JS: 304 时不更新 DOM；200 时 innerHTML 替换
```

---

## 5. 改动范围与边界

### 5.1 包含的改动

- `backend/app/core/redis_cache.py` — 新增 Redis 客户端封装
- `backend/app/core/async_persistence.py` — 新增异步持久化工具
- `backend/app/services/quote_service.py` — `get_watchlist_quotes()` / `get_market_indices()` 增加缓存优先读取
- `backend/app/services/dashboard_service.py` — 并行化聚合逻辑，接入 Redis 缓存
- `backend/app/routers/dashboard.py` — Partial 端点裁剪，ETag 支持
- `frontend/src/templates/dashboard.html` — 骨架屏
- `frontend/public/js/dashboard.js` — ETag/304 处理

### 5.2 不包含的改动（明确边界）

- 不改 `cache_service.py` 的 SQLite 缓存架构（保留现有逻辑，Redis 作为新增层）
- 不改 `data_source_facade.py` 的接口契约
- 不引入 Celery / 独立 Worker 进程（异步落盘使用 `asyncio.to_thread()`）
- 不改其他 feature（F1-F5）的调用方逻辑
- 不做移动端响应式重构（006-dashboard 已完成）

---

## 6. 风险与缓解

| ID | 风险描述 | 严重度 | 概率 | 缓解方案 |
|:---|:---|:------:|:----:|:---|
| R-01 | Redis 未部署或服务不可用导致功能异常 | 高 | 低 | Redis 连接失败时自动降级为现有逻辑（直接调外部接口 / 查数据库），不阻塞功能 |
| R-02 | 缓存数据与实时数据不一致（行情延迟） | 中 | 低 | TTL 设为 60s（与现有刷新间隔一致），用户可接受分钟级延迟；缓存 key 带版本号便于强制刷新 |
| R-03 | 异步落盘失败导致历史数据丢失 | 中 | 低 | 异步落盘异常时记录 error log，不抛异常影响主响应；后台线程带重试机制 |
| R-04 | ETag hash 计算增加 CPU 开销 | 低 | 低 | 使用 lightweight hash（如 `hashlib.md5` 对序列化后数据），数据量小，开销可忽略 |
| R-05 | 并行化 DB 查询导致 SQLite 锁竞争 | 中 | 低 | 使用独立 session（非共享 session），控制并发度；SQLite 读操作互不阻塞 |

---

## 7. 性能目标验收标准

| 场景 | 目标 | 测量方式 |
|:---|:---|:---|
| 有缓存时首响应 | < 1s | Chrome DevTools Network → TTFB + 下载 |
| 冷启动首响应 | < 2s | 重启 Redis 后首次访问，同上 |
| `/market_data` 刷新（无变化） | < 50ms | 304 响应的 TTFB |
| `/market_data` 刷新（有变化） | < 300ms | 200 响应的 TTFB |
| 自选股 50 只时首响应 | < 1s | 添加 50 只自选股后测量 |

---

## 8. 下一步

1. 使用 `writing-plans` 技能生成详细实现计划（plan.md + tasks.md）
2. 按 Phase 顺序执行：Redis 模块 → quote_service 缓存 → dashboard_service 并行化 → 路由裁剪 → 前端骨架屏/ETag → 测试验证
