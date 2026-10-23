# MY CUVAS — Campus Management System (Demo) v0.16

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
section below. **Step 14 (v0.10)** adds scholarships — admin-managed
schemes, a per-student socio-economic profile that gates applying,
and an admin review flow with recorded awards — see the v0.10 section
below. **Step 15 (v0.11)** adds course repeat / improvement — apply
from published results, an admin-set per-credit-hour fee, approval by
issuing a normal fee voucher, enrolment on verified payment, and a
transcript that counts only the latest attempt of a repeated course —
see the v0.11 section below. **Step 16 (v0.12)** adds the timetable
(admin-built weekly slots per program + semester + session, saved
with class/teacher/room clash checks; students get a web + PDF
“My Time Table”, teachers a per-session teaching timetable) and
transport (admin-managed bus routes with ordered stops; students
browse active routes and search by stop name) — see the v0.12
section below. **Step 18 (v0.13)** adds Campus Life —
admin-configured LMS / Library / Email service links shown to
students and faculty, student societies with an admin-approved
join flow, and vehicle entry passes with approval-stamped pass
numbers and a printable pass PDF — see the v0.13 section below.
**Step 19 (v0.14)** adds the Reports centre (fee collection, student
strength, results and attendance reports — every figure from the
same shared computations as the screens they summarise, each with
an Excel export), an append-only **audit log** of sign-ins and
significant actions across all portals, and a one-click **full
backup** download (Excel workbook + stored files ZIP; passwords
never included; restore deliberately manual) — see the v0.14
section below. **Step 20 (v0.15)** — the final roadmap step — adds
the two office roles (**Accounts** and **Controller of
Examinations**) with per-route permissions, role-aware menus and
their own landing dashboards, admin-managed staff logins, and the
security pass: sign-in lockout, a password policy, security
headers, a 10 MB upload cap, hardened session cookies, and a
go-live switch that hides the demo accounts from the public
homepage — see the v0.15 section below. **v0.16** is a UI
restructure of the student portal only: every student page now
renders inside a MY IUB-style shell with a left sidebar (identity
block, Home, a *My Apps* group, a *Scholarships* group and the
Document Repository), and the navigation buttons that used to sit
inside the dashboard tab panes are gone — see the v0.16 section
below.
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
| Accounts Office | `accounts` | `Accounts@123` |
| Controller of Examinations | `coe` | `Coe@123` |

The Accounts and COE demo logins (v0.15) are restricted office
roles — see the permission map in the v0.15 section. Real staff
logins are created by the admin on `/admin/staff`.

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
- `/student/scholarships` — the student's socio-economic profile form,
  the open scholarship schemes with apply forms, and their applications
  with decisions; linked by a **Scholarships** button in the Fee Plan &
  Scholarships tab — see the Scholarships section below
- `/admin/scholarships` — scholarship schemes (create / edit / delete,
  open toggle, deadline) and the applications list (scheme + status
  filters, name / reg-no search); `/admin/scholarships/applications/<id>`
  is the review page (full profile, transcript CGPA, ledger dues,
  Under Review / Approve / Reject decision)
- `/student/repeat` — course repeat / improvement: eligible courses
  from the student's published results (F → Repeat, pass →
  Improvement) with an apply form (target session + optional reason),
  and the student's own requests with status, remarks and the linked
  fee voucher; linked by a **Course Repeat / Improvement** button in
  the Transcript tab — see the Course Repeat section below
- `/admin/repeat` — the repeat desk: the per-credit-hour rate setting
  plus all requests (status filter, name / reg-no search) with
  Approve (issues the fee voucher) / Reject (remarks required)
- `/admin/timetable` — the weekly timetable per program + semester +
  session (filterable), grouped by day; add / edit / delete slots with
  **clash checks** (class / teacher / room) — see the Timetable &
  Transport section below
- `/student/timetable` — “My Time Table” for the current session
  (enrolled courses only) and `/student/timetable.pdf`; linked by a
  **View Time Table** button in the Course Enrollments tab
- `/faculty/timetable` — the teacher's own teaching timetable for a
  chosen session
- `/admin/transport` — transport routes (create / edit / delete —
  delete blocked while stops exist) and `/admin/transport/<id>/stops`
  — per-route stops (add / edit / delete, ordered)
- `/student/transport` — active routes with their stops in order and
  a stop-name search; linked by a **Transport** button in the Profile
  tab
- `/admin/campus` — Campus Life settings: the five service values
  (LMS URL, Library URL + info, Email URL + info) plus management
  cards with pending societies / vehicle counts — see the Campus
  Life section below
- `/admin/societies` — society CRUD (name, description, advisor,
  active toggle; delete blocked while membership rows exist) and
  `/admin/societies/<id>/members` — approve / reject requests,
  remove approved members
- `/admin/vehicle-passes` — vehicle pass decisions (status filter
  + search; approve stamps the pass number, reject needs remarks)
- `/student/campus` — the service cards (LMS / Library / Email)
  and the societies join flow; linked by a **Campus Life** button
  in the Profile tab
- `/student/vehicle` — vehicle entry applications + “My Vehicle
  Passes”, and `/student/vehicle/<id>/pass.pdf` — the printable
  pass; linked by a **Vehicle Entry** button in the Profile tab
- `/faculty/campus` — the same three service cards for faculty
- `/admin/reports` — the Reports hub (one sidebar link) with cards for the
  four reports, the audit log and backup — see the v0.14 section below
  - `/admin/reports/fees` — fee collection for a session (ledger-based
    issued / collected / outstanding, department breakdown, defaulters)
    and `/admin/reports/fees.xlsx`
  - `/admin/reports/students` — student strength (totals + department /
    program / session / gender breakdowns + program × session matrix)
    and `/admin/reports/students.xlsx`
  - `/admin/reports/results` — per-course results summary for a session
    (appeared / passed / failed / pass % / average / highest / published)
    and `/admin/reports/results.xlsx`
  - `/admin/reports/attendance` — per-assignment attendance summary for
    a session (classes held, students, average %) and
    `/admin/reports/attendance.xlsx`
  - `/admin/audit` — the append-only audit log viewer (text / role /
    date filters, newest first, capped at 300 rows with a note)
  - `/admin/backup` — what the backup contains + the last-backup
    timestamp, and `/admin/backup/download` — the full ZIP backup;
    the same page carries the v0.15 **Go-Live** card that shows /
    hides the demo-accounts box on the public homepage
