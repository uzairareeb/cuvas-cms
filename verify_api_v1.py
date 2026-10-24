"""Scripted verification for CUVAS CMS — Next.js migration Slice 0:
the /api/v1 foundation (JSON envelope, session auth twins, lockout
parity, CSRF header/origin guard, scoped JSON error pages).

The API must be a thin JSON layer over the SAME auth machinery as the
HTML app: POST /api/v1/auth/login runs _sign_in() + _start_session()
(so lockout, audit and the session cookie are shared, and a session
started via the API opens the HTML pages — and vice versa), and
/api/v1/auth/me identifies the session without granting anything.

Expects a FRESH database (empty users table) so seeding + counts are
exact. Env: DB_PATH=<fresh sqlite file>  OR  DATABASE_URL=<postgres uri>.
Prints PASS/FAIL lines and exits non-zero if any check fails.
"""
import sys

from werkzeug.security import generate_password_hash

import app as m

FAIL = []
HDR = {"X-Requested-With": "XMLHttpRequest"}


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail else ""))
    if not cond:
        FAIL.append(name)


def dbq(sql, params=()):
    with m.app.app_context():
        return m.get_db().execute(sql, params).fetchall()


def dbx(sql, params=()):
    with m.app.app_context():
        db = m.get_db()
        db.execute(sql, params)
        db.commit()


def api_login(client, username, password, headers=HDR):
    return client.post("/api/v1/auth/login",
                       json={"username": username, "password": password},
                       headers=headers)


def envelope_ok(resp, status=200):
    body = resp.get_json(silent=True)
    return (resp.status_code == status and isinstance(body, dict)
            and body.get("ok") is True and "data" in body)


def envelope_err(resp, status, code):
    body = resp.get_json(silent=True)
    return (resp.status_code == status and isinstance(body, dict)
            and body.get("ok") is False
            and isinstance(body.get("error"), dict)
            and body["error"].get("code") == code
            and bool(body["error"].get("message")))


# ---------------------------------------------------------------- health
c = m.app.test_client()
r = c.get("/api/v1/health")
check("health 200 + envelope + payload",
      envelope_ok(r) and r.get_json()["data"] == {
          "service": "MY CUVAS API", "version": "v1"}
      and r.content_type.startswith("application/json"))

# ------------------------------------------------- JSON errors, not HTML
r = c.get("/api/v1/nope")
check("unknown /api/v1 path -> JSON 404 envelope",
      envelope_err(r, 404, "not_found")
      and r.content_type.startswith("application/json"))
r = c.get("/api/v1/auth/login")
check("GET on POST-only login -> JSON 405 envelope",
      envelope_err(r, 405, "method_not_allowed"))
r = c.get("/no-such-page")
check("non-API 404 keeps the default HTML error page",
      r.status_code == 404
      and r.content_type.startswith("text/html"))

# ------------------------------------------------------------- CSRF guard
r = c.post("/api/v1/auth/login",
           json={"username": "admin", "password": "Admin@123"})
check("API login WITHOUT X-Requested-With -> 403 csrf_check_failed",
      envelope_err(r, 403, "csrf_check_failed"))
r = c.post("/api/v1/auth/login",
           json={"username": "admin", "password": "Admin@123"},
           headers={**HDR, "Origin": "https://evil.example.com"})
check("API login with a mismatched Origin host -> 403 csrf_check_failed",
      envelope_err(r, 403, "csrf_check_failed"))
r = c.post("/api/v1/auth/login",
           json={"username": "admin", "password": "Admin@123"},
           headers={**HDR, "Origin": "http://localhost"})
check("API login with a matching Origin host passes the guard",
      envelope_ok(r))
c.post("/api/v1/auth/logout", headers=HDR)  # reset the session again

# -------------------------------------------------------------- bad input
r = c.post("/api/v1/auth/login", data="{not json",
           content_type="application/json", headers=HDR)
check("malformed JSON body -> 400 bad_request",
      envelope_err(r, 400, "bad_request"))
r = c.post("/api/v1/auth/login", json={}, headers=HDR)
check("empty JSON object -> 400 bad_request",
      envelope_err(r, 400, "bad_request"))
