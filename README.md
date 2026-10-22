# MY CUVAS — Campus Management System (Demo) v0.4

Flask + Jinja, server-rendered. Original design (not a copy of any other portal).
Scope so far: Phase 1 steps 1–3 (v0.1 skeleton, auth/roles, dashboards), the
v0.2 foundation (**Step 6: real database layer**, **Step 7: admin CRUD +
students management**) and **Step 8 (v0.3): the working fee system** —
fee heads + fee plans, voucher generation (single + bulk) with sequential
challan numbers, challan PDF (ReportLab), 2-installment splits, paid-proof
upload (stored as a database blob), admin verify/reject, and a real
append-only ledger behind the Account Statement. **Step 9 (v0.4)** adds the
results & exams system — see the v0.4 section below.

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
- `/admin/fee-heads` — fee head CRUD (delete blocked while a head is used in plan lines)
- `/admin/fee-plans` — fee plans per program + session + semester, with fee-head line
  items and computed totals; delete blocked once vouchers exist for the plan
- `/admin/vouchers` — voucher list with status counts and status / program / session /
  search filters
  - `/admin/vouchers/generate` — generate from a fee plan: one selected student, or bulk
    for all eligible (program + session + semester, Active) students; students who
    already have a voucher from the plan are skipped and reported. Challan numbers are
    sequential: `CUVAS-<year>-<seq>`
  - `/admin/vouchers/<id>` — detail: breakdown, paid proof (view/download), **Verify**
    (marks Paid, writes the ledger credit exactly once) / **Reject** (back to Pending,
    remark shown to the student), Create 2 Installments, ledger entries for the voucher
  - `/admin/vouchers/<id>/challan.pdf` — challan PDF
- `/student` — student dashboard (8 tabs) serving the logged-in student's own real record:
  News Feed, Profile, Course Enrollments, Plan Of Study, Transcript (SGPA/CGPA computed),
  Financial Voucher (download challan PDF, create 2 installments, upload paid proof with
  payment channel), Fee Plan & Scholarships (the student's applicable real fee plan),
  Account Statement (real ledger with Total Payable / Paid / Outstanding)

### Fee-system ledger rules

The ledger is **append-only**: a debit entry when a voucher is created, a credit
entry when its payment is verified (guarded — a voucher is credited exactly
once). Splitting a voucher writes a **negative-debit reversal** for the parent
and debits the two children (first = ceil half, second = remainder, due dates =
original and +30 days), so statement totals always equal the sum of payable
voucher amounts. The parent becomes *Split into Installments* and is not
payable. Paid-proof files are stored **in the database** (`proof_blob`,
BYTEA/BLOB) — never on the ephemeral server filesystem.

## Results & Examinations (Step 9, v0.4)

Grades are **derived from obtained marks** through an editable grading scale
(`grade_bands`, seeded: 85+ A 4.00 · 80 A- 3.70 · 75 B+ 3.30 · 70 B 3.00 ·
65 B- 2.70 · 60 C+ 2.30 · 55 C 2.00 · 50 D 1.00 · below 50 F 0.00 — admin →
Grade Scale). One helper derives grade/GP and one computation
(`transcript_data`) drives the student transcript web tab **and** the
transcript PDF, so the numbers always match. Pre-v0.4 seeded results carry no
marks: they keep their stored grade/GP (legacy fallback) and are migrated to
published, keeping the demo transcript (CGPA 3.63) exactly as it was.

- **Admin → Results**: landing lists every result set (course/session/semester)
  with counts + publish state; a marks sheet per course lists the class
  (Active students of program+session, plus anyone already holding a result),
  with marks (0–100), Absent and Clear per row. Saving a result auto-creates
  the student's enrollment for that course if none exists. Sheets can be
  **Published / Unpublished** — students only see published results.
- **Marks Excel**: download the sheet (.xlsx), fill it offline, import it back
  (headers matched by normalised name; unknown reg nos / out-of-range marks
  skip that row with a reason; imported X / skipped Y summary).
- **Transcript PDF**: student (own) + admin per-student — identity block,
  per-semester tables with marks/grade/GP/quality points, SGPA footer and CGPA.
- **Roll number slips**: single (student + admin) and bulk (one PDF page per
  Active student of a program+session+semester) — photo placeholder, identity,
  the semester's course table (enrollments → results → plan of study) and
  generic exam instructions.

## Verification

`verify_v02.py` runs a 45-check scripted pass (CRUD, student lifecycle, Excel
import 3-valid/1-bad, export, delete blocks, role guards) against a **fresh**
database. `verify_v03.py` runs a 52-check pass over the fee system (fee heads /
plans, single + bulk generation with duplicate-skip counts, challan PDF bytes,
installment split maths, proof upload → admin byte-identical download → verify →
statement totals, double-verify guard, reject flow, cross-student guards).
Run either with `DB_PATH=<fresh file>` (SQLite) or `DATABASE_URL=<uri>`
(PostgreSQL) using the app venv's python. v0.3 result: **both suites ALL PASS
on both backends**; v0.1/v0.2-era databases are migrated idempotently at boot
(`backfill_v03`: demo fee plan, ledger↔voucher linking, session repair).
`verify_v04.py` adds a 60-check pass over Step 9 (grade derivation across
bands, marks sheet save/update/clear, publish visibility, SGPA/CGPA
hand-checks, marks Excel round-trip with skipped-row reasons, transcript PDF
CGPA == web CGPA, slip page counts, cross-student guards, demo transcript
intact). v0.4 result: **all three suites ALL PASS on both backends**, and the
v0.4 migration (`backfill_v04`: grade-band seed + legacy results published) is
a no-op on second boot.

## On Vercel

`vercel.json` is `{}` and `app` in `app.py` is the WSGI entry point (Framework
Preset: Flask). Without `DATABASE_URL`, Vercel uses an ephemeral SQLite DB under
`/tmp` that re-seeds on cold start; set `DATABASE_URL` (Neon) for real data.

## Not in v0.4

Documents upload/verification, tickets, notifications admin, repository,
student card PDF, faculty/dept/accounts/COE portals — later Phase 1 steps
(see `../architecture.md`).
