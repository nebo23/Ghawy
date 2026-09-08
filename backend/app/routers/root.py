"""The routes that used to live in main.py.

They were declared with `@app.…` directly on the FastAPI instance, which put
them outside `app/routers/` — the directory every permission sweep, every
route audit and every security pass in this project is scoped to. That is not
a tidiness point: the onboarding bypass survived a full review because
`PATCH /users/me/complete-onboarding` was not in any of the files being read.
A route nobody enumerates is a route nobody checks.

Paths are unchanged. The router carries no prefix, so `GET /` is still `GET /`
(the container healthcheck curls it) and every other path is byte-identical to
what it was on `@app`.

`DELETE /users/{user_id}` is deliberately NOT here. It was a second front door
to member deletion — `get_current_admin_user`, so any admin, with no
self-delete guard, no WebSocket disconnect and none of the seven cleanups for
tables that lack ON DELETE CASCADE. `admin.py` has the real one:
`require_owner`, with the comment "admins cannot delete members", and all of
that cleanup. Two routes for one action meant a commented owner-only decision
was bypassable by changing the URL, and the bypass also left orphans behind.
Nothing in the frontend ever called it. There is one door now, in admin.py.
"""
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Payment
from app.routers.users import get_current_user, get_current_admin_user
from app.routers.profile import needs_arabic_name
from app.services.name_utils import ARABIC_NAME_MESSAGE

import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Root"])


@router.get("/")
def root():
    return {"message": "Community API Is Working"}


@router.delete("/payments/{payment_id}")
def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),  # 🔒 admin auth + audit log
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    logger.warning(
        "🗑️ ADMIN DELETE PAYMENT | admin_id=%s admin_email=%s | payment_id=%s amount=%s currency=%s user_id=%s",
        current_user.id, current_user.email, payment.id, payment.amount, payment.currency, payment.user_id
    )
    db.delete(payment)
    db.commit()
    return {"message": "Payment deleted successfully"}


@router.patch("/users/me/complete-onboarding")
def complete_onboarding_patch(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """يرفع علامة إنهاء الأونبوردنج — بنفس شرط الخطوة اللي بتسأل عن الاسم.

    العلامة دي هي اللي الحارس في `utils.js` بيقرأها؛ عضو عليها بيدخل المنصة.
    فالباب ده كان بيلغي قاعدة الاسم العربي كلها: `POST /profile/complete-
    onboarding` يرفض `Nabil Ahmed` بـ422، وبعدين نداء واحد هنا يرفع العلامة
    ويدخل نفس العضو بنفس الاسم اللاتيني من غير ما حد يسأله. الشرط بيتسأل من
    `needs_arabic_name` نفسها اللي الخطوة بتستعملها، مش من نسخة تانية منه.

    اللي مش مطلوب منه اسم عربي — اسمه عربي أصلاً أو علّم «اسمي مش بالعربي» —
    بيعدّي زي ما كان بالظبط. والفرونت بينادي الباب ده بعد ما البوست ينجح، يعني
    الاسم يبقى اتظبط خلاص قبل ما نوصل هنا.
    """
    if needs_arabic_name(current_user):
        raise HTTPException(status_code=422, detail=ARABIC_NAME_MESSAGE)
    current_user.onboarding_completed = True
    db.commit()
    return {"message": "onboarding completed"}


@router.get("/config/payment-info")
def get_payment_info():
    """Public endpoint to get payment details for manual flow."""
    return {
        "instapay_number": os.getenv("INSTAPAY_NUMBER", "xxxx"),
        # The second manual rail. Same contract as the Instapay value above:
        # the page ships with the real number hardcoded and only swaps it out
        # when this env var carries something other than the placeholder, so a
        # missing variable can never blank the number a payer needs.
        "vodafone_cash_number": os.getenv("VODAFONE_CASH_NUMBER", "xxxx"),
        "subscription_price": os.getenv("SUBSCRIPTION_PRICE", "600"),
        "currency": "EGP"
    }
