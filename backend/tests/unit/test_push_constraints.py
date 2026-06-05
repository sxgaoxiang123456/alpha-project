"""BE-G1(push): 真库数据层约束验证 — 文件模式 SQLite。

覆盖 test-routing-advisor 标出的结构性缺口：
- PushLog created_at 索引在文件模式下生效
- PushChannel 主键唯一约束在文件模式下生效
- PushLog / PushChannel NOT NULL 约束拒绝非法写入

参考: test_alert_constraints.py (F4 约束测试模式)
"""

import pytest
from sqlalchemy import create_engine, exc, inspect
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base


@pytest.fixture
def file_engine(tmp_path):
    """使用文件模式 SQLite（更接近生产环境）。"""
    db_path = tmp_path / "test_push_constraints.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    import backend.app.models  # noqa: F401
    import backend.app.models.push_channel  # noqa: F401
    import backend.app.models.push_log  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # 启用外键约束（同生产配置）
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")

    yield engine
    engine.dispose()


@pytest.fixture
def db_session(file_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=file_engine)
    with SessionLocal() as session:
        yield session


class TestPushLogConstraints:
    """PushLog 数据库约束验证（文件模式 SQLite）。"""

    def test_created_at_index_exists(self, file_engine):
        """created_at 索引在文件模式下存在。"""
        inspector = inspect(file_engine)
        indexes = {idx["name"] for idx in inspector.get_indexes("push_logs")}
        assert "ix_push_logs_created_at" in indexes, "缺少 created_at 索引"

    def test_not_null_message_id_rejected(self, db_session):
        """message_id NOT NULL，插入 NULL 应失败。"""
        from sqlalchemy import text

        with pytest.raises(exc.IntegrityError):
            db_session.execute(
                text(
                    "INSERT INTO push_logs (message_id, message_type, channel, status) "
                    "VALUES (NULL, 'alert', 'feishu', 'sent')"
                )
            )
            db_session.commit()
        db_session.rollback()

    def test_not_null_message_type_rejected(self, db_session):
        """message_type NOT NULL，插入 NULL 应失败。"""
        from sqlalchemy import text

        with pytest.raises(exc.IntegrityError):
            db_session.execute(
                text(
                    "INSERT INTO push_logs (message_id, message_type, channel, status) "
                    "VALUES ('msg-001', NULL, 'feishu', 'sent')"
                )
            )
            db_session.commit()
        db_session.rollback()

    def test_insert_and_query_roundtrip(self, db_session):
        """正常插入和查询在文件模式下工作。"""
        from datetime import UTC, datetime

        from backend.app.models.push_log import PushLog

        log = PushLog(
            message_id="msg-test-001",
            message_type="alert",
            channel="feishu",
            status="sent",
            elapsed_ms=1234,
            created_at=datetime.now(UTC),
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)

        assert log.id is not None
        assert log.message_id == "msg-test-001"


class TestPushChannelConstraints:
    """PushChannel 数据库约束验证（文件模式 SQLite）。"""

    def test_primary_key_unique_rejected(self, db_session):
        """name 为主键，重复插入应触发唯一约束错误。"""
        from backend.app.models.push_channel import PushChannel

        c1 = PushChannel(name="feishu", status="active")
        db_session.add(c1)
        db_session.commit()
        db_session.expunge(c1)

        c2 = PushChannel(name="feishu", status="degraded")
        db_session.add(c2)
        with pytest.raises(exc.IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_default_values_in_file_mode(self, db_session):
        """默认值在文件模式下正确生效。"""
        from backend.app.models.push_channel import PushChannel

        channel = PushChannel(name="telegram")
        db_session.add(channel)
        db_session.commit()
        db_session.refresh(channel)

        assert channel.status == "active"
        assert channel.consecutive_failures == 0
        assert channel.rate_limited is False
        assert channel.updated_at is not None

    def test_status_not_null_rejected(self, db_session):
        """status NOT NULL，插入 NULL 应失败。"""
        from sqlalchemy import text

        with pytest.raises(exc.IntegrityError):
            db_session.execute(
                text("INSERT INTO push_channels (name, status) VALUES ('wechat', NULL)")
            )
            db_session.commit()
        db_session.rollback()
