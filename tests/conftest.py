"""Shared fixtures: a small synthetic graph and seed directory."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polistress.worldgraph import WorldGraph
from polistress.worldgraph.types import EdgeType, NodeType


def build_small_graph() -> WorldGraph:
    g = WorldGraph()
    g.add_node("team:eng", NodeType.TEAM, name="Engineering")
    g.add_node("person:ciso", NodeType.PERSON, role="CISO", archetype="ciso", team="team:eng")
    g.add_node("person:dev", NodeType.PERSON, role="Developer", archetype="developer", team="team:eng")
    g.add_node("person:aud", NodeType.PERSON, role="Auditor", archetype="auditor", team="team:eng")
    g.add_node("asset:repo", NodeType.ASSET, name="Repo", classification="confidential")
    g.add_node("control:mfa", NodeType.CONTROL, name="MFA enforcement")
    g.add_node("policy:aup", NodeType.POLICY, name="Acceptable Use")
    g.add_node("finding:001", NodeType.FINDING, name="Old finding", severity="high")
    g.add_node("ai:001", NodeType.AI_AGENT, name="Copilot", role="AI copilot")

    g.add_edge("person:dev", "person:ciso", EdgeType.REPORTS_TO)
    g.add_edge("person:aud", "person:ciso", EdgeType.REPORTS_TO)
    g.add_edge("team:eng", "asset:repo", EdgeType.OWNS)
    g.add_edge("person:dev", "asset:repo", EdgeType.OWNS)
    g.add_edge("person:dev", "ai:001", EdgeType.OWNS)
    g.add_edge("asset:repo", "policy:aup", EdgeType.GOVERNED_BY)
    g.add_edge("control:mfa", "asset:repo", EdgeType.MITIGATES)
    g.add_edge("asset:repo", "control:mfa", EdgeType.HAS_EXCEPTION)
    return g


@pytest.fixture
def small_graph() -> WorldGraph:
    return build_small_graph()


@pytest.fixture
def seed_dir(tmp_path: Path) -> Path:
    d = tmp_path / "seed"
    d.mkdir()
    (d / "org.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {"id": "team:eng", "type": "Team", "name": "Engineering"},
                    {
                        "id": "person:dev",
                        "type": "Person",
                        "role": "Developer",
                        "archetype": "developer",
                        "team": "team:eng",
                    },
                    {"id": "ai:001", "type": "AIAgent", "role": "AI copilot", "principal": "person:dev"},
                ],
                "edges": [
                    {"source": "person:dev", "target": "ai:001", "type": "owns"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (d / "assets.json").write_text(
        json.dumps(
            {
                "nodes": [{"id": "asset:repo", "type": "Asset", "name": "Repo"}],
                "edges": [{"source": "team:eng", "target": "asset:repo", "type": "owns"}],
            }
        ),
        encoding="utf-8",
    )
    (d / "policy_aup.md").write_text(
        "---\nid: policy:aup\ntitle: Acceptable Use\n---\n\n# Acceptable Use\n\nBody text.\n",
        encoding="utf-8",
    )
    return d
