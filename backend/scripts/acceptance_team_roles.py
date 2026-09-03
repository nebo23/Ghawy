"""Acceptance checks for the named team roles. Runs against a throwaway DB.

Point DATABASE_URL at a scratch database before running — the first thing this
file does is drop and rebuild the public schema, exactly like
acceptance_security.py.

What it pins down, in the order the owner would actually do it:

  1. the catalogue endpoint is owner-only,
  2. giving someone a role makes them an admin with that role's permissions,
  3. those permissions are ENFORCED — the endpoints inside the role answer and
     the ones outside it 403, tested by calling them, not by reading the row,
  4. the owner can then tune one permission by hand and the role name survives,
  5. taking the role away closes every door again,
  6. and the four ways the call must refuse.
"""
import os, sys, json
os.environ.setdefault("SECRET_KEY", "dummy_secret_for_import_check")

# Approve the target database before anything imports the app: `import main`
# writes to the database on import, so the guard has to come first.
from _acceptance_guard import require_scratch_database  # noqa: E402
require_scratch_database()

from fastapi.testclient import TestClient
import main
from app.database import SessionLocal, engine
from app.models import Base
from app import models as M

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name + (("  -> " + str(detail)) if (detail and not cond) else ""))

from sqlalchemy import text as _text
with engine.begin() as _c:
    _c.execute(_text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
Base.metadata.create_all(bind=engine)
db = SessionLocal()

import bcrypt
def mkuser(email, active=True, admin=False, owner=False, name="Test User"):
    u = M.User(email=email, hashed_password=bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode(),
               full_name=name, is_active=active, is_admin=admin, is_owner=owner,
               is_verified=True)
    db.add(u); db.commit(); db.refresh(u)
    return u

owner    = mkuser("owner@t.co", admin=True, owner=True, name="The Owner")
owner2   = mkuser("owner2@t.co", admin=True, owner=True, name="Second Owner")
staff    = mkuser("staff@t.co", name="Staff Person")
plain    = mkuser("plain@t.co", name="Plain Member")
oldadmin = mkuser("oldadmin@t.co", admin=True, name="Admin From Before")

from app.routers.users import issue_token_for
def H(u):
    db.refresh(u)
    return {"Authorization": "Bearer " + issue_token_for(u)}

client = TestClient(main.app, raise_server_exceptions=False)

from app.services.permissions import TEAM_ROLES, PERMISSION_KEYS
CM = "community_manager"
TE = "technical_engineer"
CS = "customer_success"


print("\n=== catalogue endpoint ===")
r = client.get("/admin/staff/roles", headers=H(owner))
check("owner gets /admin/staff/roles", r.status_code == 200, r.status_code)
body = r.json() if r.status_code == 200 else {}
check("it returns the three roles", len(body.get("roles", [])) == 3, body.get("roles"))
check("it returns the permission catalogue", len(body.get("catalog", [])) == len(PERMISSION_KEYS))
check("it returns the group labels", isinstance(body.get("groups"), dict) and len(body["groups"]) >= 4)
check("every role's permissions are real keys",
      all(p in PERMISSION_KEYS for role in body.get("roles", []) for p in role["permissions"]),
      [p for role in body.get("roles", []) for p in role["permissions"] if p not in PERMISSION_KEYS])
check("every role carries an Arabic label",
      all(role.get("label_ar") for role in body.get("roles", [])))

check("a plain admin is refused the catalogue",
      client.get("/admin/staff/roles", headers=H(oldadmin)).status_code == 403)
check("a member is refused the catalogue",
      client.get("/admin/staff/roles", headers=H(plain)).status_code == 403)
check("anon is refused the catalogue",
      client.get("/admin/staff/roles").status_code in (401, 403))


print("\n=== assigning a role ===")
r = client.put(f"/admin/users/{staff.id}/team-role", json={"role": CM}, headers=H(owner))
check("owner may assign a role", r.status_code == 200, r.text[:300])
db.refresh(staff)
check("the row records the role", staff.team_role == CM, staff.team_role)
check("the role made them an admin", staff.is_admin is True, staff.is_admin)
preset = [r_["permissions"] for r_ in TEAM_ROLES if r_["key"] == CM][0]
check("permissions were filled from the preset",
      sorted(json.loads(staff.staff_permissions)) == sorted(preset),
      staff.staff_permissions)
row = r.json()
check("the response carries the role key", row.get("team_role") == CM, row)
check("the response carries the English label", row.get("team_role_label") == "Community Manager", row)
check("the response carries the Arabic label", row.get("team_role_label_ar") == "مدير المجتمع", row)


print("\n=== they show up in the staff tab ===")
r = client.get("/admin/staff", headers=H(owner))
check("/admin/staff is 200 for the owner", r.status_code == 200, r.status_code)
staff_rows = r.json() if r.status_code == 200 else []
if isinstance(staff_rows, dict):
    staff_rows = staff_rows.get("staff", staff_rows.get("items", []))
mine = [x for x in staff_rows if x.get("id") == staff.id]
check("the new role-holder is listed in the staff tab", len(mine) == 1, [x.get("id") for x in staff_rows])
if mine:
    check("their row in the tab names the role", mine[0].get("team_role") == CM, mine[0])
    check("their row in the tab carries the label", mine[0].get("team_role_label") == "Community Manager", mine[0])
plain_rows = [x for x in staff_rows if x.get("id") == plain.id]
check("a plain member is NOT in the staff tab", len(plain_rows) == 0)


print("\n=== the permissions are enforced, not just stored ===")
# community_manager = users, students-progress, feedbacks, reports
check("CM may list members (users ✓)",
      client.get("/admin/users", headers=H(staff)).status_code == 200)
check("CM may NOT read payments (payments ✗)",
      client.get("/admin/payments", headers=H(staff)).status_code == 403)
check("CM may NOT read analytics (analytics ✗)",
      client.get("/admin/analytics/kpis", headers=H(staff)).status_code == 403)
check("CM may NOT hand out roles (owner-only)",
      client.put(f"/admin/users/{plain.id}/team-role", json={"role": TE}, headers=H(staff)).status_code == 403)
check("CM may NOT set another admin's permissions",
      client.put(f"/admin/staff/{oldadmin.id}/permissions", json={"permissions": PERMISSION_KEYS},
                 headers=H(staff)).status_code == 403)

# member-contacts is NOT in the CM preset — the members list must redact
r = client.get("/admin/users", headers=H(staff))
users_body = r.json() if r.status_code == 200 else []
if isinstance(users_body, dict):
    users_body = users_body.get("users", users_body.get("items", []))
target = [u for u in users_body if u.get("id") == plain.id]
check("CM sees the members list but not their email",
      bool(target) and not target[0].get("email"), target[:1])

# now a role that DOES include payments
r = client.put(f"/admin/users/{staff.id}/team-role", json={"role": CS}, headers=H(owner))
check("owner may switch the role", r.status_code == 200, r.text[:200])
check("customer success MAY read payments",
      client.get("/admin/payments", headers=H(staff)).status_code == 200)
check("customer success still may NOT read analytics",
      client.get("/admin/analytics/kpis", headers=H(staff)).status_code == 403)
r = client.get("/admin/users", headers=H(staff))
users_body = r.json() if r.status_code == 200 else []
if isinstance(users_body, dict):
    users_body = users_body.get("users", users_body.get("items", []))
target = [u for u in users_body if u.get("id") == plain.id]
check("customer success DOES see contact details (member-contacts ✓)",
      bool(target) and bool(target[0].get("email")), target[:1])

# technical engineer: content, no people-money
client.put(f"/admin/users/{staff.id}/team-role", json={"role": TE}, headers=H(owner))
check("technical engineer may NOT list members (users ✗)",
      client.get("/admin/users", headers=H(staff)).status_code == 403)
check("technical engineer may NOT read payments",
      client.get("/admin/payments", headers=H(staff)).status_code == 403)


print("\n=== hand-tuning a permission keeps the role ===")
client.put(f"/admin/users/{staff.id}/team-role", json={"role": CM}, headers=H(owner))
tuned = sorted(set(preset) | {"analytics"})
r = client.put(f"/admin/staff/{staff.id}/permissions", json={"permissions": tuned}, headers=H(owner))
check("owner may tune one permission", r.status_code == 200, r.text[:200])
db.refresh(staff)
check("the extra permission stuck",
      "analytics" in json.loads(staff.staff_permissions), staff.staff_permissions)
check("the role name survived the tune", staff.team_role == CM, staff.team_role)
check("the tuned permission is enforced",
      client.get("/admin/analytics/kpis", headers=H(staff)).status_code == 200)

# re-assigning the SAME role without reset must not stomp the hand-tuning
r = client.put(f"/admin/users/{staff.id}/team-role",
               json={"role": CM, "reset_permissions": False}, headers=H(owner))
db.refresh(staff)
check("reset_permissions=false keeps the hand-tuning",
      "analytics" in json.loads(staff.staff_permissions), staff.staff_permissions)
# ...and with reset it goes back to the preset
r = client.put(f"/admin/users/{staff.id}/team-role",
               json={"role": CM, "reset_permissions": True}, headers=H(owner))
db.refresh(staff)
check("reset_permissions=true restores the preset",
      sorted(json.loads(staff.staff_permissions)) == sorted(preset), staff.staff_permissions)
check("the hand-tuned door is shut again",
      client.get("/admin/analytics/kpis", headers=H(staff)).status_code == 403)

# a first-time assignment must take the preset even when asked not to reset
r = client.put(f"/admin/users/{plain.id}/team-role",
               json={"role": TE, "reset_permissions": False}, headers=H(owner))
db.refresh(plain)
check("a first role takes the preset even with reset_permissions=false",
      sorted(json.loads(plain.staff_permissions or "[]")) ==
      sorted([x["permissions"] for x in TEAM_ROLES if x["key"] == TE][0]),
      plain.staff_permissions)
client.put(f"/admin/users/{plain.id}/team-role", json={"role": None}, headers=H(owner))


print("\n=== taking the role away ===")
r = client.put(f"/admin/users/{staff.id}/team-role", json={"role": None}, headers=H(owner))
check("owner may clear a role", r.status_code == 200, r.text[:200])
db.refresh(staff)
check("team_role is cleared", staff.team_role is None, staff.team_role)
check("is_admin is cleared", staff.is_admin is False, staff.is_admin)
check("staff_permissions is cleared", staff.staff_permissions is None, staff.staff_permissions)
check("the demoted user is refused the members list",
      client.get("/admin/users", headers=H(staff)).status_code == 403)
check("the demoted user is refused payments",
      client.get("/admin/payments", headers=H(staff)).status_code == 403)
check("the demoted user is refused the staff tab",
      client.get("/admin/staff", headers=H(staff)).status_code == 403)
r = client.get("/admin/staff", headers=H(owner))
rows = r.json()
if isinstance(rows, dict):
    rows = rows.get("staff", rows.get("items", []))
check("the demoted user is gone from the staff tab",
      not any(x.get("id") == staff.id for x in rows))


print("\n=== the refusals ===")
r = client.put(f"/admin/users/{owner.id}/team-role", json={"role": CM}, headers=H(owner))
check("owner may not change their OWN role", r.status_code == 400, r.status_code)
check("...and the message says why", "own role" in r.text.lower(), r.text[:200])

r = client.put(f"/admin/users/{owner2.id}/team-role", json={"role": CM}, headers=H(owner))
check("an owner's role may not be set from here", r.status_code == 400, r.status_code)
check("...and the message says to remove the owner flag", "owner" in r.text.lower(), r.text[:200])
db.refresh(owner2)
check("the other owner was not touched", owner2.team_role is None and owner2.is_owner is True)

r = client.put(f"/admin/users/{plain.id}/team-role", json={"role": "supreme_leader"}, headers=H(owner))
check("an unknown role is refused", r.status_code == 400, r.status_code)
db.refresh(plain)
check("the unknown role did not make them an admin", plain.is_admin is False, plain.is_admin)

r = client.put("/admin/users/999999/team-role", json={"role": CM}, headers=H(owner))
check("an unknown user is a 404", r.status_code == 404, r.status_code)

check("a member may not assign roles",
      client.put(f"/admin/users/{plain.id}/team-role", json={"role": CM}, headers=H(plain)).status_code == 403)
check("anon may not assign roles",
      client.put(f"/admin/users/{plain.id}/team-role", json={"role": CM}).status_code in (401, 403))


print("\n=== the admin who predates the feature ===")
db.refresh(oldadmin)
check("an admin with no role reads as no role", oldadmin.team_role is None)
r = client.get("/admin/staff", headers=H(owner))
rows = r.json()
if isinstance(rows, dict):
    rows = rows.get("staff", rows.get("items", []))
old = [x for x in rows if x.get("id") == oldadmin.id]
check("they are still listed in the staff tab", len(old) == 1)
if old:
    check("their role is null, not an invented one", old[0].get("team_role") is None, old[0])
    check("their label is null too", old[0].get("team_role_label") is None, old[0])
check("they keep the pre-feature default permissions",
      client.get("/admin/users", headers=H(oldadmin)).status_code == 200)


print("\n" + "=" * 60)
print(f"  {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("   FAILED: " + f)
print("=" * 60)
sys.exit(1 if FAIL else 0)
