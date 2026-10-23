"""Scripted verification for CUVAS CMS v0.10 — Step 14 scholarships:
schemes seeded (2, open, no deadline); the socio-economic profile
save/update round-trip; applying is blocked until the profile is
complete (father/guardian name + monthly income) and blocked for a
closed scheme and a past-deadline scheme; a duplicate application in
the same session is blocked; the admin detail page shows the FULL
profile plus the demo student's CGPA 3.63 (same transcript helper) and
the ledger outstanding dues (Rs 47,500 via student_outstanding);
Under Review, then Approve needs an amount, then the student sees
Approved + amount + remarks; Reject needs remarks; a decided
application cannot be re-decided; the award never touches the fee
ledger; cross-student isolation (no profile/application data leaks);
admin-only routes reject student + faculty logins.

Expects a FRESH database (empty users table) so seeding + counts are exact.
Env: DB_PATH=<fresh sqlite file>  OR  DATABASE_URL=<postgres uri>.
Prints PASS/FAIL lines and exits non-zero if any check fails.
"""
import datetime
import sys

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


def scheme(name):
    rows = dbq("SELECT * FROM scholarship_schemes WHERE name=?", (name,))
    return rows[0] if rows else None


def profile_of(student_id):
    rows = dbq("SELECT * FROM scholarship_profiles WHERE student_id=?",
               (student_id,))
    return rows[0] if rows else None


def apps_of(student_id):
    return dbq("SELECT * FROM scholarship_applications WHERE student_id=? "
               "ORDER BY id", (student_id,))


def app_of(student_id, scheme_id):
    rows = dbq("SELECT * FROM scholarship_applications WHERE student_id=? "
               "AND scheme_id=?", (student_id, scheme_id))
    return rows[0] if rows else None


# ------------------------------------------------------- schemes seeded
schemes = dbq("SELECT * FROM scholarship_schemes ORDER BY id")
check("2 scholarship schemes seeded in order",
      [s["name"] for s in schemes] == ["Need-Based Scholarship",
                                       "Merit Scholarship"],
      str([s["name"] for s in schemes]))
check("seeded schemes open, deadline NULL, providers as specified",
      all(s["is_open"] == 1 and s["deadline"] is None for s in schemes)
      and schemes[0]["provider"] == "University / HEC"
      and schemes[1]["provider"] == "University"
      and "socio-economic profile" in schemes[0]["eligibility"]
      and "CGPA" in schemes[1]["eligibility"])
need, merit = schemes[0], schemes[1]

# ------------------------------------------------------- guards
anon = m.app.test_client()
check("anon scholarships pages redirect",
      anon.get("/student/scholarships").status_code == 302
      and anon.get("/admin/scholarships").status_code == 302)
fac = m.app.test_client()
login(fac, "faculty", "Faculty@123")
check("faculty blocked from scholarships (both sides)",
      fac.get("/admin/scholarships").status_code == 302
      and fac.get("/student/scholarships").status_code == 302)
admin = m.app.test_client()
r = login(admin, "admin", "Admin@123")
check("admin login", r.status_code == 302 and "/admin" in r.headers["Location"])
check("admin blocked from /student/scholarships",
      admin.get("/student/scholarships").status_code == 302)

# ------------------------------------------------------- fixtures (V10 namespace)
admin.post("/admin/departments/new", data={
    "name": "Dept of Scholarships (V10)", "code": "SCH-V10",
    "faculty_name": "Faculty (V10)"})
admin.post("/admin/sessions/new", data={
    "name": "Spring 2030 (V10)", "starts_on": "2030-02-01",
    "ends_on": "2030-06-30", "is_open": "1"})
dept10 = dbq("SELECT id FROM departments WHERE code='SCH-V10'")[0]["id"]
sess10 = dbq("SELECT id FROM academic_sessions WHERE name='Spring 2030 (V10)'"
             )[0]["id"]
admin.post("/admin/programs/new", data={
    "name": "BS Scholarships (V10)", "department_id": dept10,
    "degree_level": "BS", "duration_semesters": 8})
