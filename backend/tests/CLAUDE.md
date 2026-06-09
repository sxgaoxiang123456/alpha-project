# 测试指南

> 任何涉及测试的操作前必读。核心原则：**分两批跑，event loop 零容忍。**

## 1. 运行规则

```bash
# 第一批：unit + integration（一起跑，< 2 min）
.venv/bin/python -m pytest tests/unit/ tests/integration/ -v

# 第二批：e2e（单独跑，约 6-10 min）
.venv/bin/python -m pytest tests/e2e/ -v
```

**严禁 `pytest tests/` 一把梭**。E2E 的 uvicorn 子进程会污染 pytest-asyncio STRICT 模式的事件循环，导致后续 unit/integration 中的 async 测试异常（mock call_count=0、coroutine never awaited 等）。

## 2. 事件循环铁律

生产代码中**禁止**以下模式：

```python
# ❌ 禁止：条件事件循环检测 + 后台任务派发
try:
    loop = asyncio.get_running_loop()
    loop.create_task(some_async_func())
except RuntimeError:
    asyncio.run(some_async_func())

# ❌ 禁止：在非入口函数中调用 asyncio.run()
asyncio.run(some_async_func())
```

**正确做法**：无 I/O await 点的函数改为同步；确需异步时由 route handler 层管理，服务层保持同步。

## 3. E2E fixture 规范

- **健康检查必须用 `/health`，禁止用 `/`**（`/` 触发 Dashboard 数据聚合，外部数据源可能超时 10s+）
- `cwd=project_root`，`PYTHONPATH=project_root`，`--port 0`（随机端口）
- Dashboard 页面请求 `timeout=30`，其余 API `timeout=5`
- 项目仅支持 1280px+ 桌面端，移动端测试已全部移除，不要新增

## 4. 常见失败速查

| 症状 | 根因 | 修复 |
|:---|:---|:---|
| `asyncio.run() cannot be called from a running event loop` | 生产代码或测试中调了 `asyncio.run()` | 改为同步或 `@pytest.mark.asyncio` + `await` |
| `Backend health check failed` | `/` 超时或 uvicorn 启动失败 | 健康检查改用 `/health` |
| mock `call_count == 0` | `asyncio.get_running_loop()` 意外命中，后台任务未调度 | 移除事件循环检测，改为同步调用 |
| 单测独立通过但全量失败 | E2E 子进程污染事件循环 | 分两批运行 |

## 5. 测试数据

| 层级 | 数据库 | 数据准备 |
|:---|:---|:---|
| unit | `sqlite:///:memory:` | 测试内直接 insert |
| integration | SQLite 文件 | fixture seed |
| e2e | `tmp_path_factory.mktemp()` | `_seed_xxx_data(db)` |
