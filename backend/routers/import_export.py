from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.dependencies import get_db
from backend.models.group import DEFAULT_GROUP_ID, DEFAULT_GROUP_NAME, Group
from backend.models.stock import Stock
from backend.models.watchlist import WatchlistItem
from backend.schemas.watchlist import WatchlistItemResponse
from backend.services.csv_export import export_watchlist_to_csv
from backend.services.csv_import import (
    CsvRowCountExceededError,
    import_watchlist_from_csv,
    parse_csv_rows,
)
import backend.services.stock_search as stock_search

router = APIRouter(prefix="/watchlist", tags=["import-export"])

MAX_UPLOAD_SIZE = 512 * 1024  # 512KB


def _find_or_create_group(db: Session, name: str) -> dict:
    """按名称查找分组，不存在则创建。"""
    if name == DEFAULT_GROUP_NAME:
        return {"id": DEFAULT_GROUP_ID, "name": name}

    group = db.query(Group).filter_by(name=name).first()
    if group is None:
        group = Group(name=name)
        db.add(group)
        db.commit()
        db.refresh(group)

    return {"id": group.id, "name": group.name}


def _get_existing_codes(db: Session) -> set[str]:
    return {item.stock_code for item in db.query(WatchlistItem).all()}


@router.post("/import", status_code=status.HTTP_200_OK)
def import_watchlist(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """上传 CSV 批量导入自选股。"""
    content = file.file.read()

    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"文件大小超过限制（最大 {MAX_UPLOAD_SIZE // 1024}KB）",
        )

    try:
        parsed_rows = parse_csv_rows(content)
    except CsvRowCountExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV 解析失败: {exc}",
        ) from exc

    existing_codes = _get_existing_codes(db)
    current_count = db.query(WatchlistItem).count()

    result = import_watchlist_from_csv(
        parsed_rows,
        search_stock_func=stock_search.search_stock,
        find_or_create_group_func=lambda name: _find_or_create_group(db, name),
        existing_codes=existing_codes,
        current_watchlist_count=current_count,
        max_watchlist_size=100,
    )

    # 将成功项持久化到数据库
    for item in result["successes"]:
        code = item["stock_code"]

        # 确保 Stock 记录存在
        db_stock = db.get(Stock, code)
        if db_stock is None:
            db_stock = Stock(
                code=code,
                name=item["name"],
                market=item["market"],
                sector=item.get("sector"),
                status=item["status"],
            )
            db.add(db_stock)

        # 创建 WatchlistItem
        watchlist_item = WatchlistItem(
            stock_code=code,
            group_id=item["group_id"],
            cost_price=item.get("cost_price"),
            shares=item.get("shares"),
        )
        db.add(watchlist_item)

    if result["successes"]:
        db.commit()

    return result


@router.get("/export")
def export_watchlist(db: Session = Depends(get_db)):
    """导出自选股列表为 CSV 文件。"""
    from sqlalchemy.orm import joinedload

    items = (
        db.query(WatchlistItem)
        .options(joinedload(WatchlistItem.stock), joinedload(WatchlistItem.group))
        .all()
    )

    # 转换为 dict 列表
    item_dicts = []
    for item in items:
        d = {
            "stock_code": item.stock_code,
            "stock": {
                "name": item.stock.name if item.stock else "",
            } if item.stock else None,
            "group": {
                "name": item.group.name if item.group else DEFAULT_GROUP_NAME,
            } if item.group else None,
            "cost_price": item.cost_price,
            "shares": item.shares,
        }
        item_dicts.append(d)

    csv_bytes = export_watchlist_to_csv(item_dicts)

    from fastapi.responses import Response

    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="watchlist.csv"',
        },
    )
