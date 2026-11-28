"""HR: people, headcount, leave, hiring."""

from __future__ import annotations

from typing import Any

from datahub import db
from datahub.repo.common import Where, choice, clamp, paged, run

HEADCOUNT_GROUPS = ("department", "role", "level", "location", "team", "employment_type", "status")
LEAVE_TYPES = ("vacation", "sick", "medical", "parental", "unpaid")
LEAVE_STATUS = ("approved", "pending", "rejected")
_GROUP_SQL = {
    "department": "d.name",
    "role": "e.role",
    "level": "e.level",
    "location": "e.location",
    "team": "COALESCE(t.name, 'none')",
    "employment_type": "e.employment_type",
    "status": "e.status",
}


def headcount(group_by: str = "department") -> dict[str, Any]:
    """Number of people per department, role, level, location, team, type or status."""
    group = choice(group_by, HEADCOUNT_GROUPS, "group_by") or "department"
    rows = run(
        f"SELECT {_GROUP_SQL[group]} AS {group}, COUNT(*) AS people, "  # noqa: S608
        "SUM(e.monthly_cost_usd) AS monthly_cost_usd "
        "FROM employees e JOIN departments d ON d.id = e.department_id "
        "LEFT JOIN teams t ON t.id = e.team_id "
        f"GROUP BY {_GROUP_SQL[group]} ORDER BY people DESC, {group}"
    )
    return {"total": sum(r["people"] for r in rows), "rows": rows}


def find_employees(
    name: str | None = None,
    department: str | None = None,
    role: str | None = None,
    skill: str | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """People matching the filters, with their skills and manager."""
    w = Where()
    w.like("e.name", name)
    w.like("d.name", department)
    w.like("e.role", role)
    w.eq("e.status", choice(status, ("active", "on_leave"), "status"))
    if skill:
        w.raw("e.id IN (SELECT employee_id FROM skills WHERE skill LIKE ?)", f"%{skill}%")
    return paged(
        "SELECT e.id, e.name, e.role, e.level, d.name AS department, e.employment_type, "
        "e.location, e.status, e.hire_date, m.name AS manager, "
        "(SELECT group_concat(skill, ', ') FROM skills s WHERE s.employee_id = e.id) AS skills",
        "FROM employees e JOIN departments d ON d.id = e.department_id "
        "LEFT JOIN employees m ON m.id = e.manager_id",
        w,
        "d.name, e.name",
        clamp(limit),
    )


def leave_in_range(
    date_from: str | None = None,
    date_to: str | None = None,
    department: str | None = None,
    status: str | None = "approved",
    type: str | None = None,  # noqa: A002
    limit: int | None = None,
) -> dict[str, Any]:
    """Leave that overlaps the date range (default: from today onward)."""
    start = date_from or db.as_of().isoformat()
    w = Where()
    w.cmp("l.end_date", ">=", start)
    w.cmp("l.start_date", "<=", date_to)
    w.like("d.name", department)
    w.eq("l.status", choice(status, LEAVE_STATUS, "status"))
    w.eq("l.type", choice(type, LEAVE_TYPES, "type"))
    return paged(
        "SELECT e.name, e.role, d.name AS department, l.type, l.start_date, l.end_date, l.status",
        "FROM leave_requests l JOIN employees e ON e.id = l.employee_id "
        "JOIN departments d ON d.id = e.department_id",
        w,
        "l.start_date, e.name",
        clamp(limit, 50),
    )


def hiring_pipeline() -> dict[str, Any]:
    """Open roles with the number of candidates at each stage."""
    rows = run(
        "SELECT r.id, r.title, r.level, d.name AS department, r.status, r.opened_date, "
        "COUNT(c.id) AS candidates, "
        "SUM(c.stage = 'interview') AS interviewing, SUM(c.stage = 'offer') AS offers, "
        "SUM(c.stage = 'hired') AS hired "
        "FROM open_roles r JOIN departments d ON d.id = r.department_id "
        "LEFT JOIN candidates c ON c.role_id = r.id "
        "GROUP BY r.id ORDER BY r.status, r.opened_date"
    )
    return {"total": len(rows), "rows": rows}
