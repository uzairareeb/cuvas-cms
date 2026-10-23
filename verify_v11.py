"""Scripted verification for CUVAS CMS v0.11 — Step 15 course repeat /
improvement:
eligibility is computed from PUBLISHED results only (published F ->
Repeat, published pass -> Improvement, unpublished invisible); the
target session must differ from the original attempt's session; an
active request blocks duplicates; cancelling works only while
Requested; the admin rate (per credit hour) is changeable and a
change affects only vouchers issued afterwards; approving issues a
normal-series challan voucher (kind 'Repeat', repeat_request_id set,
amount = rate x credit hours, due = today + 14 days) with its ledger
debit, visible in the student's Financial Voucher tab + statement;
rejecting needs remarks and a decided request cannot be re-decided;
paying the voucher (proof upload -> admin verify) flips the request
to Enrolled and creates the target-session enrollment, while a
rejected proof activates nothing; the enrolled student joins the
marks-sheet cohort and the faculty roster for the target session;
the transcript then counts ONLY the latest attempt (web pane, the
shared helper and the PDF all agree; the earlier attempt is flagged
'Repeated'); the demo transcript stays at CGPA 3.63.

Expects a FRESH database (empty users table) so seeding + counts are exact.
Env: DB_PATH=<fresh sqlite file>  OR  DATABASE_URL=<postgres uri>.
Prints PASS/FAIL lines and exits non-zero if any check fails.
"""
import base64
import datetime
import io
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


def transcript_pane(html):
    part = html.split('id="pane-transcript"', 1)
    return part[1].split("<section", 1)[0] if len(part) > 1 else ""


def req_of(student_id, course_id, newest=True):
    rows = dbq("SELECT * FROM repeat_requests WHERE student_id=? AND course_id=? "
               "ORDER BY id DESC", (student_id, course_id))
    return rows[0] if rows else None


# ------------------------------------------------------- guards
anon = m.app.test_client()
check("anon repeat pages redirect",
      anon.get("/student/repeat").status_code == 302
      and anon.get("/admin/repeat").status_code == 302)
fac0 = m.app.test_client()
login(fac0, "faculty", "Faculty@123")
check("faculty blocked from repeat pages (both sides)",
      fac0.get("/admin/repeat").status_code == 302
      and fac0.get("/student/repeat").status_code == 302)
admin = m.app.test_client()
r = login(admin, "admin", "Admin@123")
check("admin login", r.status_code == 302 and "/admin" in r.headers["Location"])
check("admin blocked from /student/repeat",
      admin.get("/student/repeat").status_code == 302)
with m.app.app_context():
    rate0 = m.repeat_fee_per_ch(m.get_db())
check("repeat fee seeded at Rs 2000 per credit hour", rate0 == 2000, str(rate0))

# ------------------------------------------------------- fixtures (V11 namespace)
admin.post("/admin/departments/new", data={
    "name": "Dept of Repeats (V11)", "code": "REP-V11",
    "faculty_name": "Faculty (V11)"})
admin.post("/admin/sessions/new", data={
    "name": "Fall 2029 (V11)", "starts_on": "2029-09-01",
    "ends_on": "2030-01-31", "is_open": "1"})
admin.post("/admin/sessions/new", data={
    "name": "Spring 2030 (V11)", "starts_on": "2030-02-01",
    "ends_on": "2030-06-30", "is_open": "1"})
dept11 = db1("SELECT id FROM departments WHERE code='REP-V11'")["id"]
fall = db1("SELECT * FROM academic_sessions WHERE name='Fall 2029 (V11)'")
spring = db1("SELECT * FROM academic_sessions WHERE name='Spring 2030 (V11)'")
check("session ordering premise: Fall created before Spring (id order)",
      fall["id"] < spring["id"], f"{fall['id']} < {spring['id']}")
admin.post("/admin/programs/new", data={
    "name": "BS Repeats (V11)", "department_id": dept11,
    "degree_level": "BS", "duration_semesters": 8})
