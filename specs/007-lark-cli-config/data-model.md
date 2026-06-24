# Data Model: 飞书 lark-cli 环境配置

## FeishuRuntimeConfig（飞书运行配置）

**Purpose**: 表示运行时是否具备可创建飞书主通道客户端的必要配置。

**Fields**:

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `app_id_present` | boolean | `FEISHU_APP_ID` | 只表示是否非空，不暴露值。 |
| `app_secret_present` | boolean | `FEISHU_APP_SECRET` | 只表示是否非空，不暴露值。 |
| `brand_present` | boolean | `FEISHU_BRAND` | 只表示是否非空，不暴露值。 |
| `chat_id_present` | boolean | `FEISHU_CHAT_ID` | 只表示是否非空，不暴露值。 |
| `is_complete` | boolean | derived | 四个字段均 present 时为 true。 |
| `source` | string | constant | 固定为 `.env / 环境变量`。 |

**Validation Rules**:

- `is_complete=true` requires all four presence fields to be true.
- Any missing field means Feishu primary channel is not created.
- No field in this model may contain the raw app secret or raw credential values.

**Relationships**:

- Used by runtime push wiring to decide whether to instantiate `FeishuClient`.
- Used by settings page view model to display read-only status.

## FeishuDiagnosticState（飞书诊断状态）

**Purpose**: 表示用户可从设置页和推送日志理解的飞书通道排障状态。

**Fields**:

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `config_complete` | boolean | FeishuRuntimeConfig | 配置是否完整。 |
| `missing_field_labels` | list[string] | derived | 可展示字段名称，如“应用标识”“应用密钥”“群聊标识”；不展示值。 |
| `last_failure_category` | string/null | PushLog / FeishuClient result | 可选值：`auth_error`、`rate_limited`、`network_error`、`client_error`、`unknown`。 |
| `runtime_client_unavailable` | boolean | derived | 当 failure category 为 `client_error` 且指向运行时能力缺失时为 true。 |
| `restart_required_hint` | boolean | constant | 设置页固定提示 `.env` 修改需重启或重新加载服务。 |
| `guidance` | string | derived | 中文排障提示，不含敏感值。 |

**Validation Rules**:

- `missing_field_labels` may name missing variables conceptually but must not include actual secret content.
- `guidance` must not include `FEISHU_APP_SECRET` value,命令行参数中的密钥，或完整凭证明文。
- Runtime command absence is diagnostic data, not startup-blocking state.

## PushChannelStatus（推送通道状态）

**Purpose**: 表示 Feishu 主通道和 Telegram 备用通道的健康状态，复用现有模型。

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `channel` | string | `feishu` or `telegram`。 |
| `status` | string | 现有状态：`active`、`degraded`、`unavailable`。 |
| `consecutive_failures` | integer | 连续失败次数。 |
| `last_error` | string/null | 失败原因，必须脱敏。 |
| `updated_at` | datetime | 最近状态更新时间。 |

**State Transitions**:

```text
active --send failure(s)--> degraded --continued failure--> unavailable
active/degraded/unavailable --successful send--> active
```

**Feature-specific Rule**:

- Feishu env 配置不完整时，不应借用历史 webhook 把 Feishu 标记为可发送主通道。

## PushLog（推送日志）

**Purpose**: 表示每次推送请求的结果记录，复用现有日志模型。

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `message_id` | string | 单次推送请求标识。 |
| `message_type` | string | 预警/测试等消息类型。 |
| `channel` | string | 最终使用或尝试的通道。 |
| `status` | string | 现有状态：`pending`、`sent`、`failed`、`fallback`。 |
| `error_reason` | string/null | 失败原因，必须脱敏。 |
| `duration_ms` | integer/null | 发送耗时。 |
| `created_at` | datetime | 创建时间。 |

**Feature-specific Rule**:

- Feishu 主通道失败后 Telegram 成功时，保留现有 fallback 记录语义。
- 双通道均失败时，优先保留可排查的 Feishu 主通道失败原因。
- `error_reason` must not expose app_secret or raw credential values.

## SettingsPushChannelView（设置页推送通道视图）

**Purpose**: 表示设置页展示给用户的推送通道配置状态。

**Fields**:

| Field | Type | Notes |
|-------|------|-------|
| `feishu_source_label` | string | 固定说明“飞书主通道由 .env / 部署环境配置”。 |
| `feishu_config_complete` | boolean | 来自 FeishuRuntimeConfig。 |
| `feishu_status_label` | string | “已完整配置”或“未完整配置”。 |
| `feishu_missing_hint` | string/null | 缺失提示，不含具体值。 |
| `feishu_restart_hint` | string | 固定说明修改 `.env` 后需重启或重新加载服务。 |
| `telegram_token` | string/null | 现有设置页字段，按既有脱敏/加密规则处理。 |
| `telegram_chat_id` | string/null | 现有设置页字段。 |

**Validation Rules**:

- View must not include `lark_webhook` as an editable Feishu setting.
- View must not include raw `FEISHU_APP_SECRET` or other credential values.
- Saving settings must not create, update, or clear Feishu env-derived status.
