# 实施进度 · 自选股管理

## 当前任务
T1 已完成，等待下一任务。

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

## 阻塞项
（无）

## 最后更新
2026-05-30
