import os
import re
import smtplib
import unicodedata
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def _get_smtp_config():
    """Return SMTP configuration from environment variables."""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM_EMAIL", smtp_user or "no-reply@example.com")

    if not smtp_host or not smtp_user or not smtp_password:
        raise RuntimeError("SMTP settings are missing. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in .env")

    return smtp_host, smtp_port, smtp_user, smtp_password, smtp_from


def _send_email(to_email: str, subject: str, body_text: str, body_html: str = None) -> None:
    """Generic email sender. If body_html is provided, sends multipart."""
    smtp_host, smtp_port, smtp_user, smtp_password, smtp_from = _get_smtp_config()

    if body_html:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = smtp_from
        message["To"] = to_email
        message.attach(MIMEText(body_text, "plain"))
        message.attach(MIMEText(body_html, "html"))
    else:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = smtp_from
        message["To"] = to_email
        message.set_content(body_text)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(message)


def send_verification_email(to_email: str, code: str) -> None:
    _send_email(
        to_email=to_email,
        subject="Your verification code",
        body_text=(
            f"Your verification code is: {code}\n\n"
            "This code expires in 15 minutes.\n"
            "If you did not request this, ignore this email."
        ),
    )


def send_legacy_otp_email(to_email: str, code: str) -> None:
    """Send OTP for legacy members promo verification."""
    body_text = (
        f"مرحباً بك في Ghawy،\n\n"
        f"كود التحقق الخاص بك هو: {code}\n\n"
        f"هذا الكود صالح لمدة 10 دقائق.\n"
        f"إذا لم تطلب هذا الكود، يرجى تجاهل هذه الرسالة."
    )
    body_html = f"""
    <div dir="rtl" style="font-family: 'Inter', Arial, sans-serif; max-width: 520px; margin: 0 auto; background: #0a0a0a; padding: 32px; border-radius: 12px; border: 1px solid #2a2a2a; text-align: center;">
        <h2 style="color: #fff; margin: 0 0 20px;">كود التحقق الخاص بك</h2>
        <p style="color: #ccc; font-size: 16px; margin: 0 0 20px;">استخدم الكود التالي للحصول على الشهر المجاني:</p>
        <div style="background: rgba(63, 143, 249, 0.1); border: 1px solid rgba(63, 143, 249, 0.3); border-radius: 8px; padding: 24px; margin: 20px 0;">
            <p style="color: #3f8ff9; font-size: 36px; letter-spacing: 8px; font-weight: 700; margin: 0;">{code}</p>
        </div>
        <p style="color: #888; font-size: 13px; margin-top: 24px;">هذا الكود صالح لمدة 10 دقائق.</p>
    </div>
    """
    _send_email(
        to_email=to_email,
        subject="كود التحقق — Ghawy Legacy",
        body_text=body_text,
        body_html=body_html,
    )


# ═══════════════════════════════════════════════════════
#  MANUAL PAYMENT EMAILS
# ═══════════════════════════════════════════════════════

