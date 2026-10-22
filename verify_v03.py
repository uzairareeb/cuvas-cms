"""Scripted verification for CUVAS CMS v0.3 fee system (run with the app venv python).

Expects a FRESH database (empty users table) so seeding + finance counts are exact.
Env: DB_PATH=<fresh sqlite file>  OR  DATABASE_URL=<postgres uri>.
Prints PASS/FAIL lines and exits non-zero if any check fails.
"""
import io
import re
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


def statement_totals(client):
    h = client.get("/student").get_data(as_text=True)
    mm = re.search(r"Payable: <strong>Rs ([\d,]+)</strong> · Paid: <strong>Rs ([\d,]+)</strong>"
                   r".*?Outstanding: <strong>Rs ([\d,]+)</strong>", h)
    return tuple(int(x.replace(",", "")) for x in mm.groups()) if mm else None


admin = m.app.test_client()
check("landing 200", admin.get("/").status_code == 200)
check("anon /admin/vouchers redirects", admin.get("/admin/vouchers").status_code == 302)
r = login(admin, "admin", "Admin@123")
check("admin login", r.status_code == 302 and "/admin" in r.headers["Location"])

# baseline: demo student's statement must match the seeded voucher list
demo = m.app.test_client()
login(demo, "student", "Student@123")
check("demo statement baseline 107500/60000/47500",
      statement_totals(demo) == (107500, 60000, 47500), str(statement_totals(demo)))
with m.app.app_context():
    d = m.get_db()
    demo_id = d.execute("SELECT id FROM students WHERE registration_no='CUVAS-DEMO-2026-001'").fetchone()["id"]
    bs_cs = d.execute("SELECT id FROM programs WHERE name='BS Computer Science (Demo)'").fetchone()["id"]
    fall24 = d.execute("SELECT id FROM academic_sessions WHERE name='Fall 2024 (Demo)'").fetchone()["id"]
    dvm_prog = d.execute("SELECT id FROM programs WHERE name LIKE ?", ("Doctor of Veterinary%",)).fetchone()["id"]
    dvm_dept = d.execute("SELECT department_id FROM programs WHERE id=?", (dvm_prog,)).fetchone()["department_id"]
    fall25 = d.execute("SELECT id FROM academic_sessions WHERE name='Fall 2025 (Demo)'").fetchone()["id"]

# ---- fee heads CRUD
for name in ["Tuition (V3)", "Library (V3)", "Exam (V3)"]:
    admin.post("/admin/fee-heads/new", data={"name": name})
heads_page = admin.get("/admin/fee-heads").get_data(as_text=True)
check("fee heads created + listed",
      all(n in heads_page for n in ["Tuition (V3)", "Library (V3)", "Exam (V3)"]))
admin.post("/admin/fee-heads/new", data={"name": "Tuition (V3)"})
check("duplicate fee head rejected",
      "already exists" in admin.get("/admin/fee-heads").get_data(as_text=True))
head_ids = {r["name"]: r["id"] for r in dbq("SELECT id,name FROM fee_heads")}

# ---- fee plan with 3 lines (odd total 27,501 to test ceil-split)
r = admin.post("/admin/fee-plans/new", data={
    "program_id": bs_cs, "session_id": fall24, "semester_no": 3,
    "title": "V3 Test Plan", "due_date": "2026-12-01",
    "line_head_id": [str(head_ids["Tuition (V3)"]), str(head_ids["Library (V3)"]), str(head_ids["Exam (V3)"])],
    "line_amount": ["20001", "5000", "2500"]})
check("fee plan create redirects", r.status_code == 302)
plans_page = admin.get("/admin/fee-plans").get_data(as_text=True)
check("plan listed with total 27,501", "V3 Test Plan" in plans_page and "27,501" in plans_page)
plan_id = dbq("SELECT id FROM fee_plans WHERE title='V3 Test Plan'")[0]["id"]
with m.app.app_context():
    check("plan_total() = 27501", m.plan_total(m.get_db(), plan_id) == 27501)

