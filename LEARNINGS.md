# 项目教训沉淀

## 2026-06-03 · tool-quirk · 002-data-failover
**现象 / 决策**: SQLAlchemy `session.merge(obj)` 在并发下不是原子 upsert。两个线程同时 `merge` 同一主键时，由于事务隔离都看到"记录不存在"，同时标记为 pending，第一个 commit 成功，第二个 commit 抛 `IntegrityError: UNIQUE constraint failed`。
**应对**: 需要真正并发安全的 upsert 时，要么用数据库原生 `INSERT OR REPLACE`/`ON CONFLICT`，要么在应用层加锁。不要假设 ORM 的 merge 能替你做并发控制。
**应用范围**: 任何有并发写入且 key 可能冲突的 feature。
**相关文件**: `backend/app/services/cache_service.py:24-37`, `backend/tests/unit/test_concurrency.py:121-151`

## 2026-06-03 · pitfall · 002-data-failover
**现象 / 决策**: SQLite 存储 naive datetime，但代码里混用了 `datetime.now(timezone.utc)`（offset-aware）和 `datetime.utcnow()`（naive）。比较时抛 `TypeError: can't compare offset-naive and offset-aware datetimes`，导致缓存过期判断和熔断器时间戳全崩。
**应对**: 一旦选定 SQLite 做存储，所有 datetime 字段从第一天就统一用 naive UTC（`datetime.utcnow()`），不要混用。这是 schema 级决策，改起来要跨 N 个文件。
**应用范围**: 所有用 SQLite 做持久化的 feature。
**相关文件**: `backend/app/services/cache_service.py:11-13`, `backend/app/core/circuit_breaker.py:65-101`, `backend/app/models/cache_entry.py:18-22`

## 2026-06-03 · pattern · 002-data-failover
**现象 / 决策**: 第三方库（akshare / baostock）在测试环境不一定能装，直接 `patch("akshare.stock_zh_a_spot_em")` 会因为模块无法导入而失败。
**应对**: 把第三方调用抽成实例方法（如 `_fetch_from_akshare()`），在方法内部 `import akshare as ak`。测试时用 `patch.object(source, "_fetch_from_akshare", return_value=...)` 隔离，不需要安装外部库。
**应用范围**: 任何依赖外部 SDK/第三方库的 adapter/facade 层。
**相关文件**: `backend/app/services/data_source.py:94-99`, `backend/tests/unit/test_data_source.py:36-69`

## 2026-06-03 · ai-stuck · 002-data-failover
**现象 / 决策**: config.py 里早早声明了 `data_source_timeout: int = 10` 和 `data_source_retry: int = 1`，但 AkShare 的 `stock_zh_a_spot_em()` 根本没暴露 timeout 参数，代码里也没有重试逻辑。配置存在但没有任何代码引用，成为"死配置"。
**应对**: 配置项不是越多越好。如果底层 API 不支持某个参数，先别声明；等真的需要并且能用上的时候再加。死配置会误导后续维护者。
**应用范围**: 所有新增配置的 feature。
**相关文件**: `backend/app/config.py:14-15`

## 2026-06-03 · pitfall · 002-data-failover
**现象 / 决策**: 熔断器 Half-Open → Closed 的恢复逻辑最初把"进入 Half-Open 的第一次成功"计入了 `consecutive_successes`。导致只需要 1 次成功就恢复，与 spec 要求的"连续 2 次成功"不符。
**应对**: 状态机转换和计数器递增要分开想清楚。进入新状态时把计数器清零，只有"停留在这个状态期间"的事件才递增计数器。画状态图时把计数器变化标在每个转移边上。
**应用范围**: 任何有状态机 + 计数器的逻辑（熔断器、重试、限频）。
**相关文件**: `backend/app/core/circuit_breaker.py:79-94`, `backend/tests/unit/test_circuit_breaker.py:94-113`

## 2026-06-03 · pitfall · 001-stock-management
**现象 / 决策**: SQLite `BEGIN IMMEDIATE` 只阻止并发写锁，不阻止 `SELECT` 读锁。两个事务仍能同时读到 `count=99` 然后都插入成功，导致 100 只上限被突破。
**应对**: 不要迷信数据库隔离级别解决应用层竞态；单进程用 `threading.Lock()` 串行化临界区，多进程必须用分布式锁或 advisory lock。
**应用范围**: 任何有计数/配额/库存式上限的 feature。
**相关文件**: `backend/app/routers/watchlist.py:18-70`, `backend/tests/integration/test_concurrent_watchlist_limit.py`

## 2026-06-03 · pattern · 001-stock-management
**现象 / 决策**: 即使加了应用层锁，并发下数据库唯一约束仍可能抛出 `IntegrityError`（锁粒度或窗口问题）。
**应对**: 写操作永远捕获 `IntegrityError` 并返回有意义的 HTTP 状态码（409），不让 500 泄露。锁 + 约束双重保险。
**应用范围**: 所有并发写路由。
**相关文件**: `backend/app/routers/watchlist.py:61-68`

## 2026-06-03 · pattern · 001-stock-management
**现象 / 决策**: CSV 导入/导出时，单元格以 `=+-@` 开头会被 Excel / Google Sheets / WPS 解释为公式执行，`=cmd|' /C calc'!A0` 可触发命令执行。
**应对**: 导入和导出双向净化——对以 `=+-@` 开头的字段前缀单引号 `'`，Excel 会将其视为文本。封装为 `_sanitize_csv_field()` 供所有 CSV 相关 feature 复用。
**应用范围**: 任何 CSV/Excel 导入导出功能。
**相关文件**: `backend/app/services/csv_export.py:7-16`, `backend/app/services/csv_import.py:7-16`

## 2026-06-03 · tool-quirk · 001-stock-management
**现象 / 决策**: `fastapi.testclient.TestClient` 每次实例化都会触发 lifespan 事件（含 `init_db()`）。并发测试中多个线程同时创建 `TestClient` 会导致 `table already exists` 建表冲突。
**应对**: 并发测试前先预热一次 `TestClient`（触发 lifespan 建表），后续并发请求不再重复建表。
**应用范围**: 所有涉及 lifespan 初始化数据库的并发集成测试。
**相关文件**: `backend/tests/integration/test_concurrent_watchlist_limit.py:147-149`

---

每个 feature 收尾时人工追加 1-5 条，新的加在最顶部。不值得记的不记，宁可空一个 feature
也别凑数。

条目模板:

  ## <日期> · <type> · <feature 编号-名>
  **现象 / 决策**:一句话讲清问题。
  **应对**:下次怎么做。
  **应用范围**:哪类 feature 该回看这条(可选)。

type 取值:pitfall(踩坑) / decision-rethink(决策反思) / pattern(可复用套路) /
  tool-quirk(工具怪癖) / ai-stuck(AI 卡点) / arch(架构教训)。
