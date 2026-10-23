"""Scripted verification for CUVAS CMS v0.13 — Step 18 campus life:
admin-configured LMS / Library / Email service links + info
(app_settings) surface as identical cards on the student and faculty
Campus Life pages — a live button when a URL is set, a 'Not
configured yet' note when it is not — and an invalid (non-http) URL
is refused. Three demo societies are seeded (the IT one advised by
the demo teacher); students request to join from /student/campus,
duplicates are blocked, an admin approves (the student sees 'Member'
and the count moves) or rejects (the student may request again on the
same row); inactive societies are hidden from students; a society
with membership records cannot be deleted. Vehicle entry passes: a
student applies (the number is normalised to upper-case), a second
live request for the same vehicle is refused, an APPROVED vehicle
number belonging to another student is refused ('one vehicle, one
pass'), approval stamps pass_no VEH-<year>-<id> and a valid_till
defaulting to +1 year, the pass PDF is real %PDF bytes containing
the pass + vehicle numbers, is a 404 before approval and for another
student, rejection needs remarks (shown to the student), and a
decided pass cannot be re-decided. Role guards on every new page;
the student dashboard keeps exactly its 10 tabs.

Expects a FRESH database (empty users table) so seeding + counts are exact.
Env: DB_PATH=<fresh sqlite file>  OR  DATABASE_URL=<postgres uri>.
Prints PASS/FAIL lines and exits non-zero if any check fails.
"""
import base64
import datetime
import re
import sys
import zlib

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


def pdf_text(pdf_bytes):
    blob = b""
    for s in re.findall(rb"stream\r?\n(.*?)endstream", pdf_bytes, re.S):
        try:
            blob += zlib.decompress(base64.a85decode(s.strip(), adobe=True))
        except Exception:
            try:
                blob += zlib.decompress(s.strip())
            except Exception:
                pass
    return blob


LIT = "Literary Society"
SPORTS = "Sports Society"
IT = "IT &amp; Robotics Society"  # as rendered in HTML

# ------------------------------------------------------- guards / logins
anon = m.app.test_client()
check("anon new pages redirect",
      all(anon.get(p).status_code == 302 for p in
          ["/admin/campus", "/admin/societies", "/admin/vehicle-passes",
           "/student/campus", "/student/vehicle", "/faculty/campus"]))
admin = m.app.test_client()
r = login(admin, "admin", "Admin@123")
check("admin login", r.status_code == 302 and "/admin" in r.headers["Location"])
check("admin blocked from student + faculty campus pages",
      admin.get("/student/campus").status_code == 302
      and admin.get("/student/vehicle").status_code == 302
      and admin.get("/faculty/campus").status_code == 302)
fac0 = m.app.test_client()
login(fac0, "faculty", "Faculty@123")
check("faculty blocked from admin campus pages + student pages",
      fac0.get("/admin/campus").status_code == 302
      and fac0.get("/admin/societies").status_code == 302
      and fac0.get("/admin/vehicle-passes").status_code == 302
      and fac0.get("/student/campus").status_code == 302
      and fac0.get("/student/vehicle").status_code == 302)

stu = m.app.test_client()
login(stu, "student", "Student@123")
demo_sid = db1("SELECT id FROM students WHERE registration_no="
               "'CUVAS-DEMO-2026-001'")["id"]
check("student blocked from admin campus pages + faculty campus",
      stu.get("/admin/campus").status_code == 302
      and stu.get("/admin/societies").status_code == 302
      and stu.get("/admin/vehicle-passes").status_code == 302
      and stu.get("/faculty/campus").status_code == 302)

# ------------------------------------------------------- seeds (fresh DB)
socs = dbq("SELECT * FROM societies ORDER BY id")
check("societies seeded: exactly 3 on a fresh DB", len(socs) == 3,
      str(len(socs)))
check("seeded society names",
      [s["name"] for s in socs] == ["Literary Society", "Sports Society",
                                    "IT & Robotics Society"])
demo_teacher = db1("SELECT id FROM faculty WHERE email="
                   "'demo.teacher@cuvas.edu.pk'")
it_soc = [s for s in socs if s["name"] == "IT & Robotics Society"][0]
check("IT society advised by the demo teacher, the others NULL",
      it_soc["advisor_faculty_id"] == demo_teacher["id"]
      and all(s["advisor_faculty_id"] is None for s in socs
              if s["name"] != "IT & Robotics Society"))
