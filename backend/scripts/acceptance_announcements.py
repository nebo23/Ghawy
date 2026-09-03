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

and the closing pass on the feature:

  * A1 — a campaign that died mid-fan-out RESUMES instead of re-sending. The
    failure is forced, not simulated: `_chunks` is swapped so the first batch
    commits and the second raises, which is the exact shape of a worker dying
    halfway. The assertion that matters is that nobody holds two rows for the
    same campaign afterwards.
  * A2 — a scheduled campaign overdue past the grace window is closed out with
    a reason instead of being sent hours late; one inside the window still
    fires.
  * A3 — the list pages, searches title and body, and filters by status.
  * B3 — every send-as guardrail, driven at the endpoint with a hand-written
    `sender_id`, because the composer's dropdown is not where the rule lives.
  * B  — a DM campaign builds one conversation per member and no more, re-runs
    without forking it, reports real delivered/read counts, and tells the
    account holder when somebody else sent from their account.

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


# ══════════════════════════════════════════════════════════════
print("\n=== A1 · a campaign that failed part-way RESUMES, it does not re-send ===")
# ══════════════════════════════════════════════════════════════
# The rule "a sent campaign cannot be sent again" exists to prevent one thing:
# duplicate delivery, the only outcome here that cannot be taken back. It was
# measured on `status == "sent"` alone, so a campaign that died mid-fan-out sat
# at `failed` holding members who HAD been delivered — and sending it again
# reached them twice, which is exactly what the rule was for.
#
# The failure below is forced rather than simulated: `_chunks` is replaced so
# the first batch commits and the second raises, which is precisely the shape
# of a worker dying in the middle of the fan-out.
import app.routers.announcements as AN                                # noqa: E402

_real_chunks = AN._chunks


def _explode_after_one(seq, size):
    """Yield one small batch, then blow up — a real mid-fan-out death."""
    first = True
    for c in _real_chunks(seq, 2):
        if not first:
            raise RuntimeError("forced mid-fan-out failure")
        first = False
        yield c


def send_real(cid, actor=None):
    return client.post(f"/admin/announcements/{cid}/send", headers=H(actor or sender),
                       json={"mode": "real", "confirm_phrase": "GHAWY-OFFICIAL-SEND"})


for i in range(6):
    mkuser(f"resume{i}@t.co", name=f"Resume {i}", country="Yemen")

camp = mkcampaign(audience={"status": "active", "country": "Yemen"})
RID = camp["id"]
expected = client.get("/admin/announcements/audience/preview?status=active&country=Yemen",
                      headers=H(sender)).json()["count"]
check("the resume fixture has an audience worth chunking", expected == 6, expected)

AN._chunks = _explode_after_one
try:
    r = send_real(RID)
    st = wait_sent(RID)
finally:
    AN._chunks = _real_chunks

check("the forced failure lands the campaign at status=failed", st["status"] == "failed", st)
partial = notif_count(RID)
check("...having delivered SOME of the audience, not all",
      0 < partial < expected, f"{partial} of {expected}")
check("...and the status endpoint reports the partial count", st["delivered"] == partial, st)
check("...and records a reason rather than a bare dead end",
      bool(st.get("failure_reason")), st.get("failure_reason"))
check("...and reports itself resumable", st.get("resumable") is True, st)

# The lock is the thing that blocks every later send if a dying worker keeps
# it. It must be free.
check("the failed worker released the send lock", AN._send_lock.acquire(blocking=False),
      "lock still held after a failed send")
AN._send_lock.release()

delivered_before = {n.user_id for n in
                    db.query(M.Notification).filter(M.Notification.announcement_id == RID).all()}

r = send_real(RID)
body = r.json()
check("re-sending a FAILED campaign is accepted (it resumes)", r.status_code == 200,
      f"{r.status_code} {r.text[:160]}")
check("...and says it is resuming", body.get("resuming") is True, body)
check("...and skips the members it already reached",
      body.get("skipped") == partial, f"skipped={body.get('skipped')} partial={partial}")

st = wait_sent(RID)
check("the resumed send finishes at status=sent", st["status"] == "sent", st)
check("...clearing the failure reason", not st.get("failure_reason"), st.get("failure_reason"))

rows = db.query(M.Notification).filter(M.Notification.announcement_id == RID).all()
per_user = {}
for n in rows:
    per_user[n.user_id] = per_user.get(n.user_id, 0) + 1
