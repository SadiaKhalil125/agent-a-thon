"""Sales and CRM: leads, opportunities, meetings, accounts."""

from __future__ import annotations

from typing import Any

from datahub import db
from datahub.repo.common import Where, choice, clamp, one, paged, run

LEAD_STAGES = ("new", "contacted", "qualified", "proposal", "negotiation", "won", "lost")
LEAD_GROUPS = ("stage", "source", "owner", "region", "industry", "created_month")
MEETING_TYPES = ("discovery", "demo", "negotiation", "qbr", "onboarding", "internal")
MEETING_STATUS = ("scheduled", "completed", "cancelled", "no_show")
_GROUP_SQL = {
    "stage": "l.stage",
    "source": "l.source",
    "owner": "e.name",
    "region": "l.region",
    "industry": "l.industry",
    "created_month": "substr(l.created_date, 1, 7)",
}


def _lead_filters(
    stage: str | None,
    source: str | None,
    owner: str | None,
    region: str | None,
    industry: str | None,
    created_from: str | None,
    created_to: str | None,
    min_value: int | None = None,
) -> Where:
    w = Where()
    w.eq("l.stage", choice(stage, LEAD_STAGES, "stage"))
    w.eq("l.source", source)
    w.like("e.name", owner)
    w.eq("l.region", region)
    w.eq("l.industry", industry)
    w.cmp("l.created_date", ">=", created_from)
    w.cmp("l.created_date", "<=", created_to)
    w.cmp("l.est_value_usd", ">=", min_value)
    return w


def search_leads(
    stage: str | None = None,
    source: str | None = None,
    owner: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    min_value: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Leads matching the filters, biggest estimated value first."""
    w = _lead_filters(stage, source, owner, region, industry, created_from, created_to, min_value)
    return paged(
        "SELECT l.id, l.company, l.contact_name, l.stage, l.source, l.score, "
        "l.est_value_usd, l.industry, l.region, e.name AS owner, l.created_date, "
        "l.last_activity_date",
        "FROM leads l JOIN employees e ON e.id = l.owner_id",
        w,
        "l.est_value_usd DESC, l.id",
        clamp(limit),
    )


def count_leads(
    group_by: str = "stage",
    stage: str | None = None,
    source: str | None = None,
    owner: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
) -> dict[str, Any]:
    """Number and total value of leads per group (stage, source, owner, region, ...)."""
    group = choice(group_by, LEAD_GROUPS, "group_by") or "stage"
    w = _lead_filters(stage, source, owner, region, industry, created_from, created_to)
    rows = run(
        f"SELECT {_GROUP_SQL[group]} AS {group}, COUNT(*) AS leads, "  # noqa: S608
        "SUM(l.est_value_usd) AS total_value_usd "
        f"FROM leads l JOIN employees e ON e.id = l.owner_id{w.sql} "
        f"GROUP BY {group} ORDER BY leads DESC, {group}",
        w.params,
    )
    return {"total": sum(r["leads"] for r in rows), "rows": rows}


def list_meetings(
    date_from: str | None = None,
    date_to: str | None = None,
    type: str | None = None,  # noqa: A002
    status: str | None = None,
    owner: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Meetings in a date range (YYYY-MM-DD, inclusive), earliest first."""
    w = Where()
    w.cmp("substr(m.start_at, 1, 10)", ">=", date_from)
    w.cmp("substr(m.start_at, 1, 10)", "<=", date_to)
    w.eq("m.type", choice(type, MEETING_TYPES, "type"))
    w.eq("m.status", choice(status, MEETING_STATUS, "status"))
    w.like("e.name", owner)
    return paged(
        "SELECT m.id, m.title, m.type, m.status, m.start_at, m.duration_min, e.name AS owner, "
        "COALESCE(l.company, a.name, oa.name) AS company",
        "FROM meetings m JOIN employees e ON e.id = m.owner_id "
        "LEFT JOIN leads l ON l.id = m.lead_id LEFT JOIN accounts a ON a.id = m.account_id "
        "LEFT JOIN opportunities o ON o.id = m.opportunity_id "
        "LEFT JOIN accounts oa ON oa.id = o.account_id",
        w,
        "m.start_at, m.id",
        clamp(limit, 50),
    )


def pipeline_summary(group_by: str = "stage") -> dict[str, Any]:
    """Opportunities by stage or owner: count, amount and probability-weighted amount."""
    group = choice(group_by, ("stage", "owner"), "group_by") or "stage"
    expr = "o.stage" if group == "stage" else "e.name"
    rows = run(
        f"SELECT {expr} AS {group}, COUNT(*) AS opportunities, SUM(o.amount_usd) AS amount_usd, "  # noqa: S608
        "CAST(SUM(o.amount_usd * o.probability / 100.0) AS INTEGER) AS weighted_usd "
        "FROM opportunities o JOIN employees e ON e.id = o.owner_id "
        f"GROUP BY {group} ORDER BY amount_usd DESC"
    )
    return {"rows": rows}


def account_overview(account: str) -> dict[str, Any]:
    """One account (by name fragment or id) with its people, deals, projects and money."""
    where = "a.id = ?" if account.isdigit() else "a.name LIKE ?"
    param: Any = int(account) if account.isdigit() else f"%{account}%"
    acc = one(
        "SELECT a.id, a.name, a.industry, a.region, a.size_band, a.status, e.name AS owner "
        f"FROM accounts a LEFT JOIN employees e ON e.id = a.owner_id WHERE {where} "  # noqa: S608
        "ORDER BY a.id LIMIT 1",
        [param],
    )
    if acc is None:
        return {"rows": [], "total": 0}
    aid = acc["id"]
    summary = {
        "contacts": (one("SELECT COUNT(*) n FROM contacts WHERE account_id = ?", [aid]) or {})["n"],
        "open_opportunities": run(
            "SELECT stage, COUNT(*) AS n, SUM(amount_usd) AS amount_usd FROM opportunities "
            "WHERE account_id = ? AND stage IN ('proposal', 'negotiation') GROUP BY stage",
            [aid],
        ),
        "projects": run(
            "SELECT code, name, status, health, target_date FROM projects WHERE account_id = ?",
            [aid],
        ),
        "invoices": run(
            "SELECT status, COUNT(*) AS n, SUM(amount_usd) AS amount_usd FROM invoices "
            "WHERE account_id = ? GROUP BY status",
            [aid],
        ),
        "open_support_tickets": (
            one(
                "SELECT COUNT(*) n FROM support_tickets "
                "WHERE account_id = ? AND status != 'resolved'",
                [aid],
            )
            or {}
        )["n"],
        "next_meetings": run(
            "SELECT start_at, type, title FROM meetings WHERE start_at >= ? AND "
            "status = 'scheduled' AND (account_id = ? OR opportunity_id IN "
            "(SELECT id FROM opportunities WHERE account_id = ?)) ORDER BY start_at LIMIT 5",
            [db.as_of().isoformat(), aid, aid],
        ),
    }
    return {"total": 1, "rows": [acc], "summary": summary}
