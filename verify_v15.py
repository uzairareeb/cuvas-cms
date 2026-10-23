"""Scripted verification for CUVAS CMS v0.15 — Step 20 staff roles,
security hardening & go-live readiness:
  * role migration: a v0.14-shaped database whose users table still
    carries the legacy CHECK(role IN ('admin','student')) boots under
    the new code, the constraint is widened, and accounts / coe
    logins can be inserted and used (subprocess, both backends);
  * the permission matrix: accounts reaches fees / vouchers / the
    fee report + read-only students and is refused everything else;
    coe is the mirror image (results, grade scale, slips, the
    results + attendance reports); admin reaches everything,
    including /accounts and /coe; office users hitting /admin land
    on their own dashboard; sidebars are role-aware;
  * staff management: admin creates / resets / deactivates /
    reactivates office logins, the primary admin cannot be
    deactivated, and every action lands in the audit log;
  * sign-in lockout: 5 consecutive failures within the window lock
    the username (even the correct password is refused, audited as
    login_locked), a success clears the streak, other usernames
    are unaffected;
  * the password policy (8+ chars, a letter and a digit) on staff
    create/reset and on hand-typed student / faculty passwords,
    while auto-generated and Excel-imported passwords stay exempt;
  * security headers on responses, hardened cookie flags, and the
    10 MB upload cap (a >10 MB upload is refused with 413);
  * the go-live demo-accounts toggle hides / restores the homepage
    demo box (audited);
  * faculty portal and the 10 student tabs are untouched.

Expects a FRESH database (empty users table) so seeding + counts are exact.
Env: DB_PATH=<fresh sqlite file>  OR  DATABASE_URL=<postgres uri>.
Prints PASS/FAIL lines and exits non-zero if any check fails.
"""
import io
import os
import re
import subprocess
import sys
import tempfile

import app as m

FAIL = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail else ""))
    if not cond:
        FAIL.append(name)


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def dbq(sql, params=()):
    with m.app.app_context():
        return m.get_db().execute(sql, params).fetchall()


def db1(sql, params=()):
    rows = dbq(sql, params)
    return rows[0] if rows else None


def audit_rows(action=None, username=None):
    sql, params = "SELECT * FROM audit_log WHERE 1=1", []
    if action:
        sql += " AND action=?"
        params.append(action)
    if username:
        sql += " AND username=?"
        params.append(username)
    return dbq(sql + " ORDER BY id", params)


def denied(resp):
    """The house denial for a wrong role: a redirect to the user's
    own home (never the page itself)."""
    return resp.status_code == 302


# ------------------------------------------------------- demo staff seeded
for uname, role in (("accounts", "accounts"), ("coe", "coe")):
    row = db1("SELECT * FROM users WHERE username=?", (uname,))
    check(f"demo staff login '{uname}' seeded with role {role}",
          row is not None and row["role"] == role and row["is_active"] == 1)

admin = m.app.test_client()
r = login(admin, "admin", "Admin@123")
check("admin login still lands on /admin",
      r.status_code == 302 and r.headers["Location"].endswith("/admin"))

# ------------------------------------------------------- landing redirects
acc = m.app.test_client()
r = login(acc, "accounts", "Accounts@123")
check("accounts login lands on /accounts",
      r.status_code == 302 and r.headers["Location"].endswith("/accounts"))
coe = m.app.test_client()
r = login(coe, "coe", "Coe@123")
check("coe login lands on /coe",
      r.status_code == 302 and r.headers["Location"].endswith("/coe"))
check("accounts landing page loads", acc.get("/accounts").status_code == 200)
check("coe landing page loads", coe.get("/coe").status_code == 200)
r = acc.get("/admin")
check("accounts visiting /admin lands on /accounts",
      r.status_code == 302 and r.headers["Location"].endswith("/accounts"))
r = coe.get("/admin")
check("coe visiting /admin lands on /coe",
      r.status_code == 302 and r.headers["Location"].endswith("/coe"))
