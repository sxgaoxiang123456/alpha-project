# Quickstart: 飞书 lark-cli 环境配置

## Purpose

This quickstart describes how to validate the feature after implementation. It does not require real Feishu credentials in tests and must not print real `.env` values.

## Preconditions

- Backend environment is prepared through the project setup script.
- Tests use temporary environment overrides or monkeypatching for Feishu variables.
- Real `.env` secrets are not read, printed, or committed.
- Telegram fallback tests use existing test doubles or local settings fixtures.

## Verification paths

### 1. Backend unit tests

Run focused unit tests after implementation:

```bash
cd backend
.venv/bin/python -m pytest tests/unit/test_config_database_main.py tests/unit/test_feishu_client.py tests/unit/test_push_service.py
```

Expected coverage:

- Feishu env fields are loaded from runtime configuration.
- Feishu config completeness is true only when all required variables are present.
- `_push_service_factory()` creates a Feishu client when config is complete.
- `_push_service_factory()` does not create a Feishu client when config is incomplete.
- `lark-cli` command failure or absence is recorded as a client/runtime failure.
- Error messages do not expose `FEISHU_APP_SECRET`.

### 2. Settings integration tests

Run settings route integration checks:

```bash
cd backend
.venv/bin/python -m pytest tests/integration/test_settings.py
```

Expected coverage:

- GET `/settings` renders Feishu `.env` source instructions.
- GET `/settings` does not render a Feishu webhook input.
- GET `/settings` does not render Feishu secret values.
- POST `/settings` saves Telegram, datasource, refresh interval, and cooldown settings as before.
- POST `/settings` does not create or update `lark_webhook`.

### 3. Push chain integration tests

Run push-chain focused checks:

```bash
cd backend
.venv/bin/python -m pytest tests/integration/test_full_chain_alert_to_push.py tests/integration/test_push_api.py
```

Expected coverage:

- Alert-triggered push prefers Feishu when env config is complete.
- Feishu primary failure retries and then falls back to Telegram when available.
- Missing Feishu config does not use legacy webhook settings.
- Push logs preserve success/failure/fallback state and duration.

### 4. Full regression

Run the backend regression suite:

```bash
cd backend
.venv/bin/python -m pytest tests/
```

Expected outcome:

- Existing stock management, data source, realtime quotes, alert rules, Dashboard, settings, Telegram, and push-log behavior remain green.

### 5. Manual settings-page smoke test

Start the backend service after implementation:

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app
```

Then open `/settings` in a browser and verify:

- The push channel section explains Feishu is configured by `.env` / deployment environment.
- No “飞书 Webhook 地址” input appears.
- The page shows complete/incomplete Feishu status without showing secrets.
- Telegram settings remain editable.
- Saving unrelated settings does not change Feishu status.

## Safety notes

- Do not paste real Feishu app secrets into tests, screenshots, logs, or issue comments.
- Use variable names and presence/absence status when documenting configuration.
- A missing `lark-cli` runtime should be treated as a push-send diagnostic failure, not a failed application startup.
