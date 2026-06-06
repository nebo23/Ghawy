from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, UniqueConstraint
from sqlalchemy.exc import IntegrityError
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db
from app.models import (
    User, AiUpdatePost, AiUpdatePostType, AiUpdatePoll, AiUpdatePollOption,
    AiUpdatePollVote, AiUpdateReaction, AiUpdateComment
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
        "title": post.title,
        "body": post.body,
        "image_url": post.image_url,
        "video_url": post.video_url,
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

@router.get("/posts")
def list_posts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    q = db.query(AiUpdatePost).options(
        joinedload(AiUpdatePost.author),
        joinedload(AiUpdatePost.reactions),
        joinedload(AiUpdatePost.poll).joinedload(AiUpdatePoll.options),
        joinedload(AiUpdatePost.poll).joinedload(AiUpdatePoll.votes)
    )
    
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


class PollOptionCreate(BaseModel):
    text: str

class PollCreate(BaseModel):
    question: str
    options: List[PollOptionCreate]

class PostCreate(BaseModel):
    post_type: str
    title: str
    body: str
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    poll: Optional[PollCreate] = None


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

    post = AiUpdatePost(
        user_id=current_user.id,
        post_type=post_type_enum,
        title=data.title.strip(),
        body=data.body.strip(),
        image_url=data.image_url,
        video_url=data.video_url,
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
                text=opt.text.strip()
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
