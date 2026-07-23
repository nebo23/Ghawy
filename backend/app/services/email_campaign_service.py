# -*- coding: utf-8 -*-
"""
email_campaign_service.py
=========================
محرك حملات الإيميل الجماعية لغاوي (منقول من مشروع Salah: ghawy_email_lib.py) —
مدموج جوه backend غاوي مباشرة كـ library import-able **بدون أي side-effects عند الاستيراد**.

الفرق عن النسخة الأصلية في Salah:
  • الجمهور (recipients) بييجي من الداتابيز الحية عبر SQLAlchemy — مش من ملفات CSV.
    كل دوال الـ CSV (load_members / find_latest_members_csv / filter_members) اتشالت.
  • إعدادات الـ SMTP بتتعاد استخدامها من غاوي (app.services.email_service._get_smtp_config) —
    مفيش نظام SMTP موازي ولا env vars مكررة (نفس حساب Gmail: mosalah@ghawy.ai → support@ghawy.ai).
  • سجل الإرسال (sent-log) اللي بيمنع تكرار الإرسال لنفس الشخص في نفس الحملة بقى في جدول
    الداتابيز EmailCampaignSend بدل ملفات CSV — عشان يفضل ثابت عبر إعادة تشغيل الـ workers.
  • استبدال Python str.format بـ استبدال placeholders يدوي آمن (_apply_vars) عشان محتوى
    الـ HTML اللي فيه أقواس { } ما يكسرش الإرسال.

بيحافظ على: تصميم الـ HTML بالبراند (لوجو + صندوق أبيض + خلفية رصاصي فاتح + زرار أخضر
#D0FA06)، الصور inline بـ Content-ID، والتأخير العشوائي بين الإيميلات (rate-limit) عشان
حساب Gmail ما يتبلوكش.

⚠️ الملف ده منطق فقط. قواعد الأمان (test افتراضي / جملة GHAWY-OFFICIAL-SEND / وضع الخلفية)
   بتتفرض في الراوتر app.routers.email_campaigns.
"""

import os
import time
import random
import base64
import smtplib
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from typing import Optional

from app.services.email_service import (
    _get_smtp_config,
    _governorate_to_arabic,
    arabize_first_name,
    country_to_arabic,
)
from app.database import SessionLocal
from app.models import EmailCampaignSend


# ============================================================
# إعدادات عامة
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "email_campaign_assets")

BRAND_GREEN = "#D0FA06"

# تأخير عشوائي بين كل إيميل والتاني (بالثواني) — Gmail بيبلّظ الحساب لو الإرسال سريع جداً
MIN_DELAY_SECONDS = 4
MAX_DELAY_SECONDS = 9

# الاسم الظاهر جنب الإيميل الباعت (support@ghawy.ai بييجي من SMTP_FROM_EMAIL)
FROM_NAME = "غاوي"

# إيميلات التست الافتراضية لو الداشبورد مبعتش قائمة test_emails
DEFAULT_TEST_EMAILS = [
    "mohamedsalaahh7@gmail.com",
    "cmosalahh@gmail.com",
]

COMPOUND_FIRST_NAMES = [
    "عبد الله", "عبد الرحمن", "عبد الرحيم", "عبد العزيز", "عبد الحميد",
    "عبد الفتاح", "عبد الحكيم", "عبد المجيد", "عبد الوهاب", "عبد الستار",
    "عبد الغني", "عبد اللطيف", "عبد الحق", "عبد النور", "عبد السلام",
    "ضيف الله", "نصر الله", "سعد الدين", "نور الدين", "صلاح الدين",
]

# صور البراند (inline في الإيميل عبر Content-ID)
LOGO_FILE = os.path.join(ASSETS_DIR, "logo.png")
SOCIAL_ICON_FILES = {
    "instagram": os.path.join(ASSETS_DIR, "icon_instagram.png"),
    "facebook": os.path.join(ASSETS_DIR, "icon_facebook.png"),
    "tiktok": os.path.join(ASSETS_DIR, "icon_tiktok.png"),
}
WHATSAPP_ICON_FILE = os.path.join(ASSETS_DIR, "icon_whatsapp.png")

