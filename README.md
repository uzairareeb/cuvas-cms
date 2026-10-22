# MY CUVAS — Campus Management System (Demo) v0.1

Flask + Jinja, server-rendered, SQLite demo build. Original design (not a copy of any other portal).
Scope: Phase 1 build-order steps 1–3 only — skeleton + auth/roles, admin shell + dashboards,
Departments/Programs pages, and a student dashboard with 8 tabs, all from seeded **fictional demo data**.

## Run locally

```bash
cd ~/workspace/cuvas-cms/app
python3 -m venv .venv
.venv/bin/pip install flask
.venv/bin/python app.py
# then open http://127.0.0.1:5055/
```

Or with the Flask CLI:

```bash
FLASK_APP=app .venv/bin/flask run --port 5055
```

The SQLite database `cuvas_demo.db` is created and seeded automatically on first run.
Delete that file and restart to reset the demo data.

## On Vercel

`vercel.json` is `{}` (same pattern as the other CUVAS Flask portals) and `app` in
`app.py` is the WSGI entry point. Because Vercel's filesystem is read-only and
ephemeral, when the `VERCEL` env var is present the demo database is created and
seeded under `/tmp` instead of next to `app.py`; demo data simply re-seeds on a
cold start. (`DB_PATH` env var overrides the location when set.)

## Demo credentials (demo-only, fictional)

| Role    | Username  | Password     |
|---------|-----------|--------------|
| Admin   | `admin`   | `Admin@123`  |
| Student | `student` | `Student@123` |

Passwords are stored hashed (Werkzeug). Seed students, departments ("… (Demo)"),
courses, vouchers, transcript and ledger entries are all invented for demonstration —
no real people's data and no data from any external account.

## Pages

- `/` — public landing page: "MY CUVAS — Campus Management System (Demo)" + login link
- `/login`, `/logout`
- `/admin` — admin dashboard (KPI cards: students, departments, programs, pending vouchers)
- `/admin/departments`, `/admin/programs`
- `/student` — student dashboard tabs: News Feed, Profile, Course Enrollments,
  Plan Of Study, Transcript (SGPA/CGPA computed), Financial Voucher (Paid + Pending),
  Fee Plan & Scholarships, Account Statement

## Not in v0.1

CRUD/forms, fee-voucher generation & challan PDF, transcript PDF, documents, tickets,
notifications admin, repository, student card PDF, faculty/dept/accounts/COE portals,
Postgres — these come in later Phase 1 steps (see `../architecture.md`).
