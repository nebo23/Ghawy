
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Numeric, Enum, Text, ForeignKey, text, UniqueConstraint, Index, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, backref
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

class AiUpdatePostType(str, enum.Enum):
    TEXT = "text"
    VIDEO = "video"
    PHOTO = "photo"
    POLL = "poll"

class ProjectSubmissionStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"

# ═══════════════════════════════════════════
#  USER
# ═══════════════════════════════════════════

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # full_name stays the display source of truth (read in emails, chat, DMs,
    # admin, the team dashboard…) and is always recomposed from first + last.
    full_name = Column(String, nullable=False)
    first_name = Column(String, nullable=True)   # nullable: pre-split accounts
    last_name = Column(String, nullable=True)
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
    is_owner = Column(Boolean, server_default=text('false'), default=False)
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
    is_legacy_redeemed = Column(Boolean, server_default=text('false'), default=False)
    subscription_source = Column(String(64), nullable=True)
    custom_title = Column(String(120), nullable=True)
    winback_email_sent_at = Column(DateTime, nullable=True)  # إيميل "ليه وقفت؟" — يتبعت مرة واحدة بس
    first_lesson_email_sent_at = Column(DateTime, nullable=True)  # إيميل "خلصت أول درس" — مرة واحدة بس
    expiry5_email_sent_for = Column(DateTime, nullable=True)  # آخر end_at اتبعتله تنبيه الـ 5 أيام (يتصفّر مع التجديد)
    birthday_email_sent_year = Column(Integer, nullable=True)  # آخر سنة اتبعتله فيها إيميل عيد الميلاد (مرة/سنة)
    birthday_gift_year = Column(Integer, nullable=True)  # آخر سنة فعّل فيها هدية الـ 7 أيام (يمنع التكرار)
    inactive6_email_sent_at = Column(DateTime, nullable=True)  # آخر مرة اتبعتله تذكير "6 أيام مدخلتش"; يتصفّر لما يرجع نشط

    @property
    def is_online(self) -> bool:
        from datetime import datetime, timedelta
        if self.last_seen:
            return datetime.utcnow() - self.last_seen <= timedelta(seconds=65)
        return False

    end_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    # Relationships
    # دي علشان لو احنا شيلنا شخص معين كل الحاجات اللي معاه هتتمسح
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="sender", cascade="all, delete-orphan")
    course_progress = relationship("UserCourseProgress", back_populates="user", cascade="all, delete-orphan")
    progress = relationship("UserProgress", back_populates="user", cascade="all, delete-orphan")
    project_submissions = relationship("ProjectSubmission", foreign_keys="ProjectSubmission.user_id", back_populates="user", cascade="all, delete-orphan")


class PhoneOTP(Base):
    __tablename__ = "phone_otps"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    phone = Column(String, nullable=False)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# ═══════════════════════════════════════════
#  LEGACY
# ═══════════════════════════════════════════

class LegacyEmail(Base):
    __tablename__ = "legacy_emails"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

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


# ═══════════════════════════════════════════
#  DISCOUNT COUPONS
# ═══════════════════════════════════════════
#
# Two tables rather than a counter column on `coupons`.
#
# A `times_used` integer would answer "how many left" and nothing else. The
# brief asks for three more things a counter cannot give: who redeemed a code
# (the admin panel lists them), the ability to hand a slot back when a manual
# request is rejected, and — the important one — a DATABASE-level rule that one
# member cannot take the same coupon twice. That last one is a unique index over
# (coupon, member), and an index needs a row per redemption to sit on.
#
# So: `coupons` is the definition, `coupon_redemptions` is one row per member
# per coupon, and the count of live rows IS the usage counter. There is no
# second copy of the number to drift out of sync — the same lesson the pricing
# bug taught this codebase.


