"""异步历史数据落盘工具 — 将同步数据库写入移出事件循环。"""

import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from backend.app.models.historical_quote import HistoricalQuote

logger = logging.getLogger(__name__)


async def async_persist(
    quotes: list[dict[str, Any]],
    session_factory: Any,
    timestamp: datetime | None = None,
) -> None:
    """异步持久化行情数据到 SQLite。

    使用 asyncio.to_thread() 将同步数据库写入移出事件循环，
    异常时记录 error 日志，不抛到用户层。

    Args:
        quotes: 清洗后的行情数据列表，每项包含 stock_code/open/close/high/low/volume/turnover
        session_factory: SQLAlchemy sessionmaker
        timestamp: 数据时间戳，默认使用当前 UTC 时间
    """
    if not quotes:
        return

    actual_ts = timestamp or datetime.now(UTC)

    try:
        await asyncio.to_thread(_persist_sync, quotes, session_factory, actual_ts)
    except Exception:
        logger.exception("异步落盘失败")


def _persist_sync(
    quotes: list[dict[str, Any]],
    session_factory: Any,
    timestamp: datetime,
) -> None:
    """同步执行数据库写入（在后台线程中运行）。"""
    with session_factory() as session:
        for quote in quotes:
            historical = _build_historical_quote(quote, timestamp)
            if historical is None:
                continue

            existing = session.get(
                HistoricalQuote,
                (historical.stock_code, historical.date),
            )
            if existing is None:
                session.add(historical)
            else:
                existing.open = historical.open
                existing.close = historical.close
                existing.high = historical.high
                existing.low = historical.low
                existing.volume = historical.volume
                existing.turnover = historical.turnover

        session.commit()


def _build_historical_quote(
    quote: dict[str, Any],
    timestamp: datetime,
) -> HistoricalQuote | None:
    """从清洗后的行情数据构建 HistoricalQuote 模型。"""
    code = quote.get("stock_code")
    if not code:
        return None

    close = _decimal_or_none(quote.get("close") or quote.get("price"))
    open_price = _decimal_or_none(quote.get("open") or close)
    high = _decimal_or_none(quote.get("high") or close)
    low = _decimal_or_none(quote.get("low") or close)
    volume = _int_or_none(quote.get("volume"))
    turnover = _decimal_or_none(quote.get("turnover") or quote.get("amount"))

    prices = (open_price, close, high, low)
    if any(price is None or price <= 0 for price in prices):
        return None
    if volume is None or volume < 0 or turnover is None or turnover < 0:
        return None

    return HistoricalQuote(
        stock_code=code,
        date=timestamp.date(),
        open=open_price,
        close=close,
        high=high,
        low=low,
        volume=volume,
        turnover=turnover,
    )


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
