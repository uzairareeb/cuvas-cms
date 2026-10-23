"""Scripted verification for CUVAS CMS v0.16 — Step: student portal shell.

MY IUB-style student frame: every student page renders inside
student_base.html (left sidebar with identity block, Home, 'My Apps' and
'Scholarships' groups, Document Repository; the current page's item is
highlighted). Module navigation moved out of the dashboard tab panes
into the sidebar; the panes keep only functional actions. The dashboard
keeps its 10 tabs byte-identical and deep-links via ?tab=<pane>;
/student/documents, /student/tickets and /student/scholarships/profile
are GET aliases onto the matching pane/section.

Expects a FRESH database (empty users table) so seeding + counts are exact.
Env: DB_PATH=<fresh sqlite file>  OR  DATABASE_URL=<postgres uri>.
Prints PASS/FAIL lines and exits non-zero if any check fails.
"""
import io
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


def pane(html, pane_id):
    part = html.split(f'id="pane-{pane_id}"', 1)
    return part[1].split("<section", 1)[0] if len(part) > 1 else ""


def upload(client, url, fields, filename, payload, mime):
    data = dict(fields)
    data["file"] = (io.BytesIO(payload), filename, mime)
    return client.post(url, data=data, content_type="multipart/form-data")


SIDEBAR_LABELS = ["Home", "My Apps", "My Documents", "My Fee Vouchers",
                  "Support Tickets", "My Attendance", "My Clearance",
                  "Scholarships", "Course Repeat / Improvement",
                  "View Time Table", "Transport", "Campus Life",
                  "Vehicle Entry", "My Student Card", "My Scholarship Profile",
                  "Apply / My Applications", "Document Repository", "Sign out"]
SIDEBAR_HREFS = ['href="/student/documents"', 'href="/student?tab=voucher"',
                 'href="/student/tickets"', 'href="/student/attendance"',
                 'href="/student/clearance"', 'href="/student/scholarships"',
                 'href="/student/repeat"', 'href="/student/timetable"',
                 'href="/student/transport"', 'href="/student/campus"',
                 'href="/student/vehicle"', 'href="/student/card.pdf"',
                 'href="/student/scholarships/profile"',
                 'href="/student?tab=news#repository"']

# --------------------------------------------------------------- guards
anon = m.app.test_client()
check("anon student pages redirect to login",
      anon.get("/student").status_code == 302
      and anon.get("/student/attendance").status_code == 302
      and anon.get("/student/documents").status_code == 302
      and anon.get("/student/tickets").status_code == 302
      and anon.get("/student/scholarships/profile").status_code == 302)
fac = m.app.test_client()
login(fac, "faculty", "Faculty@123")
check("faculty blocked from the student shell",
      fac.get("/student").status_code == 302
      and fac.get("/student/documents").status_code == 302
      and fac.get("/student/campus").status_code == 302)

admin = m.app.test_client()
login(admin, "admin", "Admin@123")
check("admin blocked from the student shell",
      admin.get("/student").status_code == 302)

# ------------------------------------------------- dashboard in the shell
stu = m.app.test_client()
r = login(stu, "student", "Student@123")
check("demo student login lands on the dashboard",
      r.status_code == 302 and r.headers["Location"].endswith("/student"))
dash = stu.get("/student").get_data(as_text=True)
check("dashboard renders inside the student shell",
      "student-sidebar" in dash and "student-layout" in dash
      and '<aside class="sidebar student-sidebar">' in dash)
check("sidebar identity block (name / reg no / program)",
      "Demo Student" in dash and "CUVAS-DEMO-2026-001" in dash
      and "BS Computer Science (Demo)" in dash)
check("sidebar carries every My Apps + Scholarships label",
      all(lbl in dash for lbl in SIDEBAR_LABELS),
      ", ".join(lbl for lbl in SIDEBAR_LABELS if lbl not in dash))
check("sidebar links point at the modules",
      all(h in dash for h in SIDEBAR_HREFS),
      ", ".join(h for h in SIDEBAR_HREFS if h not in dash))
check("sidebar groups labelled My Apps + Scholarships",
      '<div class="nav-label">My Apps</div>' in dash
      and '<div class="nav-label">Scholarships</div>' in dash)
LABELS = ["News Feed", "Profile", "Course Enrollments", "Plan Of Study",
          "Transcript", "Financial Voucher", "Fee Plan &amp; Scholarships",
          "Account Statement", "My Documents", "Support Tickets"]
