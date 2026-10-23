"""Scripted verification for the CUVAS Bluecrest DESIGN SAMPLE (preview).

The sample is additive only: /preview/bluecrest/login and
/preview/bluecrest/admin, static/bluecrest.css and
templates/preview_*.html. The live green theme, /login, / and all
portals must be untouched. This suite asserts:
  - the logo is delivered as TEXT: brand_logo.py carries it as a
    base64 string and GET /brand/cuvas-logo.png serves bytes that are
    byte-identical (md5) to the official upload; no template or app.py
    references the logo via the static folder, and every file in the
    app tree decodes as UTF-8 (so the snapshot push accepts it);
  - bluecrest.css carries the four palette hexes and is referenced
    ONLY by the preview pages (normal /admin, /login, / carry none);
  - preview login authenticates exactly like /login (shared helper):
    admin -> preview dashboard with REAL figures (student count +
    ledger outstanding computed independently here), wrong password
    -> error + login_failed audit row, lockout parity (login_locked);
  - non-admin roles signing in via the preview land on their normal
    (green) home, and are bounced away from the preview admin page;
  - donut / session-bar data in the HTML matches the database;
  - sidebar links point at the real admin routes; search posts to
    /admin/students?q=.

Expects a FRESH database (empty users table) so seeding + counts are exact.
Env: DB_PATH=<fresh sqlite file>  OR  DATABASE_URL=<postgres uri>.
Prints PASS/FAIL lines and exits non-zero if any check fails.
"""
import hashlib
import os
import sys
from html import escape as html_escape

import app as m

FAIL = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail else ""))
    if not cond:
        FAIL.append(name)


def dbq(sql, params=()):
    with m.app.app_context():
        return m.get_db().execute(sql, params).fetchall()


def db1(sql, params=()):
    rows = dbq(sql, params)
    return rows[0] if rows else None


APP_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_LOGO = os.path.expanduser(
    "~/workspace/user/media_library/image/6b/"
    "6ba7502e9f488a3894b71c47b4f38e37bd98e5257ea1de5aa2191336c67303db.png")
FALLBACK_MD5 = "0d1f109f6aa1adfe1126ea5379d3e703"


def md5_bytes(b):
    return hashlib.md5(b).hexdigest()


def fmt(n):
    return f"{n:,}"


# ------------------------------------------------------------ logo delivery
import brand_logo

if os.path.exists(SRC_LOGO):
    with open(SRC_LOGO, "rb") as fh:
        expected_md5 = md5_bytes(fh.read())
else:
    expected_md5 = FALLBACK_MD5
check("brand_logo module decodes to the official upload (md5)",
      md5_bytes(brand_logo.logo_png_bytes()) == expected_md5,
      f"{md5_bytes(brand_logo.logo_png_bytes())} vs {expected_md5}")

anon = m.app.test_client()
r = anon.get("/brand/cuvas-logo.png")
check("GET /brand/cuvas-logo.png serves byte-identical image/png",
      r.status_code == 200 and r.mimetype == "image/png"
      and md5_bytes(r.data) == expected_md5)
r = anon.get("/static/bluecrest.css")
css = r.get_data(as_text=True)
check("bluecrest.css served + carries the four palette hexes",
      r.status_code == 200 and all(
          h in css for h in ("#17365D", "#2457A7", "#6654A3", "#E7B34C")))

with open(os.path.join(APP_DIR, "templates", "preview_login.html")) as fh:
    tpl_login = fh.read()
with open(os.path.join(APP_DIR, "templates", "preview_admin_base.html")) as fh:
    tpl_base = fh.read()
check("preview templates reference bluecrest.css + the brand logo route",
      "bluecrest.css" in tpl_login and "bluecrest.css" in tpl_base
      and "brand_cuvas_logo" in tpl_login and "brand_cuvas_logo" in tpl_base)

# ------------------------------------------- logo is text-only end to end
def _read_text(rel):
    with open(os.path.join(APP_DIR, rel)) as fh:
        return fh.read()


