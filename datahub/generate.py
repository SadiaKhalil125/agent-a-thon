"""Deterministic generator for the fabricated company database (ADR-006).

    python -m datahub.generate          # rewrites data/company/northstar.db

Same seed, same content: tests compare a hash of the logical content. Standard library only.
Everything is fabricated; emails use example.com. The company's "today" is `AS_OF` (a Tuesday).
"""

from __future__ import annotations

import hashlib
import random
import sqlite3
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from datahub import pools

AS_OF = date(2026, 12, 1)
SEED = 20261201
ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DB_PATH = ROOT / "data" / "company" / "northstar.db"

TOMORROW = AS_OF + timedelta(days=1)
HOLIDAYS = [
    ("2026-01-01", "New Year's Day"),
    ("2026-05-25", "Spring Bank Holiday"),
    ("2026-07-03", "Summer Day"),
    ("2026-09-07", "Labour Day"),
    ("2026-11-26", "Thanksgiving"),
    ("2026-12-25", "Winter Holiday"),
    ("2027-01-01", "New Year's Day"),
]
DEPARTMENTS = [
    (1, "Engineering"),
    (2, "Sales"),
    (3, "Business Development"),
    (4, "Marketing"),
    (5, "Human Resources"),
    (6, "Finance"),
    (7, "Customer Success"),
    (8, "Operations"),
    (9, "Executive"),
]
DEPT_ID = {name: i for i, name in DEPARTMENTS}
TEAMS = ["Platform", "Payments", "Billing", "Mobile", "Data", "Web"]
# (code, name, team, account, health, status)
ACTIVE_PROJECTS = [
    ("SSO", "Single Sign-On Rollout", "Platform", None, "on_track"),
    ("APIGW", "Partner API Gateway", "Platform", None, "at_risk"),
    ("PAYINT", "Project A: Payment Integration", "Payments", "Orbit Retail", "at_risk"),
    ("LOYALTY", "Project C: Loyalty API Add-on", "Payments", "Orbit Retail", "at_risk"),
    ("BILLFIX", "Project B: Billing Hotfix", "Billing", "Harbor Logistics", "on_track"),
    ("RECON", "Invoice Reconciliation Engine", "Billing", None, "off_track"),
    ("MOBCO", "Mobile Checkout App", "Mobile", None, "on_track"),
    ("FIELD", "Field Service App", "Mobile", None, "on_track"),
    ("DWH", "Data Warehouse Migration", "Data", None, "at_risk"),
    ("FRAUD", "Fraud Detection Pipeline", "Data", None, "on_track"),
    ("PORTAL", "Customer Portal Revamp", "Web", None, "off_track"),
    ("ANALYT", "Analytics Dashboard", "Web", None, "on_track"),
]
COMPLETED_PROJECTS = [
    ("CRMMIG", "CRM Migration", "Platform"),
    ("SEARCH", "Search Upgrade", "Web"),
    ("NOTIF", "Notification Service", "Platform"),
    ("EXPORT", "Bulk Export Tool", "Data"),
    ("AUDIT", "Audit Logging", "Billing"),
    ("I18N", "Localisation Support", "Web"),
    ("PERF", "Performance Tuning", "Platform"),
    ("LEGACY", "Legacy API Retirement", "Payments"),
    ("BACKUP", "Backup and Restore", "Data"),
    ("ONBRD", "Customer Onboarding Flow", "Mobile"),
]
ONHOLD_PROJECTS = [
    ("AIASST", "AI Assistant Pilot", "Data"),
    ("KIOSK", "Retail Kiosk App", "Mobile"),
]

Row = tuple[Any, ...]


def iso(d: date | datetime) -> str:
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%dT%H:%M")
    return d.strftime("%Y-%m-%d")


def month_of(d: date) -> str:
    return d.strftime("%Y-%m")


