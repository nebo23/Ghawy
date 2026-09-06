from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Any, Dict, Literal
from datetime import datetime
from decimal import Decimal
from app.models import PaymentMethod, PaymentStatus, ChannelType, MessageType, MemberRole, TeamRole

# ─── User Schemas ───────────────────────────────────────────

class UserRegister(BaseModel):
    # The signup form collects the name in two fields; full_name is derived
    # server-side (see app.services.name_utils) and stays the display name.
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    country: Optional[str] = None
    governorate: str
    turnstile_token: Optional[str] = None
    # «اسمي مش بالعربي» — العضو قال إن اسمه مش متكتب بالعربي، فالقاعدة
    # بتتخطى ليه والاسم بيتخزّن زي ما كتبه. بيتحفظ على الحساب عشان
    # الأونبوردنج ما يسألوش تاني.
    latin_name_ok: bool = False

class SendPhoneOTP(BaseModel):
    phone: str

class VerifyPhoneOTP(BaseModel):
    phone: str
    code: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# دي البيانات اللي بيبعتها لل team dashboard
class UserOut(BaseModel):
    id: int
    email: str
    full_name: str = ""
    phone: Optional[str] = None
    country: Optional[str] = None
    governorate: Optional[str] = None
    is_active: bool
    is_verified: bool
    is_admin: bool = False
    is_owner: bool = False
    avatar_url: Optional[str] = None
    selected_avatar: Optional[str] = None
    bio: Optional[str] = None
    badge: str = "Member"
    created_at: datetime
    is_online: bool = False

    class Config:
        from_attributes = True

class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    social_media_url: Optional[str] = None
    show_social_media: Optional[bool] = None

class OnboardingUpdate(BaseModel):
    birth_date: Optional[str] = None        # "DD/MM/YYYY" format
    social_media_url: Optional[str] = None
    avatar_url: Optional[str] = None        # uploaded photo URL
    selected_avatar: Optional[str] = None   # preset avatar filename

# دا الحساب الشخصي 
class UserMemberOut(BaseModel):
    id: int
    full_name: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    level: int = 1
    xp: int = 0
    streak_days: int = 0
    badge: str = "Member"
    is_admin: bool = False
    is_owner: bool = False
    is_active: bool = False
    onboarding_completed: bool = False
    social_media_url: Optional[str] = None
    show_social_media: bool = True
    created_at: datetime
    custom_title: Optional[str] = None
    # تابات لوحة الفريق المسموح بيها — الـ owner بياخد الكل، والعضو العادي فاضية
    permissions: List[str] = []

    class Config:
        from_attributes = True


# دا اللي بيظهر لما حد يدوس علي البروفايل بتاعك
class PublicProfileOut(BaseModel):
    id: int
    full_name: str
    username: str
    avatar_url: Optional[str] = None
    selected_avatar: Optional[str] = None
    bio: Optional[str] = None
    social_media_url: Optional[str] = None
    show_social_media: bool = True
    level: int = 1
    xp: int = 0
    badge: str = "Member"
    streak_days: int = 0
    joined_at: str = ""
    post_count: int = 0
    is_online: bool = False

    class Config:
        from_attributes = True

# علشان السيرفر يفتكرك (Authentication)
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Optional[dict] = None


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    verification_code: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


# ─── Password reset ──────────────────────────────────────────
# Three steps, not two: the member types the code and the new password on
# different screens, so the code is traded for a short-lived token first. That
# keeps the code out of the page while they pick a password, and makes the last
# request unreplayable once it has run.

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyResetCodeRequest(BaseModel):
    email: EmailStr
    code: str


class ResetPasswordRequest(BaseModel):
    reset_token: str
    password: str

# ─── Payment Schemas ─────────────────────────────────────────


class KashierCreateOrder(BaseModel):
    # `amount` and `currency` are accepted and then ignored — the router reads
    # both out of PLAN_PRICES. They stay on the model only so older frontends
    # that still send them are not rejected by validation.
    amount: float
    currency: str = "EGP"
    plan_key: str = "monthly_egp"
    user_email: str = ""
    # A coupon NAME, and nothing else. There is deliberately no
    # `discount_percent` or `final_amount` field here — the price after a
    # discount is worked out server-side, same rule as the plan price itself.
    coupon_code: Optional[str] = None

