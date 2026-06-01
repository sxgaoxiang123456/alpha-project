from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from backend.dependencies import get_db
from backend.models.stock import Stock
from backend.models.watchlist import WatchlistItem
from backend.schemas.stock import StockSearchResult
from backend.schemas.watchlist import BatchDeleteRequest, WatchlistItemCreate, WatchlistItemResponse, WatchlistItemUpdate
import backend.services.stock_search as stock_search

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


@router.put("/{code}", response_model=WatchlistItemResponse)
def update_watchlist_item(
    code: str,
    data: WatchlistItemUpdate,
    db: Session = Depends(get_db),
) -> WatchlistItem:
    item = db.query(WatchlistItem).filter_by(stock_code=code).first()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"股票 {code} 不在自选股列表中",
        )

    if data.group_id is not None:
        item.group_id = data.group_id
    if data.cost_price is not None:
        item.cost_price = data.cost_price
    if data.shares is not None:
        item.shares = data.shares

    db.commit()
    db.refresh(item)
    return item


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist_item(
    code: str,
    db: Session = Depends(get_db),
) -> None:
    item = db.query(WatchlistItem).filter_by(stock_code=code).first()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"股票 {code} 不在自选股列表中",
        )

    db.delete(item)
    db.commit()
    return None


@router.post("/batch-delete")
def batch_delete_watchlist_items(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db),
) -> dict:
    deleted = 0
    for code in request.codes:
        item = db.query(WatchlistItem).filter_by(stock_code=code).first()
        if item is not None:
            db.delete(item)
            deleted += 1

    db.commit()
    return {
        "deleted_count": deleted,
        "message": f"已删除 {deleted} 只股票",
    }
