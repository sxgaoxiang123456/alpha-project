# 项目教训沉淀

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