class CouponRedemptionStatus(str, enum.Enum):
    """Where a redemption sits between "started paying" and "counted".

    PENDING  — a Kashier order was created at the discounted price but has not
               been paid yet. Holds a slot, but only until `expires_at`; see
               coupon_service for why an abandoned checkout must not burn one of
               the thirty forever.
    ACTIVE   — the slot is spent: a confirmed Kashier payment, or a manual
               request that is pending or approved.
    EXPIRED  — a hold that lapsed. Written by coupon_service when it next takes
               the coupon's lock, rather than by a background job: the state has
               to be made explicit so the row lets go of its slot number, and
               the lock is the only place that can safely do it.
    RELEASED — a manual request was rejected. The slot goes back in the pool and
               the member may use the code again; the row is kept for history.

    Only PENDING and ACTIVE occupy a slot, and only those two hold a `slot_no`.
    """
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    RELEASED = "released"

    @classmethod
    def holding(cls):
        """The statuses that occupy one of a coupon's slots."""
        return (cls.PENDING.value, cls.ACTIVE.value)


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, index=True)
    # Stored lowercase, always. Every lookup lowercases its input first, so
    # `monzer`, `MONZER` and `Monzer` are one code and the unique index below is
    # what makes them one code rather than a rule someone has to remember.
    code = Column(String(64), nullable=False, unique=True, index=True)
    # What the member sees on screen and on the receipt — "Monzer", not "monzer".
    display_code = Column(String(64), nullable=True)
    discount_percent = Column(Numeric(5, 2), nullable=False)
    max_redemptions = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    redemptions = relationship("CouponRedemption", back_populates="coupon")

    @property
    def label(self) -> str:
        return self.display_code or self.code


class CouponRedemption(Base):
    """One member's claim on one coupon.

    `slot_no` is the belt to the row-lock's braces: "you are the Nth of thirty".
    Under the lock in coupon_service it is assigned the LOWEST number not
    currently held, and the unique index on (coupon_id, slot_no) means two
    transactions that somehow both decided they were number 30 cannot both land
    — the second one hits the index and rolls back.

    Lowest-free rather than count+1, which was the first attempt and is wrong:
    the moment any slot is handed back (a rejected manual request, a lapsed
    hold) the count and the highest number in use stop agreeing, and count+1
    starts naming a slot somebody already holds.

    NULL whenever the row is not holding anything — released and expired rows
    let go of their number so the next member can have it, and NULLs do not
    collide in a unique index.
    """
    __tablename__ = "coupon_redemptions"

    id = Column(Integer, primary_key=True, index=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Exactly one of these is set, depending on which rail the member took.
    payment_id = Column(Integer, ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)
    manual_request_id = Column(Integer, ForeignKey("manual_payment_requests.id", ondelete="SET NULL"), nullable=True)

    status = Column(String(16), nullable=False, default=CouponRedemptionStatus.PENDING.value, index=True)
    slot_no = Column(Integer, nullable=True)

    # The arithmetic, kept so the admin panel and any later dispute can see what
    # was actually charged and why — not recomputed from a percentage that may
    # have been edited since.
    original_amount = Column(Numeric(12, 2), nullable=False)
    final_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(8), nullable=False, default="EGP")
    plan_key = Column(String, nullable=True)

    # Only meaningful while PENDING — the moment the hold lapses.
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)
    released_at = Column(DateTime, nullable=True)

    coupon = relationship("Coupon", back_populates="redemptions")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("coupon_id", "slot_no", name="uq_coupon_redemption_slot"),
        # One live claim per (coupon, member) — the rule that stops the same
        # person taking the same coupon twice, held by the database rather than
        # by an `if` in a request handler. Partial, so a member whose manual
        # request was rejected can use the code again while the released row
        # stays for the record.
        #
        # Declared here as well as in the migration because main.py still calls
        # Base.metadata.create_all() on boot: a database created down that path
        # rather than through Alembic has to come out with the same guarantees.
        Index(
            "uq_coupon_redemption_live",
            "coupon_id", "user_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'active')"),
        ),
    )


# ═══════════════════════════════════════════
#  EMAIL CAMPAIGNS
# ═══════════════════════════════════════════

class EmailCampaignSend(Base):
    """سجل إرسال حملات الإيميل — صف لكل (حملة، إيميل) عشان نمنع تكرار الإرسال لنفس الشخص
    في نفس الحملة (dedup) حتى لو الإرسال اتقطع ورجع اشتغل. (الجدول بيتعمل auto عبر create_all)."""
    __tablename__ = "email_campaign_sends"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(String(200), index=True, nullable=False)  # اسم/معرّف الحملة
    email = Column(String(255), index=True, nullable=False)
    status = Column(String(500), nullable=False, default="sent")   # "sent" أو "failed: ..."
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)



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
    replies = relationship("Comment", foreign_keys=[parent_id], backref=backref("parent_ref", remote_side=[id]), cascade="all, delete-orphan")
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


