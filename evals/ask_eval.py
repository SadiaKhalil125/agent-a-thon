# ruff: noqa: E501
"""Evaluation set for "Ask the company": real questions, expected facts computed from the database.

Run by hand (it calls the real model and spends budget; CI never runs it):

    python -m evals.ask_eval            # all cases, 4 at a time
    python -m evals.ask_eval 3 7 12     # only these case numbers

Expected facts are read straight from the database with plain SQL here, independently of the
agents' tools, so the check is an honest comparison and not a copy of the tools' own answer.
A case passes when every expected string appears in the answer (commas and "$" ignored), the
answer cites evidence for company questions. Numbers in the answer that match no tool result are\nreported separately ("unmatched numbers"), because they show where the model did its own arithmetic.
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv

from datahub import db
from orchestration.chat_runner import prepare_ask, stream_ask

load_dotenv(".env.local")


def sql(query: str) -> list[dict[str, Any]]:
    return db.query(query)


def scalar(query: str) -> str:
    return str(next(iter(sql(query)[0].values())))


@dataclass
class Case:
    question: str
    expect: Callable[[], list[str]]
    mode: str = "company"
    history: list[tuple[str, str]] = field(default_factory=list)
    any_of: bool = False  # pass if at least one expected string appears


CASES: list[Case] = [
    Case(
        "How many meetings do we have tomorrow?",
        lambda: [
            scalar(
                "SELECT COUNT(*) FROM meetings WHERE substr(start_at,1,10)='2026-12-02' AND status='scheduled'"
            )
        ],
    ),
    Case(
        "How many discovery meetings are scheduled this month?",
        lambda: [
            scalar(
                "SELECT COUNT(*) FROM meetings WHERE type='discovery' AND status='scheduled' AND substr(start_at,1,7)='2026-12'"
            )
        ],
    ),
    Case(
        "How many leads do we have in the CRM in total?",
        lambda: [scalar("SELECT COUNT(*) FROM leads")],
    ),
    Case(
        "How many leads have been won?",
        lambda: [scalar("SELECT COUNT(*) FROM leads WHERE stage='won'")],
    ),
    Case(
        "How many leads are currently in the negotiation stage?",
        lambda: [scalar("SELECT COUNT(*) FROM leads WHERE stage='negotiation'")],
    ),
    Case(
        "How many projects are currently active?",
        lambda: [scalar("SELECT COUNT(*) FROM projects WHERE status='active'")],
    ),
    Case(
        "Which developers are overloaded, meaning allocated above 100 percent?",
        lambda: [
            r["name"]
            for r in sql(
                "SELECT e.name FROM employees e JOIN allocations a ON a.employee_id=e.id GROUP BY e.id HAVING SUM(a.percent)>100 ORDER BY SUM(a.percent) DESC LIMIT 3"
            )
        ],
    ),
    Case(
        "How many invoices are overdue?",
        lambda: [scalar("SELECT COUNT(*) FROM invoices WHERE status='overdue'")],
    ),
    Case(
        "What is the total value of overdue invoices?",
        lambda: [scalar("SELECT SUM(amount_usd) FROM invoices WHERE status='overdue'")],
    ),
    Case(
        "Which customer has the largest single overdue invoice?",
        lambda: [
            scalar(
                "SELECT a.name FROM invoices i JOIN accounts a ON a.id=i.account_id WHERE i.status='overdue' ORDER BY i.amount_usd DESC LIMIT 1"
            )
        ],
    ),
    Case(
        "Which departments went over budget in November 2026?",
        lambda: [
            r["name"]
            for r in sql(
                "SELECT d.name FROM budgets b JOIN departments d ON d.id=b.department_id WHERE b.month='2026-11' AND (SELECT COALESCE(SUM(amount_usd),0) FROM expenses e WHERE e.department_id=b.department_id AND substr(e.date,1,7)=b.month) > b.budget_usd"
            )
        ],
    ),
    Case("What is our total headcount?", lambda: [scalar("SELECT COUNT(*) FROM employees")]),
    Case(
        "How many people work in Engineering?",
        lambda: [
            scalar(
                "SELECT COUNT(*) FROM employees e JOIN departments d ON d.id=e.department_id WHERE d.name='Engineering'"
            )
        ],
    ),
    Case(
        "Who in Engineering is on approved leave on 2 December 2026?",
        lambda: [
            r["name"]
            for r in sql(
                "SELECT e.name FROM leave_requests l JOIN employees e ON e.id=l.employee_id JOIN departments d ON d.id=e.department_id WHERE d.name='Engineering' AND l.status='approved' AND l.start_date<='2026-12-02' AND l.end_date>='2026-12-02' LIMIT 2"
            )
        ],
    ),
    Case(
        "How many support tickets are still open or unresolved?",
        lambda: [scalar("SELECT COUNT(*) FROM support_tickets WHERE status != 'resolved'")],
    ),
    Case(
        "What is the health of the Payment Integration project and who is its customer?",
        lambda: [
            scalar("SELECT health FROM projects WHERE code='PAYINT'").replace("_", " "),
            scalar(
                "SELECT a.name FROM projects p JOIN accounts a ON a.id=p.account_id WHERE p.code='PAYINT'"
            ),
        ],
    ),
    Case(
        "How many open (not done) tickets does Dana Reyes have?",
        lambda: [
            scalar(
                "SELECT COUNT(*) FROM tickets k JOIN employees e ON e.id=k.assignee_id WHERE e.name='Dana Reyes' AND k.status != 'done'"
            )
        ],
    ),
    Case(
        "Which contractor has no project allocations right now?",
        lambda: [
            r["name"]
            for r in sql(
                "SELECT name FROM employees WHERE employment_type='contractor' AND id NOT IN (SELECT employee_id FROM allocations)"
            )
        ],
    ),
    Case(
        "How many roles are currently open for hiring?",
        lambda: [scalar("SELECT COUNT(*) FROM open_roles WHERE status='open'")],
    ),
    Case(
        "How many customer commitments are due before 15 December 2026 and still open?",
        lambda: [
            scalar(
                "SELECT COUNT(*) FROM commitments WHERE status='open' AND due_date < '2026-12-15'"
            )
        ],
    ),
    Case(
        "How much cash did we receive in February 2026?",
        lambda: [
            scalar("SELECT SUM(amount_usd) FROM payments WHERE substr(paid_date,1,7)='2026-02'")
        ],
    ),
    Case(
        "Who leads the Payments team?",
        lambda: [
            scalar(
                "SELECT e.name FROM teams t JOIN employees e ON e.id=t.lead_id WHERE t.name='Payments'"
            )
        ],
    ),
    Case(
        "Which of our projects are for Orbit Retail?",
        lambda: [
            r["name"]
            for r in sql(
                "SELECT p.name FROM projects p JOIN accounts a ON a.id=p.account_id WHERE a.name='Orbit Retail' AND p.status='active'"
            )
        ],
    ),
    Case(
        "Which customer has the most overdue invoices?",
        lambda: [
            scalar(
                "SELECT a.name FROM invoices i JOIN accounts a ON a.id=i.account_id WHERE i.status='overdue' GROUP BY a.id ORDER BY COUNT(*) DESC, a.name LIMIT 1"
            )
        ],
    ),
    Case(
        "and how many of those are discovery calls?",
        lambda: [
            scalar(
                "SELECT COUNT(*) FROM meetings WHERE type='discovery' AND substr(start_at,1,10)='2026-12-02' AND status='scheduled'"
            )
        ],
        history=[
            ("user", "How many meetings do we have tomorrow?"),
            ("assistant", "You have 5 meetings tomorrow (2026-12-02)."),
        ],
    ),
    Case("Write a two-line poem about Mondays.", lambda: [], mode="general"),
    Case(
        "What is our customer NPS score?",
        lambda: ["not", "no ", "don't", "cannot", "unavailable", "isn't", "n't"],
        mode="honest",
        any_of=True,
    ),
]


@dataclass
class Outcome:
    index: int
    question: str
    passed: bool
    reason: str
    clean: bool  # every number in the answer matched a tool result
    seconds: float
    answer: str
    unverified: list[str]
    calls: int


async def run_case(index: int, case: Case, gate: asyncio.Semaphore) -> Outcome:
    async with gate:
        started = time.monotonic()
        answer: dict[str, Any] | None = None
        failure: str | None = None
        try:
            prepared = prepare_ask(case.question, case.history)
            async for event, data in stream_ask(prepared):
                if event == "answer":
                    answer = data
                elif event == "failed":
                    failure = f"{data.get('code')}: {data.get('message')}"
            used = prepared.ctx.tool_budget.snapshot()["used"]
        except Exception as exc:
            failure, used = f"{type(exc).__name__}", 0
        took = time.monotonic() - started
    if answer is None:
        return Outcome(
            index, case.question, False, f"no answer ({failure})", False, took, "", [], used
        )
    text = str(answer["text"]).replace(",", "").replace("$", "")
    unverified = list(answer.get("unverifiedNumbers") or [])
    checks: list[str] = []
    expected = [e.replace(",", "") for e in case.expect()]
    if case.mode == "general":
        if answer["mode"] != "general":
            checks.append("expected a general answer")
    elif case.mode == "honest":
        if not any(e.lower() in text.lower() for e in expected) or answer.get("citations"):
            checks.append("did not clearly say the data is not available")
    else:
        if answer["mode"] != "company":
            checks.append("answered as general")
        missing = [e for e in expected if e.lower() not in text.lower()]
        if missing if not case.any_of else len(missing) == len(expected):
            checks.append("missing " + ", ".join(missing))
        if not answer.get("citations"):
            checks.append("no evidence cited")
    return Outcome(
        index,
        case.question,
        not checks,
        "; ".join(checks) or "ok",
        not unverified,
        took,
        str(answer["text"]),
        unverified,
        used,
    )


async def main(selected: list[int]) -> int:
    gate = asyncio.Semaphore(4)
    picks = [(i, c) for i, c in enumerate(CASES, 1) if not selected or i in selected]
    results = await asyncio.gather(*(run_case(i, c, gate) for i, c in picks))
    for r in sorted(results, key=lambda r: r.index):
        mark = "PASS" if r.passed else "FAIL"
        note = (
            ""
            if r.clean or not r.passed
            else "  (unmatched numbers: " + ", ".join(r.unverified) + ")"
        )
        print(f"[{mark}] {r.index:2d} {r.seconds:4.0f}s tools={r.calls} {r.question}{note}")
        if not r.passed:
            print(f"        -> {r.reason}\n        answer: {r.answer[:300]!r}")
    passed = sum(r.passed for r in results)
    clean = sum(r.passed and r.clean for r in results)
    print(
        f"\n{passed}/{len(results)} passed (right facts, evidence cited); {clean} also had every number matched"
    )
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main([int(a) for a in sys.argv[1:]])))
