"""Scenario definitions — the policy change injected at tick 0."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Scenario:
    """A policy-injection scenario.

    ``policy_node_id`` optionally links the injected policy to a node already in
    the ingested graph so observers can be found via adjacency. If it is not in
    the graph, the whole agent population is treated as potentially affected.
    """

    name: str
    policy_title: str
    policy_body: str
    policy_node_id: str | None = None
    domain: str = "ai_governance"
    ticks: int = 30
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Scenario:
        try:
            return cls(
                name=data["name"],
                policy_title=data["policy_title"],
                policy_body=data["policy_body"],
                policy_node_id=data.get("policy_node_id"),
                domain=data.get("domain", "ai_governance"),
                ticks=int(data.get("ticks", 30)),
                metadata=data.get("metadata", {}) or {},
            )
        except KeyError as exc:  # pragma: no cover - defensive
            raise ValueError(f"scenario missing required field: {exc}") from exc


def load_scenario(path: str | Path) -> Scenario:
    """Load a scenario from a YAML (or JSON, since YAML is a superset) file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"scenario file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: scenario must be a mapping")
    return Scenario.from_dict(data)
