from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func as sql_func
from starlette.concurrency import run_in_threadpool
from typing import List, Optional
from app.database import get_db, SessionLocal
from app.models import (
    User, Course, Lesson, UserProgress, Certificate, CourseReview,
    LessonPlaybackGrant,
)
from app.routers.users import get_current_user, get_current_user_optional, get_current_active_member, get_current_admin_user, require_perm
from app.schemas import (
    CourseOut, CourseDetailOut, CourseCreate, CourseUpdate, CourseReorder,
    PublicCourseOut, PublicCourseDetailOut,
    LessonCreate, AdminLessonCreate, LessonUpdate, LessonOut,
    UserCourseProgressOut, CourseProgressUpdate,
)
import logging
import threading
import time
import uuid
import os
import json
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
# صلاحية تاب الكورسات (المحتوى) — الـ owner بيعدّي دايماً
PERM_COURSES = require_perm("courses")

router = APIRouter(prefix="/courses", tags=["Courses"])

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# ═══════════════════════════════════════════════════════════════
#  PUBLIC / USER ENDPOINTS
# ═══════════════════════════════════════════════════════════════

def _can_watch(user: Optional[User], lesson: Lesson) -> bool:
    """The single rule for "may this caller have this lesson's video and PDF".

    Free previews are open to everyone including anonymous visitors; everything
    else needs an active subscription. Every endpoint that hands out
    vdo_video_id / bunny_video_url / pdf_url asks this function — a second,
    separately-worded copy of the rule is how the catalogue endpoint ended up
    giving the whole library away.
    """
    if lesson.is_free_preview:
        return True
    return bool(user is not None and user.is_active)


def _uploads_path_for(stored_url: str) -> Optional[Path]:
    """The on-disk file behind a stored upload URL, or None if it is not one.

    Accepts both prefixes, since /uploads/ rows predate authorized delivery. The
    result is resolved and must still be inside UPLOADS_DIR — a stored value is
    not automatically a safe path just because we wrote it once.
    """
    url = (stored_url or "").split("#", 1)[0].split("?", 1)[0]
    for prefix in ("/files/", "/uploads/"):
        if url.startswith(prefix):
            relative = url[len(prefix):]
            break
    else:
        return None
    if not relative or ".." in relative:
        return None
    candidate = (UPLOADS_DIR / relative).resolve()
    if not candidate.is_relative_to(UPLOADS_DIR.resolve()):
        return None
    return candidate


def _record_playback(db: Session, user_id: int, lesson_id: int) -> None:
    """Note that this member opened this lesson's video. Never fatal."""
    from app.models import LessonPlaybackGrant
    try:
        grant = db.query(LessonPlaybackGrant).filter_by(
            user_id=user_id, lesson_id=lesson_id
        ).first()
        if grant:
            grant.last_played_at = datetime.utcnow()
        else:
            db.add(LessonPlaybackGrant(user_id=user_id, lesson_id=lesson_id))
        db.commit()
    except Exception:
        # Playback must never fail because bookkeeping did.
        db.rollback()
        logger.warning("could not record playback for user=%s lesson=%s",
                       user_id, lesson_id, exc_info=True)


def _has_playback(db: Session, user_id: int, lesson_id: int) -> bool:
    from app.models import LessonPlaybackGrant
    return db.query(LessonPlaybackGrant.id).filter_by(
        user_id=user_id, lesson_id=lesson_id
    ).first() is not None


def _public_lesson(lesson: Lesson) -> dict:
    """A lesson as the anonymous catalogue sees it: everything but the goods."""
    return {
        "id": lesson.id,
        "course_id": lesson.course_id,
        "title": lesson.title,
        "description": lesson.description,
        "section_title": lesson.section_title,
        "section_order": lesson.section_order or 0,
        "order": lesson.order,
        "duration_minutes": lesson.duration_minutes,
        "video_status": lesson.video_status,
        "is_free_preview": bool(lesson.is_free_preview),
        "is_project": bool(lesson.is_project),
        "has_video": bool(lesson.bunny_video_url or lesson.vdo_video_id),
        "has_pdf": lesson.pdf_url is not None,
    }


def _public_course(course: Course) -> dict:
    return {
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "thumbnail_url": course.thumbnail_url,
        "certificate_url": course.certificate_url,
        "total_lessons": course.total_lessons,
        "course_time": course.course_time,
        "is_published": course.is_published,
        "sort_order": course.sort_order or 0,
        "created_at": course.created_at,
    }


@router.get("", response_model=List[PublicCourseOut])
def get_courses(
    db: Session = Depends(get_db),
    limit: int = Query(1000),
    offset: int = Query(0)
):
    """The published course list. Public — the marketing site renders it.

    PublicCourseOut is the response model precisely so course-level pdf_url
    cannot ride along: this endpoint needs no token, so anything it returns is
    world-readable.
    """
    return db.query(Course)\
        .filter(Course.is_published == True)\
        .order_by(Course.sort_order.asc(), Course.id.asc())\
        .limit(limit)\
        .offset(offset)\
        .all()

