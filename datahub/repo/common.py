"""Shared helpers for repository functions."""

from __future__ import annotations

from typing import Any

from datahub import db

MAX_LIMIT = 200


class BadArgumentError(ValueError):
    """A tool or endpoint argument is not one of the allowed values."""


def clamp(limit: int | None, default: int = 25) -> int:
    if limit is None:
        return default
    return max(1, min(int(limit), MAX_LIMIT))


def choice(value: str | None, allowed: tuple[str, ...], name: str) -> str | None:
    """Validate an enum-like argument (also protects the column names we interpolate)."""
    if value is None:
        return None
    if value not in allowed:
        raise BadArgumentError(f"{name} must be one of: {', '.join(allowed)}")
    return value


class Where:
    """Builds a parameterised WHERE clause."""

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.params: list[Any] = []

    def eq(self, column: str, value: Any) -> None:
        if value is not None:
            self.parts.append(f"{column} = ?")
            self.params.append(value)

    def like(self, column: str, value: str | None) -> None:
        if value:
            self.parts.append(f"{column} LIKE ?")
            self.params.append(f"%{value}%")

    def cmp(self, column: str, op: str, value: Any) -> None:
        if value is not None:
            self.parts.append(f"{column} {op} ?")
            self.params.append(value)

    def raw(self, clause: str, *params: Any) -> None:
        self.parts.append(clause)
        self.params.extend(params)

    @property
    def sql(self) -> str:
        return (" WHERE " + " AND ".join(self.parts)) if self.parts else ""


def run(sql: str, params: list[Any] | tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return db.query(sql, tuple(params))


def one(sql: str, params: list[Any] | tuple[Any, ...] = ()) -> dict[str, Any] | None:
    found = run(sql, params)
    return found[0] if found else None


def paged(select: str, frm: str, where: Where, order: str, limit: int) -> dict[str, Any]:
    """Rows plus the true total, so an answer can say 'showing 25 of 143'.

    `select`, `frm` and `order` are fixed strings in this package; user values only ever travel
    as bound parameters.
    """
    total = one(f"SELECT COUNT(*) AS n {frm}{where.sql}", where.params)  # noqa: S608
    rows = run(f"{select} {frm}{where.sql} ORDER BY {order} LIMIT ?", [*where.params, limit])  # noqa: S608
    return {"total": total["n"] if total else 0, "rows": rows}