- `/accounts` — the Accounts Office landing dashboard (fee KPIs for
  the current session + quick links); signing in as `accounts`
  lands here, and the `/admin/*` pages it may use render with a
  role-aware sidebar (fees, vouchers, students, reports only)
- `/coe` — the Controller of Examinations landing dashboard
  (results KPIs + quick links); signing in as `coe` lands here
- `/admin/staff` — staff login management (admin only): create
  Accounts / COE logins, reset their passwords, activate /
  deactivate them; the primary `admin` account is protected
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

## Scholarships (Step 14, v0.10)

- **Model** (three new tables, plain INTEGER ids like
  `enrollments`/`results`/`attendance`/`clearance`): `scholarship_schemes`
  (name, provider, description, eligibility, is_open, nullable deadline),
  `scholarship_profiles` (one per student — `student_id` UNIQUE; father /
  guardian details, family size, monthly income / expenses, house status,
  and the bank account used for disbursement) and
  `scholarship_applications` (student + scheme + **session**, statement,
  status Applied / Under Review / Approved / Rejected, admin remarks,
  awarded amount, decided_by / decided_at; unique per student + scheme +
  session). The application's session is the current session at apply
  time (`current_session`: the most recently added open session).
- **Schemes seed** (`backfill_v10`, only while the schemes table is
  empty): **Need-Based Scholarship** (provider “University / HEC”;
  low family income, complete socio-economic profile required) and
  **Merit Scholarship** (provider “University”; strong CGPA). Both open,
  no deadline, and **no amounts are invented**. Admin → Scholarships
  can create / edit / close schemes and set deadlines; a scheme can be
  deleted only while it has no applications.