prog11 = db1("SELECT id FROM programs WHERE name='BS Repeats (V11)'")["id"]
courses = {}
for code, th, lab in [("V11-101", 3, 0), ("V11-102", 2, 0), ("V11-103", 3, 0)]:
    admin.post("/admin/courses/new", data={
        "program_id": prog11, "semester_no": 1, "code": code,
        "title": f"Course {code} (V11)", "credit_theory": th,
        "credit_lab": lab, "faculty_name": "Dr V11"})
    courses[code] = db1("SELECT * FROM courses WHERE code=?", (code,))
students = {}
for reg, name in [("V11-REG-001", "V11 Student One"),
                  ("V11-REG-002", "V11 Student Two")]:
    admin.post("/admin/students/new", data={
        "registration_no": reg, "name": name, "department_id": dept11,
        "program_id": prog11, "session_id": fall["id"], "status": "Active",
        "current_semester": 1, "initial_password": "Test@1234"})
    students[reg] = db1("SELECT id FROM students WHERE registration_no=?",
                        (reg,))["id"]
s1, s2 = students["V11-REG-001"], students["V11-REG-002"]


def sheet_save(course_id, session_id, form):
    return admin.post("/admin/results/sheet",
                      query_string={"course_id": course_id,
                                    "session_id": session_id}, data=form)


def sheet_publish(course_id, session_id, action="publish"):
    return admin.post("/admin/results/sheet/publish",
                      query_string={"course_id": course_id,
                                    "session_id": session_id},
                      data={"action": action})


# Fall attempts: S1 fails 101 (30), passes 102 (74); S2 passes 102 (74).
# 103 is saved for both (S1 90, S2 25) but NOT published yet.
sheet_save(courses["V11-101"]["id"], fall["id"], {f"marks_{s1}": "30"})
sheet_save(courses["V11-102"]["id"], fall["id"],
           {f"marks_{s1}": "74", f"marks_{s2}": "74"})
sheet_save(courses["V11-103"]["id"], fall["id"],
           {f"marks_{s1}": "90", f"marks_{s2}": "25"})
sheet_publish(courses["V11-101"]["id"], fall["id"])
sheet_publish(courses["V11-102"]["id"], fall["id"])

stu1 = m.app.test_client()
login(stu1, "V11-REG-001", "Test@1234")
stu2 = m.app.test_client()
login(stu2, "V11-REG-002", "Test@1234")
check("student blocked from /admin/repeat",
      stu1.get("/admin/repeat").status_code == 302)

# ------------------------------------------------------- eligibility from published only
page = stu1.get("/student/repeat").get_data(as_text=True)
check("eligible: failed V11-101 offered as Repeat",
      "V11-101" in page and "Repeat" in page)
check("eligible: passed V11-102 offered as Improvement",
      "V11-102" in page and "Improvement" in page)
check("unpublished V11-103 NOT offered (results unpublished)",
      "V11-103" not in page)
check("student page shows the seeded rate (Rs 2,000 per credit hour)",
      "Rs 2,000 per credit hour" in page)
with m.app.app_context():
    _t, base_cgpa, _ch = m.transcript_data(m.get_db(), s1, published_only=True)
# S1 so far: 101 F (0 x 3 CH) + 102 B 3.0 (x 2 CH) -> 6 / 5 = 1.2
check("baseline transcript CGPA 1.2 (hand-computed)", base_cgpa == 1.2,
      str(base_cgpa))
pane = transcript_pane(stu1.get("/student").get_data(as_text=True))
check("baseline web CGPA 1.2 + Repeat button in Transcript tab",
      "Overall CGPA: <strong>1.2</strong>" in pane
      and "Course Repeat / Improvement" in pane)
dash = stu1.get("/student").get_data(as_text=True)
check("dashboard still has exactly 10 tabs", dash.count("data-tab=") == 10)

