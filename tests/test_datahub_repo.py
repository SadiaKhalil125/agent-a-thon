"""Repository functions return fixed, known answers against the committed fabricated database."""

from __future__ import annotations

import pytest

from datahub import dictionary
from datahub.repo import calendar as cal
from datahub.repo import crm, engineering, finance, hr
from datahub.repo.common import BadArgumentError


def test_crm_counts_and_filters() -> None:
    assert crm.count_leads()["total"] == 2000
    assert crm.search_leads(stage="won")["total"] == 126
    by_stage = {r["stage"]: r["leads"] for r in crm.count_leads()["rows"]}
    assert sum(by_stage.values()) == 2000
    assert len(crm.search_leads(limit=5)["rows"]) == 5


def test_crm_meetings_tomorrow_and_discovery_this_month() -> None:
    tomorrow = crm.list_meetings(date_from="2026-12-02", date_to="2026-12-02", status="scheduled")
    assert tomorrow["total"] == 5
    discovery = crm.list_meetings(date_from="2026-12-01", date_to="2026-12-31", type="discovery")
    assert discovery["total"] == 12


def test_crm_pipeline_and_account() -> None:
    stages = {r["stage"] for r in crm.pipeline_summary()["rows"]}
    assert {"proposal", "negotiation", "closed_won"} <= stages
    orbit = crm.account_overview("Orbit Retail")
    assert orbit["rows"][0]["name"] == "Orbit Retail"
    assert "projects" in orbit["summary"]


def test_engineering_projects_tickets_workload() -> None:
    assert engineering.list_projects(status="active")["total"] == 12
    assert engineering.project_detail("PAYINT")["rows"][0]["customer"] == "Orbit Retail"
    assert engineering.search_tickets(overdue=True)["total"] > 0
    overloaded = engineering.workload(overloaded_only=True)
    assert overloaded["total"] >= 5
    assert all(r["allocated_percent"] > 100 for r in overloaded["rows"])
    assert any(r["name"] == "Dana Reyes" for r in overloaded["rows"])
    assert engineering.teams_overview()["total"] == 6
    assert engineering.commitments()["total"] > 0


def test_hr_headcount_leave_hiring() -> None:
    assert hr.headcount()["total"] == 120
    assert {r["department"]: r["people"] for r in hr.headcount()["rows"]}["Engineering"] == 50
    assert hr.headcount("role")["total"] == 120
    leave = hr.leave_in_range(
        date_from="2026-12-02", date_to="2026-12-08", department="Engineering"
    )
    assert any(r["name"] == "Dana Reyes" and r["type"] == "medical" for r in leave["rows"])
    assert hr.find_employees(skill="kubernetes")["total"] > 0
    assert hr.hiring_pipeline()["total"] == 25


def test_finance_receivables_budgets_expenses() -> None:
    overdue = finance.invoices(status="overdue")
    assert overdue["total"] == 43
    assert all(r["days_overdue"] > 0 for r in overdue["rows"])
    summary = finance.receivables_summary()
    assert {r["status"]: r["invoices"] for r in summary["rows"]}["overdue"] == 43
    assert sum(b["invoices"] for b in summary["summary"]["overdue_aging"]) == 43
    over = finance.budget_vs_actual(only_over=True)
    assert any(r["department"] == "Engineering" and r["month"] == "2026-11" for r in over["rows"])
    assert all(r["variance_usd"] > 0 for r in over["rows"])
    assert finance.revenue_by_month()["total"] == 13
    for group in ("category", "vendor", "department"):
        assert finance.expenses_summary(group_by=group)["rows"]


def test_calendar_availability_and_overview() -> None:
    dana = cal.availability("Dana Reyes", "2026-12-01", "2026-12-14")["rows"][0]
    assert dana["working_days_in_range"] == 10
    assert dana["days_on_leave"] == 5
    assert dana["available_days"] == 5
    overview = cal.company_overview()["rows"][0]
    assert overview["today"] == "2026-12-01" and overview["leads"] == 2000
    with pytest.raises(BadArgumentError):
        cal.availability("Dana", "2026-12-10", "2026-12-01")


def test_bad_enum_argument_is_rejected_not_interpolated() -> None:
    with pytest.raises(BadArgumentError):
        crm.count_leads(group_by="stage; DROP TABLE leads")
    with pytest.raises(BadArgumentError):
        finance.invoices(status="paid' OR '1'='1")


def test_dictionary_covers_every_table() -> None:
    names = dictionary.table_names()
    assert len(names) == 29 and "leads" in names
    text = dictionary.describe_schema()
    assert "Northstar" in text and all(f"CREATE TABLE {n} " in text for n in names)
    assert "Unknown table" in dictionary.describe_schema("nope")
