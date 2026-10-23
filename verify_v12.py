"""Scripted verification for CUVAS CMS v0.12 — Step 16 timetable +
transport:
admins build the weekly timetable per program + semester + session;
saving a slot is clash-checked (same class / same teacher / same room
at an overlapping time in the same session is refused with a specific
message, while back-to-back and different-day slots pass); an edit
never clashes with itself; the slot form pre-selects the course's
assigned teacher. Students see 'My Time Table' for the current
session — exactly the slots of their enrolled courses for that
session — on the web and as a %PDF download, with an empty state when
nothing is published. Teachers see only their own slots, per session.
Transport seeds two demo routes with ordered stops on a fresh DB;
routes/stops are full CRUD (route delete blocked while stops exist);
students see active routes only and find routes by stop-name search.

Expects a FRESH database (empty users table) so seeding + counts are exact.
Env: DB_PATH=<fresh sqlite file>  OR  DATABASE_URL=<postgres uri>.
Prints PASS/FAIL lines and exits non-zero if any check fails.
"""
import base64
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


def dbexec(sql, params=()):
    with m.app.app_context():
        db = m.get_db()
        db.execute(sql, params)
        db.commit()


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


def slot_count():
    return db1("SELECT COUNT(*) c FROM timetable_slots")["c"]


# ------------------------------------------------------- guards
anon = m.app.test_client()
check("anon new pages redirect",
      all(anon.get(p).status_code == 302 for p in
          ["/admin/timetable", "/admin/transport", "/student/timetable",
           "/student/timetable.pdf", "/student/transport",
           "/faculty/timetable"]))
admin = m.app.test_client()
r = login(admin, "admin", "Admin@123")
check("admin login", r.status_code == 302 and "/admin" in r.headers["Location"])
check("admin blocked from student + faculty v0.12 pages",
      admin.get("/student/timetable").status_code == 302
      and admin.get("/student/transport").status_code == 302
      and admin.get("/faculty/timetable").status_code == 302)
fac0 = m.app.test_client()
login(fac0, "faculty", "Faculty@123")
check("demo faculty blocked from admin + student v0.12 pages",
      fac0.get("/admin/timetable").status_code == 302
      and fac0.get("/admin/transport").status_code == 302
      and fac0.get("/student/timetable").status_code == 302
      and fac0.get("/student/transport").status_code == 302)

# ------------------------------------------------------- transport seed (fresh DB)
routes = dbq("SELECT * FROM transport_routes ORDER BY id")
check("transport seed: exactly 2 routes on a fresh DB", len(routes) == 2,
      str(len(routes)))
r1_stops = dbq("SELECT * FROM transport_stops WHERE route_id=? "
               "ORDER BY sort_order", (routes[0]["id"],)) if routes else []
r2_stops = dbq("SELECT * FROM transport_stops WHERE route_id=? "
               "ORDER BY sort_order", (routes[1]["id"],)) if len(routes) > 1 else []
check("seed Route 1 stops in order with pickup times",
      [(s["stop_name"], s["pickup_time"]) for s in r1_stops] == [
          ("Satellite Town", "07:10"), ("Model Town", "07:25"),
          ("Cantt", "07:40"), ("Main Gate", "07:55"),
          ("CUVAS Campus", "08:10")],
      str([(s["stop_name"], s["pickup_time"]) for s in r1_stops]))
check("seed Route 2 stops in order with pickup times",
      [(s["stop_name"], s["pickup_time"]) for s in r2_stops] == [
          ("Hasilpur Road Chowk", "07:15"), ("University Chowk", "07:35"),
          ("Main Gate", "07:55"), ("CUVAS Campus", "08:10")],
      str([(s["stop_name"], s["pickup_time"]) for s in r2_stops]))
check("seed routes are active", all(x["is_active"] == 1 for x in routes))

# ------------------------------------------------------- fixtures (V12 namespace)
admin.post("/admin/departments/new", data={
    "name": "Dept of Timetables (V12)", "code": "TT-V12",
    "faculty_name": "Faculty (V12)"})
dept12 = db1("SELECT id FROM departments WHERE code='TT-V12'")["id"]
admin.post("/admin/sessions/new", data={
    "name": "Fall 2031 (V12)", "starts_on": "2031-09-01",
    "ends_on": "2032-01-31", "is_open": "1"})
admin.post("/admin/sessions/new", data={
    "name": "Spring 2032 (V12)", "starts_on": "2032-02-01",
    "ends_on": "2032-06-30"})
