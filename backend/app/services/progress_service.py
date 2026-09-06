from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from app.models import Lesson, UserProgress, User, Certificate
from datetime import datetime, timedelta
import uuid
import logging
import threading

logger = logging.getLogger(__name__)


def _send_email_bg(fn, *args) -> None:
    """SMTP بطيء وممكن يجمّد الـ event loop — بنبعت في thread منفصل fire-and-forget.
    الـ thread بياخد قيم بسيطة بس (مفيش DB session) عشان يفضل thread-safe."""
    def _run():
        try:
            fn(*args)
        except Exception as exc:
            logger.warning("Lifecycle email failed: %s", exc)
    threading.Thread(target=_run, daemon=True).start()


def _maybe_send_lifecycle_emails(db: Session, user_id: int, course_id: int,
                                 percentage: int, newly_completed: bool) -> None:
    """يبعت إيميل 'خلصت أول درس' و/أو 'الشهادة جاهزة' — كل واحد مرة واحدة بس.
    بنحدّد الـ flag ونعمله commit الأول (ضد التكرار) وبعدين نبعت في الخلفية."""
    from app.services.email_service import send_first_lesson_email, send_course_completed_email
    from app.models import Course

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.email:
        return

    # #1 — أول درس يخلصه المستخدم في حياته (عبر أي كورس)
    if newly_completed and user.first_lesson_email_sent_at is None:
        total_done = db.query(UserProgress).filter(UserProgress.user_id == user_id).count()
        if total_done == 1:
            user.first_lesson_email_sent_at = datetime.utcnow()
            db.commit()
            _send_email_bg(send_first_lesson_email, user.email, user.full_name, course_id)

    # #2 — الكورس وصل 100% (guard على صف الشهادة نفسه = مرة واحدة لكل كورس)
    if percentage == 100:
        cert = db.query(Certificate).filter_by(user_id=user_id, course_id=course_id).first()
        if cert and cert.completion_email_sent_at is None:
            cert.completion_email_sent_at = datetime.utcnow()
            db.commit()
            course = db.query(Course).filter(Course.id == course_id).first()
            course_name = (course.title if course else None) or "الكورس"
            _send_email_bg(send_course_completed_email, user.email, user.full_name, course_name, course_id)


def calculate_video_streak(user_id: int, db: Session) -> int:
    """
    Auto-calculate the user's "days streak" from video watching.

    Each UserProgress row records that the user watched/completed a lesson
    video (its `completed_at` timestamp is the video-watch event we use).
    Calendar days are evaluated in server UTC (consistent for all users).

    Rules:
      - One distinct UTC day with >= 1 watched video counts as 1 day.
      - Walk backwards from today: if today has a watch, start from today;
        if today has none but yesterday does, the streak is still alive and
        we start from yesterday.
      - Stop at the first day with no watch event (any gap resets it).
      - If the most recent watch was 2+ days ago, the streak is 0.
    """
    rows = (
        db.query(func.date(UserProgress.completed_at))
        .filter(
            UserProgress.user_id == user_id,
            UserProgress.completed_at.isnot(None),
        )
        .distinct()
        .all()
    )

    watched_days = set()
    for (day,) in rows:
        if day is None:
            continue
        if isinstance(day, str):
            watched_days.add(datetime.strptime(day, "%Y-%m-%d").date())
        elif isinstance(day, datetime):
            watched_days.add(day.date())
        else:
            watched_days.add(day)

    if not watched_days:
        return 0

    today = datetime.utcnow().date()
    if today in watched_days:
        cursor = today
    elif (today - timedelta(days=1)) in watched_days:
        cursor = today - timedelta(days=1)
    else:
        return 0

    streak = 0
    while cursor in watched_days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak

def member_course_progress(db: Session, user_id: int, course_id: int) -> dict:
    """كام درس خلّص العضو ده في الكورس ده، وبكام في المية. القراءة الوحيدة.

    المقام من `effective_lesson_totals` — القاعدة الوحيدة لعدد الدروس. والبسط
    من **نفس الفرع بالظبط**: كورس مقامه اتحسب بالدروس الـ ready، بسطه كمان
    بالـ ready. ده هو بيت القصيد: الحتة دي كانت متكتوبة تلات مرات، والتالتة —
    اللي في `mark_lesson_complete` — كانت بتعدّ **كل** الدروس. يعني على كورس
    فيه درس مش ready، العضو يشوف ١٠٠٪ وياخد زرار الشهادة، والباك إند يحسب
    ٧١٪ فما يعملش صف Certificate خالص. زي ما دوكسترنج `effective_lesson_totals`
    بتقول: القاعدة اتكتبت مرتين قبل كده وده اللي حصل.

    بيفلتر على `Lesson.course_id` كمان مش على `UserProgress.course_id` بس، عشان
    صف تايه ما يخليش البسط أكبر من المقام — ده كان طريق تاني لنفس العطل: نسبة
    فوق المية مابتساويش ١٠٠ فمكانتش بتصدر شهادة برضه.
    """
    totals, ready_counts = effective_lesson_totals(db, [course_id])
    total = totals.get(course_id) or 0

    q = (db.query(UserProgress.lesson_id)
           .join(Lesson, Lesson.id == UserProgress.lesson_id)
           .filter(UserProgress.user_id == user_id,
                   UserProgress.course_id == course_id,
                   Lesson.course_id == course_id))
    if ready_counts.get(course_id):
        q = q.filter(Lesson.video_status == "ready")

    completed_ids = [row[0] for row in q.all()]
    percentage = round(len(completed_ids) * 100 / total) if total > 0 else 0
    return {
        "completed_lesson_ids": completed_ids,
        "completed_lessons": len(completed_ids),
        "total_lessons": total,
        "percentage": percentage,
        "is_completed": percentage >= 100,
    }


