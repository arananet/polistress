"""The typed knowledge graph, backed by NetworkX with SQLite persistence."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import networkx as nx

from .types import EDGE_TYPES, NODE_TYPES, Domain, EdgeType, NodeType

# Which node types belong to which governance domain. A node is in a domain's
# subgraph if its type is listed here (edges are included when both endpoints
# are in the domain).
_DOMAIN_NODE_TYPES: dict[Domain, frozenset[str]] = {
    Domain.CYBER: frozenset(
        {
            NodeType.PERSON.value,
            NodeType.TEAM.value,
            NodeType.ASSET.value,
            NodeType.CONTROL.value,
            NodeType.POLICY.value,
            NodeType.FINDING.value,
        }
    ),
    Domain.AI_GOVERNANCE: frozenset(
        {
            NodeType.PERSON.value,
            NodeType.TEAM.value,
            NodeType.AI_AGENT.value,
            NodeType.CONTROL.value,
            NodeType.POLICY.value,
            NodeType.FINDING.value,
        }
    ),
}


class WorldGraph:
    """A typed directed multigraph describing an organization.

    Nodes carry a ``type`` attribute (one of :class:`NodeType`) plus arbitrary
    metadata. Edges carry a ``type`` attribute (one of :class:`EdgeType`). The
    graph can be persisted to and loaded from SQLite.
    """

    def __init__(self) -> None:
        self._g: nx.MultiDiGraph = nx.MultiDiGraph()

    # -- construction -----------------------------------------------------

    def add_node(self, node_id: str, node_type: NodeType | str, **attrs: Any) -> None:
        type_value = node_type.value if isinstance(node_type, NodeType) else node_type
        if type_value not in NODE_TYPES:
            raise ValueError(f"unknown node type: {type_value!r}")
        self._g.add_node(node_id, type=type_value, **attrs)

    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: EdgeType | str,
        **attrs: Any,
    ) -> None:
        type_value = edge_type.value if isinstance(edge_type, EdgeType) else edge_type
        if type_value not in EDGE_TYPES:
            raise ValueError(f"unknown edge type: {type_value!r}")
        if source not in self._g:
            raise KeyError(f"source node not in graph: {source!r}")
        if target not in self._g:
            raise KeyError(f"target node not in graph: {target!r}")
        self._g.add_edge(source, target, key=type_value, type=type_value, **attrs)

    # -- inspection -------------------------------------------------------

    @property
    def graph(self) -> nx.MultiDiGraph:
        return self._g

    def __len__(self) -> int:
        return self._g.number_of_nodes()

    def has_node(self, node_id: str) -> bool:
        return node_id in self._g

    def node(self, node_id: str) -> dict[str, Any]:
        return dict(self._g.nodes[node_id])

    def node_type(self, node_id: str) -> str:
        return self._g.nodes[node_id]["type"]

    def nodes_of_type(self, node_type: NodeType | str) -> list[str]:
        type_value = node_type.value if isinstance(node_type, NodeType) else node_type
        return [n for n, d in self._g.nodes(data=True) if d.get("type") == type_value]

    def edges(self) -> list[tuple[str, str, str]]:
        return [(u, v, k) for u, v, k in self._g.edges(keys=True)]

    def count_nodes(self) -> int:
        return self._g.number_of_nodes()

    def count_edges(self) -> int:
        return self._g.number_of_edges()

    # -- query API --------------------------------------------------------

    def neighbors(
        self,
        node_id: str,
        edge_type: EdgeType | str | None = None,
        direction: str = "both",
    ) -> list[str]:
        """Return neighbor node ids, optionally filtered by edge type/direction.

        ``direction`` is one of ``"out"``, ``"in"``, or ``"both"``.
        """
        if node_id not in self._g:
            raise KeyError(f"node not in graph: {node_id!r}")
        type_value = (
            edge_type.value if isinstance(edge_type, EdgeType) else edge_type
        )
        result: set[str] = set()
        if direction in ("out", "both"):
            for _, v, k in self._g.out_edges(node_id, keys=True):
                if type_value is None or k == type_value:
                    result.add(v)
        if direction in ("in", "both"):
            for u, _, k in self._g.in_edges(node_id, keys=True):
                if type_value is None or k == type_value:
                    result.add(u)
        return sorted(result)

    def paths(
        self,
        source: str,
        target: str,
        max_length: int = 6,
    ) -> list[list[str]]:
        """All simple paths from ``source`` to ``target`` (ignoring direction).

        Uses the underlying undirected projection so relationships can be
        traced regardless of edge orientation (e.g. person → team → asset).
        """
        if source not in self._g:
            raise KeyError(f"source node not in graph: {source!r}")
        if target not in self._g:
            raise KeyError(f"target node not in graph: {target!r}")
        undirected = self._g.to_undirected(as_view=True)
        return [
            list(p)
            for p in nx.all_simple_paths(undirected, source, target, cutoff=max_length)
        ]

    def subgraph_by_domain(self, domain: Domain | str) -> WorldGraph:
        """Extract the subgraph of nodes/edges relevant to a governance domain."""
        domain_enum = Domain(domain) if isinstance(domain, str) else domain
        allowed = _DOMAIN_NODE_TYPES[domain_enum]
        keep = [n for n, d in self._g.nodes(data=True) if d.get("type") in allowed]
        sub = WorldGraph()
        sub._g = self._g.subgraph(keep).copy()
        return sub

    # -- persistence ------------------------------------------------------

    def save(self, db_path: str | Path) -> None:
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        try:
            self._write_schema(conn)
            conn.execute("DELETE FROM edges")
            conn.execute("DELETE FROM nodes")
            for node_id, data in self._g.nodes(data=True):
                node_type = data["type"]
                attrs = {k: v for k, v in data.items() if k != "type"}
                conn.execute(
                    "INSERT INTO nodes (id, type, attrs) VALUES (?, ?, ?)",
                    (node_id, node_type, json.dumps(attrs, sort_keys=True)),
                )
            for u, v, k, data in self._g.edges(keys=True, data=True):
                attrs = {ak: av for ak, av in data.items() if ak != "type"}
                conn.execute(
                    "INSERT INTO edges (source, target, type, attrs) VALUES (?, ?, ?, ?)",
                    (u, v, k, json.dumps(attrs, sort_keys=True)),
                )
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def load(cls, db_path: str | Path) -> WorldGraph:
        db_path = Path(db_path)
        if not db_path.exists():
            raise FileNotFoundError(f"graph database not found: {db_path}")
        conn = sqlite3.connect(db_path)
        try:
            wg = cls()
            for node_id, node_type, attrs_json in conn.execute(
                "SELECT id, type, attrs FROM nodes"
            ):
                attrs = json.loads(attrs_json) if attrs_json else {}
                wg.add_node(node_id, node_type, **attrs)
            for source, target, edge_type, attrs_json in conn.execute(
                "SELECT source, target, type, attrs FROM edges"
            ):
                attrs = json.loads(attrs_json) if attrs_json else {}
                wg.add_edge(source, target, edge_type, **attrs)
            return wg
        finally:
            conn.close()

    @staticmethod
    def _write_schema(conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                id    TEXT PRIMARY KEY,
                type  TEXT NOT NULL,
                attrs TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS edges (
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                type   TEXT NOT NULL,
                attrs  TEXT NOT NULL,
                PRIMARY KEY (source, target, type)
            );
            CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target);
            """
        )

    # -- bulk helpers -----------------------------------------------------

    def add_nodes_from(self, items: Iterable[tuple[str, NodeType | str, dict[str, Any]]]) -> None:
        for node_id, node_type, attrs in items:
            self.add_node(node_id, node_type, **attrs)