def send_admin_payment_notification(
    full_name: str,
    email: str,
    phone: str,
    amount: float,
    created_at: str,
) -> None:
    """Notify admin team about a new manual payment submission."""
    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai")
    admin_email = os.getenv("ADMIN_EMAIL", "mosalah@ghawy.ai")

    body_text = (
        f"🔔 New payment request — {full_name}\n\n"
        f"A new manual payment request has been submitted.\n\n"
        f"Name: {full_name}\n"
        f"Email: {email}\n"
        f"Phone: {phone or 'N/A'}\n"
        f"Amount: {amount or 'N/A'} EGP\n"
        f"Submitted: {created_at}\n\n"
        f"Review it here: {frontend_url}/teamdashboard.html#pending-requests"
    )

    body_html = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 520px; margin: 0 auto; background: #0a0a0a; padding: 32px; border-radius: 12px; border: 1px solid #2a2a2a;">
        <h2 style="color: #fff; margin: 0 0 20px;">🔔 New Payment Request</h2>
        <p style="color: #aaa; margin: 0 0 20px;">A new manual payment request has been submitted.</p>
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
            <tr><td style="color: #888; padding: 8px 0; border-bottom: 1px solid #1e1e1e;">Name</td><td style="color: #fff; padding: 8px 0; border-bottom: 1px solid #1e1e1e; text-align: right;">{full_name}</td></tr>
            <tr><td style="color: #888; padding: 8px 0; border-bottom: 1px solid #1e1e1e;">Email</td><td style="color: #fff; padding: 8px 0; border-bottom: 1px solid #1e1e1e; text-align: right;">{email}</td></tr>
            <tr><td style="color: #888; padding: 8px 0; border-bottom: 1px solid #1e1e1e;">Phone</td><td style="color: #fff; padding: 8px 0; border-bottom: 1px solid #1e1e1e; text-align: right;">{phone or 'N/A'}</td></tr>
            <tr><td style="color: #888; padding: 8px 0; border-bottom: 1px solid #1e1e1e;">Amount</td><td style="color: #fff; padding: 8px 0; border-bottom: 1px solid #1e1e1e; text-align: right;">{amount or 'N/A'} EGP</td></tr>
            <tr><td style="color: #888; padding: 8px 0;">Submitted</td><td style="color: #fff; padding: 8px 0; text-align: right;">{created_at}</td></tr>
        </table>
        <a href="{frontend_url}/teamdashboard.html#pending-requests" style="display: inline-block; background: #3f8ff9; color: #000; font-weight: 700; padding: 12px 24px; border-radius: 8px; text-decoration: none;">Review Now →</a>
    </div>
    """

    _send_email(
        to_email=admin_email,
        subject=f"🔔 New payment request — {full_name}",
        body_text=body_text,
        body_html=body_html,
    )


def send_payment_approval_email(
    to_email: str,
    full_name: str,
    registration_url: str,
) -> None:
    """تأكيد الدفع + لينك تفعيل الحساب بعد موافقة الأدمن — بنفس الـ Design System البراندي."""
    name = _first_name(full_name)
    heading = f"مبروك يا {name}! دفعتك اتأكّدت ✅"
    body = [
        "تم تأكيد عملية الدفع بتاعتك بنجاح، وانت دلوقتي على بُعد خطوة واحدة بس من إنك تدخل غاوي.",
        "اضغط على الزرار عشان تحدّد الباسورد بتاعك وتفعّل حسابك وتدخل فوراً:",
    ]
    cta_text = "فعّل حسابك وادخل غاوي →"
    pre_footer = "اللينك ده صالح لمدة 48 ساعة."

    _send_email(
        to_email=to_email,
        subject=f"مبروك يا {name}! فعّل حسابك في غاوي 🎉",
        body_text=_brand_email_text(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=registration_url, pre_footer=pre_footer),
        body_html=_brand_email_html(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=registration_url, pre_footer=pre_footer),
    )


def send_payment_rejection_email(
    to_email: str,
    full_name: str,
    rejection_reason: str,
) -> None:
    """إشعار رفض طلب الدفع — بنفس الـ Design System البراندي الفاتح."""
    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai").rstrip("/")
    name = _first_name(full_name)
    heading = f"{name}، تحديث بخصوص طلب الدفع بتاعك"
    body = [
        "للأسف مقدرناش نأكّد عملية الدفع بتاعتك.",
        f"السبب: <strong>{rejection_reason}</strong>",
        "لو شايف إن ده حصل بالغلط، ردّ على الإيميل ده أو ابعت الإيصال تاني بصورة أوضح "
        "وإحنا هنراجعه فوراً.",
    ]
    cta_text = "حاول تاني"
    cta_url = f"{frontend_url}/pay.html"

    _send_email(
        to_email=to_email,
        subject="تحديث بخصوص طلب الدفع بتاعك في غاوي",
        body_text=_brand_email_text(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url),
        body_html=_brand_email_html(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url),
    )


# ═══════════════════════════════════════════════════════
#  LIVE SESSION NOTIFICATION
# ═══════════════════════════════════════════════════════

def send_live_session_notification(
    to_email: str,
    full_name: str,
    session_title: str,
    scheduled_at: str,
    description: str = "",
) -> None:
    """إشعار سيشن لايف جديدة — بنفس الـ Design System البراندي الفاتح."""
    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai").rstrip("/")
    name = _first_name(full_name)

    heading = f"{name}، في سيشن لايف جديدة مستنياك 📺"
    body = [
        f"حابين نقولك إن في جلسة بث مباشر جديدة في غاوي: <strong>{session_title}</strong>.",
        f"ميعادها: <strong>{scheduled_at}</strong>.",
    ]
    if description and description.strip():
        body.append(description.strip())
    body.append("سجّل حضورك من الزرار هنا عشان متفوّتكش 👇")
    cta_text = "احجز مكانك في اللايف 🚀"
    cta_url = f"{frontend_url}/build-with-me.html"

    _send_email(
        to_email=to_email,
        subject=f"📺 سيشن لايف جديدة: {session_title}",
        body_text=_brand_email_text(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url),
        body_html=_brand_email_html(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url),
    )


# ═══════════════════════════════════════════════════════
#  SUBSCRIPTION RENEWAL REMINDER
# ═══════════════════════════════════════════════════════

_RENEWAL_PLAN_LABELS = {
    "monthly_egp":   {"label": "الشهري",   "renew_label": "جدّد اشتراكك الشهري"},
    "quarterly_egp": {"label": "تلت شهور", "renew_label": "جدّد اشتراكك"},
    "yearly_egp":    {"label": "السنوي",   "renew_label": "جدّد اشتراكك السنوي"},
    "monthly_usd":   {"label": "الشهري",   "renew_label": "جدّد اشتراكك الشهري"},
    "quarterly_usd": {"label": "تلت شهور", "renew_label": "جدّد اشتراكك"},
    "yearly_usd":    {"label": "السنوي",   "renew_label": "جدّد اشتراكك السنوي"},
}


def _plan_price_str(plan_key: str) -> str:
    """السعر الحقيقي للباقة من مصدر الحقيقة (payment.PLAN_PRICES) — مش قيمة مكتوبة بالإيد."""
    try:
        from app.routers.payment import PLAN_PRICES  # lazy: تفادي circular import
        p = PLAN_PRICES.get(plan_key)
        if p:
            return f"{p['amount']:,} جنيه" if p["currency"] == "EGP" else f"${p['amount']}"
    except Exception:
        pass
    return ""


def send_renewal_reminder_email(
    to_email: str,
    full_name: str,
    days_left: int,
    plan_key: str,
    subscription_end,
) -> None:
    """تذكير قرب انتهاء الاشتراك — بنفس الـ Design System البراندي الفاتح + السعر الحقيقي."""
    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai").rstrip("/")
    plan = _RENEWAL_PLAN_LABELS.get(plan_key, _RENEWAL_PLAN_LABELS["monthly_egp"])
    price_str = _plan_price_str(plan_key)
    end_date_str = subscription_end.strftime("%d/%m/%Y") if subscription_end else "—"
    renew_url = f"{frontend_url}/payment.html?plan={plan_key}"
    name = _first_name(full_name)
    day_word = "يوم" if days_left == 1 else "أيام"

    heading = f"{name}، باقي {days_left} {day_word} على انتهاء اشتراكك في غاوي"
    body = [
        f"حابين نفكّرك إن اشتراكك <strong>{plan['label']}</strong> في غاوي قرب يخلص يوم "
        f"<strong>{end_date_str}</strong> — متبقّي <strong>{days_left} {day_word}</strong> بس.",
        (f"سعر التجديد: <strong>{price_str}</strong>. " if price_str else "")
        + "ولو الاشتراك خلص هتفقد الوصول لكل الكورسات والتقدّم اللي وصلتله، والشهر الجديد "
        "جوه غاوي محضّرين لك فيه كورسات وتحديثات قوية جداً — عشان كده متحمسين نكمّل معاك.",
        "تقدر تجدّد أو تراجع بيانات الدفع فوراً من الزرار هنا:",
    ]
    cta_text = f"🔄 {plan['renew_label']}"

    _send_email(
        to_email=to_email,
        subject=heading,
        body_text=_brand_email_text(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=renew_url),
        body_html=_brand_email_html(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=renew_url),
    )



# ═══════════════════════════════════════════════════════
#  WINBACK EMAIL — للي سجلوا وموصلوش لآخر خطوة
# ═══════════════════════════════════════════════════════

# governorate بيتخزن بالإنجليزي من الـ geolocation بصيغ كتير مختلفة —
# بنطبّع الاسم وبنترجمه للعربي؛ لو مش معروف بنسيب الجملة من غير اسم المحافظة.
_GOV_AR = {
    # القاهرة الكبرى
    "cairo": "القاهرة", "new cairo": "القاهرة", "al qahirah al jadidah": "القاهرة",
    "maadi": "القاهرة", "nasr city": "القاهرة", "heliopolis": "القاهرة",
    "badr": "القاهرة", "al ubur": "القاهرة",
    "10th of ramadan city": "العاشر من رمضان",
    "giza": "الجيزة", "dokki": "الجيزة", "6th of october city": "الجيزة",
    "shubra al khaymah": "القليوبية", "banha": "القليوبية", "qalyubia": "القليوبية",
    # إسكندرية والدلتا
    "alexandria": "إسكندرية", "moharam bek": "إسكندرية",
    "beheira": "البحيرة", "damanhur": "البحيرة", "abu hummus": "البحيرة", "shubrakhit": "البحيرة",
    "kafr ash shaykh": "كفر الشيخ", "kafr el sheikh": "كفر الشيخ", "al hamul": "كفر الشيخ",
    "gharbia": "الغربية", "tanta": "طنطا", "al mahallah al kubra": "المحلة", "zefta": "الغربية",
    "monufia": "المنوفية", "menouf": "المنوفية", "shibin al kawm": "المنوفية", "quweisna": "المنوفية",
    "dakahlia": "الدقهلية", "al mansurah": "المنصورة", "mit ghamr": "الدقهلية",
    "talkha": "الدقهلية", "bilqas": "الدقهلية",
    "sharqia": "الشرقية", "zagazig": "الزقازيق",
    "damietta": "دمياط", "kafr al battikh": "دمياط",
    # القناة وسيناء
    "port said": "بورسعيد", "ismailia": "الإسماعيلية", "suez": "السويس",
    "north sinai": "سيناء", "south sinai": "سيناء",
    # الصعيد والبحر الأحمر
    "faiyum": "الفيوم", "al fayyum": "الفيوم", "fayoum": "الفيوم",
    "beni suweif": "بني سويف", "bani suwayf": "بني سويف", "beni suef": "بني سويف",
    "minya": "المنيا", "mallawi": "المنيا",
    "asyut": "أسيوط", "sohag": "سوهاج", "qena": "قنا",
    "luxor": "الأقصر", "aswan": "أسوان",
    "hurghada": "الغردقة", "red sea": "البحر الأحمر", "matrouh": "مطروح",
    # مدن عربية
    "riyadh": "الرياض", "jeddah": "جدة", "dammam": "الدمام", "mecca": "مكة", "medina": "المدينة",
    "dubai": "دبي", "abu dhabi": "أبوظبي", "sharjah": "الشارقة",
    "fujairah": "الفجيرة", "ras al khaimah": "رأس الخيمة", "ajman": "عجمان",
    "kuwait city": "الكويت", "doha": "الدوحة", "muscat": "مسقط", "manama": "المنامة",
    "amman": "عمّان", "beirut": "بيروت", "baghdad": "بغداد", "erbil": "أربيل",
    "damascus": "دمشق", "aleppo": "حلب",
    "gaza": "غزة", "gaza strip": "غزة", "nablus": "نابلس", "ramallah": "رام الله",
    "tripoli": "طرابلس", "sirte": "سرت", "benghazi": "بنغازي",
    "tunis": "تونس", "algiers": "الجزائر", "annaba": "عنابة", "setif": "سطيف",
    "mostaganem": "مستغانم", "casablanca": "الدار البيضاء", "rabat": "الرباط",
    "khartoum": "الخرطوم", "nouakchott": "نواكشوط", "sanaa": "صنعاء", "taizz": "تعز",
}


def _governorate_to_arabic(raw: str) -> str:
    """يحاول يطلع اسم عربي للمحافظة/المدينة، أو يرجع نص فاضي لو مش معروفة."""
    if not raw or not raw.strip():
        return ""
    # فك التشكيل اللاتيني (Aswān -> Aswan) وتطبيع الاسم
    s = unicodedata.normalize("NFKD", raw)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("‘", "").replace("'", "").replace("ʻ", "").replace("-", " ").lower().strip()
    for junk in (" governorate", " province", " region", " district", "emirate of "):
        s = s.replace(junk, "")
    s = " ".join(s.split())
    return _GOV_AR.get(s, "")


def send_winback_email(to_email: str, full_name: str, governorate: str = None) -> None:
    """إيميل شخصي من محمد للي سجل وموصلش لآخر خطوة — بيتبعت مرة واحدة بس."""
    gov_ar = _governorate_to_arabic(governorate or "")
    greeting = f"حبايبنا والله اهل {gov_ar}" if gov_ar else "حبايبنا والله ❤️"
    # أول اسم بس عشان التحية تطلع طبيعية (الاسم الكامل بيبقى تلات/أربع كلمات)
    first_name = (full_name or "").strip().split()[0] if (full_name or "").strip() else ""
    hello = f"ازيك يا {first_name}،" if first_name else "ازيك،"

    subject = "خدت بالي إنك وقفت في آخر خطوة… 🤍"

    body_text = (
        f"{hello}\n"
        "أنا محمد, من غاوي.\n"
        f"{greeting}\n\n"
        "بس انا خدت بالي إنك دخلت علي الموقع وسجلت بالفعل, بس فضلت في آخر خطوة…\n\n"
        "انا بس عايز أفهم منك إيه اللي حصل وعطلك؟\n\n"
        "هل كان في مشكلة في الدفع؟\n"
        "ولا في حاجة في العرض مش واضحة؟\n"
        "ولا في سبب تاني خالص؟\n\n"
        "مقدر جدا اهتمامك وثقتك, فأتمني تقولي ايه السبب, وأنا هتواصل معاك شخصياً.\n\n"
        "لو حبيت ترجع وتبدأ، اللينك هنا:\n"
        "https://ghawy.ai/\n"
        "افتكر, انت لسه فيها, مستنيك 🤍\n\n"
        "محمد - غاوي"
    )

    # HTML بسيط ومقصود يبان كإيميل شخصي مش نشرة تسويقية
    body_html = f"""
    <div dir="rtl" style="font-family: Arial, Tahoma, sans-serif; max-width: 560px; margin: 0 auto; color: #1f2937; font-size: 1rem; line-height: 2; padding: 8px 4px;">
        <p style="margin: 0 0 4px;">{hello}</p>
        <p style="margin: 0 0 4px;">أنا محمد, من غاوي.</p>
        <p style="margin: 0 0 20px;">{greeting}</p>
        <p style="margin: 0 0 20px;">بس انا خدت بالي إنك دخلت علي الموقع وسجلت بالفعل, بس فضلت في آخر خطوة…</p>
        <p style="margin: 0 0 20px;">انا بس عايز أفهم منك إيه اللي حصل وعطلك؟</p>
        <p style="margin: 0 0 20px;">
            هل كان في مشكلة في الدفع؟<br>
            ولا في حاجة في العرض مش واضحة؟<br>
            ولا في سبب تاني خالص؟
        </p>
        <p style="margin: 0 0 20px;">مقدر جدا اهتمامك وثقتك, فأتمني تقولي ايه السبب, وأنا هتواصل معاك شخصياً.</p>
        <p style="margin: 0 0 4px;">لو حبيت ترجع وتبدأ، اللينك هنا:</p>
        <p style="margin: 0 0 20px;"><a href="https://ghawy.ai/" style="color: #3f8ff9; font-weight: 700;">https://ghawy.ai/</a></p>
        <p style="margin: 0 0 24px;">افتكر, انت لسه فيها, مستنيك 🤍</p>
        <p style="margin: 0; font-weight: 700;">محمد - غاوي</p>
    </div>
    """

    _send_email(
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )


# ═══════════════════════════════════════════════════════
#  AUTOMATED LIFECYCLE EMAILS — shared branded base template
#  (نفس الـ Header/Logo/السوشيال/الفوتر لكل الإيميلات؛
#   المتغيّر الوحيد هو المحتوى: العنوان + الجسم + نص زرار الـ CTA)
# ═══════════════════════════════════════════════════════

# روابط ثابتة لا تتغير
_SOCIAL_INSTAGRAM = "https://www.instagram.com/ghawy.ai/"
_SOCIAL_FACEBOOK = "https://www.facebook.com/profile.php?id=61591378479904"
_SOCIAL_TIKTOK = "https://www.tiktok.com/@ghawy.ai"
_SOCIAL_WHATSAPP = "https://wa.me/201033903334"
_WHATSAPP_DISPLAY = "01033903334"
_LINK_PRIVACY = "https://ghawy.ai/privacy"
_LINK_TERMS = "https://ghawy.ai/terms"
_LINK_START = "https://ghawy.ai"


# ───────────────────────────────────────────────────────
#  تعريب الأسماء الأولى — الغالبية العظمى من الأعضاء مسجّلين
#  باسم لاتيني (Mohamed / Ahmed / Omar ...). عشان الإيميلات
#  تبان عربي فعلاً (مش "Mohamed" وسط نص عربي)، بنترجم أشهر
#  الأسماء لصيغتها العربية. أي اسم مش معروف بيرجع None (بيرجع
#  المنادي للـ fallback).
# ───────────────────────────────────────────────────────

_AR_FIRST_NAMES = {
    # محمد وتنويعاته
    "mohamed": "محمد", "mohammed": "محمد", "mohamad": "محمد", "mohammad": "محمد",
    "muhammad": "محمد", "muhamed": "محمد", "mohammd": "محمد", "mhmd": "محمد",
    "mohab": "محمد", "med": "محمد", "moh": "محمد",
    # أحمد
    "ahmed": "أحمد", "ahmad": "أحمد", "ahmd": "أحمد",
    # محمود
    "mahmoud": "محمود", "mahmood": "محمود", "mahmoed": "محمود", "mahmud": "محمود",
    # مصطفى
    "mostafa": "مصطفى", "mustafa": "مصطفى", "moustafa": "مصطفى", "moustapha": "مصطفى",
    "mostapha": "مصطفى",
    # عمر / عمرو
    "omar": "عمر", "omer": "عمر", "umar": "عمر",
    "amr": "عمرو", "amro": "عمرو",
    # يوسف
    "youssef": "يوسف", "yousef": "يوسف", "yusuf": "يوسف", "yosef": "يوسف",
    "yousief": "يوسف", "youseff": "يوسف", "yousuf": "يوسف", "yosuf": "يوسف",
    "youssuf": "يوسف",
    # عبد الرحمن / عبد الله / عبد العزيز / عبد المجيد
    "abdelrahman": "عبد الرحمن", "abdulrahman": "عبد الرحمن", "abdurrahman": "عبد الرحمن",
    "abdelrhman": "عبد الرحمن", "abdalrahman": "عبد الرحمن", "abdorahman": "عبد الرحمن",
    "abdallah": "عبد الله", "abdullah": "عبد الله", "abdalla": "عبد الله",
    "abdulla": "عبد الله", "abdellah": "عبد الله",
    "abdelaziz": "عبد العزيز", "abdulaziz": "عبد العزيز", "abdualaziz": "عبد العزيز",
    "abdulmajeed": "عبد المجيد", "abdulmajid": "عبد المجيد",
    "abdelfattah": "عبد الفتاح", "abdo": "عبده", "abdu": "عبده", "abdel": "عبد الرحمن",
    # علي / علاء / عمار / أنس
    "ali": "علي", "aly": "علي",
    "alaa": "علاء", "aalaa": "علاء", "ala": "علاء",
    "ammar": "عمار", "anas": "أنس",
    # حمزة / حسن / حسين / حسام / حازم / هاشم
    "hamza": "حمزة", "hamzah": "حمزة",
    "hassan": "حسن", "hasan": "حسن",
    "hussein": "حسين", "hussain": "حسين", "husein": "حسين", "hosein": "حسين",
    "hossam": "حسام", "hosam": "حسام", "hussam": "حسام",
    "hazem": "حازم", "hazim": "حازم",
    "hashem": "هاشم", "hashim": "هاشم",
    # زياد / مازن / معاذ / معتز / أدهم / سيف / ياسين
    "ziad": "زياد", "zeyad": "زياد", "zyad": "زياد", "ziyad": "زياد",
    "mazen": "مازن", "mazin": "مازن",
    "moaz": "معاذ", "muadh": "معاذ",
    "moataz": "معتز", "muataz": "معتز", "motaz": "معتز",
    "adham": "أدهم",
    "seif": "سيف", "saif": "سيف", "saef": "سيف", "sayf": "سيف",
    "yassin": "ياسين", "yassine": "ياسين", "yasin": "ياسين", "yassen": "ياسين",
    "yaseen": "ياسين",
    # خالد / كريم / وليد / طارق / شريف / عمر
    "khaled": "خالد", "khalid": "خالد",
    "karim": "كريم", "kareem": "كريم", "karem": "كريم",
    "walid": "وليد", "waleed": "وليد", "waled": "وليد",
    "tarek": "طارق", "tareq": "طارق", "tarik": "طارق", "tariq": "طارق",
    "sherif": "شريف", "shrief": "شريف", "sharif": "شريف",
    # أسامة / نبيل / مؤمن / إياد / إسلام / إبراهيم / آدم / أمير
    "osama": "أسامة", "usama": "أسامة",
    "nabil": "نبيل",
    "momen": "مؤمن", "moamen": "مؤمن", "moemen": "مؤمن", "mumen": "مؤمن", "momin": "مؤمن",
    "eyad": "إياد", "iyad": "إياد",
    "eslam": "إسلام", "islam": "إسلام",
    "ibrahim": "إبراهيم", "ebrahim": "إبراهيم", "ebrahem": "إبراهيم", "ibrahem": "إبراهيم",
    "adam": "آدم",
    "amir": "أمير", "ameer": "أمير",
    # مالك / مروان / بلال / نصر / صلاح / عثمان / يحيى / إيهاب / فارس
    "malek": "مالك", "malik": "مالك",
    "marwan": "مروان",
    "belal": "بلال", "bilal": "بلال",
    "nasr": "نصر",
    "salah": "صلاح",
    "othman": "عثمان", "osman": "عثمان", "othmane": "عثمان",
    "yehia": "يحيى", "yahia": "يحيى", "yehya": "يحيى", "yahya": "يحيى",
    "ehab": "إيهاب",
    "fares": "فارس", "faris": "فارس",
    # ماجد / أمجد / سعد / سامي / هاني / زكريا / وائل / تامر / عماد / أشرف
    "maged": "ماجد", "majed": "ماجد",
    "amgad": "أمجد", "amjad": "أمجد",
    "saad": "سعد", "sa3d": "سعد",
    "samy": "سامي", "sami": "سامي",
    "hani": "هاني", "hany": "هاني",
    "zakarya": "زكريا", "zakaria": "زكريا",
    "wael": "وائل",
    "tamer": "تامر",
    "emad": "عماد", "imad": "عماد",
    "ashraf": "أشرف",
    # أيمن / بهاء / ربيع / يونس / جهاد / نعيم / زين / تيم / أيهم / رامي / فادي / سامح / باسل
    "ayman": "أيمن",
    "bahaa": "بهاء", "baha": "بهاء",
    "rabie": "ربيع", "rabea": "ربيع",
    "younis": "يونس", "younes": "يونس", "yunus": "يونس",
    "gihad": "جهاد", "jihad": "جهاد",
    "naim": "نعيم", "naeem": "نعيم",
    "zain": "زين", "zayn": "زين", "zein": "زين",
    "tayem": "تيم", "taim": "تيم", "teem": "تيم",
    "ayham": "أيهم",
    "ramy": "رامي", "rami": "رامي",
    "fady": "فادي", "fadi": "فادي",
    "sameh": "سامح",
    "bassel": "باسل", "basel": "باسل", "basil": "باسل",
    "ezz": "عز", "moheb": "محب", "anis": "أنيس",
    # أسماء قبطية شائعة
    "mina": "مينا", "mena": "مينا",
    "kerollos": "كيرلس", "kirollos": "كيرلس", "kerolous": "كيرلس", "kirolos": "كيرلس",
    "bavly": "بافلي", "filopater": "فيلوباتير", "eriny": "إيريني", "irini": "إيريني",
    "gerges": "جرجس", "george": "جورج", "beshoy": "بيشوي", "boula": "بولا",
    # أسماء بنات
    "fatma": "فاطمة", "fatima": "فاطمة", "fatimah": "فاطمة",
    "aya": "آية", "aia": "آية",
    "mariam": "مريم", "maryam": "مريم", "marim": "مريم",
    "sara": "سارة", "sarah": "سارة", "sarra": "سارة",
    "nour": "نور", "noor": "نور", "nor": "نور",
    "nourhan": "نورهان", "nurhan": "نورهان",
    "salma": "سلمى",
    "yasmin": "ياسمين", "yasmine": "ياسمين", "yasmeen": "ياسمين", "jasmine": "ياسمين",
    "habiba": "حبيبة", "habeba": "حبيبة",
    "menna": "منة", "mennah": "منة",
    "nada": "ندى",
    "dina": "دينا",
    "rana": "رنا",
    "reham": "ريهام", "riham": "ريهام",
    "heba": "هبة", "hiba": "هبة",
    "mona": "منى", "mouna": "منى",
    "esraa": "إسراء", "israa": "إسراء", "esra": "إسراء",
    "doaa": "دعاء", "doa": "دعاء",
    "amira": "أميرة", "ameera": "أميرة",
    "aisha": "عائشة", "aicha": "عائشة",
    "malak": "ملك",
    "farah": "فرح",
    "rania": "رانية", "raneem": "رنيم", "raneen": "رنين",
    "shaimaa": "شيماء", "shimaa": "شيماء", "shaima": "شيماء",
    "asmaa": "أسماء", "asma": "أسماء",
    "hana": "هنا", "hanaa": "هناء", "hannah": "هناء",
    "rahma": "رحمة", "rahmah": "رحمة",
    "toka": "تقى", "tuqa": "تقى",
    "rawan": "روان", "rewan": "روان", "rowan": "روان",
    "jana": "جنى", "jannah": "جنة", "janna": "جنة",
    "sama": "سما", "samaa": "سماء",
    "eman": "إيمان", "iman": "إيمان",
    "nadia": "نادية",
    "radwa": "رضوى", "radwan": "رضوان",
    "sherouk": "شروق", "shrouk": "شروق", "shorouk": "شروق",
    "manar": "منار", "dana": "دانة", "dania": "دانية",
    "kholoud": "خلود", "khouloud": "خلود",
    "safaa": "صفاء", "wafaa": "وفاء", "sana": "سناء", "soha": "سها",
    "sahar": "سحر", "farida": "فريدة", "basant": "بسنت",
    "sumaya": "سمية", "somaya": "سمية",
    "rahaf": "رهف", "lujain": "لجين", "lojain": "لجين",
    "jood": "جود", "joud": "جود", "judy": "جودي", "jodi": "جودي",
    "layla": "ليلى", "laila": "ليلى", "lilas": "ليلى",
    "kenzy": "كنزي", "kenzi": "كنزي", "kenza": "كنزة",
    "talia": "تاليا", "lian": "ليان", "lien": "ليان",
    "sondos": "سندس", "sandra": "ساندرا", "maria": "ماريا",
    "aml": "أمل", "amal": "أمل", "amany": "أماني", "amani": "أماني",
    "logina": "لوجينا", "rodina": "رودينا", "haidy": "هايدي",
    "joumana": "جمانة", "gomana": "جمانة", "jumana": "جمانة",
    # إضافات من بيانات الأعضاء الحقيقية + أسماء خليجية/شامية شائعة
    "anouar": "أنور", "anwar": "أنور",
    "mohanad": "مهند", "mohaned": "مهند", "mohanned": "مهند", "muhannad": "مهند",
    "fathy": "فتحي", "fathi": "فتحي",
    "abdalrhman": "عبد الرحمن", "abdelrahim": "عبد الرحيم", "abderrahmane": "عبد الرحمن",
    "amed": "أحمد",
    "oussama": "أسامة",
    "faiz": "فايز", "fayez": "فايز", "fayes": "فايز",
    "badr": "بدر", "bader": "بدر",
    "reem": "ريم", "rim": "ريم",
    "david": "داود", "dawood": "داود", "dawoud": "داود",
    "yasser": "ياسر", "yaser": "ياسر", "yassir": "ياسر",
    "samir": "سمير", "sameer": "سمير", "munir": "منير", "mounir": "منير",
    "adel": "عادل", "gamal": "جمال", "kamal": "كمال", "galal": "جلال",
    "magdy": "مجدي", "hamdy": "حمدي", "sabry": "صبري", "lotfy": "لطفي",
    "shawky": "شوقي", "shawki": "شوقي", "refaat": "رفعت",
    "taha": "طه", "ismail": "إسماعيل", "esmail": "إسماعيل", "ismael": "إسماعيل",
    "idris": "إدريس", "sohaib": "صهيب", "suhaib": "صهيب",
    "obada": "عبادة", "ubada": "عبادة", "qusai": "قصي", "qusay": "قصي",
    "wassim": "وسيم", "waseem": "وسيم", "nizar": "نزار", "ghaith": "غيث",
    "noureddine": "نور الدين", "noureddin": "نور الدين", "noureldeen": "نور الدين",
    "abdelhamid": "عبد الحميد", "abdelghani": "عبد الغني", "abdelmoneim": "عبد المنعم",
    "fahd": "فهد", "faisal": "فيصل", "faysal": "فيصل", "sultan": "سلطان",
    "turki": "تركي", "nayef": "نايف", "saud": "سعود", "rakan": "راكان",
    "rayan": "ريان", "rayyan": "ريان", "laith": "ليث", "layth": "ليث",
    "hamad": "حمد", "khalifa": "خليفة", "rashed": "راشد", "rashid": "راشد",
    # أسماء بنات إضافية
    "yousra": "يسرا", "yosra": "يسرا", "shahd": "شهد", "retaj": "ريتاج",
    "remas": "ريماس", "retal": "ريتال", "rital": "ريتال",
    "joury": "جوري", "jory": "جوري", "sham": "شام", "mayar": "ميار",
    "lamar": "لمار", "lara": "لارا", "tia": "تيا", "mila": "ميلا",
    "raghad": "رغد", "danya": "دانيا", "jouri": "جوري",
    "hala": "هالة", "ghala": "غلا", "wateen": "وتين",
    "batoul": "بتول", "batool": "بتول", "sedra": "سدرة", "sidra": "سدرة",
    "leen": "لين", "lin": "لين", "elin": "إلين", "celine": "سيلين",
}


_COUNTRY_AR = {
    "egypt": "مصر", "united arab emirates": "الإمارات", "uae": "الإمارات",
    "saudi arabia": "السعودية", "ksa": "السعودية", "kuwait": "الكويت",
    "algeria": "الجزائر", "jordan": "الأردن", "morocco": "المغرب",
    "palestine": "فلسطين", "palestinian territory": "فلسطين", "state of palestine": "فلسطين",
    "iraq": "العراق", "tunisia": "تونس", "turkey": "تركيا", "türkiye": "تركيا", "turkiye": "تركيا",
    "syria": "سوريا", "syrian arab republic": "سوريا", "libya": "ليبيا",
    "lebanon": "لبنان", "qatar": "قطر", "yemen": "اليمن", "oman": "عُمان",
    "sudan": "السودان", "mauritania": "موريتانيا", "bahrain": "البحرين",
    "united states": "الولايات المتحدة", "united states of america": "الولايات المتحدة",
    "united kingdom": "المملكة المتحدة", "germany": "ألمانيا", "france": "فرنسا",
    "italy": "إيطاليا", "canada": "كندا", "chad": "تشاد", "malaysia": "ماليزيا",
    "singapore": "سنغافورة", "burkina faso": "بوركينا فاسو", "somalia": "الصومال",
    "djibouti": "جيبوتي", "comoros": "جزر القمر",
}


def country_to_arabic(raw: str) -> str:
    """اسم البلد بالعربي، أو النص الأصلي لو مش معروف."""
    if not raw or not raw.strip():
        return ""
    if is_arabic_text(raw):
        return raw.strip()
    return _COUNTRY_AR.get(raw.strip().lower(), raw.strip())


def is_arabic_text(s: str) -> bool:
    """صح لو النص فيه أي حرف عربي."""
    return bool(s) and any("؀" <= ch <= "ۿ" for ch in s)


def _norm_latin_name(s: str) -> str:
    """تطبيع اسم لاتيني للبحث في الماب: إزالة التشكيل + حروف بس + lowercase."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = "".join(ch for ch in s if ch.isalpha())
    return s.lower().strip()


