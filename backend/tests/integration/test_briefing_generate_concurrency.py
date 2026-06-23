"""POST /api/briefing/generate 并发 / 限频轻量版测试。

验证并发调用手动刷新端点时，冷却键能起到限流作用：
至少有一个请求返回 429，或后端实际只触发一次简报生成。
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from unittest import mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.main import app


@pytest.fixture(scope="module")
def _engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import backend.app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(_engine):
    SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=_engine
    )

    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides = {}
    from backend.app.dependencies import get_db

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestBriefingGenerateConcurrency:
    def test_concurrent_manual_generate_at_least_one_429_or_single_trigger(
        self,
        client,
    ):
        import backend.app.routers.briefing as briefing_module

        # 确保交易日
        with mock.patch.object(
            briefing_module.trading_calendar,
            "is_trading_day",
            return_value=True,
        ):
            trigger_calls = []

            def _stub_trigger(app):
                trigger_calls.append(1)

            with mock.patch.object(
                briefing_module,
                "_trigger_manual_briefing",
                side_effect=_stub_trigger,
            ):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [
                        executor.submit(client.post, "/api/briefing/generate"),
                        executor.submit(client.post, "/api/briefing/generate"),
                    ]
                    responses = [f.result() for f in futures]

        status_codes = [r.status_code for r in responses]

        # 轻量版断言：至少有一个请求被 429 拦截，或者后端只触发一次生成
        assert 429 in status_codes or len(trigger_calls) <= 1, (
            f"期望至少一个 429 或只触发一次生成，"
            f"实际状态码 {status_codes}，触发次数 {len(trigger_calls)}"
        )