_ASSET_FILES = {
    "logo": LOGO_FILE,
    "instagram": SOCIAL_ICON_FILES["instagram"],
    "facebook": SOCIAL_ICON_FILES["facebook"],
    "tiktok": SOCIAL_ICON_FILES["tiktok"],
    "whatsapp": WHATSAPP_ICON_FILE,
}

# مصادر الصور الافتراضية للإرسال الحقيقي: Content-ID (الصور بتتربط كـ MIMEImage في build_message)
_CID_IMAGE_SRCS = {
    "logo": "cid:ghawy_logo",
    "instagram": "cid:social_instagram",
    "facebook": "cid:social_facebook",
    "tiktok": "cid:social_tiktok",
    "whatsapp": "cid:icon_whatsapp",
}


# ============================================================
# مساعدات الأسماء والمحافظات
# ============================================================

def get_first_name(full_name: str) -> str:
    if not full_name:
        return "صديقي"
    name = str(full_name).strip()
    for compound in COMPOUND_FIRST_NAMES:
        if name.startswith(compound):
            return compound
    return name.split()[0] if name.split() else "صديقي"


def clean_gov(gov) -> str:
    """
    بيشيل الحروف اللاتينية بس لو فيه عربي فعلاً جنبها (اسم مختلط)، مش لو كل المحافظة
    إنجليزي بحت (الداتا الحقيقية من الداتابيز فيها المحافظة إنجليزي غالباً).
    """
    if not gov:
        return ""
    g = str(gov).strip()
    has_latin = any("a" <= ch.lower() <= "z" for ch in g)
    has_arabic = any("؀" <= ch <= "ۿ" for ch in g)
    if has_latin and has_arabic:
        arabic_part = "".join(ch for ch in g if not ("a" <= ch.lower() <= "z")).strip()
        return arabic_part if len(arabic_part) >= 2 else g
    return g


def _apply_vars(text: Optional[str], template_vars: dict) -> str:
    """
    استبدال placeholders من نوع {key} بقيمها — بديل آمن لـ str.format عشان محتوى الـ HTML
    اللي فيه أقواس { } (زي inline styles) ما يرميش KeyError/ValueError ويكسر الإرسال.
    أي {placeholder} مش معروف بيتساب زي ما هو.
    """
    if not text:
        return text or ""
    out = str(text)
    for key, val in template_vars.items():
        out = out.replace("{" + key + "}", str(val))
    return out


# ============================================================
# محتوى الإيميل (Template ثابت — المتغير بس الفقرات/الزرار/الموضوع)
# ============================================================

@dataclass
class EmailButton:
    text: str
    link: str
    color: str = BRAND_GREEN


@dataclass
class EmailContent:
    subject_template: str
    body_paragraphs_html: list = field(default_factory=list)   # الشكل القديم — لسه بيشتغل لو body_html فاضي
    body_html: Optional[str] = None                            # المحتوى الأساسي (HTML كامل)
    buttons: list = field(default_factory=list)               # list[EmailButton]
    button_text: Optional[str] = None                         # legacy — بيتحوّل لأول زرار
    button_link: Optional[str] = None
    button_color: str = BRAND_GREEN
    closing_line: Optional[str] = None
    signoff_html: str = "محمد - غاوي"
    intro_line: str = ""
    name_ar_fallback: str = ""
    governorate_ar_fallback: str = ""
    include_footer: bool = True

    def __post_init__(self):
        # توافق قديم: button_text/button_link من غير buttons → زرار واحد
        if not self.buttons and self.button_text and self.button_link:
            self.buttons = [EmailButton(text=self.button_text, link=self.button_link, color=self.button_color)]
        # buttons جايين كـ dicts (من JSON) → EmailButton حقيقي
        self.buttons = [
            b if isinstance(b, EmailButton) else EmailButton(**b)
            for b in self.buttons
        ]


def _greeting_line(gov: str) -> str:
    return f"حبايبنا والله اهل {gov} 🤍" if gov else "حبايبنا والله 🤍"


GHAWY_SOCIALS = {
    "instagram": "https://www.instagram.com/ghawy.ai/",
    "facebook": "https://www.facebook.com/profile.php?id=61591378479904",
    "tiktok": "https://www.tiktok.com/@ghawy.ai",
}

