"""
MY CUVAS — Campus Management System (Demo) v0.1
Flask + Jinja, SQLite demo build. Steps 1-3 of Phase 1 only:
  1. Skeleton + auth (hashed passwords) + role guards
  2. Admin shell + dashboard KPIs, Departments & Programs pages
  3. Student dashboard with 8 tabs, seeded fictional demo data

ALL seed data is fictional / demo-only. No real people's data.
Run:  python app.py   (or: flask --app app run)
"""
import os
import sqlite3
from functools import wraps

from flask import Flask, g, redirect, render_template, request, session, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# On Vercel the deployment filesystem is read-only and instances are ephemeral,
# so the demo SQLite DB lives under /tmp there (created + seeded on cold start).
# Locally it stays next to app.py, unchanged. DB_PATH env var wins when set.
if os.environ.get("DB_PATH"):
    DB_PATH = os.environ["DB_PATH"]
elif os.environ.get("VERCEL"):
    DB_PATH = "/tmp/cuvas_demo.db"
else:
    DB_PATH = os.path.join(BASE_DIR, "cuvas_demo.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "demo-only-secret-change-me")

# ---------------------------------------------------------------- DB helpers
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin','student')),
    display_name TEXT NOT NULL,
    student_id INTEGER
);
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, code TEXT UNIQUE NOT NULL, faculty_name TEXT
);
CREATE TABLE IF NOT EXISTS programs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER REFERENCES departments(id),
    name TEXT NOT NULL, degree_level TEXT, duration_semesters INTEGER
);
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registration_no TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL, father_name TEXT, gender TEXT, dob TEXT,
    phone TEXT, email TEXT, address TEXT, campus TEXT, status TEXT,
    department_id INTEGER REFERENCES departments(id),
    program_id INTEGER REFERENCES programs(id),
    session_name TEXT, current_semester INTEGER
);
CREATE TABLE IF NOT EXISTS certificates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER, title TEXT, board TEXT, passing_year TEXT,
    total_marks INTEGER, obtained_marks INTEGER
);
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id INTEGER, semester_no INTEGER, code TEXT, title TEXT,
    credit_theory INTEGER, credit_lab INTEGER, faculty_name TEXT
);
CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER, course_id INTEGER, session_name TEXT, semester_no INTEGER
);
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER, course_id INTEGER, semester_no INTEGER,
    grade TEXT, grade_point REAL, remarks TEXT
);
CREATE TABLE IF NOT EXISTS vouchers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER, challan_no TEXT UNIQUE, title TEXT,
    amount INTEGER, due_date TEXT, status TEXT, remarks TEXT
);
CREATE TABLE IF NOT EXISTS fee_plan_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT, head TEXT, amount INTEGER
);
CREATE TABLE IF NOT EXISTS ledger_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER, voucher_title TEXT, challan_no TEXT, entry_date TEXT,
    description TEXT, debit INTEGER DEFAULT 0, credit INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, body TEXT, published_at TEXT
);
"""


def seed(db):
    if db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]:
        return
    # --- demo accounts (fictional, demo-only) ---
    db.execute(
        "INSERT INTO users (username,password_hash,role,display_name) VALUES (?,?,?,?)",
        ("admin", generate_password_hash("Admin@123"), "admin", "Demo Admin"),
    )
    cur = db.execute(
        "INSERT INTO users (username,password_hash,role,display_name) VALUES (?,?,?,?)",
        ("student", generate_password_hash("Student@123"), "student", "Demo Student"),
    )
    # --- departments (fictional demo entries) ---
    depts = [
        ("Department of Computer Science (Demo)", "CS-DEMO", "Faculty of Computing (Demo)"),
        ("Department of Veterinary Medicine (Demo)", "DVM-DEMO", "Faculty of Veterinary Sciences (Demo)"),
        ("Department of Animal Sciences (Demo)", "ANS-DEMO", "Faculty of Animal Sciences (Demo)"),
        ("Department of Food Science (Demo)", "FS-DEMO", "Faculty of Food Sciences (Demo)"),
    ]
    dept_ids = {}
    for name, code, fac in depts:
        c = db.execute("INSERT INTO departments (name,code,faculty_name) VALUES (?,?,?)", (name, code, fac))
        dept_ids[code] = c.lastrowid
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
        c = db.execute(
            "INSERT INTO programs (department_id,name,degree_level,duration_semesters) VALUES (?,?,?,?)",
            (d, n, lvl, dur),
        )
        prog_ids.append(c.lastrowid)
    bs_cs = prog_ids[0]
    # --- students (all fictional) ---
    students = [
        ("CUVAS-DEMO-2026-001", "Demo Student", "Demo Father", "Male", "2004-01-15",
         "0300-0000001", "demo.student@example.com", "Demo Address, Demo City", "Main Campus (Demo)", "Active",
         dept_ids["CS-DEMO"], bs_cs, "Fall 2024 (Demo)", 3),
        ("CUVAS-DEMO-2026-002", "Demo Student Two", "Demo Father Two", "Female", "2004-05-20",
         "0300-0000002", "demo.two@example.com", "Demo Address 2", "Main Campus (Demo)", "Active",
         dept_ids["CS-DEMO"], bs_cs, "Fall 2024 (Demo)", 3),
        ("CUVAS-DEMO-2026-003", "Demo Student Three", "Demo Father Three", "Male", "2003-11-02",
         "0300-0000003", "demo.three@example.com", "Demo Address 3", "Main Campus (Demo)", "Active",
         dept_ids["DVM-DEMO"], prog_ids[1], "Fall 2024 (Demo)", 3),
        ("CUVAS-DEMO-2026-004", "Demo Student Four", "Demo Father Four", "Female", "2004-03-18",
         "0300-0000004", "demo.four@example.com", "Demo Address 4", "Main Campus (Demo)", "Active",
         dept_ids["ANS-DEMO"], prog_ids[2], "Fall 2025 (Demo)", 1),
        ("CUVAS-DEMO-2026-005", "Demo Student Five", "Demo Father Five", "Male", "2002-08-25",
         "0300-0000005", "demo.five@example.com", "Demo Address 5", "Main Campus (Demo)", "Active",
         dept_ids["ANS-DEMO"], prog_ids[3], "Fall 2025 (Demo)", 1),
        ("CUVAS-DEMO-2026-006", "Demo Student Six", "Demo Father Six", "Female", "2004-07-09",
         "0300-0000006", "demo.six@example.com", "Demo Address 6", "Main Campus (Demo)", "Active",
         dept_ids["FS-DEMO"], prog_ids[4], "Fall 2025 (Demo)", 1),
    ]
    student_ids = []
    for s in students:
        c = db.execute(
            """INSERT INTO students (registration_no,name,father_name,gender,dob,phone,email,address,
               campus,status,department_id,program_id,session_name,current_semester)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", s)
        student_ids.append(c.lastrowid)
    demo_student = student_ids[0]
    db.execute("UPDATE users SET student_id=? WHERE username='student'", (demo_student,))
    # --- certificates for demo student ---
    db.executemany(
        "INSERT INTO certificates (student_id,title,board,passing_year,total_marks,obtained_marks) VALUES (?,?,?,?,?,?)",
        [(demo_student, "Matriculation (Demo)", "Demo Board", "2020", 1100, 920),
         (demo_student, "Intermediate (Demo)", "Demo Board", "2022", 1100, 880)],
    )
    # --- courses for BS CS (Demo): semesters 1-4 (plan of study) ---
    course_rows = [
        # sem 1
        (1, "CS-101", "Introduction to Computing (Demo)", 3, 0, "Dr Demo Faculty A"),
        (1, "MTH-101", "Calculus & Analytical Geometry (Demo)", 3, 0, "Dr Demo Faculty B"),
        (1, "ENG-101", "English Comprehension (Demo)", 2, 0, "Ms Demo Faculty C"),
        (1, "PHY-101", "Applied Physics (Demo)", 2, 1, "Dr Demo Faculty D"),
        (1, "ISL-101", "Islamic Studies (Demo)", 2, 0, "Mr Demo Faculty E"),
        # sem 2
        (2, "CS-102", "Programming Fundamentals (Demo)", 3, 1, "Dr Demo Faculty A"),
        (2, "MTH-102", "Discrete Structures (Demo)", 3, 0, "Dr Demo Faculty B"),
        (2, "ENG-102", "Communication Skills (Demo)", 2, 0, "Ms Demo Faculty C"),
        (2, "STA-102", "Statistics & Probability (Demo)", 2, 1, "Dr Demo Faculty F"),
        (2, "PAK-102", "Pakistan Studies (Demo)", 2, 0, "Mr Demo Faculty E"),
        # sem 3 (current enrollments)
        (3, "CS-201", "Object Oriented Programming (Demo)", 3, 1, "Dr Demo Faculty A"),
        (3, "CS-202", "Data Structures (Demo)", 3, 1, "Dr Demo Faculty G"),
        (3, "MTH-201", "Linear Algebra (Demo)", 3, 0, "Dr Demo Faculty B"),
        (3, "CS-203", "Digital Logic Design (Demo)", 2, 1, "Dr Demo Faculty D"),
        (3, "MGT-201", "Principles of Management (Demo)", 2, 0, "Ms Demo Faculty H"),
        # sem 4 (plan only)
        (4, "CS-204", "Database Systems (Demo)", 3, 1, "Dr Demo Faculty G"),
        (4, "CS-205", "Operating Systems (Demo)", 3, 1, "Dr Demo Faculty A"),
        (4, "MTH-202", "Numerical Methods (Demo)", 3, 0, "Dr Demo Faculty B"),
    ]
    course_ids = {}  # (sem, code) -> id
    for sem, code, title, th, lab, fac in course_rows:
        c = db.execute(
            "INSERT INTO courses (program_id,semester_no,code,title,credit_theory,credit_lab,faculty_name) VALUES (?,?,?,?,?,?,?)",
            (bs_cs, sem, code, title, th, lab, fac))
        course_ids[(sem, code)] = c.lastrowid
    # --- current enrollments: semester 3 ---
    for (sem, code), cid in course_ids.items():
        if sem == 3:
            db.execute(
                "INSERT INTO enrollments (student_id,course_id,session_name,semester_no) VALUES (?,?,?,?)",
                (demo_student, cid, "Fall 2026 (Demo)", 3))
    # --- results: semesters 1 & 2 (grade_point per course) ---
    sem1_grades = {"CS-101": ("A", 4.0), "MTH-101": ("B+", 3.5), "ENG-101": ("A", 4.0),
                   "PHY-101": ("B", 3.0), "ISL-101": ("A-", 3.7)}
    sem2_grades = {"CS-102": ("A", 4.0), "MTH-102": ("A-", 3.7), "ENG-102": ("B+", 3.5),
                   "STA-102": ("B", 3.0), "PAK-102": ("A", 4.0)}
    for sem, grades in ((1, sem1_grades), (2, sem2_grades)):
        for code, (grade, gp) in grades.items():
            db.execute(
                "INSERT INTO results (student_id,course_id,semester_no,grade,grade_point,remarks) VALUES (?,?,?,?,?,?)",
                (demo_student, course_ids[(sem, code)], sem, grade, gp, "Pass"))
    # --- vouchers: 1 Paid + 1 Pending (+ admission paid) ---
    db.executemany(
        "INSERT INTO vouchers (student_id,challan_no,title,amount,due_date,status,remarks) VALUES (?,?,?,?,?,?,?)",
        [(demo_student, "DEMO-CH-1000", "Admission Fee (Demo)", 15000, "2024-09-01", "Paid", "Paid via Demo Bank"),
         (demo_student, "DEMO-CH-1001", "Semester 2 Fee (Demo)", 45000, "2025-02-15", "Paid", "Paid via Demo Bank"),
         (demo_student, "DEMO-CH-1002", "Semester 3 Fee (Demo)", 47500, "2026-11-15", "Pending", "Payable at any Demo Bank branch")],
    )
    # --- fee plan lines (total = 47,500, matches pending voucher) ---
    db.executemany(
        "INSERT INTO fee_plan_lines (head,amount) VALUES (?,?)",
        [("Tuition Fee (Demo)", 30000), ("University / Institute Charges (Demo)", 8000),
         ("Transport Charges (Demo)", 5000), ("Library Charges (Demo)", 1500),
         ("Examination Charges (Demo)", 3000)],
    )
    # --- ledger (account statement) ---
    db.executemany(
        "INSERT INTO ledger_entries (student_id,voucher_title,challan_no,entry_date,description,debit,credit) VALUES (?,?,?,?,?,?,?)",
        [(demo_student, "Admission Fee (Demo)", "DEMO-CH-1000", "2024-09-01", "Admission fee charged (Demo)", 15000, 0),
         (demo_student, "Admission Fee (Demo)", "DEMO-CH-1000", "2024-09-03", "Payment received — Demo Bank", 0, 15000),
         (demo_student, "Semester 2 Fee (Demo)", "DEMO-CH-1001", "2025-02-01", "Semester 2 fee charged (Demo)", 45000, 0),
         (demo_student, "Semester 2 Fee (Demo)", "DEMO-CH-1001", "2025-02-10", "Payment received — Demo Bank", 0, 45000),
         (demo_student, "Semester 3 Fee (Demo)", "DEMO-CH-1002", "2026-10-01", "Semester 3 fee charged (Demo)", 47500, 0)],
    )
    # --- news feed ---
    db.executemany(
        "INSERT INTO notifications (title,body,published_at) VALUES (?,?,?)",
        [("Welcome to MY CUVAS (Demo)", "This is a demonstration build with fictional data only.", "2026-10-20"),
         ("Semester 3 Fee Deadline (Demo)", "Demo notice: the Semester 3 fee voucher is due by 15 Nov 2026.", "2026-10-21"),
         ("Demo LMS Coming Soon", "Course material and LMS features are planned for a later phase.", "2026-10-22")],
    )
    db.commit()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.row_factory = sqlite3.Row
    seed(conn)
    conn.close()


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
                flash("You do not have access to that area (demo).", "error")
                return redirect(url_for(home_for_role()))
            return view(*args, **kwargs)
        return wrapped
    return deco


