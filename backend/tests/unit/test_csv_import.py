import io
from decimal import Decimal

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_csv_content(rows: list[dict]) -> bytes:
    """将行数据编码为 UTF-8 CSV 字节流。"""
    import csv

    if not rows:
        return b""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["code", "name", "group", "cost_price", "shares"])
    writer.writeheader()
    for row in rows:
        writer.writerow({
            "code": row.get("code", ""),
            "name": row.get("name", ""),
            "group": row.get("group", "默认分组"),
            "cost_price": row.get("cost_price", ""),
            "shares": row.get("shares", ""),
        })
    return output.getvalue().encode("utf-8")


def make_n_valid_rows(n: int) -> list[dict]:
    return [
        {"code": f"{600000 + i:06d}", "name": f"股票{i+1}", "group": "默认分组"}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# parse_csv_rows
# ---------------------------------------------------------------------------

def test_parse_csv_rows_returns_20_valid_rows():
    from backend.app.services.csv_import import parse_csv_rows

    rows = make_n_valid_rows(20)
    content = make_csv_content(rows)
    parsed = parse_csv_rows(content)

    assert len(parsed) == 20
    assert parsed[0]["code"] == "600000"
    assert parsed[0]["name"] == "股票1"


def test_parse_csv_rows_rejects_over_100_rows():
    from backend.app.services.csv_import import CsvRowCountExceededError, parse_csv_rows

    rows = make_n_valid_rows(101)
    content = make_csv_content(rows)

    with pytest.raises(CsvRowCountExceededError) as exc_info:
        parse_csv_rows(content)

    assert "100" in str(exc_info.value)


def test_parse_csv_rows_rejects_malformed_csv():
    from backend.app.services.csv_import import CsvParseError, parse_csv_rows

    content = b"not,a,csv\n1,2"

    with pytest.raises(CsvParseError):
        parse_csv_rows(content)


# ---------------------------------------------------------------------------
# import_watchlist_from_csv
# ---------------------------------------------------------------------------

def test_import_20_valid_rows_returns_success_count_20():
    from backend.app.services.csv_import import import_watchlist_from_csv

    csv_rows = make_n_valid_rows(20)

    def fake_search(code: str):
        return {"code": code, "name": f"股票{code}", "market": "沪", "sector": None, "status": "正常"}

    result = import_watchlist_from_csv(csv_rows, search_stock_func=fake_search)

    assert result["success_count"] == 20
    assert result["failure_count"] == 0
    assert len(result["successes"]) == 20
    assert len(result["failures"]) == 0


def test_import_with_2_invalid_rows_returns_partial_success():
    from backend.app.services.csv_import import import_watchlist_from_csv

    csv_rows = [
        {"code": "600000", "name": "股票1"},
        {"code": "600001", "name": "股票2"},
        {"code": "60001A", "name": "错误格式"},  # 格式错误
        {"code": "600003", "name": "股票3"},
        {"code": "", "name": "空代码"},  # 空代码
    ]

    def fake_search(code: str):
        return {"code": code, "name": f"股票{code}", "market": "沪", "sector": None, "status": "正常"}

    result = import_watchlist_from_csv(csv_rows, search_stock_func=fake_search)

    assert result["success_count"] == 3
    assert result["failure_count"] == 2
    assert len(result["failures"]) == 2
    codes = [f["code"] for f in result["failures"]]
    assert "60001A" in codes or "" in codes


def test_import_skips_duplicate_stock_code():
    from backend.app.services.csv_import import import_watchlist_from_csv

    csv_rows = [
        {"code": "600000", "name": "股票1"},
        {"code": "600000", "name": "重复股票"},  # CSV 内重复
    ]

    def fake_search(code: str):
        return {"code": code, "name": f"股票{code}", "market": "沪", "sector": None, "status": "正常"}

    result = import_watchlist_from_csv(csv_rows, search_stock_func=fake_search)

    assert result["success_count"] == 1
    assert result["failure_count"] == 1
    assert result["failures"][0]["reason"] == "股票代码重复"


def test_import_with_existing_watchlist_item_skips_duplicate():
    from backend.app.services.csv_import import import_watchlist_from_csv

    csv_rows = [{"code": "600000", "name": "股票1"}]

    def fake_search(code: str):
        return {"code": code, "name": f"股票{code}", "market": "沪", "sector": None, "status": "正常"}

    # 模拟已存在 600000
    existing_codes = {"600000"}

    result = import_watchlist_from_csv(
        csv_rows,
        search_stock_func=fake_search,
        existing_codes=existing_codes,
    )

    assert result["success_count"] == 0
    assert result["failure_count"] == 1
    assert "已存在" in result["failures"][0]["reason"]


def test_import_stock_not_found_returns_failure():
    from backend.app.services.csv_import import import_watchlist_from_csv

    csv_rows = [{"code": "999999", "name": "不存在"}]

    def fake_search(code: str):
        return None

    result = import_watchlist_from_csv(csv_rows, search_stock_func=fake_search)

    assert result["success_count"] == 0
    assert result["failure_count"] == 1
    assert "不存在" in result["failures"][0]["reason"]


def test_import_reaches_watchlist_limit_returns_failure():
    from backend.app.services.csv_import import import_watchlist_from_csv

    csv_rows = [{"code": "600000", "name": "股票1"}]

    def fake_search(code: str):
        return {"code": code, "name": f"股票{code}", "market": "沪", "sector": None, "status": "正常"}

    result = import_watchlist_from_csv(
        csv_rows,
        search_stock_func=fake_search,
        current_watchlist_count=100,
        max_watchlist_size=100,
    )

    assert result["success_count"] == 0
    assert result["failure_count"] == 1
    assert "上限" in result["failures"][0]["reason"]


def test_import_preserve_cost_price_and_shares():
    from backend.app.services.csv_import import import_watchlist_from_csv

    csv_rows = [{"code": "600000", "name": "股票1", "cost_price": "1500.50", "shares": "100"}]

    def fake_search(code: str):
        return {"code": code, "name": f"股票{code}", "market": "沪", "sector": None, "status": "正常"}

    result = import_watchlist_from_csv(csv_rows, search_stock_func=fake_search)

    assert result["success_count"] == 1
    item = result["successes"][0]
    assert item["cost_price"] == Decimal("1500.50")
    assert item["shares"] == 100


def test_import_with_group_name_creates_or_finds_group():
    from backend.app.services.csv_import import import_watchlist_from_csv

    csv_rows = [{"code": "600000", "name": "股票1", "group": "持仓"}]

    def fake_search(code: str):
        return {"code": code, "name": f"股票{code}", "market": "沪", "sector": None, "status": "正常"}

    def fake_find_or_create_group(name: str):
        return {"id": 2, "name": name}

    result = import_watchlist_from_csv(
        csv_rows,
        search_stock_func=fake_search,
        find_or_create_group_func=fake_find_or_create_group,
    )

    assert result["success_count"] == 1
    assert result["successes"][0]["group_id"] == 2


def test_import_invalid_cost_price_returns_single_failure():
    from backend.app.services.csv_import import import_watchlist_from_csv

    csv_rows = [{"code": "600000", "name": "股票1", "cost_price": "abc"}]

    def fake_search(code: str):
        return {"code": code, "name": f"股票{code}", "market": "沪", "sector": None, "status": "正常"}

    result = import_watchlist_from_csv(csv_rows, search_stock_func=fake_search)

    assert result["success_count"] == 0
    assert result["failure_count"] == 1
    assert "成本价" in result["failures"][0]["reason"] or "格式" in result["failures"][0]["reason"]


def test_import_invalid_shares_returns_single_failure():
    from backend.app.services.csv_import import import_watchlist_from_csv

    csv_rows = [{"code": "600000", "name": "股票1", "shares": "xyz"}]

    def fake_search(code: str):
        return {"code": code, "name": f"股票{code}", "market": "沪", "sector": None, "status": "正常"}

    result = import_watchlist_from_csv(csv_rows, search_stock_func=fake_search)

    assert result["success_count"] == 0
    assert result["failure_count"] == 1
    assert "持股数" in result["failures"][0]["reason"] or "格式" in result["failures"][0]["reason"]
