# Contract: Push Runtime Wiring

## Scope

This contract defines how runtime configuration connects Feishu `lark-cli` credentials to the existing push service.

## Runtime inputs

| Variable | Required for Feishu primary channel | Notes |
|----------|-------------------------------------|-------|
| `FEISHU_APP_ID` | yes | Presence only may be exposed; value must not be shown. |
| `FEISHU_APP_SECRET` | yes | Secret; never expose in UI/logs/errors. |
| `FEISHU_BRAND` | yes | Required by existing Feishu client constructor. |
| `FEISHU_CHAT_ID` | yes | Presence only may be exposed; value must not be shown. |

Telegram continues to use existing settings-page/database configuration and is outside this contract change.

## Push service factory behavior

When all Feishu runtime inputs are present:

1. Create a `FeishuClient` with the env-derived values.
2. Create a `TelegramClient` only when existing Telegram settings are complete.
3. Return `PushService(db=..., feishu_client=..., telegram_client=...)`.
4. Do not execute `lark-cli` during factory creation.

When any Feishu runtime input is missing:

1. Do not create a `FeishuClient`.
2. Do not use historical `lark_webhook` settings as a fallback.
3. Still create `TelegramClient` when Telegram settings are complete.
4. Return `PushService` with `feishu_client=None` and the existing Telegram client behavior.

## Send-time behavior

- Feishu remains the primary channel when a Feishu client exists and channel health allows it.
- Feishu send failures follow existing retry behavior.
- After Feishu retries fail, Telegram fallback follows existing `PushService` rules.
- If both channels fail or are unavailable, local push log records the failure.
- Missing `lark-cli` is recorded as a client/runtime failure, not an application startup failure.

## Error and secrecy rules

- Feishu app secret must not appear in `PushLog.error_reason`, channel status errors, UI text, or test output.
- Authentication failures should be classified as auth-related without printing credentials.
- Command-not-found or unavailable runtime client failures should be classifiable for user troubleshooting.
- Historical webhook values must not influence any new Feishu primary-channel decision.

## Acceptance checks

- Complete Feishu env config creates a Feishu client in runtime factory tests.
- Incomplete Feishu env config does not create a Feishu client.
- Submitted or stored `lark_webhook` does not create a Feishu client.
- Feishu failure can fall back to Telegram and preserve primary failure reason.
- Missing `lark-cli` produces a diagnosable failure record without blocking startup.