# ------------------------------------------------------- apply guards
r = stu1.post("/student/repeat/apply", data={
    "course_id": courses["V11-101"]["id"],
    "target_session_id": fall["id"], "reason": "V11 same session"})
check("target == original session blocked (no request row)",
      r.status_code == 302 and req_of(s1, courses["V11-101"]["id"]) is None)
r = stu1.post("/student/repeat/apply", data={
    "course_id": courses["V11-103"]["id"],
    "target_session_id": spring["id"], "reason": "V11 unpublished"})
check("applying for an unpublished course blocked (no row)",
      r.status_code == 302 and req_of(s1, courses["V11-103"]["id"]) is None)
r = stu1.post("/student/repeat/apply", data={
    "course_id": courses["V11-101"]["id"],
    "target_session_id": spring["id"], "reason": "V11 reason one"})
req101 = req_of(s1, courses["V11-101"]["id"])
check("repeat request created: Requested/Repeat, Fall -> Spring, reason kept",
      r.status_code == 302 and req101 is not None
      and req101["status"] == "Requested" and req101["kind"] == "Repeat"
      and req101["from_session_id"] == fall["id"]
      and req101["target_session_id"] == spring["id"]
      and req101["reason"] == "V11 reason one", str(dict(req101 or {})))
stu1.post("/student/repeat/apply", data={
    "course_id": courses["V11-101"]["id"],
    "target_session_id": spring["id"], "reason": "V11 duplicate"})
rows101 = dbq("SELECT * FROM repeat_requests WHERE student_id=? AND course_id=?",
              (s1, courses["V11-101"]["id"]))
check("duplicate active request blocked (still 1 row)",
      len(rows101) == 1)

# ------------------------------------------------------- cancel flow (on 102)
stu1.post("/student/repeat/apply", data={
    "course_id": courses["V11-102"]["id"],
    "target_session_id": spring["id"], "reason": "V11 improve attempt"})
req102 = req_of(s1, courses["V11-102"]["id"])
check("improvement request created as Improvement/Requested",
      req102 is not None and req102["kind"] == "Improvement"
      and req102["status"] == "Requested")
stu2.post(f"/student/repeat/{req102['id']}/cancel")
check("another student cannot cancel it (still Requested)",
      req_of(s1, courses["V11-102"]["id"])["status"] == "Requested")
stu1.post(f"/student/repeat/{req102['id']}/cancel")
check("owner cancels while Requested -> Cancelled",
      req_of(s1, courses["V11-102"]["id"])["status"] == "Cancelled")
stu1.post("/student/repeat/apply", data={
    "course_id": courses["V11-102"]["id"],
    "target_session_id": spring["id"], "reason": "V11 improve retry"})
req102b = req_of(s1, courses["V11-102"]["id"])
check("re-apply after cancel creates a fresh Requested row",
      req102b is not None and req102b["id"] != req102["id"]
      and req102b["status"] == "Requested")

# ------------------------------------------------------- cross-student isolation
page2 = stu2.get("/student/repeat").get_data(as_text=True)
check("student Two's page shows none of student One's request data",
      "V11 reason one" not in page2 and "V11 Student One" not in page2)

# ------------------------------------------------------- publish 103 -> S2 eligible
sheet_publish(courses["V11-103"]["id"], fall["id"])
page2 = stu2.get("/student/repeat").get_data(as_text=True)
check("after publishing, S2 sees V11-103 as Repeat",
      "V11-103" in page2 and "Repeat" in page2)

# already-enrolled-in-target block (fixture enrollment inserted directly)
with m.app.app_context():
    db = m.get_db()
    db.insert("INSERT INTO enrollments (student_id,course_id,session_name,"
              "semester_no) VALUES (?,?,?,?)",
              (s2, courses["V11-103"]["id"], spring["name"], 1))
    db.commit()
