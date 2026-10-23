"""Scripted verification for CUVAS CMS v0.9 — Step 13 clearance:
units seeded (7, Accounts flagged); a student WITH dues applies and the
Accounts item is auto-Objected with the amount from the real ledger
computation, a zero-balance student gets it auto-Cleared by 'System';
duplicate apply blocked; admin object (remark REQUIRED) -> student sees
the remark -> Request Recheck -> item Pending + flag on the admin desk
-> admin clears -> progress syncs everywhere; admin override of the
auto-Objected Accounts item keeps its system note; the request flips to
Cleared + completed_at only when every item is Cleared; the certificate
PDF is blocked before completion and downloads after (student + admin);
cross-student isolation (404 on foreign item actions, no data leak);
unit management (add / rename / deactivate) shapes only NEW
applications while existing snapshot items stay untouched.

Expects a FRESH database (empty users table) so seeding + counts are exact.
Env: DB_PATH=<fresh sqlite file>  OR  DATABASE_URL=<postgres uri>.
Prints PASS/FAIL lines and exits non-zero if any check fails.
"""
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


def items_of(req_id):
    return dbq("SELECT * FROM clearance_items WHERE request_id=? ORDER BY id",
               (req_id,))


def item(req_id, unit_name):
    rows = dbq("SELECT * FROM clearance_items WHERE request_id=? AND unit_name=?",
               (req_id, unit_name))
    return rows[0] if rows else None


def request_of(student_id):
    rows = dbq("SELECT * FROM clearance_requests WHERE student_id=? ORDER BY id DESC",
               (student_id,))
    return rows[0] if rows else None


# ------------------------------------------------------- units seeded
units = dbq("SELECT * FROM clearance_units ORDER BY sort_order, id")
check("7 clearance units seeded in order",
      [u["name"] for u in units] == ["Accounts / Fees", "Library", "Hostel",
                                     "Examinations (COE)", "Department",
                                     "Sports", "Transport"],
      str([u["name"] for u in units]))
check("Accounts unit flagged is_accounts, all seeded units active",
      units[0]["is_accounts"] == 1
      and all(u["is_accounts"] == 0 for u in units[1:])
      and all(u["is_active"] == 1 for u in units))

# ------------------------------------------------------- guards
anon = m.app.test_client()
check("anon /student/clearance redirects", anon.get("/student/clearance").status_code == 302)
check("anon /admin/clearance redirects", anon.get("/admin/clearance").status_code == 302)
admin = m.app.test_client()
r = login(admin, "admin", "Admin@123")
check("admin login", r.status_code == 302 and "/admin" in r.headers["Location"])
check("admin blocked from /student/clearance", admin.get("/student/clearance").status_code == 302)
fac = m.app.test_client()
login(fac, "faculty", "Faculty@123")
check("faculty blocked from clearance (both sides)",
      fac.get("/admin/clearance").status_code == 302
      and fac.get("/student/clearance").status_code == 302)

# ------------------------------------------------------- fixtures (V9 namespace)
admin.post("/admin/departments/new", data={
    "name": "Dept of Clearance (V9)", "code": "CLR-V9", "faculty_name": "Faculty (V9)"})
admin.post("/admin/sessions/new", data={
    "name": "Spring 2029 (V9)", "starts_on": "2029-02-01", "ends_on": "2029-06-30",
    "is_open": "1"})
dept9 = dbq("SELECT id FROM departments WHERE code='CLR-V9'")[0]["id"]
sess9 = dbq("SELECT id FROM academic_sessions WHERE name='Spring 2029 (V9)'")[0]["id"]
admin.post("/admin/programs/new", data={
    "name": "BS Clearance (V9)", "department_id": dept9, "degree_level": "BS",
    "duration_semesters": 8})
prog9 = dbq("SELECT id FROM programs WHERE name='BS Clearance (V9)'")[0]["id"]
students9 = {}
for reg, name in [("V9-REG-001", "V9 Student One"), ("V9-REG-002", "V9 Student Two"),
                  ("V9-REG-003", "V9 Student Three")]:
    admin.post("/admin/students/new", data={
        "registration_no": reg, "name": name, "department_id": dept9,
        "program_id": prog9, "session_id": sess9, "status": "Active",
        "current_semester": 8, "initial_password": "Test@1234"})
    students9[reg] = dbq("SELECT id FROM students WHERE registration_no=?",
                         (reg,))[0]["id"]
s1, s2, s3 = students9["V9-REG-001"], students9["V9-REG-002"], students9["V9-REG-003"]
demo = dbq("SELECT * FROM students WHERE registration_no='CUVAS-DEMO-2026-001'")[0]
with m.app.app_context():
    bal = m.student_outstanding(m.get_db(), demo["id"])
