# ══════════════════════════════════════════════════════════════
#  reports.py  —  backend/app/routers/reports.py
#  Daily Team Reports Router
# ══════════════════════════════════════════════════════════════

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field, validator
import httpx
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DailyReport, TeamRole, User
from app.routers.users import get_current_active_member, get_current_admin_user

router = APIRouter(prefix="/reports", tags=["Reports"])


# ─── Pydantic Schemas ─────────────────────────────────────────

class ReportCreate(BaseModel):
    """Body لإنشاء ريبورت جديد"""
    team_role: TeamRole
    what_went_well: str = Field(..., min_length=3, max_length=2000)
    what_can_improve: str = Field(..., min_length=3, max_length=2000)
    ai_updates_count: int = Field(default=0, ge=0)
    messages_replied_count: int = Field(default=0, ge=0)

    hours_worked: Optional[float] = None
    productivity: Optional[int] = Field(default=None, ge=0, le=10)
    community_posts_count: Optional[int] = Field(default=None, ge=0)
    members_welcomed_count: Optional[int] = Field(default=None, ge=0)
    wins_encouraged_count: Optional[int] = Field(default=None, ge=0)
    avg_reply_speed: Optional[str] = None
    platform_engagement: Optional[str] = None
    projects_reviewed_count: Optional[int] = Field(default=None, ge=0)
    projects_accepted_count: Optional[int] = Field(default=None, ge=0)
    projects_rejected_count: Optional[int] = Field(default=None, ge=0)
    workflows_resolved_count: Optional[int] = Field(default=None, ge=0)
    avg_resolution_time: Optional[str] = None

    @validator("what_went_well", "what_can_improve")
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("Field cannot be blank")
        return v.strip()


class ReportOut(BaseModel):
    """شكل الريبورت اللي بيتبعت للـ Frontend"""
    id: int
    user_id: int
    team_role: str
    what_went_well: str
    what_can_improve: str
    ai_updates_count: int
    messages_replied_count: int
    
    hours_worked: Optional[float] = None
    productivity: Optional[int] = None
    community_posts_count: Optional[int] = None
    members_welcomed_count: Optional[int] = None
    wins_encouraged_count: Optional[int] = None
    avg_reply_speed: Optional[str] = None
    platform_engagement: Optional[str] = None
    projects_reviewed_count: Optional[int] = None
    projects_accepted_count: Optional[int] = None
    projects_rejected_count: Optional[int] = None
    workflows_resolved_count: Optional[int] = None
    avg_resolution_time: Optional[str] = None

    report_date: date
    created_at: datetime
    # بيتضاف بس في admin endpoint
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    author_avatar: Optional[str] = None

    class Config:
        from_attributes = True


WEBHOOK_URL = "https://n8n-vrtt.srv1552612.hstgr.cloud/webhook/32d259c1-1902-44e6-8232-eada2e4f5598"

async def send_report_to_webhook(payload: dict):
    """إرسال الريبورت للـ n8n في الخلفية بصورة Async"""
    async with httpx.AsyncClient() as client:
        try:
            await client.post(WEBHOOK_URL, json=payload, timeout=10.0)
        except Exception as e:
            # لو حصل خطأ منتجاهله عشان ميفشلش حفظ الريبورت الأصلي
            print(f"Failed to send report to webhook: {e}")


# ─── Helper ────────────────────────────────────────────────────

def _serialize(report: DailyReport, include_author: bool = False) -> dict:
    """تحويل الـ model لـ dict بيرجع للـ frontend"""
    data = {
        "id": report.id,
        "user_id": report.user_id,
        "team_role": report.team_role.value if hasattr(report.team_role, "value") else str(report.team_role),
        "what_went_well": report.what_went_well,
        "what_can_improve": report.what_can_improve,
        "ai_updates_count": report.ai_updates_count,
        "messages_replied_count": report.messages_replied_count,
        
        "hours_worked": float(report.hours_worked) if report.hours_worked is not None else None,
        "productivity": report.productivity,
        "community_posts_count": report.community_posts_count,
        "members_welcomed_count": report.members_welcomed_count,
        "wins_encouraged_count": report.wins_encouraged_count,
        "avg_reply_speed": report.avg_reply_speed,
        "platform_engagement": report.platform_engagement,
        "projects_reviewed_count": report.projects_reviewed_count,
        "projects_accepted_count": report.projects_accepted_count,
        "projects_rejected_count": report.projects_rejected_count,
        "workflows_resolved_count": report.workflows_resolved_count,
        "avg_resolution_time": report.avg_resolution_time,

        "report_date": str(report.report_date),
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }
    if include_author and report.author:
        data["author_name"] = report.author.full_name
        data["author_email"] = report.author.email
        data["author_avatar"] = report.author.avatar_url or report.author.selected_avatar
    return data


# ─── Endpoints ─────────────────────────────────────────────────

