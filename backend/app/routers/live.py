"""
Live Sessions router — admin CRUD, user registration, email notifications.
Keeps existing WebSocket endpoint for backward compatibility.
"""
import logging
import re
import json
import asyncio
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db, SessionLocal
from app.models import User, LiveSession, LiveAttendee, SessionBooking, SessionReminder, LiveSessionStatus
from app.routers.users import get_current_user, get_current_admin_user, require_perm

# صلاحية تاب اللايفات — الـ owner بيعدّي دايماً
PERM_LIVE = require_perm("live-sessions")
from app.routers.ws import get_user_from_token
from app.services.live_manager import live_manager
from app.schemas import LiveSessionCreate, LiveSessionUpdate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Live Sessions"])


def _slugify(text: str) -> str:
    """Generate a URL-friendly slug from a title."""
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug or "session"


def _unique_slug(title: str, db: Session, exclude_id: int = None) -> str:
    """Generate a unique slug for a live session."""
    base = _slugify(title)
    slug = base
    counter = 1
    while True:
        query = db.query(LiveSession).filter(LiveSession.slug == slug)
        if exclude_id:
            query = query.filter(LiveSession.id != exclude_id)
        if not query.first():
            return slug
        slug = f"{base}-{counter}"
        counter += 1


def _session_to_dict(session: LiveSession, user_id: int = None, db: Session = None) -> dict:
    """Convert a LiveSession model to a response dict."""
    is_registered = False
    attendee_count = 0
    if db:
        attendee_count = db.query(LiveAttendee).filter(LiveAttendee.session_id == session.id).count()
        if user_id:
            is_registered = db.query(LiveAttendee).filter(
                LiveAttendee.session_id == session.id,
                LiveAttendee.user_id == user_id
            ).first() is not None

    return {
        "id": session.id,
        "title": session.title,
        "slug": session.slug,
        "description": session.description,
        "scheduled_at": session.scheduled_at.isoformat() if session.scheduled_at else None,
        "youtube_url": session.youtube_url,
        "zoom_url": session.zoom_url,
        "is_published": session.is_published,
        "created_by": session.created_by,
        "attendee_count": attendee_count,
        "is_registered": is_registered,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


# ═══════════════════════════════════════════════════════════════
#  ADMIN ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.post("/admin/live/sessions", status_code=201)
def admin_create_session(
    data: LiveSessionCreate,
    admin: User = Depends(PERM_LIVE),  # 🔒 صلاحية التاب
    db: Session = Depends(get_db),
):
    slug = _unique_slug(data.title, db)
    scheduled_at = None
    if data.scheduled_at:
        try:
            scheduled_at = datetime.fromisoformat(data.scheduled_at.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid scheduled_at format. Use ISO 8601.")

    session = LiveSession(
        title=data.title,
        slug=slug,
        description=data.description,
        scheduled_at=scheduled_at,
        start_time=scheduled_at,
        youtube_url=data.youtube_url,
        zoom_url=data.zoom_url,
        is_published=False,
        created_by=admin.id,
        instructor_id=admin.id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_to_dict(session, db=db)


@router.patch("/admin/live/sessions/{session_id}")
def admin_update_session(
    session_id: int,
    data: LiveSessionUpdate,
    admin: User = Depends(PERM_LIVE),  # 🔒 صلاحية التاب
    db: Session = Depends(get_db),
):
    session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    update_data = data.model_dump(exclude_unset=True)

    if "scheduled_at" in update_data and update_data["scheduled_at"]:
        try:
            update_data["scheduled_at"] = datetime.fromisoformat(
                update_data["scheduled_at"].replace("Z", "+00:00")
            )
            update_data["start_time"] = update_data["scheduled_at"]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid scheduled_at format")

    if "title" in update_data:
        update_data["slug"] = _unique_slug(update_data["title"], db, exclude_id=session_id)

    for field, value in update_data.items():
        if hasattr(session, field):
            setattr(session, field, value)

    db.commit()
    db.refresh(session)
    return _session_to_dict(session, db=db)


@router.delete("/admin/live/sessions/{session_id}", status_code=204)
def admin_delete_session(
    session_id: int,
    admin: User = Depends(PERM_LIVE),  # 🔒 صلاحية التاب
    db: Session = Depends(get_db),
):
    session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session)
    db.commit()
    return None


@router.post("/admin/live/sessions/{session_id}/notify")
def admin_notify_session(
    session_id: int,
    admin: User = Depends(PERM_LIVE),  # 🔒 صلاحية التاب
    db: Session = Depends(get_db),
):
    session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get all active subscribers
    active_users = db.query(User).filter(User.is_active == True).all()
    sent_count = 0
    errors = 0

    for user in active_users:
        try:
            from app.services.email_service import send_live_session_notification
            send_live_session_notification(
                to_email=user.email,
                full_name=user.full_name,
                session_title=session.title,
                scheduled_at=session.scheduled_at.strftime("%A, %B %d at %I:%M %p") if session.scheduled_at else "TBD",
                description=session.description or "",
            )
            sent_count += 1
        except Exception as exc:
            errors += 1
            logger.warning("Failed to send notification to %s: %s", user.email, exc)

    return {"sent": sent_count, "errors": errors, "total": len(active_users)}


@router.get("/admin/live/sessions")
def admin_list_sessions(
    admin: User = Depends(PERM_LIVE),  # 🔒 صلاحية التاب
    db: Session = Depends(get_db),
):
    """List all sessions for admin (published + drafts)."""
    sessions = db.query(LiveSession).order_by(desc(LiveSession.created_at)).all()
    return [_session_to_dict(s, db=db) for s in sessions]


@router.get("/admin/live/sessions/{session_id}/attendees")
def admin_get_attendees(
    session_id: int,
    export: Optional[str] = Query(None),
    admin: User = Depends(PERM_LIVE),  # 🔒 صلاحية التاب
    db: Session = Depends(get_db),
):
    session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    attendees = db.query(LiveAttendee, User).join(
        User, LiveAttendee.user_id == User.id
    ).filter(
        LiveAttendee.session_id == session_id
    ).all()

    result = []
    for att, user in attendees:
        result.append({
            "id": att.id,
            "user_id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "registered_at": att.registered_at.isoformat() if att.registered_at else None,
        })

    if export == "csv":
        import csv
        import io
        from app.routers.admin import _csv_safe
        from fastapi.responses import StreamingResponse

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Name", "Email", "Registered At"])
        for a in result:
            # Same formula-injection guard as the payments export: these names
            # are member-supplied and this file opens in someone's spreadsheet.
            writer.writerow([_csv_safe(a["full_name"]), _csv_safe(a["email"]), a["registered_at"]])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=attendees-session-{session_id}.csv"},
        )

    return {"attendees": result, "total": len(result)}


# ═══════════════════════════════════════════════════════════════
#  USER / PUBLIC ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/live/sessions")
def list_published_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all published sessions ordered by scheduled_at ASC."""
    sessions = db.query(LiveSession).filter(
        LiveSession.is_published == True
    ).order_by(LiveSession.scheduled_at.asc()).all()

    return [_session_to_dict(s, user_id=current_user.id, db=db) for s in sessions]


@router.post("/live/sessions/{session_id}/register")
def register_for_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(LiveSession).filter(
        LiveSession.id == session_id,
        LiveSession.is_published == True,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    existing = db.query(LiveAttendee).filter(
        LiveAttendee.session_id == session_id,
        LiveAttendee.user_id == current_user.id,
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Already registered")

    attendee = LiveAttendee(
        session_id=session_id,
        user_id=current_user.id,
    )
    db.add(attendee)
    db.commit()
    return {"status": "success", "message": "Registered successfully"}


@router.delete("/live/sessions/{session_id}/register")
def unregister_from_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attendee = db.query(LiveAttendee).filter(
        LiveAttendee.session_id == session_id,
        LiveAttendee.user_id == current_user.id,
    ).first()
    if not attendee:
        raise HTTPException(status_code=404, detail="Not registered")
    db.delete(attendee)
    db.commit()
    return {"status": "success", "message": "Unregistered"}


# ═══════════════════════════════════════════════════════════════
#  LEGACY ENDPOINTS (kept for backward compatibility)
# ═══════════════════════════════════════════════════════════════

@router.get("/api/live-sessions")
def get_live_sessions_legacy(status_filter: Optional[str] = None, db: Session = Depends(get_db)):
    """Legacy endpoint kept for backward compat with bwm.js."""
    query = db.query(LiveSession)
    if status_filter:
        try:
            status_enum = LiveSessionStatus(status_filter)
            query = query.filter(LiveSession.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")

    sessions = query.order_by(LiveSession.start_time).all()
    result = []
    for s in sessions:
        instructor = db.query(User).filter(User.id == s.instructor_id).first() if s.instructor_id else None
        result.append({
            "id": s.id,
            "title": s.title,
            "slug": s.slug,
            "description": s.description,
            "thumbnail_url": s.thumbnail_url,
            "instructor": {
                "id": instructor.id,
                "name": instructor.full_name,
                "avatar_url": instructor.avatar_url
            } if instructor else None,
            "status": s.status.value if s.status else "upcoming",
            "difficulty": s.difficulty.value if s.difficulty else "beginner",
            "start_time": s.start_time.isoformat() if s.start_time else None,
            "end_time": s.end_time.isoformat() if s.end_time else None,
            "max_attendees": s.max_attendees,
            "current_viewers": s.current_viewers,
            "is_recording_available": s.is_recording_available,
            "tags": s.tags.split(',') if s.tags else [],
        })
    return result


# ═══════════════════════════════════════════════════════════════
#  WEBSOCKET (kept from original)
# ═══════════════════════════════════════════════════════════════

@router.websocket("/api/live-sessions/ws")
async def live_websocket(websocket: WebSocket):
    db = SessionLocal()

    # 🔒 Accept first, then wait for auth message — keeps the token out of the URL/logs
    await websocket.accept()
    try:
        auth_msg_raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        auth_msg = json.loads(auth_msg_raw)
    except (asyncio.TimeoutError, json.JSONDecodeError, Exception) as e:
        logger.warning("Live WS auth failed: no/invalid auth message — %s", e)
        await websocket.close(code=4001, reason="Auth required")
        db.close()
        return

    token = auth_msg.get("token") if isinstance(auth_msg, dict) else None
    if not token:
        await websocket.close(code=4001, reason="Token missing")
        db.close()
        return

    user = get_user_from_token(token, db)
    if not user:
        await websocket.close(code=4001, reason="Invalid token")
        db.close()
        return

    # Already accepted above, so skip the accept inside the manager
    await live_manager.connect(websocket, user.id, accept=False)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            session_id = data.get("session_id")

            if action == "join_session" and session_id:
                live_manager.join_session(user.id, session_id)
                count = live_manager.get_viewer_count(session_id)
                await live_manager.broadcast_to_session(session_id, {
                    "event": "viewer_count",
                    "session_id": session_id,
                    "count": count
                })

            elif action == "leave_session" and session_id:
                live_manager.leave_session(user.id, session_id)
                count = live_manager.get_viewer_count(session_id)
                await live_manager.broadcast_to_session(session_id, {
                    "event": "viewer_count",
                    "session_id": session_id,
                    "count": count
                })
    except WebSocketDisconnect:
        logger.info(f"User {user.id} disconnected from Live WS")
    finally:
        sessions = [s_id for s_id, users in live_manager.session_viewers.items() if user.id in users]
        live_manager.disconnect(user.id)
        for s_id in sessions:
            count = live_manager.get_viewer_count(s_id)
            await live_manager.broadcast_to_session(s_id, {
                "event": "viewer_count",
                "session_id": s_id,
                "count": count
            })
        db.close()