check("seeded societies are active", all(s["is_active"] == 1 for s in socs))
keys = dbq("SELECT key, value FROM app_settings WHERE key IN "
           "('lms_url','library_url','library_info','email_url',"
           "'email_info')")
check("five campus settings keys seeded empty",
      len(keys) == 5 and all(k["value"] == "" for k in keys),
      str([(k["key"], k["value"]) for k in keys]))

# ------------------------------------------------------- Part A: settings
page = stu.get("/student/campus").get_data(as_text=True)
check("student campus: all three services 'Not configured yet' initially",
      page.count("Not configured yet") >= 3
      and "Open LMS" not in page and "Open Library / OPAC" not in page
      and "Open Email" not in page)
fpage = fac0.get("/faculty/campus").get_data(as_text=True)
check("faculty campus shows the same not-configured cards",
      "Not configured yet" in fpage and "Open LMS" not in fpage)

r = admin.post("/admin/campus", data={
    "lms_url": "lms.example.edu.pk", "library_url": "",
    "library_info": "", "email_url": "", "email_info": ""},
    follow_redirects=True)
check("invalid URL (no http scheme) refused and NOT saved",
      "must start with http" in r.get_data(as_text=True)
      and db1("SELECT value FROM app_settings WHERE key='lms_url'"
              )["value"] == "")

admin.post("/admin/campus", data={
    "lms_url": "https://lms.example.edu.pk",
    "library_url": "https://library.example.edu.pk",
    "library_info": "Open Mon-Sat, 8am-8pm (V13)",
    "email_url": "https://mail.example.edu.pk",
    "email_info": "Your email is your Reg No @students.example.edu.pk (V13)"})
vals = {r["key"]: r["value"] for r in dbq(
    "SELECT key, value FROM app_settings WHERE key IN "
    "('lms_url','library_url','library_info','email_url','email_info')")}
check("settings round-trip saved to app_settings",
      vals.get("lms_url") == "https://lms.example.edu.pk"
      and vals.get("library_info") == "Open Mon-Sat, 8am-8pm (V13)")
page = stu.get("/student/campus").get_data(as_text=True)
check("student campus shows the live buttons + info after saving",
      "Open LMS" in page and "https://lms.example.edu.pk" in page
      and "Open Library / OPAC" in page
      and "Open Mon-Sat, 8am-8pm (V13)" in page
      and "Open Email" in page
      and "Reg No @students.example.edu.pk (V13)" in page)
fpage = fac0.get("/faculty/campus").get_data(as_text=True)
check("faculty campus shows IDENTICAL cards (same links + info)",
      "Open LMS" in fpage and "https://lms.example.edu.pk" in fpage
      and "Open Mon-Sat, 8am-8pm (V13)" in fpage
      and "Open Email" in fpage)

admin.post("/admin/campus", data={
    "lms_url": "", "library_url": "https://library.example.edu.pk",
    "library_info": "Open Mon-Sat, 8am-8pm (V13)",
    "email_url": "https://mail.example.edu.pk",
    "email_info": "Your email is your Reg No @students.example.edu.pk (V13)"})
page = stu.get("/student/campus").get_data(as_text=True)
check("clearing the LMS URL brings back the note, others stay live",
      "Not configured yet" in page and "Open LMS" not in page
      and "Open Library / OPAC" in page and "Open Email" in page)
cpage = admin.get("/admin/campus").get_data(as_text=True)
check("admin campus links to Societies + Vehicle Passes with counts",
      "Manage Societies" in cpage and "Review Vehicle Passes" in cpage)

dash = stu.get("/student").get_data(as_text=True)
LABELS = ["News Feed", "Profile", "Course Enrollments", "Plan Of Study",
          "Transcript", "Financial Voucher", "Fee Plan &amp; Scholarships",
          "Account Statement", "My Documents", "Support Tickets"]
check("dashboard keeps exactly 10 tabs, labels byte-identical",
      dash.count("data-tab=") == 10
      and all(f">{label}<" in dash for label in LABELS))
check("dashboard Profile tab links Campus Life + Vehicle Entry",
      "Campus Life" in dash and "Vehicle Entry" in dash)

# ------------------------------------------------------- Part B: societies
page = stu.get("/student/campus").get_data(as_text=True)
check("student campus lists the 3 active societies + advisor + Join",
      LIT in page and SPORTS in page and IT in page
      and "Demo Teacher" in page and "Join" in page)
lit = [s for s in socs if s["name"] == "Literary Society"][0]
sports = [s for s in socs if s["name"] == "Sports Society"][0]