# plan edit on a scratch plan, then delete it (no vouchers -> allowed)
admin.post("/admin/fee-plans/new", data={
    "program_id": bs_cs, "session_id": fall24, "semester_no": 5,
    "title": "Scratch Plan", "due_date": "", "line_head_id": [str(head_ids["Exam (V3)"])],
    "line_amount": ["1000"]})
scratch_id = dbq("SELECT id FROM fee_plans WHERE title='Scratch Plan'")[0]["id"]
admin.post(f"/admin/fee-plans/{scratch_id}/edit", data={
    "program_id": bs_cs, "session_id": fall24, "semester_no": 6,
    "title": "Scratch Plan Edited", "due_date": "2027-01-15",
    "line_head_id": [str(head_ids["Exam (V3)"])], "line_amount": ["1500"]})
row = dbq("SELECT * FROM fee_plans WHERE id=?", (scratch_id,))[0]
check("plan edit works", row["title"] == "Scratch Plan Edited" and row["semester_no"] == 6)
admin.post(f"/admin/fee-plans/{scratch_id}/delete")
check("unused plan deleted", not dbq("SELECT id FROM fee_plans WHERE id=?", (scratch_id,)))

# ---- generation: single, then bulk, then bulk again (dup prevention)
r = admin.post("/admin/vouchers/generate", data={
    "plan_id": plan_id, "due_date": "2026-12-01", "student_id": demo_id})
page = admin.get("/admin/vouchers").get_data(as_text=True)
mm = re.search(r"created (\d+), skipped (\d+)", page)
check("single generation: created 1, skipped 0", bool(mm) and mm.groups() == ("1", "0"),
      str(mm.groups() if mm else None))
vrows = dbq("SELECT * FROM vouchers WHERE fee_plan_id=? ORDER BY id", (plan_id,))
check("one voucher from plan, amount 27501, challan format",
      len(vrows) == 1 and vrows[0]["amount"] == 27501 and
      re.fullmatch(r"CUVAS-\d{4}-\d{4}", vrows[0]["challan_no"] or "") is not None,
      vrows[0]["challan_no"] if vrows else "none")
demo_voucher = vrows[0]

r = admin.post("/admin/vouchers/generate", data={
    "plan_id": plan_id, "due_date": "2026-12-01", "student_id": "all"})
page = admin.get("/admin/vouchers").get_data(as_text=True)
mm = re.search(r"created (\d+), skipped (\d+)", page)
check("bulk generation: created 1 (Student Two), skipped 1 (Demo Student)",
      bool(mm) and mm.groups() == ("1", "1"), str(mm.groups() if mm else None))
r = admin.post("/admin/vouchers/generate", data={
    "plan_id": plan_id, "due_date": "2026-12-01", "student_id": "all"})
page = admin.get("/admin/vouchers").get_data(as_text=True)
mm = re.search(r"created (\d+), skipped (\d+)", page)
check("bulk re-run: created 0, skipped 2 (duplicate prevention)",
      bool(mm) and mm.groups() == ("0", "2"), str(mm.groups() if mm else None))

# plan delete now blocked; fee head delete blocked
admin.post(f"/admin/fee-plans/{plan_id}/delete")
check("plan with vouchers: delete blocked",
      "Cannot delete" in admin.get("/admin/fee-plans").get_data(as_text=True) and
      bool(dbq("SELECT id FROM fee_plans WHERE id=?", (plan_id,))))
admin.post(f"/admin/fee-heads/{head_ids['Tuition (V3)']}/delete")
check("fee head used in plan lines: delete blocked",
      bool(dbq("SELECT id FROM fee_heads WHERE id=?", (head_ids["Tuition (V3)"],))))

# admin voucher list filters
paid_q = admin.get("/admin/vouchers?status=Pending").get_data(as_text=True)
check("voucher list filter by status works", demo_voucher["challan_no"] in paid_q)
q_page = admin.get(f"/admin/vouchers?q={demo_voucher['challan_no']}").get_data(as_text=True)
check("voucher list search by challan works", "V3 Test Plan" not in q_page and demo_voucher["challan_no"] in q_page)

