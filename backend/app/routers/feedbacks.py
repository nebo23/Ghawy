from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import os
import httpx
import logging

from app.database import get_db
from app.models import User, CommunityFeedback
from app.schemas import FeedbackCreate, FeedbackOut
from app.routers.users import get_current_active_member, get_current_admin_user, get_current_admin_or_owner_user

router = APIRouter(prefix="/feedbacks", tags=["Feedbacks"])
logger = logging.getLogger(__name__)

WEBHOOK_URL = os.getenv("N8N_FEEDBACK_WEBHOOK_URL")

async def send_webhook(payload: dict):
    if not WEBHOOK_URL:
        logger.warning("⚠️ N8N_FEEDBACK_WEBHOOK_URL not configured — skipping notification")
        return
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(WEBHOOK_URL, json=payload, timeout=10.0)
            response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to send feedback webhook: {e}")

@router.post("/", response_model=FeedbackOut, status_code=201)
async def create_feedback(
    feedback_in: FeedbackCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    # Save to database
    db_feedback = CommunityFeedback(
        user_id=current_user.id,
        role=feedback_in.role,
        person_name=feedback_in.person_name,
        person_email=feedback_in.person_email,
        feedback_text=feedback_in.feedback_text
    )
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)

    # Prepare webhook payload
    payload = {
        "role": feedback_in.role.value if hasattr(feedback_in.role, 'value') else str(feedback_in.role),
        "person_name": feedback_in.person_name,
        "person_email": feedback_in.person_email,
        "feedback_text": feedback_in.feedback_text,
        "submitted_by": current_user.full_name,
        "submitted_at": db_feedback.created_at.isoformat()
    }

    # Send webhook in background
    background_tasks.add_task(send_webhook, payload)

    return db_feedback

@router.get("/admin", response_model=list[FeedbackOut])
def get_all_feedbacks(
    skip: int = 0, limit: int = 100,
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """All feedbacks — admins and owners only."""
    feedbacks = (
        db.query(CommunityFeedback)
        .order_by(CommunityFeedback.created_at.desc())
        .offset(skip).limit(limit).all()
    )
    result = []
    for f in feedbacks:
        submitter = db.query(User).filter(User.id == f.user_id).first()
        out = FeedbackOut(
            id=f.id,
            user_id=f.user_id,
            role=f.role,
            person_name=f.person_name,
            person_email=f.person_email,
            feedback_text=f.feedback_text,
            created_at=f.created_at,
            submitted_by_name=submitter.full_name if submitter else None,
            submitted_by_avatar=(submitter.avatar_url or submitter.selected_avatar) if submitter else None,
        )
        result.append(out)
    return result


@router.get("/", response_model=list[FeedbackOut])
def get_feedbacks(
    skip: int = 0, limit: int = 50,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    feedbacks = db.query(CommunityFeedback).filter(CommunityFeedback.user_id == current_user.id).order_by(CommunityFeedback.created_at.desc()).offset(skip).limit(limit).all()
    return feedbacks


@router.delete("/{feedback_id}", status_code=204)
def delete_feedback(
    feedback_id: int,
    admin: User = Depends(get_current_admin_or_owner_user),
    db: Session = Depends(get_db),
):
    """DELETE /feedbacks/{feedback_id} — admins and owners only."""
    feedback = db.query(CommunityFeedback).filter(CommunityFeedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    db.delete(feedback)
    db.commit()
