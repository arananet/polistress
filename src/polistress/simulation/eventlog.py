"""Append-only event log backed by SQLite.

Every agent action is recorded with tick, agent_id, action, target, and
rationale. The log is append-only: SQLite triggers reject UPDATE and DELETE on
the ``events`` table, so history cannot be rewritten after the fact.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Event:
    """A single logged event."""

    event_id: int
    tick: int
    agent_id: str
    action: str
    target: str | None
    rationale: str


class AppendOnlyViolation(RuntimeError):
    """Raised when code attempts to mutate the append-only event log."""


class EventLog:
    """SQLite-backed, append-only log of simulation events."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                tick      INTEGER NOT NULL,
                agent_id  TEXT NOT NULL,
                action    TEXT NOT NULL,
                target    TEXT,
                rationale TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_events_tick ON events(tick);
            CREATE INDEX IF NOT EXISTS idx_events_agent ON events(agent_id);
            CREATE INDEX IF NOT EXISTS idx_events_action ON events(action);

            CREATE TRIGGER IF NOT EXISTS events_no_update
            BEFORE UPDATE ON events
            BEGIN
                SELECT RAISE(ABORT, 'event log is append-only: UPDATE forbidden');
            END;

            CREATE TRIGGER IF NOT EXISTS events_no_delete
            BEFORE DELETE ON events
            BEGIN
                SELECT RAISE(ABORT, 'event log is append-only: DELETE forbidden');
            END;
            """
        )
        self._conn.commit()

    def append(
        self,
        tick: int,
        agent_id: str,
        action: str,
        rationale: str,
        target: str | None = None,
    ) -> int:
        """Append an event and return its assigned ``event_id``."""
        cur = self._conn.execute(
            "INSERT INTO events (tick, agent_id, action, target, rationale) "
            "VALUES (?, ?, ?, ?, ?)",
            (tick, agent_id, action, target, rationale),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def all(self) -> list[Event]:
        rows = self._conn.execute(
            "SELECT event_id, tick, agent_id, action, target, rationale "
            "FROM events ORDER BY event_id"
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def by_tick(self, tick: int) -> list[Event]:
        rows = self._conn.execute(
            "SELECT event_id, tick, agent_id, action, target, rationale "
            "FROM events WHERE tick = ? ORDER BY event_id",
            (tick,),
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def get(self, event_id: int) -> Event | None:
        row = self._conn.execute(
            "SELECT event_id, tick, agent_id, action, target, rationale "
            "FROM events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        return self._row_to_event(row) if row else None

    def action_counts(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT action, COUNT(*) AS n FROM events GROUP BY action"
        ).fetchall()
        return {r["action"]: int(r["n"]) for r in rows}

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    def max_tick(self) -> int:
        row = self._conn.execute("SELECT MAX(tick) FROM events").fetchone()
        return int(row[0]) if row[0] is not None else -1

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        return Event(
            event_id=row["event_id"],
            tick=row["tick"],
            agent_id=row["agent_id"],
            action=row["action"],
            target=row["target"],
            rationale=row["rationale"],
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> EventLog:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
