"""Startup seeding, in three layers.

The layers exist because they answer different questions:

* :func:`seed_production_defaults` — what the app genuinely cannot boot without.
  Runs on every start, in every environment, and is idempotent.
* :func:`seed_demo_data` — fixtures that make a *developer's* database worth
  looking at. Never runs unless ``SEED_DEMO_DATA=1``, and refuses outright in
  production.
* Test fixtures — not here at all. ``backend/scripts/acceptance_*.py`` build
  their own rows against a throwaway database and do not depend on either
  function above.

What used to be here instead
----------------------------
One ``seed_defaults()`` in ``main.py`` that ran at import time and, among other
things, inserted **five real, named public figures** — Sam Altman, Sundar
Pichai, Lex Fridman, Fei-Fei Li and Mark Zuckerberg — as "Guests of Honor", each
with an invented rating (4.9), an invented attendance figure (up to 15,000) and
a fabricated upcoming live session dated five days out. Those rows reached
production and were served unauthenticated to anyone who asked. That is a false
endorsement attached to identifiable people, so it is gone rather than rewritten
with different numbers: no seed path in this file names a real person.

It was also self-healing in the worst way. The guard was
``if db.query(Guest).count() == 0``, so an admin deleting the fabricated guests
did not remove them — the next restart put them back. Production's
``guests_id_seq`` sits at 37 for 5 rows, which is what that loop looks like from
the outside.
"""

import logging
import os
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import Category, Channel, ChannelType, Coupon, Course, Guest, GuestSession, Lesson

logger = logging.getLogger(__name__)


# ── Layer 1: production-safe ───────────────────────────────────────────────

def seed_production_defaults(db) -> None:
    """Only what the app cannot boot without. Idempotent, safe in production."""
    if db.query(Category).count() == 0:
        db.add_all([
            Category(name="General", slug="general", emoji="💬", description="مناقشات عامة", sort_order=0),
            Category(name="Wins", slug="wins", emoji="🏆", description="شارك إنجازاتك", sort_order=1),
            Category(name="Questions", slug="questions", emoji="❓", description="اسأل أي سؤال", sort_order=2),
            Category(name="Resources", slug="resources", emoji="📚", description="مصادر مفيدة", sort_order=3),
        ])
        db.commit()

    if db.query(Channel).count() == 0:
        for ch_name, ch_desc in [
            ("start-here", "Welcome to Ghawy!"),
            ("general", "General discussion"),
            ("ai-tools", "AI tools & tips"),
            ("projects", "Share your projects"),
        ]:
            db.add(Channel(name=ch_name, channel_type=ChannelType.GROUP, description=ch_desc))
        db.commit()

    # start-here is the one channel the community UI assumes exists, so it is
    # checked by name as well as by the count above.
    if not db.query(Channel).filter(Channel.name == "start-here").first():
        db.add(Channel(name="start-here", channel_type=ChannelType.GROUP, description="Welcome to Ghawy!"))
        db.commit()

    # ── Discount coupons ──
    # The Alembic migration seeds these too. This is the belt to that
    # braces: a database brought up through Base.metadata.create_all()
    # rather than through Alembic still ends up with both codes, and an
    # accidental delete comes back on the next boot. Existing rows are left
    # exactly as they are — the limit or the percentage may have been tuned
    # from the admin side, and re-seeding must not undo that.
    #
    # These are real discount codes, not demo data, which is why they stayed in
    # this layer: on a database built from `ghawy_baseline` the migration that
    # would otherwise create them is skipped, so this is their only source.
    for code, display in (("monzer", "Monzer"), ("os10", "Os10")):
        if not db.query(Coupon).filter(Coupon.code == code).first():
            db.add(Coupon(
                code=code,
                display_code=display,
                discount_percent=10,
                max_redemptions=30,
                is_active=True,
            ))
    db.commit()


# ── Layer 2: development / demo ────────────────────────────────────────────

# Deliberately, obviously synthetic. Nobody should ever have to check whether
# one of these is a real person or a real course.
DEMO_GUESTS = [
    {"name": "Demo Guest 1", "title": "Demo Speaker", "company": "Demo Co",
     "bio": "Placeholder guest used to exercise the Guests of Honor UI.",
     "is_featured": True, "sessions_count": 2, "attendees_count": 40, "rating": 4.0,
     "category": "AI"},
    {"name": "Demo Guest 2", "title": "Demo Speaker", "company": "Demo Co",
     "bio": "Placeholder guest used to exercise the Guests of Honor UI.",
     "is_featured": True, "sessions_count": 1, "attendees_count": 25, "rating": 4.0,
     "category": "Tech"},
    {"name": "Demo Guest 3", "title": "Demo Speaker", "company": "Demo Co",
     "bio": "Placeholder guest used to exercise the Guests of Honor UI.",
     "is_featured": False, "sessions_count": 0, "attendees_count": 0, "rating": 0.0,
     "category": "AI"},
]

DEMO_COURSES = [
    {
        "title": "Demo — AI Automation For Beginners",
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
        "title": "Demo — Prompt Engineering Mastery",
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
        "title": "Demo — AAA Core — AI Agency Blueprint",
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
        "title": "Demo — AI Foundations",
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


def seed_demo_data(db) -> None:
    """Fixtures for a developer's database. Never call this in production."""
    if db.query(Guest).count() == 0:
        for gd in DEMO_GUESTS:
            g = Guest(**gd)
            db.add(g)
            db.commit()
            db.refresh(g)
            db.add(GuestSession(
                guest_id=g.id,
                title=f"Demo session with {g.name}",
                description="Placeholder session.",
                session_date=datetime.utcnow() + timedelta(days=5),
                status="upcoming",
            ))
        db.commit()

    if db.query(Course).count() == 0:
        for cd in DEMO_COURSES:
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


# ── Entry point ───────────────────────────────────────────────────────────

def run_startup_seed() -> None:
    """Called once per boot from the lifespan handler, under an advisory lock."""
    environment = os.getenv("ENVIRONMENT", "development")
    db = SessionLocal()
    try:
        seed_production_defaults(db)

        if os.getenv("SEED_DEMO_DATA") != "1":
            return
        if environment == "production":
            # Refuse rather than honour the flag: demo rows in the production
            # database is the exact failure this split exists to prevent.
            logger.warning("SEED_DEMO_DATA=1 ignored — refusing to seed demo data in production")
            return
        logger.warning("SEED_DEMO_DATA=1 — seeding demo guests and demo courses")
        seed_demo_data(db)
    finally:
        db.close()
