"""Settings 路由 — 配置页面渲染与持久化。"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.dependencies import get_db
from backend.app.schemas.settings import SettingCategory
from backend.app.services.settings_service import SettingsService

router = APIRouter(tags=["settings"])

# 飞书主通道不再由设置页表单采集，配置来源为 .env / 环境变量。
# lark_webhook 保留在映射中以忽略旧客户端提交，但不创建或更新记录。

# 前端表单字段名 → (setting_key, category, is_encrypted)
_FORM_FIELDS = {
    "telegram_token": ("telegram_token", SettingCategory.TELEGRAM, True),
    "telegram_chat_id": ("telegram_chat_id", SettingCategory.TELEGRAM, False),
    "datasource": ("datasource", SettingCategory.DATASOURCE, False),
    "refresh_interval": ("refresh_interval", SettingCategory.PREFERENCE, False),
    "alert_cooldown": ("alert_cooldown", SettingCategory.PREFERENCE, False),
}

# lark_webhook 不再作为活跃表单字段，仅忽略提交
_IGNORED_FORM_FIELDS = {"lark_webhook"}


def _get_encryption_key() -> bytes | None:
    """从应用配置读取加密密钥。"""
    key = get_settings().encryption_key
    if key is None:
        return None
    return key.encode() if isinstance(key, str) else key


def _load_settings(db: Session) -> dict[str, str]:
    """从数据库加载所有配置，按前端表单字段名组织。"""
    service = SettingsService(db, encryption_key=_get_encryption_key())
    settings: dict[str, str] = {}
    for form_field, (key, _, _) in _FORM_FIELDS.items():
        value = service.get_setting(key)
        if value is not None:
            settings[form_field] = value
    return settings


def _build_feishu_status() -> dict:
    """构建飞书主通道只读状态（不暴露敏感值）。"""
    app_settings = get_settings()
    is_complete = app_settings.feishu_config_complete
    return {
        "source_label": ".env / 环境变量",
        "is_complete": is_complete,
        "status_label": "已完整配置" if is_complete else "未完整配置",
        "restart_hint": "修改 .env 后需重启服务或重新加载配置才能生效",
    }


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    """设置页 — 渲染配置表单。"""
    from backend.app.main import templates

    settings = _load_settings(db)
    feishu_status = _build_feishu_status()
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"settings": settings, "feishu_status": feishu_status},
    )


def _validate_form(data: dict[str, str]) -> list[str]:
    """校验表单数据，返回错误信息列表。"""
    errors: list[str] = []
    interval = data.get("refresh_interval", "")
    if interval and not interval.isdigit() or (interval.isdigit() and not (1 <= int(interval) <= 5)):
        errors.append("刷新间隔必须在 1-5 分钟之间")
    return errors


@router.post("/settings", response_class=HTMLResponse)
async def settings_save(
    request: Request,
    db: Session = Depends(get_db),
    lark_webhook: str = Form(default=""),
    telegram_token: str = Form(default=""),
    telegram_chat_id: str = Form(default=""),
    datasource: str = Form(default="akshare"),
    refresh_interval: str = Form(default="3"),
    alert_cooldown: str = Form(default="30"),
):
    """保存设置 — 接收表单数据并持久化（lark_webhook 被忽略）。"""
    from backend.app.main import templates

    form_data = {
        "telegram_token": telegram_token,
        "telegram_chat_id": telegram_chat_id,
        "datasource": datasource,
        "refresh_interval": refresh_interval,
        "alert_cooldown": alert_cooldown,
    }

    errors = _validate_form(form_data)
    feishu_status = _build_feishu_status()
    if errors:
        settings = _load_settings(db)
        return templates.TemplateResponse(
            request,
            "settings.html",
            {"settings": settings, "feishu_status": feishu_status, "errors": errors},
        )

    service = SettingsService(db, encryption_key=_get_encryption_key())
    for form_field, value in form_data.items():
        key, category, is_encrypted = _FORM_FIELDS[form_field]
        if value:  # 只保存非空值
            service.set_setting(key, value, category=category, encrypt=is_encrypted)

    settings = _load_settings(db)
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"settings": settings, "feishu_status": feishu_status, "saved": True},
    )
