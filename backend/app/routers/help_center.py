"""
Help Center Router — public-facing support team listing.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routers.users import get_current_active_member

router = APIRouter(prefix="/help-center", tags=["Help Center"])

# Fixed display order + the label shown in the Help Center. Each entry is
# matched to a real user by their `custom_title` (so name/avatar stay dynamic —
# changing them on the account updates the Help Center automatically).
SUPPORT_TEAM = [
    {"title": "CTO", "match_titles": ["CTO"]},
    {"title": "CEO", "match_titles": ["CEO"]},
    {"title": "Community Manager", "match_titles": ["Community Manager"]},
    {"title": "Technical Support", "match_titles": ["Technical Support", "Technical Engineer"]},
]


@router.get("/team")
def get_support_team(
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """
    Return the support team members in the fixed order
    CTO → CEO → Community Manager → Technical Support.
    Accessible to all logged-in members. Data is pulled from the DB.
    """
    team = []
    for role in SUPPORT_TEAM:
        user = (
            db.query(User)
            .filter(User.custom_title.in_(role["match_titles"]))
            .order_by(User.id)
            .first()
        )
        if not user:
            continue
        team.append({
            "id": user.id,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "title": role["title"],
        })
    return team
