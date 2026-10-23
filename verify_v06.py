"""Scripted verification for CUVAS CMS v0.6 — Step 10 student services:
documents (upload/verify/reject/lock), support tickets (threads + status
flow), notifications admin (single source for landing + News Feed),
document repository (published-only for students), student card PDF.

Expects a FRESH database (empty users table) so seeding + counts are exact.
Env: DB_PATH=<fresh sqlite file>  OR  DATABASE_URL=<postgres uri>.
Prints PASS/FAIL lines and exits non-zero if any check fails.
"""
import base64
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


def pdf_text(pdf_bytes):
    """Decode ReportLab content streams (ASCII85 + Flate) to searchable text."""
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


def upload(client, url, fields, filename, payload, mime):
    data = dict(fields)
    data["file"] = (io.BytesIO(payload), filename, mime)
    return client.post(url, data=data, content_type="multipart/form-data")


PNG1 = b"\x89PNG\r\n\x1a\nV6-CNIC-FRONT-V1"
PNG2 = b"\x89PNG\r\n\x1a\nV6-CNIC-FRONT-V2-CLEARER"
PNG3 = b"\x89PNG\r\n\x1a\nV6-CNIC-FRONT-V3-SHOULD-NOT-STICK"
PDF_DOC = b"%PDF-1.4 V6-MATRIC-CERTIFICATE"
REPO1 = b"%PDF-1.4 V6-REPOSITORY-CIRCULAR"
REPO2 = b"%PDF-1.4 V6-REPOSITORY-HIDDEN"

# ------------------------------------------------------------------ setup
admin = m.app.test_client()
anon = m.app.test_client()  # landing assertions: no session, no flash leakage
check("landing 200", admin.get("/").status_code == 200)
landing0 = admin.get("/").get_data(as_text=True)
check("seed announcements still on landing (v0.1 content preserved)",
      "Welcome to MY CUVAS (Demo)" in landing0)
for path in ["/admin/documents", "/admin/tickets", "/admin/notifications",
             "/admin/repository", "/admin/notifications/new"]:
    check(f"anon {path} redirects", admin.get(path).status_code == 302)
check("anon /student/card.pdf redirects", admin.get("/student/card.pdf").status_code == 302)
check("anon student doc download redirects",
      admin.get("/student/documents/1/download").status_code == 302)
check("anon repo download redirects",
      admin.get("/student/repository/1/download").status_code == 302)

r = login(admin, "admin", "Admin@123")
check("admin login", r.status_code == 302 and "/admin" in r.headers["Location"])
dash = admin.get("/admin").get_data(as_text=True)
check("admin sidebar has Documents/Tickets/Notifications/Repository links",
      all(f'href="/admin/{p}"' in dash or f"/admin/{p}" in dash for p in
          ["documents", "tickets", "notifications", "repository"]))

admin.post("/admin/departments/new", data={
    "name": "Dept of Services (V6)", "code": "SV-V6", "faculty_name": "Faculty (V6)"})
admin.post("/admin/sessions/new", data={
    "name": "Fall 2026 (V6)", "starts_on": "2026-09-01", "ends_on": "2027-01-31",
    "is_open": "1"})
dept6 = dbq("SELECT id FROM departments WHERE code='SV-V6'")[0]["id"]
sess6 = dbq("SELECT id FROM academic_sessions WHERE name='Fall 2026 (V6)'")[0]["id"]
admin.post("/admin/programs/new", data={
    "name": "BS Services (V6)", "department_id": dept6, "degree_level": "BS",
    "duration_semesters": 8})
prog6 = dbq("SELECT id FROM programs WHERE name='BS Services (V6)'")[0]["id"]

students = {}
for reg, name in [("V6-REG-001", "V6 Student One"), ("V6-REG-002", "V6 Student Two")]:
    r = admin.post("/admin/students/new", data={
        "registration_no": reg, "name": name, "cnic": "35202-1111111-1" if reg.endswith("001")
        else "35202-2222222-2", "blood_group": "B+",
        "department_id": dept6, "program_id": prog6, "session_id": sess6,
        "status": "Active", "current_semester": 1, "initial_password": "Test@1234"})
    check(f"student {reg} created", r.status_code == 302)
    students[reg] = dbq("SELECT id FROM students WHERE registration_no=?", (reg,))[0]["id"]
sA, sB = students["V6-REG-001"], students["V6-REG-002"]

stuA = m.app.test_client()
login(stuA, "V6-REG-001", "Test@1234")
stuB = m.app.test_client()
login(stuB, "V6-REG-002", "Test@1234")

