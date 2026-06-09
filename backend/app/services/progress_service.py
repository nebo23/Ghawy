from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from app.models import Lesson, UserProgress, User, Certificate
from datetime import datetime
import uuid

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

    if not existing:
        progress = UserProgress(
            user_id=user_id,
            lesson_id=lesson_id,
            course_id=course_id
        )
        db.add(progress)
        db.commit()

    # 2. Calculate Progress
    total_lessons = db.query(Lesson).filter(Lesson.course_id == course_id).count()
    completed_lessons = db.query(UserProgress).filter(
        UserProgress.user_id == user_id,
        UserProgress.course_id == course_id
    ).count()

    percentage = round((completed_lessons / total_lessons) * 100) if total_lessons > 0 else 0

    certificate_url = None
    if percentage == 100:
        cert = issue_certificate(user_id, course_id, db)
        certificate_url = cert.certificate_id

    # 3. Return formatting required by Frontend JS
    return {
        "completed": True,
        "course_progress": {
            "completed_lessons": completed_lessons,
            "total_lessons": total_lessons,
            "percentage": percentage,
            "is_completed": percentage == 100,
            "certificate_id": certificate_url
        }
    }

def get_top_students_for_course(course_id: int, current_user_id: int, db: Session, limit: int = 30):
    total_lessons = db.query(Lesson).filter(Lesson.course_id == course_id).count()

    top_students_query = db.query(
        User.id.label("user_id"),
        User.full_name,
        User.avatar_url,
        func.count(UserProgress.id).label("completed_count")
    ).join(
        UserProgress, User.id == UserProgress.user_id
    ).filter(
        UserProgress.course_id == course_id
    ).group_by(
        User.id
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
            "is_completed": student.completed_count == total_lessons if total_lessons > 0 else False,
            "is_current_user": student.user_id == current_user_id
        })

    return {
        "top_students": result,
        "total_lessons": total_lessons
    }