def arabize_first_name(name: str):
    """
    يرجّع الصيغة العربية لاسم أول واحد:
      • لو فيه عربي أصلاً → يرجّعه زي ما هو.
      • لو لاتيني ومعروف في الماب → الترجمة العربية.
      • غير كده → None (المنادي يقرر الـ fallback).
    """
    if not name or not name.strip():
        return None
    tok = name.strip().split()[0]
    if is_arabic_text(tok):
        return tok
    return _AR_FIRST_NAMES.get(_norm_latin_name(tok))


def _first_name(full_name: str) -> str:
    """
    الاسم الأول للتحية في الإيميلات التلقائية — معرّب لو أمكن، وإلا الاسم الأول زي
    ما هو، وإلا "صديقنا".
    """
    name = (full_name or "").strip()
    if not name:
        return "صديقنا"
    tok = name.split()[0]
    return arabize_first_name(tok) or tok


def _brand_email_html(*, heading: str, body_paragraphs: list, cta_text: str,
                      cta_url: str, pre_footer: str = "") -> str:
    """القالب الأساسي الموحّد لكل الإيميلات التلقائية (RTL) — Design System فاتح."""
    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai")
    logo = f"{frontend_url}/imgs/community-logo.png"
    # أيقونات السوشيال بنسخة رمادية موحّدة (monochrome) بدل الألوان البراندية
    icon = lambda n: f"{frontend_url}/imgs/email/{n}-mono.png"

    # ستاك خطوط عربي نضيف (يفضل قريب من المرجع) مع fallbacks مضمونة على كل الأجهزة
    font_stack = "'Tajawal','Cairo',Tahoma,Arial,sans-serif"

    paragraphs_html = "".join(
        f'<p style="margin:0 0 14px;">{p}</p>' for p in body_paragraphs
    )

    pre_footer_block = ""
    if pre_footer:
        pre_footer_block = (
            '<div style="color:#4b4b52;font-size:14px;line-height:1.9;text-align:right;'
            'margin-top:8px;border-top:1px solid #E5E5E5;padding-top:16px;">'
            f'{pre_footer}</div>'
        )

    return f"""\
<div style="background:#F4F4F5;padding:24px 0;margin:0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F4F4F5;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" dir="rtl" style="max-width:600px;width:100%;background:#FFFFFF;border:1px solid #E5E5E5;border-radius:14px;overflow:hidden;font-family:{font_stack};box-shadow:0 1px 4px rgba(0,0,0,0.06);">
        <tr><td style="padding:34px 32px 8px;">
          <p style="color:#1A1A1A;font-size:16px;font-weight:600;margin:0 0 16px;text-align:right;line-height:1.7;">{heading}</p>
          <div style="color:#1A1A1A;font-size:15px;font-weight:400;line-height:1.7;text-align:right;">{paragraphs_html}</div>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:26px 0 12px;"><tr>
            <td align="center" bgcolor="#D6FF3F" style="border-radius:10px;">
              <a href="{cta_url}" style="display:block;padding:16px 24px;color:#0a0a0a;font-size:16px;font-weight:700;text-decoration:none;text-align:center;font-family:{font_stack};">{cta_text}</a>
            </td></tr></table>
          {pre_footer_block}
          <p style="color:#1A1A1A;font-size:15px;font-weight:700;margin:20px 0 0;text-align:right;">فريق غاوي</p>
        </td></tr>
        <tr><td align="center" style="padding:26px 24px 6px;">
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto;"><tr>
            <td align="center" bgcolor="#FFFFFF" style="border-radius:16px;padding:16px 22px;border:1px solid #ECECEC;">
              <img src="{logo}" alt="Ghawy" width="80" style="display:block;max-width:80px;height:auto;margin:0 auto;">
            </td></tr></table>
        </td></tr>
        <tr><td align="center" style="padding:18px 24px 6px;">
          <p style="color:#6B7280;font-size:13px;margin:0 0 12px;">تابعنا على السوشيال ميديا</p>
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto;"><tr>
            <td style="padding:0 5px;"><a href="{_SOCIAL_INSTAGRAM}"><img src="{icon('instagram')}" width="28" height="28" alt="Instagram" style="display:block;"></a></td>
            <td style="padding:0 5px;"><a href="{_SOCIAL_TIKTOK}"><img src="{icon('tiktok')}" width="28" height="28" alt="TikTok" style="display:block;"></a></td>
            <td style="padding:0 5px;"><a href="{_SOCIAL_FACEBOOK}"><img src="{icon('facebook')}" width="28" height="28" alt="Facebook" style="display:block;"></a></td>
          </tr></table>
        </td></tr>
        <tr><td align="center" style="background:#FAFAFB;padding:22px 24px;border-top:1px solid #E5E5E5;">
          <p style="color:#9a9aa6;font-size:12px;margin:0 0 10px;">© 2026 Ghawy — AI Automation Atlas</p>
          <p style="margin:0 0 10px;">
            <a href="{_LINK_TERMS}" style="color:#2563EB;font-size:12px;text-decoration:none;">الشروط والأحكام</a>
            <span style="color:#c7c7cf;">&nbsp;·&nbsp;</span>
            <a href="{_LINK_PRIVACY}" style="color:#2563EB;font-size:12px;text-decoration:none;">سياسة الخصوصية</a>
            <span style="color:#c7c7cf;">&nbsp;·&nbsp;</span>
            <a href="{_LINK_START}" style="color:#2563EB;font-size:12px;text-decoration:none;">ابدأ الآن</a>
          </p>
          <p style="margin:0;">
            <a href="{_SOCIAL_WHATSAPP}" style="color:#6B7280;font-size:12px;text-decoration:none;">
              <img src="{icon('whatsapp')}" width="14" height="14" alt="واتساب" style="vertical-align:middle;margin-left:5px;">{_WHATSAPP_DISPLAY}
            </a>
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</div>"""


