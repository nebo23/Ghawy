from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, Course, Lesson, UserCourseProgress, UserProgress, Certificate
from app.routers.users import get_current_user, get_current_active_member, get_current_admin_user
from app.schemas import (
    CourseOut, CourseDetailOut, CourseCreate, CourseUpdate,
    LessonCreate, AdminLessonCreate, LessonUpdate, LessonOut,
    UserCourseProgressOut, CourseProgressUpdate,
)
import logging
import uuid
import os
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/courses", tags=["Courses"])

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# ═══════════════════════════════════════════════════════════════
#  PUBLIC / USER ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("", response_model=List[CourseOut])
def list_courses(db: Session = Depends(get_db)):
    return db.query(Course).filter(Course.is_published == True).all()

@router.get("/{course_id}", response_model=CourseDetailOut)
def get_course_detail(course_id: int, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id, Course.is_published == True).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Use Pydantic to serialize the course first, then filter lessons
    out = CourseDetailOut.model_validate(course)
    out.lessons = [l for l in out.lessons if l.video_status == "ready"]
    return out

def issue_certificate(user_id: int, course_id: int, db: Session):
    cert = db.query(Certificate).filter_by(user_id=user_id, course_id=course_id).first()
    if not cert:
        from datetime import datetime
        import uuid
        cert_id = f"GHAWY-{datetime.utcnow().year}-{uuid.uuid4().hex[:6].upper()}"
        cert = Certificate(user_id=user_id, course_id=course_id, certificate_id=cert_id)
        db.add(cert)
        db.commit()
        db.refresh(cert)
    return cert

