"""personas — synthesize persona agents from world-graph nodes.

Each agent carries role, security_maturity, risk_appetite, workload_pressure,
goals, and a recency-weighted memory persisted to SQLite.
"""

from .agent import Agent, AgentTraits, Archetype
from .memory import AgentMemory, MemoryEntry
from .synthesize import synthesize_agents

__all__ = [
    "Agent",
    "AgentTraits",
    "Archetype",
    "AgentMemory",
    "MemoryEntry",
    "synthesize_agents",
]
