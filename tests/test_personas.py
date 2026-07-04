"""Tests for persona synthesis and recency-weighted memory."""

from __future__ import annotations

from pathlib import Path

import pytest

from polistress.personas import AgentMemory, synthesize_agents
from polistress.personas.agent import AgentTraits, Archetype
from polistress.worldgraph import WorldGraph


def test_synthesis_traits_in_range_and_deterministic(small_graph: WorldGraph) -> None:
    a1 = synthesize_agents(small_graph, seed=7, n_attackers=2)
    a2 = synthesize_agents(small_graph, seed=7, n_attackers=2)
    assert [a.id for a in a1] == [a.id for a in a2]
    for agent in a1:
        t = agent.traits
        for value in (t.security_maturity, t.risk_appetite, t.workload_pressure):
            assert 0.0 <= value <= 1.0


def test_archetype_assignment_and_attacker_objectives(small_graph: WorldGraph) -> None:
    agents = synthesize_agents(small_graph, seed=1, n_attackers=3)
    by_arch = {a.archetype for a in agents}
    assert Archetype.CISO in by_arch
    assert Archetype.AUDITOR in by_arch
    assert Archetype.DEVELOPER in by_arch
    assert Archetype.AI_AGENT in by_arch
    attackers = [a for a in agents if a.archetype == Archetype.ATTACKER]
    assert len(attackers) == 3
    assert all(a.objectives for a in attackers)
    assert all(a.is_high_influence for a in attackers)


def test_ai_agent_principal_resolved(small_graph: WorldGraph) -> None:
    agents = synthesize_agents(small_graph, seed=1, n_attackers=0)
    ai = next(a for a in agents if a.archetype == Archetype.AI_AGENT)
    # principal resolved via inbound owns edge (person:dev owns ai:001)
    assert ai.principal == "person:dev"


def test_high_influence_always_kept_under_cap(small_graph: WorldGraph) -> None:
    # max_agents=0 truncates crowd, but ciso/auditor are high-influence and kept.
    agents = synthesize_agents(small_graph, seed=1, max_agents=0, n_attackers=0)
    archs = {a.archetype for a in agents}
    assert Archetype.CISO in archs
    assert Archetype.AUDITOR in archs
    assert Archetype.DEVELOPER not in archs  # crowd truncated


def test_trait_bounds_validation() -> None:
    with pytest.raises(ValueError):
        AgentTraits(security_maturity=1.5, risk_appetite=0.5, workload_pressure=0.5)


def test_memory_recency_weighting(tmp_path: Path) -> None:
    mem = AgentMemory(tmp_path / "mem.db", decay=0.5)
    mem.observe("agent:x", tick=0, event_id=1, note="old", salience=1.0)
    mem.observe("agent:x", tick=9, event_id=2, note="recent", salience=1.0)
    recalled = mem.recall("agent:x", current_tick=10, top_k=2)
    # recent memory outranks old despite equal salience
    assert recalled[0].note == "recent"
    assert recalled[0].weight > recalled[1].weight
    assert mem.count("agent:x") == 2
    mem.close()


def test_memory_persists_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "mem.db"
    m1 = AgentMemory(db)
    m1.observe("agent:y", tick=1, event_id=5, note="persisted")
    m1.close()
    m2 = AgentMemory(db)
    assert m2.count("agent:y") == 1
    assert m2.recall("agent:y", current_tick=1)[0].note == "persisted"
    m2.close()