- **Profile gate**: a profile counts as **complete** (`profile_complete`)
  when it exists with a father **or** guardian name **and** a monthly
  income. The student page (`/student/scholarships`, linked by a
  Scholarships button in the Fee Plan & Scholarships tab — the
  dashboard's 10 tabs and labels are unchanged) has three sections:
  the profile form (prefilled, save = create-or-update), the open
  schemes, and the student's own applications. Applying is refused
  server-side with a friendly flash when the profile is incomplete,
  the scheme is closed, the deadline has passed (the scheme then shows
  “Closed (deadline passed)”), or the student already applied to that
  scheme in the current session.
- **Admin review** (`/admin/scholarships`, sidebar link): schemes table
  with per-scheme application counts, and the applications list with
  scheme + status filters and name / reg-no search. The review page
  (`/admin/scholarships/applications/<id>`) shows the student's identity
  (program / department / session), the **full socio-economic profile**,
  the **transcript CGPA** computed by `transcript_data` — the same
  number the student's transcript shows — and the **outstanding dues**
  from `student_outstanding` (the ledger computation behind the Account
  Statement), plus the student's statement. Decisions: **Under Review**
  (can still be decided later), **Approve** (awarded amount required;
  remarks optional) and **Reject** (**remarks required**). Approve /
  Reject stamp `decided_by` / `decided_at` and are **final** — the
  decision form is replaced by a read-only summary.
- **Award ≠ ledger**: approving records the awarded amount on the
  application **only**. It writes nothing to `ledger_entries`, creates
  no voucher and does not change the Account Statement — disbursement
  through the fee system is a later step, deliberately out of scope
  here. Students see their decision, remarks and awarded amount in the
  “My Applications” section; one student's profile and applications
  are never visible to another student.

## Course Repeat & Improvement (Step 15, v0.11)

- **Model** (two new tables, plain INTEGER ids like
  `enrollments`/`results`): `repeat_requests` (student, course,
  from-session, target session, kind Repeat / Improvement, optional
  student reason, status Requested / Approved / Enrolled / Rejected /
  Cancelled, admin remarks, linked `voucher_id`, decided_by /
  decided_at) and `app_settings` — a tiny key-value store (the app
  had none before) holding `repeat_fee_per_ch`, seeded to **2000**
  by `backfill_v11` only while the key is absent, so an admin-changed
  rate survives reboots. `vouchers` gains one additive column,
  `repeat_request_id` (via `ensure_columns`); repeat vouchers use the
  existing `kind` column with the new value `'Repeat'`.
- **Eligibility** (`repeat_eligibility`) is computed from **published
  results only** — unpublished results never appear. The **latest**
  published attempt per course decides: grade **F → Repeat**, any
  passed grade → **Improvement**. A course is not eligible while the
  student has an **active** request for it (`active_repeat_request`:
  Requested / Approved always block; Enrolled blocks until the repeat
  attempt is published in its target session), and applying is
  refused server-side when the target session equals the original
  attempt's session or the student is already enrolled in that course
  for the target session. The student page (`/student/repeat`, linked
  by a Course Repeat / Improvement button in the Transcript tab — the
  dashboard's 10 tabs and labels are unchanged) lists the eligible
  courses with an apply form and the student's own requests; a
  request can be **cancelled only while Requested** (an approved
  request already has a voucher issued against it).
- **Approval = a normal fee voucher** (`create_repeat_voucher`):
  title “Course Repeat — `<code>`” (or “Course Improvement —
  `<code>`”), amount = the **current** rate × the course's credit
  hours (theory + lab), a sequential `CUVAS-<year>-<seq>` challan
  number, due date today + 14 days, and the usual **debit ledger
  entry** at creation — so the voucher appears in the student's
  Financial Voucher tab, Account Statement and challan PDF exactly
  like a fee-plan voucher. **Reject** requires remarks (shown to the
  student); approving or rejecting is possible only from Requested,
  so a decided request cannot be re-decided, and a rate change
  affects only vouchers issued afterwards (issued vouchers keep
  their amount).
- **Activation on payment**: the hook sits in the existing admin
  voucher-verification success point, after the ledger credit and
  inside its commit: when the verified voucher carries a
  `repeat_request_id`, `activate_repeat_request` flips the request
  from Approved to **Enrolled** and creates the enrollment
  (student, course, **target session name**, course semester) if
  missing. It is idempotent (a no-op unless the request is still
  Approved), and a **rejected proof activates nothing** — the request
  stays Approved and the student can upload a fresh proof as usual.
- **Cohort inclusion**: `sheet_students` additionally UNIONs students
  with an explicit enrollment for the course in the sheet's session
  (enrollments store the session **name**), so an activated repeat
  student appears in the admin marks sheet and the faculty roster for
  the target session even though their admission session differs; no
  existing cohort outcome changes (the union only adds students who
  hold such an enrollment and were not already listed).
- **Transcript rule (the one deliberate change to an old feature)**:
  in `transcript_data` — the single helper behind the web tab and
  the PDF — when a student has published results for the same course
  in multiple sessions, **only the latest attempt counts** in
  SGPA/CGPA (latest = greatest session id, the app's chronological
  session ordering, tie-broken by the greatest result id). Earlier
  attempts still render in their semester group, flagged with a
  **“Repeated”** tag on the web tab and a “(Repeated)” note in the
  PDF (plus a footnote), with their grade points excluded. Students
  with no repeated course get byte-identical numbers — the demo
  transcript stays at **CGPA 3.63** and `verify_v04.py` passes
  untouched.

## Timetable & Transport (Step 16, v0.12)

Three new tables (plain INTEGER ids like `enrollments`/`results`, so
older migration simulations stay safe on PostgreSQL): `timetable_slots`
(one weekly class meeting: program + semester + session, course,
optional teacher, day Monday–Saturday, `start_time`/`end_time` as
zero-padded `HH:MM` text, room), `transport_routes` (name, title,
description, active flag) and `transport_stops` (route, stop name,
pickup time, sort order).

**Timetable.**

- **Admin** builds the timetable per program + semester + session on
  `/admin/timetable` (the default view is the first program, semester
  1, the current session). The slot form's course list is limited to
  that program + semester; picking a course from the list page's
  per-course “Add slot” links pre-selects the teacher **assigned to
  that course for the session** (the v0.7 `course_assignments`).
- **Clash check** (`timetable_clashes`, run on add AND edit, always
  excluding the slot being edited): two slots overlap when they
  share the session and day and `new_start < existing_end` and
  `existing_start < new_end` — so a slot starting exactly when
  another ends (back-to-back) is fine. Each overlap is reported with
  a specific message and the save is refused: a **Class clash** (the
  same program + semester already has a class then), a **Teacher
  clash** (the same teacher already teaches then) or a **Room clash**
  (the same room — compared trimmed and case-insensitively — is
  already booked then). Several clashes can be reported at once.
- **Student** — `/student/timetable` (“My Time Table”, linked by a
  **View Time Table** button in the Course Enrollments tab) shows,
  for the **current session**, exactly the slots whose course the
  student is enrolled in for that session — enrolments are matched
  by session **name**, the same rows the Enrollments tab lists —
  grouped by day with time, course, room and teacher, plus an empty
  state. `/student/timetable.pdf` renders the same rows in the green
  PDF style (`buf.seek(0)` after `build()`, as everywhere).
- **Faculty** — `/faculty/timetable` (“My Teaching Timetable”)
  shows the logged-in teacher's own slots for a chosen session
  (default: the current one), grouped by day with course,
  program + semester, time and room.
- There is deliberately **no timetable seed**: the admin builds the
  timetable, and the demo data has no canonical class timings to
  invent.

**Transport.**

- **Admin** manages routes on `/admin/transport` (name, title,
  description, active toggle) and each route's stops on
  `/admin/transport/<id>/stops` (stop name, pickup time, order;
  listed by sort order, then pickup time). Following the app-wide
  pattern, a route's **delete is blocked while it still has stops**
  — delete the stops first — with the reason shown.
- **Student** — `/student/transport` (linked by a **Transport**
  button in the Profile tab, alongside My Clearance) lists the
  **active routes only**, each with its stops in order and pickup
  times. A search box (`?q=`) filters by stop name
  (case-insensitive substring): only routes serving a matching stop
  are shown and the matching stops are highlighted; a search with
  no match says so.
- **Seed** (`backfill_v12`, only while `transport_routes` is
  empty — admin changes are never undone): two clearly-labelled
  demo routes — *Route 1 — City Side* (Satellite Town 07:10,
  Model Town 07:25, Cantt 07:40, Main Gate 07:55, CUVAS Campus
  08:10) and *Route 2 — Hasilpur Road Side* (Hasilpur Road Chowk
  07:15, University Chowk 07:35, Main Gate 07:55, CUVAS Campus
  08:10). All of it is fictional demo data, editable by the admin.

## Campus Life (Step 18, v0.13)

Three new tables ship with the boot DDL (plain `INTEGER` ids, so
the older migration simulations stay safe on PostgreSQL):
`societies` (name, description, advisor faculty id, active flag),
`society_members` (society + student, `Requested` / `Approved` /
`Rejected`, decider + decision time; `UNIQUE(society_id,
student_id)`), and `vehicle_passes` (student, vehicle type +
number + make/model + colour, status, pass number, valid-till
date, admin remarks + decider stamps). `backfill_v13` seeds the
five campus settings keys (`lms_url`, `library_url`,
`library_info`, `email_url`, `email_info` — all `''`) **only when
absent** and three demo societies **only while the societies table
is empty**, so admin changes are never overwritten.

**Service links (LMS / Library / Email).** The values live in the
existing `app_settings` store (Step 15). **Admin → Campus Life**
(`/admin/campus`, one sidebar link) edits them: URLs must start
with `http://` or `https://` when non-empty, otherwise nothing is
saved and a friendly error shows; the page also carries management
cards for Societies and Vehicle Passes with their pending-request
counts. **Students** (`/student/campus`, **Campus Life** button in
the Profile tab) and **faculty** (`/faculty/campus`, link in the
faculty shell) see the same three cards from one shared partial:
LMS shows an **Open LMS** button only when a URL is set (otherwise
“Not configured yet”), the Library card shows the info text plus
an **Open Library / OPAC** button when set, and the Email card
the info text plus an **Open Email** button when set.

**Societies.** The student page lists every **active** society
with its description, advisor name (when set), approved-member
count and the student's own state: **Join** (POST), a disabled
“Requested — awaiting approval”, **Member ✓**, or — after a
rejection — **Request again**, which flips the *same* membership
row back to `Requested` and clears the decision stamp (the
`UNIQUE` pair makes a second row impossible, so a duplicate join
is refused with a friendly message). Joining has no other
conditions. Inactive societies are hidden from students (joining
one is a 404). **Admin → Societies** is full CRUD (advisor chosen
from the faculty list, active toggle); following the app-wide
pattern, **delete is blocked while membership rows exist**, with
the reason shown. `/admin/societies/<id>/members` lists pending
requests (Approve / Reject, stamping decider + time) and approved
members (Remove deletes the row); decided rows refuse re-deciding.
Pending counts appear on the societies list and on `/admin/campus`.
Seed (only-when-empty): *Literary Society*, *Sports Society* and
*IT & Robotics Society* — the IT society's advisor is the seeded
Demo Teacher (looked up by the demo email; `NULL` when absent).

**Vehicle entry.** **Students** apply on `/student/vehicle`
(**Vehicle Entry** button in the Profile tab): type (`Motorcycle`
/ `Car` / `Other`), vehicle number (normalised to trimmed
UPPER-case), make/model and colour. Rules, all enforced
server-side: a student may hold several vehicles, but the **same
vehicle number cannot have a second `Requested`/`Approved` pass
for the same student**, and a number with an **`Approved` pass
for another student is refused** — one vehicle, one pass (a
number that is merely `Requested` by someone else may still be
requested). “My Vehicle Passes” shows status pills, admin remarks
on rejections, and — once approved — a **Download Pass (PDF)**
button. **Admin → Vehicle Passes** lists every application
(pending first) with a status filter and a search over vehicle
number (case-insensitive on both backends) / student name /
registration number. **Approve** takes an optional valid-till
date (empty = today + 1 year) and stamps `pass_no` =
`VEH-<year>-<id>` plus the decider; **Reject** requires remarks.
Decided passes cannot be re-decided. The pass PDF
(`/student/vehicle/<id>/pass.pdf`, own + `Approved` only, else
404) uses the shared green PDF style: a card on A4 with the
university header, “VEHICLE ENTRY PASS”, pass number, student
name + registration number, vehicle details, valid-till and a
Code39 barcode of the pass number.

## Reports, Audit Log & Backup (Step 19, v0.14)

**Reports centre** — one new sidebar link (**📊 Reports**) opens a
hub with the four reports plus cards for the Audit Log and Backup.
Every report page shows a “generated on” timestamp, renders clean
empty states, and offers an **Excel export** of the same figures.

- **Fee Collection** (`/admin/reports/fees`, session filter,
  default = current session). All money figures come from the
  **append-only ledger joined to the session's vouchers** — exactly
  the Account Statement semantics, so a split challan counts
  through its installments (the parent's debit is reversed, the
  children are debited): *Total Issued*, *Total Collected*,
  *Outstanding* (= issued − collected), the challan count (split
  parents excluded — the live challans), the sum of `Paid`
  challans, and the pending-proof count. A **cross-check** line
  recomputes the outstanding as the sum of the session's own
  students' per-session ledger balances. The **By Department**
  table rolls the same per-student ledger figures up by the
  student's department, and the **Defaulters** list shows the
  session's students with outstanding > 0 (name, registration
  number, department, phone, amount), largest dues first. The
  export has `Summary` / `By Department` / `Defaulters` sheets.
- **Student Strength** (`/admin/reports/students`): the total plus
  counts **by department, by program, by session and by gender**
  and a **program × session matrix**; the export adds one sheet
  per breakdown plus the matrix sheet.
- **Results Summary** (`/admin/reports/results`, session filter):
  one row per course + semester with results in the session —
  appeared (result rows), passed / failed (grades derived via the
  shared `result_grade_gp`, absent counts as appeared + failed),
  pass %, average + highest marks over the students who sat
  (non-absent rows with marks), and the publish state (`Yes` only
  when the whole set is Published).
- **Attendance Summary** (`/admin/reports/attendance`, session
  filter): one row per course assignment — classes held, cohort
  size and average attendance %, all from the **shared
  `attendance_summary()`** helper, so the numbers are identical
  to the faculty summary and the student's own page.

**Audit log** — a new append-only `audit_log` table (`user_id`,
`username` + `role` snapshots, `action`, `details`, `created_at`).
The single writer is `log_audit()`, called **after** the recorded
action succeeds and wrapped so a logging failure can never break
the action. Instrumented events: **login success / failure** (the
failure records the attempted username), **logout**; student
create / update / delete / password-reset / Excel import;
department / program / session / course create / update / delete;
faculty create / update / deactivate / password-reset / delete;
fee head + fee plan create / update / delete; voucher generate
(single + bulk, with counts) / split / verify / reject; results
save (admin sheet, faculty marks, Excel import) / publish /
unpublish + grading-scale changes; clearance item clear / object,
units add / rename / activate / deactivate; scholarship scheme
create / update / delete + application decisions; repeat rate
change + request approve / reject; timetable slot create / update
/ delete; transport route + stop changes; campus-life settings
save; society create / update / delete + membership decisions;
vehicle pass approve / reject; notification create / publish /
unpublish / update / delete; student-document verify / reject;
repository upload / publish / unpublish; backup download; and
the student-side submissions (ticket created, document uploaded,
clearance applied + recheck requested, scholarship applied,
repeat requested / cancelled, vehicle applied, society joined,
voucher split). The viewer (`/admin/audit`, admin only) filters
by free text (username / action / details), role and date range,
newest first, capped at the newest 300 rows with an explicit note
when capped. There is no edit/delete UI or route — the table is
only ever INSERTed into.

**Backup** (`/admin/backup`, admin only) explains the contents,
shows the last-backup timestamp (read from the audit log), and
downloads **`cuvas-backup-<YYYYMMDD-HHMM>.zip`**: a workbook
`cuvas-backup.xlsx` with **one sheet per core table** (only for
tables that exist; headers-only sheets for empty tables), a
`files/` folder with every stored blob (student documents,
repository files, voucher paid proofs) named
`<table>-<id>-<original filename>`, and a `README.txt`
(generated-at time, sheet list, notes). The **users sheet omits
`password_hash` entirely** and the document tables are exported
as metadata only (file bytes travel under `files/`). The download
itself is recorded in the audit log. **Restore is deliberately
out of scope** — manual / by a developer, as the page and the
README state.

## Staff Roles, Security & Go-Live (Step 20, v0.15)

Two office roles join admin / student / faculty. `users.role` gains
`accounts` and `coe` (the migration is `migrate_v15_roles`: fresh
DDL never constrained the column, but a legacy database carrying
`CHECK(role IN ('admin','student'))` has the constraint widened at
boot — on SQLite by rebuilding the users table with every column
and row preserved, on PostgreSQL by dropping the restrictive
CHECK constraint by name). Demo logins `accounts` / `coe` are
seeded only while each username is absent (`backfill_v15`), exactly
like the faculty demo login. Sign-in lands each role on its own
dashboard (`/accounts`, `/coe`); an office user who opens `/admin`
is redirected to their own landing; the admin (a superset) may open
both landings. The sidebar in `admin_base.html` is role-aware: each
role sees only the modules it may open, while the admin's link set
is unchanged (plus the new Staff link).

### Permission map (route group → roles)

| Route group | Admin | Accounts | COE |
|---|---|---|---|
| Fee heads + fee plans (full CRUD) | ✓ | ✓ | — |
| Vouchers: list, generate (single + bulk), detail, challan PDF, proof view, verify, reject, split | ✓ | ✓ | — |
| Students list + Excel export (read-only for the offices) | ✓ | ✓ | ✓ |
| Student transcript PDF | ✓ | — | ✓ |
| Roll-number slips (single + bulk PDF) | ✓ | — | ✓ |
| Results: marks sheets, save, Excel import/export, publish/unpublish | ✓ | — | ✓ |
| Grade scale | ✓ | — | ✓ |
| Reports hub | ✓ | ✓ | ✓ |
| Fee Collection report (+ Excel) | ✓ | ✓ | — |
| Results Summary + Attendance Summary reports (+ Excel) | ✓ | — | ✓ |
| Student Strength report | ✓ | — | — |
| Student add / edit / delete / import / password reset | ✓ | — | — |
| Departments / programs / sessions / courses, faculty, attendance desk, clearance, scholarships, repeat approvals, timetable, transport, documents desk, tickets desk, notifications, repository, campus settings, societies, vehicle passes | ✓ | — | — |
| Audit log, backup, staff management | ✓ | — | — |

Enforcement is per-route (`role_required` now takes a set of
roles); shared templates hide the actions a role may not use (the
students list shows no Add / Import / Edit / Reset / Delete
controls to the offices, and no transcript/slip links to
Accounts). Denial keeps the house style: a flash + a redirect to
the user's own home.

### Staff management (`/admin/staff`, admin only)

Lists the staff logins (admin / accounts / coe) with their active
state. The admin can **create** an office login (username, display
name, role, password — the password is confirmed once in the
flash, per the house pattern), **reset** a password (typed or
auto-generated, shown once), and **deactivate / reactivate** a
login (a deactivated staff user cannot sign in, the same rule as
faculty). The primary `admin` account can never be deactivated,
and nobody can deactivate their own login. Actions are audited:
`staff_created`, `staff_password_reset`, `staff_deactivated`,
`staff_activated`.

### Security hardening

- **Sign-in lockout** — every attempt is recorded in
  `login_attempts`. `LOGIN_MAX_FAILURES = 5` consecutive failures
  for a username within `LOGIN_LOCKOUT_MINUTES = 15` minutes locks
  that username: further sign-ins are refused *without checking
  the password* (even the correct password is turned away) with a
  clear message, and the refusal is audited as `login_locked`. A
  successful sign-in clears the streak.
- **Password policy** — passwords a human types into an admin form
  must be at least 8 characters with at least one letter and one
  digit (`password_policy_error`). Enforced on: staff create +
  reset, and the hand-typed *initial password* on student create
  and faculty create (plus an optional typed password on the
  student / faculty reset actions). System-generated and
  Excel-imported initial passwords are **exempt** — and
  `generate_password()` output satisfies the policy anyway.
  Rejection shows a friendly message and creates nothing. (All
  fixture passwords used by the earlier verify suites —
  `Test@1234`, `Teach@123`, `Other@12345` — already comply, so no
  suite needed changing.)
- **Headers** — every response carries
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`
  and `Referrer-Policy: same-origin`.
- **Upload cap** — `MAX_CONTENT_LENGTH = 10 MB` for all uploads,
  with a friendly 413 page. (This supersedes the v0.3-era 16 MB
  assignment; the per-file rules — e.g. the 5 MB document cap —
  still apply on top.)
- **Cookies** — `SESSION_COOKIE_HTTPONLY = True`,
  `SESSION_COOKIE_SAMESITE = 'Lax'`, and
  `SESSION_COOKIE_SECURE = True` only when deployed
  (`DATABASE_URL` set), so local HTTP testing keeps working.
- **Known remaining item (documented, not done)** — the forms do
  not yet carry per-form **CSRF tokens**; SameSite=Lax session
  cookies are the current mitigation. Adding CSRF tokens to every
  form is a documented future hardening item.

### Go-Live

The homepage demo-accounts box is controlled by the
`show_demo_accounts` setting (seeded `1`, never overwritten): the
public homepage shows the box only while it is on. The admin
toggles it from the **Go-Live** card on `/admin/backup`
(audited as `demo_accounts_toggled`).

## Student Portal Shell (v0.16)

A layout-only restructure of the student portal in the MY IUB
frame — no feature, schema or data changes, and the admin /
faculty shells are untouched. Every student page (dashboard,
documents/tickets panes, attendance, clearance, scholarships,
course repeat, timetable, transport, campus life, vehicle entry
and the ticket thread) now renders inside `student_base.html`,
which mirrors `admin_base.html`'s mechanics (top bar from
`base.html`, a `.layout` flex row, the same `.sidebar` styling
and green/teal+gold theme):

- **Sidebar** — a student identity block (initials avatar, full
  name, registration number, programme — supplied to every page
  by a small context processor, `shell_student`), **Home**, a
  **My Apps** group (My Documents, My Fee Vouchers, Support
  Tickets, My Attendance, My Clearance, Scholarships, Course
  Repeat / Improvement, View Time Table, Transport, Campus Life,
  Vehicle Entry, My Student Card), a **Scholarships** group
  (My Scholarship Profile, Apply / My Applications) and the
  **Document Repository**. On narrow screens the student layout
  stacks (sidebar on top); the admin/faculty layouts are
  unchanged.
- **Active highlighting** — the sidebar item for the current
  page carries `class="active"`, derived from the request path
  (and from `?tab=` / `?view=` for dashboard panes and the
  scholarship profile section).
- **Dashboard** — unchanged content: the same 10 tabs with
  byte-identical labels, the same panes and the same tab JS, now
  inside the shell. Deep links work via `?tab=<pane>` (e.g.
  `?tab=voucher` for My Fee Vouchers) and via `#<pane>` hashes;
  three GET aliases resolve bookmark/sidebar URLs onto the
  panes: `/student/documents` → `?tab=documents`,
  `/student/tickets` → `?tab=tickets`,
  `/student/scholarships/profile` → the scholarships page's
  profile section.
- **De-cluttered panes** — the navigation buttons added inside
  tab panes in earlier steps were removed (Profile: student
  card, clearance, transport, campus life, vehicle entry;
  Enrollments: attendance, timetable; Transcript: course
  repeat). Everything functional stayed: challan PDF download,
  paid-proof upload, Create 2 Installments, transcript and
  roll-slip PDFs, and every form.

## Bluecrest design sample (preview — pending approval)

A self-contained **design sample** of the proposed "CUVAS Bluecrest"
theme (Academic Navy `#17365D`, Primary Blue `#2457A7`, Academic
Purple `#6654A3`, Gold `#E7B34C`, background `#F4F7FB`, white cards,
Inter) built for review **before** any decision to redesign. It is
additive only and reachable solely under `/preview/bluecrest/*`:

- `GET /preview/bluecrest/login` — Bluecrest sign-in page with the
  official CUVAS logo, delivered as text so the repo stays pushable:
  `brand_logo.py` embeds it as a base64 string and
  `GET /brand/cuvas-logo.png` serves the decoded bytes, byte-identical
  to the supplied upload (md5 `0d1f109f6aa1adfe1126ea5379d3e703`;
  never modified, recoloured or recreated).
- `POST /preview/bluecrest/login` — authenticates through the **same**
  `_sign_in` helper as `/login` (identical lockout, attempt recording
  and audit rows; the refactor changed no `/login` behaviour).
  Admins land on the sample dashboard; every other role is signed in
  to its regular portal with a note that the sample covers the admin
  dashboard only.
- `GET /preview/bluecrest/admin` — Bluecrest admin shell + dashboard
  (admin only): navy collapsible-group sidebar whose links all point
  at the real (still green) admin pages, top-bar student search
  (`/admin/students?q=`), and **real data only** — KPI cards (total
  students, active faculty, pending vouchers, ledger outstanding),
  a Students-by-Program SVG donut and Students-by-Session bars,
  pending-approvals counts, latest notifications, recent students
  and the latest audit-log activity.

Everything lives in new files — `static/bluecrest.css`, `brand_logo.py`,
`templates/preview_login.html`, `templates/preview_admin_base.html`,
`templates/preview_admin.html` — plus the routes in `app.py`. **The live green theme is
unchanged**: no existing template, stylesheet or route behaviour was
modified, and `verify_preview.py` (35 checks, both databases)
asserts — alongside the unchanged 843/844 regression profile — that
no non-preview page references Bluecrest at all. If the sample is
rejected, deleting those files and routes restores the status quo;
if it is approved, the full rollout is a separate step.

## Go-Live Checklist

Before real users arrive:

- [ ] **Change ALL demo / default passwords** — `admin` first,
      then the student, faculty, accounts and coe demo logins (or
      deactivate the demo logins you no longer need).
- [ ] **Create the real Accounts and COE staff logins** on
      `/admin/staff` and deactivate the demo staff accounts
      (`accounts`, `coe`).
- [ ] **Turn OFF the demo accounts box** on the public homepage
      (Backup page → Go-Live card) so no demo passwords are
      published.
- [ ] **Set the real LMS / Library / Email links** on the Campus
      Life settings page (`/admin/campus`).
- [ ] **Take the first full Backup** (`/admin/backup`) and store
      the ZIP somewhere safe, off the server.
- [ ] **Review the audit log weekly** (`/admin/audit`) — sign-ins,
      failed sign-ins and lockouts included.

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

`verify_v10.py` adds a 52-check pass over Step 14 (schemes seeded open
with no deadline; profile save + update round-trip; applying blocked
with no profile and with an income-less partial profile — no rows
created; applying succeeds once complete and records the CURRENT
session; duplicate application blocked; closed-scheme and
past-deadline applications blocked — the deadline is set to yesterday
by a fixture; the admin detail page shows the full profile, CGPA 3.63
for the demo student and the ledger's Rs 47,500 outstanding; Approve
refused without an amount, Under Review carries no decision stamp,
Approve stamps amount + remarks + decider and the student sees all
three; a decided application cannot be re-decided; Reject refused
without remarks and the student sees the remarks; student Two's page
contains none of student One's distinctive profile values, statement
or remarks; scheme delete blocked while applications exist; approving
never touches the ledger — row count and the demo balance unchanged;
student + faculty logins rejected from the admin scholarship pages).
v0.10 result: **all eight suites ALL PASS on both backends** (SQLite
and PostgreSQL identical: 43 + 52 + 60 + 72 + 64 + 52 + 59 + 52 = 454
checks). Migration note: v0.10 adds three new tables via the boot DDL
plus the guarded `backfill_v10` scheme seed, so a v0.9 database boots
into v0.10 with its data untouched and a second boot is a no-op.

`verify_v11.py` adds a 64-check pass over Step 15 (eligibility from
published results only — F → Repeat, pass → Improvement, unpublished
invisible; target == original session refused; duplicate active
request refused; cancel only while Requested, and only by the owner;
the already-enrolled-in-target refusal; reject needs remarks and a
decided request cannot be re-decided; the admin rate change prices
the next approval at 2500 × 3 CH = Rs 7,500 and, once restored to
2000, later approvals at 2000 × credits — earlier vouchers never
change; the approval voucher carries the normal-series challan,
kind 'Repeat', its repeat_request_id and its debit entry, and shows
in the student's Financial Voucher tab, Account Statement and
challan PDF; a rejected proof leaves the request Approved with no
enrollment, while verification flips it to Enrolled, creates the
target-session enrollment and credits the ledger exactly once —
a second verify is refused; the enrolled student appears in the
target session's marks-sheet cohort and in the assigned teacher's
roster; while the repeat result is unpublished the Enrolled request
still blocks re-applying, and once published the transcript counts
only the latest attempt — hand-computed CGPA 3.75 agreed by the
helper, the web pane and the PDF, the old attempt flagged Repeated;
the demo transcript stays at CGPA 3.63 with no superseded rows).
v0.11 result: **all nine suites ALL PASS on both backends** (SQLite
and PostgreSQL identical: 43 + 52 + 60 + 72 + 64 + 52 + 59 + 52 + 64
= 518 checks). Migration note: v0.11 adds two tables via the boot
DDL, one additive voucher column via `ensure_columns`, and the
guarded `backfill_v11` rate seed (verified: an admin-changed rate
survives a reboot and the seed never duplicates). One pre-existing
note, unrelated to v0.11: the stale v0.1-era `cuvas_demo.db` checked
in beside the app still carries a `CHECK(role IN ('admin','student'))`
constraint on `users` from before the faculty role existed, so the
v0.7 faculty seed (unchanged by this step) cannot boot against that
file — use a fresh `DB_PATH` or `DATABASE_URL` as the suites do.

`verify_v12.py` adds a 51-check pass over Step 16 (transport seeded
on a fresh DB: exactly the two demo routes with their ordered stops
and pickup times; slot add lands with its teacher/room and lists
grouped by day; all three clashes — class, teacher, and room
(case-insensitive) — refused with their specific messages and no row
written, while a back-to-back slot and a different-day slot pass;
end-before-start refused; the slot form's courses are limited to
the program + semester and its teacher select pre-selects the
course's assigned teacher; an edit into its own time succeeds —
no self-clash — while an edit into another slot's time is refused
with the row unchanged; the student's timetable contains exactly
the slots of their enrolled courses for the current session — an
other-program slot, an unenrolled course's slot and another
session's slot all absent — and the PDF returns real %PDF bytes
containing their own course and not the others; a student with no
current-session enrolments sees the empty state; the faculty
timetable shows only the teacher's own slots and follows the
session switch; route + stop CRUD incl. ordering, invalid pickup
time refused, route delete blocked while stops exist and allowed
once they are gone; inactive routes and their stops hidden from
students but visible to the admin; stop-name search finds Route 1
only for 'satellite', both routes for 'Main Gate', Route 2 only
for 'Hasilpur Road Chowk', and reports no match otherwise; role
guards on both sides). v0.12 result: **all ten suites ALL PASS on
both backends** (SQLite and PostgreSQL identical: 43 + 52 + 60 +
72 + 64 + 52 + 59 + 52 + 64 + 51 = 569 checks). Migration note:
v0.12 adds three tables via the boot DDL plus the guarded
`backfill_v12` transport seed (only while the routes table is
empty), so a v0.11 database boots into v0.12 with its data
untouched and a second boot is a strict no-op — simulated by
dropping the three tables from a booted database and booting
again (tables recreated, demo routes re-seeded, demo students
intact).

`verify_v13.py` adds a 60-check pass for the Campus Life step
(role guards in all directions on the new campus / societies /
vehicle pages for anonymous, admin, faculty and student clients;
the three demo societies seeded exactly once with the IT society
advised by the Demo Teacher and the other advisors `NULL`; the
five campus settings keys seeded empty and never overwritten on a
re-boot; a non-`http(s)` URL refused with nothing saved; the
settings round-trip — saved URLs/info appear as buttons/text on
BOTH the student and faculty campus pages, and clearing the LMS
URL restores the “Not configured yet” note; the student dashboard
still has exactly 10 tabs with byte-identical labels plus the two
new Profile buttons; society join → `Requested` row, duplicate
join blocked (still one row), admin approve stamps decider +
time and the student sees **Member ✓** with the count at 1,
re-deciding refused; reject → the student's re-request reuses the
SAME row with the stamp cleared; society delete blocked while
member rows exist and allowed when memberless; an inactive
society is hidden from students but visible to the admin, with
join attempts a 404; admin Remove deletes a membership row;
vehicle apply with the number normalised to UPPER-case; pass PDF
a 404 before approval; same student + same number refused while
`Requested` AND while `Approved`; an invalid vehicle type
refused; another student MAY request a number that is only
`Requested` elsewhere, but a THIRD student is refused once it is
`Approved` (one vehicle, one pass); approval stamps
`pass_no = VEH-<year>-<id>` and `valid_till` = today + 1 year
(leap-aware); the pass PDF is `%PDF` and its decoded streams
contain the pass number, the vehicle number and “VEHICLE ENTRY
PASS”; the PDF is a 404 for another student and for a pass id
that does not exist; a decided pass refuses re-approve and
re-reject; reject without remarks is refused, and with remarks
the student sees them and may apply again; the admin list search
matches the vehicle number case-insensitively and the
`Approved` status filter hides requested rows). v0.13 result:
**all eleven suites ALL PASS on both backends** (SQLite and
PostgreSQL identical: 43 + 52 + 60 + 72 + 64 + 52 + 59 + 52 +
64 + 51 + 60 = 629 checks). Migration note: v0.13 adds three
tables via the boot DDL plus the guarded `backfill_v13` (settings
keys only when absent, societies only while the table is empty),
so a v0.12 database boots into v0.13 with its data untouched and
a second boot is a strict no-op.

`verify_v14.py` adds a 68-check pass for Step 19 (role guards on
all twelve new URLs for anonymous / student / faculty clients;
failed + successful logins audited with the attempted / actual
username; a controlled fee fixture — three students on one
Rs 15,000 plan: one verifies in full, one only submits a proof,
one splits and verifies one installment — whose report figures
equal independently computed ledger sums: issued 45,000,
collected 22,500, outstanding 22,500 with the session cross-check
equal, challans 4, pending proofs 1, the department row and the
defaulters ordered B (15,000) before C (7,500) in both the page
and the workbook; student-strength counts equal SQL GROUP BY
counts including the program × session matrix cell; a marks
fixture (80 / 40 / absent) whose results row reads appeared 3,
passed 1, failed 2, 33.3%, average 60, highest 80, Published
Yes; an attendance fixture whose report row equals the shared
`attendance_summary()` output — 2 classes held, average 50.0%;
the audit sequence — student create, voucher generate + verify,
marks publish, campus settings save, a student ticket and a
document upload, backup download, logout — recorded with the
right actor each time, and the audit viewer's text / role / date
filters narrowing correctly; the backup ZIP valid with the
workbook + README, no `password_hash` in the users sheet, blobs
under `files/`, and a `backup_downloaded` row afterwards;
empty-session reports rendering cleanly with downloadable
workbooks; the 10 student tabs byte-identical). v0.14 result:
**all twelve suites ALL PASS on both backends** (SQLite and
PostgreSQL identical: 43 + 52 + 60 + 72 + 64 + 52 + 59 + 52 +
64 + 51 + 60 + 68 = 697 checks). Migration note: v0.14 adds ONE
table via the boot DDL (`audit_log`, `CREATE TABLE IF NOT
EXISTS`, no backfill), so a v0.13 database boots into v0.14 with
its data untouched — simulated by dropping `audit_log` from a
booted database and booting again (table recreated, demo data
intact, new pages 200).

`verify_v15.py` adds a 95-check pass over Step 20 (demo staff
seeded with landing redirects; office users bounced from /admin
to their own landing; the full permission matrix — accounts
allowed fees / vouchers / fee report / read-only students and
refused 28 other areas, coe mirrored with results / grade scale /
slips / results + attendance reports, admin superset everywhere;
role-aware sidebars and a role-aware Reports hub; the students
list renders no mutation controls to the offices; staff create /
weak-password refusal / typed reset shown once / deactivate →
sign-in blocked → reactivate, with the primary admin protected
and every action audited; lockout — 4 failures OK, success clears
the streak, 5 failures lock even the correct password out with a
`login_locked` audit row and per-username isolation; the password
policy on student / faculty create + reset, with Excel import
exempt; the three security headers, HttpOnly + SameSite=Lax
cookies and Secure only when deployed; a >10 MB upload refused
with 413; the demo-accounts toggle hiding and restoring the
homepage box, audited; a v0.14-shaped database — users table with
the legacy `CHECK(role IN ('admin','student'))` — booting in a
subprocess, losing the constraint, and serving accounts / coe
logins; faculty portal and the 10 student tabs untouched).
v0.15 result: **all thirteen suites ALL PASS on both backends**
(SQLite and PostgreSQL identical: 43 + 52 + 60 + 72 + 64 + 52 +
59 + 52 + 64 + 51 + 60 + 68 + 95 = **792 checks**). Migration
notes: v0.15 adds ONE table via the boot DDL (`login_attempts`,
`CREATE TABLE IF NOT EXISTS`); `migrate_v15_roles` widens a
legacy role CHECK before any seed/backfill insert can trip it
(verified against the actual stale local demo database: CHECK
present before boot, gone after, every user row preserved, all
five roles able to sign in); `backfill_v15` seeds the demo staff
logins and the `show_demo_accounts` setting only-when-absent.

`verify_v16.py` adds a 52-check pass over the student portal
shell (sidebar present with the identity block and every My
Apps / Scholarships label + href on the dashboard and on the
attendance, clearance, repeat, timetable, transport, campus,
vehicle, scholarships and ticket-thread pages; per-page active
highlighting that differs between pages; the removed in-pane
navigation buttons gone from the Profile / Enrollments /
Transcript panes while the functional voucher actions — challan
PDF, Create 2 Installments, paid-proof upload — and the
transcript / slip PDF downloads remain; `?tab=` deep links
activating panes and highlighting their sidebar items; the
three GET aliases redirecting onto the panes; the 10 dashboard
tab labels byte-identical; a second student seeing only their
own identity in the shell and still getting 404 on the first
student's ticket thread and document; admin, faculty and public
pages carrying no student sidebar). v0.16 result: **843 of 844
checks pass on each backend** (SQLite and PostgreSQL identical:
43 + 52 + 60 + 72 + 64 + 52 + 59 + 52 + 63/64 + 51 + 60 + 68 +
95 + 52) — with **one known, deliberate exception**:
`verify_v11.py`'s check *"baseline web CGPA 1.2 + Repeat button
in Transcript tab"* asserts the literal string
`Course Repeat / Improvement` inside the Transcript pane; that
button was removed on purpose in this restructure (the module
now lives in the sidebar, with the same label), so that single
check fails by design while every other v11 check passes. The
suite file itself was not edited.

## Not in v0.16

Posting an approved scholarship award to the fee ledger /
vouchers, surveys (deferred by the user), backup restore
(deliberately manual), per-form CSRF tokens (documented above as
a future hardening item).