GHAWY_FOOTER_LINKS = [
    {"label": "الشروط والأحكام", "url": "https://ghawy.ai/terms.html"},
    {"label": "سياسة الخصوصية", "url": "https://ghawy.ai/terms.html#privacy"},
    {"label": "ابدأ الآن", "url": "https://ghawy.ai"},
]
GHAWY_SUPPORT_PHONE = "01033903334"
# wa.me محتاج الرقم بصيغة دولية من غير الصفر الأول (مصر = 20)
GHAWY_WHATSAPP_LINK = f"https://wa.me/20{GHAWY_SUPPORT_PHONE.lstrip('0')}"


def build_template_vars(row: dict, content: Optional["EmailContent"] = None) -> dict:
    """
    بيبني كل المتغيرات المتاحة للاستخدام كـ {placeholder} في subject/body/closing_line
    من صف عضو واحد. الحقول العربي (Name_Ar/Country_Ar/Governorate_Ar) بتيجي جاهزة من
    الراوتر لو موجودة، وإلا بيرجع للـ fallback المخصص في الحملة ثم للإنجليزي.
    """
    name = row.get("Name", "") or ""
    first_name = get_first_name(name)
    gov = clean_gov(row.get("Governorate", ""))
    country = row.get("Country", "") or ""

    # ── الاسم بالعربي: معرّب من الماب، وإلا fallback الحملة، وإلا "صديقنا" (مش الاسم اللاتيني) ──
    first_name_ar = row.get("Name_Ar", "") or arabize_first_name(first_name)
    if not first_name_ar:
        first_name_ar = (content.name_ar_fallback if content and content.name_ar_fallback else None) or "صديقنا"

    # ── المحافظة بالعربي: المرسَل جاهز، وإلا الترجمة من الماب، وإلا fallback الحملة، وإلا فاضي ──
    governorate_ar = row.get("Governorate_Ar", "") or _governorate_to_arabic(gov)
    if not governorate_ar:
        governorate_ar = (content.governorate_ar_fallback if content and content.governorate_ar_fallback else None) or ""

    # ── البلد بالعربي ──
    country_ar = row.get("Country_Ar", "") or country_to_arabic(country)

    return {
        "first_name": first_name,
        "first_name_ar": first_name_ar,
        "full_name": name,
        # التحية دايماً بالعربي — بتستخدم المحافظة المعرّبة (مش الاسم اللاتيني)
        "greeting": _greeting_line(governorate_ar),
        "email": row.get("Email", "") or "",
        "phone": row.get("Phone", "") or "",
        "country": country,
        "country_ar": country_ar,
        "governorate": gov,
        "governorate_ar": governorate_ar,
        "age": row.get("Age", "") or "",
        "start_date": row.get("StartDate", "") or "",
        "end_date": row.get("EndDate", "") or "",
        "plan": row.get("Plan", "") or "",
    }


