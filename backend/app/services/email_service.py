import os
import re
import smtplib
import unicodedata
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from pathlib import Path
from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_PATH)


# ═══════════════════════════════════════════════════════
#  هوية الباعت الموحّدة + أصول البراند (مصدر واحد لكل الإيميلات)
#  كل إيميل يخرج من النظام (معاملاتي + حملات) بيستخدم الاسم ده والقالب الموحّد.
# ═══════════════════════════════════════════════════════

# اسم الباعت الظاهر — موحّد لكل الإيميلات (معاملاتي + حملات)
FROM_NAME = "Ghawy Team"

# فونت موحّد لكل الإيميلات (Cairo + fallback مضمون)
FONT_STACK = "'Cairo', Arial, sans-serif"

# لون اللينكات الموحّد — نفس أزرق المنصة
LINK_BLUE = "#3f8ff9"

# صور البراند inline عبر Content-ID (نفس مجلد أصول الحملات — مصدر واحد مش مكرّر)
_BRAND_ASSETS_DIR = Path(__file__).resolve().parent / "email_campaign_assets"
_BRAND_ASSET_FILES = {
    "logo": _BRAND_ASSETS_DIR / "logo.png",
    "instagram": _BRAND_ASSETS_DIR / "icon_instagram.png",
    "facebook": _BRAND_ASSETS_DIR / "icon_facebook.png",
    "tiktok": _BRAND_ASSETS_DIR / "icon_tiktok.png",
    "whatsapp": _BRAND_ASSETS_DIR / "icon_whatsapp.png",
}
# مصادر الصور جوه القالب: Content-ID (للإرسال الفعلي)
_CID_IMAGE_SRCS = {
    "logo": "cid:ghawy_logo",
    "instagram": "cid:social_instagram",
    "facebook": "cid:social_facebook",
    "tiktok": "cid:social_tiktok",
    "whatsapp": "cid:icon_whatsapp",
}
# الـ Content-ID header ids المطابقة (اللي بتتربط وقت الإرسال)
_CID_HEADER_IDS = {
    "logo": "ghawy_logo",
    "instagram": "social_instagram",
    "facebook": "social_facebook",
    "tiktok": "social_tiktok",
    "whatsapp": "icon_whatsapp",
}


def _attach_brand_images(message) -> None:
    """يربط صور البراند (لوجو/سوشيال/واتساب) inline بالـ Content-IDs اللي القالب الموحّد
    بيرجّعها (cid:...). بيتندَه تلقائياً من _send_email لأي إيميل فيه صور البراند."""
    for key, header_id in _CID_HEADER_IDS.items():
        path = _BRAND_ASSET_FILES.get(key)
        if not path or not os.path.exists(path):
            continue
        try:
            with open(path, "rb") as f:
                img = MIMEImage(f.read())
            img.add_header("Content-ID", f"<{header_id}>")
            img.add_header("Content-Disposition", "inline", filename=os.path.basename(str(path)))
            message.attach(img)
        except Exception:
            continue


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
    """المُرسِل الموحّد لكل الإيميلات المعاملاتية. الاسم الظاهر دايماً FROM_NAME ("Ghawy Team").
    لو الـ HTML بيستخدم القالب الموحّد (فيه صور البراند cid:) بنربط الصور inline تلقائياً."""
    smtp_host, smtp_port, smtp_user, smtp_password, smtp_from = _get_smtp_config()
    from_header = f"{FROM_NAME} <{smtp_from}>" if FROM_NAME else smtp_from

    if body_html:
        # multipart/related عشان صور البراند inline (cid:) تتعرض جوه الإيميل
        message = MIMEMultipart("related")
        message["Subject"] = subject
        message["From"] = from_header
        message["To"] = to_email
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(body_text, "plain", "utf-8"))
        alt.attach(MIMEText(body_html, "html", "utf-8"))
        message.attach(alt)
        if "cid:" in body_html:
            _attach_brand_images(message)
    else:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = from_header
        message["To"] = to_email
        message.set_content(body_text)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(message)


def _otp_inner_html(code: str, intro: str, expiry_note: str) -> str:
    """المحتوى الداخلي لإيميل كود التحقق — بيتلفّ في القالب الموحّد."""
    return f"""
          <p style="color:#1A1A1A;font-size:16px;font-weight:600;margin:0 0 16px;text-align:right;">كود التحقق الخاص بك</p>
          <p style="color:#1A1A1A;font-size:15px;margin:0 0 18px;text-align:right;">{intro}</p>
          <div style="background:#f4f8ff;border:1px solid #d5e3fb;border-radius:10px;padding:22px;text-align:center;margin:0 0 18px;">
            <span style="color:{LINK_BLUE};font-size:34px;letter-spacing:8px;font-weight:800;font-family:{FONT_STACK};">{code}</span>
          </div>
          <p style="color:#6b7280;font-size:13px;text-align:right;margin:0;">{expiry_note}</p>"""