def issue_certificate(user_id: int, course_id: int, db: Session):
    cert = db.query(Certificate).filter_by(user_id=user_id, course_id=course_id).first()
    if not cert:
        cert_id = f"GHAWY-{datetime.utcnow().year}-{uuid.uuid4().hex[:6].upper()}"
        cert = Certificate(user_id=user_id, course_id=course_id, certificate_id=cert_id)
        db.add(cert)
        db.commit()
        db.refresh(cert)
    return cert

def mark_lesson_complete(course_id: int, lesson_id: int, user_id: int, db: Session):
    lesson = db.query(Lesson).filter(
        Lesson.id == lesson_id,
        Lesson.course_id == course_id
    ).first()
    
    if not lesson:
        raise HTTPException(404, "Lesson not found")

    # 1. Prevent Duplicates
    existing = db.query(UserProgress).filter_by(
        user_id=user_id,
        lesson_id=lesson_id,
        course_id=course_id
    ).first()

    newly_completed = not existing
    if newly_completed:
        progress = UserProgress(
            user_id=user_id,
            lesson_id=lesson_id,
            course_id=course_id
        )
        db.add(progress)
        db.commit()

    # 2. Calculate Progress — نفس الدالة اللي بتردّ على صفحة الكورس، مش حساب تاني
    prog = member_course_progress(db, user_id, course_id)
    total_lessons = prog["total_lessons"]
    completed_lessons = prog["completed_lessons"]
    percentage = prog["percentage"]

    certificate_url = None
    if prog["is_completed"]:
        cert = issue_certificate(user_id, course_id, db)
        certificate_url = cert.certificate_id

    # 2b. Automated lifecycle emails — never let a mail issue break completion
    try:
        _maybe_send_lifecycle_emails(db, user_id, course_id, percentage, newly_completed)
    except Exception:
        logger.exception("Lifecycle email trigger failed for user=%s course=%s", user_id, course_id)

    # 3. Return formatting required by Frontend JS
    return {
        "completed": True,
        "course_progress": {
            "completed_lessons": completed_lessons,
            "total_lessons": total_lessons,
            "percentage": percentage,
            "is_completed": prog["is_completed"],
            "certificate_id": certificate_url
        }
    }

def get_top_students_for_course(course_id: int, current_user_id: int, db: Session, limit: int = 30):
    # نفس المقام اللي العضو شايفه في صفحته. كان بيعدّ كل الدروس هنا، فالكورس
    # اللي فيه درس مش ready كان بيدّي اللوحة نسبة تانية غير اللي الطالب قاراها
    # على نفسه — ونفس الفرع لازم يمشي على البسط كمان.
    totals, ready_counts = effective_lesson_totals(db, [course_id])
    total_lessons = totals.get(course_id) or 0

    q = db.query(
        User.id.label("user_id"),
        User.full_name,
        User.avatar_url,
        func.count(UserProgress.id).label("completed_count")
    ).join(
        UserProgress, User.id == UserProgress.user_id
    ).join(
        Lesson, Lesson.id == UserProgress.lesson_id
    ).filter(
        UserProgress.course_id == course_id,
        Lesson.course_id == course_id,
    )
    if ready_counts.get(course_id):
        q = q.filter(Lesson.video_status == "ready")

    top_students_query = q.group_by(
        User.id, User.full_name, User.avatar_url
    ).order_by(
        func.count(UserProgress.id).desc()
    ).limit(limit).all()

    result = []
    current_rank = 1
    previous_score = None
    
    for idx, student in enumerate(top_students_query):
        score = student.completed_count
        if previous_score is not None and score < previous_score:
            current_rank = idx + 1
        previous_score = score
        
        result.append({
            "rank": current_rank,
            "user_id": student.user_id,
            "full_name": student.full_name,
            "avatar_url": student.avatar_url,
            "completed_lessons": student.completed_count,
            "total_lessons": total_lessons,
            "is_completed": student.completed_count >= total_lessons if total_lessons > 0 else False,
            "is_current_user": student.user_id == current_user_id
        })

    return {
        "top_students": result,
        "total_lessons": total_lessons
    }


def effective_lesson_totals(db: Session, course_ids):
    """كام درس بيتحسب في كل كورس — القاعدة الوحيدة اللي كل حاجة بتقيس بيها.

    القاعدة: الدروس الـ 'ready' بس، ولو الكورس مفيهوش ولا درس ready نحسب كل
    دروسه. دي بالظبط قاعدة courses.get_course_progress، وكانت متكتوبة تاني مرة
    في admin.students_progress — نسختين لنفس الرقم يعني نسبة الطالب في صفحته
    ممكن تختلف عن نسبته في لوحة الفريق. بقت هنا عشان تفضل جملة واحدة.

    بيرجّع (totals, ready_counts): `totals` هو المقام لكل كورس، و`ready_counts`
    بتقول أي كورس اتحسب بالـ ready عشان اللي بيحسب المكتمل يستخدم نفس الفرع.
    استعلامين GROUP BY وخلاص — مفيش استعلام لكل كورس.
    """
    all_counts = dict(
        db.query(Lesson.course_id, func.count(Lesson.id))
        .group_by(Lesson.course_id).all()
    )
    ready_counts = dict(
        db.query(Lesson.course_id, func.count(Lesson.id))
        .filter(Lesson.video_status == "ready")
        .group_by(Lesson.course_id).all()
    )
    totals = {cid: (ready_counts.get(cid) or all_counts.get(cid, 0)) for cid in course_ids}
    return totals, ready_counts
