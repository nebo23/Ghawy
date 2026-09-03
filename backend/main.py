from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.database import engine
from app.models import Base
from app.routers import users, payment, webhooks, chat, ws, google_auth, dashboard, courses, profile, admin, guests, posts, manual_payments, live, ai_updates, notifications, projects, reports, feedbacks, atlas, help_center, exams, birthday, email_campaigns, stats, coupons, files, announcements
from app.routers.files import PUBLIC_CATEGORIES as PUBLIC_UPLOAD_CATEGORIES
from app.seed import run_startup_seed
import os
import logging
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from app.database import get_db
# The eight names the seed used (Category, Channel, ChannelType, Course,
# Lesson, Guest, GuestSession, Coupon) moved to app/seed.py with it. The
# sixteen still listed here were already unused before this phase — see F-17.
from app.models import User, Payment, ChatMember, MemberRole, MessageRead, Message, PostReaction, CommentReaction, ManualPaymentRequest, LiveAttendee, LiveSession, AiUpdatePost, AiUpdatePoll, AiUpdatePollOption, AiUpdatePollVote, AiUpdateReaction, AiUpdateComment, CommunityFeedback
from app.routers.users import get_current_user, get_current_admin_user
from pathlib import Path

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# WARNING in production, as the comment here has always said — the code said
# INFO, so every INFO line really was being emitted, including (until now) the
# email verification codes themselves.
_log_level = logging.WARNING if ENVIRONMENT == "production" else logging.INFO
logging.basicConfig(level=_log_level, format="%(levelname)s: %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent


# ── Startup / shutdown ─────────────────────────────────────
# Everything below used to run at *import* time — the schema was built by
# Base.metadata.create_all() and a 223-line seed_defaults() that lived in this
# file, before the app object even existed. Gunicorn imports this
# module once per worker, so both ran once per worker; and create_all silently
# built tables that no migration had ever created, which is precisely how the
# Alembic history rotted until ghawy_baseline. Schema now comes from
# `alembic upgrade head` (run by the container command), and this handler only
# checks that it happened.

# One arbitrary constant, shared by every worker, so only one of them seeds.
_SEED_LOCK_KEY = 0x64_6861_7779  # "ghawy"


def _schema_is_present() -> bool:
    try:
        return inspect(engine).has_table("users")
    except Exception:
        return False


def _bootstrap_schema() -> None:
    """Make sure the database has a schema, and say so loudly if it does not."""
    if _schema_is_present():
        return
    if os.getenv("DEV_CREATE_ALL") == "1" and ENVIRONMENT != "production":
        # Local convenience only. `alembic upgrade head` works from an empty
        # database now, so this is a shortcut, never the supported path.
        logger.warning("DEV_CREATE_ALL=1 — building the schema from the models")
        Base.metadata.create_all(bind=engine)
        return
    raise RuntimeError(
        "The database has no schema. Run `alembic upgrade head` before starting "
        "the app (or set DEV_CREATE_ALL=1 outside production to build it from "
        "the models)."
    )


def _seed_once() -> None:
    """Seed under an advisory lock so N workers do not all write.

    The seed is idempotent, so the lock is not what makes this safe — it is what
    stops N workers racing each other into the same INSERT and losing on a
    unique constraint. See app/seed.py for the three layers.
    """
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _SEED_LOCK_KEY})
        try:
            run_startup_seed()
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _SEED_LOCK_KEY})
            conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # كل sync endpoint/dependency بياخد ثريد من anyio (الافتراضي 40). تحت ضغط،
    # طلب بيعدي الـ auth (transaction مفتوحة + اتصال DB محجوز) وبعدين يقف في
    # طابور الثريدات ماسك الاتصال → الـ pool بيفضى والموقع يتجمد (انهيار 2026-07-21،
    # 26 دقيقة). 120 ثريد > سعة الـ DB pool بهامش يمنع الطابور-وهو-ماسك-اتصال.
    import anyio.to_thread
    anyio.to_thread.current_default_thread_limiter().total_tokens = 120
    logger.info("✅ anyio threadpool capacity raised to 120")

    _bootstrap_schema()
    _seed_once()

    scheduler = None
    try:
        from app.scheduler import scheduler as _scheduler
        scheduler = _scheduler
        scheduler.start()
        logger.info("✅ APScheduler started")
    except Exception as e:
        logger.warning("⚠️ Scheduler not loaded: %s", e)

    yield

    if scheduler is not None:
        try:
            scheduler.shutdown()
            logger.info("🛑 APScheduler stopped")
        except Exception as e:
            logger.warning("⚠️ Scheduler shutdown failed: %s", e)