dupes = {uid: c for uid, c in per_user.items() if c > 1}
check("NOBODY received the campaign twice", not dupes, dupes)
check("...including everyone who was delivered before the failure",
      all(per_user.get(uid) == 1 for uid in delivered_before),
      {uid: per_user.get(uid) for uid in delivered_before})
check("...and the whole audience ended up delivered", len(rows) == expected,
      f"{len(rows)} of {expected}")

# ── a worker that died leaves status='sending' with no thread: same recovery ──
stuck = mkcampaign(audience={"status": "active", "country": "Yemen"})
SID2 = stuck["id"]
AN._chunks = _explode_after_one
try:
    send_real(SID2)
    wait_sent(SID2)
finally:
    AN._chunks = _real_chunks
row = db.query(M.Announcement).filter(M.Announcement.id == SID2).first()
row.status = "sending"                     # the shape a killed process leaves
db.commit()
st = client.get(f"/admin/announcements/{SID2}/status", headers=H(sender)).json()
check("a 'sending' campaign with no live worker reports stalled", st["stalled"] is True, st)
check("...and is reported resumable", st.get("resumable") is True, st)

before_rows = notif_count(SID2)
r = send_real(SID2)
check("a stalled campaign can be resumed", r.status_code == 200, f"{r.status_code} {r.text[:160]}")
st = wait_sent(SID2)
rows = db.query(M.Notification).filter(M.Notification.announcement_id == SID2).all()
per_user = {}
for n in rows:
    per_user[n.user_id] = per_user.get(n.user_id, 0) + 1
check("resuming a stalled campaign delivers nobody twice",
      all(c == 1 for c in per_user.values()), {u: c for u, c in per_user.items() if c > 1})
check("...and completes the audience", len(rows) == expected, f"{len(rows)} of {expected}")

# ── the text of a partially delivered campaign is frozen ──
frozen = mkcampaign(audience={"status": "active", "country": "Yemen"})
FID = frozen["id"]
AN._chunks = _explode_after_one
try:
    send_real(FID)
    wait_sent(FID)
finally:
    AN._chunks = _real_chunks
r = client.put(f"/admin/announcements/{FID}", headers=H(sender),
               json={"title": "REWRITTEN", "body": "REWRITTEN"})
row = db.query(M.Announcement).filter(M.Announcement.id == FID).first(); db.refresh(row)
check("a failed campaign that already reached members cannot be edited",
      r.status_code == 400, f"{r.status_code} {r.text[:120]}")
check("...and its text is untouched", row.title != "REWRITTEN", row.title)

# One that failed WITHOUT delivering anything has nothing frozen about it.
empty_fail = mkcampaign(audience={"status": "active", "country": "Yemen"})
EFID = empty_fail["id"]
row = db.query(M.Announcement).filter(M.Announcement.id == EFID).first()
row.status = "failed"
db.commit()
r = client.put(f"/admin/announcements/{EFID}", headers=H(sender),
               json={"title": "STILL EDITABLE", "body": "yes"})
check("a failed campaign that reached NOBODY is still editable",
      r.status_code == 200, f"{r.status_code} {r.text[:120]}")

wait_sent(FID)   # settle the lock before the next section


# ══════════════════════════════════════════════════════════════
print("\n=== A2 · a scheduled campaign that missed its moment is not sent late ===")
# ══════════════════════════════════════════════════════════════
from app.scheduler import _expire_stale_scheduled                     # noqa: E402

fresh = mkcampaign(audience={"status": "active", "country": "Jordan"})
FRESH = fresh["id"]
client.post(f"/admin/announcements/{FRESH}/schedule", headers=H(sender),
            json={"scheduled_for": iso_in(hours=2), "confirm_phrase": "GHAWY-OFFICIAL-SEND"})
row = db.query(M.Announcement).filter(M.Announcement.id == FRESH).first()
row.scheduled_for = _dt.utcnow() - _td(minutes=20)          # late, but within the window
db.commit()
check("a campaign overdue by minutes is still due", FRESH in _due_scheduled_announcements())

stale = mkcampaign(audience={"status": "active", "country": "Jordan"})
STALE = stale["id"]
client.post(f"/admin/announcements/{STALE}/schedule", headers=H(sender),
            json={"scheduled_for": iso_in(hours=2), "confirm_phrase": "GHAWY-OFFICIAL-SEND"})