def send_verification_email(to_email: str, code: str) -> None:
    body_text = (
        f"كود التحقق الخاص بك هو: {code}\n\n"
        "الكود صالح لمدة 15 دقيقة.\n"
        "لو مطلبتش الكود ده، تجاهل الرسالة."
    )
    inner = _otp_inner_html(
        code,
        intro="استخدم الكود التالي لإتمام عملية التحقق:",
        expiry_note="الكود صالح لمدة 15 دقيقة. لو مطلبتش الكود ده، تجاهل الرسالة.",
    )
    _send_email(
        to_email=to_email,
        subject="كود التحقق — غاوي",
        body_text=body_text,
        body_html=render_ghawy_email(inner),
    )


def send_admin_payment_notification(
    full_name: str,
    email: str,
    phone: str,
    amount: float,
    created_at: str,
    method: str = "instapay",
) -> None:
    """Notify admin team about a new manual payment submission."""
    method_ar, method_en = MANUAL_METHOD_LABELS.get(
        (method or "instapay"), MANUAL_METHOD_LABELS["instapay"]
    )
    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai")
    admin_email = os.getenv("ADMIN_EMAIL", "mosalah@ghawy.ai")

    body_text = (
        f"🔔 New payment request — {full_name}\n\n"
        f"A new manual payment request has been submitted.\n\n"
        f"Name: {full_name}\n"
        f"Email: {email}\n"
        f"Phone: {phone or 'N/A'}\n"
        f"Amount: {amount or 'N/A'} EGP\n"
        f"Method: {method_en}\n"
        f"Submitted: {created_at}\n\n"
        f"Review it here: {frontend_url}/teamdashboard.html#pending-requests"
    )

    def _row(label, value, last=False):
        border = "" if last else "border-bottom:1px solid #eee;"
        return (
            f'<tr><td style="color:#6b7280;padding:9px 0;{border}text-align:right;">{label}</td>'
            f'<td style="color:#1a1a1a;padding:9px 0;{border}text-align:left;direction:ltr;">{value}</td></tr>'
        )

    review_url = f"{frontend_url}/teamdashboard.html#pending-requests"
    inner = f"""
          <p style="color:#1A1A1A;font-size:16px;font-weight:700;margin:0 0 16px;text-align:right;">🔔 طلب دفع جديد</p>
          <p style="color:#4b4b52;font-size:15px;margin:0 0 18px;text-align:right;">اتقدّم طلب دفع يدوي جديد ومحتاج مراجعة.</p>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:0 0 22px;font-size:14px;">
            {_row('الاسم', full_name)}
            {_row('الإيميل', email)}
            {_row('الموبايل', phone or 'N/A')}
            {_row('المبلغ', f"{amount or 'N/A'} EGP")}
            {_row('طريقة التحويل', method_ar)}
            {_row('التاريخ', created_at, last=True)}
          </table>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 6px;"><tr>
            <td align="center" bgcolor="#D6FF3F" style="border-radius:10px;">
              <a href="{review_url}" style="display:block;padding:15px 24px;color:#0a0a0a;font-size:16px;font-weight:700;text-decoration:none;text-align:center;font-family:{FONT_STACK};">مراجعة الطلب الآن →</a>
            </td></tr></table>"""

    _send_email(
        to_email=admin_email,
        subject=f"🔔 New payment request — {full_name}",
        body_text=body_text,
        body_html=render_ghawy_email(inner),
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
    """إشعار رفض طلب الدفع — نفس القالب الموحّد بس بثيم أحمر (نتيجة سلبية)."""
    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai").rstrip("/")
    name = _first_name(full_name)
    heading = f"{name}، للأسف مقدرناش نأكّد طلب الدفع بتاعك ❌"
    body = [
        "راجعنا الإيصال اللي بعتّه ومقدرناش نأكّد عملية الدفع.",
        f'السبب: <strong style="color:#DC2626;">{rejection_reason}</strong>',
        "لو شايف إن ده حصل بالغلط، ردّ على الإيميل ده أو ابعت الإيصال تاني بصورة أوضح "
        "وإحنا هنراجعه فوراً.",
    ]
    cta_text = "ابعت الإيصال تاني"
    cta_url = f"{frontend_url}/pay.html"

    _send_email(
        to_email=to_email,
        subject="تحديث بخصوص طلب الدفع بتاعك في غاوي",
        body_text=_brand_email_text(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url),
        body_html=_brand_email_html(
            heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url,
            heading_color="#DC2626", cta_bg="#DC2626", cta_color="#ffffff",
        ),
    )


# ═══════════════════════════════════════════════════════
#  فاتورة الدفع (كاشير) — INVOICE
# ═══════════════════════════════════════════════════════
#
# بتتبعت مرة واحدة بس لكل عملية دفع ناجحة، من جوه
# confirm_kashier_payment — وهي النقطة الوحيدة اللي بيعدّي منها
# الـ webhook والـ redirect الاتنين، وبتشتغل على PENDING بس. يعني
# العضو عمره ما هياخد فاتورتين لنفس العملية مهما وصل الإشارتين.
#
# اللي مش بيدخل الفاتورة عن قصد:
#   • cardDataToken / ccvToken — دول توكنز بيتخصم بيهم من الكارت.
#     محصلش ولا هيحصل إنهم يتبعتوا في إيميل.
#   • settlementInfo (عمولة كاشير والمبلغ الصافي اللي بيوصلنا) —
#     ده رقم بيزنس بتاعنا إحنا، مالوش لازمة في فاتورة العميل.

_INVOICE_PLAN_LABELS = {
    "monthly_egp":   "اشتراك منصة غاوي — الباقة الشهرية",
    "quarterly_egp": "اشتراك منصة غاوي — باقة 3 شهور",
    "yearly_egp":    "اشتراك منصة غاوي — الباقة السنوية",
}

_INVOICE_DURATION_LABELS = {
    "1_month":  "شهر واحد (30 يوم)",
    "3_months": "3 شهور (90 يوم)",
    "1_year":   "سنة كاملة (365 يوم)",
}

_CURRENCY_AR = {
    "EGP": "جنيه مصري",
    "USD": "دولار أمريكي",
    "SAR": "ريال سعودي",
    "AED": "درهم إماراتي",
}

# الصيغة المعرّفة — لجملة زي "كل المبالغ محصّلة بالجنيه المصري"،
# اللي "بالـ" + النكرة بتطلع فيها غلط.
_CURRENCY_AR_DEFINITE = {
    "EGP": "الجنيه المصري",
    "USD": "الدولار الأمريكي",
    "SAR": "الريال السعودي",
    "AED": "الدرهم الإماراتي",
}

# أسماء المحافظ الإلكترونية زي ما كاشير بيبعتها في payScheme
_WALLET_SCHEME_AR = {
    "vodafonecash": "فودافون كاش",
    "etisalatcash": "اتصالات كاش",
    "orangecash": "أورنج كاش",
    "wecash": "وي باي",
    "bmwallet": "محفظة بنكية",
}


def _esc_html(value) -> str:
    """أي قيمة جاية من بوابة الدفع أو من بيانات العضو بتتهرّب قبل ما تدخل الـ HTML."""
    s = "" if value is None else str(value)
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def _fmt_cairo_datetime(dt) -> str:
    """تاريخ ووقت بتوقيت القاهرة بصيغة عربية — الباك إند بيخزن UTC naive."""
    if not dt:
        return "—"
    from datetime import timezone as _timezone
    from zoneinfo import ZoneInfo
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_timezone.utc)
    local = dt.astimezone(ZoneInfo("Africa/Cairo"))
    hour12 = local.hour % 12 or 12
    meridiem = "ص" if local.hour < 12 else "م"
    return f"{local:%d/%m/%Y} — {hour12}:{local:%M} {meridiem}"


