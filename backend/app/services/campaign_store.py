# -*- coding: utf-8 -*-
"""
campaign_store.py
=================
تخزين حملات الإيميل بشكل دائم كملفات JSON في مجلد `campaigns/` — **مصدر واحد** مشترك
بين داشبورد غاوي (تاب الإيميلات) و runner الأوتوميشن (automation_runner.py في ريبو صلاح).

الملف ده مسؤول عن القراءة/الكتابة بس — **مايبعتش أي إيميل أبداً**. الإرسال بيفضل عبر
`email_campaigns.py` بقواعده (test افتراضي / GHAWY-OFFICIAL-SEND / خلفية).

فورمات الملف (متوافق مع automation_runner.py):
{
  "campaign_id": "inactive_24h_reengagement",
  "title": "...",
  "description": "...",
  "send_mode": "automated" | "manual",   # automated = بيتبعت عبر الـ runner (triggered)
  "active": true,                          # للأوتوماتيك بس — بيتقلب من زرار صريح مش تلقائي
  "trigger": { "type": "...", ... },       # إعدادات الـ trigger (للأوتوماتيك)
  "audience": { "status": "...", "plan": "...", ... },   # فلاتر الجمهور المحفوظة
  "content": { "subject_template": "...", "body_html": "...", ... },
  "created_at": "2026-07-23T...Z",
  "updated_at": "2026-07-23T...Z"
}

المسار: env `CAMPAIGNS_DIR` أو الافتراضي `<app root>/campaigns`. في الإنتاج المجلد volume
دائم (campaigns_data) عشان الحملات المتعملة من الداشبورد ما تضيعش عند إعادة بناء الصورة.
"""
import os
import re
import json
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any

# app root = /app (backend/) — الملف ده في app/services/, نطلع 3 مستويات
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAMPAIGNS_DIR = os.environ.get("CAMPAIGNS_DIR") or os.path.join(_APP_ROOT, "campaigns")

# معرّف الحملة لازم يبقى آمن كاسم ملف (يمنع path traversal)
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")

_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_dir() -> None:
    os.makedirs(CAMPAIGNS_DIR, exist_ok=True)


def is_valid_id(campaign_id: str) -> bool:
    return bool(campaign_id and _ID_RE.match(campaign_id))


def slugify(text: str) -> str:
    """يحوّل عنوان لـ id آمن (لاتيني/أرقام/شرطات). لو مفيش حروف صالحة يرجّع فاضي."""
    if not text:
        return ""
    s = str(text).strip().lower()
    s = re.sub(r"[^\w\-]+", "-", s, flags=re.ASCII)  # أي حاجة مش لاتيني/رقم → شرطة
    s = re.sub(r"-{2,}", "-", s).strip("-_")
    return s[:100]


def _path(campaign_id: str) -> str:
    if not is_valid_id(campaign_id):
        raise ValueError(f"معرّف حملة غير صالح: {campaign_id!r}")
    return os.path.join(CAMPAIGNS_DIR, f"{campaign_id}.json")


def exists(campaign_id: str) -> bool:
    try:
        return os.path.isfile(_path(campaign_id))
    except ValueError:
        return False


def get(campaign_id: str) -> Optional[Dict[str, Any]]:
    """يقرا حملة واحدة كاملة من ملفها. None لو مش موجودة."""
    try:
        p = _path(campaign_id)
    except ValueError:
        return None
    if not os.path.isfile(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    data["campaign_id"] = campaign_id  # اسم الملف هو المصدر الموثوق للـ id
    return data


def list_all() -> List[Dict[str, Any]]:
    """كل الحملات (raw dicts) مرتّبة بأحدث تعديل الأول."""
    _ensure_dir()
    out: List[Dict[str, Any]] = []
    try:
        names = os.listdir(CAMPAIGNS_DIR)
    except FileNotFoundError:
        return out
    for name in names:
        if not name.endswith(".json"):
            continue
        cid = name[:-5]
        data = get(cid)
        if data is not None:
            out.append(data)
    out.sort(key=lambda d: d.get("updated_at") or d.get("created_at") or "", reverse=True)
    return out


def _write(campaign_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """كتابة ذرّية (temp + replace) — مايسيبش ملف نص مكتوب لو حصل خطأ."""
    _ensure_dir()
    p = _path(campaign_id)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
    return data


def create(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    ينشئ حملة جديدة بملف JSON جديد. لو مفيش campaign_id بيتولّد من العنوان (أو timestamp).
    بيضمن التفرّد بإضافة لاحقة رقمية لو الاسم متكرر.
    """
    with _lock:
        _ensure_dir()
        cid = (data.get("campaign_id") or "").strip()
        if not cid:
            cid = slugify(data.get("title", "")) or f"campaign-{datetime.utcnow():%Y%m%d-%H%M%S}"
        if not is_valid_id(cid):
            cid = f"campaign-{datetime.utcnow():%Y%m%d-%H%M%S}"
        # تفرّد
        base, n = cid, 2
        while exists(cid):
            cid = f"{base}-{n}"
            n += 1
        now = _now_iso()
        data["campaign_id"] = cid
        data.setdefault("send_mode", "manual")
        data.setdefault("active", False)
        data.setdefault("created_at", now)
        data["updated_at"] = now
        return _write(cid, data)


def update(campaign_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """يحدّث حملة موجودة في نفس الملف. None لو مش موجودة."""
    with _lock:
        existing = get(campaign_id)
        if existing is None:
            return None
        data["campaign_id"] = campaign_id
        data["created_at"] = existing.get("created_at") or _now_iso()
        data["updated_at"] = _now_iso()
        return _write(campaign_id, data)


def set_active(campaign_id: str, active: bool) -> Optional[Dict[str, Any]]:
    """يقلب فلاج active بس (لأوتوميشن) — من غير ما يلمس أي إعداد تاني."""
    with _lock:
        existing = get(campaign_id)
        if existing is None:
            return None
        existing["active"] = bool(active)
        existing["updated_at"] = _now_iso()
        return _write(campaign_id, existing)
