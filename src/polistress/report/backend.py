"""LLM backend for the report agent.

``ReportBackend`` is a Protocol so tests can inject a deterministic fake. The
runtime implementation, :class:`AnthropicReportBackend`, makes real API calls.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..llm_client import backoff_sleep

REPORT_MODEL = "claude-sonnet-4-6"


@runtime_checkable
class ReportBackend(Protocol):
    """Turns a (system, user) prompt into a completion string."""

    async def complete(self, system: str, user: str, max_tokens: int = 2000) -> str: ...


class AnthropicReportBackend:
    """Real Anthropic-backed completion for report generation and Q&A."""

    def __init__(self, max_retries: int = 4, api_key: str | None = None) -> None:
        from ..llm_client import make_async_client

        self._client = make_async_client(max_retries=2, api_key=api_key)
        self._max_retries = max_retries

    async def complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        from anthropic import APIConnectionError, APIStatusError, RateLimitError

        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = await self._client.messages.create(
                    model=REPORT_MODEL,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                return "".join(
                    b.text for b in resp.content if getattr(b, "type", None) == "text"
                )
            except (RateLimitError, APIConnectionError) as exc:
                last_exc = exc
            except APIStatusError as exc:
                if exc.status_code < 500:
                    raise
                last_exc = exc
            await backoff_sleep(last_exc, attempt)
        raise RuntimeError(
            f"report completion failed after {self._max_retries} retries"
        ) from last_exc