fall = db1("SELECT * FROM academic_sessions WHERE name='Fall 2031 (V12)'")
spring = db1("SELECT * FROM academic_sessions WHERE name='Spring 2032 (V12)'")
with m.app.app_context():
    cur = m.current_session(m.get_db())
check("current session is the new OPEN Fall 2031 (V12)",
      cur and cur["id"] == fall["id"], str(cur and cur["name"]))
progs = {}
for key, name in [("A", "BS Timetables (V12)"), ("B", "BS Other (V12)")]:
    admin.post("/admin/programs/new", data={
        "name": name, "department_id": dept12, "degree_level": "BS",
        "duration_semesters": 8})
    progs[key] = db1("SELECT * FROM programs WHERE name=?", (name,))
courses = {}
for prog, sem, code in [("A", 1, "V12-101"), ("A", 1, "V12-102"),
                        ("A", 2, "V12-201"), ("B", 1, "V12-901")]:
    admin.post("/admin/courses/new", data={
        "program_id": progs[prog]["id"], "semester_no": sem, "code": code,
        "title": f"Course {code} (V12)", "credit_theory": 3,
        "credit_lab": 0, "faculty_name": "Dr V12"})
    courses[code] = db1("SELECT * FROM courses WHERE code=?", (code,))
facs = {}
for key, name, email in [("F1", "V12 Teacher One", "v12.one@example.com"),
                         ("F2", "V12 Teacher Two", "v12.two@example.com")]:
    admin.post("/admin/faculty/new", data={
        "full_name": name, "email": email, "phone": "0300-0000012",
        "designation": "Lecturer", "department_id": dept12,
        "initial_password": "Test@1234"})
    facs[key] = db1("SELECT * FROM faculty WHERE email=?", (email,))
# the demo teacher of V12-101 for the Fall session is F1
admin.post(f"/admin/faculty/{facs['F1']['id']}/assign", data={
    "course_id": courses["V12-101"]["id"], "session_id": fall["id"]})
asg = db1("SELECT * FROM course_assignments WHERE faculty_id=? AND course_id=?",
          (facs["F1"]["id"], courses["V12-101"]["id"]))
check("fixture: F1 assigned to V12-101 for Fall", asg is not None)

students = {}
for reg, name, prog in [("V12-REG-001", "V12 Student One", "A"),
                        ("V12-REG-002", "V12 Student Two", "B")]:
    admin.post("/admin/students/new", data={
        "registration_no": reg, "name": name, "department_id": dept12,
        "program_id": progs[prog]["id"], "session_id": fall["id"],
        "status": "Active", "current_semester": 1,
        "initial_password": "Test@1234"})
    students[reg] = db1("SELECT id FROM students WHERE registration_no=?",
                        (reg,))["id"]
s1, s2 = students["V12-REG-001"], students["V12-REG-002"]
# enrolments for the current session, matched by session NAME
for sid, code in [(s1, "V12-101"), (s1, "V12-102"), (s2, "V12-901")]:
    dbexec("INSERT INTO enrollments (student_id,course_id,session_name,"
           "semester_no) VALUES (?,?,?,?)",
           (sid, courses[code]["id"], "Fall 2031 (V12)", 1))

TT_NEW = "/admin/timetable/new"


def add_slot(prog, sem, sess, course, fac, day, start, end, room):
    return admin.post(
        TT_NEW, query_string={"program_id": progs[prog]["id"],
                              "semester": sem, "session_id": sess["id"]},
        data={"program_id": progs[prog]["id"], "semester": sem,
              "session_id": sess["id"], "course_id": courses[course]["id"],
              "faculty_id": facs[fac]["id"] if fac else "",
              "day_of_week": day, "start_time": start, "end_time": end,
              "room": room}, follow_redirects=True)


# ------------------------------------------------------- slot add + clash checks
r = add_slot("A", 1, fall, "V12-101", "F1", "Monday", "09:00", "10:00",
             "CR-1 (V12)")
slot_a = db1("SELECT * FROM timetable_slots WHERE course_id=?",
             (courses["V12-101"]["id"],))
check("slot added: V12-101 Mon 09:00-10:00 CR-1 with F1",
      slot_a is not None and slot_a["day_of_week"] == "Monday"
      and slot_a["start_time"] == "09:00" and slot_a["end_time"] == "10:00"
      and slot_a["room"] == "CR-1 (V12)"
      and slot_a["faculty_id"] == facs["F1"]["id"])