check("fixture premise: demo student owes Rs 47,500 per the ledger",
      bal == 47500, str(bal))
check("fixture premise: V9 students have a zero ledger balance",
      dbq("SELECT COUNT(*) c FROM ledger_entries WHERE student_id IN (?,?,?)",
          (s1, s2, s3))[0]["c"] == 0)

# ------------------------------------------------------- zero-balance apply (auto-clear)
stu1 = m.app.test_client()
login(stu1, "V9-REG-001", "Test@1234")
check("student blocked from admin clearance pages",
      stu1.get("/admin/clearance").status_code == 302
      and stu1.get("/admin/clearance/units").status_code == 302)
dash = stu1.get("/student").get_data(as_text=True)
check("dashboard: 10 tabs intact + My Clearance button in Profile",
      dash.count("data-tab=") == 10 and "My Clearance" in dash
      and 'href="/student/clearance"' in dash)
page = stu1.get("/student/clearance").get_data(as_text=True)
check("no request yet: explanation + Apply button + unit names",
      "Apply for Clearance" in page and "Accounts / Fees" in page
      and "Library" in page)
r = stu1.post("/student/clearance/apply")
check("apply redirects", r.status_code == 302)
req1 = request_of(s1)
items1 = items_of(req1["id"]) if req1 else []
acc1 = item(req1["id"], "Accounts / Fees") if req1 else None
check("request created In Progress with one item per active unit (7)",
      req1 is not None and req1["status"] == "In Progress" and len(items1) == 7)
check("zero balance -> Accounts auto-Cleared by System with the note",
      acc1 is not None and acc1["status"] == "Cleared"
      and acc1["auto_note"] == "System check: no outstanding dues."
      and acc1["action_by"] == "System" and acc1["action_at"],
      str(dict(acc1) if acc1 else None))
check("other units start Pending with no note/action",
      all(i["status"] == "Pending" and not i["auto_note"] and not i["action_by"]
          for i in items1 if i["unit_name"] != "Accounts / Fees"))
page = stu1.get("/student/clearance").get_data(as_text=True)
check("student page shows progress 1 of 7 cleared",
      "1 of 7 cleared" in page)
r = stu1.post("/student/clearance/apply")
check("duplicate apply blocked (still exactly one request)",
      r.status_code == 302
      and len(dbq("SELECT id FROM clearance_requests WHERE student_id=?",
                  (s1,))) == 1)
cert = stu1.get("/student/clearance/certificate.pdf")
check("certificate blocked for student while In Progress",
      cert.status_code == 302 and not cert.data.startswith(b"%PDF"))
acert = admin.get(f"/admin/clearance/{req1['id']}/certificate.pdf")
check("certificate blocked for admin while In Progress",
      acert.status_code == 302 and not acert.data.startswith(b"%PDF"))

# ------------------------------------------------------- dues apply (auto-object)
demo_stu = m.app.test_client()
login(demo_stu, "student", "Student@123")
r = demo_stu.post("/student/clearance/apply")
reqd = request_of(demo["id"])
accd = item(reqd["id"], "Accounts / Fees") if reqd else None
check("dues -> Accounts auto-Objected with the amount in the system note",
      accd is not None and accd["status"] == "Objected"
      and accd["auto_note"] == "System check: outstanding dues of Rs 47,500."
      and accd["action_by"] == "System",
      str(dict(accd) if accd else None))
check("dues request: other 6 items Pending, request In Progress",
      reqd["status"] == "In Progress"
      and sum(1 for i in items_of(reqd["id"]) if i["status"] == "Pending") == 6)
page = demo_stu.get("/student/clearance").get_data(as_text=True)
check("demo student page: 0 of 7 cleared + dues note visible",
      "0 of 7 cleared" in page and "Rs 47,500" in page)

# ------------------------------------------------------- cross-student isolation
stu2 = m.app.test_client()
login(stu2, "V9-REG-002", "Test@1234")
page2 = stu2.get("/student/clearance").get_data(as_text=True)
check("student Two sees only the apply state — no leak of the demo request",
      "Apply for Clearance" in page2 and "CUVAS-DEMO-2026-001" not in page2
      and "47,500" not in page2)
r = stu2.post(f"/student/clearance/items/{accd['id']}/recheck")
check("student Two recheck on the demo item -> 404, item untouched",
      r.status_code == 404
      and item(reqd["id"], "Accounts / Fees")["status"] == "Objected"
      and item(reqd["id"], "Accounts / Fees")["recheck_requested"] == 0)
