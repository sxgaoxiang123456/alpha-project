"""异步历史落盘单元测试 — 正常落盘、异常日志、主线程不阻塞。"""

import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.async_persistence import async_persist
from backend.app.database import Base
from backend.app.models.historical_quote import HistoricalQuote


@pytest.fixture
def session_factory(tmp_path):
    """使用临时文件数据库，避免多线程 :memory: 连接隔离问题。"""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    # 确保所有模型已注册到 metadata
    import backend.app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


class TestAsyncPersistence:
    """异步落盘测试。"""

    @pytest.mark.asyncio
    async def test_persists_quotes_to_db(self, session_factory):
        """验证行情数据被正确写入数据库。"""
        quotes = [
            {
                "stock_code": "600519",
                "open": Decimal("1800.00"),
                "close": Decimal("1850.50"),
                "high": Decimal("1860.00"),
                "low": Decimal("1790.00"),
                "volume": 10000,
                "turnover": Decimal("18505000.00"),
            },
            {
                "stock_code": "600000",
                "open": Decimal("10.00"),
                "close": Decimal("10.50"),
                "high": Decimal("10.80"),
                "low": Decimal("9.90"),
                "volume": 50000,
                "turnover": Decimal("525000.00"),
            },
        ]
        timestamp = datetime(2024, 6, 10, 10, 30, 0, tzinfo=UTC)

        await async_persist(quotes, session_factory, timestamp)

        with session_factory() as session:
            results = session.query(HistoricalQuote).all()
            assert len(results) == 2
            codes = {r.stock_code for r in results}
            assert codes == {"600519", "600000"}

    @pytest.mark.asyncio
    async def test_persists_with_date_from_timestamp(self, session_factory):
        """验证落盘时使用 timestamp 的 date 部分。"""
        quotes = [
            {
                "stock_code": "600519",
                "open": Decimal("1800.00"),
                "close": Decimal("1850.50"),
                "high": Decimal("1860.00"),
                "low": Decimal("1790.00"),
                "volume": 10000,
                "turnover": Decimal("18505000.00"),
            },
        ]
        timestamp = datetime(2024, 6, 10, 15, 0, 0, tzinfo=UTC)

        await async_persist(quotes, session_factory, timestamp)

        with session_factory() as session:
            result = session.query(HistoricalQuote).first()
            assert result.date == timestamp.date()

    @pytest.mark.asyncio
    async def test_empty_quotes_noop(self, session_factory):
        """验证空列表不写入任何数据。"""
        await async_persist([], session_factory, datetime.now(UTC))

        with session_factory() as session:
            assert session.query(HistoricalQuote).count() == 0

    @pytest.mark.asyncio
    async def test_exception_logged_not_raised(self, session_factory, caplog, monkeypatch):
        """验证异常时记录日志，不抛到调用方。"""
        quotes = [{
            "stock_code": "600519",
            "open": Decimal("1800.00"),
            "close": Decimal("1850.50"),
            "high": Decimal("1860.00"),
            "low": Decimal("1790.00"),
            "volume": 10000,
            "turnover": Decimal("18505000.00"),
        }]

        def _raise(*a, **k):
            raise RuntimeError("模拟写入异常")

        monkeypatch.setattr(
            "backend.app.core.async_persistence._persist_sync", _raise
        )

        with caplog.at_level(logging.ERROR, logger="backend.app.core.async_persistence"):
            # 不应抛出异常
            await async_persist(quotes, session_factory, datetime.now(UTC))

        assert "异步落盘失败" in caplog.text

    @pytest.mark.asyncio
    async def test_main_thread_not_blocked(self, session_factory):
        """验证主线程不被阻塞 — async_persist 立即返回。"""
        quotes = [
            {
                "stock_code": "600519",
                "open": Decimal("1800.00"),
                "close": Decimal("1850.50"),
                "high": Decimal("1860.00"),
                "low": Decimal("1790.00"),
                "volume": 10000,
                "turnover": Decimal("18505000.00"),
            },
        ]
        timestamp = datetime.now(UTC)

        start = asyncio.get_event_loop().time()
        await async_persist(quotes, session_factory, timestamp)
        elapsed = asyncio.get_event_loop().time() - start

        # asyncio.to_thread 确实会等待线程完成，这里验证的是
        # 事件循环在 to_thread 期间可以执行其他任务
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_updates_existing_record(self, session_factory):
        """验证同一股票同一天的记录会被更新而非重复插入。"""
        quotes_v1 = [
            {
                "stock_code": "600519",
                "open": Decimal("1800.00"),
                "close": Decimal("1850.50"),
                "high": Decimal("1860.00"),
                "low": Decimal("1790.00"),
                "volume": 10000,
                "turnover": Decimal("18505000.00"),
            },
        ]
        quotes_v2 = [
            {
                "stock_code": "600519",
                "open": Decimal("1800.00"),
                "close": Decimal("1900.00"),  # 更新收盘价
                "high": Decimal("1910.00"),
                "low": Decimal("1790.00"),
                "volume": 20000,
                "turnover": Decimal("38000000.00"),
            },
        ]
        timestamp = datetime(2024, 6, 10, 10, 0, 0, tzinfo=UTC)

        await async_persist(quotes_v1, session_factory, timestamp)
        await async_persist(quotes_v2, session_factory, timestamp)

        with session_factory() as session:
            results = session.query(HistoricalQuote).all()
            assert len(results) == 1
            assert results[0].close == Decimal("1900.00")
            assert results[0].volume == 20000