@router.post("/", status_code=201)
def create_report(
    body: ReportCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """
    POST /reports/
    إنشاء ريبورت يومي جديد للمستخدم المسجل.
    ممكن يكتب أكتر من ريبورت في نفس اليوم.
    """
    # التحقق من الحقول المطلوبة لكل دور
    if body.team_role == TeamRole.COMMUNITY_MANAGER:
        required_fields = ["hours_worked", "productivity", "community_posts_count", "members_welcomed_count", "wins_encouraged_count", "avg_reply_speed", "platform_engagement"]
        for field in required_fields:
            if getattr(body, field) is None:
                raise HTTPException(status_code=400, detail=f"Field {field} is required for Community Manager")
    
    elif body.team_role == TeamRole.TECHNICAL_ENGINEER:
        required_fields = ["hours_worked", "productivity", "projects_reviewed_count", "projects_accepted_count", "projects_rejected_count", "workflows_resolved_count", "avg_resolution_time"]
        for field in required_fields:
            if getattr(body, field) is None:
                raise HTTPException(status_code=400, detail=f"Field {field} is required for Technical Engineer")

    today = date.today()

    report = DailyReport(
        user_id=current_user.id,
        team_role=body.team_role,
        what_went_well=body.what_went_well,
        what_can_improve=body.what_can_improve,
        ai_updates_count=body.ai_updates_count,
        messages_replied_count=body.messages_replied_count,
        
        hours_worked=body.hours_worked,
        productivity=body.productivity,
        community_posts_count=body.community_posts_count,
        members_welcomed_count=body.members_welcomed_count,
        wins_encouraged_count=body.wins_encouraged_count,
        avg_reply_speed=body.avg_reply_speed,
        platform_engagement=body.platform_engagement,
        projects_reviewed_count=body.projects_reviewed_count,
        projects_accepted_count=body.projects_accepted_count,
        projects_rejected_count=body.projects_rejected_count,
        workflows_resolved_count=body.workflows_resolved_count,
        avg_resolution_time=body.avg_resolution_time,

        report_date=today,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # تجهيز الـ payload عشان نبعته للـ webhook
    payload = {
        "role": report.team_role.value if hasattr(report.team_role, "value") else str(report.team_role),
        "submitted_by": current_user.full_name,
        "submitted_at": datetime.now().isoformat(),
        "what_went_well": report.what_went_well,
        "what_can_improve": report.what_can_improve,
    }

    if body.team_role == TeamRole.COMMUNITY_MANAGER:
        payload.update({
            "work_hours": float(report.hours_worked) if report.hours_worked is not None else None,
            "productivity": report.productivity,
            "ai_updates_count": report.ai_updates_count,
            "community_posts": report.community_posts_count,
            "replies_count": report.messages_replied_count,
            "welcome_count": report.members_welcomed_count,
            "wins_encouraged": report.wins_encouraged_count,
            "avg_response_time": report.avg_reply_speed,
            "engagement_level": report.platform_engagement,
        })
    elif body.team_role == TeamRole.TECHNICAL_ENGINEER:
        payload.update({
            "work_hours": float(report.hours_worked) if report.hours_worked is not None else None,
            "productivity": report.productivity,
            "projects_reviewed": report.projects_reviewed_count,
            "projects_accepted": report.projects_accepted_count,
            "projects_rejected": report.projects_rejected_count,
            "workflows_solved": report.workflows_resolved_count,
            "replies_count": report.messages_replied_count,
            "avg_resolution_time": report.avg_resolution_time,
        })
    elif body.team_role == TeamRole.CUSTOMER_SUCCESS:
        payload.update({
            "ai_updates_count": report.ai_updates_count,
            "replies_count": report.messages_replied_count,
        })

    # استبعاد الحقول اللي قيمتها None
    filtered_payload = {k: v for k, v in payload.items() if v is not None}

    # إضافة مهمة الـ webhook في الـ background عشان متبطأش الـ response
    background_tasks.add_task(send_report_to_webhook, filtered_payload)

    return _serialize(report)


@router.get("/my")
def my_reports(
    report_date: Optional[str] = Query(None, description="YYYY-MM-DD — فلتر بتاريخ معين"),
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """
    GET /reports/my
    ريبورتات المستخدم الحالي، مرتبة من الأحدث للأقدم.
    Optional filter: ?report_date=2026-06-12
    """
    query = db.query(DailyReport).filter(DailyReport.user_id == current_user.id)

    if report_date:
        try:
            parsed = date.fromisoformat(report_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")
        query = query.filter(DailyReport.report_date == parsed)

    reports = query.order_by(DailyReport.created_at.desc()).all()
    return [_serialize(r) for r in reports]


@router.get("/admin")
def admin_reports(
    role: Optional[str] = Query(None, description="community_manager | technical_engineer | customer_success"),
    report_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    user_id: Optional[int] = Query(None, description="فلتر بـ user_id معين"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    GET /reports/admin
    كل الريبورتات — للـ Admin فقط.
    فلاتر اختيارية: role, report_date, user_id
    """
    query = db.query(DailyReport).join(User, DailyReport.user_id == User.id)

    # فلتر بالدور
    if role and role != "all":
        valid_roles = {r.value for r in TeamRole}
        if role not in valid_roles:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role. Valid values: {', '.join(valid_roles)}"
            )
        query = query.filter(DailyReport.team_role == TeamRole(role))

    # فلتر بالتاريخ
    if report_date:
        try:
            parsed = date.fromisoformat(report_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")
        query = query.filter(DailyReport.report_date == parsed)

    # فلتر بالمستخدم
    if user_id:
        query = query.filter(DailyReport.user_id == user_id)

    reports = (
        query
        .order_by(DailyReport.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_serialize(r, include_author=True) for r in reports]
