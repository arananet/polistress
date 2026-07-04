"""Tests for the world graph: ingestion, queries, and SQLite round-trip."""

from __future__ import annotations

from pathlib import Path

import pytest

from polistress.worldgraph import WorldGraph, ingest_directory
from polistress.worldgraph.types import Domain, EdgeType, NodeType


def test_ingest_builds_expected_types(seed_dir: Path) -> None:
    g = ingest_directory(seed_dir)
    assert set(g.nodes_of_type(NodeType.PERSON)) == {"person:dev"}
    assert set(g.nodes_of_type(NodeType.AI_AGENT)) == {"ai:001"}
    assert set(g.nodes_of_type(NodeType.ASSET)) == {"asset:repo"}
    assert "policy:aup" in g.nodes_of_type(NodeType.POLICY)
    # markdown body captured
    assert "Body text." in g.node("policy:aup")["body"]
    assert ("person:dev", "ai:001", "owns") in g.edges()


def test_unknown_node_type_rejected() -> None:
    g = WorldGraph()
    with pytest.raises(ValueError):
        g.add_node("x", "Nonsense")


def test_edge_requires_existing_endpoints() -> None:
    g = WorldGraph()
    g.add_node("a", NodeType.PERSON)
    with pytest.raises(KeyError):
        g.add_edge("a", "missing", EdgeType.REPORTS_TO)


def test_neighbors_directionality(small_graph: WorldGraph) -> None:
    g = small_graph
    # dev reports_to ciso (outgoing)
    assert g.neighbors("person:dev", EdgeType.REPORTS_TO, direction="out") == ["person:ciso"]
    # ciso has two direct reports (incoming)
    assert set(g.neighbors("person:ciso", EdgeType.REPORTS_TO, direction="in")) == {
        "person:dev",
        "person:aud",
    }
    # both directions with no type filter includes owned ai + manager
    assert "ai:001" in g.neighbors("person:dev")


def test_paths_between_nodes(small_graph: WorldGraph) -> None:
    paths = small_graph.paths("person:dev", "asset:repo", max_length=5)
    assert paths
    assert all(p[0] == "person:dev" and p[-1] == "asset:repo" for p in paths)


def test_subgraph_by_domain(small_graph: WorldGraph) -> None:
    ai_gov = small_graph.subgraph_by_domain(Domain.AI_GOVERNANCE)
    assert ai_gov.has_node("ai:001")
    cyber = small_graph.subgraph_by_domain(Domain.CYBER)
    # AIAgent excluded from the cyber slice
    assert not cyber.has_node("ai:001")
    assert cyber.has_node("asset:repo")


def test_sqlite_round_trip(small_graph: WorldGraph, tmp_path: Path) -> None:
    db = tmp_path / "g.db"
    small_graph.save(db)
    loaded = WorldGraph.load(db)
    assert loaded.count_nodes() == small_graph.count_nodes()
    assert set(loaded.edges()) == set(small_graph.edges())
    assert loaded.node("asset:repo")["classification"] == "confidential"
