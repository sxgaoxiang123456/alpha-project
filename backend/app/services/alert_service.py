import logging

from sqlalchemy.orm import Session

from backend.app.models.alert_rule import AlertRule
from backend.app.models.alert_trigger import AlertTrigger

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 股票移除监听
# ---------------------------------------------------------------------------


def pause_rules_for_stock(stock_code: str, db: Session) -> int:
    """当股票从自选股中移除时，暂停该股票的所有关联规则。

    不执行 commit，由调用方统一控制事务边界。

    Returns:
        被暂停的规则数量。
    """
    affected = (
        db.query(AlertRule)
        .filter_by(stock_code=stock_code, status="active")
        .update({"status": "paused"})
    )
    if affected > 0:
        logger.info("股票 %s 已移除，暂停 %d 条关联预警规则", stock_code, affected)
    return affected


# ---------------------------------------------------------------------------
# 条件评估
# ---------------------------------------------------------------------------


def _is_condition_satisfied(rule: AlertRule, quote: dict) -> bool:
    """评估单条规则的条件是否被当前行情满足 (纯逻辑，不关心状态)。"""
    ct = rule.condition_type
    threshold = rule.threshold

    if ct == "price_above":
        return (quote.get("current_price") or 0) > threshold
    elif ct == "price_below":
        return (quote.get("current_price") or float("inf")) < threshold
    elif ct == "change_pct_above":
        pct = quote.get("change_percent")
        if pct is None:
            return False
        return float(pct) > threshold
    elif ct == "change_pct_below":
        pct = quote.get("change_percent")
        if pct is None:
            return False
        return float(pct) < threshold
    elif ct == "volume_above":
        return (quote.get("volume") or 0) > threshold
    return False


def _should_skip_quote(quote: dict) -> bool:
    """判断是否应跳过该股票的评估 (停牌、缺数据)。"""
    if quote.get("status") == "suspended":
        return True
    if quote.get("current_price") is None and quote.get("change_percent") is None:
        return True
    return False


def evaluate_rule(rule: AlertRule, quote: dict) -> bool:
    """评估单条规则：当前行情是否触发预警。

    触发条件：
    1. 规则状态为 active
    2. 行情无异常 (非停牌、有数据)
    3. 当前行情满足条件
    4. 上次评估结果为 False 或 None (即从不满足→满足的转换)

    不修改 rule.last_evaluated_result —— 由调用方在确认触发后更新。
    """
    if rule.status != "active":
        return False
    if _should_skip_quote(quote):
        return False

    current_satisfied = _is_condition_satisfied(rule, quote)

    # 仅当「不满足→满足」跨界时才触发
    # last_evaluated_result 为 None 表示新规则状态尚未初始化，不触发
    triggered = current_satisfied and rule.last_evaluated_result is False
    return triggered


def init_evaluation_state(rule: AlertRule, quote: dict) -> None:
    """初始化规则的评估状态。

    用于规则创建时：若当前行情已满足条件，将 last_evaluated_result 置为 True，
    防止下次评估时立即误触发。
    """
    if _should_skip_quote(quote):
        rule.last_evaluated_result = None
    else:
        rule.last_evaluated_result = _is_condition_satisfied(rule, quote)


# ---------------------------------------------------------------------------
# 全量检测
# ---------------------------------------------------------------------------


def detect_alerts(db: Session, quotes: dict[str, dict]) -> list[AlertTrigger]:
    """遍历所有生效规则，对最新行情进行检测。

    Args:
        db: 数据库会话。
        quotes: {stock_code: quote_dict} 最新行情快照。

    Returns:
        本次检测中新生成的 AlertTrigger 列表 (尚未持久化)。
    """
    active_rules = db.query(AlertRule).filter_by(status="active").all()
    triggers: list[AlertTrigger] = []

    for rule in active_rules:
        quote = quotes.get(rule.stock_code)
        if quote is None:
            continue

        # 首次评估：初始化状态，不触发
        if rule.last_evaluated_result is None:
            init_evaluation_state(rule, quote)
            continue

        if evaluate_rule(rule, quote):
            trigger = AlertTrigger(
                rule_id=rule.id,
                stock_code=rule.stock_code,
                condition_type=rule.condition_type,
                trigger_value=_trigger_value(rule, quote),
                level=rule.level,
                push_status="pending",
            )
            triggers.append(trigger)

        # 更新 last_evaluated_result 以反映本次行情状态
        if not _should_skip_quote(quote):
            rule.last_evaluated_result = _is_condition_satisfied(rule, quote)

    return triggers


def _trigger_value(rule: AlertRule, quote: dict) -> float:
    """提取触发时的实际值，用于记录。"""
    ct = rule.condition_type
    if ct in ("price_above", "price_below"):
        return float(quote.get("current_price") or 0)
    elif ct in ("change_pct_above", "change_pct_below"):
        return float(quote.get("change_percent") or 0)
    elif ct == "volume_above":
        return float(quote.get("volume") or 0)
    return 0.0