def _fmt_cairo_date(dt) -> str:
    """تاريخ من غير وقت (لتاريخ نهاية الاشتراك)."""
    if not dt:
        return "—"
    from datetime import timezone as _timezone
    from zoneinfo import ZoneInfo
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_timezone.utc)
    return f"{dt.astimezone(ZoneInfo('Africa/Cairo')):%d/%m/%Y}"


def _fmt_money(amount, currency: str = "EGP") -> str:
    """مبلغ بمنزلتين عشريتين + اسم العملة بالعربي — زي ما الفاتورة المفروض تبان."""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return "—"
    unit = _CURRENCY_AR.get((currency or "EGP").upper(), currency or "")
    return f"{value:,.2f} {unit}".strip()


def _mask_wallet_account(account: str) -> str:
    """رقم محفظة العميل — أول 3 وآخر 4 بس، الباقي نجوم."""
    digits = "".join(ch for ch in (account or "") if ch.isdigit())
    if len(digits) < 8:
        return account or ""
    return f"{digits[:3]}••••{digits[-4:]}"


def _invoice_payment_method(gw: dict) -> str:
    """سطر وسيلة الدفع بالظبط زي ما العميل دفع بيها."""
    method = (gw.get("method") or "").lower()
    if method == "card":
        brand = gw.get("card_brand") or "بطاقة"
        masked = gw.get("masked_card") or ""
        last4 = "".join(ch for ch in masked if ch.isdigit())[-4:] if masked else ""
        return f"بطاقة بنكية — {brand}" + (f" •••• {last4}" if last4 else "")
    if method == "wallet":
        raw_scheme = gw.get("wallet_scheme") or ""
        scheme = _WALLET_SCHEME_AR.get(raw_scheme.lower().replace(" ", ""), raw_scheme)
        account = _mask_wallet_account(gw.get("payer_account") or "")
        line = f"محفظة إلكترونية — {scheme}" if scheme else "محفظة إلكترونية"
        return line + (f" ({account})" if account else "")
    return "كاشير — دفع إلكتروني"


def _invoice_seller_rows() -> list:
    """بيانات مُصدر الفاتورة. الرقم الضريبي والسجل التجاري بيتقروا من الـ env
    وبيظهروا لو متكوّنين بس — مفيش رقم بيتخترع هنا."""
    rows = [
        ("الجهة المُصدِرة", os.getenv("COMPANY_LEGAL_NAME", "منصة غاوي — Ghawy")),
        ("الموقع الإلكتروني", "ghawy.ai"),
        ("البريد الإلكتروني", "support@ghawy.ai"),
        ("واتساب الدعم", _WHATSAPP_DISPLAY),
    ]
    address = os.getenv("COMPANY_ADDRESS", "")
    tax_id = os.getenv("COMPANY_TAX_ID", "")
    commercial_reg = os.getenv("COMPANY_COMMERCIAL_REGISTER", "")
    if address:
        rows.append(("العنوان", address))
    if tax_id:
        rows.append(("الرقم الضريبي", tax_id))
    if commercial_reg:
        rows.append(("السجل التجاري", commercial_reg))
    return rows


