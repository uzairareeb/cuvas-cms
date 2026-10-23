"""Scripted smoke verification for CUVAS CMS v0.2 (run with the app venv python).

Expects a FRESH database (empty users table) so seeding + CRUD counts are exact.
Env: DB_PATH=<fresh sqlite file>  OR  DATABASE_URL=<postgres uri>.
Prints PASS/FAIL lines and exits non-zero if any check fails.
"""
import io
import re
import sys

import app as m

FAIL = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail else ""))
    if not cond:
        FAIL.append(name)


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


admin = m.app.test_client()
check("landing 200", admin.get("/").status_code == 200)
check("anon /admin redirects to login", admin.get("/admin").status_code == 302)
r = login(admin, "admin", "Admin@123")
check("admin login", r.status_code == 302 and "/admin" in r.headers["Location"])
dash = admin.get("/admin").get_data(as_text=True)
check("dashboard KPIs seeded (6 students/4 depts/5 programs)",
      ">6<" in dash and ">4<" in dash and ">5<" in dash)

# look up seeded ids via the app's own layer
with m.app.app_context():
    db = m.get_db()
    cs_dept = db.execute("SELECT id FROM departments WHERE code='CS-DEMO'").fetchone()["id"]
    bs_cs = db.execute("SELECT id FROM programs WHERE name='BS Computer Science (Demo)'").fetchone()["id"]
    fall26 = db.execute("SELECT id FROM academic_sessions WHERE name='Fall 2026 (Demo)'").fetchone()["id"]

# ---- CRUD: department / program / session / course via UI routes
r = admin.post("/admin/departments/new", data={
    "name": "Dept of Testing (Verify)", "code": "TST-V", "faculty_name": "Faculty of Testing"})
check("create department", r.status_code == 302)
rows = admin.get("/admin/departments").get_data(as_text=True)
check("department listed", "Dept of Testing (Verify)" in rows)
with m.app.app_context():
    db = m.get_db()
    tst_dept = db.execute("SELECT id FROM departments WHERE code='TST-V'").fetchone()["id"]

r = admin.post("/admin/programs/new", data={
    "name": "BS Testing (Verify)", "department_id": tst_dept,
    "degree_level": "BS", "duration_semesters": 8})
check("create program", r.status_code == 302)
with m.app.app_context():
    db = m.get_db()
    tst_prog = db.execute("SELECT id FROM programs WHERE name='BS Testing (Verify)'").fetchone()["id"]

r = admin.post("/admin/sessions/new", data={
    "name": "Spring-2027", "starts_on": "2027-02-01", "ends_on": "2027-06-30", "is_open": "on"})
check("create session", r.status_code == 302)
with m.app.app_context():
    db = m.get_db()
    tst_sess = db.execute("SELECT id FROM academic_sessions WHERE name='Spring-2027'").fetchone()["id"]

r = admin.post("/admin/courses/new", data={
    "program_id": tst_prog, "semester_no": 1, "code": "TST-101", "title": "Testing Basics",
    "credit_theory": 3, "credit_lab": 1, "faculty_name": "Dr Verify"})
check("create course", r.status_code == 302)
check("course listed", "TST-101" in admin.get("/admin/courses").get_data(as_text=True))
with m.app.app_context():
    db = m.get_db()
    tst_course = db.execute("SELECT id FROM courses WHERE code='TST-101'").fetchone()["id"]

# edit course title
r = admin.post(f"/admin/courses/{tst_course}/edit", data={
    "program_id": tst_prog, "semester_no": 2, "code": "TST-101", "title": "Testing Basics II",
    "credit_theory": 2, "credit_lab": 1, "faculty_name": "Dr Verify"})
check("edit course", r.status_code == 302 and
      "Testing Basics II" in admin.get("/admin/courses").get_data(as_text=True))

# ---- students: add via form, password shown once, new student login works
form = {
    "registration_no": "VERIFY-2027-001", "cnic": "35202-9999999-9", "name": "Verify Student",
    "father_name": "Verify Father", "gender": "Male", "dob": "2005-01-01", "domicile": "Bahawalpur",
    "blood_group": "B+", "phone": "0300-9999999", "email": "verify.student@example.com",
    "address_present": "Verify Present Address", "address_permanent": "Verify Permanent Address",
    "department_id": tst_dept, "program_id": tst_prog, "session_id": tst_sess,
    "campus": "Main Campus (Demo)", "status": "Active", "current_semester": 1,
    "initial_password": "",
}
r = admin.post("/admin/students/new", data=form)
check("add student redirects", r.status_code == 302)
lst = admin.get("/admin/students").get_data(as_text=True)
pw_match = re.search(r"initial password: (\S+)", lst)
check("initial password shown once on success", bool(pw_match))
check("student appears in list", "Verify Student" in lst and "VERIFY-2027-001" in lst)
new_pw = pw_match.group(1) if pw_match else ""