r = c.post("/api/v1/auth/login", json={"username": "admin"}, headers=HDR)
check("missing password -> 400 bad_request",
      envelope_err(r, 400, "bad_request"))

# ------------------------------------------------------------------- /me
r = c.get("/api/v1/auth/me")
check("/me anonymous -> 401 not_authenticated",
      envelope_err(r, 401, "not_authenticated"))

# ------------------------------------------------------- wrong credentials
r = api_login(c, "admin", "WrongPass@9")
check("wrong password -> 401 invalid_credentials",
      envelope_err(r, 401, "invalid_credentials"))

# ------------------------------------------------------------ admin login
admin_row = dbq("SELECT * FROM users WHERE username='admin'")[0]
r = api_login(c, "admin", "Admin@123")
body = r.get_json() or {}
user = (body.get("data") or {}).get("user") or {}
check("admin API login -> 200 envelope",
      envelope_ok(r))
check("admin identity matches the users row",
      user.get("id") == admin_row["id"]
      and user.get("username") == "admin"
      and user.get("role") == "admin"
      and user.get("name") == admin_row["display_name"])
check("admin home is the existing landing path /admin",
      (body.get("data") or {}).get("home") == "/admin")

r = c.get("/api/v1/auth/me")
check("/me after API login -> 200, same user + home",
      envelope_ok(r)
      and (r.get_json()["data"].get("user") or {}).get("username") == "admin"
      and r.get_json()["data"].get("home") == "/admin")

# ------------------------------------------- interop (i): API -> HTML app
r = c.get("/admin")
check("session from API login opens the HTML /admin (interop i)",
      r.status_code == 200)

# ----------------------------------------------------------------- logout
r = c.post("/api/v1/auth/logout", headers=HDR)
check("API logout -> 200 ok, empty data",
      envelope_ok(r) and r.get_json()["data"] == {})
r = c.get("/api/v1/auth/me")
check("/me after API logout -> 401",
      envelope_err(r, 401, "not_authenticated"))
r = c.get("/admin")
check("HTML /admin after API logout redirects to login",
      r.status_code == 302 and "/login" in r.headers["Location"])
r = c.post("/api/v1/auth/logout", headers=HDR)
check("anonymous API logout is idempotent ok",
      envelope_ok(r) and r.get_json()["data"] == {})

# ------------------------------------------- interop (ii): HTML -> API /me
c2 = m.app.test_client()
r = c2.post("/login", data={"username": "admin", "password": "Admin@123"})
check("HTML login still lands on /admin",
      r.status_code == 302 and r.headers["Location"].endswith("/admin"))
r = c2.get("/api/v1/auth/me")
check("/me accepts a session started by HTML /login (interop ii)",
      envelope_ok(r)
      and (r.get_json()["data"].get("user") or {}).get("username") == "admin")

# ----------------------------------------------------------- student login
c3 = m.app.test_client()
stu_row = dbq("SELECT * FROM users WHERE username='student'")[0]
r = api_login(c3, "student", "Student@123")
body = r.get_json() or {}
user = (body.get("data") or {}).get("user") or {}
check("student API login -> role student, home /student",
      envelope_ok(r) and user.get("role") == "student"
      and user.get("id") == stu_row["id"]
      and user.get("name") == stu_row["display_name"]
      and (body.get("data") or {}).get("home") == "/student")
r = c3.get("/student")
check("session from API login opens the HTML student dashboard",
      r.status_code == 200)

# ------------------------------------------------- lockout parity (shared)
dbx("INSERT INTO users (username,password_hash,role,display_name,"
    "student_id,is_active) VALUES (?,?,?,?,NULL,1)",
    ("api_lock_test", generate_password_hash("LockTest@123"),
     "student", "API Lock Test"))
c4 = m.app.test_client()
r = api_login(c4, "api_lock_test", "LockTest@123")
check("lock-test account API login works before any failures",
      envelope_ok(r))
c4.post("/api/v1/auth/logout", headers=HDR)
codes = [api_login(c4, "api_lock_test", "Nope@12345").status_code
         for _ in range(5)]
check("5 wrong API passwords -> 401 invalid_credentials each time",
      codes == [401] * 5, f"got {codes}")
