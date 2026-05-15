from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Course, UserCourseProgress, Post, Message
from app.routers.users import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/summary")
def get_dashboard_summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 1. User stats
    user_data = {
        "full_name": current_user.full_name,
        "email": current_user.email,
        "avatar_url": current_user.avatar_url,
        "level": current_user.level,
        "xp": current_user.xp,
        "streak_days": current_user.streak_days,
        "badge": current_user.badge
    }

    # 2. Courses (For now, let's just return all published courses with the user's progress)
    courses_query = db.query(Course).filter(Course.is_published == True).limit(3).all()
    courses_data = []
    for course in courses_query:
        progress = db.query(UserCourseProgress).filter(
            UserCourseProgress.course_id == course.id,
            UserCourseProgress.user_id == current_user.id
        ).first()
        
        courses_data.append({
            "id": course.id,
            "title": course.title,
            "thumbnail_url": course.thumbnail_url,
            "total_lessons": course.total_lessons,
            "completed_lessons": progress.completed_lessons if progress else 0,
            "percent": float(progress.percent) if progress else 0.0
        })

    # 3. Recent Posts (limit 4)
    posts_query = db.query(Post).order_by(Post.created_at.desc()).limit(4).all()
    recent_posts = []
    for post in posts_query:
        recent_posts.append({
            "id": post.id,
            "title": post.title,
            "category": post.category.slug if post.category else "general",
            "likes_count": post.like_count,
            "created_at": post.created_at,
            "author_name": post.author.full_name if post.author else "Unknown"
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
