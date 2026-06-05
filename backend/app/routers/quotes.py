import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.dependencies import get_db
from backend.app.core.trading_calendar import is_trading_day, is_trading_time
from backend.app.models.watchlist import WatchlistItem
from backend.app.schemas.quote import MarketIndex, Quote
from backend.app.services.cache_service import CacheService
from backend.app.services.data_cleaner import DataCleaner
from backend.app.services.data_source_facade import DataSourceFacade
from backend.app.services.market_index import MarketIndexService
from backend.app.services.quote_service import QuoteService

router = APIRouter(prefix="/quotes", tags=["quotes"])


def get_quote_cache(db: Session = Depends(get_db)) -> CacheService:
    return CacheService(db)


def get_quote_service(
    db: Session = Depends(get_db),
    cache: CacheService = Depends(get_quote_cache),
) -> QuoteService:
    return QuoteService(
        db=db,
        facade=DataSourceFacade(db),
        cleaner=DataCleaner(),
        cache=cache,
    )


def get_market_index_service(
    db: Session = Depends(get_db),
    cache: CacheService = Depends(get_quote_cache),
) -> MarketIndexService:
    return MarketIndexService(
        facade=DataSourceFacade(db),
        cache=cache,
    )


@router.get("", response_model=list[Quote])
def list_quotes(
    db: Session = Depends(get_db),
    cache: CacheService = Depends(get_quote_cache),
    quote_service: QuoteService = Depends(get_quote_service),
) -> list[Quote]:
    from datetime import date as date_type

    items = db.query(WatchlistItem).order_by(WatchlistItem.id).all()
    if not items:
        return []

    today = date_type.today()
    outside_trading = not is_trading_day(today) or not is_trading_time()

    cached_quotes: list[Quote] = []
    for item in items:
        cached = cache.get(f"quote:{item.stock_code}")
        if cached is None:
            return quote_service.get_watchlist_quotes()
        quote = Quote.model_validate_json(cached)
        quote.source_status = "cached"
        if outside_trading:
            quote.status = "market_closed"
        cached_quotes.append(quote)

    return cached_quotes


@router.get("/market", response_model=list[MarketIndex])
def list_market_indices(
    cache: CacheService = Depends(get_quote_cache),
    market_index_service: MarketIndexService = Depends(get_market_index_service),
) -> list[MarketIndex]:
    cached_indices: list[MarketIndex] = []
    for index_code in MarketIndexService.INDEX_CODES:
        cached = cache.get(f"market_index:{index_code}")
        if cached is None:
            return market_index_service.get_indices()
        cached_indices.append(MarketIndex.model_validate_json(cached))

    return cached_indices
