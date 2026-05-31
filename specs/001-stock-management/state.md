# 实施进度 · 自选股管理

## 当前任务
T5 已完成，Foundation 阶段可继续推进 T6。

## 已完成
- [X] T01 · 创建项目骨架：requirements.txt + Dockerfile + docker-compose.yml + .env.example
  - RED：2026-05-30 `docker build -t stock-mgt .` 失败，原因：缺少 Dockerfile。
  - GREEN：补齐 `requirements.txt`、`Dockerfile`、`docker-compose.yml`，并纳入 `.dockerignore`；`.env.example` 基线已存在，无需修改。
  - 验证：2026-05-30 `docker build -t stock-mgt .` 成功生成 `stock-mgt:latest`。
  - 审查修复：2026-05-30 扩展 `.dockerignore` 敏感本地配置排除（`.env*`，保留 `.env.example`，并排除 `.mcp.json`、`.credentials.*`）；`docker-compose.yml` 端口改为仅绑定 localhost。
  - 审查验证：2026-05-30 `docker compose config --quiet` 与 `docker build -t stock-mgt .` 均通过。
  - 复审修复：2026-05-30 在 `.dockerignore` 增加 `*.csv`，避免真实导入/持仓 CSV 被 `COPY . .` 打入镜像。
  - 复审验证：2026-05-30 `docker compose config --quiet` 与 `docker build -t stock-mgt .` 均通过。
  - 最终复审修复：2026-05-30 将 `.dockerignore` 的 `.credentials.yaml/.yml/.json` 具体规则收敛为 `.credentials.*`，覆盖 `.credentials.toml`、`.credentials.local`、`.credentials.dev` 等本地凭据文件。
  - 最终复审验证：2026-05-30 `docker compose config --quiet` 与 `docker build -t stock-mgt .` 均通过。

- [X] T02 · 创建配置与数据库层：app/config.py + app/database.py + app/main.py
  - RED：2026-05-30 `python -m pytest tests/unit/test_config_database_main.py` 失败，4 个用例均因 `ModuleNotFoundError: No module named 'app'` 暴露配置/数据库/FastAPI 入口尚不存在。
  - GREEN：新增 `app/__init__.py`、`app/config.py`、`app/database.py`、`app/main.py`；配置层读取 `DATABASE_URL` 并提供 SQLite 默认值，数据库层暴露 `engine`/`SessionLocal`/`Base`/`init_db()`，FastAPI 入口提供 `/health` 与 Swagger `/docs`。
  - 验证：2026-05-30 `python -m pytest tests/unit/test_config_database_main.py` 通过（4 passed）；`uvicorn app.main:app --host 127.0.0.1 --port 8001` 启动后 `/health` 与 `/docs` 均返回 200。

- [X] T03 · 创建 Stock 数据模型：app/models/stock.py
  - RED：2026-05-30 `python -m pytest tests/unit/test_models.py` 失败，4 个用例均因 `ModuleNotFoundError: No module named 'app.models'` 暴露 Stock 模型尚不存在。
  - GREEN：新增 `app/models/__init__.py` 与 `app/models/stock.py`；Stock 使用 `stocks` 表，包含 `code/name/market/sector/status` 字段，`code` 为主键，`name`/`market` 非空。
  - 验证：2026-05-30 `python -m pytest tests/unit/test_models.py` 通过（4 passed）；`python -m pytest tests/unit/test_config_database_main.py` 回归通过（4 passed）。
  - 审查修复 RED：2026-05-31 `python -m pytest tests/unit/test_models.py` 失败，新增应用 lifespan 初始化路径用例发现 `stocks` 不在 `init_db()` 创建后的临时 SQLite 表列表中（`AssertionError: assert 'stocks' in []`）。
  - 审查修复 GREEN：在 `app.database.init_db()` 调用 `Base.metadata.create_all()` 前集中导入 `app.models`，确保 Stock 模型注册到 metadata。
  - 审查修复验证：2026-05-31 `python -m pytest tests/unit/test_models.py` 通过（5 passed）；`python -m pytest tests/unit/test_config_database_main.py` 回归通过（4 passed）。

- [X] T04 · 创建 Group 数据模型：app/models/group.py
  - RED：2026-05-31 `python -m pytest tests/unit/test_models.py` 失败，新增用例发现 `groups` 表不存在（`sqlite3.OperationalError: no such table: groups`），且 `app.models.group` 尚未实现。
  - GREEN：新增 `app/models/group.py` 与 `Group` 模型（`id/name/created_at/is_default`），在 `app.models` 导出，并在 `init_db()` 建表后幂等创建 `id=1, name="默认分组", is_default=True` 的默认分组。
  - 验证：2026-05-31 `python -m pytest tests/unit/test_models.py` 通过（10 passed）；`python -m pytest tests/unit/test_config_database_main.py` 回归通过（4 passed）。
  - 审查修复 RED：2026-05-31 `python -m pytest tests/unit/test_models.py` 失败，新增 PostgreSQL DDL 用例发现 `groups.id` 仍编译为 `SERIAL`，未避开默认分组 `id=1` 的序列起点风险。
  - 审查修复 GREEN：将 `Group.id` 改为 `Identity(start=2)`，PostgreSQL DDL 编译为 identity 且起点为 2，避免后续自定义分组与默认分组主键冲突。
  - 审查修复验证：2026-05-31 `python -m pytest tests/unit/test_models.py tests/unit/test_config_database_main.py` 通过。

- [X] T05 · 创建 WatchlistItem 数据模型：app/models/watchlist.py
  - RED：2026-05-31 `python -m pytest tests/unit/test_models.py` 失败，新增 T5 用例发现 `watchlist_items` 未由 lifespan/init_db 创建，且 `app.models.watchlist` 尚未实现。
  - GREEN：新增 `app/models/watchlist.py` 与 `WatchlistItem` 模型（`id/stock_code/group_id/added_at/cost_price/shares`），`stock_code` 外键到 `stocks.code` 且唯一，`group_id` 外键到 `groups.id`，并建立 `stock`/`group` 关系；在 `app.models` 导出以供 `init_db()` 注册。
  - 验证：2026-05-31 `python -m pytest tests/unit/test_models.py tests/unit/test_config_database_main.py` 通过（22 passed）。
  - 审查修复 RED：2026-05-31 `python -m pytest tests/unit/test_models.py` 失败，新增生产 SQLite `init_db()` 路径用例发现非法 `WatchlistItem(stock_code="999999", group_id=999)` 提交未触发 `IntegrityError`（`Failed: DID NOT RAISE`）。
  - 审查修复 GREEN：在 SQLite engine 连接建立时通过 SQLAlchemy event listener 执行 `PRAGMA foreign_keys=ON`，使 `stocks.code` / `groups.id` 外键在默认 SQLite 环境真实生效。
  - 审查修复验证：2026-05-31 `python -m pytest tests/unit/test_models.py tests/unit/test_config_database_main.py` 通过（23 passed）。

## 阻塞项
（无）

## 最后更新
2026-05-31