class KashierOrderOut(BaseModel):
    payment_url: str
    order_id: str
    amount: str
    currency: str


class PaymentOut(BaseModel):
    id: int
    user_id: int
    method: PaymentMethod
    status: PaymentStatus
    amount: float
    currency: str
    provider_order_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ─── Community Schemas ───────────────────────────────────────

class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    emoji: str = "📁"
    sort_order: int = 0

    class Config:
        from_attributes = True

class PostCreate(BaseModel):
    category_id: Optional[int] = None
    title: str
    body: str

class PostCreateNew(BaseModel):
    title: str
    content: str
    category: str
    tag: Optional[str] = None
    tag_color: Optional[str] = None
    image_url: Optional[str] = None

class PostUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None

class PostOut(BaseModel):
    id: int
    user_id: int
    category_id: Optional[int] = None
    title: str
    body: str
    like_count: int = 0
    comment_count: int = 0
    is_pinned: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    author: UserMemberOut

    class Config:
        from_attributes = True

class PostAuthorOut(BaseModel):
    id: int
    name: str
    avatar_url: Optional[str] = None
    selected_avatar: Optional[str] = None
    badge: str = "Member"

class PostOutNew(BaseModel):
    id: int
    title: str
    content: str
    category: str
    tag: Optional[str] = None
    tag_color: Optional[str] = None
    image_url: Optional[str] = None
    likes_count: int = 0
    comments_count: int = 0
    created_at: str  # "2h ago" format
    author: PostAuthorOut

class CommentCreate(BaseModel):
    body: str
    parent_id: Optional[int] = None

class CommentOutNew(BaseModel):
    id: int
    content: str
    created_at: str  # "2h ago" format
    author: PostAuthorOut

class CommentOut(BaseModel):
    id: int
    post_id: int
    user_id: int
    parent_id: Optional[int] = None
    body: str
    created_at: datetime
    author: UserMemberOut

    class Config:
        from_attributes = True

# ─── Chat Schemas ────────────────────────────────────────────

class ChannelCreate(BaseModel):
    name: str
    channel_type: ChannelType = ChannelType.GROUP
    description: Optional[str] = None

class ChannelOut(BaseModel):
    id: int
    name: str
    channel_type: ChannelType
    description: Optional[str] = None
    created_at: datetime
    member_count: Optional[int] = 0
    unread_count: Optional[int] = 0
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class MessageOut(BaseModel):
    id: int
    channel_id: int
    sender_id: int
    content: Optional[str] = None
    message_type: MessageType = MessageType.TEXT
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    reply_to_id: Optional[int] = None
    read_count: int = 0
    created_at: datetime
    sender_name: Optional[str] = None
    sender_avatar: Optional[str] = None
    sender_badge: Optional[str] = None
    sender_is_admin: bool = False
    channel_name: Optional[str] = None
    reactions_summary: Optional[list[dict]] = []

    class Config:
        from_attributes = True

class MessageCreate(BaseModel):
    content: Optional[str] = None
    message_type: MessageType = MessageType.TEXT
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    reply_to_id: Optional[int] = None

class ChatMemberOut(BaseModel):
    id: int
    user_id: int
    channel_id: int
    role: MemberRole
    joined_at: datetime
    user: Optional[UserMemberOut] = None

    class Config:
        from_attributes = True

# ─── Course Schemas ──────────────────────────────────────────

class LessonOut(BaseModel):
    id: int
    course_id: int
    title: str
    description: Optional[str] = None
    video_url: Optional[str] = None
    content: Optional[str] = None
    section_title: Optional[str] = None
    section_order: int = 0
    order: int
    duration_minutes: int
    bunny_video_url: Optional[str] = None
    vdo_video_id: Optional[str] = None
    video_status: str = "pending"
    is_free_preview: bool = False
    is_project: bool = False
    pdf_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class CourseOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    pdf_url: Optional[str] = None
    certificate_url: Optional[str] = None
    total_lessons: int
    course_time: Optional[str] = None
    is_published: bool
    sort_order: int = 0
    created_at: datetime

    class Config:
        from_attributes = True

