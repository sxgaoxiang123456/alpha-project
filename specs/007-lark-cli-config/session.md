# 007-lark-cli-config · 开发会话总结

## 基本信息

| 项目 | 值 |
|:---|:---|
| Feature | 007-lark-cli-config · 飞书 lark-cli 环境配置 |
| 分支 | feat-007-lark-cli-config → develop |
| 创建 | 2026-06-08 |
| 完成 | 2026-06-09 |
| Tag | v0.1.0-007-lark-cli-config |
| 总测试 | 490 单元/集成 + 36 E2E 全绿 |
| 飞书真实发送 | ✅ 飞书群收到卡片消息 |

## 变更摘要

### 后端 (5 files)

| 文件 | 变更 |
|:---|:---|
| `backend/app/config.py` | +FEISHU_APP_ID / SECRET / BRAND / CHAT_ID 字段；feishu_config_complete 属性；brand 空值 fallback validator |
| `backend/app/main.py` | _push_service_factory 提升为模块级函数，按 feishu_config_complete 创建 FeishuClient；移除 lifespan 内旧闭包 |
| `backend/app/routers/settings.py` | 移除 lark_webhook 表单映射；_build_feishu_status() 构建只读配置状态含 missing_hint |
| `backend/app/services/feishu_client.py` | lark-cli v1.0.1 适配：_ensure_config 自动注册，--as bot 调用，路径去重，receive_id_type=chat_id，stderr 脱敏 |
| `README.md` | 推送通道文档：飞书走 .env，Telegram 走设置页 |

### 前端 (1 file)

| 文件 | 变更 |
|:---|:---|
| `frontend/src/templates/settings.html` | 飞书 webhook 输入框 → .env 只读状态面板（含完整/缺失提示、重启说明） |

### 测试 (6 files，+27 tests)

| 文件 | 新增测试 |
|:---|:---|
| `tests/unit/test_config_database_main.py` | 5 Feishu env config + 4 factory wiring |
| `tests/unit/test_feishu_client.py` | 2 stderr 脱敏验证 + 1 lark-cli 不可用分类 |
| `tests/unit/test_push_service.py` | 3 Feishu 降级/日志回归 |
| `tests/integration/test_settings.py` | 7 设置页无 webhook + 1 missing_hint + 2 真库 webhook 回归 |
| `tests/integration/test_full_chain_alert_to_push.py` | 2 Feishu 主通道分发 + 2 缺失回归 + 3 P0 journey J001 |

## Code Review 门禁

| 类别 | 数量 | 处置 |
|:---|:---|:---|
| Critical | 0 | — |
| Important | 4 | 3 修复 (I1 stderr 脱敏, I2 missing_hint, I3 死代码) + 1 Push back (I4) |
| Minor | 4 | 2 Push back (M2 type:ignore, M3 颜色语义) + 2 Deferred (M1 brand spec, M4 lazy import) |

## 路由补测闭环

| 阶段 | 执行器 | 产出 |
|:---|:---|:---|
| test-routing-advisor | — | 判定主类=局部前后端，次类=单后端；识别完整功能链路 J001 |
| full-chain-testing | 3 journey tests | F3→F4→F5→飞书 P0 旅程安全网（H1-H4 交接点验证） |
| backend-testing | 2 gap tests | 真库 webhook 回归 + stderr 脱敏验证 |

## 全链路真实发送验证

生产环境 lark-cli v1.0.1 适配修复（3 个兼容性问题）：

| # | 问题 | 修复 |
|:---|:---|:---|
| 1 | `--app-id`/`--app-secret` v1.0.1 不支持 | _call_lark_cli 改用 `--as bot` + _ensure_config 自动注册 |
| 2 | 路径重复 `/open-apis/open-apis/im/...` | 路径改为 `im/v1/messages`（lark-cli 自动加前缀） |
| 3 | 缺少 `receive_id_type=chat_id` | 添加 `--params '{"receive_id_type":"chat_id"}'` |

**验证结果：** `start.sh` 重启 → 设置页「已完整配置」→ 飞书群收到卡片 ✅

## 已知遗留

- `lark-cli` 当前版本 1.0.1，提示可升级至 1.0.49（非阻塞）
- `test_health_checker.py::test_open_source_two_successes_restores_closed` 为已有 flaky 测试（AkShare 外部调用时序），非 007 引入

---

创建时间: 2026-06-09
