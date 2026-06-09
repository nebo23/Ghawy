from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.database import engine
from app.models import Base
from app.routers import users, payment, webhooks, chat, ws, google_auth, dashboard, courses, profile, admin, guests, posts, manual_payments, live, ai_updates, notifications, projects
import os
import logging
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Payment, Category, Channel, ChatMember, MemberRole, ChannelType, Course, Lesson, MessageRead, Message, Guest, GuestSession, PostReaction, CommentReaction, ManualPaymentRequest, LiveAttendee, LiveSession, AiUpdatePost, AiUpdatePoll, AiUpdatePollOption, AiUpdatePollVote, AiUpdateReaction, AiUpdateComment
from pathlib import Path

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(name)s: %(message)s")

BACKEND_DIR = Path(__file__).resolve().parent

def apply_sqlite_compat_migrations():
    if not str(engine.url).startswith("sqlite"):
        return
    with engine.connect() as conn:
        inspector = inspect(conn)
        user_columns = {col["name"] for col in inspector.get_columns("users")}
        if "is_verified" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 0"))
        if "country" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN country VARCHAR"))
        if "verification_code" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN verification_code VARCHAR(6)"))
        if "verification_expiry" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN verification_expiry DATETIME"))
        if "avatar_url" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR"))
        if "bio" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN bio TEXT"))
        if "level" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1"))
        if "xp" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN xp INTEGER DEFAULT 0"))
        if "streak_days" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN streak_days INTEGER DEFAULT 0"))
        if "badge" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN badge VARCHAR DEFAULT 'Member'"))
        # Onboarding fields migration
        if "birth_date" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN birth_date DATE"))
        if "social_media_url" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN social_media_url VARCHAR"))
        if "show_social_media" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN show_social_media BOOLEAN DEFAULT 1"))
        if "onboarding_completed" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0"))
        if "selected_avatar" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN selected_avatar VARCHAR"))
        # Messages migration
        msg_columns = {col["name"] for col in inspector.get_columns("messages")}
        if "read_count" not in msg_columns:
            conn.execute(text("ALTER TABLE messages ADD COLUMN read_count INTEGER DEFAULT 0"))
        if "is_deleted" not in msg_columns:
            conn.execute(text("ALTER TABLE messages ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
        # Create message_reads table if not exists
        if not inspector.has_table("message_reads"):
            conn.execute(text("""
                CREATE TABLE message_reads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    read_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(message_id, user_id)
                )
            """))
        # User last_seen migration
        if "last_seen" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN last_seen DATETIME"))
        # ── Recurring / Subscription columns ──
        if "card_token" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN card_token VARCHAR"))
        if "shopper_reference" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN shopper_reference VARCHAR"))
        if "subscription_type" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN subscription_type VARCHAR DEFAULT 'monthly'"))
        if "subscription_start" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN subscription_start DATETIME"))
        if "subscription_end" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN subscription_end DATETIME"))
        if "last_charged_at" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN last_charged_at DATETIME"))
        if "next_charge_at" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN next_charge_at DATETIME"))
        # ── Payment recurring columns ──
        payment_columns = {col["name"] for col in inspector.get_columns("payments")}
        if "is_recurring" not in payment_columns:
            conn.execute(text("ALTER TABLE payments ADD COLUMN is_recurring BOOLEAN DEFAULT 0"))
        if "recurring_cycle" not in payment_columns:
            conn.execute(text("ALTER TABLE payments ADD COLUMN recurring_cycle INTEGER DEFAULT 0"))
        # Posts migration — new fields for community redesign
        if inspector.has_table("posts"):
            post_cols = {col["name"] for col in inspector.get_columns("posts")}
            if "category_slug" not in post_cols:
                conn.execute(text("ALTER TABLE posts ADD COLUMN category_slug VARCHAR"))
            if "tag" not in post_cols:
                conn.execute(text("ALTER TABLE posts ADD COLUMN tag VARCHAR"))
            if "tag_color" not in post_cols:
                conn.execute(text("ALTER TABLE posts ADD COLUMN tag_color VARCHAR"))
            if "tags" not in post_cols:
                conn.execute(text("ALTER TABLE posts ADD COLUMN tags VARCHAR"))
            if "image_url" not in post_cols:
                conn.execute(text("ALTER TABLE posts ADD COLUMN image_url VARCHAR"))
        if inspector.has_table("lessons"):
            lesson_cols = {col["name"] for col in inspector.get_columns("lessons")}
            if "section_title" not in lesson_cols:
                conn.execute(text("ALTER TABLE lessons ADD COLUMN section_title VARCHAR"))
            if "section_order" not in lesson_cols:
                conn.execute(text("ALTER TABLE lessons ADD COLUMN section_order INTEGER DEFAULT 0"))
                
        if inspector.has_table("guests"):
            guest_cols = {col["name"] for col in inspector.get_columns("guests")}
            if "company_logo" not in guest_cols:
                conn.execute(text("ALTER TABLE guests ADD COLUMN company_logo VARCHAR"))

        # Post & Comment Reactions migration
        if not inspector.has_table("post_reactions"):
            conn.execute(text("""
                CREATE TABLE post_reactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    emoji VARCHAR(10) NOT NULL,
                    UNIQUE(post_id, user_id)
                )
            """))
        if not inspector.has_table("comment_reactions"):
            conn.execute(text("""
                CREATE TABLE comment_reactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    comment_id INTEGER NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    emoji VARCHAR(10) NOT NULL,
                    UNIQUE(comment_id, user_id)
                )
            """))

        # ── Manual Payment Requests (Instapay) ──
        if not inspector.has_table("manual_payment_requests"):
            conn.execute(text("""
                CREATE TABLE manual_payment_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name VARCHAR NOT NULL,
                    email VARCHAR NOT NULL,
                    phone VARCHAR,
                    receipt_url VARCHAR NOT NULL,
                    amount NUMERIC(12, 2),
                    notes TEXT,
                    status VARCHAR DEFAULT 'pending',
                    invite_token VARCHAR UNIQUE,
                    invite_sent_at DATETIME,
                    invite_expires_at DATETIME,
                    reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    reviewed_at DATETIME,
                    rejection_reason VARCHAR,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))

        # ── Lesson Cloudflare columns ──
        if inspector.has_table("lessons"):
            lesson_cols = {col["name"] for col in inspector.get_columns("lessons")}
            if "cloudflare_video_id" not in lesson_cols:
                conn.execute(text("ALTER TABLE lessons ADD COLUMN cloudflare_video_id VARCHAR"))
            if "video_status" not in lesson_cols:
                conn.execute(text("ALTER TABLE lessons ADD COLUMN video_status VARCHAR DEFAULT 'pending'"))
            if "pdf_url" not in lesson_cols:
                conn.execute(text("ALTER TABLE lessons ADD COLUMN pdf_url VARCHAR"))

        # ── LiveSession new columns ──
        if inspector.has_table("live_sessions"):
            ls_cols = {col["name"] for col in inspector.get_columns("live_sessions")}
            if "youtube_url" not in ls_cols:
                conn.execute(text("ALTER TABLE live_sessions ADD COLUMN youtube_url VARCHAR"))
            if "zoom_url" not in ls_cols:
                conn.execute(text("ALTER TABLE live_sessions ADD COLUMN zoom_url VARCHAR"))
            if "is_published" not in ls_cols:
                conn.execute(text("ALTER TABLE live_sessions ADD COLUMN is_published BOOLEAN DEFAULT 0"))
            if "created_by" not in ls_cols:
                conn.execute(text("ALTER TABLE live_sessions ADD COLUMN created_by INTEGER"))
            if "scheduled_at" not in ls_cols:
                conn.execute(text("ALTER TABLE live_sessions ADD COLUMN scheduled_at DATETIME"))

        # ── LiveAttendee table ──
        if not inspector.has_table("live_attendees"):
            conn.execute(text("""
                CREATE TABLE live_attendees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL REFERENCES live_sessions(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(session_id, user_id)
                )
            """))

        # ── Course Reviews table ──
        if not inspector.has_table("course_reviews"):
            conn.execute(text("""
                CREATE TABLE course_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    rating INTEGER NOT NULL,
                    comment TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(course_id, user_id)
                )
            """))

        conn.commit()

def seed_defaults():
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        if db.query(Category).count() == 0:
            defaults = [
                Category(name="General", slug="general", emoji="💬", description="مناقشات عامة", sort_order=0),
                Category(name="Wins", slug="wins", emoji="🏆", description="شارك إنجازاتك", sort_order=1),
                Category(name="Questions", slug="questions", emoji="❓", description="اسأل أي سؤال", sort_order=2),
                Category(name="Resources", slug="resources", emoji="📚", description="مصادر مفيدة", sort_order=3),
            ]
            db.add_all(defaults)
            db.commit()
        if db.query(Channel).count() == 0:
            for ch_name, ch_desc in [("start-here", "Welcome to Ghawy!"), ("general", "General discussion"), ("ai-tools", "AI tools & tips"), ("projects", "Share your projects")]:
                db.add(Channel(name=ch_name, channel_type=ChannelType.GROUP, description=ch_desc))
            db.commit()
        # Ensure start-here channel exists even if other channels were already seeded
        if not db.query(Channel).filter(Channel.name == "start-here").first():
            db.add(Channel(name="start-here", channel_type=ChannelType.GROUP, description="Welcome to Ghawy!"))
            db.commit()

        # Seed Guests
        if db.query(Guest).count() == 0:
            guests_data = [
                {"name": "Sam Altman", "title": "CEO of OpenAI", "company": "OpenAI", 
                 "bio": "Leading the way in artificial general intelligence and global innovation.",
                 "is_featured": True, "total_sessions": 12, "total_attendees": 15000, "rating": 4.9,
                 "category": "AI"},
                {"name": "Sundar Pichai", "title": "CEO of Google", "company": "Google",
                 "bio": "Building helpful technology for everyone.",
                 "is_featured": True, "total_sessions": 8, "total_attendees": 12000, "rating": 4.8,
                 "category": "Tech"},
                {"name": "Lex Fridman", "title": "AI Researcher", "company": "MIT",
                 "bio": "Exploring intelligence, consciousness and the universe.",
                 "is_featured": True, "total_sessions": 6, "total_attendees": 8000, "rating": 4.9,
                 "category": "AI"},
                {"name": "Fei-Fei Li", "title": "AI Pioneer", "company": "Stanford",
                 "bio": "Advancing AI to benefit humanity.",
                 "is_featured": True, "total_sessions": 5, "total_attendees": 6000, "rating": 4.8,
                 "category": "AI"},
                {"name": "Mark Zuckerberg", "title": "CEO of Meta", "company": "Meta",
                 "bio": "Building the future beyond imagination.",
                 "is_featured": True, "total_sessions": 4, "total_attendees": 10000, "rating": 4.7,
                 "category": "Tech"},
            ]
            from datetime import datetime, timedelta
            for gd in guests_data:
                g = Guest(**gd)
                db.add(g)
                db.commit()
                db.refresh(g)
                # Add upcoming session
                db.add(GuestSession(
                    guest_id=g.id,
                    title=f"Live Session with {g.name}",
                    description=f"An exclusive session with {g.title}",
                    session_date=datetime.utcnow() + timedelta(days=5),
                    status="upcoming"
                ))
            db.commit()

        # Seed Courses
        if db.query(Course).count() == 0:
            courses_data = [
                {
                    "title": "AI Automation For Beginners",
                    "description": "Learn how to build smart automations and save 10+ hours every week. From n8n basics to deploying full AI-powered workflows.",
                    "thumbnail_url": None,
                    "is_published": True,
                    "sections": [
                        ("Introduction To AI Automation", [
                            ("What is AI Automation?", 9),
                            ("The Automation Landscape", 13),
                            ("Setting Up Your Workspace", 10),
                        ]),
                        ("Building Your First Workflow", [
                            ("Understanding n8n Interface", 15),
                            ("Your First Automation", 20),
                            ("Working with Triggers", 12),
                            ("Error Handling Basics", 18),
                        ]),
                        ("Connecting APIs & Services", [
                            ("REST API Fundamentals", 25),
                            ("Connecting Google Sheets", 14),
                            ("Slack & Discord Integrations", 16),
                            ("CRM Automation", 22),
                            ("Email Workflows", 18),
                        ]),
                        ("AI-Powered Automation", [
                            ("Integrating OpenAI", 20),
                            ("Building a Support Bot", 30),
                            ("Content Generation Pipeline", 25),
                            ("Lead Qualification Agent", 28),
                        ]),
                        ("Advanced Patterns", [
                            ("Multi-Step Workflows", 22),
                            ("Conditional Logic", 15),
                            ("Data Transformation", 18),
                            ("Scheduling & Cron Jobs", 12),
                            ("Monitoring & Alerts", 16),
                        ]),
                        ("Deployment & Scaling", [
                            ("Self-Hosting n8n", 20),
                            ("Production Best Practices", 15),
                            ("Final Project: Full Automation", 35),
                        ]),
                    ],
                },
                {
                    "title": "Prompt Engineering Mastery",
                    "description": "Master the art of writing professional prompts. Learn how to control AI models and get the best possible results.",
                    "thumbnail_url": None,
                    "is_published": True,
                    "sections": [
                        ("Prompt Fundamentals", [
                            ("Introduction to Prompt Engineering", 25),
                            ("Basics of Writing Prompts", 35),
                            ("Few-Shot Learning Techniques", 40),
                        ]),
                        ("Advanced Techniques", [
                            ("Chain of Thought Prompting", 35),
                            ("Context Engineering", 45),
                            ("Building System Prompts", 30),
                        ]),
                        ("Multi-Modal & Security", [
                            ("Multi-Modal Prompts (Image + Text)", 28),
                            ("Performance & Evaluation", 30),
                            ("Prompt Injection & Protection", 25),
                        ]),
                        ("Projects", [
                            ("Applied Projects - Part 1", 40),
                            ("Applied Projects - Part 2", 32),
                        ]),
                    ],
                },
                {
                    "title": "AAA Core — AI Agency Blueprint",
                    "description": "The complete roadmap to build an AI Automation Agency from scratch. From model to pricing to execution and marketing.",
                    "thumbnail_url": None,
                    "is_published": True,
                    "sections": [
                        ("Foundation", [
                            ("Introduction to the AAA Model", 30),
                            ("Building Your First Model", 55),
                        ]),
                        ("Business Strategy", [
                            ("Pricing Strategies", 40),
                            ("Building an AI Automation Agency", 60),
                        ]),
                        ("Operations", [
                            ("Client & Project Management", 45),
                            ("Marketing & Client Acquisition", 50),
                            ("Execution & Delivery", 45),
                        ]),
                    ],
                },
                {
                    "title": "AI Foundations",
                    "description": "The real starting point for understanding AI. From AI history to building an AI Agent from scratch.",
                    "thumbnail_url": None,
                    "is_published": True,
                    "sections": [
                        ("Understanding AI", [
                            ("History of Artificial Intelligence", 45),
                            ("Understanding Neural Networks", 50),
                        ]),
                        ("Modern AI", [
                            ("LLMs Explained", 55),
                            ("Building an AI Agent From Scratch", 50),
                        ]),
                    ],
                },
            ]

            for cd in courses_data:
                total = sum(dur for sec in cd["sections"] for _, dur in sec[1])
                total_lessons = sum(len(sec[1]) for sec in cd["sections"])
                course = Course(
                    title=cd["title"],
                    description=cd["description"],
                    thumbnail_url=cd.get("thumbnail_url"),
                    total_lessons=total_lessons,
                    is_published=cd["is_published"],
                )
                db.add(course)
                db.commit()
                db.refresh(course)

                lesson_order = 0
                for sec_idx, (sec_title, lessons) in enumerate(cd["sections"]):
                    for les_title, les_dur in lessons:
                        lesson_order += 1
                        db.add(Lesson(
                            course_id=course.id,
                            title=les_title,
                            section_title=sec_title,
                            section_order=sec_idx,
                            order=lesson_order,
                            duration_minutes=les_dur,
                        ))
                db.commit()

    finally:
        db.close()

# ✅ app يتعمل الأول
app = FastAPI(title="Community Backend", version="2.0.0")

# ✅ SECRET_KEY من الـ .env مش الـ client secret
app.add_middleware(SessionMiddleware, secret_key=os.getenv('SECRET_KEY', 'fallback-secret'))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# إنشاء الجداول
Base.metadata.create_all(bind=engine)
apply_sqlite_compat_migrations()
seed_defaults()

# Create uploads directory
uploads_dir = BACKEND_DIR / "uploads"
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# Create and mount static directory (for onboarding avatars)
static_dir = BACKEND_DIR / "static" / "avatars"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(BACKEND_DIR / "static")), name="static")

# ✅ Routers كلها بعد app
app.include_router(users.router)
app.include_router(payment.router)
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

@app.get("/")
def root():
    return {"message": "Community API Is Working"}

@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

@app.delete("/payments/{payment_id}")
def delete_payment(payment_id: int, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    db.delete(payment)
    db.commit()
    return {"message": "Payment deleted successfully"}

from app.routers.users import get_current_user
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
        "instapay_number": os.getenv("INSTAPAY_NUMBER", "01019381981"),
        "subscription_price": os.getenv("SUBSCRIPTION_PRICE", "500"),
        "currency": "EGP"
    }

# ── Scheduler (recurring charges) ──────────────────────────
try:
    from app.scheduler import scheduler

    @app.on_event("startup")
    async def startup_scheduler():
        scheduler.start()
        logging.getLogger(__name__).info("✅ APScheduler started")

    @app.on_event("shutdown")
    async def shutdown_scheduler():
        scheduler.shutdown()
        logging.getLogger(__name__).info("🛑 APScheduler stopped")

except Exception as e:
    logging.getLogger(__name__).warning("⚠️ Scheduler not loaded: %s", e)
# Force Reload

# reload