stu2.post("/student/repeat/apply", data={
    "course_id": courses["V11-103"]["id"],
    "target_session_id": spring["id"], "reason": "V11 enrolled already"})
check("already enrolled in the target session blocked (no row)",
      req_of(s2, courses["V11-103"]["id"]) is None)
with m.app.app_context():
    db = m.get_db()
    db.execute("DELETE FROM enrollments WHERE student_id=? AND course_id=? "
               "AND session_name=?",
               (s2, courses["V11-103"]["id"], spring["name"]))
    db.commit()

# ------------------------------------------------------- admin: reject path (S1 / 102)
admin.post(f"/admin/repeat/{req102b['id']}/reject", data={"admin_remarks": "  "})
check("reject without remarks refused (still Requested)",
      req_of(s1, courses["V11-102"]["id"])["status"] == "Requested")
admin.post(f"/admin/repeat/{req102b['id']}/reject",
           data={"admin_remarks": "V11 reject reason"})
req102b = req_of(s1, courses["V11-102"]["id"])
check("rejected: remarks + decider stamped",
      req102b["status"] == "Rejected"
      and req102b["admin_remarks"] == "V11 reject reason"
      and req102b["decided_by"] == "Demo Admin" and req102b["decided_at"])
page = stu1.get("/student/repeat").get_data(as_text=True)
check("student sees Rejected + the rejection remarks",
      "Rejected" in page and "V11 reject reason" in page)
admin.post(f"/admin/repeat/{req102b['id']}/approve")
req102b = req_of(s1, courses["V11-102"]["id"])
check("a decided request cannot be re-decided (no voucher issued)",
      req102b["status"] == "Rejected" and req102b["voucher_id"] is None)

# ------------------------------------------------------- rate change -> approve S1/101
admin.post("/admin/repeat/rate", data={"rate": "2500"})
with m.app.app_context():
    rate_now = m.repeat_fee_per_ch(m.get_db())
check("admin rate change stored (2500)", rate_now == 2500, str(rate_now))
admin.post(f"/admin/repeat/{req101['id']}/approve")
req101 = req_of(s1, courses["V11-101"]["id"])
v101 = db1("SELECT * FROM vouchers WHERE id=?", (req101["voucher_id"],))
expected_due = (datetime.date.today() + datetime.timedelta(days=14)).isoformat()
check("approved: status + voucher linked + decider stamped",
      req101["status"] == "Approved" and req101["voucher_id"] is not None
      and req101["decided_by"] == "Demo Admin" and req101["decided_at"])
check("voucher: title/kind/link, amount = 2500 x 3 CH = 7500, due +14d",
      v101 is not None and v101["title"] == "Course Repeat — V11-101"
      and v101["kind"] == "Repeat"
      and v101["repeat_request_id"] == req101["id"]
      and v101["amount"] == 7500 and v101["due_date"] == expected_due
      and v101["status"] == "Pending", str(dict(v101 or {})))
check("voucher challan is in the normal CUVAS series",
      re.fullmatch(r"CUVAS-\d{4}-\d{4}", v101["challan_no"] or "") is not None,
      v101["challan_no"])
led = dbq("SELECT * FROM ledger_entries WHERE voucher_id=?", (v101["id"],))
check("ledger debit of 7500 written at voucher creation",
      len(led) == 1 and led[0]["debit"] == 7500 and led[0]["credit"] == 0)
n_v = db1("SELECT COUNT(*) c FROM vouchers WHERE student_id=?", (s1,))["c"]
admin.post(f"/admin/repeat/{req101['id']}/approve")
check("re-approving an Approved request issues no second voucher",
      db1("SELECT COUNT(*) c FROM vouchers WHERE student_id=?", (s1,))["c"] == n_v
      and req_of(s1, courses["V11-101"]["id"])["status"] == "Approved")
stu1.post(f"/student/repeat/{req101['id']}/cancel")
check("an Approved request cannot be cancelled by the student",
      req_of(s1, courses["V11-101"]["id"])["status"] == "Approved")

