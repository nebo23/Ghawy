from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func, UniqueConstraint
from sqlalchemy.exc import IntegrityError
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.models import (
    User, AiUpdatePost, AiUpdatePostType, AiUpdatePoll, AiUpdatePollOption,
    AiUpdatePollVote, AiUpdateReaction, AiUpdateComment, AiUpdateRead
)
from app.routers.users import get_current_admin_user, get_current_active_member

router = APIRouter(prefix="/ai-updates", tags=["AI Updates"])

# ── Allowed emojis ──
ALLOWED_EMOJIS = {"👍", "❤️", "😮", "🔥", "👏"}

# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def time_ago(dt: datetime) -> str:
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
    if not user:
        return None
    return {
        "id": user.id,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
        "selected_avatar": getattr(user, 'selected_avatar', None),
        "badge": user.badge or "Member",
        "is_admin": user.is_admin,
        "custom_title": getattr(user, 'custom_title', '') or "",
    }


def get_reaction_counts(reactions: list) -> dict:
    counts = {}
    for r in reactions:
        counts[r.emoji] = counts.get(r.emoji, 0) + 1
    return counts


def get_user_reactions(reactions: list, user_id: int) -> list:
    return [r.emoji for r in reactions if r.user_id == user_id]


def build_poll_dict(poll: AiUpdatePoll, current_user_id: int) -> dict:
    if not poll:
        return None
    user_voted_option_id = None
    for vote in poll.votes:
        if vote.user_id == current_user_id:
            user_voted_option_id = vote.option_id
            break

    options = []
    total_votes = poll.total_votes or 0
    for opt in poll.options:
        pct = round((opt.votes_count / total_votes * 100)) if total_votes > 0 else 0
        options.append({
            "id": opt.id,
            "text": opt.text,
            "image_url": opt.image_url,
            "votes_count": opt.votes_count,
            "percentage": pct
        })

    return {
        "id": poll.id,
        "question": poll.question,
        "total_votes": total_votes,
        "options": options,
        "user_voted_option_id": user_voted_option_id
    }


def build_post_dict(post: AiUpdatePost, current_user_id: int) -> dict:
    return {
        "id": post.id,
        "post_type": post.post_type.value if post.post_type else "text",
        "category": (post.category or "news"),
        "title": post.title,
        "body": post.body,
        "image_url": post.image_url,
        "video_url": post.video_url,
        "media": post.media or [],
        "is_pinned": post.is_pinned,
        "like_count": post.like_count or 0,
        "comment_count": post.comment_count or 0,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "time_ago": time_ago(post.created_at),
        "author": build_author_dict(post.author),
        "reaction_counts": get_reaction_counts(post.reactions) if post.reactions else {},
        "user_reactions": get_user_reactions(post.reactions, current_user_id) if post.reactions else [],
        "poll": build_poll_dict(post.poll, current_user_id) if post.poll else None
    }


def build_comment_dict(comment: AiUpdateComment, include_replies: bool = True) -> dict:
    result = {
        "id": comment.id,
        "post_id": comment.post_id,
        "parent_id": comment.parent_id,
        "body": comment.body,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "time_ago": time_ago(comment.created_at),
        "author": build_author_dict(comment.author)
    }
    if include_replies and not comment.parent_id:
        result["replies"] = [
            build_comment_dict(r, include_replies=False)
            for r in (comment.replies or [])
        ]
    return result


# ══════════════════════════════════════════════════════════════
#  POSTS
# ══════════════════════════════════════════════════════════════

# Editorial categories the feed understands. NULL rows behave as "news".
VALID_CATEGORIES = {"news", "tools", "models", "updates", "tutorials", "discussions"}


