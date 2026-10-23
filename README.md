# MY CUVAS — Campus Management System (Demo) v0.9

Flask + Jinja, server-rendered. Original design (not a copy of any other portal).
Scope so far: Phase 1 steps 1–3 (v0.1 skeleton, auth/roles, dashboards), the
v0.2 foundation (**Step 6: real database layer**, **Step 7: admin CRUD +
students management**) and **Step 8 (v0.3): the working fee system** —
fee heads + fee plans, voucher generation (single + bulk) with sequential
challan numbers, challan PDF (ReportLab), 2-installment splits, paid-proof
upload (stored as a database blob), admin verify/reject, and a real
append-only ledger behind the Account Statement. **Step 9 (v0.4)** adds the
results & exams system, and **Step 10 (v0.6)** adds the student-services
pack — document verification, support tickets, notifications admin, the
document repository and the student card PDF — see the v0.6 section below.
**Step 11 (v0.7)** adds the faculty portal — faculty records with
auto-created logins, course assignments and a teacher portal for rosters
and marks entry — see the v0.7 section below. **Step 12 (v0.8)** adds
attendance, and **Step 13 (v0.9)** adds degree clearance with an
auto-evaluated Accounts check and a certificate PDF — see the v0.9
section below.
(The v0.5 navy redesign was rolled back at the user's request; the UI is
still the original v0.4 green/teal+gold theme.)

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

| Role    | Username  | Password      |
|---------|-----------|---------------|
| Admin   | `admin`   | `Admin@123`   |
| Student | `student` | `Student@123` |
| Faculty | `faculty` | `Faculty@123` |

The demo faculty account belongs to the fictional “Demo Teacher”
(`demo.teacher@cuvas.edu.pk`, Lecturer, Department of Computer Science)
and is pre-assigned two of the demo student's Semester 3 courses
(CS-201, CS-202) in the Fall 2024 (Demo) session. Faculty members added by
the admin get their own login: **username = email**, with an initial
password shown to the admin **once**, exactly like student logins.

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
- `/admin/faculty` — faculty records (search by name / email, department filter)
  - `/admin/faculty/new` — add faculty member (auto-creates the login, username = email)
  - `/admin/faculty/<id>/edit` — edit profile, activate / deactivate (deactivation
    blocks login), reset password (shown once), and manage **course assignments**
  - Delete is blocked while the member holds course assignments
- `/faculty` — the faculty portal (role `faculty` only): profile card + own
  courses grouped by session, class roster + Excel export, marks entry,
  and per-course **attendance** (mark/edit/delete per-date sheets, summary
  + Excel — see the Attendance section below)
- `/admin/attendance` — read-only attendance overview for all assignments
  (`/admin/attendance/<assignment_id>` = the teacher's summary, read-only)
- `/student/attendance` — the student's own per-course attendance (counts,
  %, date-wise detail); linked from the Course Enrollments tab
- `/student/clearance` — the student's degree-clearance checklist (apply,
  per-unit status / remarks / system notes, recheck requests, certificate
  download once fully cleared); linked by a **My Clearance** button in
  the Profile tab — see the Clearance section below
