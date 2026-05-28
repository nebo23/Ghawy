from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Numeric, Enum, Text, ForeignKey, text, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

# ═══════════════════════════════════════════
#  ENUMS
# ═══════════════════════════════════════════

class PaymentMethod(str, enum.Enum):
    KASHIER = "kashier"
    MANUAL = "manual"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    REFUNDED = "refunded"

class ChannelType(str, enum.Enum):
    GROUP = "group"
    DM = "dm"
    ANNOUNCEMENT = "announcement"

class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    VOICE = "voice"
    LINK = "link"

class MemberRole(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"

class LiveSessionStatus(str, enum.Enum):
    LIVE = "live"
    UPCOMING = "upcoming"
    ENDED = "ended"
    CANCELLED = "cancelled"

class LiveSessionDifficulty(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class PaymentRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

# ═══════════════════════════════════════════
#  USER
# ═══════════════════════════════════════════

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=True)
    country = Column(String, nullable=True)
    governorate = Column(String, nullable=True)
    is_active = Column(Boolean, server_default=text('false'), default=False)   # يتفعل بعد الدفع
    is_verified = Column(Boolean, server_default=text('false'), default=False)
    verification_code = Column(String(6), nullable=True)
    verification_expiry = Column(DateTime, nullable=True)
    is_admin = Column(Boolean, server_default=text('false'), default=False)
    avatar_url = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    level = Column(Integer, server_default=text('1'), default=1)
    xp = Column(Integer, server_default=text('0'), default=0)
    streak_days = Column(Integer, server_default=text('0'), default=0)
    badge = Column(String, default="Member")
    birth_date = Column(Date, nullable=True)
    social_media_url = Column(String, nullable=True)
    show_social_media = Column(Boolean, server_default=text('true'), default=True)
    onboarding_completed = Column(Boolean, server_default=text('false'), default=False)
    selected_avatar = Column(String, nullable=True)
    last_seen = Column(DateTime, nullable=True)

    @property
    def is_online(self) -> bool:
        from datetime import datetime, timedelta
        if self.last_seen:
            return datetime.utcnow() - self.last_seen <= timedelta(seconds=65)
        return False

    # ── Recurring / Subscription ──────────────────
    card_token = Column(String, nullable=True)
    shopper_reference = Column(String, nullable=True)
    subscription_type = Column(String, default="monthly")  # monthly / yearly
    subscription_start = Column(DateTime, nullable=True)
    subscription_end = Column(DateTime, nullable=True)
    last_charged_at = Column(DateTime, nullable=True)
    next_charge_at = Column(DateTime, nullable=True)
    failed_charge_count = Column(Integer, server_default=text('0'), default=0)

    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    # Relationships
    # دي علشان لو احنا شيلنا شخص معين كل الحاجات اللي معاه هتتمسح
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="sender", cascade="all, delete-orphan")
    course_progress = relationship("UserCourseProgress", back_populates="user", cascade="all, delete-orphan")

# ═══════════════════════════════════════════
#  PAYMENT
# ═══════════════════════════════════════════

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    method = Column(Enum(PaymentMethod), nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String, default="EGP")
    provider_order_id = Column(String, nullable=True, index=True)  # generic provider order id
    plan_key = Column(String, nullable=True)  # monthly_egp, yearly_egp, monthly_usd, yearly_usd
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)

    # ── Recurring ─────────────────────────────────
    is_recurring = Column(Boolean, server_default=text('false'), default=False)
    recurring_cycle = Column(Integer, server_default=text('0'), default=0)  # 0=first payment, 1,2,3...

