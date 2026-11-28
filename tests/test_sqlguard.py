"""The SQL guard accepts plain SELECTs and rejects everything else."""

from __future__ import annotations

import pytest

from datahub import db
from datahub.sqlguard import SqlRejectedError, run_select


def test_plain_select_and_aggregate_work() -> None:
    result = run_select("SELECT COUNT(*) AS n FROM leads")
    assert result["rows"] == [{"n": 2000}]
    assert result["columns"] == ["n"] and not result["truncated"]


def test_with_cte_and_join_and_trailing_semicolon_work() -> None:
    sql = (
        "WITH big AS (SELECT account_id, SUM(amount_usd) AS s FROM invoices GROUP BY account_id) "
        "SELECT a.name, big.s FROM big JOIN accounts a ON a.id = big.account_id "
        "ORDER BY big.s DESC LIMIT 3;"
    )
    assert run_select(sql)["rowCount"] == 3


def test_rows_are_capped_and_flagged() -> None:
    result = run_select("SELECT id FROM leads")
    assert result["rowCount"] == 200 and result["truncated"] is True


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM leads",
        "UPDATE leads SET score = 0",
        "INSERT INTO leads (id) VALUES (1)",
        "DROP TABLE leads",
        "CREATE TABLE x (a INT)",
        "SELECT 1; DELETE FROM leads",
        "SELECT 1; SELECT 2",
        "PRAGMA table_info(leads)",
        "ATTACH DATABASE 'x.db' AS x",
        "VACUUM",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM sqlite_schema",
        "SELECT load_extension('x')",
        "SELECT readfile('x')",
        "SELECT * FROM leads -- hide",
        "SELECT /* hide */ 1",
        "",
        "   ",
        "EXPLAIN SELECT 1",
        "WITH x AS (SELECT 1) DELETE FROM leads",
        "WITH x AS (SELECT 1) INSERT INTO leads (id) SELECT * FROM x",
        "WITH x AS (SELECT 1) INSERT INTO brand_new SELECT * FROM x",
        "SELECT * FROM pragma_table_info('leads')",
        "SELECT * FROM no_such_table",
    ],
)
def test_adversarial_statements_are_rejected(sql: str) -> None:
    with pytest.raises(SqlRejectedError):
        run_select(sql)


def test_oversize_statement_is_rejected() -> None:
    with pytest.raises(SqlRejectedError, match="too long"):
        run_select("SELECT " + "1," * 1500 + "1")


def test_runaway_recursive_query_times_out() -> None:
    sql = "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r) SELECT COUNT(*) FROM r"
    with pytest.raises(SqlRejectedError, match="too long"):
        run_select(sql, timeout=0.3)


def test_database_is_untouched_after_attacks() -> None:
    for sql in ("DELETE FROM leads", "DROP TABLE leads"):
        with pytest.raises(SqlRejectedError):
            run_select(sql)
    assert db.query("SELECT COUNT(*) AS n FROM leads")[0]["n"] == 2000