lst = admin.get("/admin/timetable", query_string={
    "program_id": progs["A"]["id"], "semester": 1,
    "session_id": fall["id"]}).get_data(as_text=True)
check("admin timetable lists the slot grouped under Monday",
      "Monday" in lst and "V12-101" in lst and "CR-1 (V12)" in lst
      and "V12 Teacher One" in lst)

r = add_slot("A", 1, fall, "V12-102", "F2", "Monday", "09:30", "10:30",
             "CR-9 (V12)")
check("CLASS clash blocked with its message (no row)",
      "Class clash" in r.get_data(as_text=True) and slot_count() == 1)
r = add_slot("B", 1, fall, "V12-901", "F1", "Monday", "09:30", "10:30",
             "CR-8 (V12)")
check("TEACHER clash blocked with its message (no row)",
      "Teacher clash" in r.get_data(as_text=True) and slot_count() == 1)
r = add_slot("A", 2, fall, "V12-201", "F2", "Monday", "09:15", "09:45",
             "cr-1 (v12)")
check("ROOM clash blocked, case-insensitive room (no row)",
      "Room clash" in r.get_data(as_text=True) and slot_count() == 1)
r = add_slot("A", 1, fall, "V12-102", "F2", "Monday", "10:00", "11:00",
             "CR-1 (V12)")
check("back-to-back slot (starts at the other's end) is NOT a clash",
      slot_count() == 2)
r = add_slot("A", 1, fall, "V12-102", "F2", "Tuesday", "09:30", "10:30",
             "CR-1 (V12)")
tue = db1("SELECT * FROM timetable_slots WHERE day_of_week='Tuesday'")
check("different-day overlapping slot succeeds", tue is not None
      and slot_count() == 3)
r = add_slot("A", 1, fall, "V12-102", "F2", "Wednesday", "12:00", "11:00",
             "CR-3 (V12)")
check("end before start refused (no row)",
      "end time must be after the start time" in r.get_data(as_text=True)
      and slot_count() == 3)
r = add_slot("B", 1, fall, "V12-901", "F2", "Wednesday", "09:00", "10:00",
             "CR-5 (V12)")
r = add_slot("A", 2, fall, "V12-201", "F2", "Wednesday", "11:00", "12:00",
             "CR-7 (V12)")
r = add_slot("A", 1, spring, "V12-101", "F1", "Thursday", "09:00", "10:00",
             "SPR-ROOM (V12)")
check("setup slots: other-program, unenrolled-course and other-session "
      "slots exist", slot_count() == 6, str(slot_count()))

# ------------------------------------------------------- assigned-teacher preselect
form = admin.get(TT_NEW, query_string={
    "program_id": progs["A"]["id"], "semester": 1,
    "session_id": fall["id"],
    "course_id": courses["V12-101"]["id"]}).get_data(as_text=True)
check("slot form pre-selects the assigned teacher (F1) for V12-101",
      re.search(r'value="%d"[^>]*selected' % facs["F1"]["id"], form)
      is not None)
check("slot form courses are limited to program + semester",
      "V12-101" in form and "V12-102" in form and "V12-201" not in form
      and "V12-901" not in form)

# ------------------------------------------------------- edit (self-clash + into clash)
slot_b = db1("SELECT * FROM timetable_slots WHERE course_id=? "
             "AND day_of_week='Monday'", (courses["V12-102"]["id"],))
r = admin.post(f"/admin/timetable/{slot_a['id']}/edit", data={
    "program_id": progs["A"]["id"], "semester": 1, "session_id": fall["id"],
    "course_id": courses["V12-101"]["id"], "faculty_id": facs["F1"]["id"],
    "day_of_week": "Monday", "start_time": "09:00", "end_time": "10:00",
    "room": "CR-2 (V12)"}, follow_redirects=True)
slot_a2 = db1("SELECT * FROM timetable_slots WHERE id=?", (slot_a["id"],))
check("edit into its own time (room only) succeeds — no self-clash",
      slot_a2["room"] == "CR-2 (V12)" and slot_count() == 6)
r = admin.post(f"/admin/timetable/{slot_b['id']}/edit", data={
    "program_id": progs["A"]["id"], "semester": 1, "session_id": fall["id"],
    "course_id": courses["V12-102"]["id"], "faculty_id": facs["F2"]["id"],
    "day_of_week": "Monday", "start_time": "09:30", "end_time": "10:30",
    "room": "CR-1 (V12)"}, follow_redirects=True)
