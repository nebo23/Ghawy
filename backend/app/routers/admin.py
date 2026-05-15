"""
Admin-only endpoints for manual operations like triggering recurring charges.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.routers.users import get_current_user
from app.services.recurring import run_recurring_charges

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/trigger-recurring")
async def trigger_recurring(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger recurring charges. Admin only."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")

    results = await run_recurring_charges(db)
    return results
