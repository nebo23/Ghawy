import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import SessionLocal
from app.models import User, LiveSession, SessionBooking, SessionReminder, LiveSessionStatus
from app.routers.ws import get_user_from_token
from app.services.live_manager import live_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/live-sessions", tags=["Live Sessions"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(get_user_from_token)):
    # This is a placeholder since the app uses websockets with tokens in URL, 
    # but for API we should use the standard Authorization header.
    # We will assume a standard dependency exists. Let's create one.
    pass

from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_current_user_api(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from app.routers.ws import get_user_from_token
    user = get_user_from_token(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return user


@router.get("")
def get_live_sessions(status_filter: Optional[str] = None, db: Session = Depends(get_db)):
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
        instructor = db.query(User).filter(User.id == s.instructor_id).first()
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
            "status": s.status.value,
            "difficulty": s.difficulty.value,
            "start_time": s.start_time.isoformat(),
            "end_time": s.end_time.isoformat(),
            "max_attendees": s.max_attendees,
            "current_viewers": s.current_viewers,
            "is_recording_available": s.is_recording_available,
            "tags": s.tags.split(',') if s.tags else []
        })
    return result

@router.get("/booked")
def get_booked_sessions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user_api)):
    bookings = db.query(SessionBooking).filter(SessionBooking.user_id == current_user.id).all()
    session_ids = [b.session_id for b in bookings]
    sessions = db.query(LiveSession).filter(LiveSession.id.in_(session_ids)).order_by(LiveSession.start_time).all()
    
    result = []
    for s in sessions:
        instructor = db.query(User).filter(User.id == s.instructor_id).first()
        result.append({
            "id": s.id,
            "title": s.title,
            "status": s.status.value,
            "start_time": s.start_time.isoformat(),
            "instructor_name": instructor.full_name if instructor else "Instructor",
            "thumbnail_url": s.thumbnail_url
        })
    return result

@router.post("/{session_id}/book")
def book_session(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_api)):
    session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if session.status != LiveSessionStatus.UPCOMING:
        raise HTTPException(status_code=400, detail="Can only book upcoming sessions")
        
    existing = db.query(SessionBooking).filter(
        SessionBooking.user_id == current_user.id,
        SessionBooking.session_id == session_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Already booked")
        
    booking = SessionBooking(user_id=current_user.id, session_id=session_id)
    db.add(booking)
    db.commit()
    return {"status": "success", "message": "Session booked successfully"}

@router.delete("/{session_id}/book")
def cancel_booking(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_api)):
    booking = db.query(SessionBooking).filter(
        SessionBooking.user_id == current_user.id,
        SessionBooking.session_id == session_id
    ).first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    db.delete(booking)
    db.commit()
    return {"status": "success", "message": "Booking cancelled"}

@router.post("/{session_id}/reminder")
def toggle_reminder(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_api)):
    session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    reminder = db.query(SessionReminder).filter(
        SessionReminder.user_id == current_user.id,
        SessionReminder.session_id == session_id
    ).first()
    
    if reminder:
        db.delete(reminder)
        db.commit()
        return {"status": "success", "message": "Reminder removed", "reminder_active": False}
    else:
        # Remind 15 minutes before
        from datetime import timedelta
        reminder_time = session.start_time - timedelta(minutes=15)
        new_reminder = SessionReminder(
            user_id=current_user.id,
            session_id=session_id,
            reminder_time=reminder_time
        )
        db.commit()
        return {"status": "success", "message": "Reminder set", "reminder_active": True}

@router.websocket("/ws/{token}")
async def live_websocket(websocket: WebSocket, token: str):
    db = SessionLocal()
    user = get_user_from_token(token, db)
    if not user:
        await websocket.close(code=4001, reason="Invalid token")
        db.close()
        return

    await live_manager.connect(websocket, user.id)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            session_id = data.get("session_id")
            
            if action == "join_session" and session_id:
                live_manager.join_session(user.id, session_id)
                # Broadcast new viewer count
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
        # User disconnected, but we need to know which session they were in to broadcast count decrease
        # The manager handles removal. We can broadcast updated counts for all sessions they were in
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