fails = dbq("SELECT COUNT(*) c FROM login_attempts "
            "WHERE username='api_lock_test' AND success=0")[0]["c"]
check("failed API attempts are recorded in login_attempts",
      fails >= 5, f"recorded {fails}")
r = api_login(c4, "api_lock_test", "LockTest@123")
check("correct password after 5 failures -> 423 account_locked",
      envelope_err(r, 423, "account_locked")
      and "This account is locked" in r.get_json()["error"]["message"])
r = c4.post("/login", data={"username": "api_lock_test",
                            "password": "LockTest@123"})
check("HTML /login shows the same lockout for API-driven failures",
      r.status_code == 200
      and "This account is locked" in r.get_data(as_text=True))

# --------------------------------------- Slice 1: admin dashboard endpoint
DASH = "/api/v1/admin/dashboard"
r = m.app.test_client().get(DASH)
check("dashboard anonymous -> 401 not_authenticated",
      envelope_err(r, 401, "not_authenticated"))
r = c3.get(DASH)  # c3 holds the student session
check("dashboard as student -> 403 forbidden",
      envelope_err(r, 403, "forbidden"))
c5 = m.app.test_client()
r = api_login(c5, "accounts", "Accounts@123")
check("accounts API login works (for the dashboard denial check)",
      envelope_ok(r) and (r.get_json()["data"].get("user") or {}).get(
          "role") == "accounts")
r = c5.get(DASH)
check("dashboard as accounts -> 403 forbidden",
      envelope_err(r, 403, "forbidden"))
c5.post("/api/v1/auth/logout", headers=HDR)

c6 = m.app.test_client()
api_login(c6, "admin", "Admin@123")
r = c6.get(DASH)
check("dashboard as admin -> 200 envelope", envelope_ok(r))
dash = (r.get_json() or {}).get("data") or {}
kpis = dash.get("kpis") or {}

# Ground truth — independent direct SQL, computed here, not via the API.
gt_students = dbq("SELECT COUNT(*) c FROM students")[0]["c"]
gt_faculty = dbq("SELECT COUNT(*) c FROM faculty "
                 "WHERE COALESCE(is_active,1)=1")[0]["c"]
gt_pending_v = dbq("SELECT COUNT(*) c FROM vouchers "
                   "WHERE status IN ('Pending','Proof Submitted')")[0]["c"]
gt_outstanding = 0
for srow in dbq("SELECT id FROM students"):
    gt_outstanding += dbq(
        "SELECT COALESCE(SUM(debit),0)-COALESCE(SUM(credit),0) t "
        "FROM ledger_entries WHERE student_id=?", (srow["id"],))[0]["t"]
check("dashboard KPI total_students == ground truth",
      kpis.get("total_students") == gt_students,
      f"api={kpis.get('total_students')} sql={gt_students}")
check("dashboard KPI active_faculty == ground truth",
      kpis.get("active_faculty") == gt_faculty,
      f"api={kpis.get('active_faculty')} sql={gt_faculty}")
check("dashboard KPI pending_vouchers == ground truth",
      kpis.get("pending_vouchers") == gt_pending_v,
      f"api={kpis.get('pending_vouchers')} sql={gt_pending_v}")
check("dashboard KPI total_outstanding == per-student ledger sum",
      kpis.get("total_outstanding") == gt_outstanding,
      f"api={kpis.get('total_outstanding')} sql={gt_outstanding}")

gt_by_program = {row["name"]: row["c"] for row in dbq(
    """SELECT COALESCE(p.name,'No Program') name, COUNT(s.id) c
       FROM students s LEFT JOIN programs p ON p.id=s.program_id
       GROUP BY COALESCE(p.name,'No Program')""")}
api_by_program = {row["name"]: row["count"]
                  for row in dash.get("students_by_program") or []}
check("students_by_program matches ground truth",
      api_by_program == gt_by_program,
      f"api={api_by_program} sql={gt_by_program}")
check("students_by_program counts sum to total_students",
      sum(api_by_program.values()) == gt_students)
