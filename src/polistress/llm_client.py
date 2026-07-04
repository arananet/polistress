"""Anthropic async client construction with flexible credential resolution.

Runtime code makes real Anthropic API calls. Two credential modes are supported,
resolved from the environment (never hard-coded):

* ``ANTHROPIC_API_KEY`` — sent as the ``x-api-key`` header (standard API keys).
* ``ANTHROPIC_AUTH_TOKEN`` — an OAuth access token (``sk-ant-oat…``) sent as
  ``Authorization: Bearer`` together with the required ``oauth-2025-04-20`` beta
  header.

``ANTHROPIC_API_KEY`` takes precedence when both are set.
"""

from __future__ import annotations

import asyncio
import os
import random
from typing import Any

_OAUTH_BETA = "oauth-2025-04-20"


async def backoff_sleep(exc: Exception, attempt: int, cap: float = 60.0) -> None:
    """Sleep before a retry, honoring a ``retry-after`` header when present.

    Falls back to exponential backoff with jitter, capped at ``cap`` seconds.
    """
    retry_after = _retry_after_seconds(exc)
    if retry_after is not None:
        await asyncio.sleep(min(cap, retry_after) + random.uniform(0, 0.5))
        return
    await asyncio.sleep(min(cap, 2.0**attempt) + random.uniform(0, 1))


def _retry_after_seconds(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    value = headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def has_credentials() -> bool:
    """True if either supported credential is present in the environment."""
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def make_async_client(max_retries: int = 2, api_key: str | None = None) -> Any:
    """Construct an ``AsyncAnthropic`` client from available credentials.

    Raises ``RuntimeError`` if no credential is available — runtime code makes
    real calls, so there is no silent fallback.
    """
    from anthropic import AsyncAnthropic

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return AsyncAnthropic(api_key=key, max_retries=max_retries)

    token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if token:
        return AsyncAnthropic(
            auth_token=token,
            max_retries=max_retries,
            default_headers={"anthropic-beta": _OAUTH_BETA},
        )

    raise RuntimeError(
        "No Anthropic credentials found. Set ANTHROPIC_API_KEY (standard key) or "
        "ANTHROPIC_AUTH_TOKEN (OAuth token); the engine makes real LLM calls."
    )