_tpl_dir = os.path.join(APP_DIR, "templates")
_tpl_all = [_read_text(os.path.join("templates", fn))
            for fn in sorted(os.listdir(_tpl_dir)) if fn.endswith(".html")]
check("no template or app.py references the logo via the static folder",
      "filename='cuvas-logo.png'" not in _read_text("app.py")
      and all("filename='cuvas-logo.png'" not in t for t in _tpl_all))

_non_text = []
for _root, _dirs, _files in os.walk(APP_DIR):
    _dirs[:] = [d for d in _dirs if d not in (".venv", "__pycache__")]
    for _fn in _files:
        if _fn.endswith(".db"):
            continue
        _p = os.path.join(_root, _fn)
        try:
            with open(_p, "rb") as fh:
                fh.read().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            _non_text.append(os.path.relpath(_p, APP_DIR))
check("every file in the app tree is UTF-8 text (snapshot-pushable)",
      not _non_text, "non-text: " + ", ".join(_non_text))

# ------------------------------------------------------------ preview login page
r = anon.get("/preview/bluecrest/login")
html = r.get_data(as_text=True)
check("preview login page renders (200) with logo, form + sample note",
      r.status_code == 200 and "/brand/cuvas-logo.png" in html
      and 'name="username"' in html and 'name="password"' in html
      and "Bluecrest sample" in html
      and "Cholistan University of Veterinary and Animal Sciences, Bahawalpur" in html)
check("preview login page lists the five demo accounts",
      all(s in html for s in ("admin / Admin@123", "student / Student@123",
                              "faculty / Faculty@123", "accounts / Accounts@123",
                              "coe / Coe@123")))

r = anon.get("/preview/bluecrest/admin")
check("anonymous preview admin -> redirect to a login",
      r.status_code == 302 and "/login" in r.headers.get("Location", ""),
      r.headers.get("Location", ""))

# ------------------------------------------------------------ wrong password
before = db1("SELECT COUNT(*) c FROM audit_log WHERE action='login_failed' "
             "AND username='admin'")["c"]
r = anon.post("/preview/bluecrest/login",
              data={"username": "admin", "password": "WrongPass1"})
html = r.get_data(as_text=True)
after = db1("SELECT COUNT(*) c FROM audit_log WHERE action='login_failed' "
            "AND username='admin'")["c"]
check("wrong password -> back on preview login with the usual error",
      r.status_code == 200 and "Invalid username or password." in html
      and "/brand/cuvas-logo.png" in html)
check("wrong password wrote a login_failed audit row", after == before + 1)

# ------------------------------------------------------------ admin preview login
adm = m.app.test_client()
r = adm.post("/preview/bluecrest/login",
             data={"username": "admin", "password": "Admin@123"})
check("admin preview login -> redirect to the preview dashboard",
      r.status_code == 302
      and r.headers.get("Location", "").endswith("/preview/bluecrest/admin"),
      r.headers.get("Location", ""))
r = adm.get("/preview/bluecrest/admin")
html = r.get_data(as_text=True)
check("preview admin dashboard renders (200) in Bluecrest",
      r.status_code == 200 and "bluecrest.css" in html
      and "/brand/cuvas-logo.png" in html and ">Preview</span>" in html
      and "Welcome Back," in html)

students_n = db1("SELECT COUNT(*) c FROM students")["c"]
row = db1("SELECT COALESCE(SUM(debit),0) d, COALESCE(SUM(credit),0) c "
          "FROM ledger_entries")
outstanding = (row["d"] or 0) - (row["c"] or 0)
faculty_n = db1("SELECT COUNT(*) c FROM faculty "
                "WHERE COALESCE(is_active,1)=1")["c"]
pending_v = db1("SELECT COUNT(*) c FROM vouchers "
                "WHERE status IN ('Pending','Proof Submitted')")["c"]
check("KPI: real total students figure on the dashboard",
      f'Total Students</div><div class="vl">{fmt(students_n)}</div>' in html,
      f"students={students_n}")
