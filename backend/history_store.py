"""Durable local storage for completed analysis results."""

import os
import sqlite3
from pathlib import Path
from typing import Any

from backend.schemas import AnalysisResults


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "analysis_history.sqlite3"
DB_PATH = Path(os.getenv("REVORA_HISTORY_DB", str(DEFAULT_DB_PATH)))


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize() -> None:
    """Create the history table if it does not exist."""
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                created_at TEXT NOT NULL,
                mode TEXT NOT NULL,
                results_json TEXT NOT NULL
            )
            """
        )


def save(entry: dict[str, Any]) -> None:
    """Persist an analysis, replacing an entry with the same ID."""
    results: AnalysisResults = entry["results"]
    with _connect() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO analyses
                (id, filename, created_at, mode, results_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                entry["id"],
                entry["filename"],
                entry["created_at"],
                entry["mode"],
                results.model_dump_json(),
            ),
        )


def get(analysis_id: str) -> dict[str, Any] | None:
    """Load one analysis from durable storage."""
    with _connect() as connection:
        row = connection.execute(
            "SELECT id, filename, created_at, mode, results_json FROM analyses WHERE id = ?",
            (analysis_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "filename": row["filename"],
        "created_at": row["created_at"],
        "mode": row["mode"],
        "results": AnalysisResults.model_validate_json(row["results_json"]),
    }


def list_all() -> list[dict[str, Any]]:
    """Load all persisted analyses, newest first."""
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, filename, created_at, mode, results_json
            FROM analyses
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [
        {
            "id": row["id"],
            "filename": row["filename"],
            "created_at": row["created_at"],
            "mode": row["mode"],
            "results": AnalysisResults.model_validate_json(row["results_json"]),
        }
        for row in rows
    ]


def delete(analysis_id: str) -> bool:
    """Delete an analysis and report whether a persisted row existed."""
    with _connect() as connection:
        cursor = connection.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
        return cursor.rowcount > 0
