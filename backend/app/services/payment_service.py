"""
Shared Kashier payment confirmation logic.

Both the server-to-server webhook (`/webhooks/kashier`) and the browser
success redirect (`/payment/kashier/success`) funnel through
`confirm_kashier_payment` so a confirmation is applied exactly once,
no matter which signal arrives first.
"""
import os
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.orm import Session

from app.models import Payment, PaymentStatus, User

logger = logging.getLogger(__name__)

# Egypt timezone — handles DST automatically (UTC+2 winter / UTC+3 summer)
CAIRO_TZ = ZoneInfo("Africa/Cairo")


def to_cairo_iso(dt):
    """Convert a naive-UTC datetime to an Egypt-local ISO 8601 string (with offset).

    The backend stores naive UTC timestamps; the n8n automation expects Egypt
    wall-clock time, so we attach UTC then shift to Africa/Cairo.
    """
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CAIRO_TZ).isoformat()


def plan_duration(plan_key: str):
    """Map a plan_key to (days, duration_type)."""
    days, duration_type = 30, "1_month"
    if plan_key:
        if "yearly" in plan_key:
            days, duration_type = 365, "1_year"
        elif "quarterly" in plan_key:
            days, duration_type = 90, "3_months"
    return days, duration_type


async def send_payment_n8n_webhook(payload: dict):
    """Notify the N8N payment automation. Best-effort, never raises."""
    webhook_url = os.getenv("N8N_PAYMENT_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("⚠️ N8N_PAYMENT_WEBHOOK_URL not configured — skipping notification")
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json=payload, timeout=10.0)
            logger.info("✅ Successfully sent payment webhook to N8N")
    except Exception as e:
        logger.error("❌ Failed to send N8N payment webhook: %s", e)


def _build_n8n_payload(user, payment: Payment, duration_type: str, transaction_id: str = ""):
    return {
        "user_id": user.id if user else payment.user_id,
        "user_name": getattr(user, "full_name", "") if user else "",
        "user_email": getattr(user, "email", "") if user else "",
        "user_phone": getattr(user, "phone", "") if user else "",
        "amount": float(payment.amount) if payment.amount else 0.0,
        "currency": payment.currency,
        "order_id": payment.provider_order_id,
        "transaction_id": transaction_id or "",
        "payment_status": "success",
        "payment_method": "kashier",
        "paid_at": to_cairo_iso(payment.confirmed_at or datetime.utcnow()),
        "subscription_duration": duration_type,
    }


def _invoice_number(payment: Payment) -> str:
    """رقم فاتورة ثابت ومتفرّد لكل عملية: GHW-<سنة الدفع>-<id الدفعة>.

    مبني على الـ primary key بتاع الـ payment، يعني متكرّرش أبداً ولا محتاج
    عدّاد تاني يتزنق مع نفسه. ولو نفس الفاتورة اتبعتت تاني لأي سبب، هتطلع
    بنفس الرقم بالظبط — وده المقصود.
    """
    year = (payment.confirmed_at or datetime.utcnow()).year
    return f"GHW-{year}-{payment.id:06d}"