check("admin may open /accounts (superset)", admin.get("/accounts").status_code == 200)
check("admin may open /coe (superset)", admin.get("/coe").status_code == 200)
check("accounts refused /coe", denied(acc.get("/coe")))
check("coe refused /accounts", denied(coe.get("/accounts")))

stu = m.app.test_client()
login(stu, "student", "Student@123")
fac = m.app.test_client()
login(fac, "faculty", "Faculty@123")
check("student refused /accounts and /coe",
      denied(stu.get("/accounts")) and denied(stu.get("/coe")))
check("faculty refused /accounts and /coe",
      denied(fac.get("/accounts")) and denied(fac.get("/coe")))
check("faculty portal still loads", fac.get("/faculty").status_code == 200)

# ------------------------------------------------------- permission matrix: accounts
ACC_OK = ["/admin/fee-heads", "/admin/fee-plans", "/admin/vouchers",
          "/admin/vouchers/generate", "/admin/students",
          "/admin/students/export.xlsx", "/admin/reports",
          "/admin/reports/fees", "/admin/reports/fees.xlsx"]
ACC_NO = ["/admin/departments", "/admin/programs", "/admin/sessions",
          "/admin/courses", "/admin/faculty", "/admin/results",
          "/admin/grade-scale", "/admin/attendance", "/admin/clearance",
          "/admin/scholarships", "/admin/repeat", "/admin/timetable",
          "/admin/transport", "/admin/documents", "/admin/tickets",
          "/admin/notifications", "/admin/repository", "/admin/campus",
          "/admin/societies", "/admin/vehicle-passes", "/admin/audit",
          "/admin/backup", "/admin/staff", "/admin/reports/results",
          "/admin/reports/attendance", "/admin/reports/students",
          "/admin/students/new", "/admin/students/import"]
check("accounts: allowed fee/voucher/report/student pages load",
      all(acc.get(u).status_code == 200 for u in ACC_OK),
      str([(u, acc.get(u).status_code) for u in ACC_OK]))
check("accounts: everything else is refused (redirect)",
      all(denied(acc.get(u)) for u in ACC_NO),
      str([(u, acc.get(u).status_code) for u in ACC_NO]))
demo_student = db1("SELECT * FROM students WHERE registration_no='CUVAS-DEMO-2026-001'")
a_voucher = db1("SELECT * FROM vouchers WHERE student_id=? ORDER BY id",
                (demo_student["id"],))
check("accounts: voucher detail + challan PDF load",
      acc.get(f"/admin/vouchers/{a_voucher['id']}").status_code == 200
      and acc.get(f"/admin/vouchers/{a_voucher['id']}/challan.pdf").status_code == 200)
n_students = db1("SELECT COUNT(*) c FROM students")["c"]
r = acc.post("/admin/students/new", data={
    "registration_no": "HACK-001", "name": "Should Not Exist",
    "initial_password": ""})
check("accounts: student add POST refused + nothing created",
      denied(r) and db1("SELECT COUNT(*) c FROM students")["c"] == n_students
      and db1("SELECT id FROM students WHERE registration_no='HACK-001'") is None)
r = acc.post(f"/admin/students/{demo_student['id']}/delete")
check("accounts: student delete POST refused + student intact",
      denied(r) and db1("SELECT id FROM students WHERE id=?",
                        (demo_student["id"],)) is not None)
check("accounts: student transcript PDF refused",
      denied(acc.get(f"/admin/students/{demo_student['id']}/transcript.pdf")))

# ------------------------------------------------------- permission matrix: coe
COE_OK = ["/admin/results", "/admin/grade-scale", "/admin/students",
          "/admin/students/export.xlsx", "/admin/reports",
          "/admin/reports/results", "/admin/reports/results.xlsx",
          "/admin/reports/attendance", "/admin/reports/attendance.xlsx"]
COE_NO = ["/admin/fee-heads", "/admin/fee-plans", "/admin/vouchers",
          "/admin/departments", "/admin/faculty", "/admin/attendance",
          "/admin/clearance", "/admin/scholarships", "/admin/repeat",
          "/admin/timetable", "/admin/transport", "/admin/documents",
          "/admin/tickets", "/admin/notifications", "/admin/repository",
          "/admin/campus", "/admin/societies", "/admin/vehicle-passes",
          "/admin/audit", "/admin/backup", "/admin/staff",
          "/admin/reports/fees", "/admin/reports/students",
          "/admin/students/new", "/admin/students/import"]
