"""Scripted verification for the Premium Minimal Academic PREVIEW sample.

Additive preview only: /preview/academic/login, /preview/academic/admin
and /brand/cuvas-logo.jpg, styled solely by static/academic.css. The
live green theme (static/style.css + every existing template) must be
untouched, so this suite also re-renders the existing public / login /
admin / student pages and asserts the preview stylesheet is referenced
by NO non-preview template.

Expects a FRESH database (empty users table) so seeding + counts are
exact. Env: DB_PATH=<fresh sqlite file>  OR  DATABASE_URL=<postgres uri>.
Prints PASS/FAIL lines and exits non-zero if any check fails.
"""
import hashlib
import re
import sys
from pathlib import Path

import app as m

FAIL = []
BASE = Path(__file__).resolve().parent
SOURCE_JPG = (BASE.parents[1] / "user" / "media_library" / "image" / "5b"
              / "5b881aa81537ffe0abbb37408c2816511305debca672140ad86a828751d1f39c.jpg")


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail else ""))
    if not cond:
        FAIL.append(name)


def dbq(sql, params=()):
    with m.app.app_context():
        return m.get_db().execute(sql, params).fetchall()


def one(sql, params=()):
    return dbq(sql, params)[0]["c"]


# ------------------------------------------------------------ logo route
anon = m.app.test_client()
r = anon.get("/brand/cuvas-logo.jpg")
src_md5 = hashlib.md5(SOURCE_JPG.read_bytes()).hexdigest()
check("logo route serves the supplied JPG byte-identical (md5)",
      r.status_code == 200 and r.mimetype == "image/jpeg"
      and hashlib.md5(r.data).hexdigest() == src_md5,
      f"served md5={hashlib.md5(r.data).hexdigest()} source md5={src_md5}")

# ------------------------------------------------------------ login page
r = anon.get("/preview/academic/login")
html = r.get_data(as_text=True)
check("preview login page renders with logo + form + preview stylesheet",
      r.status_code == 200 and "/brand/cuvas-logo.jpg" in html
      and 'name="username"' in html and 'name="password"' in html
      and "academic.css" in html and "style.css" not in html)
r = anon.get("/preview/academic/admin")
check("anonymous preview dashboard redirects to the preview login",
      r.status_code == 302
      and r.headers["Location"].endswith("/preview/academic/login"))
r = anon.post("/preview/academic/login",
              data={"username": "nobody-academic", "password": "Wrong@123"})
check("failed preview login re-renders with the shared error + audit trail",
      r.status_code == 200 and "Invalid username or password." in
      r.get_data(as_text=True)
      and one("SELECT COUNT(*) c FROM login_attempts "
              "WHERE username='nobody-academic' AND success=0") == 1)

# ------------------------------------------------- admin via the preview
students = one("SELECT COUNT(*) c FROM students")
faculty = one("SELECT COUNT(*) c FROM faculty WHERE COALESCE(is_active,1)=1")
pend_v = one("SELECT COUNT(*) c FROM vouchers "
             "WHERE status IN ('Pending','Proof Submitted')")
outstanding = one("SELECT COALESCE(SUM(debit),0)-COALESCE(SUM(credit),0) c "
                  "FROM ledger_entries")
adm = m.app.test_client()
r = adm.post("/preview/academic/login",
             data={"username": "admin", "password": "Admin@123"})
check("admin preview login lands on the preview dashboard",
      r.status_code == 302
      and r.headers["Location"].endswith("/preview/academic/admin"))
dash = adm.get("/preview/academic/admin")
html = dash.get_data(as_text=True)
check("preview dashboard renders 200 in the academic shell",
      dash.status_code == 200 and "ac-sidebar" in html
      and "academic.css" in html and "style.css" not in html)
check("stat cards show the database's real KPI numbers",
      f'<div class="num">{students:,}</div>' in html
      and f'<div class="num">{faculty:,}</div>' in html
      and f'<div class="num">{pend_v:,}</div>' in html
      and f'<div class="num">Rs {outstanding:,}</div>' in html,
      f"students={students} faculty={faculty} pending={pend_v} "
      f"outstanding={outstanding}")
prog = dbq("SELECT p.name name, COUNT(*) c FROM students s "
           "LEFT JOIN programs p ON p.id=s.program_id "
           "GROUP BY p.name ORDER BY c DESC LIMIT 1")
check("students-by-program uses real program counts",
      bool(prog) and prog[0]["name"] in html and "Students by Program" in html)
