"""T1-T2: PushLog / PushChannel 模型测试。

RED 阶段 —— 模型尚未创建，测试应先 FAIL。
"""

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from backend.app.database import Base


@pytest.fixture
def in_memory_engine():
    engine = create_engine("sqlite:///:memory:")
    yield engine
    engine.dispose()


@pytest.fixture
def fresh_tables(in_memory_engine):
    import backend.app.models  # noqa: F401
    import backend.app.models.push_channel  # noqa: F401
    import backend.app.models.push_log  # noqa: F401

    Base.metadata.create_all(bind=in_memory_engine)
    return in_memory_engine


class TestPushLogModel:
    """T1: PushLog 数据模型。"""

    def test_table_created_with_required_columns(self, fresh_tables):
        inspector = inspect(fresh_tables)
        columns = {col["name"]: col for col in inspector.get_columns("push_logs")}

        required = [
            "id", "message_id", "message_type", "channel",
            "status", "error_reason", "elapsed_ms", "created_at",
        ]
        for col_name in required:
            assert col_name in columns, f"缺少字段: {col_name}"

    def test_created_at_index_exists(self, fresh_tables):
        inspector = inspect(fresh_tables)
        indexes = {idx["name"] for idx in inspector.get_indexes("push_logs")}

        assert "ix_push_logs_created_at" in indexes, "缺少 created_at 索引"

    def test_default_values(self, fresh_tables):
        from backend.app.models.push_log import PushLog

        log = PushLog(
            message_id="msg-001",
            message_type="alert",
            channel="feishu",
            status="pending",
        )
        with Session(fresh_tables) as session:
            session.add(log)
            session.flush()
            session.refresh(log)

        assert log.status == "pending"
        assert log.created_at is not None

    def test_insert_and_query(self, fresh_tables):
        from backend.app.models.push_log import PushLog

        with Session(fresh_tables) as session:
            log = PushLog(
                message_id="msg-002",
                message_type="alert",
                channel="feishu",
                status="sent",
                elapsed_ms=1234,
            )
            session.add(log)
            session.commit()
            session.refresh(log)

            assert log.id is not None
            assert log.message_id == "msg-002"
            assert log.status == "sent"
            assert log.elapsed_ms == 1234
            assert log.created_at is not None

    def test_nullable_fields(self, fresh_tables):
        from backend.app.models.push_log import PushLog

        with Session(fresh_tables) as session:
            log = PushLog(
                message_id="msg-003",
                message_type="briefing",
                channel="telegram",
                status="failed",
            )
            session.add(log)
            session.commit()
            session.refresh(log)

            assert log.error_reason is None
            assert log.elapsed_ms is None


class TestPushChannelModel:
    """T2: PushChannel 数据模型。"""

    def test_table_created_with_required_columns(self, fresh_tables):
        inspector = inspect(fresh_tables)
        columns = {col["name"] for col in inspector.get_columns("push_channels")}

        required = {"name", "status", "consecutive_failures", "rate_limited", "updated_at"}
        assert required <= columns, f"缺少字段: {required - columns}"

    def test_default_values(self, fresh_tables):
        from backend.app.models.push_channel import PushChannel

        channel = PushChannel(name="feishu")
        with Session(fresh_tables) as session:
            session.add(channel)
            session.flush()
            session.refresh(channel)

        assert channel.status == "active"
        assert channel.consecutive_failures == 0
        assert channel.rate_limited is False
        assert channel.updated_at is not None

    def test_insert_and_query(self, fresh_tables):
        from backend.app.models.push_channel import PushChannel

        with Session(fresh_tables) as session:
            channel = PushChannel(
                name="telegram",
                status="degraded",
                consecutive_failures=3,
                rate_limited=True,
            )
            session.add(channel)
            session.commit()
            session.refresh(channel)

            assert channel.name == "telegram"
            assert channel.status == "degraded"
            assert channel.consecutive_failures == 3
            assert channel.rate_limited is True

    def test_primary_key_is_name(self, fresh_tables):
        from backend.app.models.push_channel import PushChannel

        with Session(fresh_tables) as session:
            channel = PushChannel(name="feishu")
            session.add(channel)
            session.commit()
            session.expunge(channel)

            # name 是主键，不能重复插入
            dup = PushChannel(name="feishu")
            session.add(dup)
            with pytest.raises(Exception):
                session.commit()
            session.rollback()
