from datetime import datetime

import pytest


class TestPromptLoader:
    def test_loads_briefing_template(self):
        from backend.app.services.prompt_loader import PromptLoader

        loader = PromptLoader()
        prompt = loader.render(
            market_indices={
                "上证指数": {"current": 3000.5, "change_pct": 1.2},
            },
            top_movers=[
                {
                    "stock_code": "600000",
                    "stock_name": "浦发银行",
                    "move_type": "volume_spike",
                    "value": 3.5,
                    "change_percent": 2.1,
                    "sector": "银行",
                    "insight": "成交量突增",
                    "data_sufficient": True,
                },
            ],
            alert_history=["600000 价格突破 10.5"],
            today="2026-06-23",
        )
        assert "上证指数" in prompt
        assert "浦发银行" in prompt
        assert "600000" in prompt
        assert "JSON" in prompt or "json" in prompt

    def test_missing_template_raises_runtime_error(self, tmp_path, monkeypatch):
        from backend.app.services.prompt_loader import PromptLoader

        monkeypatch.setenv("PROMPT_TEMPLATE_DIR", str(tmp_path))
        loader = PromptLoader()
        with pytest.raises(RuntimeError):
            loader.render()