row = db.query(M.Announcement).filter(M.Announcement.id == STALE).first()
row.scheduled_for = _dt.utcnow() - (AN.SCHEDULE_GRACE + _td(minutes=5))
db.commit()
check("a campaign overdue past the grace window is NOT due",
      STALE not in _due_scheduled_announcements())

before = notif_count(STALE)
closed = _expire_stale_scheduled()
row = db.query(M.Announcement).filter(M.Announcement.id == STALE).first(); db.refresh(row)
check("the stale sweep closes it out", STALE in closed, closed)
check("...marking it failed rather than leaving it scheduled forever",
      row.status == "failed", row.status)
check("...with the reason written on the row", bool(row.failure_reason), row.failure_reason)
check("...and it delivered to nobody", notif_count(STALE) == before, notif_count(STALE))
check("...and the fresh one was left alone",
      db.query(M.Announcement).filter(M.Announcement.id == FRESH).first().status == "scheduled")

asyncio.run(fire_scheduled_announcements())
st = wait_sent(FRESH)
check("the campaign inside the window still fires", st["status"] == "sent", st)
row = db.query(M.Announcement).filter(M.Announcement.id == STALE).first(); db.refresh(row)
check("...and the stale one is still failed, not swept up with it",
      row.status == "failed", row.status)


# ══════════════════════════════════════════════════════════════
print("\n=== A3 · the list paginates, searches and filters ===")
# ══════════════════════════════════════════════════════════════
r = client.get("/admin/announcements?limit=5&offset=0", headers=H(sender))
p1 = r.json()
check("the list answers with a paged envelope",
      isinstance(p1, dict) and {"items", "total", "has_more"} <= set(p1), list(p1)[:6])
check("...honouring the page size", len(p1["items"]) == 5, len(p1["items"]))
check("...and reporting a total larger than the page", p1["total"] > 5, p1["total"])
check("...and saying there is more", p1["has_more"] is True, p1)

p2 = client.get("/admin/announcements?limit=5&offset=5", headers=H(sender)).json()
check("paging does not repeat campaigns",
      not ({i["id"] for i in p1["items"]} & {i["id"] for i in p2["items"]}))

needle = mkcampaign(title="Ramadan schedule notice", body="the body mentions ZZQQ uniquely")
r = client.get("/admin/announcements?q=Ramadan", headers=H(sender)).json()
check("search matches the title", any(i["id"] == needle["id"] for i in r["items"]), r["total"])
r = client.get("/admin/announcements?q=ZZQQ", headers=H(sender)).json()
check("search matches the body too", any(i["id"] == needle["id"] for i in r["items"]), r["total"])
r = client.get("/admin/announcements?q=nothing-matches-this-at-all", headers=H(sender)).json()
check("a search that matches nothing returns nothing", r["total"] == 0, r["total"])

r = client.get("/admin/announcements?status=sent", headers=H(sender)).json()
check("status=sent returns only sent campaigns",
      r["items"] and all(i["status"] == "sent" for i in r["items"]),
      {i["status"] for i in r["items"]})
r = client.get("/admin/announcements?status=failed", headers=H(sender)).json()
check("status=failed returns only failed campaigns",
      r["items"] and all(i["status"] == "failed" for i in r["items"]),
      {i["status"] for i in r["items"]})
r = client.get("/admin/announcements?status=draft", headers=H(sender)).json()
check("status=draft returns only drafts",
      r["items"] and all(i["status"] == "draft" for i in r["items"]),
      {i["status"] for i in r["items"]})

sent_page = client.get("/admin/announcements?status=sent&limit=50", headers=H(sender)).json()
check("a sent campaign in the list still carries its delivered/read stats",
      any(i["delivered"] > 0 for i in sent_page["items"]),
      [i["delivered"] for i in sent_page["items"]][:5])
failed_page = client.get("/admin/announcements?status=failed&limit=50", headers=H(sender)).json()
check("a FAILED campaign shows its partial delivery count on the card",
      any(i["delivered"] > 0 for i in failed_page["items"]),
      [(i["id"], i["delivered"]) for i in failed_page["items"]][:6])


# ══════════════════════════════════════════════════════════════
print("\n=== B3 · who a DM campaign comes from — enforced at the ENDPOINT ===")
# ══════════════════════════════════════════════════════════════
# The composer's dropdown is a convenience. Every assertion here goes straight
# at the API with a hand-written sender_id, because that is the only place the
# rule can actually be broken.
sender2 = mkuser("sender2@t.co", admin=True, name="Second Admin")
sender2.staff_permissions = dump_permissions(["announcements"])
db.commit()