prog10 = dbq("SELECT id FROM programs WHERE name='BS Scholarships (V10)'"
             )[0]["id"]
students10 = {}
for reg, name in [("V10-REG-001", "V10 Student One"),
                  ("V10-REG-002", "V10 Student Two")]:
    admin.post("/admin/students/new", data={
        "registration_no": reg, "name": name, "department_id": dept10,
        "program_id": prog10, "session_id": sess10, "status": "Active",
        "current_semester": 8, "initial_password": "Test@1234"})
    students10[reg] = dbq("SELECT id FROM students WHERE registration_no=?",
                          (reg,))[0]["id"]
s1, s2 = students10["V10-REG-001"], students10["V10-REG-002"]
demo = dbq("SELECT * FROM students WHERE registration_no='CUVAS-DEMO-2026-001'"
           )[0]
with m.app.app_context():
    bal = m.student_outstanding(m.get_db(), demo["id"])
    ledger_before = m.get_db().execute(
        "SELECT COUNT(*) c FROM ledger_entries").fetchone()["c"]
check("fixture premise: demo student owes Rs 47,500 per the ledger",
      bal == 47500, str(bal))

# admin-side schemes fixtures: one closed, one past its deadline
admin.post("/admin/scholarships/schemes/new", data={
    "name": "V10 Closed Scheme", "provider": "V10 Provider",
    "description": "Closed fixture", "eligibility": "None",
    "is_open": "1"})  # the form's checkbox, ticked as a browser sends it
closed = scheme("V10 Closed Scheme")
check("scheme created via admin form (open when the box is ticked)",
      closed is not None and closed["is_open"] == 1)
admin.post(f"/admin/scholarships/schemes/{closed['id']}/edit", data={
    "name": "V10 Closed Scheme", "provider": "V10 Provider",
    "description": "Closed fixture", "eligibility": "None"})
closed = scheme("V10 Closed Scheme")
check("scheme edited with the open box unchecked -> closed",
      closed["is_open"] == 0)
yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
admin.post("/admin/scholarships/schemes/new", data={
    "name": "V10 Deadline Scheme", "provider": "V10 Provider",
    "description": "Deadline fixture", "eligibility": "None",
    "deadline": yesterday, "is_open": "1"})
deadline_scheme = scheme("V10 Deadline Scheme")
check("deadline scheme created open with yesterday's deadline stored",
      deadline_scheme is not None and deadline_scheme["is_open"] == 1
      and deadline_scheme["deadline"] == yesterday)

# ------------------------------------------------------- dashboard link + student guards
stu1 = m.app.test_client()
login(stu1, "V10-REG-001", "Test@1234")
check("student blocked from admin scholarship pages",
      stu1.get("/admin/scholarships").status_code == 302
      and stu1.get("/admin/scholarships/schemes/new").status_code == 302)
dash = stu1.get("/student").get_data(as_text=True)
check("dashboard: 10 tabs intact + Scholarships button in Fee Plan tab",
      dash.count("data-tab=") == 10
      and 'href="/student/scholarships"' in dash
      and "Scholarships — My Profile" in dash)

# ------------------------------------------------------- apply blocked without a profile
page = stu1.get("/student/scholarships").get_data(as_text=True)
check("student page: 3 sections + seeded schemes listed as open",
      "My Socio-Economic Profile" in page and "Open Scholarships" in page
      and "My Applications" in page and "Need-Based Scholarship" in page
      and "Merit Scholarship" in page and "No profile yet" in page)
check("closed scheme not offered to students",
      "V10 Closed Scheme" not in page)
check("deadline scheme shown as Closed (deadline passed)",
      "V10 Deadline Scheme" in page and "Closed (deadline passed)" in page)
r = stu1.post(f"/student/scholarships/{need['id']}/apply",
              data={"statement": "V10 premature application"})
check("apply without any profile -> redirect, NO application row",
      r.status_code == 302 and apps_of(s1) == [])
page = stu1.get("/student/scholarships").get_data(as_text=True)
check("friendly flash explains the profile must be completed first",
      "Complete your socio-economic profile before applying." in page)

