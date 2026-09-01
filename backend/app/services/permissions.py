"""
صلاحيات فريق العمل — أي تابات لوحة الفريق يقدر الأدمن يشوفها.

الـ owner عنده كل حاجة دايماً وملهوش صف صلاحيات؛ اللي بيتخزن في
`users.staff_permissions` هو مفاتيح التابات اللي الـ owner فتحها للأدمن ده.
العمود JSON نصّي: `null` معناها "لسه محدش عدّله" فبيقع على الديفولت القديم
(التابات الخمسة بتاعت الناس)، وقايمة فاضية `[]` معناها الـ owner قفل كل حاجة
بإيده — الفرق بينهم مقصود، عشان أدمن اتشال منه كل حاجة ميرجعش للديفولت لوحده.
"""
import json
import logging
from typing import Iterable, List, Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)


# ── الكتالوج ──────────────────────────────────────────────────
# المفتاح = الـ data-tab بتاع الزرار في teamdashboard.html، عشان الفرونت
# يقدر يخفي/يظهر الأزرار من نفس القايمة من غير جدول ترجمة تاني.
PERMISSIONS = [
    # الناس
    {"key": "users",             "label": "Members",           "label_ar": "الأعضاء",            "group": "people"},
    {"key": "students-progress", "label": "Students Progress", "label_ar": "تقدّم الطلاب",       "group": "people"},
    {"key": "projects",          "label": "Projects",          "label_ar": "المشاريع",           "group": "people"},
    {"key": "reports",           "label": "Reports",           "label_ar": "التقارير",           "group": "people"},
    {"key": "feedbacks",         "label": "Feedbacks",         "label_ar": "الآراء",             "group": "people"},
    # الفلوس
    {"key": "payments",          "label": "Payments",          "label_ar": "المدفوعات",          "group": "money"},
    {"key": "pending-requests",  "label": "Pending Requests",  "label_ar": "الطلبات المعلّقة",   "group": "money"},
    {"key": "coupons",           "label": "Coupons",           "label_ar": "الكوبونات",          "group": "money"},
    {"key": "analytics",         "label": "Analytics",         "label_ar": "التحليلات",          "group": "money"},
    # المحتوى
    {"key": "courses",           "label": "Courses",           "label_ar": "الكورسات",           "group": "content"},
    {"key": "live-sessions",     "label": "Live Sessions",     "label_ar": "اللايفات",           "group": "content"},
    {"key": "guest-of-honors",   "label": "Guest of Honors",   "label_ar": "ضيوف الشرف",         "group": "content"},
    {"key": "emails",            "label": "Emails",            "label_ar": "حملات الإيميل",      "group": "content"},
    # صلاحيات مش تاب — حاجات جوه تاب موجود
    {"key": "member-contacts",   "label": "Member contacts (email & phone)",
     "label_ar": "بيانات التواصل (إيميل وتليفون)", "group": "extra"},
]

PERMISSION_KEYS = [p["key"] for p in PERMISSIONS]

GROUP_LABELS = {
    "people":  {"label": "People",  "label_ar": "الناس"},
    "money":   {"label": "Money",   "label_ar": "الفلوس"},
    "content": {"label": "Content", "label_ar": "المحتوى"},
    "extra":   {"label": "Extras",  "label_ar": "إضافي"},
}

# ديفولت الأدمن الجديد = نفس اللي كان شايفه قبل الفيتشر دي.
DEFAULT_ADMIN_PERMISSIONS = [
    "users", "students-progress", "projects", "reports", "feedbacks",
]


# ── قراءة ─────────────────────────────────────────────────────
def normalize_permissions(values: Optional[Iterable[str]]) -> List[str]:
    """رجّع المفاتيح المعروفة بس، من غير تكرار، وبترتيب الكتالوج."""
    wanted = {str(v).strip() for v in (values or [])}
    return [k for k in PERMISSION_KEYS if k in wanted]


def permissions_for(user) -> List[str]:
    """كل الصلاحيات الفعّالة لليوزر ده."""
    if user is None:
        return []
    if getattr(user, "is_owner", False):
        return list(PERMISSION_KEYS)
    if not getattr(user, "is_admin", False):
        return []

    raw = getattr(user, "staff_permissions", None)
    if raw is None or raw == "":
        return list(DEFAULT_ADMIN_PERMISSIONS)
    if isinstance(raw, list):
        return normalize_permissions(raw)
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        logger.warning("staff_permissions غير صالح لليوزر %s — بنقع على الديفولت", getattr(user, "id", "?"))
        return list(DEFAULT_ADMIN_PERMISSIONS)
    if not isinstance(parsed, list):
        return list(DEFAULT_ADMIN_PERMISSIONS)
    return normalize_permissions(parsed)


def has_permission(user, key: str) -> bool:
    return key in permissions_for(user)


def dump_permissions(values: Iterable[str]) -> str:
    """الشكل اللي بيتخزن بيه في العمود."""
    return json.dumps(normalize_permissions(values))


# ── فرض ───────────────────────────────────────────────────────
def require_permission(current_user, key: str) -> None:
    """403 لو اليوزر مش معاه الصلاحية دي (الـ owner بيعدّي دايماً)."""
    if not has_permission(current_user, key):
        raise HTTPException(status_code=403, detail="You don't have access to this section")


def catalog() -> dict:
    """الكتالوج زي ما الفرونت بيستهلكه."""
    return {
        "permissions": PERMISSIONS,
        "groups": GROUP_LABELS,
        "defaults": DEFAULT_ADMIN_PERMISSIONS,
    }
