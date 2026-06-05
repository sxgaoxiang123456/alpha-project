"""BE-G1: 真库数据层约束验证 — SQLite FK + UNIQUE + NOT NULL。

RED 阶段 —— 测试约束违反场景。
"""

import pytest
from sqlalchemy import create_engine, exc
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # 开启外键约束 (PRAGMA foreign_keys=ON)
    import backend.app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    # SQLite 在 create_all 之后需要重新连接才能让 PRAGMA 生效
    # 在 SQLAlchemy 中通过 connect_args 或事件处理
    # 直接通过 raw SQL 设置
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with SessionLocal() as session:
        yield session


class TestForeignKeyConstraint:
    """FK: alert_triggers.rule_id → alert_rules.id。"""

    def test_insert_trigger_with_nonexistent_rule_fails(self, db_session):
        from backend.app.models.alert_trigger import AlertTrigger

        trigger = AlertTrigger(
            rule_id=99999,  # 不存在的规则
            stock_code="600519",
            condition_type="price_below",
            trigger_value=1500.0,
            level="watch",
            push_status="pending",
        )
        db_session.add(trigger)
        with pytest.raises(exc.IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_insert_trigger_with_valid_rule_succeeds(self, db_session):
        from backend.app.models.alert_rule import AlertRule
        from backend.app.models.alert_trigger import AlertTrigger

        rule = AlertRule(
            stock_code="600519",
            condition_type="price_below",
            threshold=1500.0,
        )
        db_session.add(rule)
        db_session.flush()

        trigger = AlertTrigger(
            rule_id=rule.id,
            stock_code="600519",
            condition_type="price_below",
            trigger_value=1498.0,
            level="watch",
            push_status="pending",
        )
        db_session.add(trigger)
        db_session.commit()
        assert trigger.id is not None


class TestUniqueConstraint:
    """UNIQUE: cooldown_trackers.rule_id。"""

    def test_insert_duplicate_rule_id_fails(self, db_session):
        from backend.app.models.cooldown_tracker import CooldownTracker
        from datetime import datetime

        t1 = CooldownTracker(
            rule_id=1,
            last_triggered_at=datetime.utcnow(),
            cooldown_minutes=30,
        )
        db_session.add(t1)
        db_session.flush()

        t2 = CooldownTracker(
            rule_id=1,  # 重复的 rule_id
            last_triggered_at=datetime.utcnow(),
            cooldown_minutes=60,
        )
        db_session.add(t2)
        with pytest.raises(exc.IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestNotNullConstraint:
    """NOT NULL: 必填字段在 DB 层被拒绝。"""

    def test_alert_rule_missing_condition_type_fails(self, db_session):
        from sqlalchemy import text

        # 直接 SQL 插入缺少 NOT NULL 字段 → 应被数据库拒绝
        with pytest.raises(exc.IntegrityError):
            db_session.execute(
                text("INSERT INTO alert_rules (stock_code, threshold) "
                     "VALUES ('600519', 1500)")
            )
            db_session.commit()
        db_session.rollback()