@router.get("/posts")
def list_posts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    category: Optional[str] = Query(None),
    sort: str = Query("latest"),
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    q = db.query(AiUpdatePost).options(
        joinedload(AiUpdatePost.author),
        joinedload(AiUpdatePost.reactions),
        joinedload(AiUpdatePost.poll).joinedload(AiUpdatePoll.options),
        joinedload(AiUpdatePost.poll).joinedload(AiUpdatePoll.votes)
    )

    # The feed is a full archive — every post stays reachable through pagination.
    # (It used to hide anything older than 7 days, which made posts vanish from
    # the feed while the sidebar rails still linked to them.)

    cat = (category or "").strip().lower()
    if cat and cat != "all" and cat in VALID_CATEGORIES:
        if cat == "news":
            # Legacy rows with NULL category read as news.
            q = q.filter((AiUpdatePost.category == "news") | (AiUpdatePost.category.is_(None)))
        else:
            q = q.filter(AiUpdatePost.category == cat)

    if sort == "popular":
        q = q.order_by(
            desc(AiUpdatePost.is_pinned),
            desc(AiUpdatePost.like_count + AiUpdatePost.comment_count),
            desc(AiUpdatePost.created_at),
        )
    else:
        q = q.order_by(desc(AiUpdatePost.is_pinned), desc(AiUpdatePost.created_at))

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


# ─── Unread count (sidebar badge) ─────────────────────────────