check("coe: allowed results/report/student pages load",
      all(coe.get(u).status_code == 200 for u in COE_OK),
      str([(u, coe.get(u).status_code) for u in COE_OK]))
check("coe: everything else is refused (redirect)",
      all(denied(coe.get(u)) for u in COE_NO),
      str([(u, coe.get(u).status_code) for u in COE_NO]))
check("coe: transcript + single slip PDFs load",
      coe.get(f"/admin/students/{demo_student['id']}/transcript.pdf").status_code == 200
      and coe.get(f"/admin/students/{demo_student['id']}/slip.pdf").status_code == 200)
r = coe.get(f"/admin/slips.pdf?program_id={demo_student['program_id']}"
            f"&session_id={demo_student['session_id']}&semester_no=3")
check("coe: bulk slips PDF loads",
      r.status_code == 200 and r.data[:4] == b"%PDF", str(r.status_code))
r = coe.post(f"/admin/students/{demo_student['id']}/reset-password")
check("coe: student password reset POST refused",
      denied(r))
r = coe.post("/admin/vouchers/generate", data={})
check("coe: voucher generate POST refused", denied(r))

# ------------------------------------------------------- admin superset
ADMIN_OK = ["/admin", "/admin/staff", "/admin/audit", "/admin/backup",
            "/admin/reports", "/admin/reports/students",
            "/admin/reports/fees", "/admin/reports/results",
            "/admin/reports/attendance", "/admin/departments",
            "/admin/campus"]
check("admin: every area still loads",
      all(admin.get(u).status_code == 200 for u in ADMIN_OK),
      str([(u, admin.get(u).status_code) for u in ADMIN_OK]))

# ------------------------------------------------------- role-aware sidebars
acc_html = acc.get("/admin/students").get_data(as_text=True)
check("accounts sidebar: has Vouchers + Fee Plans links",
      'href="/admin/vouchers"' in acc_html and 'href="/admin/fee-plans"' in acc_html)
check("accounts sidebar: no Backup / Audit / Staff / Departments links",
      'href="/admin/backup"' not in acc_html
      and 'href="/admin/audit"' not in acc_html
      and 'href="/admin/staff"' not in acc_html
      and 'href="/admin/departments"' not in acc_html)
check("accounts students page: no Add/Import/Edit/Delete controls",
      "Add Student" not in acc_html and "Excel Import" not in acc_html
      and "Reset Password" not in acc_html and ">Delete<" not in acc_html)
coe_html = coe.get("/admin/students").get_data(as_text=True)
check("coe sidebar: has Results link, no Vouchers / Fee Heads links",
      'href="/admin/results"' in coe_html
      and 'href="/admin/vouchers"' not in coe_html
      and 'href="/admin/fee-heads"' not in coe_html)
check("coe students page: Transcript + Slip offered, no Edit/Delete",
      "Transcript PDF" in coe_html and "Roll Slip PDF" in coe_html
      and ">Delete<" not in coe_html and "Add Student" not in coe_html)
adm_html = admin.get("/admin/students").get_data(as_text=True)
check("admin sidebar: full link set incl. Staff + Backup-reachable pages",
      all(f'href="{u}"' in adm_html for u in
          ("/admin/vouchers", "/admin/departments", "/admin/results",
           "/admin/reports", "/admin/staff", "/admin/campus"))
      and "Add Student" in adm_html)
hub_acc = acc.get("/admin/reports").get_data(as_text=True)
check("reports hub is role-aware for accounts (fee card only)",
      "Fee Collection" in hub_acc and "Audit Log" not in hub_acc
      and "Results Summary" not in hub_acc and "Backup" not in hub_acc)