def home_for_role():
    return "admin_dashboard" if session.get("role") == "admin" else "student_dashboard"


# ---------------------------------------------------------------- routes
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
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.update(user_id=user["id"], role=user["role"],
                           display_name=user["display_name"], student_id=user["student_id"])
            return redirect(url_for(home_for_role()))
        flash("Invalid username or password (demo).", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


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
           LEFT JOIN programs p ON p.id=s.program_id ORDER BY s.id LIMIT 6""").fetchall()
    pending = db.execute(
        "SELECT v.*, s.name student_name FROM vouchers v JOIN students s ON s.id=v.student_id WHERE v.status='Pending'").fetchall()
    return render_template("admin_dashboard.html", kpis=kpis,
                           recent_students=recent_students, pending=pending)


@app.route("/admin/departments")
@role_required("admin")
def admin_departments():
    rows = get_db().execute(
        """SELECT d.*, (SELECT COUNT(*) FROM programs p WHERE p.department_id=d.id) prog_count,
                  (SELECT COUNT(*) FROM students s WHERE s.department_id=d.id) stu_count
           FROM departments d ORDER BY d.name""").fetchall()
    return render_template("admin_departments.html", rows=rows)


@app.route("/admin/programs")
@role_required("admin")
def admin_programs():
    rows = get_db().execute(
        """SELECT p.*, d.name dept FROM programs p
           LEFT JOIN departments d ON d.id=p.department_id ORDER BY d.name, p.name""").fetchall()
    return render_template("admin_programs.html", rows=rows)


@app.route("/student")
@role_required("student")
def student_dashboard():
    db = get_db()
    sid = session.get("student_id")
    student = db.execute(
        """SELECT s.*, d.name dept, p.name prog FROM students s
           LEFT JOIN departments d ON d.id=s.department_id
           LEFT JOIN programs p ON p.id=s.program_id WHERE s.id=?""", (sid,)).fetchone()
    certs = db.execute("SELECT * FROM certificates WHERE student_id=?", (sid,)).fetchall()
    news = db.execute("SELECT * FROM notifications ORDER BY published_at DESC").fetchall()
    enrollments = db.execute(
        """SELECT e.*, c.code, c.title, c.credit_theory, c.credit_lab, c.faculty_name
           FROM enrollments e JOIN courses c ON c.id=e.course_id
           WHERE e.student_id=? ORDER BY c.code""", (sid,)).fetchall()
    plan_rows = db.execute(
        "SELECT * FROM courses WHERE program_id=? ORDER BY semester_no, code",
        (student["program_id"],)).fetchall()
    plan = {}
    for r in plan_rows:
        plan.setdefault(r["semester_no"], []).append(r)
    plan_hours = {sem: sum((x["credit_theory"] or 0) + (x["credit_lab"] or 0) for x in rows)
                  for sem, rows in plan.items()}

    # transcript with computed SGPA / CGPA
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
            items.append({**dict(r), "credits": credits, "quality_points": points})
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
