"""SQLite-backed experiment memory store with FTS5 search."""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExperimentRecord:
    id: int | None = None
    timestamp: str = ""
    sample: str = ""
    measurement_type: str = ""
    parameters: dict[str, Any] | None = None
    result_path: str = ""
    notes: str = ""


@dataclass
class MemoryStore:
    db_path: Path = Path("./data/memory.db")

    def __post_init__(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    sample TEXT NOT NULL DEFAULT '',
                    measurement_type TEXT NOT NULL,
                    parameters TEXT DEFAULT '{}',
                    result_path TEXT DEFAULT '',
                    notes TEXT DEFAULT ''
                )
            """)
            # FTS5 virtual table for full-text search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS experiments_fts USING fts5(
                    sample, measurement_type, notes,
                    content='experiments', content_rowid='id'
                )
            """)
            # Triggers to keep FTS in sync
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS experiments_ai AFTER INSERT ON experiments BEGIN
                    INSERT INTO experiments_fts(rowid, sample, measurement_type, notes)
                    VALUES (new.id, new.sample, new.measurement_type, new.notes);
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS experiments_ad AFTER DELETE ON experiments BEGIN
                    INSERT INTO experiments_fts(experiments_fts, rowid, sample, measurement_type, notes)
                    VALUES('delete', old.id, old.sample, old.measurement_type, old.notes);
                END
            """)

    def record_experiment(
        self,
        measurement_type: str,
        sample: str = "",
        parameters: dict | None = None,
        result_path: str = "",
        notes: str = "",
    ) -> int:
        """Store an experiment record. Returns the record ID."""
        ts = datetime.now().isoformat()
        params_json = json.dumps(parameters or {})
        with sqlite3.connect(self.db_path) as conn:
            sql = (
                "INSERT INTO experiments"
                " (timestamp, sample, measurement_type, parameters, result_path, notes)"
                " VALUES (?, ?, ?, ?, ?, ?)"
            )
            cursor = conn.execute(sql, (ts, sample, measurement_type, params_json, result_path, notes))
            return cursor.lastrowid

    def search(self, query: str, limit: int = 10) -> list[ExperimentRecord]:
        """Full-text search across experiments."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            sql = (
                "SELECT e.* FROM experiments e"
                " JOIN experiments_fts f ON e.id = f.rowid"
                " WHERE experiments_fts MATCH ? ORDER BY rank LIMIT ?"
            )
            rows = conn.execute(sql, (query, limit)).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_recent(self, limit: int = 10) -> list[ExperimentRecord]:
        """Get most recent experiments."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM experiments ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_by_type(self, measurement_type: str, limit: int = 20) -> list[ExperimentRecord]:
        """Get experiments by measurement type."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM experiments WHERE measurement_type = ? ORDER BY timestamp DESC LIMIT ?",
                (measurement_type.upper(), limit),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def _row_to_record(self, row) -> ExperimentRecord:
        return ExperimentRecord(
            id=row["id"],
            timestamp=row["timestamp"],
            sample=row["sample"],
            measurement_type=row["measurement_type"],
            parameters=json.loads(row["parameters"]) if row["parameters"] else {},
            result_path=row["result_path"],
            notes=row["notes"],
        )
