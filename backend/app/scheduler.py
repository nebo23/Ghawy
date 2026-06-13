"""
APScheduler daily jobs:
 - Check for expired subscriptions and deactivate users
 - Send renewal reminders 2 days before expiration
"""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import SessionLocal
from app.models import User, Payment, PaymentStatus

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Africa/Cairo")


# ─── Deactivate Expired Subscriptions ──────────────────────
# @scheduler.scheduled_job("cron", hour=9, minute=0)
@scheduler.scheduled_job("interval", minutes=2)
async def daily_subscription_check_job():
    """Runs every day at 9:00 AM Cairo time."""
    logger.info("⏰ Scheduler: Starting daily subscription check...")
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        expired_users = db.query(User).filter(
            User.is_active == True,
            User.end_at.isnot(None),
            User.end_at <= now
        ).all()
        
        count = 0
        for user in expired_users:
            user.is_active = False
            count += 1
            logger.info("🚫 Deactivated user_id=%s due to expired subscription", user.id)
            
        db.commit()
        logger.info("⏰ Scheduler done: deactivated %s users", count)
    except Exception as e:
        logger.error("💥 Scheduler error: %s", e)
    finally:
        db.close()


# ─── Renewal Reminder (2 days before expiry) ──────────────
# @scheduler.scheduled_job("cron", hour=9, minute=0, id="renewal_reminder")
@scheduler.scheduled_job("interval", minutes=2, id="renewal_reminder")
async def check_expiring_subscriptions():
    """
    بيدور على المستخدمين اللي اشتراكهم هينتهي خلال يومين ويبعتلهم إيميل
    """
    from app.services.email_service import send_renewal_reminder_email

    logger.info("📧 Scheduler: Checking for expiring subscriptions...")
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        # TESTING: Check for users expiring in the next 3 minutes
        target_date = now + timedelta(minutes=3)

        # بحث عن المستخدمين اللي end_at بتاعهم في خلال 3 دقايق

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

    except Exception as e:
        logger.error("💥 Renewal reminder error: %s", e)
    finally:
        db.close()
