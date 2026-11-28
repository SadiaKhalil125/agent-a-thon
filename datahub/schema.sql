-- CompanyTwin "Ask the company" database. Every row is fabricated (fictional Northstar Systems).
-- Dates are ISO text: YYYY-MM-DD for dates, YYYY-MM-DDTHH:MM for timestamps. Money is whole USD.

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- ---------------------------------------------------------------- HR / people
CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);

CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, lead_id INTEGER);

CREATE TABLE employees (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  department_id INTEGER NOT NULL REFERENCES departments(id),
  team_id INTEGER REFERENCES teams(id),
  role TEXT NOT NULL,
  level TEXT NOT NULL,
  manager_id INTEGER REFERENCES employees(id),
  hire_date TEXT NOT NULL,
  employment_type TEXT NOT NULL,         -- employee | contractor
  location TEXT NOT NULL,
  status TEXT NOT NULL,                  -- active | on_leave
  monthly_cost_usd INTEGER NOT NULL
);

CREATE TABLE skills (employee_id INTEGER NOT NULL REFERENCES employees(id), skill TEXT NOT NULL,
  PRIMARY KEY (employee_id, skill));

CREATE TABLE leave_requests (
  id INTEGER PRIMARY KEY,
  employee_id INTEGER NOT NULL REFERENCES employees(id),
  type TEXT NOT NULL,                    -- vacation | sick | medical | parental | unpaid
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  status TEXT NOT NULL,                  -- approved | pending | rejected
  approved_by INTEGER REFERENCES employees(id)
);

CREATE TABLE holidays (date TEXT PRIMARY KEY, name TEXT NOT NULL);

CREATE TABLE open_roles (
  id INTEGER PRIMARY KEY,
  department_id INTEGER NOT NULL REFERENCES departments(id),
  title TEXT NOT NULL,
  level TEXT NOT NULL,
  status TEXT NOT NULL,                  -- open | on_hold | filled
  opened_date TEXT NOT NULL,
  hiring_manager_id INTEGER REFERENCES employees(id)
);

CREATE TABLE candidates (
  id INTEGER PRIMARY KEY,
  role_id INTEGER NOT NULL REFERENCES open_roles(id),
  name TEXT NOT NULL,
  stage TEXT NOT NULL,                   -- applied | screen | interview | offer | hired | rejected
  source TEXT NOT NULL,
  applied_date TEXT NOT NULL
);

-- ---------------------------------------------------------------- CRM / sales
CREATE TABLE accounts (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  industry TEXT NOT NULL,
  region TEXT NOT NULL,
  size_band TEXT NOT NULL,               -- smb | mid_market | enterprise
  status TEXT NOT NULL,                  -- prospect | customer | churned
  owner_id INTEGER REFERENCES employees(id),
  created_date TEXT NOT NULL
);

CREATE TABLE contacts (
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  name TEXT NOT NULL,
  title TEXT NOT NULL,
  email TEXT NOT NULL
);

CREATE TABLE leads (
  id INTEGER PRIMARY KEY,
  company TEXT NOT NULL,
  contact_name TEXT NOT NULL,
  email TEXT NOT NULL,
  source TEXT NOT NULL,                  -- website | referral | event | outbound | partner | webinar
  stage TEXT NOT NULL,                   -- new | contacted | qualified | proposal | negotiation | won | lost
  score INTEGER NOT NULL,                -- 0..100
  est_value_usd INTEGER NOT NULL,
  industry TEXT NOT NULL,
  region TEXT NOT NULL,
  owner_id INTEGER NOT NULL REFERENCES employees(id),
  account_id INTEGER REFERENCES accounts(id),
  created_date TEXT NOT NULL,
  last_activity_date TEXT
);

CREATE TABLE opportunities (
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  lead_id INTEGER REFERENCES leads(id),
  name TEXT NOT NULL,
  stage TEXT NOT NULL,                   -- proposal | negotiation | closed_won | closed_lost
  amount_usd INTEGER NOT NULL,
  probability INTEGER NOT NULL,          -- percent
  owner_id INTEGER NOT NULL REFERENCES employees(id),
  created_date TEXT NOT NULL,
  expected_close_date TEXT NOT NULL
);

CREATE TABLE meetings (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  type TEXT NOT NULL,                    -- discovery | demo | negotiation | qbr | onboarding | internal
  account_id INTEGER REFERENCES accounts(id),
  lead_id INTEGER REFERENCES leads(id),
  opportunity_id INTEGER REFERENCES opportunities(id),
  owner_id INTEGER NOT NULL REFERENCES employees(id),
  start_at TEXT NOT NULL,
  duration_min INTEGER NOT NULL,
  status TEXT NOT NULL,                  -- scheduled | completed | cancelled | no_show
  notes TEXT
);

CREATE TABLE meeting_attendees (
  meeting_id INTEGER NOT NULL REFERENCES meetings(id),
  employee_id INTEGER NOT NULL REFERENCES employees(id),
  PRIMARY KEY (meeting_id, employee_id)
);

