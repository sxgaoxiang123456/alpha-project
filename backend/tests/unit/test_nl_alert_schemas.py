import pytest
from pydantic import ValidationError

from backend.app.schemas.nl_alert import (
    AlertRuleSummary,
    NaturalLanguageAlertRequest,
    NaturalLanguageAlertResponse,
    StockCandidate,
)


def test_request_requires_query():
    with pytest.raises(ValidationError):
        NaturalLanguageAlertRequest(query="")


def test_request_query_max_length():
    with pytest.raises(ValidationError):
        NaturalLanguageAlertRequest(query="x" * 201)


def test_request_selected_stock_code_optional():
    req = NaturalLanguageAlertRequest(query="茅台跌破 1500")
    assert req.selected_stock_code is None

    req2 = NaturalLanguageAlertRequest(query="银行跌破 10", selected_stock_code="600036")
    assert req2.selected_stock_code == "600036"


def test_stock_candidate_sort_key():
    a = StockCandidate(stock_code="600036", stock_name="招商银行", match_score=0.9, market_cap=1000.0)
    b = StockCandidate(stock_code="601166", stock_name="兴业银行", match_score=0.8, market_cap=2000.0)
    # Higher match_score should come first when sorting ascending by sort_key.
    assert a.sort_key < b.sort_key

    c = StockCandidate(stock_code="600000", stock_name="浦发银行", match_score=0.9, market_cap=500.0)
    # Same match_score: higher market_cap should come first.
    assert a.sort_key < c.sort_key


def test_response_success_structure():
    rule = AlertRuleSummary(stock_code="600519", stock_name="贵州茅台", condition_type="price_below", threshold=1500.0)
    resp = NaturalLanguageAlertResponse(success=True, message="预警已创建", rule=rule)
    assert resp.success is True
    assert resp.rule.threshold == 1500.0
    assert resp.candidates is None


def test_response_ambiguous_structure():
    candidates = [
        StockCandidate(stock_code="600036", stock_name="招商银行", sector="银行", market_cap=8500.5, match_score=0.92),
    ]
    resp = NaturalLanguageAlertResponse(success=False, message="请选择", candidates=candidates)
    assert resp.candidates[0].match_score == 0.92
    assert resp.rule is None
