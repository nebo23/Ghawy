from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any, Dict, Literal
from datetime import datetime
from app.models import PaymentMethod, PaymentStatus, ChannelType, MessageType, MemberRole, TeamRole

# ─── User Schemas ───────────────────────────────────────────

class UserRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    country: Optional[str] = None
    governorate: str

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

# ─── Payment Schemas ─────────────────────────────────────────


class KashierCreateOrder(BaseModel):
    amount: float
    currency: str = "EGP"
    plan_key: str = "monthly_egp"
    user_email: str = ""

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
    total_lessons: int
    course_time: Optional[str] = None
    is_published: bool
    created_at: datetime

    class Config:
        from_attributes = True

class CourseDetailOut(CourseOut):
    lessons: List[LessonOut] = []

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
    member_email: str
    course_title: str
    reviewer_name: Optional[str] = None

class ProjectNotesUpdate(BaseModel):
    notes: str = ""

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
    person_email: EmailStr
    feedback_text: str

class FeedbackOut(BaseModel):
    id: int
    user_id: int
    role: TeamRole
    person_name: str
    person_email: str
    feedback_text: str
    created_at: datetime
    submitted_by_name: Optional[str] = None
    submitted_by_avatar: Optional[str] = None

    class Config:
        from_attributes = True