def dm_payload(**over):
    p = {"title": "DM T", "body": "DM B", "type": "info", "delivery": "dm"}
    p.update(over)
    return p


# ── sender_id must be an admin ──
for bad_id, label in ((member.id, "an ordinary member"), (dormant.id, "an inactive member")):
    r = client.post("/admin/announcements", headers=H(owner), json=dm_payload(sender_id=bad_id))
    check(f"sender_id cannot be {label}", r.status_code == 400, f"{r.status_code} {r.text[:120]}")

r = client.post("/admin/announcements", headers=H(owner), json=dm_payload(sender_id=999999))
check("sender_id cannot be an account that does not exist", r.status_code == 400,
      f"{r.status_code} {r.text[:120]}")

# ── only the owner may send as somebody else ──
r = client.post("/admin/announcements", headers=H(sender), json=dm_payload(sender_id=sender2.id))
check("an admin cannot create a DM campaign FROM another admin",
      r.status_code == 403, f"{r.status_code} {r.text[:120]}")
r = client.post("/admin/announcements", headers=H(sender), json=dm_payload(sender_id=owner.id))
check("an admin cannot create a DM campaign FROM the owner",
      r.status_code == 403, f"{r.status_code} {r.text[:120]}")

r = client.post("/admin/announcements", headers=H(sender), json=dm_payload(sender_id=sender.id))
check("an admin CAN send as themselves", r.status_code == 201, f"{r.status_code} {r.text[:120]}")
own_dm = r.json()
check("...and the stored sender is them", own_dm["sender_id"] == sender.id, own_dm["sender_id"])

r = client.post("/admin/announcements", headers=H(sender), json=dm_payload())
check("omitting sender_id defaults to the actor, not to nobody",
      r.status_code == 201 and r.json()["sender_id"] == sender.id, r.text[:120])

r = client.post("/admin/announcements", headers=H(owner), json=dm_payload(sender_id=sender2.id))
check("the OWNER may send as another admin", r.status_code == 201, f"{r.status_code} {r.text[:120]}")
owner_as_other = r.json()
check("...and it is stored against that admin",
      owner_as_other["sender_id"] == sender2.id, owner_as_other["sender_id"])

# ── the same rule on update, not only on create ──
r = client.put(f"/admin/announcements/{own_dm['id']}", headers=H(sender),
               json=dm_payload(sender_id=sender2.id))
row = db.query(M.Announcement).filter(M.Announcement.id == own_dm["id"]).first(); db.refresh(row)
check("an admin cannot re-point an existing campaign at another admin",
      r.status_code == 403, f"{r.status_code} {r.text[:120]}")
check("...and the stored sender is unchanged", row.sender_id == sender.id, row.sender_id)

# ── and on send: the campaign row alone proves nothing ──
# The owner built this one to go out as sender2. An admin pressing send on it
# must be refused, or the rule is only skin deep.
r = client.post(f"/admin/announcements/{owner_as_other['id']}/send", headers=H(sender),
                json={"mode": "real", "confirm_phrase": "GHAWY-OFFICIAL-SEND"})
check("an admin cannot SEND a campaign that goes out from another admin's account",
      r.status_code == 403, f"{r.status_code} {r.text[:120]}")
check("...and that refusal did not leave the send lock held",
      AN._send_lock.acquire(blocking=False), "lock held after a refused send")
AN._send_lock.release()

r = client.post(f"/admin/announcements/{owner_as_other['id']}/schedule", headers=H(sender),
                json={"scheduled_for": iso_in(hours=2), "confirm_phrase": "GHAWY-OFFICIAL-SEND"})
check("...nor SCHEDULE it", r.status_code == 403, f"{r.status_code} {r.text[:120]}")

r = client.post(f"/admin/announcements/{owner_as_other['id']}/duplicate", headers=H(sender), json={})
check("duplicating it is allowed but resets the sender to the duplicator",
      r.status_code == 201 and r.json()["sender_id"] == sender.id,
      f"{r.status_code} {r.text[:140]}")

# ── the senders list matches the rule it advertises ──
mine = client.get("/admin/announcements/senders", headers=H(sender)).json()
check("an admin is offered only themselves as a sender",
      [s["id"] for s in mine] == [sender.id], [s["id"] for s in mine])
