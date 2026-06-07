import pytest
from pydantic import ValidationError

from backend.app.schemas.dashboard import (
    AlertSummary,
    BriefingData,
    ChannelStatusItem,
    DashboardViewResponse,
    MarketSnapshot,
    PushHistoryItem,
    StockCardData,
)


class TestMarketSnapshot:
    def test_valid_snapshot(self):
        s = MarketSnapshot(
            name="上证指数",
            current_value=3000.5,
            change_percent=1.23,
            change_amount=36.5,
            updated_at="2026-06-05T10:00:00+00:00",
        )
        assert s.name == "上证指数"
        assert s.current_value == 3000.5

    def test_invalid_change_percent_type(self):
        with pytest.raises(ValidationError):
            MarketSnapshot(
                name="上证指数",
                current_value=3000,
                change_percent="invalid",
                change_amount=36,
            )


class TestStockCardData:
    def test_valid_stock_card(self):
        s = StockCardData(
            code="600000",
            name="浦发银行",
            current_price=10.5,
            change_percent=2.5,
            change_amount=0.25,
            group_name="持仓",
            trend=[10.1, 10.2, 10.3, 10.4, 10.5],
        )
        assert s.code == "600000"
        assert len(s.trend) == 5

    def test_invalid_code_length(self):
        with pytest.raises(ValidationError):
            StockCardData(
                code="60000",
                name="短代码",
                current_price=10,
                change_percent=1,
                change_amount=0.1,
            )


class TestBriefingData:
    def test_valid_briefing(self):
        b = BriefingData(
            insights=["大盘整体向好", "科技股领涨"],
            generated_at="2026-06-05T09:30:00+00:00",
        )
        assert len(b.insights) == 2

    def test_empty_insights(self):
        b = BriefingData(insights=[])
        assert b.insights == []


class TestAlertSummary:
    def test_valid_alert(self):
        a = AlertSummary(
            stock_code="600000",
            stock_name="浦发银行",
            condition="价格突破 10.5",
            level="alert",
        )
        assert a.level == "alert"

    def test_invalid_level(self):
        with pytest.raises(ValidationError):
            AlertSummary(
                stock_code="600000",
                stock_name="浦发银行",
                condition="测试",
                level="invalid",
            )


class TestPushHistoryItem:
    def test_valid_push(self):
        p = PushHistoryItem(
            message_type="alert",
            title="浦发银行价格预警",
            sent_at="2026-06-05T10:00:00+00:00",
            channel="lark",
            status="success",
        )
        assert p.channel == "lark"

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            PushHistoryItem(
                message_type="alert",
                title="测试",
                sent_at="2026-06-05T10:00:00+00:00",
                channel="lark",
                status="unknown",
            )


class TestChannelStatusItem:
    def test_valid_channel(self):
        c = ChannelStatusItem(
            name="lark",
            status="active",
            rate_limited=False,
            last_updated="2026-06-05T10:00:00+00:00",
        )
        assert c.name == "lark"
        assert c.status == "active"

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            ChannelStatusItem(
                name="lark",
                status="broken",
            )


class TestDashboardViewResponse:
    def test_valid_dashboard_response(self):
        d = DashboardViewResponse(
            layout_mode="desktop",
            last_refresh="2026-06-05T10:00:00+00:00",
            market_indices=[
                MarketSnapshot(name="上证指数", current_value=3000, change_percent=1, change_amount=30),
            ],
            watchlist=[
                StockCardData(code="600000", name="浦发银行", current_price=10.5, change_percent=1, change_amount=0.1),
            ],
            briefing=BriefingData(insights=["今日简报"]),
            alerts=[],
            push_history=[],
            channel_status=[],
        )
        assert d.layout_mode == "desktop"
        assert len(d.market_indices) == 1

    def test_invalid_layout_mode(self):
        with pytest.raises(ValidationError):
            DashboardViewResponse(
                layout_mode="tablet",
                market_indices=[],
                watchlist=[],
                briefing=BriefingData(insights=[]),
            )
