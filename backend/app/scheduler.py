"""
APScheduler daily job — runs recurring charges at 9:00 AM Cairo time.
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import SessionLocal
from app.services.recurring import run_recurring_charges

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Africa/Cairo")


@scheduler.scheduled_job("cron", hour=9, minute=0)
async def daily_recurring_job():
    """Runs every day at 9:00 AM Cairo time."""
    logger.info("⏰ Scheduler: Starting daily recurring charge check...")
    db = SessionLocal()
    try:
        results = await run_recurring_charges(db)
        logger.info("⏰ Scheduler done: %s", results)
    except Exception as e:
        logger.error("💥 Scheduler error: %s", e)
    finally:
        db.close()