# ---- challan PDF (admin + student)
r = admin.get(f"/admin/vouchers/{demo_voucher['id']}/challan.pdf")
check("admin challan PDF is real bytes", r.status_code == 200 and r.data[:4] == b"%PDF" and len(r.data) > 500,
      f"{len(r.data)} bytes")
r = demo.get(f"/student/vouchers/{demo_voucher['id']}/challan.pdf")
check("student challan PDF is real bytes", r.status_code == 200 and r.data[:4] == b"%PDF" and len(r.data) > 500)

# ---- split into 2 installments by the student
r = demo.post(f"/student/vouchers/{demo_voucher['id']}/installments")
check("student split redirects ok", r.status_code == 302)
parent = dbq("SELECT * FROM vouchers WHERE id=?", (demo_voucher["id"],))[0]
children = dbq("SELECT * FROM vouchers WHERE parent_voucher_id=? ORDER BY id", (demo_voucher["id"],))
check("parent status = Split into Installments", parent["status"] == "Split into Installments")
check("2 children, kind=installment", len(children) == 2 and all(c["kind"] == "installment" for c in children))
check("split amounts: ceil half 13751 + remainder 13750 = 27501",
      [c["amount"] for c in children] == [13751, 13750], str([c["amount"] for c in children]))
check("child due dates: first = parent due, second = +30 days",
      children[0]["due_date"] == "2026-12-01" and children[1]["due_date"] == "2026-12-31",
      f"{children[0]['due_date']} / {children[1]['due_date']}")
check("statement after split: payable 135001 / paid 60000 / outstanding 75001",
      statement_totals(demo) == (135001, 60000, 75001), str(statement_totals(demo)))
r = demo.post(f"/student/vouchers/{demo_voucher['id']}/installments")
check("re-split of split parent refused",
      "Only a Pending voucher" in demo.get("/student").get_data(as_text=True))

# ---- proof upload + admin view + verify (installment 1)
PROOF = b"\x89PNG\r\n\x1a\nFAKE-PROOF-BYTES-V03-12345"
child1, child2 = children
r = demo.post(f"/student/vouchers/{child1['id']}/proof",
              data={"proof": (io.BytesIO(PROOF), "paid-proof.png"), "payment_channel": "Mobile Wallet"},
              content_type="multipart/form-data")
check("proof upload redirects", r.status_code == 302)
v = dbq("SELECT * FROM vouchers WHERE id=?", (child1["id"],))[0]
check("voucher now Proof Submitted with blob stored",
      v["status"] == "Proof Submitted" and bytes(v["proof_blob"]) == PROOF and
      v["proof_filename"] == "paid-proof.png" and v["payment_channel"] == "Mobile Wallet")
r = admin.get(f"/admin/vouchers/{child1['id']}/proof")
check("admin downloads identical proof bytes", r.status_code == 200 and r.data == PROOF)
detail = admin.get(f"/admin/vouchers/{child1['id']}").get_data(as_text=True)
check("admin detail shows proof + verify", "paid-proof.png" in detail and "Verify" in detail)

r = admin.post(f"/admin/vouchers/{child1['id']}/verify")
check("verify redirects", r.status_code == 302)
v = dbq("SELECT * FROM vouchers WHERE id=?", (child1["id"],))[0]
check("voucher Paid with paid_at set", v["status"] == "Paid" and bool(v["paid_at"]))
credits = dbq("SELECT * FROM ledger_entries WHERE voucher_id=? AND credit>0", (child1["id"],))
check("exactly one credit entry of 13751", len(credits) == 1 and credits[0]["credit"] == 13751)
check("statement after verify: paid 73751 / outstanding 61250",
      statement_totals(demo) == (135001, 73751, 61250), str(statement_totals(demo)))
admin.post(f"/admin/vouchers/{child1['id']}/verify")  # double verify attempt
credits = dbq("SELECT * FROM ledger_entries WHERE voucher_id=? AND credit>0", (child1["id"],))
check("double verify does not double-count", len(credits) == 1 and
      statement_totals(demo) == (135001, 73751, 61250))