stu.post(f"/student/societies/{lit['id']}/join")
row = db1("SELECT * FROM society_members WHERE society_id=? AND "
          "student_id=?", (lit["id"], demo_sid))
check("join creates a Requested membership row",
      row is not None and row["status"] == "Requested")
page = stu.get("/student/campus").get_data(as_text=True)
check("student sees 'Requested — awaiting approval' after joining",
      "Requested — awaiting approval" in page)
stu.post(f"/student/societies/{lit['id']}/join", follow_redirects=True)
check("duplicate join blocked (still exactly one row, still Requested)",
      db1("SELECT COUNT(*) c FROM society_members WHERE society_id=? "
          "AND student_id=?", (lit["id"], demo_sid))["c"] == 1
      and db1("SELECT status FROM society_members WHERE society_id=? "
              "AND student_id=?", (lit["id"], demo_sid)
              )["status"] == "Requested")
spage = admin.get("/admin/societies").get_data(as_text=True)
check("admin societies list shows the pending count",
      "Pending" in spage and LIT in spage)
check("admin campus pending-societies count is 1",
      "1 membership request(s) waiting" in
      admin.get("/admin/campus").get_data(as_text=True))

admin.post(f"/admin/societies/{lit['id']}/members/{row['id']}/approve")
row = db1("SELECT * FROM society_members WHERE id=?", (row["id"],))
check("admin approve flips to Approved with the decision stamp",
      row["status"] == "Approved" and row["decided_by"] == "Demo Admin"
      and row["decided_at"])
page = stu.get("/student/campus").get_data(as_text=True)
check("student sees 'Member ✓' after approval",
      "Member ✓" in page)
check("approved-member count increments to 1 on the student page",
      db1("SELECT COUNT(*) c FROM society_members WHERE society_id=? "
          "AND status='Approved'", (lit["id"],))["c"] == 1)
r = admin.post(f"/admin/societies/{lit['id']}/members/{row['id']}/approve")
check("re-deciding a decided membership is refused",
      db1("SELECT status FROM society_members WHERE id=?",
          (row["id"],))["status"] == "Approved")

stu.post(f"/student/societies/{sports['id']}/join")
srow = db1("SELECT * FROM society_members WHERE society_id=? AND "
           "student_id=?", (sports["id"], demo_sid))
admin.post(f"/admin/societies/{sports['id']}/members/{srow['id']}/reject")
srow = db1("SELECT * FROM society_members WHERE id=?", (srow["id"],))
check("admin reject flips to Rejected with the stamp",
      srow["status"] == "Rejected" and srow["decided_by"] == "Demo Admin")
page = stu.get("/student/campus").get_data(as_text=True)
check("rejected student sees Rejected + 'Request again'",
      "Rejected" in page and "Request again" in page)
stu.post(f"/student/societies/{sports['id']}/join")
srow2 = db1("SELECT * FROM society_members WHERE society_id=? AND "
            "student_id=?", (sports["id"], demo_sid))
check("re-request reuses the SAME row, back to Requested, stamp cleared",
      srow2["id"] == srow["id"] and srow2["status"] == "Requested"
      and srow2["decided_by"] is None and srow2["decided_at"] is None)

r = admin.post(f"/admin/societies/{lit['id']}/delete",
               follow_redirects=True)
check("society delete BLOCKED while membership rows exist",
      "Cannot delete" in r.get_data(as_text=True)
      and db1("SELECT * FROM societies WHERE id=?", (lit["id"],))
      is not None)

admin.post("/admin/societies/new", data={
    "name": "Hidden Society (V13)", "description": "inactive fixture",
    "advisor_faculty_id": "", "is_active": ""})
hidden = db1("SELECT * FROM societies WHERE name='Hidden Society (V13)'")
check("society created without the active box is inactive",
      hidden is not None and hidden["is_active"] == 0)
page = stu.get("/student/campus").get_data(as_text=True)
check("inactive society hidden from students, visible to the admin",
      "Hidden Society (V13)" not in page
      and "Hidden Society (V13)" in
      admin.get("/admin/societies").get_data(as_text=True))
check("joining an inactive society is a 404",
      stu.post(f"/student/societies/{hidden['id']}/join").status_code == 404)
r = admin.post(f"/admin/societies/{hidden['id']}/delete")
check("memberless society CAN be deleted",
      r.status_code == 302 and db1(
          "SELECT * FROM societies WHERE id=?", (hidden["id"],)) is None)

admin.post(f"/admin/societies/{sports['id']}/members/{srow2['id']}/remove")
check("admin Remove deletes the membership row",
      db1("SELECT * FROM society_members WHERE id=?",
          (srow2["id"],)) is None)

