"""
Posts Router — Posts, Comments, Reactions (Skool-style Community Feed)
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func, and_
from typing import Optional, List
from datetime import datetime, timedelta
from app.database import get_db
from app.models import (
    User, Post, Comment, PostLike, PostReaction, CommentReaction,
    Category, Channel, Notification
)
from app.routers.users import get_current_user, get_current_active_member
from app.services.file_service import save_upload
from app.services.ws_manager import manager
from pydantic import BaseModel

router = APIRouter(prefix="/posts", tags=["Posts"])

# ── Allowed emojis ──
ALLOWED_EMOJIS = {"👍", "❤️", "😮", "🔥", "👏"}

# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def time_ago(dt):
    """Return human-readable time difference."""
    if not dt:
        return ""
    now = datetime.utcnow()
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 30:
        return f"{days}d ago"
    months = days // 30
    return f"{months}mo ago"


def build_author_dict(user: User) -> dict:
    """Build author info dict from a User object."""
    return {
        "id": user.id,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
        "selected_avatar": user.selected_avatar,
        "badge": user.badge or "Member",
        "is_admin": user.is_admin,
    }


def get_reaction_counts(reactions: list) -> dict:
    """Count reactions by emoji."""
    counts = {}
    for r in reactions:
        counts[r.emoji] = counts.get(r.emoji, 0) + 1
    return counts


def get_user_reactions(reactions: list, user_id: int) -> list:
    """Get list of emojis the user has reacted with."""
    return [r.emoji for r in reactions if r.user_id == user_id]


def build_post_dict(post: Post, current_user_id: int) -> dict:
    """Build a full post response dict."""
    tags_list = []
    if post.tags:
        tags_list = [t.strip() for t in post.tags.split(",") if t.strip()]
    elif post.tag:
        tags_list = [post.tag]

    return {
        "id": post.id,
        "channel": post.category_slug or "",
        "title": post.title,
        "body": post.body,
        "tag": post.tag,
        "tag_color": post.tag_color,
        "tags": tags_list,
        "image_url": post.image_url,
        "is_pinned": post.is_pinned,
        "like_count": post.like_count or 0,
        "comment_count": post.comment_count or 0,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "updated_at": post.updated_at.isoformat() if post.updated_at else None,
        "time_ago": time_ago(post.created_at),
        "author": build_author_dict(post.author) if post.author else None,
        "reaction_counts": get_reaction_counts(post.reactions) if post.reactions else {},
        "user_reactions": get_user_reactions(post.reactions, current_user_id) if post.reactions else [],
    }


def build_comment_dict(comment: Comment, current_user_id: int, include_replies: bool = True) -> dict:
    """Build a comment response dict."""
    result = {
        "id": comment.id,
        "post_id": comment.post_id,
        "parent_id": comment.parent_id,
        "body": comment.body,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "time_ago": time_ago(comment.created_at),
        "author": build_author_dict(comment.author) if comment.author else None,
        "reaction_counts": get_reaction_counts(comment.reactions) if comment.reactions else {},
        "user_reactions": get_user_reactions(comment.reactions, current_user_id) if comment.reactions else [],
    }
    if include_replies and not comment.parent_id:
        result["replies"] = [
            build_comment_dict(r, current_user_id, include_replies=False)
            for r in (comment.replies or [])
        ]
    return result


# ══════════════════════════════════════════════════════════════
#  LIST POSTS IN A CHANNEL
# ══════════════════════════════════════════════════════════════

@router.get("/{channel}")
def list_posts(
    channel: str,
    sort: str = Query("latest", pattern="^(latest|top)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    search: str = Query("", max_length=200),
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    q = (
        db.query(Post)
        .options(joinedload(Post.author), joinedload(Post.reactions))
        .filter(Post.category_slug == channel)
    )

    if search:
        q = q.filter(
            (Post.title.ilike(f"%{search}%")) | (Post.body.ilike(f"%{search}%"))
        )

    # Sorting
    if sort == "top":
        q = q.order_by(desc(Post.like_count), desc(Post.created_at))
    else:
        q = q.order_by(desc(Post.is_pinned), desc(Post.created_at))

    total = q.count()
    pages = max(1, (total + limit - 1) // limit)
    offset = (page - 1) * limit
    posts = q.offset(offset).limit(limit).all()

    return {
        "posts": [build_post_dict(p, current_user.id) for p in posts],
        "total": total,
        "page": page,
        "pages": pages,
    }


# ══════════════════════════════════════════════════════════════
#  CREATE A POST
# ══════════════════════════════════════════════════════════════

@router.post("/{channel}", status_code=201)
async def create_post(
    channel: str,
    title: str = Form(...),
    body: str = Form(...),
    tags: str = Form(""),
    image: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    if not title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    if len(title) > 120:
        raise HTTPException(status_code=400, detail="Title max 120 characters")
    if not body.strip() or len(body.strip()) < 10:
        raise HTTPException(status_code=400, detail="Body must be at least 10 characters")

    image_url = None
    if image and image.filename:
        try:
            result = await save_upload(image, subfolder="posts")
            image_url = result["file_url"]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Parse tags
    tags_str = ",".join([t.strip() for t in tags.split(",") if t.strip()]) if tags else None

    post = Post(
        user_id=current_user.id,
        category_slug=channel,
        title=title.strip(),
        body=body.strip(),
        tags=tags_str,
        image_url=image_url,
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    # Eager load relationships for response
    post = (
        db.query(Post)
        .options(joinedload(Post.author), joinedload(Post.reactions))
        .filter(Post.id == post.id)
        .first()
    )

    post_data = build_post_dict(post, current_user.id)

    # Broadcast via WebSocket to all online users. Post "channels" are category
    # slugs (e.g. "introduce-yourself"), not chat Channel rows, so we cannot
    # scope by channel id. The client filters by the channel it is viewing and
    # ignores its own posts, so a global broadcast delivers new posts in
    # real-time without requiring a page refresh.
    await manager.broadcast_to_all({
        "event": "new_post",
        "data": post_data,
    }, exclude_user=current_user.id)

    return post_data


# ══════════════════════════════════════════════════════════════
#  TOP TOPICS (TAG COUNTS)
# ══════════════════════════════════════════════════════════════

@router.get("/{channel}/top-topics")
def get_top_topics(
    channel: str,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """Return top 8 tags by usage in this channel."""
    posts = db.query(Post.tags).filter(
        Post.category_slug == channel,
        Post.tags != None,
        Post.tags != "",
    ).all()

    tag_counts = {}
    for (tags_str,) in posts:
        if tags_str:
            for tag in tags_str.split(","):
                tag = tag.strip()
                if tag:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    return [{"tag": tag, "count": count} for tag, count in sorted_tags]


# ══════════════════════════════════════════════════════════════
#  PINNED POSTS
# ══════════════════════════════════════════════════════════════

@router.get("/{channel}/pinned")
def get_pinned_posts(
    channel: str,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    posts = (
        db.query(Post)
        .options(joinedload(Post.author), joinedload(Post.reactions))
        .filter(Post.category_slug == channel, Post.is_pinned == True)
        .order_by(desc(Post.created_at))
        .all()
    )
    return [build_post_dict(p, current_user.id) for p in posts]


# ══════════════════════════════════════════════════════════════
#  GET SINGLE POST WITH COMMENTS
# ══════════════════════════════════════════════════════════════

@router.get("/{channel}/{post_id:int}")
def get_post(
    channel: str,
    post_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    post = (
        db.query(Post)
        .options(
            joinedload(Post.author),
            joinedload(Post.reactions),
            joinedload(Post.comments).joinedload(Comment.author),
            joinedload(Post.comments).joinedload(Comment.reactions),
        )
        .filter(Post.id == post_id, Post.category_slug == channel)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    result = build_post_dict(post, current_user.id)

    # Build nested comments (top-level only, with replies nested)
    top_comments = [c for c in post.comments if c.parent_id is None]
    top_comments.sort(key=lambda c: c.created_at)
    result["comments"] = [build_comment_dict(c, current_user.id) for c in top_comments]

    return result


# ══════════════════════════════════════════════════════════════
#  EDIT POST
# ══════════════════════════════════════════════════════════════

class PostUpdateBody(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    tags: Optional[str] = None

@router.patch("/{channel}/{post_id:int}")
def edit_post(
    channel: str,
    post_id: int,
    data: PostUpdateBody,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id, Post.category_slug == channel).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    if data.title is not None:
        if not data.title.strip() or len(data.title) > 120:
            raise HTTPException(status_code=400, detail="Invalid title")
        post.title = data.title.strip()
    if data.body is not None:
        if not data.body.strip() or len(data.body.strip()) < 10:
            raise HTTPException(status_code=400, detail="Body must be at least 10 characters")
        post.body = data.body.strip()
    if data.tags is not None:
        post.tags = ",".join([t.strip() for t in data.tags.split(",") if t.strip()]) or None

    db.commit()
    db.refresh(post)

    post = (
        db.query(Post)
        .options(joinedload(Post.author), joinedload(Post.reactions))
        .filter(Post.id == post.id)
        .first()
    )
    return build_post_dict(post, current_user.id)


# ══════════════════════════════════════════════════════════════
#  DELETE POST
# ══════════════════════════════════════════════════════════════

@router.delete("/{channel}/{post_id:int}")
def delete_post(
    channel: str,
    post_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id, Post.category_slug == channel).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    db.delete(post)
    db.commit()
    return {"message": "Post deleted"}


# ══════════════════════════════════════════════════════════════
#  PIN / UNPIN POST
# ══════════════════════════════════════════════════════════════

@router.patch("/{channel}/{post_id:int}/pin")
def toggle_pin(
    channel: str,
    post_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")

    post = db.query(Post).filter(Post.id == post_id, Post.category_slug == channel).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post.is_pinned = not post.is_pinned
    db.commit()
    return {"is_pinned": post.is_pinned}


# ══════════════════════════════════════════════════════════════
#  REACT TO A POST (TOGGLE)
# ══════════════════════════════════════════════════════════════

class ReactionBody(BaseModel):
    emoji: str

@router.post("/{post_id}/react")
async def react_to_post(
    post_id: int,
    data: ReactionBody,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    if data.emoji not in ALLOWED_EMOJIS:
        raise HTTPException(status_code=400, detail=f"Invalid emoji. Allowed: {', '.join(ALLOWED_EMOJIS)}")

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check existing reaction
    existing = db.query(PostReaction).filter(
        PostReaction.post_id == post_id,
        PostReaction.user_id == current_user.id,
    ).first()

    is_new_reaction = not existing
    if existing:
        if existing.emoji == data.emoji:
            db.delete(existing)
            post.like_count = max((post.like_count or 0) - 1, 0)
            is_new_reaction = False
        else:
            existing.emoji = data.emoji
    else:
        db.add(PostReaction(post_id=post_id, user_id=current_user.id, emoji=data.emoji))
        post.like_count = (post.like_count or 0) + 1

    db.commit()

    # Notify post author if a new reaction was added
    if is_new_reaction and post.user_id != current_user.id:
        channel_name = post.category_slug or 'general'
        notif = Notification(
            user_id=post.user_id,
            title="New Reaction",
            body=f"{current_user.full_name} reacted {data.emoji} to your post.",
            type="reaction",
            link=f"chat.html?channel={channel_name}&post={post_id}"
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        await manager.send_personal(post.user_id, {
            "event": "notification",
            "data": {"id": notif.id, "title": notif.title, "body": notif.body, "type": notif.type, "link": notif.link, "is_read": notif.is_read}
        })

    reactions = db.query(PostReaction).filter(PostReaction.post_id == post_id).all()
    return {
        "reaction_counts": get_reaction_counts(reactions),
        "user_reactions": get_user_reactions(reactions, current_user.id),
    }


# ══════════════════════════════════════════════════════════════
#  LIST COMMENTS FOR A POST
# ══════════════════════════════════════════════════════════════

@router.get("/{post_id}/comments")
def list_comments(
    post_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    comments = (
        db.query(Comment)
        .options(
            joinedload(Comment.author),
            joinedload(Comment.reactions),
            joinedload(Comment.replies).joinedload(Comment.author),
            joinedload(Comment.replies).joinedload(Comment.reactions),
        )
        .filter(Comment.post_id == post_id, Comment.parent_id == None)
        .order_by(Comment.created_at)
        .all()
    )

    return [build_comment_dict(c, current_user.id) for c in comments]


# ══════════════════════════════════════════════════════════════
#  ADD A COMMENT
# ══════════════════════════════════════════════════════════════

class CommentCreateBody(BaseModel):
    body: str
    parent_id: Optional[int] = None

@router.post("/{post_id}/comments", status_code=201)
async def add_comment(
    post_id: int,
    data: CommentCreateBody,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if not data.body.strip():
        raise HTTPException(status_code=400, detail="Comment body is required")

    # Validate parent_id if provided (must belong to same post, max 1 level)
    if data.parent_id:
        parent = db.query(Comment).filter(
            Comment.id == data.parent_id,
            Comment.post_id == post_id,
        ).first()
        if not parent:
            raise HTTPException(status_code=400, detail="Parent comment not found")
        if parent.parent_id is not None:
            raise HTTPException(status_code=400, detail="Cannot nest replies more than 1 level deep")

    comment = Comment(
        post_id=post_id,
        user_id=current_user.id,
        body=data.body.strip(),
        parent_id=data.parent_id,
    )
    db.add(comment)

    # Update post comment count
    post.comment_count = (post.comment_count or 0) + 1

    db.commit()
    db.refresh(comment)

    # Eager load for response
    comment = (
        db.query(Comment)
        .options(joinedload(Comment.author), joinedload(Comment.reactions))
        .filter(Comment.id == comment.id)
        .first()
    )

    comment_data = build_comment_dict(comment, current_user.id, include_replies=False)

    # One source for both notification links below. The reply branch used to
    # build its link from a bare `channel_name`, which no longer existed after
    # the rename — every reply to a comment raised NameError and 500'd.
    channel_name_for_link = post.category_slug or 'general'

    # Notify post author on new comment (if not a reply and not self)
    if not data.parent_id and post.user_id != current_user.id:
        notif = Notification(
            user_id=post.user_id,
            title="New Comment",
            body=f"{current_user.full_name} commented on your post.",
            type="comment",
            link=f"chat.html?channel={channel_name_for_link}&post={post_id}"
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        await manager.send_personal(post.user_id, {
            "event": "notification",
            "data": {"id": notif.id, "title": notif.title, "body": notif.body, "type": notif.type, "link": notif.link, "is_read": notif.is_read}
        })

    # Broadcast via WebSocket to all online users. Post channels are category
    # slugs (not chat Channel rows), so we broadcast globally; the client only
    # refreshes the comment thread if it currently has that post open.
    await manager.broadcast_to_all({
        "event": "new_comment",
        "data": {**comment_data, "post_id": post_id},
    }, exclude_user=current_user.id)

    # Notification for reply
    if data.parent_id:
        parent_comment = db.query(Comment).filter(Comment.id == data.parent_id).first()
        if parent_comment and parent_comment.user_id != current_user.id:
            notif = Notification(
                user_id=parent_comment.user_id,
                title="New Reply",
                body=f"{current_user.full_name} replied to your comment.",
                type="reply",
                link=f"chat.html?channel={channel_name_for_link}&post={post_id}"
            )
            db.add(notif)
            db.commit()
            db.refresh(notif)

            await manager.send_personal(
                parent_comment.user_id,
                {
                    "event": "notification",
                    "data": {
                        "id": notif.id,
                        "title": notif.title,
                        "body": notif.body,
                        "type": notif.type,
                        "link": notif.link,
                        "is_read": notif.is_read,
                        "created_at": notif.created_at.isoformat(),
                    }
                }
            )

    return comment_data


# ══════════════════════════════════════════════════════════════
#  EDIT COMMENT
# ══════════════════════════════════════════════════════════════

class CommentUpdateBody(BaseModel):
    body: str

@router.patch("/{post_id}/comments/{comment_id}")
def edit_comment(
    post_id: int,
    comment_id: int,
    data: CommentUpdateBody,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    comment = db.query(Comment).filter(
        Comment.id == comment_id, Comment.post_id == post_id
    ).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    if not data.body.strip():
        raise HTTPException(status_code=400, detail="Comment body is required")

    comment.body = data.body.strip()
    db.commit()
    db.refresh(comment)

    comment = (
        db.query(Comment)
        .options(joinedload(Comment.author), joinedload(Comment.reactions))
        .filter(Comment.id == comment.id)
        .first()
    )
    return build_comment_dict(comment, current_user.id, include_replies=False)


# ══════════════════════════════════════════════════════════════
#  DELETE COMMENT
# ══════════════════════════════════════════════════════════════

@router.delete("/{post_id}/comments/{comment_id}")
def delete_comment(
    post_id: int,
    comment_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    comment = db.query(Comment).filter(
        Comment.id == comment_id, Comment.post_id == post_id
    ).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Update post comment count
    post = db.query(Post).filter(Post.id == post_id).first()
    if post:
        # Count this comment + its replies
        reply_count = db.query(Comment).filter(Comment.parent_id == comment_id).count()
        post.comment_count = max((post.comment_count or 0) - 1 - reply_count, 0)

    db.delete(comment)
    db.commit()
    return {"message": "Comment deleted"}


# ══════════════════════════════════════════════════════════════
#  REACT TO A COMMENT (TOGGLE)
# ══════════════════════════════════════════════════════════════

@router.post("/comments/{comment_id}/react")
async def react_to_comment(
    comment_id: int,
    data: ReactionBody,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    if data.emoji not in ALLOWED_EMOJIS:
        raise HTTPException(status_code=400, detail=f"Invalid emoji")

    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    existing = db.query(CommentReaction).filter(
        CommentReaction.comment_id == comment_id,
        CommentReaction.user_id == current_user.id,
    ).first()

    is_new_reaction = not existing
    if existing:
        if existing.emoji == data.emoji:
            db.delete(existing)
            is_new_reaction = False
        else:
            existing.emoji = data.emoji
    else:
        db.add(CommentReaction(comment_id=comment_id, user_id=current_user.id, emoji=data.emoji))

    db.commit()

    # Notify comment author on new reaction
    if is_new_reaction and comment.user_id != current_user.id:
        post = db.query(Post).filter(Post.id == comment.post_id).first()
        channel_name_for_link = (post.category_slug if post else None) or 'general'
        notif = Notification(
            user_id=comment.user_id,
            title="New Like",
            body=f"{current_user.full_name} liked your comment.",
            type="like",
            link=f"chat.html?channel={channel_name_for_link}&post={comment.post_id}"
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        await manager.send_personal(comment.user_id, {
            "event": "notification",
            "data": {"id": notif.id, "title": notif.title, "body": notif.body, "type": notif.type, "link": notif.link, "is_read": notif.is_read}
        })

    reactions = db.query(CommentReaction).filter(CommentReaction.comment_id == comment_id).all()
    return {
        "reaction_counts": get_reaction_counts(reactions),
        "user_reactions": get_user_reactions(reactions, current_user.id),
    }



