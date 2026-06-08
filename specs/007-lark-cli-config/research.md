# Research: 飞书 lark-cli 环境配置

## Decision 1: 飞书主通道配置只读 `.env` / 环境变量

**Decision**: 飞书主通道只从运行环境读取 `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_BRAND`、`FEISHU_CHAT_ID`，不再使用设置页或数据库中的历史 `lark_webhook`。

**Rationale**: 当前实际发送链路是 `FeishuClient` 通过 `lark-cli` 调用飞书 Open API，所需参数不是机器人 webhook。继续读取 webhook 会让主通道配置来源和发送客户端构造参数不一致，导致真实发送无法闭环。

**Alternatives considered**:

- 继续保留 webhook 作为主通道：拒绝，和 `lark-cli` 技术方向冲突。
- 在设置页采集 app_id/app_secret/chat_id：拒绝，会扩大敏感凭证落库和脱敏范围。
- 自动迁移旧 webhook 记录：拒绝，旧值无法转换为 Open API 凭证，迁移没有语义价值。

## Decision 2: 配置完整性以四个 Feishu 运行时变量非空为准

**Decision**: `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_BRAND`、`FEISHU_CHAT_ID` 均存在且非空时，飞书主通道视为可尝试发送；任一缺失则不创建 Feishu 主通道客户端。

**Rationale**: 现有 `FeishuClient` 构造函数需要 app_id、app_secret、brand、chat_id。半配置会导致发送阶段失败且容易泄露排障噪声，因此应在运行时工厂阶段将其判定为“配置未完整”。

**Alternatives considered**:

- 只要求 app_id/app_secret/chat_id：拒绝，和现有客户端构造签名不完全一致。
- 半配置也创建客户端，让发送时报错：拒绝，会把可静态判断的配置缺失变成运行时失败。
- 在设置页显示具体变量值：拒绝，敏感信息泄露风险高。

## Decision 3: 复用 `FeishuClient` + `PushService`，只修正工厂接线

**Decision**: 不重写推送服务。后续实现只在 `backend/app/main.py` 的 `_push_service_factory()` 中按配置完整性创建 `FeishuClient` 并传给 `PushService`，保留现有重试、降级、通道健康和日志逻辑。

**Rationale**: 当前 `PushService` 已经具备 Feishu 优先、失败重试、Telegram 降级、本地日志和状态记录能力。缺口是运行时没有创建 Feishu 客户端，而不是推送策略缺失。

**Alternatives considered**:

- 新增独立 Feishu 推送服务：拒绝，会重复已有主备链路并扩大回归面。
- 修改 `PushService` 的通道策略：拒绝，本 feature 明确要求保留既有降级/日志体验。
- 将 Telegram 也改为环境变量配置：拒绝，不属于本 feature 范围。

## Decision 4: 设置页展示只读 Feishu 状态并移除 webhook 输入

**Decision**: 设置页不再展示可编辑的“飞书 Webhook 地址”输入框；改为展示飞书主通道由 `.env` / 部署环境维护、当前配置完整/缺失、修改后需重启或重新加载服务生效的中文说明。

**Rationale**: webhook 输入框会误导用户保存无效配置。设置页仍需要给用户排障入口，但只能展示非敏感状态，不能采集或回显 app_secret。

**Alternatives considered**:

- 保留 webhook 输入但禁用：拒绝，仍会强化错误配置模型。
- 展示脱敏后的 app_id/chat_id：拒绝，当前验收只要求完整/缺失；展示更多字段会增加泄露和维护成本。
- 完全移除飞书区域：拒绝，会让用户无法理解主通道配置来源和重启边界。

## Decision 5: `lark-cli` 缺失是发送时诊断，不是启动门禁

**Decision**: 应用启动时不主动执行 `lark-cli` 探测；当 Feishu 配置完整但运行时缺少命令或命令失败时，`FeishuClient` 返回可记录的客户端错误，`PushService` 按既有规则降级或记录失败。

**Rationale**: 私有部署环境可能暂时没有安装命令行工具，但这不应阻塞行情、预警、设置页和本地日志能力。发送时失败记录比启动失败更符合本 feature 的“不中断其他功能”约束。

**Alternatives considered**:

- 启动时强校验 `lark-cli`：拒绝，会影响系统启动和非推送功能。
- Dockerfile 内强制安装并作为本 feature 必改项：拒绝，本 feature 聚焦配置接线；部署安装可在后续部署专项处理。
- 静默忽略 Feishu 失败：拒绝，会破坏用户排障体验。

## Decision 6: 测试以接线和安全边界为核心

**Decision**: 后续实现需要覆盖配置字段、工厂创建真实 `FeishuClient`、缺失配置不创建主通道、设置页不保存 webhook、Feishu 失败降级 Telegram、错误信息不包含 app_secret。

**Rationale**: 过往缺口集中在 UI 字段和客户端构造参数不一致，以及 `_push_service_factory()` 始终传入 `feishu_client=None`。测试必须覆盖真实接线，而不能只 mock `PushService` 内部行为。

**Alternatives considered**:

- 只测 `PushService`：拒绝，无法发现主通道从未创建的问题。
- 使用真实 `.env` 凭证做集成测试：拒绝，会泄露敏感信息且不可重复。
- 不测 settings POST 忽略 webhook：拒绝，历史表单字段可能继续写入无效配置。

## Decision 7: README 更新为部署说明，既有 feature 文档不修改

**Decision**: README 的推送通道配置说明应随实现更新：飞书通过 `.env` / 部署环境配置，Telegram 仍通过设置页配置。既有 feature 文档如 `specs/005-*`、`specs/006-*` 不在本 feature 中修改。

**Rationale**: README 是用户部署入口，当前 webhook 文案会误导排障。历史 feature 文档属于既有设计记录，用户明确要求不改。

**Alternatives considered**:

- 同步修改历史 feature 文档：拒绝，违反本次范围。
- 不更新 README：拒绝，会保留用户-facing 的错误配置说明。
