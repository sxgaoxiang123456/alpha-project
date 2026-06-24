import json
from unittest import mock

import pytest

from backend.app.services.prompt_loader import PromptLoader


class TestBriefingLLMClient:
    def test_success_returns_parsed_dict(self):
        from backend.app.services.briefing_llm_client import BriefingLLMClient

        fake_response = mock.MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "market_summary": "大盘向好",
                                "sector_hotspots": ["科技"],
                                "risks": [],
                                "insights": ["科技股领涨"],
                                "disclaimer": "仅供参考",
                            }
                        )
                    }
                }
            ]
        }

        with mock.patch("httpx.Client.post", return_value=fake_response) as mock_post:
            client = BriefingLLMClient(api_key="test-key", base_url="https://test.local")
            result = client.generate("prompt text")

        assert result.is_degraded is False
        assert result.data["insights"] == ["科技股领涨"]
        assert mock_post.call_count == 1

    def test_three_failures_returns_degraded(self):
        from backend.app.services.briefing_llm_client import BriefingLLMClient

        fake_response = mock.MagicMock()
        fake_response.status_code = 500
        fake_response.text = "Internal Server Error"

        with mock.patch("httpx.Client.post", return_value=fake_response) as mock_post:
            client = BriefingLLMClient(
                api_key="test-key",
                base_url="https://test.local",
                retry_attempts=3,
                retry_interval_seconds=0,
                timeout_seconds=5,
            )
            result = client.generate("prompt text")

        assert result.is_degraded is True
        assert result.data is None
        assert result.error_reason is not None
        assert mock_post.call_count == 3

    def test_invalid_json_returns_degraded(self):
        from backend.app.services.briefing_llm_client import BriefingLLMClient

        fake_response = mock.MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {
            "choices": [{"message": {"content": "not valid json"}}]
        }

        with mock.patch("httpx.Client.post", return_value=fake_response):
            client = BriefingLLMClient(
                api_key="test-key",
                base_url="https://test.local",
                retry_interval_seconds=0,
            )
            result = client.generate("prompt text")

        assert result.is_degraded is True

    def test_missing_api_key_returns_degraded(self):
        from backend.app.services.briefing_llm_client import BriefingLLMClient

        client = BriefingLLMClient(api_key="")
        result = client.generate("prompt text")

        assert result.is_degraded is True
        assert "api_key" in result.error_reason.lower() or "key" in result.error_reason.lower()

    def test_request_exception_returns_degraded(self):
        from backend.app.services.briefing_llm_client import BriefingLLMClient

        with mock.patch("httpx.Client.post", side_effect=Exception("connection error")):
            client = BriefingLLMClient(
                api_key="test-key",
                base_url="https://test.local",
                retry_attempts=2,
                retry_interval_seconds=0,
            )
            result = client.generate("prompt text")

        assert result.is_degraded is True
        assert "connection error" in result.error_reason or "LLM 调用异常" in result.error_reason