# incomplete profile (guardian only, no income) still blocks
stu1.post("/student/scholarships/profile",
          data={"guardian_name": "V10 Guardian One"})
p = profile_of(s1)
check("partial profile saved (guardian name, income still empty)",
      p is not None and p["guardian_name"] == "V10 Guardian One"
      and p["monthly_income"] is None)
stu1.post(f"/student/scholarships/{need['id']}/apply",
          data={"statement": "V10 still incomplete"})
check("incomplete profile (no income) still blocks applying",
      apps_of(s1) == [])

# ------------------------------------------------------- profile save + update round-trip
stu1.post("/student/scholarships/profile", data={
    "father_name": "V10 Father One", "father_status": "Alive",
    "father_occupation": "V10 Farmer", "guardian_name": "V10 Guardian One",
    "guardian_relation": "Uncle", "family_members": "7",
    "siblings_studying": "3", "monthly_income": "45000",
    "monthly_expenses": "40000", "house_status": "Own",
    "bank_name": "V10 Test Bank", "account_title": "V10 Father One",
    "account_number": "V10-ACC-001", "bank_branch": "V10 Branch"})
p = profile_of(s1)
check("profile saved with all fields",
      p is not None and p["father_name"] == "V10 Father One"
      and p["father_status"] == "Alive"
      and p["father_occupation"] == "V10 Farmer"
      and p["family_members"] == 7 and p["siblings_studying"] == 3
      and p["monthly_income"] == 45000 and p["monthly_expenses"] == 40000
      and p["house_status"] == "Own" and p["bank_name"] == "V10 Test Bank"
      and p["account_number"] == "V10-ACC-001" and p["updated_at"],
      str(dict(p) if p else None))
page = stu1.get("/student/scholarships").get_data(as_text=True)
check("profile form prefilled + marked complete",
      "V10-ACC-001" in page and "Profile complete" in page)
stu1.post("/student/scholarships/profile", data={
    "father_name": "V10 Father One", "father_status": "Alive",
    "father_occupation": "V10 Farmer", "guardian_name": "V10 Guardian One",
    "guardian_relation": "Uncle", "family_members": "7",
    "siblings_studying": "3", "monthly_income": "52000",
    "monthly_expenses": "41000", "house_status": "Own",
    "bank_name": "V10 Test Bank", "account_title": "V10 Father One",
    "account_number": "V10-ACC-001", "bank_branch": "V10 Branch"})
rows = dbq("SELECT * FROM scholarship_profiles WHERE student_id=?", (s1,))
check("profile update round-trip (one row, income now 52,000)",
      len(rows) == 1 and rows[0]["monthly_income"] == 52000
      and rows[0]["monthly_expenses"] == 41000)

# ------------------------------------------------------- apply succeeds + duplicate blocked
r = stu1.post(f"/student/scholarships/{need['id']}/apply",
              data={"statement": "V10 statement from student one"})
app1 = app_of(s1, need["id"])
check("application created: Applied, current session, statement kept",
      r.status_code == 302 and app1 is not None
      and app1["status"] == "Applied"
      and app1["session_id"] == sess10
      and app1["statement"] == "V10 statement from student one",
      str(dict(app1) if app1 else None))
r = stu1.post(f"/student/scholarships/{need['id']}/apply",
              data={"statement": "V10 duplicate attempt"})
check("duplicate application in the same session blocked (still 1 row)",
      r.status_code == 302 and len(apps_of(s1)) == 1)
page = stu1.get("/student/scholarships").get_data(as_text=True)
check("scheme now shows Already applied; application listed as Applied",
      "Already applied" in page and "Need-Based Scholarship" in page)

# ------------------------------------------------------- closed + deadline schemes blocked
stu1.post(f"/student/scholarships/{closed['id']}/apply",
          data={"statement": "V10 closed attempt"})
check("applying to a closed scheme blocked (no row)",
      app_of(s1, closed["id"]) is None and len(apps_of(s1)) == 1)
stu1.post(f"/student/scholarships/{deadline_scheme['id']}/apply",
          data={"statement": "V10 late attempt"})
check("applying after the deadline blocked (no row)",
      app_of(s1, deadline_scheme["id"]) is None and len(apps_of(s1)) == 1)