hub_coe = coe.get("/admin/reports").get_data(as_text=True)
check("reports hub is role-aware for coe (results + attendance only)",
      "Results Summary" in hub_coe and "Attendance Summary" in hub_coe
      and "Fee Collection" not in hub_coe and "Audit Log" not in hub_coe)

# ------------------------------------------------------- staff management
r = admin.post("/admin/staff", data={
    "username": "officer15", "display_name": "V15 Accounts Officer",
    "role": "accounts", "password": "Officer@123"})
check("staff create redirects + login listed",
      r.status_code == 302
      and "officer15" in admin.get("/admin/staff").get_data(as_text=True))
off = db1("SELECT * FROM users WHERE username='officer15'")
check("staff_created audited by admin",
      len(audit_rows("staff_created", "admin")) >= 1
      and any("officer15" in (a["details"] or "")
              for a in audit_rows("staff_created")))
offc = m.app.test_client()
r = login(offc, "officer15", "Officer@123")
check("new staff login works and lands on /accounts",
      r.status_code == 302 and r.headers["Location"].endswith("/accounts"))
r = admin.post("/admin/staff", data={
    "username": "weakling15", "display_name": "Weak Password",
    "role": "coe", "password": "weak"})
check("staff create with a weak password refused + nothing created",
      r.status_code == 200
      and db1("SELECT id FROM users WHERE username='weakling15'") is None)
for weak in ("abcdefgh", "12345678", "Sh0rt"):
    r = admin.post("/admin/staff", data={
        "username": f"weak-{weak}", "display_name": "Weak",
        "role": "accounts", "password": weak})
    check(f"password policy refuses '{weak}' on staff create",
          db1("SELECT id FROM users WHERE username=?",
              (f"weak-{weak}",)) is None)
r = admin.post("/admin/staff", data={
    "username": "officer15", "display_name": "Duplicate",
    "role": "coe", "password": "Officer@123"})
check("duplicate staff username refused",
      db1("SELECT COUNT(*) c FROM users WHERE username='officer15'")["c"] == 1)

# reset (typed) — policy enforced, shown once, old password dies
r = admin.post(f"/admin/staff/{off['id']}/reset-password",
               data={"new_password": "weak"})
lst = admin.get("/admin/staff").get_data(as_text=True)
check("staff reset with weak password refused",
      "Could not reset password" in lst)
r = admin.post(f"/admin/staff/{off['id']}/reset-password",
               data={"new_password": "Reset@1234"})
lst = admin.get("/admin/staff").get_data(as_text=True)
check("staff reset shows the new password once",
      "New password: Reset@1234" in lst)
check("staff_password_reset audited",
      len(audit_rows("staff_password_reset", "admin")) >= 1)
offc2 = m.app.test_client()
r = login(offc2, "officer15", "Officer@123")
check("old staff password no longer works", r.status_code == 200)
r = login(offc2, "officer15", "Reset@1234")
check("new staff password works",
      r.status_code == 302 and r.headers["Location"].endswith("/accounts"))

# deactivate / reactivate
r = admin.post(f"/admin/staff/{off['id']}/toggle-active")
offc3 = m.app.test_client()
r = login(offc3, "officer15", "Reset@1234")
check("deactivated staff login cannot sign in",
      r.status_code == 200 and "Invalid username or password" in r.get_data(as_text=True))
check("staff_deactivated audited",
      len(audit_rows("staff_deactivated", "admin")) >= 1)
r = admin.post(f"/admin/staff/{off['id']}/toggle-active")
offc4 = m.app.test_client()
r = login(offc4, "officer15", "Reset@1234")
check("reactivated staff login works again", r.status_code == 302)
check("staff_activated audited",
      len(audit_rows("staff_activated", "admin")) >= 1)

# primary admin is protected
admin_row = db1("SELECT * FROM users WHERE username='admin'")
admin.post(f"/admin/staff/{admin_row['id']}/toggle-active")
lst = admin.get("/admin/staff").get_data(as_text=True)
check("primary admin cannot be deactivated",
      "cannot be deactivated" in lst
      and db1("SELECT is_active FROM users WHERE username='admin'")["is_active"] == 1)
