"""T10-T12: 冷却期、合并推送、跨交易日重置单元测试。

RED 阶段 —— 相关函数尚未实现。
"""

from datetime import UTC, datetime, timedelta

import pytest
from freezegun import freeze_time
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models.alert_rule import AlertRule
from backend.app.models.alert_trigger import AlertTrigger
from backend.app.models.cooldown_tracker import CooldownTracker


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import backend.app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with SessionLocal() as session:
        yield session


def _make_rule(db, **kwargs):
    defaults = {
        "stock_code": "600519",
        "condition_type": "price_below",
        "threshold": 1500.0,
        "cooldown_minutes": 30,
        "level": "watch",
        "status": "active",
        "last_evaluated_result": False,
    }
    defaults.update(kwargs)
    rule = AlertRule(**defaults)
    db.add(rule)
    db.flush()
    return rule


def _make_quote(stock_code="600519", price=1498.0):
    return {
        "stock_code": stock_code,
        "stock_name": "测试股票",
        "current_price": price,
        "change_percent": None,
        "change_amount": None,
        "volume": None,
        "turnover": None,
        "updated_at": datetime.now(UTC),
        "status": "normal",
        "source_status": "primary",
        "actual_timestamp": datetime.now(UTC),
    }


class TestCooldownCheck:
    """T10: 冷却期检查。"""

    def test_not_in_cooldown_returns_false(self, db_session):
        from backend.app.services.alert_service import is_in_cooldown

        rule = _make_rule(db_session)
        assert is_in_cooldown(db_session, rule) is False

    def test_in_cooldown_returns_true(self, db_session):
        from backend.app.services.alert_service import is_in_cooldown

        rule = _make_rule(db_session)
        tracker = CooldownTracker(
            rule_id=rule.id,
            last_triggered_at=datetime.utcnow(),
            cooldown_minutes=30,
        )
        db_session.add(tracker)
        db_session.flush()

        assert is_in_cooldown(db_session, rule) is True

    @freeze_time("2026-06-04 10:00:00")
    def test_cooldown_expired_returns_false(self, db_session):
        from backend.app.services.alert_service import is_in_cooldown

        rule = _make_rule(db_session)
        # 40 分钟前触发
        tracker = CooldownTracker(
            rule_id=rule.id,
            last_triggered_at=datetime.utcnow() - timedelta(minutes=40),
            cooldown_minutes=30,
        )
        db_session.add(tracker)
        db_session.flush()

        assert is_in_cooldown(db_session, rule) is False

    @freeze_time("2026-06-04 10:00:00")
    def test_cooldown_borderline_not_expired(self, db_session):
        """冷却期边界: 刚好 30 分钟仍在冷却中。"""
        from backend.app.services.alert_service import is_in_cooldown

        rule = _make_rule(db_session)
        tracker = CooldownTracker(
            rule_id=rule.id,
            last_triggered_at=datetime.utcnow() - timedelta(minutes=30),
            cooldown_minutes=30,
        )
        db_session.add(tracker)
        db_session.flush()

        assert is_in_cooldown(db_session, rule) is True


class TestUpdateCooldown:
    """T10: 触发后更新冷却期。"""

    @freeze_time("2026-06-04 10:00:00")
    def test_create_new_cooldown_entry(self, db_session):
        from backend.app.services.alert_service import update_cooldown

        rule = _make_rule(db_session)
        update_cooldown(db_session, rule)

        tracker = db_session.get(CooldownTracker, rule.id)
        assert tracker is not None
        assert tracker.cooldown_minutes == 30

    def test_update_existing_cooldown_entry(self, db_session):
        from backend.app.services.alert_service import update_cooldown

        rule = _make_rule(db_session, cooldown_minutes=60)
        with freeze_time("2026-06-04 10:00:00") as frozen_time:
            update_cooldown(db_session, rule)
            tracker1 = db_session.get(CooldownTracker, rule.id)
            assert tracker1 is not None
            assert tracker1.cooldown_minutes == 60

            frozen_time.tick(delta=timedelta(hours=2))
            # 冷却期已过，再次触发应更新 tracker
            update_cooldown(db_session, rule)
            db_session.refresh(tracker1)
            assert tracker1.cooldown_minutes == 60


