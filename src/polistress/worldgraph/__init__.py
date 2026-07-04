"""worldgraph — typed knowledge graph over an organization.

Ingest seed documents (markdown/JSON) into a NetworkX graph of typed nodes and
edges, persist to SQLite, and query by adjacency, paths, and domain.
"""

from .graph import WorldGraph
from .ingest import ingest_directory
from .types import EDGE_TYPES, NODE_TYPES, Domain, EdgeType, NodeType

__all__ = [
    "WorldGraph",
    "ingest_directory",
    "NodeType",
    "EdgeType",
    "Domain",
    "NODE_TYPES",
    "EDGE_TYPES",
]