def _brand_email_text(*, heading: str, body_paragraphs: list, cta_text: str,
                      cta_url: str, pre_footer: str = "") -> str:
    """نسخة نصية بسيطة (plain-text) لنفس المحتوى — لتحسين الوصول والـ deliverability."""
    strip = lambda s: re.sub(r"<[^>]+>", "", s or "")
    lines = [strip(heading), ""]
    lines += [strip(p) for p in body_paragraphs]
    lines += ["", f"{strip(cta_text)}: {cta_url}"]
    if pre_footer:
        lines += ["", strip(pre_footer)]
    lines += [
        "",
        "— فريق غاوي",
        f"إنستجرام: {_SOCIAL_INSTAGRAM}",
        f"تيك توك: {_SOCIAL_TIKTOK}",
        f"فيسبوك: {_SOCIAL_FACEBOOK}",
        f"واتساب: {_SOCIAL_WHATSAPP}",
        "© 2026 Ghawy — AI Automation Atlas",
    ]
    return "\n".join(lines)


# ─── 1) إيميل: خلّص أول درس ──────────────────────────────
def send_first_lesson_email(to_email: str, full_name: str, course_id: int) -> None:
    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai")
    name = _first_name(full_name)
    heading = f"عاش جداً يا {name}،"
    body = [
        "أنا لسه ظاهر عندي في السيستم إنك خلصت أول درس، ومقدرتش مبعتلكش بنفسي أقولك: عاش يا بطل، البداية دايماً هي أصعب خطوة وأنت كسرتها خلاص.",
        "ناس كتير بتسجل ولكن مش بتبدأ فعلاً. بس أنت أخدت أكشن وبدأت فعلاً. فدا يدل إنك داخل وعارف إنت عايز إيه، وشغوف بجد وعارف من نفسك ومن شغلك.",
        "الخطوة اللي جاية هي الأهم. لأن البداية لوحدها عمرها ما كانت كفاية. الاستمرارية هي اللي بتبني الصورة كاملة. الدرس الجاي مستنيك وجاهز، كمل طريقك وإحنا معاك خطوة بخطوة.",
    ]
    cta_text = "ادخل على الدرس الثاني الآن"
    cta_url = f"{frontend_url}/course-detail.html?id={course_id}"
    pre_footer = f"افتكر دايماً يا {name}، كل خطوة إنت بتاخدها إحنا هنفضل شايفينها، وهنفضل دايماً ندعمك 🙏."

    _send_email(
        to_email=to_email,
        subject=f"عاش جداً يا {name}،",
        body_text=_brand_email_text(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url, pre_footer=pre_footer),
        body_html=_brand_email_html(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url, pre_footer=pre_footer),
    )