# ------------------------------------------------------- Part C: vehicle
def apply_vehicle(client, vtype, vno, model="Honda CG 125", color="Black"):
    return client.post("/student/vehicle/apply", data={
        "vehicle_type": vtype, "vehicle_no": vno,
        "make_model": model, "color": color}, follow_redirects=True)


r = apply_vehicle(stu, "Motorcycle", "lea-777 ")
vp = db1("SELECT * FROM vehicle_passes WHERE student_id=?", (demo_sid,))
check("vehicle applied; number normalised to UPPER-case trimmed",
      vp is not None and vp["vehicle_no"] == "LEA-777"
      and vp["status"] == "Requested" and vp["vehicle_type"] == "Motorcycle")
vpage = stu.get("/student/vehicle").get_data(as_text=True)
check("student vehicle page lists the request as Requested",
      "LEA-777" in vpage and "Requested" in vpage)
check("pass PDF is a 404 BEFORE approval",
      stu.get(f"/student/vehicle/{vp['id']}/pass.pdf").status_code == 404)
r = apply_vehicle(stu, "Motorcycle", "LEA-777")
check("same student + same vehicle while Requested is refused",
      "already have a requested pass" in r.get_data(as_text=True)
      and db1("SELECT COUNT(*) c FROM vehicle_passes WHERE student_id=?",
              (demo_sid,))["c"] == 1)
r = stu.post("/student/vehicle/apply", data={
    "vehicle_type": "Hovercraft", "vehicle_no": "HOV-1",
    "make_model": "", "color": ""}, follow_redirects=True)
check("invalid vehicle type refused, no row",
      db1("SELECT * FROM vehicle_passes WHERE vehicle_no='HOV-1'") is None)

# fixture students Two + Three (created via the admin form, like v12)
admin.post("/admin/departments/new", data={
    "name": "Dept of Campus Life (V13)", "code": "CL-V13",
    "faculty_name": "Faculty (V13)"})
dept13 = db1("SELECT id FROM departments WHERE code='CL-V13'")["id"]
admin.post("/admin/programs/new", data={
    "name": "BS Campus Life (V13)", "department_id": dept13,
    "degree_level": "BS", "duration_semesters": 8})
prog13 = db1("SELECT * FROM programs WHERE name='BS Campus Life (V13)'")
sess13 = db1("SELECT * FROM academic_sessions WHERE is_open=1 "
             "ORDER BY id DESC LIMIT 1")
fixtures = {}
for reg, name in [("V13-REG-002", "V13 Student Two"),
                  ("V13-REG-003", "V13 Student Three")]:
    admin.post("/admin/students/new", data={
        "registration_no": reg, "name": name, "department_id": dept13,
        "program_id": prog13["id"], "session_id": sess13["id"],
        "status": "Active", "current_semester": 1,
        "initial_password": "Test@1234"})
    fixtures[reg] = db1("SELECT id FROM students WHERE registration_no=?",
                        (reg,))
two = fixtures["V13-REG-002"]
three = fixtures["V13-REG-003"]
stu2 = m.app.test_client()
login(stu2, "V13-REG-002", "Test@1234")
r = apply_vehicle(stu2, "Car", "lea-777", "Toyota Corolla", "White")
check("another student MAY request the same number while only Requested",
      db1("SELECT * FROM vehicle_passes WHERE student_id=? AND "
          "vehicle_no='LEA-777'", (two["id"],)) is not None)

r = admin.post(f"/admin/vehicle-passes/{vp['id']}/approve", data={},
               follow_redirects=True)
vp = db1("SELECT * FROM vehicle_passes WHERE id=?", (vp["id"],))
year = datetime.date.today().year
expected_till = datetime.date.today().replace(year=year + 1).isoformat() \
    if not (datetime.date.today().month == 2
            and datetime.date.today().day == 29) else \
    datetime.date.today().replace(year=year + 1, day=28).isoformat()
check("approval stamps pass_no VEH-<year>-<id> + valid_till = today + 1 year",
      vp["status"] == "Approved" and vp["pass_no"] == f"VEH-{year}-{vp['id']}"
      and vp["valid_till"] == expected_till,
      f"{vp['pass_no']} / {vp['valid_till']} vs {expected_till}")
other_req = db1("SELECT * FROM vehicle_passes WHERE student_id=? AND "
                "vehicle_no='LEA-777'", (two["id"],))