adm2 = m.app.test_client()
check("admin can still log in after the toggle attempt",
      login(adm2, "admin", "Admin@123").status_code == 302)
check("staff pages are admin-only",
      denied(acc.get("/admin/staff")) and denied(coe.get("/admin/staff")))

# ------------------------------------------------------- sign-in lockout
admin.post("/admin/staff", data={
    "username": "locktest15", "display_name": "Lock Test",
    "role": "coe", "password": "Lock@12345"})
lock_id = db1("SELECT id FROM users WHERE username='locktest15'")["id"]
c1 = m.app.test_client()
for i in range(4):
    r = login(c1, "locktest15", "wrong-pass")
check("4 failures do not lock yet", r.status_code == 200)
r = login(c1, "locktest15", "Lock@12345")
check("correct password still works after 4 failures (streak < 5)",
      r.status_code == 302)
c1.get("/logout")
for i in range(5):
    login(c1, "locktest15", "wrong-pass")
r = login(c1, "locktest15", "Lock@12345")
body = r.get_data(as_text=True)
check("after 5 failures the CORRECT password is refused (locked)",
      r.status_code == 200 and "locked" in body)
check("login_locked audited for the locked username",
      len(audit_rows("login_locked", "locktest15")) >= 1)
with m.app.app_context():
    streak = m._login_failure_streak(m.get_db(), "locktest15")
    locked = m._login_locked(m.get_db(), "locktest15")
check("lockout helpers agree (streak >= 5, locked)",
      streak >= 5 and locked, f"streak={streak}")
check("lockout is per-username: admin unaffected",
      login(m.app.test_client(), "admin", "Admin@123").status_code == 302)
# success clears the streak (fresh user, never reaches 5 in a row)
admin.post("/admin/staff", data={
    "username": "streak15", "display_name": "Streak Test",
    "role": "accounts", "password": "Streak@123"})
c2 = m.app.test_client()
for i in range(4):
    login(c2, "streak15", "nope-nope")
r = login(c2, "streak15", "Streak@123")
check("streak user: success after 4 failures", r.status_code == 302)
c2.get("/logout")
for i in range(4):
    login(c2, "streak15", "nope-nope")
r = login(c2, "streak15", "Streak@123")
check("success cleared the streak: 4 more failures still no lock",
      r.status_code == 302)
with m.app.app_context():
    check("streak helper reads 0 after the success",
          m._login_failure_streak(m.get_db(), "streak15") == 0)

# ------------------------------------------------------- password policy: students / faculty
dept = db1("SELECT * FROM departments ORDER BY id LIMIT 1")
prog = db1("SELECT * FROM programs ORDER BY id LIMIT 1")
sess = db1("SELECT * FROM academic_sessions ORDER BY id LIMIT 1")
sform = {"registration_no": "V15-POL-001", "cnic": "35202-1515151-5",
         "name": "Policy Student", "father_name": "Policy Father",
         "gender": "Male", "dob": "2005-01-01", "domicile": "Multan",
         "blood_group": "A+", "phone": "0300-1515151",
         "email": "pol15@example.com", "address_present": "Addr",
         "address_permanent": "Addr", "department_id": dept["id"],
         "program_id": prog["id"], "session_id": sess["id"],
         "campus": "Main Campus (Demo)", "status": "Active",
         "current_semester": 1, "initial_password": "weak"}
r = admin.post("/admin/students/new", data=sform)
check("student create with weak typed password refused + not created",
      r.status_code == 200 and "too short" in r.get_data(as_text=True)
      and db1("SELECT id FROM students WHERE registration_no='V15-POL-001'") is None)
sform["initial_password"] = "Strong@123"
r = admin.post("/admin/students/new", data=sform)
check("student create with a compliant typed password works",
      r.status_code == 302
      and db1("SELECT id FROM students WHERE registration_no='V15-POL-001'") is not None)
polc = m.app.test_client()
check("policy student logs in with the typed password",
      login(polc, "V15-POL-001", "Strong@123").status_code == 302)
pol_stu = db1("SELECT * FROM students WHERE registration_no='V15-POL-001'")
r = admin.post(f"/admin/students/{pol_stu['id']}/reset-password",
               data={"new_password": "weak"})
