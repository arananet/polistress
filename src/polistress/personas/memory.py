"""Recency-weighted agent memory, persisted to SQLite.

Each memory entry records an observed event with a base salience. Recall weights
entries by ``salience * decay ** (current_tick - tick)`` so recent, salient
observations dominate — an exponential recency model.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MemoryEntry:
    """A single remembered observation."""

    agent_id: str
    tick: int
    event_id: int
    note: str
    salience: float
    weight: float = 0.0


class AgentMemory:
    """SQLite-backed store of agent observations with recency-weighted recall."""

    def __init__(self, db_path: str | Path, decay: float = 0.85) -> None:
        if not 0.0 < decay <= 1.0:
            raise ValueError(f"decay must be in (0, 1], got {decay}")
        self.db_path = Path(db_path)
        self.decay = decay
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS agent_memory (
                mem_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                tick     INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                note     TEXT NOT NULL,
                salience REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_mem_agent ON agent_memory(agent_id);
            """
        )
        self._conn.commit()

    def observe(
        self,
        agent_id: str,
        tick: int,
        event_id: int,
        note: str,
        salience: float = 1.0,
    ) -> None:
        """Record that ``agent_id`` observed an event at ``tick``."""
        self._conn.execute(
            "INSERT INTO agent_memory (agent_id, tick, event_id, note, salience) "
            "VALUES (?, ?, ?, ?, ?)",
            (agent_id, tick, event_id, note, float(salience)),
        )
        self._conn.commit()

    def recall(
        self,
        agent_id: str,
        current_tick: int,
        top_k: int = 8,
    ) -> list[MemoryEntry]:
        """Return the ``top_k`` most recency-weighted memories for an agent."""
        rows = self._conn.execute(
            "SELECT agent_id, tick, event_id, note, salience FROM agent_memory "
            "WHERE agent_id = ?",
            (agent_id,),
        ).fetchall()
        entries: list[MemoryEntry] = []
        for row in rows:
            age = max(0, current_tick - row["tick"])
            weight = float(row["salience"]) * (self.decay**age)
            entries.append(
                MemoryEntry(
                    agent_id=row["agent_id"],
                    tick=row["tick"],
                    event_id=row["event_id"],
                    note=row["note"],
                    salience=row["salience"],
                    weight=weight,
                )
            )
        entries.sort(key=lambda e: e.weight, reverse=True)
        return entries[:top_k]

    def count(self, agent_id: str | None = None) -> int:
        if agent_id is None:
            row = self._conn.execute("SELECT COUNT(*) FROM agent_memory").fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM agent_memory WHERE agent_id = ?", (agent_id,)
            ).fetchone()
        return int(row[0])

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> AgentMemory:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
