"""Agent archetypes and the synthesized persona dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Archetype(StrEnum):
    """Persona archetypes an agent can take on."""

    EMPLOYEE = "employee"
    SYSADMIN = "sysadmin"
    DEVELOPER = "developer"
    CISO = "ciso"
    AUDITOR = "auditor"
    ATTACKER = "attacker"
    AI_AGENT = "ai_agent"


# Archetypes whose decisions are high-influence and routed to the stronger model.
HIGH_INFLUENCE: frozenset[Archetype] = frozenset(
    {Archetype.CISO, Archetype.AUDITOR, Archetype.ATTACKER}
)


@dataclass
class AgentTraits:
    """Numeric behavioral traits, each in the closed interval [0, 1]."""

    security_maturity: float
    risk_appetite: float
    workload_pressure: float

    def __post_init__(self) -> None:
        for name in ("security_maturity", "risk_appetite", "workload_pressure"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1], got {value}")


@dataclass
class Agent:
    """A persona agent synthesized from a world-graph node."""

    id: str
    archetype: Archetype
    role: str
    node_id: str
    traits: AgentTraits
    goals: list[str] = field(default_factory=list)
    # Attacker-only: objectives such as "data_exfil", "privilege_escalation".
    objectives: list[str] = field(default_factory=list)
    # ai_agent-only: the person id this copilot acts on behalf of.
    principal: str | None = None
    team: str | None = None

    @property
    def is_high_influence(self) -> bool:
        return self.archetype in HIGH_INFLUENCE

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "archetype": self.archetype.value,
            "role": self.role,
            "node_id": self.node_id,
            "team": self.team,
            "traits": {
                "security_maturity": self.traits.security_maturity,
                "risk_appetite": self.traits.risk_appetite,
                "workload_pressure": self.traits.workload_pressure,
            },
            "goals": self.goals,
            "objectives": self.objectives,
            "principal": self.principal,
        }