def _inv_section(title: str, rows: list) -> str:
    """عنوان قسم + جدول تسميات/قيم. القيم LTR عشان الأرقام واللاتيني يبانوا صح في RTL."""
    body = ""
    for index, (label, value) in enumerate(rows):
        border = "" if index == len(rows) - 1 else "border-bottom:1px solid #EFEFEF;"
        body += (
            f'<tr><td style="color:#6b7280;padding:9px 0;{border}text-align:right;'
            f'font-size:13px;white-space:nowrap;">{_esc_html(label)}</td>'
            f'<td style="color:#1a1a1a;padding:9px 0 9px 0;{border}text-align:left;'
            f'direction:ltr;unicode-bidi:plaintext;font-size:13px;font-weight:600;">'
            f'{_esc_html(value)}</td></tr>'
        )
    return (
        f'<p style="color:#1A1A1A;font-size:14px;font-weight:700;margin:26px 0 8px;'
        f'text-align:right;">{_esc_html(title)}</p>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;">{body}</table>'
    )


def _invoice_html(inv: dict) -> str:
    """جسم الفاتورة — بيتلفّ في القالب الموحّد render_ghawy_email زي أي إيميل تاني."""
    currency = inv.get("currency") or "EGP"
    gw = inv.get("gateway") or {}
    name = _first_name(inv.get("user_name") or "")
    discount = inv.get("discount_amount") or 0

    # ── الترويسة: رقم الفاتورة + ختم "مدفوعة" ──
    header = f"""
          <p style="color:#1A1A1A;font-size:18px;font-weight:700;margin:0 0 4px;text-align:right;">فاتورة دفع</p>
          <p style="color:#4b4b52;font-size:15px;margin:0 0 18px;text-align:right;line-height:1.8;">
            أهلاً يا {_esc_html(name)} — استلمنا دفعتك بنجاح واشتراكك اتفعّل. دي فاتورتك بكل تفاصيل العملية.
          </p>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                 style="background:#f4f8ff;border:1px solid #d5e3fb;border-radius:10px;margin:0 0 6px;">
            <tr>
              <td style="padding:16px 18px;text-align:right;">
                <div style="color:#6b7280;font-size:12px;margin-bottom:3px;">رقم الفاتورة</div>
                <div style="color:{LINK_BLUE};font-size:17px;font-weight:800;direction:ltr;
                            unicode-bidi:plaintext;text-align:right;">{_esc_html(inv.get('invoice_number'))}</div>
              </td>
              <td style="padding:16px 18px;text-align:left;">
                <span style="display:inline-block;background:#D6FF3F;color:#0a0a0a;font-size:13px;
                             font-weight:800;padding:7px 14px;border-radius:999px;">مدفوعة ✅</span>
              </td>
            </tr>
          </table>"""

    # ── البند: الباقة نفسها ──
    plan_label = _INVOICE_PLAN_LABELS.get(inv.get("plan_key"), "اشتراك منصة غاوي")
    duration_label = _INVOICE_DURATION_LABELS.get(inv.get("duration_type"), "")
    item = f"""
          <p style="color:#1A1A1A;font-size:14px;font-weight:700;margin:26px 0 8px;text-align:right;">تفاصيل الاشتراك</p>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                 style="border-collapse:collapse;border:1px solid #EFEFEF;border-radius:10px;">
            <tr style="background:#FAFAFA;">
              <th style="color:#6b7280;font-size:12px;font-weight:600;padding:10px 14px;text-align:right;">البيان</th>
              <th style="color:#6b7280;font-size:12px;font-weight:600;padding:10px 14px;text-align:center;">الكمية</th>
              <th style="color:#6b7280;font-size:12px;font-weight:600;padding:10px 14px;text-align:left;">القيمة</th>
            </tr>
            <tr>
              <td style="padding:14px;text-align:right;color:#1a1a1a;font-size:13px;font-weight:600;border-top:1px solid #EFEFEF;">
                {_esc_html(plan_label)}
                <div style="color:#6b7280;font-size:12px;font-weight:400;margin-top:4px;">{_esc_html(duration_label)}</div>
              </td>
              <td style="padding:14px;text-align:center;color:#1a1a1a;font-size:13px;border-top:1px solid #EFEFEF;">1</td>
              <td style="padding:14px;text-align:left;color:#1a1a1a;font-size:13px;font-weight:600;direction:ltr;border-top:1px solid #EFEFEF;">
                {_esc_html(_fmt_money(inv.get('original_amount'), currency))}
              </td>
            </tr>
          </table>"""

    # ── الحساب: السعر ثم الخصم ثم المدفوع ──
    totals_rows = (
        f'<tr><td style="color:#6b7280;padding:8px 0;text-align:right;font-size:13px;">سعر الباقة</td>'
        f'<td style="color:#1a1a1a;padding:8px 0;text-align:left;direction:ltr;font-size:13px;">'
        f'{_esc_html(_fmt_money(inv.get("original_amount"), currency))}</td></tr>'
    )
    if discount:
        # ساعات بيبقى فيه خصم مؤكد من غير اسم كوبون مؤكد (شوف _pricing_details) —
        # ساعتها بنكتب "الخصم" ساكت بدل "الخصم (كوبون None)".
        coupon_note = ""
        if inv.get("coupon_code"):
            coupon_note = f' (كوبون {inv["coupon_code"]}'
            percent = inv.get("coupon_percent")
            if percent:
                # 20.0 لازم تطلع "20%" مش "20.0%"، و 12.5 تفضل زي ما هي.
                percent_str = f"{percent:g}" if isinstance(percent, (int, float)) else str(percent)
                coupon_note += f' — {percent_str}%'
            coupon_note += ')'
        totals_rows += (
            f'<tr><td style="color:#6b7280;padding:8px 0;text-align:right;font-size:13px;">'
            f'الخصم{_esc_html(coupon_note)}</td>'
            f'<td style="color:#16a34a;padding:8px 0;text-align:left;direction:ltr;font-size:13px;font-weight:600;">'
            f'- {_esc_html(_fmt_money(discount, currency))}</td></tr>'
        )
    totals = f"""
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:14px 0 0;">
            {totals_rows}
            <tr>
              <td style="color:#1a1a1a;padding:14px 0 0;text-align:right;font-size:15px;font-weight:800;border-top:2px solid #1a1a1a;">
                الإجمالي المدفوع
              </td>
              <td style="color:#1a1a1a;padding:14px 0 0;text-align:left;direction:ltr;font-size:16px;font-weight:800;border-top:2px solid #1a1a1a;">
                {_esc_html(_fmt_money(inv.get('amount'), currency))}
              </td>
            </tr>
          </table>"""

    # ── الأقسام: العميل / العملية / المُصدر ──
    customer = _inv_section("بيانات العميل", [
        ("الاسم", inv.get("user_name") or "—"),
        ("رقم العضوية", f"#{inv.get('user_id')}"),
        ("البريد الإلكتروني", inv.get("user_email") or "—"),
        ("رقم الموبايل", inv.get("user_phone") or "—"),
        ("الدولة", country_to_arabic(inv.get("user_country") or "") or "—"),
        ("المحافظة", _governorate_to_arabic(inv.get("user_governorate") or "") or "—"),
    ])

    transaction_rows = [
        ("وسيلة الدفع", _invoice_payment_method(gw)),
    ]
    if gw.get("card_holder"):
        transaction_rows.append(("اسم حامل البطاقة", gw["card_holder"]))
    if gw.get("payer_name"):
        transaction_rows.append(("اسم صاحب المحفظة", gw["payer_name"]))
    if gw.get("paid_through"):
        transaction_rows.append(("مزوّد المحفظة", gw["paid_through"]))
    transaction_rows += [
        ("بوابة الدفع", "Kashier"),
        ("رقم العملية", gw.get("transaction_id") or "—"),
        ("رقم الطلب", inv.get("order_id") or "—"),
    ]
    if gw.get("kashier_order_id"):
        transaction_rows.append(("مرجع كاشير", gw["kashier_order_id"]))
    if gw.get("order_reference"):
        transaction_rows.append(("رقم مرجعي إضافي", gw["order_reference"]))
    if gw.get("response_message"):
        code = f" ({gw['response_code']})" if gw.get("response_code") else ""
        transaction_rows.append(("نتيجة العملية", f"{gw['response_message']}{code}"))
    transaction_rows.append(("تاريخ ووقت الدفع", _fmt_cairo_datetime(inv.get("paid_at"))))
    if gw.get("channel"):
        transaction_rows.append(("قناة الدفع", gw["channel"]))
    if gw.get("customer_ip"):
        transaction_rows.append(("عنوان IP وقت الدفع", gw["customer_ip"]))
    transaction_rows.append(("حالة الدفع", "ناجحة — تم التحصيل"))
    transaction = _inv_section("بيانات عملية الدفع", transaction_rows)

    activation = _inv_section("تفعيل الاشتراك", [
        ("تاريخ التفعيل", _fmt_cairo_datetime(inv.get("paid_at"))),
        ("المدة المضافة", f"{inv.get('days')} يوم"),
        ("الاشتراك ساري حتى", _fmt_cairo_date(inv.get("subscription_end"))),
    ])

    seller = _inv_section("بيانات مُصدر الفاتورة", _invoice_seller_rows())

    notes = f"""
          <div style="background:#FAFAFA;border-radius:10px;padding:16px 18px;margin:26px 0 0;
                      color:#6b7280;font-size:12.5px;line-height:1.9;text-align:right;">
            • الفاتورة دي صادرة إلكترونياً ومعتمدة من غير توقيع أو ختم.<br>
            • كل المبالغ محصّلة بـ{_esc_html(_CURRENCY_AR_DEFINITE.get(currency.upper(), currency))} وشاملة أي رسوم.<br>
            • مفيش تجديد تلقائي — الاشتراك بينتهي لوحده بانتهاء مدته من غير أي خصم تاني.<br>
            • المبالغ المدفوعة غير قابلة للاسترداد وفقاً لـ<a href="{_LINK_TERMS}" style="color:{LINK_BLUE};text-decoration:none;">الشروط والأحكام</a>.<br>
            • لأي استفسار بخصوص الفاتورة دي، ردّ على الإيميل ده أو كلّمنا على support@ghawy.ai واذكر رقم الفاتورة.
          </div>"""

    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai").rstrip("/")
    cta = f"""
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:28px 0 6px;"><tr>
            <td align="center" bgcolor="#D6FF3F" style="border-radius:10px;">
              <a href="{frontend_url}/dashboard.html" style="display:block;padding:16px 24px;color:#0a0a0a;
                 font-size:16px;font-weight:700;text-decoration:none;text-align:center;font-family:{FONT_STACK};">
                ادخل المنصة وابدأ دلوقتي →
              </a>
            </td></tr></table>
          <p style="color:#1A1A1A;font-size:15px;font-weight:700;margin:20px 0 0;text-align:right;">فريق غاوي</p>"""

    inner = header + item + totals + customer + activation + transaction + seller + notes + cta
    return render_ghawy_email(inner)


