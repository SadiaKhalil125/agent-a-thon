"""Read-only access to the fabricated company database (no writes, no server state).

The file is opened with `mode=ro&immutable=1`, so it also works on Vercel's read-only filesystem.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "company" / "northstar.db"


class DatabaseMissingError(RuntimeError):
    """The database file has not been generated (python -m datahub.generate)."""


def connect(path: Path | None = None) -> sqlite3.Connection:
    """A new read-only connection. Rows are `sqlite3.Row` (dict-like)."""
    target = path or DB_PATH
    if not target.is_file():
        raise DatabaseMissingError("Company database not found. Run: python -m datahub.generate")
    conn = sqlite3.connect(
        f"{target.resolve().as_uri()}?mode=ro&immutable=1", uri=True, check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def query(sql: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> list[dict[str, Any]]:
    """Run one parameterised SELECT and return plain dicts."""
    conn = connect()
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def meta(key: str) -> str:
    rows = query("SELECT value FROM meta WHERE key = ?", (key,))
    if not rows:
        raise KeyError(key)
    return str(rows[0]["value"])


def as_of() -> date:
    """The company's 'today'. Fixed so questions like 'tomorrow' are reproducible."""
    return date.fromisoformat(meta("as_of"))


__all__ = ["DB_PATH", "DatabaseMissingError", "as_of", "connect", "meta", "query"]
