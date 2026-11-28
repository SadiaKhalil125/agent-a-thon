"""Guarded read-only SQL for the agents (security boundary, ADR-006).

Layers, any one of which already stops a write: a read-only immutable connection, SQLite's
`query_only`, a SELECT/WITH-only text check, single statement, no comments, a table allow-list and
function allow-list enforced by the SQLite authorizer, plus row, length and time caps.
"""

from __future__ import annotations

import re
import sqlite3
import time
from typing import Any

from datahub import db
from datahub.dictionary import table_names

MAX_SQL_LENGTH = 2000
MAX_ROWS = 200
TIMEOUT_SECONDS = 3.0

ALLOWED_FUNCTIONS = frozenset(
    {
        "count",
        "sum",
        "avg",
        "min",
        "max",
        "total",
        "round",
        "abs",
        "coalesce",
        "ifnull",
        "nullif",
        "length",
        "lower",
        "upper",
        "substr",
        "substring",
        "trim",
        "ltrim",
        "rtrim",
        "replace",
        "instr",
        "date",
        "datetime",
        "strftime",
        "julianday",
        "group_concat",
        "printf",
        "cast",
        "iif",
        "typeof",
        "like",
        "glob",
    }
)


class SqlRejectedError(ValueError):
    """The statement is not a plain, allowed SELECT. The message is safe to show the model."""


def _allowed_tables() -> frozenset[str]:
    return frozenset(table_names())


def _check_text(sql: str) -> str:
    text = sql.strip()
    if not text:
        raise SqlRejectedError("Empty statement.")
    if len(text) > MAX_SQL_LENGTH:
        raise SqlRejectedError(f"Statement too long (max {MAX_SQL_LENGTH} characters).")
    if "--" in text or "/*" in text or "*/" in text:
        raise SqlRejectedError("Comments are not allowed.")
    text = text.rstrip(";").rstrip()
    if ";" in text:
        raise SqlRejectedError("Only one statement is allowed.")
    head = text.split(None, 1)[0].lower()
    if head not in ("select", "with"):
        raise SqlRejectedError("Only SELECT statements are allowed.")
    return text


_CTE_NAME = re.compile(r"(\w+)\s*(?:\([^()]*\))?\s*AS\s*\(", re.IGNORECASE)


def _cte_names(text: str) -> frozenset[str]:
    """Names the statement defines itself with WITH (a recursive CTE reads its own name)."""
    return frozenset(m.group(1) for m in _CTE_NAME.finditer(text)) - _allowed_tables()


def _authorizer(tables: frozenset[str], ctes: frozenset[str] = frozenset()) -> Any:
    ok, deny = sqlite3.SQLITE_OK, sqlite3.SQLITE_DENY

    def authorize(action: int, arg1: str | None, arg2: str | None, *_: Any) -> int:
        if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
            return ok
        if action == sqlite3.SQLITE_READ:
            return ok if arg1 in tables or arg1 in ctes else deny
        if action == sqlite3.SQLITE_FUNCTION:
            return ok if (arg2 or "").lower() in ALLOWED_FUNCTIONS else deny
        return deny

    return authorize


def run_select(
    sql: str, *, max_rows: int = MAX_ROWS, timeout: float = TIMEOUT_SECONDS
) -> dict[str, Any]:
    """Run one guarded SELECT. Returns columns, rows, rowCount and whether it was truncated."""
    text = _check_text(sql)
    conn = db.connect()
    deadline = time.monotonic() + timeout
    try:
        conn.set_authorizer(_authorizer(_allowed_tables(), _cte_names(text)))
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10000)
        try:
            cursor = conn.execute(text)
            fetched = cursor.fetchmany(max_rows + 1)
        except sqlite3.DatabaseError as exc:
            message = str(exc)
            if "interrupted" in message:
                raise SqlRejectedError("Query took too long. Simplify it or add filters.") from None
            if "not authorized" in message or "prohibited" in message:
                raise SqlRejectedError(
                    "Statement uses something that is not allowed (only SELECT on the "
                    "documented tables and basic functions)."
                ) from None
            raise SqlRejectedError(f"SQL error: {message}") from None
        columns = [d[0] for d in cursor.description or []]
        truncated = len(fetched) > max_rows
        rows = [dict(zip(columns, row, strict=True)) for row in fetched[:max_rows]]
        return {"columns": columns, "rows": rows, "rowCount": len(rows), "truncated": truncated}
    finally:
        conn.close()


__all__ = ["MAX_ROWS", "SqlRejectedError", "run_select"]