check("KPI: real total outstanding Rs from the ledger",
      f'Total Outstanding (Rs)</div><div class="vl">{fmt(outstanding)}</div>' in html,
      f"outstanding={fmt(outstanding)}")
check("KPI: real active faculty + pending vouchers figures",
      f'Active Faculty</div><div class="vl">{fmt(faculty_n)}</div>' in html
      and f'Pending Vouchers</div><div class="vl">{fmt(pending_v)}</div>' in html,
      f"faculty={faculty_n} pending_vouchers={pending_v}")

# ------------------------------------------------------------ charts vs database
progs = dbq("""SELECT COALESCE(p.name,'Unassigned') nm, COUNT(*) c
               FROM students s LEFT JOIN programs p ON p.id=s.program_id
               GROUP BY COALESCE(p.name,'Unassigned') ORDER BY c DESC, nm""")
ok_donut = bool(progs) and all(
    (html_escape(p["nm"]) in html and f'>{p["c"]}</span>' in html
     and f"{p['c'] * 100.0 / students_n:.1f}%" in html) for p in progs)
check("donut legend matches per-program counts + percentages", ok_donut,
      "; ".join(f"{p['nm']}={p['c']}" for p in progs))
sessions = dbq("""SELECT COALESCE(ss.name,'Unassigned') nm, COUNT(*) c
                  FROM students s
                  LEFT JOIN academic_sessions ss ON ss.id=s.session_id
                  GROUP BY COALESCE(ss.name,'Unassigned')
                  ORDER BY c DESC, nm""")
ok_bars = bool(sessions) and all(
    (html_escape(s["nm"]) in html and f'>{s["c"]}</span>' in html)
    for s in sessions)
check("session bars match per-session counts", ok_bars,
      "; ".join(f"{s['nm']}={s['c']}" for s in sessions))

# ------------------------------------------------------------ pending approvals
expected_pending = [
    ("Paid proofs waiting verification",
     db1("SELECT COUNT(*) c FROM vouchers WHERE status='Proof Submitted'")["c"]),
    ("Clearance items pending",
     db1("SELECT COUNT(*) c FROM clearance_items WHERE status='Pending'")["c"]),
    ("Scholarship applications undecided",
     db1("SELECT COUNT(*) c FROM scholarship_applications "
         "WHERE status IN ('Applied','Under Review')")["c"]),
    ("Vehicle passes requested",
     db1("SELECT COUNT(*) c FROM vehicle_passes WHERE status='Requested'")["c"]),
    ("Society join requests",
     db1("SELECT COUNT(*) c FROM society_members WHERE status='Requested'")["c"]),
    ("Open support tickets",
     db1("SELECT COUNT(*) c FROM tickets WHERE status='Open'")["c"]),
]
ok_pending = all(
    f'<span class="n">{c}</span><span class="t">{label}</span>' in html
    for label, c in expected_pending)
check("pending approvals panel shows the real counts", ok_pending,
      "; ".join(f"{label}={c}" for label, c in expected_pending))

# ------------------------------------------------------------ sidebar + search + panels
needles = ['href="/admin/students"', 'href="/admin/faculty"',
           'href="/admin/departments"', 'href="/admin/programs"',
           'href="/admin/sessions"', 'href="/admin/courses"',
           'href="/admin/fee-heads"', 'href="/admin/fee-plans"',
           'href="/admin/vouchers"', 'href="/admin/reports"',
           'href="/admin/results"', 'href="/admin/grade-scale"',
           'href="/admin/attendance"', 'href="/admin/clearance"',
           'href="/admin/scholarships"', 'href="/admin/repeat"',
           'href="/admin/timetable"', 'href="/admin/transport"',
           'href="/admin/documents"', 'href="/admin/tickets"',
           'href="/admin/notifications"', 'href="/admin/repository"',
           'href="/admin/campus"', 'href="/admin/staff"',
           'href="/admin/audit"', 'href="/admin/backup"',
           'href="/preview/bluecrest/admin"']
missing = [n for n in needles if n not in html]
check("sidebar links point at the real admin routes", not missing,
      "missing: " + ", ".join(missing))
