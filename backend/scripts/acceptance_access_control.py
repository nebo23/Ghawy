"""Phase 3 acceptance: access-control findings and their fixes.

Reproduces each Phase 3 finding against a throwaway database and asserts the
behaviour that the fix must produce. Run it before the fix to watch the
FAIL lines describe the vulnerability, and after to watch them pass.

    DATABASE_URL=postgresql://user:pw@host:5432/ghawy_test \
        python backend/scripts/acceptance_access_control.py
"""
import json
import os

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


def mkuser(email, active=True, admin=False, owner=False, name="Test User"):
    u = M.User(email=email, hashed_password=bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode(),
               full_name=name, is_active=active, is_admin=admin, is_owner=owner,
               is_verified=True)
    db.add(u); db.commit(); db.refresh(u)
    return u


alice   = mkuser("alice@t.co",   name="Alice")
bob     = mkuser("bob@t.co",     name="Bob")
mallory = mkuser("mallory@t.co", name="Mallory")     # ordinary paying member
freebie = mkuser("free@t.co", active=False, name="Freebie")
owner   = mkuser("owner@t.co", admin=True, owner=True, name="Owner")
staff   = mkuser("staff@t.co", admin=True, name="Staff")   # announcements permission below

from app.services.permissions import dump_permissions     # noqa: E402
staff.staff_permissions = dump_permissions(["announcements"])
db.commit()

from app.routers.users import issue_token_for, create_file_token   # noqa: E402


def H(u):
    db.refresh(u)
    return {"Authorization": "Bearer " + issue_token_for(u)}


client = TestClient(main.app, raise_server_exceptions=False)

# ── Fixtures: a private DM between Alice and Bob, with an attachment ────────
dm = M.Channel(name="dm-alice-bob", channel_type=M.ChannelType.DM)
db.add(dm); db.commit(); db.refresh(dm)
db.add_all([
    M.ChatMember(channel_id=dm.id, user_id=alice.id),
    M.ChatMember(channel_id=dm.id, user_id=bob.id),
])
db.commit()

secret_msg = M.Message(channel_id=dm.id, sender_id=alice.id,
                       content="ALICE_PRIVATE_SECRET")
db.add(secret_msg); db.commit()

course = M.Course(title="Course A", description="d", is_published=True, total_lessons=1)
db.add(course); db.commit(); db.refresh(course)
lesson = M.Lesson(course_id=course.id, title="L1", order=1, video_status="ready",
                  duration_minutes=0, bunny_video_url="https://bunny/x.m3u8")
db.add(lesson); db.commit(); db.refresh(lesson)


print("\n=== F-A: GET /api/live-sessions must not serve members-only content anonymously ===")
r = client.get("/api/live-sessions")
check("anon /api/live-sessions is not a 200 data dump", r.status_code != 200, f"{r.status_code} {r.text[:120]}")

print("\n=== F-B: lesson duration is writable only by a caller entitled to watch ===")
# The decision: the player is the only thing that knows a video's real length,
# and course-detail.html PATCHes this from three places, so the write stays with
# the player rather than moving behind PERM_COURSES. What changes is who counts
# as "the player" — an entitled watcher, not any registered account.
r = client.patch(f"/courses/{course.id}/lessons/{lesson.id}/duration?duration_seconds=600",
                 headers=H(freebie))
check("an account that may not watch cannot write lesson duration",
      r.status_code in (401, 402, 403), f"{r.status_code} {r.text[:120]}")
r = client.get(f"/courses/{course.id}/lessons", headers=H(freebie))
check("...and the duration really is still unset", '"duration_minutes":0' in r.text.replace(" ", "")
      or r.status_code != 200, r.text[:200])

r = client.patch(f"/courses/{course.id}/lessons/{lesson.id}/duration?duration_seconds=600",
                 headers=H(mallory))
check("a member watching the lesson may still report its duration (the feature)",
      r.status_code == 200, f"{r.status_code} {r.text[:120]}")

# The "only if zero" rule still holds, so a second caller cannot rewrite it.
r = client.patch(f"/courses/{course.id}/lessons/{lesson.id}/duration?duration_seconds=99999",
                 headers=H(alice))
check("an already-set duration cannot be overwritten",
      r.status_code == 200 and (r.json() or {}).get("duration_minutes") == 10,
      f"{r.status_code} {r.text[:120]}")

# An anonymous caller has no business here at all.
r = client.patch(f"/courses/{course.id}/lessons/{lesson.id}/duration?duration_seconds=600")
check("anonymous cannot write lesson duration", r.status_code == 401,
      f"{r.status_code} {r.text[:120]}")

