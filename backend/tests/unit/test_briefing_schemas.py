from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.app.schemas.briefing import (
    BriefingGenerateRequest,
    BriefingResponse,
    TopMover,
)


class TestTopMover:
    def test_valid_top_mover(self):
        m = TopMover(
            stock_code="600000",
            stock_name="浦发银行",
            move_type="volume_spike",
            value=3.5,
            change_percent=2.1,
            sector="银行",
            insight="成交量突增",
            data_sufficient=True,
        )
        assert m.stock_code == "600000"
        assert m.move_type == "volume_spike"

    def test_invalid_stock_code_length(self):
        with pytest.raises(ValidationError):
            TopMover(
                stock_code="60000",
                stock_name="浦发银行",
                move_type="volume_spike",
                value=1.0,
                change_percent=1.0,
            )

    def test_invalid_move_type(self):
        with pytest.raises(ValidationError):
            TopMover(
                stock_code="600000",
                stock_name="浦发银行",
                move_type="unknown",
                value=1.0,
                change_percent=1.0,
            )


class TestBriefingResponse:
    def test_valid_briefing(self):
        b = BriefingResponse(
            date="2026-06-23",
            market_indices={
                "上证指数": {"current": 3000.0, "change_pct": 1.0},
            },
            top_movers=[
                TopMover(
                    stock_code="600000",
                    stock_name="浦发银行",
                    move_type="volume_spike",
                    value=3.5,
                    change_percent=2.1,
                ),
            ],
            insights=["大盘整体向好"],
            is_degraded=False,
            generated_at=datetime(2026, 6, 23, 8, 50, 0),
        )
        assert b.is_degraded is False
        assert len(b.top_movers) == 1

    def test_degraded_reason_only_when_degraded(self):
        with pytest.raises(ValidationError):
            BriefingResponse(
                date="2026-06-23",
                market_indices={},
                top_movers=[],
                insights=[],
                is_degraded=False,
                degraded_reason="LLM 失败",
            )


class TestBriefingGenerateRequest:
    def test_valid_manual_request(self):
        r = BriefingGenerateRequest(manual=True)
        assert r.manual is True

    def test_default_manual_is_false(self):
        r = BriefingGenerateRequest()
        assert r.manual is False
