"""Tests for the append-only event log and simulation integrity."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from polistress.personas import synthesize_agents
from polistress.personas.memory import AgentMemory
from polistress.simulation import EventLog, SimulationEngine
from polistress.simulation.actions import POLICY_INJECTION, Action
from polistress.simulation.decider import Decision, DecisionContext
from polistress.simulation.scenario import Scenario
from polistress.worldgraph import WorldGraph


def test_append_and_fields(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "e.db")
    eid = log.append(tick=3, agent_id="agent:1", action="comply", rationale="ok", target="control:mfa")
    ev = log.get(eid)
    assert ev is not None
    assert (ev.tick, ev.agent_id, ev.action, ev.target, ev.rationale) == (
        3,
        "agent:1",
        "comply",
        "control:mfa",
        "ok",
    )
    log.close()


def test_event_log_is_append_only(tmp_path: Path) -> None:
    db = tmp_path / "e.db"
    log = EventLog(db)
    eid = log.append(tick=1, agent_id="a", action="comply", rationale="r")
    log.close()

    conn = sqlite3.connect(db)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE events SET action='ignore' WHERE event_id=?", (eid,))
        conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM events WHERE event_id=?", (eid,))
        conn.commit()
    conn.close()


class FakeDecider:
    """Deterministic decider for tests — no LLM calls in the test path."""

    def __init__(self) -> None:
        self.calls = 0

    async def decide(self, agent, context: DecisionContext) -> Decision:
        self.calls += 1
        from polistress.personas.agent import Archetype

        target = context.reachable_targets[0] if context.reachable_targets else None
        if agent.archetype == Archetype.ATTACKER:
            return Decision(Action.EXPLOIT_ATTEMPT, target, "probing controls")
        if agent.archetype == Archetype.DEVELOPER:
            return Decision(Action.WORKAROUND, target, "deadline pressure")
        return Decision(Action.COMPLY, target, "following policy")


async def test_simulation_produces_grounded_log(small_graph: WorldGraph, tmp_path: Path) -> None:
    agents = synthesize_agents(small_graph, seed=1, n_attackers=2)
    log = EventLog(tmp_path / "e.db")
    memory = AgentMemory(tmp_path / "m.db")
    engine = SimulationEngine(small_graph, agents, log, memory, FakeDecider())
    scenario = Scenario(
        name="Test",
        policy_title="Test policy",
        policy_body="Body",
        policy_node_id="policy:aup",
    )
    await engine.run(scenario, ticks=3)

    # tick 0 is a single PolicyInjection event
    t0 = log.by_tick(0)
    assert len(t0) == 1
    assert t0[0].action == POLICY_INJECTION
    assert t0[0].agent_id == "system"

    # every tick 1..3 produced one event per agent
    for tick in (1, 2, 3):
        assert len(log.by_tick(tick)) == len(agents)

    counts = log.action_counts()
    assert counts.get(Action.EXPLOIT_ATTEMPT.value, 0) > 0  # attackers probed
    assert counts.get(Action.COMPLY.value, 0) > 0
    # memory seeded with the injection for every agent
    assert memory.count() > 0
    log.close()
    memory.close()