check("dashboard keeps exactly 10 tabs, labels byte-identical",
      dash.count("data-tab=") == 10
      and all(f">{label}<" in dash for label in LABELS))
check("Home is the active sidebar item on the plain dashboard",
      '<a class="active" href="/student">' in dash
      and '<a class="active" href="/student/attendance">' not in dash)
check("dashboard JS supports #pane deep links too",
      "location.hash" in dash)

# ------------------------------------------------------- panes de-cluttered
prof = pane(dash, "profile")
check("Profile pane: navigation buttons removed",
      all(x not in prof for x in ("My Clearance", "Campus Life",
                                  "Vehicle Entry", "Download Student Card",
                                  'href="/student/transport"'))
      and "Personal &amp; Academic Profile" in prof)
enr = pane(dash, "enrollments")
check("Enrollments pane: My Attendance / View Time Table buttons removed",
      "My Attendance" not in enr and "View Time Table" not in enr
      and "Course Enrollments" in enr)
tr = pane(dash, "transcript")
check("Transcript pane: Repeat button removed, PDF downloads kept",
      "Course Repeat / Improvement" not in tr
      and "Download Transcript (PDF)" in tr
      and "Roll Number Slip (PDF)" in tr
      and "Overall CGPA: <strong>3.63</strong>" in tr)
vo = pane(dash, "voucher")
check("Voucher pane: functional actions kept (challan / split / proof)",
      "Challan PDF" in vo and "Create 2 Installments" in vo
      and "Submit Paid Proof" in vo)
docs = pane(dash, "documents")
check("Documents pane: upload form kept",
      'action="/student/documents/upload"' in docs and "Upload Document" in docs)
ticks = pane(dash, "tickets")
check("Tickets pane: create form kept", "Create Ticket" in ticks)

# ------------------------------------------------------------- deep links
d = stu.get("/student?tab=voucher").get_data(as_text=True)
check("?tab=voucher activates the Financial Voucher pane",
      'var active = "voucher"' in d)
check("?tab=voucher highlights My Fee Vouchers in the sidebar",
      '<a class="active" href="/student?tab=voucher">' in d)
d = stu.get("/student?tab=documents").get_data(as_text=True)
check("?tab=documents activates the My Documents pane + sidebar item",
      'var active = "documents"' in d
      and '<a class="active" href="/student/documents">' in d)
d = stu.get("/student?tab=tickets").get_data(as_text=True)
check("?tab=tickets activates the Support Tickets pane + sidebar item",
      'var active = "tickets"' in d
      and '<a class="active" href="/student/tickets">' in d)
d = stu.get("/student?tab=news").get_data(as_text=True)
check("News pane carries the Document Repository anchor",
      'id="repository"' in d and "Document Repository" in d)
r = stu.get("/student/documents")
check("GET /student/documents alias -> documents pane",
      r.status_code == 302
      and r.headers["Location"].endswith("/student?tab=documents"))
r = stu.get("/student/tickets")
check("GET /student/tickets alias -> tickets pane",
      r.status_code == 302
      and r.headers["Location"].endswith("/student?tab=tickets"))
r = stu.get("/student/scholarships/profile")
check("GET /student/scholarships/profile alias -> profile section",
      r.status_code == 302
      and r.headers["Location"].endswith("/student/scholarships?view=profile#profile"))

# ------------------------------------------------- sub-pages in the shell
SUBPAGES = [
    ("/student/attendance", "/student/attendance", "My Attendance"),
    ("/student/clearance", "/student/clearance", "My Clearance"),
    ("/student/repeat", "/student/repeat", "Course Repeat / Improvement"),
    ("/student/timetable", "/student/timetable", "My Time Table"),
    ("/student/transport", "/student/transport", "Transport"),
    ("/student/campus", "/student/campus", "Campus Life"),
    ("/student/vehicle", "/student/vehicle", "Vehicle Entry Pass"),
]
for url, active_href, marker in SUBPAGES:
    page = stu.get(url).get_data(as_text=True)
    check(f"{url} renders in the shell with its own item active",
          "student-sidebar" in page
          and f'<a class="active" href="{active_href}">' in page
          and marker in page)
page = stu.get("/student/transport").get_data(as_text=True)
check("transport page content intact (seeded route + stop search)",
      "City Side" in page and 'name="q"' in page)
page = stu.get("/student/campus").get_data(as_text=True)
check("campus page content intact (seeded societies)",
      "Literary Society" in page and "Sports Society" in page)