# ------------------------------------------------------------- documents
r = upload(stuA, "/student/documents/upload", {"doc_type": "CNIC Front"},
           "cnic-front.png", PNG1, "image/png")
check("student A CNIC upload redirects ok", r.status_code == 302)
rows = dbq("SELECT * FROM student_documents WHERE student_id=? AND doc_type='CNIC Front'", (sA,))
check("upload stored as ONE row, Pending, bytes intact",
      len(rows) == 1 and rows[0]["status"] == "Pending"
      and bytes(rows[0]["file_data"]) == PNG1)
doc_id = rows[0]["id"]
htmlA = stuA.get("/student").get_data(as_text=True)
check("A dashboard lists CNIC Front as Pending",
      "CNIC Front" in htmlA and "Pending" in htmlA)
dl = stuA.get(f"/student/documents/{doc_id}/download")
check("A downloads own document byte-identical",
      dl.status_code == 200 and dl.data == PNG1)
check("B cannot download A's document (404)",
      stuB.get(f"/student/documents/{doc_id}/download").status_code == 404)

r = upload(stuA, "/student/documents/upload", {"doc_type": "Domicile"},
           "evil.txt", b"not an image", "text/plain")
check("non-image/PDF upload rejected (no Domicile row)",
      dbq("SELECT * FROM student_documents WHERE student_id=? AND doc_type='Domicile'",
          (sA,)) == [])

adm_docs = admin.get("/admin/documents").get_data(as_text=True)
check("admin documents page lists A's upload", "V6 Student One" in adm_docs
      and "CNIC Front" in adm_docs)
adm_dl = admin.get(f"/admin/documents/{doc_id}/download")
check("admin download byte-identical", adm_dl.status_code == 200 and adm_dl.data == PNG1)

admin.post(f"/admin/documents/{doc_id}/reject",
           data={"remarks": "Blurry scan — please re-upload (V6)"})
row = dbq("SELECT * FROM student_documents WHERE id=?", (doc_id,))[0]
check("reject stores status + remarks + reviewer",
      row["status"] == "Rejected"
      and row["admin_remarks"] == "Blurry scan — please re-upload (V6)"
      and bool(row["reviewed_by"]) and bool(row["reviewed_at"]))
htmlA = stuA.get("/student").get_data(as_text=True)
check("student sees Rejected + admin remark",
      "Rejected" in htmlA and "Blurry scan — please re-upload (V6)" in htmlA)

upload(stuA, "/student/documents/upload", {"doc_type": "CNIC Front"},
       "cnic-front-v2.png", PNG2, "image/png")
row = dbq("SELECT * FROM student_documents WHERE id=?", (doc_id,))[0]
check("re-upload replaces in place: Pending again, new bytes, remarks cleared",
      row["status"] == "Pending" and bytes(row["file_data"]) == PNG2
      and not row["admin_remarks"])
check("still exactly one CNIC Front row for A",
      len(dbq("SELECT * FROM student_documents WHERE student_id=? AND doc_type='CNIC Front'",
              (sA,))) == 1)

admin.post(f"/admin/documents/{doc_id}/verify", data={"remarks": "Looks good (V6)"})
row = dbq("SELECT * FROM student_documents WHERE id=?", (doc_id,))[0]
check("verify stores Verified + reviewer", row["status"] == "Verified"
      and bool(row["reviewed_by"]))
upload(stuA, "/student/documents/upload", {"doc_type": "CNIC Front"},
       "cnic-front-v3.png", PNG3, "image/png")
row = dbq("SELECT * FROM student_documents WHERE id=?", (doc_id,))[0]
check("Verified document is locked against replace",
      row["status"] == "Verified" and bytes(row["file_data"]) == PNG2)
stuA.post(f"/student/documents/{doc_id}/delete")
check("Verified document is locked against delete",
      len(dbq("SELECT * FROM student_documents WHERE id=?", (doc_id,))) == 1)
htmlA = stuA.get("/student").get_data(as_text=True)
check("A dashboard shows Verified + locked note",
      "Verified" in htmlA and "locked" in htmlA)

upload(stuA, "/student/documents/upload", {"doc_type": "Matric Certificate"},
       "matric.pdf", PDF_DOC, "application/pdf")
rows = dbq("SELECT * FROM student_documents WHERE student_id=? AND doc_type='Matric Certificate'",
           (sA,))
check("second doc type uploads independently (PDF ok)",
      len(rows) == 1 and rows[0]["status"] == "Pending"
      and bytes(rows[0]["file_data"]) == PDF_DOC)
check("admin status filter works",
      "Matric Certificate" in admin.get("/admin/documents",
                                        query_string={"status": "Pending"}).get_data(as_text=True))
