from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Course, Lesson, UserCourseProgress, UserProgress, Post, Message, AiUpdatePost
from app.routers.users import get_current_user, get_current_active_member
from app.services.progress_service import calculate_video_streak

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def count_completed_courses(user_id: int, db: Session) -> int:
    """
    Count courses the user has FULLY completed.

    A course is "fully completed" only when the user has a completed
    UserProgress row for EVERY lesson in that course (i.e. completed
    lessons >= total lessons, total > 0). Uses the existing completion
    tracking only — it does not change how completion is recorded.
    """
    total_by_course = dict(
        db.query(Lesson.course_id, func.count(Lesson.id))
        .group_by(Lesson.course_id)
        .all()
    )
    completed_by_course = dict(
        db.query(UserProgress.course_id, func.count(UserProgress.id))
        .filter(UserProgress.user_id == user_id)
        .group_by(UserProgress.course_id)
        .all()
    )

    completed = 0
    for course_id, total in total_by_course.items():
        if total and completed_by_course.get(course_id, 0) >= total:
            completed += 1
    return completed

@router.get("/summary")
def get_dashboard_summary(current_user: User = Depends(get_current_active_member), db: Session = Depends(get_db)):
    # 1. User stats
    # Auto-calculated streak from video watching (server UTC calendar days).
    # Exposed as both `streak_days` (so the profile card / achievements that
    # already read this field show it) and `days_streak` (dashboard stat card).
    video_streak = calculate_video_streak(current_user.id, db)
    user_data = {
        "full_name": current_user.full_name,
        "email": current_user.email,
        "avatar_url": current_user.avatar_url,
        "level": current_user.level,
        "xp": current_user.xp,
        "streak_days": video_streak,
        "days_streak": video_streak,
        # Total number of fully completed courses (all time).
        "courses_completed": count_completed_courses(current_user.id, db),
        "badge": current_user.badge,
        "is_admin": current_user.is_admin
    }

    # 2. Courses (For now, let's just return all published courses with the user's progress)
    courses_query = db.query(Course).filter(Course.is_published == True).all()
    courses_data = []
    for course in courses_query:
        from app.models import UserProgress
        completed_lessons = db.query(UserProgress).filter(
            UserProgress.course_id == course.id,
            UserProgress.user_id == current_user.id
        ).count()
        
        percent = 0.0
        if course.total_lessons > 0:
            percent = (completed_lessons / course.total_lessons) * 100
            
        courses_data.append({
            "id": course.id,
            "title": course.title,
            "thumbnail_url": course.thumbnail_url,
            "total_lessons": course.total_lessons,
            "course_time": course.course_time,
            "completed_lessons": completed_lessons,
            "percent": float(percent)
        })

    # 3. Recent AI Update Posts (limit 4)
    ai_posts_query = db.query(AiUpdatePost).order_by(AiUpdatePost.created_at.desc()).limit(4).all()
    recent_posts = []
    for post in ai_posts_query:
        author = post.author
        avatar_url = None
        selected_avatar = None
        if author:
            avatar_url = author.avatar_url
            selected_avatar = author.selected_avatar
        recent_posts.append({
            "id": post.id,
            "title": post.title,
            "body": post.body,
            "likes_count": post.like_count,
            "comment_count": post.comment_count,
            "created_at": post.created_at,
            "author_name": author.full_name if author else "Unknown",
            "author_avatar_url": avatar_url,
            "author_selected_avatar": selected_avatar,
        })

    # 4. Recent Messages (limit 3, ideally one per channel)
    messages_query = db.query(Message).order_by(Message.created_at.desc()).limit(3).all()
    recent_messages = []
    for msg in messages_query:
        recent_messages.append({
            "id": msg.id,
            "channel": msg.channel.name if msg.channel else "general",
            "content": msg.content,
            "created_at": msg.created_at,
            "author_name": msg.sender.full_name if msg.sender else "Unknown",
            "avatar_url": msg.sender.avatar_url if msg.sender else None
        })

    return {
        "user": user_data,
        "courses": courses_data,
        "recent_posts": recent_posts,
        "recent_messages": recent_messages
    }
