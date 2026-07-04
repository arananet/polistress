"""Ingest seed documents (markdown / JSON) into a :class:`WorldGraph`.

Two document shapes are recognized:

* **JSON** files containing ``{"nodes": [...], "edges": [...]}``. Each node is
  ``{"id", "type", ...metadata}``; each edge is
  ``{"source", "target", "type", ...metadata}``.
* **Markdown** files, each ingested as a single ``Policy`` node. A leading
  ``key: value`` front-matter block (delimited by ``---`` lines) supplies the
  node id and metadata; the remaining body is stored as ``body``.

Ingestion is two-pass: all nodes across all files are added first, then edges,
so cross-file references resolve regardless of file order.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .graph import WorldGraph
from .types import NodeType


def _parse_markdown_policy(path: Path) -> tuple[str, dict[str, Any]]:
    """Return ``(node_id, attrs)`` for a markdown policy document."""
    text = path.read_text(encoding="utf-8")
    meta: dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        _, _, rest = text.partition("---")
        front, sep, body = rest.partition("---")
        if sep:
            for line in front.strip().splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    meta[key.strip()] = value.strip()
        else:
            body = text
    node_id = meta.pop("id", None) or f"policy:{path.stem}"
    attrs: dict[str, Any] = {"body": body.strip()}
    attrs.update(meta)
    if "name" not in attrs:
        attrs["name"] = meta.get("title", path.stem)
    return node_id, attrs


def _collect_json(path: Path) -> tuple[list[dict], list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object with 'nodes'/'edges'")
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    return nodes, edges


def ingest_directory(directory: str | Path) -> WorldGraph:
    """Build a :class:`WorldGraph` from every ``.json`` and ``.md`` file under ``directory``."""
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"not a directory: {directory}")

    json_files = sorted(directory.rglob("*.json"))
    # README files document the seed set; they are not policy content.
    md_files = sorted(
        p for p in directory.rglob("*.md") if p.stem.lower() != "readme"
    )
    if not json_files and not md_files:
        raise ValueError(f"no .json or .md seed documents found under {directory}")

    wg = WorldGraph()
    pending_edges: list[dict] = []

    # Pass 1: nodes.
    for jf in json_files:
        nodes, edges = _collect_json(jf)
        for node in nodes:
            node_id = node["id"]
            node_type = node["type"]
            attrs = {k: v for k, v in node.items() if k not in ("id", "type")}
            if not wg.has_node(node_id):
                wg.add_node(node_id, node_type, **attrs)
        pending_edges.extend(edges)

    for mf in md_files:
        node_id, attrs = _parse_markdown_policy(mf)
        if not wg.has_node(node_id):
            wg.add_node(node_id, NodeType.POLICY, **attrs)

    # Pass 2: edges.
    for edge in pending_edges:
        wg.add_edge(
            edge["source"],
            edge["target"],
            edge["type"],
            **{k: v for k, v in edge.items() if k not in ("source", "target", "type")},
        )

    return wg
