"""Tests for the AI governance LLM gateway (TC-AIG-013)."""
import httpx

from app.core.llm_gateway import LLMGateway


def test_mock_mode_returns_stable_traceable_response():
    gateway = LLMGateway(mode="mock")

    result = gateway.complete("Check material naming.", trace_id="trace-mock-001")

    assert result == {
        "content": "Mock LLM suggestion: requires human review.",
        "model": "mock-governance-v1",
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "trace_id": "trace-mock-001",
        "degraded": False,
    }


def test_deepseek_mode_returns_provider_content_and_usage(monkeypatch):
    def fake_post(url, *, headers, json, timeout):
        assert url == "https://api.deepseek.com/chat/completions"
        assert headers["Authorization"] == "Bearer test-key"
        assert json["model"] == "deepseek-chat"
        assert timeout == 15.0
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "model": "deepseek-chat",
                "choices": [{"message": {"content": "Review required."}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            },
        )

    monkeypatch.setattr("app.core.llm_gateway.httpx.post", fake_post)
    gateway = LLMGateway(mode="deepseek", api_key="test-key")

    result = gateway.complete("Check material naming.", trace_id="trace-deepseek-001")

    assert result["content"] == "Review required."
    assert result["model"] == "deepseek-chat"
    assert result["usage"]["total_tokens"] == 8
    assert result["trace_id"] == "trace-deepseek-001"
    assert result["degraded"] is False


def test_deepseek_failures_open_circuit_and_fall_back_to_mock(monkeypatch):
    request_count = 0

    def failing_post(*args, **kwargs):
        nonlocal request_count
        request_count += 1
        raise httpx.TimeoutException("provider timeout")

    monkeypatch.setattr("app.core.llm_gateway.httpx.post", failing_post)
    gateway = LLMGateway(mode="deepseek", api_key="test-key")

    first_result = gateway.complete("Check material naming.", trace_id="trace-failure-001")
    second_result = gateway.complete("Check material naming.", trace_id="trace-failure-002")

    assert request_count == 2
    assert first_result["degraded"] is True
    assert second_result["degraded"] is True
    assert second_result["model"] == "mock-governance-v1"
    assert second_result["trace_id"] == "trace-failure-002"


def test_deepseek_usage_logs_warning_after_reaching_token_limit(monkeypatch, caplog):
    def fake_post(*args, **kwargs):
        return httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
            json={
                "choices": [{"message": {"content": "Review required."}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
            },
        )

    monkeypatch.setattr("app.core.llm_gateway.httpx.post", fake_post)
    gateway = LLMGateway(mode="deepseek", api_key="test-key", token_limit=5)

    gateway.complete("Check material naming.", trace_id="trace-token-001")

    assert "LLM token limit reached trace_id=trace-token-001" in caplog.text