# ─── 2) إيميل: خلّص كورس كامل (الشهادة جاهزة) ────────────
def send_course_completed_email(to_email: str, full_name: str, course_name: str, course_id: int) -> None:
    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai")
    name = _first_name(full_name)
    heading = f"مبروك يا {name}! شهادتك من غاوي جاهزة 🎓"
    body = [
        f"يا أهلاً بيك يا غاوي، أنا عرفت إنك أتممت كورس {course_name} بالكامل في غاوي بنجاح!",
        "فريق غاوي مش قادر يوصفلك مدى فخره بيك. الوصول للنهاية وتطبيق كل الدروس دي خطوة مبيعملهاش غير شخص \"غاوي\" فعلاً وعايز ينقل حياته وشغله لمكان تاني خالص.",
        "تتويجاً للمجهود ده، فريق غاوي جهز لك شهادة إتمام الكورس الرسمية الخاصة بيك، ومتاحة دلوقتي للتحميل فوراً. تقدر تحمل شهادتك من هنا:",
    ]
    cta_text = "تحميل شهادة الإتمام 🎓"
    cta_url = f"{frontend_url}/course-detail.html?id={course_id}"
    pre_footer = "افتكر دايماً.. دي مجرد بداية لرحلة أكبر جوه المجتمع، والكورسات والتحديثات الجاية مستنياك عشان نطور أكتر وأكتر."

    _send_email(
        to_email=to_email,
        subject=f"مبروك يا {name}! شهادتك من غاوي جاهزة 🎓",
        body_text=_brand_email_text(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url, pre_footer=pre_footer),
        body_html=_brand_email_html(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url, pre_footer=pre_footer),
    )