def _pricing_details(db: Session, payment: Payment) -> dict:
    """سعر الباقة الأصلي والخصم اللي العميل خده فعلاً على الأوردر ده.

    مصدرين، بالترتيب:

      1. صف الـ CouponRedemption المربوط بالدفعة دي — ده المصدر الدقيق: فيه
         السعر قبل وبعد الخصم زي ما اتحسبوا وقت الشراء نفسه، واسم الكوبون.

      2. لو مفيش صف مربوط: سعر الباقة من PLAN_PRICES مقابل المدفوع فعلاً.
         الحالة دي بتحصل بجد — لو العضو فتح أوردر بكوبون وساب صفحة الدفع
         وفتح أوردر تاني، reserve_redemption بتحدّث نفس الصف بدل ما تعمل
         جديد، فالـ payment_id بتاعه بيفضل مأشّر على الأوردر القديم المهجور.
         ساعتها الحساب نفسه مؤكد (السعر المعلن ناقص المدفوع)، اللي مش مؤكد هو
         اسم الكوبون — فبندوّر عليه بأقرب صف للعضو بنفس السعر النهائي، ولو
         ملقيناش بنكتب الخصم من غير اسم بدل ما نخمّن اسم غلط.

    من غير الجزء ده كانت فاتورة كل حد دفع بخصم هتقول "سعر الباقة 540" —
    صح حسابياً بس بتخفي إن هو أصلاً خد خصم.
    """
    amount = float(payment.amount or 0)
    try:
        from app.models import CouponRedemption

        redemption = db.query(CouponRedemption).filter(
            CouponRedemption.payment_id == payment.id
        ).first()
        if redemption and redemption.coupon:
            original = float(redemption.original_amount or 0)
            final = float(redemption.final_amount or 0)
            return {
                "original_amount": original or amount,
                "discount_amount": max(original - final, 0),
                "coupon_code": redemption.coupon.label,
                "coupon_percent": float(redemption.coupon.discount_percent or 0),
            }

        from app.routers.payment import PLAN_PRICES  # lazy: payment.py بيستورد الملف ده

        plan = PLAN_PRICES.get(payment.plan_key or "")
        if not plan:
            return {}
        list_price = float(plan["amount"])
        if amount >= list_price:
            return {}

        # الخصم أكيد؛ اسم الكوبون هو اللي بندوّر عليه.
        orphan = db.query(CouponRedemption).filter(
            CouponRedemption.user_id == payment.user_id,
            CouponRedemption.plan_key == payment.plan_key,
            CouponRedemption.final_amount == payment.amount,
        ).order_by(CouponRedemption.id.desc()).first()
        details = {
            "original_amount": list_price,
            "discount_amount": list_price - amount,
        }
        if orphan and orphan.coupon:
            details["coupon_code"] = orphan.coupon.label
            details["coupon_percent"] = float(orphan.coupon.discount_percent or 0)
        return details
    except Exception as exc:
        logger.warning("⚠️ Could not read pricing details for payment %s: %s", payment.id, exc)
        return {}


def _build_invoice(db: Session, user, payment: Payment, days: int, duration_type: str,
                   gateway_details: dict = None) -> dict:
    """كل بيانات الفاتورة في dict عادي (مش ORM objects).

    الفاتورة بتتبعت في BackgroundTask بعد ما الـ request تخلص والـ session تقفل،
    فأي attribute بيتقرا من user/payment لازم يتقرا هنا وهو لسه في إيده.
    """
    amount = float(payment.amount or 0)
    pricing = _pricing_details(db, payment)
    return {
        "invoice_number": _invoice_number(payment),
        "order_id": payment.provider_order_id,
        "plan_key": payment.plan_key,
        "duration_type": duration_type,
        "days": days,
        "amount": amount,
        # من غير كوبون، سعر الباقة هو المدفوع نفسه.
        "original_amount": pricing.get("original_amount", amount),
        "discount_amount": pricing.get("discount_amount", 0),
        "coupon_code": pricing.get("coupon_code"),
        "coupon_percent": pricing.get("coupon_percent"),
        "currency": payment.currency or "EGP",
        "paid_at": payment.confirmed_at or datetime.utcnow(),
        "subscription_end": getattr(user, "end_at", None) if user else None,
        "user_id": user.id if user else payment.user_id,
        "user_name": getattr(user, "full_name", "") if user else "",
        "user_email": getattr(user, "email", "") if user else "",
        "user_phone": getattr(user, "phone", "") if user else "",
        "user_country": getattr(user, "country", "") if user else "",
        "user_governorate": getattr(user, "governorate", "") if user else "",
        "gateway": gateway_details or {},
    }


def send_payment_invoice(invoice: dict):
    """يبعت الفاتورة. best-effort زي إشعار n8n — الدفع اتأكّد والاشتراك اتفعّل
    خلاص قبل ما نوصل هنا، فمفيش سبب إن فشل SMTP يرجّع 500 لكاشير ويخلّيه
    يبعت الـ webhook تاني."""
    try:
        from app.services.email_service import send_payment_invoice_email
        send_payment_invoice_email(invoice)
        logger.info("🧾 Invoice %s emailed to %s", invoice.get("invoice_number"), invoice.get("user_email"))
    except Exception as exc:
        logger.error("❌ Failed to send invoice %s to %s: %s",
                     invoice.get("invoice_number"), invoice.get("user_email"), exc)


