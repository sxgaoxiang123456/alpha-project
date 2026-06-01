import sys
from types import SimpleNamespace

import pytest


def test_search_stock_by_code_returns_akshare_match():
    from app.services.stock_search import search_stock

    def akshare_lookup(query: str):
        assert query == "600519"
        return {
            "code": "600519",
            "name": "贵州茅台",
            "market": "沪",
            "sector": "白酒",
            "status": "正常",
        }

    def baostock_lookup(query: str):
        raise AssertionError("AkShare 命中时不应调用 BaoStock")

    stock = search_stock(
        "600519",
        akshare_lookup=akshare_lookup,
        baostock_lookup=baostock_lookup,
    )

    assert stock is not None
    assert stock.code == "600519"
    assert stock.name == "贵州茅台"
    assert stock.market == "沪"
    assert stock.sector == "白酒"
    assert stock.status == "正常"


def test_search_stock_falls_back_to_baostock_when_akshare_fails():
    from app.services.stock_search import search_stock

    def akshare_lookup(query: str):
        raise RuntimeError("akshare unavailable")

    def baostock_lookup(query: str):
        assert query == "600519"
        return {
            "code": "600519",
            "name": "贵州茅台",
            "market": "沪",
            "sector": None,
            "status": "正常",
        }

    stock = search_stock(
        "600519",
        akshare_lookup=akshare_lookup,
        baostock_lookup=baostock_lookup,
    )

    assert stock is not None
    assert stock.code == "600519"
    assert stock.name == "贵州茅台"


def test_search_stock_returns_none_when_no_provider_finds_code():
    from app.services.stock_search import search_stock

    calls = []

    def akshare_lookup(query: str):
        calls.append("akshare")
        return None

    def baostock_lookup(query: str):
        calls.append("baostock")
        return None

    stock = search_stock(
        "999999",
        akshare_lookup=akshare_lookup,
        baostock_lookup=baostock_lookup,
    )

    assert stock is None
    assert calls == ["akshare", "baostock"]


def test_search_stock_rejects_invalid_code_format_without_querying_providers():
    from app.services.stock_search import StockCodeFormatError, search_stock

    def fail_lookup(query: str):
        raise AssertionError("格式错误时不应调用数据源")

    with pytest.raises(StockCodeFormatError):
        search_stock(
            "60051A",
            akshare_lookup=fail_lookup,
            baostock_lookup=fail_lookup,
        )


def test_search_stocks_by_name_returns_candidates_from_akshare():
    from app.services.stock_search import search_stocks

    def akshare_lookup(query: str):
        assert query == "茅台"
        return [
            {"code": "600519", "name": "贵州茅台", "market": "沪"},
            {"code": "600809", "name": "山西汾酒", "market": "沪"},
        ]

    def baostock_lookup(query: str):
        raise AssertionError("名称搜索不应调用 BaoStock 精确代码查询")

    stocks = search_stocks(
        "茅台",
        akshare_lookup=akshare_lookup,
        baostock_lookup=baostock_lookup,
    )

    assert [stock.code for stock in stocks] == ["600519", "600809"]
    assert stocks[0].name == "贵州茅台"


def test_search_stock_returns_unverified_manual_stock_when_all_providers_fail():
    from app.services.stock_search import search_stock

    def fail_lookup(query: str):
        raise RuntimeError("provider unavailable")

    stock = search_stock(
        "600519",
        manual_name="贵州茅台",
        akshare_lookup=fail_lookup,
        baostock_lookup=fail_lookup,
    )

    assert stock is not None
    assert stock.code == "600519"
    assert stock.name == "贵州茅台"
    assert stock.market == "沪"
    assert stock.status == "待验证"


def test_search_stock_raises_source_unavailable_without_manual_name():
    from app.services.stock_search import StockDataSourceUnavailableError, search_stock

    def fail_lookup(query: str):
        raise RuntimeError("provider unavailable")

    with pytest.raises(StockDataSourceUnavailableError):
        search_stock(
            "600519",
            akshare_lookup=fail_lookup,
            baostock_lookup=fail_lookup,
        )


def test_search_stocks_falls_back_to_baostock_for_code_query_when_akshare_fails():
    from app.services.stock_search import search_stocks

    def akshare_lookup(query: str):
        raise RuntimeError("akshare unavailable")

    def baostock_lookup(query: str):
        assert query == "600519"
        return {
            "code": "600519",
            "name": "贵州茅台",
            "market": "沪",
            "status": "正常",
        }

    stocks = search_stocks(
        "600519",
        akshare_lookup=akshare_lookup,
        baostock_lookup=baostock_lookup,
    )

    assert [stock.code for stock in stocks] == ["600519"]
    assert stocks[0].name == "贵州茅台"