check("dashboard sections present (approvals / recent / activity / notices)",
      all(x in html for x in ("Pending Approvals", "Recent Students",
                              "Recent Activity", "Recent Notifications",
                              "Quick Links", "Pending Vouchers")))
total_waiting = sum(int(x) for x in re.findall(r">(\d+) waiting<", html))
queues = (one("SELECT COUNT(*) c FROM vouchers WHERE status='Proof Submitted'")
          + one("SELECT COUNT(*) c FROM student_documents WHERE status='Pending'")
          + one("SELECT COUNT(*) c FROM tickets WHERE status IN ('Open','In Process')")
          + one("SELECT COUNT(*) c FROM clearance_items WHERE status='Pending'")
          + one("SELECT COUNT(*) c FROM scholarship_applications "
                "WHERE status IN ('Applied','Under Review')")
          + one("SELECT COUNT(*) c FROM society_members WHERE status='Requested'")
          + one("SELECT COUNT(*) c FROM vehicle_passes WHERE status='Requested'")
          + one("SELECT COUNT(*) c FROM repeat_requests WHERE status='Requested'"))
check("pending-approval counts equal the real queue sizes",
      total_waiting == queues, f"page={total_waiting} db={queues}")

# ------------------------------------------- navigation purity (STRICT)
nav = html.split('<nav class="ac-nav"', 1)[1].split("</nav>", 1)[0]
links = re.findall(r"<a\b.*?</a>", nav, re.S)
emoji = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF"
                   "\u2190-\u21FF\uFE0F]")
check("navigation is text-only: no svg / icon classes / emoji in nav links",
      "<svg" not in nav and 'class="icon' not in nav and "<img" not in nav
      and not emoji.search(nav)
      and all("<svg" not in a and not emoji.search(a) for a in links),
      f"{len(links)} nav links inspected")
check("sidebar groups are expandable text-labelled parents",
      all(g in nav for g in ("Management", "Finance", "Examinations",
                             "Services", "System"))
      and nav.count("ac-group-toggle") == 5)
check("nav destinations are the real admin routes",
      all(h in nav for h in ('href="/admin/departments"', 'href="/admin/students"',
                             'href="/admin/vouchers"', 'href="/admin/results"',
                             'href="/admin/reports"', 'href="/admin/audit"',
                             'href="/admin/backup"'))
      and 'href="/logout"' in html)

# ------------------------------------------------------- other roles bounce
stu = m.app.test_client()
r = stu.post("/preview/academic/login",
             data={"username": "student", "password": "Student@123"})
check("student via preview login bounces to the normal student home",
      r.status_code == 302 and r.headers["Location"].endswith("/student"))
home = stu.get("/student").get_data(as_text=True)
check("bounced student sees the admin-only note on their normal home",
      "admin-only" in home)
r = stu.get("/preview/academic/admin")
check("signed-in student cannot open the preview dashboard",
      r.status_code == 302 and r.headers["Location"].endswith("/student"))

# ------------------------------------------------------------ stylesheet
css = (BASE / "static" / "academic.css").read_text()
hexes = ["#244A7C", "#3B6295", "#F5F7FA", "#FFFFFF", "#1E293B", "#64748B",
         "#E2E8F0", "#15803D", "#B45309", "#DC2626"]
check("academic.css carries every palette token from the spec",
      all(h in css for h in hexes),
      ", ".join(h for h in hexes if h not in css))
check("academic.css respects prefers-reduced-motion + 150-300ms motion",
      "prefers-reduced-motion" in css and "220ms" in css and "160ms" in css)
refs = sorted(p.name for p in (BASE / "templates").glob("*.html")
              if "academic.css" in p.read_text())
check("academic.css is referenced ONLY by the preview templates",
      refs == ["academic_admin_base.html", "academic_login.html"], str(refs))

# ------------------------------------------- existing system still intact
check("existing public + login pages still render",
      anon.get("/").status_code == 200
      and anon.get("/login").status_code == 200)
adm2 = m.app.test_client()
adm2.post("/login", data={"username": "admin", "password": "Admin@123"})
real_admin = adm2.get("/admin").get_data(as_text=True)
check("real admin dashboard unchanged (green shell, no preview css)",
      "academic.css" not in real_admin and 'href="/admin/students"' in real_admin)
stu2 = m.app.test_client()
stu2.post("/login", data={"username": "student", "password": "Student@123"})
check("real student dashboard still renders after normal login",
      stu2.get("/student").status_code == 200)

print()
if FAIL:
    print(f"{len(FAIL)} FAILURE(S):")
    for f in FAIL:
        print(" -", f)
    sys.exit(1)
print("ALL ACADEMIC PREVIEW CHECKS PASSED")
