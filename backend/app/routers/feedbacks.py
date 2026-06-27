from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import os
import httpx
import logging

from app.database import get_db
from app.models import User, CommunityFeedback
from app.schemas import FeedbackCreate, FeedbackOut
from app.routers.users import get_current_active_member

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

@router.get("/", response_model=list[FeedbackOut])
def get_feedbacks(
    skip: int = 0, limit: int = 50,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db)
):
    # Only users can see their own feedbacks, or if it's admin, we can show all.
    # Based on the prompt, it seems users see "previous feedbacks". Let's show the user's own feedbacks.
    feedbacks = db.query(CommunityFeedback).filter(CommunityFeedback.user_id == current_user.id).order_by(CommunityFeedback.created_at.desc()).offset(skip).limit(limit).all()
    return feedbacks