check("student reset with weak typed password refused",
      "Could not reset password" in admin.get("/admin/students").get_data(as_text=True))
check("student password unchanged after refused reset",
      login(m.app.test_client(), "V15-POL-001", "Strong@123").status_code == 302)
r = admin.post(f"/admin/students/{pol_stu['id']}/reset-password",
               data={"new_password": "Fresh@1234"})
check("student reset with compliant typed password works",
      login(m.app.test_client(), "V15-POL-001", "Fresh@1234").status_code == 302)
fform = {"full_name": "V15 Policy Teacher", "email": "pol15.teacher@example.com",
         "phone": "0300-1515152", "designation": "Lecturer",
         "department_id": dept["id"], "initial_password": "weak"}
r = admin.post("/admin/faculty/new", data=fform)
check("faculty create with weak typed password refused + not created",
      r.status_code == 200
      and db1("SELECT id FROM faculty WHERE email='pol15.teacher@example.com'") is None)
fform["initial_password"] = "Teach@123"
r = admin.post("/admin/faculty/new", data=fform)
check("faculty create with a compliant typed password works",
      r.status_code == 302
      and db1("SELECT id FROM faculty WHERE email='pol15.teacher@example.com'") is not None)

# ------------------------------------------------------- Excel import stays exempt
from openpyxl import Workbook
wb = Workbook()
ws = wb.active
ws.append(["Name", "Registration No", "CNIC", "Father Name", "Gender",
           "Date of Birth", "Department", "Program", "Session", "Campus",
           "Status", "Current Semester", "Phone", "Email", "Blood Group",
           "Domicile"])
ws.append(["V15 Imported One", "V15-IMP-001", "35202-1616161-6", "Imp Father",
           "Female", "2005-03-03", dept["name"], prog["name"], sess["name"],
           "Main Campus (Demo)", "Active", 1, "0300-1616161",
           "imp15@example.com", "A+", "Multan"])
buf = io.BytesIO()
wb.save(buf)
buf.seek(0)
r = admin.post("/admin/students/import", data={"file": (buf, "v15_import.xlsx")},
               content_type="multipart/form-data")
body = r.get_data(as_text=True)
check("Excel import still works (generated passwords exempt from policy)",
      r.status_code == 200 and "V15-IMP-001" in body)
creds = re.findall(r"(V15-IMP-001)</td><td>[^<]+</td><td><code>([^<]+)</code>", body)
check("imported student got a one-time password",
      len(creds) == 1, f"found {len(creds)}")
if creds:
    check("imported student can log in with the generated password",
          login(m.app.test_client(), creds[0][0], creds[0][1]).status_code == 302)

# ------------------------------------------------------- headers + cookies + upload cap
resp = m.app.test_client().get("/")
check("security headers on the landing page",
      resp.headers.get("X-Content-Type-Options") == "nosniff"
      and resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
      and resp.headers.get("Referrer-Policy") == "same-origin")
resp = admin.get("/admin")
check("security headers on an admin page too",
      resp.headers.get("X-Content-Type-Options") == "nosniff"
      and resp.headers.get("X-Frame-Options") == "SAMEORIGIN")
lc = m.app.test_client()
r = lc.post("/login", data={"username": "admin", "password": "Admin@123"})
set_cookie = r.headers.get("Set-Cookie", "")
check("session cookie is HttpOnly + SameSite=Lax",
      "HttpOnly" in set_cookie and "SameSite=Lax" in set_cookie, set_cookie)
check("cookie config: Lax + HttpOnly; Secure only when deployed (PG)",
      m.app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
      and m.app.config["SESSION_COOKIE_HTTPONLY"] is True
      and m.app.config["SESSION_COOKIE_SECURE"] is (True if m.PG else False))
big = io.BytesIO(b"x" * (10 * 1024 * 1024 + 1))
r = admin.post("/admin/students/import", data={"file": (big, "big.xlsx")},
               content_type="multipart/form-data")
