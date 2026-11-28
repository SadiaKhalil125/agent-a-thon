"""Calendar: who is free when (derived from leave, holidays and meetings), plus an overview."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from datahub import db
from datahub.repo.common import BadArgumentError, run


def _working_days(start: date, end: date, holidays: set[str]) -> list[str]:
    days = []
    d = start
    while d <= end:
        if d.weekday() < 5 and d.isoformat() not in holidays:
            days.append(d.isoformat())
        d += timedelta(days=1)
    return days


def availability(
    person: str, date_from: str | None = None, date_to: str | None = None
) -> dict[str, Any]:
    """Working days, approved leave and meetings for people matching a name, in a date range."""
    start = date.fromisoformat(date_from) if date_from else db.as_of()
    end = date.fromisoformat(date_to) if date_to else start + timedelta(days=13)
    if end < start or (end - start).days > 120:
        raise BadArgumentError("date range must be 0 to 120 days")
    holidays = {r["date"] for r in run("SELECT date FROM holidays")}
    working = _working_days(start, end, holidays)
    people = run(
        "SELECT id, name, role FROM employees WHERE name LIKE ? ORDER BY name LIMIT 10",
        [f"%{person}%"],
    )
    rows = []
    for p in people:
        leave = run(
            "SELECT start_date, end_date, type FROM leave_requests WHERE employee_id = ? "
            "AND status = 'approved' AND end_date >= ? AND start_date <= ?",
            [p["id"], start.isoformat(), end.isoformat()],
        )
        off = {
            d
            for lv in leave
            for d in _working_days(
                max(start, date.fromisoformat(lv["start_date"])),
                min(end, date.fromisoformat(lv["end_date"])),
                holidays,
            )
        }
        meetings = run(
            "SELECT m.start_at, m.title FROM meetings m WHERE m.status = 'scheduled' AND "
            "substr(m.start_at, 1, 10) BETWEEN ? AND ? AND (m.owner_id = ? OR m.id IN "
            "(SELECT meeting_id FROM meeting_attendees WHERE employee_id = ?)) ORDER BY m.start_at",
            [start.isoformat(), end.isoformat(), p["id"], p["id"]],
        )
        free = [d for d in working if d not in off]
        rows.append(
            {
                "name": p["name"],
                "role": p["role"],
                "working_days_in_range": len(working),
                "days_on_leave": len(off),
                "available_days": len(free),
                "first_available_day": free[0] if free else None,
                "leave": leave,
                "meetings": meetings,
            }
        )
    return {
        "total": len(rows),
        "rows": rows,
        "summary": {"from": start.isoformat(), "to": end.isoformat()},
    }


def company_overview() -> dict[str, Any]:
    """Headline numbers across the company, plus the company's 'today'."""
    counts = {
        table: run(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"]  # noqa: S608
        for table in (
            "employees",
            "accounts",
            "leads",
            "opportunities",
            "projects",
            "tickets",
            "invoices",
        )
    }
    today = db.as_of().isoformat()
    active = run("SELECT COUNT(*) AS n FROM projects WHERE status = 'active'")[0]["n"]
    return {
        "rows": [
            {"today": today, "weekday": db.meta("weekday"), "active_projects": active, **counts}
        ],
        "summary": {"company": db.meta("company"), "currency": db.meta("currency")},
    }
