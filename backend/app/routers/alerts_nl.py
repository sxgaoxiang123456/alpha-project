import threading

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.dependencies import get_db
from backend.app.models.alert_rule import AlertRule
from backend.app.schemas.nl_alert import (
    AlertRuleSummary,
    NaturalLanguageAlertRequest,
    NaturalLanguageAlertResponse,
)
from backend.app.services.briefing_llm_client import BriefingLLMClient
from backend.app.services.nl_alert_parser import NLAlertParser

router = APIRouter(prefix="/alerts", tags=["alerts"])

_nl_alert_add_lock = threading.Lock()

_CONDITION_LABELS = {
    "price_above": "价格 >",
    "price_below": "价格 <",
    "change_pct_above": "涨跌幅 >",
    "change_pct_below": "涨跌幅 <",
}


def get_nl_alert_parser() -> NLAlertParser:
    settings = get_settings()
    llm_client = None
    if settings.deepseek_api_key:
        llm_client = BriefingLLMClient(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
            timeout_seconds=settings.deepseek_timeout_seconds,
            retry_attempts=settings.deepseek_retry_attempts,
            retry_interval_seconds=settings.deepseek_retry_interval_seconds,
        )
    return NLAlertParser(
        confidence_threshold=float(getattr(settings, "nl_alert_confidence_threshold", 0.7)),
        llm_client=llm_client,
    )


@router.post("/natural-language", response_model=NaturalLanguageAlertResponse)
def create_alert_from_natural_language(
    req: NaturalLanguageAlertRequest,
    db: Session = Depends(get_db),
    parser: NLAlertParser = Depends(get_nl_alert_parser),
) -> NaturalLanguageAlertResponse:
    intent = parser.parse(req.query, selected_stock_code=req.selected_stock_code)

    if intent.invalid:
        if intent.invalid_reason == "multi_stock":
            return NaturalLanguageAlertResponse(
                success=False,
                message="一次仅支持一只股票",
            )
        if intent.invalid_reason == "multi_condition":
            return NaturalLanguageAlertResponse(
                success=False,
                message="暂不支持组合条件",
            )

    if intent.unsupported_condition:
        return NaturalLanguageAlertResponse(
            success=False,
            message=f"暂不支持{intent.unsupported_condition}条件，请使用价格或涨跌幅条件",
        )

    if intent.ambiguity:
        return NaturalLanguageAlertResponse(
            success=False,
            message="请从候选列表中选择具体股票",
            candidates=intent.candidates,
        )

    if intent.confidence < parser.confidence_threshold:
        return NaturalLanguageAlertResponse(
            success=False,
            message="未能理解，请用『股票名+条件』格式重试，或前往预警页面手动配置",
        )

    if not intent.stock_code or not intent.condition_type or intent.threshold is None:
        return NaturalLanguageAlertResponse(
            success=False,
            message="未能理解，请用『股票名+条件』格式重试，或前往预警页面手动配置",
        )

    return _create_rule(
        db,
        stock_code=intent.stock_code,
        stock_name=intent.stock_name or intent.stock_code,
        condition_type=intent.condition_type,
        threshold=intent.threshold,
    )


def _create_rule(
    db: Session,
    *,
    stock_code: str,
    stock_name: str,
    condition_type: str,
    threshold: float,
) -> NaturalLanguageAlertResponse:
    settings = get_settings()
    max_rules = settings.max_alert_rules

    with _nl_alert_add_lock:
        active_count = db.query(AlertRule).filter_by(status="active").count()
        if active_count >= max_rules:
            return NaturalLanguageAlertResponse(
                success=False,
                message="预警规则已达上限，请先删除其他规则",
            )

        existing = db.query(AlertRule).filter_by(
            stock_code=stock_code,
            condition_type=condition_type,
            threshold=threshold,
            status="active",
        ).first()
        if existing is not None:
            return NaturalLanguageAlertResponse(
                success=False,
                message="该预警规则已存在，请勿重复创建",
            )

        rule = AlertRule(
            stock_code=stock_code,
            condition_type=condition_type,
            threshold=threshold,
            cooldown_minutes=settings.default_cooldown_minutes,
            level="watch",
            status="active",
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)

    label = _CONDITION_LABELS.get(condition_type, condition_type)
    return NaturalLanguageAlertResponse(
        success=True,
        message=f"预警已创建：{stock_name} {label} {threshold}",
        rule=AlertRuleSummary(
            stock_code=stock_code,
            stock_name=stock_name,
            condition_type=condition_type,
            threshold=threshold,
        ),
    )