check("sidebar groups present (Management/Finance/Examinations/Services/System)",
      all(g in html for g in ("Management", "Finance", "Examinations",
                              "Services", "System")))
check("topbar search submits to /admin/students with q",
      'action="/admin/students"' in html and 'name="q"' in html)
latest_student = db1("SELECT name FROM students ORDER BY id DESC LIMIT 1")
check("recent students table shows the newest student",
      bool(latest_student) and html_escape(latest_student["name"]) in html)
check("recent activity shows the preview sign-in (login_success)",
      "login_success" in html)
notif = db1("SELECT title FROM notifications "
            "ORDER BY published_at DESC, id DESC LIMIT 1")
check("recent notifications panel shows the latest notification",
      bool(notif) and html_escape(notif["title"]) in html)

# ------------------------------------------------------------ green theme untouched
r = adm.get("/admin")
green = r.get_data(as_text=True)
check("normal /admin has NO bluecrest anywhere (green theme untouched)",
      r.status_code == 200 and "bluecrest" not in green.lower())
r = anon.get("/login")
check("normal /login has NO bluecrest",
      r.status_code == 200 and "bluecrest" not in r.get_data(as_text=True).lower())
r = anon.get("/")
check("landing page has NO bluecrest",
      r.status_code == 200 and "bluecrest" not in r.get_data(as_text=True).lower())
adm.get("/logout")

# ------------------------------------------------------------ student via preview login
stu = m.app.test_client()
r = stu.post("/preview/bluecrest/login",
             data={"username": "student", "password": "Student@123"})
check("student via preview login -> normal student home (not the preview)",
      r.status_code == 302
      and r.headers.get("Location", "").endswith("/student"),
      r.headers.get("Location", ""))
r = stu.get("/student")
shtml = r.get_data(as_text=True)
check("student lands on the regular (green) dashboard + sample flash",
      r.status_code == 200 and "bluecrest.css" not in shtml
      and "design sample" in shtml.lower())
r = stu.get("/preview/bluecrest/admin")
check("student is bounced away from the preview admin page",
      r.status_code == 302
      and r.headers.get("Location", "").endswith("/student"),
      r.headers.get("Location", ""))
stu.get("/logout")

# ------------------------------------------------------------ other roles bounced
for uname, pw, home in (("faculty", "Faculty@123", "/faculty"),
                        ("accounts", "Accounts@123", "/accounts"),
                        ("coe", "Coe@123", "/coe")):
    c = m.app.test_client()
    c.post("/login", data={"username": uname, "password": pw})
    r = c.get("/preview/bluecrest/admin")
    check(f"{uname} is redirected away from the preview admin page",
          r.status_code == 302
          and r.headers.get("Location", "").endswith(home),
          r.headers.get("Location", ""))
    c.get("/logout")

# ------------------------------------------------------------ lockout parity (LAST: pollutes a throwaway user)
from werkzeug.security import generate_password_hash
with m.app.app_context():
    db = m.get_db()
    db.execute("INSERT INTO users (username,password_hash,display_name,role,"
               "student_id,is_active) VALUES (?,?,?,?,NULL,1)",
               ("previewlock", generate_password_hash("Lock@123"),
                "Preview Lock Test", "admin"))
    db.commit()
lk = m.app.test_client()
for _ in range(5):
    lk.post("/preview/bluecrest/login",
            data={"username": "previewlock", "password": "nope-nope"})
r = lk.post("/preview/bluecrest/login",
            data={"username": "previewlock", "password": "Lock@123"})
locked_rows = db1("SELECT COUNT(*) c FROM audit_log "
                  "WHERE action='login_locked' AND username='previewlock'")["c"]
check("5 failures via preview login lock the account (correct password refused)",
      r.status_code == 200 and "locked" in r.get_data(as_text=True)
      and locked_rows >= 1)

print()
if FAIL:
    print(f"{len(FAIL)} CHECK(S) FAILED: " + "; ".join(FAIL))
    sys.exit(1)
print("ALL PREVIEW CHECKS PASSED")
