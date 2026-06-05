"""T10: 推送历史查询 API 测试。

采用 FastAPI + 内存 SQLite 方案（模式 B）。
"""

from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.dependencies import get_db
from backend.app.models.push_log import PushLog
from backend.app.routers.push import router


def _make_client():
    """创建使用内存 SQLite 的 TestClient。"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )

    import backend.app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    app = FastAPI()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.include_router(router)

    return TestClient(app), TestingSessionLocal


class TestPushLogsQuery:
    """T10: GET /push/logs 推送历史查询。"""

    def _seed_logs(self, session, base_time=None):
        """写入 10 条测试日志（8 成功 2 失败）。"""
        now = base_time or datetime.now(UTC)
        logs = [
            PushLog(message_id="msg-01", message_type="alert", channel="feishu", status="sent", created_at=now - timedelta(hours=1)),
            PushLog(message_id="msg-02", message_type="alert", channel="feishu", status="sent", created_at=now - timedelta(hours=2)),
            PushLog(message_id="msg-03", message_type="alert", channel="telegram", status="fallback", created_at=now - timedelta(hours=3)),
            PushLog(message_id="msg-04", message_type="alert", channel="feishu", status="sent", created_at=now - timedelta(hours=4)),
            PushLog(message_id="msg-05", message_type="briefing", channel="feishu", status="sent", created_at=now - timedelta(hours=5)),
            PushLog(message_id="msg-06", message_type="briefing", channel="feishu", status="sent", created_at=now - timedelta(hours=6)),
            PushLog(message_id="msg-07", message_type="system", channel="feishu", status="sent", created_at=now - timedelta(hours=7)),
            PushLog(message_id="msg-08", message_type="alert", channel="feishu", status="sent", created_at=now - timedelta(hours=8)),
            PushLog(message_id="msg-09", message_type="alert", channel="feishu", status="failed", error_reason="auth failed", created_at=now - timedelta(hours=9)),
            PushLog(message_id="msg-10", message_type="briefing", channel="telegram", status="failed", error_reason="timeout", created_at=now - timedelta(hours=10)),
        ]
        session.add_all(logs)
        session.commit()
        return now

    def test_list_all_logs(self):
        client, SessionLocal = _make_client()
        with SessionLocal() as session:
            self._seed_logs(session)

        resp = client.get("/push/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 10

    def test_filter_by_message_type(self):
        client, SessionLocal = _make_client()
        with SessionLocal() as session:
            self._seed_logs(session)

        resp = client.get("/push/logs?message_type=alert")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 6
        for item in data:
            assert item["message_type"] == "alert"

    def test_filter_by_status(self):
        client, SessionLocal = _make_client()
        with SessionLocal() as session:
            self._seed_logs(session)

        resp = client.get("/push/logs?status=failed")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        for item in data:
            assert item["status"] == "failed"

    def test_filter_by_time_range(self):
        client, SessionLocal = _make_client()
        with SessionLocal() as session:
            now = self._seed_logs(session)

        start = (now - timedelta(hours=5)).isoformat()
        end = (now - timedelta(hours=1)).isoformat()

        resp = client.get(f"/push/logs?start_time={start}&end_time={end}")
        assert resp.status_code == 200
        data = resp.json()
        # 5小时内到1小时前：msg-01, msg-02, msg-03, msg-04, msg-05
        assert len(data) == 5

    def test_combined_filter(self):
        client, SessionLocal = _make_client()
        with SessionLocal() as session:
            self._seed_logs(session)

        resp = client.get("/push/logs?message_type=briefing&status=sent")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        for item in data:
            assert item["message_type"] == "briefing"
            assert item["status"] == "sent"

    def test_limit_recent_100(self):
        client, SessionLocal = _make_client()
        with SessionLocal() as session:
            now = datetime.now(UTC)
            logs = [
                PushLog(
                    message_id=f"msg-{i:03d}",
                    message_type="alert",
                    channel="feishu",
                    status="sent",
                    created_at=now - timedelta(minutes=i),
                )
                for i in range(150)
            ]
            session.add_all(logs)
            session.commit()

        resp = client.get("/push/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 100
