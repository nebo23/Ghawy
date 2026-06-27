from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy import func
from pydantic import BaseModel

from app.database import get_db
from app.models import Guest, GuestSession, User, SuggestedGuest
from app.routers.users import get_current_user, get_current_active_member
from app.services.file_service import save_avatar

router = APIRouter(prefix="/guests", tags=["Guest of Honors"])

# ─── SCHEMAS ───────────────────────────────────────────────────

class GuestSessionOut(BaseModel):
    id: int
    guest_id: int
    title: str
    description: Optional[str] = None
    session_date: datetime
    platform: Optional[str] = None
    session_url: Optional[str] = None
    attendees_count: int = 0
    rating: float = 0.0
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
    avatar_initials: Optional[str] = None
    avatar_color: Optional[str] = None
    category: Optional[str] = None
    is_featured: bool
    sessions_count: int = 0
    attendees_count: int = 0
    rating: float = 0.0
    sessions: List[GuestSessionOut] = []

    class Config:
        from_attributes = True

class SuggestGuestRequest(BaseModel):
    name: str
    reason: Optional[str] = None

class SuggestedGuestOut(BaseModel):
    id: int
    user_id: int
    name: str
    reason: Optional[str] = None
    created_at: datetime
    user_name: Optional[str] = None

    class Config:
        from_attributes = True

class GuestCreate(BaseModel):
    name: str
    title: str
    company: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    avatar_initials: Optional[str] = None
    avatar_color: Optional[str] = None
    category: Optional[str] = None
    is_featured: bool = False
    sessions_count: int = 0
    attendees_count: int = 0
    rating: float = 0.0

class SessionCreate(BaseModel):
    guest_id: int
    title: str
    description: Optional[str] = None
    session_date: datetime
    platform: Optional[str] = None
    session_url: Optional[str] = None
    status: str = "upcoming"
    attendees_count: int = 0
    rating: float = 0.0
    description: Optional[str] = None
    session_date: datetime
    platform: Optional[str] = None
    session_url: Optional[str] = None
    status: str = "upcoming"
    attendees_count: int = 0
    rating: float = 0.0

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
    total_attendees = db.query(func.sum(Guest.attendees_count)).scalar() or 0
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

@router.get("/sessions/", response_model=List[GuestSessionOut])
def list_sessions(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(GuestSession)
    if status:
        query = query.filter(GuestSession.status == status)
    
    # Order: upcoming first, then past
    if status == 'upcoming':
        query = query.order_by(GuestSession.session_date.asc())
    else:
        query = query.order_by(GuestSession.session_date.desc())
        
    sessions = query.all()
    result = []
    for s in sessions:
        out = GuestSessionOut.model_validate(s)
        out.guest_name = s.guest.name if s.guest else None
        out.guest_title = s.guest.title if s.guest else None
        result.append(out)
    return result

@router.get("/suggest", response_model=List[SuggestedGuestOut])
def get_suggested_guests(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_member)):
    if not getattr(current_user, 'is_owner', False):
        raise HTTPException(status_code=403, detail="Owners only")
    suggestions = db.query(SuggestedGuest).order_by(SuggestedGuest.created_at.desc()).all()
    res = []
    for s in suggestions:
        out = SuggestedGuestOut.model_validate(s)
        out.user_name = s.user.full_name if s.user else "Unknown"
        res.append(out)
    return res

@router.post("/suggest")
def suggest_guest(data: SuggestGuestRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_member)):
    sg = SuggestedGuest(
        user_id=current_user.id,
        name=data.name,
        reason=data.reason
    )
    db.add(sg)
    db.commit()
    return {"success": True, "message": "Thank you for the suggestion!"}

@router.delete("/suggest/{suggestion_id}")
def delete_suggested_guest(suggestion_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_member)):
    if not getattr(current_user, 'is_owner', False):
        raise HTTPException(status_code=403, detail="Owners only")
    sg = db.query(SuggestedGuest).filter(SuggestedGuest.id == suggestion_id).first()
    if not sg:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    db.delete(sg)
    db.commit()
    return {"success": True}

@router.get("/{guest_id}", response_model=GuestOut)
def get_guest(guest_id: int, db: Session = Depends(get_db)):
    guest = db.query(Guest).filter(Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    return guest

@router.post("/upload-avatar")
async def upload_guest_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_member)
):
    if not getattr(current_user, 'is_owner', False):
        raise HTTPException(status_code=403, detail="Owners only")
    try:
        url = await save_avatar(file)
        return {"avatar_url": url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Admin Routes
@router.post("/")
def create_guest(data: GuestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_member)):
    if not getattr(current_user, 'is_owner', False):
        raise HTTPException(status_code=403, detail="Owners only")
    
    guest = Guest(**data.model_dump())
    db.add(guest)
    db.commit()
    db.refresh(guest)
    return guest

@router.put("/{guest_id}")
def update_guest(guest_id: int, data: GuestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_member)):
    if not getattr(current_user, 'is_owner', False):
        raise HTTPException(status_code=403, detail="Owners only")
        
    guest = db.query(Guest).filter(Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
        
    for key, value in data.model_dump().items():
        setattr(guest, key, value)
        
    db.commit()
    db.refresh(guest)
    return guest

@router.delete("/{guest_id}")
def delete_guest(guest_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_member)):
    if not getattr(current_user, 'is_owner', False):
        raise HTTPException(status_code=403, detail="Owners only")
    guest = db.query(Guest).filter(Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    db.delete(guest)
    db.commit()
    return {"success": True}

@router.post("/sessions/")
def create_session(data: SessionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_member)):
    if not getattr(current_user, 'is_owner', False):
        raise HTTPException(status_code=403, detail="Owners only")
        
    guest = db.query(Guest).filter(Guest.id == data.guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
        
    session = GuestSession(**data.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

@router.put("/sessions/{session_id}")
def update_session(session_id: int, data: SessionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_member)):
    if not getattr(current_user, 'is_owner', False):
        raise HTTPException(status_code=403, detail="Owners only")
    session = db.query(GuestSession).filter(GuestSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if session.guest_id != data.guest_id:
        guest = db.query(Guest).filter(Guest.id == data.guest_id).first()
        if not guest:
            raise HTTPException(status_code=404, detail="Guest not found")
            
    for key, value in data.model_dump().items():
        setattr(session, key, value)
    db.commit()
    db.refresh(session)
    return session

@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_member)):
    if not getattr(current_user, 'is_owner', False):
        raise HTTPException(status_code=403, detail="Owners only")
    session = db.query(GuestSession).filter(GuestSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session)
    db.commit()
    return {"success": True}
