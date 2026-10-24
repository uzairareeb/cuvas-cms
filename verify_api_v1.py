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

print()
if FAIL:
    print(f"{len(FAIL)} FAILURE(S):")
    for f in FAIL:
        print(" -", f)
    sys.exit(1)
print("ALL API V1 CHECKS PASSED")
