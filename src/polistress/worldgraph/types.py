"""Node, edge, and domain vocabularies for the world graph."""

from __future__ import annotations

from enum import StrEnum


class NodeType(StrEnum):
    """Typed entities in the organizational knowledge graph."""

    PERSON = "Person"
    TEAM = "Team"
    ASSET = "Asset"
    CONTROL = "Control"
    POLICY = "Policy"
    FINDING = "Finding"
    AI_AGENT = "AIAgent"


class EdgeType(StrEnum):
    """Typed relationships between graph nodes."""

    REPORTS_TO = "reports_to"
    OWNS = "owns"
    GOVERNED_BY = "governed_by"
    DEPENDS_ON = "depends_on"
    HAS_EXCEPTION = "has_exception"
    MITIGATES = "mitigates"


class Domain(StrEnum):
    """Governance domains used to slice the graph into subgraphs."""

    CYBER = "cyber"
    AI_GOVERNANCE = "ai_governance"


NODE_TYPES: frozenset[str] = frozenset(t.value for t in NodeType)
EDGE_TYPES: frozenset[str] = frozenset(t.value for t in EdgeType)