# ---- reject flow (installment 2)
demo.post(f"/student/vouchers/{child2['id']}/proof",
          data={"proof": (io.BytesIO(b"blurry-image-bytes"), "proof2.jpg"),
                "payment_channel": "Bank"},
          content_type="multipart/form-data")
check("installment 2 proof submitted",
      dbq("SELECT status FROM vouchers WHERE id=?", (child2["id"],))[0]["status"] == "Proof Submitted")
admin.post(f"/admin/vouchers/{child2['id']}/reject",
           data={"remark": "Proof blurry (Verify) — please upload a clear copy"})
v = dbq("SELECT * FROM vouchers WHERE id=?", (child2["id"],))[0]
check("rejected voucher back to Pending", v["status"] == "Pending")
dash = demo.get("/student").get_data(as_text=True)
check("rejection remark visible to student", "Proof blurry (Verify)" in dash)
check("statement unchanged after reject", statement_totals(demo) == (135001, 73751, 61250))

# student fee-plan tab shows the applicable real plan (newest match)
check("fee plan tab shows real plan lines (Tuition (V3) / 27,501)",
      "Tuition (V3)" in dash and "27,501" in dash)

# installment challan PDF works too
r = demo.get(f"/student/vouchers/{child1['id']}/challan.pdf")
check("installment challan PDF is real bytes", r.status_code == 200 and r.data[:4] == b"%PDF")

# ---- guards: another student cannot touch demo student's vouchers
form = {
    "registration_no": "OTHER-V3-001", "cnic": "35202-7777777-7", "name": "Other Student V3",
    "father_name": "Other Father", "gender": "Female", "dob": "2005-01-01", "domicile": "Multan",
    "blood_group": "A+", "phone": "0300-7777777", "email": "other.v3@example.com",
    "address_present": "Other Address", "address_permanent": "Other Address",
    "department_id": dvm_dept, "program_id": dvm_prog, "session_id": fall25,
    "campus": "Main Campus (Demo)", "status": "Active", "current_semester": 1,
    "initial_password": "Other@12345",
}
r = admin.post("/admin/students/new", data=form)
check("second student created", r.status_code == 302)
other = m.app.test_client()
login(other, "OTHER-V3-001", "Other@12345")
r = other.get(f"/student/vouchers/{child2['id']}/challan.pdf")
check("other student cannot download demo challan", r.status_code == 302 and r.data[:4] != b"%PDF")
before = dbq("SELECT proof_filename, status FROM vouchers WHERE id=?", (child2["id"],))[0]
other.post(f"/student/vouchers/{child2['id']}/proof",
           data={"proof": (io.BytesIO(b"evil-bytes"), "evil.png"), "payment_channel": "Bank"},
           content_type="multipart/form-data")
after = dbq("SELECT proof_filename, status FROM vouchers WHERE id=?", (child2["id"],))[0]
check("other student cannot upload proof to demo voucher",
      before["proof_filename"] == after["proof_filename"] and after["status"] == "Pending")
other.post(f"/student/vouchers/{demo_voucher['id']}/installments")
check("other student cannot split demo voucher",
      dbq("SELECT status FROM vouchers WHERE id=?", (demo_voucher["id"],))[0]["status"] == "Split into Installments"
      and len(dbq("SELECT id FROM vouchers WHERE parent_voucher_id=?", (demo_voucher["id"],))) == 2)
check("anon challan PDF redirects", m.app.test_client().get(
    f"/student/vouchers/{child1['id']}/challan.pdf").status_code == 302)

# ---- regressions: v0.2 surfaces still alive
check("students page loads", admin.get("/admin/students").status_code == 200)
check("students import page loads", admin.get("/admin/students/import").status_code == 200)
dash_html = admin.get("/admin").get_data(as_text=True)
check("admin dashboard loads + student KPI reflects adds (=7)", ">7<" in dash_html)
d = demo.get("/student").get_data(as_text=True)
check("demo student still has 8 tabs + CGPA 3.63", d.count("data-tab=") == 8 and "3.63" in d)

print()
print("RESULT:", "ALL PASS" if not FAIL else f"{len(FAIL)} FAILURES: {FAIL}")
sys.exit(1 if FAIL else 0)