# voucher visible in the student's own lists, exactly like a fee voucher
dash = stu1.get("/student").get_data(as_text=True)
vpane = dash.split('id="pane-voucher"', 1)[1].split("<section", 1)[0]
spane = dash.split('id="pane-statement"', 1)[1].split("<section", 1)[0]
check("repeat voucher listed in the Financial Voucher tab",
      "Course Repeat — V11-101" in vpane and v101["challan_no"] in vpane)
check("repeat debit listed in the Account Statement",
      v101["challan_no"] in spane and "7,500" in spane)
pdf = stu1.get(f"/student/vouchers/{v101['id']}/challan.pdf")
check("repeat challan PDF downloads like any voucher",
      pdf.status_code == 200 and pdf.data[:5] == b"%PDF-")

# ------------------------------------------------------- rate back -> later approvals use it
admin.post("/admin/repeat/rate", data={"rate": "2000"})
stu2.post("/student/repeat/apply", data={
    "course_id": courses["V11-103"]["id"],
    "target_session_id": spring["id"], "reason": "V11 s2 repeat"})
req_s2_103 = req_of(s2, courses["V11-103"]["id"])
admin.post(f"/admin/repeat/{req_s2_103['id']}/approve")
req_s2_103 = req_of(s2, courses["V11-103"]["id"])
v_s2 = db1("SELECT * FROM vouchers WHERE id=?", (req_s2_103["voucher_id"],))
check("later approval uses the restored rate: 2000 x 3 CH = 6000",
      v_s2 is not None and v_s2["amount"] == 6000
      and v_s2["title"] == "Course Repeat — V11-103")
v101_again = db1("SELECT * FROM vouchers WHERE id=?", (v101["id"],))
check("the earlier voucher keeps its 7500 (rate change is not retroactive)",
      v101_again["amount"] == 7500)
check("challan series is sequential across repeat vouchers",
      int(v_s2["challan_no"].rsplit("-", 1)[1]) > int(v101["challan_no"].rsplit("-", 1)[1]))
stu2.post("/student/repeat/apply", data={
    "course_id": courses["V11-102"]["id"],
    "target_session_id": spring["id"], "reason": "V11 s2 improve"})
req_s2_102 = req_of(s2, courses["V11-102"]["id"])
admin.post(f"/admin/repeat/{req_s2_102['id']}/approve")
req_s2_102 = req_of(s2, courses["V11-102"]["id"])
v_s2i = db1("SELECT * FROM vouchers WHERE id=?", (req_s2_102["voucher_id"],))
check("improvement voucher: title + amount 2000 x 2 CH = 4000, kind Repeat",
      v_s2i is not None and v_s2i["title"] == "Course Improvement — V11-102"
      and v_s2i["amount"] == 4000 and v_s2i["kind"] == "Repeat")

# ------------------------------------------------------- payment activation (S1 / 101)
def spring_enrollment(student_id, course_id):
    return dbq("SELECT * FROM enrollments WHERE student_id=? AND course_id=? "
               "AND session_name=?", (student_id, course_id, spring["name"]))

check("before payment: no Spring enrollment for S1 in V11-101",
      spring_enrollment(s1, courses["V11-101"]["id"]) == [])
stu1.post(f"/student/vouchers/{v101['id']}/proof",
          data={"proof": (io.BytesIO(b"v11-proof-bytes"), "proof.png"),
                "payment_channel": "Bank"},
          content_type="multipart/form-data")
v101 = db1("SELECT * FROM vouchers WHERE id=?", (v101["id"],))
check("proof uploaded -> Proof Submitted", v101["status"] == "Proof Submitted")
admin.post(f"/admin/vouchers/{v101['id']}/reject",
           data={"remark": "V11 proof unreadable"})
