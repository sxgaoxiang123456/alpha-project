import threading

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.dependencies import get_db
from backend.app.models.alert_rule import AlertRule
from backend.app.models.cooldown_tracker import CooldownTracker
from backend.app.schemas.alert import (
    AlertRuleRequest,
    AlertRuleResponse,
    AlertRuleUpdateRequest,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])

MAX_ALERT_RULES = 50

_alert_add_lock = threading.Lock()


@router.post("", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
def create_alert_rule(
    req: AlertRuleRequest,
    db: Session = Depends(get_db),
) -> AlertRuleResponse:
    with _alert_add_lock:
        active_count = db.query(AlertRule).filter_by(status="active").count()
        if active_count >= MAX_ALERT_RULES:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"生效规则数量已达上限（{MAX_ALERT_RULES} 条），请先删除或暂停其他规则",
            )

        rule = AlertRule(
            stock_code=req.stock_code,
            condition_type=req.condition_type,
            threshold=req.threshold,
            cooldown_minutes=req.cooldown_minutes,
            level=req.level,
        )
        db.add(rule)
        try:
            db.flush()
            response = AlertRuleResponse.model_validate(rule)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="规则创建失败，请检查输入数据",
            ) from exc

    return response


@router.get("", response_model=list[AlertRuleResponse])
def list_alert_rules(
    status: str | None = Query(default=None, pattern="^(active|paused)$"),
    db: Session = Depends(get_db),
) -> list[AlertRule]:
    q = db.query(AlertRule)
    if status is not None:
        q = q.filter_by(status=status)
    return q.order_by(AlertRule.created_at.desc()).all()


@router.get("/{rule_id}", response_model=AlertRuleResponse)
def get_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db),
) -> AlertRule:
    rule = db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="规则不存在")
    return rule


@router.put("/{rule_id}", response_model=AlertRuleResponse)
def update_alert_rule(
    rule_id: int,
    req: AlertRuleUpdateRequest,
    db: Session = Depends(get_db),
) -> AlertRule:
    rule = db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="规则不存在")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)

    # 修改任何字段后重置冷却期
    db.query(CooldownTracker).filter_by(rule_id=rule_id).delete()

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="规则更新失败，请检查输入数据",
        ) from exc
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db),
) -> None:
    rule = db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="规则不存在")

    db.query(CooldownTracker).filter_by(rule_id=rule_id).delete()
    db.delete(rule)
    db.commit()


@router.patch("/{rule_id}/toggle", response_model=AlertRuleResponse)
def toggle_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db),
) -> AlertRule:
    rule = db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="规则不存在")

    rule.status = "paused" if rule.status == "active" else "active"
    db.query(CooldownTracker).filter_by(rule_id=rule_id).delete()
    db.commit()
    db.refresh(rule)
    return rule
