"""Derive grounded signals from the event log.

Signals are deterministic aggregations of real events — each carries the actual
event ids that produced it, so downstream findings can cite them. This keeps LLM
output grounded: the model writes narrative around evidence it did not invent.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from ..simulation.actions import Action
from ..simulation.eventlog import EventLog
from ..worldgraph import WorldGraph
from ..worldgraph.types import NodeType

# Actions that indicate friction with, or circumvention of, the injected policy.
_FRICTION_ACTIONS = {
    Action.WORKAROUND.value,
    Action.REQUEST_EXCEPTION.value,
    Action.EXPLOIT_ATTEMPT.value,
    Action.REPORT_CONCERN.value,
    Action.ESCALATE.value,
    Action.IGNORE.value,
}


@dataclass
class Signal:
    """A grounded aggregation of events sharing an action (and optional target)."""

    kind: str
    description: str
    action: str
    event_ids: list[int] = field(default_factory=list)
    affected_targets: list[str] = field(default_factory=list)
    agent_ids: list[str] = field(default_factory=list)
    count: int = 0


def derive_signals(log: EventLog, graph: WorldGraph) -> list[Signal]:
    """Return signals ordered by how strongly they indicate policy stress."""
    events = log.all()
    by_action: dict[str, list] = defaultdict(list)
    for ev in events:
        if ev.action in _FRICTION_ACTIONS:
            by_action[ev.action].append(ev)

    signals: list[Signal] = []
    for action, evs in by_action.items():
        targets = sorted({e.target for e in evs if e.target})
        agents = sorted({e.agent_id for e in evs})
        signals.append(
            Signal(
                kind=f"{action}_cluster",
                description=(
                    f"{len(evs)} '{action}' events across {len(agents)} agents"
                    + (f" touching {len(targets)} targets" if targets else "")
                ),
                action=action,
                event_ids=[e.event_id for e in evs],
                affected_targets=targets,
                agent_ids=agents,
                count=len(evs),
            )
        )

    # Shadow-AI signal: workarounds/ignores by AI copilots or developers around
    # the AI policy are the canonical "shadow AI" emergence pattern. Archetype is
    # resolved through the graph (agent id "agent:<node_id>" -> node).
    def _is_shadow_actor(agent_id: str) -> bool:
        node_id = agent_id.removeprefix("agent:")
        if not graph.has_node(node_id):
            return False
        node = graph.node(node_id)
        if node.get("type") == NodeType.AI_AGENT.value:
            return True
        return node.get("archetype") == "developer"

    shadow_events = [
        e
        for e in events
        if e.action in (Action.WORKAROUND.value, Action.IGNORE.value)
        and _is_shadow_actor(e.agent_id)
    ]
    if shadow_events:
        signals.append(
            Signal(
                kind="shadow_ai",
                description=(
                    f"{len(shadow_events)} workaround/ignore events by AI copilots or "
                    "developers — potential shadow-AI adoption"
                ),
                action="workaround",
                event_ids=[e.event_id for e in shadow_events],
                affected_targets=sorted({e.target for e in shadow_events if e.target}),
                agent_ids=sorted({e.agent_id for e in shadow_events}),
                count=len(shadow_events),
            )
        )

    # Rank: exploit attempts and shadow AI first, then by volume.
    priority = {"exploit_attempt_cluster": 0, "shadow_ai": 1}
    signals.sort(key=lambda s: (priority.get(s.kind, 5), -s.count))
    return signals