cert = stu2.get("/student/clearance/certificate.pdf")
check("student Two (no request) certificate blocked",
      cert.status_code == 302 and not cert.data.startswith(b"%PDF"))

# ------------------------------------------------------- admin desk: list + filters
lst = admin.get("/admin/clearance").get_data(as_text=True)
check("admin list shows both requests with progress",
      "V9 Student One" in lst and "Demo Student" in lst
      and "1 of 7 cleared" in lst and "0 of 7 cleared" in lst)
lst = admin.get("/admin/clearance", query_string={"q": "CUVAS-DEMO-2026-001"}
                ).get_data(as_text=True)
check("admin list search finds the demo request only",
      "Demo Student" in lst and "V9 Student One" not in lst)
lst = admin.get("/admin/clearance", query_string={"status": "Cleared"}
                ).get_data(as_text=True)
check("admin list filter Cleared matches nothing yet",
      "Demo Student" not in lst and "V9 Student One" not in lst)
check("admin detail of unknown request -> 404",
      admin.get("/admin/clearance/999999").status_code == 404)
check("admin item actions on unknown item -> 404",
      admin.post("/admin/clearance/items/999999/clear").status_code == 404
      and admin.post("/admin/clearance/items/999999/object",
                     data={"remark": "x"}).status_code == 404)

# ------------------------------------------------------- object -> recheck -> clear
lib = item(reqd["id"], "Library")
r = admin.post(f"/admin/clearance/items/{lib['id']}/object", data={"remark": "  "})
check("objection without a remark is refused (item stays Pending)",
      r.status_code == 302
      and item(reqd["id"], "Library")["status"] == "Pending")
r = admin.post(f"/admin/clearance/items/{lib['id']}/object",
               data={"remark": "V9: overdue book not returned"})
lib = item(reqd["id"], "Library")
check("objection recorded with remark + admin stamped",
      lib["status"] == "Objected"
      and lib["remarks"] == "V9: overdue book not returned"
      and lib["action_by"] == "Demo Admin" and lib["action_at"])
page = demo_stu.get("/student/clearance").get_data(as_text=True)
check("student sees the objection remark + Recheck button",
      "V9: overdue book not returned" in page and "Request Recheck" in page)
# a recheck on a merely-Pending item does nothing
hos = item(reqd["id"], "Hostel")
demo_stu.post(f"/student/clearance/items/{hos['id']}/recheck")
check("recheck on a Pending item is refused (no flag set)",
      item(reqd["id"], "Hostel")["recheck_requested"] == 0)
r = demo_stu.post(f"/student/clearance/items/{lib['id']}/recheck")
lib = item(reqd["id"], "Library")
check("recheck: item back to Pending, flagged, remark kept as history",
      r.status_code == 302 and lib["status"] == "Pending"
      and lib["recheck_requested"] == 1
      and lib["remarks"] == "V9: overdue book not returned")
det = admin.get(f"/admin/clearance/{reqd['id']}").get_data(as_text=True)
check("admin desk flags the recheck request",
      "Recheck requested" in det)
r = admin.post(f"/admin/clearance/items/{lib['id']}/clear", data={"remark": ""})
lib = item(reqd["id"], "Library")
check("admin clears the rechecked item (flag reset, stamped)",
      lib["status"] == "Cleared" and lib["recheck_requested"] == 0
      and lib["action_by"] == "Demo Admin")

# ------------------------------------------------------- clear the rest, then override Accounts
for unit_name in ("Hostel", "Examinations (COE)", "Department", "Sports",
                  "Transport"):
    it = item(reqd["id"], unit_name)
    admin.post(f"/admin/clearance/items/{it['id']}/clear",
               data={"remark": f"Cleared (V9) — {unit_name}"})
page = demo_stu.get("/student/clearance").get_data(as_text=True)
reqd_now = request_of(demo["id"])
check("6 of 7 cleared, Accounts still Objected -> still In Progress",
      "6 of 7 cleared" in page and reqd_now["status"] == "In Progress"
      and reqd_now["completed_at"] is None)
acert = admin.get(f"/admin/clearance/{reqd['id']}/certificate.pdf")
check("certificate still blocked for admin at 6 of 7",
      acert.status_code == 302 and not acert.data.startswith(b"%PDF"))
acc_id = item(reqd["id"], "Accounts / Fees")["id"]
r = admin.post(f"/admin/clearance/items/{acc_id}/clear",
               data={"remark": "Dues settled at the bank (V9)"})
accd = item(reqd["id"], "Accounts / Fees")
reqd_now = request_of(demo["id"])
check("admin override clears the auto-Objected Accounts item",
      accd["status"] == "Cleared" and accd["action_by"] == "Demo Admin"
      and accd["remarks"] == "Dues settled at the bank (V9)")
