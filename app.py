"""
MY CUVAS — Campus Management System (Demo) v0.16
Flask + Jinja, server-rendered. Phase 1 steps 1-3 (v0.1) + v0.2 foundation:
  6. Real database layer — PostgreSQL when DATABASE_URL is set (psycopg v3),
     SQLite otherwise (local dev / demo fallback). Idempotent schema + seed.
  7. Admin CRUD for Departments / Programs / Sessions / Courses, and full
     Students management (list/search/filter, add/edit, auto student login,
     password reset, Excel import/export with template).
  8. v0.3 working fee system — fee heads + fee plans, voucher generation
     (single + bulk) with sequential challan numbers, challan PDF (ReportLab),
     2-installment splits, paid-proof upload stored as a DB blob, admin
     verify/reject, and a real append-only ledger behind the Account Statement.
  9. v0.4 results & exams — editable grading scale (grade_bands), marks entry
     sheets with publish/unpublish, marks Excel download/import, transcripts
     driven by published results (one SGPA/CGPA helper for web tab + PDF),
     transcript PDF, and roll number slips (single + bulk PDF).
 10. v0.6 student services — document uploads with admin verification
     (student_documents, files stored as DB blobs), support tickets with
     admin/student threads (tickets + ticket_messages), admin-managed
     notifications feeding the landing page + student News Feed (the v0.1
     notifications table, extended additively), an official document
     repository (repository_docs, blobs), and a student card PDF with a
     Code39 barcode of the registration number.
 11. v0.7 faculty portal — faculty records with auto-created logins
     (users.faculty_id, role 'faculty'), course assignments (one primary
     teacher per course+session), and a /faculty portal where a teacher
     sees only their own courses, the class roster (+ Excel export) and a
     marks sheet that writes into the same results store as the admin
     sheet. Faculty can never publish; once the admin publishes a set,
     the faculty sheet locks read-only.
 12. v0.8 attendance — faculty mark a per-date sheet (Present / Absent /
     Late / Leave) for their own assignments only (upsert per student+date,
     future dates rejected, a marked date can be deleted); ONE shared
     helper (attendance_summary) computes classes held + per-student
     P/A/L/Leave counts + percentage = present / classes held, and feeds
     the faculty summary (+ Excel), the read-only admin overview and the
     student's own /student/attendance page (own rows only).
 13. v0.9 clearance — a student applies for degree clearance; one item is
     created per active clearance unit (clearance_units, admin-managed).
     The Accounts / Fees item is AUTO-EVALUATED at apply time from the
     student's ledger balance (dues -> Objected with a system note, zero
     -> Cleared by 'System'); admins clear or object each item (an
     objection needs a remark), the student can request a recheck of an
     objected item, and once every item is Cleared the request completes
     and a clearance certificate PDF becomes downloadable.
 14. v0.10 scholarships — scholarship schemes (admin CRUD, open/close +
     deadline), a per-student socio-economic profile (family + bank
     details, one record per student) that must be COMPLETE before the
     student can apply, and applications (one per student + scheme +
     session) reviewed on an admin detail page that shows the profile,
     the transcript CGPA (same helper as the transcript) and the ledger
     outstanding dues. Admins set Under Review, Approve (with an awarded
     amount) or Reject (remark required); a decided application is
     final. Approving records the award ONLY — it never writes to the
     fee ledger in this version.
 15. v0.11 course repeat / improvement — a student applies to repeat a
     failed course (or improve a passed one) from their PUBLISHED
     results into a different session; the fee is an admin-set
     per-credit-hour rate (app_settings) x the course credit hours.
     Admin approval issues a normal fee voucher (kind='Repeat',
     vouchers.repeat_request_id) through the same challan + ledger
     path as every other voucher; when that voucher's proof is
     VERIFIED, the request flips to Enrolled and the student is
     enrolled for the course in the target session, joining the marks
     sheet cohort and faculty roster like any other student. The
     transcript counts ONLY the latest attempt of a repeated course
     in SGPA/CGPA (earlier attempts stay visible, flagged 'Repeated');
     transcripts of students without repeats are unchanged.
 16. v0.12 timetable + transport — admins build the weekly timetable
     per program + semester + session (timetable_slots); saving a slot
     is clash-checked (same class, same teacher or same room already
     busy at an overlapping time in that session is refused, while
     back-to-back slots are fine). Students see 'My Time Table' for
     the current session (only their enrolled courses) on the web and
     as a PDF; teachers see their own teaching timetable per session.
     Transport is admin-managed bus routes with ordered pickup stops
     (transport_routes + transport_stops, seeded with two clearly-demo
     routes); students browse the active routes and search by stop
     name.
 17. v0.13 campus life — admin-configured service links/info for the
     LMS, Library and student Email (five app_settings keys, edited on
     /admin/campus) surface as identical cards in the student and
     faculty Campus Life pages; only configured services show a live
     button. Student societies (societies + society_members) are
     seeded with three demo societies; students request to join and an
     admin approves or rejects (a rejected student may request again).
     Vehicle entry passes (vehicle_passes) are applied for by the
     student, approved by an admin (pass number VEH-<year>-<id> and a
     validity date are stamped at approval), and downloaded as a
     Code39-barcode pass PDF; the same vehicle number can never hold
     two live passes. (Step 17 surveys were deferred by the user and
     are deliberately NOT part of this release.)
 18. v0.14 reports, audit log & backup — an admin Reports centre
     (/admin/reports) with four reports whose figures come from the
     SAME shared computations as the screens they summarise: Fee
     Collection (ledger-based issued / collected / outstanding for a
     session, department breakdown + defaulters), Student Strength,
     Results Summary (grades derived via result_grade_gp) and
     Attendance Summary (the shared attendance_summary helper) —
     each with an Excel export. An append-only audit_log records
     sign-ins (success + failure), sign-outs and every significant
     create / update / delete / decision across the admin, faculty
     and student portals, written by ONE helper (log_audit) that can
     never break the action it records. /admin/backup downloads a
     full ZIP backup: one Excel workbook (a sheet per table, the
     users sheet WITHOUT password hashes, document tables as
     metadata only) plus every stored file blob under files/ and a
     README. Restore is deliberately manual / by a developer.
 19. v0.15 staff roles, security & go-live — two office roles join
     admin / student / faculty: 'accounts' (fee heads, fee plans,
     vouchers end-to-end, read-only students, the Fee Collection
     report) and 'coe' (results + grade scale + roll slips, read-only
     students incl. transcripts, the Results and Attendance reports),
     enforced per-route by a multi-role role_required and a role-aware
     admin sidebar; each office gets its own landing dashboard
     (/accounts, /coe) and the admin manages staff logins on
     /admin/staff (create / reset / deactivate, primary admin
     protected). Security: sign-in lockout (5 consecutive failures
     within 15 minutes locks the username, audited as login_locked),
     a password policy (8+ chars, a letter and a digit) for
     interactively-set passwords, security headers on every response,
     a 10 MB upload cap with a friendly 413, and hardened session
     cookies (HttpOnly, SameSite=Lax, Secure when deployed).
     Go-live: the homepage demo-accounts box is controlled by the
     show_demo_accounts setting, toggled from the Backup page.
 20. v0.16 student portal shell — a UI restructure ONLY (no feature,
     schema or route changes): every student page now renders inside a
     MY IUB-style shell (student_base.html) with a left sidebar —
     student identity block, Home, a 'My Apps' group, a 'Scholarships'
     group and the Document Repository — mirroring the admin portal's
     sidebar mechanics in the same green/teal+gold theme. Module
     navigation moved OUT of the dashboard tab panes into the sidebar;
     the in-pane navigation buttons were removed while every functional
     action (challan PDF, paid-proof upload, installments, transcript /
     slip PDFs, forms) stayed. The dashboard keeps its 10 tabs
     byte-identical and deep-links via ?tab=<pane> (already supported);
     /student/documents, /student/tickets and
     /student/scholarships/profile exist as GET aliases that redirect
     to the matching dashboard pane / scholarships section so sidebar
     and bookmark URLs resolve. A context processor supplies the
     sidebar identity (shell_student) to every student page.

ALL seed data is fictional / demo-only. No real people's data.
Run:  python app.py   (or: flask --app app run)
"""
import datetime
import io
import math
import os
import re
import secrets
import sqlite3
import string
from functools import wraps

from flask import (Flask, abort, g, redirect, render_template, request,
                   send_file, session, url_for, flash)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------ config
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
PG = bool(DATABASE_URL)

if os.environ.get("DB_PATH"):
    DB_PATH = os.environ["DB_PATH"]
elif os.environ.get("VERCEL"):
    DB_PATH = "/tmp/cuvas_demo.db"
else:
    DB_PATH = os.path.join(BASE_DIR, "cuvas_demo.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "demo-only-secret-change-me")

# --- v0.15 security hardening -------------------------------------------
# Upload cap: any request body over 10 MB is refused with a friendly 413
# (see the error handler below) instead of being read into memory / DB.
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
# Session cookies: HttpOnly + SameSite=Lax everywhere; Secure only in the
# deployed configuration (DATABASE_URL set — production runs over HTTPS),
# so plain-HTTP local testing keeps working.
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
if PG:
    app.config["SESSION_COOKIE_SECURE"] = True


@app.after_request
def _security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    return resp


@app.errorhandler(413)
def _upload_too_large(_err):
    return ("""<!doctype html><html><head><title>Upload too large</title></head>
<body style="font-family:sans-serif;margin:3em">
<h1>Upload too large</h1>
<p>The maximum upload size is <strong>10 MB</strong>. Please choose a
smaller file and try again.</p>
<p><a href="/">← Back to the home page</a></p>
</body></html>""", 413)

# ------------------------------------------------------- data-access layer
# One thin wrapper over sqlite3 / psycopg v3 so the rest of the app writes a
# single dialect: "?" placeholders and dict-style rows everywhere.
#   db.execute(sql, params)  -> cursor wrapper (.fetchone()/.fetchall() dicts)
#   db.insert(sql, params)   -> new row id (lastrowid / RETURNING id)
#   db.executemany(sql, seq) / db.commit() / db.rollback()

if PG:
    import psycopg
    from psycopg.rows import dict_row


class _Cursor:
    def __init__(self, cur):
        self._cur = cur

    @property
    def lastrowid(self):
        return getattr(self._cur, "lastrowid", None)

    def fetchone(self):
        row = self._cur.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self):
        return [dict(r) for r in self._cur.fetchall()]


class DB:
    def __init__(self, conn):
        self.conn = conn

    def _sql(self, sql):
        return sql.replace("?", "%s") if PG else sql

    def execute(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(self._sql(sql), tuple(params))
        return _Cursor(cur)

    def insert(self, sql, params=()):
        cur = self.conn.cursor()
        if PG:
            cur.execute(self._sql(sql) + " RETURNING id", tuple(params))
            return cur.fetchone()["id"]
        cur.execute(sql, tuple(params))
        return cur.lastrowid

    def executemany(self, sql, seq):
        cur = self.conn.cursor()
        cur.executemany(self._sql(sql), [tuple(p) for p in seq])
        return _Cursor(cur)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        try:
            self.conn.rollback()
        except Exception:
            pass


def connect():
    if PG:
        return DB(psycopg.connect(DATABASE_URL, row_factory=dict_row))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return DB(conn)


def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.conn.close()


@app.context_processor
def _student_shell_context():
    """v0.16: identity data for the student sidebar shell.

    Several student pages (transport, campus, vehicle, ticket thread)
    do not load the student record for their own content; the sidebar
    needs name / registration no / program on EVERY student page, so
    it is supplied here instead of changing those views. Presentation
    only — returns {} for every non-student render."""
    if session.get("role") != "student" or not session.get("student_id"):
        return {}
    try:
        st = get_db().execute(
            """SELECT s.name, s.registration_no, p.name AS prog
               FROM students s LEFT JOIN programs p ON p.id=s.program_id
               WHERE s.id=?""", (session["student_id"],)).fetchone()
    except Exception:
        st = None
    return {"shell_student": st}


LIKE = "ILIKE" if PG else "LIKE"  # case-insensitive search on both backends


def is_unique_error(exc):
    msg = str(exc).lower()
    return "unique" in msg or "duplicate key" in msg


# ------------------------------------------------------------------ schema
_PK = "SERIAL PRIMARY KEY" if PG else "INTEGER PRIMARY KEY AUTOINCREMENT"

DDL = [
    f"""CREATE TABLE IF NOT EXISTS users (
        id {_PK}, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
        role TEXT NOT NULL, display_name TEXT NOT NULL,
        student_id INTEGER, is_active INTEGER DEFAULT 1)""",
    f"""CREATE TABLE IF NOT EXISTS departments (
        id {_PK}, name TEXT NOT NULL, code TEXT UNIQUE NOT NULL, faculty_name TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS programs (
        id {_PK}, department_id INTEGER REFERENCES departments(id),
        name TEXT NOT NULL, degree_level TEXT, duration_semesters INTEGER)""",
    f"""CREATE TABLE IF NOT EXISTS academic_sessions (
        id {_PK}, name TEXT UNIQUE NOT NULL, starts_on TEXT, ends_on TEXT,
        is_open INTEGER DEFAULT 0)""",
    f"""CREATE TABLE IF NOT EXISTS students (
        id {_PK}, registration_no TEXT UNIQUE NOT NULL, cnic TEXT UNIQUE,
        name TEXT NOT NULL, father_name TEXT, gender TEXT, dob TEXT,
        domicile TEXT, blood_group TEXT, phone TEXT, email TEXT,
        address TEXT, address_present TEXT, address_permanent TEXT,
        campus TEXT, status TEXT,
        department_id INTEGER REFERENCES departments(id),
        program_id INTEGER REFERENCES programs(id),
        session_id INTEGER REFERENCES academic_sessions(id),
        session_name TEXT, current_semester INTEGER)""",
    f"""CREATE TABLE IF NOT EXISTS certificates (
        id {_PK}, student_id INTEGER, title TEXT, board TEXT, passing_year TEXT,
        total_marks INTEGER, obtained_marks INTEGER)""",
    f"""CREATE TABLE IF NOT EXISTS courses (
        id {_PK}, program_id INTEGER, semester_no INTEGER, code TEXT, title TEXT,
        credit_theory INTEGER, credit_lab INTEGER, faculty_name TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS enrollments (
        id {_PK}, student_id INTEGER, course_id INTEGER, session_name TEXT, semester_no INTEGER)""",
    f"""CREATE TABLE IF NOT EXISTS results (
        id {_PK}, student_id INTEGER, course_id INTEGER, semester_no INTEGER,
        grade TEXT, grade_point REAL, remarks TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS vouchers (
        id {_PK}, student_id INTEGER, challan_no TEXT UNIQUE, title TEXT,
        amount INTEGER, due_date TEXT, status TEXT, remarks TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS fee_plan_lines (
        id {_PK}, head TEXT, amount INTEGER)""",
    f"""CREATE TABLE IF NOT EXISTS ledger_entries (
        id {_PK}, student_id INTEGER, voucher_title TEXT, challan_no TEXT,
        entry_date TEXT, description TEXT, debit INTEGER DEFAULT 0, credit INTEGER DEFAULT 0)""",
    f"""CREATE TABLE IF NOT EXISTS notifications (
        id {_PK}, title TEXT, body TEXT, published_at TEXT)""",
    # --- v0.3 finance ---
    f"""CREATE TABLE IF NOT EXISTS fee_heads (
        id {_PK}, name TEXT UNIQUE NOT NULL)""",
    f"""CREATE TABLE IF NOT EXISTS fee_plans (
        id {_PK}, program_id INTEGER REFERENCES programs(id),
        session_id INTEGER REFERENCES academic_sessions(id),
        semester_no INTEGER, title TEXT, due_date TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS counters (
        name TEXT PRIMARY KEY, value INTEGER NOT NULL DEFAULT 0)""",
    # --- v0.4 results / grading ---
    f"""CREATE TABLE IF NOT EXISTS grade_bands (
        id {_PK}, min_marks REAL NOT NULL, grade TEXT NOT NULL,
        grade_point REAL NOT NULL)""",
    # --- v0.6 student services (new tables only) ---
    f"""CREATE TABLE IF NOT EXISTS student_documents (
        id {_PK}, student_id INTEGER REFERENCES students(id),
        doc_type TEXT, file_name TEXT, file_mime TEXT,
        file_data {"BYTEA" if PG else "BLOB"},
        status TEXT DEFAULT 'Pending', admin_remarks TEXT,
        uploaded_at TEXT, reviewed_at TEXT, reviewed_by TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS tickets (
        id {_PK}, student_id INTEGER REFERENCES students(id),
        category TEXT, subject TEXT, status TEXT DEFAULT 'Open',
        created_at TEXT, updated_at TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS ticket_messages (
        id {_PK}, ticket_id INTEGER REFERENCES tickets(id),
        sender_role TEXT, sender_name TEXT, body TEXT, created_at TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS repository_docs (
        id {_PK}, title TEXT, category TEXT, description TEXT,
        file_name TEXT, file_mime TEXT,
        file_data {"BYTEA" if PG else "BLOB"},
        uploaded_by TEXT, created_at TEXT, is_published INTEGER DEFAULT 1)""",
    # --- v0.7 faculty (new tables only) ---
    f"""CREATE TABLE IF NOT EXISTS faculty (
        id {_PK}, full_name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
        phone TEXT, designation TEXT,
        department_id INTEGER REFERENCES departments(id),
        is_active INTEGER DEFAULT 1, created_at TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS course_assignments (
        id {_PK}, faculty_id INTEGER REFERENCES faculty(id),
        course_id INTEGER REFERENCES courses(id),
        session_id INTEGER REFERENCES academic_sessions(id),
        created_at TEXT, UNIQUE(faculty_id, course_id, session_id))""",
    # --- v0.8 attendance (new table only; class_date is ISO text; plain
    # INTEGER ids like enrollments/results — no REFERENCES, so older
    # migration simulations that drop course_assignments still work on PG)
    f"""CREATE TABLE IF NOT EXISTS attendance (
        id {_PK}, assignment_id INTEGER, student_id INTEGER,
        class_date TEXT NOT NULL, status TEXT NOT NULL,
        marked_by_faculty_id INTEGER,
        created_at TEXT, updated_at TEXT,
        UNIQUE(assignment_id, student_id, class_date))""",
    # --- v0.9 clearance (new tables only; plain INTEGER ids like
    # enrollments/results/attendance — no REFERENCES, so older migration
    # simulations stay safe on PG; unit_name is a snapshot on each item
    # so later unit renames/deactivations never rewrite history) ---
    f"""CREATE TABLE IF NOT EXISTS clearance_units (
        id {_PK}, name TEXT NOT NULL, sort_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1, is_accounts INTEGER DEFAULT 0)""",
    f"""CREATE TABLE IF NOT EXISTS clearance_requests (
        id {_PK}, student_id INTEGER,
        status TEXT DEFAULT 'In Progress',
        created_at TEXT, completed_at TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS clearance_items (
        id {_PK}, request_id INTEGER, unit_id INTEGER, unit_name TEXT,
        status TEXT DEFAULT 'Pending', remarks TEXT, auto_note TEXT,
        action_by TEXT, action_at TEXT,
        recheck_requested INTEGER DEFAULT 0, created_at TEXT,
        UNIQUE(request_id, unit_id))""",
    # --- v0.10 scholarships (new tables only; plain INTEGER ids like
    # enrollments/results/attendance/clearance — no REFERENCES, so older
    # migration simulations stay safe on PG) ---
    f"""CREATE TABLE IF NOT EXISTS scholarship_schemes (
        id {_PK}, name TEXT NOT NULL, provider TEXT, description TEXT,
        eligibility TEXT, is_open INTEGER DEFAULT 1, deadline TEXT,
        created_at TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS scholarship_profiles (
        id {_PK}, student_id INTEGER UNIQUE NOT NULL,
        father_name TEXT, father_status TEXT, father_occupation TEXT,
        guardian_name TEXT, guardian_relation TEXT,
        family_members INTEGER, siblings_studying INTEGER,
        monthly_income INTEGER, monthly_expenses INTEGER,
        house_status TEXT, bank_name TEXT, account_title TEXT,
        account_number TEXT, bank_branch TEXT, updated_at TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS scholarship_applications (
        id {_PK}, student_id INTEGER, scheme_id INTEGER, session_id INTEGER,
        statement TEXT, status TEXT DEFAULT 'Applied',
        admin_remarks TEXT, awarded_amount INTEGER,
        decided_by TEXT, decided_at TEXT, created_at TEXT,
        UNIQUE(student_id, scheme_id, session_id))""",
    # --- v0.11 course repeat / improvement (new tables only; plain
    # INTEGER ids like enrollments/results — no REFERENCES, so older
    # migration simulations stay safe on PG). app_settings is a tiny
    # key-value store (the app had none before v0.11). ---
    f"""CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY, value TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS repeat_requests (
        id {_PK}, student_id INTEGER, course_id INTEGER,
        from_session_id INTEGER, target_session_id INTEGER,
        kind TEXT, reason TEXT,
        status TEXT DEFAULT 'Requested', admin_remarks TEXT,
        voucher_id INTEGER, decided_by TEXT, decided_at TEXT,
        created_at TEXT)""",
    # --- v0.12 timetable + transport (new tables only; plain INTEGER
    # ids like enrollments/results — no REFERENCES, so older migration
    # simulations stay safe on PG). Times are 'HH:MM' 24-hour text,
    # which sorts and compares correctly as strings. ---
    f"""CREATE TABLE IF NOT EXISTS timetable_slots (
        id {_PK}, program_id INTEGER, semester INTEGER, session_id INTEGER,
        course_id INTEGER, faculty_id INTEGER,
        day_of_week TEXT, start_time TEXT, end_time TEXT, room TEXT,
        created_at TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS transport_routes (
        id {_PK}, name TEXT NOT NULL, title TEXT, description TEXT,
        is_active INTEGER DEFAULT 1, created_at TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS transport_stops (
        id {_PK}, route_id INTEGER, stop_name TEXT NOT NULL,
        pickup_time TEXT, sort_order INTEGER DEFAULT 0)""",
    # --- v0.13 campus life (new tables only; plain INTEGER ids like
    # enrollments/results — no REFERENCES, so older migration
    # simulations stay safe on PG). The LMS/Library/Email service
    # links + info live in the v0.11 app_settings store, not tables. ---
    f"""CREATE TABLE IF NOT EXISTS societies (
        id {_PK}, name TEXT NOT NULL, description TEXT,
        advisor_faculty_id INTEGER, is_active INTEGER DEFAULT 1,
        created_at TEXT)""",
    f"""CREATE TABLE IF NOT EXISTS society_members (
        id {_PK}, society_id INTEGER, student_id INTEGER,
        status TEXT DEFAULT 'Requested', created_at TEXT,
        decided_by TEXT, decided_at TEXT,
        UNIQUE(society_id, student_id))""",
    f"""CREATE TABLE IF NOT EXISTS vehicle_passes (
        id {_PK}, student_id INTEGER, vehicle_type TEXT,
        vehicle_no TEXT, make_model TEXT, color TEXT,
        status TEXT DEFAULT 'Requested', pass_no TEXT,
        valid_till TEXT, admin_remarks TEXT,
        decided_by TEXT, decided_at TEXT, created_at TEXT)""",
    # --- v0.14 audit log (new table only; plain INTEGER user id like
    # enrollments/results — no REFERENCES. Append-only by design: the
    # ONLY writer is log_audit() below with plain INSERTs; no route
    # edits or deletes rows. username/role are snapshots taken at the
    # time of the action, so later renames never rewrite history.) ---
    f"""CREATE TABLE IF NOT EXISTS audit_log (
        id {_PK}, user_id INTEGER, username TEXT, role TEXT,
        action TEXT, details TEXT, created_at TEXT)""",
    # --- v0.15 sign-in lockout (new table only; one row per sign-in
    # attempt, success flag included, so the lockout helper can count
    # consecutive failures since the last success) ---
    f"""CREATE TABLE IF NOT EXISTS login_attempts (
        id {_PK}, username TEXT, success INTEGER DEFAULT 0,
        attempted_at TEXT)""",
]

# Columns added in v0.2 to tables that may already exist from v0.1.
EXTRA_COLUMNS = {
    "users": [("is_active", "INTEGER DEFAULT 1"),
              # --- v0.7: links a faculty login to its faculty record ---
              ("faculty_id", "INTEGER")],
    "students": [("cnic", "TEXT"), ("domicile", "TEXT"), ("blood_group", "TEXT"),
                 ("address_present", "TEXT"), ("address_permanent", "TEXT"),
                 ("session_id", "INTEGER")],
    # --- v0.3 finance columns (existing vouchers / plan lines / ledger) ---
    "vouchers": [("session_id", "INTEGER"), ("semester_no", "INTEGER"),
                 ("kind", "TEXT"), ("parent_voucher_id", "INTEGER"),
                 ("fee_plan_id", "INTEGER"), ("payment_channel", "TEXT"),
                 ("paid_at", "TEXT"), ("proof_filename", "TEXT"),
                 ("proof_mimetype", "TEXT"),
                 ("proof_blob", "BYTEA" if PG else "BLOB"),
                 # --- v0.11: links a repeat voucher to its request ---
                 ("repeat_request_id", "INTEGER")],
    "fee_plan_lines": [("plan_id", "INTEGER"), ("head_id", "INTEGER")],
    "ledger_entries": [("voucher_id", "INTEGER")],
    # --- v0.4 results columns (marks, publish state, session/enrollment link) ---
    "results": [("session_id", "INTEGER"), ("marks_obtained", "REAL"),
                ("is_absent", "INTEGER DEFAULT 0"),
                ("is_published", "INTEGER DEFAULT 0"),
                ("enrollment_id", "INTEGER")],
    # --- v0.6 notifications columns (the v0.1 table gains audience / publish
    # state / audit fields additively; existing rows keep showing because the
    # defaults are audience='All' and is_published=1) ---
    "notifications": [("audience", "TEXT DEFAULT 'All'"),
                      ("is_published", "INTEGER DEFAULT 1"),
                      ("created_by", "TEXT"), ("created_at", "TEXT")],
}


def ensure_columns(db, table, cols):
    if PG:
        existing = {r["column_name"] for r in db.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name=?",
            (table,)).fetchall()}
    else:
        existing = {r["name"] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, ddl in cols:
        if name not in existing:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init_db():
    db = connect()
    for stmt in DDL:
        db.execute(stmt)
    for table, cols in EXTRA_COLUMNS.items():
        ensure_columns(db, table, cols)
    db.commit()
    migrate_v15_roles(db)
    db.commit()
    seed(db)
    backfill_v03(db)
    backfill_v04(db)
    backfill_v06(db)
    backfill_v07(db)
    backfill_v09(db)
    backfill_v10(db)
    backfill_v11(db)
    backfill_v12(db)
    backfill_v13(db)
    backfill_v15(db)
    db.commit()
    db.conn.close()


# ------------------------------------------------------- v0.3 finance backfill
def backfill_v03(db):
    """Idempotent v0.3 migration for databases created by v0.1/v0.2 (and for
    fresh seeds): build fee heads + the demo fee plan from the legacy global
    fee_plan_lines, tag seeded vouchers, link ledger rows to their voucher,
    and make sure every voucher has its debit (and, if Paid, credit) entry so
    statement totals always match the voucher list. Safe to run repeatedly."""
    # --- repair v0.1-era students: they carry session_name but no session_id,
    # and their DB may have no session rows at all. Create/link them so fee
    # plans (which match on session_id) work on migrated databases too. ---
    for r in db.execute(
            """SELECT DISTINCT session_name FROM students
               WHERE session_id IS NULL AND session_name IS NOT NULL AND session_name<>''""").fetchall():
        srow = db.execute("SELECT id FROM academic_sessions WHERE name=?",
                          (r["session_name"],)).fetchone()
        sid = srow["id"] if srow else db.insert(
            "INSERT INTO academic_sessions (name,starts_on,ends_on,is_open) VALUES (?,?,?,?)",
            (r["session_name"], "", "", 0))
        db.execute("UPDATE students SET session_id=? WHERE session_name=? AND session_id IS NULL",
                   (sid, r["session_name"]))

    # --- fee heads from legacy plan lines (or the standard demo heads) ---
    if not db.execute("SELECT COUNT(*) c FROM fee_heads").fetchone()["c"]:
        heads = []
        for r in db.execute(
                "SELECT head FROM fee_plan_lines WHERE head IS NOT NULL ORDER BY id").fetchall():
            if r["head"] not in heads:
                heads.append(r["head"])
        if not heads:
            heads = ["Tuition Fee (Demo)", "University / Institute Charges (Demo)",
                     "Transport Charges (Demo)", "Library Charges (Demo)",
                     "Examination Charges (Demo)"]
        for h in heads:
            db.insert("INSERT INTO fee_heads (name) VALUES (?)", (h,))
    head_ids = {r["name"]: r["id"] for r in db.execute("SELECT id,name FROM fee_heads").fetchall()}

    # --- demo fee plan for the demo student, built from the legacy lines ---
    demo = db.execute(
        "SELECT * FROM students WHERE registration_no='CUVAS-DEMO-2026-001'").fetchone()
    demo_sid = None
    if demo:
        demo_sid = demo.get("session_id")
        if not demo_sid and demo.get("session_name"):
            # v0.1-era rows have session_name but a NULL session_id column
            srow = db.execute("SELECT id FROM academic_sessions WHERE name=?",
                               (demo["session_name"],)).fetchone()
            if srow:
                demo_sid = srow["id"]
    if demo and demo.get("program_id") and demo_sid:
        plan = db.execute(
            "SELECT id FROM fee_plans WHERE program_id=? AND session_id=? AND semester_no=?",
            (demo["program_id"], demo_sid, demo["current_semester"] or 3)).fetchone()
        if not plan:
            plan_id = db.insert(
                "INSERT INTO fee_plans (program_id,session_id,semester_no,title,due_date) VALUES (?,?,?,?,?)",
                (demo["program_id"], demo_sid, demo["current_semester"] or 3,
                 "Semester Fee Plan (Demo)", "2026-11-15"))
        else:
            plan_id = plan["id"]
        # attach the legacy global lines to this plan (once only)
        for line in db.execute(
                "SELECT * FROM fee_plan_lines WHERE plan_id IS NULL ORDER BY id").fetchall():
            db.execute("UPDATE fee_plan_lines SET plan_id=?, head_id=? WHERE id=?",
                       (plan_id, head_ids.get(line["head"]), line["id"]))
        # tag the demo student's vouchers
        db.execute(
            "UPDATE vouchers SET kind='admission' WHERE student_id=? AND challan_no='DEMO-CH-1000' AND kind IS NULL",
            (demo["id"],))
        db.execute(
            "UPDATE vouchers SET kind='semester', semester_no=2, session_id=? "
            "WHERE student_id=? AND challan_no='DEMO-CH-1001' AND kind IS NULL",
            (demo_sid, demo["id"]))
        db.execute(
            "UPDATE vouchers SET kind='semester', semester_no=?, session_id=?, fee_plan_id=? "
            "WHERE student_id=? AND challan_no='DEMO-CH-1002' AND kind IS NULL",
            (demo["current_semester"] or 3, demo_sid, plan_id, demo["id"]))
    db.execute("UPDATE vouchers SET kind='semester' WHERE kind IS NULL")

    # --- link ledger rows to vouchers by challan number ---
    db.execute(
        """UPDATE ledger_entries SET voucher_id=(
               SELECT id FROM vouchers WHERE vouchers.challan_no=ledger_entries.challan_no)
           WHERE voucher_id IS NULL AND challan_no IS NOT NULL""")

    # --- guarantee debit/credit entries for every voucher ---
    for v in db.execute("SELECT * FROM vouchers ORDER BY id").fetchall():
        has_debit = db.execute(
            "SELECT COUNT(*) c FROM ledger_entries WHERE voucher_id=? AND debit>0",
            (v["id"],)).fetchone()["c"]
        if not has_debit:
            db.insert(
                """INSERT INTO ledger_entries (student_id,voucher_id,voucher_title,challan_no,
                   entry_date,description,debit,credit) VALUES (?,?,?,?,?,?,?,?)""",
                (v["student_id"], v["id"], v["title"], v["challan_no"],
                 v["due_date"] or _today(), f"{v['title']} charged", v["amount"] or 0, 0))
        if v["status"] == "Paid":
            has_credit = db.execute(
                "SELECT COUNT(*) c FROM ledger_entries WHERE voucher_id=? AND credit>0",
                (v["id"],)).fetchone()["c"]
            if not has_credit:
                channel = v.get("payment_channel") or "Bank"
                db.insert(
                    """INSERT INTO ledger_entries (student_id,voucher_id,voucher_title,challan_no,
                       entry_date,description,debit,credit) VALUES (?,?,?,?,?,?,?,?)""",
                    (v["student_id"], v["id"], v["title"], v["challan_no"],
                     (v.get("paid_at") or _today())[:10],
                     f"Payment received — {channel}", 0, v["amount"] or 0))


# ------------------------------------------------------- v0.4 results backfill
DEFAULT_GRADE_BANDS = [
    (85, "A", 4.00), (80, "A-", 3.70), (75, "B+", 3.30), (70, "B", 3.00),
    (65, "B-", 2.70), (60, "C+", 2.30), (55, "C", 2.00), (50, "D", 1.00),
    (0, "F", 0.00),
]


def backfill_v04(db):
    """Idempotent v0.4 migration: seed the default grading scale, and mark the
    pre-v0.4 seeded demo results as published (they pre-date marks entry, so
    they are recognised by: not absent, no marks recorded, a stored grade).
    Rows created by the v0.4 marks sheet always carry marks or the absent
    flag, so this never re-publishes results an admin has unpublished."""
    if not db.execute("SELECT COUNT(*) c FROM grade_bands").fetchone()["c"]:
        for min_marks, grade, gp in DEFAULT_GRADE_BANDS:
            db.insert("INSERT INTO grade_bands (min_marks,grade,grade_point) VALUES (?,?,?)",
                      (min_marks, grade, gp))
    db.execute(
        """UPDATE results SET is_published=1
           WHERE COALESCE(is_published,0)=0 AND COALESCE(is_absent,0)=0
             AND marks_obtained IS NULL AND grade IS NOT NULL""")


# ------------------------------------------------------- v0.6 services backfill
def backfill_v06(db):
    """Idempotent v0.6 migration for databases created by v0.1–v0.4: the
    notifications table gains its v0.6 columns via ensure_columns (existing
    rows get audience='All' / is_published=1 from the column defaults, so
    seeded announcements keep showing); here we only backfill created_at
    from the legacy published_at date. No-op on re-run."""
    db.execute(
        """UPDATE notifications SET created_at=published_at
           WHERE created_at IS NULL AND published_at IS NOT NULL""")


# ------------------------------------------------------- v0.7 faculty backfill
def backfill_v07(db):
    """Idempotent v0.7 migration: seed ONE fictional demo teacher (with the
    'faculty' demo login) and assign them two of the demo student's current
    courses in the demo student's own session, so the faculty roster is
    non-empty out of the box. Guarded on the faculty table being empty —
    a strict no-op once any faculty exist, and it never touches results,
    so the seeded demo transcript (CGPA 3.63) is unaffected."""
    if db.execute("SELECT COUNT(*) c FROM faculty").fetchone()["c"]:
        return
    demo = db.execute(
        "SELECT * FROM students WHERE registration_no='CUVAS-DEMO-2026-001'").fetchone()
    if not demo:
        return
    fid = db.insert(
        """INSERT INTO faculty (full_name,email,phone,designation,department_id,
           is_active,created_at) VALUES (?,?,?,?,?,?,?)""",
        ("Demo Teacher", "demo.teacher@cuvas.edu.pk", "0300-0000100",
         "Lecturer", demo.get("department_id"), 1, _now()))
    login_row = db.execute("SELECT * FROM users WHERE username='faculty'").fetchone()
    if login_row is None:
        db.insert(
            """INSERT INTO users (username,password_hash,role,display_name,faculty_id)
               VALUES (?,?,?,?,?)""",
            ("faculty", generate_password_hash("Faculty@123"), "faculty",
             "Demo Teacher", fid))
    elif not login_row.get("faculty_id"):
        # repair a half-migrated demo login: link it to the fresh record
        db.execute(
            "UPDATE users SET role='faculty', display_name='Demo Teacher', "
            "password_hash=?, faculty_id=? WHERE id=?",
            (generate_password_hash("Faculty@123"), fid, login_row["id"]))
    if demo.get("program_id") and demo.get("session_id"):
        courses = db.execute(
            "SELECT id FROM courses WHERE program_id=? AND semester_no=? "
            "ORDER BY code LIMIT 2",
            (demo["program_id"], demo.get("current_semester") or 3)).fetchall()
        for c in courses:
            db.insert(
                """INSERT INTO course_assignments (faculty_id,course_id,session_id,
                   created_at) VALUES (?,?,?,?)""",
                (fid, c["id"], demo["session_id"], _now()))


# ------------------------------------------------------- v0.9 clearance seed
DEFAULT_CLEARANCE_UNITS = [
    ("Accounts / Fees", 1), ("Library", 0), ("Hostel", 0),
    ("Examinations (COE)", 0), ("Department", 0), ("Sports", 0),
    ("Transport", 0),
]


def backfill_v09(db):
    """Idempotent v0.9 migration: seed the clearance units (in order,
    'Accounts / Fees' first and flagged is_accounts=1 so the apply flow
    can auto-evaluate it) ONLY while the units table is empty. A strict
    no-op afterwards, so admin renames/deactivations are never undone."""
    if db.execute("SELECT COUNT(*) c FROM clearance_units").fetchone()["c"]:
        return
    for i, (name, is_accounts) in enumerate(DEFAULT_CLEARANCE_UNITS, start=1):
        db.insert(
            "INSERT INTO clearance_units (name,sort_order,is_active,is_accounts) "
            "VALUES (?,?,1,?)", (name, i, is_accounts))


# ------------------------------------------------------- v0.10 scholarships seed
DEFAULT_SCHOLARSHIP_SCHEMES = [
    ("Need-Based Scholarship", "University / HEC",
     "Financial assistance for enrolled students who need support to "
     "continue their studies.",
     "For enrolled students whose family income is low; requires a "
     "complete socio-economic profile."),
    ("Merit Scholarship", "University",
     "Recognition and support for enrolled students with outstanding "
     "academic performance.",
     "For enrolled students with strong academic standing (CGPA)."),
]


def backfill_v10(db):
    """Idempotent v0.10 migration: seed the two generic scholarship
    schemes ONLY while the schemes table is empty. A strict no-op
    afterwards, so admin edits/closures are never undone."""
    if db.execute("SELECT COUNT(*) c FROM scholarship_schemes").fetchone()["c"]:
        return
    for name, provider, description, eligibility in DEFAULT_SCHOLARSHIP_SCHEMES:
        db.insert(
            """INSERT INTO scholarship_schemes (name,provider,description,
               eligibility,is_open,deadline,created_at)
               VALUES (?,?,?,?,1,NULL,?)""",
            (name, provider, description, eligibility, _now()))


# ------------------------------------------------- v0.11 app settings + seed
def get_setting(db, key, default=None):
    row = db.execute("SELECT value FROM app_settings WHERE key=?",
                     (key,)).fetchone()
    return row["value"] if row else default


def set_setting(db, key, value):
    if db.execute("SELECT key FROM app_settings WHERE key=?",
                  (key,)).fetchone():
        db.execute("UPDATE app_settings SET value=? WHERE key=?",
                   (value, key))
    else:
        db.execute("INSERT INTO app_settings (key,value) VALUES (?,?)",
                   (key, value))


def repeat_fee_per_ch(db):
    """Admin-set repeat fee per credit hour (Rs). Falls back to the
    seeded default when the stored value is somehow unusable."""
    try:
        return max(0, int(get_setting(db, "repeat_fee_per_ch", "2000")))
    except (TypeError, ValueError):
        return 2000


def backfill_v11(db):
    """Idempotent v0.11 seed: the default repeat fee per credit hour.
    Only written while the key is absent, so an admin-changed rate is
    never overwritten by a reboot."""
    if get_setting(db, "repeat_fee_per_ch") is None:
        db.execute(
            "INSERT INTO app_settings (key,value) VALUES (?,?)",
            ("repeat_fee_per_ch", "2000"))


# ------------------------------------------------------- v0.12 transport seed
DEMO_TRANSPORT_ROUTES = [
    ("Route 1", "Route 1 — City Side",
     "Demo route — morning pickups on the city side. (Demo data, "
     "editable by the admin.)",
     [("Satellite Town", "07:10"), ("Model Town", "07:25"),
      ("Cantt", "07:40"), ("Main Gate", "07:55"),
      ("CUVAS Campus", "08:10")]),
    ("Route 2", "Route 2 — Hasilpur Road Side",
     "Demo route — morning pickups along Hasilpur Road. (Demo data, "
     "editable by the admin.)",
     [("Hasilpur Road Chowk", "07:15"), ("University Chowk", "07:35"),
      ("Main Gate", "07:55"), ("CUVAS Campus", "08:10")]),
]


def backfill_v12(db):
    """Idempotent v0.12 seed: two clearly-labelled demo transport
    routes with their stops, ONLY while the routes table is empty.
    A strict no-op afterwards, so admin edits/deletions are never
    undone. (No timetable seed: the demo data has no canonical class
    timings to invent — the admin builds the timetable.)"""
    if db.execute("SELECT COUNT(*) c FROM transport_routes").fetchone()["c"]:
        return
    for name, title, description, stops in DEMO_TRANSPORT_ROUTES:
        rid = db.insert(
            """INSERT INTO transport_routes (name,title,description,
               is_active,created_at) VALUES (?,?,?,?,?)""",
            (name, title, description, 1, _now()))
        for i, (stop_name, pickup_time) in enumerate(stops, start=1):
            db.insert(
                """INSERT INTO transport_stops (route_id,stop_name,
                   pickup_time,sort_order) VALUES (?,?,?,?)""",
                (rid, stop_name, pickup_time, i))


# ------------------------------------------------- v0.13 campus life seed
CAMPUS_SETTING_KEYS = ("lms_url", "library_url", "library_info",
                       "email_url", "email_info")

DEMO_SOCIETIES = [
    ("Literary Society",
     "Poetry, debates, creative writing and the annual literary "
     "festival. (Demo data, editable by the admin.)", None),
    ("Sports Society",
     "Cricket, football and athletics — inter-department tournaments "
     "and the annual sports gala. (Demo data, editable by the admin.)",
     None),
    ("IT & Robotics Society",
     "Programming contests, robotics projects and tech talks. "
     "(Demo data, editable by the admin.)", "demo"),
]


def backfill_v13(db):
    """Idempotent v0.13 seed: make sure the five Campus Life settings
    keys exist (as empty strings — an admin fills them in; existing
    values are NEVER overwritten) and seed the three demo societies
    ONLY while the societies table is empty, so admin edits and
    deletions are never undone."""
    for key in CAMPUS_SETTING_KEYS:
        if get_setting(db, key) is None:
            db.execute("INSERT INTO app_settings (key,value) VALUES (?,?)",
                       (key, ""))
    if db.execute("SELECT COUNT(*) c FROM societies").fetchone()["c"]:
        return
    demo_faculty = db.execute(
        "SELECT id FROM faculty WHERE email=?",
        ("demo.teacher@cuvas.edu.pk",)).fetchone()
    demo_faculty_id = demo_faculty["id"] if demo_faculty else None
    for name, description, advisor in DEMO_SOCIETIES:
        db.insert(
            """INSERT INTO societies (name,description,advisor_faculty_id,
               is_active,created_at) VALUES (?,?,?,?,?)""",
            (name, description,
             demo_faculty_id if advisor == "demo" else None, 1, _now()))


# ------------------------------------------------- v0.15 staff roles migration
def migrate_v15_roles(db):
    """v0.15 widening of users.role for the 'accounts' / 'coe' staff
    roles. Fresh databases are unaffected (the DDL never constrained
    role), but very old databases can carry a restrictive CHECK:
      * SQLite: a legacy table may have CHECK(role IN ('admin','student'))
        baked into its CREATE TABLE — SQLite cannot drop a constraint,
        so the table is rebuilt without it (every column and row is
        preserved via an explicit column list).
      * PostgreSQL: any CHECK constraint on users whose definition
        mentions role but not the new roles is dropped by name.
    Runs BEFORE seed/backfills so their inserts of newer roles (the
    v0.7 faculty login, the v0.15 staff logins) can never trip a
    legacy constraint. A strict no-op when no restrictive CHECK is
    found, and on any unexpected shape the table is left untouched."""
    if PG:
        rows = db.execute(
            """SELECT con.conname name, pg_get_constraintdef(con.oid) def
               FROM pg_constraint con
               JOIN pg_class rel ON rel.oid = con.conrelid
               WHERE rel.relname='users' AND con.contype='c'""").fetchall()
        for r in rows:
            if "role" in r["def"] and "accounts" not in r["def"]:
                db.execute(
                    f'ALTER TABLE users DROP CONSTRAINT "{r["name"]}"')
        return
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone()
    sql = (row["sql"] if row else "") or ""
    if "CHECK" not in sql.upper() or "accounts" in sql:
        return
    new_sql = re.sub(r",?\s*CHECK\s*\(\s*role\s+IN\s*\([^)]*\)\s*\)",
                     "", sql, flags=re.I)
    if new_sql == sql or "CHECK" in new_sql.upper() and "role" in new_sql:
        return  # unknown CHECK shape — leave the table exactly as it is
    new_sql = new_sql.replace("CREATE TABLE users",
                              "CREATE TABLE users_v15_new", 1)
    if "users_v15_new" not in new_sql:
        return  # unexpected CREATE TABLE shape — leave things untouched
    new_sql = new_sql.replace(", )", ")").replace("( ,", "(")
    cols = [r["name"] for r in
            db.execute("PRAGMA table_info(users)").fetchall()]
    collist = ", ".join(cols)
    db.execute("ALTER TABLE users RENAME TO users_v15_old")
    db.execute(new_sql)
    db.execute(f"INSERT INTO users_v15_new ({collist}) "
               f"SELECT {collist} FROM users_v15_old")
    db.execute("DROP TABLE users_v15_old")
    db.execute("ALTER TABLE users_v15_new RENAME TO users")


# ------------------------------------------------------- v0.15 staff seed
DEMO_STAFF = [
    ("accounts", "Accounts@123", "accounts", "Demo Accounts Officer"),
    ("coe", "Coe@123", "coe", "Demo Controller of Examinations"),
]


def backfill_v15(db):
    """Idempotent v0.15 seed: the two demo staff logins, created ONLY
    while each username is absent — a renamed / re-passworded /
    deactivated staff account is never resurrected or overwritten —
    and the go-live homepage setting show_demo_accounts='1', written
    ONLY while the key is absent so an admin's toggle survives
    reboots."""
    for username, pw, role, name in DEMO_STAFF:
        if not db.execute("SELECT id FROM users WHERE username=?",
                          (username,)).fetchone():
            db.insert(
                """INSERT INTO users (username,password_hash,role,
                   display_name) VALUES (?,?,?,?)""",
                (username, generate_password_hash(pw), role, name))
    if get_setting(db, "show_demo_accounts") is None:
        db.execute("INSERT INTO app_settings (key,value) VALUES (?,?)",
                   ("show_demo_accounts", "1"))


def _today():
    return datetime.date.today().isoformat()


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# -------------------------------------------------------------------- seed
def seed(db):
    if db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]:
        return
    db.insert(
        "INSERT INTO users (username,password_hash,role,display_name) VALUES (?,?,?,?)",
        ("admin", generate_password_hash("Admin@123"), "admin", "Demo Admin"))
    # --- academic sessions (fictional demo entries) ---
    sess_ids = {}
    for name, starts, ends, is_open in [
            ("Fall 2024 (Demo)", "2024-09-01", "2025-01-31", 0),
            ("Fall 2025 (Demo)", "2025-09-01", "2026-01-31", 0),
            ("Fall 2026 (Demo)", "2026-09-01", "2027-01-31", 1)]:
        sess_ids[name] = db.insert(
            "INSERT INTO academic_sessions (name,starts_on,ends_on,is_open) VALUES (?,?,?,?)",
            (name, starts, ends, is_open))
    # --- departments (fictional demo entries) ---
    depts = [
        ("Department of Computer Science (Demo)", "CS-DEMO", "Faculty of Computing (Demo)"),
        ("Department of Veterinary Medicine (Demo)", "DVM-DEMO", "Faculty of Veterinary Sciences (Demo)"),
        ("Department of Animal Sciences (Demo)", "ANS-DEMO", "Faculty of Animal Sciences (Demo)"),
        ("Department of Food Science (Demo)", "FS-DEMO", "Faculty of Food Sciences (Demo)"),
    ]
    dept_ids = {}
    for name, code, fac in depts:
        dept_ids[code] = db.insert(
            "INSERT INTO departments (name,code,faculty_name) VALUES (?,?,?)", (name, code, fac))
    # --- programs ---
    progs = [
        (dept_ids["CS-DEMO"], "BS Computer Science (Demo)", "BS", 8),
        (dept_ids["DVM-DEMO"], "Doctor of Veterinary Medicine (Demo)", "DVM", 10),
        (dept_ids["ANS-DEMO"], "BS Animal Sciences (Demo)", "BS", 8),
        (dept_ids["ANS-DEMO"], "MPhil Animal Nutrition (Demo)", "MPhil", 4),
        (dept_ids["FS-DEMO"], "BS Food Science & Technology (Demo)", "BS", 8),
    ]
    prog_ids = []
    for d, n, lvl, dur in progs:
        prog_ids.append(db.insert(
            "INSERT INTO programs (department_id,name,degree_level,duration_semesters) VALUES (?,?,?,?)",
            (d, n, lvl, dur)))
    bs_cs = prog_ids[0]
    # --- students (all fictional) ---
    students = [
        ("CUVAS-DEMO-2026-001", "35202-0000001-1", "Demo Student", "Demo Father", "Male", "2004-01-15",
         "Demo Domicile", "B+", "0300-0000001", "demo.student@example.com",
         "Demo Address, Demo City", "Demo Permanent Address", "Main Campus (Demo)", "Active",
         dept_ids["CS-DEMO"], bs_cs, sess_ids["Fall 2024 (Demo)"], "Fall 2024 (Demo)", 3),
        ("CUVAS-DEMO-2026-002", "35202-0000002-2", "Demo Student Two", "Demo Father Two", "Female", "2004-05-20",
         "Demo Domicile", "A+", "0300-0000002", "demo.two@example.com",
         "Demo Address 2", "Demo Permanent Address 2", "Main Campus (Demo)", "Active",
         dept_ids["CS-DEMO"], bs_cs, sess_ids["Fall 2024 (Demo)"], "Fall 2024 (Demo)", 3),
        ("CUVAS-DEMO-2026-003", "35202-0000003-3", "Demo Student Three", "Demo Father Three", "Male", "2003-11-02",
         "Demo Domicile", "O+", "0300-0000003", "demo.three@example.com",
         "Demo Address 3", "Demo Permanent Address 3", "Main Campus (Demo)", "Active",
         dept_ids["DVM-DEMO"], prog_ids[1], sess_ids["Fall 2024 (Demo)"], "Fall 2024 (Demo)", 3),
        ("CUVAS-DEMO-2026-004", "35202-0000004-4", "Demo Student Four", "Demo Father Four", "Female", "2004-03-18",
         "Demo Domicile", "AB+", "0300-0000004", "demo.four@example.com",
         "Demo Address 4", "Demo Permanent Address 4", "Main Campus (Demo)", "Active",
         dept_ids["ANS-DEMO"], prog_ids[2], sess_ids["Fall 2025 (Demo)"], "Fall 2025 (Demo)", 1),
        ("CUVAS-DEMO-2026-005", "35202-0000005-5", "Demo Student Five", "Demo Father Five", "Male", "2002-08-25",
         "Demo Domicile", "B-", "0300-0000005", "demo.five@example.com",
         "Demo Address 5", "Demo Permanent Address 5", "Main Campus (Demo)", "Active",
         dept_ids["ANS-DEMO"], prog_ids[3], sess_ids["Fall 2025 (Demo)"], "Fall 2025 (Demo)", 1),
        ("CUVAS-DEMO-2026-006", "35202-0000006-6", "Demo Student Six", "Demo Father Six", "Female", "2004-07-09",
         "Demo Domicile", "O-", "0300-0000006", "demo.six@example.com",
         "Demo Address 6", "Demo Permanent Address 6", "Main Campus (Demo)", "Active",
         dept_ids["FS-DEMO"], prog_ids[4], sess_ids["Fall 2025 (Demo)"], "Fall 2025 (Demo)", 1),
    ]
    student_ids = []
    for s in students:
        student_ids.append(db.insert(
            """INSERT INTO students (registration_no,cnic,name,father_name,gender,dob,domicile,
               blood_group,phone,email,address_present,address_permanent,address,campus,status,
               department_id,program_id,session_id,session_name,current_semester)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7], s[8], s[9], s[10], s[11],
             s[10], s[12], s[13], s[14], s[15], s[16], s[17], s[18])))
    demo_student = student_ids[0]
    db.insert(
        "INSERT INTO users (username,password_hash,role,display_name,student_id) VALUES (?,?,?,?,?)",
        ("student", generate_password_hash("Student@123"), "student", "Demo Student", demo_student))
    # --- certificates for demo student ---
    db.executemany(
        "INSERT INTO certificates (student_id,title,board,passing_year,total_marks,obtained_marks) VALUES (?,?,?,?,?,?)",
        [(demo_student, "Matriculation (Demo)", "Demo Board", "2020", 1100, 920),
         (demo_student, "Intermediate (Demo)", "Demo Board", "2022", 1100, 880)])
    # --- courses for BS CS (Demo): semesters 1-4 (plan of study) ---
    course_rows = [
        (1, "CS-101", "Introduction to Computing (Demo)", 3, 0, "Dr Demo Faculty A"),
        (1, "MTH-101", "Calculus & Analytical Geometry (Demo)", 3, 0, "Dr Demo Faculty B"),
        (1, "ENG-101", "English Comprehension (Demo)", 2, 0, "Ms Demo Faculty C"),
        (1, "PHY-101", "Applied Physics (Demo)", 2, 1, "Dr Demo Faculty D"),
        (1, "ISL-101", "Islamic Studies (Demo)", 2, 0, "Mr Demo Faculty E"),
        (2, "CS-102", "Programming Fundamentals (Demo)", 3, 1, "Dr Demo Faculty A"),
        (2, "MTH-102", "Discrete Structures (Demo)", 3, 0, "Dr Demo Faculty B"),
        (2, "ENG-102", "Communication Skills (Demo)", 2, 0, "Ms Demo Faculty C"),
        (2, "STA-102", "Statistics & Probability (Demo)", 2, 1, "Dr Demo Faculty F"),
        (2, "PAK-102", "Pakistan Studies (Demo)", 2, 0, "Mr Demo Faculty E"),
        (3, "CS-201", "Object Oriented Programming (Demo)", 3, 1, "Dr Demo Faculty A"),
        (3, "CS-202", "Data Structures (Demo)", 3, 1, "Dr Demo Faculty G"),
        (3, "MTH-201", "Linear Algebra (Demo)", 3, 0, "Dr Demo Faculty B"),
        (3, "CS-203", "Digital Logic Design (Demo)", 2, 1, "Dr Demo Faculty D"),
        (3, "MGT-201", "Principles of Management (Demo)", 2, 0, "Ms Demo Faculty H"),
        (4, "CS-204", "Database Systems (Demo)", 3, 1, "Dr Demo Faculty G"),
        (4, "CS-205", "Operating Systems (Demo)", 3, 1, "Dr Demo Faculty A"),
        (4, "MTH-202", "Numerical Methods (Demo)", 3, 0, "Dr Demo Faculty B"),
    ]
    course_ids = {}
    for sem, code, title, th, lab, fac in course_rows:
        course_ids[(sem, code)] = db.insert(
            "INSERT INTO courses (program_id,semester_no,code,title,credit_theory,credit_lab,faculty_name) VALUES (?,?,?,?,?,?,?)",
            (bs_cs, sem, code, title, th, lab, fac))
    for (sem, code), cid in course_ids.items():
        if sem == 3:
            db.execute(
                "INSERT INTO enrollments (student_id,course_id,session_name,semester_no) VALUES (?,?,?,?)",
                (demo_student, cid, "Fall 2026 (Demo)", 3))
    sem1_grades = {"CS-101": ("A", 4.0), "MTH-101": ("B+", 3.5), "ENG-101": ("A", 4.0),
                   "PHY-101": ("B", 3.0), "ISL-101": ("A-", 3.7)}
    sem2_grades = {"CS-102": ("A", 4.0), "MTH-102": ("A-", 3.7), "ENG-102": ("B+", 3.5),
                   "STA-102": ("B", 3.0), "PAK-102": ("A", 4.0)}
    for sem, grades in ((1, sem1_grades), (2, sem2_grades)):
        for code, (grade, gp) in grades.items():
            db.execute(
                "INSERT INTO results (student_id,course_id,semester_no,grade,grade_point,remarks) VALUES (?,?,?,?,?,?)",
                (demo_student, course_ids[(sem, code)], sem, grade, gp, "Pass"))
    db.executemany(
        "INSERT INTO vouchers (student_id,challan_no,title,amount,due_date,status,remarks) VALUES (?,?,?,?,?,?,?)",
        [(demo_student, "DEMO-CH-1000", "Admission Fee (Demo)", 15000, "2024-09-01", "Paid", "Paid via Demo Bank"),
         (demo_student, "DEMO-CH-1001", "Semester 2 Fee (Demo)", 45000, "2025-02-15", "Paid", "Paid via Demo Bank"),
         (demo_student, "DEMO-CH-1002", "Semester 3 Fee (Demo)", 47500, "2026-11-15", "Pending", "Payable at any Demo Bank branch")])
    db.executemany(
        "INSERT INTO fee_plan_lines (head,amount) VALUES (?,?)",
        [("Tuition Fee (Demo)", 30000), ("University / Institute Charges (Demo)", 8000),
         ("Transport Charges (Demo)", 5000), ("Library Charges (Demo)", 1500),
         ("Examination Charges (Demo)", 3000)])
    db.executemany(
        "INSERT INTO ledger_entries (student_id,voucher_title,challan_no,entry_date,description,debit,credit) VALUES (?,?,?,?,?,?,?)",
        [(demo_student, "Admission Fee (Demo)", "DEMO-CH-1000", "2024-09-01", "Admission fee charged (Demo)", 15000, 0),
         (demo_student, "Admission Fee (Demo)", "DEMO-CH-1000", "2024-09-03", "Payment received — Demo Bank", 0, 15000),
         (demo_student, "Semester 2 Fee (Demo)", "DEMO-CH-1001", "2025-02-01", "Semester 2 fee charged (Demo)", 45000, 0),
         (demo_student, "Semester 2 Fee (Demo)", "DEMO-CH-1001", "2025-02-10", "Payment received — Demo Bank", 0, 45000),
         (demo_student, "Semester 3 Fee (Demo)", "DEMO-CH-1002", "2026-10-01", "Semester 3 fee charged (Demo)", 47500, 0)])
    db.executemany(
        "INSERT INTO notifications (title,body,published_at) VALUES (?,?,?)",
        [("Welcome to MY CUVAS (Demo)", "This is a demonstration build with fictional data only.", "2026-10-20"),
         ("Semester 3 Fee Deadline (Demo)", "Demo notice: the Semester 3 fee voucher is due by 15 Nov 2026.", "2026-10-21"),
         ("Demo LMS Coming Soon", "Course material and LMS features are planned for a later phase.", "2026-10-22")])
    db.commit()


init_db()


# ---------------------------------------------------------------- auth guards
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    """Gate a view to one or more roles. v0.15 generalised this from a
    single role to a set, so office roles can share the admin route
    tree per the Step 20 permission map; every pre-v0.15 call site
    passes exactly one role and behaves exactly as before. Denial is
    the house style: a flash + a redirect to the user's own home."""
    def deco(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login", next=request.path))
            if session.get("role") not in roles:
                flash("You do not have access to that area.", "error")
                return redirect(url_for(home_for_role()))
            return view(*args, **kwargs)
        return wrapped
    return deco


def home_for_role():
    return {"admin": "admin_dashboard",
            "accounts": "accounts_dashboard",
            "coe": "coe_dashboard",
            "faculty": "faculty_dashboard"}.get(session.get("role"),
                                                "student_dashboard")


# ------------------------------------------------------------- audit log (v0.14)
def log_audit(action, details="", username=None, role=None, user_id=None):
    """Append ONE row to the audit log for the current actor.

    Actor identity defaults to the signed-in session user (the username
    / role are looked up from the users row, so the snapshot is the
    login identity at action time); callers recording a sign-in pass
    the identity explicitly. A failed sign-in passes the ATTEMPTED
    username. This helper NEVER raises and never rolls back the
    caller's work: it is called only after the action it records has
    succeeded, and any logging failure is swallowed so the action
    itself can never be broken by the audit trail."""
    try:
        db = get_db()
        if user_id is None:
            user_id = session.get("user_id")
        if user_id and (username is None or role is None):
            u = db.execute("SELECT username, role FROM users WHERE id=?",
                           (user_id,)).fetchone()
            if u:
                if username is None:
                    username = u["username"]
                if role is None:
                    role = u["role"]
        if username is None:
            username = ""
        if role is None:
            role = session.get("role") or ""
        db.execute(
            """INSERT INTO audit_log (user_id,username,role,action,details,
               created_at) VALUES (?,?,?,?,?,?)""",
            (user_id, username, role, action, details or "", _now()))
        db.commit()
    except Exception:
        try:
            get_db().rollback()
        except Exception:
            pass


# ---------------------------------------------------------------- routes: public / auth
# ------------------------------------------------- sign-in lockout (v0.15)
LOGIN_MAX_FAILURES = 5        # consecutive failures that trigger a lock
LOGIN_LOCKOUT_MINUTES = 15    # window those failures must fall within


def _record_login_attempt(db, username, success):
    """One login_attempts row per sign-in attempt. House-safe like
    log_audit: it never raises into the sign-in flow."""
    try:
        db.execute(
            "INSERT INTO login_attempts (username,success,attempted_at) "
            "VALUES (?,?,?)", (username, 1 if success else 0, _now()))
        db.commit()
    except Exception:
        db.rollback()


def _login_failure_streak(db, username):
    """Consecutive failed attempts for username inside the lockout
    window, counting back from the newest attempt and stopping at the
    most recent success (so a successful sign-in clears the streak)."""
    cutoff = (datetime.datetime.now()
              - datetime.timedelta(
                  minutes=LOGIN_LOCKOUT_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
    rows = db.execute(
        """SELECT success FROM login_attempts
           WHERE username=? AND attempted_at>=? ORDER BY id DESC""",
        (username, cutoff)).fetchall()
    streak = 0
    for r in rows:
        if r["success"]:
            break
        streak += 1
    return streak


def _login_locked(db, username):
    return _login_failure_streak(db, username) >= LOGIN_MAX_FAILURES


@app.route("/")
def landing():
    db = get_db()
    news = db.execute(
        """SELECT * FROM notifications
           WHERE COALESCE(is_published,1)=1 AND COALESCE(audience,'All') IN ('All','Students')
           ORDER BY published_at DESC, id DESC LIMIT 3""").fetchall()
    # v0.15 go-live: the demo-accounts box on the public homepage is
    # shown only while the admin leaves show_demo_accounts on.
    show_demo = get_setting(db, "show_demo_accounts", "1") == "1"
    return render_template("landing.html", news=news, show_demo=show_demo)


def _sign_in(db, username, password):
    """Shared credential check (factored out of the /login view
    WITHOUT any behaviour change): lockout refusal, the password check
    (including the faculty-deactivation rule), and the attempt + audit
    recording for the locked / failed outcomes all happen here, exactly
    as the /login view has always done them. Returns (user, state)
    with state 'ok', 'failed' or 'locked'; on 'ok' the caller starts
    the session via _start_session."""
    user = db.execute("SELECT * FROM users WHERE username=?",
                      (username,)).fetchone()
    if _login_locked(db, username):
        # locked: refuse WITHOUT checking the password, so even
        # the correct password is turned away until the window
        # of consecutive failures ages out.
        log_audit("login_locked",
                  f"Sign-in refused for '{username}': temporarily "
                  f"locked after {LOGIN_MAX_FAILURES} failed attempts",
                  username=username,
                  role=(user["role"] if user else ""),
                  user_id=(user["id"] if user else None))
        return user, "locked"
    ok = bool(user and user.get("is_active", 1)
              and check_password_hash(user["password_hash"], password))
    if ok and user["role"] == "faculty":
        # a deactivated faculty record blocks login even if the users
        # row's own flag ever drifts out of sync
        fac = db.execute("SELECT is_active FROM faculty WHERE id=?",
                         (user.get("faculty_id"),)).fetchone()
        ok = bool(fac and fac.get("is_active", 1))
    if ok:
        _record_login_attempt(db, username, True)
        return user, "ok"
    _record_login_attempt(db, username, False)
    log_audit("login_failed", "Failed sign-in attempt",
              username=username,
              role=(user["role"] if user else ""),
              user_id=(user["id"] if user else None))
    return user, "failed"


def _start_session(user):
    """Populate the session for a freshly authenticated user and write
    the login_success audit row — identical to what /login has always
    done inline."""
    session.clear()
    session.update(user_id=user["id"], role=user["role"],
                   display_name=user["display_name"],
                   student_id=user["student_id"],
                   faculty_id=user.get("faculty_id"))
    log_audit("login_success", f"Signed in as {user['role']}",
              username=user["username"], role=user["role"],
              user_id=user["id"])


def _locked_flash(username):
    flash(f"Too many failed sign-in attempts for '{username}'. "
          f"This account is locked — please try again in "
          f"{LOGIN_LOCKOUT_MINUTES} minutes.", "error")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user, state = _sign_in(db, username, password)
        if state == "locked":
            _locked_flash(username)
            return render_template("login.html")
        if state == "ok":
            _start_session(user)
            return redirect(url_for(home_for_role()))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    log_audit("logout")
    session.clear()
    return redirect(url_for("landing"))


# ---------------------------------------------------------------- routes: admin dashboard
@app.route("/admin")
@role_required("admin")
def admin_dashboard():
    db = get_db()
    kpis = {
        "students": db.execute("SELECT COUNT(*) c FROM students").fetchone()["c"],
        "departments": db.execute("SELECT COUNT(*) c FROM departments").fetchone()["c"],
        "programs": db.execute("SELECT COUNT(*) c FROM programs").fetchone()["c"],
        "pending_vouchers": db.execute("SELECT COUNT(*) c FROM vouchers WHERE status IN ('Pending','Proof Submitted')").fetchone()["c"],
    }
    recent_students = db.execute(
        """SELECT s.*, d.name dept, p.name prog FROM students s
           LEFT JOIN departments d ON d.id=s.department_id
           LEFT JOIN programs p ON p.id=s.program_id ORDER BY s.id DESC LIMIT 6""").fetchall()
    pending = db.execute(
        "SELECT v.*, s.name student_name FROM vouchers v JOIN students s ON s.id=v.student_id WHERE v.status IN ('Pending','Proof Submitted') ORDER BY v.id DESC").fetchall()
    return render_template("admin_dashboard.html", kpis=kpis,
                           recent_students=recent_students, pending=pending)


# ------------------------------------------------- staff office landings (v0.15)
@app.route("/accounts")
@role_required("admin", "accounts")
def accounts_dashboard():
    """Accounts Office landing: fee KPIs for the current session from
    the SAME _fee_report computation as the Fee Collection report,
    plus the live proof queue size."""
    db = get_db()
    sess = current_session(db)
    rep = _fee_report(db, sess)
    pending_vouchers = db.execute(
        "SELECT COUNT(*) c FROM vouchers WHERE status='Pending'"
    ).fetchone()["c"]
    return render_template("accounts_dashboard.html", sess=sess, rep=rep,
                           pending_vouchers=pending_vouchers)


@app.route("/coe")
@role_required("admin", "coe")
def coe_dashboard():
    """Controller of Examinations landing: results KPIs — how many
    result rows exist, how many course result SETS are fully
    published (via the same _result_set_state the marks sheet uses),
    and the student count."""
    db = get_db()
    total_results = db.execute(
        "SELECT COUNT(*) c FROM results").fetchone()["c"]
    groups = db.execute(
        """SELECT DISTINCT course_id, semester_no, session_id
           FROM results""").fetchall()
    published_sets = 0
    for gr in groups:
        state, _pub, _tot = _result_set_state(
            db, gr["course_id"], gr["semester_no"], gr["session_id"])
        if state == "Published":
            published_sets += 1
    students = db.execute(
        "SELECT COUNT(*) c FROM students").fetchone()["c"]
    return render_template("coe_dashboard.html",
                           total_results=total_results,
                           total_sets=len(groups),
                           published_sets=published_sets,
                           students=students)


# ---------------------------------------------------------------- helpers: admin CRUD
def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def dept_options(db):
    return db.execute("SELECT id,name FROM departments ORDER BY name").fetchall()


def program_options(db):
    return db.execute("SELECT id,name FROM programs ORDER BY name").fetchall()


def session_options(db):
    return db.execute("SELECT id,name FROM academic_sessions ORDER BY name").fetchall()


# ---------------------------------------------------------------- departments CRUD
@app.route("/admin/departments")
@role_required("admin")
def admin_departments():
    rows = get_db().execute(
        """SELECT d.*, (SELECT COUNT(*) FROM programs p WHERE p.department_id=d.id) prog_count,
                  (SELECT COUNT(*) FROM students s WHERE s.department_id=d.id) stu_count
           FROM departments d ORDER BY d.name""").fetchall()
    return render_template("admin_departments.html", rows=rows)


@app.route("/admin/departments/new", methods=["GET", "POST"])
@role_required("admin")
def admin_department_new():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip()
        faculty = request.form.get("faculty_name", "").strip()
        if not name or not code:
            flash("Department name and code are required.", "error")
        elif db.execute("SELECT id FROM departments WHERE code=?", (code,)).fetchone():
            flash(f"A department with code '{code}' already exists.", "error")
        else:
            try:
                db.insert("INSERT INTO departments (name,code,faculty_name) VALUES (?,?,?)",
                          (name, code, faculty))
                db.commit()
                log_audit("department_created", f"Department '{name}' ({code})")
                flash(f"Department '{name}' added.", "ok")
                return redirect(url_for("admin_departments"))
            except Exception as e:
                db.rollback()
                flash("Could not add department: " + ("code already exists." if is_unique_error(e) else str(e)), "error")
    return render_template("department_form.html", dept=None)


@app.route("/admin/departments/<int:dept_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def admin_department_edit(dept_id):
    db = get_db()
    dept = db.execute("SELECT * FROM departments WHERE id=?", (dept_id,)).fetchone()
    if not dept:
        flash("Department not found.", "error")
        return redirect(url_for("admin_departments"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip()
        faculty = request.form.get("faculty_name", "").strip()
        clash = db.execute("SELECT id FROM departments WHERE code=? AND id<>?", (code, dept_id)).fetchone()
        if not name or not code:
            flash("Department name and code are required.", "error")
        elif clash:
            flash(f"A department with code '{code}' already exists.", "error")
        else:
            try:
                db.execute("UPDATE departments SET name=?,code=?,faculty_name=? WHERE id=?",
                           (name, code, faculty, dept_id))
                db.commit()
                log_audit("department_updated", f"Department '{name}' ({code})")
                flash(f"Department '{name}' updated.", "ok")
                return redirect(url_for("admin_departments"))
            except Exception as e:
                db.rollback()
                flash("Could not update department: " + ("code already exists." if is_unique_error(e) else str(e)), "error")
    return render_template("department_form.html", dept=dept)


@app.route("/admin/departments/<int:dept_id>/delete", methods=["POST"])
@role_required("admin")
def admin_department_delete(dept_id):
    db = get_db()
    dept = db.execute("SELECT * FROM departments WHERE id=?", (dept_id,)).fetchone()
    if not dept:
        flash("Department not found.", "error")
        return redirect(url_for("admin_departments"))
    progs = db.execute("SELECT COUNT(*) c FROM programs WHERE department_id=?", (dept_id,)).fetchone()["c"]
    studs = db.execute("SELECT COUNT(*) c FROM students WHERE department_id=?", (dept_id,)).fetchone()["c"]
    if progs or studs:
        flash(f"Cannot delete '{dept['name']}': it is still referenced by "
              f"{progs} program(s) and {studs} student(s). Reassign or remove those first.", "error")
        return redirect(url_for("admin_departments"))
    db.execute("DELETE FROM departments WHERE id=?", (dept_id,))
    db.commit()
    log_audit("department_deleted", f"Department '{dept['name']}'")
    flash(f"Department '{dept['name']}' deleted.", "ok")
    return redirect(url_for("admin_departments"))


# ---------------------------------------------------------------- programs CRUD
@app.route("/admin/programs")
@role_required("admin")
def admin_programs():
    rows = get_db().execute(
        """SELECT p.*, d.name dept, (SELECT COUNT(*) FROM students s WHERE s.program_id=p.id) stu_count,
                  (SELECT COUNT(*) FROM courses c WHERE c.program_id=p.id) course_count
           FROM programs p LEFT JOIN departments d ON d.id=p.department_id ORDER BY d.name, p.name""").fetchall()
    return render_template("admin_programs.html", rows=rows)


def _program_form_values(db):
    return {"departments": dept_options(db),
            "levels": ["BS", "MPhil", "PhD", "DVM", "MS", "BSc", "Other"]}


@app.route("/admin/programs/new", methods=["GET", "POST"])
@role_required("admin")
def admin_program_new():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        dept_id = _int_or_none(request.form.get("department_id"))
        level = request.form.get("degree_level", "").strip()
        duration = _int_or_none(request.form.get("duration_semesters"))
        if not name or not dept_id:
            flash("Program name and department are required.", "error")
        else:
            db.insert("INSERT INTO programs (department_id,name,degree_level,duration_semesters) VALUES (?,?,?,?)",
                      (dept_id, name, level, duration))
            db.commit()
            log_audit("program_created", f"Program '{name}'")
            flash(f"Program '{name}' added.", "ok")
            return redirect(url_for("admin_programs"))
    return render_template("program_form.html", prog=None, **_program_form_values(db))


@app.route("/admin/programs/<int:prog_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def admin_program_edit(prog_id):
    db = get_db()
    prog = db.execute("SELECT * FROM programs WHERE id=?", (prog_id,)).fetchone()
    if not prog:
        flash("Program not found.", "error")
        return redirect(url_for("admin_programs"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        dept_id = _int_or_none(request.form.get("department_id"))
        level = request.form.get("degree_level", "").strip()
        duration = _int_or_none(request.form.get("duration_semesters"))
        if not name or not dept_id:
            flash("Program name and department are required.", "error")
        else:
            db.execute("UPDATE programs SET department_id=?,name=?,degree_level=?,duration_semesters=? WHERE id=?",
                       (dept_id, name, level, duration, prog_id))
            db.commit()
            log_audit("program_updated", f"Program '{name}'")
            flash(f"Program '{name}' updated.", "ok")
            return redirect(url_for("admin_programs"))
    return render_template("program_form.html", prog=prog, **_program_form_values(db))


@app.route("/admin/programs/<int:prog_id>/delete", methods=["POST"])
@role_required("admin")
def admin_program_delete(prog_id):
    db = get_db()
    prog = db.execute("SELECT * FROM programs WHERE id=?", (prog_id,)).fetchone()
    if not prog:
        flash("Program not found.", "error")
        return redirect(url_for("admin_programs"))
    studs = db.execute("SELECT COUNT(*) c FROM students WHERE program_id=?", (prog_id,)).fetchone()["c"]
    courses = db.execute("SELECT COUNT(*) c FROM courses WHERE program_id=?", (prog_id,)).fetchone()["c"]
    if studs or courses:
        flash(f"Cannot delete '{prog['name']}': it is still referenced by "
              f"{studs} student(s) and {courses} course(s). Reassign or remove those first.", "error")
        return redirect(url_for("admin_programs"))
    db.execute("DELETE FROM programs WHERE id=?", (prog_id,))
    db.commit()
    log_audit("program_deleted", f"Program '{prog['name']}'")
    flash(f"Program '{prog['name']}' deleted.", "ok")
    return redirect(url_for("admin_programs"))


# ---------------------------------------------------------------- sessions CRUD
@app.route("/admin/sessions")
@role_required("admin")
def admin_sessions():
    rows = get_db().execute(
        """SELECT s.*, (SELECT COUNT(*) FROM students st WHERE st.session_id=s.id) stu_count
           FROM academic_sessions s ORDER BY s.name""").fetchall()
    return render_template("admin_sessions.html", rows=rows)


@app.route("/admin/sessions/new", methods=["GET", "POST"])
@role_required("admin")
def admin_session_new():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        starts = request.form.get("starts_on", "").strip()
        ends = request.form.get("ends_on", "").strip()
        is_open = 1 if request.form.get("is_open") else 0
        if not name:
            flash("Session name is required (e.g. Fall-2026).", "error")
        elif db.execute("SELECT id FROM academic_sessions WHERE name=?", (name,)).fetchone():
            flash(f"A session named '{name}' already exists.", "error")
        else:
            db.insert("INSERT INTO academic_sessions (name,starts_on,ends_on,is_open) VALUES (?,?,?,?)",
                      (name, starts, ends, is_open))
            db.commit()
            log_audit("session_created", f"Session '{name}'")
            flash(f"Session '{name}' added.", "ok")
            return redirect(url_for("admin_sessions"))
    return render_template("session_form.html", sess=None)


@app.route("/admin/sessions/<int:sess_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def admin_session_edit(sess_id):
    db = get_db()
    sess = db.execute("SELECT * FROM academic_sessions WHERE id=?", (sess_id,)).fetchone()
    if not sess:
        flash("Session not found.", "error")
        return redirect(url_for("admin_sessions"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        starts = request.form.get("starts_on", "").strip()
        ends = request.form.get("ends_on", "").strip()
        is_open = 1 if request.form.get("is_open") else 0
        clash = db.execute("SELECT id FROM academic_sessions WHERE name=? AND id<>?", (name, sess_id)).fetchone()
        if not name:
            flash("Session name is required.", "error")
        elif clash:
            flash(f"A session named '{name}' already exists.", "error")
        else:
            db.execute("UPDATE academic_sessions SET name=?,starts_on=?,ends_on=?,is_open=? WHERE id=?",
                       (name, starts, ends, is_open, sess_id))
            db.execute("UPDATE students SET session_name=? WHERE session_id=?", (name, sess_id))
            db.commit()
            log_audit("session_updated", f"Session '{name}'")
            flash(f"Session '{name}' updated.", "ok")
            return redirect(url_for("admin_sessions"))
    return render_template("session_form.html", sess=sess)


@app.route("/admin/sessions/<int:sess_id>/delete", methods=["POST"])
@role_required("admin")
def admin_session_delete(sess_id):
    db = get_db()
    sess = db.execute("SELECT * FROM academic_sessions WHERE id=?", (sess_id,)).fetchone()
    if not sess:
        flash("Session not found.", "error")
        return redirect(url_for("admin_sessions"))
    studs = db.execute("SELECT COUNT(*) c FROM students WHERE session_id=?", (sess_id,)).fetchone()["c"]
    if studs:
        flash(f"Cannot delete session '{sess['name']}': it is still referenced by {studs} student(s).", "error")
        return redirect(url_for("admin_sessions"))
    db.execute("DELETE FROM academic_sessions WHERE id=?", (sess_id,))
    db.commit()
    log_audit("session_deleted", f"Session '{sess['name']}'")
    flash(f"Session '{sess['name']}' deleted.", "ok")
    return redirect(url_for("admin_sessions"))


# ---------------------------------------------------------------- courses CRUD
@app.route("/admin/courses")
@role_required("admin")
def admin_courses():
    db = get_db()
    prog_filter = _int_or_none(request.args.get("program_id"))
    sql = """SELECT c.*, p.name prog FROM courses c
             LEFT JOIN programs p ON p.id=c.program_id"""
    params = []
    if prog_filter:
        sql += " WHERE c.program_id=?"
        params.append(prog_filter)
    sql += " ORDER BY p.name, c.semester_no, c.code"
    rows = db.execute(sql, params).fetchall()
    return render_template("admin_courses.html", rows=rows, programs=program_options(db),
                           program_filter=prog_filter)


def _course_form_values(db):
    return {"programs": program_options(db)}


@app.route("/admin/courses/new", methods=["GET", "POST"])
@role_required("admin")
def admin_course_new():
    db = get_db()
    if request.method == "POST":
        prog_id = _int_or_none(request.form.get("program_id"))
        sem = _int_or_none(request.form.get("semester_no"))
        code = request.form.get("code", "").strip()
        title = request.form.get("title", "").strip()
        th = _int_or_none(request.form.get("credit_theory")) or 0
        lab = _int_or_none(request.form.get("credit_lab")) or 0
        faculty = request.form.get("faculty_name", "").strip()
        if not prog_id or not code or not title or sem is None:
            flash("Program, semester, course code and title are required.", "error")
        else:
            db.insert(
                "INSERT INTO courses (program_id,semester_no,code,title,credit_theory,credit_lab,faculty_name) VALUES (?,?,?,?,?,?,?)",
                (prog_id, sem, code, title, th, lab, faculty))
            db.commit()
            log_audit("course_created", f"Course '{code} — {title}'")
            flash(f"Course '{code} — {title}' added.", "ok")
            return redirect(url_for("admin_courses"))
    return render_template("course_form.html", course=None, **_course_form_values(db))


@app.route("/admin/courses/<int:course_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def admin_course_edit(course_id):
    db = get_db()
    course = db.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
    if not course:
        flash("Course not found.", "error")
        return redirect(url_for("admin_courses"))
    if request.method == "POST":
        prog_id = _int_or_none(request.form.get("program_id"))
        sem = _int_or_none(request.form.get("semester_no"))
        code = request.form.get("code", "").strip()
        title = request.form.get("title", "").strip()
        th = _int_or_none(request.form.get("credit_theory")) or 0
        lab = _int_or_none(request.form.get("credit_lab")) or 0
        faculty = request.form.get("faculty_name", "").strip()
        if not prog_id or not code or not title or sem is None:
            flash("Program, semester, course code and title are required.", "error")
        else:
            db.execute(
                "UPDATE courses SET program_id=?,semester_no=?,code=?,title=?,credit_theory=?,credit_lab=?,faculty_name=? WHERE id=?",
                (prog_id, sem, code, title, th, lab, faculty, course_id))
            db.commit()
            log_audit("course_updated", f"Course '{code}'")
            flash(f"Course '{code}' updated.", "ok")
            return redirect(url_for("admin_courses"))
    return render_template("course_form.html", course=course, **_course_form_values(db))


@app.route("/admin/courses/<int:course_id>/delete", methods=["POST"])
@role_required("admin")
def admin_course_delete(course_id):
    db = get_db()
    course = db.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
    if not course:
        flash("Course not found.", "error")
        return redirect(url_for("admin_courses"))
    enr = db.execute("SELECT COUNT(*) c FROM enrollments WHERE course_id=?", (course_id,)).fetchone()["c"]
    res = db.execute("SELECT COUNT(*) c FROM results WHERE course_id=?", (course_id,)).fetchone()["c"]
    if enr or res:
        flash(f"Cannot delete course '{course['code']}': it is referenced by "
              f"{enr} enrollment(s) and {res} result(s).", "error")
        return redirect(url_for("admin_courses"))
    db.execute("DELETE FROM courses WHERE id=?", (course_id,))
    db.commit()
    log_audit("course_deleted", f"Course '{course['code']}'")
    flash(f"Course '{course['code']}' deleted.", "ok")
    return redirect(url_for("admin_courses"))


# ---------------------------------------------------------------- students management
STUDENT_STATUSES = ["Active", "Completed", "Left", "Freeze", "Cancelled"]
GENDERS = ["Male", "Female", "Other"]
BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

# Excel columns: (field key, template header). Headers are matched by NAME.
EXCEL_COLUMNS = [
    ("registration_no", "Registration No"),
    ("cnic", "CNIC"),
    ("name", "Name"),
    ("father_name", "Father Name"),
    ("gender", "Gender"),
    ("dob", "Date of Birth"),
    ("domicile", "Domicile"),
    ("blood_group", "Blood Group"),
    ("phone", "Phone"),
    ("email", "Email"),
    ("address_present", "Present Address"),
    ("address_permanent", "Permanent Address"),
    ("department", "Department"),
    ("program", "Program"),
    ("session", "Session"),
    ("campus", "Campus"),
    ("status", "Status"),
    ("current_semester", "Current Semester"),
]
_EXCEL_ALIASES = {
    "registration_no": ["registrationno", "regno", "registration", "rollno"],
    "cnic": ["cnic", "cnicno", "nic", "nationalid"],
    "name": ["name", "studentname", "fullname"],
    "father_name": ["fathername", "father"],
    "gender": ["gender", "sex"],
    "dob": ["dateofbirth", "dob", "birthdate"],
    "domicile": ["domicile"],
    "blood_group": ["bloodgroup", "blood"],
    "phone": ["phone", "phoneno", "mobile", "contact"],
    "email": ["email", "emailaddress"],
    "address_present": ["presentaddress", "address", "currentaddress"],
    "address_permanent": ["permanentaddress"],
    "department": ["department", "dept"],
    "program": ["program", "programme", "degree"],
    "session": ["session", "batch"],
    "campus": ["campus"],
    "status": ["status"],
    "current_semester": ["currentsemester", "semester"],
}


def _norm_header(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _header_map(header_row):
    """Map normalised header cell -> column index, then resolve to field keys."""
    norm_to_idx = {}
    for idx, cell in enumerate(header_row):
        n = _norm_header(cell)
        if n:
            norm_to_idx[n] = idx
    field_to_idx = {}
    for field, _label in EXCEL_COLUMNS:
        for alias in _EXCEL_ALIASES[field] + [_norm_header(field)]:
            if alias in norm_to_idx:
                field_to_idx[field] = norm_to_idx[alias]
                break
    return field_to_idx


def generate_password():
    """A system-generated initial password. Always satisfies the v0.15
    password policy (at least one letter and one digit), even though
    generated passwords are exempt from it — belt and braces."""
    letters = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"
    digits = "23456789"
    alphabet = letters + digits
    body = "".join(secrets.choice(alphabet) for _ in range(8))
    if not any(c.isdigit() for c in body):
        pos = secrets.randbelow(len(body))
        body = body[:pos] + secrets.choice(digits) + body[pos + 1:]
    if not any(c.isalpha() for c in body):
        pos = secrets.randbelow(len(body))
        body = body[:pos] + secrets.choice(letters) + body[pos + 1:]
    return "Cuvas-" + body


# ------------------------------------------------- password policy (v0.15)
PASSWORD_MIN_LENGTH = 8


def password_policy_error(pw):
    """None when pw satisfies the interactively-set password policy
    (minimum 8 characters, at least one letter and one digit), else a
    friendly reason. Applied ONLY where a human types a password into
    an admin form; system-generated / imported initial passwords are
    exempt (generate_password above is policy-compliant anyway)."""
    if not pw or len(pw) < PASSWORD_MIN_LENGTH:
        return (f"Password is too short — use at least "
                f"{PASSWORD_MIN_LENGTH} characters.")
    if not any(c.isalpha() for c in pw):
        return "Password must contain at least one letter."
    if not any(c.isdigit() for c in pw):
        return "Password must contain at least one digit."
    return None


def create_student(db, data, password=None):
    """Insert a student + their login (username = registration no).
    Returns (student_id, initial_password). Raises ValueError on duplicates.
    Does NOT commit — the caller commits (per student, so imports are row-safe)."""
    reg = (data.get("registration_no") or "").strip()
    name = (data.get("name") or "").strip()
    if not reg:
        raise ValueError("Registration No is missing")
    if not name:
        raise ValueError("Name is missing")
    cnic = (data.get("cnic") or "").strip() or None
    if db.execute("SELECT id FROM students WHERE registration_no=?", (reg,)).fetchone():
        raise ValueError(f"Registration No '{reg}' already exists")
    if cnic and db.execute("SELECT id FROM students WHERE cnic=?", (cnic,)).fetchone():
        raise ValueError(f"CNIC '{cnic}' is already registered to another student")
    if db.execute("SELECT id FROM users WHERE username=?", (reg,)).fetchone():
        raise ValueError(f"A login with username '{reg}' already exists")
    session_name = data.get("session_name") or ""
    if data.get("session_id"):
        row = db.execute("SELECT name FROM academic_sessions WHERE id=?",
                         (data["session_id"],)).fetchone()
        if row:
            session_name = row["name"]
    sid = db.insert(
        """INSERT INTO students (registration_no,cnic,name,father_name,gender,dob,domicile,
           blood_group,phone,email,address_present,address_permanent,address,campus,status,
           department_id,program_id,session_id,session_name,current_semester)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (reg, cnic, name, data.get("father_name") or None, data.get("gender") or None,
         data.get("dob") or None, data.get("domicile") or None, data.get("blood_group") or None,
         data.get("phone") or None, data.get("email") or None,
         data.get("address_present") or None, data.get("address_permanent") or None,
         data.get("address_present") or None, data.get("campus") or None,
         data.get("status") or "Active", data.get("department_id"), data.get("program_id"),
         data.get("session_id"), session_name, data.get("current_semester")))
    pw = password or generate_password()
    db.insert(
        "INSERT INTO users (username,password_hash,role,display_name,student_id) VALUES (?,?,?,?,?)",
        (reg, generate_password_hash(pw), "student", name, sid))
    return sid, pw


def _student_filter_sql(args):
    """Shared WHERE builder for the students list + export."""
    clauses, params = [], []
    q = (args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        clauses.append(f"(s.name {LIKE} ? OR s.registration_no {LIKE} ? OR s.cnic {LIKE} ?)")
        params += [like, like, like]
    for key, col in (("department_id", "s.department_id"), ("program_id", "s.program_id"),
                     ("session_id", "s.session_id")):
        val = _int_or_none(args.get(key))
        if val:
            clauses.append(f"{col}=?")
            params.append(val)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


@app.route("/admin/students")
@role_required("admin", "accounts", "coe")
def admin_students():
    db = get_db()
    where, params = _student_filter_sql(request.args)
    total = db.execute(f"SELECT COUNT(*) c FROM students s{where}", params).fetchone()["c"]
    per_page = 25
    pages = max(1, math.ceil(total / per_page))
    page = min(max(_int_or_none(request.args.get("page")) or 1, 1), pages)
    rows = db.execute(
        f"""SELECT s.*, d.name dept, p.name prog, ss.name sess FROM students s
            LEFT JOIN departments d ON d.id=s.department_id
            LEFT JOIN programs p ON p.id=s.program_id
            LEFT JOIN academic_sessions ss ON ss.id=s.session_id
            {where} ORDER BY s.id DESC LIMIT ? OFFSET ?""",
        params + [per_page, (page - 1) * per_page]).fetchall()
    return render_template(
        "admin_students.html", rows=rows, total=total, page=page, pages=pages,
        departments=dept_options(db), programs=program_options(db),
        sessions=session_options(db), args=request.args)


def _student_form_values(db, student=None):
    return {"departments": dept_options(db), "programs": program_options(db),
            "sessions": session_options(db), "statuses": STUDENT_STATUSES,
            "genders": GENDERS, "blood_groups": BLOOD_GROUPS, "student": student}


def _student_data_from_form(form):
    return {
        "registration_no": form.get("registration_no", "").strip(),
        "cnic": form.get("cnic", "").strip(),
        "name": form.get("name", "").strip(),
        "father_name": form.get("father_name", "").strip(),
        "gender": form.get("gender", "").strip(),
        "dob": form.get("dob", "").strip(),
        "domicile": form.get("domicile", "").strip(),
        "blood_group": form.get("blood_group", "").strip(),
        "phone": form.get("phone", "").strip(),
        "email": form.get("email", "").strip(),
        "address_present": form.get("address_present", "").strip(),
        "address_permanent": form.get("address_permanent", "").strip(),
        "department_id": _int_or_none(form.get("department_id")),
        "program_id": _int_or_none(form.get("program_id")),
        "session_id": _int_or_none(form.get("session_id")),
        "campus": form.get("campus", "").strip(),
        "status": form.get("status", "").strip() or "Active",
        "current_semester": _int_or_none(form.get("current_semester")),
    }


@app.route("/admin/students/new", methods=["GET", "POST"])
@role_required("admin")
def admin_student_new():
    db = get_db()
    if request.method == "POST":
        data = _student_data_from_form(request.form)
        chosen_pw = request.form.get("initial_password", "").strip() or None
        pw_err = password_policy_error(chosen_pw) if chosen_pw else None
        if pw_err:
            # v0.15 policy: a hand-typed initial password must comply;
            # leaving it blank auto-generates a compliant one instead.
            flash(f"Could not add student: {pw_err} Leave the initial "
                  f"password blank to auto-generate one.", "error")
            return render_template("student_form.html",
                                   **_student_form_values(db))
        try:
            sid, pw = create_student(db, data, password=chosen_pw)
            db.commit()
            log_audit("student_created",
                      f"Student '{data['name']}' ({data['registration_no']})")
            flash(f"Student '{data['name']}' added. Student login — username: "
                  f"{data['registration_no']} · initial password: {pw} — "
                  f"shown ONCE, note it now.", "ok")
            return redirect(url_for("admin_students"))
        except ValueError as e:
            db.rollback()
            flash(f"Could not add student: {e}", "error")
        except Exception as e:
            db.rollback()
            flash("Could not add student: " + ("duplicate registration/CNIC." if is_unique_error(e) else str(e)), "error")
    return render_template("student_form.html", **_student_form_values(db))


@app.route("/admin/students/<int:student_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def admin_student_edit(student_id):
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for("admin_students"))
    if request.method == "POST":
        data = _student_data_from_form(request.form)
        cnic = data["cnic"] or None
        clash = None
        if cnic:
            clash = db.execute("SELECT id FROM students WHERE cnic=? AND id<>?",
                               (cnic, student_id)).fetchone()
        if clash:
            flash(f"CNIC '{cnic}' is already registered to another student.", "error")
        else:
            session_name = student["session_name"]
            if data["session_id"]:
                row = db.execute("SELECT name FROM academic_sessions WHERE id=?",
                                 (data["session_id"],)).fetchone()
                if row:
                    session_name = row["name"]
            try:
                db.execute(
                    """UPDATE students SET cnic=?,name=?,father_name=?,gender=?,dob=?,domicile=?,
                       blood_group=?,phone=?,email=?,address_present=?,address_permanent=?,address=?,
                       campus=?,status=?,department_id=?,program_id=?,session_id=?,session_name=?,
                       current_semester=? WHERE id=?""",
                    (cnic, data["name"] or student["name"], data["father_name"] or None,
                     data["gender"] or None, data["dob"] or None, data["domicile"] or None,
                     data["blood_group"] or None, data["phone"] or None, data["email"] or None,
                     data["address_present"] or None, data["address_permanent"] or None,
                     data["address_present"] or None, data["campus"] or None, data["status"],
                     data["department_id"], data["program_id"], data["session_id"], session_name,
                     data["current_semester"], student_id))
                # keep the login's display name in sync; username/password untouched
                db.execute("UPDATE users SET display_name=? WHERE student_id=?",
                           (data["name"] or student["name"], student_id))
                db.commit()
                log_audit("student_updated",
                          f"Student '{data['name'] or student['name']}' ({student['registration_no']})")
                flash(f"Student '{data['name'] or student['name']}' updated.", "ok")
                return redirect(url_for("admin_students"))
            except Exception as e:
                db.rollback()
                flash("Could not update student: " + ("duplicate CNIC." if is_unique_error(e) else str(e)), "error")
    return render_template("student_form.html", **_student_form_values(db, student))


@app.route("/admin/students/<int:student_id>/delete", methods=["POST"])
@role_required("admin")
def admin_student_delete(student_id):
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for("admin_students"))
    for table in ("certificates", "enrollments", "results", "vouchers", "ledger_entries"):
        db.execute(f"DELETE FROM {table} WHERE student_id=?", (student_id,))
    db.execute("DELETE FROM users WHERE student_id=?", (student_id,))
    db.execute("DELETE FROM students WHERE id=?", (student_id,))
    db.commit()
    log_audit("student_deleted",
                f"Student '{student['name']}' ({student['registration_no']})")
    flash(f"Student '{student['name']}' ({student['registration_no']}) and their login deleted.", "ok")
    return redirect(url_for("admin_students"))


@app.route("/admin/students/<int:student_id>/reset-password", methods=["POST"])
@role_required("admin")
def admin_student_reset_password(student_id):
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for("admin_students"))
    chosen_pw = request.form.get("new_password", "").strip()
    if chosen_pw:
        pw_err = password_policy_error(chosen_pw)
        if pw_err:
            flash(f"Could not reset password: {pw_err}", "error")
            return redirect(url_for("admin_students"))
        pw = chosen_pw
    else:
        pw = generate_password()
    db.execute("UPDATE users SET password_hash=? WHERE student_id=?",
               (generate_password_hash(pw), student_id))
    db.commit()
    log_audit("student_password_reset",
                f"Password reset for {student['registration_no']} ({student['name']})")
    flash(f"Password reset for {student['registration_no']} ({student['name']}). "
          f"New password: {pw} — shown ONCE, note it now.", "ok")
    return redirect(url_for("admin_students"))


# ---------------------------------------------------------------- faculty management (v0.7)
FACULTY_DESIGNATIONS = ["Professor", "Associate Professor",
                        "Assistant Professor", "Lecturer"]


def create_faculty(db, data, password=None):
    """Insert a faculty record + their login (username = email).
    Returns (faculty_id, initial_password). Raises ValueError on duplicates.
    Does NOT commit — the caller commits."""
    name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip()
    if not name:
        raise ValueError("Full name is missing")
    if not email:
        raise ValueError("Email is missing")
    if "@" not in email:
        raise ValueError(f"Email '{email}' does not look valid")
    if db.execute("SELECT id FROM faculty WHERE email=?", (email,)).fetchone():
        raise ValueError(f"Email '{email}' is already registered to another faculty member")
    if db.execute("SELECT id FROM users WHERE username=?", (email,)).fetchone():
        raise ValueError(f"A login with username '{email}' already exists")
    fid = db.insert(
        """INSERT INTO faculty (full_name,email,phone,designation,department_id,
           is_active,created_at) VALUES (?,?,?,?,?,?,?)""",
        (name, email, data.get("phone") or None, data.get("designation") or None,
         data.get("department_id"), 1, _now()))
    pw = password or generate_password()
    db.insert(
        "INSERT INTO users (username,password_hash,role,display_name,faculty_id) VALUES (?,?,?,?,?)",
        (email, generate_password_hash(pw), "faculty", name, fid))
    return fid, pw


def _faculty_data_from_form(form):
    return {
        "full_name": form.get("full_name", "").strip(),
        "email": form.get("email", "").strip(),
        "phone": form.get("phone", "").strip(),
        "designation": form.get("designation", "").strip(),
        "department_id": _int_or_none(form.get("department_id")),
    }


def _faculty_assignments(db, faculty_id):
    return db.execute(
        """SELECT a.*, c.code course_code, c.title course_title,
                  c.semester_no, c.program_id, p.name prog_name, ss.name sess_name
           FROM course_assignments a
           JOIN courses c ON c.id=a.course_id
           LEFT JOIN programs p ON p.id=c.program_id
           LEFT JOIN academic_sessions ss ON ss.id=a.session_id
           WHERE a.faculty_id=? ORDER BY ss.name, c.code""",
        (faculty_id,)).fetchall()


def _faculty_form_values(db, faculty=None):
    courses = db.execute(
        """SELECT c.*, p.name prog_name FROM courses c
           LEFT JOIN programs p ON p.id=c.program_id
           ORDER BY p.name, c.semester_no, c.code""").fetchall()
    return {"departments": dept_options(db), "designations": FACULTY_DESIGNATIONS,
            "faculty": faculty, "courses": courses,
            "sessions": session_options(db),
            "assignments": _faculty_assignments(db, faculty["id"]) if faculty else []}


def _get_faculty_or_redirect(db, faculty_id):
    fac = db.execute("SELECT * FROM faculty WHERE id=?", (faculty_id,)).fetchone()
    if not fac:
        flash("Faculty member not found.", "error")
    return fac


@app.route("/admin/faculty")
@role_required("admin")
def admin_faculty():
    db = get_db()
    clauses, params = [], []
    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        clauses.append(f"(f.full_name {LIKE} ? OR f.email {LIKE} ?)")
        params += [like, like]
    dept_id = _int_or_none(request.args.get("department_id"))
    if dept_id:
        clauses.append("f.department_id=?")
        params.append(dept_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = db.execute(
        f"""SELECT f.*, d.name dept,
                  (SELECT COUNT(*) FROM course_assignments a WHERE a.faculty_id=f.id) assign_count
            FROM faculty f LEFT JOIN departments d ON d.id=f.department_id
            {where} ORDER BY f.full_name""", params).fetchall()
    return render_template("admin_faculty.html", rows=rows,
                           departments=dept_options(db), args=request.args)


@app.route("/admin/faculty/new", methods=["GET", "POST"])
@role_required("admin")
def admin_faculty_new():
    db = get_db()
    if request.method == "POST":
        data = _faculty_data_from_form(request.form)
        chosen_pw = request.form.get("initial_password", "").strip() or None
        pw_err = password_policy_error(chosen_pw) if chosen_pw else None
        if pw_err:
            # v0.15 policy: same rule as student create.
            flash(f"Could not add faculty member: {pw_err} Leave the "
                  f"initial password blank to auto-generate one.", "error")
            return render_template("faculty_form.html",
                                   **_faculty_form_values(db))
        try:
            fid, pw = create_faculty(db, data, password=chosen_pw)
            db.commit()
            log_audit("faculty_created",
                      f"Faculty '{data['full_name']}' ({data['email']})")
            flash(f"Faculty member '{data['full_name']}' added. Faculty login — "
                  f"username: {data['email']} · initial password: {pw} — "
                  f"shown ONCE, note it now.", "ok")
            return redirect(url_for("admin_faculty"))
        except ValueError as e:
            db.rollback()
            flash(f"Could not add faculty member: {e}", "error")
        except Exception as e:
            db.rollback()
            flash("Could not add faculty member: " + ("duplicate email." if is_unique_error(e) else str(e)), "error")
    return render_template("faculty_form.html", **_faculty_form_values(db))


@app.route("/admin/faculty/<int:faculty_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def admin_faculty_edit(faculty_id):
    db = get_db()
    fac = _get_faculty_or_redirect(db, faculty_id)
    if not fac:
        return redirect(url_for("admin_faculty"))
    if request.method == "POST":
        data = _faculty_data_from_form(request.form)
        is_active = 1 if request.form.get("is_active") else 0
        clash = None
        if data["email"]:
            clash = db.execute("SELECT id FROM faculty WHERE email=? AND id<>?",
                               (data["email"], faculty_id)).fetchone()
            if not clash:
                clash = db.execute(
                    "SELECT id FROM users WHERE username=? AND COALESCE(faculty_id,-1)<>?",
                    (data["email"], faculty_id)).fetchone()
        if not data["full_name"] or not data["email"] or "@" not in data["email"]:
            flash("Full name and a valid email are required.", "error")
        elif clash:
            flash(f"Email '{data['email']}' is already in use by another account.", "error")
        else:
            try:
                db.execute(
                    """UPDATE faculty SET full_name=?, email=?, phone=?,
                       designation=?, department_id=?, is_active=? WHERE id=?""",
                    (data["full_name"], data["email"], data["phone"] or None,
                     data["designation"] or None, data["department_id"],
                     is_active, faculty_id))
                # the login's username IS the email: keep both in sync
                db.execute(
                    "UPDATE users SET username=?, display_name=?, is_active=? "
                    "WHERE faculty_id=?",
                    (data["email"], data["full_name"], is_active, faculty_id))
                db.commit()
                log_audit("faculty_deactivated" if not is_active else "faculty_updated",
                          f"Faculty '{data['full_name']}' ({data['email']})")
                flash(f"Faculty member '{data['full_name']}' updated.", "ok")
                return redirect(url_for("admin_faculty_edit", faculty_id=faculty_id))
            except Exception as e:
                db.rollback()
                flash("Could not update faculty member: " + ("duplicate email." if is_unique_error(e) else str(e)), "error")
    return render_template("faculty_form.html", **_faculty_form_values(db, fac))


@app.route("/admin/faculty/<int:faculty_id>/reset-password", methods=["POST"])
@role_required("admin")
def admin_faculty_reset_password(faculty_id):
    db = get_db()
    fac = _get_faculty_or_redirect(db, faculty_id)
    if not fac:
        return redirect(url_for("admin_faculty"))
    chosen_pw = request.form.get("new_password", "").strip()
    if chosen_pw:
        pw_err = password_policy_error(chosen_pw)
        if pw_err:
            flash(f"Could not reset password: {pw_err}", "error")
            return redirect(url_for("admin_faculty_edit", faculty_id=faculty_id))
        pw = chosen_pw
    else:
        pw = generate_password()
    db.execute("UPDATE users SET password_hash=? WHERE faculty_id=?",
               (generate_password_hash(pw), faculty_id))
    db.commit()
    log_audit("faculty_password_reset",
                f"Password reset for {fac['email']} ({fac['full_name']})")
    flash(f"Password reset for {fac['email']} ({fac['full_name']}). "
          f"New password: {pw} — shown ONCE, note it now.", "ok")
    return redirect(url_for("admin_faculty_edit", faculty_id=faculty_id))


@app.route("/admin/faculty/<int:faculty_id>/delete", methods=["POST"])
@role_required("admin")
def admin_faculty_delete(faculty_id):
    db = get_db()
    fac = _get_faculty_or_redirect(db, faculty_id)
    if not fac:
        return redirect(url_for("admin_faculty"))
    assigned = db.execute(
        "SELECT COUNT(*) c FROM course_assignments WHERE faculty_id=?",
        (faculty_id,)).fetchone()["c"]
    if assigned:
        flash(f"Cannot delete '{fac['full_name']}': they still hold "
              f"{assigned} course assignment(s). Remove the assignments first "
              f"(or deactivate the account instead).", "error")
        return redirect(url_for("admin_faculty"))
    db.execute("DELETE FROM users WHERE faculty_id=?", (faculty_id,))
    db.execute("DELETE FROM faculty WHERE id=?", (faculty_id,))
    db.commit()
    log_audit("faculty_deleted", f"Faculty '{fac['full_name']}'")
    flash(f"Faculty member '{fac['full_name']}' and their login deleted.", "ok")
    return redirect(url_for("admin_faculty"))


@app.route("/admin/faculty/<int:faculty_id>/assign", methods=["POST"])
@role_required("admin")
def admin_faculty_assign(faculty_id):
    db = get_db()
    fac = _get_faculty_or_redirect(db, faculty_id)
    if not fac:
        return redirect(url_for("admin_faculty"))
    course_id = _int_or_none(request.form.get("course_id"))
    session_id = _int_or_none(request.form.get("session_id"))
    back = redirect(url_for("admin_faculty_edit", faculty_id=faculty_id))
    course = db.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone() if course_id else None
    sess = db.execute("SELECT * FROM academic_sessions WHERE id=?", (session_id,)).fetchone() if session_id else None
    if not course or not sess:
        flash("Choose a course and a session to assign.", "error")
        return back
    mine = db.execute(
        "SELECT id FROM course_assignments WHERE faculty_id=? AND course_id=? AND session_id=?",
        (faculty_id, course_id, session_id)).fetchone()
    if mine:
        flash(f"{course['code']} in {sess['name']} is already assigned to "
              f"{fac['full_name']}.", "error")
        return back
    other = db.execute(
        """SELECT f.full_name FROM course_assignments a
           JOIN faculty f ON f.id=a.faculty_id
           WHERE a.course_id=? AND a.session_id=? AND a.faculty_id<>?""",
        (course_id, session_id, faculty_id)).fetchone()
    if other:
        flash(f"{course['code']} in {sess['name']} is already assigned to "
              f"{other['full_name']} — one primary teacher per course + session. "
              f"Remove that assignment first if you want to reassign it.", "error")
        return back
    try:
        db.insert(
            """INSERT INTO course_assignments (faculty_id,course_id,session_id,created_at)
               VALUES (?,?,?,?)""",
            (faculty_id, course_id, session_id, _now()))
        db.commit()
        flash(f"Assigned {course['code']} ({sess['name']}) to {fac['full_name']}.", "ok")
    except Exception as e:
        db.rollback()
        flash("Could not assign course: " + ("already assigned." if is_unique_error(e) else str(e)), "error")
    return back


@app.route("/admin/faculty/<int:faculty_id>/assign/<int:assignment_id>/remove", methods=["POST"])
@role_required("admin")
def admin_faculty_unassign(faculty_id, assignment_id):
    db = get_db()
    fac = _get_faculty_or_redirect(db, faculty_id)
    if not fac:
        return redirect(url_for("admin_faculty"))
    row = db.execute(
        """SELECT a.*, c.code FROM course_assignments a JOIN courses c ON c.id=a.course_id
           WHERE a.id=? AND a.faculty_id=?""", (assignment_id, faculty_id)).fetchone()
    if row:
        db.execute("DELETE FROM course_assignments WHERE id=?", (assignment_id,))
        db.commit()
        flash(f"Assignment removed: {row['code']} is no longer taught by "
              f"{fac['full_name']} in that session.", "ok")
    return redirect(url_for("admin_faculty_edit", faculty_id=faculty_id))


# ---------------------------------------------------------------- students: Excel
def _cell_str(value):
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        try:
            return value.strftime("%Y-%m-%d")
        except Exception:
            return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


@app.route("/admin/students/template.xlsx")
@role_required("admin")
def admin_students_template():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Students"
    ws.append([label for _f, label in EXCEL_COLUMNS])
    ws.append(["CUVAS-DEMO-2027-001", "35202-0000007-7", "Example Student (Demo)", "Example Father",
               "Female", "2005-02-02", "Demo Domicile", "A+", "0300-0000007",
               "example.student@example.com", "Example Present Address", "Example Permanent Address",
               "Department of Computer Science (Demo)", "BS Computer Science (Demo)",
               "Fall 2026 (Demo)", "Main Campus (Demo)", "Active", 1])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="students_import_template.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/admin/students/import", methods=["GET", "POST"])
@role_required("admin")
def admin_students_import():
    db = get_db()
    if request.method == "GET":
        return render_template("student_import.html")
    f = request.files.get("file")
    if not f or not f.filename:
        flash("Please choose an .xlsx file to import.", "error")
        return render_template("student_import.html")
    if not f.filename.lower().endswith(".xlsx"):
        flash("Only .xlsx files are supported (download the template).", "error")
        return render_template("student_import.html")
    from openpyxl import load_workbook
    try:
        wb = load_workbook(f, data_only=True)
    except Exception as e:
        flash(f"Could not read that file as an Excel workbook: {e}", "error")
        return render_template("student_import.html")
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        flash("The file is empty.", "error")
        return render_template("student_import.html")
    field_to_idx = _header_map(rows[0])
    if "registration_no" not in field_to_idx or "name" not in field_to_idx:
        flash("Could not find the required 'Registration No' and 'Name' columns — "
              "headers are matched by name; please use the template.", "error")
        return render_template("student_import.html")

    # name -> id lookups for department / program / session
    dept_by_name = {r["name"].strip().lower(): r["id"] for r in db.execute("SELECT id,name FROM departments").fetchall()}
    prog_by_name = {r["name"].strip().lower(): r["id"] for r in db.execute("SELECT id,name FROM programs").fetchall()}
    sess_by_name = {r["name"].strip().lower(): r["id"] for r in db.execute("SELECT id,name FROM academic_sessions").fetchall()}

    imported, skipped, created_logins = [], [], []
    for lineno, raw in enumerate(rows[1:], start=2):
        if raw is None or all(v is None or str(v).strip() == "" for v in raw):
            continue

        def val(field):
            idx = field_to_idx.get(field)
            return _cell_str(raw[idx]) if idx is not None and idx < len(raw) else ""

        data = {field: val(field) for field, _l in EXCEL_COLUMNS
                if field not in ("department", "program", "session")}
        data["current_semester"] = _int_or_none(data.get("current_semester"))
        label = data.get("registration_no") or data.get("name") or f"row {lineno}"
        problems = []
        for field, lookup in (("department", dept_by_name), ("program", prog_by_name),
                              ("session", sess_by_name)):
            name_val = val(field)
            if name_val:
                found = lookup.get(name_val.strip().lower())
                if found is None:
                    problems.append(f"unknown {field} '{name_val}'")
                else:
                    data[field + "_id"] = found
        if problems:
            skipped.append((lineno, label, "; ".join(problems)))
            continue
        try:
            sid, pw = create_student(db, data)
            db.commit()
            imported.append(label)
            created_logins.append({"registration_no": data["registration_no"],
                                   "name": data["name"], "password": pw})
        except ValueError as e:
            db.rollback()
            skipped.append((lineno, label, str(e)))
        except Exception as e:
            db.rollback()
            skipped.append((lineno, label, "duplicate registration/CNIC" if is_unique_error(e) else str(e)))
    log_audit("students_imported",
              f"Excel import: {len(imported)} imported, {len(skipped)} skipped")
    return render_template("student_import_result.html", imported=imported,
                           skipped=skipped, created_logins=created_logins)


@app.route("/admin/students/export.xlsx")
@role_required("admin", "accounts", "coe")
def admin_students_export():
    db = get_db()
    where, params = _student_filter_sql(request.args)
    rows = db.execute(
        f"""SELECT s.*, d.name dept_name, p.name prog_name, ss.name sess_name FROM students s
            LEFT JOIN departments d ON d.id=s.department_id
            LEFT JOIN programs p ON p.id=s.program_id
            LEFT JOIN academic_sessions ss ON ss.id=s.session_id
            {where} ORDER BY s.id""", params).fetchall()
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Students"
    ws.append([label for _f, label in EXCEL_COLUMNS])
    for r in rows:
        values = []
        for field, _label in EXCEL_COLUMNS:
            if field == "department":
                values.append(r["dept_name"] or "")
            elif field == "program":
                values.append(r["prog_name"] or "")
            elif field == "session":
                values.append(r["sess_name"] or r["session_name"] or "")
            else:
                v = r.get(field)
                values.append("" if v is None else v)
        ws.append(values)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="students_export.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------------------------------------------------------------- routes: student dashboard
@app.route("/student")
@role_required("student")
def student_dashboard():
    db = get_db()
    sid = session.get("student_id")
    student = db.execute(
        """SELECT s.*, d.name dept, p.name prog FROM students s
           LEFT JOIN departments d ON d.id=s.department_id
           LEFT JOIN programs p ON p.id=s.program_id WHERE s.id=?""", (sid,)).fetchone()
    if not student:
        flash("No student record is linked to this login.", "error")
        return redirect(url_for("logout"))
    certs = db.execute("SELECT * FROM certificates WHERE student_id=?", (sid,)).fetchall()
    news = db.execute(
        """SELECT * FROM notifications
           WHERE COALESCE(is_published,1)=1 AND COALESCE(audience,'All') IN ('All','Students')
           ORDER BY published_at DESC, id DESC""").fetchall()
    # --- v0.6: own documents, own tickets, published repository items ---
    my_documents = db.execute(
        "SELECT id,doc_type,file_name,file_mime,status,admin_remarks,uploaded_at,reviewed_at "
        "FROM student_documents WHERE student_id=? ORDER BY uploaded_at DESC, id DESC",
        (sid,)).fetchall()
    my_tickets = db.execute(
        "SELECT * FROM tickets WHERE student_id=? ORDER BY updated_at DESC, id DESC",
        (sid,)).fetchall()
    repo_docs = db.execute(
        """SELECT id,title,category,description,file_name,created_at FROM repository_docs
           WHERE COALESCE(is_published,1)=1 ORDER BY created_at DESC, id DESC""").fetchall()
    enrollments = db.execute(
        """SELECT e.*, c.code, c.title, c.credit_theory, c.credit_lab, c.faculty_name
           FROM enrollments e JOIN courses c ON c.id=e.course_id
           WHERE e.student_id=? ORDER BY c.code""", (sid,)).fetchall()
    plan_rows = db.execute(
        "SELECT * FROM courses WHERE program_id=? ORDER BY semester_no, code",
        (student["program_id"],)).fetchall() if student["program_id"] else []
    plan = {}
    for r in plan_rows:
        plan.setdefault(r["semester_no"], []).append(r)
    plan_hours = {sem: sum((x["credit_theory"] or 0) + (x["credit_lab"] or 0) for x in rows)
                  for sem, rows in plan.items()}

    # transcript: published results only, grades derived via the shared helper
    transcript, cgpa, cumulative_ch = transcript_data(db, sid, published_only=True)

    vouchers = db.execute("SELECT * FROM vouchers WHERE student_id=? ORDER BY id", (sid,)).fetchall()
    voucher_children = {v["id"] for v in vouchers if v.get("parent_voucher_id")}
    parents_with_children = {v["parent_voucher_id"] for v in vouchers if v.get("parent_voucher_id")}
    for v in vouchers:
        v["payable"] = v["status"] == "Pending"
        v["can_split"] = v["status"] == "Pending" and v["id"] not in parents_with_children
        v["is_child"] = v["id"] in voucher_children
    # the student's applicable real fee plan (program + session + semester)
    student_plan, fee_lines = None, []
    eff_session_id = student.get("session_id")
    if not eff_session_id and student.get("session_name"):
        srow = db.execute("SELECT id FROM academic_sessions WHERE name=?",
                          (student["session_name"],)).fetchone()
        if srow:
            eff_session_id = srow["id"]
    if student["program_id"] and eff_session_id:
        student_plan = db.execute(
            """SELECT fp.*, p.name prog_name, ss.name sess_name FROM fee_plans fp
               LEFT JOIN programs p ON p.id=fp.program_id
               LEFT JOIN academic_sessions ss ON ss.id=fp.session_id
               WHERE fp.program_id=? AND fp.session_id=? AND fp.semester_no=?
               ORDER BY fp.id DESC""",
            (student["program_id"], eff_session_id,
             student["current_semester"] or 0)).fetchone()
    if student_plan:
        fee_lines = db.execute(
            """SELECT l.*, h.name head_name FROM fee_plan_lines l
               LEFT JOIN fee_heads h ON h.id=l.head_id WHERE l.plan_id=? ORDER BY l.id""",
            (student_plan["id"],)).fetchall()
        for l in fee_lines:
            l["head"] = l.get("head_name") or l.get("head")
    else:
        fee_lines = db.execute(
            "SELECT * FROM fee_plan_lines WHERE plan_id IS NULL ORDER BY id").fetchall()
    fee_total = sum(x["amount"] or 0 for x in fee_lines)
    ledger = db.execute("SELECT * FROM ledger_entries WHERE student_id=? ORDER BY entry_date, id", (sid,)).fetchall()
    payable = sum(x["debit"] or 0 for x in ledger)
    paid = sum(x["credit"] or 0 for x in ledger)
    active_tab = request.args.get("tab", "news")
    return render_template(
        "student_dashboard.html", student=student, certs=certs, news=news,
        enrollments=enrollments, plan=plan, plan_hours=plan_hours,
        fulfilled_hours=cumulative_ch, transcript=transcript, cgpa=cgpa,
        vouchers=vouchers, fee_lines=fee_lines, fee_total=fee_total,
        student_plan=student_plan,
        ledger=ledger, payable=payable, paid=paid, outstanding=payable - paid,
        my_documents=my_documents, doc_types=DOC_TYPES,
        my_tickets=my_tickets, ticket_categories=TICKET_CATEGORIES,
        repo_docs=repo_docs,
        active_tab=active_tab)


# ================================================================ v0.3 FINANCE
# Fee heads, fee plans, vouchers, challan PDF, installments, paid proof,
# verification and the append-only ledger. Rules (architecture.md):
#   * a debit ledger entry is written when a voucher is created, a credit
#     entry when its payment is verified — entries are never edited/deleted;
#   * splitting a voucher reverses the parent's debit (negative debit entry)
#     and debits the two children, so statement totals always equal the sum
#     of payable voucher amounts;
#   * verification is guarded so a voucher can be credited exactly once.
VOUCHER_STATUSES = ["Pending", "Proof Submitted", "Paid", "Split into Installments"]
PAYMENT_CHANNELS = ["Bank", "Mobile Wallet", "RAAST"]
# (The request-size cap lives with the v0.15 hardening config near the
# top of this file: MAX_CONTENT_LENGTH = 10 MB for every upload,
# proof uploads included — per-file rules still apply on top of it.)


def next_challan_no(db):
    """Sequential challan number, e.g. CUVAS-2026-0007 (per-year counter)."""
    year = datetime.date.today().year
    key = f"challan-{year}"
    row = db.execute("SELECT value FROM counters WHERE name=?", (key,)).fetchone()
    if row is None:
        db.execute("INSERT INTO counters (name,value) VALUES (?,0)", (key,))
        val = 0
    else:
        val = row["value"]
    val += 1
    db.execute("UPDATE counters SET value=? WHERE name=?", (val, key))
    return f"CUVAS-{year}-{val:04d}"


def ledger_add(db, voucher, entry_date, description, debit=0, credit=0):
    return db.insert(
        """INSERT INTO ledger_entries (student_id,voucher_id,voucher_title,challan_no,
           entry_date,description,debit,credit) VALUES (?,?,?,?,?,?,?,?)""",
        (voucher["student_id"], voucher["id"], voucher["title"], voucher["challan_no"],
         entry_date, description, debit, credit))


def plan_total(db, plan_id):
    row = db.execute(
        "SELECT COALESCE(SUM(amount),0) t FROM fee_plan_lines WHERE plan_id=?",
        (plan_id,)).fetchone()
    return row["t"] or 0


def plan_lines(db, plan_id):
    return db.execute(
        """SELECT l.*, h.name head_name FROM fee_plan_lines l
           LEFT JOIN fee_heads h ON h.id=l.head_id WHERE l.plan_id=? ORDER BY l.id""",
        (plan_id,)).fetchall()


def get_voucher(db, voucher_id):
    return db.execute(
        """SELECT v.*, s.name student_name, s.registration_no, s.program_id student_program_id,
                  p.name prog_name, ss.name sess_name
           FROM vouchers v JOIN students s ON s.id=v.student_id
           LEFT JOIN programs p ON p.id=s.program_id
           LEFT JOIN academic_sessions ss ON ss.id=COALESCE(v.session_id, s.session_id)
           WHERE v.id=?""", (voucher_id,)).fetchone()


def voucher_breakdown(db, v):
    """(label, amount) lines for the challan PDF."""
    if v.get("parent_voucher_id"):
        parent = db.execute("SELECT * FROM vouchers WHERE id=?",
                            (v["parent_voucher_id"],)).fetchone()
        siblings = db.execute(
            "SELECT id FROM vouchers WHERE parent_voucher_id=? ORDER BY id",
            (v["parent_voucher_id"],)).fetchall()
        idx = [s["id"] for s in siblings].index(v["id"]) + 1 if siblings else 1
        label = f"Installment {idx} of {len(siblings) or 2}"
        if parent:
            label += f" — {parent['title']} ({parent['challan_no']})"
        return [(label, v["amount"] or 0)]
    if v.get("fee_plan_id"):
        lines = plan_lines(db, v["fee_plan_id"])
        if lines and sum(l["amount"] or 0 for l in lines) == (v["amount"] or 0):
            return [(l.get("head_name") or l.get("head") or "Fee", l["amount"] or 0)
                    for l in lines]
    return [(v["title"], v["amount"] or 0)]


def build_challan_pdf(db, v):
    """Challan PDF bytes for one voucher (ReportLab)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer,
                                    Table, TableStyle)
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    student = db.execute(
        """SELECT s.*, p.name prog_name, d.name dept_name FROM students s
           LEFT JOIN programs p ON p.id=s.program_id
           LEFT JOIN departments d ON d.id=s.department_id WHERE s.id=?""",
        (v["student_id"],)).fetchone()
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=16 * mm, bottomMargin=14 * mm,
                            leftMargin=16 * mm, rightMargin=16 * mm,
                            title=f"Fee Challan {v['challan_no']}")
    story = [Paragraph("MY CUVAS — Campus Management System", styles["Title"]),
             Paragraph("Cholistan University of Veterinary and Animal Sciences",
                       styles["Heading3"]),
             Paragraph("FEE CHALLAN / VOUCHER", styles["Heading2"]), Spacer(1, 4 * mm)]
    info = [["Student Name", student["name"] if student else "—",
             "Challan No.", v["challan_no"] or "—"],
            ["Registration No.", student["registration_no"] if student else "—",
             "Status", v["status"] or "—"],
            ["Program", (student["prog_name"] or "—") if student else "—",
             "Due Date", v["due_date"] or "—"],
            ["Department", (student["dept_name"] or "—") if student else "—",
             "Semester", str(v.get("semester_no") or (student["current_semester"] if student else "—"))],
            ["Voucher Title", v["title"] or "—", "Kind", (v.get("kind") or "semester").title()]]
    t = Table(info, colWidths=[32 * mm, 52 * mm, 26 * mm, 58 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b9d2c2")),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eaf5ee")),
                           ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eaf5ee")),
                           ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [t, Spacer(1, 5 * mm)]
    lines = voucher_breakdown(db, v)
    rows = [["#", "Description", "Amount (Rs)"]]
    for i, (label, amt) in enumerate(lines, 1):
        rows.append([str(i), label, f"{amt:,}"])
    rows.append(["", "TOTAL PAYABLE", f"{v['amount'] or 0:,}"])
    lt = Table(rows, colWidths=[10 * mm, 108 * mm, 50 * mm])
    lt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b9d2c2")),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b6b3a")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eaf5ee")),
                            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("ALIGN", (2, 0), (2, -1), "RIGHT")]))
    story += [lt, Spacer(1, 6 * mm)]
    if v["status"] == "Split into Installments":
        story.append(Paragraph(
            "This voucher has been split into installments and is NOT payable — "
            "please pay the installment challans instead.", styles["BodyText"]))
    else:
        story.append(Paragraph(
            "Payable at any bank branch / mobile wallet / RAAST. After payment, upload the "
            "paid proof from your MY CUVAS student portal; the voucher is marked Paid after "
            "verification by the accounts office.", styles["BodyText"]))
    story += [Spacer(1, 8 * mm),
              Paragraph("Generated by MY CUVAS (Demo) — all data shown is fictional demo data.",
                        styles["BodyText"])]
    doc.build(story)
    buf.seek(0)  # AFTER build() — house lesson (0-byte PDFs otherwise)
    return buf.getvalue()


def split_voucher(db, v):
    """Split a Pending, childless voucher into 2 installments.
    Returns (ok, message). Reverses the parent debit in the ledger and
    debits the children, keeping statement totals exact."""
    if v["status"] != "Pending":
        return False, "Only a Pending voucher can be split into installments."
    children = db.execute("SELECT COUNT(*) c FROM vouchers WHERE parent_voucher_id=?",
                          (v["id"],)).fetchone()["c"]
    if children:
        return False, "This voucher has already been split into installments."
    amount = v["amount"] or 0
    if amount < 2:
        return False, "Voucher amount is too small to split."
    first = (amount + 1) // 2  # ceil half
    parts = [(first, v["due_date"]), (amount - first, _add_days(v["due_date"], 30))]
    db.execute("UPDATE vouchers SET status='Split into Installments' WHERE id=?", (v["id"],))
    ledger_add(db, v, _today(),
               f"Reversed — {v['title']} ({v['challan_no']}) split into installments",
               debit=-amount)
    for i, (amt, due) in enumerate(parts, 1):
        title = f"{v['title']} — Installment {i} of 2"
        challan = next_challan_no(db)
        cid = db.insert(
            """INSERT INTO vouchers (student_id,challan_no,title,amount,due_date,status,remarks,
               session_id,semester_no,kind,parent_voucher_id,fee_plan_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (v["student_id"], challan, title, amt, due, "Pending", "",
             v.get("session_id"), v.get("semester_no"), "installment", v["id"],
             v.get("fee_plan_id")))
        child = dict(v, id=cid, challan_no=challan, title=title)
        ledger_add(db, child, _today(), f"{title} charged", debit=amt)
    return True, "Voucher split into 2 installments."


def _add_days(date_str, days):
    try:
        d = datetime.date.fromisoformat((date_str or "")[:10])
    except ValueError:
        d = datetime.date.today()
    return (d + datetime.timedelta(days=days)).isoformat()


# ---------------------------------------------------------------- fee heads (admin)
@app.route("/admin/fee-heads")
@role_required("admin", "accounts")
def admin_fee_heads():
    rows = get_db().execute(
        """SELECT h.*, (SELECT COUNT(*) FROM fee_plan_lines l WHERE l.head_id=h.id) use_count
           FROM fee_heads h ORDER BY h.name""").fetchall()
    return render_template("fee_heads.html", rows=rows)


@app.route("/admin/fee-heads/new", methods=["POST"])
@role_required("admin", "accounts")
def admin_fee_head_new():
    db = get_db()
    name = request.form.get("name", "").strip()
    if not name:
        flash("Fee head name is required.", "error")
    elif db.execute("SELECT id FROM fee_heads WHERE name=?", (name,)).fetchone():
        flash(f"A fee head named '{name}' already exists.", "error")
    else:
        db.insert("INSERT INTO fee_heads (name) VALUES (?)", (name,))
        db.commit()
        log_audit("fee_head_created", f"Fee head '{name}'")
        flash(f"Fee head '{name}' added.", "ok")
    return redirect(url_for("admin_fee_heads"))


@app.route("/admin/fee-heads/<int:head_id>/edit", methods=["GET", "POST"])
@role_required("admin", "accounts")
def admin_fee_head_edit(head_id):
    db = get_db()
    head = db.execute("SELECT * FROM fee_heads WHERE id=?", (head_id,)).fetchone()
    if not head:
        flash("Fee head not found.", "error")
        return redirect(url_for("admin_fee_heads"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        clash = db.execute("SELECT id FROM fee_heads WHERE name=? AND id<>?",
                           (name, head_id)).fetchone()
        if not name:
            flash("Fee head name is required.", "error")
        elif clash:
            flash(f"A fee head named '{name}' already exists.", "error")
        else:
            db.execute("UPDATE fee_heads SET name=? WHERE id=?", (name, head_id))
            db.commit()
            log_audit("fee_head_updated", f"Fee head renamed to '{name}'")
            flash(f"Fee head renamed to '{name}'.", "ok")
            return redirect(url_for("admin_fee_heads"))
    return render_template("fee_head_form.html", head=head)


@app.route("/admin/fee-heads/<int:head_id>/delete", methods=["POST"])
@role_required("admin", "accounts")
def admin_fee_head_delete(head_id):
    db = get_db()
    head = db.execute("SELECT * FROM fee_heads WHERE id=?", (head_id,)).fetchone()
    if not head:
        flash("Fee head not found.", "error")
        return redirect(url_for("admin_fee_heads"))
    used = db.execute("SELECT COUNT(*) c FROM fee_plan_lines WHERE head_id=?",
                      (head_id,)).fetchone()["c"]
    if used:
        flash(f"Cannot delete fee head '{head['name']}': it is used in {used} fee plan line(s).",
              "error")
        return redirect(url_for("admin_fee_heads"))
    db.execute("DELETE FROM fee_heads WHERE id=?", (head_id,))
    db.commit()
    log_audit("fee_head_deleted", f"Fee head '{head['name']}'")
    flash(f"Fee head '{head['name']}' deleted.", "ok")
    return redirect(url_for("admin_fee_heads"))


# ---------------------------------------------------------------- fee plans (admin)
@app.route("/admin/fee-plans")
@role_required("admin", "accounts")
def admin_fee_plans():
    rows = get_db().execute(
        """SELECT fp.*, p.name prog_name, ss.name sess_name,
                  COALESCE((SELECT SUM(l.amount) FROM fee_plan_lines l WHERE l.plan_id=fp.id),0) total,
                  (SELECT COUNT(*) FROM vouchers v WHERE v.fee_plan_id=fp.id) voucher_count
           FROM fee_plans fp LEFT JOIN programs p ON p.id=fp.program_id
           LEFT JOIN academic_sessions ss ON ss.id=fp.session_id
           ORDER BY p.name, fp.semester_no""").fetchall()
    return render_template("fee_plans.html", rows=rows)


def _fee_plan_form_values(db, plan=None):
    lines = plan_lines(db, plan["id"]) if plan else []
    return {"programs": program_options(db), "sessions": session_options(db),
            "heads": db.execute("SELECT * FROM fee_heads ORDER BY name").fetchall(),
            "plan": plan, "lines": lines}


def _save_fee_plan(db, plan_id, form):
    """Create (plan_id=None) or update a fee plan + its lines. Returns plan id
    or None after flashing the problem. Caller commits."""
    program_id = _int_or_none(form.get("program_id"))
    session_id = _int_or_none(form.get("session_id"))
    semester_no = _int_or_none(form.get("semester_no"))
    title = form.get("title", "").strip()
    due_date = form.get("due_date", "").strip()
    if not program_id or not session_id or semester_no is None:
        flash("Program, session and semester number are required.", "error")
        return None
    head_ids = form.getlist("line_head_id")
    amounts = form.getlist("line_amount")
    lines = []
    for hid, amt in zip(head_ids, amounts):
        hid, amt = _int_or_none(hid), _int_or_none(amt)
        if hid and amt and amt > 0:
            lines.append((hid, amt))
    if not lines:
        flash("Add at least one fee line (fee head + amount).", "error")
        return None
    if plan_id is None:
        plan_id = db.insert(
            "INSERT INTO fee_plans (program_id,session_id,semester_no,title,due_date) VALUES (?,?,?,?,?)",
            (program_id, session_id, semester_no, title, due_date))
    else:
        db.execute(
            "UPDATE fee_plans SET program_id=?,session_id=?,semester_no=?,title=?,due_date=? WHERE id=?",
            (program_id, session_id, semester_no, title, due_date, plan_id))
        db.execute("DELETE FROM fee_plan_lines WHERE plan_id=?", (plan_id,))
    heads = {r["id"]: r["name"] for r in db.execute("SELECT id,name FROM fee_heads").fetchall()}
    for hid, amt in lines:
        db.insert(
            "INSERT INTO fee_plan_lines (plan_id,head_id,head,amount) VALUES (?,?,?,?)",
            (plan_id, hid, heads.get(hid), amt))
    return plan_id


@app.route("/admin/fee-plans/new", methods=["GET", "POST"])
@role_required("admin", "accounts")
def admin_fee_plan_new():
    db = get_db()
    if request.method == "POST":
        pid = _save_fee_plan(db, None, request.form)
        if pid:
            db.commit()
            log_audit("fee_plan_created", f"Fee plan #{pid}")
            flash("Fee plan created.", "ok")
            return redirect(url_for("admin_fee_plans"))
        db.rollback()
    return render_template("fee_plan_form.html", **_fee_plan_form_values(db))


@app.route("/admin/fee-plans/<int:plan_id>/edit", methods=["GET", "POST"])
@role_required("admin", "accounts")
def admin_fee_plan_edit(plan_id):
    db = get_db()
    plan = db.execute("SELECT * FROM fee_plans WHERE id=?", (plan_id,)).fetchone()
    if not plan:
        flash("Fee plan not found.", "error")
        return redirect(url_for("admin_fee_plans"))
    if request.method == "POST":
        if _save_fee_plan(db, plan_id, request.form):
            db.commit()
            log_audit("fee_plan_updated", f"Fee plan #{plan_id}")
            flash("Fee plan updated.", "ok")
            return redirect(url_for("admin_fee_plans"))
        db.rollback()
    return render_template("fee_plan_form.html", **_fee_plan_form_values(db, plan))


@app.route("/admin/fee-plans/<int:plan_id>/delete", methods=["POST"])
@role_required("admin", "accounts")
def admin_fee_plan_delete(plan_id):
    db = get_db()
    plan = db.execute("SELECT * FROM fee_plans WHERE id=?", (plan_id,)).fetchone()
    if not plan:
        flash("Fee plan not found.", "error")
        return redirect(url_for("admin_fee_plans"))
    used = db.execute("SELECT COUNT(*) c FROM vouchers WHERE fee_plan_id=?",
                      (plan_id,)).fetchone()["c"]
    if used:
        flash(f"Cannot delete this fee plan: {used} voucher(s) were already generated from it.",
              "error")
        return redirect(url_for("admin_fee_plans"))
    db.execute("DELETE FROM fee_plan_lines WHERE plan_id=?", (plan_id,))
    db.execute("DELETE FROM fee_plans WHERE id=?", (plan_id,))
    db.commit()
    log_audit("fee_plan_deleted", f"Fee plan '{plan['title']}'")
    flash("Fee plan deleted.", "ok")
    return redirect(url_for("admin_fee_plans"))


# ---------------------------------------------------------------- vouchers (admin)
def _voucher_filter_sql(args):
    clauses, params = [], []
    status = (args.get("status") or "").strip()
    if status in VOUCHER_STATUSES:
        clauses.append("v.status=?")
        params.append(status)
    prog = _int_or_none(args.get("program_id"))
    if prog:
        clauses.append("s.program_id=?")
        params.append(prog)
    sess = _int_or_none(args.get("session_id"))
    if sess:
        clauses.append("COALESCE(v.session_id, s.session_id)=?")
        params.append(sess)
    q = (args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        clauses.append(f"(v.challan_no {LIKE} ? OR s.name {LIKE} ? OR s.registration_no {LIKE} ?)")
        params += [like, like, like]
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


@app.route("/admin/vouchers")
@role_required("admin", "accounts")
def admin_vouchers():
    db = get_db()
    where, params = _voucher_filter_sql(request.args)
    rows = db.execute(
        f"""SELECT v.*, s.name student_name, s.registration_no, p.name prog_name
            FROM vouchers v JOIN students s ON s.id=v.student_id
            LEFT JOIN programs p ON p.id=s.program_id {where} ORDER BY v.id DESC""",
        params).fetchall()
    counts = {s: db.execute("SELECT COUNT(*) c FROM vouchers WHERE status=?",
                             (s,)).fetchone()["c"] for s in VOUCHER_STATUSES}
    counts["total"] = db.execute("SELECT COUNT(*) c FROM vouchers").fetchone()["c"]
    return render_template("admin_vouchers.html", rows=rows, counts=counts,
                           programs=program_options(db), sessions=session_options(db),
                           statuses=VOUCHER_STATUSES, args=request.args)


def eligible_students(db, plan):
    return db.execute(
        """SELECT * FROM students WHERE program_id=? AND session_id=?
           AND current_semester=? AND COALESCE(status,'Active')='Active' ORDER BY name""",
        (plan["program_id"], plan["session_id"], plan["semester_no"])).fetchall()


def create_plan_voucher(db, plan, student, due_date):
    """Generate one voucher from a plan for a student + its debit ledger entry.
    Returns the voucher id, or None if the student already has one from the plan."""
    existing = db.execute(
        "SELECT id FROM vouchers WHERE fee_plan_id=? AND student_id=?",
        (plan["id"], student["id"])).fetchone()
    if existing:
        return None
    sess = db.execute("SELECT name FROM academic_sessions WHERE id=?",
                      (plan["session_id"],)).fetchone()
    title = f"Semester {plan['semester_no']} Fee"
    if sess:
        title += f" — {sess['name']}"
    total = plan_total(db, plan["id"])
    challan = next_challan_no(db)
    vid = db.insert(
        """INSERT INTO vouchers (student_id,challan_no,title,amount,due_date,status,remarks,
           session_id,semester_no,kind,fee_plan_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (student["id"], challan, title, total, due_date, "Pending", "",
         plan["session_id"], plan["semester_no"], "semester", plan["id"]))
    v = {"id": vid, "student_id": student["id"], "challan_no": challan, "title": title}
    ledger_add(db, v, _today(), f"{title} charged", debit=total)
    return vid


@app.route("/admin/vouchers/generate", methods=["GET", "POST"])
@role_required("admin", "accounts")
def admin_voucher_generate():
    db = get_db()
    plans = db.execute(
        """SELECT fp.*, p.name prog_name, ss.name sess_name FROM fee_plans fp
           LEFT JOIN programs p ON p.id=fp.program_id
           LEFT JOIN academic_sessions ss ON ss.id=fp.session_id ORDER BY fp.id DESC""").fetchall()
    plan = None
    plan_id = _int_or_none(request.values.get("plan_id"))
    if plan_id:
        plan = db.execute("SELECT * FROM fee_plans WHERE id=?", (plan_id,)).fetchone()
    if request.method == "POST":
        if not plan:
            flash("Please choose a fee plan first.", "error")
            return redirect(url_for("admin_voucher_generate"))
        due_date = request.form.get("due_date", "").strip() or plan.get("due_date") or _today()
        targets = eligible_students(db, plan)
        chosen = request.form.get("student_id", "")
        if chosen and chosen != "all":
            sid = _int_or_none(chosen)
            targets = [s for s in targets if s["id"] == sid]
            if not targets:
                flash("That student is not eligible for this plan "
                      "(program / session / semester / status must match).", "error")
                return redirect(url_for("admin_voucher_generate", plan_id=plan["id"]))
        created = skipped = 0
        for s in targets:
            if create_plan_voucher(db, plan, s, due_date):
                created += 1
            else:
                skipped += 1
        db.commit()
        log_audit("voucher_generated",
                  f"{created} voucher(s) created, {skipped} skipped — plan '{plan['title']}'")
        flash(f"Voucher generation complete — created {created}, skipped {skipped} "
              f"(already had a voucher from this plan).", "ok" if created else "error")
        return redirect(url_for("admin_vouchers"))
    students = eligible_students(db, plan) if plan else []
    return render_template("voucher_generate.html", plans=plans, plan=plan,
                           students=students,
                           plan_total_due=plan_total(db, plan["id"]) if plan else 0)


@app.route("/admin/vouchers/<int:voucher_id>")
@role_required("admin", "accounts")
def admin_voucher_detail(voucher_id):
    db = get_db()
    v = get_voucher(db, voucher_id)
    if not v:
        flash("Voucher not found.", "error")
        return redirect(url_for("admin_vouchers"))
    children = db.execute("SELECT * FROM vouchers WHERE parent_voucher_id=? ORDER BY id",
                          (voucher_id,)).fetchall()
    parent = db.execute("SELECT * FROM vouchers WHERE id=?",
                        (v["parent_voucher_id"],)).fetchone() if v.get("parent_voucher_id") else None
    entries = db.execute("SELECT * FROM ledger_entries WHERE voucher_id=? ORDER BY id",
                         (voucher_id,)).fetchall()
    return render_template("voucher_detail.html", v=v, children=children, parent=parent,
                           breakdown=voucher_breakdown(db, v), entries=entries,
                           channels=PAYMENT_CHANNELS)


@app.route("/admin/vouchers/<int:voucher_id>/challan.pdf")
@role_required("admin", "accounts")
def admin_voucher_challan(voucher_id):
    db = get_db()
    v = get_voucher(db, voucher_id)
    if not v:
        abort(404)
    return send_file(io.BytesIO(build_challan_pdf(db, v)), as_attachment=True,
                     download_name=f"challan-{v['challan_no']}.pdf",
                     mimetype="application/pdf")


@app.route("/admin/vouchers/<int:voucher_id>/proof")
@role_required("admin", "accounts")
def admin_voucher_proof(voucher_id):
    db = get_db()
    v = db.execute("SELECT * FROM vouchers WHERE id=?", (voucher_id,)).fetchone()
    if not v or not v.get("proof_blob"):
        abort(404)
    return send_file(io.BytesIO(bytes(v["proof_blob"])), as_attachment=True,
                     download_name=v.get("proof_filename") or f"proof-{voucher_id}",
                     mimetype=v.get("proof_mimetype") or "application/octet-stream")


@app.route("/admin/vouchers/<int:voucher_id>/verify", methods=["POST"])
@role_required("admin", "accounts")
def admin_voucher_verify(voucher_id):
    db = get_db()
    v = get_voucher(db, voucher_id)
    if not v:
        flash("Voucher not found.", "error")
        return redirect(url_for("admin_vouchers"))
    if v["status"] == "Paid":
        flash("This voucher is already Paid — it cannot be verified twice.", "error")
        return redirect(url_for("admin_voucher_detail", voucher_id=voucher_id))
    if v["status"] != "Proof Submitted":
        flash("Only a voucher with a submitted paid proof can be verified.", "error")
        return redirect(url_for("admin_voucher_detail", voucher_id=voucher_id))
    db.execute("UPDATE vouchers SET status='Paid', paid_at=? WHERE id=?",
               (_now(), voucher_id))
    already = db.execute(
        "SELECT COUNT(*) c FROM ledger_entries WHERE voucher_id=? AND credit>0",
        (voucher_id,)).fetchone()["c"]
    if not already:  # credit exactly once
        channel = v.get("payment_channel") or "Bank"
        ledger_add(db, v, _today(), f"Payment received — {channel}", credit=v["amount"] or 0)
    # --- v0.11: a verified repeat voucher activates its repeat request
    # (request -> Enrolled + the target-session enrollment). Runs inside
    # the same commit; the helper is a no-op unless the request is still
    # 'Approved', so re-verification can never double-activate. ---
    if v.get("repeat_request_id"):
        activate_repeat_request(db, v["repeat_request_id"])
    db.commit()
    log_audit("voucher_verified",
                f"Challan {v['challan_no']} — Rs {v['amount']:,}")
    flash(f"Voucher {v['challan_no']} verified — marked Paid.", "ok")
    return redirect(url_for("admin_voucher_detail", voucher_id=voucher_id))


@app.route("/admin/vouchers/<int:voucher_id>/reject", methods=["POST"])
@role_required("admin", "accounts")
def admin_voucher_reject(voucher_id):
    db = get_db()
    v = get_voucher(db, voucher_id)
    if not v:
        flash("Voucher not found.", "error")
        return redirect(url_for("admin_vouchers"))
    if v["status"] != "Proof Submitted":
        flash("Only a voucher with a submitted paid proof can be rejected.", "error")
        return redirect(url_for("admin_voucher_detail", voucher_id=voucher_id))
    remark = request.form.get("remark", "").strip() or "Paid proof rejected — please upload a clear copy."
    db.execute("UPDATE vouchers SET status='Pending', remarks=? WHERE id=?",
               (remark, voucher_id))
    db.commit()
    log_audit("voucher_rejected", f"Challan {v['challan_no']}")
    flash(f"Proof for {v['challan_no']} rejected — voucher is Pending again.", "ok")
    return redirect(url_for("admin_voucher_detail", voucher_id=voucher_id))


@app.route("/admin/vouchers/<int:voucher_id>/installments", methods=["POST"])
@role_required("admin", "accounts")
def admin_voucher_installments(voucher_id):
    db = get_db()
    v = get_voucher(db, voucher_id)
    if not v:
        flash("Voucher not found.", "error")
        return redirect(url_for("admin_vouchers"))
    ok, msg = split_voucher(db, v)
    db.commit() if ok else db.rollback()
    if ok:
        log_audit("voucher_split",
                  f"Challan {v['challan_no']} split into 2 installments")
    flash(msg, "ok" if ok else "error")
    return redirect(url_for("admin_voucher_detail", voucher_id=voucher_id))


# ---------------------------------------------------------------- vouchers (student)
def _own_voucher_or_none(db, voucher_id):
    v = get_voucher(db, voucher_id)
    if not v or v["student_id"] != session.get("student_id"):
        return None
    return v


@app.route("/student/vouchers/<int:voucher_id>/challan.pdf")
@role_required("student")
def student_voucher_challan(voucher_id):
    db = get_db()
    v = _own_voucher_or_none(db, voucher_id)
    if not v:
        flash("That voucher does not belong to your account.", "error")
        return redirect(url_for("student_dashboard", tab="voucher"))
    return send_file(io.BytesIO(build_challan_pdf(db, v)), as_attachment=True,
                     download_name=f"challan-{v['challan_no']}.pdf",
                     mimetype="application/pdf")


@app.route("/student/vouchers/<int:voucher_id>/installments", methods=["POST"])
@role_required("student")
def student_voucher_installments(voucher_id):
    db = get_db()
    v = _own_voucher_or_none(db, voucher_id)
    if not v:
        flash("That voucher does not belong to your account.", "error")
        return redirect(url_for("student_dashboard", tab="voucher"))
    ok, msg = split_voucher(db, v)
    db.commit() if ok else db.rollback()
    if ok:
        log_audit("voucher_split",
                  f"Challan {v['challan_no']} split into 2 installments")
    flash(msg, "ok" if ok else "error")
    return redirect(url_for("student_dashboard", tab="voucher"))


@app.route("/student/vouchers/<int:voucher_id>/proof", methods=["POST"])
@role_required("student")
def student_voucher_proof(voucher_id):
    db = get_db()
    v = _own_voucher_or_none(db, voucher_id)
    if not v:
        flash("That voucher does not belong to your account.", "error")
        return redirect(url_for("student_dashboard", tab="voucher"))
    if v["status"] != "Pending":
        flash("Paid proof can only be uploaded for a Pending voucher.", "error")
        return redirect(url_for("student_dashboard", tab="voucher"))
    f = request.files.get("proof")
    channel = request.form.get("payment_channel", "Bank")
    if channel not in PAYMENT_CHANNELS:
        channel = "Bank"
    if not f or not f.filename:
        flash("Please choose the paid voucher image/PDF file first.", "error")
        return redirect(url_for("student_dashboard", tab="voucher"))
    blob = f.read()
    if not blob:
        flash("That file is empty.", "error")
        return redirect(url_for("student_dashboard", tab="voucher"))
    db.execute(
        """UPDATE vouchers SET status='Proof Submitted', proof_blob=?, proof_filename=?,
           proof_mimetype=?, payment_channel=? WHERE id=?""",
        (blob, f.filename, f.mimetype or "application/octet-stream", channel, voucher_id))
    db.commit()
    flash(f"Paid proof for challan {v['challan_no']} submitted via {channel} — "
          f"it will be marked Paid after verification.", "ok")
    return redirect(url_for("student_dashboard", tab="voucher"))


# ================================================================ v0.4 RESULTS
# Grading scale, marks entry, transcripts and roll number slips. Rules:
#   * grade + grade point for a marks-based result are ALWAYS derived from
#     grade_bands (single helper) — entry screens, the transcript web tab and
#     the transcript PDF all read the same computation, so numbers match;
#   * pre-v0.4 seeded results carry no marks: they keep their stored grade /
#     grade point (legacy fallback in result_grade_gp) and are published by
#     the v0.4 backfill, which keeps the demo transcript exactly as it was;
#   * students only ever see PUBLISHED results on their transcript.

def get_grade_bands(db):
    return db.execute(
        "SELECT * FROM grade_bands ORDER BY min_marks DESC").fetchall()


def grade_for_marks(marks, is_absent, bands):
    """(grade, grade_point) derived from obtained marks via the bands."""
    if is_absent:
        return "F", 0.0
    if marks is None:
        return None, None
    for b in bands:  # bands sorted by min_marks DESC
        if marks >= b["min_marks"]:
            return b["grade"], float(b["grade_point"])
    return "F", 0.0


def result_grade_gp(row, bands):
    """Grade/GP actually shown for a result row: derived from marks when the
    row has marks (or the absent flag); legacy seeded rows fall back to the
    grade / grade point stored on the row."""
    if row.get("is_absent"):
        return "F", 0.0
    if row.get("marks_obtained") is not None:
        return grade_for_marks(float(row["marks_obtained"]), False, bands)
    return row.get("grade"), float(row.get("grade_point") or 0.0)


def transcript_data(db, student_id, published_only=True):
    """The ONE transcript computation, used by the student web tab and the
    transcript PDF. Returns (transcript, cgpa, total_credit_hours) where
    transcript = {semester_no: {"rows": [...], "sgpa": x, "cgpa": running}}.

    v0.11 repeat rule: when the student has (published) results for the
    SAME course in multiple sessions, only the LATEST attempt counts in
    SGPA/CGPA — latest = greatest session (sessions are created in
    chronological order, so the session id is the ordering), tie-broken
    by the greatest result id. Earlier attempts still appear in their
    semester group, flagged "superseded", with their points excluded.
    A student with no repeated course gets exactly the pre-v0.11 sums."""
    bands = get_grade_bands(db)
    pub = " AND COALESCE(r.is_published,0)=1" if published_only else ""
    rows = db.execute(
        f"""SELECT r.*, c.code, c.title, c.credit_theory, c.credit_lab
            FROM results r JOIN courses c ON c.id=r.course_id
            WHERE r.student_id=?{pub} ORDER BY r.semester_no, c.code""",
        (student_id,)).fetchall()
    latest_id = {}
    for r in rows:
        key = (r.get("session_id") or 0, r["id"])
        cur = latest_id.get(r["course_id"])
        if cur is None or key > cur[0]:
            latest_id[r["course_id"]] = (key, r["id"])
    superseded_ids = {r["id"] for r in rows
                      if latest_id[r["course_id"]][1] != r["id"]}
    transcript, cumulative_qp, cumulative_ch, cgpa = {}, 0.0, 0, 0.0
    for sem in sorted({r["semester_no"] for r in rows}):
        items, qp, ch = [], 0.0, 0
        for r in [x for x in rows if x["semester_no"] == sem]:
            credits = (r["credit_theory"] or 0) + (r["credit_lab"] or 0)
            grade, gp = result_grade_gp(r, bands)
            points = round((gp or 0.0) * credits, 2)
            superseded = r["id"] in superseded_ids
            if not superseded:
                qp += points
                ch += credits
            marks = r.get("marks_obtained")
            items.append({**r, "credits": credits, "grade": grade,
                          "grade_point": gp, "quality_points": points,
                          "superseded": superseded,
                          "marks_display": ("Absent" if r.get("is_absent") else
                                            ("—" if marks is None else
                                             (f"{marks:g}" if isinstance(marks, float) else str(marks))))})
        cumulative_qp += qp
        cumulative_ch += ch
        cgpa = round(cumulative_qp / cumulative_ch, 2) if cumulative_ch else 0.0
        transcript[sem] = {"rows": items,
                           "sgpa": round(qp / ch, 2) if ch else 0.0, "cgpa": cgpa}
    return transcript, cgpa, cumulative_ch


def find_result(db, student_id, course_id, semester_no, session_id):
    """A student's result for a course/semester, preferring the row recorded
    for this session; pre-v0.4 rows have session_id NULL and match any sheet."""
    return db.execute(
        """SELECT * FROM results WHERE student_id=? AND course_id=? AND semester_no=?
           AND (session_id=? OR session_id IS NULL)
           ORDER BY CASE WHEN session_id IS NULL THEN 1 ELSE 0 END, id LIMIT 1""",
        (student_id, course_id, semester_no, session_id)).fetchone()


def ensure_enrollment(db, student, course, session_id, semester_no):
    enr = db.execute(
        "SELECT * FROM enrollments WHERE student_id=? AND course_id=?",
        (student["id"], course["id"])).fetchone()
    if enr:
        return enr["id"]
    sess = db.execute("SELECT name FROM academic_sessions WHERE id=?",
                      (session_id,)).fetchone() if session_id else None
    return db.insert(
        "INSERT INTO enrollments (student_id,course_id,session_name,semester_no) VALUES (?,?,?,?)",
        (student["id"], course["id"], sess["name"] if sess else student.get("session_name"),
         semester_no))


def save_result(db, student, course, session_id, semester_no, marks, is_absent, bands):
    """Insert or update one result (marks + derived grade stored as a cache;
    the transcript always re-derives). Returns the result id. Caller commits."""
    grade, gp = grade_for_marks(marks, is_absent, bands)
    remarks = "Absent" if is_absent else ("Pass" if (gp or 0) > 0 else "Fail")
    enr_id = ensure_enrollment(db, student, course, session_id, semester_no)
    existing = find_result(db, student["id"], course["id"], semester_no, session_id)
    if existing:
        db.execute(
            """UPDATE results SET session_id=?, enrollment_id=?, marks_obtained=?,
               is_absent=?, grade=?, grade_point=?, remarks=? WHERE id=?""",
            (session_id, enr_id, marks, 1 if is_absent else 0, grade, gp, remarks,
             existing["id"]))
        return existing["id"]
    return db.insert(
        """INSERT INTO results (student_id,course_id,semester_no,grade,grade_point,remarks,
           session_id,marks_obtained,is_absent,is_published,enrollment_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (student["id"], course["id"], semester_no, grade, gp, remarks,
         session_id, marks, 1 if is_absent else 0, 0, enr_id))


def sheet_students(db, program_id, session_id, course_id, semester_no):
    """Class list for a marks sheet: Active students of program+session, plus
    any student who already has a result for this course set, plus (v0.11)
    any student explicitly enrolled for this course in this session —
    an activated course-repeat enrols the student for the course in the
    target session even though their admission session (and the program
    pattern above) belongs to an earlier session."""
    rows = db.execute(
        """SELECT * FROM students WHERE program_id=? AND session_id=?
           AND COALESCE(status,'Active')='Active'""",
        (program_id, session_id)).fetchall() if program_id and session_id else []
    seen = {s["id"] for s in rows}
    for r in db.execute(
            """SELECT DISTINCT student_id FROM results WHERE course_id=? AND semester_no=?
               AND (session_id=? OR session_id IS NULL)""",
            (course_id, semester_no, session_id)).fetchall():
        if r["student_id"] not in seen:
            s = db.execute("SELECT * FROM students WHERE id=?",
                           (r["student_id"],)).fetchone()
            if s:
                rows.append(s)
                seen.add(s["id"])
    if session_id:
        sess = db.execute("SELECT name FROM academic_sessions WHERE id=?",
                          (session_id,)).fetchone()
        if sess:
            for r in db.execute(
                    """SELECT DISTINCT student_id FROM enrollments
                       WHERE course_id=? AND session_name=?""",
                    (course_id, sess["name"])).fetchall():
                if r["student_id"] not in seen:
                    s = db.execute("SELECT * FROM students WHERE id=?",
                                   (r["student_id"],)).fetchone()
                    if s:
                        rows.append(s)
                        seen.add(s["id"])
    return sorted(rows, key=lambda s: s["name"])


def _parse_marks(raw):
    """-> float marks, or None for blank, or raises ValueError for bad input."""
    raw = (raw or "").strip()
    if raw == "":
        return None
    try:
        marks = float(raw)
    except ValueError:
        raise ValueError(f"'{raw}' is not a number")
    if marks < 0 or marks > 100:
        raise ValueError(f"marks {raw} are outside 0–100")
    return marks


# ---------------------------------------------------------------- grade scale (admin)
@app.route("/admin/grade-scale", methods=["GET", "POST"])
@role_required("admin", "coe")
def admin_grade_scale():
    db = get_db()
    if request.method == "POST":
        ids = request.form.getlist("band_id")
        errors, updates = [], []
        seen_mins = set()
        for bid in ids:
            min_marks = request.form.get(f"min_{bid}", "").strip()
            grade = request.form.get(f"grade_{bid}", "").strip()
            gp = request.form.get(f"gp_{bid}", "").strip()
            try:
                min_f = float(min_marks)
                gp_f = float(gp)
                if not (0 <= min_f <= 100):
                    raise ValueError
                if not (0 <= gp_f <= 5):
                    raise ValueError
            except ValueError:
                errors.append(f"Band #{bid}: min marks must be 0–100 and grade point 0–5.")
                continue
            if not grade:
                errors.append(f"Band #{bid}: grade label is required.")
                continue
            if min_f in seen_mins:
                errors.append(f"Two bands cannot share min marks {min_f:g}.")
                continue
            seen_mins.add(min_f)
            updates.append((min_f, grade, gp_f, _int_or_none(bid)))
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            for min_f, grade, gp_f, bid in updates:
                db.execute("UPDATE grade_bands SET min_marks=?, grade=?, grade_point=? WHERE id=?",
                           (min_f, grade, gp_f, bid))
            db.commit()
            log_audit("grade_scale_updated", "Grading scale bands updated")
            flash("Grading scale updated — grades are derived from it everywhere.", "ok")
            return redirect(url_for("admin_grade_scale"))
    bands = get_grade_bands(db)
    for i, b in enumerate(bands):
        b["max_marks"] = (bands[i - 1]["min_marks"] - 1) if i else 100
    return render_template("grade_scale.html", bands=bands)


@app.route("/admin/grade-scale/add", methods=["POST"])
@role_required("admin", "coe")
def admin_grade_scale_add():
    db = get_db()
    try:
        min_f = float(request.form.get("min_marks", ""))
        gp_f = float(request.form.get("grade_point", ""))
        grade = request.form.get("grade", "").strip()
        if not grade or not (0 <= min_f <= 100) or not (0 <= gp_f <= 5):
            raise ValueError
    except ValueError:
        flash("New band needs min marks 0–100, a grade label, and grade point 0–5.", "error")
        return redirect(url_for("admin_grade_scale"))
    if db.execute("SELECT id FROM grade_bands WHERE min_marks=?", (min_f,)).fetchone():
        flash(f"A band with min marks {min_f:g} already exists.", "error")
        return redirect(url_for("admin_grade_scale"))
    db.insert("INSERT INTO grade_bands (min_marks,grade,grade_point) VALUES (?,?,?)",
              (min_f, grade, gp_f))
    db.commit()
    log_audit("grade_scale_updated", f"Band {grade} (from {min_f:g}) added")
    flash(f"Grade band {grade} (from {min_f:g}) added.", "ok")
    return redirect(url_for("admin_grade_scale"))


@app.route("/admin/grade-scale/<int:band_id>/delete", methods=["POST"])
@role_required("admin", "coe")
def admin_grade_scale_delete(band_id):
    db = get_db()
    band = db.execute("SELECT * FROM grade_bands WHERE id=?", (band_id,)).fetchone()
    if band:
        db.execute("DELETE FROM grade_bands WHERE id=?", (band_id,))
        db.commit()
        log_audit("grade_scale_updated", f"Band '{band['grade']}' deleted")
        flash(f"Grade band '{band['grade']}' deleted.", "ok")
    return redirect(url_for("admin_grade_scale"))


# ---------------------------------------------------------------- results (admin)
def _result_ctx(db):
    """Shared selections for the results screens."""
    course_id = _int_or_none(request.values.get("course_id"))
    program_id = _int_or_none(request.values.get("program_id"))
    session_id = _int_or_none(request.values.get("session_id"))
    semester_no = _int_or_none(request.values.get("semester_no"))
    course = db.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone() if course_id else None
    if course:
        program_id = program_id or course["program_id"]
        semester_no = semester_no or course["semester_no"]
    return course, program_id, session_id, semester_no


@app.route("/admin/results")
@role_required("admin", "coe")
def admin_results():
    db = get_db()
    course, program_id, session_id, semester_no = _result_ctx(db)
    sets = db.execute(
        """SELECT c.id course_id, c.code, c.title, p.name prog_name,
                  r.semester_no, r.session_id, ss.name sess_name,
                  COUNT(*) total,
                  SUM(CASE WHEN COALESCE(r.is_published,0)=1 THEN 1 ELSE 0 END) published
           FROM results r JOIN courses c ON c.id=r.course_id
           LEFT JOIN programs p ON p.id=c.program_id
           LEFT JOIN academic_sessions ss ON ss.id=r.session_id
           GROUP BY c.id, c.code, c.title, p.name, r.semester_no, r.session_id, ss.name
           ORDER BY p.name, r.semester_no, c.code""").fetchall()
    for s in sets:
        s["published"] = int(s["published"] or 0)
        s["state"] = ("Published" if s["published"] == s["total"]
                      else "Unpublished" if s["published"] == 0 else "Partially published")
    if program_id and semester_no:
        courses = db.execute(
            "SELECT * FROM courses WHERE program_id=? AND semester_no=? ORDER BY code",
            (program_id, semester_no)).fetchall()
    elif program_id:
        courses = db.execute(
            "SELECT * FROM courses WHERE program_id=? ORDER BY semester_no, code",
            (program_id,)).fetchall()
    else:
        courses = db.execute("SELECT * FROM courses ORDER BY code").fetchall()
    return render_template(
        "results_home.html", sets=sets, courses=courses,
        programs=program_options(db), sessions=session_options(db),
        course=course, program_id=program_id, session_id=session_id,
        semester_no=semester_no, semesters=list(range(1, 13)))


def _sheet_args(db):
    course, program_id, session_id, semester_no = _result_ctx(db)
    if not course:
        return None
    program_id = course["program_id"]
    semester_no = course["semester_no"]
    if not session_id:
        open_sess = db.execute(
            "SELECT id FROM academic_sessions WHERE is_open=1 ORDER BY id").fetchone()
        session_id = open_sess["id"] if open_sess else (
            session_options(db)[0]["id"] if session_options(db) else None)
    return course, program_id, session_id, semester_no


@app.route("/admin/results/sheet", methods=["GET", "POST"])
@role_required("admin", "coe")
def admin_results_sheet():
    db = get_db()
    ctx = _sheet_args(db)
    if not ctx:
        flash("Choose a course to open its marks sheet.", "error")
        return redirect(url_for("admin_results"))
    course, program_id, session_id, semester_no = ctx
    bands = get_grade_bands(db)
    if request.method == "POST":
        students = sheet_students(db, program_id, session_id, course["id"], semester_no)
        ids = [s["id"] for s in students]
        saved = cleared = 0
        problems = []
        for sid in ids:
            student = next(s for s in students if s["id"] == sid)
            if request.form.get(f"clear_{sid}"):
                old = find_result(db, sid, course["id"], semester_no, session_id)
                if old:
                    db.execute("DELETE FROM results WHERE id=?", (old["id"],))
                    cleared += 1
                continue
            if request.form.get(f"absent_{sid}"):
                save_result(db, student, course, session_id, semester_no, None, True, bands)
                saved += 1
                continue
            raw = request.form.get(f"marks_{sid}", "")
            try:
                marks = _parse_marks(raw)
            except ValueError as e:
                problems.append(f"{student['name']}: {e}")
                continue
            if marks is None:
                continue  # blank = leave unchanged; use the clear box to delete
            save_result(db, student, course, session_id, semester_no, marks, False, bands)
            saved += 1
        db.commit()
        msg = f"Marks sheet saved — {saved} result(s) saved"
        if cleared:
            msg += f", {cleared} cleared"
        msg += "."
        log_audit("results_saved",
                  f"Marks sheet {course['code']} sem {semester_no} — {saved} saved, {cleared} cleared")
        flash(msg, "ok")
        for p in problems:
            flash(p, "error")
        return redirect(url_for("admin_results_sheet", course_id=course["id"],
                                session_id=session_id))
    students = sheet_students(db, program_id, session_id, course["id"], semester_no)
    rows = []
    for s in students:
        res = find_result(db, s["id"], course["id"], semester_no, session_id)
        grade, gp = result_grade_gp(res, bands) if res else (None, None)
        rows.append({"student": s, "result": res, "grade": grade, "gp": gp})
    published = sum(1 for r in rows if r["result"] and r["result"].get("is_published"))
    session_row = db.execute("SELECT * FROM academic_sessions WHERE id=?",
                             (session_id,)).fetchone() if session_id else None
    program = db.execute("SELECT * FROM programs WHERE id=?", (program_id,)).fetchone()
    return render_template(
        "marks_sheet.html", course=course, program=program, session_row=session_row,
        session_id=session_id, semester_no=semester_no, rows=rows,
        published=published, total=len(rows))


@app.route("/admin/results/sheet/publish", methods=["POST"])
@role_required("admin", "coe")
def admin_results_publish():
    db = get_db()
    ctx = _sheet_args(db)
    if not ctx:
        flash("Choose a course first.", "error")
        return redirect(url_for("admin_results"))
    course, program_id, session_id, semester_no = ctx
    publish = 1 if request.form.get("action") == "publish" else 0
    db.execute(
        """UPDATE results SET is_published=? WHERE course_id=? AND semester_no=?
           AND (session_id=? OR session_id IS NULL)""",
        (publish, course["id"], semester_no, session_id))
    db.commit()
    log_audit("results_published" if publish else "results_unpublished",
              f"{course['code']} sem {semester_no}")
    flash(f"Results for {course['code']} are now "
          f"{'PUBLISHED — students can see them' if publish else 'UNPUBLISHED — hidden from students'}.",
          "ok")
    return redirect(url_for("admin_results_sheet", course_id=course["id"],
                            session_id=session_id))


@app.route("/admin/results/sheet.xlsx")
@role_required("admin", "coe")
def admin_results_sheet_xlsx():
    db = get_db()
    ctx = _sheet_args(db)
    if not ctx:
        flash("Choose a course first.", "error")
        return redirect(url_for("admin_results"))
    course, program_id, session_id, semester_no = ctx
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Marks"
    ws.append(["Registration No", "Name", "Marks Obtained", "Absent"])
    for s in sheet_students(db, program_id, session_id, course["id"], semester_no):
        res = find_result(db, s["id"], course["id"], semester_no, session_id)
        marks = "" if not res or res.get("marks_obtained") is None else res["marks_obtained"]
        absent = "Yes" if res and res.get("is_absent") else ""
        ws.append([s["registration_no"], s["name"], marks, absent])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name=f"marks-{course['code']}-sem{semester_no}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


MARKS_ALIASES = {
    "registration_no": ["registrationno", "regno", "registration", "rollno"],
    "marks": ["marksobtained", "marks", "obtainedmarks", "mark", "obtained"],
    "absent": ["absent", "isabsent", "absence"],
}


@app.route("/admin/results/import", methods=["POST"])
@role_required("admin", "coe")
def admin_results_import():
    db = get_db()
    ctx = _sheet_args(db)
    if not ctx:
        flash("Choose a course first.", "error")
        return redirect(url_for("admin_results"))
    course, program_id, session_id, semester_no = ctx
    bands = get_grade_bands(db)
    f = request.files.get("file")
    if not f or not f.filename or not f.filename.lower().endswith(".xlsx"):
        flash("Please choose the marks .xlsx file to import.", "error")
        return redirect(url_for("admin_results_sheet", course_id=course["id"],
                                session_id=session_id))
    from openpyxl import load_workbook
    try:
        wb = load_workbook(f, data_only=True)
    except Exception as e:
        flash(f"Could not read that file as an Excel workbook: {e}", "error")
        return redirect(url_for("admin_results_sheet", course_id=course["id"],
                                session_id=session_id))
    rows = list(wb.active.iter_rows(values_only=True))
    if not rows:
        flash("The file is empty.", "error")
        return redirect(url_for("admin_results_sheet", course_id=course["id"],
                                session_id=session_id))
    norm_to_idx = {}
    for idx, cell in enumerate(rows[0]):
        n = _norm_header(cell)
        if n:
            norm_to_idx[n] = idx
    col = {}
    for field, aliases in MARKS_ALIASES.items():
        for a in aliases:
            if a in norm_to_idx:
                col[field] = norm_to_idx[a]
                break
    if "registration_no" not in col or "marks" not in col:
        flash("Could not find 'Registration No' and 'Marks Obtained' columns — "
              "please use the downloaded marks sheet.", "error")
        return redirect(url_for("admin_results_sheet", course_id=course["id"],
                                session_id=session_id))
    imported, skipped = [], []
    for lineno, raw in enumerate(rows[1:], start=2):
        if raw is None or all(v is None or str(v).strip() == "" for v in raw):
            continue

        def val(field):
            idx = col.get(field)
            return _cell_str(raw[idx]) if idx is not None and idx < len(raw) else ""

        reg = val("registration_no")
        student = db.execute("SELECT * FROM students WHERE registration_no=?",
                             (reg,)).fetchone() if reg else None
        if not student:
            skipped.append((lineno, reg or "—", f"unknown registration no '{reg}'"))
            continue
        absent_txt = val("absent").strip().lower()
        is_absent = absent_txt in ("yes", "y", "1", "true", "absent", "a", "x")
        marks_txt = val("marks")
        if marks_txt.strip().lower() == "absent":
            is_absent, marks_txt = True, ""
        if is_absent:
            save_result(db, student, course, session_id, semester_no, None, True, bands)
            imported.append(reg)
            continue
        try:
            marks = _parse_marks(marks_txt)
        except ValueError as e:
            skipped.append((lineno, reg, str(e)))
            continue
        if marks is None:
            skipped.append((lineno, reg, "no marks given and not marked absent"))
            continue
        save_result(db, student, course, session_id, semester_no, marks, False, bands)
        imported.append(reg)
    db.commit()
    log_audit("results_imported",
              f"Marks import {course['code']} sem {semester_no} — {len(imported)} imported, {len(skipped)} skipped")
    return render_template("results_import_result.html", imported=imported,
                           skipped=skipped, course=course, session_id=session_id)


# ---------------------------------------------------------------- transcript PDF
def student_full(db, student_id):
    return db.execute(
        """SELECT s.*, d.name dept_name, p.name prog_name, ss.name sess_name
           FROM students s LEFT JOIN departments d ON d.id=s.department_id
           LEFT JOIN programs p ON p.id=s.program_id
           LEFT JOIN academic_sessions ss ON ss.id=s.session_id
           WHERE s.id=?""", (student_id,)).fetchone()


def _pdf_header(styles, title_text):
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.units import mm
    return [Paragraph("MY CUVAS — Campus Management System", styles["Title"]),
            Paragraph("Cholistan University of Veterinary and Animal Sciences",
                      styles["Heading3"]),
            Paragraph(title_text, styles["Heading2"]), Spacer(1, 4 * mm)]


def build_transcript_pdf(db, student_id):
    """Official-style transcript PDF bytes, driven by transcript_data()
    (published results only) — the same numbers as the student's web tab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer,
                                    Table, TableStyle)
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    student = student_full(db, student_id)
    transcript, cgpa, _ch = transcript_data(db, student_id, published_only=True)
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=14 * mm, bottomMargin=14 * mm,
                            leftMargin=14 * mm, rightMargin=14 * mm,
                            title=f"Transcript {student['registration_no']}")
    story = _pdf_header(styles, "OFFICIAL TRANSCRIPT (Demo)")
    green = colors.HexColor("#0b6b3a")
    grid = colors.HexColor("#b9d2c2")
    light = colors.HexColor("#eaf5ee")
    info = [["Student Name", student["name"], "Registration No.", student["registration_no"]],
            ["Program", student["prog_name"] or "—", "Department", student["dept_name"] or "—"],
            ["Session", student["sess_name"] or student.get("session_name") or "—",
             "Current Semester", str(student.get("current_semester") or "—")]]
    t = Table(info, colWidths=[30 * mm, 58 * mm, 30 * mm, 64 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, grid),
                           ("BACKGROUND", (0, 0), (0, -1), light),
                           ("BACKGROUND", (2, 0), (2, -1), light),
                           ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [t, Spacer(1, 5 * mm)]
    if not transcript:
        story.append(Paragraph("No published results yet.", styles["BodyText"]))
    for sem in sorted(transcript):
        block = transcript[sem]
        story.append(Paragraph(f"Semester {sem} — SGPA: {block['sgpa']:.2f}",
                               styles["Heading3"]))
        rows = [["Code", "Course Title", "Cr. Hrs", "Marks", "Grade", "Grade Points", "Quality Points"]]
        for r in block["rows"]:
            title = r["title"] + (" (Repeated)" if r.get("superseded") else "")
            rows.append([r["code"], title, str(r["credits"]), r["marks_display"],
                         r["grade"] or "—",
                         f"{r['grade_point']:.2f}" if r["grade_point"] is not None else "—",
                         f"{r['quality_points']:.2f}"])
        rows.append(["", f"Semester SGPA", "", "", "", "", f"{block['sgpa']:.2f}"])
        lt = Table(rows, colWidths=[16 * mm, 74 * mm, 14 * mm, 16 * mm, 14 * mm, 22 * mm, 26 * mm])
        lt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, grid),
                                ("BACKGROUND", (0, 0), (-1, 0), green),
                                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                ("BACKGROUND", (0, -1), (-1, -1), light),
                                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                                ("FONTSIZE", (0, 0), (-1, -1), 8),
                                ("ALIGN", (2, 0), (-1, -1), "CENTER")]))
        story += [lt, Spacer(1, 4 * mm)]
    if any(r.get("superseded") for b in transcript.values() for r in b["rows"]):
        story.append(Paragraph(
            "Note: a course marked (Repeated) is an earlier attempt that was "
            "superseded by a later attempt of the same course — only the "
            "latest attempt counts towards the SGPA/CGPA above.",
            styles["BodyText"]))
        story.append(Spacer(1, 3 * mm))
    story += [Spacer(1, 2 * mm),
              Paragraph(f"<b>Cumulative GPA (CGPA): {cgpa:.2f}</b>", styles["Heading3"]),
              Spacer(1, 6 * mm),
              Paragraph(f"Generated on {_now()} by MY CUVAS (Demo) — system-generated, "
                        f"all data shown is fictional demo data.", styles["BodyText"])]
    doc.build(story)
    buf.seek(0)  # AFTER build() — house lesson
    return buf.getvalue()


@app.route("/student/transcript.pdf")
@role_required("student")
def student_transcript_pdf():
    db = get_db()
    sid = session.get("student_id")
    if not sid:
        abort(404)
    student = student_full(db, sid)
    return send_file(io.BytesIO(build_transcript_pdf(db, sid)), as_attachment=True,
                     download_name=f"transcript-{student['registration_no']}.pdf",
                     mimetype="application/pdf")


@app.route("/admin/students/<int:student_id>/transcript.pdf")
@role_required("admin", "coe")
def admin_student_transcript_pdf(student_id):
    db = get_db()
    student = student_full(db, student_id)
    if not student:
        abort(404)
    return send_file(io.BytesIO(build_transcript_pdf(db, student_id)), as_attachment=True,
                     download_name=f"transcript-{student['registration_no']}.pdf",
                     mimetype="application/pdf")


# ---------------------------------------------------------------- roll number slips
def slip_courses(db, student, semester_no):
    """Courses for a student's slip: enrolments first, then their result
    courses, then the program's plan of study for that semester."""
    rows = db.execute(
        """SELECT c.* FROM enrollments e JOIN courses c ON c.id=e.course_id
           WHERE e.student_id=? AND e.semester_no=? ORDER BY c.code""",
        (student["id"], semester_no)).fetchall()
    if not rows:
        rows = db.execute(
            """SELECT DISTINCT c.* FROM results r JOIN courses c ON c.id=r.course_id
               WHERE r.student_id=? AND r.semester_no=? ORDER BY c.code""",
            (student["id"], semester_no)).fetchall()
    if not rows and student.get("program_id"):
        rows = db.execute(
            "SELECT * FROM courses WHERE program_id=? AND semester_no=? ORDER BY code",
            (student["program_id"], semester_no)).fetchall()
    return rows


def build_slips_pdf(db, student_semesters):
    """Roll number slips — one page per (student, semester_no)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=14 * mm, bottomMargin=14 * mm,
                            leftMargin=14 * mm, rightMargin=14 * mm,
                            title="Roll Number Slips")
    green = colors.HexColor("#0b6b3a")
    grid = colors.HexColor("#b9d2c2")
    story = []
    for i, (student, semester_no) in enumerate(student_semesters):
        if i:
            story.append(PageBreak())
        story += _pdf_header(styles, "ROLL NUMBER SLIP — Semester Examination")
        photo = Table([[Paragraph("<br/><br/>STUDENT<br/>PHOTO", styles["BodyText"])]],
                      colWidths=[30 * mm], rowHeights=[36 * mm])
        photo.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, green),
                                   ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                   ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        info = [["Student Name", student["name"]],
                ["Registration / Roll No.", student["registration_no"]],
                ["Program", student["prog_name"] or "—"],
                ["Department", student["dept_name"] or "—"],
                ["Session", student["sess_name"] or student.get("session_name") or "—"],
                ["Semester", str(semester_no)]]
        it = Table(info, colWidths=[42 * mm, 100 * mm])
        it.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, grid),
                                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eaf5ee")),
                                ("FONTSIZE", (0, 0), (-1, -1), 9),
                                ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        combo = Table([[photo, it]], colWidths=[36 * mm, 146 * mm])
        combo.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                   ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        story += [combo, Spacer(1, 5 * mm)]
        courses = slip_courses(db, student, semester_no)
        rows = [["#", "Course Code", "Course Title", "Credit Hours"]]
        for j, c in enumerate(courses, 1):
            rows.append([str(j), c["code"], c["title"],
                         f"{(c['credit_theory'] or 0)}-{(c['credit_lab'] or 0)}"])
        if not courses:
            rows.append(["", "—", "No courses found for this semester", ""])
        ct = Table(rows, colWidths=[10 * mm, 28 * mm, 104 * mm, 40 * mm])
        ct.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, grid),
                                ("BACKGROUND", (0, 0), (-1, 0), green),
                                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                ("FONTSIZE", (0, 0), (-1, -1), 9)]))
        story += [ct, Spacer(1, 6 * mm),
                  Paragraph("<b>Instructions:</b>", styles["BodyText"]),
                  Paragraph("1. Bring this roll number slip and your student card to every paper.",
                            styles["BodyText"]),
                  Paragraph("2. Reach the examination hall at least 30 minutes before the paper starts.",
                            styles["BodyText"]),
                  Paragraph("3. Mobile phones, smart watches and other electronic devices are not "
                            "allowed inside the examination hall.", styles["BodyText"]),
                  Paragraph("4. Write your roll number on the answer book exactly as shown on this slip.",
                            styles["BodyText"]),
                  Spacer(1, 6 * mm),
                  Paragraph(f"Generated on {_now()} by MY CUVAS (Demo) — system-generated slip, "
                            f"all data shown is fictional demo data.", styles["BodyText"])]
    doc.build(story)
    buf.seek(0)  # AFTER build() — house lesson
    return buf.getvalue()


def _slip_semester_arg(student):
    return _int_or_none(request.args.get("semester_no")) or student.get("current_semester") or 1


@app.route("/student/slip.pdf")
@role_required("student")
def student_slip_pdf():
    db = get_db()
    sid = session.get("student_id")
    student = student_full(db, sid) if sid else None
    if not student:
        abort(404)
    sem = _slip_semester_arg(student)
    return send_file(io.BytesIO(build_slips_pdf(db, [(student, sem)])), as_attachment=True,
                     download_name=f"roll-slip-{student['registration_no']}-sem{sem}.pdf",
                     mimetype="application/pdf")


@app.route("/admin/students/<int:student_id>/slip.pdf")
@role_required("admin", "coe")
def admin_student_slip_pdf(student_id):
    db = get_db()
    student = student_full(db, student_id)
    if not student:
        abort(404)
    sem = _slip_semester_arg(student)
    return send_file(io.BytesIO(build_slips_pdf(db, [(student, sem)])), as_attachment=True,
                     download_name=f"roll-slip-{student['registration_no']}-sem{sem}.pdf",
                     mimetype="application/pdf")


@app.route("/admin/slips.pdf")
@role_required("admin", "coe")
def admin_slips_bulk_pdf():
    db = get_db()
    program_id = _int_or_none(request.args.get("program_id"))
    session_id = _int_or_none(request.args.get("session_id"))
    semester_no = _int_or_none(request.args.get("semester_no")) or 1
    if not program_id or not session_id:
        flash("Choose a program and session to generate bulk roll number slips.", "error")
        return redirect(url_for("admin_results"))
    students = db.execute(
        """SELECT s.*, d.name dept_name, p.name prog_name, ss.name sess_name
           FROM students s LEFT JOIN departments d ON d.id=s.department_id
           LEFT JOIN programs p ON p.id=s.program_id
           LEFT JOIN academic_sessions ss ON ss.id=s.session_id
           WHERE s.program_id=? AND s.session_id=? AND COALESCE(s.status,'Active')='Active'
           ORDER BY s.name""", (program_id, session_id)).fetchall()
    if not students:
        flash("No active students found for that program + session.", "error")
        return redirect(url_for("admin_results"))
    return send_file(io.BytesIO(build_slips_pdf(db, [(s, semester_no) for s in students])),
                     as_attachment=True,
                     download_name=f"roll-slips-sem{semester_no}.pdf",
                     mimetype="application/pdf")


# ================================================================ v0.6 SERVICES
# Student documents, support tickets, notifications admin, document
# repository and the student card PDF. Rules:
#   * uploaded files live ONLY as database blobs (like the v0.3 fee proofs)
#     — never on the filesystem; every file route requires login and checks
#     ownership / role before serving a single byte;
#   * a Verified document is locked for the student (no replace / delete);
#   * notifications (the v0.1 table, extended in v0.6) are the single source
#     for the landing page and the student News Feed — published items with
#     audience All/Students only;
#   * students only ever see PUBLISHED repository documents.

DOC_TYPES = ["CNIC Front", "CNIC Back", "Matric Certificate",
             "Intermediate Certificate", "Domicile", "Passport Photo", "Other"]
DOC_STATUSES = ["Pending", "Verified", "Rejected"]
TICKET_CATEGORIES = ["Fee", "Result", "Admission", "IT / Login", "Hostel", "Other"]
TICKET_STATUSES = ["Open", "In Process", "Resolved", "Closed"]
NOTIF_AUDIENCES = ["All", "Students", "Admins"]
REPO_CATEGORIES = ["Circular", "Notification", "Policy", "Form", "Other"]
UPLOAD_EXTS = {"pdf", "png", "jpg", "jpeg", "gif", "webp"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # ~5 MB per uploaded file


def _read_upload(f):
    """Validate an uploaded file (images + PDF, <= ~5 MB).
    Returns (blob, error_message) — exactly one of them is None."""
    if not f or not f.filename:
        return None, "Please choose a file first."
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in UPLOAD_EXTS:
        return None, "Only images (PNG / JPG / GIF / WEBP) or PDF files are allowed."
    blob = f.read()
    if not blob:
        return None, "That file is empty."
    if len(blob) > MAX_UPLOAD_BYTES:
        return None, "That file is too large — the limit is 5 MB."
    return blob, None


def _serve_blob(row, data_key="file_data"):
    return send_file(io.BytesIO(bytes(row[data_key])), as_attachment=True,
                     download_name=row.get("file_name") or "download",
                     mimetype=row.get("file_mime") or "application/octet-stream")


# ------------------------------------------------------- student documents
def _own_document_or_none(db, doc_id):
    doc = db.execute("SELECT * FROM student_documents WHERE id=?", (doc_id,)).fetchone()
    if not doc or doc["student_id"] != session.get("student_id"):
        return None
    return doc


@app.route("/student/documents")
@role_required("student")
def student_documents():
    """v0.16 alias: My Documents lives in the dashboard's documents
    pane — the sidebar / bookmark URL resolves to it."""
    return redirect(url_for("student_dashboard", tab="documents"))


@app.route("/student/documents/upload", methods=["POST"])
@role_required("student")
def student_document_upload():
    db = get_db()
    sid = session.get("student_id")
    doc_type = request.form.get("doc_type", "").strip()
    if doc_type not in DOC_TYPES:
        flash("Please choose a valid document type.", "error")
        return redirect(url_for("student_dashboard", tab="documents"))
    existing = db.execute(
        "SELECT * FROM student_documents WHERE student_id=? AND doc_type=?",
        (sid, doc_type)).fetchone()
    if existing and existing["status"] == "Verified":
        flash(f"Your {doc_type} is Verified and locked — it cannot be replaced.", "error")
        return redirect(url_for("student_dashboard", tab="documents"))
    f = request.files.get("file")
    blob, err = _read_upload(f)
    if err:
        flash(err, "error")
        return redirect(url_for("student_dashboard", tab="documents"))
    mime = f.mimetype or "application/octet-stream"
    if existing:  # replace a Pending / Rejected document: back to Pending
        db.execute(
            """UPDATE student_documents SET file_name=?, file_mime=?, file_data=?,
               status='Pending', admin_remarks=NULL, uploaded_at=?,
               reviewed_at=NULL, reviewed_by=NULL WHERE id=?""",
            (f.filename, mime, blob, _now(), existing["id"]))
        flash(f"{doc_type} re-uploaded — it is Pending verification again.", "ok")
    else:
        db.insert(
            """INSERT INTO student_documents (student_id,doc_type,file_name,file_mime,
               file_data,status,uploaded_at) VALUES (?,?,?,?,?, 'Pending', ?)""",
            (sid, doc_type, f.filename, mime, blob, _now()))
        flash(f"{doc_type} uploaded — it will appear after admin verification.", "ok")
    db.commit()
    log_audit("document_uploaded", f"{doc_type} — {f.filename}")
    return redirect(url_for("student_dashboard", tab="documents"))


@app.route("/student/documents/<int:doc_id>/download")
@role_required("student")
def student_document_download(doc_id):
    doc = _own_document_or_none(get_db(), doc_id)
    if not doc:
        abort(404)
    return _serve_blob(doc)


@app.route("/student/documents/<int:doc_id>/delete", methods=["POST"])
@role_required("student")
def student_document_delete(doc_id):
    db = get_db()
    doc = _own_document_or_none(db, doc_id)
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for("student_dashboard", tab="documents"))
    if doc["status"] == "Verified":
        flash("A Verified document is locked and cannot be deleted.", "error")
        return redirect(url_for("student_dashboard", tab="documents"))
    db.execute("DELETE FROM student_documents WHERE id=?", (doc_id,))
    db.commit()
    flash(f"{doc['doc_type']} deleted.", "ok")
    return redirect(url_for("student_dashboard", tab="documents"))


# --------------------------------------------------------- admin documents
@app.route("/admin/documents")
@role_required("admin")
def admin_documents():
    db = get_db()
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()
    sql = """SELECT d.*, s.name student_name, s.registration_no
             FROM student_documents d JOIN students s ON s.id=d.student_id WHERE 1=1"""
    params = []
    if status in DOC_STATUSES:
        sql += " AND d.status=?"
        params.append(status)
    if q:
        sql += f" AND (s.name {LIKE} ? OR s.registration_no {LIKE} ?)"
        params += [f"%{q}%", f"%{q}%"]
    # Pending first by default, then newest
    sql += """ ORDER BY CASE WHEN d.status='Pending' THEN 0
                             WHEN d.status='Rejected' THEN 1 ELSE 2 END,
                      d.uploaded_at DESC, d.id DESC"""
    rows = db.execute(sql, params).fetchall()
    counts = {r["status"]: r["c"] for r in db.execute(
        "SELECT status, COUNT(*) c FROM student_documents GROUP BY status").fetchall()}
    return render_template("admin_documents.html", rows=rows, counts=counts,
                           doc_statuses=DOC_STATUSES, args=request.args)


@app.route("/admin/documents/<int:doc_id>/download")
@role_required("admin")
def admin_document_download(doc_id):
    doc = get_db().execute(
        "SELECT * FROM student_documents WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        abort(404)
    return _serve_blob(doc)


@app.route("/admin/documents/<int:doc_id>/verify", methods=["POST"])
@role_required("admin")
def admin_document_verify(doc_id):
    db = get_db()
    doc = db.execute("SELECT * FROM student_documents WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for("admin_documents"))
    remarks = request.form.get("remarks", "").strip()
    db.execute(
        "UPDATE student_documents SET status='Verified', admin_remarks=?, "
        "reviewed_at=?, reviewed_by=? WHERE id=?",
        (remarks or doc.get("admin_remarks"), _now(),
         session.get("display_name"), doc_id))
    db.commit()
    log_audit("document_verified",
                f"{doc['doc_type']} — {doc['file_name']}")
    flash(f"{doc['doc_type']} for {doc['file_name']} marked Verified.", "ok")
    return redirect(url_for("admin_documents"))


@app.route("/admin/documents/<int:doc_id>/reject", methods=["POST"])
@role_required("admin")
def admin_document_reject(doc_id):
    db = get_db()
    doc = db.execute("SELECT * FROM student_documents WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for("admin_documents"))
    remarks = request.form.get("remarks", "").strip() or \
        "Document rejected — please upload a clear, readable copy."
    db.execute(
        "UPDATE student_documents SET status='Rejected', admin_remarks=?, "
        "reviewed_at=?, reviewed_by=? WHERE id=?",
        (remarks, _now(), session.get("display_name"), doc_id))
    db.commit()
    log_audit("document_rejected",
                f"{doc['doc_type']} — {doc['file_name']}")
    flash(f"{doc['doc_type']} rejected — the student can re-upload it.", "ok")
    return redirect(url_for("admin_documents"))


# --------------------------------------------------------- support tickets
def _ticket_full(db, ticket_id):
    return db.execute(
        """SELECT t.*, s.name student_name, s.registration_no
           FROM tickets t JOIN students s ON s.id=t.student_id WHERE t.id=?""",
        (ticket_id,)).fetchone()


def _ticket_messages(db, ticket_id):
    return db.execute(
        "SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY id",
        (ticket_id,)).fetchall()


def _add_ticket_message(db, ticket, role, name, body):
    db.insert(
        "INSERT INTO ticket_messages (ticket_id,sender_role,sender_name,body,created_at) "
        "VALUES (?,?,?,?,?)", (ticket["id"], role, name, body, _now()))
    db.execute("UPDATE tickets SET updated_at=? WHERE id=?", (_now(), ticket["id"]))


@app.route("/student/tickets")
@role_required("student")
def student_tickets():
    """v0.16 alias: Support Tickets lives in the dashboard's tickets
    pane — the sidebar / bookmark URL resolves to it."""
    return redirect(url_for("student_dashboard", tab="tickets"))


@app.route("/student/tickets/new", methods=["POST"])
@role_required("student")
def student_ticket_new():
    db = get_db()
    sid = session.get("student_id")
    category = request.form.get("category", "").strip()
    subject = request.form.get("subject", "").strip()
    body = request.form.get("message", "").strip()
    if category not in TICKET_CATEGORIES:
        flash("Please choose a valid ticket category.", "error")
        return redirect(url_for("student_dashboard", tab="tickets"))
    if not subject or not body:
        flash("Ticket subject and message are required.", "error")
        return redirect(url_for("student_dashboard", tab="tickets"))
    student = db.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    tid = db.insert(
        "INSERT INTO tickets (student_id,category,subject,status,created_at,updated_at) "
        "VALUES (?,?,?,'Open',?,?)", (sid, category, subject, _now(), _now()))
    db.insert(
        "INSERT INTO ticket_messages (ticket_id,sender_role,sender_name,body,created_at) "
        "VALUES (?, 'student', ?, ?, ?)",
        (tid, student["name"] if student else session.get("display_name"), body, _now()))
    db.commit()
    log_audit("ticket_created", f"Ticket #{tid} — {subject}")
    flash(f"Ticket #{tid} created — the admin office will reply here.", "ok")
    return redirect(url_for("student_ticket_thread", ticket_id=tid))


@app.route("/student/tickets/<int:ticket_id>")
@role_required("student")
def student_ticket_thread(ticket_id):
    db = get_db()
    ticket = _ticket_full(db, ticket_id)
    if not ticket or ticket["student_id"] != session.get("student_id"):
        abort(404)
    return render_template("student_ticket.html", ticket=ticket,
                           messages=_ticket_messages(db, ticket_id))


@app.route("/student/tickets/<int:ticket_id>/reply", methods=["POST"])
@role_required("student")
def student_ticket_reply(ticket_id):
    db = get_db()
    ticket = _ticket_full(db, ticket_id)
    if not ticket or ticket["student_id"] != session.get("student_id"):
        abort(404)
    if ticket["status"] == "Closed":
        flash("This ticket is Closed — replies are no longer accepted. "
              "Please open a new ticket if you still need help.", "error")
        return redirect(url_for("student_ticket_thread", ticket_id=ticket_id))
    body = request.form.get("message", "").strip()
    if not body:
        flash("Please write a message first.", "error")
        return redirect(url_for("student_ticket_thread", ticket_id=ticket_id))
    _add_ticket_message(db, ticket, "student", ticket["student_name"], body)
    db.commit()
    flash("Reply posted.", "ok")
    return redirect(url_for("student_ticket_thread", ticket_id=ticket_id))


@app.route("/student/tickets/<int:ticket_id>/close", methods=["POST"])
@role_required("student")
def student_ticket_close(ticket_id):
    db = get_db()
    ticket = _ticket_full(db, ticket_id)
    if not ticket or ticket["student_id"] != session.get("student_id"):
        abort(404)
    if ticket["status"] != "Resolved":
        flash("Only a Resolved ticket can be closed.", "error")
        return redirect(url_for("student_ticket_thread", ticket_id=ticket_id))
    db.execute("UPDATE tickets SET status='Closed', updated_at=? WHERE id=?",
               (_now(), ticket_id))
    db.commit()
    flash(f"Ticket #{ticket_id} closed. Thank you!", "ok")
    return redirect(url_for("student_dashboard", tab="tickets"))


@app.route("/admin/tickets")
@role_required("admin")
def admin_tickets():
    db = get_db()
    status = request.args.get("status", "")
    category = request.args.get("category", "")
    sql = """SELECT t.*, s.name student_name, s.registration_no
             FROM tickets t JOIN students s ON s.id=t.student_id WHERE 1=1"""
    params = []
    if status in TICKET_STATUSES:
        sql += " AND t.status=?"
        params.append(status)
    if category in TICKET_CATEGORIES:
        sql += " AND t.category=?"
        params.append(category)
    sql += " ORDER BY t.updated_at DESC, t.id DESC"
    rows = db.execute(sql, params).fetchall()
    counts = {r["status"]: r["c"] for r in db.execute(
        "SELECT status, COUNT(*) c FROM tickets GROUP BY status").fetchall()}
    return render_template("admin_tickets.html", rows=rows, counts=counts,
                           ticket_statuses=TICKET_STATUSES,
                           ticket_categories=TICKET_CATEGORIES, args=request.args)


@app.route("/admin/tickets/<int:ticket_id>")
@role_required("admin")
def admin_ticket_thread(ticket_id):
    db = get_db()
    ticket = _ticket_full(db, ticket_id)
    if not ticket:
        abort(404)
    return render_template("admin_ticket.html", ticket=ticket,
                           messages=_ticket_messages(db, ticket_id),
                           ticket_statuses=TICKET_STATUSES)


@app.route("/admin/tickets/<int:ticket_id>/reply", methods=["POST"])
@role_required("admin")
def admin_ticket_reply(ticket_id):
    db = get_db()
    ticket = _ticket_full(db, ticket_id)
    if not ticket:
        abort(404)
    body = request.form.get("message", "").strip()
    if not body:
        flash("Please write a reply first.", "error")
        return redirect(url_for("admin_ticket_thread", ticket_id=ticket_id))
    _add_ticket_message(db, ticket, "admin",
                        session.get("display_name") or "Admin", body)
    db.commit()
    flash("Reply posted — the student can see it in their Support Tickets tab.", "ok")
    return redirect(url_for("admin_ticket_thread", ticket_id=ticket_id))


@app.route("/admin/tickets/<int:ticket_id>/status", methods=["POST"])
@role_required("admin")
def admin_ticket_status(ticket_id):
    db = get_db()
    ticket = _ticket_full(db, ticket_id)
    if not ticket:
        abort(404)
    status = request.form.get("status", "").strip()
    if status not in TICKET_STATUSES:
        flash("Invalid ticket status.", "error")
        return redirect(url_for("admin_ticket_thread", ticket_id=ticket_id))
    db.execute("UPDATE tickets SET status=?, updated_at=? WHERE id=?",
               (status, _now(), ticket_id))
    db.commit()
    flash(f"Ticket #{ticket_id} is now {status}.", "ok")
    return redirect(url_for("admin_ticket_thread", ticket_id=ticket_id))


# ------------------------------------------------------ notifications admin
@app.route("/admin/notifications")
@role_required("admin")
def admin_notifications():
    rows = get_db().execute(
        "SELECT * FROM notifications ORDER BY id DESC").fetchall()
    return render_template("admin_notifications.html", rows=rows)


def _notification_form_values(form):
    return (form.get("title", "").strip(), form.get("body", "").strip(),
            form.get("audience", "All").strip(),
            1 if form.get("is_published") else 0)


@app.route("/admin/notifications/new", methods=["GET", "POST"])
@role_required("admin")
def admin_notification_new():
    db = get_db()
    if request.method == "POST":
        title, body, audience, published = _notification_form_values(request.form)
        if audience not in NOTIF_AUDIENCES:
            audience = "All"
        if not title or not body:
            flash("Notification title and body are required.", "error")
        else:
            db.insert(
                """INSERT INTO notifications (title,body,published_at,audience,
                   is_published,created_by,created_at) VALUES (?,?,?,?,?,?,?)""",
                (title, body, _today(), audience, published,
                 session.get("display_name"), _now()))
            db.commit()
            log_audit("notification_published" if published else "notification_created",
                      f"Notification '{title}'")
            flash(f"Notification '{title}' saved.", "ok")
            return redirect(url_for("admin_notifications"))
    return render_template("notification_form.html", notif=None,
                           audiences=NOTIF_AUDIENCES)


@app.route("/admin/notifications/<int:notif_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def admin_notification_edit(notif_id):
    db = get_db()
    notif = db.execute("SELECT * FROM notifications WHERE id=?", (notif_id,)).fetchone()
    if not notif:
        flash("Notification not found.", "error")
        return redirect(url_for("admin_notifications"))
    if request.method == "POST":
        title, body, audience, published = _notification_form_values(request.form)
        if audience not in NOTIF_AUDIENCES:
            audience = "All"
        if not title or not body:
            flash("Notification title and body are required.", "error")
        else:
            db.execute(
                """UPDATE notifications SET title=?, body=?, audience=?, is_published=?,
                   published_at=? WHERE id=?""",
                (title, body, audience, published,
                 _today() if published else notif.get("published_at"), notif_id))
            db.commit()
            log_audit("notification_updated", f"Notification '{title}'")
            flash(f"Notification '{title}' updated.", "ok")
            return redirect(url_for("admin_notifications"))
    return render_template("notification_form.html", notif=notif,
                           audiences=NOTIF_AUDIENCES)


@app.route("/admin/notifications/<int:notif_id>/toggle", methods=["POST"])
@role_required("admin")
def admin_notification_toggle(notif_id):
    db = get_db()
    notif = db.execute("SELECT * FROM notifications WHERE id=?", (notif_id,)).fetchone()
    if not notif:
        flash("Notification not found.", "error")
        return redirect(url_for("admin_notifications"))
    new_state = 0 if notif.get("is_published") else 1
    db.execute(
        "UPDATE notifications SET is_published=?, published_at=? WHERE id=?",
        (new_state, _today() if new_state else notif.get("published_at"), notif_id))
    db.commit()
    log_audit("notification_published" if new_state else "notification_unpublished",
              f"Notification '{notif['title']}'")
    flash(f"Notification '{notif['title']}' is now "
          f"{'Published' if new_state else 'Unpublished'}.", "ok")
    return redirect(url_for("admin_notifications"))


@app.route("/admin/notifications/<int:notif_id>/delete", methods=["POST"])
@role_required("admin")
def admin_notification_delete(notif_id):
    db = get_db()
    notif = db.execute("SELECT * FROM notifications WHERE id=?", (notif_id,)).fetchone()
    if not notif:
        flash("Notification not found.", "error")
        return redirect(url_for("admin_notifications"))
    db.execute("DELETE FROM notifications WHERE id=?", (notif_id,))
    db.commit()
    log_audit("notification_deleted", f"Notification '{notif['title']}'")
    flash(f"Notification '{notif['title']}' deleted.", "ok")
    return redirect(url_for("admin_notifications"))


# ------------------------------------------------------- document repository
@app.route("/admin/repository")
@role_required("admin")
def admin_repository():
    rows = get_db().execute(
        "SELECT id,title,category,description,file_name,file_mime,uploaded_by,"
        "created_at,is_published FROM repository_docs ORDER BY id DESC").fetchall()
    return render_template("admin_repository.html", rows=rows,
                           repo_categories=REPO_CATEGORIES)


@app.route("/admin/repository/upload", methods=["POST"])
@role_required("admin")
def admin_repository_upload():
    db = get_db()
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    if category not in REPO_CATEGORIES:
        category = "Other"
    if not title:
        flash("A title is required for the repository document.", "error")
        return redirect(url_for("admin_repository"))
    f = request.files.get("file")
    blob, err = _read_upload(f)
    if err:
        flash(err, "error")
        return redirect(url_for("admin_repository"))
    db.insert(
        """INSERT INTO repository_docs (title,category,description,file_name,
           file_mime,file_data,uploaded_by,created_at,is_published)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (title, category, description, f.filename,
         f.mimetype or "application/octet-stream", blob,
         session.get("display_name"), _now(),
         1 if request.form.get("is_published") else 0))
    db.commit()
    log_audit("repository_published" if request.form.get("is_published") else "repository_uploaded",
                f"Repository document '{title}'")
    flash(f"Repository document '{title}' uploaded.", "ok")
    return redirect(url_for("admin_repository"))


@app.route("/admin/repository/<int:doc_id>/toggle", methods=["POST"])
@role_required("admin")
def admin_repository_toggle(doc_id):
    db = get_db()
    doc = db.execute("SELECT * FROM repository_docs WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        flash("Repository document not found.", "error")
        return redirect(url_for("admin_repository"))
    new_state = 0 if doc.get("is_published") else 1
    db.execute("UPDATE repository_docs SET is_published=? WHERE id=?",
               (new_state, doc_id))
    db.commit()
    log_audit("repository_published" if new_state else "repository_unpublished",
                f"Repository document '{doc['title']}'")
    flash(f"'{doc['title']}' is now {'Published' if new_state else 'Unpublished'}.", "ok")
    return redirect(url_for("admin_repository"))


@app.route("/admin/repository/<int:doc_id>/delete", methods=["POST"])
@role_required("admin")
def admin_repository_delete(doc_id):
    db = get_db()
    doc = db.execute("SELECT id,title FROM repository_docs WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        flash("Repository document not found.", "error")
        return redirect(url_for("admin_repository"))
    db.execute("DELETE FROM repository_docs WHERE id=?", (doc_id,))
    db.commit()
    flash(f"Repository document '{doc['title']}' deleted.", "ok")
    return redirect(url_for("admin_repository"))


@app.route("/admin/repository/<int:doc_id>/download")
@role_required("admin")
def admin_repository_download(doc_id):
    doc = get_db().execute(
        "SELECT * FROM repository_docs WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        abort(404)
    return _serve_blob(doc)


@app.route("/student/repository/<int:doc_id>/download")
@role_required("student")
def student_repository_download(doc_id):
    doc = get_db().execute(
        "SELECT * FROM repository_docs WHERE id=?", (doc_id,)).fetchone()
    if not doc or not doc.get("is_published"):
        abort(404)
    return _serve_blob(doc)


# ================================================================ v0.7 FACULTY PORTAL
# A teacher sees ONLY their own course assignments. Marks entry writes into
# the same results store as the admin sheet (save_result / find_result /
# sheet_students), but faculty can never publish — and once the admin has
# published a set, the faculty sheet for it is locked read-only.

def _current_faculty(db):
    fid = session.get("faculty_id")
    if not fid:
        return None
    return db.execute(
        """SELECT f.*, d.name dept_name FROM faculty f
           LEFT JOIN departments d ON d.id=f.department_id WHERE f.id=?""",
        (fid,)).fetchone()


def _own_assignment_or_none(db, assignment_id):
    """The assignment row (with course/program/session context) ONLY when it
    belongs to the logged-in teacher — every faculty course route goes
    through this, so another teacher's assignment id is simply not found."""
    return db.execute(
        """SELECT a.*, c.code course_code, c.title course_title,
                  c.semester_no, c.program_id, p.name prog_name,
                  ss.name sess_name
           FROM course_assignments a
           JOIN courses c ON c.id=a.course_id
           LEFT JOIN programs p ON p.id=c.program_id
           LEFT JOIN academic_sessions ss ON ss.id=a.session_id
           WHERE a.id=? AND a.faculty_id=?""",
        (assignment_id, session.get("faculty_id"))).fetchone()


def _result_set_state(db, course_id, semester_no, session_id):
    """Publish state of one result set, exactly as the admin sheet sees it."""
    rows = db.execute(
        """SELECT COALESCE(is_published,0) pub FROM results
           WHERE course_id=? AND semester_no=?
             AND (session_id=? OR session_id IS NULL)""",
        (course_id, semester_no, session_id)).fetchall()
    total = len(rows)
    published = sum(1 for r in rows if r["pub"])
    if total == 0:
        state = "No marks entered"
    elif published == total:
        state = "Published"
    elif published == 0:
        state = "Unpublished"
    else:
        state = "Partially published"
    return state, published, total


@app.route("/faculty")
@role_required("faculty")
def faculty_dashboard():
    db = get_db()
    fac = _current_faculty(db)
    if not fac:
        flash("No faculty record is linked to this login.", "error")
        return redirect(url_for("logout"))
    groups, by_session = [], {}
    for a in _faculty_assignments(db, fac["id"]):
        a = dict(a)
        a["student_count"] = len(sheet_students(
            db, a["program_id"], a["session_id"], a["course_id"], a["semester_no"]))
        a["result_state"], _, _ = _result_set_state(
            db, a["course_id"], a["semester_no"], a["session_id"])
        key = a["session_id"]
        if key not in by_session:
            by_session[key] = {"session_name": a["sess_name"], "courses": []}
            groups.append(by_session[key])
        by_session[key]["courses"].append(a)
    return render_template("faculty_dashboard.html", faculty=fac, groups=groups)


@app.route("/faculty/course/<int:assignment_id>/students")
@role_required("faculty")
def faculty_course_students(assignment_id):
    db = get_db()
    a = _own_assignment_or_none(db, assignment_id)
    if not a:
        abort(404)
    roster = sheet_students(db, a["program_id"], a["session_id"],
                            a["course_id"], a["semester_no"])
    return render_template("faculty_students.html", a=a, roster=roster)


@app.route("/faculty/course/<int:assignment_id>/students.xlsx")
@role_required("faculty")
def faculty_course_students_xlsx(assignment_id):
    db = get_db()
    a = _own_assignment_or_none(db, assignment_id)
    if not a:
        abort(404)
    roster = sheet_students(db, a["program_id"], a["session_id"],
                            a["course_id"], a["semester_no"])
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Class List"
    ws.append(["Reg No", "Name", "Signature"])
    for s in roster:
        ws.append([s["registration_no"], s["name"], ""])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name=f"class-list-{a['course_code']}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/faculty/course/<int:assignment_id>/marks", methods=["GET", "POST"])
@role_required("faculty")
def faculty_course_marks(assignment_id):
    db = get_db()
    a = _own_assignment_or_none(db, assignment_id)
    if not a:
        abort(404)
    course = db.execute("SELECT * FROM courses WHERE id=?", (a["course_id"],)).fetchone()
    bands = get_grade_bands(db)
    state, published_n, total_n = _result_set_state(
        db, a["course_id"], a["semester_no"], a["session_id"])
    locked = total_n > 0 and published_n == total_n
    if request.method == "POST":
        if locked:
            flash("These results have been PUBLISHED by the admin — marks are "
                  "locked and can no longer be edited here.", "error")
            return redirect(url_for("faculty_course_marks",
                                    assignment_id=assignment_id))
        students = sheet_students(db, a["program_id"], a["session_id"],
                                  a["course_id"], a["semester_no"])
        saved, problems = 0, []
        for student in students:
            sid = student["id"]
            existing = find_result(db, sid, a["course_id"],
                                   a["semester_no"], a["session_id"])
            if existing and existing.get("is_published"):
                continue  # a published row is never faculty-editable
            if request.form.get(f"absent_{sid}"):
                save_result(db, student, course, a["session_id"],
                            a["semester_no"], None, True, bands)
                saved += 1
                continue
            raw = request.form.get(f"marks_{sid}", "")
            try:
                marks = _parse_marks(raw)
            except ValueError as e:
                problems.append(f"{student['name']}: {e}")
                continue
            if marks is None:
                continue  # blank = leave unchanged, exactly like the admin sheet
            save_result(db, student, course, a["session_id"],
                        a["semester_no"], marks, False, bands)
            saved += 1
        db.commit()
        log_audit("results_saved",
                  f"Faculty marks {course['code']} sem {a['semester_no']} — {saved} saved")
        flash(f"Marks saved — {saved} result(s) recorded. They stay "
              f"UNPUBLISHED (hidden from students) until the admin publishes them.", "ok")
        for p in problems:
            flash(p, "error")
        return redirect(url_for("faculty_course_marks",
                                assignment_id=assignment_id))
    students = sheet_students(db, a["program_id"], a["session_id"],
                              a["course_id"], a["semester_no"])
    rows = []
    for s in students:
        res = find_result(db, s["id"], a["course_id"],
                          a["semester_no"], a["session_id"])
        grade, gp = result_grade_gp(res, bands) if res else (None, None)
        rows.append({"student": s, "result": res, "grade": grade, "gp": gp})
    return render_template("faculty_marks.html", a=a, rows=rows,
                           state=state, locked=locked)


# ================================================================ v0.8 ATTENDANCE
# Faculty mark one sheet per class date for THEIR OWN assignments (every
# route resolves through _own_assignment_or_none, so another teacher's
# assignment is a 404 on GET and POST alike). Saving upserts per
# (assignment, student, date) — re-saving a date edits it in place and can
# never duplicate a row. Future dates are rejected with no writes.
# attendance_summary() below is the ONE computation behind the faculty
# summary, the read-only admin overview and the student's own page:
#   classes_held = distinct class_dates recorded for the assignment
#   percentage   = round(present / classes_held * 100, 1)
# Late / Leave do NOT count as present; the P/A/L/Leave counts are always
# displayed next to the percentage so the definition stays transparent.

ATTENDANCE_STATUSES = ["Present", "Absent", "Late", "Leave"]


def attendance_summary(db, assignment_id):
    """-> {'classes_held': int, 'dates': [iso-date, ...],
          'by_student': {student_id: {present, absent, late, leave,
                                      total, pct}}}"""
    dates = [r["class_date"] for r in db.execute(
        """SELECT DISTINCT class_date FROM attendance
           WHERE assignment_id=? ORDER BY class_date""",
        (assignment_id,)).fetchall()]
    classes_held = len(dates)
    by_student = {}
    for r in db.execute(
            """SELECT student_id, status, COUNT(*) n FROM attendance
               WHERE assignment_id=? GROUP BY student_id, status""",
            (assignment_id,)).fetchall():
        d = by_student.setdefault(
            r["student_id"], {"present": 0, "absent": 0, "late": 0,
                              "leave": 0, "total": 0, "pct": 0.0})
        key = (r["status"] or "").lower()
        if key in ("present", "absent", "late", "leave"):
            d[key] += r["n"]
        d["total"] += r["n"]
    for d in by_student.values():
        d["pct"] = (round(d["present"] / classes_held * 100, 1)
                    if classes_held else 0.0)
    return {"classes_held": classes_held, "dates": dates,
            "by_student": by_student}


def _attendance_summary_rows(db, a):
    """(classes_held, rows) for an assignment row `a` (with program_id):
    the sheet_students cohort, in roster order, joined with the shared
    summary counts — students never marked yet count zeroes."""
    summ = attendance_summary(db, a["id"])
    rows = []
    for s in sheet_students(db, a["program_id"], a["session_id"],
                            a["course_id"], a["semester_no"]):
        d = summ["by_student"].get(
            s["id"], {"present": 0, "absent": 0, "late": 0, "leave": 0,
                      "total": 0, "pct": 0.0})
        rows.append({"student": s, **d})
    return summ["classes_held"], rows


def _marked_dates(db, assignment_id):
    """Marked dates for one assignment, newest first, with status counts."""
    return db.execute(
        """SELECT class_date,
                  SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) p,
                  SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) ab,
                  SUM(CASE WHEN status='Late' THEN 1 ELSE 0 END) lt,
                  SUM(CASE WHEN status='Leave' THEN 1 ELSE 0 END) lv,
                  COUNT(*) total
           FROM attendance WHERE assignment_id=?
           GROUP BY class_date ORDER BY class_date DESC""",
        (assignment_id,)).fetchall()


def _clean_class_date(raw):
    """-> the ISO date string when `raw` is exactly YYYY-MM-DD, else None."""
    raw = (raw or "").strip()
    try:
        parsed = datetime.date.fromisoformat(raw)
    except ValueError:
        return None
    return raw if parsed.isoformat() == raw else None


@app.route("/faculty/course/<int:assignment_id>/attendance")
@role_required("faculty")
def faculty_attendance(assignment_id):
    db = get_db()
    a = _own_assignment_or_none(db, assignment_id)
    if not a:
        abort(404)
    return render_template("faculty_attendance.html", a=a,
                           dates=_marked_dates(db, assignment_id),
                           today=_today())


@app.route("/faculty/course/<int:assignment_id>/attendance/mark",
           methods=["GET", "POST"])
@role_required("faculty")
def faculty_attendance_mark(assignment_id):
    db = get_db()
    a = _own_assignment_or_none(db, assignment_id)
    if not a:
        abort(404)
    class_date = _clean_class_date(request.values.get("date"))
    if class_date is None:
        flash("Pick a valid class date (YYYY-MM-DD) to mark attendance.",
              "error")
        return redirect(url_for("faculty_attendance",
                                assignment_id=assignment_id))
    if class_date > _today():
        flash(f"Attendance for {class_date} cannot be marked — that date "
              f"is in the future.", "error")
        return redirect(url_for("faculty_attendance",
                                assignment_id=assignment_id))
    students = sheet_students(db, a["program_id"], a["session_id"],
                              a["course_id"], a["semester_no"])
    if request.method == "POST":
        now, fid = _now(), session.get("faculty_id")
        saved = 0
        for s in students:
            status = request.form.get(f"status_{s['id']}", "Present")
            if status not in ATTENDANCE_STATUSES:
                status = "Present"
            existing = db.execute(
                """SELECT id FROM attendance WHERE assignment_id=?
                   AND student_id=? AND class_date=?""",
                (assignment_id, s["id"], class_date)).fetchone()
            if existing:
                db.execute(
                    """UPDATE attendance SET status=?,
                       marked_by_faculty_id=?, updated_at=? WHERE id=?""",
                    (status, fid, now, existing["id"]))
            else:
                db.insert(
                    """INSERT INTO attendance (assignment_id, student_id,
                       class_date, status, marked_by_faculty_id,
                       created_at, updated_at) VALUES (?,?,?,?,?,?,?)""",
                    (assignment_id, s["id"], class_date, status, fid,
                     now, now))
            saved += 1
        db.commit()
        flash(f"Attendance for {class_date} saved — {saved} student(s) "
              f"recorded.", "ok")
        return redirect(url_for("faculty_attendance",
                                assignment_id=assignment_id))
    marks = {r["student_id"]: r["status"] for r in db.execute(
        "SELECT student_id, status FROM attendance "
        "WHERE assignment_id=? AND class_date=?",
        (assignment_id, class_date)).fetchall()}
    return render_template("faculty_attendance_mark.html", a=a,
                           students=students, class_date=class_date,
                           marks=marks, statuses=ATTENDANCE_STATUSES)


@app.route("/faculty/course/<int:assignment_id>/attendance/delete",
           methods=["POST"])
@role_required("faculty")
def faculty_attendance_delete(assignment_id):
    db = get_db()
    a = _own_assignment_or_none(db, assignment_id)
    if not a:
        abort(404)
    class_date = _clean_class_date(request.form.get("date"))
    if class_date is None:
        flash("No valid date was given — nothing was deleted.", "error")
        return redirect(url_for("faculty_attendance",
                                assignment_id=assignment_id))
    db.execute(
        "DELETE FROM attendance WHERE assignment_id=? AND class_date=?",
        (assignment_id, class_date))
    db.commit()
    flash(f"Attendance for {class_date} deleted — that class no longer "
          f"counts in the summaries.", "ok")
    return redirect(url_for("faculty_attendance",
                            assignment_id=assignment_id))


@app.route("/faculty/course/<int:assignment_id>/attendance/summary")
@role_required("faculty")
def faculty_attendance_summary(assignment_id):
    db = get_db()
    a = _own_assignment_or_none(db, assignment_id)
    if not a:
        abort(404)
    classes_held, rows = _attendance_summary_rows(db, a)
    return render_template("faculty_attendance_summary.html", a=a,
                           rows=rows, classes_held=classes_held)


@app.route("/faculty/course/<int:assignment_id>/attendance/summary.xlsx")
@role_required("faculty")
def faculty_attendance_summary_xlsx(assignment_id):
    db = get_db()
    a = _own_assignment_or_none(db, assignment_id)
    if not a:
        abort(404)
    classes_held, rows = _attendance_summary_rows(db, a)
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance Summary"
    ws.append([f"{a['course_code']} — {a['course_title']}"])
    ws.append([f"Classes held: {classes_held}"])
    ws.append(["Reg No", "Name", "Present", "Absent", "Late", "Leave",
               "Total", "Attendance %"])
    for r in rows:
        s = r["student"]
        ws.append([s["registration_no"], s["name"], r["present"],
                   r["absent"], r["late"], r["leave"], r["total"], r["pct"]])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf, as_attachment=True,
        download_name=f"attendance-{a['course_code']}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ------------------------------------------------------- student attendance
@app.route("/student/attendance")
@role_required("student")
def student_attendance():
    db = get_db()
    sid = session.get("student_id")
    student = db.execute("SELECT * FROM students WHERE id=?",
                         (sid,)).fetchone()
    if not student:
        flash("No student record is linked to this login.", "error")
        return redirect(url_for("logout"))
    enrollments = db.execute(
        """SELECT e.*, c.code, c.title FROM enrollments e
           JOIN courses c ON c.id=e.course_id
           WHERE e.student_id=? ORDER BY c.code""", (sid,)).fetchall()
    courses = []
    for e in enrollments:
        sess = db.execute(
            "SELECT id FROM academic_sessions WHERE name=?",
            (e["session_name"],)).fetchone() if e["session_name"] else None
        # a course+session has at most one primary teacher, so at most one
        # assignment can hold this student's attendance for the course
        assignment = db.execute(
            """SELECT a.id, f.full_name teacher_name FROM course_assignments a
               JOIN faculty f ON f.id=a.faculty_id
               WHERE a.course_id=? AND a.session_id=?""",
            (e["course_id"], sess["id"])).fetchone() if sess else None
        entry = {"enrollment": e,
                 "teacher": assignment["teacher_name"] if assignment else None,
                 "classes_held": 0, "counts": None, "detail": []}
        if assignment:
            summ = attendance_summary(db, assignment["id"])
            entry["classes_held"] = summ["classes_held"]
            entry["counts"] = summ["by_student"].get(sid)
            entry["detail"] = db.execute(
                """SELECT class_date, status FROM attendance
                   WHERE assignment_id=? AND student_id=?
                   ORDER BY class_date""",
                (assignment["id"], sid)).fetchall()
        courses.append(entry)
    return render_template("student_attendance.html", student=student,
                           courses=courses)


# ------------------------------------------------------------ admin overview
def _assignment_full(db, assignment_id):
    """One assignment with course/program/session/teacher context (admin)."""
    return db.execute(
        """SELECT a.*, c.code course_code, c.title course_title,
                  c.semester_no, c.program_id, p.name prog_name,
                  ss.name sess_name, f.full_name teacher_name
           FROM course_assignments a
           JOIN courses c ON c.id=a.course_id
           LEFT JOIN programs p ON p.id=c.program_id
           LEFT JOIN academic_sessions ss ON ss.id=a.session_id
           JOIN faculty f ON f.id=a.faculty_id WHERE a.id=?""",
        (assignment_id,)).fetchone()


@app.route("/admin/attendance")
@role_required("admin")
def admin_attendance():
    db = get_db()
    rows = []
    for r in db.execute(
            """SELECT a.id FROM course_assignments a
               JOIN courses c ON c.id=a.course_id
               LEFT JOIN academic_sessions ss ON ss.id=a.session_id
               ORDER BY ss.name, c.code""").fetchall():
        a = dict(_assignment_full(db, r["id"]))
        a["classes_held"] = attendance_summary(db, a["id"])["classes_held"]
        a["student_count"] = len(sheet_students(
            db, a["program_id"], a["session_id"], a["course_id"],
            a["semester_no"]))
        rows.append(a)
    return render_template("admin_attendance.html", rows=rows)


@app.route("/admin/attendance/<int:assignment_id>")
@role_required("admin")
def admin_attendance_detail(assignment_id):
    db = get_db()
    a = _assignment_full(db, assignment_id)
    if not a:
        abort(404)
    classes_held, rows = _attendance_summary_rows(db, a)
    return render_template("admin_attendance_detail.html", a=a, rows=rows,
                           classes_held=classes_held)


# ================================================================ v0.9 CLEARANCE
# Degree clearance: the student applies once; the system creates one item
# per ACTIVE clearance unit. The Accounts / Fees item is auto-evaluated at
# apply time from the SAME ledger computation behind the Account Statement
# (total debit - total credit): dues -> Objected with a system note, zero
# -> Cleared by 'System'. Admins then clear or object each item (an admin
# may also override the auto-evaluated Accounts item); an objection needs
# a remark, and the student may ask for a recheck, which returns the item
# to Pending flagged for the admin. When every item is Cleared the
# request completes and the certificate PDF unlocks.

def student_outstanding(db, student_id):
    """Outstanding dues from the append-only ledger — exactly the Account
    Statement computation (sum of debits minus sum of credits)."""
    row = db.execute(
        """SELECT COALESCE(SUM(debit),0) d, COALESCE(SUM(credit),0) c
           FROM ledger_entries WHERE student_id=?""", (student_id,)).fetchone()
    return (row["d"] or 0) - (row["c"] or 0)


def _active_clearance_units(db):
    return db.execute(
        "SELECT * FROM clearance_units WHERE COALESCE(is_active,1)=1 "
        "ORDER BY sort_order, id").fetchall()


def _accounts_unit(db):
    return db.execute(
        "SELECT * FROM clearance_units WHERE COALESCE(is_accounts,0)=1 "
        "ORDER BY sort_order, id LIMIT 1").fetchone()


def _clearance_items(db, request_id):
    return db.execute(
        "SELECT * FROM clearance_items WHERE request_id=? ORDER BY id",
        (request_id,)).fetchall()


def _sync_clearance_status(db, request_id):
    """Keep the stored request status in step with its items: all Cleared
    -> 'Cleared' + completed_at; anything else -> 'In Progress'."""
    items = _clearance_items(db, request_id)
    req = db.execute("SELECT * FROM clearance_requests WHERE id=?",
                     (request_id,)).fetchone()
    if not req:
        return
    if items and all(i["status"] == "Cleared" for i in items):
        db.execute(
            "UPDATE clearance_requests SET status='Cleared', completed_at=? "
            "WHERE id=?",
            (req.get("completed_at") or _now(), request_id))
    else:
        db.execute(
            "UPDATE clearance_requests SET status='In Progress', "
            "completed_at=NULL WHERE id=?", (request_id,))


def _clearance_progress(db, request_id):
    items = _clearance_items(db, request_id)
    cleared = sum(1 for i in items if i["status"] == "Cleared")
    return cleared, len(items)


def _own_clearance_item_or_none(db, item_id):
    item = db.execute("SELECT * FROM clearance_items WHERE id=?",
                      (item_id,)).fetchone()
    if not item:
        return None
    req = db.execute("SELECT * FROM clearance_requests WHERE id=?",
                     (item["request_id"],)).fetchone()
    if not req or req["student_id"] != session.get("student_id"):
        return None
    return item


def _clearance_request_full(db, request_id):
    return db.execute(
        """SELECT r.*, s.name student_name, s.registration_no, s.cnic,
                  p.name prog_name, d.name dept_name
           FROM clearance_requests r
           JOIN students s ON s.id=r.student_id
           LEFT JOIN programs p ON p.id=s.program_id
           LEFT JOIN departments d ON d.id=s.department_id
           WHERE r.id=?""", (request_id,)).fetchone()


# ------------------------------------------------------------ student side
@app.route("/student/clearance")
@role_required("student")
def student_clearance():
    db = get_db()
    sid = session.get("student_id")
    student = student_full(db, sid) if sid else None
    if not student:
        flash("No student record is linked to this login.", "error")
        return redirect(url_for("logout"))
    req = db.execute(
        "SELECT * FROM clearance_requests WHERE student_id=? "
        "ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
    items, cleared_count = [], 0
    if req:
        items = _clearance_items(db, req["id"])
        cleared_count = sum(1 for i in items if i["status"] == "Cleared")
    return render_template(
        "student_clearance.html", student=student, req=req, items=items,
        cleared_count=cleared_count,
        units=_active_clearance_units(db) if not req else [])


@app.route("/student/clearance/apply", methods=["POST"])
@role_required("student")
def student_clearance_apply():
    db = get_db()
    sid = session.get("student_id")
    student = student_full(db, sid) if sid else None
    if not student:
        abort(404)
    existing = db.execute(
        "SELECT * FROM clearance_requests WHERE student_id=? "
        "ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
    if existing and existing["status"] == "In Progress":
        flash("Your clearance application is already in progress.", "error")
        return redirect(url_for("student_clearance"))
    if existing and existing["status"] == "Cleared":
        flash("You are already cleared — a new application is not needed.",
              "error")
        return redirect(url_for("student_clearance"))
    units = _active_clearance_units(db)
    if not units:
        flash("Clearance is not open yet — no units are configured.", "error")
        return redirect(url_for("student_clearance"))
    accounts = _accounts_unit(db)
    balance = student_outstanding(db, sid)
    now = _now()
    req_id = db.insert(
        "INSERT INTO clearance_requests (student_id,status,created_at,completed_at) "
        "VALUES (?,?,?,NULL)", (sid, "In Progress", now))
    for unit in units:
        status, auto_note, action_by, action_at = "Pending", None, None, None
        if accounts and unit["id"] == accounts["id"]:
            action_by, action_at = "System", now
            if balance > 0:
                status = "Objected"
                auto_note = (f"System check: outstanding dues of "
                             f"Rs {balance:,}.")
            else:
                status = "Cleared"
                auto_note = "System check: no outstanding dues."
        db.insert(
            """INSERT INTO clearance_items (request_id,unit_id,unit_name,status,
               remarks,auto_note,action_by,action_at,recheck_requested,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (req_id, unit["id"], unit["name"], status, None, auto_note,
             action_by, action_at, 0, now))
    _sync_clearance_status(db, req_id)
    db.commit()
    log_audit("clearance_applied", "Clearance application submitted")
    flash("Clearance application submitted. Each unit will now review it.",
          "ok")
    return redirect(url_for("student_clearance"))


@app.route("/student/clearance/items/<int:item_id>/recheck", methods=["POST"])
@role_required("student")
def student_clearance_recheck(item_id):
    db = get_db()
    item = _own_clearance_item_or_none(db, item_id)
    if not item:
        abort(404)
    if item["status"] != "Objected":
        flash("Only an objected item can be sent for a recheck.", "error")
        return redirect(url_for("student_clearance"))
    # back to Pending, flagged for the admin; the objection remark stays
    # on the item as history
    db.execute(
        "UPDATE clearance_items SET status='Pending', recheck_requested=1 "
        "WHERE id=?", (item_id,))
    _sync_clearance_status(db, item["request_id"])
    db.commit()
    log_audit("clearance_recheck_requested", f"Unit '{item['unit_name']}'")
    flash(f"Recheck requested for {item['unit_name']}.", "ok")
    return redirect(url_for("student_clearance"))


# ------------------------------------------------------------ certificate PDF
def build_clearance_certificate_pdf(db, request_id):
    """Clearance certificate PDF bytes — same green style as the other
    PDFs. Caller guarantees the request exists and is Cleared."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer,
                                    Table, TableStyle)
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    req = _clearance_request_full(db, request_id)
    student = student_full(db, req["student_id"])
    items = _clearance_items(db, request_id)
    year = (req.get("completed_at") or req.get("created_at") or _today())[:4]
    cert_no = f"CLR-{year}-{req['id']}"
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=14 * mm,
                            bottomMargin=14 * mm, leftMargin=14 * mm,
                            rightMargin=14 * mm,
                            title=f"Clearance Certificate {cert_no}")
    story = _pdf_header(styles, "CLEARANCE CERTIFICATE")
    green = colors.HexColor("#0b6b3a")
    grid = colors.HexColor("#b9d2c2")
    light = colors.HexColor("#eaf5ee")
    story.append(Paragraph(f"Certificate No: <b>{cert_no}</b>",
                           styles["BodyText"]))
    story.append(Spacer(1, 3 * mm))
    info = [["Student Name", student["name"],
             "Registration No.", student["registration_no"]],
            ["CNIC", student.get("cnic") or "—",
             "Program", student["prog_name"] or "—"],
            ["Department", student["dept_name"] or "—",
             "Session",
             student["sess_name"] or student.get("session_name") or "—"]]
    t = Table(info, colWidths=[30 * mm, 58 * mm, 30 * mm, 64 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, grid),
                           ("BACKGROUND", (0, 0), (0, -1), light),
                           ("BACKGROUND", (2, 0), (2, -1), light),
                           ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [t, Spacer(1, 5 * mm)]
    story.append(Paragraph(
        "This is to certify that the above-named student has been cleared "
        "by all units of the university listed below.",
        styles["BodyText"]))
    story.append(Spacer(1, 3 * mm))
    rows = [["Unit", "Status", "Cleared On", "Cleared By"]]
    for it in items:
        rows.append([it["unit_name"], "Cleared",
                     (it.get("action_at") or "")[:10] or "—",
                     it.get("action_by") or "—"])
    lt = Table(rows, colWidths=[64 * mm, 30 * mm, 30 * mm, 58 * mm])
    lt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, grid),
                            ("BACKGROUND", (0, 0), (-1, 0), green),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [lt, Spacer(1, 8 * mm)]
    story.append(Paragraph("<b><font color=\"#0b6b3a\" size=\"16\">CLEARED"
                           "</font></b>", styles["BodyText"]))
    story += [Spacer(1, 6 * mm),
              Paragraph(f"Generated on {_now()} by MY CUVAS (Demo) — "
                        f"system-generated certificate, no signature "
                        f"required. All data shown is fictional demo data.",
                        styles["BodyText"])]
    doc.build(story)
    buf.seek(0)  # AFTER build() — house lesson
    return buf.getvalue()


@app.route("/student/clearance/certificate.pdf")
@role_required("student")
def student_clearance_certificate():
    db = get_db()
    sid = session.get("student_id")
    req = db.execute(
        "SELECT * FROM clearance_requests WHERE student_id=? "
        "ORDER BY id DESC LIMIT 1", (sid,)).fetchone() if sid else None
    if not req or req["status"] != "Cleared":
        flash("The clearance certificate is available once every unit has "
              "cleared you.", "error")
        return redirect(url_for("student_clearance"))
    student = student_full(db, sid)
    return send_file(
        io.BytesIO(build_clearance_certificate_pdf(db, req["id"])),
        as_attachment=True,
        download_name=f"clearance-certificate-{student['registration_no']}.pdf",
        mimetype="application/pdf")


# ------------------------------------------------------------ admin desk
@app.route("/admin/clearance")
@role_required("admin")
def admin_clearance():
    db = get_db()
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()
    sql = ("SELECT r.id FROM clearance_requests r "
           "JOIN students s ON s.id=r.student_id WHERE 1=1")
    params = []
    if status in ("In Progress", "Cleared"):
        sql += " AND r.status=?"
        params.append(status)
    if q:
        sql += f" AND (s.name {LIKE} ? OR s.registration_no {LIKE} ?)"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY r.id DESC"
    rows = []
    for r in db.execute(sql, params).fetchall():
        full = dict(_clearance_request_full(db, r["id"]))
        full["cleared_count"], full["total_count"] = _clearance_progress(
            db, r["id"])
        rows.append(full)
    counts = {s: db.execute(
        "SELECT COUNT(*) c FROM clearance_requests WHERE status=?",
        (s,)).fetchone()["c"] for s in ("In Progress", "Cleared")}
    return render_template("admin_clearance.html", rows=rows, counts=counts,
                           status=status, q=q)


@app.route("/admin/clearance/<int:request_id>")
@role_required("admin")
def admin_clearance_detail(request_id):
    db = get_db()
    req = _clearance_request_full(db, request_id)
    if not req:
        abort(404)
    items = _clearance_items(db, request_id)
    cleared_count = sum(1 for i in items if i["status"] == "Cleared")
    return render_template(
        "admin_clearance_detail.html", req=req, items=items,
        cleared_count=cleared_count,
        outstanding=student_outstanding(db, req["student_id"]))


@app.route("/admin/clearance/items/<int:item_id>/clear", methods=["POST"])
@role_required("admin")
def admin_clearance_item_clear(item_id):
    db = get_db()
    item = db.execute("SELECT * FROM clearance_items WHERE id=?",
                      (item_id,)).fetchone()
    if not item:
        abort(404)
    remark = request.form.get("remark", "").strip()
    if remark:
        db.execute(
            "UPDATE clearance_items SET status='Cleared', remarks=?, "
            "action_by=?, action_at=?, recheck_requested=0 WHERE id=?",
            (remark, session.get("display_name"), _now(), item_id))
    else:
        db.execute(
            "UPDATE clearance_items SET status='Cleared', action_by=?, "
            "action_at=?, recheck_requested=0 WHERE id=?",
            (session.get("display_name"), _now(), item_id))
    _sync_clearance_status(db, item["request_id"])
    db.commit()
    log_audit("clearance_item_cleared",
                f"Unit '{item['unit_name']}' (request #{item['request_id']})")
    flash(f"{item['unit_name']} cleared.", "ok")
    return redirect(url_for("admin_clearance_detail",
                            request_id=item["request_id"]))


@app.route("/admin/clearance/items/<int:item_id>/object", methods=["POST"])
@role_required("admin")
def admin_clearance_item_object(item_id):
    db = get_db()
    item = db.execute("SELECT * FROM clearance_items WHERE id=?",
                      (item_id,)).fetchone()
    if not item:
        abort(404)
    remark = request.form.get("remark", "").strip()
    if not remark:
        flash("A remark is required when raising an objection — the "
              "student needs to know what to fix.", "error")
        return redirect(url_for("admin_clearance_detail",
                                request_id=item["request_id"]))
    db.execute(
        "UPDATE clearance_items SET status='Objected', remarks=?, "
        "action_by=?, action_at=?, recheck_requested=0 WHERE id=?",
        (remark, session.get("display_name"), _now(), item_id))
    _sync_clearance_status(db, item["request_id"])
    db.commit()
    log_audit("clearance_item_objected",
                f"Unit '{item['unit_name']}' (request #{item['request_id']})")
    flash(f"Objection recorded for {item['unit_name']}.", "ok")
    return redirect(url_for("admin_clearance_detail",
                            request_id=item["request_id"]))


@app.route("/admin/clearance/<int:request_id>/certificate.pdf")
@role_required("admin")
def admin_clearance_certificate(request_id):
    db = get_db()
    req = _clearance_request_full(db, request_id)
    if not req:
        abort(404)
    if req["status"] != "Cleared":
        flash("The certificate is available only once this request is "
              "fully cleared.", "error")
        return redirect(url_for("admin_clearance_detail",
                                request_id=request_id))
    return send_file(
        io.BytesIO(build_clearance_certificate_pdf(db, request_id)),
        as_attachment=True,
        download_name=f"clearance-certificate-{req['registration_no']}.pdf",
        mimetype="application/pdf")


# ------------------------------------------------------------ admin: units
@app.route("/admin/clearance/units", methods=["GET", "POST"])
@role_required("admin")
def admin_clearance_units():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Unit name is required.", "error")
        elif db.execute(
                f"SELECT id FROM clearance_units WHERE name {LIKE} ?",
                (name,)).fetchone():
            flash(f"A clearance unit named '{name}' already exists.",
                  "error")
        else:
            top = db.execute(
                "SELECT COALESCE(MAX(sort_order),0) m FROM clearance_units"
            ).fetchone()["m"]
            db.insert(
                "INSERT INTO clearance_units (name,sort_order,is_active,"
                "is_accounts) VALUES (?,?,1,0)", (name, top + 1))
            db.commit()
            log_audit("clearance_units_changed", f"Unit '{name}' added")
            flash(f"Clearance unit '{name}' added.", "ok")
        return redirect(url_for("admin_clearance_units"))
    units = db.execute(
        "SELECT * FROM clearance_units ORDER BY sort_order, id").fetchall()
    return render_template("admin_clearance_units.html", units=units)


@app.route("/admin/clearance/units/<int:unit_id>/rename", methods=["POST"])
@role_required("admin")
def admin_clearance_unit_rename(unit_id):
    db = get_db()
    unit = db.execute("SELECT * FROM clearance_units WHERE id=?",
                      (unit_id,)).fetchone()
    if not unit:
        abort(404)
    name = request.form.get("name", "").strip()
    if not name:
        flash("Unit name is required.", "error")
    elif db.execute(
            f"SELECT id FROM clearance_units WHERE name {LIKE} ? AND id<>?",
            (name, unit_id)).fetchone():
        flash(f"Another clearance unit is already named '{name}'.", "error")
    else:
        # renames affect FUTURE applications only — existing items keep
        # their snapshot unit_name
        db.execute("UPDATE clearance_units SET name=? WHERE id=?",
                   (name, unit_id))
        db.commit()
        log_audit("clearance_units_changed", f"Unit renamed to '{name}'")
        flash(f"Unit renamed to '{name}'.", "ok")
    return redirect(url_for("admin_clearance_units"))


@app.route("/admin/clearance/units/<int:unit_id>/toggle", methods=["POST"])
@role_required("admin")
def admin_clearance_unit_toggle(unit_id):
    db = get_db()
    unit = db.execute("SELECT * FROM clearance_units WHERE id=?",
                      (unit_id,)).fetchone()
    if not unit:
        abort(404)
    new_state = 0 if unit.get("is_active", 1) else 1
    db.execute("UPDATE clearance_units SET is_active=? WHERE id=?",
               (new_state, unit_id))
    db.commit()
    log_audit("clearance_units_changed",
              f"Unit '{unit['name']}' {'activated' if new_state else 'deactivated'}")
    flash(f"Unit '{unit['name']}' "
          f"{'activated' if new_state else 'deactivated'}.", "ok")
    return redirect(url_for("admin_clearance_units"))


# ------------------------------------------------------------ student card
def build_student_card_pdf(db, student_id):
    """Student card PDF bytes: one ID-proportioned card on an A4 page
    (dashed cut line, CUVAS header band in the standard PDF green, photo
    placeholder, identity fields and a Code39 barcode of the registration
    number)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas as pdfcanvas

    student = student_full(db, student_id)
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4
    green = colors.HexColor("#0b6b3a")
    dark = colors.HexColor("#175732")
    grid = colors.HexColor("#b9d2c2")
    card_w, card_h = 170 * mm, 170 * mm / 1.586  # ID-card proportions
    x0 = (page_w - card_w) / 2
    y_top = page_h - 30 * mm
    y0 = y_top - card_h

    # cut-out guide + card body
    c.setStrokeColor(grid)
    c.setDash(4, 3)
    c.rect(x0 - 4 * mm, y0 - 4 * mm, card_w + 8 * mm, card_h + 8 * mm, stroke=1, fill=0)
    c.setDash()
    c.setStrokeColor(green)
    c.setLineWidth(1.4)
    c.setFillColor(colors.white)
    c.rect(x0, y0, card_w, card_h, stroke=1, fill=1)

    # header band
    band_h = 17 * mm
    c.setFillColor(green)
    c.rect(x0, y_top - band_h, card_w, band_h, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(x0 + 6 * mm, y_top - 8 * mm, "MY CUVAS — Campus Management System")
    c.setFont("Helvetica", 8.5)
    c.drawString(x0 + 6 * mm, y_top - 13.5 * mm,
                 "Cholistan University of Veterinary and Animal Sciences")
    c.setFillColor(dark)
    c.setFont("Helvetica-Bold", 12.5)
    c.drawCentredString(x0 + card_w / 2, y_top - band_h - 7 * mm, "STUDENT CARD")

    # photo placeholder (right side)
    photo_w, photo_h = 26 * mm, 33 * mm
    photo_x = x0 + card_w - photo_w - 6 * mm
    photo_y = y_top - band_h - 14 * mm - photo_h
    c.setStrokeColor(green)
    c.setLineWidth(0.9)
    c.rect(photo_x, photo_y, photo_w, photo_h, stroke=1, fill=0)
    c.setFillColor(dark)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(photo_x + photo_w / 2, photo_y + photo_h / 2 + 2, "PASSPORT")
    c.drawCentredString(photo_x + photo_w / 2, photo_y + photo_h / 2 - 3.5 * mm, "PHOTO")

    # identity fields (left side)
    fields = [("Name", student["name"]),
              ("Registration No", student["registration_no"]),
              ("CNIC", student.get("cnic") or "—"),
              ("Program", student["prog_name"] or "—"),
              ("Department", student["dept_name"] or "—"),
              ("Session", student["sess_name"] or student.get("session_name") or "—"),
              ("Blood Group", student.get("blood_group") or "—")]
    fy = y_top - band_h - 16 * mm
    for label, value in fields:
        c.setFillColor(dark)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x0 + 6 * mm, fy, label)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 9)
        c.drawString(x0 + 36 * mm, fy, str(value)[:52])
        fy -= 6.2 * mm

    # barcode of the registration number
    reg = (student["registration_no"] or "").upper()
    try:
        from reportlab.graphics.barcode import code39
        barcode = code39.Standard39(reg, checksum=0, barHeight=11 * mm,
                                    barWidth=0.42 * mm, gap=0.21 * mm)
        barcode.drawOn(c, x0 + 6 * mm, y0 + 11 * mm)
    except Exception:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x0 + 6 * mm, y0 + 13 * mm, reg)
    c.setFillColor(dark)
    c.setFont("Helvetica-Oblique", 8.5)
    c.drawRightString(x0 + card_w - 6 * mm, y0 + 6 * mm,
                      "Valid for the duration of the program")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 8)
    c.drawString(x0, y0 - 12 * mm,
                 f"Generated on {_now()} by MY CUVAS (Demo) — system-generated card, "
                 f"all data shown is fictional demo data.")
    c.showPage()
    c.save()
    buf.seek(0)  # AFTER save() — house lesson
    return buf.getvalue()


@app.route("/student/card.pdf")
@role_required("student")
def student_card_pdf():
    db = get_db()
    sid = session.get("student_id")
    student = student_full(db, sid) if sid else None
    if not student:
        abort(404)
    return send_file(io.BytesIO(build_student_card_pdf(db, sid)), as_attachment=True,
                     download_name=f"student-card-{student['registration_no']}.pdf",
                     mimetype="application/pdf")


@app.route("/admin/students/<int:student_id>/card.pdf")
@role_required("admin")
def admin_student_card_pdf(student_id):
    db = get_db()
    student = student_full(db, student_id)
    if not student:
        abort(404)
    return send_file(io.BytesIO(build_student_card_pdf(db, student_id)),
                     as_attachment=True,
                     download_name=f"student-card-{student['registration_no']}.pdf",
                     mimetype="application/pdf")


# ================================================================ v0.10 SCHOLARSHIPS
# Scholarship schemes (admin CRUD) + a per-student socio-economic profile
# + applications. A student must first complete the profile (father or
# guardian name AND monthly income); applications are unique per
# student + scheme + session and can only target a scheme that is open
# and inside its deadline. The admin reviews each application on a
# detail page showing the student's identity, the FULL profile, the
# transcript CGPA (via transcript_data — the same number the student
# sees) and the ledger outstanding dues (student_outstanding). Statuses:
# Applied -> Under Review -> Approved (awarded amount recorded) /
# Rejected (remark required). Approved / Rejected are FINAL. Approving
# records the award on the application ONLY — it never writes to the
# append-only fee ledger in this version.

SCHOLARSHIP_STATUSES = ("Applied", "Under Review", "Approved", "Rejected")
FATHER_STATUSES = ("Alive", "Deceased")
HOUSE_STATUSES = ("Own", "Rented", "Other")

_PROFILE_TEXT_FIELDS = ("father_name", "father_occupation", "guardian_name",
                        "guardian_relation", "bank_name", "account_title",
                        "account_number", "bank_branch")
_PROFILE_INT_FIELDS = ("family_members", "siblings_studying",
                       "monthly_income", "monthly_expenses")
_PROFILE_ALL_FIELDS = (_PROFILE_TEXT_FIELDS + _PROFILE_INT_FIELDS +
                       ("father_status", "house_status"))


def current_session(db):
    """The latest/current academic session: sessions are created in
    chronological order, so the current one is the most recently added
    OPEN session (falling back to the most recently added session) —
    the same ordering _sheet_args relies on."""
    row = db.execute(
        "SELECT * FROM academic_sessions WHERE is_open=1 "
        "ORDER BY id DESC").fetchone()
    if not row:
        row = db.execute(
            "SELECT * FROM academic_sessions ORDER BY id DESC").fetchone()
    return row


def scholarship_profile(db, student_id):
    return db.execute(
        "SELECT * FROM scholarship_profiles WHERE student_id=?",
        (student_id,)).fetchone()


def profile_complete(db, student_id):
    """A profile counts as complete when it exists with a father or
    guardian name AND a monthly income filled in."""
    p = scholarship_profile(db, student_id)
    if not p:
        return False
    return bool((p.get("father_name") or p.get("guardian_name"))
                and p.get("monthly_income") is not None)


def _scheme_apply_state(db, scheme, student_id, sess):
    """(can_apply, note) for this student + scheme right now."""
    if not scheme or not scheme.get("is_open", 1):
        return False, "Closed"
    if scheme.get("deadline") and scheme["deadline"] < _today():
        return False, "Closed (deadline passed)"
    if sess:
        dup = db.execute(
            """SELECT id FROM scholarship_applications
               WHERE student_id=? AND scheme_id=? AND session_id=?""",
            (student_id, scheme["id"], sess["id"])).fetchone()
        if dup:
            return False, "Already applied"
    return True, "Open"


def _application_full(db, app_id):
    return db.execute(
        """SELECT a.*, sc.name scheme_name, sc.provider scheme_provider,
                  ss.name sess_name, s.name student_name, s.registration_no,
                  s.cnic cnic, p.name prog_name, d.name dept_name
           FROM scholarship_applications a
           JOIN scholarship_schemes sc ON sc.id=a.scheme_id
           JOIN students s ON s.id=a.student_id
           LEFT JOIN academic_sessions ss ON ss.id=a.session_id
           LEFT JOIN programs p ON p.id=s.program_id
           LEFT JOIN departments d ON d.id=s.department_id
           WHERE a.id=?""", (app_id,)).fetchone()


# ------------------------------------------------------------ student side
@app.route("/student/scholarships")
@role_required("student")
def student_scholarships():
    db = get_db()
    sid = session.get("student_id")
    student = student_full(db, sid) if sid else None
    if not student:
        flash("No student record is linked to this login.", "error")
        return redirect(url_for("logout"))
    profile = scholarship_profile(db, sid)
    sess = current_session(db)
    schemes = []
    for sc in db.execute(
            """SELECT * FROM scholarship_schemes
               WHERE COALESCE(is_open,1)=1 ORDER BY id""").fetchall():
        sc = dict(sc)
        sc["can_apply"], sc["state_note"] = _scheme_apply_state(
            db, sc, sid, sess)
        schemes.append(sc)
    applications = db.execute(
        """SELECT a.*, sc.name scheme_name, ss.name sess_name
           FROM scholarship_applications a
           JOIN scholarship_schemes sc ON sc.id=a.scheme_id
           LEFT JOIN academic_sessions ss ON ss.id=a.session_id
           WHERE a.student_id=? ORDER BY a.id DESC""", (sid,)).fetchall()
    return render_template(
        "student_scholarships.html", student=student, profile=profile,
        profile_done=profile_complete(db, sid), schemes=schemes,
        applications=applications, father_statuses=FATHER_STATUSES,
        house_statuses=HOUSE_STATUSES, today=_today())


@app.route("/student/scholarships/profile", methods=["GET"])
@role_required("student")
def student_scholarship_profile():
    """v0.16 alias: the socio-economic profile is section 1 of the
    scholarships page — the sidebar / bookmark URL resolves to it.
    (Saving the profile stays the POST route below.)"""
    return redirect(url_for("student_scholarships") + "?view=profile#profile")


@app.route("/student/scholarships/profile", methods=["POST"])
@role_required("student")
def student_scholarship_profile_save():
    db = get_db()
    sid = session.get("student_id")
    student = student_full(db, sid) if sid else None
    if not student:
        abort(404)
    form = request.form
    values = {}
    for f in _PROFILE_TEXT_FIELDS:
        values[f] = form.get(f, "").strip() or None
    for f in _PROFILE_INT_FIELDS:
        values[f] = _int_or_none(form.get(f, "").strip())
    values["father_status"] = (form.get("father_status")
                               if form.get("father_status") in FATHER_STATUSES
                               else None)
    values["house_status"] = (form.get("house_status")
                              if form.get("house_status") in HOUSE_STATUSES
                              else None)
    existing = scholarship_profile(db, sid)
    cols = ", ".join(_PROFILE_ALL_FIELDS)
    if existing:
        sets = ", ".join(f"{f}=?" for f in _PROFILE_ALL_FIELDS)
        db.execute(
            f"UPDATE scholarship_profiles SET {sets}, updated_at=? "
            "WHERE student_id=?",
            [values[f] for f in _PROFILE_ALL_FIELDS] + [_now(), sid])
    else:
        marks = ", ".join("?" for _ in _PROFILE_ALL_FIELDS)
        db.execute(
            f"INSERT INTO scholarship_profiles (student_id, {cols}, "
            f"updated_at) VALUES (?, {marks}, ?)",
            [sid] + [values[f] for f in _PROFILE_ALL_FIELDS] + [_now()])
    db.commit()
    if profile_complete(db, sid):
        flash("Socio-economic profile saved — it is complete, so you can "
              "now apply for scholarships.", "ok")
    else:
        flash("Socio-economic profile saved — note it is still incomplete: "
              "a father or guardian name and the monthly family income are "
              "required before you can apply.", "ok")
    return redirect(url_for("student_scholarships"))


@app.route("/student/scholarships/<int:scheme_id>/apply", methods=["POST"])
@role_required("student")
def student_scholarship_apply(scheme_id):
    db = get_db()
    sid = session.get("student_id")
    student = student_full(db, sid) if sid else None
    if not student:
        abort(404)
    scheme = db.execute("SELECT * FROM scholarship_schemes WHERE id=?",
                        (scheme_id,)).fetchone()
    if not scheme:
        abort(404)
    if not profile_complete(db, sid):
        flash("Complete your socio-economic profile before applying.",
              "error")
        return redirect(url_for("student_scholarships"))
    if not scheme.get("is_open", 1):
        flash(f"'{scheme['name']}' is not open for applications.", "error")
        return redirect(url_for("student_scholarships"))
    if scheme.get("deadline") and scheme["deadline"] < _today():
        flash(f"The deadline for '{scheme['name']}' "
              f"({scheme['deadline']}) has passed.", "error")
        return redirect(url_for("student_scholarships"))
    sess = current_session(db)
    if not sess:
        flash("No academic session is configured yet — applications are "
              "not open.", "error")
        return redirect(url_for("student_scholarships"))
    dup = db.execute(
        """SELECT id FROM scholarship_applications
           WHERE student_id=? AND scheme_id=? AND session_id=?""",
        (sid, scheme_id, sess["id"])).fetchone()
    if dup:
        flash(f"You have already applied for '{scheme['name']}' in "
              f"{sess['name']}.", "error")
        return redirect(url_for("student_scholarships"))
    try:
        db.insert(
            """INSERT INTO scholarship_applications (student_id,scheme_id,
               session_id,statement,status,created_at)
               VALUES (?,?,?,?,?,?)""",
            (sid, scheme_id, sess["id"],
             request.form.get("statement", "").strip(),
             "Applied", _now()))
        db.commit()
    except Exception as exc:
        db.rollback()
        if is_unique_error(exc):
            flash(f"You have already applied for '{scheme['name']}' in "
                  f"{sess['name']}.", "error")
            return redirect(url_for("student_scholarships"))
        raise
    log_audit("scholarship_applied", f"Scheme '{scheme['name']}'")
    flash(f"Application submitted for '{scheme['name']}' "
          f"({sess['name']}).", "ok")
    return redirect(url_for("student_scholarships"))


# ------------------------------------------------------------ admin: schemes
def _scheme_form_values(form):
    return {
        "name": form.get("name", "").strip(),
        "provider": form.get("provider", "").strip(),
        "description": form.get("description", "").strip(),
        "eligibility": form.get("eligibility", "").strip(),
        "deadline": form.get("deadline", "").strip() or None,
        "is_open": 1 if form.get("is_open") else 0,
    }


@app.route("/admin/scholarships/schemes/new", methods=["GET", "POST"])
@role_required("admin")
def admin_scholarship_scheme_new():
    db = get_db()
    if request.method == "POST":
        v = _scheme_form_values(request.form)
        if not v["name"]:
            flash("Scheme name is required.", "error")
        else:
            db.insert(
                """INSERT INTO scholarship_schemes (name,provider,
                   description,eligibility,is_open,deadline,created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (v["name"], v["provider"], v["description"],
                 v["eligibility"], v["is_open"], v["deadline"], _now()))
            db.commit()
            log_audit("scholarship_scheme_created", f"Scheme '{v['name']}'")
            flash(f"Scholarship scheme '{v['name']}' added.", "ok")
            return redirect(url_for("admin_scholarships"))
    return render_template("scholarship_scheme_form.html", scheme=None)


@app.route("/admin/scholarships/schemes/<int:scheme_id>/edit",
           methods=["GET", "POST"])
@role_required("admin")
def admin_scholarship_scheme_edit(scheme_id):
    db = get_db()
    scheme = db.execute("SELECT * FROM scholarship_schemes WHERE id=?",
                        (scheme_id,)).fetchone()
    if not scheme:
        flash("Scholarship scheme not found.", "error")
        return redirect(url_for("admin_scholarships"))
    if request.method == "POST":
        v = _scheme_form_values(request.form)
        if not v["name"]:
            flash("Scheme name is required.", "error")
        else:
            db.execute(
                """UPDATE scholarship_schemes SET name=?, provider=?,
                   description=?, eligibility=?, is_open=?, deadline=?
                   WHERE id=?""",
                (v["name"], v["provider"], v["description"],
                 v["eligibility"], v["is_open"], v["deadline"], scheme_id))
            db.commit()
            log_audit("scholarship_scheme_updated", f"Scheme '{v['name']}'")
            flash(f"Scholarship scheme '{v['name']}' updated.", "ok")
            return redirect(url_for("admin_scholarships"))
    return render_template("scholarship_scheme_form.html", scheme=scheme)


@app.route("/admin/scholarships/schemes/<int:scheme_id>/delete",
           methods=["POST"])
@role_required("admin")
def admin_scholarship_scheme_delete(scheme_id):
    db = get_db()
    scheme = db.execute("SELECT * FROM scholarship_schemes WHERE id=?",
                        (scheme_id,)).fetchone()
    if not scheme:
        flash("Scholarship scheme not found.", "error")
        return redirect(url_for("admin_scholarships"))
    used = db.execute(
        "SELECT COUNT(*) c FROM scholarship_applications WHERE scheme_id=?",
        (scheme_id,)).fetchone()["c"]
    if used:
        flash(f"Cannot delete scheme '{scheme['name']}': it has {used} "
              "application(s). Close it instead so the history stays.",
              "error")
        return redirect(url_for("admin_scholarships"))
    db.execute("DELETE FROM scholarship_schemes WHERE id=?", (scheme_id,))
    db.commit()
    log_audit("scholarship_scheme_deleted", f"Scheme '{scheme['name']}'")
    flash(f"Scholarship scheme '{scheme['name']}' deleted.", "ok")
    return redirect(url_for("admin_scholarships"))


# ------------------------------------------------------- admin: applications
@app.route("/admin/scholarships")
@role_required("admin")
def admin_scholarships():
    db = get_db()
    schemes = db.execute(
        """SELECT sc.*, (SELECT COUNT(*) FROM scholarship_applications a
               WHERE a.scheme_id=sc.id) app_count
           FROM scholarship_schemes sc ORDER BY sc.id""").fetchall()
    status = request.args.get("status", "")
    scheme_id = _int_or_none(request.args.get("scheme_id", ""))
    q = request.args.get("q", "").strip()
    sql = ("SELECT a.id FROM scholarship_applications a "
           "JOIN students s ON s.id=a.student_id WHERE 1=1")
    params = []
    if status in SCHOLARSHIP_STATUSES:
        sql += " AND a.status=?"
        params.append(status)
    if scheme_id:
        sql += " AND a.scheme_id=?"
        params.append(scheme_id)
    if q:
        sql += f" AND (s.name {LIKE} ? OR s.registration_no {LIKE} ?)"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY a.id DESC"
    rows = [_application_full(db, r["id"])
            for r in db.execute(sql, params).fetchall()]
    counts = {s: db.execute(
        "SELECT COUNT(*) c FROM scholarship_applications WHERE status=?",
        (s,)).fetchone()["c"] for s in SCHOLARSHIP_STATUSES}
    return render_template(
        "admin_scholarships.html", schemes=schemes, rows=rows,
        counts=counts, status=status, scheme_id=scheme_id, q=q,
        statuses=SCHOLARSHIP_STATUSES)


@app.route("/admin/scholarships/applications/<int:app_id>")
@role_required("admin")
def admin_scholarship_application(app_id):
    db = get_db()
    appl = _application_full(db, app_id)
    if not appl:
        abort(404)
    student = student_full(db, appl["student_id"])
    _transcript, cgpa, _ch = transcript_data(
        db, appl["student_id"], published_only=True)
    return render_template(
        "admin_scholarship_application.html", appl=appl, student=student,
        profile=scholarship_profile(db, appl["student_id"]),
        profile_done=profile_complete(db, appl["student_id"]),
        cgpa=cgpa, outstanding=student_outstanding(db, appl["student_id"]))


@app.route("/admin/scholarships/applications/<int:app_id>/decide",
           methods=["POST"])
@role_required("admin")
def admin_scholarship_decide(app_id):
    db = get_db()
    appl = db.execute("SELECT * FROM scholarship_applications WHERE id=?",
                      (app_id,)).fetchone()
    if not appl:
        abort(404)
    back = redirect(url_for("admin_scholarship_application", app_id=app_id))
    if appl["status"] in ("Approved", "Rejected"):
        flash("This application has already been decided — the decision "
              "is final.", "error")
        return back
    decision = request.form.get("decision", "")
    remarks = request.form.get("admin_remarks", "").strip()
    if decision == "Under Review":
        db.execute(
            "UPDATE scholarship_applications SET status='Under Review' "
            "WHERE id=?", (app_id,))
        db.commit()
        log_audit("scholarship_application_decided",
                  f"Application #{app_id} — Under Review")
        flash("Application marked Under Review.", "ok")
        return back
    if decision == "Approve":
        amount = _int_or_none(request.form.get("awarded_amount", "").strip())
        if amount is None or amount < 0:
            flash("Enter the awarded amount (Rs) to approve this "
                  "application.", "error")
            return back
        db.execute(
            """UPDATE scholarship_applications SET status='Approved',
               awarded_amount=?, admin_remarks=?, decided_by=?,
               decided_at=? WHERE id=?""",
            (amount, remarks or None, session.get("display_name"), _now(),
             app_id))
        db.commit()
        log_audit("scholarship_application_decided",
                  f"Application #{app_id} — Approved, Rs {amount:,}")
        flash(f"Application approved — award of Rs {amount:,} recorded. "
              "(The award is recorded here only; it does not post to the "
              "fee ledger.)", "ok")
        return back
    if decision == "Reject":
        if not remarks:
            flash("Remarks are required when rejecting — the student "
                  "needs to know why.", "error")
            return back
        db.execute(
            """UPDATE scholarship_applications SET status='Rejected',
               awarded_amount=NULL, admin_remarks=?, decided_by=?,
               decided_at=? WHERE id=?""",
            (remarks, session.get("display_name"), _now(), app_id))
        db.commit()
        log_audit("scholarship_application_decided",
                  f"Application #{app_id} — Rejected")
        flash("Application rejected.", "ok")
        return back
    flash("Please choose a decision.", "error")
    return back


# ============================================================ v0.11 REPEAT
# Course Repeat / Improvement. A student applies from their PUBLISHED
# results (an F must be repeated; a passed course may be improved) into
# a DIFFERENT session. The admin approves by issuing a normal fee
# voucher (kind='Repeat', vouchers.repeat_request_id) priced at the
# admin-set per-credit-hour rate x the course's credit hours; the
# voucher flows through the usual challan / proof / verify path, and
# verification activates the request (Enrolled + target-session
# enrollment). The transcript counts only the latest attempt of a
# repeated course (see transcript_data).

REPEAT_STATUSES = ["Requested", "Approved", "Enrolled", "Rejected", "Cancelled"]


def _attempt_key(r):
    """Ordering of one result attempt: session first (sessions are
    created chronologically, so the id IS the ordering), then row id."""
    return (r.get("session_id") or 0, r["id"])


def _published_attempts(db, student_id):
    return db.execute(
        """SELECT r.*, c.code, c.title, c.credit_theory, c.credit_lab,
                  ss.name from_sess_name
           FROM results r JOIN courses c ON c.id=r.course_id
           LEFT JOIN academic_sessions ss ON ss.id=r.session_id
           WHERE r.student_id=? AND COALESCE(r.is_published,0)=1
           ORDER BY r.id""", (student_id,)).fetchall()


def latest_attempt(db, student_id, course_id):
    """The student's latest PUBLISHED attempt at a course, or None."""
    rows = [r for r in _published_attempts(db, student_id)
            if r["course_id"] == course_id]
    return max(rows, key=_attempt_key) if rows else None


def active_repeat_request(db, student_id, course_id):
    """The request that currently blocks a new application for this
    course: 'Requested'/'Approved' always block; 'Enrolled' blocks
    until the repeat attempt has been published in its target session."""
    for req in db.execute(
            """SELECT * FROM repeat_requests WHERE student_id=? AND course_id=?
               AND status IN ('Requested','Approved','Enrolled')
               ORDER BY id DESC""", (student_id, course_id)).fetchall():
        if req["status"] in ("Requested", "Approved"):
            return req
        done = db.execute(
            """SELECT COUNT(*) c FROM results WHERE student_id=?
               AND course_id=? AND session_id=?
               AND COALESCE(is_published,0)=1""",
            (student_id, course_id, req["target_session_id"])).fetchone()["c"]
        if not done:
            return req
    return None


def repeat_eligibility(db, student_id):
    """Courses the student may apply to repeat / improve right now:
    the latest PUBLISHED attempt per course decides — grade F means
    'Repeat', any passed grade means 'Improvement'. Courses with an
    active repeat request are not eligible (they show under My Repeat
    Requests instead). Unpublished results never appear here."""
    bands = get_grade_bands(db)
    latest = {}
    for r in _published_attempts(db, student_id):
        cur = latest.get(r["course_id"])
        if cur is None or _attempt_key(r) > _attempt_key(cur):
            latest[r["course_id"]] = r
    out = []
    for course_id, r in latest.items():
        grade, _gp = result_grade_gp(r, bands)
        if grade is None:
            continue
        if active_repeat_request(db, student_id, course_id):
            continue
        out.append({**r, "grade": grade,
                    "kind": "Repeat" if grade == "F" else "Improvement",
                    "credits": (r["credit_theory"] or 0)
                               + (r["credit_lab"] or 0)})
    return sorted(out, key=lambda x: x["code"])


def _repeat_request_full(db, req_id):
    return db.execute(
        """SELECT rr.*, c.code course_code, c.title course_title,
                  c.semester_no course_semester,
                  c.credit_theory, c.credit_lab,
                  fs.name from_sess_name, ts.name target_sess_name,
                  s.name student_name, s.registration_no,
                  p.name prog_name,
                  v.challan_no, v.status voucher_status,
                  v.amount voucher_amount
           FROM repeat_requests rr
           JOIN courses c ON c.id=rr.course_id
           JOIN students s ON s.id=rr.student_id
           LEFT JOIN academic_sessions fs ON fs.id=rr.from_session_id
           LEFT JOIN academic_sessions ts ON ts.id=rr.target_session_id
           LEFT JOIN programs p ON p.id=s.program_id
           LEFT JOIN vouchers v ON v.id=rr.voucher_id
           WHERE rr.id=?""", (req_id,)).fetchone()


def _own_repeat_request_or_none(db, req_id):
    req = db.execute("SELECT * FROM repeat_requests WHERE id=?",
                     (req_id,)).fetchone()
    if not req or req["student_id"] != session.get("student_id"):
        return None
    return req


def create_repeat_voucher(db, req, student, course):
    """Issue the repeat fee voucher for an approved request through the
    SAME path as plan vouchers: sequential challan number + the debit
    ledger entry at creation. Caller commits. Returns the voucher id."""
    credits = (course.get("credit_theory") or 0) + (course.get("credit_lab") or 0)
    amount = int(round(repeat_fee_per_ch(db) * credits))
    title = (f"Course Repeat — {course['code']}" if req["kind"] == "Repeat"
             else f"Course Improvement — {course['code']}")
    challan = next_challan_no(db)
    vid = db.insert(
        """INSERT INTO vouchers (student_id,challan_no,title,amount,due_date,status,remarks,
           session_id,semester_no,kind,repeat_request_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (student["id"], challan, title, amount, _add_days(_today(), 14),
         "Pending", "", req["target_session_id"], course["semester_no"],
         "Repeat", req["id"]))
    v = {"id": vid, "student_id": student["id"], "challan_no": challan,
         "title": title}
    ledger_add(db, v, _today(), f"{title} charged", debit=amount)
    return vid


def activate_repeat_request(db, req_id):
    """Payment activation for a repeat request, called from the voucher
    verification success point (inside its commit). Idempotent: only an
    'Approved' request flips to 'Enrolled', and the target-session
    enrollment is created only if missing. Returns True when it ran."""
    req = db.execute("SELECT * FROM repeat_requests WHERE id=?",
                     (req_id,)).fetchone()
    if not req or req["status"] != "Approved":
        return False
    db.execute("UPDATE repeat_requests SET status='Enrolled' WHERE id=?",
               (req_id,))
    course = db.execute("SELECT * FROM courses WHERE id=?",
                        (req["course_id"],)).fetchone()
    sess = db.execute("SELECT name FROM academic_sessions WHERE id=?",
                      (req["target_session_id"],)).fetchone()
    if course and sess:
        enr = db.execute(
            """SELECT id FROM enrollments WHERE student_id=? AND course_id=?
               AND session_name=?""",
            (req["student_id"], req["course_id"], sess["name"])).fetchone()
        if not enr:
            db.insert(
                """INSERT INTO enrollments (student_id,course_id,session_name,
                   semester_no) VALUES (?,?,?,?)""",
                (req["student_id"], req["course_id"], sess["name"],
                 course["semester_no"]))
    return True


# ------------------------------------------------------------ student side
@app.route("/student/repeat")
@role_required("student")
def student_repeat():
    db = get_db()
    sid = session.get("student_id")
    student = student_full(db, sid)
    if not student:
        flash("No student record is linked to this login.", "error")
        return redirect(url_for("logout"))
    sessions = db.execute(
        "SELECT * FROM academic_sessions ORDER BY id").fetchall()
    my_requests = [_repeat_request_full(db, r["id"]) for r in db.execute(
        "SELECT id FROM repeat_requests WHERE student_id=? ORDER BY id DESC",
        (sid,)).fetchall()]
    return render_template(
        "student_repeat.html", student=student,
        eligible=repeat_eligibility(db, sid), sessions=sessions,
        my_requests=my_requests, rate=repeat_fee_per_ch(db))


@app.route("/student/repeat/apply", methods=["POST"])
@role_required("student")
def student_repeat_apply():
    db = get_db()
    sid = session.get("student_id")
    back = redirect(url_for("student_repeat"))
    course_id = _int_or_none(request.form.get("course_id"))
    target_id = _int_or_none(request.form.get("target_session_id"))
    reason = request.form.get("reason", "").strip()
    course = db.execute("SELECT * FROM courses WHERE id=?",
                        (course_id,)).fetchone() if course_id else None
    target = db.execute("SELECT * FROM academic_sessions WHERE id=?",
                        (target_id,)).fetchone() if target_id else None
    if not course or not target:
        flash("Please choose a course and a target session.", "error")
        return back
    att = latest_attempt(db, sid, course["id"])
    if not att:
        flash("That course is not eligible — only courses with a published "
              "result can be repeated or improved.", "error")
        return back
    # the original attempt's session: the result's own session, falling
    # back to the student's admission session for pre-v0.4 seeded rows
    student = student_full(db, sid)
    from_session_id = att.get("session_id") or (student or {}).get("session_id")
    if from_session_id and target["id"] == from_session_id:
        flash("The target session must be different from the session of "
              "the original attempt.", "error")
        return back
    if active_repeat_request(db, sid, course["id"]):
        flash(f"You already have an active repeat request for "
              f"{course['code']} — see My Repeat Requests below.", "error")
        return back
    enr = db.execute(
        """SELECT id FROM enrollments WHERE student_id=? AND course_id=?
           AND session_name=?""", (sid, course["id"], target["name"])).fetchone()
    if enr:
        flash(f"You are already enrolled in {course['code']} for "
              f"{target['name']}.", "error")
        return back
    bands = get_grade_bands(db)
    grade, _gp = result_grade_gp(att, bands)
    if grade is None:
        flash("That course is not eligible for a repeat application.",
              "error")
        return back
    kind = "Repeat" if grade == "F" else "Improvement"
    db.insert(
        """INSERT INTO repeat_requests (student_id,course_id,from_session_id,
           target_session_id,kind,reason,status,created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (sid, course["id"], att.get("session_id"), target["id"], kind,
         reason or None, "Requested", _now()))
    db.commit()
    log_audit("repeat_requested", f"{kind} — {course['code']}")
    flash(f"{kind} request for {course['code']} submitted — the admin "
          f"office will review it and issue the fee voucher on approval.",
          "ok")
    return back


@app.route("/student/repeat/<int:req_id>/cancel", methods=["POST"])
@role_required("student")
def student_repeat_cancel(req_id):
    db = get_db()
    req = _own_repeat_request_or_none(db, req_id)
    if not req:
        flash("That repeat request does not belong to your account.",
              "error")
        return redirect(url_for("student_repeat"))
    if req["status"] != "Requested":
        flash("Only a request that is still awaiting review can be "
              "cancelled — an approved request already has a voucher "
              "issued against it.", "error")
        return redirect(url_for("student_repeat"))
    db.execute("UPDATE repeat_requests SET status='Cancelled' WHERE id=?",
               (req_id,))
    db.commit()
    log_audit("repeat_request_cancelled", f"Request #{req_id}")
    flash("Repeat request cancelled.", "ok")
    return redirect(url_for("student_repeat"))


# -------------------------------------------------------------- admin side
@app.route("/admin/repeat")
@role_required("admin")
def admin_repeat():
    db = get_db()
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()
    sql = ("SELECT rr.id FROM repeat_requests rr "
           "JOIN students s ON s.id=rr.student_id WHERE 1=1")
    params = []
    if status in REPEAT_STATUSES:
        sql += " AND rr.status=?"
        params.append(status)
    if q:
        sql += f" AND (s.name {LIKE} ? OR s.registration_no {LIKE} ?)"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY rr.id DESC"
    rows = [_repeat_request_full(db, r["id"])
            for r in db.execute(sql, params).fetchall()]
    counts = {s: db.execute(
        "SELECT COUNT(*) c FROM repeat_requests WHERE status=?",
        (s,)).fetchone()["c"] for s in REPEAT_STATUSES}
    return render_template(
        "admin_repeat.html", rows=rows, counts=counts, status=status, q=q,
        statuses=REPEAT_STATUSES, rate=repeat_fee_per_ch(db))


@app.route("/admin/repeat/rate", methods=["POST"])
@role_required("admin")
def admin_repeat_rate():
    db = get_db()
    rate = _int_or_none(request.form.get("rate", "").strip())
    if rate is None or rate <= 0:
        flash("Enter a valid repeat fee per credit hour (a positive "
              "number of rupees).", "error")
        return redirect(url_for("admin_repeat"))
    set_setting(db, "repeat_fee_per_ch", str(rate))
    db.commit()
    log_audit("repeat_rate_updated", f"Repeat fee per credit hour: Rs {rate:,}")
    flash(f"Repeat fee updated to Rs {rate:,} per credit hour — this "
          f"applies to vouchers issued from now on; vouchers already "
          f"issued keep their amount.", "ok")
    return redirect(url_for("admin_repeat"))


@app.route("/admin/repeat/<int:req_id>/approve", methods=["POST"])
@role_required("admin")
def admin_repeat_approve(req_id):
    db = get_db()
    req = db.execute("SELECT * FROM repeat_requests WHERE id=?",
                     (req_id,)).fetchone()
    if not req:
        abort(404)
    back = redirect(url_for("admin_repeat"))
    if req["status"] != "Requested":
        flash("Only a request awaiting review can be approved — this "
              "one has already been decided.", "error")
        return back
    student = db.execute("SELECT * FROM students WHERE id=?",
                         (req["student_id"],)).fetchone()
    course = db.execute("SELECT * FROM courses WHERE id=?",
                        (req["course_id"],)).fetchone()
    if not student or not course:
        flash("The student or course for this request no longer exists.",
              "error")
        return back
    vid = create_repeat_voucher(db, req, student, course)
    db.execute(
        """UPDATE repeat_requests SET status='Approved', voucher_id=?,
           decided_by=?, decided_at=? WHERE id=?""",
        (vid, session.get("display_name"), _now(), req_id))
    db.commit()
    v = get_voucher(db, vid)
    log_audit("repeat_request_approved",
              f"Request #{req_id} — voucher {v['challan_no']}")
    flash(f"Request approved — repeat voucher {v['challan_no']} of "
          f"Rs {v['amount']:,} issued to {student['name']}. The student "
          f"is enrolled automatically once the payment is verified.",
          "ok")
    return back


@app.route("/admin/repeat/<int:req_id>/reject", methods=["POST"])
@role_required("admin")
def admin_repeat_reject(req_id):
    db = get_db()
    req = db.execute("SELECT * FROM repeat_requests WHERE id=?",
                     (req_id,)).fetchone()
    if not req:
        abort(404)
    back = redirect(url_for("admin_repeat"))
    if req["status"] != "Requested":
        flash("Only a request awaiting review can be rejected — this "
              "one has already been decided.", "error")
        return back
    remarks = request.form.get("admin_remarks", "").strip()
    if not remarks:
        flash("Remarks are required when rejecting — the student needs "
              "to know why.", "error")
        return back
    db.execute(
        """UPDATE repeat_requests SET status='Rejected', admin_remarks=?,
           decided_by=?, decided_at=? WHERE id=?""",
        (remarks, session.get("display_name"), _now(), req_id))
    db.commit()
    log_audit("repeat_request_rejected", f"Request #{req_id}")
    flash("Repeat request rejected.", "ok")
    return back


# ================================================================ v0.12 TIMETABLE + TRANSPORT
# Timetable: one slot = one weekly class meeting of a course, placed by
# the admin per program + semester + session. Saving is clash-checked
# (see timetable_clashes). Transport: admin-managed routes with ordered
# pickup stops; students see active routes only and can search by stop.

TIMETABLE_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
                  "Friday", "Saturday"]
_DAY_INDEX = {d: i for i, d in enumerate(TIMETABLE_DAYS)}


def _clean_time(raw):
    """Normalize a time input to zero-padded 'HH:MM' (24h), or None."""
    m = re.match(r"^(\d{1,2}):(\d{2})$", (raw or "").strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return None
    return f"{h:02d}:{mi:02d}"


def _group_slots_by_day(rows):
    """[(day, [slots...]), ...] in Monday..Saturday order, non-empty
    days only; slots inside a day sorted by start time."""
    rows = sorted(rows, key=lambda r: (_DAY_INDEX.get(r["day_of_week"], 99),
                                       r["start_time"] or ""))
    return [(d, [r for r in rows if r["day_of_week"] == d])
            for d in TIMETABLE_DAYS if any(r["day_of_week"] == d
                                            for r in rows)]


def timetable_clashes(db, cand, exclude_id=None):
    """Friendly clash messages for a candidate slot dict (keys:
    program_id, semester, session_id, faculty_id, day_of_week,
    start_time, end_time, room). Two slots overlap when they share the
    session + day and new_start < existing_end AND existing_start <
    new_end ('HH:MM' strings compare correctly) — so a slot that starts
    exactly when another ends (back-to-back) is NOT a clash. The slot
    being edited (exclude_id) never clashes with itself."""
    rows = db.execute(
        """SELECT ts.*, c.code course_code FROM timetable_slots ts
           JOIN courses c ON c.id=ts.course_id
           WHERE ts.session_id=? AND ts.day_of_week=?
             AND ts.start_time < ? AND ? < ts.end_time""",
        (cand["session_id"], cand["day_of_week"],
         cand["end_time"], cand["start_time"])).fetchall()
    msgs = []
    room_key = (cand.get("room") or "").strip().lower()
    for r in rows:
        if exclude_id and r["id"] == exclude_id:
            continue
        when = f"{r['day_of_week']} {r['start_time']}–{r['end_time']}"
        if (r["program_id"] == cand["program_id"]
                and r["semester"] == cand["semester"]):
            msgs.append(
                f"Class clash: this class (same program + semester) "
                f"already has {r['course_code']} on {when} in this "
                f"session.")
        if cand.get("faculty_id") and r.get("faculty_id") == cand["faculty_id"]:
            msgs.append(
                f"Teacher clash: the selected teacher already teaches "
                f"{r['course_code']} on {when} in this session.")
        if room_key and (r["room"] or "").strip().lower() == room_key:
            msgs.append(
                f"Room clash: room '{cand['room'].strip()}' is already "
                f"booked for {r['course_code']} on {when} in this "
                f"session.")
    out, seen = [], set()
    for msg in msgs:
        if msg not in seen:
            seen.add(msg)
            out.append(msg)
    return out


def _slot_form_context(db, prog_id, sem_no, sess_id, course_id=None):
    """Select options for the slot form for one program+semester: its
    courses, all faculty, and the teacher to preselect (the course's
    assigned teacher for the session, when course_id is known)."""
    courses = db.execute(
        "SELECT * FROM courses WHERE program_id=? AND semester_no=? "
        "ORDER BY code", (prog_id, sem_no)).fetchall() \
        if prog_id and sem_no else []
    faculty = db.execute(
        "SELECT id, full_name FROM faculty ORDER BY full_name").fetchall()
    assigned_faculty_id = None
    if course_id and sess_id:
        a = db.execute(
            "SELECT faculty_id FROM course_assignments "
            "WHERE course_id=? AND session_id=?",
            (course_id, sess_id)).fetchone()
        if a:
            assigned_faculty_id = a["faculty_id"]
    return {"courses": courses, "faculty_list": faculty,
            "assigned_faculty_id": assigned_faculty_id}


def _slot_from_form(db, form):
    """Validate the slot form -> (candidate dict, error message)."""
    prog_id = _int_or_none(form.get("program_id"))
    sem_no = _int_or_none(form.get("semester"))
    sess_id = _int_or_none(form.get("session_id"))
    course_id = _int_or_none(form.get("course_id"))
    faculty_id = _int_or_none(form.get("faculty_id"))
    day = (form.get("day_of_week") or "").strip()
    start = _clean_time(form.get("start_time"))
    end = _clean_time(form.get("end_time"))
    room = (form.get("room") or "").strip()
    if not (prog_id and sem_no and sess_id and course_id):
        return None, "Please choose the program, semester, session and course."
    course = db.execute("SELECT * FROM courses WHERE id=?",
                        (course_id,)).fetchone()
    if not course or course["program_id"] != prog_id \
            or course["semester_no"] != sem_no:
        return None, "The chosen course does not belong to that program + semester."
    if day not in TIMETABLE_DAYS:
        return None, "Please choose a day of the week (Monday to Saturday)."
    if not start or not end:
        return None, "Please give valid start and end times (HH:MM)."
    if end <= start:
        return None, "The end time must be after the start time."
    return {"program_id": prog_id, "semester": sem_no,
            "session_id": sess_id, "course_id": course_id,
            "faculty_id": faculty_id, "day_of_week": day,
            "start_time": start, "end_time": end, "room": room}, None


# ------------------------------------------------------- timetable (admin)
@app.route("/admin/timetable")
@role_required("admin")
def admin_timetable():
    db = get_db()
    programs = program_options(db)
    sessions = session_options(db)
    prog_id = _int_or_none(request.args.get("program_id"))
    if not prog_id and programs:
        prog_id = programs[0]["id"]
    sem_no = _int_or_none(request.args.get("semester")) or 1
    sess = current_session(db)
    sess_id = _int_or_none(request.args.get("session_id")) \
        or (sess["id"] if sess else None)
    rows = []
    if prog_id and sess_id:
        rows = db.execute(
            """SELECT ts.*, c.code course_code, c.title course_title,
                      f.full_name faculty_name
               FROM timetable_slots ts
               JOIN courses c ON c.id=ts.course_id
               LEFT JOIN faculty f ON f.id=ts.faculty_id
               WHERE ts.program_id=? AND ts.semester=? AND ts.session_id=?
               ORDER BY ts.start_time""",
            (prog_id, sem_no, sess_id)).fetchall()
    prog_name = next((p["name"] for p in programs if p["id"] == prog_id), "")
    sess_name = next((s["name"] for s in sessions if s["id"] == sess_id), "")
    class_courses = db.execute(
        "SELECT * FROM courses WHERE program_id=? AND semester_no=? "
        "ORDER BY code", (prog_id, sem_no)).fetchall() if prog_id else []
    return render_template(
        "admin_timetable.html", programs=programs, sessions=sessions,
        prog_id=prog_id, semester=sem_no, sess_id=sess_id,
        prog_name=prog_name, sess_name=sess_name, courses=class_courses,
        day_groups=_group_slots_by_day(rows), days=TIMETABLE_DAYS)


@app.route("/admin/timetable/new", methods=["GET", "POST"])
@role_required("admin")
def admin_timetable_new():
    db = get_db()
    if request.method == "POST":
        back = {"program_id": request.args.get("program_id")
                or request.form.get("program_id"),
                "semester": request.args.get("semester")
                or request.form.get("semester"),
                "session_id": request.args.get("session_id")
                or request.form.get("session_id")}
        cand, err = _slot_from_form(db, request.form)
        if err:
            flash(err, "error")
            return redirect(url_for("admin_timetable_new", **back))
        clashes = timetable_clashes(db, cand)
        if clashes:
            for msg in clashes:
                flash(msg, "error")
            return redirect(url_for(
                "admin_timetable_new", program_id=cand["program_id"],
                semester=cand["semester"], session_id=cand["session_id"],
                course_id=cand["course_id"]))
        db.insert(
            """INSERT INTO timetable_slots (program_id,semester,session_id,
               course_id,faculty_id,day_of_week,start_time,end_time,room,
               created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (cand["program_id"], cand["semester"], cand["session_id"],
             cand["course_id"], cand["faculty_id"], cand["day_of_week"],
             cand["start_time"], cand["end_time"], cand["room"], _now()))
        db.commit()
        log_audit("timetable_slot_created", "Timetable slot added")
        flash("Timetable slot added.", "ok")
        return redirect(url_for(
            "admin_timetable", program_id=cand["program_id"],
            semester=cand["semester"], session_id=cand["session_id"]))
    prog_id = _int_or_none(request.args.get("program_id"))
    if not prog_id:
        progs = program_options(db)
        prog_id = progs[0]["id"] if progs else None
    sem_no = _int_or_none(request.args.get("semester")) or 1
    sess = current_session(db)
    sess_id = _int_or_none(request.args.get("session_id")) \
        or (sess["id"] if sess else None)
    course_id = _int_or_none(request.args.get("course_id"))
    ctx = _slot_form_context(db, prog_id, sem_no, sess_id, course_id)
    slot = {"program_id": prog_id, "semester": sem_no,
            "session_id": sess_id, "course_id": course_id,
            "faculty_id": ctx["assigned_faculty_id"],
            "day_of_week": "Monday", "start_time": "09:00",
            "end_time": "10:00", "room": ""}
    return render_template(
        "timetable_slot_form.html", slot=slot, is_new=True,
        programs=program_options(db), sessions=session_options(db),
        days=TIMETABLE_DAYS, **ctx)


@app.route("/admin/timetable/<int:slot_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def admin_timetable_edit(slot_id):
    db = get_db()
    slot = db.execute("SELECT * FROM timetable_slots WHERE id=?",
                      (slot_id,)).fetchone()
    if not slot:
        abort(404)
    back = {"program_id": slot["program_id"], "semester": slot["semester"],
            "session_id": slot["session_id"]}
    if request.method == "POST":
        cand, err = _slot_from_form(db, request.form)
        if err:
            flash(err, "error")
            return redirect(url_for("admin_timetable_edit", slot_id=slot_id))
        clashes = timetable_clashes(db, cand, exclude_id=slot_id)
        if clashes:
            for msg in clashes:
                flash(msg, "error")
            return redirect(url_for("admin_timetable_edit", slot_id=slot_id))
        db.execute(
            """UPDATE timetable_slots SET program_id=?, semester=?,
               session_id=?, course_id=?, faculty_id=?, day_of_week=?,
               start_time=?, end_time=?, room=? WHERE id=?""",
            (cand["program_id"], cand["semester"], cand["session_id"],
             cand["course_id"], cand["faculty_id"], cand["day_of_week"],
             cand["start_time"], cand["end_time"], cand["room"], slot_id))
        db.commit()
        log_audit("timetable_slot_updated", f"Slot #{slot_id}")
        flash("Timetable slot updated.", "ok")
        return redirect(url_for("admin_timetable", **back))
    ctx = _slot_form_context(db, slot["program_id"], slot["semester"],
                             slot["session_id"], slot["course_id"])
    return render_template(
        "timetable_slot_form.html", slot=slot, is_new=False,
        programs=program_options(db), sessions=session_options(db),
        days=TIMETABLE_DAYS, **ctx)


@app.route("/admin/timetable/<int:slot_id>/delete", methods=["POST"])
@role_required("admin")
def admin_timetable_delete(slot_id):
    db = get_db()
    slot = db.execute("SELECT * FROM timetable_slots WHERE id=?",
                      (slot_id,)).fetchone()
    if not slot:
        abort(404)
    back = {"program_id": slot["program_id"], "semester": slot["semester"],
            "session_id": slot["session_id"]}
    db.execute("DELETE FROM timetable_slots WHERE id=?", (slot_id,))
    db.commit()
    log_audit("timetable_slot_deleted", f"Slot #{slot_id}")
    flash("Timetable slot deleted.", "ok")
    return redirect(url_for("admin_timetable", **back))


# ----------------------------------------------------- timetable (student)
def _student_timetable_rows(db, student_id, sess):
    """The student's own timetable rows for one session: slots whose
    course the student is enrolled in for that session (enrollments
    carry the session NAME — the same rows the Enrollments tab lists,
    narrowed to this session)."""
    if not sess:
        return []
    enrolled = {r["course_id"] for r in db.execute(
        """SELECT DISTINCT course_id FROM enrollments
           WHERE student_id=? AND session_name=?""",
        (student_id, sess["name"])).fetchall()}
    if not enrolled:
        return []
    rows = db.execute(
        """SELECT ts.*, c.code course_code, c.title course_title,
                  f.full_name faculty_name
           FROM timetable_slots ts
           JOIN courses c ON c.id=ts.course_id
           LEFT JOIN faculty f ON f.id=ts.faculty_id
           WHERE ts.session_id=?""", (sess["id"],)).fetchall()
    return [r for r in rows if r["course_id"] in enrolled]


def build_timetable_pdf(db, student_id):
    """The student's time table as a PDF, in the same green style as
    the transcript PDF and driven by the same rows as the web page."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer,
                                    Table, TableStyle)
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    student = student_full(db, student_id)
    sess = current_session(db)
    rows = _student_timetable_rows(db, student_id, sess)
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=14 * mm,
                            bottomMargin=14 * mm, leftMargin=14 * mm,
                            rightMargin=14 * mm,
                            title=f"Time Table {student['registration_no']}")
    story = _pdf_header(styles, "MY TIME TABLE (Demo)")
    green = colors.HexColor("#0b6b3a")
    grid = colors.HexColor("#b9d2c2")
    light = colors.HexColor("#eaf5ee")
    info = [["Student Name", student["name"],
             "Registration No.", student["registration_no"]],
            ["Program", student["prog_name"] or "—",
             "Department", student["dept_name"] or "—"],
            ["Session", (sess["name"] if sess else "—"),
             "Current Semester", str(student.get("current_semester") or "—")]]
    t = Table(info, colWidths=[30 * mm, 58 * mm, 30 * mm, 64 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, grid),
                           ("BACKGROUND", (0, 0), (0, -1), light),
                           ("BACKGROUND", (2, 0), (2, -1), light),
                           ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [t, Spacer(1, 5 * mm)]
    if not rows:
        story.append(Paragraph(
            "No timetable slots have been published for your courses in "
            "this session yet.", styles["BodyText"]))
    for day, day_rows in _group_slots_by_day(rows):
        story.append(Paragraph(day, styles["Heading3"]))
        data = [["Time", "Course", "Room", "Teacher"]]
        for r in day_rows:
            data.append([f"{r['start_time']} – {r['end_time']}",
                         f"{r['course_code']} — {r['course_title']}",
                         r["room"] or "—", r["faculty_name"] or "—"])
        lt = Table(data, colWidths=[32 * mm, 82 * mm, 28 * mm, 40 * mm])
        lt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, grid),
                                ("BACKGROUND", (0, 0), (-1, 0), green),
                                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                                ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        story += [lt, Spacer(1, 4 * mm)]
    story += [Spacer(1, 2 * mm),
              Paragraph(f"Generated on {_now()} by MY CUVAS (Demo) — "
                        f"system-generated, all data shown is fictional "
                        f"demo data.", styles["BodyText"])]
    doc.build(story)
    buf.seek(0)  # AFTER build() — house lesson
    return buf.getvalue()


@app.route("/student/timetable")
@role_required("student")
def student_timetable():
    db = get_db()
    sid = session.get("student_id")
    student = student_full(db, sid) if sid else None
    if not student:
        flash("No student record is linked to this login.", "error")
        return redirect(url_for("logout"))
    sess = current_session(db)
    rows = _student_timetable_rows(db, sid, sess)
    return render_template(
        "student_timetable.html", student=student, sess=sess,
        day_groups=_group_slots_by_day(rows), has_slots=bool(rows))


@app.route("/student/timetable.pdf")
@role_required("student")
def student_timetable_pdf():
    db = get_db()
    sid = session.get("student_id")
    if not sid:
        abort(404)
    student = student_full(db, sid)
    return send_file(
        io.BytesIO(build_timetable_pdf(db, sid)), as_attachment=True,
        download_name=f"timetable-{student['registration_no']}.pdf",
        mimetype="application/pdf")


# ----------------------------------------------------- timetable (faculty)
@app.route("/faculty/timetable")
@role_required("faculty")
def faculty_timetable():
    db = get_db()
    fac = _current_faculty(db)
    if not fac:
        flash("No faculty record is linked to this login.", "error")
        return redirect(url_for("logout"))
    sessions = session_options(db)
    sess = current_session(db)
    sess_id = _int_or_none(request.args.get("session_id")) \
        or (sess["id"] if sess else None)
    sess_name = next((s["name"] for s in sessions if s["id"] == sess_id), "")
    rows = []
    if sess_id:
        rows = db.execute(
            """SELECT ts.*, c.code course_code, c.title course_title,
                      p.name prog_name
               FROM timetable_slots ts
               JOIN courses c ON c.id=ts.course_id
               LEFT JOIN programs p ON p.id=ts.program_id
               WHERE ts.faculty_id=? AND ts.session_id=?
               ORDER BY ts.start_time""",
            (fac["id"], sess_id)).fetchall()
    return render_template(
        "faculty_timetable.html", faculty=fac, sessions=sessions,
        sess_id=sess_id, sess_name=sess_name,
        day_groups=_group_slots_by_day(rows), has_slots=bool(rows))


# ------------------------------------------------------- transport (admin)
def _route_or_none(db, route_id):
    return db.execute("SELECT * FROM transport_routes WHERE id=?",
                      (route_id,)).fetchone()


def _route_stops(db, route_id):
    return db.execute(
        """SELECT * FROM transport_stops WHERE route_id=?
           ORDER BY sort_order, pickup_time, id""", (route_id,)).fetchall()


def _route_form_values(form):
    return {"name": (form.get("name") or "").strip(),
            "title": (form.get("title") or "").strip(),
            "description": (form.get("description") or "").strip(),
            "is_active": 1 if form.get("is_active") else 0}


@app.route("/admin/transport")
@role_required("admin")
def admin_transport():
    db = get_db()
    routes = db.execute(
        """SELECT r.*, (SELECT COUNT(*) FROM transport_stops s
               WHERE s.route_id=r.id) stop_count
           FROM transport_routes r ORDER BY r.id""").fetchall()
    return render_template("admin_transport.html", routes=routes)


@app.route("/admin/transport/new", methods=["GET", "POST"])
@role_required("admin")
def admin_transport_new():
    db = get_db()
    if request.method == "POST":
        v = _route_form_values(request.form)
        if not v["name"]:
            flash("Please give the route a name (e.g. Route 3).", "error")
            return render_template("transport_route_form.html", route=v,
                                   is_new=True)
        db.insert(
            """INSERT INTO transport_routes (name,title,description,
               is_active,created_at) VALUES (?,?,?,?,?)""",
            (v["name"], v["title"] or None, v["description"] or None,
             v["is_active"], _now()))
        db.commit()
        log_audit("transport_route_created", f"Route '{v['name']}'")
        flash("Transport route created — now add its stops.", "ok")
        return redirect(url_for("admin_transport"))
    return render_template("transport_route_form.html",
                           route={"is_active": 1}, is_new=True)


@app.route("/admin/transport/<int:route_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def admin_transport_edit(route_id):
    db = get_db()
    route = _route_or_none(db, route_id)
    if not route:
        abort(404)
    if request.method == "POST":
        v = _route_form_values(request.form)
        if not v["name"]:
            flash("Please give the route a name (e.g. Route 3).", "error")
            return render_template("transport_route_form.html",
                                   route=dict(route, **v), is_new=False)
        db.execute(
            """UPDATE transport_routes SET name=?, title=?, description=?,
               is_active=? WHERE id=?""",
            (v["name"], v["title"] or None, v["description"] or None,
             v["is_active"], route_id))
        db.commit()
        log_audit("transport_route_updated", f"Route '{v['name']}'")
        flash("Transport route updated.", "ok")
        return redirect(url_for("admin_transport"))
    return render_template("transport_route_form.html", route=route,
                           is_new=False)


@app.route("/admin/transport/<int:route_id>/delete", methods=["POST"])
@role_required("admin")
def admin_transport_delete(route_id):
    db = get_db()
    route = _route_or_none(db, route_id)
    if not route:
        abort(404)
    stops = db.execute(
        "SELECT COUNT(*) c FROM transport_stops WHERE route_id=?",
        (route_id,)).fetchone()["c"]
    if stops:
        flash(f"Cannot delete '{route['name']}': it still has {stops} "
              f"stop(s). Delete the stops first, then the route.",
              "error")
        return redirect(url_for("admin_transport_stops", route_id=route_id))
    db.execute("DELETE FROM transport_routes WHERE id=?", (route_id,))
    db.commit()
    log_audit("transport_route_deleted", f"Route '{route['name']}'")
    flash("Transport route deleted.", "ok")
    return redirect(url_for("admin_transport"))


@app.route("/admin/transport/<int:route_id>/stops")
@role_required("admin")
def admin_transport_stops(route_id):
    db = get_db()
    route = _route_or_none(db, route_id)
    if not route:
        abort(404)
    stops = _route_stops(db, route_id)
    next_order = (stops[-1]["sort_order"] or 0) + 1 if stops else 1
    return render_template("admin_transport_stops.html", route=route,
                           stops=stops, next_order=next_order)


def _stop_form_values(db, form, route_id):
    """Validate a stop form -> (values dict, error message)."""
    name = (form.get("stop_name") or "").strip()
    pickup = _clean_time(form.get("pickup_time"))
    order = _int_or_none(form.get("sort_order"))
    if order is None:
        rows = _route_stops(db, route_id)
        order = ((rows[-1]["sort_order"] or 0) + 1) if rows else 1
    if not name:
        return None, "Please give the stop a name."
    if not pickup:
        return None, "Please give a valid pickup time (HH:MM)."
    return {"stop_name": name, "pickup_time": pickup,
            "sort_order": order}, None


@app.route("/admin/transport/<int:route_id>/stops/add", methods=["POST"])
@role_required("admin")
def admin_transport_stop_add(route_id):
    db = get_db()
    if not _route_or_none(db, route_id):
        abort(404)
    v, err = _stop_form_values(db, request.form, route_id)
    if err:
        flash(err, "error")
        return redirect(url_for("admin_transport_stops", route_id=route_id))
    db.insert(
        """INSERT INTO transport_stops (route_id,stop_name,pickup_time,
           sort_order) VALUES (?,?,?,?)""",
        (route_id, v["stop_name"], v["pickup_time"], v["sort_order"]))
    db.commit()
    log_audit("transport_stop_added", f"Stop '{v['stop_name']}'")
    flash("Stop added.", "ok")
    return redirect(url_for("admin_transport_stops", route_id=route_id))


def _stop_or_none(db, route_id, stop_id):
    return db.execute(
        "SELECT * FROM transport_stops WHERE id=? AND route_id=?",
        (stop_id, route_id)).fetchone()


@app.route("/admin/transport/<int:route_id>/stops/<int:stop_id>/edit",
           methods=["POST"])
@role_required("admin")
def admin_transport_stop_edit(route_id, stop_id):
    db = get_db()
    if not _stop_or_none(db, route_id, stop_id):
        abort(404)
    v, err = _stop_form_values(db, request.form, route_id)
    if err:
        flash(err, "error")
        return redirect(url_for("admin_transport_stops", route_id=route_id))
    db.execute(
        """UPDATE transport_stops SET stop_name=?, pickup_time=?,
           sort_order=? WHERE id=?""",
        (v["stop_name"], v["pickup_time"], v["sort_order"], stop_id))
    db.commit()
    log_audit("transport_stop_updated", f"Stop '{v['stop_name']}'")
    flash("Stop updated.", "ok")
    return redirect(url_for("admin_transport_stops", route_id=route_id))


@app.route("/admin/transport/<int:route_id>/stops/<int:stop_id>/delete",
           methods=["POST"])
@role_required("admin")
def admin_transport_stop_delete(route_id, stop_id):
    db = get_db()
    if not _stop_or_none(db, route_id, stop_id):
        abort(404)
    db.execute("DELETE FROM transport_stops WHERE id=?", (stop_id,))
    db.commit()
    log_audit("transport_stop_deleted", f"Route #{route_id} stop #{stop_id}")
    flash("Stop deleted.", "ok")
    return redirect(url_for("admin_transport_stops", route_id=route_id))


# ----------------------------------------------------- transport (student)
@app.route("/student/transport")
@role_required("student")
def student_transport():
    db = get_db()
    q = (request.args.get("q") or "").strip()
    routes = []
    for r in db.execute(
            "SELECT * FROM transport_routes WHERE COALESCE(is_active,1)=1 "
            "ORDER BY id").fetchall():
        stops = _route_stops(db, r["id"])
        match_ids = {s["id"] for s in stops
                     if q and q.lower() in (s["stop_name"] or "").lower()}
        if q and not match_ids:
            continue  # search: only routes serving a matching stop
        routes.append({"route": r, "stops": stops, "match_ids": match_ids})
    return render_template("student_transport.html", routes=routes, q=q)


# ------------------------------------------------------- v0.13 campus life
def _campus_values(db):
    return {k: (get_setting(db, k, "") or "") for k in CAMPUS_SETTING_KEYS}


def _is_valid_service_url(value):
    return value == "" or value.startswith(("http://", "https://"))


def _campus_societies(db, student_id=None):
    """Society rows for display: advisor name, approved-member count,
    pending count, and (when student_id is given) the student's own
    membership row. Only ACTIVE societies unless include_inactive."""
    rows = db.execute(
        """SELECT s.*, f.full_name advisor_name,
                  (SELECT COUNT(*) FROM society_members m
                    WHERE m.society_id=s.id AND m.status='Approved')
                      member_count,
                  (SELECT COUNT(*) FROM society_members m
                    WHERE m.society_id=s.id AND m.status='Requested')
                      pending_count
           FROM societies s
           LEFT JOIN faculty f ON f.id=s.advisor_faculty_id
           ORDER BY s.id""").fetchall()
    mine = {}
    if student_id is not None:
        mine = {m["society_id"]: m for m in db.execute(
            "SELECT * FROM society_members WHERE student_id=?",
            (student_id,)).fetchall()}
    return [{"society": s, "member_count": s["member_count"],
             "pending_count": s["pending_count"],
             "mine": mine.get(s["id"])} for s in rows]


def _society_or_none(db, society_id):
    return db.execute("SELECT * FROM societies WHERE id=?",
                      (society_id,)).fetchone()


def _society_form_values(db, form):
    adv = (form.get("advisor_faculty_id") or "").strip()
    return {"name": (form.get("name") or "").strip(),
            "description": (form.get("description") or "").strip(),
            "advisor_faculty_id": int(adv) if adv.isdigit() else None,
            "is_active": 1 if form.get("is_active") else 0}


@app.route("/admin/campus", methods=["GET", "POST"])
@role_required("admin")
def admin_campus():
    db = get_db()
    if request.method == "POST":
        values = {k: (request.form.get(k) or "").strip()
                  for k in CAMPUS_SETTING_KEYS}
        bad = [k for k in ("lms_url", "library_url", "email_url")
               if not _is_valid_service_url(values[k])]
        if bad:
            flash("Service links must start with http:// or https:// "
                  "(or be left blank) — check: "
                  + ", ".join(bad) + ".", "error")
            return render_template("admin_campus.html", values=values,
                                   pending_societies=_pending_societies(db),
                                   pending_vehicles=_pending_vehicles(db))
        for k, v in values.items():
            set_setting(db, k, v)
        db.commit()
        log_audit("campus_settings_saved", "Campus Life links & info saved")
        flash("Campus Life links & info saved.", "ok")
        return redirect(url_for("admin_campus"))
    return render_template("admin_campus.html", values=_campus_values(db),
                           pending_societies=_pending_societies(db),
                           pending_vehicles=_pending_vehicles(db))


def _pending_societies(db):
    return db.execute(
        "SELECT COUNT(*) c FROM society_members WHERE status='Requested'"
    ).fetchone()["c"]


def _pending_vehicles(db):
    return db.execute(
        "SELECT COUNT(*) c FROM vehicle_passes WHERE status='Requested'"
    ).fetchone()["c"]


@app.route("/student/campus")
@role_required("student")
def student_campus():
    db = get_db()
    sid = session.get("student_id")
    societies = [x for x in _campus_societies(db, sid)
                 if x["society"]["is_active"]]
    return render_template("student_campus.html", values=_campus_values(db),
                           societies=societies)


@app.route("/faculty/campus")
@role_required("faculty")
def faculty_campus():
    db = get_db()
    return render_template("faculty_campus.html", values=_campus_values(db))


@app.route("/student/societies/<int:society_id>/join", methods=["POST"])
@role_required("student")
def student_society_join(society_id):
    db = get_db()
    soc = _society_or_none(db, society_id)
    if not soc or not soc["is_active"]:
        abort(404)
    sid = session.get("student_id")
    existing = db.execute(
        "SELECT * FROM society_members WHERE society_id=? AND student_id=?",
        (society_id, sid)).fetchone()
    if existing:
        if existing["status"] == "Rejected":
            db.execute(
                """UPDATE society_members SET status='Requested',
                   decided_by=NULL, decided_at=NULL, created_at=?
                   WHERE id=?""", (_now(), existing["id"]))
            db.commit()
            log_audit("society_joined", f"{soc['name']} — requested again")
            flash(f"Membership of {soc['name']} requested again — "
                  "waiting for approval.", "ok")
        else:
            flash(f"You have already {'joined' if existing['status'] == 'Approved' else 'requested to join'} "
                  f"{soc['name']}.", "error")
        return redirect(url_for("student_campus"))
    db.insert(
        """INSERT INTO society_members (society_id,student_id,status,
           created_at) VALUES (?,?,?,?)""",
        (society_id, sid, "Requested", _now()))
    db.commit()
    log_audit("society_joined", f"{soc['name']} — join requested")
    flash(f"Membership of {soc['name']} requested — waiting for "
          "approval.", "ok")
    return redirect(url_for("student_campus"))


@app.route("/admin/societies")
@role_required("admin")
def admin_societies():
    db = get_db()
    return render_template("admin_societies.html",
                           societies=_campus_societies(db))


@app.route("/admin/societies/new", methods=["GET", "POST"])
@role_required("admin")
def admin_society_new():
    db = get_db()
    faculty = db.execute("SELECT * FROM faculty ORDER BY full_name").fetchall()
    if request.method == "POST":
        v = _society_form_values(db, request.form)
        if not v["name"]:
            flash("Please give the society a name.", "error")
            return render_template("society_form.html", society=v,
                                   faculty=faculty, is_new=True)
        db.insert(
            """INSERT INTO societies (name,description,advisor_faculty_id,
               is_active,created_at) VALUES (?,?,?,?,?)""",
            (v["name"], v["description"] or None, v["advisor_faculty_id"],
             v["is_active"], _now()))
        db.commit()
        log_audit("society_created", f"Society '{v['name']}'")
        flash("Society created.", "ok")
        return redirect(url_for("admin_societies"))
    return render_template("society_form.html", society={"is_active": 1},
                           faculty=faculty, is_new=True)


@app.route("/admin/societies/<int:society_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def admin_society_edit(society_id):
    db = get_db()
    soc = _society_or_none(db, society_id)
    if not soc:
        abort(404)
    faculty = db.execute("SELECT * FROM faculty ORDER BY full_name").fetchall()
    if request.method == "POST":
        v = _society_form_values(db, request.form)
        if not v["name"]:
            flash("Please give the society a name.", "error")
            v["id"] = society_id
            return render_template("society_form.html", society=v,
                                   faculty=faculty, is_new=False)
        db.execute(
            """UPDATE societies SET name=?, description=?,
               advisor_faculty_id=?, is_active=? WHERE id=?""",
            (v["name"], v["description"] or None, v["advisor_faculty_id"],
             v["is_active"], society_id))
        db.commit()
        log_audit("society_updated", f"Society '{v['name']}'")
        flash("Society saved.", "ok")
        return redirect(url_for("admin_societies"))
    return render_template("society_form.html", society=soc,
                           faculty=faculty, is_new=False)


@app.route("/admin/societies/<int:society_id>/delete", methods=["POST"])
@role_required("admin")
def admin_society_delete(society_id):
    db = get_db()
    soc = _society_or_none(db, society_id)
    if not soc:
        abort(404)
    members = db.execute(
        "SELECT COUNT(*) c FROM society_members WHERE society_id=?",
        (society_id,)).fetchone()["c"]
    if members:
        flash(f"Cannot delete {soc['name']}: it still has {members} "
              "membership record(s). Remove the members first (or just "
              "deactivate the society).", "error")
        return redirect(url_for("admin_societies"))
    db.execute("DELETE FROM societies WHERE id=?", (society_id,))
    db.commit()
    log_audit("society_deleted", f"Society '{soc['name']}'")
    flash("Society deleted.", "ok")
    return redirect(url_for("admin_societies"))


@app.route("/admin/societies/<int:society_id>/members")
@role_required("admin")
def admin_society_members(society_id):
    db = get_db()
    soc = _society_or_none(db, society_id)
    if not soc:
        abort(404)
    rows = db.execute(
        """SELECT m.*, st.name student_name, st.registration_no
           FROM society_members m
           JOIN students st ON st.id=m.student_id
           WHERE m.society_id=? ORDER BY m.id""", (society_id,)).fetchall()
    pending = [r for r in rows if r["status"] == "Requested"]
    decided = [r for r in rows if r["status"] != "Requested"]
    return render_template("admin_society_members.html", society=soc,
                           pending=pending, decided=decided)


@app.route("/admin/societies/<int:society_id>/members/<int:member_id>/<action>",
           methods=["POST"])
@role_required("admin")
def admin_society_member_decide(society_id, member_id, action):
    db = get_db()
    soc = _society_or_none(db, society_id)
    member = db.execute(
        "SELECT * FROM society_members WHERE id=? AND society_id=?",
        (member_id, society_id)).fetchone()
    if not soc or not member:
        abort(404)
    back = redirect(url_for("admin_society_members", society_id=society_id))
    if action == "remove":
        db.execute("DELETE FROM society_members WHERE id=?", (member_id,))
        db.commit()
        log_audit("society_membership_decided", f"Removed — {soc['name']}")
        flash("Membership removed.", "ok")
        return back
    if action not in ("approve", "reject"):
        abort(404)
    if member["status"] != "Requested":
        flash("That membership request has already been decided.",
              "error")
        return back
    db.execute(
        """UPDATE society_members SET status=?, decided_by=?, decided_at=?
           WHERE id=?""",
        ("Approved" if action == "approve" else "Rejected",
         session.get("display_name"), _now(), member_id))
    db.commit()
    log_audit("society_membership_decided", f"{action} — {soc['name']}")
    flash("Membership approved." if action == "approve"
          else "Membership rejected.", "ok")
    return back


# ------------------------------------------------- v0.13 vehicle entry
VEHICLE_TYPES = ("Motorcycle", "Car", "Other")


def _norm_vehicle_no(raw):
    return (raw or "").strip().upper()


def _own_vehicle_or_none(db, pass_id):
    return db.execute(
        "SELECT * FROM vehicle_passes WHERE id=? AND student_id=?",
        (pass_id, session.get("student_id"))).fetchone()


@app.route("/student/vehicle")
@role_required("student")
def student_vehicle():
    db = get_db()
    passes = db.execute(
        "SELECT * FROM vehicle_passes WHERE student_id=? ORDER BY id DESC",
        (session.get("student_id"),)).fetchall()
    return render_template("student_vehicle.html", passes=passes,
                           vehicle_types=VEHICLE_TYPES)


@app.route("/student/vehicle/apply", methods=["POST"])
@role_required("student")
def student_vehicle_apply():
    db = get_db()
    sid = session.get("student_id")
    back = redirect(url_for("student_vehicle"))
    vtype = (request.form.get("vehicle_type") or "").strip()
    vno = _norm_vehicle_no(request.form.get("vehicle_no"))
    make_model = (request.form.get("make_model") or "").strip()
    color = (request.form.get("color") or "").strip()
    if vtype not in VEHICLE_TYPES:
        flash("Please choose a vehicle type.", "error")
        return back
    if not vno:
        flash("Please enter the vehicle number (e.g. LEA-123).", "error")
        return back
    mine_live = db.execute(
        """SELECT * FROM vehicle_passes WHERE student_id=?
           AND UPPER(vehicle_no)=? AND status IN ('Requested','Approved')
           ORDER BY id LIMIT 1""", (sid, vno)).fetchone()
    if mine_live:
        art = "an" if mine_live["status"] == "Approved" else "a"
        flash(f"You already have {art} {mine_live['status'].lower()} "
              f"pass for vehicle {vno}.", "error")
        return back
    other = db.execute(
        """SELECT * FROM vehicle_passes WHERE UPPER(vehicle_no)=?
           AND status='Approved' AND student_id<>? ORDER BY id LIMIT 1""",
        (vno, sid)).fetchone()
    if other:
        flash(f"Vehicle {vno} already holds an approved entry pass for "
              "another student — one vehicle, one pass. If this is your "
              "vehicle, contact the admin office.", "error")
        return back
    db.insert(
        """INSERT INTO vehicle_passes (student_id,vehicle_type,vehicle_no,
           make_model,color,status,created_at) VALUES (?,?,?,?,?,?,?)""",
        (sid, vtype, vno, make_model or None, color or None,
         "Requested", _now()))
    db.commit()
    log_audit("vehicle_pass_applied", f"{vno} ({vtype})")
    flash("Vehicle entry pass requested — waiting for admin approval.",
          "ok")
    return back


@app.route("/admin/vehicle-passes")
@role_required("admin")
def admin_vehicle_passes():
    db = get_db()
    status = (request.args.get("status") or "").strip()
    q = (request.args.get("q") or "").strip()
    sql = """SELECT vp.*, st.name student_name, st.registration_no
             FROM vehicle_passes vp
             JOIN students st ON st.id=vp.student_id WHERE 1=1"""
    params = []
    if status in ("Requested", "Approved", "Rejected"):
        sql += " AND vp.status=?"
        params.append(status)
    if q:
        # vehicle numbers are stored UPPER-case; match them
        # case-insensitively on both backends (PG LIKE is sensitive,
        # SQLite's is not), names / reg nos as elsewhere in the app.
        sql += (" AND (UPPER(vp.vehicle_no) LIKE ? OR st.name LIKE ? "
                "OR st.registration_no LIKE ?)")
        params += [f"%{q.upper()}%", f"%{q}%", f"%{q}%"]
    sql += " ORDER BY (vp.status='Requested') DESC, vp.id DESC"
    passes = db.execute(sql, params).fetchall()
    counts = {r["status"]: r["c"] for r in db.execute(
        "SELECT status, COUNT(*) c FROM vehicle_passes GROUP BY status"
    ).fetchall()}
    return render_template("admin_vehicle_passes.html", passes=passes,
                           status=status, q=q, counts=counts)


@app.route("/admin/vehicle-passes/<int:pass_id>/approve", methods=["POST"])
@role_required("admin")
def admin_vehicle_approve(pass_id):
    db = get_db()
    vp = db.execute("SELECT * FROM vehicle_passes WHERE id=?",
                    (pass_id,)).fetchone()
    if not vp:
        abort(404)
    back = redirect(url_for("admin_vehicle_passes"))
    if vp["status"] != "Requested":
        flash("That pass has already been decided.", "error")
        return back
    valid_till = (request.form.get("valid_till") or "").strip()
    if valid_till:
        try:
            datetime.date.fromisoformat(valid_till)
        except ValueError:
            flash("Valid-till must be a valid date (YYYY-MM-DD).",
                  "error")
            return back
    else:
        today = datetime.date.today()
        try:
            valid_till = today.replace(year=today.year + 1).isoformat()
        except ValueError:  # 29 Feb -> 28 Feb next year
            valid_till = today.replace(year=today.year + 1,
                                       day=28).isoformat()
    pass_no = f"VEH-{datetime.date.today().year}-{pass_id}"
    db.execute(
        """UPDATE vehicle_passes SET status='Approved', pass_no=?,
           valid_till=?, admin_remarks=?, decided_by=?, decided_at=?
           WHERE id=?""",
        (pass_no, valid_till,
         (request.form.get("admin_remarks") or "").strip() or None,
         session.get("display_name"), _now(), pass_id))
    db.commit()
    log_audit("vehicle_pass_approved",
                f"{pass_no} — {vp['vehicle_no']}, valid till {valid_till}")
    flash(f"Pass {pass_no} approved (valid till {valid_till}).", "ok")
    return back


@app.route("/admin/vehicle-passes/<int:pass_id>/reject", methods=["POST"])
@role_required("admin")
def admin_vehicle_reject(pass_id):
    db = get_db()
    vp = db.execute("SELECT * FROM vehicle_passes WHERE id=?",
                    (pass_id,)).fetchone()
    if not vp:
        abort(404)
    back = redirect(url_for("admin_vehicle_passes"))
    if vp["status"] != "Requested":
        flash("That pass has already been decided.", "error")
        return back
    remarks = (request.form.get("admin_remarks") or "").strip()
    if not remarks:
        flash("Remarks are required when rejecting — the student needs "
              "to know why.", "error")
        return back
    db.execute(
        """UPDATE vehicle_passes SET status='Rejected', admin_remarks=?,
           decided_by=?, decided_at=? WHERE id=?""",
        (remarks, session.get("display_name"), _now(), pass_id))
    db.commit()
    log_audit("vehicle_pass_rejected", f"{vp['vehicle_no']}")
    flash("Vehicle pass rejected.", "ok")
    return back


def build_vehicle_pass_pdf(db, pass_id):
    """Vehicle entry pass PDF bytes — same card-on-A4 pattern (and the
    same green style) as the student card: pass number, student +
    vehicle identity, validity, and a Code39 barcode of the pass no."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas as pdfcanvas

    vp = db.execute("SELECT * FROM vehicle_passes WHERE id=?",
                    (pass_id,)).fetchone()
    student = student_full(db, vp["student_id"])
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4
    green = colors.HexColor("#0b6b3a")
    dark = colors.HexColor("#175732")
    grid = colors.HexColor("#b9d2c2")
    card_w, card_h = 170 * mm, 170 * mm / 1.586
    x0 = (page_w - card_w) / 2
    y_top = page_h - 30 * mm
    y0 = y_top - card_h

    c.setStrokeColor(grid)
    c.setDash(4, 3)
    c.rect(x0 - 4 * mm, y0 - 4 * mm, card_w + 8 * mm, card_h + 8 * mm,
           stroke=1, fill=0)
    c.setDash()
    c.setStrokeColor(green)
    c.setLineWidth(1.4)
    c.setFillColor(colors.white)
    c.rect(x0, y0, card_w, card_h, stroke=1, fill=1)

    band_h = 17 * mm
    c.setFillColor(green)
    c.rect(x0, y_top - band_h, card_w, band_h, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(x0 + 6 * mm, y_top - 8 * mm,
                 "MY CUVAS — Campus Management System")
    c.setFont("Helvetica", 8.5)
    c.drawString(x0 + 6 * mm, y_top - 13.5 * mm,
                 "Cholistan University of Veterinary and Animal Sciences")
    c.setFillColor(dark)
    c.setFont("Helvetica-Bold", 12.5)
    c.drawCentredString(x0 + card_w / 2, y_top - band_h - 7 * mm,
                        "VEHICLE ENTRY PASS")

    fields = [("Pass No", vp["pass_no"]),
              ("Student", student["name"] if student else "—"),
              ("Registration No",
               student["registration_no"] if student else "—"),
              ("Vehicle Type", vp["vehicle_type"]),
              ("Vehicle No", vp["vehicle_no"]),
              ("Make / Model", vp["make_model"] or "—"),
              ("Color", vp["color"] or "—"),
              ("Valid Till", vp["valid_till"] or "—")]
    fy = y_top - band_h - 16 * mm
    for label, value in fields:
        c.setFillColor(dark)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x0 + 6 * mm, fy, label)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold" if label in ("Pass No", "Vehicle No")
                    else "Helvetica", 9)
        c.drawString(x0 + 36 * mm, fy, str(value)[:52])
        fy -= 6.2 * mm

    pno = (vp["pass_no"] or "").upper()
    try:
        from reportlab.graphics.barcode import code39
        barcode = code39.Standard39(pno, checksum=0, barHeight=11 * mm,
                                    barWidth=0.42 * mm, gap=0.21 * mm)
        barcode.drawOn(c, x0 + 6 * mm, y0 + 11 * mm)
    except Exception:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x0 + 6 * mm, y0 + 13 * mm, pno)
    c.setFillColor(dark)
    c.setFont("Helvetica-Oblique", 8.5)
    c.drawRightString(x0 + card_w - 6 * mm, y0 + 6 * mm,
                      "Show at the campus gate on entry")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 8)
    c.drawString(x0, y0 - 12 * mm,
                 f"Generated on {_now()} by MY CUVAS (Demo) — "
                 f"system-generated pass, all data shown is fictional "
                 f"demo data.")
    c.showPage()
    c.save()
    buf.seek(0)  # AFTER save() — house lesson
    return buf.getvalue()


@app.route("/student/vehicle/<int:pass_id>/pass.pdf")
@role_required("student")
def student_vehicle_pass_pdf(pass_id):
    db = get_db()
    vp = _own_vehicle_or_none(db, pass_id)
    if not vp or vp["status"] != "Approved":
        abort(404)
    return send_file(io.BytesIO(build_vehicle_pass_pdf(db, pass_id)),
                     as_attachment=True,
                     download_name=f"vehicle-pass-{vp['pass_no']}.pdf",
                     mimetype="application/pdf")


# ================================================================ v0.14 REPORTS,
# AUDIT LOG & BACKUP
# Reports centre: four admin reports whose figures come from the SAME
# computations as the screens they summarise (the ledger behind the
# Account Statement, result_grade_gp for grades, the shared
# attendance_summary helper), each with an Excel export. The audit log
# is append-only: log_audit() above is its only writer. Backup is a
# ZIP with one workbook (a sheet per table — password hashes are never
# included) plus the stored file blobs; restore is manual by design.

XLSX_MIME = ("application/vnd.openxmlformats-officedocument."
             "spreadsheetml.sheet")


def _xlsx_download(wb, filename):
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype=XLSX_MIME)


def _report_session(db):
    """Session for a report: the explicit ?session_id= when valid,
    else the current session (the same rule as the rest of the app)."""
    sid = _int_or_none(request.args.get("session_id"))
    if sid:
        row = db.execute("SELECT * FROM academic_sessions WHERE id=?",
                         (sid,)).fetchone()
        if row:
            return row
    return current_session(db)


# ------------------------------------------------------------- fee collection
def _fee_report(db, sess):
    """Fee collection figures for one session, computed from the
    append-only ledger joined to that session's vouchers — exactly the
    Account Statement semantics (a split reverses the parent debit and
    debits the children, so ledger sums are always the live totals)."""
    data = {"session": sess, "issued_count": 0, "issued_rs": 0,
            "collected_rs": 0, "outstanding_rs": 0, "pending_proof": 0,
            "paid_rs": 0, "cross_outstanding": 0,
            "departments": [], "defaulters": []}
    if not sess:
        return data
    sid = sess["id"]
    vouchers = db.execute("SELECT * FROM vouchers WHERE session_id=?",
                          (sid,)).fetchall()
    live = [v for v in vouchers if v["status"] != "Split into Installments"]
    data["issued_count"] = len(live)
    data["pending_proof"] = sum(
        1 for v in vouchers if v["status"] == "Proof Submitted")
    data["paid_rs"] = sum(v["amount"] or 0 for v in live
                           if v["status"] == "Paid")
    agg = db.execute(
        """SELECT COALESCE(SUM(l.debit),0) d, COALESCE(SUM(l.credit),0) c
           FROM ledger_entries l JOIN vouchers v ON v.id=l.voucher_id
           WHERE v.session_id=?""", (sid,)).fetchone()
    data["issued_rs"] = agg["d"] or 0
    data["collected_rs"] = agg["c"] or 0
    data["outstanding_rs"] = data["issued_rs"] - data["collected_rs"]
    # per-student figures for THIS session's vouchers only
    per = {}
    for r in db.execute(
            """SELECT l.student_id sid, COALESCE(SUM(l.debit),0) d,
                      COALESCE(SUM(l.credit),0) c
               FROM ledger_entries l JOIN vouchers v ON v.id=l.voucher_id
               WHERE v.session_id=? GROUP BY l.student_id""",
            (sid,)).fetchall():
        per[r["sid"]] = {"issued": r["d"] or 0, "collected": r["c"] or 0}
    students = {s["id"]: s for s in db.execute(
        """SELECT s.*, d.name dept_name FROM students s
           LEFT JOIN departments d ON d.id=s.department_id""").fetchall()}
    by_dept = {}
    for st_id, f in per.items():
        st = students.get(st_id)
        dept = (st["dept_name"] if st else None) or "—"
        d = by_dept.setdefault(dept, {"department": dept, "issued": 0,
                                       "collected": 0, "outstanding": 0})
        d["issued"] += f["issued"]
        d["collected"] += f["collected"]
        d["outstanding"] += f["issued"] - f["collected"]
    data["departments"] = sorted(by_dept.values(),
                                  key=lambda d: d["department"])
    in_session = [s for s in students.values()
                  if s.get("session_id") == sid]
    def _out(st_id):
        f = per.get(st_id)
        return (f["issued"] - f["collected"]) if f else 0
    data["cross_outstanding"] = sum(_out(s["id"]) for s in in_session)
    defaulters = [{"name": s["name"],
                   "registration_no": s["registration_no"],
                   "department": s["dept_name"] or "—",
                   "phone": s.get("phone") or "—",
                   "outstanding": _out(s["id"])}
                  for s in in_session if _out(s["id"]) > 0]
    data["defaulters"] = sorted(defaulters,
                                 key=lambda d: -d["outstanding"])
    return data


@app.route("/admin/reports")
@role_required("admin", "accounts", "coe")
def admin_reports():
    db = get_db()
    last_backup = db.execute(
        "SELECT created_at FROM audit_log WHERE action='backup_downloaded' "
        "ORDER BY id DESC LIMIT 1").fetchone()
    audit_count = db.execute(
        "SELECT COUNT(*) c FROM audit_log").fetchone()["c"]
    return render_template("admin_reports.html", generated=_now(),
                           last_backup=(last_backup["created_at"]
                                        if last_backup else None),
                           audit_count=audit_count)


@app.route("/admin/reports/fees")
@role_required("admin", "accounts")
def admin_report_fees():
    db = get_db()
    sess = _report_session(db)
    return render_template(
        "admin_report_fees.html", generated=_now(),
        sessions=session_options(db), sess=sess,
        rep=_fee_report(db, sess))


@app.route("/admin/reports/fees.xlsx")
@role_required("admin", "accounts")
def admin_report_fees_xlsx():
    db = get_db()
    sess = _report_session(db)
    rep = _fee_report(db, sess)
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Fee Collection Report"])
    ws.append(["Session", sess["name"] if sess else "—"])
    ws.append(["Generated On", _now()])
    ws.append(["Challans Issued", rep["issued_count"]])
    ws.append(["Total Issued (Rs)", rep["issued_rs"]])
    ws.append(["Total Collected (Rs)", rep["collected_rs"]])
    ws.append(["Total Outstanding (Rs)", rep["outstanding_rs"]])
    ws.append(["Pending Proofs", rep["pending_proof"]])
    ws2 = wb.create_sheet("By Department")
    ws2.append(["Department", "Issued (Rs)", "Collected (Rs)",
                "Outstanding (Rs)"])
    for d in rep["departments"]:
        ws2.append([d["department"], d["issued"], d["collected"],
                    d["outstanding"]])
    ws3 = wb.create_sheet("Defaulters")
    ws3.append(["Name", "Registration No", "Department", "Phone",
                "Outstanding (Rs)"])
    for d in rep["defaulters"]:
        ws3.append([d["name"], d["registration_no"], d["department"],
                    d["phone"], d["outstanding"]])
    return _xlsx_download(wb, "fee-collection-report.xlsx")


# ------------------------------------------------------------- student strength
def _students_report(db):
    total = db.execute("SELECT COUNT(*) c FROM students").fetchone()["c"]

    def breakdown(sql):
        return [{"label": r["label"], "count": r["c"]} for r in
                db.execute(sql).fetchall()]

    by_dept = breakdown(
        """SELECT COALESCE(d.name,'—') label, COUNT(*) c FROM students s
           LEFT JOIN departments d ON d.id=s.department_id
           GROUP BY label ORDER BY c DESC, label""")
    by_prog = breakdown(
        """SELECT COALESCE(p.name,'—') label, COUNT(*) c FROM students s
           LEFT JOIN programs p ON p.id=s.program_id
           GROUP BY label ORDER BY c DESC, label""")
    by_sess = breakdown(
        """SELECT COALESCE(ss.name, s.session_name, '—') label, COUNT(*) c
           FROM students s
           LEFT JOIN academic_sessions ss ON ss.id=s.session_id
           GROUP BY label ORDER BY c DESC, label""")
    by_gender = breakdown(
        """SELECT COALESCE(NULLIF(s.gender,''),'Not recorded') label,
                  COUNT(*) c FROM students s
           GROUP BY label ORDER BY c DESC, label""")
    programs = db.execute("SELECT * FROM programs ORDER BY name").fetchall()
    sessions = db.execute(
        "SELECT * FROM academic_sessions ORDER BY id").fetchall()
    counts = {}
    for r in db.execute(
            """SELECT program_id, session_id, COUNT(*) c FROM students
               GROUP BY program_id, session_id""").fetchall():
        counts[(r["program_id"], r["session_id"])] = r["c"]
    matrix = []
    for p in programs:
        cells = [counts.get((p["id"], s["id"]), 0) for s in sessions]
        matrix.append({"program": p["name"], "cells": cells,
                       "total": sum(cells)})
    return {"total": total, "by_department": by_dept,
            "by_program": by_prog, "by_session": by_sess,
            "by_gender": by_gender, "sessions": sessions,
            "matrix": matrix}


@app.route("/admin/reports/students")
@role_required("admin")
def admin_report_students():
    db = get_db()
    return render_template("admin_report_students.html", generated=_now(),
                           rep=_students_report(db))


@app.route("/admin/reports/students.xlsx")
@role_required("admin")
def admin_report_students_xlsx():
    db = get_db()
    rep = _students_report(db)
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Student Strength Report"])
    ws.append(["Generated On", _now()])
    ws.append(["Total Students", rep["total"]])
    for title, rows in (("By Department", rep["by_department"]),
                        ("By Program", rep["by_program"]),
                        ("By Session", rep["by_session"]),
                        ("By Gender", rep["by_gender"])):
        w = wb.create_sheet(title)
        w.append([title.replace("By ", ""), "Students"])
        for r in rows:
            w.append([r["label"], r["count"]])
    wm = wb.create_sheet("Program x Session")
    wm.append(["Program"] + [s["name"] for s in rep["sessions"]]
              + ["Total"])
    for row in rep["matrix"]:
        wm.append([row["program"]] + row["cells"] + [row["total"]])
    return _xlsx_download(wb, "student-strength-report.xlsx")


# ------------------------------------------------------------- results summary
def _results_report(db, sess):
    rows = []
    if not sess:
        return rows
    bands = get_grade_bands(db)
    groups = {}
    for r in db.execute(
            """SELECT r.*, c.code, c.title FROM results r
               JOIN courses c ON c.id=r.course_id
               WHERE r.session_id=? ORDER BY c.code, r.semester_no""",
            (sess["id"],)).fetchall():
        groups.setdefault((r["course_id"], r["semester_no"]),
                          []).append(r)
    for (cid, sem), rs in groups.items():
        appeared = len(rs)
        passed = 0
        marks = []
        for r in rs:
            grade, _gp = result_grade_gp(r, bands)
            if grade and grade != "F":
                passed += 1
            if not r.get("is_absent") and r.get("marks_obtained") is not None:
                marks.append(float(r["marks_obtained"]))
        state, _pub, _tot = _result_set_state(db, cid, sem, sess["id"])
        rows.append({
            "course_code": rs[0]["code"], "course_title": rs[0]["title"],
            "semester_no": sem, "appeared": appeared, "passed": passed,
            "failed": appeared - passed,
            "pass_pct": round(passed / appeared * 100, 1) if appeared else 0.0,
            "avg_marks": (round(sum(marks) / len(marks), 1)
                          if marks else None),
            "highest": max(marks) if marks else None,
            "published": "Yes" if state == "Published" else "No"})
    return rows


@app.route("/admin/reports/results")
@role_required("admin", "coe")
def admin_report_results():
    db = get_db()
    sess = _report_session(db)
    return render_template(
        "admin_report_results.html", generated=_now(),
        sessions=session_options(db), sess=sess,
        rows=_results_report(db, sess))


@app.route("/admin/reports/results.xlsx")
@role_required("admin", "coe")
def admin_report_results_xlsx():
    db = get_db()
    sess = _report_session(db)
    rows = _results_report(db, sess)
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Results Summary"
    ws.append(["Results Summary — " + (sess["name"] if sess else "—")])
    ws.append(["Generated On", _now()])
    ws.append(["Course", "Title", "Semester", "Appeared", "Passed",
               "Failed", "Pass %", "Average Marks", "Highest Marks",
               "Published"])
    for r in rows:
        ws.append([r["course_code"], r["course_title"], r["semester_no"],
                   r["appeared"], r["passed"], r["failed"], r["pass_pct"],
                   r["avg_marks"], r["highest"], r["published"]])
    return _xlsx_download(wb, "results-summary-report.xlsx")


# ------------------------------------------------------------- attendance summary
def _attendance_report(db, sess):
    rows = []
    if not sess:
        return rows
    for a in db.execute(
            """SELECT a.*, c.code course_code, c.title course_title,
                      c.program_id, c.semester_no,
                      f.full_name teacher_name, p.name prog_name
               FROM course_assignments a
               JOIN courses c ON c.id=a.course_id
               LEFT JOIN programs p ON p.id=c.program_id
               LEFT JOIN faculty f ON f.id=a.faculty_id
               WHERE a.session_id=? ORDER BY c.code""",
            (sess["id"],)).fetchall():
        classes_held, srows = _attendance_summary_rows(db, a)
        avg = (round(sum(r["pct"] for r in srows) / len(srows), 1)
               if srows else 0.0)
        rows.append({"course_code": a["course_code"],
                     "course_title": a["course_title"],
                     "teacher_name": a["teacher_name"] or "—",
                     "prog_name": a["prog_name"] or "—",
                     "semester_no": a["semester_no"],
                     "classes_held": classes_held,
                     "students": len(srows), "avg_pct": avg})
    return rows


@app.route("/admin/reports/attendance")
@role_required("admin", "coe")
def admin_report_attendance():
    db = get_db()
    sess = _report_session(db)
    return render_template(
        "admin_report_attendance.html", generated=_now(),
        sessions=session_options(db), sess=sess,
        rows=_attendance_report(db, sess))


@app.route("/admin/reports/attendance.xlsx")
@role_required("admin", "coe")
def admin_report_attendance_xlsx():
    db = get_db()
    sess = _report_session(db)
    rows = _attendance_report(db, sess)
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance Summary"
    ws.append(["Attendance Summary — " + (sess["name"] if sess else "—")])
    ws.append(["Generated On", _now()])
    ws.append(["Course", "Title", "Teacher", "Semester", "Classes Held",
               "Students", "Average Attendance %"])
    for r in rows:
        ws.append([r["course_code"], r["course_title"], r["teacher_name"],
                   r["semester_no"], r["classes_held"], r["students"],
                   r["avg_pct"]])
    return _xlsx_download(wb, "attendance-summary-report.xlsx")


# ------------------------------------------------------------- audit log viewer
@app.route("/admin/audit")
@role_required("admin")
def admin_audit():
    db = get_db()
    q = (request.args.get("q") or "").strip()
    role = (request.args.get("role") or "").strip()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    clauses, params = [], []
    if q:
        like = f"%{q}%"
        clauses.append(f"(username {LIKE} ? OR action {LIKE} ? OR "
                       f"details {LIKE} ?)")
        params += [like, like, like]
    if role:
        clauses.append("role=?")
        params.append(role)
    if date_from:
        clauses.append("substr(created_at,1,10)>=?")
        params.append(date_from)
    if date_to:
        clauses.append("substr(created_at,1,10)<=?")
        params.append(date_to)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    total = db.execute(f"SELECT COUNT(*) c FROM audit_log{where}",
                       params).fetchone()["c"]
    rows = db.execute(
        f"SELECT * FROM audit_log{where} ORDER BY id DESC LIMIT 300",
        params).fetchall()
    roles = [r["role"] for r in db.execute(
        "SELECT DISTINCT role FROM audit_log WHERE role<>'' "
        "ORDER BY role").fetchall()]
    return render_template(
        "admin_audit.html", rows=rows, total=total, capped=total > 300,
        roles=roles, q=q, role=role, date_from=date_from, date_to=date_to,
        generated=_now())


# ------------------------------------------------------------- backup
# (table, sheet name) — a sheet is included only when the table exists.
BACKUP_SHEETS = [
    ("departments", "departments"), ("programs", "programs"),
    ("academic_sessions", "sessions"), ("courses", "courses"),
    ("students", "students"), ("faculty", "faculty"),
    ("users", "users"), ("certificates", "certificates"),
    ("enrollments", "enrollments"), ("results", "results"),
    ("fee_heads", "fee_heads"), ("fee_plans", "fee_plans"),
    ("fee_plan_lines", "fee_plan_lines"), ("vouchers", "vouchers"),
    ("ledger_entries", "ledger"), ("grade_bands", "grade_bands"),
    ("student_documents", "student_documents"), ("tickets", "tickets"),
    ("ticket_messages", "ticket_messages"),
    ("repository_docs", "repository_docs"),
    ("notifications", "notifications"),
    ("course_assignments", "course_assignments"),
    ("attendance", "attendance"),
    ("clearance_units", "clearance_units"),
    ("clearance_requests", "clearance_requests"),
    ("clearance_items", "clearance_items"),
    ("scholarship_schemes", "scholarship_schemes"),
    ("scholarship_profiles", "scholarship_profiles"),
    ("scholarship_applications", "scholarship_applications"),
    ("repeat_requests", "repeat_requests"),
    ("timetable_slots", "timetable_slots"),
    ("transport_routes", "transport_routes"),
    ("transport_stops", "transport_stops"),
    ("societies", "societies"), ("society_members", "society_members"),
    ("vehicle_passes", "vehicle_passes"),
    ("app_settings", "app_settings"), ("counters", "counters"),
    ("audit_log", "audit_log"), ("login_attempts", "login_attempts"),
]
# Columns never written to a backup: password hashes (never exportable)
# and stored file bytes (the files themselves travel under files/).
BACKUP_DROP_COLUMNS = {
    "users": {"password_hash"},
    "student_documents": {"file_data"},
    "repository_docs": {"file_data"},
    "vouchers": {"proof_blob"},
}


def _table_columns(db, table):
    if PG:
        return [r["column_name"] for r in db.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema='public' AND table_name=?
               ORDER BY ordinal_position""", (table,)).fetchall()]
    return [r["name"] for r in db.execute(
        f"PRAGMA table_info({table})").fetchall()]


def _backup_cell(value):
    if isinstance(value, (bytes, memoryview)):
        return ""
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return value


def _safe_filename(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name or "file")


def _backup_files(db):
    """(arcname, bytes) for every stored blob: student documents,
    repository files and voucher paid proofs."""
    out = []
    for table, blob_col, name_col in (
            ("student_documents", "file_data", "file_name"),
            ("repository_docs", "file_data", "file_name"),
            ("vouchers", "proof_blob", "proof_filename")):
        for r in db.execute(
                f"SELECT id, {name_col} name, {blob_col} blob FROM {table} "
                f"WHERE {blob_col} IS NOT NULL").fetchall():
            if r["blob"]:
                out.append((f"{table}-{r['id']}-"
                            f"{_safe_filename(r['name'])}",
                            bytes(r["blob"])))
    return out


# ------------------------------------------------- staff management (v0.15)
STAFF_ROLES = ("accounts", "coe")
STAFF_ROLE_LABELS = {"admin": "Admin",
                     "accounts": "Accounts Office",
                     "coe": "Controller of Examinations"}


def _staff_user_or_none(db, user_id):
    row = db.execute(
        "SELECT * FROM users WHERE id=? AND role IN ('admin','accounts','coe')",
        (user_id,)).fetchone()
    return row


@app.route("/admin/staff", methods=["GET", "POST"])
@role_required("admin")
def admin_staff():
    """Admin-only management of the staff logins (admin / accounts /
    coe): create office logins, reset their passwords, and
    activate / deactivate them. The primary 'admin' account can
    never be deactivated."""
    db = get_db()
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        display_name = request.form.get("display_name", "").strip()
        role = request.form.get("role", "").strip()
        password = (request.form.get("password") or "").strip()
        if not username or not display_name:
            flash("Username and display name are required.", "error")
        elif role not in STAFF_ROLES:
            flash("Choose a staff role (Accounts Office or Controller "
                  "of Examinations).", "error")
        elif db.execute("SELECT id FROM users WHERE username=?",
                        (username,)).fetchone():
            flash(f"A login with username '{username}' already exists.",
                  "error")
        else:
            pw_err = password_policy_error(password)
            if pw_err:
                flash(f"Could not create staff login: {pw_err}", "error")
            else:
                db.insert(
                    """INSERT INTO users (username,password_hash,role,
                       display_name) VALUES (?,?,?,?)""",
                    (username, generate_password_hash(password), role,
                     display_name))
                db.commit()
                log_audit("staff_created",
                          f"Staff login '{username}' "
                          f"({STAFF_ROLE_LABELS[role]}) for {display_name}")
                flash(f"Staff login '{username}' created for "
                      f"{display_name} ({STAFF_ROLE_LABELS[role]}). "
                      f"Password: {password} — shown ONCE, note it now.",
                      "ok")
                return redirect(url_for("admin_staff"))
    rows = db.execute(
        """SELECT * FROM users WHERE role IN ('admin','accounts','coe')
           ORDER BY CASE role WHEN 'admin' THEN 0 WHEN 'accounts' THEN 1
           ELSE 2 END, username""").fetchall()
    return render_template("admin_staff.html", rows=rows,
                           staff_roles=STAFF_ROLES,
                           role_labels=STAFF_ROLE_LABELS)


@app.route("/admin/staff/<int:user_id>/reset-password", methods=["POST"])
@role_required("admin")
def admin_staff_reset_password(user_id):
    db = get_db()
    user = _staff_user_or_none(db, user_id)
    if not user:
        flash("Staff login not found.", "error")
        return redirect(url_for("admin_staff"))
    chosen_pw = request.form.get("new_password", "").strip()
    if chosen_pw:
        pw_err = password_policy_error(chosen_pw)
        if pw_err:
            flash(f"Could not reset password: {pw_err}", "error")
            return redirect(url_for("admin_staff"))
        pw = chosen_pw
    else:
        pw = generate_password()
    db.execute("UPDATE users SET password_hash=? WHERE id=?",
               (generate_password_hash(pw), user_id))
    db.commit()
    log_audit("staff_password_reset",
              f"Password reset for staff login '{user['username']}'")
    flash(f"Password reset for '{user['username']}' "
          f"({user['display_name']}). New password: {pw} — shown ONCE, "
          f"note it now.", "ok")
    return redirect(url_for("admin_staff"))


@app.route("/admin/staff/<int:user_id>/toggle-active", methods=["POST"])
@role_required("admin")
def admin_staff_toggle_active(user_id):
    db = get_db()
    user = _staff_user_or_none(db, user_id)
    if not user:
        flash("Staff login not found.", "error")
        return redirect(url_for("admin_staff"))
    if user["username"] == "admin":
        flash("The primary admin account cannot be deactivated.", "error")
        return redirect(url_for("admin_staff"))
    if user["id"] == session.get("user_id"):
        flash("You cannot deactivate your own login.", "error")
        return redirect(url_for("admin_staff"))
    new_state = 0 if user.get("is_active", 1) else 1
    db.execute("UPDATE users SET is_active=? WHERE id=?",
               (new_state, user_id))
    db.commit()
    log_audit("staff_activated" if new_state else "staff_deactivated",
              f"Staff login '{user['username']}' "
              f"({STAFF_ROLE_LABELS.get(user['role'], user['role'])})")
    flash(f"Staff login '{user['username']}' "
          f"{'activated' if new_state else 'deactivated'}.", "ok")
    return redirect(url_for("admin_staff"))


@app.route("/admin/backup")
@role_required("admin")
def admin_backup():
    db = get_db()
    last = db.execute(
        "SELECT * FROM audit_log WHERE action='backup_downloaded' "
        "ORDER BY id DESC LIMIT 1").fetchone()
    return render_template(
        "admin_backup.html", last_backup=last, generated=_now(),
        show_demo_accounts=get_setting(db, "show_demo_accounts", "1"))


@app.route("/admin/backup/demo-accounts", methods=["POST"])
@role_required("admin")
def admin_backup_demo_toggle():
    """Go-Live toggle: show / hide the demo-accounts box (with the
    demo passwords) on the PUBLIC homepage."""
    db = get_db()
    show = "1" if request.form.get("show_demo_accounts") else "0"
    set_setting(db, "show_demo_accounts", show)
    db.commit()
    log_audit("demo_accounts_toggled",
              "Homepage demo accounts box "
              + ("shown" if show == "1" else "hidden"))
    flash("Homepage demo accounts box is now "
          + ("SHOWN — remember to hide it at go-live."
             if show == "1" else "hidden."), "ok")
    return redirect(url_for("admin_backup"))


@app.route("/admin/backup/download")
@role_required("admin")
def admin_backup_download():
    db = get_db()
    import zipfile
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    sheet_names = []
    for table, sheet in BACKUP_SHEETS:
        cols = [c for c in _table_columns(db, table)
                if c not in BACKUP_DROP_COLUMNS.get(table, set())]
        if not cols:
            continue  # table does not exist in this database
        ws = wb.create_sheet(sheet[:31])
        ws.append(cols)
        order = " ORDER BY id" if "id" in cols else ""
        for r in db.execute(
                f"SELECT {', '.join(cols)} FROM {table}{order}").fetchall():
            ws.append([_backup_cell(r[c]) for c in cols])
        sheet_names.append(sheet)
    if not sheet_names:
        ws = wb.create_sheet("empty")
        ws.append(["No tables found"])
        sheet_names.append("empty")
    xbuf = io.BytesIO()
    wb.save(xbuf)
    files = _backup_files(db)
    readme = (
        "MY CUVAS — Full Data Backup\n"
        f"Generated: {_now()}\n\n"
        "Contents\n"
        "--------\n"
        "cuvas-backup.xlsx — one sheet per database table:\n"
        + "".join(f"  - {s}\n" for s in sheet_names)
        + f"files/ — {len(files)} stored file(s) from the database "
          "(student documents, repository files, voucher paid proofs), "
          "named <table>-<id>-<original filename>.\n\n"
        "Notes\n"
        "-----\n"
        "- Passwords are NEVER included: the users sheet omits the "
        "password_hash column, so logins cannot be restored from this "
        "backup.\n"
        "- Document / repository tables appear as metadata only; the "
        "file bytes themselves are under files/.\n"
        "- Restore is manual / by a developer — the app has no "
        "automatic restore.\n")
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("cuvas-backup.xlsx", xbuf.getvalue())
        for arc, blob in files:
            z.writestr(f"files/{arc}", blob)
        z.writestr("README.txt", readme)
    zbuf.seek(0)
    log_audit("backup_downloaded",
              f"Full backup downloaded: {len(sheet_names)} sheets, "
              f"{len(files)} stored file(s)")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    return send_file(zbuf, as_attachment=True,
                     download_name=f"cuvas-backup-{stamp}.zip",
                     mimetype="application/zip")


# ================================================================
# PREVIEW SAMPLE — Premium Minimal Academic theme (pending decision)
# Additive only: three routes + templates/academic_*.html +
# static/academic.css + brand_assets.py. The live theme
# (static/style.css and every existing template) is untouched, and
# sign-in reuses the shared _sign_in/_start_session/_locked_flash
# helpers exactly like /login (same lockout + audit behaviour).
# ================================================================
import brand_assets


@app.route("/brand/cuvas-logo.jpg")
def brand_cuvas_logo_jpg():
    """The official CUVAS logo (user-supplied JPG), served byte-
    identical from the base64 text module brand_assets.py — the
    GitHub connector cannot push binary files."""
    resp = send_file(io.BytesIO(brand_assets.logo_jpg_bytes()),
                     mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/preview/academic/login", methods=["GET", "POST"])
def academic_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user, state = _sign_in(db, username, password)
        if state == "locked":
            _locked_flash(username)
            return render_template("academic_login.html")
        if state == "ok":
            _start_session(user)
            if user["role"] == "admin":
                return redirect(url_for("academic_admin"))
            flash("This design preview is admin-only; you have been "
                  "signed in to your normal home instead.", "error")
            return redirect(url_for(home_for_role()))
        flash("Invalid username or password.", "error")
    return render_template("academic_login.html")


def _academic_admin_data(db):
    """Real figures for the preview dashboard — the same tables and
    shared helpers as the real admin screens; nothing invented."""
    kpis = {
        "students": db.execute(
            "SELECT COUNT(*) c FROM students").fetchone()["c"],
        "faculty": db.execute(
            "SELECT COUNT(*) c FROM faculty "
            "WHERE COALESCE(is_active,1)=1").fetchone()["c"],
        "pending_vouchers": db.execute(
            "SELECT COUNT(*) c FROM vouchers "
            "WHERE status IN ('Pending','Proof Submitted')"
        ).fetchone()["c"],
        "outstanding": db.execute(
            "SELECT COALESCE(SUM(debit),0)-COALESCE(SUM(credit),0) c "
            "FROM ledger_entries").fetchone()["c"],
    }

    def _bars(rows):
        top = max([r["count"] for r in rows], default=0)
        return [{"name": r["name"], "count": r["count"],
                 "pct": round(100 * r["count"] / top) if top else 0}
                for r in rows]

    by_program = _bars(db.execute(
        """SELECT COALESCE(p.name,'Unassigned') name, COUNT(*) count
           FROM students s LEFT JOIN programs p ON p.id=s.program_id
           GROUP BY 1 ORDER BY count DESC, 1""").fetchall())
    by_session = _bars(db.execute(
        """SELECT COALESCE(sess.name, s.session_name, 'Unassigned') name,
                  COUNT(*) count
           FROM students s
           LEFT JOIN academic_sessions sess ON sess.id=s.session_id
           GROUP BY 1 ORDER BY count DESC, 1""").fetchall())

    def _count(sql):
        return db.execute(sql).fetchone()["c"]

    approvals = [
        {"label": "Fee voucher proofs to verify",
         "count": _count("SELECT COUNT(*) c FROM vouchers "
                         "WHERE status='Proof Submitted'"),
         "url": url_for("admin_vouchers")},
        {"label": "Student documents to verify",
         "count": _count("SELECT COUNT(*) c FROM student_documents "
                         "WHERE status='Pending'"),
         "url": url_for("admin_documents")},
        {"label": "Open support tickets",
         "count": _count("SELECT COUNT(*) c FROM tickets "
                         "WHERE status IN ('Open','In Process')"),
         "url": url_for("admin_tickets")},
        {"label": "Clearance items pending",
         "count": _count("SELECT COUNT(*) c FROM clearance_items "
                         "WHERE status='Pending'"),
         "url": url_for("admin_clearance")},
        {"label": "Scholarship applications to decide",
         "count": _count("SELECT COUNT(*) c FROM scholarship_applications "
                         "WHERE status IN ('Applied','Under Review')"),
         "url": url_for("admin_scholarships")},
        {"label": "Society join requests",
         "count": _pending_societies(db),
         "url": url_for("admin_societies")},
        {"label": "Vehicle pass requests",
         "count": _pending_vehicles(db),
         "url": url_for("admin_vehicle_passes")},
        {"label": "Course repeat requests",
         "count": _count("SELECT COUNT(*) c FROM repeat_requests "
                         "WHERE status='Requested'"),
         "url": url_for("admin_repeat")},
    ]
    pending = db.execute(
        "SELECT v.*, s.name student_name FROM vouchers v "
        "JOIN students s ON s.id=v.student_id "
        "WHERE v.status IN ('Pending','Proof Submitted') "
        "ORDER BY v.id DESC").fetchall()
    recent_students = db.execute(
        """SELECT s.*, d.name dept, p.name prog FROM students s
           LEFT JOIN departments d ON d.id=s.department_id
           LEFT JOIN programs p ON p.id=s.program_id
           ORDER BY s.id DESC LIMIT 6""").fetchall()
    notifications = db.execute(
        """SELECT * FROM notifications
           WHERE COALESCE(is_published,1)=1
             AND COALESCE(audience,'All') IN ('All','Students')
           ORDER BY published_at DESC, id DESC LIMIT 5""").fetchall()
    recent_activity = db.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT 6").fetchall()
    return {"kpis": kpis, "by_program": by_program,
            "by_session": by_session, "approvals": approvals,
            "pending": pending, "recent_students": recent_students,
            "notifications": notifications,
            "recent_activity": recent_activity}


@app.route("/preview/academic/admin")
def academic_admin():
    if not session.get("user_id"):
        return redirect(url_for("academic_login"))
    if session.get("role") != "admin":
        flash("This design preview is admin-only.", "error")
        return redirect(url_for(home_for_role()))
    return render_template("academic_admin.html",
                           **_academic_admin_data(get_db()))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5055, debug=False)