v101 = db1("SELECT * FROM vouchers WHERE id=?", (v101["id"],))
check("rejected proof: voucher Pending again, request STILL Approved, "
      "no enrollment created",
      v101["status"] == "Pending"
      and req_of(s1, courses["V11-101"]["id"])["status"] == "Approved"
      and spring_enrollment(s1, courses["V11-101"]["id"]) == [])
stu1.post(f"/student/vouchers/{v101['id']}/proof",
          data={"proof": (io.BytesIO(b"v11-proof-bytes-2"), "proof2.png"),
                "payment_channel": "RAAST"},
          content_type="multipart/form-data")
admin.post(f"/admin/vouchers/{v101['id']}/verify")
v101 = db1("SELECT * FROM vouchers WHERE id=?", (v101["id"],))
req101 = req_of(s1, courses["V11-101"]["id"])
enr = spring_enrollment(s1, courses["V11-101"]["id"])
check("verified payment: voucher Paid + request Enrolled + enrollment created",
      v101["status"] == "Paid" and req101["status"] == "Enrolled"
      and len(enr) == 1 and enr[0]["semester_no"] == 1, str(dict(enr[0]) if enr else None))
credits = dbq("SELECT * FROM ledger_entries WHERE voucher_id=? AND credit>0",
              (v101["id"],))
check("exactly one ledger credit of 7500 for the repeat voucher",
      len(credits) == 1 and credits[0]["credit"] == 7500)
admin.post(f"/admin/vouchers/{v101['id']}/verify")
credits = dbq("SELECT * FROM ledger_entries WHERE voucher_id=? AND credit>0",
              (v101["id"],))
check("double verify refused: still one credit, request still Enrolled",
      len(credits) == 1
      and req_of(s1, courses["V11-101"]["id"])["status"] == "Enrolled"
      and len(spring_enrollment(s1, courses["V11-101"]["id"])) == 1)

# ------------------------------------------------------- cohort: sheet + faculty roster
sheet_html = admin.get("/admin/results/sheet", query_string={
    "course_id": courses["V11-101"]["id"],
    "session_id": spring["id"]}).get_data(as_text=True)
check("marks sheet cohort for Spring V11-101 contains the repeat student",
      "V11-REG-001" in sheet_html)
admin.post("/admin/faculty/new", data={
    "full_name": "V11 Teacher", "email": "v11.teacher@example.com",
    "phone": "0300-0000000", "designation": "Lecturer",
    "department_id": dept11, "initial_password": "Teach@123"})
fac11 = db1("SELECT * FROM faculty WHERE email='v11.teacher@example.com'")
admin.post(f"/admin/faculty/{fac11['id']}/assign", data={
    "course_id": courses["V11-101"]["id"], "session_id": spring["id"]})
asg = db1("SELECT * FROM course_assignments WHERE faculty_id=? AND course_id=? "
          "AND session_id=?", (fac11["id"], courses["V11-101"]["id"], spring["id"]))
fac_client = m.app.test_client()
login(fac_client, "v11.teacher@example.com", "Teach@123")
roster = fac_client.get(f"/faculty/course/{asg['id']}/students").get_data(as_text=True)
check("faculty roster for Spring V11-101 contains the repeat student",
      "V11-REG-001" in roster and "V11 Student One" in roster)

# ------------------------------------------------------- repeat marks + transcript rule
sheet_save(courses["V11-101"]["id"], spring["id"], {f"marks_{s1}": "85"})
stu1.post("/student/repeat/apply", data={
    "course_id": courses["V11-101"]["id"],
    "target_session_id": spring["id"], "reason": "V11 too soon"})
check("Enrolled request still blocks while the repeat result is unpublished",
      len(dbq("SELECT * FROM repeat_requests WHERE student_id=? AND course_id=? "
              "AND status='Requested'", (s1, courses["V11-101"]["id"]))) == 0)
