"""
MY CUVAS — Campus Management System (Demo) v0.2
Flask + Jinja, server-rendered. Phase 1 steps 1-3 (v0.1) + v0.2 foundation:
  6. Real database layer — PostgreSQL when DATABASE_URL is set (psycopg v3),
     SQLite otherwise (local dev / demo fallback). Idempotent schema + seed.
  7. Admin CRUD for Departments / Programs / Sessions / Courses, and full
     Students management (list/search/filter, add/edit, auto student login,
     password reset, Excel import/export with template).

ALL seed data is fictional / demo-only. No real people's data.
Run:  python app.py   (or: flask --app app run)
"""
import io
import math
import os
import re
import secrets
import sqlite3
import string
from functools import wraps

from flask import (Flask, g, redirect, render_template, request, send_file,
                   session, url_for, flash)
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
]

# Columns added in v0.2 to tables that may already exist from v0.1.
EXTRA_COLUMNS = {
    "users": [("is_active", "INTEGER DEFAULT 1")],
    "students": [("cnic", "TEXT"), ("domicile", "TEXT"), ("blood_group", "TEXT"),
                 ("address_present", "TEXT"), ("address_permanent", "TEXT"),
                 ("session_id", "INTEGER")],
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
    db.conn.close()


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
    return "admin_dashboard" if session.get("role") == "admin" else "student_dashboard"


# ---------------------------------------------------------------- routes: public / auth
@app.route("/")
def landing():
    db = get_db()
    news = db.execute("SELECT * FROM notifications ORDER BY published_at DESC LIMIT 3").fetchall()
    return render_template("landing.html", news=news)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user and user.get("is_active", 1) and check_password_hash(user["password_hash"], password):
            session.clear()
            session.update(user_id=user["id"], role=user["role"],
                           display_name=user["display_name"], student_id=user["student_id"])
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
        "pending_vouchers": db.execute("SELECT COUNT(*) c FROM vouchers WHERE status='Pending'").fetchone()["c"],
    }
    recent_students = db.execute(
        """SELECT s.*, d.name dept, p.name prog FROM students s
           LEFT JOIN departments d ON d.id=s.department_id
           LEFT JOIN programs p ON p.id=s.program_id ORDER BY s.id DESC LIMIT 6""").fetchall()
    pending = db.execute(
        "SELECT v.*, s.name student_name FROM vouchers v JOIN students s ON s.id=v.student_id WHERE v.status='Pending'").fetchall()
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
    news = db.execute("SELECT * FROM notifications ORDER BY published_at DESC").fetchall()
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

    transcript, cumulative_qp, cumulative_ch, cgpa = {}, 0.0, 0, 0.0
    for sem in sorted({r["semester_no"] for r in db.execute(
            "SELECT DISTINCT semester_no FROM results WHERE student_id=?", (sid,)).fetchall()}):
        rows = db.execute(
            """SELECT r.*, c.code, c.title, c.credit_theory, c.credit_lab
               FROM results r JOIN courses c ON c.id=r.course_id
               WHERE r.student_id=? AND r.semester_no=? ORDER BY c.code""", (sid, sem)).fetchall()
        items, qp, ch = [], 0.0, 0
        for r in rows:
            credits = (r["credit_theory"] or 0) + (r["credit_lab"] or 0)
            points = round(r["grade_point"] * credits, 2)
            qp += points; ch += credits
            items.append({**r, "credits": credits, "quality_points": points})
        cumulative_qp += qp; cumulative_ch += ch
        cgpa = round(cumulative_qp / cumulative_ch, 2) if cumulative_ch else 0.0
        transcript[sem] = {"rows": items, "sgpa": round(qp / ch, 2) if ch else 0.0, "cgpa": cgpa}

    vouchers = db.execute("SELECT * FROM vouchers WHERE student_id=? ORDER BY id", (sid,)).fetchall()
    fee_lines = db.execute("SELECT * FROM fee_plan_lines ORDER BY id").fetchall()
    fee_total = sum(x["amount"] for x in fee_lines)
    ledger = db.execute("SELECT * FROM ledger_entries WHERE student_id=? ORDER BY entry_date, id", (sid,)).fetchall()
    payable = sum(x["debit"] for x in ledger)
    paid = sum(x["credit"] for x in ledger)
    active_tab = request.args.get("tab", "news")
    return render_template(
        "student_dashboard.html", student=student, certs=certs, news=news,
        enrollments=enrollments, plan=plan, plan_hours=plan_hours,
        fulfilled_hours=cumulative_ch, transcript=transcript, cgpa=cgpa,
        vouchers=vouchers, fee_lines=fee_lines, fee_total=fee_total,
        ledger=ledger, payable=payable, paid=paid, outstanding=payable - paid,
        active_tab=active_tab)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5055, debug=False)