theirs = client.get("/admin/announcements/senders", headers=H(owner)).json()
ids = {s["id"] for s in theirs}
check("the owner is offered the admins", {owner.id, sender.id, sender2.id} <= ids, ids)
check("...and no ordinary member is offered", member.id not in ids and dormant.id not in ids, ids)


# ── the account must STILL be an admin when the campaign actually fires ──
# A scheduled campaign reaches the fan-out from the scheduler, which never goes
# through the endpoint's check. If somebody's admin rights are taken away
# between the schedule and the send, the campaign must not still go out from
# their account.
demoted = mkuser("demoted@t.co", admin=True, name="Soon Demoted")
target = mkuser("dmt@t.co", name="DM Target Demote", country="Libya")
c = client.post("/admin/announcements", headers=H(owner),
                json=dm_payload(title="Scheduled DM", body="body", sender_id=demoted.id,
                                audience={"status": "active", "country": "Libya"})).json()
DEMID = c["id"]
r = client.post(f"/admin/announcements/{DEMID}/schedule", headers=H(owner),
                json={"scheduled_for": iso_in(hours=2), "confirm_phrase": "GHAWY-OFFICIAL-SEND"})
check("the owner can schedule a DM campaign from another admin", r.status_code == 200,
      f"{r.status_code} {r.text[:120]}")

demoted.is_admin = False                       # rights removed after scheduling
db.commit()
row = db.query(M.Announcement).filter(M.Announcement.id == DEMID).first()
row.scheduled_for = _dt.utcnow() - _td(minutes=1)
db.commit()

asyncio.run(fire_scheduled_announcements())
row = db.query(M.Announcement).filter(M.Announcement.id == DEMID).first(); db.refresh(row)
check("a campaign from an account that is no longer an admin does NOT fire",
      row.status == "failed", row.status)
check("...saying why on the row", bool(row.failure_reason), row.failure_reason)
check("...and sending no message at all",
      db.query(M.Message).filter(M.Message.announcement_id == DEMID).count() == 0)
check("...and leaving the send lock free", AN._send_lock.acquire(blocking=False),
      "lock held after a refused scheduled send")
AN._send_lock.release()


# ══════════════════════════════════════════════════════════════
print("\n=== B · a DM campaign creates one real conversation per member ===")
# ══════════════════════════════════════════════════════════════
dm_a = mkuser("dma@t.co", name="DM Target A", country="Tunisia")
dm_b = mkuser("dmb@t.co", name="DM Target B", country="Tunisia")

c = client.post("/admin/announcements", headers=H(sender),
                json=dm_payload(title="Ahlan", body="Rasala khassa",
                                audience={"status": "active", "country": "Tunisia"})).json()
DMID = c["id"]
check("the campaign records its delivery mode", c["delivery"] == "dm", c["delivery"])

r = send_real(DMID)
check("the DM send is accepted", r.status_code == 200, f"{r.status_code} {r.text[:160]}")
st = wait_sent(DMID)
check("...and finishes at status=sent", st["status"] == "sent", st)

msgs = db.query(M.Message).filter(M.Message.announcement_id == DMID).all()
check("exactly one message per recipient", len(msgs) == 2, len(msgs))
check("...all sent from the chosen account",
      {m.sender_id for m in msgs} == {sender.id}, {m.sender_id for m in msgs})

chans = db.query(M.Channel).filter(M.Channel.id.in_([m.channel_id for m in msgs])).all()
check("one channel per recipient, no duplicates", len({c_.id for c_ in chans}) == 2,
      [c_.name for c_ in chans])
check("...all of them DM channels",
      all(c_.channel_type == M.ChannelType.DM for c_ in chans),
      [c_.channel_type for c_ in chans])
expected_names = {f"dm_{min(sender.id, u.id)}_{max(sender.id, u.id)}" for u in (dm_a, dm_b)}
check("...named by the deterministic rule the rest of chat uses",
      {c_.name for c_ in chans} == expected_names, {c_.name for c_ in chans})

for c_ in chans:
    mems = db.query(M.ChatMember).filter(M.ChatMember.channel_id == c_.id).all()
    check(f"{c_.name} has exactly two members", len(mems) == 2, [m.user_id for m in mems])
    check(f"{c_.name} has the sender as one of them",
          sender.id in {m.user_id for m in mems}, [m.user_id for m in mems])

