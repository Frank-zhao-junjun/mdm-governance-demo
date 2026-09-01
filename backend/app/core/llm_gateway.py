"""LLM provider boundary for AI-enhanced governance suggestions."""
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
_MOCK_MODEL = "mock-governance-v1"
_MOCK_CONTENT = "Mock LLM suggestion: requires human review."


class LLMGateway:
    """Returns advisory LLM output and degrades to a deterministic mock safely."""

    def __init__(
        self,
        mode: str = "mock",
        api_key: str | None = None,
        token_limit: int = 10_000,
        cooldown_seconds: float = 15.0,
    ):
        if mode not in {"mock", "deepseek"}:
            raise ValueError("LLM mode must be 'mock' or 'deepseek'.")
        if token_limit < 1:
            raise ValueError("token_limit must be positive.")

        self.mode = mode
        self.api_key = api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY")
        self.token_limit = token_limit
        self.cooldown_seconds = cooldown_seconds
        self._failures = 0
        self._open_until = 0.0
        self._total_tokens = 0

    def complete(self, prompt: str, trace_id: str) -> dict[str, Any]:
        """Return a traceable suggestion; provider errors never stop governance checks."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string.")
        if not isinstance(trace_id, str) or not trace_id.strip():
            raise ValueError("trace_id must be a non-empty string.")

        if self.mode == "mock":
            return self._mock_response(trace_id, degraded=False)

        if self._circuit_is_open():
            logger.warning("LLM circuit open; using mock response trace_id=%s", trace_id)
            return self._mock_response(trace_id, degraded=True)

        for _ in range(2):
            try:
                result = self._call_deepseek(prompt, trace_id)
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
                self._failures += 1
                logger.warning(
                    "LLM provider request failed trace_id=%s failure_count=%s error_type=%s",
                    trace_id,
                    self._failures,
                    type(error).__name__,
                )
                if self._failures >= 2:
                    self._open_until = time.monotonic() + self.cooldown_seconds
                    break
            else:
                self._failures = 0
                self._record_usage(result["usage"], trace_id)
                return result

        return self._mock_response(trace_id, degraded=True)

    def _circuit_is_open(self) -> bool:
        if time.monotonic() < self._open_until:
            return True
        if self._open_until:
            self._open_until = 0.0
            self._failures = 0
        return False

    def _call_deepseek(self, prompt: str, trace_id: str) -> dict[str, Any]:
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for deepseek mode.")

        response = httpx.post(
            _DEEPSEEK_ENDPOINT,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=15.0,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage", {})
        normalized_usage = {
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
            "total_tokens": int(usage.get("total_tokens", 0)),
        }
        if not isinstance(content, str) or not content.strip():
            raise ValueError("LLM provider returned empty content.")

        return {
            "content": content,
            "model": payload.get("model", "deepseek-chat"),
            "usage": normalized_usage,
            "trace_id": trace_id,
            "degraded": False,
        }

    def _mock_response(self, trace_id: str, *, degraded: bool) -> dict[str, Any]:
        return {
            "content": _MOCK_CONTENT,
            "model": _MOCK_MODEL,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "trace_id": trace_id,
            "degraded": degraded,
        }

    def _record_usage(self, usage: dict[str, int], trace_id: str) -> None:
        self._total_tokens += usage["total_tokens"]
        if self._total_tokens >= self.token_limit:
            logger.warning(
                "LLM token limit reached trace_id=%s total_tokens=%s token_limit=%s",
                trace_id,
                self._total_tokens,
                self.token_limit,
            )
