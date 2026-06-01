from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_db
from app.models.stock import Stock
from app.models.watchlist import WatchlistItem
from app.schemas.stock import StockSearchResult
from app.schemas.watchlist import WatchlistItemCreate, WatchlistItemResponse
import app.services.stock_search as stock_search

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

MAX_WATCHLIST_SIZE = 100


@router.post("", response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED)
def add_watchlist_item(
    item: WatchlistItemCreate,
    db: Session = Depends(get_db),
) -> WatchlistItem:
    count = db.query(WatchlistItem).count()
    if count >= MAX_WATCHLIST_SIZE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="自选股数量已达上限（100只）",
        )

    stock = stock_search.search_stock(item.stock_code)
    if stock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"股票 {item.stock_code} 不存在",
        )

    existing = db.query(WatchlistItem).filter_by(stock_code=item.stock_code).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"股票 {item.stock_code} 已存在于自选股列表中",
        )

    db_stock = db.get(Stock, item.stock_code)
    if db_stock is None:
        db_stock = Stock(
            code=stock.code,
            name=stock.name,
            market=stock.market,
            sector=stock.sector,
            status=stock.status,
        )
        db.add(db_stock)

    watchlist_item = WatchlistItem(
        stock_code=item.stock_code,
        group_id=item.group_id,
        cost_price=item.cost_price,
        shares=item.shares,
    )
    db.add(watchlist_item)
    db.commit()
    db.refresh(watchlist_item)

    return watchlist_item


@router.get("/search", response_model=list[StockSearchResult])
def search_watchlist(
    q: str = Query(..., min_length=1),
) -> list[StockSearchResult]:
    return stock_search.search_stocks(q)


@router.get("", response_model=list[WatchlistItemResponse])
def list_watchlist_items(
    db: Session = Depends(get_db),
) -> list[WatchlistItem]:
    items = (
        db.query(WatchlistItem)
        .options(joinedload(WatchlistItem.stock), joinedload(WatchlistItem.group))
        .all()
    )
    return items