print("\n=== F-C: a member must not be able to join, read or post into someone else's DM ===")
r = client.post(f"/chat/channels/{dm.id}/join", headers=H(mallory))
check("outsider cannot join a DM channel", r.status_code in (403, 404),
      f"{r.status_code} {r.text[:120]}")

r = client.get(f"/chat/channels/{dm.id}/messages", headers=H(mallory))
leaked = "ALICE_PRIVATE_SECRET" in r.text
check("outsider cannot read the DM history", r.status_code == 404 and not leaked,
      f"{r.status_code} leaked={leaked} {r.text[:160]}")

r = client.post(f"/chat/channels/{dm.id}/messages", headers=H(mallory),
                json={"content": "MALLORY_WAS_HERE"})
check("outsider cannot post into the DM", r.status_code in (403, 404),
      f"{r.status_code} {r.text[:120]}")

# The participants must be unaffected by the fix.
r = client.get(f"/chat/channels/{dm.id}/messages", headers=H(alice))
check("participant still reads their own DM", r.status_code == 200 and "ALICE_PRIVATE_SECRET" in r.text,
      f"{r.status_code} {r.text[:160]}")

# Community channels must still auto-join — that is the product.
grp = M.Channel(name="general", channel_type=M.ChannelType.GROUP)
db.add(grp); db.commit(); db.refresh(grp)
r = client.post(f"/chat/channels/{grp.id}/join", headers=H(mallory))
check("member can still join an open community channel", r.status_code == 200,
      f"{r.status_code} {r.text[:120]}")
r = client.get(f"/chat/channels/{grp.id}/messages", headers=H(mallory))
check("member can still read an open community channel", r.status_code == 200,
      f"{r.status_code} {r.text[:120]}")

print("\n=== F-D: announcement links must be internal paths only ===")
for payload in ["//evil.example", "/\\evil.example", "java\tscript:alert(1)"]:
    r = client.post("/admin/announcements", headers=H(staff),
                    json={"title": "t", "body": "b", "link": payload})
    stored = (r.json() or {}).get("link") if r.status_code == 201 else None
    rejected = r.status_code == 400
    safe = rejected or (isinstance(stored, str) and stored.startswith("/") and not stored.startswith("//")
                        and "\\" not in stored and ":" not in stored)
    check(f"link {payload!r} cannot escape the origin", safe,
          f"status={r.status_code} stored={stored!r}")

r = client.post("/admin/announcements", headers=H(staff),
                json={"title": "t", "body": "b", "link": "/dashboard.html"})
check("a genuine internal link is still accepted",
      r.status_code == 201 and (r.json() or {}).get("link") == "/dashboard.html",
      f"{r.status_code} {r.text[:160]}")

print("\n=== F-E: the file cookie must honour the token_version kill switch ===")
stale_file_cookie = create_file_token(alice.id)
alice.token_version = (alice.token_version or 0) + 1      # what /logout-all does
db.commit()
r = client.get("/files/receipts/whatever.jpg", cookies={"ghawy_files": stale_file_cookie})
check("a file cookie minted before logout-all is refused", r.status_code == 401,
      f"{r.status_code} {r.text[:120]}")

db.refresh(alice)
fresh_file_cookie = create_file_token(alice.id, alice.token_version or 0)
r = client.get("/files/receipts/whatever.jpg", cookies={"ghawy_files": fresh_file_cookie})
check("a file cookie minted after the bump still works (404 = past auth, no such file)",
      r.status_code == 404, f"{r.status_code} {r.text[:120]}")

# The session token is still accepted as a file credential; the OAuth hand-off
# token, which is not a session, must not be.
r = client.get("/files/receipts/whatever.jpg", headers=H(alice))
check("a session bearer token still opens files", r.status_code == 404,
      f"{r.status_code} {r.text[:120]}")

from app.routers.users import create_handoff_token          # noqa: E402
r = client.get("/files/receipts/whatever.jpg",
               headers={"Authorization": "Bearer " + create_handoff_token(alice.id)})
check("the 120-second OAuth hand-off token is not a file credential",
      r.status_code == 401, f"{r.status_code} {r.text[:120]}")

print("\n" + "=" * 72)
print(f"passed {len(PASS)}   failed {len(FAIL)}")
for f in FAIL:
    print("  FAILED: " + f)
print("=" * 72)
raise SystemExit(1 if FAIL else 0)
