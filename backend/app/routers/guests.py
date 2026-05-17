from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy import func
from pydantic import BaseModel

from app.database import get_db
from app.models import Guest, GuestSession, User
from app.routers.users import get_current_user

router = APIRouter(prefix="/guests", tags=["Guest of Honors"])

# ─── SCHEMAS ───────────────────────────────────────────────────

class GuestSessionOut(BaseModel):
    id: int
    guest_id: int
    title: str
    description: Optional[str] = None
    session_date: datetime
    duration_minutes: int
    video_url: Optional[str] = None
    attendees: int
    status: str
    guest_name: Optional[str] = None
    guest_title: Optional[str] = None

    class Config:
        from_attributes = True

class GuestOut(BaseModel):
    id: int
    name: str
    title: str
    company: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    company_logo: Optional[str] = None
    category: Optional[str] = None
    is_featured: bool
    total_sessions: int
    total_attendees: int
    rating: float
    sessions: List[GuestSessionOut] = []

    class Config:
        from_attributes = True

class SuggestGuestRequest(BaseModel):
    name: str
    reason: Optional[str] = None

class GuestCreate(BaseModel):
    name: str
    title: str
    company: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    company_logo: Optional[str] = None
    category: Optional[str] = None
    is_featured: bool = False

class SessionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    session_date: datetime
    duration_minutes: int = 60
    video_url: Optional[str] = None
    status: str = "upcoming"

# ─── ENDPOINTS ─────────────────────────────────────────────────

@router.get("/", response_model=List[GuestOut])
def list_guests(
    featured: Optional[bool] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Guest)
    if featured is not None:
        query = query.filter(Guest.is_featured == featured)
    if category and category != 'All Categories':
        query = query.filter(Guest.category == category)
    
    guests = query.all()
    return guests

@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total_guests = db.query(func.count(Guest.id)).scalar() or 0
    total_attendees = db.query(func.sum(Guest.total_attendees)).scalar() or 0
    avg_rating = db.query(func.avg(Guest.rating)).scalar() or 0.0
    
    # Sessions this month
    now = datetime.utcnow()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    sessions_this_month = db.query(func.count(GuestSession.id)).filter(GuestSession.session_date >= start_of_month).scalar() or 0
    
    return {
        "total_guests": total_guests,
        "sessions_this_month": sessions_this_month,
        "total_attendees": total_attendees,
        "avg_rating": round(float(avg_rating), 1)
    }

@router.get("/sessions/upcoming", response_model=List[GuestSessionOut])
def upcoming_sessions(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    sessions = (
        db.query(GuestSession)
        .filter(GuestSession.session_date >= now)
        .order_by(GuestSession.session_date.asc())
        .limit(10)
        .all()
    )
    
    result = []
    for s in sessions:
        out = GuestSessionOut.model_validate(s)
        out.guest_name = s.guest.name if s.guest else None
        out.guest_title = s.guest.title if s.guest else None
        result.append(out)
        
    return result

@router.get("/sessions/past", response_model=List[GuestSessionOut])
def past_sessions(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    sessions = (
        db.query(GuestSession)
        .filter(GuestSession.session_date < now)
        .order_by(GuestSession.session_date.desc())
        .limit(10)
        .all()
    )
    
    result = []
    for s in sessions:
        out = GuestSessionOut.model_validate(s)
        out.guest_name = s.guest.name if s.guest else None
        out.guest_title = s.guest.title if s.guest else None
        result.append(out)
        
    return result

@router.get("/{guest_id}", response_model=GuestOut)
def get_guest(guest_id: int, db: Session = Depends(get_db)):
    guest = db.query(Guest).filter(Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    return guest

@router.post("/suggest")
def suggest_guest(data: SuggestGuestRequest, current_user: User = Depends(get_current_user)):
    # In a real app, save this to a Suggestions table or send an email
    return {"success": True, "message": "Thank you for the suggestion!"}

# Admin Routes
@router.post("/")
def create_guest(data: GuestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    
    guest = Guest(**data.model_dump())
    db.add(guest)
    db.commit()
    db.refresh(guest)
    return guest

@router.put("/{guest_id}")
def update_guest(guest_id: int, data: GuestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
        
    guest = db.query(Guest).filter(Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
        
    for key, value in data.model_dump().items():
        setattr(guest, key, value)
        
    db.commit()
    db.refresh(guest)
    return guest

@router.post("/{guest_id}/sessions")
def create_session(guest_id: int, data: SessionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
        
    guest = db.query(Guest).filter(Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
        
    session = GuestSession(guest_id=guest_id, **data.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session