stu = m.app.test_client()
r = login(stu, "VERIFY-2027-001", new_pw)
check("new student can log in with issued password", r.status_code == 302 and "/student" in r.headers["Location"])
prof = stu.get("/student").get_data(as_text=True)
check("new student sees own profile", "Verify Student" in prof and "35202-9999999-9" in prof
      and "Verify Present Address" in prof and "BS Testing (Verify)" in prof)
check("role guard: student blocked from /admin", stu.get("/admin").status_code == 302)

# edit student (phone) — login must keep working
with m.app.app_context():
    db = m.get_db()
    stu_id = db.execute("SELECT id FROM students WHERE registration_no='VERIFY-2027-001'").fetchone()["id"]
edit_form = dict(form, phone="0300-1111111")
r = admin.post(f"/admin/students/{stu_id}/edit", data=edit_form)
check("edit student", r.status_code == 302)
stu2 = m.app.test_client()
login(stu2, "VERIFY-2027-001", new_pw)
prof2 = stu2.get("/student").get_data(as_text=True)
check("edited phone shows + login intact after edit", "0300-1111111" in prof2)

# duplicate registration must be rejected, not 500
r = admin.post("/admin/students/new", data=form)
check("duplicate student rejected gracefully", r.status_code == 200 and "already exists" in r.get_data(as_text=True))

# reset password
r = admin.post(f"/admin/students/{stu_id}/reset-password")
check("reset password redirects", r.status_code == 302)
lst = admin.get("/admin/students").get_data(as_text=True)
m2 = re.search(r"New password: (\S+)", lst)
check("reset password shown once", bool(m2))
stu3 = m.app.test_client()
r = login(stu3, "VERIFY-2027-001", m2.group(1) if m2 else "")
check("login works with reset password", r.status_code == 302 and "/student" in r.headers["Location"])

# ---- Excel import: 3 valid + 1 bad (unknown department)
from openpyxl import Workbook, load_workbook
wb = Workbook()
ws = wb.active
headers = ["Name", "Registration No", "CNIC", "Father Name", "Gender", "Date of Birth",
           "Department", "Program", "Session", "Campus", "Status", "Current Semester",
           "Phone", "Email", "Blood Group", "Domicile"]  # shuffled on purpose
ws.append(headers)
base = ["Imp Student One", "IMP-001", "35202-1111111-1", "Imp Father", "Female", "2005-03-03",
        "Dept of Testing (Verify)", "BS Testing (Verify)", "Spring-2027", "Main Campus (Demo)",
        "Active", 1, "0300-1000001", "imp.one@example.com", "A+", "Multan"]
ws.append(base)
ws.append(["Imp Student Two", "IMP-002", "35202-2222222-2", "Imp Father", "Male", "2005-04-04",
           "Department of Computer Science (Demo)", "BS Computer Science (Demo)", "Fall 2026 (Demo)",
           "Main Campus (Demo)", "Active", 3, "0300-1000002", "imp.two@example.com", "O+", "Lahore"])
ws.append(["Imp Student Three", "IMP-003", "35202-3333333-3", "Imp Father", "Female", "2005-05-05",
           "Dept of Testing (Verify)", "BS Testing (Verify)", "Spring-2027", "Main Campus (Demo)",
           "Active", 1, "0300-1000003", "imp.three@example.com", "B-", "Karachi"])
ws.append(["Imp Student Bad", "IMP-004", "35202-4444444-4", "Imp Father", "Male", "2005-06-06",
           "Department That Does Not Exist", "BS Testing (Verify)", "Spring-2027",
           "Main Campus (Demo)", "Active", 1, "0300-1000004", "imp.bad@example.com", "A-", "Nowhere"])
buf = io.BytesIO()
wb.save(buf)
buf.seek(0)
r = admin.post("/admin/students/import", data={"file": (buf, "import_test.xlsx")},
               content_type="multipart/form-data")
body = r.get_data(as_text=True)
check("import result page 200", r.status_code == 200)
check("import summary: 3 imported", re.search(r'<div class="num">3</div><div class="lbl">Imported</div>', body) is not None)
check("import summary: 1 skipped", re.search(r'<div class="num">1</div><div class="lbl">Skipped</div>', body) is not None)
check("bad-row reason names unknown department", "unknown department" in body and "Department That Does Not Exist" in body)
creds = re.findall(r"(IMP-00\d)</td><td>[^<]+</td><td><code>([^<]+)</code>", body)
check("import shows 3 one-time passwords", len(creds) == 3, f"found {len(creds)}")
if creds:
    imp = m.app.test_client()
    r = login(imp, creds[0][0], creds[0][1])
    check("imported student can log in", r.status_code == 302 and "/student" in r.headers["Location"])

