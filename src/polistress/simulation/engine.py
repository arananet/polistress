"""The discrete-tick simulation loop."""

from __future__ import annotations

import asyncio

from ..personas.agent import Agent, Archetype
from ..personas.memory import AgentMemory
from ..worldgraph import WorldGraph
from ..worldgraph.types import NodeType
from .actions import POLICY_INJECTION, Action
from .decider import Decider, DecisionContext
from .eventlog import EventLog
from .scenario import Scenario

# Salience assigned to remembered observations, by the action observed.
_SALIENCE = {
    POLICY_INJECTION: 2.0,
    Action.ESCALATE.value: 1.6,
    Action.EXPLOIT_ATTEMPT.value: 1.6,
    Action.REPORT_CONCERN.value: 1.4,
    Action.REQUEST_EXCEPTION.value: 1.2,
}
_DEFAULT_SALIENCE = 1.0
_MAX_OBSERVATIONS = 6
_MAX_TARGETS = 6


class SimulationEngine:
    """Runs a policy-injection scenario over discrete ticks."""

    def __init__(
        self,
        graph: WorldGraph,
        agents: list[Agent],
        event_log: EventLog,
        memory: AgentMemory,
        decider: Decider,
    ) -> None:
        self.graph = graph
        self.agents = agents
        self.log = event_log
        self.memory = memory
        self.decider = decider
        self._neighborhood: dict[str, set[str]] = {}
        self._targets: dict[str, list[str]] = {}
        self._controls = sorted(graph.nodes_of_type(NodeType.CONTROL))
        self._precompute()

    def _precompute(self) -> None:
        """Precompute each agent's observable neighborhood and reachable targets."""
        control_set = set(self._controls)
        asset_set = set(self.graph.nodes_of_type(NodeType.ASSET))
        for agent in self.agents:
            if agent.archetype == Archetype.ATTACKER:
                # Attackers probe controls, so their neighborhood/targets are controls.
                self._neighborhood[agent.id] = control_set.copy()
                self._targets[agent.id] = self._controls[:_MAX_TARGETS]
                continue
            hood: set[str] = {agent.node_id}
            if self.graph.has_node(agent.node_id):
                hood.update(self.graph.neighbors(agent.node_id))
                # extend one hop through team membership
                for n in list(hood):
                    if self.graph.has_node(n):
                        hood.update(self.graph.neighbors(n))
            self._neighborhood[agent.id] = hood
            reachable = [
                n for n in sorted(hood) if n in control_set or n in asset_set
            ]
            self._targets[agent.id] = reachable[:_MAX_TARGETS]

    async def run(self, scenario: Scenario, ticks: int) -> None:
        """Inject the policy at tick 0, then step ``ticks`` discrete ticks."""
        self._inject_policy(scenario)
        for tick in range(1, ticks + 1):
            await self._step(scenario, tick)

    def _inject_policy(self, scenario: Scenario) -> None:
        event_id = self.log.append(
            tick=0,
            agent_id="system",
            action=POLICY_INJECTION,
            rationale=scenario.policy_title,
            target=scenario.policy_node_id,
        )
        note = f"Policy injected: {scenario.policy_title}"
        for agent in self.agents:
            self.memory.observe(
                agent.id, 0, event_id, note, salience=_SALIENCE[POLICY_INJECTION]
            )

    async def _step(self, scenario: Scenario, tick: int) -> None:
        prev_events = self.log.by_tick(tick - 1)
        contexts = {
            agent.id: self._build_context(scenario, agent, tick, prev_events)
            for agent in self.agents
        }
        decisions = await asyncio.gather(
            *(self.decider.decide(agent, contexts[agent.id]) for agent in self.agents)
        )
        for agent, decision in zip(self.agents, decisions, strict=True):
            event_id = self.log.append(
                tick=tick,
                agent_id=agent.id,
                action=decision.action.value,
                rationale=decision.rationale,
                target=decision.target,
            )
            salience = _SALIENCE.get(decision.action.value, _DEFAULT_SALIENCE)
            self.memory.observe(
                agent.id,
                tick,
                event_id,
                f"I chose to {decision.action.value} "
                f"(target={decision.target}): {decision.rationale}",
                salience=salience,
            )

    def _build_context(
        self,
        scenario: Scenario,
        agent: Agent,
        tick: int,
        prev_events,
    ) -> DecisionContext:
        hood = self._neighborhood.get(agent.id, set())
        observations: list[str] = []
        for ev in prev_events:
            if ev.agent_id == agent.id:
                continue
            if ev.target in hood or ev.agent_id in hood or ev.agent_id == "system":
                observations.append(
                    f"{ev.agent_id} did {ev.action}"
                    + (f" on {ev.target}" if ev.target else "")
                )
            if len(observations) >= _MAX_OBSERVATIONS:
                break
        memories = [m.note for m in self.memory.recall(agent.id, tick, top_k=5)]
        return DecisionContext(
            tick=tick,
            policy_title=scenario.policy_title,
            policy_body=scenario.policy_body,
            observations=observations,
            memories=memories,
            reachable_targets=self._targets.get(agent.id, []),
        )