def test_search_stocks_rejects_code_like_invalid_query_without_querying_providers():
    from app.services.stock_search import StockCodeFormatError, search_stocks

    def fail_lookup(query: str):
        raise AssertionError("格式错误时不应调用数据源")

    with pytest.raises(StockCodeFormatError):
        search_stocks(
            "60051A",
            akshare_lookup=fail_lookup,
            baostock_lookup=fail_lookup,
        )


def test_search_stock_treats_default_provider_errors_as_source_unavailable(monkeypatch):
    from app.services.stock_search import search_stock

    class BadAkshareFrame:
        columns = ["unexpected"]

    monkeypatch.setitem(
        sys.modules,
        "akshare",
        SimpleNamespace(stock_info_a_code_name=lambda: BadAkshareFrame()),
    )
    monkeypatch.setitem(
        sys.modules,
        "baostock",
        SimpleNamespace(
            login=lambda: SimpleNamespace(error_code="1"),
            logout=lambda: None,
        ),
    )

    stock = search_stock("600519", manual_name="贵州茅台")

    assert stock is not None
    assert stock.code == "600519"
    assert stock.name == "贵州茅台"
    assert stock.status == "待验证"


def test_search_stock_treats_baostock_query_error_as_source_unavailable(monkeypatch):
    from app.services.stock_search import search_stock

    monkeypatch.setitem(
        sys.modules,
        "akshare",
        SimpleNamespace(stock_info_a_code_name=lambda: (_ for _ in ()).throw(RuntimeError())),
    )
    monkeypatch.setitem(
        sys.modules,
        "baostock",
        SimpleNamespace(
            login=lambda: SimpleNamespace(error_code="0"),
            query_stock_basic=lambda code: SimpleNamespace(error_code="1"),
            logout=lambda: None,
        ),
    )

    stock = search_stock("600519", manual_name="贵州茅台")

    assert stock is not None
    assert stock.code == "600519"
    assert stock.name == "贵州茅台"
    assert stock.status == "待验证"


def test_search_stock_uses_fallback_when_primary_returns_different_code():
    from app.services.stock_search import search_stock

    def akshare_lookup(query: str):
        return {"code": "600000", "name": "浦发银行", "market": "沪"}

    def baostock_lookup(query: str):
        return {"code": "600519", "name": "贵州茅台", "market": "沪"}

    stock = search_stock(
        "600519",
        akshare_lookup=akshare_lookup,
        baostock_lookup=baostock_lookup,
    )

    assert stock is not None
    assert stock.code == "600519"
    assert stock.name == "贵州茅台"


def test_search_stock_treats_malformed_matching_result_as_source_unavailable():
    from app.services.stock_search import search_stock

    def malformed_lookup(query: str):
        return {"code": "600519"}

    stock = search_stock(
        "600519",
        manual_name="贵州茅台",
        akshare_lookup=malformed_lookup,
        baostock_lookup=malformed_lookup,
    )

    assert stock is not None
    assert stock.code == "600519"
    assert stock.name == "贵州茅台"
    assert stock.status == "待验证"


def test_search_stocks_by_name_raises_when_akshare_unavailable():
    from app.services.stock_search import StockDataSourceUnavailableError, search_stocks

    def akshare_lookup(query: str):
        raise RuntimeError("akshare unavailable")

    with pytest.raises(StockDataSourceUnavailableError):
        search_stocks("茅台", akshare_lookup=akshare_lookup)


def test_search_stocks_by_name_raises_when_provider_result_is_malformed():
    from app.services.stock_search import StockDataSourceUnavailableError, search_stocks

    def akshare_lookup(query: str):
        return [{"code": "600519"}]

    with pytest.raises(StockDataSourceUnavailableError):
        search_stocks("茅台", akshare_lookup=akshare_lookup)


def test_search_functions_reject_none_query_without_querying_providers():
    from app.services.stock_search import StockCodeFormatError, search_stock, search_stocks

    def fail_lookup(query: str):
        raise AssertionError("格式错误时不应调用数据源")

    with pytest.raises(StockCodeFormatError):
        search_stock(None, akshare_lookup=fail_lookup, baostock_lookup=fail_lookup)

    with pytest.raises(StockCodeFormatError):
        search_stocks(None, akshare_lookup=fail_lookup, baostock_lookup=fail_lookup)