# ------------------------------------------------------- demo student applies to Merit
demo_stu = m.app.test_client()
login(demo_stu, "student", "Student@123")
demo_stu.post("/student/scholarships/profile", data={
    "father_name": "Demo Father", "father_status": "Alive",
    "father_occupation": "Demo Occupation", "family_members": "5",
    "siblings_studying": "2", "monthly_income": "60000",
    "monthly_expenses": "55000", "house_status": "Rented",
    "bank_name": "V10 Demo Bank", "account_title": "Demo Father",
    "account_number": "V10-DEMO-ACC", "bank_branch": "Demo Branch"})
demo_stu.post(f"/student/scholarships/{merit['id']}/apply",
              data={"statement": "V10 demo merit statement"})
dapp = app_of(demo["id"], merit["id"])
check("demo student application created (Merit, Applied)",
      dapp is not None and dapp["status"] == "Applied")

# ------------------------------------------------------- admin lists + filters
lst = admin.get("/admin/scholarships").get_data(as_text=True)
check("admin list: schemes with counts + both applications",
      "Need-Based Scholarship" in lst and "V10 Student One" in lst
      and "Demo Student" in lst and "Applied: <strong>2</strong>" in lst)
lst = admin.get("/admin/scholarships",
                query_string={"scheme_id": merit["id"]}).get_data(as_text=True)
check("filter by scheme Merit -> demo application only",
      "Demo Student" in lst and "V10 Student One" not in lst)
lst = admin.get("/admin/scholarships",
                query_string={"q": "V10-REG-001"}).get_data(as_text=True)
check("search by registration no -> student One only",
      "V10 Student One" in lst and "Demo Student" not in lst)
lst = admin.get("/admin/scholarships",
                query_string={"status": "Approved"}).get_data(as_text=True)
check("filter Approved matches nothing yet",
      "V10 Student One" not in lst and "Demo Student" not in lst)
check("admin detail of unknown application -> 404",
      admin.get("/admin/scholarships/applications/999999").status_code == 404)
check("student blocked from the admin application detail",
      stu1.get(f"/admin/scholarships/applications/{dapp['id']}"
               ).status_code == 302)

# ------------------------------------------------------- admin detail: profile + CGPA + dues
det = admin.get(f"/admin/scholarships/applications/{dapp['id']}"
                ).get_data(as_text=True)
check("admin detail shows identity + scheme + statement",
      "Demo Student" in det and "CUVAS-DEMO-2026-001" in det
      and "Merit Scholarship" in det and "V10 demo merit statement" in det)
check("admin detail shows the FULL socio-economic profile",
      "V10 Demo Bank" in det and "V10-DEMO-ACC" in det
      and "60,000" in det and "Demo Occupation" in det
      and "Rented" in det)
check("admin detail: CGPA 3.63 (transcript helper) + dues Rs 47,500",
      "3.63" in det and "47,500" in det)

# ------------------------------------------------------- decisions: review, approve
r = admin.post(f"/admin/scholarships/applications/{dapp['id']}/decide",
               data={"decision": "Approve",
                     "admin_remarks": "V10 trying without amount"})
dapp_now = app_of(demo["id"], merit["id"])
check("approve without an awarded amount is refused (still Applied)",
      dapp_now["status"] == "Applied" and dapp_now["decided_at"] is None)
admin.post(f"/admin/scholarships/applications/{dapp['id']}/decide",
           data={"decision": "Under Review"})
dapp_now = app_of(demo["id"], merit["id"])
check("Under Review set (no decision stamp yet)",
      dapp_now["status"] == "Under Review"
      and dapp_now["decided_at"] is None)
admin.post(f"/admin/scholarships/applications/{dapp['id']}/decide",
           data={"decision": "Approve", "awarded_amount": "25000",
                 "admin_remarks": "V10 approved: strong merit case"})
dapp_now = app_of(demo["id"], merit["id"])
check("approved: amount + remarks + decider stamped",
      dapp_now["status"] == "Approved"
      and dapp_now["awarded_amount"] == 25000
      and dapp_now["admin_remarks"] == "V10 approved: strong merit case"
      and dapp_now["decided_by"] == "Demo Admin"
      and dapp_now["decided_at"], str(dict(dapp_now)))