page = stu.get("/student/vehicle").get_data(as_text=True)
check("vehicle page content intact (apply form)",
      'name="vehicle_no"' in page and "Request Pass" in page)
page = stu.get("/student/timetable").get_data(as_text=True)
check("timetable page keeps its functional PDF download",
      'href="/student/timetable.pdf"' in page)
page = stu.get("/student/scholarships").get_data(as_text=True)
check("scholarships page in shell, applications item active",
      "student-sidebar" in page
      and '<a class="active" href="/student/scholarships">' in page
      and 'id="profile"' in page and 'id="applications"' in page
      and 'name="father_name"' in page)
page = stu.get("/student/scholarships?view=profile").get_data(as_text=True)
check("scholarships ?view=profile highlights My Scholarship Profile",
      '<a class="active" href="/student/scholarships/profile">' in page)
att = stu.get("/student/attendance").get_data(as_text=True)
camp = stu.get("/student/campus").get_data(as_text=True)
check("active highlighting differs per page",
      '<a class="active" href="/student/campus">' not in att
      and '<a class="active" href="/student/attendance">' not in camp)

# ticket thread in the shell
r = stu.post("/student/tickets/new", data={
    "category": "Fee", "subject": "Shell check ticket (V16)",
    "message": "Created to verify the thread page renders in the shell."})
check("ticket create redirects to the thread", r.status_code == 302)
tid = int(r.headers["Location"].rstrip("/").split("/")[-1])
thread = stu.get(f"/student/tickets/{tid}").get_data(as_text=True)
check("ticket thread renders in the shell, tickets item active",
      "student-sidebar" in thread
      and '<a class="active" href="/student/tickets">' in thread
      and "Shell check ticket (V16)" in thread)

# student card via the sidebar route
r = stu.get("/student/card.pdf")
check("My Student Card sidebar route downloads the card PDF",
      r.status_code == 200 and r.data.startswith(b"%PDF"))

# ------------------------------------------------------------- isolation
dept_id = dbq("SELECT id FROM departments ORDER BY id LIMIT 1")[0]["id"]
prog_id = dbq("SELECT id FROM programs ORDER BY id LIMIT 1")[0]["id"]
sess_id = dbq("SELECT id FROM academic_sessions ORDER BY id LIMIT 1")[0]["id"]
r = admin.post("/admin/students/new", data={
    "registration_no": "V16-REG-002", "name": "V16 Student Two",
    "cnic": "35202-1616161-6", "blood_group": "O+",
    "department_id": dept_id, "program_id": prog_id, "session_id": sess_id,
    "status": "Active", "current_semester": 1, "initial_password": "Test@1234"})
check("second student created", r.status_code == 302)
stuB = m.app.test_client()
login(stuB, "V16-REG-002", "Test@1234")
dashB = stuB.get("/student").get_data(as_text=True)
check("student B's shell shows B's own identity only",
      "V16 Student Two" in dashB and "V16-REG-002" in dashB
      and "CUVAS-DEMO-2026-001" not in dashB)
check("student B cannot open student A's ticket thread",
      stuB.get(f"/student/tickets/{tid}").status_code == 404)
r = upload(stu, "/student/documents/upload", {"doc_type": "CNIC Front"},
           "v16-cnic.png", b"\x89PNG\r\n\x1a\nV16-DOC", "image/png")
check("student A document upload still works", r.status_code == 302)
doc_id = dbq("SELECT id FROM student_documents WHERE file_name='v16-cnic.png'")[0]["id"]
check("student B cannot download student A's document",
      stuB.get(f"/student/documents/{doc_id}/download").status_code == 404)
check("student A downloads own document",
      stu.get(f"/student/documents/{doc_id}/download").status_code == 200)

# ------------------------------------------- admin / faculty / public intact
adash = admin.get("/admin").get_data(as_text=True)
check("admin shell unchanged (no student sidebar)",
      "student-sidebar" not in adash and "My Fee Vouchers" not in adash
      and 'href="/admin/students"' in adash)
fdash = fac.get("/faculty").get_data(as_text=True)
check("faculty shell unchanged (no student sidebar / My Apps)",
      "student-sidebar" not in fdash and "My Apps" not in fdash
      and "My Courses" in fdash)
land = anon.get("/").get_data(as_text=True)
check("public landing unchanged (no student sidebar)",
      "student-sidebar" not in land)

print()
if FAIL:
    print(f"{len(FAIL)} FAILURE(S):")
    for f in FAIL:
        print(" -", f)
    sys.exit(1)
print("ALL V16 CHECKS PASSED")
