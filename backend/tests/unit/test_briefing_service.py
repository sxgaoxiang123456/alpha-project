from datetime import UTC, datetime
from decimal import Decimal
from unittest import mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.schemas.briefing import BriefingResponse, TopMover
from backend.app.schemas.quote import MarketIndex, Quote


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


class FakeMarketIndexService:
    def get_indices(self, *, use_cache=False):
        return [
            MarketIndex(
                index_code="sh000001",
                index_name="上证指数",
                current_point=Decimal("3000.5"),
                change_percent=Decimal("1.2"),
                change_amount=Decimal("36.5"),
                turnover=Decimal("450000000000"),
                updated_at=datetime.now(UTC),
                source_status="primary",
                actual_timestamp=datetime.now(UTC),
            ),
        ]


class FakeQuoteService:
    def get_watchlist_quotes(self, *, use_cache=False):
        return [
            Quote(
                stock_code="600000",
                stock_name="浦发银行",
                current_price=Decimal("10.5"),
                change_percent=Decimal("2.1"),
                volume=5000000,
                turnover=Decimal("50000000"),
                updated_at=datetime.now(UTC),
                status="normal",
                source_status="primary",
                actual_timestamp=datetime.now(UTC),
            ),
        ]


class FakeTopMoverService:
    def compute_top_movers(self, watchlist_quotes, fallback_quotes=None):
        return [
            TopMover(
                stock_code="600000",
                stock_name="浦发银行",
                move_type="volume_spike",
                value=3.5,
                change_percent=2.1,
                sector="银行",
                insight="成交量突增",
                data_sufficient=True,
            ),
        ]


class FakePromptLoader:
    def render(self, **kwargs):
        return "prompt text"


class FakeLLMClient:
    def __init__(self, degraded=False):
        self.degraded = degraded

    def generate(self, prompt):
        from backend.app.services.briefing_llm_client import LLMResult

        if self.degraded:
            return LLMResult(is_degraded=True, error_reason="LLM 失败")
        return LLMResult(
            is_degraded=False,
            data={"insights": ["大盘整体向好"], "market_summary": "情绪积极"},
        )


class TestBriefingService:
    def test_generate_returns_briefing_on_trading_day(self, db_session):
        from backend.app.services.briefing_service import BriefingService

        service = BriefingService(
            db=db_session,
            market_index_service=FakeMarketIndexService(),
            quote_service=FakeQuoteService(),
            top_mover_service=FakeTopMoverService(),
            prompt_loader=FakePromptLoader(),
            llm_client=FakeLLMClient(degraded=False),
            is_trading_day=lambda d: True,
        )

        result = service.generate(current_date=datetime(2026, 6, 23).date())

        assert isinstance(result, BriefingResponse)
        assert result.is_degraded is False
        assert "上证指数" in result.market_indices
        assert len(result.top_movers) == 1
        assert result.top_movers[0].stock_code == "600000"
        assert result.insights == ["大盘整体向好"]

    def test_generate_skips_on_non_trading_day(self, db_session):
        from backend.app.services.briefing_service import BriefingService

        service = BriefingService(
            db=db_session,
            market_index_service=FakeMarketIndexService(),
            quote_service=FakeQuoteService(),
            top_mover_service=FakeTopMoverService(),
            prompt_loader=FakePromptLoader(),
            llm_client=FakeLLMClient(degraded=False),
            is_trading_day=lambda d: False,
        )

        result = service.generate(current_date=datetime(2026, 6, 23).date())

        assert result is None

    def test_generate_degraded_when_llm_fails(self, db_session):
        from backend.app.services.briefing_service import BriefingService

        service = BriefingService(
            db=db_session,
            market_index_service=FakeMarketIndexService(),
            quote_service=FakeQuoteService(),
            top_mover_service=FakeTopMoverService(),
            prompt_loader=FakePromptLoader(),
            llm_client=FakeLLMClient(degraded=True),
            is_trading_day=lambda d: True,
        )

        result = service.generate(current_date=datetime(2026, 6, 23).date())

        assert isinstance(result, BriefingResponse)
        assert result.is_degraded is True
        assert result.degraded_reason is not None
        assert result.insights == []
        assert len(result.top_movers) == 1

    def test_generate_caches_latest_briefing(self, db_session):
        from backend.app.services.briefing_service import BriefingService

        cache = {}

        class FakeCacheService:
            def set(self, key, value, ttl_seconds=None):
                cache[key] = value

        service = BriefingService(
            db=db_session,
            market_index_service=FakeMarketIndexService(),
            quote_service=FakeQuoteService(),
            top_mover_service=FakeTopMoverService(),
            prompt_loader=FakePromptLoader(),
            llm_client=FakeLLMClient(degraded=False),
            is_trading_day=lambda d: True,
            cache_service=FakeCacheService(),
        )

        service.generate(current_date=datetime(2026, 6, 23).date())

        assert "latest_briefing" in cache