def _invoice_text(inv: dict) -> str:
    """نسخة نصية من نفس الفاتورة — للـ deliverability وللقارئات النصية."""
    currency = inv.get("currency") or "EGP"
    gw = inv.get("gateway") or {}
    lines = [
        f"فاتورة دفع — {inv.get('invoice_number')}",
        "الحالة: مدفوعة",
        "",
        f"البيان: {_INVOICE_PLAN_LABELS.get(inv.get('plan_key'), 'اشتراك منصة غاوي')}",
        f"المدة: {_INVOICE_DURATION_LABELS.get(inv.get('duration_type'), '')}",
        f"سعر الباقة: {_fmt_money(inv.get('original_amount'), currency)}",
    ]
    if inv.get("discount_amount"):
        label = f"الخصم (كوبون {inv['coupon_code']})" if inv.get("coupon_code") else "الخصم"
        lines.append(f"{label}: - {_fmt_money(inv.get('discount_amount'), currency)}")
    lines += [
        f"الإجمالي المدفوع: {_fmt_money(inv.get('amount'), currency)}",
        "",
        "بيانات العميل:",
        f"  الاسم: {inv.get('user_name') or '—'}",
        f"  رقم العضوية: #{inv.get('user_id')}",
        f"  البريد الإلكتروني: {inv.get('user_email') or '—'}",
        f"  رقم الموبايل: {inv.get('user_phone') or '—'}",
        "",
        "تفعيل الاشتراك:",
        f"  تاريخ التفعيل: {_fmt_cairo_datetime(inv.get('paid_at'))}",
        f"  المدة المضافة: {inv.get('days')} يوم",
        f"  ساري حتى: {_fmt_cairo_date(inv.get('subscription_end'))}",
        "",
        "بيانات العملية:",
        f"  وسيلة الدفع: {_invoice_payment_method(gw)}",
        f"  بوابة الدفع: Kashier",
        f"  رقم العملية: {gw.get('transaction_id') or '—'}",
        f"  رقم الطلب: {inv.get('order_id') or '—'}",
        f"  تاريخ ووقت الدفع: {_fmt_cairo_datetime(inv.get('paid_at'))}",
        "",
        "مُصدر الفاتورة:",
    ]
    lines += [f"  {label}: {value}" for label, value in _invoice_seller_rows()]
    lines += [
        "",
        "فاتورة صادرة إلكترونياً ولا تحتاج توقيع. مفيش تجديد تلقائي.",
        "المبالغ غير قابلة للاسترداد وفقاً للشروط والأحكام: " + _LINK_TERMS,
        "",
        "— فريق غاوي",
        "support@ghawy.ai",
        "© Copyright Ghawy 2026",
    ]
    return "\n".join(lines)


