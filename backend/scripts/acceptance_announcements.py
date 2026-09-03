"""Acceptance: in-app announcements — permissions, audience, send rules, fan-out.

Covers the Phase 3 checklist for this router plus the background-send change:

  * every endpoint enforces the `announcements` permission, `/audience/preview`
    included — it is the one that hands back member names and counts
  * the audience is steerable only through the whitelisted filter keys
  * a real send with a wrong or missing confirm phrase is refused and writes
    nothing
  * a campaign that has been sent cannot be sent again or edited
  * the real send returns before the fan-out finishes, and the rows still all
    land with the status ending at "sent"

`_clean_link` is deliberately NOT retested here — acceptance_access_control.py
already drives twelve escape spellings through POST /admin/announcements, and
two copies of that list would drift apart.

    DATABASE_URL=postgresql://user:pw@host:5432/ghawy_test \
        python backend/scripts/acceptance_announcements.py
"""
import os
import time

os.environ.setdefault("SECRET_KEY", "dummy_secret_for_import_check")

from _acceptance_guard import require_scratch_database  # noqa: E402
require_scratch_database()

from fastapi.testclient import TestClient          # noqa: E402
from sqlalchemy import text as _text               # noqa: E402
import bcrypt                                      # noqa: E402

import main                                        # noqa: E402
from app.database import SessionLocal, engine      # noqa: E402
from app.models import Base                        # noqa: E402
from app import models as M                        # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name + (("  -> " + str(detail)) if (detail and not cond) else ""))