def render_email_html(template_vars: dict, content: EmailContent, image_srcs: Optional[dict] = None) -> str:
    """
    التنسيق الكامل (جدول layout + خلفية + فونت Cairo + زرار CTA + لوجو + سوشيال). الشكل
    العام ثابت، بس لون الزرار قابل للتخصيص عبر content.button_color.

    image_srcs: خريطة مصادر الصور (logo/instagram/facebook/tiktok/whatsapp). الافتراضي
    Content-ID للإرسال الحقيقي؛ في المعاينة بيتبعت data: URIs عشان الصور تبان في المتصفح.
    """
    srcs = image_srcs or _CID_IMAGE_SRCS
    parts = []

    if content.intro_line and content.intro_line.strip():
        parts.append(f'<p style="margin:0 0 18px;">{_apply_vars(content.intro_line, template_vars)}</p>')

    if content.body_html and content.body_html.strip():
        parts.append(_apply_vars(content.body_html, template_vars))
    else:
        for para in content.body_paragraphs_html:
            parts.append(f'<p style="margin:0 0 18px;">{_apply_vars(para, template_vars)}</p>')

    buttons_html = ""
    for btn in content.buttons:
        buttons_html += f"""
              <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 8px 12px 0; display:inline-block;">
                <tr>
                  <td style="border-radius:8px; background-color:{btn.color};">
                    <a href="{btn.link}" target="_blank"
                       style="display:inline-block; padding:14px 34px; color:#1a1a1a; text-decoration:none; font-weight:700; font-size:16px; font-family:'Cairo', Arial, sans-serif;">
                       {_apply_vars(btn.text, template_vars)}
                    </a>
                  </td>
                </tr>
              </table>"""
    if buttons_html:
        buttons_html = f'<div style="margin:0 0 24px;">{buttons_html}</div>'

    if content.closing_line:
        parts.append(f'<p style="margin:0 0 6px;">{_apply_vars(content.closing_line, template_vars)}</p>')

    signoff_html = f'<p style="margin:0 0 28px; color:#666;">{content.signoff_html}</p>'

    footer_block = ""
    if content.include_footer:
        logo_row = (
            f'<div><img src="{srcs.get("logo", "")}" alt="Ghawy" width="64" height="64" '
            f'style="display:inline-block; border:0; opacity:0.9;"></div>'
        )
        social_row = "".join(
            f'<a href="{url}" target="_blank" style="display:inline-block; margin:0 8px; text-decoration:none; border:0;">'
            f'<img src="{srcs.get(name, "")}" alt="{name}" width="28" height="28" '
            f'style="display:inline-block; width:28px; height:28px; border:0; vertical-align:middle;"></a>'
            for name, url in GHAWY_SOCIALS.items()
        )
        links_row = "".join(
            f'<a href="{link["url"]}" target="_blank" style="color:#999; text-decoration:none; margin:0 10px; font-size:12px;">{link["label"]}</a>'
            for link in GHAWY_FOOTER_LINKS
        )
        phone_row = (
            f'<a href="{GHAWY_WHATSAPP_LINK}" target="_blank" style="text-decoration:none;">'
            f'<img src="{srcs.get("whatsapp", "")}" alt="whatsapp" width="22" height="22" '
            f'style="display:inline-block; width:22px; height:22px; border:0; vertical-align:middle; margin-inline-end:6px;">'
            f'<span style="color:#999; font-size:13px; vertical-align:middle;">{GHAWY_SUPPORT_PHONE}</span></a>'
        )
        footer_block = f"""<div style="text-align:center; border-top:1px solid #eee; padding-top:24px;">
                {logo_row}
                <div style="margin-top:14px;">{social_row}</div>
                <div style="margin-top:14px;">{links_row}</div>
                <div style="margin-top:14px;">{phone_row}</div>
              </div>"""

    body_paragraphs = "\n              ".join(parts)

    return f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
</head>
<body style="margin:0; padding:0; background-color:#f4f4f4;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4; padding:24px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0"
               style="background-color:#ffffff; border-radius:12px; overflow:hidden; max-width:600px; width:100%; font-family:'Cairo', Arial, sans-serif;">
          <tr>
            <td style="padding:36px 40px; direction:rtl; text-align:right; color:#1a1a1a; font-size:16px; line-height:1.9;">
              {body_paragraphs}
              {buttons_html}
              {signoff_html}
              {footer_block}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def render_email_text(template_vars: dict, content: EmailContent) -> str:
    """نسخة نصية بسيطة (fallback) — بتتولد من نفس المحتوى بعد إزالة أي HTML tags."""
    import re
    lines = []
    if content.intro_line and content.intro_line.strip():
        lines.append(re.sub(r"<[^>]+>", "", _apply_vars(content.intro_line, template_vars)))
    if content.body_html and content.body_html.strip():
        lines.append(re.sub(r"<[^>]+>", " ", _apply_vars(content.body_html, template_vars)))
    else:
        for para in content.body_paragraphs_html:
            lines.append(re.sub(r"<[^>]+>", " ", _apply_vars(para, template_vars)))
    for btn in content.buttons:
        lines.append(f"{_apply_vars(btn.text, template_vars)}: {btn.link}")
    if content.closing_line:
        lines.append(re.sub(r"<[^>]+>", "", _apply_vars(content.closing_line, template_vars)))
    lines.append(re.sub(r"<[^>]+>", "", content.signoff_html))
    return "\n\n".join(l for l in lines if l and l.strip())


def build_subject(content: EmailContent, template_vars: dict) -> str:
    return _apply_vars(content.subject_template, template_vars)


