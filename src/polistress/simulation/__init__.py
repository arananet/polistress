"""simulation — discrete tick loop driving persona agents via the Anthropic API.

Agents observe events via graph adjacency, decide actions through real LLM
calls, and emit new events into an append-only SQLite log.
"""

from .actions import ACTIONS, Action
from .decider import AnthropicDecider, Decider, Decision
from .engine import SimulationEngine
from .eventlog import Event, EventLog
from .scenario import Scenario, load_scenario

__all__ = [
    "Action",
    "ACTIONS",
    "Decision",
    "Decider",
    "AnthropicDecider",
    "EventLog",
    "Event",
    "SimulationEngine",
    "Scenario",
    "load_scenario",
]