sheet_publish(courses["V11-101"]["id"], spring["id"])
with m.app.app_context():
    db = m.get_db()
    tdata, new_cgpa, _ch = m.transcript_data(db, s1, published_only=True)
    rows101 = [r for b in tdata.values() for r in b["rows"]
               if r["code"] == "V11-101"]
    old = [r for r in rows101 if r["session_id"] == fall["id"]]
    new = [r for r in rows101 if r["session_id"] == spring["id"]]
    elig = m.repeat_eligibility(db, s1)
# counted attempts: 101 Spring A 4.0x3=12 + 102 B 3.0x2=6 + 103 A 4.0x3=12
# -> 30 / 8 = 3.75 ; the Fall F attempt is excluded.
check("transcript counts ONLY the latest attempt: CGPA 3.75 (hand-computed)",
      new_cgpa == 3.75, str(new_cgpa))
check("both attempts render; old flagged superseded, new one not",
      len(rows101) == 2 and len(old) == 1 and len(new) == 1
      and old[0]["superseded"] is True and new[0]["superseded"] is False)
pane = transcript_pane(stu1.get("/student").get_data(as_text=True))
check("web transcript: CGPA 3.75 + Repeated tag on the old attempt",
      "Overall CGPA: <strong>3.75</strong>" in pane and "Repeated" in pane)
tpdf = stu1.get("/student/transcript.pdf")
blob = pdf_text(tpdf.data)
check("transcript PDF: %PDF + Repeated tag + CGPA 3.75",
      tpdf.data[:5] == b"%PDF-" and b"Repeated" in blob and b"3.75" in blob)
check("after the repeat is published, V11-101 is eligible again as Improvement",
      any(e["code"] == "V11-101" and e["kind"] == "Improvement" for e in elig))

# ------------------------------------------------------- admin list surface
lst = admin.get("/admin/repeat").get_data(as_text=True)
check("admin list shows requests + counts + the rate",
      "V11 Student One" in lst and "V11 Student Two" in lst
      and "Enrolled: <strong>1</strong>" in lst
      and "Approved: <strong>2</strong>" in lst)
lst = admin.get("/admin/repeat", query_string={"status": "Enrolled"}
                ).get_data(as_text=True)
check("filter Enrolled -> only student One's request",
      "V11 Student One" in lst and "V11 Student Two" not in lst)
lst = admin.get("/admin/repeat", query_string={"q": "V11-REG-002"}
                ).get_data(as_text=True)
check("search by reg no -> only student Two's requests",
      "V11 Student Two" in lst and "V11 Student One" not in lst)
check("unknown request approve/reject -> 404",
      admin.post("/admin/repeat/999999/approve").status_code == 404
      and admin.post("/admin/repeat/999999/reject",
                     data={"admin_remarks": "x"}).status_code == 404)

# ------------------------------------------------------- demo sanity
demo = m.app.test_client()
login(demo, "student", "Student@123")
ddash = demo.get("/student").get_data(as_text=True)
with m.app.app_context():
    db = m.get_db()
    demo_row = db.execute(
        "SELECT id FROM students WHERE registration_no='CUVAS-DEMO-2026-001'"
    ).fetchone()
    _t, demo_cgpa, _ch = m.transcript_data(db, demo_row["id"],
                                           published_only=True)
    demo_superseded = any(r.get("superseded") for b in _t.values()
                          for r in b["rows"])
check("demo student: 10 tabs + CGPA 3.63 intact (helper + web)",
      ddash.count("data-tab=") == 10 and demo_cgpa == 3.63
      and "Overall CGPA: <strong>3.63</strong>" in transcript_pane(ddash))
check("demo transcript has no superseded rows (rule is a no-op without repeats)",
      demo_superseded is False)
check("demo student repeat page loads", demo.get("/student/repeat").status_code == 200)

print()
if FAIL:
    print(f"{len(FAIL)} FAILURES: {FAIL}")
    sys.exit(1)
print("ALL CHECKS PASSED")