- `/admin/clearance` — the admin clearance desk (requests with progress,
  status filter + search; per-item Clear / Object; certificate PDF) and
  `/admin/clearance/units` — manage the clearance units (add / rename /
  activate / deactivate)
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
- `/student` — student dashboard (10 tabs since v0.6) serving the logged-in student's own real record:
  News Feed, Profile, Course Enrollments, Plan Of Study, Transcript (SGPA/CGPA computed),
  Financial Voucher (download challan PDF, create 2 installments, upload paid proof with
  payment channel), Fee Plan & Scholarships (the student's applicable real fee plan),
  Account Statement (real ledger with Total Payable / Paid / Outstanding),
  **My Documents** and **Support Tickets** (v0.6 — see below)

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

## Student Services (Step 10, v0.6)

- **My Documents** (student tab): upload per type — CNIC Front, CNIC Back,
  Matric Certificate, Intermediate Certificate, Domicile, Passport Photo,
  Other. Images + PDF only, ≤ 5 MB, stored **as a database blob**
  (`student_documents.file_data`, BYTEA/BLOB) — never on the filesystem.
  One row per student + type: re-uploading a Pending/Rejected document
  replaces it and returns it to Pending; a **Verified document is locked**
  (no replace, no delete). Students download only their own files
  (`/student/documents/<id>/download`; anyone else's → 404).
- **Admin → Documents** (`/admin/documents`): status counts, status filter +
  student search, pending first; per-row View/Download, **Verify** and
  **Reject with remarks** (reviewer + timestamp recorded; the remark shows
  on the student's dashboard).
- **Support Tickets**: student tab to create a ticket (categories: Fee,
  Result, Admission, IT / Login, Hostel, Other) and follow the thread at
  `/student/tickets/<id>`; statuses Open → In Process → Resolved → Closed.
  The student may reply while the ticket is not Closed and may close their
  own Resolved ticket; a Closed ticket rejects new replies.
  **Admin → Tickets** (`/admin/tickets`) filters by status + category, with
  the same thread view, reply box and status control.
- **Notifications**: the original v0.1 `notifications` table is now the
  single source for the landing page **and** the student News Feed,
  extended additively (`audience` All/Students/Admins, `is_published`,
  `created_by`, `created_at` — existing announcements keep showing).
  **Admin → Notifications** (`/admin/notifications`): create / edit /
  delete + publish toggle. Only published All/Students items are public;
  Admins-audience items never reach the landing page or student feed.
- **Document Repository**: **Admin → Repository** (`/admin/repository`)
  uploads official Circulars / Notifications / Policies / Forms (blob
  storage, same upload rules) with publish toggle + delete. Published
  items are listed in the student's News Feed tab with a download button;
  unpublished items are invisible to students and their download route
  returns 404 for students.
- **Student Card PDF**: `/student/card.pdf` (own card) and
  `/admin/students/<id>/card.pdf` — one ID-proportioned card on an A4 page
  with a dashed cut line, the green CUVAS header band used by the other
  PDFs, a passport-photo placeholder, Name / Registration No / CNIC /
  Program / Department / Session / Blood Group, a **Code39 barcode of the
  registration number**, and the line “Valid for the duration of the
  program”. Buttons: Profile tab of the student dashboard and the admin
  student list (“Card PDF”).

## Faculty Portal (Step 11, v0.7)

- **Faculty records** (`faculty` table: name, unique email, phone,
  designation — Professor / Associate Professor / Assistant Professor /
  Lecturer — department, active flag). Creating a record auto-creates the
  login (`users` row, role `faculty`, linked via the additive
  `users.faculty_id` column; **username = email**); the initial password
  is admin-set on the form or generated, and is shown to the admin
  **once**, mirroring the student flow. Editing the email keeps the login
  username in sync; resetting the password shows the new one once;
  **deactivating** a member (faculty flag, mirrored onto the login)
  blocks sign-in with the usual friendly error. Delete is blocked while
  course assignments exist.
- **Course assignments** (`course_assignments`: faculty + course +
  session, unique together) are managed on the faculty edit page. One
  course + session has **one primary teacher**: assigning it to a second
  teacher is blocked with a message naming the current teacher — reassign
  only after removing the existing assignment.
- **Teacher portal** (`/faculty`, own shell in the same theme): a profile
  summary card and **My Courses** grouped by session — course code/title,
  program, semester, enrolled-student count and the result set's publish
  state. The roster (`/faculty/course/<assignment_id>/students`) is
  exactly the admin marks-sheet cohort for that course + session (Active
  students of the program + session, plus anyone already holding a
  result), with an **Excel export** (Reg No, Name, blank Signature
  column). Marks entry (`/faculty/course/<assignment_id>/marks`) is the
  admin sheet's grid (marks 0–100 or Absent; blank = unchanged) writing
  into the **same results store** via the same helpers — but there is no
  publish control: saves always leave the set **Unpublished**, and once
  the admin publishes a set the faculty sheet locks **read-only** (page
  note + server-side POST guard; individually published rows are never
  faculty-editable either). Every faculty course route resolves the
  assignment through an ownership check, so another teacher's assignment
  id returns **404** on view, roster, export and marks (GET and POST).
  Role guards are symmetric: faculty cannot open `/admin/*` or
  `/student`, and admin/student cannot open `/faculty/*`.
- **Demo seed** (`backfill_v07`, runs only while the faculty table is
  empty): the fictional **Demo Teacher** above, login `faculty` /
  `Faculty@123`, assigned CS-201 + CS-202 in the demo student's session
  so the roster shows the seeded class. It never touches results — the
  demo transcript (CGPA 3.63) is unchanged.

## Attendance (Step 12, v0.8)

- **Model** (`attendance` table — the only new table; plain INTEGER ids
  like `enrollments`/`results`): one row per student per class date per
  course assignment (`UNIQUE(assignment_id, student_id, class_date)`),
  status **Present / Absent / Late / Leave**, the marking teacher and
  created/updated timestamps. Created idempotently by the boot DDL — no
  backfill is needed, and a v0.7-era database simply gains the table.
- **Faculty flow** (from each course card on `/faculty`, or
  `/faculty/course/<assignment_id>/attendance`): the landing lists every
  marked date with its P/A/L/Leave counts, an **Edit** link and a
  **Delete** action (the app's confirm-form pattern), plus a date picker
  (defaults to today) into the mark sheet
  (`.../attendance/mark?date=YYYY-MM-DD`). The sheet is the
  `sheet_students` roster with a status select per student — **Present**
  pre-selected for unmarked students, saved values pre-selected on
  re-open. Saving **upserts** per student, so re-saving a date corrects
  it in place and can never duplicate a row. **Future dates are
  rejected** with a friendly flash and zero writes; malformed dates just
  bounce back to the landing. Every route resolves through the same
  assignment-ownership check as the rest of the portal, so another
  teacher's assignment is a **404** on landing, mark (GET + POST),
  summary, Excel export and delete alike.
- **One shared computation** — `attendance_summary(assignment_id)` is the
  single source for all three audiences: **classes held** = the number
  of distinct class dates recorded for the assignment; per student it
  returns the P/A/L/Leave counts, the total marked, and
  **percentage = round(present / classes_held × 100, 1)**. Late and Leave
  do **not** count as present; the raw counts are always displayed next
  to the percentage so the definition stays transparent.
- **Faculty summary** (`.../attendance/summary`): the per-student table
  (Reg No, Name, P, A, L, Leave, Total, %) with classes held, plus an
  **Excel export** of the same table (`.../attendance/summary.xlsx`).
- **Student page** (`/student/attendance`, linked by a **My Attendance**
  button in the Course Enrollments tab — the dashboard's 10 tabs and
  their labels are unchanged): for each enrolled course, the teacher
  (resolved through the course+session's single assignment), classes
  held, the student's **own** counts and %, and a date-wise detail list
  (date + status pill). A course with no assignment or no marks yet
  shows “No attendance recorded yet”. Students only ever see their own
  rows.
- **Admin overview** (`/admin/attendance`, sidebar link): a read-only
  list of all assignments (teacher, course, program, session, classes
  held, students) linking to `/admin/attendance/<assignment_id>` — the
  same summary table the teacher sees, rendered from the same partial,
  with no mark/edit/delete controls.

## Clearance (Step 13, v0.9)

- **Model** (three new tables, plain INTEGER ids like
  `enrollments`/`results`/`attendance`): `clearance_units` (name,
  sort_order, is_active, is_accounts), `clearance_requests` (student,
  stored status `In Progress` / `Cleared` kept in sync with its items,
  created_at, completed_at) and `clearance_items` (request + unit,
  `unit_name` **snapshot**, status Pending / Cleared / Objected, admin
  remarks, `auto_note` system-check text, action_by / action_at,
  recheck flag; unique per request + unit).
- **Units seed** (`backfill_v09`, only while the units table is empty):
  Accounts / Fees (flagged `is_accounts`), Library, Hostel,
  Examinations (COE), Department, Sports, Transport. **Admin →
  Clearance → Manage Units** (`/admin/clearance/units`) can add, rename
  and activate/deactivate units; units are never deleted, and renames /
  deactivations shape **new applications only** — existing requests
  keep their snapshot items.
- **Apply flow** (`/student/clearance`, **My Clearance** button in the
  Profile tab — the dashboard's 10 tabs and labels are unchanged): with
  no request, an explanation + Apply button. Applying creates the
  request plus one item per **active** unit. The Accounts item is
  **auto-evaluated** from the student's ledger balance
  (`student_outstanding` — the same total-debit − total-credit
  computation as the Account Statement): dues → **Objected** with
  `System check: outstanding dues of Rs <amount>.`; zero → **Cleared**
  with `System check: no outstanding dues.`, stamped as action_by
  `System`. All other units start Pending. A second apply while one is
  In Progress (or already Cleared) is blocked with a friendly flash.
- **Student checklist**: per unit — status pill, admin remarks, the
  system note shown distinctly (🤖), who acted and when, and progress
  “X of Y cleared”. An Objected item offers **Request Recheck**: the
  item returns to Pending flagged `recheck_requested` (the objection
  remark stays as history); the admin desk shows a “Recheck requested”
  badge, and acting on the item clears the flag.
- **Admin desk** (`/admin/clearance`, sidebar link): requests list
  (student, reg no, program, applied date, X-of-Y progress, status;
  filter by status + search by name / reg no). The detail page
  (`/admin/clearance/<id>`) shows the student summary — including the
  live ledger outstanding figure — and per item a **Clear** action
  (optional remark) and an **Object** action (**remark required** —
  the student must know what to fix). Any item, including the
  auto-evaluated Accounts item, can be overridden by the admin; the
  override stamps the admin's name and the `auto_note` stays visible.
  After every action the request status is re-synced: all items
  Cleared → `Cleared` + `completed_at`, otherwise `In Progress`.
- **Certificate PDF** (`build_clearance_certificate_pdf`, the usual
  green PDF style): CUVAS header, “CLEARANCE CERTIFICATE”, certificate
  no `CLR-<year>-<request_id>`, the student's name / reg no / CNIC /
  program / department / session, a table of units with status and
  clearance dates, a bold **CLEARED** line and a system-generated note.
  Routes: `/student/clearance/certificate.pdf` (own latest request
  only) and `/admin/clearance/<id>/certificate.pdf` — both refuse with
  a flash + redirect until the request is fully Cleared. Students only
  ever see their own request: a recheck POST against another student's
  item returns 404.

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
`verify_v06.py` adds a 72-check pass over Step 10 (document upload stored as
bytes + Pending, reject-with-remarks visible to the student, re-upload
replacement, Verified lock against replace/delete, cross-student download
404, ticket create → admin reply → status flow → student close → closed
ticket rejects replies, notification publish/audience visibility on landing
+ News Feed, repository published-only access, card PDF for self/admin with
cross-student guards, original 8 tab labels byte-identical + 2 new tabs).
v0.6 result: **all four suites ALL PASS on both backends** (SQLite: 43 + 52
+ 60 + 72; PostgreSQL identical). Note: the three older suites each had one
assertion updated — the demo dashboard tab count 8 → 10 — because Step 10
adds the My Documents and Support Tickets tabs; the original 8 labels are
asserted byte-identical in `verify_v06.py`. The v0.6 migration (new tables +
additive notification columns, `backfill_v06` created_at backfill) was also
verified against a simulated v0.4-era database: it boots cleanly, keeps the
seeded announcements, and is a no-op on second boot.

## On Vercel

`vercel.json` is `{}` and `app` in `app.py` is the WSGI entry point (Framework
Preset: Flask). Without `DATABASE_URL`, Vercel uses an ephemeral SQLite DB under
`/tmp` that re-seeds on cold start; set `DATABASE_URL` (Neon) for real data.

`verify_v07.py` adds a 64-check pass over Step 11 (faculty create →
shown-once login, duplicate email blocked, assignment create +
duplicate blocked, second teacher blocked from the same course+session,
dashboard isolation, roster == enrolled cohort, roster Excel shape,
cross-faculty 404s on view/roster/export/marks GET+POST, faculty marks →
invisible while Unpublished → visible after the ADMIN publishes, no
faculty publish control, post-publish lock, role guards both ways,
email-change login sync, reset-password flow, deactivation blocks login,
delete guard then delete-after-unassign, demo teacher seed + roster, demo
transcript intact, and a v0.6-era migration simulation: strip the new
tables/column + faculty logins, boot, assert clean re-seed and a no-op
second boot). v0.7 result: **all five suites ALL PASS on both backends**
(SQLite: 43 + 52 + 60 + 72 + 64; PostgreSQL identical).
`verify_v08.py` adds a 52-check pass over Step 12 (mark a date → rows
saved with the chosen statuses + marking teacher stamped; re-save
updates in place with classes_held unchanged; a second date →
hand-computed percentages, 1 present of 2 = 50.0; the same numbers
asserted on the faculty summary, the admin overview/detail and both
students' own pages, with each student's (date, status) pair set exactly
his own; future dates rejected with zero writes on GET and POST;
delete-a-date → summaries recompute on all three surfaces; cross-faculty
404s on landing/mark/summary/Excel/delete; the never-marked empty
state; the summary Excel shape; role guards both ways; the demo
accounts untouched). v0.8 result: **all six suites ALL PASS on both
backends** (SQLite and PostgreSQL identical: 43 + 52 + 60 + 72 + 64 +
52). One build note: `verify_v07`'s Postgres migration simulation drops
`course_assignments`, which PostgreSQL refuses while another table holds
a foreign key to it — the `attendance` table therefore uses plain
INTEGER ids (exactly like `enrollments`/`results`) instead of
`REFERENCES`, keeping every older migration simulation green.
`verify_v09.py` adds a 59-check pass over Step 13 (units seeded in
order with Accounts flagged; the demo student — Rs 47,500 outstanding
per the real ledger — applies and gets Accounts auto-Objected with the
amount in the system note while a zero-balance fixture student is
auto-Cleared by 'System'; duplicate apply blocked; objection without a
remark refused, with a remark shown to the student; recheck returns the
item to Pending + flagged on the admin desk with the remark preserved;
clearing item by item syncs progress on both sides; the admin override
of the auto-Objected Accounts item keeps its system note; the request
flips to Cleared + completed_at only at 7 of 7; the certificate is
blocked before completion and returns real %PDF bytes after, for both
the student and the admin; cross-student recheck on a foreign item is a
404 and no clearance data leaks into another student's page; unit
add/rename/deactivate shapes a new application — deactivated Sports
excluded, the added unit included — while the existing request keeps
its snapshot items; clearance never writes to the ledger; the demo
transcript stays at CGPA 3.63). v0.9 result: **all seven suites ALL
PASS on both backends** (SQLite and PostgreSQL identical: 43 + 52 + 60
+ 72 + 64 + 52 + 59). A v0.8-era migration was also simulated (the
three clearance tables dropped from a booted database): the next boot
recreates them, re-seeds the 7 units, keeps all demo data, and a
further boot is a strict no-op.

## Not in v0.9

Scholarships application flow, course repeat, timetable, surveys,
dept/accounts/COE portals — the rest of Phase 2 (see
`../architecture.md`).