paneB = stuB.get("/student").get_data(as_text=True) \
    .split('id="pane-documents"', 1)[1].split("<section", 1)[0]
check("B's document list is empty (A's uploads not visible)",
      "No documents uploaded yet." in paneB and "cnic-front" not in paneB)

# --------------------------------------------------------------- tickets
r = stuA.post("/student/tickets/new", data={
    "category": "Fee", "subject": "Challan amount wrong (V6)",
    "message": "My semester challan shows the wrong amount, please check."})
check("ticket create redirects to thread", r.status_code == 302
      and "/student/tickets/" in r.headers["Location"])
trows = dbq("SELECT * FROM tickets WHERE student_id=?", (sA,))
check("ticket stored Open", len(trows) == 1 and trows[0]["status"] == "Open")
tid = trows[0]["id"]
msgs = dbq("SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY id", (tid,))
check("first message stored from student",
      len(msgs) == 1 and msgs[0]["sender_role"] == "student"
      and "wrong amount" in msgs[0]["body"])

adm_list = admin.get("/admin/tickets").get_data(as_text=True)
check("admin ticket list shows the ticket", "Challan amount wrong (V6)" in adm_list)
admin.post(f"/admin/tickets/{tid}/reply",
           data={"message": "We are checking your challan (V6)."})
admin.post(f"/admin/tickets/{tid}/status", data={"status": "In Process"})
trow = dbq("SELECT * FROM tickets WHERE id=?", (tid,))[0]
check("admin reply + status In Process stored",
      trow["status"] == "In Process"
      and len(dbq("SELECT * FROM ticket_messages WHERE ticket_id=?", (tid,))) == 2)
threadA = stuA.get(f"/student/tickets/{tid}").get_data(as_text=True)
check("student thread shows admin reply + In Process",
      "We are checking your challan (V6)." in threadA and "In Process" in threadA)
check("B cannot open A's ticket thread (404)",
      stuB.get(f"/student/tickets/{tid}").status_code == 404)

stuA.post(f"/student/tickets/{tid}/reply", data={"message": "Thank you (V6)."})
check("student reply appended",
      len(dbq("SELECT * FROM ticket_messages WHERE ticket_id=?", (tid,))) == 3)
admin.post(f"/admin/tickets/{tid}/status", data={"status": "Resolved"})
stuA.post(f"/student/tickets/{tid}/close")
trow = dbq("SELECT * FROM tickets WHERE id=?", (tid,))[0]
check("student closes a Resolved ticket", trow["status"] == "Closed")
stuA.post(f"/student/tickets/{tid}/reply", data={"message": "Late reply (V6)"})
check("closed ticket rejects new student reply",
      len(dbq("SELECT * FROM ticket_messages WHERE ticket_id=?", (tid,))) == 3)
check("admin status+category filters work",
      "Challan amount wrong (V6)" in admin.get(
          "/admin/tickets", query_string={"status": "Closed", "category": "Fee"}
      ).get_data(as_text=True))

# ----------------------------------------------------------- notifications
admin.post("/admin/notifications/new", data={
    "title": "V6 Notice Alpha", "body": "Alpha body for students.",
    "audience": "Students", "is_published": "on"})
landing = anon.get("/").get_data(as_text=True)
check("published Students notification appears on landing", "V6 Notice Alpha" in landing)
newsA = stuA.get("/student").get_data(as_text=True)
check("published notification appears in student News Feed", "V6 Notice Alpha" in newsA)

admin.post("/admin/notifications/new", data={
    "title": "V6 Draft Beta", "body": "Beta body — not yet public.",
    "audience": "All"})
check("unpublished notification NOT on landing",
      "V6 Draft Beta" not in anon.get("/").get_data(as_text=True))
check("unpublished notification NOT in student News Feed",
      "V6 Draft Beta" not in stuA.get("/student").get_data(as_text=True))

admin.post("/admin/notifications/new", data={
    "title": "V6 Admins Only", "body": "Office-only note.",
    "audience": "Admins", "is_published": "on"})
check("Admins-audience item NOT on landing",
      "V6 Admins Only" not in anon.get("/").get_data(as_text=True))
check("Admins-audience item NOT in student News Feed",
      "V6 Admins Only" not in stuA.get("/student").get_data(as_text=True))

beta_id = dbq("SELECT id FROM notifications WHERE title='V6 Draft Beta'")[0]["id"]
admin.post(f"/admin/notifications/{beta_id}/toggle")
check("publish toggle makes it appear on landing",
      "V6 Draft Beta" in anon.get("/").get_data(as_text=True))
