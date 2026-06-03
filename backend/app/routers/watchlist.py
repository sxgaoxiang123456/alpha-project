import threading

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.app.dependencies import get_db
from backend.app.models.stock import Stock
from backend.app.models.watchlist import WatchlistItem
from backend.app.schemas.stock import StockSearchResult
from backend.app.schemas.watchlist import BatchDeleteRequest, WatchlistItemCreate, WatchlistItemResponse, WatchlistItemUpdate
import backend.app.services.stock_search as stock_search

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

MAX_WATCHLIST_SIZE = 100

# 串行化 add_watchlist_item 中的 count 检查与 INSERT，防止并发突破上限。
# 单进程内有效；多进程/多实例部署需替换为分布式锁（如 Redis distributed lock）。
_watchlist_add_lock = threading.Lock()


@router.post("", response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED)
def add_watchlist_item(
    item: WatchlistItemCreate,
    db: Session = Depends(get_db),
) -> WatchlistItem:
    # 搜索不依赖数据库状态，可在锁外执行
    stock = stock_search.search_stock(item.stock_code)
    if stock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"股票 {item.stock_code} 不存在",
        )

    with _watchlist_add_lock:
        count = db.query(WatchlistItem).count()
        if count >= MAX_WATCHLIST_SIZE:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="自选股数量已达上限（100只）",
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
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"股票 {item.stock_code} 已存在于自选股列表中",
            ) from exc
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