class TestMergeTriggers:
    """T11: 合并推送。"""

    def test_single_rule_no_merge(self, db_session):
        from backend.app.services.alert_service import merge_triggers

        rule = _make_rule(db_session)
        trigger = AlertTrigger(
            rule_id=rule.id,
            stock_code="600519",
            condition_type="price_below",
            trigger_value=1498.0,
            level="watch",
            push_status="pending",
        )
        db_session.add(trigger)
        db_session.flush()

        merged = merge_triggers(db_session, [trigger])
        assert len(merged) == 1

    def test_same_stock_rules_merged(self, db_session):
        from backend.app.services.alert_service import merge_triggers

        r1 = _make_rule(db_session, condition_type="price_below", threshold=1500, level="watch")
        r2 = _make_rule(db_session, condition_type="change_pct_below", threshold=-3.0, level="alert")

        t1 = AlertTrigger(
            rule_id=r1.id, stock_code="600519", condition_type="price_below",
            trigger_value=1498.0, level="watch", push_status="pending",
        )
        t2 = AlertTrigger(
            rule_id=r2.id, stock_code="600519", condition_type="change_pct_below",
            trigger_value=-3.5, level="alert", push_status="pending",
        )
        db_session.add_all([t1, t2])
        db_session.flush()

        merged = merge_triggers(db_session, [t1, t2])
        assert len(merged) == 1
        assert merged[0].merged_rule_ids is not None
        assert str(r1.id) in merged[0].merged_rule_ids
        assert str(r2.id) in merged[0].merged_rule_ids

    def test_merge_takes_highest_level(self, db_session):
        from backend.app.services.alert_service import merge_triggers

        r1 = _make_rule(db_session, condition_type="price_below", level="watch")
        r2 = _make_rule(db_session, condition_type="change_pct_below", level="alert")

        t1 = AlertTrigger(
            rule_id=r1.id, stock_code="600519", condition_type="price_below",
            trigger_value=1498.0, level="watch", push_status="pending",
        )
        t2 = AlertTrigger(
            rule_id=r2.id, stock_code="600519", condition_type="change_pct_below",
            trigger_value=-3.5, level="alert", push_status="pending",
        )
        db_session.add_all([t1, t2])
        db_session.flush()

        merged = merge_triggers(db_session, [t1, t2])
        assert len(merged) == 1
        assert merged[0].level == "alert"

    def test_different_stocks_not_merged(self, db_session):
        from backend.app.services.alert_service import merge_triggers

        r1 = _make_rule(db_session, stock_code="600519")
        r2 = _make_rule(db_session, stock_code="000001")

        t1 = AlertTrigger(
            rule_id=r1.id, stock_code="600519", condition_type="price_below",
            trigger_value=1498.0, level="watch", push_status="pending",
        )
        t2 = AlertTrigger(
            rule_id=r2.id, stock_code="000001", condition_type="price_above",
            trigger_value=10.5, level="watch", push_status="pending",
        )
        db_session.add_all([t1, t2])
        db_session.flush()

        merged = merge_triggers(db_session, [t1, t2])
        assert len(merged) == 2


class TestCrossTradingDayReset:
    """T12: 跨交易日冷却期重置。"""

    @freeze_time("2026-06-04 10:00:00")
    def test_reset_clears_all_cooldowns(self, db_session):
        from backend.app.services.alert_service import reset_all_cooldowns

        r1 = _make_rule(db_session)
        tracker = CooldownTracker(
            rule_id=r1.id,
            last_triggered_at=datetime.utcnow(),
            cooldown_minutes=30,
        )
        db_session.add(tracker)
        db_session.flush()

        reset_all_cooldowns(db_session)
        assert db_session.get(CooldownTracker, r1.id) is None

    @freeze_time("2026-06-04 10:00:00")
    def test_reset_empty_table_no_error(self, db_session):
        from backend.app.services.alert_service import reset_all_cooldowns

        _make_rule(db_session)
        reset_all_cooldowns(db_session)
        # 不应抛出异常
