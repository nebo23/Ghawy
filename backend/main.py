from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.database import engine
from app.models import Base
from app.routers import users, payment, webhooks, chat, ws, google_auth, dashboard, courses, profile, admin, guests, posts, manual_payments, live, ai_updates, notifications, projects, reports, feedbacks
import os
import logging
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Payment, Category, Channel, ChatMember, MemberRole, ChannelType, Course, Lesson, MessageRead, Message, Guest, GuestSession, PostReaction, CommentReaction, ManualPaymentRequest, LiveAttendee, LiveSession, AiUpdatePost, AiUpdatePoll, AiUpdatePollOption, AiUpdatePollVote, AiUpdateReaction, AiUpdateComment, CommunityFeedback
from app.routers.users import get_current_user, get_current_admin_user
from pathlib import Path

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Use WARNING in production to avoid leaking sensitive data in logs
_log_level = logging.WARNING if ENVIRONMENT == "production" else logging.DEBUG
logging.basicConfig(level=_log_level, format="%(levelname)s: %(name)s: %(message)s")

BACKEND_DIR = Path(__file__).resolve().parent

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
                 "is_featured": True, "sessions_count": 12, "attendees_count": 15000, "rating": 4.9,
                 "category": "AI"},
                {"name": "Sundar Pichai", "title": "CEO of Google", "company": "Google",
                 "bio": "Building helpful technology for everyone.",
                 "is_featured": True, "sessions_count": 8, "attendees_count": 12000, "rating": 4.8,
                 "category": "Tech"},
                {"name": "Lex Fridman", "title": "AI Researcher", "company": "MIT",
                 "bio": "Exploring intelligence, consciousness and the universe.",
                 "is_featured": True, "sessions_count": 6, "attendees_count": 8000, "rating": 4.9,
                 "category": "AI"},
                {"name": "Fei-Fei Li", "title": "AI Pioneer", "company": "Stanford",
                 "bio": "Advancing AI to benefit humanity.",
                 "is_featured": True, "sessions_count": 5, "attendees_count": 6000, "rating": 4.8,
                 "category": "AI"},
                {"name": "Mark Zuckerberg", "title": "CEO of Meta", "company": "Meta",
                 "bio": "Building the future beyond imagination.",
                 "is_featured": True, "sessions_count": 4, "attendees_count": 10000, "rating": 4.7,
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

# ✅ app يتعمل الأول — disable docs in production
_docs_url = None if ENVIRONMENT == "production" else "/docs"
_redoc_url = None if ENVIRONMENT == "production" else "/redoc"
app = FastAPI(
    title="Community Backend",
    version="2.0.0",
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)

# ✅ SECRET_KEY من الـ .env مش الـ client secret
app.add_middleware(SessionMiddleware, secret_key=os.getenv('SECRET_KEY', 'fallback-secret'))
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5500").split(","), # 🌐 قراءة النطاقات المسموحة من متغيرات البيئة للسماح بنطاقات الإنتاج (CORS Fix)
    # allow_origin_regex is removed to use explicit origins from environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# إنشاء الجداول
Base.metadata.create_all(bind=engine)
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
app.include_router(reports.router)
app.include_router(feedbacks.router)

@app.get("/")
def root():
    return {"message": "Community API Is Working"}

@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)): # 🔒 إضافة Depends(get_current_admin_user) لحماية مسار الحذف من الأشخاص غير المصرح لهم
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

@app.delete("/payments/{payment_id}")
def delete_payment(payment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)): # 🔒 إضافة Depends(get_current_admin_user) لحماية مسار الحذف من الأشخاص غير المصرح لهم
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
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
