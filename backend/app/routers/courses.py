from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, Course, Lesson, UserCourseProgress
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
    return course

@router.get("/{course_id}/progress", response_model=UserCourseProgressOut)
def get_course_progress(course_id: int, current_user: User = Depends(get_current_active_member), db: Session = Depends(get_db)):
    progress = db.query(UserCourseProgress).filter(
        UserCourseProgress.course_id == course_id,
        UserCourseProgress.user_id == current_user.id
    ).first()
    if not progress:
        return {"completed_lessons": 0, "percent": 0.0}
    return progress

@router.post("/{course_id}/progress", response_model=UserCourseProgressOut)
def update_course_progress(course_id: int, data: CourseProgressUpdate, current_user: User = Depends(get_current_active_member), db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    progress = db.query(UserCourseProgress).filter(
        UserCourseProgress.course_id == course_id,
        UserCourseProgress.user_id == current_user.id
    ).first()

    percent = 0.0
    if course.total_lessons > 0:
        percent = min((data.completed_lessons / course.total_lessons) * 100, 100.0)

    if progress:
        progress.completed_lessons = data.completed_lessons
        progress.percent = percent
    else:
        progress = UserCourseProgress(
            user_id=current_user.id,
            course_id=course_id,
            completed_lessons=data.completed_lessons,
            percent=percent
        )
        db.add(progress)

    db.commit()
    db.refresh(progress)
    return progress


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

# ─── Admin: Create lesson + CF direct upload ─────────────────
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

    # Create Cloudflare Stream direct upload URL
    upload_info = {"upload_url": "", "video_id": ""}
    try:
        from app.services.cloudflare_stream import create_direct_upload
        upload_info = create_direct_upload(max_duration_seconds=7200)
    except Exception as exc:
        logger.warning("CF Stream direct_upload failed: %s", exc)

    lesson = Lesson(
        course_id=course_id,
        title=data.title,
        section_title=data.section_title,
        order=data.order,
        duration_minutes=data.duration_minutes,
        cloudflare_video_id=upload_info.get("video_id", ""),
        video_status="pending",
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
    for field, value in data.model_dump(exclude_unset=True).items():
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