CREATE TABLE activities (
  id INTEGER PRIMARY KEY,
  lead_id INTEGER REFERENCES leads(id),
  account_id INTEGER REFERENCES accounts(id),
  owner_id INTEGER NOT NULL REFERENCES employees(id),
  type TEXT NOT NULL,                    -- call | email | note | demo
  date TEXT NOT NULL
);

-- ---------------------------------------------------------------- engineering / delivery
CREATE TABLE projects (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  account_id INTEGER REFERENCES accounts(id),
  team_id INTEGER REFERENCES teams(id),
  manager_id INTEGER REFERENCES employees(id),
  status TEXT NOT NULL,                  -- active | completed | on_hold
  health TEXT NOT NULL,                  -- on_track | at_risk | off_track | done
  start_date TEXT NOT NULL,
  target_date TEXT NOT NULL,
  budget_usd INTEGER NOT NULL,
  description TEXT NOT NULL
);

CREATE TABLE sprints (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  name TEXT NOT NULL,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  status TEXT NOT NULL                   -- completed | active | planned
);

CREATE TABLE tickets (
  id INTEGER PRIMARY KEY,
  key TEXT NOT NULL UNIQUE,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  sprint_id INTEGER REFERENCES sprints(id),
  title TEXT NOT NULL,
  type TEXT NOT NULL,                    -- feature | bug | task | chore
  priority TEXT NOT NULL,                -- low | medium | high | critical
  status TEXT NOT NULL,                  -- todo | in_progress | in_review | blocked | done
  assignee_id INTEGER REFERENCES employees(id),
  estimate_days REAL NOT NULL,
  created_date TEXT NOT NULL,
  due_date TEXT,
  blocked_by_ticket_id INTEGER REFERENCES tickets(id)
);

CREATE TABLE allocations (
  employee_id INTEGER NOT NULL REFERENCES employees(id),
  project_id INTEGER NOT NULL REFERENCES projects(id),
  percent INTEGER NOT NULL,
  PRIMARY KEY (employee_id, project_id)
);

CREATE TABLE contracts (
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  project_id INTEGER REFERENCES projects(id),
  value_usd INTEGER NOT NULL,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  sla_tier TEXT NOT NULL                 -- standard | premium | enterprise
);

CREATE TABLE commitments (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  description TEXT NOT NULL,
  due_date TEXT NOT NULL,
  status TEXT NOT NULL                   -- open | met | missed
);

CREATE TABLE support_tickets (
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  subject TEXT NOT NULL,
  severity TEXT NOT NULL,                -- low | medium | high | critical
  status TEXT NOT NULL,                  -- open | pending | resolved
  opened_date TEXT NOT NULL,
  closed_date TEXT,
  assignee_id INTEGER REFERENCES employees(id)
);

-- ---------------------------------------------------------------- finance
CREATE TABLE invoices (
  id INTEGER PRIMARY KEY,
  number TEXT NOT NULL UNIQUE,
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  project_id INTEGER REFERENCES projects(id),
  amount_usd INTEGER NOT NULL,
  issued_date TEXT NOT NULL,
  due_date TEXT NOT NULL,
  status TEXT NOT NULL,                  -- draft | sent | paid | overdue | void
  paid_date TEXT
);

CREATE TABLE payments (
  id INTEGER PRIMARY KEY,
  invoice_id INTEGER NOT NULL REFERENCES invoices(id),
  amount_usd INTEGER NOT NULL,
  paid_date TEXT NOT NULL,
  method TEXT NOT NULL                   -- wire | card | ach
);

CREATE TABLE vendors (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  status TEXT NOT NULL                   -- active | inactive
);

CREATE TABLE budgets (
  department_id INTEGER NOT NULL REFERENCES departments(id),
  month TEXT NOT NULL,                   -- YYYY-MM
  budget_usd INTEGER NOT NULL,
  PRIMARY KEY (department_id, month)
);

CREATE TABLE expenses (
  id INTEGER PRIMARY KEY,
  department_id INTEGER NOT NULL REFERENCES departments(id),
  vendor_id INTEGER REFERENCES vendors(id),
  date TEXT NOT NULL,
  category TEXT NOT NULL,
  amount_usd INTEGER NOT NULL,
  description TEXT NOT NULL,
  approved_by INTEGER REFERENCES employees(id)
);

CREATE TABLE purchase_orders (
  id INTEGER PRIMARY KEY,
  vendor_id INTEGER NOT NULL REFERENCES vendors(id),
  department_id INTEGER NOT NULL REFERENCES departments(id),
  amount_usd INTEGER NOT NULL,
  status TEXT NOT NULL,                  -- open | received | closed
  created_date TEXT NOT NULL
);

CREATE INDEX idx_leads_stage ON leads(stage);
CREATE INDEX idx_leads_owner ON leads(owner_id);
CREATE INDEX idx_meetings_start ON meetings(start_at);
CREATE INDEX idx_tickets_project ON tickets(project_id);
CREATE INDEX idx_tickets_assignee ON tickets(assignee_id);
CREATE INDEX idx_invoices_account ON invoices(account_id);
CREATE INDEX idx_expenses_dept_date ON expenses(department_id, date);