# ═══════════════════════════════════════════
#  COMMUNITY — Categories, Posts, Comments, Likes
# ═══════════════════════════════════════════

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    emoji = Column(String, default="📁")
    sort_order = Column(Integer, server_default=text('0'), default=0)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    posts = relationship("Post", back_populates="category")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=True)
    category_slug = Column(String, nullable=True, index=True)  # channel identifier e.g. "workflows-help"
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    tag = Column(String, nullable=True)       # e.g. "Help", "Question", "Win"
    tag_color = Column(String, nullable=True)  # e.g. "orange", "blue", "gold"
    tags = Column(String, nullable=True)       # comma-separated tags e.g. "Make.com,n8n,Zapier"
    image_url = Column(String, nullable=True)
    like_count = Column(Integer, server_default=text('0'), default=0)
    comment_count = Column(Integer, server_default=text('0'), default=0)
    is_pinned = Column(Boolean, server_default=text('false'), default=False)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    author = relationship("User", back_populates="posts")
    category = relationship("Category", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    likes = relationship("PostLike", back_populates="post", cascade="all, delete-orphan")
    reactions = relationship("PostReaction", back_populates="post", cascade="all, delete-orphan")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    post = relationship("Post", back_populates="comments")
    author = relationship("User", back_populates="comments")
    replies = relationship("Comment", backref="parent", remote_side=[id])
    reactions = relationship("CommentReaction", back_populates="comment", cascade="all, delete-orphan")


class PostLike(Base):
    __tablename__ = "post_likes"
    __table_args__ = (UniqueConstraint('post_id', 'user_id'),)

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    post = relationship("Post", back_populates="likes")


class PostReaction(Base):
    __tablename__ = "post_reactions"
    __table_args__ = (UniqueConstraint('post_id', 'user_id'),)

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    emoji = Column(String, nullable=False)  # "👍" | "❤️" | "😮" | "🔥" | "👏"
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    post = relationship("Post", back_populates="reactions")


class CommentReaction(Base):
    __tablename__ = "comment_reactions"
    __table_args__ = (UniqueConstraint('comment_id', 'user_id'),)

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    emoji = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    comment = relationship("Comment", back_populates="reactions")

# ═══════════════════════════════════════════
#  CHAT — Channels, Members, Messages
# ═══════════════════════════════════════════

class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    channel_type = Column(Enum(ChannelType), default=ChannelType.GROUP)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    members = relationship("ChatMember", back_populates="channel", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="channel", cascade="all, delete-orphan")


class ChatMember(Base):
    __tablename__ = "chat_members"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(Enum(MemberRole), default=MemberRole.MEMBER)
    joined_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)
    last_read_at = Column(DateTime, nullable=True)

    channel = relationship("Channel", back_populates="members")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=True)
    message_type = Column(Enum(MessageType), default=MessageType.TEXT)
    file_url = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    reply_to_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    read_count = Column(Integer, server_default=text('0'), default=0)
    is_deleted = Column(Boolean, server_default=text('false'), default=False)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    channel = relationship("Channel", back_populates="messages")
    sender = relationship("User", back_populates="messages")
    reply_to = relationship("Message", remote_side=[id])
    reads = relationship("MessageRead", back_populates="message", cascade="all, delete-orphan")


class MessageRead(Base):
    __tablename__ = "message_reads"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    read_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    message = relationship("Message", back_populates="reads")
    user = relationship("User")

# ═══════════════════════════════════════════
#  COURSES
# ═══════════════════════════════════════════

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    total_lessons = Column(Integer, server_default=text('0'), default=0)
    is_published = Column(Boolean, server_default=text('false'), default=False)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    lessons = relationship("Lesson", back_populates="course", cascade="all, delete-orphan", order_by="Lesson.order")
    progress = relationship("UserCourseProgress", back_populates="course", cascade="all, delete-orphan")


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    video_url = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    section_title = Column(String, nullable=True)
    section_order = Column(Integer, server_default=text('0'), default=0)
    order = Column(Integer, server_default=text('0'), default=0)
    duration_minutes = Column(Integer, server_default=text('0'), default=0)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    course = relationship("Course", back_populates="lessons")


class UserCourseProgress(Base):
    __tablename__ = "user_course_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    completed_lessons = Column(Integer, server_default=text('0'), default=0)
    percent = Column(Numeric(5, 2), server_default=text('0.0'), default=0.0)
    last_accessed = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    user = relationship("User", back_populates="course_progress")
    course = relationship("Course", back_populates="progress")

# ═══════════════════════════════════════════
#  GUEST OF HONORS
# ═══════════════════════════════════════════