def send_payment_invoice_email(invoice: dict) -> None:
    """يبعت فاتورة الدفع للعضو بعد ما كاشير يأكّد العملية.

    `invoice` قاموس عادي (مش ORM objects) عشان الفنكشن دي بتشتغل في
    BackgroundTask بعد ما الـ DB session بتكون قفلت خلاص. مفاتيحه:

      invoice_number, order_id, plan_key, duration_type, days,
      amount, original_amount, discount_amount, currency,
      coupon_code, coupon_percent, paid_at, subscription_end,
      user_id, user_name, user_email, user_phone, user_country,
      user_governorate, gateway{...}
    """
    to_email = (invoice.get("user_email") or "").strip()
    if not to_email:
        return
    _send_email(
        to_email=to_email,
        subject=f"فاتورة اشتراكك في غاوي — {invoice.get('invoice_number')}",
        body_text=_invoice_text(invoice),
        body_html=_invoice_html(invoice),
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
}


def _plan_price_str(plan_key: str) -> str:
    """السعر الحقيقي للباقة من مصدر الحقيقة (payment.PLAN_PRICES) — مش قيمة مكتوبة بالإيد."""
    try:
        from app.routers.payment import PLAN_PRICES  # lazy: تفادي circular import
        p = PLAN_PRICES.get(plan_key)
        if p:
            # كل الباقات بالجنيه المصري — مفيش تسعير بالدولار.
            return f"{p['amount']:,} جنيه"
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
    # /pricing replaced /payment as the page holding the plans and checkout.
    renew_url = f"{frontend_url}/pricing?plan={plan_key}"
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

    # اللينك دايماً من URL نضيف (من غير سلاش زايدة في الأول ولا نص الزرار في الـ href)
    cta_url = _LINK_START  # "https://ghawy.ai"
    cta_text = "ارجع وكمّل آخر خطوة 🤍"

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
        f"لو حبيت ترجع وتبدأ، اللينك هنا:\n{cta_url}\n"
        "افتكر, انت لسه فيها, مستنيك 🤍\n\n"
        "محمد - غاوي"
    )

    # المحتوى الداخلي بس — بيتلفّ في القالب الموحّد render_ghawy_email (نفس الهيدر/اللوجو
    # والـ card الفاتح وفونت Cairo والفوتر الموحّد زي كل إيميلات غاوي).
    inner = f"""
          <p style="color:#1A1A1A;font-size:16px;font-weight:600;margin:0 0 4px;text-align:right;">{hello}</p>
          <p style="color:#1A1A1A;font-size:15px;margin:0 0 4px;text-align:right;">أنا محمد, من غاوي.</p>
          <p style="color:#1A1A1A;font-size:15px;margin:0 0 18px;text-align:right;">{greeting}</p>
          <p style="color:#1A1A1A;font-size:15px;margin:0 0 16px;text-align:right;line-height:1.9;">بس انا خدت بالي إنك دخلت علي الموقع وسجلت بالفعل, بس فضلت في آخر خطوة…</p>
          <p style="color:#1A1A1A;font-size:15px;margin:0 0 16px;text-align:right;line-height:1.9;">انا بس عايز أفهم منك إيه اللي حصل وعطلك؟</p>
          <p style="color:#1A1A1A;font-size:15px;margin:0 0 16px;text-align:right;line-height:1.9;">
            هل كان في مشكلة في الدفع؟<br>
            ولا في حاجة في العرض مش واضحة؟<br>
            ولا في سبب تاني خالص؟
          </p>
          <p style="color:#1A1A1A;font-size:15px;margin:0 0 16px;text-align:right;line-height:1.9;">مقدر جدا اهتمامك وثقتك, فأتمني تقولي ايه السبب, وأنا هتواصل معاك شخصياً.</p>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0 12px;"><tr>
            <td align="center" bgcolor="#D6FF3F" style="border-radius:10px;">
              <a href="{cta_url}" style="display:block;padding:16px 24px;color:#0a0a0a;font-size:16px;font-weight:700;text-decoration:none;text-align:center;font-family:{FONT_STACK};">{cta_text}</a>
            </td></tr></table>
          <p style="color:#1A1A1A;font-size:15px;margin:6px 0 20px;text-align:right;">افتكر, انت لسه فيها, مستنيك 🤍</p>
          <p style="color:#1A1A1A;font-size:15px;font-weight:700;margin:0;text-align:right;">محمد - غاوي</p>"""

    _send_email(
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        body_html=render_ghawy_email(inner),
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


def _ghawy_footer_html(srcs: dict) -> str:
    """الفوتر الموحّد لكل الإيميلات: لوجو + سوشيال (تيك توك/فيسبوك/إنستجرام) + لينكات
    زرقا + واتساب الدعم + سطر الكوبيرايت. srcs = خريطة مصادر الصور
    (CID للإرسال الفعلي / data: URIs للمعاينة)."""
    def link(url, label):
        return (f'<a href="{url}" target="_blank" style="color:{LINK_BLUE};text-decoration:none;'
                f'margin:0 9px;font-size:13px;">{label}</a>')

    def social(url, key, alt):
        return (f'<a href="{url}" target="_blank" style="display:inline-block;margin:0 7px;text-decoration:none;border:0;">'
                f'<img src="{srcs.get(key, "")}" width="28" height="28" alt="{alt}" '
                f'style="display:inline-block;width:28px;height:28px;border:0;vertical-align:middle;"></a>')

    return f"""
        <tr><td style="padding:0 40px 34px;">
          <div style="border-top:1px solid #eee;padding-top:26px;text-align:center;">
            <div><img src="{srcs.get('logo', '')}" alt="Ghawy" width="72" style="display:inline-block;border:0;opacity:0.92;"></div>
            <div style="margin-top:16px;">
              {social(_SOCIAL_TIKTOK, 'tiktok', 'TikTok')}
              {social(_SOCIAL_FACEBOOK, 'facebook', 'Facebook')}
              {social(_SOCIAL_INSTAGRAM, 'instagram', 'Instagram')}
            </div>
            <div style="margin-top:18px;">
              {link(_LINK_TERMS, 'الشروط والأحكام')}
              {link(_LINK_PRIVACY, 'سياسة الخصوصية')}
              {link(_LINK_START, 'ابدأ الآن')}
            </div>
            <div style="margin-top:14px;">
              <a href="{_SOCIAL_WHATSAPP}" target="_blank" style="text-decoration:none;color:{LINK_BLUE};font-size:13px;">
                <img src="{srcs.get('whatsapp', '')}" width="18" height="18" alt="واتساب" style="vertical-align:middle;margin-left:6px;border:0;">الدعم: {_WHATSAPP_DISPLAY}
              </a>
            </div>
            <div style="margin-top:20px;color:#9a9aa6;font-size:12px;">© Copyright Ghawy 2026</div>
          </div>
        </td></tr>"""


def _hero_emoji_html(hero_emoji: str) -> str:
    """بلوك الـ hero: emoji/أيقونة كبيرة متوسّطة فوق المحتوى مباشرة (لإيميلات عيد الميلاد/
    الشهادة وأي إيميل أيقوني). بستايل inline آمن للإيميل. لو مفيش emoji بيرجّع نص فاضي
    فالإيميل يترندر عادي من غير مساحة زايدة."""
    emoji = (hero_emoji or "").strip()
    if not emoji:
        return ""
    # الـ emoji بييجي من منشئ الحملة — نهرّبه HTML كدفاع خلفي (الـ emoji متأثرش)
    emoji = (emoji.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))[:16]
    return (
        '<div style="text-align:center;margin:0 0 24px;line-height:1;">'
        f'<span style="font-size:64px;line-height:1;display:inline-block;">{emoji}</span>'
        '</div>'
    )


