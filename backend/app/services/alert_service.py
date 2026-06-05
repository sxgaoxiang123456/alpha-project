from datetime import UTC, datetime

import logging

from sqlalchemy.orm import Session

from backend.app.models.alert_rule import AlertRule
from backend.app.models.alert_trigger import AlertTrigger
from backend.app.models.cooldown_tracker import CooldownTracker

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

    if ct in ("price_above", "price_below"):
        price = quote.get("current_price")
        if price is None:
            return False
        price = float(price)
        return price > threshold if ct == "price_above" else price < threshold
    elif ct in ("change_pct_above", "change_pct_below"):
        pct = quote.get("change_percent")
        if pct is None:
            return False
        pct = float(pct)
        return pct > threshold if ct == "change_pct_above" else pct < threshold
    elif ct == "volume_above":
        vol = quote.get("volume")
        if vol is None:
            return False
        return float(vol) > threshold
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


def _normalize_quote(quote: dict) -> dict:
    """将 JSON 反序列化后的字符串数值转为 float/int。

    缓存存储 Quote.model_dump_json() 后，Decimal → str, datetime → str。
    """
    for key in ("current_price", "change_percent", "change_amount", "turnover"):
        val = quote.get(key)
        if isinstance(val, str):
            try:
                quote[key] = float(val)
            except (ValueError, TypeError):
                quote[key] = None
    vol = quote.get("volume")
    if isinstance(vol, str):
        try:
            quote["volume"] = int(vol)
        except (ValueError, TypeError):
            quote["volume"] = None
    return quote


def detect_alerts(db: Session, quotes: dict[str, dict]) -> list[AlertTrigger]:
    """遍历所有生效规则，对最新行情进行检测。

    Args:
        db: 数据库会话。
        quotes: {stock_code: quote_dict} 最新行情快照 (dict 或 JSON 解析结果均可)。

    Returns:
        本次检测中新生成的 AlertTrigger 列表 (已合并，尚未持久化)。
    """
    # 标准化数值类型 (JSON 反序列化后字符串 → 数值)
    for quote in quotes.values():
        _normalize_quote(quote)
    active_rules = db.query(AlertRule).filter_by(status="active").all()
    raw_triggers: list[AlertTrigger] = []

    for rule in active_rules:
        quote = quotes.get(rule.stock_code)
        if quote is None:
            continue

        # 首次评估：初始化状态，不触发
        if rule.last_evaluated_result is None:
            init_evaluation_state(rule, quote)
            continue

        # 冷却期检查
        if is_in_cooldown(db, rule):
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
            raw_triggers.append(trigger)
            update_cooldown(db, rule)

        # 更新 last_evaluated_result 以反映本次行情状态
        if not _should_skip_quote(quote):
            rule.last_evaluated_result = _is_condition_satisfied(rule, quote)

    return raw_triggers


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


# ---------------------------------------------------------------------------
# 冷却期管理 (T10)
# ---------------------------------------------------------------------------


def is_in_cooldown(db: Session, rule: AlertRule) -> bool:
    """检查规则当前是否在冷却期内。"""
    tracker = db.get(CooldownTracker, rule.id)
    if tracker is None:
        return False

    elapsed = datetime.utcnow() - tracker.last_triggered_at
    return elapsed.total_seconds() <= tracker.cooldown_minutes * 60


def update_cooldown(db: Session, rule: AlertRule) -> None:
    """触发规则后更新冷却期记录 (upsert)。"""
    tracker = db.get(CooldownTracker, rule.id)
    if tracker is None:
        tracker = CooldownTracker(
            rule_id=rule.id,
            last_triggered_at=datetime.utcnow(),
            cooldown_minutes=rule.cooldown_minutes,
        )
        db.add(tracker)
        db.flush()
    else:
        tracker.last_triggered_at = datetime.utcnow()
        tracker.cooldown_minutes = rule.cooldown_minutes


def reset_all_cooldowns(db: Session) -> None:
    """清除所有冷却期记录 (跨交易日重置)。"""
    db.query(CooldownTracker).delete()
    logger.info("交易日变更，已重置全部冷却期")


# ---------------------------------------------------------------------------
# 合并推送 (T11)
# ---------------------------------------------------------------------------


def merge_triggers(
    db: Session,
    triggers: list[AlertTrigger],
) -> list[AlertTrigger]:
    """为同一股票的多规则触发标记合并关系。

    保留全部 trigger 记录（FR-012 审计要求），在同一股票的多条
    trigger 上设置 merged_rule_ids，供 F4 推送时合并。

    规则：
    - 同股票触发多条规则时，所有 trigger 记录 merged_rule_ids
    - 不丢弃任何 trigger 记录，不修改原始 level
    """
    if len(triggers) <= 1:
        return triggers

    groups: dict[str, list[AlertTrigger]] = {}
    for t in triggers:
        groups.setdefault(t.stock_code, []).append(t)

    for group in groups.values():
        if len(group) <= 1:
            continue
        rule_ids = ",".join(str(t.rule_id) for t in group)
        for t in group:
            t.merged_rule_ids = rule_ids

    return triggers

