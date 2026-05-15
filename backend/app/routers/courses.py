from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, Course, Lesson, UserCourseProgress
from app.routers.users import get_current_user
from app.schemas import CourseOut, CourseDetailOut, CourseCreate, LessonCreate, LessonOut, UserCourseProgressOut, CourseProgressUpdate

router = APIRouter(prefix="/courses", tags=["Courses"])

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
def get_course_progress(course_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    progress = db.query(UserCourseProgress).filter(
        UserCourseProgress.course_id == course_id,
        UserCourseProgress.user_id == current_user.id
    ).first()
    if not progress:
        return {"completed_lessons": 0, "percent": 0.0}
    return progress

@router.post("/{course_id}/progress", response_model=UserCourseProgressOut)
def update_course_progress(course_id: int, data: CourseProgressUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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

# Admin only endpoints
def get_admin_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    return current_user

@router.post("", response_model=CourseOut, status_code=201)
def create_course(data: CourseCreate, admin_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    course = Course(
        title=data.title,
        description=data.description,
        thumbnail_url=data.thumbnail_url,
        total_lessons=data.total_lessons,
        is_published=data.is_published
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course

@router.post("/{course_id}/lessons", response_model=LessonOut, status_code=201)
def add_lesson(course_id: int, data: LessonCreate, admin_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    lesson = Lesson(
        course_id=course_id,
        title=data.title,
        video_url=data.video_url,
        content=data.content,
        order=data.order,
        duration_minutes=data.duration_minutes
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return lesson