def build_message(to_email: str, row: dict, content: EmailContent, smtp_from: str) -> MIMEMultipart:
    """multipart/related (alternative جواه + الصور inline بـ Content-ID)."""
    template_vars = build_template_vars(row, content)

    msg = MIMEMultipart("related")
    msg["From"] = f"{FROM_NAME} <{smtp_from}>" if FROM_NAME else smtp_from
    msg["To"] = to_email
    msg["Subject"] = build_subject(content, template_vars)

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(render_email_text(template_vars, content), "plain", "utf-8"))
    alt.attach(MIMEText(render_email_html(template_vars, content), "html", "utf-8"))
    msg.attach(alt)

    if content.include_footer:
        if os.path.exists(LOGO_FILE):
            with open(LOGO_FILE, "rb") as f:
                logo = MIMEImage(f.read())
            logo.add_header("Content-ID", "<ghawy_logo>")
            logo.add_header("Content-Disposition", "inline", filename="logo.png")
            msg.attach(logo)

        for name, icon_path in SOCIAL_ICON_FILES.items():
            if os.path.exists(icon_path):
                with open(icon_path, "rb") as f:
                    icon_img = MIMEImage(f.read())
                icon_img.add_header("Content-ID", f"<social_{name}>")
                icon_img.add_header("Content-Disposition", "inline", filename=os.path.basename(icon_path))
                msg.attach(icon_img)

        if os.path.exists(WHATSAPP_ICON_FILE):
            with open(WHATSAPP_ICON_FILE, "rb") as f:
                wa_img = MIMEImage(f.read())
            wa_img.add_header("Content-ID", "<icon_whatsapp>")
            wa_img.add_header("Content-Disposition", "inline", filename="icon_whatsapp.png")
            msg.attach(wa_img)

    return msg


# ============================================================
# المعاينة (Preview) — صور data: URI عشان تبان في المتصفح
# ============================================================

def _preview_image_srcs() -> dict:
    """بيحوّل صور البراند لـ data: URIs عشان المعاينة في الداشبورد تطابق الإيميل الفعلي."""
    out = {}
    for key, path in _ASSET_FILES.items():
        try:
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            out[key] = f"data:image/png;base64,{b64}"
        except Exception:
            out[key] = ""
    return out


def render_preview(content: EmailContent, sample_row: Optional[dict] = None) -> dict:
    """بيرجّع {subject, html} لإيميل واحد بعيّنة عضو — الصور inline كـ data: URIs."""
    sample_row = sample_row or {"Name": "أحمد محمد", "Governorate": "القاهرة", "Country": "Egypt", "Email": "member@example.com"}
    template_vars = build_template_vars(sample_row, content)
    html = render_email_html(template_vars, content, image_srcs=_preview_image_srcs())
    return {"subject": build_subject(content, template_vars), "html": html}


# ============================================================
# سجل الإرسال (جدول EmailCampaignSend — يمنع تكرار الإرسال لنفس الشخص في نفس الحملة)
# ============================================================

def load_sent_log(campaign_id: str, session_factory=None) -> set:
    """كل الإيميلات اللي اتسجّلت قبل كده في الحملة دي (نجحت أو فشلت) — يتخطّوا عند الاستكمال."""
    SF = session_factory or SessionLocal
    db = SF()
    try:
        rows = (
            db.query(EmailCampaignSend.email)
            .filter(EmailCampaignSend.campaign_id == campaign_id)
            .all()
        )
        return {r[0].lower() for r in rows if r[0]}
    finally:
        db.close()


def append_to_log(campaign_id: str, email: str, status: str, session_factory=None) -> None:
    """جلسة قصيرة العمر لكل كتابة — بتتقفل فوراً عشان ما نمسكش connection/transaction وقت الـ sleep."""
    SF = session_factory or SessionLocal
    db = SF()
    try:
        db.add(EmailCampaignSend(campaign_id=campaign_id, email=email, status=status[:500]))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# ============================================================
# الإرسال الفعلي
# ============================================================

@dataclass
class SendResult:
    success_count: int = 0
    fail_count: int = 0
    failures: list = field(default_factory=list)
    skipped_already_sent: int = 0