check("override keeps the original system note visible",
      accd["auto_note"] == "System check: outstanding dues of Rs 47,500.")
check("all items Cleared -> request Cleared + completed_at set",
      reqd_now["status"] == "Cleared" and reqd_now["completed_at"])
page = demo_stu.get("/student/clearance").get_data(as_text=True)
check("student page: completion banner + system note still shown + cert button",
      "All units have cleared you" in page and "Rs 47,500" in page
      and "/student/clearance/certificate.pdf" in page)
det = admin.get(f"/admin/clearance/{reqd['id']}").get_data(as_text=True)
check("admin detail also keeps the system note after override",
      "outstanding dues of Rs 47,500" in det)

# ------------------------------------------------------- certificates after completion
cert = demo_stu.get("/student/clearance/certificate.pdf")
check("student certificate downloads as a real PDF after completion",
      cert.status_code == 200 and cert.data[:5] == b"%PDF-"
      and len(cert.data) > 1000, f"{cert.status_code} {len(cert.data)}B")
acert = admin.get(f"/admin/clearance/{reqd['id']}/certificate.pdf")
check("admin certificate downloads as a real PDF after completion",
      acert.status_code == 200 and acert.data[:5] == b"%PDF-")
r = demo_stu.post("/student/clearance/apply")
check("apply after Cleared is blocked (still one request)",
      r.status_code == 302
      and len(dbq("SELECT id FROM clearance_requests WHERE student_id=?",
                  (demo["id"],))) == 1)

# ------------------------------------------------------- unit management shapes NEW applications only
units_page = admin.get("/admin/clearance/units").get_data(as_text=True)
check("units page lists the 7 seeded units + Accounts badge",
      all(n in units_page for n in ("Accounts / Fees", "Library", "Transport"))
      and "Accounts — auto-checked" in units_page)
admin.post("/admin/clearance/units", data={"name": "V9 Extra Unit"})
check("unit added (8 total)",
      len(dbq("SELECT id FROM clearance_units")) == 8)
admin.post("/admin/clearance/units", data={"name": "V9 Extra Unit"})
check("duplicate unit name refused (still 8)",
      len(dbq("SELECT id FROM clearance_units")) == 8)
extra = dbq("SELECT * FROM clearance_units WHERE name='V9 Extra Unit'")[0]
admin.post(f"/admin/clearance/units/{extra['id']}/rename",
           data={"name": "V9 Alumni Office"})
check("unit renamed",
      dbq("SELECT name FROM clearance_units WHERE id=?",
          (extra["id"],))[0]["name"] == "V9 Alumni Office")
sports = dbq("SELECT * FROM clearance_units WHERE name='Sports'")[0]
admin.post(f"/admin/clearance/units/{sports['id']}/toggle")
check("Sports deactivated",
      dbq("SELECT is_active FROM clearance_units WHERE id=?",
          (sports["id"],))[0]["is_active"] == 0)

stu3 = m.app.test_client()
login(stu3, "V9-REG-003", "Test@1234")
stu3.post("/student/clearance/apply")
req3 = request_of(s3)
items3 = items_of(req3["id"]) if req3 else []
names3 = [i["unit_name"] for i in items3]
check("new application excludes the deactivated unit, includes the added one",
      "Sports" not in names3 and "V9 Alumni Office" in names3
      and len(items3) == 7, str(names3))
check("new application still auto-clears Accounts for a zero balance",
      item(req3["id"], "Accounts / Fees")["status"] == "Cleared")
check("existing request snapshot untouched (demo request still has Sports)",
      len(items_of(reqd["id"])) == 7
      and item(reqd["id"], "Sports") is not None
      and item(reqd["id"], "Sports")["status"] == "Cleared")
admin.post(f"/admin/clearance/units/{sports['id']}/toggle")
check("Sports reactivated",
      dbq("SELECT is_active FROM clearance_units WHERE id=?",
          (sports["id"],))[0]["is_active"] == 1)

# ------------------------------------------------------- demo sanity
ddash = demo_stu.get("/student").get_data(as_text=True)
check("demo student: 10 tabs + CGPA 3.63 untouched by v0.9",
      ddash.count("data-tab=") == 10 and "3.63" in ddash)
with m.app.app_context():
    bal = m.student_outstanding(m.get_db(), demo["id"])
check("clearance never wrote to the ledger (demo still owes 47,500)",
      bal == 47500)

print()
if FAIL:
    print(f"{len(FAIL)} FAILURES: {FAIL}")
    sys.exit(1)
print("ALL CHECKS PASSED")