@router.get("/unread")
def get_ai_updates_unread(
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    """Number of AI Update posts published since the user last opened the feed."""
    read_state = db.query(AiUpdateRead).filter(AiUpdateRead.user_id == current_user.id).first()
    since = (read_state.last_read_at if read_state else None) or current_user.created_at

    q = db.query(func.count(AiUpdatePost.id)).filter(AiUpdatePost.user_id != current_user.id)
    if since:
        q = q.filter(AiUpdatePost.created_at > since)

    return {"unread_count": q.scalar() or 0}


@router.put("/read")
def mark_ai_updates_read(
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    """Mark the AI Updates feed as seen — creates the per-user marker if needed."""
    read_state = db.query(AiUpdateRead).filter(AiUpdateRead.user_id == current_user.id).first()
    if not read_state:
        read_state = AiUpdateRead(user_id=current_user.id)
        db.add(read_state)
    read_state.last_read_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


# ─── Overview (stats + sidebar rails) ─────────────────────────

@router.get("/overview")
def get_overview(
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    """Aggregate data for the AI Updates header stats and right-hand rails."""
    week_ago = datetime.utcnow() - timedelta(days=7)

    def _cat_expr():
        # Treat NULL category as "news" so legacy rows are counted.
        return func.coalesce(AiUpdatePost.category, "news")

    # ── Weekly stat cards ──
    def _count_since(*cats):
        qq = db.query(func.count(AiUpdatePost.id)).filter(AiUpdatePost.created_at >= week_ago)
        if cats:
            qq = qq.filter(_cat_expr().in_(cats))
        return qq.scalar() or 0

    stats = {
        "updates_this_week": _count_since(),  # all posts this week
        "tools_this_week": _count_since("tools"),
        "models_this_week": _count_since("models"),
        "discussions_this_week": _count_since("discussions"),
    }

    # ── Most popular (by engagement, all time) ──
    popular_rows = (
        db.query(AiUpdatePost)
        .order_by(desc(AiUpdatePost.like_count + AiUpdatePost.comment_count), desc(AiUpdatePost.created_at))
        .limit(5)
        .all()
    )
    most_popular = [
        {
            "id": p.id,
            "title": p.title,
            "category": p.category or "news",
            "engagement": (p.like_count or 0) + (p.comment_count or 0),
            "like_count": p.like_count or 0,
            "comment_count": p.comment_count or 0,
        }
        for p in popular_rows
    ]

    # ── New tools ──
    tool_rows = (
        db.query(AiUpdatePost)
        .filter(AiUpdatePost.category == "tools")
        .order_by(desc(AiUpdatePost.created_at))
        .limit(5)
        .all()
    )
    new_tools = [
        {"id": p.id, "title": p.title, "time_ago": time_ago(p.created_at)}
        for p in tool_rows
    ]

    # ── What's new (latest posts, any category) ──
    recent_rows = (
        db.query(AiUpdatePost)
        .order_by(desc(AiUpdatePost.created_at))
        .limit(6)
        .all()
    )
    whats_new = [
        {
            "id": p.id,
            "title": p.title,
            "category": p.category or "news",
            "time_ago": time_ago(p.created_at),
        }
        for p in recent_rows
    ]

    # ── Top contributors (members ranked by comments + reactions given) ──
    comment_counts = dict(
        db.query(AiUpdateComment.user_id, func.count(AiUpdateComment.id))
        .group_by(AiUpdateComment.user_id)
        .all()
    )
    reaction_counts = dict(
        db.query(AiUpdateReaction.user_id, func.count(AiUpdateReaction.id))
        .group_by(AiUpdateReaction.user_id)
        .all()
    )
    points_by_user = {}
    for uid, c in comment_counts.items():
        points_by_user[uid] = points_by_user.get(uid, 0) + c * 3
    for uid, r in reaction_counts.items():
        points_by_user[uid] = points_by_user.get(uid, 0) + r * 1

    top_ids = sorted(points_by_user, key=lambda k: points_by_user[k], reverse=True)[:5]
    top_contributors = []
    if top_ids:
        users = {u.id: u for u in db.query(User).filter(User.id.in_(top_ids)).all()}
        for uid in top_ids:
            u = users.get(uid)
            if not u:
                continue
            top_contributors.append({
                "id": u.id,
                "full_name": u.full_name,
                "avatar_url": u.avatar_url,
                "selected_avatar": getattr(u, "selected_avatar", None),
                "is_admin": u.is_admin,
                "custom_title": getattr(u, "custom_title", "") or "",
                "badge": u.badge or "Member",
                "points": points_by_user[uid],
            })

    return {
        "stats": stats,
        "most_popular": most_popular,
        "new_tools": new_tools,
        "whats_new": whats_new,
        "top_contributors": top_contributors,
    }


class PollOptionCreate(BaseModel):
    text: str
    image_url: Optional[str] = None

class PollCreate(BaseModel):
    question: str
    options: List[PollOptionCreate]

class MediaItem(BaseModel):
    type: str   # "image" | "video"
    url: str

class PostCreate(BaseModel):
    post_type: str
    title: str
    body: str
    category: Optional[str] = "news"
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    media: Optional[List[MediaItem]] = None
    poll: Optional[PollCreate] = None

class PostUpdate(BaseModel):
    # Every field optional; only the ones sent are applied (exclude_unset).
    post_type: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    media: Optional[List[MediaItem]] = None


MAX_MEDIA_ITEMS = 10

def normalize_media(items) -> list:
    """Validate/clean a media list into [{"type": "image"|"video", "url": str}, ...]."""
    out = []
    for m in (items or []):
        t = (m.type or "").strip().lower()
        u = (m.url or "").strip()
        if t in ("image", "video") and u:
            out.append({"type": t, "url": u})
    return out[:MAX_MEDIA_ITEMS]


@router.post("/posts", status_code=201)
def create_post(
    data: PostCreate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    try:
        post_type_enum = AiUpdatePostType(data.post_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid post type")

    category = (data.category or "news").strip().lower()
    if category not in VALID_CATEGORIES:
        category = "news"

    media = normalize_media(data.media)
    # Keep legacy single-media columns in sync with the first media item.
    image_url = data.image_url or next((m["url"] for m in media if m["type"] == "image"), None)
    video_url = data.video_url or next((m["url"] for m in media if m["type"] == "video"), None)

    post = AiUpdatePost(
        user_id=current_user.id,
        post_type=post_type_enum,
        category=category,
        title=data.title.strip(),
        body=data.body.strip(),
        image_url=image_url,
        video_url=video_url,
        media=media or None,
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    if post_type_enum == AiUpdatePostType.POLL and data.poll:
        if len(data.poll.options) < 2 or len(data.poll.options) > 4:
            raise HTTPException(status_code=400, detail="Polls must have 2 to 4 options")
        
        poll = AiUpdatePoll(
            post_id=post.id,
            question=data.poll.question.strip()
        )
        db.add(poll)
        db.commit()
        db.refresh(poll)

        for opt in data.poll.options:
            poll_option = AiUpdatePollOption(
                poll_id=poll.id,
                text=opt.text.strip(),
                image_url=(opt.image_url or "").strip() or None
            )
            db.add(poll_option)
        db.commit()

    # Re-fetch with eager loading
    post = db.query(AiUpdatePost).options(
        joinedload(AiUpdatePost.author),
        joinedload(AiUpdatePost.reactions),
        joinedload(AiUpdatePost.poll).joinedload(AiUpdatePoll.options),
        joinedload(AiUpdatePost.poll).joinedload(AiUpdatePoll.votes)
    ).filter(AiUpdatePost.id == post.id).first()

    return build_post_dict(post, current_user.id)


@router.delete("/posts/{post_id}")
def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    post = db.query(AiUpdatePost).filter(AiUpdatePost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    db.delete(post)
    db.commit()
    return {"message": "Post deleted"}


@router.patch("/posts/{post_id}/pin")
def toggle_pin(
    post_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    post = db.query(AiUpdatePost).filter(AiUpdatePost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post.is_pinned = not post.is_pinned
    db.commit()
    return {"is_pinned": post.is_pinned}


@router.patch("/posts/{post_id}")
def update_post(
    post_id: int,
    data: PostUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    post = db.query(AiUpdatePost).filter(AiUpdatePost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    fields = data.dict(exclude_unset=True)

    if "post_type" in fields and fields["post_type"] is not None:
        try:
            post.post_type = AiUpdatePostType(fields["post_type"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid post type")

    if "category" in fields and fields["category"] is not None:
        category = (fields["category"] or "news").strip().lower()
        post.category = category if category in VALID_CATEGORIES else "news"

    if "title" in fields and fields["title"] is not None:
        post.title = fields["title"].strip()

    if "body" in fields and fields["body"] is not None:
        post.body = fields["body"].strip()

    # image_url / video_url: presence in the payload replaces the value (None clears it).
    if "image_url" in fields:
        post.image_url = fields["image_url"] or None
    if "video_url" in fields:
        post.video_url = fields["video_url"] or None

    # media: presence in the payload replaces the whole list; keep legacy columns in sync.
    if "media" in fields:
        media = normalize_media(data.media)
        post.media = media or None
        post.image_url = next((m["url"] for m in media if m["type"] == "image"), None)
        post.video_url = next((m["url"] for m in media if m["type"] == "video"), None)

    db.commit()

    post = db.query(AiUpdatePost).options(
        joinedload(AiUpdatePost.author),
        joinedload(AiUpdatePost.reactions),
        joinedload(AiUpdatePost.poll).joinedload(AiUpdatePoll.options),
        joinedload(AiUpdatePost.poll).joinedload(AiUpdatePoll.votes)
    ).filter(AiUpdatePost.id == post.id).first()

    return build_post_dict(post, current_user.id)


# ══════════════════════════════════════════════════════════════
#  REACTIONS
# ══════════════════════════════════════════════════════════════

class ReactionBody(BaseModel):
    emoji: str

@router.post("/posts/{post_id}/react")
def react_to_post(
    post_id: int,
    data: ReactionBody,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    if data.emoji not in ALLOWED_EMOJIS:
        raise HTTPException(status_code=400, detail="Invalid emoji")

    post = db.query(AiUpdatePost).filter(AiUpdatePost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    existing = db.query(AiUpdateReaction).filter(
        AiUpdateReaction.post_id == post_id,
        AiUpdateReaction.user_id == current_user.id
    ).first()

    if existing:
        if existing.emoji == data.emoji:
            db.delete(existing)
            post.like_count = max((post.like_count or 0) - 1, 0)
        else:
            existing.emoji = data.emoji
    else:
        db.add(AiUpdateReaction(post_id=post_id, user_id=current_user.id, emoji=data.emoji))
        post.like_count = (post.like_count or 0) + 1

    db.commit()

    reactions = db.query(AiUpdateReaction).filter(AiUpdateReaction.post_id == post_id).all()
    return {
        "reaction_counts": get_reaction_counts(reactions),
        "user_reactions": get_user_reactions(reactions, current_user.id)
    }


# ══════════════════════════════════════════════════════════════
#  COMMENTS
# ══════════════════════════════════════════════════════════════

@router.get("/posts/{post_id}/comments")
def list_comments(
    post_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    post = db.query(AiUpdatePost).filter(AiUpdatePost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    comments = (
        db.query(AiUpdateComment)
        .options(
            joinedload(AiUpdateComment.author),
            joinedload(AiUpdateComment.replies).joinedload(AiUpdateComment.author)
        )
        .filter(AiUpdateComment.post_id == post_id, AiUpdateComment.parent_id == None)
        .order_by(AiUpdateComment.created_at)
        .all()
    )

    return [build_comment_dict(c) for c in comments]


class CommentCreateBody(BaseModel):
    body: str
    parent_id: Optional[int] = None

@router.post("/posts/{post_id}/comments", status_code=201)
def add_comment(
    post_id: int,
    data: CommentCreateBody,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    post = db.query(AiUpdatePost).filter(AiUpdatePost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if not data.body.strip():
        raise HTTPException(status_code=400, detail="Comment body is required")

    if data.parent_id:
        parent = db.query(AiUpdateComment).filter(
            AiUpdateComment.id == data.parent_id,
            AiUpdateComment.post_id == post_id
        ).first()
        if not parent:
            raise HTTPException(status_code=400, detail="Parent comment not found")
        if parent.parent_id is not None:
            raise HTTPException(status_code=400, detail="Cannot nest replies more than 1 level deep")

    comment = AiUpdateComment(
        post_id=post_id,
        user_id=current_user.id,
        body=data.body.strip(),
        parent_id=data.parent_id
    )
    db.add(comment)
    post.comment_count = (post.comment_count or 0) + 1
    db.commit()
    db.refresh(comment)

    comment = db.query(AiUpdateComment).options(joinedload(AiUpdateComment.author)).filter(AiUpdateComment.id == comment.id).first()
    return build_comment_dict(comment, include_replies=False)


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    comment = db.query(AiUpdateComment).filter(AiUpdateComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    post = db.query(AiUpdatePost).filter(AiUpdatePost.id == comment.post_id).first()
    if post:
        reply_count = db.query(AiUpdateComment).filter(AiUpdateComment.parent_id == comment_id).count()
        post.comment_count = max((post.comment_count or 0) - 1 - reply_count, 0)

    db.delete(comment)
    db.commit()
    return {"message": "Comment deleted"}


# ══════════════════════════════════════════════════════════════
#  POLLS
# ══════════════════════════════════════════════════════════════

class VoteBody(BaseModel):
    option_id: int

@router.post("/polls/{poll_id}/vote")
def vote_poll(
    poll_id: int,
    data: VoteBody,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    poll = db.query(AiUpdatePoll).filter(AiUpdatePoll.id == poll_id).first()
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")

    option = db.query(AiUpdatePollOption).filter(
        AiUpdatePollOption.id == data.option_id,
        AiUpdatePollOption.poll_id == poll_id
    ).first()
    if not option:
        raise HTTPException(status_code=404, detail="Option not found")

    try:
        vote = AiUpdatePollVote(poll_id=poll_id, option_id=data.option_id, user_id=current_user.id)
        db.add(vote)
        poll.total_votes = (poll.total_votes or 0) + 1
        option.votes_count = (option.votes_count or 0) + 1
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="You have already voted on this poll")

    return build_poll_dict(poll, current_user.id)


@router.get("/polls/{poll_id}/results")
def get_poll_results(
    poll_id: int,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    poll = db.query(AiUpdatePoll).options(
        joinedload(AiUpdatePoll.options),
        joinedload(AiUpdatePoll.votes)
    ).filter(AiUpdatePoll.id == poll_id).first()
    
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")

    return build_poll_dict(poll, current_user.id)
