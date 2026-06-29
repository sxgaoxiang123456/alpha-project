import difflib

import pytest

from backend.app.services.stock_search import search_stock_candidates


def _fake_lookup(query: str):
    data = [
        {"code": "600036", "name": "招商银行", "sector": "银行", "market_cap": 8500.5},
        {"code": "601166", "name": "兴业银行", "sector": "银行", "market_cap": 3200.0},
        {"code": "600000", "name": "浦发银行", "sector": "银行", "market_cap": 2100.0},
    ]
    if query.isdigit() and len(query) == 6:
        return [item for item in data if item["code"] == query]
    return [item for item in data if query in item["name"]]


def test_search_candidates_by_name_returns_sorted_list():
    candidates = search_stock_candidates("银行", akshare_lookup=_fake_lookup, top_n=10)
    assert len(candidates) == 3
    # All are substring matches, so top candidate is the one with highest market cap.
    assert candidates[0].stock_name == "招商银行"
    assert candidates[0].match_score == pytest.approx(0.9)


def test_search_candidates_exact_name_match():
    candidates = search_stock_candidates("招商银行", akshare_lookup=_fake_lookup)
    assert len(candidates) == 1
    assert candidates[0].match_score == pytest.approx(1.0)


def test_search_candidates_sort_by_market_cap_when_same_score():
    # "银行" matches all with same substring score; sorted by market_cap desc
    candidates = search_stock_candidates("银行", akshare_lookup=_fake_lookup, top_n=10)
    assert candidates[1].market_cap >= candidates[2].market_cap


def test_search_candidates_top_n():
    candidates = search_stock_candidates("银行", akshare_lookup=_fake_lookup, top_n=2)
    assert len(candidates) == 2


def test_search_candidates_by_code_returns_single():
    candidates = search_stock_candidates("600036", akshare_lookup=_fake_lookup)
    assert len(candidates) == 1
    assert candidates[0].stock_code == "600036"


def test_search_candidates_returns_sector():
    candidates = search_stock_candidates("招商银行", akshare_lookup=_fake_lookup)
    assert candidates[0].sector == "银行"