with engine.begin() as _c:
    _c.execute(_text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
Base.metadata.create_all(bind=engine)
db = SessionLocal()


def mkuser(email, active=True, admin=False, owner=False, name="Test User", country=None):
    u = M.User(email=email, hashed_password=bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode(),
               full_name=name, is_active=active, is_admin=admin, is_owner=owner,
               is_verified=True, country=country)
    db.add(u); db.commit(); db.refresh(u)
    return u


from app.services.permissions import dump_permissions     # noqa: E402
from app.routers.users import issue_token_for             # noqa: E402

owner   = mkuser("owner@t.co", admin=True, owner=True, name="Owner")
sender  = mkuser("sender@t.co", admin=True, name="Sender")          # has the permission
nosy    = mkuser("nosy@t.co",   admin=True, name="Nosy Staff")      # admin, other permissions
member  = mkuser("member@t.co", name="Ordinary Member", country="Egypt")
member2 = mkuser("m2@t.co",     name="Second Member",   country="Egypt")
faraway = mkuser("far@t.co",    name="Far Member",      country="Jordan")
dormant = mkuser("dorm@t.co", active=False, name="Dormant Member", country="Egypt")

sender.staff_permissions = dump_permissions(["announcements"])
nosy.staff_permissions = dump_permissions(["users", "payments"])    # anything but announcements
db.commit()

client = TestClient(main.app)


def H(u):
    return {"Authorization": "Bearer " + issue_token_for(u)}


def notif_count(announcement_id=None):
    q = db.query(M.Notification)
    if announcement_id is not None:
        q = q.filter(M.Notification.announcement_id == announcement_id)
    db.expire_all()
    return q.count()


def mkcampaign(actor=None, **over):
    payload = {"title": "T", "body": "B", "type": "info"}
    payload.update(over)
    r = client.post("/admin/announcements", headers=H(actor or sender), json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ══════════════════════════════════════════════════════════════
print("\n=== every endpoint enforces the `announcements` permission ===")
# ══════════════════════════════════════════════════════════════
camp = mkcampaign()
CID = camp["id"]

ENDPOINTS = [
    ("GET",    "/admin/announcements",                      None),
    ("GET",    f"/admin/announcements/{CID}",               None),
    ("GET",    "/admin/announcements/audience/preview",     None),
    ("GET",    f"/admin/announcements/{CID}/status",        None),
    ("POST",   "/admin/announcements",                      {"title": "x", "body": "y"}),
    ("PUT",    f"/admin/announcements/{CID}",               {"title": "x", "body": "y"}),
    ("POST",   f"/admin/announcements/{CID}/duplicate",     {}),
    ("POST",   f"/admin/announcements/{CID}/send",          {"mode": "test"}),
    ("DELETE", f"/admin/announcements/{CID}",               None),
]

for method, path, body in ENDPOINTS:
    r = client.request(method, path, headers=H(member), json=body)
    check(f"member is refused {method} {path}", r.status_code == 403, f"{r.status_code} {r.text[:100]}")

for method, path, body in ENDPOINTS:
    r = client.request(method, path, headers=H(nosy), json=body)
    check(f"admin without the permission is refused {method} {path}",
          r.status_code == 403, f"{r.status_code} {r.text[:100]}")

for method, path, body in ENDPOINTS:
    r = client.request(method, path, json=body)
    check(f"anonymous is refused {method} {path}", r.status_code == 401, f"{r.status_code} {r.text[:100]}")

# The preview is the endpoint that leaks names and counts, so it gets its own
# assertion rather than only living in the loop above.
r = client.get("/admin/announcements/audience/preview", headers=H(member))
leaked = any(n in r.text for n in ("Ordinary Member", "Second Member", "member@t.co"))
check("/audience/preview leaks no member names to someone without the permission",
      r.status_code == 403 and not leaked, f"{r.status_code} {r.text[:160]}")

r = client.get("/admin/announcements/audience/preview", headers=H(sender))
check("...and still answers for someone who has it", r.status_code == 200, f"{r.status_code} {r.text[:120]}")


# ══════════════════════════════════════════════════════════════
print("\n=== the audience is steerable only by the whitelisted filter keys ===")
# ══════════════════════════════════════════════════════════════
# Every one of these is a key the client made up. If any of them survives into
# the stored filter, the audience is no longer server-decided.
INJECTED = {
    "user_ids": [member.id, faraway.id],
    "ids": [faraway.id],
    "id": faraway.id,
    "emails": ["far@t.co"],
    "is_admin": True,
    "limit": 999999,
    "sql": "1=1",
    "__class__": "x",
}
c = mkcampaign(audience=dict(INJECTED, status="active", country="Egypt"))
stored = c["audience"]
check("unknown audience keys are dropped on save",
      not (set(INJECTED) & set(stored)), f"survived: {sorted(set(INJECTED) & set(stored))}")
check("the whitelisted keys are kept",
      stored.get("status") == "active" and stored.get("country") == "Egypt", stored)

# Same keys through the preview query string: they must not change the answer.
base = client.get("/admin/announcements/audience/preview?status=active&country=Egypt",
                  headers=H(sender)).json()
poisoned = client.get(
    "/admin/announcements/audience/preview?status=active&country=Egypt"
    f"&user_ids={faraway.id}&ids={faraway.id}&is_admin=true&limit=999999&include_staff=false",
    headers=H(sender)).json()
check("injected query keys do not change the resolved count",
      base["count"] == poisoned["count"], f"{base['count']} vs {poisoned['count']}")
check("the filter really is doing something (Egypt+active excludes the others)",
      base["count"] == 2, f"count={base['count']} (expect member + member2)")

sample_ids = {s["id"] for s in base.get("sample", [])}
check("a member outside the filter is not in the audience",
      faraway.id not in sample_ids and dormant.id not in sample_ids, sample_ids)
check("staff are excluded unless include_staff is set",
      sender.id not in sample_ids and owner.id not in sample_ids, sample_ids)


# ══════════════════════════════════════════════════════════════
print("\n=== a real send needs the exact confirm phrase ===")
# ══════════════════════════════════════════════════════════════
# Note the phrase is compared after .strip(), so surrounding whitespace is
# tolerated on purpose — an operator pasting the phrase should not be blocked by
# a trailing space. Everything else about it is exact, including case.
for phrase in (None, "", "ghawy-official-send", "wrong", "GHAWY OFFICIAL SEND",
               "GHAWY-OFFICIAL-SENDX", "GHAWY_OFFICIAL_SEND"):
    c = mkcampaign(audience={"status": "all"})
    body = {"mode": "real"}
    if phrase is not None:
        body["confirm_phrase"] = phrase
    before = notif_count()
    r = client.post(f"/admin/announcements/{c['id']}/send", headers=H(sender), json=body)
    after = notif_count()
    row = db.query(M.Announcement).filter(M.Announcement.id == c["id"]).first()
    db.refresh(row)
    check(f"confirm_phrase={phrase!r} is refused with 400", r.status_code == 400,
          f"{r.status_code} {r.text[:120]}")
    check(f"confirm_phrase={phrase!r} wrote zero notification rows", after == before,
          f"{before} -> {after}")
    check(f"confirm_phrase={phrase!r} leaves the campaign a draft", row.status == "draft", row.status)

# Whitespace around the phrase is trimmed, not rejected — assert the behaviour
# the code actually intends rather than assuming it is exact-match on the raw
# string.
c_ws = mkcampaign(audience={"status": "active", "country": "Jordan"})
r = client.post(f"/admin/announcements/{c_ws['id']}/send", headers=H(sender),
                json={"mode": "real", "confirm_phrase": "  GHAWY-OFFICIAL-SEND  "})
check("whitespace around the confirm phrase is trimmed, not refused",
      r.status_code == 200, f"{r.status_code} {r.text[:120]}")


def wait_sent(cid, timeout=30):
    """The fan-out runs in a thread now — wait for it before asserting.

    Also what keeps these cases independent: the send lock is held until the
    worker finishes, so firing the next send too early gets a 409 rather than
    the behaviour under test.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = client.get(f"/admin/announcements/{cid}/status", headers=H(sender)).json()
        if st["status"] in ("sent", "failed"):
            return st
        time.sleep(0.2)
    return client.get(f"/admin/announcements/{cid}/status", headers=H(sender)).json()


wait_sent(c_ws["id"])                      # release the lock before the next send

c = mkcampaign(audience={"status": "active", "country": "Jordan"})
r = client.post(f"/admin/announcements/{c['id']}/send", headers=H(sender),
                json={"mode": "real", "confirm_phrase": "GHAWY-OFFICIAL-SEND"})
check("the exact phrase is accepted", r.status_code == 200, f"{r.status_code} {r.text[:160]}")

st = wait_sent(c["id"])
check("the accepted send reaches status=sent", st["status"] == "sent", st)
check("it delivered to exactly the filtered member", st["delivered"] == 1, st)
only = db.query(M.Notification).filter(M.Notification.announcement_id == c["id"]).all()
check("...and that member is the one the filter named",
      [n.user_id for n in only] == [faraway.id], [n.user_id for n in only])


# ══════════════════════════════════════════════════════════════
print("\n=== a sent campaign cannot be sent again or edited ===")
# ══════════════════════════════════════════════════════════════
sent_id = c["id"]
before = notif_count()
r = client.post(f"/admin/announcements/{sent_id}/send", headers=H(sender),
                json={"mode": "real", "confirm_phrase": "GHAWY-OFFICIAL-SEND"})
check("re-sending a sent campaign is refused with 400", r.status_code == 400,
      f"{r.status_code} {r.text[:120]}")
check("the refused re-send wrote no rows", notif_count() == before, f"{before} -> {notif_count()}")

r = client.put(f"/admin/announcements/{sent_id}", headers=H(sender),
               json={"title": "EDITED AFTER SEND", "body": "EDITED", "type": "warning"})
row = db.query(M.Announcement).filter(M.Announcement.id == sent_id).first()
db.refresh(row)
check("editing a sent campaign is refused", r.status_code == 400, f"{r.status_code} {r.text[:120]}")
check("...and the stored campaign is untouched",
      row.title != "EDITED AFTER SEND" and row.body != "EDITED", f"{row.title!r}/{row.body!r}")

# The escape hatch the refusal points at must actually work.
r = client.post(f"/admin/announcements/{sent_id}/duplicate", headers=H(sender), json={})
check("duplicating a sent campaign gives a fresh draft",
      r.status_code == 201 and r.json()["status"] == "draft", f"{r.status_code} {r.text[:120]}")


# ══════════════════════════════════════════════════════════════
print("\n=== the real send hands off to a thread and still delivers ===")
# ══════════════════════════════════════════════════════════════
for i in range(60):                       # a crowd worth fanning out to
    mkuser(f"crowd{i}@t.co", name=f"Crowd {i}", country="Egypt")

c = mkcampaign(audience={"status": "active", "country": "Egypt"})
expected = client.get("/admin/announcements/audience/preview?status=active&country=Egypt",
                      headers=H(sender)).json()["count"]

t0 = time.time()
r = client.post(f"/admin/announcements/{c['id']}/send", headers=H(sender),
                json={"mode": "real", "confirm_phrase": "GHAWY-OFFICIAL-SEND"})
elapsed = time.time() - t0
body = r.json()
check("the send is accepted", r.status_code == 200, f"{r.status_code} {r.text[:160]}")
check("it reports the resolved recipient count", body.get("delivered") == expected,
      f"{body.get('delivered')} vs {expected}")
check("it returns while the campaign is still 'sending'", body.get("status") == "sending", body)

st = wait_sent(c["id"])
check("the thread finishes at status=sent", st["status"] == "sent", st)
check("every recipient row landed", st["delivered"] == expected, f"{st['delivered']} vs {expected}")
check("sending_active is cleared when it finishes", st["sending_active"] is False, st)
check("a finished send is not reported as stalled", st["stalled"] is False, st)
check(f"the request did not block on the fan-out ({elapsed:.2f}s)", elapsed < 5, f"{elapsed:.2f}s")

rows = db.query(M.Notification).filter(M.Notification.announcement_id == c["id"]).all()
check("no member got the same campaign twice",
      len({n.user_id for n in rows}) == len(rows), f"{len(rows)} rows, {len({n.user_id for n in rows})} members")
check("the notification carries the campaign's own type",
      all(n.type == "info" for n in rows), {n.type for n in rows})
check("staff were not swept into the audience",
      sender.id not in {n.user_id for n in rows} and owner.id not in {n.user_id for n in rows})

# A test send is still synchronous and still goes to the sender alone.
c2 = mkcampaign(audience={"status": "all"})
before = notif_count()
r = client.post(f"/admin/announcements/{c2['id']}/send", headers=H(sender), json={"mode": "test"})
after = notif_count()
row = db.query(M.Announcement).filter(M.Announcement.id == c2["id"]).first()
db.refresh(row)
check("a test send writes exactly one row", after - before == 1, f"{before} -> {after}")
test_rows = db.query(M.Notification).filter(M.Notification.announcement_id == c2["id"]).all()
check("...addressed to the sender and nobody else",
      [n.user_id for n in test_rows] == [sender.id], [n.user_id for n in test_rows])
check("...and it leaves the campaign a draft", row.status == "draft", row.status)


# ══════════════════════════════════════════════════════════════
print("\n=== the recipients view answers 'who did not open it' ===")
# ══════════════════════════════════════════════════════════════
big_id = c["id"]                                   # the 60+ member campaign above
rows = db.query(M.Notification).filter(M.Notification.announcement_id == big_id).all()
for n in rows[:5]:                                 # five of them opened it
    n.is_read = True
db.commit()
total = len(rows)

r = client.get(f"/admin/announcements/{big_id}/recipients", headers=H(sender))
d = r.json()
check("recipients answers for someone with the permission", r.status_code == 200, r.text[:120])
check("it reports read/unread over the whole campaign",
      d["delivered"] == total and d["read"] == 5 and d["unread"] == total - 5, d)
check("it defaults to the members who did NOT open it",
      all(i["is_read"] is False for i in d["items"]), [i["is_read"] for i in d["items"]][:5])

r = client.get(f"/admin/announcements/{big_id}/recipients?state=read", headers=H(sender))
d_read = r.json()
check("state=read returns only openers", d_read["total"] == 5
      and all(i["is_read"] for i in d_read["items"]), d_read["total"])

r = client.get(f"/admin/announcements/{big_id}/recipients?state=all&limit=10&offset=0", headers=H(sender))
p1 = r.json()
r = client.get(f"/admin/announcements/{big_id}/recipients?state=all&limit=10&offset=10", headers=H(sender))
p2 = r.json()
check("it pages rather than dumping the whole audience",
      len(p1["items"]) == 10 and p1["has_more"] is True, f"{len(p1['items'])} has_more={p1['has_more']}")
check("paging does not repeat rows",
      not ({i["user_id"] for i in p1["items"]} & {i["user_id"] for i in p2["items"]}))
check("the page total counts the campaign, not the page", p1["total"] == total, p1["total"])

r = client.get(f"/admin/announcements/{big_id}/recipients?state=all&search=Crowd%207", headers=H(sender))
d_s = r.json()
check("search narrows by name", d_s["total"] >= 1
      and all("Crowd 7" in i["full_name"] for i in d_s["items"]), d_s["total"])

r = client.get(f"/admin/announcements/{big_id}/recipients", headers=H(member))
leaked = any(x in r.text for x in ("Crowd 1", "crowd1@t.co"))
check("recipients leaks no member to someone without the permission",
      r.status_code == 403 and not leaked, f"{r.status_code} {r.text[:120]}")
r = client.get(f"/admin/announcements/{big_id}/recipients")
check("recipients refuses anonymous", r.status_code == 401, r.status_code)


# ══════════════════════════════════════════════════════════════
print("\n=== scheduling: the human decision happens at schedule time ===")
# ══════════════════════════════════════════════════════════════
import asyncio                                                    # noqa: E402
from datetime import datetime as _dt, timedelta as _td            # noqa: E402

def iso_in(**kw):
    return (_dt.utcnow() + _td(**kw)).isoformat()

c = mkcampaign(audience={"status": "active", "country": "Jordan"})
SID = c["id"]

r = client.post(f"/admin/announcements/{SID}/schedule", headers=H(sender),
                json={"scheduled_for": iso_in(hours=2)})
check("scheduling without the confirm phrase is refused", r.status_code == 400, r.text[:120])

r = client.post(f"/admin/announcements/{SID}/schedule", headers=H(sender),
                json={"scheduled_for": iso_in(hours=2), "confirm_phrase": "nope"})
check("scheduling with a wrong confirm phrase is refused", r.status_code == 400, r.text[:120])

r = client.post(f"/admin/announcements/{SID}/schedule", headers=H(sender),
                json={"scheduled_for": iso_in(hours=-1), "confirm_phrase": "GHAWY-OFFICIAL-SEND"})
check("scheduling in the past is refused", r.status_code == 400, r.text[:120])

r = client.post(f"/admin/announcements/{SID}/schedule", headers=H(sender),
                json={"scheduled_for": "not-a-date", "confirm_phrase": "GHAWY-OFFICIAL-SEND"})
check("an unparseable date is refused", r.status_code == 400, r.text[:120])

r = client.post(f"/admin/announcements/{SID}/schedule", headers=H(member),
                json={"scheduled_for": iso_in(hours=2), "confirm_phrase": "GHAWY-OFFICIAL-SEND"})
check("scheduling needs the announcements permission", r.status_code == 403, r.status_code)

r = client.post(f"/admin/announcements/{SID}/schedule", headers=H(sender),
                json={"scheduled_for": iso_in(hours=2), "confirm_phrase": "GHAWY-OFFICIAL-SEND"})
check("a valid schedule is accepted", r.status_code == 200, r.text[:160])
check("...and the campaign is now 'scheduled'", (r.json() or {}).get("status") == "scheduled", r.json())
check("...with the due time stored", bool((r.json() or {}).get("scheduled_for")), r.json())

# The phrase was typed against THIS text, so the text is frozen until unscheduled.
r = client.put(f"/admin/announcements/{SID}", headers=H(sender),
               json={"title": "SWAPPED", "body": "SWAPPED", "type": "promo"})
row = db.query(M.Announcement).filter(M.Announcement.id == SID).first(); db.refresh(row)
check("a scheduled campaign cannot be edited", r.status_code == 400, r.text[:120])
check("...and its text is untouched", row.title != "SWAPPED", row.title)

r = client.post(f"/admin/announcements/{SID}/unschedule", headers=H(sender))
row = db.query(M.Announcement).filter(M.Announcement.id == SID).first(); db.refresh(row)
check("unscheduling returns it to draft",
      r.status_code == 200 and row.status == "draft" and row.scheduled_for is None,
      f"{r.status_code} {row.status} {row.scheduled_for}")
r = client.post(f"/admin/announcements/{SID}/unschedule", headers=H(sender))
check("unscheduling something that is not scheduled is refused", r.status_code == 400, r.status_code)

# ── the job itself ──
from app.scheduler import fire_scheduled_announcements, _due_scheduled_announcements   # noqa: E402

client.post(f"/admin/announcements/{SID}/schedule", headers=H(sender),
            json={"scheduled_for": iso_in(hours=2), "confirm_phrase": "GHAWY-OFFICIAL-SEND"})
check("a future campaign is not yet due", SID not in _due_scheduled_announcements())

row = db.query(M.Announcement).filter(M.Announcement.id == SID).first()
row.scheduled_for = _dt.utcnow() - _td(minutes=1)          # its moment arrives
db.commit()
check("a past-due campaign is picked up by the sweep", SID in _due_scheduled_announcements())

before = notif_count(SID)
asyncio.run(fire_scheduled_announcements())
st = wait_sent(SID)
check("the scheduler fires it without any phrase at fire time", st["status"] == "sent", st)
check("...and it delivered", st["delivered"] >= 1 and notif_count(SID) > before,
      f"{before} -> {notif_count(SID)}")
check("...and it is no longer due", SID not in _due_scheduled_announcements())


print("\n" + "=" * 72)
print(f"passed {len(PASS)}   failed {len(FAIL)}")
for f in FAIL:
    print("  FAILED: " + f)
print("=" * 72)
raise SystemExit(1 if FAIL else 0)