alpha_id = dbq("SELECT id FROM notifications WHERE title='V6 Notice Alpha'")[0]["id"]
admin.post(f"/admin/notifications/{alpha_id}/edit", data={
    "title": "V6 Notice Alpha Revised", "body": "Alpha body revised.",
    "audience": "Students", "is_published": "on"})
adm_notifs = admin.get("/admin/notifications").get_data(as_text=True)
check("edit updates the notification", "V6 Notice Alpha Revised" in adm_notifs)
admin.post(f"/admin/notifications/{beta_id}/delete")
check("delete removes the notification",
      dbq("SELECT * FROM notifications WHERE id=?", (beta_id,)) == [])

# ------------------------------------------------------------- repository
r = upload(admin, "/admin/repository/upload",
           {"title": "V6 Circular Alpha", "category": "Circular",
            "description": "Alpha circular for all students.",
            "is_published": "on"}, "circular-alpha.pdf", REPO1, "application/pdf")
check("admin repository upload redirects ok", r.status_code == 302)
rrows = dbq("SELECT * FROM repository_docs WHERE title='V6 Circular Alpha'")
check("repository row stored published, bytes intact",
      len(rrows) == 1 and rrows[0]["is_published"] == 1
      and bytes(rrows[0]["file_data"]) == REPO1)
repo_id = rrows[0]["id"]
newsA = stuA.get("/student").get_data(as_text=True)
check("published repository item listed in student News Feed",
      "V6 Circular Alpha" in newsA)
dl = stuA.get(f"/student/repository/{repo_id}/download")
check("student downloads published repository file byte-identical",
      dl.status_code == 200 and dl.data == REPO1)

upload(admin, "/admin/repository/upload",
       {"title": "V6 Hidden Beta", "category": "Notification",
        "description": "Not for students yet."}, "hidden-beta.pdf", REPO2,
       "application/pdf")
hrow = dbq("SELECT * FROM repository_docs WHERE title='V6 Hidden Beta'")[0]
check("unpublished repository upload stored unpublished", hrow["is_published"] == 0)
check("student cannot download unpublished repository file (404)",
      stuA.get(f"/student/repository/{hrow['id']}/download").status_code == 404)
check("unpublished repository item NOT listed for students",
      "V6 Hidden Beta" not in stuA.get("/student").get_data(as_text=True))
adm_dl = admin.get(f"/admin/repository/{hrow['id']}/download")
check("admin can still download the unpublished file",
      adm_dl.status_code == 200 and adm_dl.data == REPO2)
admin.post(f"/admin/repository/{hrow['id']}/toggle")
check("publishing it makes the student download work",
      stuA.get(f"/student/repository/{hrow['id']}/download").status_code == 200)

# ------------------------------------------------------------ student card
cardA = stuA.get("/student/card.pdf")
check("student A card PDF %PDF + size",
      cardA.data[:5] == b"%PDF-" and len(cardA.data) > 800, str(len(cardA.data)))
blob = pdf_text(cardA.data)
check("card shows STUDENT CARD + A's registration no",
      b"STUDENT CARD" in blob and b"V6-REG-001" in blob)
check("card shows A's program + blood group",
      b"BS Services" in blob and b"B+" in blob)
adm_card = admin.get(f"/admin/students/{sA}/card.pdf")
check("admin can fetch any student's card PDF",
      adm_card.status_code == 200 and adm_card.data[:5] == b"%PDF-")
check("student cannot use the admin card route",
      stuA.get(f"/admin/students/{sB}/card.pdf").status_code == 302)
cardB = stuB.get("/student/card.pdf")
check("B's own card carries B's registration no only",
      b"V6-REG-002" in pdf_text(cardB.data)
      and b"V6-REG-001" not in pdf_text(cardB.data))

# ------------------------------------------------- tabs + demo data intact
demo = m.app.test_client()
login(demo, "student", "Student@123")
dh = demo.get("/student").get_data(as_text=True)
orig_labels = ["News Feed", "Profile", "Course Enrollments", "Plan Of Study",
               "Transcript", "Financial Voucher", "Fee Plan &amp; Scholarships",
               "Account Statement"]
check("original 8 tab labels byte-identical",
      all(f">{lbl}</button>" in dh for lbl in orig_labels))
check("new tabs present: 10 total with My Documents + Support Tickets",
      dh.count("data-tab=") == 10 and ">My Documents</button>" in dh
      and ">Support Tickets</button>" in dh)
check("demo CGPA 3.63 intact", "Overall CGPA: <strong>3.63</strong>" in dh)
check("card download button on student profile area",
      "/student/card.pdf" in dh)

print()
if FAIL:
    print(f"{len(FAIL)} FAILURES: {FAIL}")
    sys.exit(1)
print("ALL CHECKS PASSED")
