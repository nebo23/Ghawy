from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Numeric, Enum, Text, ForeignKey, text
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
    PAYPAL = "paypal"
    KASHIER = "kashier"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"

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
    is_active = Column(Boolean, server_default=text('false'))   # يتفعل بعد الدفع
    is_verified = Column(Boolean, server_default=text('false'))
    verification_code = Column(String(6), nullable=True)
    verification_expiry = Column(DateTime, nullable=True)
    is_admin = Column(Boolean, server_default=text('false'))
    avatar_url = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    level = Column(Integer, server_default=text('1'))
    xp = Column(Integer, server_default=text('0'))
    streak_days = Column(Integer, server_default=text('0'))
    badge = Column(String, default="Member")
    birth_date = Column(Date, nullable=True)
    social_media_url = Column(String, nullable=True)
    show_social_media = Column(Boolean, server_default=text('true'))
    onboarding_completed = Column(Boolean, server_default=text('false'))
    selected_avatar = Column(String, nullable=True)
    last_seen = Column(DateTime, nullable=True)

    # ── Recurring / Subscription ──────────────────
    card_token = Column(String, nullable=True)
    shopper_reference = Column(String, nullable=True)
    subscription_type = Column(String, default="monthly")  # monthly / yearly
    subscription_start = Column(DateTime, nullable=True)
    subscription_end = Column(DateTime, nullable=True)
    last_charged_at = Column(DateTime, nullable=True)
    next_charge_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    # Relationships
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
    user_id = Column(Integer, nullable=False)
    method = Column(Enum(PaymentMethod), nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String, default="EGP")
    paypal_order_id = Column(String, nullable=True)       # للـ PayPal
    provider_order_id = Column(String, nullable=True, index=True)  # generic provider order id
    created_at = Column(DateTime, server_default=func.now())
    confirmed_at = Column(DateTime, nullable=True)

    # ── Recurring ─────────────────────────────────
    is_recurring = Column(Boolean, server_default=text('false'))
    recurring_cycle = Column(Integer, server_default=text('0'))  # 0=first payment, 1,2,3...

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
    sort_order = Column(Integer, server_default=text('0'))
    created_at = Column(DateTime, server_default=func.now())

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
    image_url = Column(String, nullable=True)
    like_count = Column(Integer, server_default=text('0'))
    comment_count = Column(Integer, server_default=text('0'))
    is_pinned = Column(Boolean, server_default=text('false'))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    author = relationship("User", back_populates="posts")
    category = relationship("Category", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    likes = relationship("PostLike", back_populates="post", cascade="all, delete-orphan")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    post = relationship("Post", back_populates="comments")
    author = relationship("User", back_populates="comments")
    replies = relationship("Comment", backref="parent", remote_side=[id])


class PostLike(Base):
    __tablename__ = "post_likes"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    post = relationship("Post", back_populates="likes")

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
    created_at = Column(DateTime, server_default=func.now())

    members = relationship("ChatMember", back_populates="channel", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="channel", cascade="all, delete-orphan")


class ChatMember(Base):
    __tablename__ = "chat_members"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(Enum(MemberRole), default=MemberRole.MEMBER)
    joined_at = Column(DateTime, server_default=func.now())
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
    read_count = Column(Integer, server_default=text('0'))
    is_deleted = Column(Boolean, server_default=text('false'))
    created_at = Column(DateTime, server_default=func.now())

    channel = relationship("Channel", back_populates="messages")
    sender = relationship("User", back_populates="messages")
    reply_to = relationship("Message", remote_side=[id])
    reads = relationship("MessageRead", back_populates="message", cascade="all, delete-orphan")


class MessageRead(Base):
    __tablename__ = "message_reads"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    read_at = Column(DateTime, server_default=func.now())

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
    total_lessons = Column(Integer, server_default=text('0'))
    is_published = Column(Boolean, server_default=text('false'))
    created_at = Column(DateTime, server_default=func.now())

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
    section_order = Column(Integer, server_default=text('0'))
    order = Column(Integer, server_default=text('0'))
    duration_minutes = Column(Integer, server_default=text('0'))
    created_at = Column(DateTime, server_default=func.now())

    course = relationship("Course", back_populates="lessons")


class UserCourseProgress(Base):
    __tablename__ = "user_course_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    completed_lessons = Column(Integer, server_default=text('0'))
    percent = Column(Numeric(5, 2), server_default=text('0.0'))
    last_accessed = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="course_progress")
    course = relationship("Course", back_populates="progress")