class PostChannelRead(Base):
    """Per-user last-seen marker for community post channels (sidebar unread badge)."""
    __tablename__ = "post_channel_reads"
    __table_args__ = (UniqueConstraint('user_id', 'channel'),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    channel = Column(String, nullable=False)  # posts.category_slug e.g. "announcements"
    last_read_at = Column(DateTime, nullable=True)


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
    edited_at = Column(DateTime, nullable=True)  # set when the sender edits the message
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    channel = relationship("Channel", back_populates="messages")
    sender = relationship("User", back_populates="messages")
    reply_to = relationship("Message", remote_side=[id])
    reads = relationship("MessageRead", back_populates="message", cascade="all, delete-orphan")
    reactions = relationship("ChatMessageReaction", back_populates="message", cascade="all, delete-orphan")


class ChatMessageReaction(Base):
    __tablename__ = "chat_message_reactions"
    __table_args__ = (UniqueConstraint("message_id", "user_id", name="uq_chat_message_reaction_user"),)

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    emoji = Column(String(10), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    message = relationship("Message", back_populates="reactions")
    user = relationship("User")


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
    pdf_url = Column(String, nullable=True)
    # Certificate template image; personalized (name/course/date) client-side on download
    certificate_url = Column(String, nullable=True)
    total_lessons = Column(Integer, server_default=text('0'), default=0)
    course_time = Column(String, nullable=True)
    is_published = Column(Boolean, server_default=text('false'), default=False)
    sort_order = Column(Integer, server_default=text('0'), default=0)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    lessons = relationship("Lesson", back_populates="course", cascade="all, delete-orphan", order_by="Lesson.order")
    progress = relationship("UserCourseProgress", back_populates="course", cascade="all, delete-orphan")
    project_submissions = relationship("ProjectSubmission", back_populates="course", cascade="all, delete-orphan")
    exams = relationship("Exam", back_populates="course", cascade="all, delete-orphan", order_by="Exam.sort_order")


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    video_url = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    section_title = Column(String, nullable=True)
    section_order = Column(Integer, server_default=text('0'), default=0)
    order = Column(Integer, server_default=text('0'), default=0)
    duration_minutes = Column(Integer, server_default=text('0'), default=0)
    # Bunny.net (legacy)
    bunny_video_url = Column(String, nullable=True)
    # VdoCipher
    vdo_video_id = Column(String, nullable=True)
    video_status = Column(String, server_default=text("'pending'"), default="pending")  # pending | processing | ready | error
    is_free_preview = Column(Boolean, server_default=text('false'), default=False)
    # Marks a lesson that has an associated project — course page shows a "Go to Projects" button
    is_project = Column(Boolean, server_default=text('false'), default=False)
    # PDF attachment
    pdf_url = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    course = relationship("Course", back_populates="lessons")
    progress = relationship("UserProgress", back_populates="lesson", cascade="all, delete-orphan")


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


class UserProgress(Base):
    __tablename__ = "user_progress"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    lesson_id = Column(Integer, ForeignKey("lessons.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    completed_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "lesson_id"),)

    user = relationship("User", back_populates="progress")
    lesson = relationship("Lesson", back_populates="progress")


class Certificate(Base):
    __tablename__ = "certificates"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    certificate_id = Column(String, unique=True)  # GHAWY-2026-XXXXXX
    issued_at = Column(DateTime, default=datetime.utcnow)
    completion_email_sent_at = Column(DateTime, nullable=True)  # إيميل "شهادتك جاهزة" — مرة واحدة لكل كورس
    __table_args__ = (UniqueConstraint("user_id", "course_id"),)


class ProjectSubmission(Base):
    __tablename__ = "project_submissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String, nullable=False)
    file_url = Column(String, nullable=False)
    json_payload = Column(JSON, nullable=False)
    status = Column(String, nullable=False, default=ProjectSubmissionStatus.PENDING.value, server_default=text("'pending'"))
    admin_notes = Column(Text, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)
    updated_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow, onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id], back_populates="project_submissions")
    course = relationship("Course", back_populates="project_submissions")
    reviewer = relationship("User", foreign_keys=[reviewed_by])


class Exam(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    pass_percent = Column(Integer, server_default=text('70'), default=70)
    # questions: list of {"text": str, "options": [str, ...], "correct": int}
    questions = Column(JSON, nullable=False, default=list, server_default=text("'[]'"))
    is_published = Column(Boolean, server_default=text('false'), default=False)
    sort_order = Column(Integer, server_default=text('0'), default=0)
    # Curriculum placement: show this exam right after this lesson (null = end of course)
    after_lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    course = relationship("Course", back_populates="exams")
    attempts = relationship("ExamAttempt", back_populates="exam", cascade="all, delete-orphan")


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    score = Column(Integer, nullable=False, default=0)  # percent 0-100
    correct_count = Column(Integer, nullable=False, default=0)
    total_questions = Column(Integer, nullable=False, default=0)
    passed = Column(Boolean, nullable=False, default=False, server_default=text('false'))
    # answers: {"<question_index>": <selected_option_index>}
    answers = Column(JSON, nullable=False, default=dict, server_default=text("'{}'"))
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    exam = relationship("Exam", back_populates="attempts")
    user = relationship("User")

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
    avatar_url = Column(String, nullable=True)         # new field
    avatar_initials = Column(String(5), nullable=True) # e.g. "MZ"
    avatar_color = Column(String(20), nullable=True)   # hex color
    category = Column(String, nullable=True)      # "AI", "Business", etc.
    is_featured = Column(Boolean, server_default=text('false'), default=False)
    sessions_count = Column(Integer, server_default=text('0'), default=0)
    attendees_count = Column(Integer, server_default=text('0'), default=0)
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
    platform = Column(String, nullable=True)      # "Zoom" / "YouTube" / etc.
    session_url = Column(String, nullable=True)
    status = Column(String, server_default=text("'upcoming'"), default="upcoming")  # upcoming / past / cancelled
    attendees_count = Column(Integer, server_default=text('0'), default=0)
    rating = Column(Numeric(3,1), server_default=text('0.0'), default=0.0)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)
    
    guest = relationship("Guest", back_populates="sessions")

class SuggestedGuest(Base):
    __tablename__ = "suggested_guests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    user = relationship("User")

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
    instructor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(Enum(LiveSessionStatus), default=LiveSessionStatus.UPCOMING)
    difficulty = Column(Enum(LiveSessionDifficulty), default=LiveSessionDifficulty.BEGINNER)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    stream_url = Column(String, nullable=True)
    recording_url = Column(String, nullable=True)
    max_attendees = Column(Integer, server_default=text('0'), default=0)
    current_viewers = Column(Integer, server_default=text('0'), default=0)
    is_recording_available = Column(Boolean, server_default=text('false'), default=False)
    tags = Column(String, nullable=True)
    # New fields for scheduled live sessions
    youtube_url = Column(String, nullable=True)
    zoom_url = Column(String, nullable=True)
    is_published = Column(Boolean, server_default=text('false'), default=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    scheduled_at = Column(DateTime, nullable=True)  # primary scheduled time
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)
    
    instructor = relationship("User", foreign_keys=[instructor_id])
    creator = relationship("User", foreign_keys=[created_by])
    bookings = relationship("SessionBooking", back_populates="session", cascade="all, delete-orphan")
    reminders = relationship("SessionReminder", back_populates="session", cascade="all, delete-orphan")
    projects = relationship("SessionProject", back_populates="session", cascade="all, delete-orphan")
    attendees = relationship("LiveAttendee", back_populates="session", cascade="all, delete-orphan")


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


class LiveAttendee(Base):
    __tablename__ = "live_attendees"
    __table_args__ = (UniqueConstraint('session_id', 'user_id'),)

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("live_sessions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    registered_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    session = relationship("LiveSession", back_populates="attendees")
    user = relationship("User")

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
    amount = Column(Numeric(12, 2), nullable=True)     # optional, what they CLAIM to have paid — user-supplied
    # What the member actually owed, worked out server-side from the plan and
    # any coupon. `amount` above is typed by the payer and so is a claim, not a
    # figure; the reviewer needs a number the payer could not touch to compare
    # the receipt against, or a discounted transfer looks short and gets
    # rejected by mistake.
    expected_amount = Column(Numeric(12, 2), nullable=True)
    coupon_code = Column(String(64), nullable=True)    # lowercase code, or NULL
    plan = Column(String, nullable=True)               # monthly | quarterly | yearly (drives subscription length)
    notes = Column(Text, nullable=True)                # any notes from user
    status = Column(String, default="pending")         # pending | approved | rejected
    invite_token = Column(String, nullable=True, unique=True)  # one-time registration token
    invite_sent_at = Column(DateTime, nullable=True)
    invite_expires_at = Column(DateTime, nullable=True)        # token valid for 48 hours
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

# ═══════════════════════════════════════════
#  AI UPDATES (Standalone Section)
# ═══════════════════════════════════════════

class AiUpdatePost(Base):
    __tablename__ = "ai_update_posts"

    id = Column(Integer, primary_key=True, index=True)
    post_type = Column(Enum(AiUpdatePostType), nullable=False, default=AiUpdatePostType.TEXT)
    # Editorial category (news / tools / models / updates / tutorials / discussions).
    # Distinct from post_type (which is the media kind). NULL is treated as "news".
    category = Column(String(30), nullable=True, default="news")
    title = Column(String(120), nullable=False)
    body = Column(Text, nullable=False)
    image_url = Column(String, nullable=True)
    video_url = Column(String, nullable=True)
    # Multi-media support: list of {"type": "image"|"video", "url": str}.
    # image_url / video_url are kept in sync with the first item for legacy readers.
    media = Column(JSON, nullable=True)
    is_pinned = Column(Boolean, default=False)
    
    # Denormalized counts
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    author = relationship("User")
    reactions = relationship("AiUpdateReaction", back_populates="post", cascade="all, delete-orphan")
    comments = relationship("AiUpdateComment", back_populates="post", cascade="all, delete-orphan")
    poll = relationship("AiUpdatePoll", back_populates="post", uselist=False, cascade="all, delete-orphan")


class AiUpdatePoll(Base):
    __tablename__ = "ai_update_polls"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("ai_update_posts.id", ondelete="CASCADE"), nullable=False, unique=True)
    question = Column(String, nullable=False)
    total_votes = Column(Integer, default=0)

    post = relationship("AiUpdatePost", back_populates="poll")
    options = relationship("AiUpdatePollOption", back_populates="poll", cascade="all, delete-orphan", order_by="AiUpdatePollOption.id")
    votes = relationship("AiUpdatePollVote", back_populates="poll", cascade="all, delete-orphan")


class AiUpdatePollOption(Base):
    __tablename__ = "ai_update_poll_options"

    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey("ai_update_polls.id", ondelete="CASCADE"), nullable=False)
    text = Column(String, nullable=False)
    image_url = Column(String, nullable=True)
    votes_count = Column(Integer, default=0)

    poll = relationship("AiUpdatePoll", back_populates="options")
    votes = relationship("AiUpdatePollVote", back_populates="option", cascade="all, delete-orphan")


class AiUpdatePollVote(Base):
    __tablename__ = "ai_update_poll_votes"
    __table_args__ = (UniqueConstraint('poll_id', 'user_id'),)

    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey("ai_update_polls.id", ondelete="CASCADE"), nullable=False)
    option_id = Column(Integer, ForeignKey("ai_update_poll_options.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    poll = relationship("AiUpdatePoll", back_populates="votes")
    option = relationship("AiUpdatePollOption", back_populates="votes")
    user = relationship("User")


class AiUpdateReaction(Base):
    __tablename__ = "ai_update_reactions"
    __table_args__ = (UniqueConstraint('post_id', 'user_id'),)

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("ai_update_posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    emoji = Column(String(10), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    post = relationship("AiUpdatePost", back_populates="reactions")
    user = relationship("User")


class AiUpdateComment(Base):
    __tablename__ = "ai_update_comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("ai_update_posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Integer, ForeignKey("ai_update_comments.id", ondelete="CASCADE"), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    post = relationship("AiUpdatePost", back_populates="comments")
    author = relationship("User")
    replies = relationship("AiUpdateComment", backref=backref("parent", remote_side=[id]), cascade="all, delete-orphan")


class AiUpdateRead(Base):
    """Per-user last-seen marker for the AI Updates feed (sidebar unread badge)."""
    __tablename__ = "ai_update_reads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    last_read_at = Column(DateTime, nullable=True)


class CourseReview(Base):
    __tablename__ = "course_reviews"
    __table_args__ = (UniqueConstraint('course_id', 'user_id'),)

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    course = relationship("Course", backref=backref("reviews", cascade="all, delete-orphan"))
    user = relationship("User")


# ══════════════════════════════════════════════════════════════
#  NOTIFICATIONS
# ══════════════════════════════════════════════════════════════

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    type = Column(String, nullable=False, default="info")
    link = Column(String, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    user = relationship("User")


# ══════════════════════════════════════════════════════════════
#  DAILY REPORTS (Team Section)
# ══════════════════════════════════════════════════════════════

class TeamRole(str, enum.Enum):
    COMMUNITY_MANAGER = "community_manager"
    TECHNICAL_ENGINEER = "technical_engineer"
    CUSTOMER_SUCCESS = "customer_success"


class DailyReport(Base):
    """
    ريبورت يومي — كل عضو في الفريق يكتب ريبورت عن إنجازاته.
    ممكن يكون في أكتر من ريبورت لنفس اليوم.

    المكان: backend/app/models.py
    """
    __tablename__ = "daily_reports"

    id = Column(Integer, primary_key=True, index=True)

    # صاحب الريبورت
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # الدور المختار وقت الكتابة
    team_role = Column(Enum(TeamRole), nullable=False)

    # الأسئلة الأربعة
    what_went_well = Column(Text, nullable=False)        # ايه اللي كان كويس النهارده؟
    what_can_improve = Column(Text, nullable=False)      # ايه اللي ممكن يتحسن؟
    ai_updates_count = Column(Integer, nullable=False, server_default=text('0'), default=0)   # عملت كام AI Update؟
    messages_replied_count = Column(Integer, nullable=False, server_default=text('0'), default=0)  # عملت ريبلاي لكام ماسدج؟

    # حقول جديدة ديناميكية حسب الـ role
    hours_worked = Column(Numeric(5, 2), nullable=True)
    productivity = Column(Integer, nullable=True)
    community_posts_count = Column(Integer, nullable=True)
    members_welcomed_count = Column(Integer, nullable=True)
    wins_encouraged_count = Column(Integer, nullable=True)
    avg_reply_speed = Column(String, nullable=True)
    platform_engagement = Column(String, nullable=True)
    projects_reviewed_count = Column(Integer, nullable=True)
    projects_accepted_count = Column(Integer, nullable=True)
    projects_rejected_count = Column(Integer, nullable=True)
    workflows_resolved_count = Column(Integer, nullable=True)
    avg_resolution_time = Column(String, nullable=True)

    # التاريخ (تاريخ اليوم — مش datetime — لتسهيل الفلترة)
    report_date = Column(Date, nullable=False, index=True)

    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    # Relationship
    author = relationship("User")


class CommunityFeedback(Base):
    """
    Feedback from community members.
    """
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(Enum(TeamRole), nullable=False)
    person_name = Column(String, nullable=False)
    # Legacy: kept nullable for old records; new feedbacks identify the member by id instead.
    person_email = Column(String, nullable=True)
    # The member this feedback is about, stored as a plain user id (validated in
    # the app layer). No FK constraint — avoids locking the busy users table.
    person_user_id = Column(Integer, nullable=True)
    # Optional image attached to the feedback, shown inside the card.
    image_url = Column(String, nullable=True)
    feedback_text = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    # Relationship
    submitted_by_user = relationship("User")


class AdminMemberNote(Base):
    """
    Notes added by admins to member profiles.
    """
    __tablename__ = "admin_member_notes"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    note = Column(Text, nullable=False, default='')
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=datetime.utcnow, default=datetime.utcnow)

    member = relationship("User", foreign_keys=[member_id])
    admin = relationship("User", foreign_keys=[updated_by])


class BirthdayGiftClaim(Base):
    """
    طلبات هدية عيد الميلاد (7 أيام مجانية).
    زرار الإيميل مبقاش يفعّل الهدية فوراً — بيسجّل طلب pending هنا، والأدمن
    بيوافق عليه من الـ Team Dashboard (Pending Requests) فتتضاف الأيام
    ويوصل لليوزر DM تهنئة أوتوماتيك من أكونت محمد صلاح.
    (الجدول بيتعمل auto عبر create_all — مفيش migration)
    user_id/decided_by من غير FK constraint عشان نتجنب أي lock على جدول users.
    """
    __tablename__ = "birthday_gift_claims"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    year = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="pending", server_default="pending")  # pending / approved / rejected
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)
    decided_by = Column(Integer, nullable=True)
