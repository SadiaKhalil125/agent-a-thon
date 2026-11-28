"""Data dictionary for the agents: what each table holds, taken from schema.sql itself."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

OVERVIEW = """\
Company: Northstar Systems (fictional). All data is fabricated. Money is whole USD.
Dates are ISO text (YYYY-MM-DD; timestamps YYYY-MM-DDTHH:MM). The company's "today" is stored in
meta (key as_of); "tomorrow" is the next day, "this month" is the calendar month of today.
Ids are integers; join on the *_id columns. Departments: Engineering, Sales, Business
Development, Marketing, Human Resources, Finance, Customer Success, Operations, Executive.
Areas: HR (employees, skills, leave_requests, holidays, open_roles, candidates, departments, teams),
CRM/sales (accounts, contacts, leads, opportunities, meetings, meeting_attendees, activities),
engineering/delivery (projects, sprints, tickets, allocations, contracts, commitments,
support_tickets), finance (invoices, payments, budgets, expenses, vendors, purchase_orders).
Useful facts: allocations.percent per person can exceed 100 in total (overloaded); a developer
with no allocations is free; an invoice is overdue when status = 'overdue'; a project's customer is
projects.account_id; meetings.status 'scheduled' means still to happen.
"""


@lru_cache(maxsize=1)
def _tables() -> dict[str, str]:
    text = SCHEMA_PATH.read_text(encoding="utf-8")
    found: dict[str, str] = {}
    for match in re.finditer(r"CREATE TABLE (\w+) \((.*?)\n?\);", text, flags=re.S):
        found[match.group(1)] = f"CREATE TABLE {match.group(1)} ({match.group(2).rstrip()}\n);"
    return found


def table_names() -> list[str]:
    return sorted(_tables())


def describe_schema(table: str | None = None) -> str:
    """Overview plus CREATE TABLE text (value hints are in its comments) for one or all tables."""
    tables = _tables()
    if table is not None:
        if table not in tables:
            return f"Unknown table '{table}'. Tables: {', '.join(table_names())}"
        return tables[table]
    return OVERVIEW + "\n" + "\n\n".join(tables[name] for name in tables)