# ✅ app يتعمل الأول — disable docs in production
# openapi_url كمان لازم يتقفل: docs_url=None بيخفي الـ UI بس، و/openapi.json كان
# لسه شغال — ماسح 2026-07-21 سحب منه خريطة الـ API كاملة قبل ما يضرب الـ endpoints
_docs_url = None if ENVIRONMENT == "production" else "/docs"
_redoc_url = None if ENVIRONMENT == "production" else "/redoc"
_openapi_url = None if ENVIRONMENT == "production" else "/openapi.json"
app = FastAPI(
    title="Community Backend",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

# ✅ SECRET_KEY من الـ .env — لازم يكون موجود وإلا التطبيق ميشتغلش
_SECRET_KEY = os.getenv('SECRET_KEY')
if not _SECRET_KEY or _SECRET_KEY == 'fallback-secret':
    raise RuntimeError(
        "SECRET_KEY environment variable is required and must not be the fallback value. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
app.add_middleware(SessionMiddleware, secret_key=_SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5500").split(","), # 🌐 قراءة النطاقات المسموحة من متغيرات البيئة للسماح بنطاقات الإنتاج (CORS Fix)
    # allow_origin_regex is removed to use explicit origins from environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Create uploads directory
uploads_dir = BACKEND_DIR / "uploads"
uploads_dir.mkdir(exist_ok=True)

# Only the categories that are genuinely public get a StaticFiles mount. The
# blanket app.mount("/uploads", …) that used to be here served the whole tree —
# lesson PDFs, payment receipts, project submissions, chat and DM attachments —
# to anyone who knew a filename. Everything else is served by app.routers.files,
# which checks who is asking and whether that file is theirs to open.
for _category in PUBLIC_UPLOAD_CATEGORIES:
    _dir = uploads_dir / _category
    _dir.mkdir(parents=True, exist_ok=True)
    app.mount(f"/uploads/{_category}", StaticFiles(directory=str(_dir)), name=f"uploads-{_category}")

# Create and mount static directory (for onboarding avatars)
static_dir = BACKEND_DIR / "static" / "avatars"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(BACKEND_DIR / "static")), name="static")

# ✅ Routers كلها بعد app
app.include_router(users.router)
app.include_router(payment.router)
app.include_router(coupons.router)
app.include_router(files.router)
app.include_router(webhooks.router)
app.include_router(chat.router)
app.include_router(ws.router)
app.include_router(google_auth.router)
app.include_router(dashboard.router)
app.include_router(courses.router)
app.include_router(profile.router)
app.include_router(admin.router)
app.include_router(guests.router)
app.include_router(posts.router)
app.include_router(manual_payments.router)
app.include_router(live.router)
app.include_router(ai_updates.router)
app.include_router(notifications.router)
app.include_router(projects.router)
app.include_router(exams.router)
app.include_router(reports.router)
app.include_router(feedbacks.router)
app.include_router(atlas.router)
app.include_router(help_center.router)
app.include_router(birthday.router)
app.include_router(email_campaigns.router)
app.include_router(announcements.router)
app.include_router(stats.router)

@app.get("/")
def root():
    return {"message": "Community API Is Working"}

@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)): # 🔒 محمي بـ admin auth + audit log
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    logger.warning(
        "🗑️ ADMIN DELETE USER | admin_id=%s admin_email=%s | target_user_id=%s target_email=%s",
        current_user.id, current_user.email, user.id, user.email
    )
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

@app.delete("/payments/{payment_id}")
def delete_payment(payment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)): # 🔒 محمي بـ admin auth + audit log
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

@app.patch("/users/me/complete-onboarding")
def complete_onboarding_patch(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    current_user.onboarding_completed = True
    db.commit()
    return {"message": "onboarding completed"}

@app.get("/config/payment-info")
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

# Force Reload

# reload