# ─── 3) إيميل: باقي 5 أيام على انتهاء الاشتراك ───────────
def send_5day_expiry_email(to_email: str, full_name: str) -> None:
    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai")
    name = _first_name(full_name)
    heading = f"{name}، باقي 5 أيام على انتهاء اشتراكك في غاوي"
    body = [
        "حابين نفكرك إن باقي 5 أيام فقط على انتهاء فترة اشتراكك الحالية في غاوي.",
        "إنت لسه في نص الطريق. ولو الاشتراك خلص، هتفقد الوصول لكل الكورسات الجاية والتقدم اللي وصلتله. الشهر الجديد جوه غاوي محضرين لك فيه كورسات وتحديثات قوية جداً، عشان كده إحنا متحمسين جداً نكمل معاك الرحلة دي ونشوف النقلة اللي هتعملها في شغلك الشهر الجاي.",
        "لو حابب تراجع بيانات الدفع أو تتحكم في اشتراكك، تقدر تدخل على حسابك فوراً من هنا:",
    ]
    cta_text = "إدارة اشتراكي وبيانات الدفع ⚙️"
    cta_url = f"{frontend_url}/profile-settings.html"

    _send_email(
        to_email=to_email,
        subject=f"{name}، باقي 5 أيام على انتهاء اشتراكك في غاوي",
        body_text=_brand_email_text(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url),
        body_html=_brand_email_html(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url),
    )