# The member's own DM list is the thing that has to show it — a channel row in
# the database that the member cannot see is not a delivered message.
r = client.get("/chat/dm/list", headers=H(dm_a))
listed = r.json() if r.status_code == 200 else []
mine_row = next((d for d in listed
                 if (d.get("user") or {}).get("id") == sender.id and d.get("channel_id")), None)
check("the conversation shows up in the member's DM list",
      r.status_code == 200 and mine_row is not None,
      f"{r.status_code} {[(d.get('user') or {}).get('full_name') for d in listed]}")
if mine_row:
    check("...attributed to the account it was sent from",
          (mine_row["user"] or {}).get("full_name") == "Sender", mine_row["user"])
    check("...carrying the campaign text as the last message",
          "Rasala khassa" in (mine_row.get("last_message") or ""), mine_row.get("last_message"))
    check("...and counted as unread for the member",
          mine_row.get("unread_count") == 1, mine_row.get("unread_count"))
    # The member must be able to open it, not merely see it listed.
    rm = client.get(f"/chat/messages?channel={mine_row['channel_name']}", headers=H(dm_a))
    check("...and the member can open it and read the message",
          rm.status_code == 200 and any("Rasala khassa" in (m.get("content") or "")
                                        for m in (rm.json() or [])),
          f"{rm.status_code} {rm.text[:120]}")

# ── running it again must not fork the conversation ──
row = db.query(M.Announcement).filter(M.Announcement.id == DMID).first()
row.status = "failed"                       # pretend the worker died at the end
db.commit()
channels_before = {c_.id for c_ in chans}
r = send_real(DMID)
check("re-running a DM campaign is accepted (resume)", r.status_code == 200,
      f"{r.status_code} {r.text[:160]}")
check("...and reports both recipients already reached", r.json().get("skipped") == 2, r.json())
wait_sent(DMID)
msgs2 = db.query(M.Message).filter(M.Message.announcement_id == DMID).all()
check("re-running sends NO second message", len(msgs2) == 2, len(msgs2))
all_dm_channels = db.query(M.Channel).filter(M.Channel.name.in_(list(expected_names))).all()
check("re-running creates NO second channel for the same pair",
      len(all_dm_channels) == 2 and {c_.id for c_ in all_dm_channels} == channels_before,
      [(c_.id, c_.name) for c_ in all_dm_channels])
for c_ in all_dm_channels:
    mems = db.query(M.ChatMember).filter(M.ChatMember.channel_id == c_.id).all()
    check(f"re-running does not duplicate membership in {c_.name}", len(mems) == 2,
          [m.user_id for m in mems])


# ══════════════════════════════════════════════════════════════
print("\n=== B7 · delivered/read are real numbers in DM mode ===")
# ══════════════════════════════════════════════════════════════
st = client.get(f"/admin/announcements/{DMID}/status", headers=H(sender)).json()
check("the status endpoint counts DM deliveries, not zero", st["delivered"] == 2, st)

d = client.get(f"/admin/announcements/{DMID}", headers=H(sender)).json()
check("a DM campaign reports delivered on the card", d["delivered"] == 2, d["delivered"])
check("...and read starts at zero because nobody opened it", d["read"] == 0, d["read"])

# Reuse the mechanism the chat already has, rather than a second one.
r = client.put(f"/chat/dm/read?channel={chans[0].name}", headers=H(dm_a if
               chans[0].name.endswith(str(max(sender.id, dm_a.id))) else dm_b))
d = client.get(f"/admin/announcements/{DMID}", headers=H(sender)).json()
check("opening the conversation registers as a read", d["read"] == 1, f"read={d['read']} ({r.status_code})")
check("...and the read rate follows", d["read_rate"] == 50, d["read_rate"])

rc = client.get(f"/admin/announcements/{DMID}/recipients?state=all", headers=H(sender)).json()
check("the recipients drawer answers for a DM campaign", rc["delivery"] == "dm", rc)
check("...listing both members", rc["delivered"] == 2 and len(rc["items"]) == 2, rc["total"])
check("...with one of them marked read", rc["read"] == 1 and rc["unread"] == 1, rc)
check("...and naming the members, not the sender",
      {i["user_id"] for i in rc["items"]} == {dm_a.id, dm_b.id},
      {i["user_id"] for i in rc["items"]})
