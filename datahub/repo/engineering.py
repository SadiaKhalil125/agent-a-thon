"""Engineering and delivery: projects, tickets, workloads, commitments."""

from __future__ import annotations

from typing import Any

from datahub import db
from datahub.repo.common import Where, choice, clamp, one, paged, run

PROJECT_STATUS = ("active", "completed", "on_hold")
PROJECT_HEALTH = ("on_track", "at_risk", "off_track", "done")
TICKET_STATUS = ("todo", "in_progress", "in_review", "blocked", "done")
TICKET_PRIORITY = ("low", "medium", "high", "critical")


def list_projects(
    status: str | None = None,
    health: str | None = None,
    team: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Projects with progress (done tickets / all tickets) and how many people are allocated."""
    w = Where()
    w.eq("p.status", choice(status, PROJECT_STATUS, "status"))
    w.eq("p.health", choice(health, PROJECT_HEALTH, "health"))
    w.like("t.name", team)
    return paged(
        "SELECT p.code, p.name, p.status, p.health, t.name AS team, a.name AS customer, "
        "p.start_date, p.target_date, p.budget_usd, "
        "(SELECT COUNT(*) FROM tickets k WHERE k.project_id = p.id) AS tickets, "
        "(SELECT COUNT(*) FROM tickets k WHERE k.project_id = p.id AND k.status = 'done') "
        "AS tickets_done, "
        "(SELECT COUNT(*) FROM allocations al WHERE al.project_id = p.id) AS people_allocated",
        "FROM projects p JOIN teams t ON t.id = p.team_id "
        "LEFT JOIN accounts a ON a.id = p.account_id",
        w,
        "p.status, p.target_date, p.code",
        clamp(limit, 50),
    )


def project_detail(project: str) -> dict[str, Any]:
    """One project (code, id or name fragment): ticket counts, people, commitments, sprint."""
    proj = one(
        "SELECT p.id, p.code, p.name, p.status, p.health, p.start_date, p.target_date, "
        "p.budget_usd, t.name AS team, m.name AS manager, a.name AS customer "
        "FROM projects p JOIN teams t ON t.id = p.team_id "
        "LEFT JOIN employees m ON m.id = p.manager_id "
        "LEFT JOIN accounts a ON a.id = p.account_id "
        "WHERE p.code = ? OR p.id = ? OR p.name LIKE ? ORDER BY p.id LIMIT 1",
        [project.upper(), int(project) if project.isdigit() else -1, f"%{project}%"],
    )
    if proj is None:
        return {"total": 0, "rows": []}
    pid = proj.pop("id")
    summary = {
        "tickets_by_status": run(
            "SELECT status, COUNT(*) AS tickets, SUM(estimate_days) AS estimate_days "
            "FROM tickets WHERE project_id = ? GROUP BY status",
            [pid],
        ),
        "people": run(
            "SELECT e.name, e.role, al.percent FROM allocations al "
            "JOIN employees e ON e.id = al.employee_id WHERE al.project_id = ? "
            "ORDER BY al.percent DESC",
            [pid],
        ),
        "commitments": run(
            "SELECT description, due_date, status FROM commitments WHERE project_id = ? "
            "ORDER BY due_date",
            [pid],
        ),
        "current_sprint": one(
            "SELECT name, start_date, end_date FROM sprints WHERE project_id = ? "
            "AND status = 'active'",
            [pid],
        ),
        "invoices": run(
            "SELECT number, amount_usd, status, due_date FROM invoices WHERE project_id = ? "
            "ORDER BY issued_date DESC LIMIT 10",
            [pid],
        ),
    }
    return {"total": 1, "rows": [proj], "summary": summary}


def search_tickets(
    project: str | None = None,
    status: str | None = None,
    assignee: str | None = None,
    priority: str | None = None,
    overdue: bool | None = None,
    unassigned: bool | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Tickets matching the filters. `overdue` means not done and due before today."""
    w = Where()
    w.eq("p.code", project.upper() if project else None)
    w.eq("k.status", choice(status, TICKET_STATUS, "status"))
    w.like("e.name", assignee)
    w.eq("k.priority", choice(priority, TICKET_PRIORITY, "priority"))
    if overdue:
        w.raw("k.status != 'done' AND k.due_date < ?", db.as_of().isoformat())
    if unassigned:
        w.raw("k.assignee_id IS NULL")
    return paged(
        "SELECT k.key, k.title, p.code AS project, k.type, k.priority, k.status, "
        "e.name AS assignee, k.estimate_days, k.due_date, k.blocked_by_ticket_id",
        "FROM tickets k JOIN projects p ON p.id = k.project_id "
        "LEFT JOIN employees e ON e.id = k.assignee_id",
        w,
        "CASE k.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 "
        "WHEN 'medium' THEN 2 ELSE 3 END, "
        "k.due_date, k.id",
        clamp(limit),
    )


def workload(
    person: str | None = None, overloaded_only: bool = False, limit: int | None = None
) -> dict[str, Any]:
    """Allocation total, open tickets and remaining estimate days per person."""
    w = Where()
    w.like("e.name", person)
    outer = " WHERE allocated_percent > 100" if overloaded_only else ""
    rows = run(
        "SELECT * FROM (SELECT e.name, e.role, t.name AS team, e.employment_type, e.status, "
        "COALESCE((SELECT SUM(percent) FROM allocations a WHERE a.employee_id = e.id), 0) "
        "AS allocated_percent, "
        "(SELECT COUNT(*) FROM tickets k WHERE k.assignee_id = e.id AND k.status != 'done') "
        "AS open_tickets, "
        "COALESCE((SELECT SUM(estimate_days) FROM tickets k WHERE k.assignee_id = e.id "
        "AND k.status != 'done'), 0) AS open_estimate_days, "
        "(SELECT group_concat(p.code || ' ' || a.percent || '%', ', ') FROM allocations a "
        "JOIN projects p ON p.id = a.project_id WHERE a.employee_id = e.id) AS projects "
        "FROM employees e JOIN teams t ON t.id = e.team_id"
        f"{w.sql}){outer} ORDER BY allocated_percent DESC, name LIMIT ?",  # noqa: S608
        [*w.params, clamp(limit, 50)],
    )
    return {"total": len(rows), "rows": rows}


def teams_overview() -> dict[str, Any]:
    """Each engineering team: lead, headcount, average allocation, active projects."""
    rows = run(
        "SELECT t.name AS team, l.name AS lead, COUNT(e.id) AS people, "
        "(SELECT group_concat(code, ', ') FROM projects p WHERE p.team_id = t.id "
        "AND p.status = 'active') AS active_projects "
        "FROM teams t LEFT JOIN employees l ON l.id = t.lead_id "
        "LEFT JOIN employees e ON e.team_id = t.id GROUP BY t.id ORDER BY t.name"
    )
    return {"total": len(rows), "rows": rows}


def commitments(status: str | None = "open", due_before: str | None = None) -> dict[str, Any]:
    """Customer commitments by due date."""
    w = Where()
    w.eq("c.status", choice(status, ("open", "met", "missed"), "status"))
    w.cmp("c.due_date", "<=", due_before)
    return paged(
        "SELECT c.description, c.due_date, c.status, p.code AS project, a.name AS customer",
        "FROM commitments c JOIN projects p ON p.id = c.project_id "
        "JOIN accounts a ON a.id = c.account_id",
        w,
        "c.due_date",
        50,
    )
