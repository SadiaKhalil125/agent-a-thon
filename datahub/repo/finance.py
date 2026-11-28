"""Finance: invoices, receivables, budgets, expenses, revenue."""

from __future__ import annotations

from typing import Any

from datahub import db
from datahub.repo.common import Where, choice, clamp, run

INVOICE_STATUS = ("draft", "sent", "paid", "overdue", "void")


def invoices(
    status: str | None = None,
    account: str | None = None,
    min_amount: int | None = None,
    issued_from: str | None = None,
    issued_to: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Invoices matching the filters, largest first, with days overdue where relevant."""
    w = Where()
    w.eq("i.status", choice(status, INVOICE_STATUS, "status"))
    w.like("a.name", account)
    w.cmp("i.amount_usd", ">=", min_amount)
    w.cmp("i.issued_date", ">=", issued_from)
    w.cmp("i.issued_date", "<=", issued_to)
    today = db.as_of().isoformat()
    total = run(
        "SELECT COUNT(*) AS n FROM invoices i JOIN accounts a ON a.id = i.account_id" + w.sql,  # noqa: S608
        w.params,
    )[0]["n"]
    # The `today` parameter comes before the WHERE parameters in the statement.
    rows = run(
        "SELECT i.number, a.name AS account, p.code AS project, i.amount_usd, i.status, "  # noqa: S608
        "i.issued_date, i.due_date, i.paid_date, CASE WHEN i.status = 'overdue' THEN "
        "CAST(julianday(?) - julianday(i.due_date) AS INTEGER) END AS days_overdue "
        "FROM invoices i JOIN accounts a ON a.id = i.account_id "
        f"LEFT JOIN projects p ON p.id = i.project_id{w.sql} "
        "ORDER BY i.amount_usd DESC, i.id LIMIT ?",
        [today, *w.params, clamp(limit)],
    )
    return {"total": total, "rows": rows}


def receivables_summary() -> dict[str, Any]:
    """Money by invoice status plus overdue aging buckets."""
    today = db.as_of().isoformat()
    by_status = run(
        "SELECT status, COUNT(*) AS invoices, SUM(amount_usd) AS amount_usd FROM invoices "
        "GROUP BY status ORDER BY amount_usd DESC"
    )
    aging = run(
        "SELECT CASE WHEN d <= 30 THEN '1-30 days' WHEN d <= 60 THEN '31-60 days' "
        "WHEN d <= 90 THEN '61-90 days' ELSE 'over 90 days' END AS bucket, "
        "COUNT(*) AS invoices, SUM(amount_usd) AS amount_usd FROM ("
        "SELECT amount_usd, CAST(julianday(?) - julianday(due_date) AS INTEGER) AS d "
        "FROM invoices WHERE status = 'overdue') GROUP BY bucket ORDER BY MIN(d)",
        [today],
    )
    return {"rows": by_status, "summary": {"overdue_aging": aging}}


def budget_vs_actual(
    department: str | None = None, month: str | None = None, only_over: bool = False
) -> dict[str, Any]:
    """Budget, actual spend and variance per department and month (month is YYYY-MM)."""
    w = Where()
    w.like("d.name", department)
    w.eq("b.month", month)
    outer = " WHERE actual_usd > budget_usd" if only_over else ""
    rows = run(
        "SELECT * FROM (SELECT d.name AS department, b.month, b.budget_usd, "
        "COALESCE((SELECT SUM(amount_usd) FROM expenses e WHERE e.department_id = b.department_id "
        "AND substr(e.date, 1, 7) = b.month), 0) AS actual_usd "
        f"FROM budgets b JOIN departments d ON d.id = b.department_id{w.sql}){outer} "  # noqa: S608
        "ORDER BY month DESC, department LIMIT 200",
        w.params,
    )
    for r in rows:
        r["variance_usd"] = r["actual_usd"] - r["budget_usd"]
    return {"total": len(rows), "rows": rows}


def revenue_by_month() -> dict[str, Any]:
    """Cash received per month (sum of payments)."""
    rows = run(
        "SELECT substr(paid_date, 1, 7) AS month, COUNT(*) AS payments, SUM(amount_usd) "
        "AS received_usd FROM payments GROUP BY month ORDER BY month"
    )
    return {"total": len(rows), "rows": rows}


def expenses_summary(
    department: str | None = None, month: str | None = None, group_by: str = "category"
) -> dict[str, Any]:
    """Spend per category or vendor, optionally for one department and month."""
    group = choice(group_by, ("category", "vendor", "department"), "group_by") or "category"
    expr = {"category": "e.category", "vendor": "v.name", "department": "d.name"}[group]
    w = Where()
    w.like("d.name", department)
    w.eq("substr(e.date, 1, 7)", month)
    rows = run(
        f"SELECT {expr} AS {group}, COUNT(*) AS items, SUM(e.amount_usd) AS spend_usd "  # noqa: S608
        "FROM expenses e JOIN departments d ON d.id = e.department_id "
        f"LEFT JOIN vendors v ON v.id = e.vendor_id{w.sql} "
        f"GROUP BY {expr} ORDER BY spend_usd DESC LIMIT 50",
        w.params,
    )
    return {"total": len(rows), "rows": rows}
