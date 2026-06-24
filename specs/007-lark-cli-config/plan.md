# Implementation Plan: 飞书 lark-cli 环境配置

**Branch**: `007-lark-cli-config` | **Date**: 2026-06-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-lark-cli-config/spec.md`

## Summary

将飞书主推送通道从历史 webhook 配置切换为只读 `.env` / 环境变量中的飞书应用配置。实现策略是复用现有 `FeishuClient` 与 `PushService` 主备通道链路：后端在运行时配置完整时创建 Feishu 主通道客户端，设置页移除 webhook 可编辑入口并展示只读配置状态，Telegram 备用通道、推送降级、推送日志和 Dashboard 排障体验保持不变。

## Technical Context

**Language/Version**: Python 3.x 后端；Jinja2 + HTML 模板前端；项目未锁定更细语言版本  
**Primary Dependencies**: FastAPI、SQLAlchemy、Pydantic Settings、Jinja2、pytest/httpx、现有 `FeishuClient`、现有 `PushService`、现有 `TelegramClient`、运行时 `lark-cli`  
**Storage**: SQLite/SQLAlchemy 现有设置与推送日志表；飞书主通道凭证不入库，仅从 `.env` / 环境变量读取  
**Testing**: pytest 单元/集成/E2E；Feishu 调用通过测试替身或 monkeypatch 覆盖，不读取真实 `.env` 密钥  
**Target Platform**: 私有部署单用户 Web 应用；Docker Compose / 本地后端进程；1280px+ 桌面浏览器  
**Project Type**: FastAPI 后端服务 + 服务端渲染设置页  
**Performance Goals**: 不增加应用启动外部依赖探测；保留现有推送异步提交、重试、降级和日志写入节奏；设置页仍为一次普通页面渲染  
**Constraints**: 不实现交易功能；不引入多用户/权限扩展；不新增付费服务；不在 UI、日志、错误提示中展示飞书密钥；中文用户界面；暗色设计体系；飞书配置只读 `.env`；`lark-cli` 缺失作为发送失败记录而非启动失败  
**Scale/Scope**: MVP 单用户；一个飞书主通道 + 现有 Telegram 备用通道；范围仅限主通道配置来源、运行时接线、设置页展示、README 与测试覆盖

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Application |
|-----------|--------|-------------|
| 信息展示边界，绝不交易 | PASS | 本 feature 只调整预警推送通道配置，不新增交易、下单或撮合能力。 |
| 单用户架构优先 | PASS | 不新增用户、权限、租户或多账号配置模型。 |
| 零成本数据源优先 / 年成本约束 | PASS | 复用已有飞书自建应用与 `lark-cli`，不引入付费通道。 |
| 推送即核心体验 | PASS | 优先恢复飞书主通道真实发送，同时保留 Telegram 降级与本地日志兜底。 |
| 桌面暗色中文 UI | PASS | 设置页仅替换推送通道区域文案/状态，继续使用现有中文模板与暗色 token。 |
| 测试先行 | PASS | 后续 tasks 将先补配置、工厂接线、设置页和全链路回归测试，再实现。 |
| Surgical Changes | PASS | 变更集中在配置、运行时工厂、设置页、README 和相关测试，不触碰行情/预警/Dashboard 业务逻辑。 |

**Gate Result**: PASS。无宪法冲突，无需 Complexity Tracking 豁免。

## Project Structure

### Documentation (this feature)

```text
specs/007-lark-cli-config/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── settings-push-channel-view.md
│   └── push-runtime-wiring.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── config.py                         # 新增飞书 env 配置字段与完整性判断来源
│   ├── main.py                           # 在 _push_service_factory() 中按 env 完整性创建 FeishuClient
│   ├── routers/
│   │   └── settings.py                   # 设置页上下文展示飞书只读状态；保存时不写 lark_webhook
│   └── services/
│       ├── feishu_client.py              # 复用现有 lark-cli 客户端；测试运行时能力缺失分类
│       └── push_service.py               # 复用现有主备、重试、降级、日志行为；按需补回归测试
├── tests/
│   ├── unit/
│   │   ├── test_config_database_main.py  # env 配置、push factory 接线、无 env 不创建主通道
│   │   ├── test_feishu_client.py         # lark-cli 缺失/失败分类与密钥不泄露
│   │   └── test_push_service.py          # 主通道失败、Telegram 降级、日志原因回归
│   ├── integration/
│   │   ├── test_settings.py              # settings GET/POST 不展示/不保存 webhook，展示 env 状态
│   │   └── test_full_chain_alert_to_push.py # 预警到推送链路优先使用 Feishu 主通道
│   └── e2e/
│       └── test_full_chain.py            # 端到端回归：配置缺失、降级、本地日志

frontend/
└── src/
    └── templates/
        └── settings.html                 # 移除飞书 webhook 输入，展示 env 只读配置说明和重启提示

README.md                                # 更新推送通道配置说明：飞书走 .env，Telegram 走设置页
```

**Structure Decision**: 保持现有单体 FastAPI/Jinja2 项目结构，不新增服务、不新增前端构建链路、不迁移数据库记录。飞书配置状态由后端运行时配置派生并传入现有设置页模板；推送发送继续走 `PushService` 的既有主备通道流程。

## Phase 0 Research Summary

Research documented in [research.md](./research.md). Key decisions:

- 飞书主通道配置只读 `.env` / 环境变量，不再读取或迁移旧 webhook 设置。
- `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_CHAT_ID` 均非空时创建 `FeishuClient`；`FEISHU_BRAND` 为可选项，缺省使用 `feishu`。
- `lark-cli` 可用性不在启动期阻断；发送时缺失或失败记录为可排查失败原因，并触发既有降级/日志路径。
- 设置页只展示完整/缺失状态、配置来源和重启生效提示，不展示任何敏感值。

## Phase 1 Design Summary

Design artifacts:

- [data-model.md](./data-model.md): 运行配置、诊断状态、通道状态、推送日志、设置页视图模型。
- [contracts/settings-push-channel-view.md](./contracts/settings-push-channel-view.md): 设置页 GET/POST 行为契约。
- [contracts/push-runtime-wiring.md](./contracts/push-runtime-wiring.md): 推送运行时工厂与主备通道接线契约。
- [quickstart.md](./quickstart.md): 后续实现完成后的验证路径。

## Constitution Check (Post-Design)

| Principle | Status | Post-design verification |
|-----------|--------|--------------------------|
| 信息展示边界，绝不交易 | PASS | 数据模型和契约只涉及推送配置/日志，不包含交易动作。 |
| 单用户架构优先 | PASS | 无用户维度配置，无权限模型。 |
| 零成本数据源优先 / 年成本约束 | PASS | 未新增付费供应商或云服务。 |
| 推送即核心体验 | PASS | 主通道真实接线与降级回归测试被列为核心 tasks。 |
| 桌面暗色中文 UI | PASS | UI contract 要求中文只读说明，继续使用现有设置页结构。 |
| 测试先行 | PASS | tasks 将按测试优先顺序拆分。 |
| Surgical Changes | PASS | contracts 与 tasks 限定到本 plan 列出的文件路径。 |

**Post-design Gate Result**: PASS。无未解决澄清项。

## Complexity Tracking

无宪法违反项；不需要复杂度豁免。