class CourseDetailOut(CourseOut):
    lessons: List[LessonOut] = []

    class Config:
        from_attributes = True

# ── Public (anonymous) catalogue views ────────────────────────
# The marketing site and the course card grid are reachable without a token, so
# they get these shapes instead of LessonOut/CourseOut. What is missing here is
# the point: vdo_video_id, bunny_video_url, pdf_url, video_url and content are
# the paid product, and a schema that cannot carry them cannot leak them by a
# later field being added in the wrong place. `has_video`/`has_pdf` give the
# catalogue the "there is a video here" signal it actually renders.

class PublicLessonOut(BaseModel):
    id: int
    course_id: int
    title: str
    description: Optional[str] = None
    section_title: Optional[str] = None
    section_order: int = 0
    order: int
    duration_minutes: int
    video_status: str = "pending"
    is_free_preview: bool = False
    is_project: bool = False
    has_video: bool = False
    has_pdf: bool = False

    class Config:
        from_attributes = True

class PublicCourseOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    certificate_url: Optional[str] = None
    total_lessons: int
    course_time: Optional[str] = None
    is_published: bool
    sort_order: int = 0
    created_at: datetime

    class Config:
        from_attributes = True

class PublicCourseDetailOut(PublicCourseOut):
    lessons: List[PublicLessonOut] = []

    class Config:
        from_attributes = True

class UserCourseProgressOut(BaseModel):
    completed_lessons: int
    percent: float

    class Config:
        from_attributes = True

class CourseProgressUpdate(BaseModel):
    completed_lessons: int

class LessonCreate(BaseModel):
    title: str
    description: Optional[str] = None
    bunny_video_url: Optional[str] = None
    vdo_video_id: Optional[str] = None
    pdf_url: Optional[str] = None
    order: Optional[int] = 0
    duration_minutes: Optional[int] = None
    is_free_preview: bool = False

class AdminLessonCreate(BaseModel):
    title: str
    section_title: Optional[str] = None
    order: int = 0
    duration_minutes: int = 0
    bunny_video_url: Optional[str] = None
    vdo_video_id: Optional[str] = None
    is_project: bool = False

class LessonUpdate(BaseModel):
    title: Optional[str] = None
    section_title: Optional[str] = None
    description: Optional[str] = None
    bunny_video_url: Optional[str] = None
    vdo_video_id: Optional[str] = None
    video_status: Optional[str] = None
    pdf_url: Optional[str] = None
    order: Optional[int] = None
    duration_minutes: Optional[int] = None
    is_free_preview: Optional[bool] = None
    is_project: Optional[bool] = None

class CourseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    pdf_url: Optional[str] = None
    total_lessons: int = 0
    course_time: Optional[str] = None
    is_published: bool = False

class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    pdf_url: Optional[str] = None
    course_time: Optional[str] = None
    is_published: Optional[bool] = None

class CourseReorder(BaseModel):
    order: List[int]  # course IDs in the desired display order


ProjectStatusLiteral = Literal["pending", "approved", "changes_requested"]

class ProjectSubmissionOut(BaseModel):
    id: int
    user_id: int
    course_id: int
    file_name: str
    file_url: str
    json_payload: Dict[str, Any] | List[Any]
    status: ProjectStatusLiteral
    admin_notes: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AdminProjectSubmissionOut(ProjectSubmissionOut):
    member_name: str
    # None لما المشاهد ملوش صلاحية `member-contacts` — مش string فاضي،
    # عشان الواجهة تعرف تفرّق بين "مفيش إيميل" و"مش من حقك تشوفه".
    member_email: Optional[str] = None
    course_title: str
    reviewer_name: Optional[str] = None

class ProjectNotesUpdate(BaseModel):
    notes: str = ""