# ─── 4) إيميل: عيد ميلاد (هدية 7 أيام مجانية) ─────────────
def send_birthday_email(to_email: str, full_name: str, age: int, user_id: int, year: int) -> None:
    """تهنئة عيد ميلاد + زرار بيمدّد الاشتراك 7 أيام على الباقة الحالية.
    الزرار بيروح لـ /api/birthday/claim ومعاه توكن موقّع بيربط الهدية باليوزر."""
    from app.routers.birthday import make_birthday_token  # lazy عشان نتجنب circular import

    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai").rstrip("/")
    name = _first_name(full_name)
    token = make_birthday_token(user_id, year)

    heading = f"ازيك يا {name}،"
    age_line = (
        f"النهاردة بتكمل {age} سنة من السعي والتطوير، ويارب السنة الجديدة تعود عليك بكل "
        "الخير وتكون سنة نجاح وتقدم في تعلمك."
        if age else
        "النهاردة يوم مميز جداً، ويارب السنة الجديدة تعود عليك بكل الخير وتكون سنة نجاح "
        "وتقدم في تعلمك."
    )
    body = [
        age_line,
        "فريق غاوي حابب يهنئك بمناسبة عيد ميلادك، ويمدّد اشتراكك لمدة 7 أيام مجانية 🎁 "
        "تقدر تفعّل هديتك دلوقتي من الزرار هنا:",
    ]
    cta_text = "تفعيل الـ 7 أيام المجانية"
    cta_url = f"{frontend_url}/api/birthday/claim?token={token}"
    pre_footer = "كل سنة وانت طيب من كل فريق غاوي 🎂"

    _send_email(
        to_email=to_email,
        subject=f"كل سنة وانت طيب يا {name}! 🎉",
        body_text=_brand_email_text(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url, pre_footer=pre_footer),
        body_html=_brand_email_html(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url, pre_footer=pre_footer),
    )