check("upload over 10 MB refused with a friendly 413",
      r.status_code == 413 and b"10 MB" in r.data, str(r.status_code))

# ------------------------------------------------------- go-live demo toggle
anon = m.app.test_client()
home = anon.get("/").get_data(as_text=True)
check("homepage shows the demo-accounts box by default",
      "Demo accounts" in home and "Admin@123" in home
      and "Accounts@123" in home and "Coe@123" in home)
r = admin.post("/admin/backup/demo-accounts", data={})
check("toggle POST redirects back to the backup page",
      r.status_code == 302 and r.headers["Location"].endswith("/admin/backup"))
home = anon.get("/").get_data(as_text=True)
check("homepage demo box hidden after the toggle (no demo passwords)",
      "Demo accounts" not in home and "Admin@123" not in home
      and "Student@123" not in home)
check("demo_accounts_toggled audited",
      len(audit_rows("demo_accounts_toggled", "admin")) >= 1)
bp = admin.get("/admin/backup").get_data(as_text=True)
check("backup page carries the Go-Live card in the hidden state",
      "Go-Live" in bp and "does <strong>not</strong> show" in bp)
r = admin.post("/admin/backup/demo-accounts", data={"show_demo_accounts": "1"})
home = anon.get("/").get_data(as_text=True)
check("toggling back on restores the demo box",
      "Demo accounts" in home and "Admin@123" in home)
check("demo toggle is admin-only",
      denied(acc.post("/admin/backup/demo-accounts", data={})))

# ------------------------------------------------------- role migration (v0.14-shaped DB)
# A database created by v0.14-era code whose users table still
# carries the legacy CHECK(role IN ('admin','student')) must boot
# under v0.15, have the constraint widened, and accept + use the
# new staff roles. Runs in a subprocess so init_db re-runs.
MIG_SNIPPET = r'''
import json
import app as m
from werkzeug.security import generate_password_hash
out = {}
with m.app.app_context():
    db = m.get_db()
    if m.PG:
        rows = db.execute(
            "SELECT pg_get_constraintdef(con.oid) def FROM pg_constraint con "
            "JOIN pg_class rel ON rel.oid=con.conrelid "
            "WHERE rel.relname='users' AND con.contype='c'").fetchall()
        out["role_checks_left"] = sum(
            1 for r in rows if "role" in r["def"] and "accounts" not in r["def"])
    else:
        sql = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()["sql"]
        out["check_in_users_sql"] = "CHECK" in (sql or "").upper()
    for uname, role in (("migacc", "accounts"), ("migcoe", "coe")):
        db.insert("INSERT INTO users (username,password_hash,role,display_name) "
                  "VALUES (?,?,?,?)",
                  (uname, generate_password_hash("Mig@12345"), role, "Migrated"))
    db.commit()
    out["admin_still_there"] = db.execute(
        "SELECT COUNT(*) c FROM users WHERE username='admin'").fetchone()["c"]
    out["staff_seeded"] = db.execute(
        "SELECT COUNT(*) c FROM users WHERE username IN ('accounts','coe')"
    ).fetchone()["c"]
c = m.app.test_client()
r = c.post("/login", data={"username": "migacc", "password": "Mig@12345"})
out["migacc_login"] = [r.status_code, r.headers.get("Location", "")]
r = c.post("/login", data={"username": "migcoe", "password": "Mig@12345"})
out["migcoe_login"] = [r.status_code, r.headers.get("Location", "")]
r = c.post("/login", data={"username": "admin", "password": "Admin@123"})
out["admin_login"] = [r.status_code, r.headers.get("Location", "")]
print("MIGJSON " + json.dumps(out))
'''