class Guest(Base):
    __tablename__ = "guests"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    title = Column(String, nullable=False)        # "CEO of OpenAI"
    company = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String, nullable=True)    # photo URL
    company_logo = Column(String, nullable=True)  # company logo URL
    category = Column(String, nullable=True)      # "AI", "Business", etc.
    is_featured = Column(Boolean, server_default=text('false'), default=False)
    total_sessions = Column(Integer, server_default=text('0'), default=0)
    total_attendees = Column(Integer, server_default=text('0'), default=0)
    rating = Column(Numeric(3,1), server_default=text('0.0'), default=0.0)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)
    
    sessions = relationship("GuestSession", back_populates="guest", cascade="all, delete-orphan")

class GuestSession(Base):
    __tablename__ = "guest_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    guest_id = Column(Integer, ForeignKey("guests.id", ondelete="CASCADE"))
    title = Column(String, nullable=False)        # "The Future of AI and Humanity"
    description = Column(Text, nullable=True)
    session_date = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, server_default=text('60'), default=60)
    video_url = Column(String, nullable=True)
    attendees = Column(Integer, server_default=text('0'), default=0)
    status = Column(String, server_default=text("'upcoming'"), default="upcoming")  # upcoming / past / live
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)
    
    guest = relationship("Guest", back_populates="sessions")

# ═══════════════════════════════════════════
#  BUILD WITH ME (LIVE)
# ═══════════════════════════════════════════

class LiveSession(Base):
    __tablename__ = "live_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    instructor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(LiveSessionStatus), default=LiveSessionStatus.UPCOMING)
    difficulty = Column(Enum(LiveSessionDifficulty), default=LiveSessionDifficulty.BEGINNER)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    stream_url = Column(String, nullable=True)
    recording_url = Column(String, nullable=True)
    max_attendees = Column(Integer, server_default=text('0'), default=0) # 0 means unlimited
    current_viewers = Column(Integer, server_default=text('0'), default=0)
    is_recording_available = Column(Boolean, server_default=text('false'), default=False)
    tags = Column(String, nullable=True) # Comma separated
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)
    
    instructor = relationship("User", foreign_keys=[instructor_id])
    bookings = relationship("SessionBooking", back_populates="session", cascade="all, delete-orphan")
    reminders = relationship("SessionReminder", back_populates="session", cascade="all, delete-orphan")
    projects = relationship("SessionProject", back_populates="session", cascade="all, delete-orphan")


class SessionBooking(Base):
    __tablename__ = "session_bookings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(Integer, ForeignKey("live_sessions.id", ondelete="CASCADE"), nullable=False)
    reminder_enabled = Column(Boolean, server_default=text('true'), default=True)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)
    
    user = relationship("User")
    session = relationship("LiveSession", back_populates="bookings")


class SessionReminder(Base):
    __tablename__ = "session_reminders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(Integer, ForeignKey("live_sessions.id", ondelete="CASCADE"), nullable=False)
    reminder_sent = Column(Boolean, server_default=text('false'), default=False)
    reminder_time = Column(DateTime, nullable=False)
    
    user = relationship("User")
    session = relationship("LiveSession", back_populates="reminders")


class SessionProject(Base):
    __tablename__ = "session_projects"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("live_sessions.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    rating = Column(Numeric(3,1), server_default=text('0.0'), default=0.0)
    creator_name = Column(String, nullable=False)
    
    session = relationship("LiveSession", back_populates="projects")

# ═══════════════════════════════════════════
#  MANUAL PAYMENT REQUESTS (Instapay)
# ═══════════════════════════════════════════

class ManualPaymentRequest(Base):
    __tablename__ = "manual_payment_requests"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    receipt_url = Column(String, nullable=False)       # uploaded screenshot path
    amount = Column(Numeric(12, 2), nullable=True)     # optional, what they claim to have paid
    notes = Column(Text, nullable=True)                # any notes from user
    status = Column(String, default="pending")         # pending | approved | rejected
    invite_token = Column(String, nullable=True, unique=True)  # one-time registration token
    invite_sent_at = Column(DateTime, nullable=True)
    invite_expires_at = Column(DateTime, nullable=True)        # token valid for 48 hours
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

