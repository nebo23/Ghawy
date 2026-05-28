from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from app.models import PaymentMethod, PaymentStatus, ChannelType, MessageType, MemberRole

# ─── User Schemas ───────────────────────────────────────────

class UserRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    phone: str
    country: Optional[str] = None
    governorate: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# دي البيانات اللي بيبعتها لل team dashboard
class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    country: Optional[str] = None
    governorate: Optional[str] = None
    is_active: bool
    is_verified: bool
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
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
    is_active: bool = False
    social_media_url: Optional[str] = None
    show_social_media: bool = True
    created_at: datetime

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

class PayPalCreateOrder(BaseModel):
    amount: float
    currency: str = "USD"

class KashierCreateOrder(BaseModel):
    amount: float
    currency: str = "EGP"
    user_email: str = ""

class KashierOrderOut(BaseModel):
    payment_url: str
    order_id: str
    amount: str
    currency: str

class PayPalOrderOut(BaseModel):
    order_id: str
    approval_url: str


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
    channel_name: Optional[str] = None

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
    video_url: Optional[str] = None
    content: Optional[str] = None
    section_title: Optional[str] = None
    section_order: int = 0
    order: int
    duration_minutes: int
    created_at: datetime

    class Config:
        from_attributes = True

class CourseOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    total_lessons: int
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
    video_url: Optional[str] = None
    content: Optional[str] = None
    order: int = 0
    duration_minutes: int = 0

class CourseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    total_lessons: int = 0
    is_published: bool = False