@router.patch("/{course_id}/lessons/{lesson_id}/complete")
async def mark_lesson_complete(
    course_id: int,
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # تأكد إن الدرس موجود في الكورس
    lesson = db.query(Lesson).filter(
        Lesson.id == lesson_id,
        Lesson.course_id == course_id
    ).first()
    if not lesson:
        raise HTTPException(404, "Lesson not found")

    # إضافة progress لو مش موجود
    existing = db.query(UserProgress).filter_by(
        user_id=current_user.id,
        lesson_id=lesson_id
    ).first()

    if not existing:
        progress = UserProgress(
            user_id=current_user.id,
            lesson_id=lesson_id,
            course_id=course_id
        )
        db.add(progress)
        db.commit()

    # حساب الـ progress
    total = db.query(Lesson).filter(Lesson.course_id == course_id).count()
    completed = db.query(UserProgress).filter_by(
        user_id=current_user.id,
        course_id=course_id
    ).count()
    percentage = round((completed / total) * 100) if total > 0 else 0

    # لو اكتمل 100% → issue certificate
    certificate_url = None
    if percentage == 100:
        cert = issue_certificate(current_user.id, course_id, db)
        certificate_url = cert.certificate_id

    return {
        "completed": True,
        "course_progress": {
            "completed_lessons": completed,
            "total_lessons": total,
            "percentage": percentage,
            "is_completed": percentage == 100,
            "certificate_id": certificate_url
        }
    }

@router.delete("/{course_id}/lessons/{lesson_id}/complete")
async def unmark_lesson_complete(
    course_id: int,
    lesson_id: int,
    current_user: User = Depends(get_current_user),
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
    total_lessons = db.query(Lesson).filter(
        Lesson.course_id == course_id
    ).count()

    # أكتر الطلاب إتمامًا
    from sqlalchemy import func
    top = db.query(
        UserProgress.user_id,
        func.count(UserProgress.id).label("completed_count")
    ).filter(
        UserProgress.course_id == course_id
    ).group_by(
        UserProgress.user_id
    ).order_by(
        func.count(UserProgress.id).desc()
    ).limit(10).all()

    result = []
    for rank, (user_id, count) in enumerate(top, 1):
        user = db.query(User).filter(User.id == user_id).first()
        result.append({
            "rank": rank,
            "user_id": user_id,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "completed_lessons": count,
            "total_lessons": total_lessons,
            "is_completed": count == total_lessons,
            "is_current_user": user_id == current_user.id
        })

    return {
        "top_students": result,
        "total_lessons": total_lessons
    }

@router.get("/{course_id}/progress")
async def get_course_progress(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    total = db.query(Lesson).filter(Lesson.course_id == course_id).count()
    completed_rows = db.query(UserProgress).filter_by(
        user_id=current_user.id,
        course_id=course_id
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
def admin_list_courses(admin: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    return db.query(Course).order_by(Course.created_at.desc()).all()

# ─── Admin: Create course ────────────────────────────────────
@router.post("/admin/courses", response_model=CourseOut, status_code=201)
def create_course(data: CourseCreate, admin: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    course = Course(
        title=data.title,
        description=data.description,
        thumbnail_url=data.thumbnail_url,
        pdf_url=data.pdf_url,
        total_lessons=data.total_lessons,
        is_published=data.is_published
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course

# ─── Admin: Update course ────────────────────────────────────
@router.patch("/admin/courses/{course_id}", response_model=CourseOut)
def update_course(course_id: int, data: CourseUpdate, admin: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
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
def delete_course(course_id: int, admin: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    # Delete CF videos for all lessons
    from app.services.cloudflare_stream import delete_video
    for lesson in course.lessons:
        if lesson.cloudflare_video_id:
            delete_video(lesson.cloudflare_video_id)
    db.delete(course)
    db.commit()
    return None

# ─── Admin: Upload course PDF (direct file upload) ──────────
@router.post("/admin/courses/{course_id}/upload-pdf")
async def upload_course_pdf(
    course_id: int,
    file: UploadFile = File(...),
    admin: User = Depends(get_current_admin_user),
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
    course.pdf_url = f"/uploads/course-pdfs/{safe_name}"
    db.commit()
    db.refresh(course)
    
    return {"pdf_url": course.pdf_url, "message": "PDF uploaded successfully"}

# ─── Admin: Upload course thumbnail (direct file upload) ─────
@router.post("/admin/courses/{course_id}/upload-thumbnail")
async def upload_course_thumbnail(
    course_id: int,
    file: UploadFile = File(...),
    admin: User = Depends(get_current_admin_user),
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

# ─── Admin: Get lessons for a course ───────────────────────
@router.get("/admin/{course_id}/lessons", response_model=List[LessonOut])
def admin_get_lessons(
    course_id: int,
    admin: User = Depends(get_current_admin_user),
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
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # No Cloudflare Stream direct upload needed for Bunny.net
    upload_info = {"upload_url": "", "video_id": ""}

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
        cloudflare_video_id=upload_info.get("video_id", ""),
        bunny_video_url=data.bunny_video_url,
        video_status="ready" if data.bunny_video_url else "pending",
    )
    db.add(lesson)

    # Update course total_lessons count
    course.total_lessons = len(course.lessons) + 1
    db.commit()
    db.refresh(lesson)

    return {
        "lesson_id": lesson.id,
        "upload_url": upload_info.get("upload_url", ""),
        "video_id": upload_info.get("video_id", ""),
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
    admin: User = Depends(get_current_admin_user),
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

    for field, value in update_data.items():
        setattr(lesson, field, value)
    db.commit()
    db.refresh(lesson)
    return lesson

# ─── Admin: Generate PDF presigned upload URL ────────────────
@router.post("/admin/lessons/{lesson_id}/pdf")
def admin_upload_pdf(
    lesson_id: int,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    try:
        from app.services.cloudflare_r2 import generate_presigned_upload_url
        result = generate_presigned_upload_url(
            filename=f"lesson-{lesson_id}.pdf",
            content_type="application/pdf",
            folder="lesson-pdfs",
        )
        return result
    except Exception as exc:
        logger.error("R2 presigned URL failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to generate upload URL")

# ─── Admin: Delete lesson + CF video ─────────────────────────
@router.delete("/admin/lessons/{lesson_id}", status_code=204)
def admin_delete_lesson(
    lesson_id: int,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    # Delete CF video
    if lesson.cloudflare_video_id:
        from app.services.cloudflare_stream import delete_video
        delete_video(lesson.cloudflare_video_id)

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
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    if not lesson.cloudflare_video_id:
        return {"status": "pending", "message": "No video uploaded yet"}

    try:
        from app.services.cloudflare_stream import get_video_status
        status = get_video_status(lesson.cloudflare_video_id)
        # Update the stored status
        if lesson.video_status != status:
            lesson.video_status = status
            db.commit()
        return {"status": status}
    except Exception as exc:
        logger.error("CF status poll failed for lesson %d: %s", lesson_id, exc)
        return {"status": "error", "message": str(exc)}

@router.patch("/{course_id}/lessons/{lesson_id}", dependencies=[Depends(get_current_admin_user)])
async def update_lesson(course_id: int, lesson_id: int, data: LessonUpdate, db: Session = Depends(get_db)):
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id, Lesson.course_id == course_id).first()
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    if data.cloudflare_video_url:
        valid_patterns = ["iframe.cloudflarestream.com", "cloudflarestream.com", "videodelivery.net"]
        if not any(p in data.cloudflare_video_url for p in valid_patterns):
            raise HTTPException(400, "Invalid Cloudflare Stream URL. Must be from cloudflarestream.com")
    if data.bunny_video_url:
        valid_patterns = ["iframe.mediadelivery.net", "mediadelivery.net", "b-cdn.net"]
        if not any(p in data.bunny_video_url for p in valid_patterns):
            raise HTTPException(400, "Invalid Bunny.net URL. Must be from mediadelivery.net or b-cdn.net")
    update_data = data.model_dump(exclude_unset=True)
    if "bunny_video_url" in update_data and update_data["bunny_video_url"] != lesson.bunny_video_url:
        from app.services.bunny_stream import get_video_duration_minutes
        new_duration = get_video_duration_minutes(update_data["bunny_video_url"])
        if new_duration > 0 or update_data.get("duration_minutes", 0) == 0:
            update_data["duration_minutes"] = new_duration

    for field, value in update_data.items():
        setattr(lesson, field, value)
    db.commit()
    db.refresh(lesson)
    return lesson

@router.post("/{course_id}/lessons", dependencies=[Depends(get_current_admin_user)])
async def create_lesson(course_id: int, data: LessonCreate, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(404, "Course not found")
    lesson_data = data.model_dump()
    if lesson_data.get("bunny_video_url") and not lesson_data.get("duration_minutes"):
        from app.services.bunny_stream import get_video_duration_minutes
        lesson_data["duration_minutes"] = get_video_duration_minutes(lesson_data["bunny_video_url"])

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
        can_watch = current_user.is_active or lesson.is_free_preview
        result.append({
            "id": lesson.id,
            "title": lesson.title,
            "description": lesson.description,
            "duration_minutes": lesson.duration_minutes,
            "order": lesson.order,
            "is_free_preview": lesson.is_free_preview,
            "has_pdf": lesson.pdf_url is not None,
            "has_video": lesson.bunny_video_url is not None or lesson.cloudflare_video_url is not None,
            "cloudflare_video_url": lesson.cloudflare_video_url if can_watch else None,
            "bunny_video_url": lesson.bunny_video_url if can_watch else None,
            "pdf_url": lesson.pdf_url if can_watch else None,
            "is_completed": lesson.id in completed_ids,
        })
    return result
