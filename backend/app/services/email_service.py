import os
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
    """Send approval + invite link to user after admin approves their payment."""
    body_text = (
        f"Hi {full_name},\n\n"
        "Your payment has been verified! You're one step away from joining Ghawy.\n\n"
        "Click the link below to set your password and get instant access:\n\n"
        f"{registration_url}\n\n"
        "This link expires in 48 hours.\n\n"
        "See you inside,\n"
        "The Ghawy Team"
    )

    body_html = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 520px; margin: 0 auto; background: #0a0a0a; padding: 32px; border-radius: 12px; border: 1px solid #2a2a2a;">
        <div style="text-align: center; margin-bottom: 24px;">
            <div style="font-size: 48px; margin-bottom: 8px;">🎉</div>
            <h2 style="color: #fff; margin: 0;">You're in!</h2>
        </div>
        <p style="color: #ccc; line-height: 1.6;">Hi {full_name},</p>
        <p style="color: #ccc; line-height: 1.6;">Your payment has been verified! You're one step away from joining Ghawy.</p>
        <p style="color: #ccc; line-height: 1.6;">Click the button below to set your password and get instant access:</p>
        <div style="text-align: center; margin: 28px 0;">
            <a href="{registration_url}" style="display: inline-block; background: #3f8ff9; color: #000; font-weight: 700; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-size: 16px;">Complete Registration →</a>
        </div>
        <p style="color: #888; font-size: 13px; text-align: center;">This link expires in 48 hours.</p>
        <hr style="border: none; border-top: 1px solid #2a2a2a; margin: 24px 0;">
        <p style="color: #888; font-size: 13px;">See you inside,<br>The Ghawy Team</p>
    </div>
    """

    _send_email(
        to_email=to_email,
        subject="You're in! Complete your Ghawy registration 🎉",
        body_text=body_text,
        body_html=body_html,
    )


def send_payment_rejection_email(
    to_email: str,
    full_name: str,
    rejection_reason: str,
) -> None:
    """Notify user that their payment request was rejected."""
    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai")

    body_text = (
        f"Hi {full_name},\n\n"
        "Unfortunately we couldn't verify your payment.\n\n"
        f"Reason: {rejection_reason}\n\n"
        "If you believe this is a mistake, please reply to this email "
        "or resubmit with a clearer receipt.\n\n"
        f"Try again: {frontend_url}/pay.html\n\n"
        "The Ghawy Team"
    )

    body_html = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 520px; margin: 0 auto; background: #0a0a0a; padding: 32px; border-radius: 12px; border: 1px solid #2a2a2a;">
        <h2 style="color: #fff; margin: 0 0 20px;">Update on your payment request</h2>
        <p style="color: #ccc; line-height: 1.6;">Hi {full_name},</p>
        <p style="color: #ccc; line-height: 1.6;">Unfortunately we couldn't verify your payment.</p>
        <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 16px; margin: 20px 0;">
            <p style="color: #ef4444; margin: 0; font-weight: 600;">Reason:</p>
            <p style="color: #fca5a5; margin: 8px 0 0;">{rejection_reason}</p>
        </div>
        <p style="color: #ccc; line-height: 1.6;">If you believe this is a mistake, please reply to this email or resubmit with a clearer receipt.</p>
        <div style="text-align: center; margin: 28px 0;">
            <a href="{frontend_url}/pay.html" style="display: inline-block; background: #2a2a2a; color: #fff; font-weight: 600; padding: 12px 24px; border-radius: 8px; text-decoration: none; border: 1px solid #333;">Try Again →</a>
        </div>
        <hr style="border: none; border-top: 1px solid #2a2a2a; margin: 24px 0;">
        <p style="color: #888; font-size: 13px;">The Ghawy Team</p>
    </div>
    """

    _send_email(
        to_email=to_email,
        subject="Update on your Ghawy payment request",
        body_text=body_text,
        body_html=body_html,
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
    """Notify a subscriber about an upcoming live session."""
    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai")

    body_text = (
        f"Hi {full_name},\n\n"
        f"📺 New live session announced!\n\n"
        f"Title: {session_title}\n"
        f"When: {scheduled_at}\n"
        f"{('Description: ' + description + chr(10)) if description else ''}\n"
        f"Register here: {frontend_url}/build-with-me.html\n\n"
        "See you there!\n"
        "The Ghawy Team"
    )

    body_html = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 520px; margin: 0 auto; background: #0a0a0a; padding: 32px; border-radius: 12px; border: 1px solid #2a2a2a;">
        <div style="text-align: center; margin-bottom: 24px;">
            <div style="font-size: 48px; margin-bottom: 8px;">📺</div>
            <h2 style="color: #fff; margin: 0;">New Live Session!</h2>
        </div>
        <p style="color: #ccc; line-height: 1.6;">Hi {full_name},</p>
        <p style="color: #ccc; line-height: 1.6;">We have a new live session coming up!</p>
        <div style="background: rgba(63, 143, 249, 0.08); border: 1px solid rgba(63, 143, 249, 0.25); border-radius: 10px; padding: 20px; margin: 20px 0;">
            <h3 style="color: #fff; margin: 0 0 8px;">{session_title}</h3>
            <p style="color: #3f8ff9; font-weight: 600; margin: 0 0 8px;">🗓 {scheduled_at}</p>
            {'<p style="color: #aaa; margin: 0;">' + description + '</p>' if description else ''}
        </div>
        <div style="text-align: center; margin: 28px 0;">
            <a href="{frontend_url}/build-with-me.html" style="display: inline-block; background: #3f8ff9; color: #000; font-weight: 700; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-size: 16px;">Register Now →</a>
        </div>
        <hr style="border: none; border-top: 1px solid #2a2a2a; margin: 24px 0;">
        <p style="color: #888; font-size: 13px;">See you there!<br>The Ghawy Team</p>
    </div>
    """

    _send_email(
        to_email=to_email,
        subject=f"📺 New Live Session: {session_title}",
        body_text=body_text,
        body_html=body_html,
    )


# ═══════════════════════════════════════════════════════
#  SUBSCRIPTION RENEWAL REMINDER
# ═══════════════════════════════════════════════════════

_RENEWAL_PLAN_LABELS = {
    "monthly_egp":   {"label": "الشهري",       "amount": "10 جنيه",   "renew_label": "جدد اشتراكك الشهري"},
    "quarterly_egp": {"label": "تلت شهور",     "amount": "1,200 جنيه", "renew_label": "جدد اشتراكك"},
    "yearly_egp":    {"label": "السنوي",        "amount": "3,000 جنيه", "renew_label": "جدد اشتراكك السنوي"},
    "monthly_usd":   {"label": "Monthly",       "amount": "$15",        "renew_label": "Renew Monthly Plan"},
    "quarterly_usd": {"label": "Quarterly",     "amount": "$35",        "renew_label": "Renew Quarterly Plan"},
    "yearly_usd":    {"label": "Yearly",        "amount": "$100",       "renew_label": "Renew Yearly Plan"},
}


def send_renewal_reminder_email(
    to_email: str,
    full_name: str,
    days_left: int,
    plan_key: str,
    subscription_end,
) -> None:
    """بيبعت إيميل تذكير انتهاء الاشتراك"""
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5500")
    plan = _RENEWAL_PLAN_LABELS.get(plan_key, _RENEWAL_PLAN_LABELS["monthly_egp"])
    end_date_str = subscription_end.strftime("%d/%m/%Y") if subscription_end else "—"
    renew_url = f"{frontend_url}/payment.html?plan={plan_key}"

    is_arabic = plan_key.endswith("_egp")

    if is_arabic:
        subject = f"⏰ اشتراكك في Ghawy هينتهي خلال {days_left} يوم"
        body_text = (
            f"مرحباً {full_name},\n\n"
            f"اشتراكك {plan['label']} هينتهي في {end_date_str} — متبقيلك {days_left} يوم بس.\n\n"
            f"سعر التجديد: {plan['amount']}\n\n"
            f"جدد من هنا: {renew_url}\n\n"
            "لو محتاج مساعدة، تواصل معنا في أي وقت.\n"
            "© 2026 Ghawy — AI Automation Atlas"
        )
        body_html = f"""
        <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #0a0a0f; color: #fff; border-radius: 12px; overflow: hidden;">
            <div style="background: linear-gradient(135deg, #3f8ff9, #1d6fd4); padding: 32px; text-align: center;">
                <h1 style="margin: 0; font-size: 1.8rem; font-weight: 900;">Ghawy</h1>
                <p style="margin: 8px 0 0; opacity: .8;">منصة التعلم الذكي</p>
            </div>
            <div style="padding: 32px;">
                <h2 style="color: #fff; margin-bottom: 16px;">مرحباً {full_name} 👋</h2>
                <p style="color: #9ca3af; line-height: 1.8; margin-bottom: 24px;">
                    اشتراكك <strong style="color: #fff;">{plan["label"]}</strong> هينتهي في
                    <strong style="color: #f59e0b;">{end_date_str}</strong>
                    — يعني متبقيلك <strong style="color: #ef4444;">{days_left} يوم</strong> بس.
                </p>
                <div style="background: #1f2937; border-radius: 8px; padding: 16px; margin-bottom: 24px; text-align: center;">
                    <div style="font-size: .8rem; color: #6b7280; margin-bottom: 4px;">سعر التجديد</div>
                    <div style="font-size: 1.5rem; font-weight: 900; color: #3f8ff9;">{plan["amount"]}</div>
                </div>
                <div style="text-align: center; margin-bottom: 24px;">
                    <a href="{renew_url}"
                       style="display: inline-block; background: #3f8ff9; color: #fff; padding: 14px 32px; border-radius: 8px; font-weight: 700; font-size: 1rem; text-decoration: none;">
                        🔄 {plan["renew_label"]}
                    </a>
                </div>
                <p style="color: #6b7280; font-size: .82rem; text-align: center;">
                    لو محتاج مساعدة، تواصل معنا في أي وقت.
                </p>
            </div>
            <div style="background: #050507; padding: 16px; text-align: center;">
                <p style="color: #374151; font-size: .75rem; margin: 0;">© 2026 Ghawy — AI Automation Atlas</p>
            </div>
        </div>
        """
    else:
        subject = f"⏰ Your Ghawy subscription expires in {days_left} day{'s' if days_left > 1 else ''}"
        body_text = (
            f"Hi {full_name},\n\n"
            f"Your {plan['label']} subscription expires on {end_date_str} — only {days_left} day{'s' if days_left > 1 else ''} left.\n\n"
            f"Renewal Price: {plan['amount']}\n\n"
            f"Renew here: {renew_url}\n\n"
            "Need help? Reach out anytime.\n"
            "© 2026 Ghawy — AI Automation Atlas"
        )
        body_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #0a0a0f; color: #fff; border-radius: 12px; overflow: hidden;">
            <div style="background: linear-gradient(135deg, #3f8ff9, #1d6fd4); padding: 32px; text-align: center;">
                <h1 style="margin: 0; font-size: 1.8rem; font-weight: 900;">Ghawy</h1>
                <p style="margin: 8px 0 0; opacity: .8;">AI Learning Platform</p>
            </div>
            <div style="padding: 32px;">
                <h2 style="color: #fff; margin-bottom: 16px;">Hi {full_name} 👋</h2>
                <p style="color: #9ca3af; line-height: 1.8; margin-bottom: 24px;">
                    Your <strong style="color: #fff;">{plan["label"]}</strong> subscription expires on
                    <strong style="color: #f59e0b;">{end_date_str}</strong>
                    — only <strong style="color: #ef4444;">{days_left} day{'s' if days_left > 1 else ''}</strong> left.
                </p>
                <div style="background: #1f2937; border-radius: 8px; padding: 16px; margin-bottom: 24px; text-align: center;">
                    <div style="font-size: .8rem; color: #6b7280; margin-bottom: 4px;">Renewal Price</div>
                    <div style="font-size: 1.5rem; font-weight: 900; color: #3f8ff9;">{plan["amount"]}</div>
                </div>
                <div style="text-align: center; margin-bottom: 24px;">
                    <a href="{renew_url}"
                       style="display: inline-block; background: #3f8ff9; color: #fff; padding: 14px 32px; border-radius: 8px; font-weight: 700; font-size: 1rem; text-decoration: none;">
                        🔄 {plan["renew_label"]}
                    </a>
                </div>
                <p style="color: #6b7280; font-size: .82rem; text-align: center;">
                    Need help? Reach out anytime.
                </p>
            </div>
            <div style="background: #050507; padding: 16px; text-align: center;">
                <p style="color: #374151; font-size: .75rem; margin: 0;">© 2026 Ghawy — AI Automation Atlas</p>
            </div>
        </div>
        """

    _send_email(
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
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