# ─── Exam Schemas ────────────────────────────────────────────

class ExamQuestionIn(BaseModel):
    text: str
    options: List[str]
    correct: int  # index of the correct option


class ExamCreate(BaseModel):
    title: str
    description: Optional[str] = None
    pass_percent: int = 70
    questions: List[ExamQuestionIn] = []
    is_published: bool = False
    after_lesson_id: Optional[int] = None  # place exam after this lesson in the curriculum


class ExamUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    pass_percent: Optional[int] = None
    questions: Optional[List[ExamQuestionIn]] = None
    is_published: Optional[bool] = None
    sort_order: Optional[int] = None
    after_lesson_id: Optional[int] = None


class ExamSubmit(BaseModel):
    # {"<question_index>": <selected_option_index>}
    answers: Dict[str, int] = {}

# ─── Live Session Schemas ────────────────────────────────────

class LiveSessionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    scheduled_at: Optional[str] = None  # ISO 8601 datetime string
    youtube_url: Optional[str] = None
    zoom_url: Optional[str] = None

class LiveSessionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_at: Optional[str] = None
    youtube_url: Optional[str] = None
    zoom_url: Optional[str] = None
    is_published: Optional[bool] = None

# ─── Feedback Schemas ────────────────────────────────────────

class FeedbackCreate(BaseModel):
    role: TeamRole
    person_name: str
    person_user_id: Optional[int] = None
    image_url: Optional[str] = None
    feedback_text: str

class FeedbackOut(BaseModel):
    id: int
    user_id: int
    role: TeamRole
    person_name: str
    person_user_id: Optional[int] = None
    person_email: Optional[str] = None   # legacy records only
    image_url: Optional[str] = None
    feedback_text: str
    created_at: datetime
    submitted_by_name: Optional[str] = None
    submitted_by_avatar: Optional[str] = None

    class Config:
        from_attributes = True

# ─── Coupon Admin Schemas ────────────────────────────────────
#
# The limits live here rather than as `if` statements in the handler so a bad
# number comes back as a described 422 the panel can render, instead of a
# generic message someone has to translate.
#
# What is deliberately NOT on CouponUpdate: `code`. It is the lookup key — it
# is stored lowercase behind a unique index, it travels in payment links as
# `?coupon=...`, and a live 30-minute hold is keyed to the coupon a member
# already applied. Renaming it would break the link in someone's hand and the
# checkout tab they have open. Cosmetics change through `display_code`.

COUPON_CODE_PATTERN = r"^[A-Za-z0-9]+$"


def _clean_coupon_code(v: str) -> str:
    """Trim, then insist on letters and digits only.

    The code goes into a URL as `?coupon=...`. A space becomes `%20`, and a
    member who copies the code off the screen and types it by hand never
    reproduces that — so the character set is narrowed at the door rather than
    debugged later.
    """
    v = (v or "").strip()
    if not v:
        raise ValueError("Code cannot be empty")
    if len(v) > 64:
        raise ValueError("Code cannot be longer than 64 characters")
    import re
    if not re.match(COUPON_CODE_PATTERN, v):
        raise ValueError("Code can only contain letters and numbers — no spaces or symbols")
    return v


class CouponCreate(BaseModel):
    # Kept exactly as typed: `code` is lowercased for storage, and this same
    # string is saved as `display_code` so the panel and the receipt say
    # "Monzer" rather than "monzer".
    code: str
    discount_percent: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    max_redemptions: int = Field(ge=1)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def _validate_code(cls, v: str) -> str:
        return _clean_coupon_code(v)


class CouponUpdate(BaseModel):
    """Only what changed. Every field optional; `code` is not a field."""
    discount_percent: Optional[Decimal] = Field(default=None, gt=0, le=100, max_digits=5, decimal_places=2)
    max_redemptions: Optional[int] = Field(default=None, ge=1)
    is_active: Optional[bool] = None
    display_code: Optional[str] = None

    @field_validator("display_code")
    @classmethod
    def _validate_display_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return _clean_coupon_code(v)