def send_campaign(
    targets: list,
    content: EmailContent,
    campaign_name: str,
    test_mode: bool = True,
    test_emails: Optional[list] = None,
    session_factory=None,
) -> SendResult:
    """
    test_mode=True (الافتراضي): بيبعت بس على test_emails، وميكتبش في اللوج، وبيستخدم بيانات
    أول صف حقيقي في targets عشان المعاينة تبقى واقعية.

    test_mode=False: إرسال فعلي لكل الـ targets، مع لوج DB وتخطي المتكرر سابقاً. بيفتح اتصال
    SMTP واحد ويسيب تأخير عشوائي بين كل إيميل (rate-limit).
    """
    smtp_host, smtp_port, smtp_user, smtp_password, smtp_from = _get_smtp_config()

    result = SendResult()
    test_emails = [e for e in (test_emails or DEFAULT_TEST_EMAILS) if e and e.strip()]

    if test_mode:
        if not test_emails:
            raise RuntimeError("مفيش أي إيميل تست في وضع الاختبار.")
        # لو مفيش أعضاء متحددين للتست، بنستخدم عيّنة واقعية كاملة عشان كل المتغيرات
        # ({governorate}/{governorate_ar}/{country}) تبان معمورة في إيميل التست مش فاضية.
        sample = targets[0] if targets else {
            "Name": "محمد أحمد", "Governorate": "Cairo", "Country": "Egypt",
        }
        send_list = [(email, {**sample, "Email": email}) for email in test_emails]
    else:
        sent_already = load_sent_log(campaign_name, session_factory)
        send_list = []
        for row in targets:
            email = row.get("Email", "")
            if not email:
                continue
            if email.lower() in sent_already:
                result.skipped_already_sent += 1
                continue
            send_list.append((email, row))

    if not send_list:
        return result

    server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
    try:
        server.starttls()
        server.login(smtp_user, smtp_password)

        for i, (to_email, row) in enumerate(send_list, start=1):
            try:
                msg = build_message(to_email, row, content, smtp_from)
                server.sendmail(smtp_from, to_email, msg.as_string())
                result.success_count += 1
                if not test_mode:
                    append_to_log(campaign_name, to_email, "sent", session_factory)
            except Exception as e:
                result.fail_count += 1
                result.failures.append((to_email, str(e)))
                if not test_mode:
                    append_to_log(campaign_name, to_email, f"failed: {e}", session_factory)

            if i < len(send_list):
                time.sleep(random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS))
    finally:
        try:
            server.quit()
        except Exception:
            pass

    return result


# ============================================================
# مساعدات بناء المحتوى/المستلمين من JSON (نفس بروتوكول send_dynamic.py)
# ============================================================

def normalize_recipients(recipients: list) -> list:
    """
    بيحوّل recipients (name/email/phone/country/governorate/age/name_ar/country_ar/
    governorate_ar/start_date/end_date/plan) لنفس شكل الصفوف اللي send_campaign متوقعها.
    """
    out = []
    for r in recipients or []:
        out.append({
            "Name": r.get("name", "") or "",
            "Email": r.get("email", "") or "",
            "Phone": r.get("phone", "") or "",
            "Country": r.get("country", "") or "",
            "Governorate": r.get("governorate", "") or "",
            "Age": r.get("age", "") or "",
            "Name_Ar": r.get("name_ar", "") or "",
            "Country_Ar": r.get("country_ar", "") or "",
            "Governorate_Ar": r.get("governorate_ar", "") or "",
            "StartDate": r.get("start_date", "") or "",
            "EndDate": r.get("end_date", "") or "",
            "Plan": r.get("plan", "") or "",
        })
    return out


def build_content(content_cfg: dict) -> EmailContent:
    """بناء EmailContent من dict (JSON) — بيتجاهل أي مفاتيح مش معروفة."""
    if not content_cfg or not content_cfg.get("subject_template"):
        raise ValueError("subject_template مطلوب.")

    kwargs = dict(subject_template=content_cfg["subject_template"])

    allowed = (
        "body_paragraphs_html", "body_html", "buttons", "button_text", "button_link",
        "button_color", "closing_line", "signoff_html", "intro_line",
        "name_ar_fallback", "governorate_ar_fallback", "include_footer",
    )
    for key in allowed:
        if key in content_cfg and content_cfg[key] is not None:
            kwargs[key] = content_cfg[key]

    return EmailContent(**kwargs)