gt_by_session = {row["name"]: row["c"] for row in dbq(
    """SELECT COALESCE(se.name, s.session_name, 'No Session') name,
              COUNT(s.id) c
       FROM students s
       LEFT JOIN academic_sessions se ON se.id=s.session_id
       GROUP BY COALESCE(se.name, s.session_name, 'No Session')""")}
api_by_session = {row["name"]: row["count"]
                  for row in dash.get("students_by_session") or []}
check("students_by_session matches ground truth",
      api_by_session == gt_by_session,
      f"api={api_by_session} sql={gt_by_session}")

gt_queues = {
    "voucher_proofs": dbq("SELECT COUNT(*) c FROM vouchers "
                          "WHERE status='Proof Submitted'")[0]["c"],
    "documents": dbq("SELECT COUNT(*) c FROM student_documents "
                     "WHERE status='Pending'")[0]["c"],
    "tickets": dbq("SELECT COUNT(*) c FROM tickets "
                   "WHERE status IN ('Open','In Process')")[0]["c"],
    "clearance": dbq("SELECT COUNT(*) c FROM clearance_items "
                     "WHERE status='Pending'")[0]["c"],
    "scholarships": dbq("SELECT COUNT(*) c FROM scholarship_applications "
                        "WHERE status IN ('Applied','Under Review')")[0]["c"],
    "societies": dbq("SELECT COUNT(*) c FROM society_members "
                     "WHERE status='Requested'")[0]["c"],
    "vehicle_passes": dbq("SELECT COUNT(*) c FROM vehicle_passes "
                          "WHERE status='Requested'")[0]["c"],
    "course_repeat": dbq("SELECT COUNT(*) c FROM repeat_requests "
                         "WHERE status='Requested'")[0]["c"],
}
api_queues = {row["key"]: row["count"]
              for row in dash.get("pending_approvals") or []}
check("pending_approvals has exactly the 8 queues",
      set(api_queues) == set(gt_queues),
      f"api keys={sorted(api_queues)}")
check("pending_approvals counts == ground truth",
      api_queues == gt_queues, f"api={api_queues} sql={gt_queues}")
check("pending_approvals rows carry label + legacy href",
      all(row.get("label") and (row.get("href") or "").startswith("/admin/")
          for row in dash.get("pending_approvals") or []))

api_pv = dash.get("pending_vouchers") or []
check("pending_vouchers list length == min(KPI, 10) and fields present",
      len(api_pv) == min(gt_pending_v, 10)
      and all({"challan_no", "student_name", "amount", "status"}
              <= set(row) for row in api_pv))
gt_first_pv = dbq(
    """SELECT v.challan_no FROM vouchers v
       WHERE v.status IN ('Pending','Proof Submitted')
       ORDER BY v.id DESC LIMIT 1""")
check("pending_vouchers is latest-first",
      not gt_first_pv
      or (api_pv and api_pv[0]["challan_no"] == gt_first_pv[0]["challan_no"]))
api_rs = dash.get("recent_students") or []
gt_rs = dbq("SELECT registration_no FROM students ORDER BY id DESC LIMIT 8")
check("recent_students == latest 8 by id, with reg_no/name/program/status",
      [row["reg_no"] for row in api_rs]
      == [row["registration_no"] for row in gt_rs]
      and all({"reg_no", "name", "program", "status"} <= set(row)
              for row in api_rs))
api_rn = dash.get("recent_notifications") or []
gt_rn = dbq("SELECT title FROM notifications ORDER BY id DESC LIMIT 5")
check("recent_notifications == latest 5 titles",
      [row["title"] for row in api_rn] == [row["title"] for row in gt_rn]
      and all("created_at" in row for row in api_rn))
api_ra = dash.get("recent_activity") or []
gt_ra = dbq("SELECT action FROM audit_log ORDER BY id DESC LIMIT 8")
check("recent_activity == latest audit_log rows (action/detail/created_at)",
      [row["action"] for row in api_ra] == [row["action"] for row in gt_ra]
      and all({"action", "detail", "created_at"} <= set(row)
              for row in api_ra))
c6.post("/api/v1/auth/logout", headers=HDR)

print()
if FAIL:
    print(f"{len(FAIL)} FAILURE(S):")
    for f in FAIL:
        print(" -", f)
    sys.exit(1)
print("ALL API V1 CHECKS PASSED")
