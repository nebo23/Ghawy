"""
APScheduler daily jobs:
 - Check for expired subscriptions and deactivate users
 - Send renewal reminders 2 days before expiration
 - Send one-time winback email to users stuck at the last step for 24h+

⚠️ كل شغل الداتابيز والـ SMTP هنا لازم يحصل جوه asyncio.to_thread —
الـ jobs بتشتغل على نفس الـ event loop بتاع السيرفر كله، وأي انتظار
synchronous (زي pool checkout وقت الزحمة أو SMTP بطيء) بيجمّد الموقع بالكامل.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import extract
from app.database import SessionLocal
from app.models import User, Payment, PaymentStatus, UserCourseProgress

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Africa/Cairo")


# ─── Deactivate Expired Subscriptions ──────────────────────
def _deactivate_expired_users() -> list[int]:
    """Sync body — runs in a thread. Returns deactivated user ids."""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        expired_users = db.query(User).filter(
            User.is_active == True,
            User.end_at.isnot(None),
            User.end_at <= now
        ).all()

        deactivated_ids = []
        for user in expired_users:
            user.is_active = False
            deactivated_ids.append(user.id)
            logger.info("🚫 Deactivated user_id=%s due to expired subscription", user.id)

        db.commit()
        return deactivated_ids
    finally:
        db.close()


@scheduler.scheduled_job("cron", hour=9, minute=0)
async def daily_subscription_check_job():
    logger.info("⏰ Scheduler: Starting daily subscription check...")
    try:
        deactivated_ids = await asyncio.to_thread(_deactivate_expired_users)
        logger.info("⏰ Scheduler done: deactivated %s users", len(deactivated_ids))

        # Force-disconnect deactivated users from WebSocket in real-time
        if deactivated_ids:
            from app.services.ws_manager import manager as ws_manager
            for uid in deactivated_ids:
                await ws_manager.disconnect_user(uid)
                logger.info("⚡ Force-disconnected WS for user_id=%s", uid)
    except Exception as e:
        logger.error("💥 Scheduler error: %s", e)


# ─── Renewal Reminder (2 days before expiry) ──────────────
def _send_renewal_reminders() -> None:
    """Sync body — runs in a thread (DB + SMTP)."""
    from app.services.email_service import send_renewal_reminder_email

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        # Check for users expiring in the next 2 days
        target_date = now + timedelta(days=2)

        expiring_users = db.query(User).filter(
            User.is_active == True,
            User.end_at.isnot(None),
            User.end_at >= now,
            User.end_at <= target_date,
        ).all()

        logger.info("📧 Found %s expiring subscriptions", len(expiring_users))

        for user in expiring_users:
            try:
                # جيب آخر plan_key
                last_payment = db.query(Payment).filter(
                    Payment.user_id == user.id,
                    Payment.status == PaymentStatus.CONFIRMED
                ).order_by(Payment.created_at.desc()).first()

                plan_key = (last_payment.plan_key if last_payment and last_payment.plan_key else None) or "monthly_egp"
                days_left = max(0, (user.end_at - now).days)

                send_renewal_reminder_email(
                    to_email=user.email,
                    full_name=user.full_name,
                    days_left=days_left,
                    plan_key=plan_key,
                    subscription_end=user.end_at
                )
                logger.info("✅ Reminder sent to %s — %s days left", user.email, days_left)

            except Exception as e:
                logger.error("❌ Failed to send reminder to %s: %s", user.email, e)
    finally:
        db.close()


@scheduler.scheduled_job("cron", hour=9, minute=0, id="renewal_reminder")
async def check_expiring_subscriptions():
    """
    بيدور على المستخدمين اللي اشتراكهم هينتهي خلال يومين ويبعتلهم إيميل
    """
    logger.info("📧 Scheduler: Checking for expiring subscriptions...")
    try:
        await asyncio.to_thread(_send_renewal_reminders)
    except Exception as e:
        logger.error("💥 Renewal reminder error: %s", e)


# ─── 5-Day Expiry Reminder (exactly 5 days before expiry) ──
def _send_5day_expiry_reminders() -> None:
    """Sync body — runs in a thread (DB + SMTP).
    بيبعت إيميل 'باقي 5 أيام' مرة واحدة لكل فترة اشتراك. الـ guard
    (expiry5_email_sent_for == end_at) بيمنع التكرار ويتصفّر تلقائياً مع
    التجديد لأن end_at بيتغير."""
    from app.services.email_service import send_5day_expiry_email

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        # نافذة "باقي 5 أيام": ينتهي بعد 4 لـ 5 أيام من دلوقتي
        window_lo = now + timedelta(days=4)
        window_hi = now + timedelta(days=5)

        candidates = db.query(User).filter(
            User.is_active == True,
            User.end_at.isnot(None),
            User.end_at > window_lo,
            User.end_at <= window_hi,
            User.email.isnot(None),
        ).all()

        logger.info("📧 Found %s subscriptions ~5 days from expiry", len(candidates))
        sent = 0
        for user in candidates:
            # متبعتش تاني لنفس فترة الاشتراك (نفس end_at)
            if (user.expiry5_email_sent_for is not None and user.end_at is not None
                    and abs((user.expiry5_email_sent_for - user.end_at).total_seconds()) < 60):
                continue
            try:
                send_5day_expiry_email(user.email, user.full_name)
                user.expiry5_email_sent_for = user.end_at
                db.commit()  # commit لكل واحد عشان لو حصل crash ميتبعتش تاني
                sent += 1
                time.sleep(0.5)  # مهلة صغيرة بين الإيميلات عشان Gmail
            except Exception as e:
                db.rollback()
                logger.error("❌ 5-day expiry email failed for %s: %s", user.email, e)

        logger.info("📧 5-day expiry done: sent %s/%s", sent, len(candidates))
    finally:
        db.close()


@scheduler.scheduled_job("cron", hour=9, minute=15, id="expiry_5day_reminder")
async def check_5day_expiry():
    """بيدور يومياً على اللي باقي على اشتراكهم 5 أيام ويبعتلهم تنبيه — مرة واحدة."""
    logger.info("📧 Scheduler: Checking for 5-day expiry reminders...")
    try:
        await asyncio.to_thread(_send_5day_expiry_reminders)
    except Exception as e:
        logger.error("💥 5-day expiry reminder error: %s", e)


# ─── Birthday Email (هدية 7 أيام) ─────────────────────────
def _send_birthday_emails() -> None:
    """Sync body — runs in a thread (DB + SMTP).
    بيبعت تهنئة عيد ميلاد + هدية 7 أيام للمشتركين اللي عيد ميلادهم النهاردة —
    مرة واحدة في السنة (guard: birthday_email_sent_year). بنبعت بس للي عندهم
    اشتراك مدفوع قبل كده (عشان الهدية 'على الباقة الحالية')."""
    from app.services.email_service import send_birthday_email

    db = SessionLocal()
    try:
        today = datetime.now(timezone.utc).astimezone().date()
        year = today.year

        paid_user_ids = db.query(Payment.user_id).filter(
            Payment.status == PaymentStatus.CONFIRMED
        )

        candidates = db.query(User).filter(
            User.birth_date.isnot(None),
            extract("month", User.birth_date) == today.month,
            extract("day", User.birth_date) == today.day,
            User.email.isnot(None),
            (User.birthday_email_sent_year.is_(None)) | (User.birthday_email_sent_year != year),
            User.id.in_(paid_user_ids),
        ).all()

        logger.info("🎂 Found %s birthday(s) today", len(candidates))
        sent = 0
        for user in candidates:
            try:
                age = year - user.birth_date.year
                send_birthday_email(
                    to_email=user.email,
                    full_name=user.full_name,
                    age=age if age > 0 else 0,
                    user_id=user.id,
                    year=year,
                )
                user.birthday_email_sent_year = year
                db.commit()  # commit لكل واحد عشان لو حصل crash ميتبعتش تاني
                sent += 1
                time.sleep(0.5)  # مهلة صغيرة بين الإيميلات عشان Gmail
            except Exception as e:
                db.rollback()
                logger.error("❌ Birthday email failed for %s: %s", user.email, e)

        logger.info("🎂 Birthday emails done: sent %s/%s", sent, len(candidates))
    finally:
        db.close()


@scheduler.scheduled_job("cron", hour=9, minute=30, id="birthday_email")
async def check_birthdays():
    """بيدور يومياً على أعياد ميلاد النهاردة ويبعت تهنئة + هدية 7 أيام."""
    logger.info("🎂 Scheduler: Checking for birthdays...")
    try:
        await asyncio.to_thread(_send_birthday_emails)
    except Exception as e:
        logger.error("💥 Birthday email error: %s", e)


# ─── 6-Day Inactivity Nudge ("افتكر اللي بدأت عشانه") ─────
INACTIVE_DAYS = 6
INACTIVE_BATCH_SIZE = 40


def _send_inactive_6day_emails() -> None:
    """Sync body — runs in a thread (DB + SMTP).
    بيبعت تذكير للمشتركين النشطين اللي آخر دخول ليهم (last_seen) بقاله أكتر
    من 6 أيام. الـ guard (inactive6_email_sent_at) بيمنع التكرار في نفس
    فترة الغياب، وبيتصفّر ضمنياً لما اليوزر يرجع (last_seen يبقى أحدث من
    تاريخ الإرسال)، فأي فترة غياب جديدة بتتبعت مرة واحدة."""
    from app.services.email_service import send_inactive_6day_email

    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai").rstrip("/")
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        cutoff = now - timedelta(days=INACTIVE_DAYS)

        candidates = db.query(User).filter(
            User.is_active == True,
            User.email.isnot(None),
            User.last_seen.isnot(None),
            User.last_seen <= cutoff,
            # اتبعتش قبل كده في نفس فترة الغياب دي
            (User.inactive6_email_sent_at.is_(None))
            | (User.inactive6_email_sent_at < User.last_seen),
        ).order_by(User.last_seen.asc()).limit(INACTIVE_BATCH_SIZE).all()

        logger.info("😴 Found %s inactive (6d+) subscribers", len(candidates))
        sent = 0
        for user in candidates:
            try:
                # deep link لآخر كورس اتفتح، وإلا الداشبورد
                last_course = db.query(UserCourseProgress).filter(
                    UserCourseProgress.user_id == user.id
                ).order_by(UserCourseProgress.last_accessed.desc()).first()
                resume_url = (
                    f"{frontend_url}/course-detail.html?id={last_course.course_id}"
                    if last_course else f"{frontend_url}/dashboard.html"
                )

                send_inactive_6day_email(user.email, user.full_name, resume_url)
                user.inactive6_email_sent_at = datetime.utcnow()
                db.commit()  # commit لكل واحد عشان لو حصل crash ميتبعتش تاني
                sent += 1
                time.sleep(0.5)  # مهلة صغيرة بين الإيميلات عشان Gmail
            except Exception as e:
                db.rollback()
                logger.error("❌ Inactive-6d email failed for %s: %s", user.email, e)

        logger.info("😴 Inactive-6d done: sent %s/%s", sent, len(candidates))
    finally:
        db.close()


@scheduler.scheduled_job("cron", hour=9, minute=45, id="inactive_6day")
async def check_inactive_6day():
    """بيدور يومياً على المشتركين اللي غابوا 6 أيام+ ويبعتلهم تذكير يرجعوا."""
    logger.info("😴 Scheduler: Checking for 6-day inactive subscribers...")
    try:
        await asyncio.to_thread(_send_inactive_6day_emails)
    except Exception as e:
        logger.error("💥 Inactive-6d error: %s", e)


# ─── Winback Email (registered but never activated, 24h+) ──
# اللي اتعمل قبل الحد ده عمره ما هيوصله الإيميل (قرار الإطلاق: آخر 5 أيام بس)
WINBACK_MIN_CREATED_AT = datetime(2026, 7, 3)
# دفعة صغيرة عشان Gmail بيقفل الاتصال لو بعتنا كتير ورا بعض
WINBACK_BATCH_SIZE = 30


def _send_winback_batch() -> None:
    """Sync body — runs in a thread (DB + SMTP)."""
    from app.services.email_service import send_winback_email

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        cutoff_24h = now - timedelta(hours=24)

        paid_user_ids = db.query(Payment.user_id).filter(
            Payment.status == PaymentStatus.CONFIRMED
        )

        candidates = db.query(User).filter(
            User.is_active == False,
            User.winback_email_sent_at.is_(None),
            User.email.isnot(None),
            User.created_at <= cutoff_24h,
            User.created_at >= WINBACK_MIN_CREATED_AT,
            ~User.id.in_(paid_user_ids),
        ).order_by(User.created_at.asc()).limit(WINBACK_BATCH_SIZE).all()

        if not candidates:
            return

        logger.info("💌 Found %s winback candidates", len(candidates))
        sent = 0
        for user in candidates:
            try:
                send_winback_email(user.email, user.full_name, user.governorate)
                user.winback_email_sent_at = datetime.utcnow()
                db.commit()  # commit لكل واحد عشان لو حصل crash ميتبعتش تاني
                sent += 1
                time.sleep(0.5)  # مهلة صغيرة بين الإيميلات عشان Gmail
            except Exception as e:
                db.rollback()
                logger.error("❌ Winback email failed for %s: %s", user.email, e)

        logger.info("💌 Winback done: sent %s/%s emails", sent, len(candidates))
    finally:
        db.close()


# gunicorn بيعمل restart للـ worker كل شوية (max_requests) فالعدّاد بيتصفّر —
# لازم أول تشغيلة تبقى قريبة من الإقلاع وإلا الـ job عمرها ما هتشتغل
@scheduler.scheduled_job(
    "interval",
    minutes=10,
    id="winback_email",
    next_run_time=datetime.now(timezone.utc) + timedelta(seconds=120),
)
async def send_winback_emails():
    """
    بيدور على اللي سجلوا وعدّى عليهم 24 ساعة من غير ما يتفعلوا (مدفعوش)
    ويبعتلهم إيميل شخصي من محمد — مرة واحدة بس لكل شخص.
    """
    logger.info("💌 Scheduler: Checking for winback candidates...")
    try:
        await asyncio.to_thread(_send_winback_batch)
    except Exception as e:
        logger.error("💥 Winback scheduler error: %s", e)