# ─── Member: progress across every course, in ONE request ────
#
# Both endpoints below are registered BEFORE "/{course_id}" on purpose: a path
# that starts with a literal segment has to be declared before the wildcard
# that could swallow it, or "/courses/stats" becomes course_id="stats".

@router.get("/progress/summary")
def get_progress_summary(
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """The caller's progress in every course, in one round trip.

    The members' courses page used to call GET /courses/{id}/progress once per
    course inside a loop — N+1 requests before it could so much as sort the
    cards by progress, and every one of them a session checkout. This is the
    same numbers from seven grouped queries — a fixed cost that does not grow
    with the number of courses.

    The percentage is computed by exactly the rule get_course_progress uses
    (progress_service.effective_lesson_totals): count only 'ready' lessons, and
    fall back to every lesson for a course that has none ready. Anything else
    and a member would read one number on the card and a different one after
    opening the course.

    Every course is returned, not only the published ones: a course can be
    unpublished while a member still holds progress in it, and the caller can
    only ever see their own rows here.
    """
    from app.services.progress_service import effective_lesson_totals

    course_ids = [cid for (cid,) in db.query(Course.id).all()]
    totals, ready_counts = effective_lesson_totals(db, course_ids)

    # Completed lessons per course for THIS member — the ready-only tally and
    # the all-lessons tally, one grouped query each. Which one a course uses is
    # the same branch effective_lesson_totals took for its denominator.
    ready_done = dict(
        db.query(UserProgress.course_id, sql_func.count(UserProgress.id))
        .join(Lesson, Lesson.id == UserProgress.lesson_id)
        .filter(UserProgress.user_id == current_user.id, Lesson.video_status == "ready")
        .group_by(UserProgress.course_id).all()
    )
    all_done = dict(
        db.query(UserProgress.course_id, sql_func.count(UserProgress.id))
        .filter(UserProgress.user_id == current_user.id)
        .group_by(UserProgress.course_id).all()
    )
    # "Last opened this course". NOT from user_course_progress.last_accessed,
    # which is the column that sounds exactly right and is empty: nothing in
    # this codebase has ever inserted a user_course_progress row (grep it), so
    # reading it would hand every member a null. The two tables that do record
    # the member touching a course are lesson_playback_grants (they opened a
    # video) and user_progress (they finished a lesson); the later of the two
    # is the answer.
    played = dict(
        db.query(Lesson.course_id, sql_func.max(LessonPlaybackGrant.last_played_at))
        .select_from(LessonPlaybackGrant)
        .join(Lesson, Lesson.id == LessonPlaybackGrant.lesson_id)
        .filter(LessonPlaybackGrant.user_id == current_user.id)
        .group_by(Lesson.course_id).all()
    )
    finished = dict(
        db.query(UserProgress.course_id, sql_func.max(UserProgress.completed_at))
        .filter(UserProgress.user_id == current_user.id)
        .group_by(UserProgress.course_id).all()
    )

    out = []
    for cid in course_ids:
        total = totals.get(cid, 0)
        done = ready_done.get(cid, 0) if ready_counts.get(cid) else all_done.get(cid, 0)
        percentage = round((done / total) * 100) if total > 0 else 0
        out.append({
            "course_id": cid,
            "completed_lessons": done,
            "total_lessons": total,
            "percentage": percentage,
            "is_completed": percentage == 100,
            "last_accessed": max(
                [t for t in (played.get(cid), finished.get(cid)) if t is not None],
                default=None,
            ),
        })
    return out


# ─── Member: aggregate course statistics ─────────────────────
#
# Cached in-process for a minute. These numbers drive the "Most watched" and
# "Most engaged" sorts on the courses page — nobody is watching them tick, and
# an uncached endpoint that runs five GROUP BYs on every page load is the shape
# of request that took the site down on 2026-07-21. Same design as
# stats.public_stats: async handler, single-flight refresh in a worker thread
# with its own short-lived session, stale value served to everyone else.

COURSE_STATS_TTL_SECONDS = 60

_stats_lock = threading.Lock()
_course_stats = None        # last computed list (None until the first refresh)
_course_stats_at = 0.0      # time.monotonic() of that computation
_course_stats_refreshing = False


def _compute_course_stats() -> List[dict]:
    """Runs in a worker thread. Own session, closed immediately.

    engagement_score answers "how much does the average learner actually do
    with this course", on a 0..1 scale, from three normalised parts:

        0.5 * depth       lessons_completed / learners / total_lessons
                          — the share of the course the average learner has
                            finished
        0.3 * completion  completions / learners
                          — the share of learners who reached the end
        0.2 * rating      avg_rating / 5

    Each part is a ratio in 0..1, so the weights mean what they say. The raw
    lessons-per-learner figure is deliberately divided by the course length:
    left unnormalised, a long course would outrank a short, loved, finished one
    on lesson count alone. A course nobody has opened scores 0 rather than
    dividing by zero.

    The formula lives here and only here so "most engaged" means one thing —
    the frontend sorts on the number, it does not compute it.
    """
    db = SessionLocal()
    try:
        courses = db.query(Course).filter(Course.is_published == True).all()  # noqa: E712
        course_ids = [c.id for c in courses]
        if not course_ids:
            return []

        from app.services.progress_service import effective_lesson_totals
        totals, _ready = effective_lesson_totals(db, course_ids)

        # `learners` = distinct members who have actually touched the course.
        #
        # The obvious source is user_course_progress — one row per (member,
        # course), with a last_accessed on it. It is empty. Nothing in this
        # codebase writes to that table; it is read in three places and
        # populated in none, so sourcing "Most watched" from it would have
        # ranked every course zero and the sort would have looked broken rather
        # than absent.
        #
        # So: opened a lesson's video (lesson_playback_grants) OR completed a
        # lesson (user_progress). UNION dedupes a member who did both, and the
        # count is one grouped pass over the result.
        watched = (
            db.query(UserProgress.course_id.label("cid"),
                     UserProgress.user_id.label("uid"))
            .union(
                db.query(Lesson.course_id.label("cid"),
                         LessonPlaybackGrant.user_id.label("uid"))
                .select_from(LessonPlaybackGrant)
                .join(Lesson, Lesson.id == LessonPlaybackGrant.lesson_id)
            )
            .subquery()
        )
        learners = dict(
            db.query(watched.c.cid, sql_func.count(sql_func.distinct(watched.c.uid)))
            .group_by(watched.c.cid).all()
        )
        lessons_done = dict(
            db.query(UserProgress.course_id, sql_func.count(UserProgress.id))
            .group_by(UserProgress.course_id).all()
        )
        completions = dict(
            db.query(Certificate.course_id, sql_func.count(Certificate.id))
            .group_by(Certificate.course_id).all()
        )
        reviews = {
            cid: (count, float(avg or 0))
            for cid, count, avg in db.query(
                CourseReview.course_id,
                sql_func.count(CourseReview.id),
                sql_func.avg(CourseReview.rating),
            ).group_by(CourseReview.course_id).all()
        }

        rows = []
        for cid in course_ids:
            n_learners = learners.get(cid, 0)
            n_lessons = lessons_done.get(cid, 0)
            n_done = completions.get(cid, 0)
            n_reviews, avg_rating = reviews.get(cid, (0, 0.0))
            total_lessons = totals.get(cid, 0)

            if n_learners and total_lessons:
                depth = min(1.0, (n_lessons / n_learners) / total_lessons)
                completion_rate = min(1.0, n_done / n_learners)
            else:
                depth = completion_rate = 0.0
            score = 0.5 * depth + 0.3 * completion_rate + 0.2 * (avg_rating / 5.0)

            rows.append({
                "course_id": cid,
                "learners": n_learners,
                "completions": n_done,
                "lessons_completed": n_lessons,
                "reviews_count": n_reviews,
                "avg_rating": round(avg_rating, 2),
                "engagement_score": round(score, 4),
            })
        return rows
    finally:
        db.close()


@router.get("/stats")
async def get_course_stats(current_user: User = Depends(get_current_active_member)):
    """Aggregate numbers per published course — counts only, never a name.

    Members only, because it describes how the community uses the library. It
    carries nothing personal: no user ids, no names, no per-member rows — just
    how many people, how many lessons, how many certificates, and the average
    rating, all of them sums over the whole membership.
    """
    global _course_stats, _course_stats_at, _course_stats_refreshing

    with _stats_lock:
        cached = _course_stats
        fresh = cached is not None and (time.monotonic() - _course_stats_at) < COURSE_STATS_TTL_SECONDS
        should_refresh = not fresh and not _course_stats_refreshing
        if should_refresh:
            _course_stats_refreshing = True

    if not should_refresh:
        # Fresh, or somebody else is already refreshing — serve what we have.
        # `cached` is None only in the first concurrent burst after boot, and
        # the page treats a missing row as "no stats yet" rather than zero.
        return cached if cached is not None else []

    try:
        rows = await run_in_threadpool(_compute_course_stats)
    except Exception:
        logger.exception("Course stats refresh failed")
        with _stats_lock:
            _course_stats_refreshing = False
        # Never fail the courses page over a sort key.
        return cached if cached is not None else []

    with _stats_lock:
        _course_stats = rows
        _course_stats_at = time.monotonic()
        _course_stats_refreshing = False

    return rows


@router.get("/{course_id}", response_model=None)
def get_course_detail(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """One course with its curriculum. Public, so it carries no playable media.

    Video ids and PDF URLs appear only for a caller who may actually watch the
    lesson (_can_watch). The player and the Resources tab read them from
    GET /courses/{id}/lessons instead, which requires a token.
    """
    course = db.query(Course)\
        .options(joinedload(Course.lessons))\
        .filter(Course.id == course_id, Course.is_published == True)\
        .first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    out = _public_course(course)
    if current_user is not None and current_user.is_active and course.pdf_url:
        out["pdf_url"] = course.pdf_url

    lessons = []
    for lesson in course.lessons:  # relationship is already order_by=Lesson.order
        if lesson.video_status != "ready":
            continue
        row = _public_lesson(lesson)
        if _can_watch(current_user, lesson):
            # Only name a field we are actually handing over, so a response can
            # never advertise "vdo_video_id" for a lesson it withheld.
            for key, value in (("bunny_video_url", lesson.bunny_video_url),
                               ("vdo_video_id", lesson.vdo_video_id),
                               ("pdf_url", lesson.pdf_url)):
                if value:
                    row[key] = value
        lessons.append(row)
    out["lessons"] = lessons
    return out

def issue_certificate(user_id: int, course_id: int, db: Session):
    from app.services.progress_service import issue_certificate as issue_cert
    return issue_cert(user_id, course_id, db)

@router.patch("/{course_id}/lessons/{lesson_id}/duration")
async def update_lesson_duration(
    course_id: int,
    lesson_id: int,
    duration_seconds: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    """Called by the frontend player to save real video duration to DB.

    The player is the only thing that knows a video's true length, so the write
    stays where it is rather than moving behind PERM_COURSES — but it is a write
    to global course content, and it took get_current_user, so *any* registered
    account (including one that never paid) could set the advertised duration of
    any lesson in any course. The "only if zero" test below is a race, not an
    authorization check: it decides whether to write, never who may.

    So the caller must now be someone actually entitled to watch this lesson —
    the same rule, via the same function, that decides whether they may have its
    video at all. A member reporting the length of a video they are watching is
    the intended use; anyone else is not.
    """
    lesson = db.query(Lesson).filter(
        Lesson.id == lesson_id,
        Lesson.course_id == course_id
    ).first()
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    if not _can_watch(current_user, lesson):
        raise HTTPException(403, "Subscription required to watch this lesson")
    # Only update if currently 0 to avoid overwriting manually-set durations
    if lesson.duration_minutes == 0 and duration_seconds > 0:
        lesson.duration_minutes = max(1, round(duration_seconds / 60))
        db.commit()
    return {"duration_minutes": lesson.duration_minutes}

@router.post("/{course_id}/lessons/{lesson_id}/complete")
async def mark_lesson_complete(
    course_id: int,
    lesson_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    """Mark a lesson complete. Requires a paid membership and, for a VdoCipher
    lesson, evidence that the member actually opened the video.

    This took get_current_user and recorded completion on request alone, so a
    free registered account could loop POSTs to 100% and mint a certificate for
    a course it had never opened.
    """
    lesson = db.query(Lesson).filter(
        Lesson.id == lesson_id,
        Lesson.course_id == course_id,
    ).first()
    if not lesson:
        raise HTTPException(404, "Lesson not found")

    if lesson.vdo_video_id and not _has_playback(db, current_user.id, lesson.id):
        # Bunny-hosted and text lessons are exempt because the server sees no
        # playback event for them at all — one more reason to finish moving
        # those to VdoCipher.
        raise HTTPException(
            status_code=409,
            detail="افتح الدرس واتفرج عليه الأول قبل ما تعلّمه كمكتمل",
        )

    logger.info("lesson complete | user_id=%s course_id=%s lesson_id=%s",
                current_user.id, course_id, lesson_id)
    from app.services.progress_service import mark_lesson_complete
    return mark_lesson_complete(course_id, lesson_id, current_user.id, db)

@router.delete("/{course_id}/lessons/{lesson_id}/complete")
async def unmark_lesson_complete(
    course_id: int,
    lesson_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    db.query(UserProgress).filter_by(
        user_id=current_user.id,
        lesson_id=lesson_id
    ).delete()
    db.commit()
    return {"completed": False}

@router.get("/{course_id}/top-students")
async def get_top_students(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.services.progress_service import get_top_students_for_course
    return get_top_students_for_course(course_id, current_user.id, db)

@router.get("/{course_id}/progress")
async def get_course_progress(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # بنحسب بس الـ lessons الـ ready، لو ما فيش ready نحسب كل الـ lessons
    ready_lesson_ids_rows = db.query(Lesson.id).filter(
        Lesson.course_id == course_id,
        Lesson.video_status == "ready"
    ).all()
    ready_ids_set = {r.id for r in ready_lesson_ids_rows}

    if ready_ids_set:
        total = len(ready_ids_set)
        completed_rows = db.query(UserProgress).filter(
            UserProgress.user_id == current_user.id,
            UserProgress.course_id == course_id,
            UserProgress.lesson_id.in_(ready_ids_set)
        ).all()
    else:
        # Fallback: كل الـ lessons
        total = db.query(Lesson).filter(Lesson.course_id == course_id).count()
        completed_rows = db.query(UserProgress).filter(
            UserProgress.user_id == current_user.id,
            UserProgress.course_id == course_id
        ).all()
    completed_ids = [r.lesson_id for r in completed_rows]
    percentage = round((len(completed_ids) / total) * 100) if total > 0 else 0

    cert = db.query(Certificate).filter_by(
        user_id=current_user.id,
        course_id=course_id
    ).first()

    return {
        "completed_lesson_ids": completed_ids,
        "completed_lessons": len(completed_ids),
        "total_lessons": total,
        "percentage": percentage,
        "is_completed": percentage == 100,
        "certificate_id": cert.certificate_id if cert else None
    }

# ═══════════════════════════════════════════════════════════════
#  ADMIN ENDPOINTS
# ═══════════════════════════════════════════════════════════════

# ─── Admin: List ALL courses (including unpublished) ─────────
@router.get("/admin/all", response_model=List[CourseOut])
# ─── Admin: List ALL courses ─────────────────────────────────
@router.get("/admin/courses", response_model=List[CourseOut])
def admin_list_courses(admin: User = Depends(PERM_COURSES), db: Session = Depends(get_db)):
    return db.query(Course).order_by(Course.sort_order.asc(), Course.id.asc()).all()

# ─── Admin: Reorder courses ──────────────────────────────────
# NOTE: declared BEFORE "/admin/courses/{course_id}" so the literal
# path "reorder" is not captured as an int course_id.
@router.patch("/admin/courses/reorder")
def reorder_courses(data: CourseReorder, admin: User = Depends(PERM_COURSES), db: Session = Depends(get_db)):
    """Set each course's sort_order to its position in the provided ID list."""
    for index, course_id in enumerate(data.order):
        db.query(Course).filter(Course.id == course_id).update(
            {Course.sort_order: index}, synchronize_session=False
        )
    db.commit()
    return {"message": "Course order updated", "count": len(data.order)}

# ─── Admin: Create course ────────────────────────────────────
@router.post("/admin/courses", response_model=CourseOut, status_code=201)
def create_course(data: CourseCreate, admin: User = Depends(PERM_COURSES), db: Session = Depends(get_db)):
    course = Course(
        title=data.title,
        description=data.description,
        thumbnail_url=data.thumbnail_url,
        pdf_url=data.pdf_url,
        total_lessons=data.total_lessons,
        course_time=data.course_time,
        is_published=data.is_published
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course

# ─── Admin: Update course ────────────────────────────────────
@router.patch("/admin/courses/{course_id}", response_model=CourseOut)
def update_course(course_id: int, data: CourseUpdate, admin: User = Depends(PERM_COURSES), db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(course, field, value)
    db.commit()
    db.refresh(course)
    return course

# ─── Admin: Delete course ────────────────────────────────────
@router.delete("/admin/courses/{course_id}", status_code=204)
def delete_course(course_id: int, admin: User = Depends(PERM_COURSES), db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    db.delete(course)
    db.commit()
    return None

# ─── Admin: Upload course PDF (direct file upload) ──────────
@router.post("/admin/courses/{course_id}/upload-pdf")
async def upload_course_pdf(
    course_id: int,
    file: UploadFile = File(...),
    admin: User = Depends(PERM_COURSES),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Save file
    pdf_dir = UPLOADS_DIR / "course-pdfs"
    pdf_dir.mkdir(exist_ok=True)
    safe_name = f"course_{course_id}_{uuid.uuid4().hex[:8]}.pdf"
    file_path = pdf_dir / safe_name
    
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Update course record
    new_url = f"/files/course-pdfs/{safe_name}"
    
    import json
    current_resources = []
    if course.pdf_url:
        try:
            current_resources = json.loads(course.pdf_url)
        except:
            current_resources = [{"name": "Resource", "url": course.pdf_url}]
            
    current_resources.append({"name": file.filename, "url": new_url})
    course.pdf_url = json.dumps(current_resources)
    
    db.commit()
    db.refresh(course)
    
    return {"pdf_url": course.pdf_url, "message": "PDF uploaded successfully"}

# ─── Admin: Upload course thumbnail (direct file upload) ─────
@router.post("/admin/courses/{course_id}/upload-thumbnail")
async def upload_course_thumbnail(
    course_id: int,
    file: UploadFile = File(...),
    admin: User = Depends(PERM_COURSES),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    allowed = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Only image files are allowed ({', '.join(allowed)})")

    # Save file
    thumb_dir = UPLOADS_DIR / "course-thumbnails"
    thumb_dir.mkdir(exist_ok=True)
    safe_name = f"course_{course_id}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = thumb_dir / safe_name
    
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Update course record
    course.thumbnail_url = f"/uploads/course-thumbnails/{safe_name}"
    db.commit()
    db.refresh(course)
    
    return {"thumbnail_url": course.thumbnail_url, "message": "Thumbnail uploaded successfully"}

# ─── Admin: Upload course certificate template ───────────────
@router.post("/admin/{course_id}/certificate")
async def upload_course_certificate(
    course_id: int,
    file: UploadFile = File(...),
    admin: User = Depends(PERM_COURSES),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    allowed = ('.jpg', '.jpeg', '.png', '.webp')
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Only image files are allowed ({', '.join(allowed)})")

    cert_dir = UPLOADS_DIR / "course-certificates"
    cert_dir.mkdir(exist_ok=True)
    safe_name = f"course_{course_id}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = cert_dir / safe_name

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    course.certificate_url = f"/files/course-certificates/{safe_name}"
    db.commit()
    db.refresh(course)

    return {"certificate_url": course.certificate_url, "message": "Certificate template uploaded successfully"}


@router.delete("/admin/{course_id}/certificate")
def delete_course_certificate(
    course_id: int,
    admin: User = Depends(PERM_COURSES),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    course.certificate_url = None
    db.commit()
    return {"message": "Certificate template removed"}

# ─── Admin: Get lessons for a course ───────────────────────
@router.get("/admin/{course_id}/lessons", response_model=List[LessonOut])
def admin_get_lessons(
    course_id: int,
    admin: User = Depends(PERM_COURSES),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    lessons = db.query(Lesson).filter(Lesson.course_id == course_id).order_by(Lesson.order).all()
    return lessons

# ─── Admin: Create lesson ─────────────────────────────────
@router.post("/admin/{course_id}/lessons", status_code=201)
def admin_create_lesson(
    course_id: int,
    data: AdminLessonCreate,
    admin: User = Depends(PERM_COURSES),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    duration_minutes = data.duration_minutes
    if data.bunny_video_url and not duration_minutes:
        from app.services.bunny_stream import get_video_duration_minutes
        duration_minutes = get_video_duration_minutes(data.bunny_video_url)

    lesson = Lesson(
        course_id=course_id,
        title=data.title,
        section_title=data.section_title,
        order=data.order,
        duration_minutes=duration_minutes,
        bunny_video_url=data.bunny_video_url,
        vdo_video_id=data.vdo_video_id,
        video_status="ready" if (data.bunny_video_url or data.vdo_video_id) else "pending",
        is_project=data.is_project,
    )
    db.add(lesson)

    # Update course total_lessons count
    course.total_lessons = len(course.lessons) + 1
    db.commit()
    db.refresh(lesson)

    return {
        "lesson_id": lesson.id,
        "lesson": {
            "id": lesson.id,
            "title": lesson.title,
            "order": lesson.order,
            "duration_minutes": lesson.duration_minutes,
            "section_title": lesson.section_title,
            "video_status": lesson.video_status,
        }
    }

# ─── Admin: Update lesson metadata ──────────────────────────
@router.patch("/admin/lessons/{lesson_id}", response_model=LessonOut)
def admin_update_lesson(
    lesson_id: int,
    data: LessonUpdate,
    admin: User = Depends(PERM_COURSES),
    db: Session = Depends(get_db)
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    update_data = data.model_dump(exclude_unset=True)
    if "bunny_video_url" in update_data and update_data["bunny_video_url"] != lesson.bunny_video_url:
        from app.services.bunny_stream import get_video_duration_minutes
        new_duration = get_video_duration_minutes(update_data["bunny_video_url"])
        if new_duration > 0 or update_data.get("duration_minutes", 0) == 0:
            update_data["duration_minutes"] = new_duration

    # Auto-set video_status to ready if a video is being added
    if "vdo_video_id" in update_data and update_data["vdo_video_id"]:
        if "video_status" not in update_data:
            update_data["video_status"] = "ready"
    elif "bunny_video_url" in update_data and update_data["bunny_video_url"]:
        if "video_status" not in update_data:
            update_data["video_status"] = "ready"

    for field, value in update_data.items():
        setattr(lesson, field, value)
    db.commit()
    db.refresh(lesson)
    return lesson

# ─── Admin: Upload PDF — supports multiple PDFs per lesson ────
@router.post("/admin/lessons/{lesson_id}/pdfs")
async def admin_upload_pdf(
    lesson_id: int,
    file: UploadFile = File(...),
    admin: User = Depends(PERM_COURSES),
    db: Session = Depends(get_db)
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Save file
    pdf_dir = UPLOADS_DIR / "lesson-pdfs"
    pdf_dir.mkdir(exist_ok=True)
    safe_name = f"lesson_{lesson_id}_{uuid.uuid4().hex[:8]}.pdf"
    file_path = pdf_dir / safe_name

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    new_url = f"/files/lesson-pdfs/{safe_name}"
    original_name = file.filename

    # Parse existing pdf_url as list
    try:
        existing = json.loads(lesson.pdf_url) if lesson.pdf_url else []
        if not isinstance(existing, list):
            # Migrate legacy single string
            existing = [{"name": "Resource", "url": lesson.pdf_url}]
    except Exception:
        existing = []

    existing.append({"name": original_name, "url": new_url})
    lesson.pdf_url = json.dumps(existing)
    db.commit()
    db.refresh(lesson)

    return {"pdf_url": new_url, "name": original_name, "all_pdfs": existing, "message": "PDF uploaded successfully"}


# ─── Admin: Delete a single PDF from lesson ───────────────────
@router.delete("/admin/lessons/{lesson_id}/pdfs")
def admin_delete_lesson_pdf(
    lesson_id: int,
    pdf_url: str,
    admin: User = Depends(PERM_COURSES),
    db: Session = Depends(get_db)
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    try:
        existing = json.loads(lesson.pdf_url) if lesson.pdf_url else []
        if not isinstance(existing, list):
            existing = [{"name": "Resource", "url": lesson.pdf_url}]
    except Exception:
        existing = []

    # Only a URL this lesson actually lists may be deleted. pdf_url is a raw
    # query parameter, and the old code did UPLOADS_DIR.parent / it.lstrip("/")
    # and unlinked the result — so "../../anything" escaped the uploads tree and
    # deleted arbitrary files. Matching against the stored list first means the
    # parameter selects an entry rather than describing a path.
    match = next((p for p in existing if p.get("url") == pdf_url), None)
    if match is None:
        raise HTTPException(status_code=404, detail="PDF not attached to this lesson")

    existing = [p for p in existing if p.get("url") != pdf_url]
    lesson.pdf_url = json.dumps(existing) if existing else None
    db.commit()

    # Delete file from disk — resolved, and refused if it lands outside uploads.
    try:
        stored_url = match.get("url") or ""
        file_path = _uploads_path_for(stored_url)
        if file_path and file_path.exists():
            file_path.unlink()
    except Exception:
        logger.warning("could not remove PDF file for lesson %s", lesson_id, exc_info=True)

    return {"message": "PDF deleted", "all_pdfs": existing}

# ─── Admin: Delete lesson + CF video ─────────────────────────
@router.delete("/admin/lessons/{lesson_id}", status_code=204)
def admin_delete_lesson(
    lesson_id: int,
    admin: User = Depends(PERM_COURSES),
    db: Session = Depends(get_db)
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    course = lesson.course
    db.delete(lesson)
    # Update course total_lessons count
    if course:
        course.total_lessons = max(0, course.total_lessons - 1)
    db.commit()
    return None

# ─── Admin: Poll video processing status ────────────────────
@router.get("/admin/lessons/{lesson_id}/status")
def admin_lesson_status(
    lesson_id: int,
    admin: User = Depends(PERM_COURSES),
    db: Session = Depends(get_db)
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    return {"status": lesson.video_status}

@router.patch("/{course_id}/lessons/{lesson_id}", dependencies=[Depends(PERM_COURSES)])
async def update_lesson(course_id: int, lesson_id: int, data: LessonUpdate, db: Session = Depends(get_db)):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id, Lesson.course_id == course_id).first()
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    if data.bunny_video_url:
        valid_patterns = ["iframe.mediadelivery.net", "mediadelivery.net", "b-cdn.net"]
        if not any(p in data.bunny_video_url for p in valid_patterns):
            raise HTTPException(400, "Invalid Bunny.net URL. Must be from mediadelivery.net or b-cdn.net")
    update_data = data.model_dump(exclude_unset=True)
    if "bunny_video_url" in update_data and update_data["bunny_video_url"] != lesson.bunny_video_url:
        from app.services.bunny_stream import get_video_duration_minutes
        from fastapi.concurrency import run_in_threadpool
        # sync requests call (up to 10s) — keep it off the event loop
        new_duration = await run_in_threadpool(get_video_duration_minutes, update_data["bunny_video_url"])
        if new_duration > 0 or update_data.get("duration_minutes", 0) == 0:
            update_data["duration_minutes"] = new_duration

    # Auto-set video_status to ready if a video is being added
    if "vdo_video_id" in update_data and update_data["vdo_video_id"]:
        if "video_status" not in update_data:
            update_data["video_status"] = "ready"
    elif "bunny_video_url" in update_data and update_data["bunny_video_url"]:
        if "video_status" not in update_data:
            update_data["video_status"] = "ready"

    for field, value in update_data.items():
        setattr(lesson, field, value)
    db.commit()
    db.refresh(lesson)
    return lesson

@router.post("/{course_id}/lessons", dependencies=[Depends(PERM_COURSES)])
async def create_lesson(course_id: int, data: LessonCreate, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(404, "Course not found")
    lesson_data = data.model_dump()
    if lesson_data.get("bunny_video_url") and not lesson_data.get("duration_minutes"):
        from app.services.bunny_stream import get_video_duration_minutes
        from fastapi.concurrency import run_in_threadpool
        # sync requests call (up to 10s) — keep it off the event loop
        lesson_data["duration_minutes"] = await run_in_threadpool(get_video_duration_minutes, lesson_data["bunny_video_url"])

    lesson = Lesson(course_id=course_id, **lesson_data)
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return lesson

@router.get("/{course_id}/lessons")
async def get_lessons(course_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lessons = db.query(Lesson).filter(
        Lesson.course_id == course_id,
        Lesson.video_status == "ready"
    ).order_by(Lesson.order).all()
    completed_ids = [
        r.lesson_id for r in db.query(UserProgress).filter_by(
            user_id=current_user.id, course_id=course_id
        ).all()
    ]
    result = []
    for lesson in lessons:
        can_watch = _can_watch(current_user, lesson)
        result.append({
            "id": lesson.id,
            "title": lesson.title,
            "description": lesson.description,
            "duration_minutes": lesson.duration_minutes,
            "order": lesson.order,
            "is_free_preview": lesson.is_free_preview,
            "has_pdf": lesson.pdf_url is not None,
            "has_video": (lesson.bunny_video_url is not None or lesson.vdo_video_id is not None),
            "bunny_video_url": lesson.bunny_video_url if can_watch else None,
            "vdo_video_id": lesson.vdo_video_id if can_watch else None,
            "pdf_url": lesson.pdf_url if can_watch else None,
            "is_completed": lesson.id in completed_ids,
        })
    return result

# ─── VdoCipher OTP ────────────────────────────────────────────
@router.get("/{course_id}/lessons/{lesson_id}/vdo-otp")
async def get_vdo_otp(
    course_id: int,
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a VdoCipher OTP for secure video playback. Only accessible to active members."""
    lesson = db.query(Lesson).filter(
        Lesson.id == lesson_id,
        Lesson.course_id == course_id
    ).first()
    if not lesson:
        raise HTTPException(404, "Lesson not found")

    # Check access: must be active member or free preview
    if not (current_user.is_active or lesson.is_free_preview):
        raise HTTPException(403, "Subscription required to watch this lesson")

    if not lesson.vdo_video_id:
        raise HTTPException(404, "No VdoCipher video associated with this lesson")

    # The one playback event the server actually witnesses. Recorded before the
    # OTP goes out, so completion can later ask "did this member ever open this
    # video?" instead of taking a POST's word for it.
    _record_playback(db, current_user.id, lesson.id)

    from app.services.vdocipher import generate_otp
    from fastapi.concurrency import run_in_threadpool
    try:
        # generate_otp does a blocking requests.post (up to 10s) — run it in a
        # thread so it can't freeze the single-worker event loop
        otp_data = await run_in_threadpool(
            generate_otp,
            video_id=lesson.vdo_video_id,
            user_id=current_user.id,
            user_name=current_user.full_name,
        )
    except ValueError as e:
        raise HTTPException(500, str(e))

    return otp_data

from pydantic import BaseModel
class ReviewCreate(BaseModel):
    rating: int
    comment: str = ""

@router.get("/{course_id}/reviews")
async def get_course_reviews(course_id: int, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(404, "Course not found")
        
    reviews = db.query(CourseReview).filter(CourseReview.course_id == course_id).order_by(CourseReview.created_at.desc()).all()
    
    result = []
    for r in reviews:
        result.append({
            "id": r.id,
            "rating": r.rating,
            "comment": r.comment,
            "date": r.created_at.isoformat() + "Z",
            "user": {
                "id": r.user.id,
                "full_name": r.user.full_name,
                "avatar_url": r.user.avatar_url
            }
        })
    return result

@router.post("/{course_id}/reviews")
async def create_course_review(
    course_id: int, 
    data: ReviewCreate, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(404, "Course not found")
        
    existing = db.query(CourseReview).filter_by(course_id=course_id, user_id=current_user.id).first()
    if existing:
        existing.rating = data.rating
        existing.comment = data.comment
        db.commit()
        return {"message": "Review updated"}
    
    review = CourseReview(
        course_id=course_id,
        user_id=current_user.id,
        rating=data.rating,
        comment=data.comment
    )
    db.add(review)
    db.commit()
    return {"message": "Review added"}

@router.delete("/{course_id}/reviews/{review_id}", dependencies=[Depends(PERM_COURSES)])
async def delete_course_review(course_id: int, review_id: int, db: Session = Depends(get_db)):
    review = db.query(CourseReview).filter(CourseReview.id == review_id, CourseReview.course_id == course_id).first()
    if not review:
        raise HTTPException(404, "Review not found")
    
    db.delete(review)
    db.commit()
    return {"message": "Review deleted successfully"}