slot_b2 = db1("SELECT * FROM timetable_slots WHERE id=?", (slot_b["id"],))
check("edit INTO a clash is blocked and the row is unchanged",
      "Class clash" in r.get_data(as_text=True)
      and slot_b2["start_time"] == "10:00" and slot_b2["end_time"] == "11:00")
check("edit unknown slot -> 404",
      admin.get("/admin/timetable/999999/edit").status_code == 404)

# ------------------------------------------------------- student timetable
stu1 = m.app.test_client()
login(stu1, "V12-REG-001", "Test@1234")
check("student blocked from admin timetable + transport",
      stu1.get("/admin/timetable").status_code == 302
      and stu1.get("/admin/transport").status_code == 302)
page = stu1.get("/student/timetable").get_data(as_text=True)
check("student timetable shows own enrolled courses' slots",
      "V12-101" in page and "V12-102" in page and "Monday" in page
      and "CR-2 (V12)" in page and "V12 Teacher One" in page)
check("student timetable excludes other-program + unenrolled slots",
      "V12-901" not in page and "V12-201" not in page)
check("student timetable is for the current session only",
      "SPR-ROOM (V12)" not in page)
dash = stu1.get("/student").get_data(as_text=True)
check("dashboard keeps exactly 10 tabs + View Time Table button",
      dash.count("data-tab=") == 10 and "View Time Table" in dash
      and "Transport" in dash)
pdf = stu1.get("/student/timetable.pdf")
txt = pdf_text(pdf.data)
check("student timetable PDF: %PDF bytes with own course, without others",
      pdf.status_code == 200 and pdf.data[:5] == b"%PDF-"
      and b"V12-101" in txt and b"V12-901" not in txt)

demo = m.app.test_client()
login(demo, "student", "Student@123")
dpage = demo.get("/student/timetable").get_data(as_text=True)
check("demo student (nothing enrolled this session) sees the empty state",
      "No timetable slots have been published" in dpage)

# ------------------------------------------------------- faculty timetable
fteach = m.app.test_client()
login(fteach, "v12.one@example.com", "Test@1234")
fpage = fteach.get("/faculty/timetable").get_data(as_text=True)
check("faculty timetable shows only own slots (F1: V12-101)",
      "V12-101" in fpage and "V12-102" not in fpage
      and "CR-2 (V12)" in fpage and "SPR-ROOM (V12)" not in fpage)
fpage = fteach.get("/faculty/timetable",
                   query_string={"session_id": spring["id"]}
                   ).get_data(as_text=True)
check("faculty timetable session switch shows the Spring slot",
      "SPR-ROOM (V12)" in fpage and "CR-2 (V12)" not in fpage)
check("faculty blocked from student timetable + transport",
      fteach.get("/student/timetable").status_code == 302
      and fteach.get("/student/transport").status_code == 302)

# ------------------------------------------------------- slot delete
r = admin.post(f"/admin/timetable/{tue['id']}/delete")
check("slot delete removes the row",
      r.status_code == 302 and slot_count() == 5
      and db1("SELECT * FROM timetable_slots WHERE id=?",
              (tue["id"],)) is None)

# ------------------------------------------------------- transport CRUD
r = admin.post("/admin/transport/new", data={
    "name": "Route 3 (V12)", "title": "Route 3 — North Side (V12)",
    "description": "V12 test route", "is_active": "1"},
    follow_redirects=True)
route3 = db1("SELECT * FROM transport_routes WHERE name='Route 3 (V12)'")
check("route created active with its fields",
      route3 is not None and route3["is_active"] == 1
      and route3["title"] == "Route 3 — North Side (V12)")
admin.post(f"/admin/transport/{route3['id']}/stops/add", data={
    "stop_name": "Zebra Stop (V12)", "pickup_time": "07:05",
    "sort_order": 2})
admin.post(f"/admin/transport/{route3['id']}/stops/add", data={
    "stop_name": "Alpha Stop (V12)", "pickup_time": "06:55",
    "sort_order": 1})
stops3 = dbq("SELECT * FROM transport_stops WHERE route_id=? "
             "ORDER BY sort_order", (route3["id"],))
check("stops are stored and ordered by sort_order (Alpha before Zebra)",
      [s["stop_name"] for s in stops3] == ["Alpha Stop (V12)",
                                           "Zebra Stop (V12)"])
