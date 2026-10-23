"""
MY CUVAS — Campus Management System (Demo) v0.7
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
                 ("proof_blob", "BYTEA" if PG else "BLOB")],
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
    seed(db)
    backfill_v03(db)
    backfill_v04(db)
    backfill_v06(db)
    backfill_v07(db)
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


def role_required(role):
    def deco(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login", next=request.path))
            if session.get("role") != role:
                flash("You do not have access to that area.", "error")
                return redirect(url_for(home_for_role()))
            return view(*args, **kwargs)
        return wrapped
    return deco


def home_for_role():
    return {"admin": "admin_dashboard",
            "faculty": "faculty_dashboard"}.get(session.get("role"),
                                                "student_dashboard")


# ---------------------------------------------------------------- routes: public / auth
@app.route("/")
def landing():
    db = get_db()
    news = db.execute(
        """SELECT * FROM notifications
           WHERE COALESCE(is_published,1)=1 AND COALESCE(audience,'All') IN ('All','Students')
           ORDER BY published_at DESC, id DESC LIMIT 3""").fetchall()
    return render_template("landing.html", news=news)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        ok = bool(user and user.get("is_active", 1)
                  and check_password_hash(user["password_hash"], password))
        if ok and user["role"] == "faculty":
            # a deactivated faculty record blocks login even if the users
            # row's own flag ever drifts out of sync
            fac = db.execute("SELECT is_active FROM faculty WHERE id=?",
                             (user.get("faculty_id"),)).fetchone()
            ok = bool(fac and fac.get("is_active", 1))
        if ok:
            session.clear()
            session.update(user_id=user["id"], role=user["role"],
                           display_name=user["display_name"],
                           student_id=user["student_id"],
                           faculty_id=user.get("faculty_id"))
            return redirect(url_for(home_for_role()))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
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
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
    return "Cuvas-" + "".join(secrets.choice(alphabet) for _ in range(8))


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
@role_required("admin")
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
        try:
            sid, pw = create_student(db, data, password=chosen_pw)
            db.commit()
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
    pw = generate_password()
    db.execute("UPDATE users SET password_hash=? WHERE student_id=?",
               (generate_password_hash(pw), student_id))
    db.commit()
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
        try:
            fid, pw = create_faculty(db, data, password=chosen_pw)
            db.commit()
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
    pw = generate_password()
    db.execute("UPDATE users SET password_hash=? WHERE faculty_id=?",
               (generate_password_hash(pw), faculty_id))
    db.commit()
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
    return render_template("student_import_result.html", imported=imported,
                           skipped=skipped, created_logins=created_logins)


@app.route("/admin/students/export.xlsx")
@role_required("admin")
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
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # proof uploads


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
@role_required("admin")
def admin_fee_heads():
    rows = get_db().execute(
        """SELECT h.*, (SELECT COUNT(*) FROM fee_plan_lines l WHERE l.head_id=h.id) use_count
           FROM fee_heads h ORDER BY h.name""").fetchall()
    return render_template("fee_heads.html", rows=rows)


@app.route("/admin/fee-heads/new", methods=["POST"])
@role_required("admin")
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
        flash(f"Fee head '{name}' added.", "ok")
    return redirect(url_for("admin_fee_heads"))


@app.route("/admin/fee-heads/<int:head_id>/edit", methods=["GET", "POST"])
@role_required("admin")
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
            flash(f"Fee head renamed to '{name}'.", "ok")
            return redirect(url_for("admin_fee_heads"))
    return render_template("fee_head_form.html", head=head)


@app.route("/admin/fee-heads/<int:head_id>/delete", methods=["POST"])
@role_required("admin")
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
    flash(f"Fee head '{head['name']}' deleted.", "ok")
    return redirect(url_for("admin_fee_heads"))


# ---------------------------------------------------------------- fee plans (admin)
@app.route("/admin/fee-plans")
@role_required("admin")
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
@role_required("admin")
def admin_fee_plan_new():
    db = get_db()
    if request.method == "POST":
        pid = _save_fee_plan(db, None, request.form)
        if pid:
            db.commit()
            flash("Fee plan created.", "ok")
            return redirect(url_for("admin_fee_plans"))
        db.rollback()
    return render_template("fee_plan_form.html", **_fee_plan_form_values(db))


@app.route("/admin/fee-plans/<int:plan_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def admin_fee_plan_edit(plan_id):
    db = get_db()
    plan = db.execute("SELECT * FROM fee_plans WHERE id=?", (plan_id,)).fetchone()
    if not plan:
        flash("Fee plan not found.", "error")
        return redirect(url_for("admin_fee_plans"))
    if request.method == "POST":
        if _save_fee_plan(db, plan_id, request.form):
            db.commit()
            flash("Fee plan updated.", "ok")
            return redirect(url_for("admin_fee_plans"))
        db.rollback()
    return render_template("fee_plan_form.html", **_fee_plan_form_values(db, plan))


@app.route("/admin/fee-plans/<int:plan_id>/delete", methods=["POST"])
@role_required("admin")
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
@role_required("admin")
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
@role_required("admin")
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
        flash(f"Voucher generation complete — created {created}, skipped {skipped} "
              f"(already had a voucher from this plan).", "ok" if created else "error")
        return redirect(url_for("admin_vouchers"))
    students = eligible_students(db, plan) if plan else []
    return render_template("voucher_generate.html", plans=plans, plan=plan,
                           students=students,
                           plan_total_due=plan_total(db, plan["id"]) if plan else 0)


@app.route("/admin/vouchers/<int:voucher_id>")
@role_required("admin")
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
@role_required("admin")
def admin_voucher_challan(voucher_id):
    db = get_db()
    v = get_voucher(db, voucher_id)
    if not v:
        abort(404)
    return send_file(io.BytesIO(build_challan_pdf(db, v)), as_attachment=True,
                     download_name=f"challan-{v['challan_no']}.pdf",
                     mimetype="application/pdf")


@app.route("/admin/vouchers/<int:voucher_id>/proof")
@role_required("admin")
def admin_voucher_proof(voucher_id):
    db = get_db()
    v = db.execute("SELECT * FROM vouchers WHERE id=?", (voucher_id,)).fetchone()
    if not v or not v.get("proof_blob"):
        abort(404)
    return send_file(io.BytesIO(bytes(v["proof_blob"])), as_attachment=True,
                     download_name=v.get("proof_filename") or f"proof-{voucher_id}",
                     mimetype=v.get("proof_mimetype") or "application/octet-stream")


@app.route("/admin/vouchers/<int:voucher_id>/verify", methods=["POST"])
@role_required("admin")
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
    db.commit()
    flash(f"Voucher {v['challan_no']} verified — marked Paid.", "ok")
    return redirect(url_for("admin_voucher_detail", voucher_id=voucher_id))


@app.route("/admin/vouchers/<int:voucher_id>/reject", methods=["POST"])
@role_required("admin")
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
    flash(f"Proof for {v['challan_no']} rejected — voucher is Pending again.", "ok")
    return redirect(url_for("admin_voucher_detail", voucher_id=voucher_id))


@app.route("/admin/vouchers/<int:voucher_id>/installments", methods=["POST"])
@role_required("admin")
def admin_voucher_installments(voucher_id):
    db = get_db()
    v = get_voucher(db, voucher_id)
    if not v:
        flash("Voucher not found.", "error")
        return redirect(url_for("admin_vouchers"))
    ok, msg = split_voucher(db, v)
    db.commit() if ok else db.rollback()
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
    transcript = {semester_no: {"rows": [...], "sgpa": x, "cgpa": running}}."""
    bands = get_grade_bands(db)
    pub = " AND COALESCE(r.is_published,0)=1" if published_only else ""
    rows = db.execute(
        f"""SELECT r.*, c.code, c.title, c.credit_theory, c.credit_lab
            FROM results r JOIN courses c ON c.id=r.course_id
            WHERE r.student_id=?{pub} ORDER BY r.semester_no, c.code""",
        (student_id,)).fetchall()
    transcript, cumulative_qp, cumulative_ch, cgpa = {}, 0.0, 0, 0.0
    for sem in sorted({r["semester_no"] for r in rows}):
        items, qp, ch = [], 0.0, 0
        for r in [x for x in rows if x["semester_no"] == sem]:
            credits = (r["credit_theory"] or 0) + (r["credit_lab"] or 0)
            grade, gp = result_grade_gp(r, bands)
            points = round((gp or 0.0) * credits, 2)
            qp += points
            ch += credits
            marks = r.get("marks_obtained")
            items.append({**r, "credits": credits, "grade": grade,
                          "grade_point": gp, "quality_points": points,
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
    any student who already has a result for this course set."""
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
@role_required("admin")
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
            flash("Grading scale updated — grades are derived from it everywhere.", "ok")
            return redirect(url_for("admin_grade_scale"))
    bands = get_grade_bands(db)
    for i, b in enumerate(bands):
        b["max_marks"] = (bands[i - 1]["min_marks"] - 1) if i else 100
    return render_template("grade_scale.html", bands=bands)


@app.route("/admin/grade-scale/add", methods=["POST"])
@role_required("admin")
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
    flash(f"Grade band {grade} (from {min_f:g}) added.", "ok")
    return redirect(url_for("admin_grade_scale"))


@app.route("/admin/grade-scale/<int:band_id>/delete", methods=["POST"])
@role_required("admin")
def admin_grade_scale_delete(band_id):
    db = get_db()
    band = db.execute("SELECT * FROM grade_bands WHERE id=?", (band_id,)).fetchone()
    if band:
        db.execute("DELETE FROM grade_bands WHERE id=?", (band_id,))
        db.commit()
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
@role_required("admin")
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
@role_required("admin")
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
@role_required("admin")
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
    flash(f"Results for {course['code']} are now "
          f"{'PUBLISHED — students can see them' if publish else 'UNPUBLISHED — hidden from students'}.",
          "ok")
    return redirect(url_for("admin_results_sheet", course_id=course["id"],
                            session_id=session_id))


@app.route("/admin/results/sheet.xlsx")
@role_required("admin")
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
@role_required("admin")
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
            rows.append([r["code"], r["title"], str(r["credits"]), r["marks_display"],
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
@role_required("admin")
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
@role_required("admin")
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
@role_required("admin")
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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5055, debug=False)