# ─── 5) إيميل: 6 أيام مدخلش المنصة خالص ───────────────────
def send_inactive_6day_email(to_email: str, full_name: str, resume_url: str = None) -> None:
    """تذكير شخصي لليوزر اللي بقاله 6 أيام مدخلش المنصة — يرجّعه يكمّل.
    resume_url = deep link لآخر كورس وقف عنده، أو الداشبورد لو مش متاح."""
    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai").rstrip("/")
    name = _first_name(full_name)
    cta_url = resume_url or f"{frontend_url}/dashboard.html"

    heading = f"ازيك يا {name}، يارب تكون بخير وبأحسن حال."
    body = [
        "أنا لاحظت إن بقالك 6 أيام كاملين مدخلتش على المنصة ولا كملت طريقك في الكورس "
        "والمجتمع، فقلت لازم أبعتلك وأطمن عليك بنفسي.. انت كويس؟",
        "أنا عارف إن ضغوطات الحياة والشغل ساعات بتاخدنا، بس خليني أفكرك: أنت دخلت غاوي "
        "عشان كان عندك هدف واضح وعايز تعمل نقلة حقيقية في حياتك. الهدف دا لسه مستنيك "
        "جوه، ومفيش حاجة هتوصلك ليه غير الالتزام والاستمرارية.",
        "كل يوم بيفوت وأنت بعيد، الحماس بيقل، والخطوة بتبقى أصعب. إحنا لسه فيها، "
        "والشباب في الكوميونيتي شغالين ومكملين، والدروس مستنياك عشان تبدأ تطبق وتشوف "
        "نتايج بعينك. خصص لنفسك نص ساعة في اليوم وارجع كمل.",
        "وجودك هنا كان قرار، لكن استمراريتك هي مسؤولية، افتكر اللي انت بدأت عشانه.",
        "ادخل دلوقتي وشوف وقفت فين وكمل طريقك من هنا:",
    ]
    cta_text = "ارجع للمنصة وكمل طريقك 🚀"
    pre_footer = (
        "لو في أي حاجة معطلاك أو واقفة قدامك، ادخل على الكوميونيتي واكتب بوست، "
        "والفريق هيرد عليك فوراً."
    )

    _send_email(
        to_email=to_email,
        subject=f"{name}، افتكر اللي بدأت عشانه!",
        body_text=_brand_email_text(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url, pre_footer=pre_footer),
        body_html=_brand_email_html(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url, pre_footer=pre_footer),
    )
