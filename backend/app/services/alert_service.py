import logging

from sqlalchemy.orm import Session

from backend.app.models.alert_rule import AlertRule

logger = logging.getLogger(__name__)


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
