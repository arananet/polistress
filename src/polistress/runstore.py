"""Filesystem layout for simulation runs.

A run bundles everything needed to report on it: the graph snapshot, the
append-only event log, agent memory, the synthesized agents, and the scenario.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex

DEFAULT_ROOT = Path("runs")


def new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{token_hex(2)}"


@dataclass
class RunPaths:
    """Resolved paths for a single run's artifacts."""

    run_id: str
    root: Path

    @property
    def dir(self) -> Path:
        return self.root / self.run_id

    @property
    def graph_db(self) -> Path:
        return self.dir / "graph.db"

    @property
    def events_db(self) -> Path:
        return self.dir / "events.db"

    @property
    def memory_db(self) -> Path:
        return self.dir / "memory.db"

    @property
    def agents_json(self) -> Path:
        return self.dir / "agents.json"

    @property
    def scenario_json(self) -> Path:
        return self.dir / "scenario.json"

    @property
    def meta_json(self) -> Path:
        return self.dir / "meta.json"

    @property
    def findings_json(self) -> Path:
        return self.dir / "findings.json"

    @property
    def findings_csv(self) -> Path:
        return self.dir / "findings.csv"

    def ensure(self) -> RunPaths:
        self.dir.mkdir(parents=True, exist_ok=True)
        return self

    def write_meta(self, meta: dict) -> None:
        self.meta_json.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def read_meta(self) -> dict:
        if not self.meta_json.exists():
            return {}
        return json.loads(self.meta_json.read_text(encoding="utf-8"))


def run_paths(run_id: str, root: Path | str = DEFAULT_ROOT) -> RunPaths:
    return RunPaths(run_id=run_id, root=Path(root))
