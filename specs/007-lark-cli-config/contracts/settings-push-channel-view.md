# Contract: Settings Push Channel View

## Scope

This contract defines how the settings page exposes push-channel configuration after Feishu moves from webhook to `.env` / runtime configuration.

## GET `/settings`

### Required behavior

- Render the existing settings page.
- Show a read-only Feishu main-channel section.
- State in Chinese that Feishu is configured through `.env` / deployment environment variables.
- Show whether Feishu configuration is complete.
- Explain that `.env` changes require service restart or config reload before the page reflects new runtime values.
- Keep Telegram fields editable through the existing settings form.
- Keep data source and system preference fields unchanged.

### Feishu view data

The page context should provide a non-sensitive Feishu status object equivalent to:

| Field | Required | Description |
|-------|----------|-------------|
| `source_label` | yes | Human-readable source, `.env / 环境变量`. |
| `is_complete` | yes | True only when all required Feishu runtime variables are present. |
| `status_label` | yes | Chinese status label such as “已完整配置” or “未完整配置”. |
| `missing_hint` | no | Chinese non-sensitive hint for incomplete config. |
| `restart_hint` | yes | Chinese hint that service restart/reload is required after env changes. |

### Forbidden output

- No editable `lark_webhook` input.
- No Feishu webhook placeholder.
- No raw `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_BRAND`, or `FEISHU_CHAT_ID` values.
- No app secret in HTML, page context dumps, logs, or validation errors.

## POST `/settings`

### Accepted fields

The form save behavior remains limited to existing non-Feishu-runtime settings:

| Field | Behavior |
|-------|----------|
| `telegram_token` | Preserve existing encrypted settings behavior. |
| `telegram_chat_id` | Preserve existing settings behavior. |
| `datasource` | Preserve existing preference behavior. |
| `refresh_interval` | Preserve existing preference behavior. |
| `alert_cooldown` | Preserve existing preference behavior. |

### Feishu webhook handling

- `lark_webhook` is no longer an accepted active configuration field.
- If an old client or crafted request submits `lark_webhook`, the save path must not create or update Feishu webhook settings.
- Existing historical database records are not deleted automatically.
- Saving Telegram or preference fields must not modify Feishu runtime config status.

## Acceptance checks

- Opening settings shows Feishu `.env` source text and no webhook input.
- Saving settings does not write a new `lark_webhook` setting.
- Existing Telegram settings can still be saved and read.
- No Feishu secret values appear in rendered HTML.