rc = client.get(f"/admin/announcements/{DMID}/recipients?state=unread", headers=H(sender)).json()
check("state=unread narrows to the member who has not opened it",
      rc["total"] == 1 and all(i["is_read"] is False for i in rc["items"]), rc["total"])
rc = client.get(f"/admin/announcements/{DMID}/recipients", headers=H(member))
check("the DM recipients view still needs the permission", rc.status_code == 403, rc.status_code)


# ══════════════════════════════════════════════════════════════
print("\n=== B4 · the account a campaign went out from is told ===")
# ══════════════════════════════════════════════════════════════
def sender_notifs(uid):
    db.expire_all()
    return (db.query(M.Notification)
            .filter(M.Notification.user_id == uid,
                    M.Notification.announcement_id.is_(None),
                    M.Notification.title.like("%حملة اتبعتت من حسابك%"))
            .all())


dm_c = mkuser("dmc@t.co", name="DM Target C", country="Oman")
before = len(sender_notifs(sender2.id))
c = client.post("/admin/announcements", headers=H(owner),
                json=dm_payload(title="From another admin", body="text",
                                sender_id=sender2.id,
                                audience={"status": "active", "country": "Oman"})).json()
r = send_real(c["id"], actor=owner)
check("the owner may send as another admin", r.status_code == 200, f"{r.status_code} {r.text[:160]}")
wait_sent(c["id"])

row = db.query(M.Announcement).filter(M.Announcement.id == c["id"]).first(); db.refresh(row)
check("sender_id records whose account the member saw", row.sender_id == sender2.id, row.sender_id)
check("sent_by records who actually pushed the button", row.sent_by == owner.id, row.sent_by)

after = sender_notifs(sender2.id)
check("the account owner is told a campaign went out from their account",
      len(after) == before + 1, f"{before} -> {len(after)}")
if after:
    note = after[-1]
    check("...the notice says how many members it reached", "1" in (note.body or ""), note.body)
    check("...and that replies land in their DMs", "الرسايل الخاصة" in (note.body or ""), note.body)
    check("...and it does NOT count itself as a campaign delivery",
          note.announcement_id is None, note.announcement_id)
check("the campaign's own delivered count is unpolluted by that notice",
      client.get(f"/admin/announcements/{c['id']}", headers=H(sender)).json()["delivered"] == 1,
      client.get(f"/admin/announcements/{c['id']}", headers=H(sender)).json()["delivered"])

# Sending as YOURSELF must not notify you about your own action.
dm_d = mkuser("dmd@t.co", name="DM Target D", country="Qatar")
before_self = len(sender_notifs(sender.id))
c = client.post("/admin/announcements", headers=H(sender),
                json=dm_payload(title="From me", body="text",
                                audience={"status": "active", "country": "Qatar"})).json()
send_real(c["id"])
wait_sent(c["id"])
check("sending as yourself does not notify you about yourself",
      len(sender_notifs(sender.id)) == before_self, len(sender_notifs(sender.id)))
row = db.query(M.Announcement).filter(M.Announcement.id == c["id"]).first(); db.refresh(row)
check("...but both fields are still stored",
      row.sender_id == sender.id and row.sent_by == sender.id, (row.sender_id, row.sent_by))


# ══════════════════════════════════════════════════════════════
print("\n=== B6 · the test send shows what a member will actually see ===")
# ══════════════════════════════════════════════════════════════
c = client.post("/admin/announcements", headers=H(owner),
                json=dm_payload(title="Test DM", body="body of the test",
                                sender_id=sender2.id,
                                audience={"status": "all"})).json()
r = client.post(f"/admin/announcements/{c['id']}/send", headers=H(owner), json={"mode": "test"})
d = r.json()
check("a DM test send is accepted", r.status_code == 200, f"{r.status_code} {r.text[:140]}")
check("...and lands as a real DM, not a bell notification", d.get("delivery") == "dm", d)
tm = db.query(M.Message).filter(M.Message.announcement_id == c["id"]).all()
check("...one message, from the chosen sender",
      len(tm) == 1 and tm[0].sender_id == sender2.id, [(m.sender_id, m.channel_id) for m in tm])
tch = db.query(M.Channel).filter(M.Channel.id == tm[0].channel_id).first()
check("...in the conversation between the sender and the operator",
      tch.name == f"dm_{min(sender2.id, owner.id)}_{max(sender2.id, owner.id)}", tch.name)
check("...and it goes to the operator alone", db.query(M.Message)
      .filter(M.Message.announcement_id == c["id"]).count() == 1)

