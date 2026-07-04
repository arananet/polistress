#!/usr/bin/env python3
"""Produce the example findings register in ``examples/``.

This drives the FULL polistress pipeline — ingest → synthesize → simulate →
report — over the synthetic organization, and writes the resulting findings
register (JSON + CSV) plus a run summary.

Provenance note: a real ``polistress simulate`` run makes live Anthropic API
calls (``ANTHROPIC_API_KEY`` required). This example script substitutes a
deterministic, trait-driven *offline decider* and the report agent's
deterministic (non-LLM) findings path so the artifact is fully reproducible in
CI and in environments without an API key. The event log, signal extraction,
framework mappings, and event-id citations are produced by the real pipeline
code — only the per-agent decision and findings-narration LLM calls are stood
in for. The offline decider lives here, not in ``src/``: runtime code never
mocks the LLM.

Run: ``python examples/generate_example.py``
"""

from __future__ import annotations

import asyncio
import random
from pathlib import Path

from polistress.personas import synthesize_agents
from polistress.personas.agent import Archetype
from polistress.personas.memory import AgentMemory
from polistress.report import ReportAgent
from polistress.report.findings import write_csv, write_json
from polistress.simulation import EventLog, SimulationEngine, load_scenario
from polistress.simulation.actions import Action
from polistress.simulation.decider import Decision, DecisionContext
from polistress.worldgraph import ingest_directory

ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "data" / "synthetic_org"
SCENARIO = ROOT / "scenarios" / "ai_usage_policy.yaml"
OUT = ROOT / "examples"


class OfflineDecider:
    """Deterministic, trait-driven stand-in for the LLM decider (example only)."""

    def __init__(self, seed: int = 0) -> None:
        self._seed = seed

    async def decide(self, agent, ctx: DecisionContext) -> Decision:
        rng = random.Random(f"{self._seed}:{agent.id}:{ctx.tick}")
        target = ctx.reachable_targets[0] if ctx.reachable_targets else None
        maturity = agent.traits.security_maturity
        risk = agent.traits.risk_appetite
        pressure = agent.traits.workload_pressure

        if agent.archetype == Archetype.ATTACKER:
            return Decision(
                Action.EXPLOIT_ATTEMPT, target, "probing controls for a data-exfil path"
            )
        if agent.archetype == Archetype.AUDITOR:
            return Decision(
                Action.REPORT_CONCERN, target, "flagged unreviewed AI copilots"
            )
        if agent.archetype == Archetype.CISO:
            return Decision(Action.ESCALATE, target, "driving review-board rollout")
        if agent.archetype == Archetype.AI_AGENT:
            # Copilots keep running until reviewed — canonical shadow-AI pattern.
            if rng.random() < 0.6:
                return Decision(
                    Action.WORKAROUND, target, "kept assisting via unreviewed copilot"
                )
            return Decision(Action.IGNORE, target, "continued default behavior")
        if agent.archetype == Archetype.DEVELOPER:
            score = risk * 0.5 + pressure * 0.5 - maturity * 0.4
            if score > 0.35:
                return Decision(
                    Action.WORKAROUND, target, "used unapproved AI code assistant to hit deadline"
                )
            if rng.random() < 0.25:
                return Decision(
                    Action.REQUEST_EXCEPTION, target, "asked to keep current AI tooling"
                )
            return Decision(Action.COMPLY, target, "switched to an approved tool")
        # employees / sysadmins
        if maturity > 0.7:
            return Decision(Action.COMPLY, target, "adopted approved tooling")
        if risk > 0.65 and rng.random() < 0.4:
            return Decision(Action.WORKAROUND, target, "used a personal AI account")
        return Decision(Action.COMPLY, target, "following the new policy")


async def main() -> None:
    graph = ingest_directory(SEED_DIR)
    scenario = load_scenario(SCENARIO)
    agents = synthesize_agents(graph, seed=0, max_agents=200, n_attackers=3)

    events_db = OUT / "_run" / "events.db"
    memory_db = OUT / "_run" / "memory.db"
    for p in (events_db, memory_db):
        if p.exists():
            p.unlink()

    log = EventLog(events_db)
    memory = AgentMemory(memory_db)
    engine = SimulationEngine(graph, agents, log, memory, OfflineDecider(seed=0))
    ticks = scenario.ticks
    await engine.run(scenario, ticks)

    report = ReportAgent(graph, log, backend=_NullBackend(), domain=scenario.domain)
    findings = await report.build_findings()

    write_json(findings, OUT / "findings.json")
    write_csv(findings, OUT / "findings.csv")

    counts = log.action_counts()
    _write_summary(OUT / "run_summary.md", scenario, agents, ticks, counts, findings)

    log.close()
    memory.close()
    print(
        f"Wrote {len(findings)} findings from {sum(counts.values())} events "
        f"({len(agents)} agents x {ticks} ticks) to examples/."
    )


class _NullBackend:
    """Forces the report agent's deterministic (non-LLM) findings path."""

    async def complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        return ""


def _write_summary(path, scenario, agents, ticks, counts, findings) -> None:
    lines = [
        f"# Example run summary — {scenario.name}",
        "",
        "> Generated by `examples/generate_example.py` over the synthetic org.",
        "> Decisions use a deterministic offline decider (no API key required);",
        "> a real `polistress simulate` run makes live Anthropic API calls.",
        "",
        f"- Agents: **{len(agents)}**",
        f"- Ticks: **{ticks}**",
        f"- Total events: **{sum(counts.values())}**",
        "",
        "## Action distribution",
        "",
        "| action | count |",
        "|---|---:|",
    ]
    for action, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {action} | {n} |")
    lines += ["", "## Findings", "", "| id | severity | title | citations |", "|---|---|---|---:|"]
    for f in findings:
        lines.append(
            f"| {f.id} | {f.severity} | {f.title} | {len(f.root_cause_events)} |"
        )
    lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
