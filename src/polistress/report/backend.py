"""LLM backend for the report agent.

``ReportBackend`` is a Protocol so tests can inject a deterministic fake. The
runtime implementation, :class:`AnthropicReportBackend`, makes real API calls.
"""

from __future__ import annotations

import asyncio
import os
import random
from typing import Protocol, runtime_checkable

REPORT_MODEL = "claude-sonnet-4-6"


@runtime_checkable
class ReportBackend(Protocol):
    """Turns a (system, user) prompt into a completion string."""

    async def complete(self, system: str, user: str, max_tokens: int = 2000) -> str: ...


class AnthropicReportBackend:
    """Real Anthropic-backed completion for report generation and Q&A."""

    def __init__(self, max_retries: int = 4, api_key: str | None = None) -> None:
        from anthropic import AsyncAnthropic

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set; the report agent makes real LLM calls"
            )
        self._client = AsyncAnthropic(api_key=key, max_retries=2)
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
            await asyncio.sleep(min(16.0, 2.0**attempt) + random.uniform(0, 1))
        raise RuntimeError(
            f"report completion failed after {self._max_retries} retries"
        ) from last_exc
