"""Agent decision-making via real Anthropic API calls.

High-influence agents (ciso, auditor, attacker) use ``claude-sonnet-4-6``; crowd
agents use ``claude-haiku-4-5-20251001``. Calls are made with ``AsyncAnthropic``,
concurrency is capped with a semaphore, and transient failures are retried with
exponential backoff on top of the SDK's own retries.

``Decider`` is a Protocol so tests can inject a deterministic fake — runtime code
always uses :class:`AnthropicDecider`, which makes real API calls.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..llm_client import backoff_sleep
from .actions import Action

MODEL_HIGH_INFLUENCE = "claude-sonnet-4-6"
MODEL_CROWD = "claude-haiku-4-5-20251001"


@dataclass
class DecisionContext:
    """Everything an agent sees when deciding its action this tick."""

    tick: int
    policy_title: str
    policy_body: str
    observations: list[str] = field(default_factory=list)
    memories: list[str] = field(default_factory=list)
    reachable_targets: list[str] = field(default_factory=list)


@dataclass
class Decision:
    """The action an agent chose, with a target and a rationale."""

    action: Action
    target: str | None
    rationale: str


@runtime_checkable
class Decider(Protocol):
    """Turns an agent + context into a :class:`Decision`."""

    async def decide(self, agent: AgentLike, context: DecisionContext) -> Decision: ...


class AgentLike(Protocol):
    id: str
    role: str
    archetype: object
    goals: list[str]
    objectives: list[str]

    @property
    def is_high_influence(self) -> bool: ...


def _system_prompt(agent: AgentLike) -> str:
    traits = getattr(agent, "traits", None)
    trait_line = ""
    if traits is not None:
        trait_line = (
            f"Your security maturity is {traits.security_maturity:.2f}, "
            f"risk appetite {traits.risk_appetite:.2f}, "
            f"workload pressure {traits.workload_pressure:.2f} (each 0..1)."
        )
    goals = "; ".join(agent.goals) if agent.goals else "act reasonably"
    objectives = ""
    if getattr(agent, "objectives", None):
        objectives = (
            " As an adversary, your objectives are: "
            + ", ".join(agent.objectives)
            + "."
        )
    return (
        f"You are role-playing a {agent.archetype.value if hasattr(agent.archetype, 'value') else agent.archetype} "
        f"in a GRC policy simulation. Your role is: {agent.role}. "
        f"Your goals: {goals}.{objectives} {trait_line} "
        "Given the newly injected policy and what you observe this tick, choose "
        "exactly one action. Respond with ONLY a JSON object of the form "
        '{"action": "<one of comply|workaround|request_exception|escalate|'
        'exploit_attempt|report_concern|ignore>", "target": "<id or null>", '
        '"rationale": "<one sentence>"}. No prose outside the JSON.'
    )


def _user_prompt(context: DecisionContext) -> str:
    obs = "\n".join(f"- {o}" for o in context.observations) or "- (nothing new)"
    mem = "\n".join(f"- {m}" for m in context.memories) or "- (no prior memories)"
    targets = ", ".join(context.reachable_targets) or "(none)"
    return (
        f"Tick {context.tick}.\n"
        f"Injected policy: {context.policy_title}\n{context.policy_body}\n\n"
        f"What you observe this tick:\n{obs}\n\n"
        f"Your recent memories (most salient first):\n{mem}\n\n"
        f"Targets you can reach (controls/assets/people): {targets}\n\n"
        "Choose your single action now as JSON."
    )


def _parse_decision(text: str, fallback_target: str | None) -> Decision:
    """Parse the model's JSON reply, defaulting to IGNORE on malformed output."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return Decision(Action.IGNORE, fallback_target, "unparseable model reply")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return Decision(Action.IGNORE, fallback_target, "invalid JSON from model")
    raw_action = str(data.get("action", "")).strip().lower()
    try:
        action = Action(raw_action)
    except ValueError:
        action = Action.IGNORE
    target = data.get("target")
    if target in ("", "null", None):
        target = fallback_target
    rationale = str(data.get("rationale", "")).strip() or "no rationale given"
    return Decision(action, target, rationale)


class AnthropicDecider:
    """Real Anthropic-backed decider with capped concurrency and backoff."""

    def __init__(
        self,
        max_concurrency: int = 8,
        max_retries: int = 4,
        api_key: str | None = None,
    ) -> None:
        from ..llm_client import make_async_client

        self._client = make_async_client(max_retries=2, api_key=api_key)
        self._sem = asyncio.Semaphore(max_concurrency)
        self._max_retries = max_retries

    async def decide(self, agent: AgentLike, context: DecisionContext) -> Decision:
        from anthropic import APIConnectionError, APIStatusError, RateLimitError

        model = MODEL_HIGH_INFLUENCE if agent.is_high_influence else MODEL_CROWD
        fallback_target = context.reachable_targets[0] if context.reachable_targets else None
        system = _system_prompt(agent)
        user = _user_prompt(context)

        async with self._sem:
            last_exc: Exception | None = None
            for attempt in range(self._max_retries):
                try:
                    resp = await self._client.messages.create(
                        model=model,
                        max_tokens=300,
                        system=system,
                        messages=[{"role": "user", "content": user}],
                    )
                    text = "".join(
                        b.text for b in resp.content if getattr(b, "type", None) == "text"
                    )
                    return _parse_decision(text, fallback_target)
                except (RateLimitError, APIConnectionError) as exc:
                    last_exc = exc
                except APIStatusError as exc:
                    if exc.status_code < 500:
                        raise
                    last_exc = exc
                await backoff_sleep(last_exc, attempt)
            raise RuntimeError(
                f"decision failed after {self._max_retries} retries"
            ) from last_exc
