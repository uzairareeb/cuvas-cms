# MY CUVAS — Campus Management System (Demo) v0.2

Flask + Jinja, server-rendered. Original design (not a copy of any other portal).
Scope so far: Phase 1 steps 1–3 (v0.1 skeleton, auth/roles, dashboards) plus the
v0.2 foundation — **Step 6: real database layer** and **Step 7: admin CRUD +
students management**.

## Database (Step 6)

One thin data-access layer in `app.py` serves both backends — the app code
writes a single dialect (`?` placeholders, dict-style rows):

- **PostgreSQL** when `DATABASE_URL` is set (psycopg v3; Neon in production)
- **SQLite** otherwise (local dev / demo fallback; file = `DB_PATH` env var,
  else `/tmp/cuvas_demo.db` on Vercel, else `cuvas_demo.db` next to `app.py`)

Schema creation is idempotent on both backends (`CREATE TABLE IF NOT EXISTS`,
plus column migrations for v0.1 databases; `SERIAL` vs `AUTOINCREMENT` handled
in the layer). Demo data is seeded only when the users table is empty.

## Run locally

```bash
cd ~/workspace/cuvas-cms/app
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
# then open http://127.0.0.1:5055/
```

Against PostgreSQL instead: `DATABASE_URL=postgresql://… .venv/bin/python app.py`

## Demo credentials (demo-only, fictional)

| Role    | Username  | Password     |
|---------|-----------|--------------|
| Admin   | `admin`   | `Admin@123`  |
| Student | `student` | `Student@123` |

Students added by the admin (form or Excel import) get their own login:
**username = Registration No**, with an initial password that is shown to the
admin **once** (it is only ever stored hashed). Passwords are hashed with
Werkzeug. All seed data is invented for demonstration — no real people's data.

## Pages

- `/` — public landing page + announcements; `/login`, `/logout`
- `/admin` — dashboard (KPIs from real DB counts: students, departments, programs, pending vouchers)
- `/admin/students` — search (name / reg. no / CNIC), filters (department / program / session), 25 per page
  - `/admin/students/new` — add student (auto-creates the student login)
  - `/admin/students/<id>/edit` — edit (login username = Registration No stays fixed)
  - Reset Password + Delete actions on the list
  - `/admin/students/import` — Excel (.xlsx) import; headers matched **by name**,
    bad rows skipped with reasons, summary + one-time passwords on the result page
  - `/admin/students/template.xlsx` — downloadable import template
  - `/admin/students/export.xlsx` — export of the currently filtered list
- `/admin/departments`, `/admin/programs`, `/admin/sessions`, `/admin/courses` — full CRUD;
  deletes are blocked with an explanation while other records still reference the row
- `/student` — student dashboard (8 tabs) serving the logged-in student's own real record:
  News Feed, Profile, Course Enrollments, Plan Of Study, Transcript (SGPA/CGPA computed),
  Financial Voucher, Fee Plan & Scholarships, Account Statement

## Verification

`verify_v02.py` runs a 45-check scripted pass (CRUD, student lifecycle, Excel
import 3-valid/1-bad, export, delete blocks, role guards) against a **fresh**
database. Run it with `DB_PATH=<fresh file>` (SQLite) or `DATABASE_URL=<uri>`
(PostgreSQL) using the app venv's python. v0.2 result: **ALL PASS on both backends**.

## On Vercel

`vercel.json` is `{}` and `app` in `app.py` is the WSGI entry point (Framework
Preset: Flask). Without `DATABASE_URL`, Vercel uses an ephemeral SQLite DB under
`/tmp` that re-seeds on cold start; set `DATABASE_URL` (Neon) for real data.

## Not in v0.2

Fee-plan → voucher generation & challan PDF, installments, transcript PDF,
documents, tickets, notifications admin, repository, student card PDF,
faculty/dept/accounts/COE portals — later Phase 1 steps (see `../architecture.md`).