class Builder:
    """Holds the RNG and every generated table, so cross-links stay consistent."""

    def __init__(self) -> None:
        self.rng = random.Random(SEED)
        self.used_names: set[str] = set()
        self.used_emails: set[str] = set()
        self.t: dict[str, list[Row]] = {}
        self.emp: list[dict[str, Any]] = []
        self.accounts: list[dict[str, Any]] = []
        self.leads: list[dict[str, Any]] = []
        self.opps: list[dict[str, Any]] = []
        self.projects: list[dict[str, Any]] = []
        self.holiday_dates = {h[0] for h in HOLIDAYS}
        self.team_id = {name: i + 1 for i, name in enumerate(TEAMS)}

    # ---------------------------------------------------------------- helpers
    def pick(self, seq: Sequence[Any]) -> Any:
        return seq[self.rng.randrange(len(seq))]

    def wpick(self, options: Sequence[tuple[Any, float]]) -> Any:
        return self.rng.choices([o[0] for o in options], weights=[o[1] for o in options])[0]

    def person_name(self, unique: bool = True) -> str:
        """A fabricated full name. Employees are unique; contacts and candidates may repeat."""
        while True:
            name = f"{self.pick(pools.FIRST)} {self.pick(pools.LAST)}"
            if not unique:
                return name
            if name not in self.used_names:
                self.used_names.add(name)
                return name

    def email(self, name: str, domain: str = "example.com") -> str:
        base = name.lower().replace(" ", ".")
        email = f"{base}@{domain}"
        n = 2
        while email in self.used_emails:
            email = f"{base}{n}@{domain}"
            n += 1
        self.used_emails.add(email)
        return email

    def weekday(self, start: date, end: date) -> date:
        for _ in range(60):
            d = start + timedelta(days=self.rng.randint(0, (end - start).days))
            if d.weekday() < 5 and iso(d) not in self.holiday_dates:
                return d
        return start

    def when(self, d: date, earliest: int = 9, latest: int = 16) -> datetime:
        hour = self.rng.randint(earliest, latest)
        return datetime(d.year, d.month, d.day, hour, self.pick([0, 30]))

    def add(self, table: str, row: Row) -> None:
        self.t.setdefault(table, []).append(row)

    # ---------------------------------------------------------------- people
    def add_employee(
        self,
        name: str,
        dept: str,
        role: str,
        level: str,
        manager: int | None,
        *,
        team: str | None = None,
        etype: str = "employee",
        email: str | None = None,
        hire: date | None = None,
    ) -> int:
        eid = len(self.emp) + 1
        cost = {
            "Junior": 6500,
            "Mid": 9000,
            "Senior": 12500,
            "Staff": 15500,
            "Lead": 14500,
            "Manager": 13500,
            "Director": 18000,
            "Executive": 26000,
        }[level]
        if etype == "contractor":
            cost = 11000
        hire = hire or AS_OF - timedelta(days=self.rng.randint(60, 2600))
        record = {
            "id": eid,
            "name": name,
            "dept": dept,
            "role": role,
            "level": level,
            "team": team,
            "etype": etype,
            "manager": manager,
        }
        self.emp.append(record)
        if email:
            self.used_emails.add(email)
        else:
            email = self.email(name)
        self.add(
            "employees",
            (
                eid,
                name,
                email,
                DEPT_ID[dept],
                self.team_id[team] if team else None,
                role,
                level,
                manager,
                iso(hire),
                etype,
                self.pick(pools.LOCATIONS),
                "active",
                cost,
            ),
        )
        return eid

    def build_people(self) -> None:
        for i, name in DEPARTMENTS:
            self.add("departments", (i, name))
        for i, name in enumerate(TEAMS, start=1):
            self.add("teams", (i, name, None))
        # Anchor names first so no random employee collides with them.
        for n in ("Dana Reyes", "Marcus Lee", "Quinn Okafor", "Priya Nair", "Noor Haddad"):
            self.used_names.add(n)
        ceo = self.add_employee(self.person_name(), "Executive", "CEO", "Executive", None)
        cto = self.add_employee(self.person_name(), "Executive", "CTO", "Executive", ceo)
        coo = self.add_employee(self.person_name(), "Executive", "COO", "Executive", ceo)
        self.add_employee(self.person_name(), "Executive", "Chief of Staff", "Director", ceo)
        self.heads = {"Executive": ceo}
        # Engineering: VP, 6 team leads, 36 developers (4 anchors), 7 QA.
        vp = self.add_employee(self.person_name(), "Engineering", "VP Engineering", "Director", cto)
        self.heads["Engineering"] = vp
        lead_ids: dict[str, int] = {}
        for team in TEAMS:
            lead_ids[team] = self.add_employee(
                self.person_name(), "Engineering", "Engineering Lead", "Lead", vp, team=team
            )
        self.team_lead = lead_ids
        dev_plan: dict[str, list[str | None]] = {t: [None] * 6 for t in TEAMS}
        dev_plan["Payments"][0:2] = ["Dana Reyes", "Priya Nair"]
        dev_plan["Billing"][0] = "Marcus Lee"
        self.devs: list[int] = []
        for team in TEAMS:
            for slot in dev_plan[team]:
                if slot == "Dana Reyes":
                    eid = self.add_employee(
                        slot, "Engineering", "Senior Developer", "Senior", lead_ids[team], team=team
                    )
                elif slot == "Priya Nair":
                    eid = self.add_employee(
                        slot,
                        "Engineering",
                        "Contract Developer",
                        "Mid",
                        lead_ids[team],
                        team=team,
                        etype="contractor",
                    )
                elif slot == "Marcus Lee":
                    eid = self.add_employee(
                        slot, "Engineering", "Developer", "Mid", lead_ids[team], team=team
                    )
                else:
                    level = self.wpick([("Junior", 2), ("Mid", 4), ("Senior", 3), ("Staff", 1)])
                    role = "Senior Developer" if level in ("Senior", "Staff") else "Developer"
                    eid = self.add_employee(
                        self.person_name(), "Engineering", role, level, lead_ids[team], team=team
                    )
                self.devs.append(eid)
        qa_teams = ["Payments", "Payments", "Billing", "Mobile", "Data", "Web", "Platform"]
        for i, team in enumerate(qa_teams):
            name = "Quinn Okafor" if i == 0 else self.person_name()
            eid = self.add_employee(
                name, "Engineering", "QA Engineer", "Mid", lead_ids[team], team=team
            )
            self.devs.append(eid)
        # Other departments.
        layout = {
            "Sales": (
                "VP Sales",
                [("Account Executive", 10), ("Sales Development Rep", 5), ("Sales Engineer", 2)],
            ),
            "Business Development": ("Business Development Lead", [("BD Manager", 7)]),
            "Marketing": ("Head of Marketing", [("Marketing Manager", 4), ("Content Lead", 3)]),
            "Human Resources": ("Head of People", [("HR Partner", 3), ("Recruiter", 2)]),
            "Finance": ("Finance Director", [("Accountant", 4), ("Financial Analyst", 3)]),
            "Customer Success": ("Head of Customer Success", [("Customer Success Manager", 9)]),
            "Operations": (
                "Head of Operations",
                [("Operations Analyst", 4), ("IT Support", 2), ("Office Manager", 1)],
            ),
        }
        reports_to = {"Sales": coo, "Business Development": coo}
        for dept, (head_role, roles) in layout.items():
            hname = "Noor Haddad" if dept == "Business Development" else self.person_name()
            head = self.add_employee(
                hname,
                dept,
                head_role,
                "Director",
                reports_to.get(dept, coo),
                email="bd.lead@example.com" if dept == "Business Development" else None,
            )
            self.heads[dept] = head
            for role, count in roles:
                for _ in range(count):
                    level = "Senior" if role in ("Account Executive", "Finance Manager") else "Mid"
                    self.add_employee(self.person_name(), dept, role, level, head)
        for team, lead in lead_ids.items():
            self.t["teams"][self.team_id[team] - 1] = (self.team_id[team], team, lead)
        # Skills.
        fixed = {
            "Dana Reyes": ["integration", "backend", "payments"],
            "Marcus Lee": ["integration", "backend"],
            "Priya Nair": ["integration", "backend"],
            "Quinn Okafor": ["qa"],
        }
        for e in self.emp:
            if e["dept"] != "Engineering":
                continue
            if e["name"] in fixed:
                skills = fixed[e["name"]]
            elif e["role"] == "QA Engineer":
                skills = ["qa", self.pick(pools.SKILLS)]
            else:
                skills = sorted(set(self.rng.sample(pools.SKILLS, self.rng.randint(2, 4))))
            for s in skills:
                self.add("skills", (e["id"], s))

    def ids(self, dept: str, *roles: str) -> list[int]:
        return [
            e["id"] for e in self.emp if e["dept"] == dept and (not roles or e["role"] in roles)
        ]

    # ---------------------------------------------------------------- HR extras
    def build_hr(self) -> None:
        for h in HOLIDAYS:
            self.add("holidays", h)
        employees = [e["id"] for e in self.emp]
        leave_id = 0
        dana = next(e["id"] for e in self.emp if e["name"] == "Dana Reyes")
        rows: list[Row] = []

        def leave(eid: int, kind: str, start: date, days: int, status: str) -> None:
            nonlocal leave_id
            leave_id += 1
            end = start
            left = days - 1
            while left > 0:
                end += timedelta(days=1)
                if end.weekday() < 5:
                    left -= 1
            approver = self.heads.get(self.emp[eid - 1]["dept"], self.heads["Executive"])
            rows.append((leave_id, eid, kind, iso(start), iso(end), status, approver))

        leave(dana, "medical", date(2026, 12, 2), 5, "approved")
        for _ in range(230):
            eid = self.pick(employees)
            if self.emp[eid - 1]["name"] == "Dana Reyes":
                continue
            start = self.weekday(AS_OF - timedelta(days=330), AS_OF + timedelta(days=45))
            kind = self.wpick(
                [("vacation", 60), ("sick", 25), ("medical", 6), ("parental", 4), ("unpaid", 5)]
            )
            days = {
                "vacation": self.rng.randint(2, 10),
                "sick": self.rng.randint(1, 4),
                "medical": self.rng.randint(3, 12),
                "parental": self.rng.randint(10, 25),
                "unpaid": self.rng.randint(1, 5),
            }[kind]
            status = (
                "approved"
                if start < AS_OF
                else self.wpick([("approved", 60), ("pending", 38), ("rejected", 2)])
            )
            leave(eid, kind, start, days, status)
        # A realistic cluster of upcoming leave among developers.
        for eid in self.rng.sample(self.devs, 9):
            if eid != dana:
                leave(
                    eid,
                    "vacation",
                    self.weekday(date(2026, 12, 7), date(2026, 12, 23)),
                    self.rng.randint(3, 8),
                    "approved",
                )
        for r in rows:
            self.add("leave_requests", r)
        on_leave = {r[1] for r in rows if r[5] == "approved" and r[3] <= iso(AS_OF) <= r[4]}
        self.on_leave = on_leave
        # Recruiting.
        role_titles = {
            "Engineering": [
                "Backend Developer",
                "Frontend Developer",
                "QA Engineer",
                "DevOps Engineer",
            ],
            "Sales": ["Account Executive", "Sales Engineer"],
            "Marketing": ["Content Marketer"],
            "Customer Success": ["Customer Success Manager"],
            "Finance": ["Financial Analyst"],
            "Operations": ["IT Support"],
        }
        role_id = 0
        for dept, titles in role_titles.items():
            copies = 10 if dept == "Engineering" else 3
            for i in range(copies):
                role_id += 1
                title = titles[i % len(titles)]
                status = (
                    "filled" if role_id % 6 == 0 else ("on_hold" if role_id % 9 == 0 else "open")
                )
                opened = AS_OF - timedelta(days=self.rng.randint(5, 150))
                self.add(
                    "open_roles",
                    (
                        role_id,
                        DEPT_ID[dept],
                        title,
                        self.pick(["Mid", "Senior", "Junior"]),
                        status,
                        iso(opened),
                        self.heads.get(dept),
                    ),
                )
        cand = 0
        for rid in range(1, role_id + 1):
            for _ in range(self.rng.randint(5, 14)):
                cand += 1
                stage = self.wpick(
                    [
                        ("applied", 30),
                        ("screen", 25),
                        ("interview", 20),
                        ("offer", 5),
                        ("hired", 5),
                        ("rejected", 15),
                    ]
                )
                self.add(
                    "candidates",
                    (
                        cand,
                        rid,
                        self.person_name(unique=False),
                        stage,
                        self.pick(pools.LEAD_SOURCES),
                        iso(AS_OF - timedelta(days=self.rng.randint(1, 120))),
                    ),
                )

    # ---------------------------------------------------------------- CRM
    def company_name(self) -> str:
        while True:
            name = (
                f"{self.pick(pools.COMPANY_ADJ)} {self.pick(pools.COMPANY_NOUN)} "
                f"{self.pick(pools.COMPANY_SUFFIX)}"
            )
            if name not in self.used_names:
                self.used_names.add(name)
                return name

    def build_crm(self) -> None:
        sellers = self.ids("Sales", "Account Executive", "Sales Development Rep")
        bd = self.ids("Business Development", "BD Manager")
        csms = self.ids("Customer Success", "Customer Success Manager")
        self.lead_owners = sellers + bd
        # Accounts: 140 customers (2 anchors), 30 churned, 230 prospects.
        for i in range(400):
            if i == 0:
                name, status = "Orbit Retail", "customer"
            elif i == 1:
                name, status = "Harbor Logistics", "customer"
            else:
                name = self.company_name()
                status = "customer" if i < 140 else ("churned" if i < 170 else "prospect")
            industry = (
                "Retail" if i == 0 else "Logistics" if i == 1 else self.pick(pools.INDUSTRIES)
            )
            owner = self.pick(csms if status == "customer" else sellers)
            created = AS_OF - timedelta(days=self.rng.randint(30, 1100))
            acc = {"id": i + 1, "name": name, "status": status}
            self.accounts.append(acc)
            self.add(
                "accounts",
                (
                    i + 1,
                    name,
                    industry,
                    self.pick(pools.REGIONS),
                    self.wpick([("smb", 50), ("mid_market", 35), ("enterprise", 15)]),
                    status,
                    owner,
                    iso(created),
                ),
            )
        titles = [
            "CTO",
            "VP Operations",
            "Head of IT",
            "Procurement Manager",
            "CFO",
            "Product Director",
        ]
        for cid in range(1, 1501):
            acc = self.accounts[self.rng.randrange(len(self.accounts))]
            name = self.person_name(unique=False)
            slug = str(acc["name"]).lower().replace(" ", "")
            self.add(
                "contacts",
                (cid, acc["id"], name, self.pick(titles), self.email(name, f"{slug}.example.com")),
            )
        # Leads.
        stages = [
            ("new", 36),
            ("contacted", 22),
            ("qualified", 15),
            ("proposal", 9),
            ("negotiation", 6),
            ("won", 6),
            ("lost", 6),
        ]
        score_base = {
            "new": 25,
            "contacted": 40,
            "qualified": 65,
            "proposal": 75,
            "negotiation": 82,
            "won": 90,
            "lost": 30,
        }
        non_churned = [a for a in self.accounts if a["status"] != "churned"]
        for lid in range(1, 2001):
            stage = self.wpick(stages)
            created = AS_OF - timedelta(days=self.rng.randint(1, 540))
            last = created + timedelta(days=self.rng.randint(0, max(0, (AS_OF - created).days)))
            company = self.company_name()
            contact = self.person_name(unique=False)
            value = int(round(self.rng.lognormvariate(9.9, 0.8) / 500) * 500)
            value = max(2000, min(value, 400000))
            account = (
                self.pick(non_churned)["id"]
                if stage in ("proposal", "negotiation", "won")
                else None
            )
            lead = {
                "id": lid,
                "stage": stage,
                "company": company,
                "owner": self.pick(self.lead_owners),
                "account": account,
                "value": value,
                "created": created,
            }
            self.leads.append(lead)
            self.add(
                "leads",
                (
                    lid,
                    company,
                    contact,
                    self.email(contact, f"{company.split()[0].lower()}.example.com"),
                    self.pick(pools.LEAD_SOURCES),
                    stage,
                    max(0, min(100, score_base[stage] + self.rng.randint(-15, 15))),
                    value,
                    self.pick(pools.INDUSTRIES),
                    self.pick(pools.REGIONS),
                    lead["owner"],
                    account,
                    iso(created),
                    iso(last),
                ),
            )
        # Opportunities from late-stage leads.
        oid = 0
        for lead in self.leads:
            if lead["stage"] not in ("proposal", "negotiation", "won"):
                continue
            oid += 1
            stage = "closed_won" if lead["stage"] == "won" else lead["stage"]
            prob = {"proposal": 30, "negotiation": 60, "closed_won": 100}[stage]
            if stage == "closed_won":
                close = AS_OF - timedelta(days=self.rng.randint(1, 200))
            else:
                close = AS_OF + timedelta(days=self.rng.randint(5, 90))
            opp = {"id": oid, "stage": stage, "account": lead["account"], "owner": lead["owner"]}
            self.opps.append(opp)
            self.add(
                "opportunities",
                (
                    oid,
                    lead["account"],
                    lead["id"],
                    f"{lead['company']} platform deal",
                    stage,
                    lead["value"],
                    prob,
                    lead["owner"],
                    iso(max(lead["created"], close - timedelta(days=120))),
                    iso(close),
                ),
            )
        self.build_meetings(sellers, bd, csms)
        act = 0
        for _ in range(3000):
            act += 1
            use_lead = self.rng.random() < 0.7
            self.add(
                "activities",
                (
                    act,
                    self.pick(self.leads)["id"] if use_lead else None,
                    None if use_lead else self.pick(self.accounts)["id"],
                    self.pick(self.lead_owners),
                    self.pick(["call", "email", "email", "note", "demo"]),
                    iso(AS_OF - timedelta(days=self.rng.randint(0, 270))),
                ),
            )

    def build_meetings(self, sellers: list[int], bd: list[int], csms: list[int]) -> None:
        sales_eng = self.ids("Sales", "Sales Engineer")
        early = [lead for lead in self.leads if lead["stage"] in ("new", "contacted", "qualified")]
        qualified = [lead for lead in self.leads if lead["stage"] == "qualified"]
        customers = [a for a in self.accounts if a["status"] == "customer"]
        negotiating = [o for o in self.opps if o["stage"] == "negotiation"]
        mid = [o for o in self.opps if o["stage"] in ("proposal", "negotiation")]
        mid_id = 0
        titles = {
            "discovery": "Discovery call",
            "demo": "Product demo",
            "negotiation": "Commercial negotiation",
            "qbr": "Quarterly business review",
            "onboarding": "Onboarding kickoff",
            "internal": "Pipeline review",
        }

        def make(kind: str, start: datetime, status: str) -> None:
            nonlocal mid_id
            mid_id += 1
            lead = acc = opp = None
            owner = self.pick(sellers + bd)
            label = "Northstar"
            if kind == "discovery":
                lead_row = self.pick(early)
                lead, owner, label = lead_row["id"], lead_row["owner"], lead_row["company"]
            elif kind == "demo":
                lead_row = self.pick(qualified)
                lead, owner, label = lead_row["id"], lead_row["owner"], lead_row["company"]
            elif kind == "negotiation":
                opp_row = self.pick(negotiating)
                opp, acc, owner = opp_row["id"], opp_row["account"], opp_row["owner"]
                label = self.accounts[acc - 1]["name"]
            elif kind in ("qbr", "onboarding"):
                acc_row = self.pick(customers)
                acc, owner = acc_row["id"], self.pick(csms)
                label = acc_row["name"]
            notes = (
                None
                if status == "scheduled"
                else self.pick(
                    [
                        "Good fit, next step agreed.",
                        "Needs budget approval.",
                        "Asked for a proposal.",
                        "Technical questions pending.",
                        "Positive, follow up next week.",
                    ]
                )
            )
            self.add(
                "meetings",
                (
                    mid_id,
                    f"{titles[kind]} with {label}",
                    kind,
                    acc,
                    lead,
                    opp,
                    owner,
                    iso(start),
                    self.pick([30, 45, 60]),
                    status,
                    notes,
                ),
            )
            attendees = {owner}
            if kind in ("demo", "discovery") and sales_eng and self.rng.random() < 0.6:
                attendees.add(self.pick(sales_eng))
            if self.rng.random() < 0.4:
                attendees.add(self.pick(sellers + bd))
            for a in sorted(attendees):
                self.add("meeting_attendees", (mid_id, a))

        kinds = [
            ("discovery", 30),
            ("demo", 25),
            ("negotiation", 12),
            ("qbr", 15),
            ("onboarding", 8),
            ("internal", 10),
        ]
        for _ in range(420):  # past, strictly before "today"
            kind = self.wpick(kinds)
            if kind == "negotiation" and not mid:
                kind = "demo"
            day = self.weekday(AS_OF - timedelta(days=365), AS_OF - timedelta(days=1))
            status = self.wpick([("completed", 88), ("no_show", 5), ("cancelled", 7)])
            make(kind, self.when(day), status)
        non_discovery = [(k, w) for k, w in kinds if k != "discovery"]
        for i in range(4):  # today: no discovery, so the December discovery count stays exact
            make(
                self.wpick(non_discovery),
                self.when(AS_OF, 9 if i < 2 else 13, 11 if i < 2 else 17),
                "completed" if i < 2 else "scheduled",
            )
        for kind in ("discovery", "discovery", "demo", "qbr", "negotiation"):  # tomorrow: exactly 5
            make(kind, self.when(TOMORROW), "scheduled")
        for _ in range(10):  # the other 10 discovery meetings of December
            make(
                "discovery",
                self.when(self.weekday(date(2026, 12, 3), date(2026, 12, 31))),
                "scheduled",
            )
        for _ in range(6):  # January discovery meetings (distractors for "this month")
            make(
                "discovery",
                self.when(self.weekday(date(2027, 1, 4), date(2027, 1, 29))),
                "scheduled",
            )
        for _ in range(40):  # other upcoming meetings, never discovery
            make(
                self.wpick(non_discovery),
                self.when(self.weekday(date(2026, 12, 3), date(2027, 1, 29))),
                "scheduled",
            )

    # ---------------------------------------------------------------- engineering
    def build_engineering(self) -> None:
        customers = [a for a in self.accounts if a["status"] == "customer"]
        acc_by_name = {a["name"]: a["id"] for a in self.accounts}
        pid = 0

        def add_project(
            code: str,
            name: str,
            team: str,
            account: int | None,
            status: str,
            health: str,
            start: date,
            target: date,
            budget: int,
        ) -> None:
            nonlocal pid
            pid += 1
            acc = {
                "id": pid,
                "code": code,
                "team": team,
                "status": status,
                "account": account,
                "start": start,
                "target": target,
            }
            self.projects.append(acc)
            self.add(
                "projects",
                (
                    pid,
                    code,
                    name,
                    account,
                    self.team_id[team],
                    self.team_lead[team],
                    status,
                    health,
                    iso(start),
                    iso(target),
                    budget,
                    f"{name} for {team} team.",
                ),
            )

        anchor_dates = {
            "PAYINT": date(2026, 12, 9),
            "BILLFIX": date(2026, 12, 4),
            "LOYALTY": date(2026, 12, 11),
        }
        for code, name, team, account_name, health in ACTIVE_PROJECTS:
            account = acc_by_name[account_name] if account_name else self.pick(customers)["id"]
            start = AS_OF - timedelta(days=self.rng.randint(40, 220))
            target = anchor_dates.get(code, AS_OF + timedelta(days=self.rng.randint(20, 150)))
            add_project(
                code,
                name,
                team,
                account,
                "active",
                health,
                start,
                target,
                self.rng.randint(8, 90) * 10000,
            )
        for code, name, team in COMPLETED_PROJECTS:
            end = AS_OF - timedelta(days=self.rng.randint(20, 300))
            add_project(
                code,
                name,
                team,
                self.pick(customers)["id"],
                "completed",
                "done",
                end - timedelta(days=self.rng.randint(60, 200)),
                end,
                self.rng.randint(5, 60) * 10000,
            )
        for code, name, team in ONHOLD_PROJECTS:
            add_project(
                code,
                name,
                team,
                None,
                "on_hold",
                "at_risk",
                AS_OF - timedelta(days=150),
                AS_OF + timedelta(days=120),
                self.rng.randint(5, 30) * 10000,
            )
        self.build_allocations()
        self.build_tickets()
        # Contracts, commitments and support.
        cid = 0
        by_account_project = {
            p["account"]: p["id"] for p in self.projects if p["status"] == "active"
        }
        for a in self.accounts:
            if a["status"] != "customer":
                continue
            cid += 1
            start = AS_OF - timedelta(days=self.rng.randint(60, 700))
            self.add(
                "contracts",
                (
                    cid,
                    a["id"],
                    by_account_project.get(a["id"]),
                    self.rng.randint(20, 600) * 1000,
                    iso(start),
                    iso(start + timedelta(days=self.rng.choice([365, 540, 730]))),
                    self.wpick([("standard", 55), ("premium", 33), ("enterprise", 12)]),
                ),
            )
        commit = 0
        fixed = {
            "PAYINT": ("Orbit Retail go-live of the payment integration", date(2026, 12, 9)),
            "BILLFIX": ("Harbor Logistics billing hotfix delivered", date(2026, 12, 4)),
            "LOYALTY": ("Orbit Retail loyalty API add-on delivered", date(2026, 12, 11)),
        }
        for p in self.projects:
            if p["status"] == "active":
                for i in range(2):
                    commit += 1
                    text, due = fixed.get(
                        p["code"],
                        (
                            f"{p['code']} milestone {i + 1} accepted",
                            AS_OF + timedelta(days=self.rng.randint(7, 70)),
                        ),
                    )
                    if p["code"] in fixed and i == 1:
                        text, due = (f"{p['code']} acceptance sign-off", due + timedelta(days=5))
                    self.add("commitments", (commit, p["id"], p["account"], text, iso(due), "open"))
            elif p["status"] == "completed":
                commit += 1
                self.add(
                    "commitments",
                    (
                        commit,
                        p["id"],
                        p["account"],
                        f"{p['code']} delivered",
                        iso(p["target"]),
                        self.wpick([("met", 90), ("missed", 10)]),
                    ),
                )
        ops = self.ids("Customer Success", "Customer Success Manager") + self.ids(
            "Operations", "IT Support"
        )
        subjects = [
            "Login failures",
            "Report is slow",
            "Data export error",
            "Billing question",
            "Feature request",
            "Integration timeout",
            "Access request",
            "Wrong totals",
        ]
        customer_ids = [a["id"] for a in self.accounts if a["status"] == "customer"]
        for sid in range(1, 601):
            opened = AS_OF - timedelta(days=self.rng.randint(0, 240))
            status = self.wpick([("resolved", 70), ("open", 20), ("pending", 10)])
            closed = (
                opened + timedelta(days=self.rng.randint(0, 20)) if status == "resolved" else None
            )
            if closed and closed > AS_OF:
                closed = AS_OF
            self.add(
                "support_tickets",
                (
                    sid,
                    self.pick(customer_ids),
                    self.pick(subjects),
                    self.wpick([("low", 35), ("medium", 40), ("high", 20), ("critical", 5)]),
                    status,
                    iso(opened),
                    iso(closed) if closed else None,
                    self.pick(ops),
                ),
            )

    def build_allocations(self) -> None:
        by_team: dict[str, list[dict[str, Any]]] = {}
        for p in self.projects:
            if p["status"] == "active":
                by_team.setdefault(p["team"], []).append(p)
        by_code = {p["code"]: p for p in self.projects}
        name_to_id = {e["name"]: e["id"] for e in self.emp}
        overloaded = set(
            self.rng.sample(
                [
                    d
                    for d in self.devs
                    if d
                    not in (
                        name_to_id["Priya Nair"],
                        name_to_id["Quinn Okafor"],
                        name_to_id["Marcus Lee"],
                        name_to_id["Dana Reyes"],
                    )
                ],
                5,
            )
        )
        overloaded.add(name_to_id["Dana Reyes"])
        self.alloc: dict[int, dict[int, int]] = {}
        for eid in self.devs:
            e = self.emp[eid - 1]
            if e["etype"] == "contractor":
                continue  # the contractor is deliberately free
            projects = by_team[e["team"]]
            total = (
                self.rng.choice([115, 120, 130, 140])
                if eid in overloaded
                else self.rng.choice([70, 80, 90, 100, 100])
            )
            first = round(total * self.rng.choice([0.5, 0.6, 0.7]) / 10) * 10
            shares = {projects[0]["id"]: first, projects[1]["id"]: total - first}
            if e["role"] != "QA Engineer" and self.rng.random() < 0.35:
                other = self.pick(
                    [p for p in self.projects if p["status"] == "active" and p["team"] != e["team"]]
                )
                shares[projects[1]["id"]] = max(10, shares[projects[1]["id"]] - 20)
                shares[other["id"]] = 20
            self.alloc[eid] = shares
        marcus = name_to_id["Marcus Lee"]
        self.alloc[marcus] = {by_code["BILLFIX"]["id"]: 60, by_code["PAYINT"]["id"]: 30}
        dana = name_to_id["Dana Reyes"]
        self.alloc[dana] = {by_code["PAYINT"]["id"]: 70, by_code["LOYALTY"]["id"]: 50}
        for eid, shares in self.alloc.items():
            for project_id, percent in sorted(shares.items()):
                self.add("allocations", (eid, project_id, percent))

    def build_tickets(self) -> None:
        tid = 0
        ticket_rows: dict[int, list[int]] = {}
        sprint_id = 0
        name_to_id = {e["name"]: e["id"] for e in self.emp}
        done_statuses = [
            ("done", 42),
            ("in_review", 7),
            ("in_progress", 16),
            ("blocked", 5),
            ("todo", 30),
        ]

        def staff(project_id: int) -> tuple[list[int], list[int]]:
            people = [(e, s[project_id]) for e, s in sorted(self.alloc.items()) if project_id in s]
            return [p[0] for p in people], [p[1] for p in people]

        for project in self.projects:
            code, status = project["code"], project["status"]
            sprints: list[tuple[int, str]] = []
            if status == "active":
                cur_start = AS_OF - timedelta(days=self.rng.randint(0, 10))
                for k in range(-5, 2):
                    sprint_id += 1
                    start = cur_start + timedelta(days=14 * k)
                    state = "completed" if k < 0 else ("active" if k == 0 else "planned")
                    self.add(
                        "sprints",
                        (
                            sprint_id,
                            project["id"],
                            f"Sprint {k + 6}",
                            iso(start),
                            iso(start + timedelta(days=13)),
                            state,
                        ),
                    )
                    sprints.append((sprint_id, state))
            people, weights = staff(project["id"])
            count = {"active": 85, "completed": 45, "on_hold": 30}[status]
            ticket_rows[project["id"]] = []
            for n in range(1, count + 1):
                tid += 1
                if status == "completed":
                    st = "done"
                elif status == "on_hold":
                    st = self.wpick([("done", 50), ("todo", 40), ("in_progress", 10)])
                else:
                    st = self.wpick(done_statuses)
                sprint = None
                if sprints:
                    done_sp = [s for s, state in sprints if state == "completed"]
                    active_sp = [s for s, state in sprints if state == "active"]
                    planned_sp = [s for s, state in sprints if state == "planned"]
                    if st == "done":
                        sprint = self.pick(done_sp if self.rng.random() < 0.7 else active_sp)
                    elif st == "todo":
                        sprint = self.pick(planned_sp) if self.rng.random() < 0.6 else None
                    else:
                        sprint = active_sp[0]
                assignee = None
                if st != "todo" or self.rng.random() < 0.5:
                    assignee = (
                        self.rng.choices(people, weights=weights)[0]
                        if people
                        else self.pick(self.devs)
                    )
                created = AS_OF - timedelta(days=self.rng.randint(1, 150))
                due = None
                if status == "active" and st != "done":
                    due = AS_OF + timedelta(days=self.rng.randint(1, 20))
                    if st == "in_progress" and self.rng.random() < 0.15:
                        due = AS_OF - timedelta(days=self.rng.randint(1, 10))
                key = f"{code}-{n}"
                title = f"{self.pick(pools.TICKET_VERBS)} {self.pick(pools.TICKET_OBJECTS)}"
                row = [
                    tid,
                    key,
                    project["id"],
                    sprint,
                    title,
                    self.wpick([("feature", 40), ("bug", 30), ("task", 22), ("chore", 8)]),
                    self.wpick([("low", 25), ("medium", 50), ("high", 20), ("critical", 5)]),
                    st,
                    assignee,
                    float(self.pick([0.5, 1, 1, 2, 2, 3, 5, 8])),
                    iso(created),
                    iso(due) if due else None,
                    None,
                ]
                ticket_rows[project["id"]].append(tid)
                self.add("tickets", tuple(row))
        # Anchor storyline tickets (replace generated ones so keys match the recovery demo).
        anchors = {
            "PAYINT-1": (
                "NS-142",
                "Payment gateway integration",
                "in_progress",
                name_to_id["Dana Reyes"],
                4.0,
                date(2026, 12, 5),
            ),
            "PAYINT-2": (
                "NS-143",
                "Integration QA and acceptance testing",
                "todo",
                name_to_id["Quinn Okafor"],
                2.0,
                date(2026, 12, 9),
            ),
            "BILLFIX-1": (
                "NS-150",
                "Billing hotfix",
                "in_progress",
                name_to_id["Marcus Lee"],
                2.0,
                date(2026, 12, 3),
            ),
            "LOYALTY-1": (
                "NS-151",
                "Loyalty API add-on",
                "todo",
                name_to_id["Dana Reyes"],
                5.0,
                date(2026, 12, 11),
            ),
        }
        fixed_rows: list[Row] = []
        for trow in self.t["tickets"]:
            if trow[1] in anchors:
                nkey, title, st, assignee, est, due = anchors[trow[1]]
                trow = (
                    trow[0],
                    nkey,
                    trow[2],
                    trow[3],
                    title,
                    "feature",
                    "high",
                    st,
                    assignee,
                    est,
                    trow[10],
                    iso(due),
                    None,
                )
            fixed_rows.append(trow)
        self.t["tickets"] = fixed_rows
        # Blocked tickets point at an unfinished ticket of the same project.
        final: list[Row] = []
        by_project: dict[int, list[Row]] = {}
        for trow in self.t["tickets"]:
            by_project.setdefault(trow[2], []).append(trow)
        for trow in self.t["tickets"]:
            if trow[7] == "blocked":
                open_ones = [
                    r
                    for r in by_project[trow[2]]
                    if r[7] in ("todo", "in_progress") and r[0] != trow[0]
                ]
                trow = (*trow[:12], self.pick(open_ones)[0] if open_ones else None)
            final.append(trow)
        self.t["tickets"] = final

    # ---------------------------------------------------------------- finance
    def build_finance(self) -> None:
        for vid in range(1, 41):
            self.add(
                "vendors",
                (
                    vid,
                    f"{self.company_name()} (vendor)",
                    self.pick(
                        [
                            "cloud",
                            "software",
                            "agency",
                            "hardware",
                            "legal",
                            "recruiting",
                            "facilities",
                        ]
                    ),
                    "active" if vid % 9 else "inactive",
                ),
            )
        customers = [a["id"] for a in self.accounts if a["status"] != "prospect"]
        active_projects = [
            p
            for p in self.projects
            if p["status"] in ("active", "completed") and p["account"] is not None
        ]
        start = AS_OF - timedelta(days=364)
        plan: list[tuple[date, int, int | None]] = []
        for _ in range(800):
            issued = start + timedelta(days=self.rng.randint(0, 363))
            if self.rng.random() < 0.35:
                p = self.pick(active_projects)
                plan.append((issued, p["account"], p["id"]))
            else:
                plan.append((issued, self.pick(customers), None))
        plan.sort(key=lambda x: x[0])
        pay_id = 0
        for n, (issued, account, project) in enumerate(plan, start=1):
            amount = int(round(self.rng.lognormvariate(9.3, 0.9) / 250) * 250)
            amount = max(1000, min(amount, 120000))
            due = issued + timedelta(days=30)
            number = f"INV-{issued.year}-{n:04d}"
            outcome = self.rng.random()
            paid_date = None
            if outcome < 0.02:
                status = "void"
            elif outcome < (0.8 if (AS_OF - issued).days <= 90 else 0.975):
                paid_date = due + timedelta(days=self.rng.randint(-10, 15))
                if paid_date > AS_OF:
                    paid_date, status = None, "sent"
                else:
                    paid_date = max(paid_date, issued + timedelta(days=1))
                    status = "paid"
            else:
                status = "overdue" if due < AS_OF else "sent"
            if status == "sent" and due < AS_OF:
                status = "overdue"
            self.add(
                "invoices",
                (
                    n,
                    number,
                    account,
                    project,
                    amount,
                    iso(issued),
                    iso(due),
                    status,
                    iso(paid_date) if paid_date else None,
                ),
            )
            if status == "paid" and paid_date:
                parts = [amount] if self.rng.random() < 0.85 else [amount * 6 // 10]
                if len(parts) == 2 or parts[0] != amount:
                    parts.append(amount - parts[0])
                for i, part in enumerate(parts):
                    pay_id += 1
                    when = (
                        paid_date
                        if i == len(parts) - 1
                        else max(issued, paid_date - timedelta(days=9))
                    )
                    self.add(
                        "payments",
                        (
                            pay_id,
                            n,
                            part,
                            iso(when),
                            self.wpick([("wire", 45), ("ach", 35), ("card", 20)]),
                        ),
                    )
        # Draft invoices tied to the two recovery-demo milestones.
        n = len(plan)
        by_code = {p["code"]: p for p in self.projects}
        for k, (code, amount) in enumerate((("PAYINT", 8000), ("LOYALTY", 6000)), start=1):
            p = by_code[code]
            self.add(
                "invoices",
                (
                    n + k,
                    f"INV-DRAFT-{code}",
                    p["account"],
                    p["id"],
                    amount,
                    iso(AS_OF),
                    iso(AS_OF + timedelta(days=30)),
                    "draft",
                    None,
                ),
            )
        # Budgets, expenses, purchase orders.
        base = {
            "Engineering": 160000,
            "Sales": 70000,
            "Business Development": 40000,
            "Marketing": 90000,
            "Human Resources": 25000,
            "Finance": 20000,
            "Customer Success": 30000,
            "Operations": 45000,
            "Executive": 35000,
        }
        months = [date(2025, 12, 1)] + [date(2026, m, 1) for m in range(1, 13)]
        exp_id = 0
        for dept_id, dept in DEPARTMENTS:
            head = self.heads.get(dept, self.heads["Executive"])
            for m in months:
                key = month_of(m)
                budget = int(base[dept] * (1 + self.rng.uniform(-0.04, 0.04)) // 1000 * 1000)
                self.add("budgets", (dept_id, key, budget))
                if m > AS_OF:
                    continue
                partial = m.year == AS_OF.year and m.month == AS_OF.month
                factor = self.rng.gauss(0.92, 0.06)
                if dept == "Marketing" and key in ("2026-08", "2026-09", "2026-10"):
                    factor = self.rng.uniform(1.12, 1.22)
                if dept == "Engineering" and key == "2026-11":
                    factor = 1.09
                actual = int(budget * (0.04 if partial else max(0.6, factor)))
                items = 1 if partial else self.rng.randint(14, 26)
                weights = [self.rng.random() + 0.2 for _ in range(items)]
                amounts = [max(1, int(actual * w / sum(weights))) for w in weights]
                amounts[-1] += actual - sum(amounts)
                last_day = 1 if partial else 28
                for amt in amounts:
                    exp_id += 1
                    cat = self.pick(pools.EXPENSE_CATEGORIES[dept])
                    when = date(m.year, m.month, self.rng.randint(1, last_day))
                    self.add(
                        "expenses",
                        (
                            exp_id,
                            dept_id,
                            self.rng.randint(1, 40),
                            iso(when),
                            cat,
                            amt,
                            f"{cat} ({dept})",
                            head,
                        ),
                    )
        for po in range(1, 121):
            dept_id = self.pick(DEPARTMENTS)[0]
            self.add(
                "purchase_orders",
                (
                    po,
                    self.rng.randint(1, 40),
                    dept_id,
                    self.rng.randint(2, 80) * 500,
                    self.wpick([("open", 30), ("received", 30), ("closed", 40)]),
                    iso(AS_OF - timedelta(days=self.rng.randint(1, 300))),
                ),
            )

    # ---------------------------------------------------------------- output
    def build(self) -> None:
        self.build_people()
        self.build_hr()
        self.build_crm()
        self.build_engineering()
        self.build_finance()


TABLE_ORDER = [
    "meta",
    "departments",
    "teams",
    "employees",
    "skills",
    "leave_requests",
    "holidays",
    "open_roles",
    "candidates",
    "accounts",
    "contacts",
    "leads",
    "opportunities",
    "meetings",
    "meeting_attendees",
    "activities",
    "projects",
    "sprints",
    "tickets",
    "allocations",
    "contracts",
    "commitments",
    "support_tickets",
    "invoices",
    "payments",
    "vendors",
    "budgets",
    "expenses",
    "purchase_orders",
]


def generate(path: Path | None = None) -> Path:
    """Build the database file and return its path."""
    target = path or DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    b = Builder()
    b.build()
    meta = [
        ("company", "Northstar Systems (fictional)"),
        ("as_of", iso(AS_OF)),
        ("weekday", AS_OF.strftime("%A")),
        ("currency", "USD"),
        ("note", "All data is fabricated for the SSI Agent-A-Thon demo. Emails use example.com."),
        ("schema_version", "1"),
    ]
    for kv in meta:
        b.add("meta", kv)
    conn = sqlite3.connect(target)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute("PRAGMA foreign_keys = OFF")  # self-references load out of order; checked below
    for table in TABLE_ORDER:
        rows = b.t.get(table, [])
        if not rows:
            continue
        marks = ",".join("?" * len(rows[0]))
        conn.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)  # noqa: S608
    # Employees on approved leave today are marked, so "who is out" matches the leave table.
    conn.execute(
        "UPDATE employees SET status = 'on_leave' WHERE id IN (SELECT employee_id FROM "
        "leave_requests WHERE status = 'approved' AND start_date <= ? AND end_date >= ?)",
        (iso(AS_OF), iso(AS_OF)),
    )
    conn.commit()
    broken = conn.execute("PRAGMA foreign_key_check").fetchall()
    if broken:
        conn.close()
        raise RuntimeError(f"foreign key violations: {broken[:5]}")
    conn.execute("VACUUM")
    conn.close()
    return target


def content_hash(path: Path | None = None) -> str:
    """Hash of the logical content (not the file bytes, which vary with the SQLite version)."""
    conn = sqlite3.connect(path or DB_PATH)
    try:
        digest = hashlib.sha256()
        for line in conn.iterdump():
            digest.update(line.encode("utf-8"))
        return digest.hexdigest()
    finally:
        conn.close()


def main() -> None:
    path = generate()
    conn = sqlite3.connect(path)
    for table in TABLE_ORDER:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
        print(f"{table:20s} {count:6d}")
    conn.close()
    print(f"\n{path} ({path.stat().st_size / 1024:.0f} KB)  content hash {content_hash(path)[:16]}")


if __name__ == "__main__":
    main()
