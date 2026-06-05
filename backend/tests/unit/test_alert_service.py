"""T7-T9: 预警检测引擎单元测试。

RED 阶段 —— 检测引擎函数尚未实现，测试应先 FAIL。
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
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
    }
    defaults.update(kwargs)
    rule = AlertRule(**defaults)
    db.add(rule)
    db.flush()
    return rule


def _make_quote(stock_code="600519", price=1498.0, change_pct=Decimal("-1.5"),
                volume=50000):
    return {
        "stock_code": stock_code,
        "stock_name": "测试股票",
        "current_price": price,
        "change_percent": change_pct,
        "change_amount": Decimal("-0.50"),
        "volume": volume,
        "turnover": Decimal("1000000"),
        "updated_at": datetime.now(UTC),
        "status": "normal",
        "source_status": "primary",
        "actual_timestamp": datetime.now(UTC),
    }


class TestConditionEvaluation:
    """T7-T8: 条件评估逻辑。"""

    def test_price_below_triggers_when_price_drops(self, db_session):
        from backend.app.services.alert_service import evaluate_rule

        rule = _make_rule(db_session, condition_type="price_below", threshold=1500.0)
        rule.last_evaluated_result = False  # 初始化: 之前不满足
        quote = _make_quote(price=1498.0)

        result = evaluate_rule(rule, quote)
        assert result is True

    def test_price_below_no_trigger_when_price_above(self, db_session):
        from backend.app.services.alert_service import evaluate_rule

        rule = _make_rule(db_session, condition_type="price_below", threshold=1500.0)
        rule.last_evaluated_result = False
        quote = _make_quote(price=1505.0)

        result = evaluate_rule(rule, quote)
        assert result is False

    def test_price_above_triggers_when_price_rises(self, db_session):
        from backend.app.services.alert_service import evaluate_rule

        rule = _make_rule(db_session, condition_type="price_above", threshold=1600.0)
        rule.last_evaluated_result = False
        quote = _make_quote(price=1605.0)

        result = evaluate_rule(rule, quote)
        assert result is True

    def test_change_pct_above_triggers(self, db_session):
        from backend.app.services.alert_service import evaluate_rule

        rule = _make_rule(db_session, condition_type="change_pct_above", threshold=5.0)
        rule.last_evaluated_result = False
        quote = _make_quote(change_pct=Decimal("5.2"))

        result = evaluate_rule(rule, quote)
        assert result is True

    def test_change_pct_below_triggers(self, db_session):
        from backend.app.services.alert_service import evaluate_rule

        rule = _make_rule(db_session, condition_type="change_pct_below", threshold=-3.0)
        rule.last_evaluated_result = False
        quote = _make_quote(change_pct=Decimal("-3.5"))

        result = evaluate_rule(rule, quote)
        assert result is True

    def test_volume_above_triggers(self, db_session):
        from backend.app.services.alert_service import evaluate_rule

        rule = _make_rule(db_session, condition_type="volume_above", threshold=10000.0)
        rule.last_evaluated_result = False
        quote = _make_quote(volume=15000)

        result = evaluate_rule(rule, quote)
        assert result is True

    def test_volume_above_no_trigger_below_threshold(self, db_session):
        from backend.app.services.alert_service import evaluate_rule

        rule = _make_rule(db_session, condition_type="volume_above", threshold=20000.0)
        rule.last_evaluated_result = False
        quote = _make_quote(volume=15000)

        result = evaluate_rule(rule, quote)
        assert result is False

    def test_suspended_stock_skipped(self, db_session):
        from backend.app.services.alert_service import evaluate_rule

        rule = _make_rule(db_session, condition_type="price_below", threshold=1500.0)
        rule.last_evaluated_result = False
        quote = _make_quote(price=1498.0)
        quote["status"] = "suspended"

        result = evaluate_rule(rule, quote)
        assert result is False

    def test_boundary_equals_threshold_no_trigger(self, db_session):
        """价格恰等于阈值时不触发 (价格高于/低于是严格比较)。"""
        from backend.app.services.alert_service import evaluate_rule

        rule = _make_rule(db_session, condition_type="price_below", threshold=1500.0)
        rule.last_evaluated_result = False
        quote = _make_quote(price=1500.0)

        result = evaluate_rule(rule, quote)
        assert result is False


class TestLastEvaluatedResult:
    """T9: 已满足不触发逻辑。"""

    def test_create_when_already_satisfied_no_trigger_first_time(self, db_session):
        """创建规则时行情已满足条件，不立即触发。"""
        from backend.app.services.alert_service import evaluate_rule

        rule = _make_rule(db_session, condition_type="price_below", threshold=1500.0)
        # 初次评估，行情已满足 → 初始化 last_evaluated_result
        quote = _make_quote(price=1498.0)

        result = evaluate_rule(rule, quote)
        # 规则刚创建，last_evaluated_result 为 None
        # 满足条件但应初始化为 True 而非触发
        assert rule.last_evaluated_result is None
        # 先初始化状态
        from backend.app.services.alert_service import init_evaluation_state
        init_evaluation_state(rule, quote)
        assert rule.last_evaluated_result is True

    def test_satisfied_to_not_satisfied_to_satisfied_triggers(self, db_session):
        """行情从不满足→满足时才触发。"""
        from backend.app.services.alert_service import evaluate_rule

        rule = _make_rule(db_session, condition_type="price_below", threshold=1500.0)
        # Step 1: 初始化 — 行情 1600, 不满足
        rule.last_evaluated_result = False

        # Step 2: 行情跌到 1498 — 满足，应触发
        quote = _make_quote(price=1498.0)
        result = evaluate_rule(rule, quote)
        assert result is True

    def test_already_satisfied_no_repeat_trigger(self, db_session):
        """已经满足条件的，不重复触发。"""
        from backend.app.services.alert_service import evaluate_rule

        rule = _make_rule(db_session, condition_type="price_below", threshold=1500.0)
        rule.last_evaluated_result = True

        # 行情仍然满足
        quote = _make_quote(price=1490.0)
        result = evaluate_rule(rule, quote)
        assert result is False

    def test_satisfied_then_not_then_satisfied_triggers_again(self, db_session):
        """满足→不满足→满足，重新触发 (跨界)。"""
        from backend.app.services.alert_service import evaluate_rule

        rule = _make_rule(db_session, condition_type="price_below", threshold=1500.0)
        # Step 1: 满足
        rule.last_evaluated_result = True

        # Step 2: 回到不满足
        quote = _make_quote(price=1510.0)
        result = evaluate_rule(rule, quote)
        assert result is False
        # 更新状态
        rule.last_evaluated_result = False

        # Step 3: 再次满足
        quote2 = _make_quote(price=1495.0)
        result = evaluate_rule(rule, quote2)
        assert result is True


class TestDetectAll:
    """T7: 全量规则检测。"""

    def test_detect_runs_all_active_rules(self, db_session):
        from backend.app.services.alert_service import detect_alerts

        r1 = _make_rule(db_session, stock_code="600519", condition_type="price_below",
                        threshold=1500.0, status="active")
        r2 = _make_rule(db_session, stock_code="000001", condition_type="price_above",
                        threshold=10.0, status="active")
        _make_rule(db_session, stock_code="000002", condition_type="price_below",
                   threshold=5.0, status="paused")

        # 初始化: 上次行情不满足
        r1.last_evaluated_result = False
        r2.last_evaluated_result = False

        quotes = {
            "600519": _make_quote("600519", price=1498.0),
            "000001": _make_quote("000001", price=10.5),
            "000002": _make_quote("000002", price=4.0),
        }

        triggers = detect_alerts(db_session, quotes)
        # 600519 triggers (price_below 1500, 1498 < 1500),
        # 000001 triggers (price_above 10, 10.5 > 10),
        # 000002 is paused, should not trigger
        assert len(triggers) == 2
        stock_codes = {t.stock_code for t in triggers}
        assert stock_codes == {"600519", "000001"}

    def test_detect_skips_no_quote(self, db_session):
        """没有行情数据的股票不进行评估。"""
        from backend.app.services.alert_service import detect_alerts

        _make_rule(db_session, stock_code="600519", condition_type="price_below",
                   threshold=1500.0, status="active")

        triggers = detect_alerts(db_session, {})
        assert len(triggers) == 0