check("admin approving the first pass is fine; the OTHER request is "
      "still Requested", other_req["status"] == "Requested")
r = apply_vehicle(stu, "Motorcycle", "LEA-777")
check("same student duplicate while APPROVED is refused",
      "already have an approved pass" in r.get_data(as_text=True)
      and db1("SELECT COUNT(*) c FROM vehicle_passes WHERE student_id=? "
              "AND vehicle_no='LEA-777'", (demo_sid,))["c"] == 1)

stu3 = m.app.test_client()
login(stu3, "V13-REG-003", "Test@1234")
r = apply_vehicle(stu3, "Car", "LEA-777", "Suzuki Mehran", "Silver")
check("a THIRD student is refused: number already Approved elsewhere",
      "already holds an approved entry pass for another student"
      in r.get_data(as_text=True)
      and db1("SELECT * FROM vehicle_passes WHERE student_id=?",
              (three["id"],)) is None)

pdf = stu.get(f"/student/vehicle/{vp['id']}/pass.pdf")
txt = pdf_text(pdf.data)
check("pass PDF: %PDF bytes with pass no + vehicle no + title",
      pdf.status_code == 200 and pdf.data[:5] == b"%PDF-"
      and vp["pass_no"].encode() in txt and b"LEA-777" in txt
      and b"VEHICLE ENTRY PASS" in txt)
check("pass PDF for ANOTHER student is a 404",
      stu2.get(f"/student/vehicle/{vp['id']}/pass.pdf").status_code == 404)
check("pass PDF for a pass id that does not exist is a 404",
      stu.get("/student/vehicle/999999/pass.pdf").status_code == 404)

r = admin.post(f"/admin/vehicle-passes/{vp['id']}/approve", data={},
               follow_redirects=True)
vp2 = db1("SELECT * FROM vehicle_passes WHERE id=?", (vp["id"],))
check("decided pass cannot be re-approved",
      "already been decided" in r.get_data(as_text=True)
      and vp2["pass_no"] == vp["pass_no"])
r = admin.post(f"/admin/vehicle-passes/{vp['id']}/reject", data={
    "admin_remarks": "too late"}, follow_redirects=True)
check("decided pass cannot be rejected either",
      db1("SELECT status FROM vehicle_passes WHERE id=?",
          (vp["id"],))["status"] == "Approved")

r = apply_vehicle(stu, "Car", "xyz-999", "Suzuki Mehran", "Silver")
vpz = db1("SELECT * FROM vehicle_passes WHERE vehicle_no='XYZ-999'")
r = admin.post(f"/admin/vehicle-passes/{vpz['id']}/reject", data={
    "admin_remarks": ""}, follow_redirects=True)
check("reject WITHOUT remarks is refused (still Requested)",
      "Remarks are required" in r.get_data(as_text=True)
      and db1("SELECT status FROM vehicle_passes WHERE id=?",
              (vpz["id"],))["status"] == "Requested")
admin.post(f"/admin/vehicle-passes/{vpz['id']}/reject", data={
    "admin_remarks": "No parking slot available (V13)"})
vpz = db1("SELECT * FROM vehicle_passes WHERE id=?", (vpz["id"],))
check("reject with remarks stamps status + decider",
      vpz["status"] == "Rejected"
      and vpz["admin_remarks"] == "No parking slot available (V13)"
      and vpz["decided_by"] == "Demo Admin")
vpage = stu.get("/student/vehicle").get_data(as_text=True)
check("student sees the rejection remarks on their page",
      "No parking slot available (V13)" in vpage
      and "XYZ-999" in vpage)
r = apply_vehicle(stu, "Car", "XYZ-999", "Suzuki Mehran", "Silver")
check("after a REJECTION the same student may apply again",
      db1("SELECT COUNT(*) c FROM vehicle_passes WHERE vehicle_no="
          "'XYZ-999' AND status='Requested'")["c"] == 1)
lst = admin.get("/admin/vehicle-passes",
                query_string={"q": "xyz-999"}).get_data(as_text=True)
check("admin vehicle list search matches the vehicle number "
      "(case-insensitive via stored UPPER value)", "XYZ-999" in lst)
lst = admin.get("/admin/vehicle-passes",
                query_string={"status": "Approved"}).get_data(as_text=True)
check("admin vehicle status filter shows approved, hides requested",
      "LEA-777" in lst and "XYZ-999" not in lst)

print()
if FAIL:
    print(f"{len(FAIL)} FAILURES: {FAIL}")
    sys.exit(1)
print("ALL CHECKS PASSED")
