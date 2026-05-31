from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError


def test_watchlist_create_rejects_invalid_cost_price_string():
    from app.schemas.watchlist import WatchlistItemCreate

    with pytest.raises(ValidationError):
        WatchlistItemCreate(stock_code="600519", cost_price="abc")


def test_stock_and_watchlist_reject_non_six_digit_codes():
    from app.schemas.stock import StockBase
    from app.schemas.watchlist import WatchlistCsvRow, WatchlistItemCreate

    with pytest.raises(ValidationError):
        StockBase(code="60051A", name="贵州茅台", market="沪")

    with pytest.raises(ValidationError):
        WatchlistItemCreate(stock_code="60051")

    with pytest.raises(ValidationError):
        StockBase(code="６００５１９", name="贵州茅台", market="沪")

    with pytest.raises(ValidationError):
        WatchlistItemCreate(stock_code="٦٠٠٥١٩")

    with pytest.raises(ValidationError):
        WatchlistCsvRow(code="６００５１９", name="贵州茅台")


def test_watchlist_rejects_negative_cost_price_and_shares():
    from app.schemas.watchlist import WatchlistItemCreate, WatchlistItemUpdate

    with pytest.raises(ValidationError):
        WatchlistItemCreate(stock_code="600519", cost_price=Decimal("-0.01"))

    with pytest.raises(ValidationError):
        WatchlistItemUpdate(shares=-1)


def test_watchlist_create_and_update_accept_valid_holding_payloads():
    from app.schemas.watchlist import WatchlistItemCreate, WatchlistItemUpdate

    created = WatchlistItemCreate(
        stock_code="600519",
        cost_price="1500.50",
        shares=100,
    )
    updated = WatchlistItemUpdate(
        group_id=2,
        cost_price=Decimal("1498.00"),
        shares=0,
    )

    assert created.group_id == 1
    assert created.cost_price == Decimal("1500.50")
    assert created.shares == 100
    assert updated.group_id == 2
    assert updated.cost_price == Decimal("1498.00")
    assert updated.shares == 0


def test_group_create_rejects_blank_name():
    from app.schemas.group import GroupCreate

    with pytest.raises(ValidationError):
        GroupCreate(name="   ")


def test_watchlist_csv_row_validates_csv_contract():
    from app.schemas.watchlist import WatchlistCsvRow

    row = WatchlistCsvRow(
        code="600519",
        name="贵州茅台",
        group=" 持仓 ",
        cost_price="1500.50",
        shares=100,
    )
    blank_optional_row = WatchlistCsvRow(
        code="000001",
        name="平安银行",
        group="观察",
        cost_price="",
        shares="   ",
    )

    assert row.code == "600519"
    assert row.group == "持仓"
    assert row.cost_price == Decimal("1500.50")
    assert row.shares == 100
    assert blank_optional_row.cost_price is None
    assert blank_optional_row.shares is None

    with pytest.raises(ValidationError):
        WatchlistCsvRow(code="60051A", name="贵州茅台")

    with pytest.raises(ValidationError):
        WatchlistCsvRow(code="600519", name="   ")


def test_group_response_supports_model_validate_from_sqlalchemy_model():
    from app.models.group import Group
    from app.schemas.group import GroupResponse

    created_at = datetime(2026, 5, 31, 10, 0, tzinfo=UTC)
    group = Group(id=1, name="默认分组", created_at=created_at, is_default=True)

    response = GroupResponse.model_validate(group)

    assert response.id == 1
    assert response.name == "默认分组"
    assert response.created_at == created_at
    assert response.is_default is True


def test_response_schemas_support_model_validate_from_attributes():
    from app.models.group import Group
    from app.models.stock import Stock
    from app.models.watchlist import WatchlistItem
    from app.schemas import GroupResponse, StockResponse, WatchlistItemResponse

    added_at = datetime(2026, 5, 31, 10, 30, tzinfo=UTC)
    group = Group(id=1, name="默认分组", created_at=added_at, is_default=True)
    stock = Stock(
        code="600519",
        name="贵州茅台",
        market="沪",
        sector="白酒",
        status="待验证",
    )
    item = WatchlistItem(
        id=7,
        stock_code="600519",
        group_id=1,
        added_at=added_at,
        cost_price=Decimal("1500.50"),
        shares=100,
    )
    item.stock = stock
    item.group = group

    stock_response = StockResponse.model_validate(stock)
    group_response = GroupResponse.model_validate(group)
    watchlist_response = WatchlistItemResponse.model_validate(item)

    assert stock_response.code == "600519"
    assert stock_response.status == "待验证"
    assert group_response.name == "默认分组"
    assert watchlist_response.id == 7
    assert watchlist_response.cost_price == Decimal("1500.50")
    assert watchlist_response.shares == 100
    assert watchlist_response.stock == stock_response
    assert watchlist_response.group == group_response


def test_watchlist_response_rejects_negative_cost_price_from_attributes():
    from app.models.watchlist import WatchlistItem
    from app.schemas import WatchlistItemResponse

    item = WatchlistItem(
        id=8,
        stock_code="600519",
        group_id=1,
        added_at=datetime(2026, 5, 31, 11, 0, tzinfo=UTC),
        cost_price=Decimal("-1.00"),
        shares=100,
    )

    with pytest.raises(ValidationError):
        WatchlistItemResponse.model_validate(item)