def render_ghawy_email(body_html: str, *, image_srcs: dict = None, footer: bool = True,
                       hero_emoji: str = "") -> str:
    """القالب الموحّد الوحيد لشكل أي إيميل غاوي (معاملاتي أو حملة).
    body_html = المحتوى الداخلي بس؛ الإطار (card فاتح + فونت Cairo + الفوتر الموحّد) واحد
    لكل الإيميلات — ممنوع يبقى فيه قالب تاني.
    hero_emoji (اختياري) = emoji/أيقونة كبيرة تتعرض فوق المحتوى مباشرة كـ hero متوسّط."""
    srcs = image_srcs or _CID_IMAGE_SRCS
    footer_html = _ghawy_footer_html(srcs) if footer else ""
    hero_html = _hero_emoji_html(hero_emoji)
    return f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f4f4f4;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4;padding:24px 0;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0"
             style="background-color:#ffffff;border-radius:12px;overflow:hidden;max-width:600px;width:100%;font-family:{FONT_STACK};box-shadow:0 1px 4px rgba(0,0,0,0.06);">
        <tr>
          <td style="padding:36px 40px;direction:rtl;text-align:right;color:#1a1a1a;font-size:16px;line-height:1.9;font-family:{FONT_STACK};">
            {hero_html}{body_html}
          </td>
        </tr>
        {footer_html}
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _brand_email_html(*, heading: str, body_paragraphs: list, cta_text: str,
                      cta_url: str, pre_footer: str = "", hero_emoji: str = "",
                      cta_bg: str = "#D6FF3F", cta_color: str = "#0a0a0a",
                      heading_color: str = "#1A1A1A") -> str:
    """الإيميلات التلقائية: بيبني المحتوى الداخلي بس (عنوان + فقرات + زرار CTA + توقيع)
    ويلفّه في القالب الموحّد render_ghawy_email — فمفيش قالب مكرّر.
    hero_emoji (اختياري) = emoji كبيرة فوق المحتوى (عيد ميلاد 🎂 / شهادة 🎓 ...).
    cta_bg/cta_color/heading_color (اختياري) = تلوين مختلف للإيميلات السلبية
    (زي رفض الدفع بالأحمر) — الافتراضي هو الليموني البراندي لكل الباقي."""
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

    inner = f"""
          <p style="color:{heading_color};font-size:16px;font-weight:600;margin:0 0 16px;text-align:right;line-height:1.7;">{heading}</p>
          <div style="color:#1A1A1A;font-size:15px;font-weight:400;line-height:1.7;text-align:right;">{paragraphs_html}</div>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:26px 0 12px;"><tr>
            <td align="center" bgcolor="{cta_bg}" style="border-radius:10px;">
              <a href="{cta_url}" style="display:block;padding:16px 24px;color:{cta_color};font-size:16px;font-weight:700;text-decoration:none;text-align:center;font-family:{FONT_STACK};">{cta_text}</a>
            </td></tr></table>
          {pre_footer_block}
          <p style="color:#1A1A1A;font-size:15px;font-weight:700;margin:20px 0 0;text-align:right;">فريق غاوي</p>"""
    return render_ghawy_email(inner, hero_emoji=hero_emoji)


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
        "© Copyright Ghawy 2026",
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
        body_html=_brand_email_html(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url, pre_footer=pre_footer, hero_emoji="🎓"),
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
        "فريق غاوي حابب يهنئك بمناسبة عيد ميلادك، ويهديك 7 أيام مجانية على اشتراكك 🎁 "
        "اضغط على الزرار وسجّل طلب هديتك، وأول ما نفعّلهالك هتوصلك رسالة تأكيد على المنصة:",
    ]
    cta_text = "تفعيل الـ 7 أيام المجانية"
    cta_url = f"{frontend_url}/api/birthday/claim?token={token}"
    pre_footer = "كل سنة وانت طيب من كل فريق غاوي 🎂"

    _send_email(
        to_email=to_email,
        subject=f"كل سنة وانت طيب يا {name}! 🎉",
        body_text=_brand_email_text(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url, pre_footer=pre_footer),
        body_html=_brand_email_html(heading=heading, body_paragraphs=body, cta_text=cta_text, cta_url=cta_url, pre_footer=pre_footer, hero_emoji="🎂"),
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
