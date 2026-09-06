"""Acceptance checks for certificate issuing — the three-denominator bug.

    DATABASE_URL=postgresql://...:5432/ghawy_scratch \
        python backend/scripts/acceptance_certificates.py

The bug this pins down: the page told the member 100% using ready lessons only,
while `mark_lesson_complete` decided the certificate using EVERY lesson. On a
course carrying one unready lesson the member saw 100%, got the download button,
and no `Certificate` row was ever written — so the browser invented an ID and
drew it onto the PNG, and the completion email (guarded on that same row) never
went either.

It cannot be reproduced against production: every lesson there is `ready` today,
so the two rules happen to agree and the bug is dormant rather than fixed. That
is exactly why this script builds the course the bug needs.
"""
import os, sys
os.environ.setdefault("SECRET_KEY", "dummy_secret_for_import_check")

from _acceptance_guard import require_scratch_database  # noqa: E402
require_scratch_database()

import main  # noqa: F401  (imported for the same app wiring the others use)
from app.database import SessionLocal, engine
from app.models import Base
from app import models as M
from app.services import progress_service as PS

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name + (("  -> " + str(detail)) if (detail and not cond) else ""))

from sqlalchemy import text as _text
with engine.begin() as _c:
    _c.execute(_text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
Base.metadata.create_all(bind=engine)
db = SessionLocal()

PS._maybe_send_lifecycle_emails = lambda *a, **k: None   # no SMTP in a test

def mkuser(email):
    u = M.User(email=email, full_name="محمد صلاح", first_name="محمد", last_name="صلاح",
               hashed_password="x", is_verified=True, is_active=True)
    db.add(u); db.commit(); db.refresh(u); return u

def mkcourse(title, ready, unready=0):
    c = M.Course(title=title, description="", is_published=True)
    db.add(c); db.commit(); db.refresh(c)
    ls = []
    for i in range(ready):
        l = M.Lesson(course_id=c.id, title=f"ready {i}", video_status="ready")
        db.add(l); ls.append(l)
    for i in range(unready):
        l = M.Lesson(course_id=c.id, title=f"pending {i}", video_status="processing")
        db.add(l); ls.append(l)
    db.commit()
    for l in ls: db.refresh(l)
    return c, [l for l in ls if l.video_status == "ready"], [l for l in ls if l.video_status != "ready"]

print("\n── The course the bug needs: 5 ready lessons, 2 not ready ───────")

u = mkuser("finisher@t.co")
course, ready, pending = mkcourse("AI For Thumbnail Design", ready=5, unready=2)

last = None
for l in ready:
    last = PS.mark_lesson_complete(course.id, l.id, u.id, db)

seen = PS.member_course_progress(db, u.id, course.id)
check("[C1] the member sees 100% (ready lessons are the denominator)",
      seen["percentage"] == 100 and seen["total_lessons"] == 5, seen)
check("[C2] the completion payload agrees with the page — one rule, not two",
      last["course_progress"]["percentage"] == seen["percentage"]
      and last["course_progress"]["is_completed"] is True, last["course_progress"])

# What the rule that used to issue certificates would have said, on this exact
# fixture. Kept as an assertion rather than a comment so the gap it describes
# cannot quietly come back: if someone re-points the issuer at every lesson,
# [C3] fails and this line says why.
_old_total = db.query(M.Lesson).filter(M.Lesson.course_id == course.id).count()
_old_done = db.query(M.UserProgress).filter(
    M.UserProgress.user_id == u.id, M.UserProgress.course_id == course.id).count()
_old_pct = round(_old_done * 100 / _old_total)
check("[C2b] the OLD all-lessons rule really does disagree here (5/7 = 71%)",
      _old_total == 7 and _old_pct == 71 and _old_pct != seen["percentage"],
      (_old_done, _old_total, _old_pct))

cert = db.query(M.Certificate).filter_by(user_id=u.id, course_id=course.id).first()
check("[C3] a real Certificate row exists", cert is not None)
check("[C4] …with a server-issued ID, not an invented one",
      bool(cert) and cert.certificate_id.startswith("GHAWY-"),
      cert.certificate_id if cert else None)
check("[C5] the endpoint hands that ID back, so the browser never has to invent",
      last["course_progress"]["certificate_id"] == (cert.certificate_id if cert else None),
      last["course_progress"]["certificate_id"])

print("\n── The other way to the same broken state: counting over 100 ────")

u2 = mkuser("straggler@t.co")
course2, ready2, _ = mkcourse("Two Lesson Course", ready=2)
for l in ready2:
    PS.mark_lesson_complete(course2.id, l.id, u2.id, db)
# a row pointing at another course's lesson but tagged with this course_id —
# the shape that used to push completed above total and so never equal 100
stray = M.UserProgress(user_id=u2.id, lesson_id=ready[0].id, course_id=course2.id)
db.add(stray); db.commit()
p2 = PS.member_course_progress(db, u2.id, course2.id)
check("[C6] a stray progress row cannot push the count past the denominator",
      p2["completed_lessons"] == 2 and p2["percentage"] == 100, p2)

print("\n── An unfinished course issues nothing ──────────────────────────")

u3 = mkuser("partial@t.co")
course3, ready3, _ = mkcourse("Half Done", ready=4)
PS.mark_lesson_complete(course3.id, ready3[0].id, u3.id, db)
p3 = PS.member_course_progress(db, u3.id, course3.id)
check("[C7] 1 of 4 is 25% and no certificate",
      p3["percentage"] == 25 and not p3["is_completed"]
      and db.query(M.Certificate).filter_by(user_id=u3.id, course_id=course3.id).first() is None, p3)

print("\n── A course with no ready lesson at all falls back to every lesson ──")

u4 = mkuser("nothingready@t.co")
course4, _, pend4 = mkcourse("All Pending", ready=0, unready=3)
for l in pend4:
    PS.mark_lesson_complete(course4.id, l.id, u4.id, db)
p4 = PS.member_course_progress(db, u4.id, course4.id)
c4 = db.query(M.Certificate).filter_by(user_id=u4.id, course_id=course4.id).first()
check("[C8] all three count, member reaches 100%, certificate issued",
      p4["total_lessons"] == 3 and p4["percentage"] == 100 and c4 is not None, p4)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:"); [print("   -", f) for f in FAIL]
sys.exit(1 if FAIL else 0)
