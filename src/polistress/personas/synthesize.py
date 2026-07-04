"""Deterministically synthesize persona agents from a world graph."""

from __future__ import annotations

import random

from ..worldgraph import WorldGraph
from ..worldgraph.types import EdgeType, NodeType
from .agent import Agent, AgentTraits, Archetype

# Per-archetype trait baselines: (security_maturity, risk_appetite, workload_pressure).
# Synthesis jitters each baseline deterministically per node.
_TRAIT_BASELINES: dict[Archetype, tuple[float, float, float]] = {
    Archetype.EMPLOYEE: (0.45, 0.50, 0.55),
    Archetype.SYSADMIN: (0.75, 0.35, 0.60),
    Archetype.DEVELOPER: (0.55, 0.55, 0.75),
    Archetype.CISO: (0.90, 0.20, 0.65),
    Archetype.AUDITOR: (0.85, 0.15, 0.50),
    Archetype.ATTACKER: (0.80, 0.95, 0.40),
    Archetype.AI_AGENT: (0.40, 0.60, 0.30),
}

_ARCHETYPE_GOALS: dict[Archetype, list[str]] = {
    Archetype.EMPLOYEE: ["get my work done", "avoid friction from controls"],
    Archetype.SYSADMIN: ["keep systems running", "apply approved configurations"],
    Archetype.DEVELOPER: ["ship features on deadline", "use productive tooling"],
    Archetype.CISO: ["reduce organizational risk", "drive policy adoption"],
    Archetype.AUDITOR: ["verify control effectiveness", "document exceptions"],
    Archetype.ATTACKER: ["find and exploit weak controls", "remain undetected"],
    Archetype.AI_AGENT: ["assist my principal efficiently", "complete requested tasks"],
}

_ATTACKER_OBJECTIVES: list[list[str]] = [
    ["data_exfil"],
    ["privilege_escalation"],
    ["data_exfil", "privilege_escalation"],
]


def _jitter(rng: random.Random, base: float, spread: float = 0.12) -> float:
    return max(0.0, min(1.0, base + rng.uniform(-spread, spread)))


def _rng_for(seed: int, key: str) -> random.Random:
    return random.Random(f"{seed}:{key}")


def _resolve_archetype(node_attrs: dict) -> Archetype:
    hint = node_attrs.get("archetype")
    if hint:
        try:
            return Archetype(hint)
        except ValueError:
            pass
    role = (node_attrs.get("role") or "").lower()
    if "ciso" in role or "chief information security" in role:
        return Archetype.CISO
    if "audit" in role:
        return Archetype.AUDITOR
    if "sysadmin" in role or "administrator" in role or "sre" in role:
        return Archetype.SYSADMIN
    if "developer" in role or "engineer" in role:
        return Archetype.DEVELOPER
    return Archetype.EMPLOYEE


def _make_traits(rng: random.Random, archetype: Archetype) -> AgentTraits:
    sm, ra, wp = _TRAIT_BASELINES[archetype]
    return AgentTraits(
        security_maturity=_jitter(rng, sm),
        risk_appetite=_jitter(rng, ra),
        workload_pressure=_jitter(rng, wp),
    )


def synthesize_agents(
    graph: WorldGraph,
    seed: int = 0,
    max_agents: int | None = None,
    n_attackers: int = 3,
) -> list[Agent]:
    """Synthesize persona agents from graph nodes.

    Person and AIAgent nodes become agents; ``n_attackers`` external attacker
    agents are injected. High-influence agents (ciso, auditor) are always kept;
    crowd agents are truncated to ``max_agents`` (attackers are additional).
    Synthesis is deterministic for a fixed ``seed`` and graph.
    """
    high_influence: list[Agent] = []
    crowd: list[Agent] = []

    for node_id in sorted(graph.nodes_of_type(NodeType.PERSON)):
        attrs = graph.node(node_id)
        archetype = _resolve_archetype(attrs)
        rng = _rng_for(seed, node_id)
        agent = Agent(
            id=f"agent:{node_id}",
            archetype=archetype,
            role=attrs.get("role", archetype.value),
            node_id=node_id,
            traits=_make_traits(rng, archetype),
            goals=list(_ARCHETYPE_GOALS[archetype]),
            team=attrs.get("team"),
        )
        (high_influence if agent.is_high_influence else crowd).append(agent)

    for node_id in sorted(graph.nodes_of_type(NodeType.AI_AGENT)):
        attrs = graph.node(node_id)
        rng = _rng_for(seed, node_id)
        principal = attrs.get("principal")
        if principal is None:
            owners = graph.neighbors(node_id, EdgeType.OWNS, direction="in")
            principal = owners[0] if owners else None
        agent = Agent(
            id=f"agent:{node_id}",
            archetype=Archetype.AI_AGENT,
            role=attrs.get("role", "AI copilot"),
            node_id=node_id,
            traits=_make_traits(rng, Archetype.AI_AGENT),
            goals=list(_ARCHETYPE_GOALS[Archetype.AI_AGENT]),
            principal=principal,
            team=attrs.get("team"),
        )
        crowd.append(agent)

    if max_agents is not None and len(crowd) > max_agents:
        crowd = crowd[:max_agents]

    attackers: list[Agent] = []
    for i in range(n_attackers):
        rng = _rng_for(seed, f"attacker:{i}")
        attackers.append(
            Agent(
                id=f"agent:attacker:{i}",
                archetype=Archetype.ATTACKER,
                role="external threat actor",
                node_id=f"attacker:{i}",
                traits=_make_traits(rng, Archetype.ATTACKER),
                goals=list(_ARCHETYPE_GOALS[Archetype.ATTACKER]),
                objectives=list(_ATTACKER_OBJECTIVES[i % len(_ATTACKER_OBJECTIVES)]),
            )
        )

    return high_influence + crowd + attackers
