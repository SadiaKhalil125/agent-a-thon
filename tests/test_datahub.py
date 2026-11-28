"""TASK-029: the fabricated company database is deterministic, complete and consistent."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from datahub import db, generate


@pytest.fixture(scope="module")
def conn() -> Iterator[sqlite3.Connection]:
    connection = db.connect()
    yield connection
    connection.close()


def one(conn: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()) -> Any:
    return conn.execute(sql, params).fetchone()[0]


# ---- determinism and freshness --------------------------------------------------------


def test_generator_is_deterministic_and_the_committed_file_is_current(tmp_path: Path) -> None:
    rebuilt = generate.generate(tmp_path / "again.db")
    assert generate.content_hash(rebuilt) == generate.content_hash(db.DB_PATH)


def test_database_is_small_enough_to_ship() -> None:
    assert db.DB_PATH.stat().st_size < 10 * 1024 * 1024


def test_company_today_is_fixed() -> None:
    assert db.as_of() == date(2026, 12, 1)
    assert db.meta("weekday") == "Tuesday"


# ---- volumes the owner asked for ---------------------------------------------------------


def test_volumes(conn: sqlite3.Connection) -> None:
    assert one(conn, "SELECT COUNT(*) FROM leads") == 2000
    assert one(conn, "SELECT COUNT(*) FROM employees") == 120
    assert one(conn, "SELECT COUNT(*) FROM accounts") == 400
    assert one(conn, "SELECT COUNT(*) FROM contacts") >= 1000
    assert one(conn, "SELECT COUNT(*) FROM tickets") >= 1500
    assert one(conn, "SELECT COUNT(*) FROM invoices") >= 800
    assert one(conn, "SELECT COUNT(*) FROM meetings") >= 450


def test_five_meetings_tomorrow(conn: sqlite3.Connection) -> None:
    count = one(
        conn,
        "SELECT COUNT(*) FROM meetings WHERE start_at LIKE '2026-12-02%' AND status = 'scheduled'",
    )
    assert count == 5


def test_twelve_discovery_meetings_this_month(conn: sqlite3.Connection) -> None:
    count = one(
        conn,
        "SELECT COUNT(*) FROM meetings WHERE type = 'discovery' AND start_at LIKE '2026-12%'",
    )
    assert count == 12
    scheduled = one(
        conn,
        "SELECT COUNT(*) FROM meetings WHERE type = 'discovery' AND start_at LIKE '2026-12%' "
        "AND status = 'scheduled'",
    )
    assert scheduled == 12


def test_twelve_active_projects_and_many_developers(conn: sqlite3.Connection) -> None:
    assert one(conn, "SELECT COUNT(*) FROM projects WHERE status = 'active'") == 12
    developers = one(
        conn,
        "SELECT COUNT(*) FROM employees WHERE role IN "
        "('Developer', 'Senior Developer', 'Contract Developer')",
    )
    assert developers >= 36
    assert one(conn, "SELECT COUNT(*) FROM teams") == 6


def test_every_department_has_data(conn: sqlite3.Connection) -> None:
    for dept in (
        "Engineering",
        "Sales",
        "Business Development",
        "Marketing",
        "Human Resources",
        "Finance",
        "Customer Success",
        "Operations",
        "Executive",
    ):
        n = one(
            conn,
            "SELECT COUNT(*) FROM employees e JOIN departments d ON d.id = e.department_id "
            "WHERE d.name = ?",
            (dept,),
        )
        assert n >= 4, dept


# ---- integrity and cross-domain consistency --------------------------------------------


def test_no_foreign_key_violations(conn: sqlite3.Connection) -> None:
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_tickets_are_worked_by_engineering_people(conn: sqlite3.Connection) -> None:
    other = one(
        conn,
        "SELECT COUNT(*) FROM tickets t JOIN employees e ON e.id = t.assignee_id "
        "JOIN departments d ON d.id = e.department_id WHERE d.name != 'Engineering'",
    )
    assert other == 0


def test_project_invoices_belong_to_the_project_account(conn: sqlite3.Connection) -> None:
    bad = one(
        conn,
        "SELECT COUNT(*) FROM invoices i JOIN projects p ON p.id = i.project_id "
        "WHERE i.account_id != p.account_id",
    )
    assert bad == 0


def test_paid_invoices_are_fully_paid_and_overdue_ones_really_are(
    conn: sqlite3.Connection,
) -> None:
    short = one(
        conn,
        "SELECT COUNT(*) FROM invoices i WHERE status = 'paid' AND amount_usd != "
        "(SELECT COALESCE(SUM(amount_usd), 0) FROM payments p WHERE p.invoice_id = i.id)",
    )
    assert short == 0
    assert (
        one(
            conn,
            "SELECT COUNT(*) FROM invoices WHERE status = 'overdue' AND due_date >= '2026-12-01'",
        )
        == 0
    )
    assert one(conn, "SELECT COUNT(*) FROM invoices WHERE status = 'overdue'") > 10
    assert (
        one(conn, "SELECT COUNT(*) FROM invoices WHERE status = 'sent' AND due_date < '2026-12-01'")
        == 0
    )


def test_the_past_is_finished_and_the_future_is_scheduled(conn: sqlite3.Connection) -> None:
    assert (
        one(
            conn,
            "SELECT COUNT(*) FROM meetings WHERE start_at < '2026-12-01' AND status = 'scheduled'",
        )
        == 0
    )
    assert (
        one(
            conn,
            "SELECT COUNT(*) FROM meetings "
            "WHERE start_at >= '2026-12-02' AND status != 'scheduled'",
        )
        == 0
    )
    assert (
        one(
            conn,
            "SELECT COUNT(*) FROM meetings "
            "WHERE type = 'discovery' AND start_at LIKE '2026-12-01%'",
        )
        == 0
    )


def test_some_developers_are_overloaded_and_the_contractor_is_free(
    conn: sqlite3.Connection,
) -> None:
    over = conn.execute(
        "SELECT employee_id, SUM(percent) p FROM allocations GROUP BY employee_id HAVING p > 100"
    ).fetchall()
    assert len(over) >= 5
    free = one(
        conn,
        "SELECT COUNT(*) FROM allocations a JOIN employees e ON e.id = a.employee_id "
        "WHERE e.employment_type = 'contractor'",
    )
    assert free == 0


def test_blocked_tickets_say_what_blocks_them(conn: sqlite3.Connection) -> None:
    assert one(conn, "SELECT COUNT(*) FROM tickets WHERE status = 'blocked'") > 10
    assert (
        one(
            conn,
            "SELECT COUNT(*) FROM tickets "
            "WHERE status = 'blocked' AND blocked_by_ticket_id IS NULL",
        )
        == 0
    )


def test_over_budget_months_exist_for_questions(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT b.department_id, b.month FROM budgets b JOIN expenses e "
        "ON e.department_id = b.department_id AND substr(e.date, 1, 7) = b.month "
        "GROUP BY b.department_id, b.month HAVING SUM(e.amount_usd) > b.budget_usd"
    ).fetchall()
    assert len(rows) >= 3


def test_people_on_leave_match_the_leave_table(conn: sqlite3.Connection) -> None:
    mismatch = one(
        conn,
        "SELECT COUNT(*) FROM employees e WHERE (e.status = 'on_leave') != (e.id IN "
        "(SELECT employee_id FROM leave_requests WHERE status = 'approved' "
        "AND start_date <= '2026-12-01' AND end_date >= '2026-12-01'))",
    )
    assert mismatch == 0


# ---- anchors that tie this database to the recovery demo --------------------------------


def test_recovery_demo_anchors_are_present(conn: sqlite3.Connection) -> None:
    people = dict(conn.execute("SELECT name, role FROM employees").fetchall())
    assert people["Dana Reyes"] == "Senior Developer"
    assert people["Marcus Lee"] == "Developer"
    assert people["Quinn Okafor"] == "QA Engineer"
    assert people["Priya Nair"] == "Contract Developer"
    accounts = {r[0] for r in conn.execute("SELECT name FROM accounts")}
    assert {"Orbit Retail", "Harbor Logistics"} <= accounts
    keys = {r[0] for r in conn.execute("SELECT key FROM tickets WHERE key LIKE 'NS-%'")}
    assert keys == {"NS-142", "NS-143", "NS-150", "NS-151"}
    leave = conn.execute(
        "SELECT l.start_date, l.end_date, l.status FROM leave_requests l JOIN employees e "
        "ON e.id = l.employee_id WHERE e.name = 'Dana Reyes' AND l.start_date >= '2026-12-01'"
    ).fetchall()
    assert [tuple(r) for r in leave] == [("2026-12-02", "2026-12-08", "approved")]


# ---- fabricated and read-only -------------------------------------------------------------


def test_every_email_is_on_a_reserved_example_domain(conn: sqlite3.Connection) -> None:
    for table in ("employees", "contacts", "leads"):
        bad = one(conn, f"SELECT COUNT(*) FROM {table} WHERE email NOT LIKE '%example.com'")  # noqa: S608
        assert bad == 0, table


def test_the_connection_cannot_write(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("UPDATE leads SET stage = 'won'")
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DROP TABLE leads")


def test_missing_database_is_reported(tmp_path: Path) -> None:
    with pytest.raises(db.DatabaseMissingError):
        db.connect(tmp_path / "nope.db")
