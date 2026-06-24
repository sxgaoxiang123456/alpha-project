"""BriefingLLMClient HTTP 边界故障注入测试。

使用 httpx.MockTransport 在真实 HTTP 客户端层注入故障，
验证 BriefingLLMClient 的超时、重试、降级行为。
"""

import json
from contextlib import contextmanager
from http import HTTPStatus
from unittest import mock

import httpx
import pytest

from backend.app.services.briefing_llm_client import BriefingLLMClient


class _JsonTransport(httpx.MockTransport):
    """返回 JSON 响应的 transport。"""

    def __init__(self, payload: dict, status_code: int = HTTPStatus.OK):
        self.payload = payload
        self.status_code = status_code

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=self.status_code,
            json=self.payload,
        )


class _TextTransport(httpx.MockTransport):
    """返回纯文本响应的 transport。"""

    def __init__(self, text: str, status_code: int = HTTPStatus.OK):
        self.text = text
        self.status_code = status_code

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=self.status_code,
            text=self.text,
        )


class _TimeoutTransport(httpx.MockTransport):
    """每次请求都抛出超时异常。"""

    def __init__(self):
        super().__init__(self.handle_request)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Request timed out")


class _SequenceTransport(httpx.MockTransport):
    """按序列返回不同响应。"""

    def __init__(self, responses: list):
        super().__init__(self.handle_request)
        self.responses = responses
        self.call_count = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self.responses[self.call_count]
        self.call_count += 1
        if isinstance(response, Exception):
            raise response
        return response


@contextmanager
def _client(transport, *, retry_attempts: int = 2):
    """构造 BriefingLLMClient，每次调用 httpx.Client 都返回新的带 transport 实例。"""

    real_client_class = httpx.Client

    def _factory(*args, **kwargs):
        return real_client_class(transport=transport)

    with mock.patch(
        "backend.app.services.briefing_llm_client.httpx.Client",
        side_effect=_factory,
    ):
        client = BriefingLLMClient(
            api_key="test-key",
            base_url="https://api.deepseek.com",
            timeout_seconds=1,
            retry_attempts=retry_attempts,
            retry_interval_seconds=0,
        )
        yield client


def _valid_payload(content: dict) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(content),
                }
            }
        ]
    }


class TestBriefingLLMClientHTTPFaults:
    def test_http_500_then_200_retries_and_succeeds(self):
        transport = _SequenceTransport(
            [
                httpx.Response(HTTPStatus.INTERNAL_SERVER_ERROR, text="boom"),
                httpx.Response(HTTPStatus.OK, json=_valid_payload({"insights": ["ok"]})),
            ]
        )
        with _client(transport, retry_attempts=2) as client:
            result = client.generate("prompt")

        assert result.is_degraded is False
        assert result.data == {"insights": ["ok"]}
        assert transport.call_count == 2

    def test_http_500_all_attempts_returns_degraded(self):
        transport = _JsonTransport(
            {"error": "boom"},
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        )
        with _client(transport, retry_attempts=3) as client:
            result = client.generate("prompt")

        assert result.is_degraded is True
        assert result.data is None
        assert "500" in result.error_reason or "HTTP 错误" in result.error_reason

    def test_http_503_then_timeout_returns_degraded(self):
        transport = _SequenceTransport(
            [
                httpx.Response(HTTPStatus.SERVICE_UNAVAILABLE, text="overloaded"),
                httpx.TimeoutException("timeout"),
            ]
        )
        with _client(transport, retry_attempts=2) as client:
            result = client.generate("prompt")

        assert result.is_degraded is True
        assert result.data is None

    def test_http_timeout_returns_degraded(self):
        with _client(_TimeoutTransport(), retry_attempts=2) as client:
            result = client.generate("prompt")

        assert result.is_degraded is True
        assert result.data is None
        assert "超时" in result.error_reason

    def test_non_json_response_returns_degraded(self):
        transport = _TextTransport("this is not json")
        with _client(transport) as client:
            result = client.generate("prompt")

        assert result.is_degraded is True
        assert result.data is None

    def test_empty_content_returns_degraded(self):
        transport = _JsonTransport(
            {"choices": [{"message": {"content": ""}}]},
        )
        with _client(transport) as client:
            result = client.generate("prompt")

        assert result.is_degraded is True
        assert result.data is None

    def test_malformed_choices_returns_degraded(self):
        transport = _JsonTransport(
            {"choices": "not-a-list"},
        )
        with _client(transport) as client:
            result = client.generate("prompt")

        assert result.is_degraded is True
        assert result.data is None

    def test_missing_api_key_returns_degraded_without_http_call(self):
        client = BriefingLLMClient(api_key="")

        result = client.generate("prompt")

        assert result.is_degraded is True
        assert result.data is None