mig_env = dict(os.environ)
mig_detail = ""
if m.PG:
    import psycopg
    base_uri = os.environ["DATABASE_URL"]
    mig_uri = base_uri.replace("/t_v15?", "/t_v15mig?") \
        if "/t_v15?" in base_uri else base_uri
    if mig_uri == base_uri:  # fall back: swap the db name in the path
        mig_uri = re.sub(r"/[^/?]+(\?|$)", "/t_v15mig\\1", base_uri, count=1)
    root = re.sub(r"/[^/?]+(\?|$)", "/postgres\\1", mig_uri, count=1)
    with psycopg.connect(root, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP DATABASE IF EXISTS t_v15mig")
            cur.execute("CREATE DATABASE t_v15mig")
    from werkzeug.security import generate_password_hash as _gph
    with psycopg.connect(mig_uri, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE users (id SERIAL PRIMARY KEY, "
                "username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, "
                "role TEXT NOT NULL CHECK (role IN ('admin','student')), "
                "display_name TEXT NOT NULL, student_id INTEGER)")
            cur.execute(
                "INSERT INTO users (username,password_hash,role,display_name) "
                "VALUES ('admin', %s, 'admin', 'Demo Admin')",
                (_gph("Admin@123"),))
    mig_env["DATABASE_URL"] = mig_uri
    mig_env.pop("DB_PATH", None)
else:
    import sqlite3
    from werkzeug.security import generate_password_hash as _gph
    mig_path = os.path.join(tempfile.mkdtemp(), "v14shaped.db")
    conn = sqlite3.connect(mig_path)
    conn.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, "
        "role TEXT NOT NULL CHECK(role IN ('admin','student')), "
        "display_name TEXT NOT NULL, student_id INTEGER)")
    conn.execute(
        "INSERT INTO users (username,password_hash,role,display_name) "
        "VALUES ('admin', ?, 'admin', 'Demo Admin')", (_gph("Admin@123"),))
    conn.commit()
    conn.close()
    mig_env["DB_PATH"] = mig_path
    mig_env.pop("DATABASE_URL", None)

mig_file = os.path.join(tempfile.mkdtemp(), "mig_snippet.py")
with open(mig_file, "w") as fh:
    fh.write(MIG_SNIPPET)
APP_DIR = os.path.dirname(os.path.abspath(m.__file__))
mig_env["PYTHONPATH"] = APP_DIR + os.pathsep + mig_env.get("PYTHONPATH", "")
proc = subprocess.run([sys.executable, mig_file], env=mig_env,
                      capture_output=True, text=True, cwd=APP_DIR)
mig = None
for line in proc.stdout.splitlines():
    if line.startswith("MIGJSON "):
        import json as _json
        mig = _json.loads(line[len("MIGJSON "):])
if mig is None:
    mig_detail = (proc.stdout + proc.stderr)[-600:]
check("v0.14-shaped DB boots under v0.15 (migration subprocess)",
      mig is not None, mig_detail)
if mig:
    if m.PG:
        check("migration dropped the restrictive PG role CHECK",
              mig["role_checks_left"] == 0, str(mig))
    else:
        check("migration rebuilt the SQLite users table without the CHECK",
              mig["check_in_users_sql"] is False, str(mig))
    check("migration kept the existing admin row + seeded demo staff",
          mig["admin_still_there"] == 1 and mig["staff_seeded"] == 2, str(mig))
    check("migrated DB: accounts + coe logins insertable and usable",
          mig["migacc_login"][0] == 302
          and mig["migacc_login"][1].endswith("/accounts")
          and mig["migcoe_login"][0] == 302
          and mig["migcoe_login"][1].endswith("/coe"), str(mig))
    check("migrated DB: original admin login still works",
          mig["admin_login"][0] == 302
          and mig["admin_login"][1].endswith("/admin"), str(mig))

# ------------------------------------------------------- student tabs untouched
dash = stu.get("/student").get_data(as_text=True)
LABELS = ["News Feed", "Profile", "Course Enrollments", "Plan Of Study",
          "Transcript", "Financial Voucher", "Fee Plan &amp; Scholarships",
          "Account Statement", "My Documents", "Support Tickets"]
check("student dashboard keeps exactly 10 tabs, labels byte-identical",
      dash.count("data-tab=") == 10
      and all(f">{label}<" in dash for label in LABELS))

print()
if FAIL:
    print(f"{len(FAIL)} FAILURE(S):")
    for f in FAIL:
        print(" -", f)
    sys.exit(1)
print("ALL V15 CHECKS PASSED")