def _queue_invoice(db: Session, user, payment: Payment, days: int, duration_type: str,
                   gateway_details: dict, background_tasks=None) -> None:
    """يجهّز الفاتورة ويحطها في طابور الإرسال — ومبيرميش حاجة أبداً.

    مش الإرسال بس اللي ممكن يقع: بناء الفاتورة نفسه بيقرا من الداتابيز
    (سعر الكوبون، وattributes اتعمَلها expire بعد الـ commit اللي فات). أي
    مشكلة هناك كانت هتطلع 500 لكاشير على عملية دفع **اتأكّدت واتفعّلت خلاص** —
    وده أسوأ نتيجة ممكنة: العضو دفع وأخد اشتراكه، وكاشير فاكر إن العملية فشلت.
    الفاتورة ورقة إثبات، مش شرط لإتمام الدفع.
    """
    try:
        invoice = _build_invoice(db, user, payment, days, duration_type, gateway_details)
    except Exception as exc:
        logger.error("❌ Could not build invoice for order %s: %s", payment.provider_order_id, exc)
        return

    if background_tasks is not None:
        background_tasks.add_task(send_payment_invoice, invoice)
    else:
        send_payment_invoice(invoice)


def confirm_kashier_payment(db: Session, payment: Payment, source: str,
                            background_tasks=None, transaction_id: str = "",
                            gateway_details: dict = None):
    """
    Idempotently confirm a Kashier payment and activate the user's subscription.

    Only a PENDING payment is acted on; calling again on an already-CONFIRMED
    payment is a no-op (so the webhook and the success redirect can't double-apply).

    Returns (user, newly_confirmed).
    """
    days, duration_type = plan_duration(payment.plan_key)
    user = db.query(User).filter(User.id == payment.user_id).first()

    if payment.status != PaymentStatus.PENDING:
        logger.info("ℹ️ Payment %s already %s — skipping (%s)",
                    payment.provider_order_id, payment.status, source)
        return user, False

    payment.status = PaymentStatus.CONFIRMED
    payment.confirmed_at = datetime.utcnow()

    # A coupon hold on this order becomes a spent slot now that the money has
    # actually arrived. Deliberately inside the same transaction as the status
    # change, so the two cannot end up disagreeing. It cannot raise and cannot
    # refuse — if the coupon filled up while the member was on the payment page
    # we honour the price they were quoted and log the overflow, because the
    # only outcome worse than a thirty-first discount is taking someone's money
    # and then not activating them.
    from app.services import coupon_service
    coupon_service.confirm_redemption(db, payment)

    if user:
        # Extends from the later of "now" or the current end date, so an early
        # renewal doesn't shorten an active subscription.
        from app.services.subscription_service import extend_subscription
        extend_subscription(user, days)

    db.commit()
    logger.info("✅ Payment CONFIRMED via %s | order=%s | user=%s",
                source, payment.provider_order_id, payment.user_id)

    # الفاتورة بتتبني هنا وهي جوه الـ session، وبتتبعت بعد ما الـ response يمشي.
    # مكانها هنا مقصود: ده المكان الوحيد اللي بيمرّ منه الـ webhook والـ redirect
    # الاتنين، وبيشتغل على PENDING بس — يعني فاتورة واحدة لكل عملية مهما وصلت
    # الإشارتين، ومن غير ما حد يفتكر ينده عليها في المسارين.
    gateway = dict(gateway_details or {})
    # transaction_id بييجي كـ argument منفصل من زمان (قبل gateway_details)، فبنسيبه
    # يكسب لو مبعوت — بس من غير ما string فاضية تمسح واحدة جاية من الـ payload.
    if transaction_id or not gateway.get("transaction_id"):
        gateway["transaction_id"] = transaction_id or gateway.get("transaction_id", "")

    if background_tasks is not None:
        payload = _build_n8n_payload(user, payment, duration_type, transaction_id)
        background_tasks.add_task(send_payment_n8n_webhook, payload)

    # لازم تكون بعد الـ commit وجوه الـ session — بتقرا سعر الكوبون وتاريخ
    # نهاية الاشتراك الجديد. ومكانها هنا معناه فاتورة واحدة لكل عملية: ده
    # المكان الوحيد اللي بيعدّي منه الـ webhook والـ redirect الاتنين، وبيشتغل
    # على PENDING بس.
    _queue_invoice(db, user, payment, days, duration_type, gateway, background_tasks)

    return user, True
