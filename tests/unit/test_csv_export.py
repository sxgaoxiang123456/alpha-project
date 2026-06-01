import csv
import io
from decimal import Decimal

import pytest


# ---------------------------------------------------------------------------
# export_watchlist_to_csv
# ---------------------------------------------------------------------------

def test_export_empty_watchlist_returns_header_only():
    from app.services.csv_export import export_watchlist_to_csv

    result = export_watchlist_to_csv([])
    text = result.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    assert reader.fieldnames == ["code", "name", "group", "cost_price", "shares"]
    assert list(reader) == []


def test_export_watchlist_with_items():
    from app.services.csv_export import export_watchlist_to_csv

    items = [
        {
            "stock_code": "600519",
            "stock": {"name": "贵州茅台", "market": "沪", "sector": "白酒", "status": "正常"},
            "group": {"name": "持仓"},
            "cost_price": Decimal("1500.50"),
            "shares": 100,
        },
        {
            "stock_code": "000001",
            "stock": {"name": "平安银行", "market": "深", "sector": "银行", "status": "正常"},
            "group": {"name": "默认分组"},
            "cost_price": None,
            "shares": None,
        },
    ]

    result = export_watchlist_to_csv(items)
    text = result.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)

    assert len(rows) == 2
    assert rows[0]["code"] == "600519"
    assert rows[0]["name"] == "贵州茅台"
    assert rows[0]["group"] == "持仓"
    assert rows[0]["cost_price"] == "1500.50"
    assert rows[0]["shares"] == "100"

    assert rows[1]["code"] == "000001"
    assert rows[1]["name"] == "平安银行"
    assert rows[1]["group"] == "默认分组"
    assert rows[1]["cost_price"] == ""
    assert rows[1]["shares"] == ""


def test_export_format_matches_import_format():
    """导出格式必须与导入格式一致，确保用户可导出后再导入。"""
    from app.services.csv_export import export_watchlist_to_csv

    items = [
        {
            "stock_code": "600000",
            "stock": {"name": "浦发银行", "market": "沪", "sector": "银行", "status": "正常"},
            "group": {"name": "观察"},
            "cost_price": Decimal("10.50"),
            "shares": 500,
        },
    ]

    result = export_watchlist_to_csv(items)
    text = result.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)

    # 验证所有必需的导入列都存在
    assert "code" in reader.fieldnames
    assert "name" in reader.fieldnames
    assert "group" in reader.fieldnames
    assert "cost_price" in reader.fieldnames
    assert "shares" in reader.fieldnames

    # 验证数据正确
    assert rows[0]["code"] == "600000"
    assert rows[0]["name"] == "浦发银行"
    assert rows[0]["group"] == "观察"
    assert rows[0]["cost_price"] == "10.50"
    assert rows[0]["shares"] == "500"


def test_export_with_missing_stock_or_group_uses_defaults():
    from app.services.csv_export import export_watchlist_to_csv

    items = [
        {
            "stock_code": "600000",
            "stock": None,
            "group": None,
            "cost_price": None,
            "shares": None,
        },
    ]

    result = export_watchlist_to_csv(items)
    text = result.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)

    assert rows[0]["code"] == "600000"
    assert rows[0]["name"] == ""
    assert rows[0]["group"] == "默认分组"
    assert rows[0]["cost_price"] == ""
    assert rows[0]["shares"] == ""
