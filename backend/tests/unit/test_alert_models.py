"""T1-T3: AlertRule / AlertTrigger / CooldownTracker 模型测试。

RED 阶段 —— 模型尚未创建，测试应先 FAIL。
"""

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from backend.app.database import Base


@pytest.fixture
def in_memory_engine():
    """创建内存 SQLite 引擎，用于测试模型定义和表创建。"""
    engine = create_engine("sqlite:///:memory:")
    yield engine
    engine.dispose()


@pytest.fixture
def fresh_tables(in_memory_engine):
    """通过导入模型模块触发 Base.metadata 注册，然后在内存库中建表。"""
    import backend.app.models  # noqa: F401
    import backend.app.models.alert_rule  # noqa: F401
    import backend.app.models.alert_trigger  # noqa: F401
    import backend.app.models.cooldown_tracker  # noqa: F401

    Base.metadata.create_all(bind=in_memory_engine)
    return in_memory_engine


class TestAlertRuleModel:
    """T1: AlertRule 数据模型。"""

    def test_table_created_with_required_columns(self, fresh_tables):
        inspector = inspect(fresh_tables)
        columns = {col["name"]: col for col in inspector.get_columns("alert_rules")}

        required = [
            "id", "stock_code", "condition_type", "threshold",
            "cooldown_minutes", "level", "status", "last_evaluated_result",
            "created_at", "updated_at",
        ]
        for col_name in required:
            assert col_name in columns, f"缺少字段: {col_name}"

    def test_stock_code_index_exists(self, fresh_tables):
        inspector = inspect(fresh_tables)
        indexes = {idx["name"] for idx in inspector.get_indexes("alert_rules")}

        assert "ix_alert_rules_stock_code" in indexes, "缺少 stock_code 索引"

    def test_default_values(self, fresh_tables):
        from backend.app.models.alert_rule import AlertRule

        rule = AlertRule(
            stock_code="600519",
            condition_type="price_below",
            threshold=1500.00,
        )
        with Session(fresh_tables) as session:
            session.add(rule)
            session.flush()
            session.refresh(rule)

        assert rule.cooldown_minutes == 30
        assert rule.level == "watch"
        assert rule.status == "active"
        assert rule.last_evaluated_result is None

    def test_insert_and_query(self, fresh_tables):
        from backend.app.models.alert_rule import AlertRule

        with Session(fresh_tables) as session:
            rule = AlertRule(
                stock_code="600519",
                condition_type="price_below",
                threshold=1500.00,
                cooldown_minutes=30,
                level="watch",
                status="active",
            )
            session.add(rule)
            session.commit()
            session.refresh(rule)

            assert rule.id is not None
            assert rule.stock_code == "600519"
            assert rule.created_at is not None
            assert rule.updated_at is not None

    def test_condition_type_choices(self, fresh_tables):
        """验证 condition_type 只能是 5 种预定义值。"""
        valid = [
            "price_above", "price_below",
            "change_pct_above", "change_pct_below",
            "volume_above",
        ]
        from backend.app.models.alert_rule import AlertRule

        for ct in valid:
            with Session(fresh_tables) as session:
                rule = AlertRule(
                    stock_code="600519",
                    condition_type=ct,
                    threshold=100.0,
                )
                session.add(rule)
                session.commit()

        # 无效类型应在 SQL 层被 CHECK 约束拒绝
        with Session(fresh_tables) as session:
            rule = AlertRule(
                stock_code="600519",
                condition_type="invalid_type",
                threshold=100.0,
            )
            session.add(rule)
            with pytest.raises(Exception):
                session.commit()
            session.rollback()


class TestAlertTriggerModel:
    """T2: AlertTrigger 数据模型。"""

    def test_table_created_with_required_columns(self, fresh_tables):
        inspector = inspect(fresh_tables)
        columns = {col["name"] for col in inspector.get_columns("alert_triggers")}

        required = {
            "id", "rule_id", "stock_code", "condition_type",
            "trigger_value", "triggered_at", "level", "push_status",
        }
        assert required <= columns, f"缺少字段: {required - columns}"

    def test_foreign_key_to_rule(self, fresh_tables):
        from backend.app.models.alert_rule import AlertRule
        from backend.app.models.alert_trigger import AlertTrigger

        with Session(fresh_tables) as session:
            rule = AlertRule(
                stock_code="000001",
                condition_type="price_above",
                threshold=10.00,
            )
            session.add(rule)
            session.flush()

            trigger = AlertTrigger(
                rule_id=rule.id,
                stock_code="000001",
                condition_type="price_above",
                trigger_value=10.50,
                level="watch",
                push_status="pending",
            )
            session.add(trigger)
            session.commit()
            session.refresh(trigger)

            assert trigger.id is not None
            assert trigger.rule_id == rule.id
            assert trigger.triggered_at is not None


class TestCooldownTrackerModel:
    """T3: CooldownTracker 数据模型。"""

    def test_table_created_with_required_columns(self, fresh_tables):
        inspector = inspect(fresh_tables)
        columns = {col["name"] for col in inspector.get_columns("cooldown_trackers")}

        required = {"rule_id", "last_triggered_at", "cooldown_minutes"}
        assert required <= columns, f"缺少字段: {required - columns}"

    def test_rule_id_unique_index(self, fresh_tables):
        inspector = inspect(fresh_tables)
        indexes = {idx["name"] for idx in inspector.get_indexes("cooldown_trackers")}

        assert "ix_cooldown_trackers_rule_id" in indexes, "缺少 rule_id 唯一索引"

    def test_insert_and_query(self, fresh_tables):
        from datetime import UTC, datetime
        from backend.app.models.cooldown_tracker import CooldownTracker

        with Session(fresh_tables) as session:
            tracker = CooldownTracker(
                rule_id=1,
                last_triggered_at=datetime.now(UTC).replace(tzinfo=None),
                cooldown_minutes=30,
            )
            session.add(tracker)
            session.commit()
            session.refresh(tracker)

            assert tracker.rule_id == 1
            assert tracker.cooldown_minutes == 30