page = demo_stu.get("/student/scholarships").get_data(as_text=True)
check("student sees Approved + Rs 25,000 + the admin remarks",
      "Approved" in page and "25,000" in page
      and "V10 approved: strong merit case" in page)
det = admin.get(f"/admin/scholarships/applications/{dapp['id']}"
                ).get_data(as_text=True)
check("decided application: form replaced by the final-decision note",
      "Decisions are final" in det and 'name="decision"' not in det)
admin.post(f"/admin/scholarships/applications/{dapp['id']}/decide",
           data={"decision": "Reject",
                 "admin_remarks": "V10 trying to overturn"})
dapp_now = app_of(demo["id"], merit["id"])
check("a decided application cannot be re-decided",
      dapp_now["status"] == "Approved"
      and dapp_now["awarded_amount"] == 25000
      and dapp_now["admin_remarks"] == "V10 approved: strong merit case")

# ------------------------------------------------------- reject needs remarks
admin.post(f"/admin/scholarships/applications/{app1['id']}/decide",
           data={"decision": "Reject", "admin_remarks": "   "})
app1_now = app_of(s1, need["id"])
check("reject without remarks is refused (still Applied)",
      app1_now["status"] == "Applied" and app1_now["decided_at"] is None)
admin.post(f"/admin/scholarships/applications/{app1['id']}/decide",
           data={"decision": "Reject",
                 "admin_remarks": "V10 rejection: documents incomplete"})
app1_now = app_of(s1, need["id"])
check("rejected: remarks + decider stamped, no award",
      app1_now["status"] == "Rejected"
      and app1_now["admin_remarks"] == "V10 rejection: documents incomplete"
      and app1_now["awarded_amount"] is None
      and app1_now["decided_by"] == "Demo Admin" and app1_now["decided_at"])
page = stu1.get("/student/scholarships").get_data(as_text=True)
check("student One sees Rejected + the rejection remarks",
      "Rejected" in page
      and "V10 rejection: documents incomplete" in page)

# ------------------------------------------------------- cross-student isolation
stu2 = m.app.test_client()
login(stu2, "V10-REG-002", "Test@1234")
page2 = stu2.get("/student/scholarships").get_data(as_text=True)
check("student Two sees none of student One's profile data",
      "V10 Father One" not in page2 and "V10-ACC-001" not in page2
      and "V10 Test Bank" not in page2 and "52,000" not in page2)
check("student Two sees none of the others' applications or remarks",
      "V10 statement from student one" not in page2
      and "V10 rejection: documents incomplete" not in page2
      and "V10 approved: strong merit case" not in page2
      and "No applications yet." in page2 and apps_of(s2) == [])

# ------------------------------------------------------- scheme delete guard
admin.post(f"/admin/scholarships/schemes/{need['id']}/delete")
check("scheme with applications cannot be deleted",
      scheme("Need-Based Scholarship") is not None)
admin.post(f"/admin/scholarships/schemes/{deadline_scheme['id']}/delete")
check("scheme without applications can be deleted",
      scheme("V10 Deadline Scheme") is None)

# ------------------------------------------------------- ledger + demo sanity
with m.app.app_context():
    bal = m.student_outstanding(m.get_db(), demo["id"])
    ledger_after = m.get_db().execute(
        "SELECT COUNT(*) c FROM ledger_entries").fetchone()["c"]
check("approving a scholarship never touched the fee ledger",
      bal == 47500 and ledger_after == ledger_before,
      f"balance={bal} rows {ledger_before}->{ledger_after}")
ddash = demo_stu.get("/student").get_data(as_text=True)
check("demo student: 10 tabs + CGPA 3.63 untouched by v0.10",
      ddash.count("data-tab=") == 10 and "3.63" in ddash)

print()
if FAIL:
    print(f"{len(FAIL)} FAILURES: {FAIL}")
    sys.exit(1)
print("ALL CHECKS PASSED")
