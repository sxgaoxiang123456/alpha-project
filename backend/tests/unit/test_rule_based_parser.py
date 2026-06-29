import pytest

from backend.app.services.rule_based_parser import RuleBasedParser, ParsedAlertIntent


@pytest.fixture
def parser():
    return RuleBasedParser()


def test_parse_price_below_with_name(parser):
    intent = parser.parse("茅台跌破 1500 提醒我")
    assert intent.stock_name == "茅台"
    assert intent.condition_type == "price_below"
    assert intent.threshold == 1500.0
    assert intent.confidence == 1.0
    assert not intent.invalid


def test_parse_price_above_with_code(parser):
    intent = parser.parse("600519 涨到 1600 提醒我")
    assert intent.stock_code == "600519"
    assert intent.condition_type == "price_above"
    assert intent.threshold == 1600.0
    assert intent.confidence == 1.0


def test_parse_change_pct_below(parser):
    intent = parser.parse("五粮液跌幅超过 3% 提醒我")
    assert intent.stock_name == "五粮液"
    assert intent.condition_type == "change_pct_below"
    assert intent.threshold == -3.0


def test_parse_change_pct_above(parser):
    intent = parser.parse("茅台涨超 5% 提醒我")
    assert intent.stock_name == "茅台"
    assert intent.condition_type == "change_pct_above"
    assert intent.threshold == 5.0


def test_unsupported_volume_condition(parser):
    intent = parser.parse("茅台成交量突破 10 万手提醒我")
    assert intent.unsupported_condition == "成交量"
    assert intent.condition_type is None


def test_multiple_stocks_invalid(parser):
    intent = parser.parse("茅台和五粮液都跌破 1500")
    assert intent.invalid is True


def test_multiple_conditions_invalid(parser):
    intent = parser.parse("茅台跌破 1500 或涨超 5%")
    assert intent.invalid is True


def test_low_confidence_without_condition(parser):
    intent = parser.parse("帮我看着点茅台")
    assert intent.confidence < 0.7
    assert intent.condition_type is None