# When the operator IS the sender there is no such conversation to have; say so
# rather than inventing a thread with yourself.
c = client.post("/admin/announcements", headers=H(sender),
                json=dm_payload(title="Self test", body="b", audience={"status": "all"})).json()
r = client.post(f"/admin/announcements/{c['id']}/send", headers=H(sender), json={"mode": "test"})
d = r.json()
check("testing a DM campaign you are the sender of still works",
      r.status_code == 200, f"{r.status_code} {r.text[:140]}")
check("...falling back to the bell", d.get("delivery") == "bell", d)
check("...and saying so plainly instead of silently changing surface",
      "المرسِل" in (d.get("message") or ""), d.get("message"))
check("...and creating no self-conversation",
      db.query(M.Channel).filter(M.Channel.name == f"dm_{sender.id}_{sender.id}").count() == 0)
check("...and no DM message", db.query(M.Message)
      .filter(M.Message.announcement_id == c["id"]).count() == 0)


# ══════════════════════════════════════════════════════════════
print("\n=== B · bell campaigns are untouched by any of this ===")
# ══════════════════════════════════════════════════════════════
bell_user = mkuser("bellonly@t.co", name="Bell Only", country="Kuwait")
c = mkcampaign(audience={"status": "active", "country": "Kuwait"})
check("a campaign created without a delivery mode defaults to bell",
      c["delivery"] == "bell", c["delivery"])
check("...and has no sender account", c["sender_id"] is None, c["sender_id"])
send_real(c["id"])
st = wait_sent(c["id"])
check("a bell campaign still delivers as a notification", st["status"] == "sent", st)
check("...writing notification rows", notif_count(c["id"]) == 1, notif_count(c["id"]))
check("...and no chat messages at all",
      db.query(M.Message).filter(M.Message.announcement_id == c["id"]).count() == 0)
check("...and its stats still read from notifications",
      client.get(f"/admin/announcements/{c['id']}", headers=H(sender)).json()["delivered"] == 1)


# ══════════════════════════════════════════════════════════════
print("\n=== A4 · saved audience segments ===")
# ══════════════════════════════════════════════════════════════
r = client.post("/admin/announcements/segments", headers=H(sender),
                json={"name": "Active Egypt", "filters": {"status": "active", "country": "Egypt",
                                                          "user_ids": [faraway.id]}})
check("a segment can be saved", r.status_code == 201, f"{r.status_code} {r.text[:120]}")
seg = r.json()
check("...storing the filter, not a member list",
      "user_ids" not in seg["filters"] and seg["filters"]["country"] == "Egypt", seg["filters"])

r = client.post("/admin/announcements/segments", headers=H(sender),
                json={"name": "Active Egypt", "filters": {"status": "inactive"}})
check("saving the same name updates rather than duplicating",
      r.status_code == 201 and r.json()["id"] == seg["id"], f"{r.status_code} {r.text[:120]}")
check("...with the new filter", r.json()["filters"]["status"] == "inactive", r.json()["filters"])

r = client.post("/admin/announcements/segments", headers=H(sender), json={"name": "  "})
check("a nameless segment is refused", r.status_code == 400, r.status_code)

r = client.get("/admin/announcements/segments", headers=H(member))
check("segments need the announcements permission", r.status_code == 403, r.status_code)
r = client.get("/admin/announcements/segments")
check("segments refuse anonymous", r.status_code == 401, r.status_code)

# Deleting a segment must not disturb a campaign built from it.
built = mkcampaign(audience={"status": "active", "country": "Egypt"})
r = client.delete(f"/admin/announcements/segments/{seg['id']}", headers=H(sender))
check("a segment can be deleted", r.status_code == 204, r.status_code)
row = db.query(M.Announcement).filter(M.Announcement.id == built["id"]).first(); db.refresh(row)
check("...and the campaign built from it keeps its own copy of the filter",
      "Egypt" in (row.audience or ""), row.audience)
check("...and is still there", row.status == "draft", row.status)
r = client.delete(f"/admin/announcements/segments/{seg['id']}", headers=H(sender))
check("deleting a segment that is gone is a clean 404", r.status_code == 404, r.status_code)

print("\n" + "=" * 72)
print(f"passed {len(PASS)}   failed {len(FAIL)}")
for f in FAIL:
    print("  FAILED: " + f)
print("=" * 72)
raise SystemExit(1 if FAIL else 0)