# template download
r = admin.get("/admin/students/template.xlsx")
check("template downloads", r.status_code == 200 and len(r.data) > 1000)
twb = load_workbook(io.BytesIO(r.data))
check("template headers match", twb.active.cell(row=1, column=1).value == "Registration No")

# export honours a filter (department = test dept => verify + 2 imported = 3 rows + header)
r = admin.get(f"/admin/students/export.xlsx?department_id={tst_dept}")
check("export downloads", r.status_code == 200 and "spreadsheet" in r.headers.get("Content-Type", ""))
ewb = load_workbook(io.BytesIO(r.data))
erows = ewb.active.max_row
check("export row count for filtered dept = 4 (header+3)", erows == 4, f"max_row={erows}")
allr = admin.get("/admin/students/export.xlsx")
allrows = load_workbook(io.BytesIO(allr.data)).active.max_row
check("export all = header + 6 seeded + 1 added + 3 imported = 11", allrows == 11, f"max_row={allrows}")

# search works
res = admin.get("/admin/students?q=IMP-002").get_data(as_text=True)
check("search finds imported student", "Imp Student Two" in res and "Verify Student" not in res)

# ---- deletes + reference blocks
r = admin.post(f"/admin/departments/{tst_dept}/delete")
dept_page = admin.get("/admin/departments").get_data(as_text=True)  # first render carries the flash
with m.app.app_context():
    db = m.get_db()
    still_there = db.execute("SELECT COUNT(*) c FROM departments WHERE id=?", (tst_dept,)).fetchone()["c"]
check("referenced department delete blocked",
      still_there == 1 and "Cannot delete" in dept_page)
r = admin.post(f"/admin/programs/{bs_cs}/delete")
prog_page = admin.get("/admin/programs").get_data(as_text=True)
check("referenced program delete blocked", "Cannot delete" in prog_page)
r = admin.post(f"/admin/sessions/{fall26}/delete")
sess_page = admin.get("/admin/sessions").get_data(as_text=True)
check("referenced session delete blocked", "Cannot delete" in sess_page)

# create + delete an unreferenced department succeeds
admin.post("/admin/departments/new", data={"name": "Temp Dept (Verify)", "code": "TMP-V", "faculty_name": ""})
with m.app.app_context():
    db = m.get_db()
    tmp_dept = db.execute("SELECT id FROM departments WHERE code='TMP-V'").fetchone()["id"]
admin.post(f"/admin/departments/{tmp_dept}/delete")
with m.app.app_context():
    db = m.get_db()
    tmp_gone = db.execute("SELECT COUNT(*) c FROM departments WHERE id=?", (tmp_dept,)).fetchone()["c"]
dept_page = admin.get("/admin/departments").get_data(as_text=True)
check("unreferenced department deleted",
      tmp_gone == 0 and f"/admin/departments/{tmp_dept}/edit" not in dept_page)

# delete the created course (unreferenced) succeeds
admin.post(f"/admin/courses/{tst_course}/delete")
with m.app.app_context():
    db = m.get_db()
    course_gone = db.execute("SELECT COUNT(*) c FROM courses WHERE id=?", (tst_course,)).fetchone()["c"]
courses_page = admin.get("/admin/courses").get_data(as_text=True)
check("course deleted",
      course_gone == 0 and f"/admin/courses/{tst_course}/edit" not in courses_page)

# delete a student + login gone
with m.app.app_context():
    db = m.get_db()
    imp2 = db.execute("SELECT id FROM students WHERE registration_no='IMP-002'").fetchone()["id"]
admin.post(f"/admin/students/{imp2}/delete")
gone = m.app.test_client()
r = login(gone, "IMP-002", "whatever")
check("deleted student login removed", not (r.status_code == 302 and "/student" in r.headers.get("Location", "")))

# dashboard counts reflect CRUD: students = 6 seeded +1 added +3 imported -1 deleted = 9
dash = admin.get("/admin").get_data(as_text=True)
check("dashboard student count reflects CRUD (=9)", ">9<" in dash)

# demo student dashboard still fully works
demo = m.app.test_client()
login(demo, "student", "Student@123")
d = demo.get("/student").get_data(as_text=True)
# v0.6 added the My Documents + Support Tickets tabs: 10 tabs total
check("demo student 10 tabs + CGPA intact", d.count('data-tab=') == 10 and "3.63" in d)

print()
print("RESULT:", "ALL PASS" if not FAIL else f"{len(FAIL)} FAILURES: {FAIL}")
sys.exit(1 if FAIL else 0)
