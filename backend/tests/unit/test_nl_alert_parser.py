from unittest.mock import MagicMock

import pytest

from backend.app.schemas.nl_alert import StockCandidate
from backend.app.services.nl_alert_parser import NLAlertParser


def _fake_candidates(query: str) -> list[StockCandidate]:
    data = {
        "600519": StockCandidate(stock_code="600519", stock_name="贵州茅台", sector="白酒", market_cap=20000.0, match_score=1.0),
        "600036": StockCandidate(stock_code="600036", stock_name="招商银行", sector="银行", market_cap=8500.5, match_score=1.0),
        "601166": StockCandidate(stock_code="601166", stock_name="兴业银行", sector="银行", market_cap=3200.0, match_score=1.0),
    }
    if query in data:
        return [data[query]]
    if query == "银行":
        return [data["600036"], data["601166"]]
    if "茅台" in query or query == "price_below":
        return [data["600519"]]
    return []


@pytest.fixture
def parser():
    return NLAlertParser(confidence_threshold=0.7)


def test_rule_hit_returns_resolved_intent(parser):
    intent = parser.parse("茅台跌破 1500 提醒我", stock_resolver=_fake_candidates)
    assert intent.stock_code == "600519"
    assert intent.condition_type == "price_below"
    assert intent.threshold == 1500.0
    assert intent.confidence >= 0.7
    assert not intent.ambiguity


def test_ambiguous_name_returns_candidates(parser):
    intent = parser.parse("银行跌破 10 元提醒我", stock_resolver=_fake_candidates)
    assert intent.ambiguity is True
    assert len(intent.candidates) >= 2
    assert intent.stock_code is None


def test_selected_stock_code_resolves_ambiguity(parser):
    intent = parser.parse(
        "银行跌破 10 元提醒我",
        selected_stock_code="601166",
        stock_resolver=_fake_candidates,
    )
    assert intent.stock_code == "601166"
    assert intent.condition_type == "price_below"
    assert not intent.ambiguity


def test_llm_fallback_used_when_rule_low_confidence(parser):
    llm_client = MagicMock()
    llm_client.generate.return_value = MagicMock(
        is_degraded=False,
        data={
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "condition_type": "price_below",
            "threshold": 1500.0,
            "confidence": 0.95,
            "unsupported_condition": None,
            "invalid": False,
        },
    )
    intent = parser.parse(
        "帮我盯着点茅台，价格要是掉到1500",
        llm_client=llm_client,
        stock_resolver=_fake_candidates,
    )
    assert intent.stock_code == "600519"
    assert intent.condition_type == "price_below"
    llm_client.generate.assert_called_once()


def test_llm_degradation_returns_low_confidence(parser):
    llm_client = MagicMock()
    llm_client.generate.return_value = MagicMock(is_degraded=True, error_reason="timeout")
    intent = parser.parse(
        "帮我盯着点茅台",
        llm_client=llm_client,
        stock_resolver=_fake_candidates,
    )
    assert intent.confidence < 0.7
    assert intent.condition_type is None


def test_unsupported_condition_skips_llm(parser):
    llm_client = MagicMock()
    intent = parser.parse(
        "茅台成交量突破 10 万手提醒我",
        llm_client=llm_client,
        stock_resolver=_fake_candidates,
    )
    assert intent.unsupported_condition == "成交量"
    llm_client.generate.assert_not_called()