spage = admin.get(f"/admin/transport/{route3['id']}/stops"
                  ).get_data(as_text=True)
check("admin stops page lists them in order",
      spage.index("Alpha Stop (V12)") < spage.index("Zebra Stop (V12)"))
zebra = stops3[1]
admin.post(f"/admin/transport/{route3['id']}/stops/{zebra['id']}/edit",
           data={"stop_name": "Zebra Stop (V12)",
                 "pickup_time": "07:07", "sort_order": 2})
check("stop edit updates the pickup time",
      db1("SELECT * FROM transport_stops WHERE id=?",
          (zebra["id"],))["pickup_time"] == "07:07")
admin.post(f"/admin/transport/{route3['id']}/stops/add", data={
    "stop_name": "Bad Time Stop (V12)", "pickup_time": "25:99",
    "sort_order": 9}, follow_redirects=True)
check("stop with an invalid pickup time is refused",
      db1("SELECT * FROM transport_stops WHERE stop_name='Bad Time Stop (V12)'")
      is None)
r = admin.post(f"/admin/transport/{route3['id']}/delete",
               follow_redirects=True)
check("route delete BLOCKED while stops exist",
      "Cannot delete" in r.get_data(as_text=True)
      and db1("SELECT * FROM transport_routes WHERE id=?",
              (route3["id"],)) is not None)
r = admin.post(f"/admin/transport/{route3['id']}/edit", data={
    "name": "Route 3 (V12)", "title": "Route 3 — North Side (V12)",
    "description": "V12 test route edited", "is_active": "1"})
check("route edit saves", db1("SELECT * FROM transport_routes WHERE id=?",
      (route3["id"],))["description"] == "V12 test route edited")
for s in dbq("SELECT * FROM transport_stops WHERE route_id=?",
             (route3["id"],)):
    admin.post(f"/admin/transport/{route3['id']}/stops/{s['id']}/delete")
r = admin.post(f"/admin/transport/{route3['id']}/delete")
check("route deletes once its stops are gone",
      r.status_code == 302 and db1(
          "SELECT * FROM transport_routes WHERE id=?",
          (route3["id"],)) is None)

admin.post("/admin/transport/new", data={
    "name": "Route Hidden (V12)", "title": "Hidden Route (V12)",
    "description": "inactive fixture"})
hidden = db1("SELECT * FROM transport_routes WHERE name='Route Hidden (V12)'")
check("route created without the active box is inactive",
      hidden is not None and hidden["is_active"] == 0)
admin.post(f"/admin/transport/{hidden['id']}/stops/add", data={
    "stop_name": "Hidden Stop (V12)", "pickup_time": "06:30",
    "sort_order": 1})

# ------------------------------------------------------- student transport + search
tpage = stu1.get("/student/transport").get_data(as_text=True)
check("student transport shows the seeded routes with times",
      "Satellite Town" in tpage and "07:10" in tpage
      and "Hasilpur Road Chowk" in tpage and "CUVAS Campus" in tpage)
check("student transport hides inactive routes + their stops",
      "Route Hidden (V12)" not in tpage and "Hidden Stop (V12)" not in tpage)
check("admin transport list still shows the inactive route",
      "Route Hidden (V12)" in admin.get("/admin/transport"
                                         ).get_data(as_text=True))
tpage = stu1.get("/student/transport",
                 query_string={"q": "satellite"}).get_data(as_text=True)
check("stop search (case-insensitive) finds Route 1 only",
      "Satellite Town" in tpage and "Hasilpur Road Chowk" not in tpage)
tpage = stu1.get("/student/transport",
                 query_string={"q": "Main Gate"}).get_data(as_text=True)
check("stop search 'Main Gate' finds BOTH routes",
      "Satellite Town" in tpage and "Hasilpur Road Chowk" in tpage)
tpage = stu1.get("/student/transport",
                 query_string={"q": "Hasilpur Road Chowk"}
                 ).get_data(as_text=True)
check("stop search finds Route 2 only",
      "Hasilpur Road Chowk" in tpage and "Satellite Town" not in tpage)
tpage = stu1.get("/student/transport",
                 query_string={"q": "no-such-stop-xyz"}).get_data(as_text=True)
check("stop search with no match says so",
      "No active route serves a stop matching" in tpage)

print()
if FAIL:
    print(f"{len(FAIL)} FAILURES: {FAIL}")
    sys.exit(1)
print("ALL CHECKS PASSED")
