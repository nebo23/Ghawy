"""
فاتورة الدفع كملف PDF مرفق مع الإيميل — العميل يحمّلها أو يطبعها في أي وقت.

الأرقام هنا مش متكتوبة تاني: كل سطر في الـ PDF بيتبني من نفس الـ helpers اللي
إيميل الفاتورة بيستخدمها (`_invoice_*_rows` في email_service)، فمستحيل النسختين
يختلفوا لو حد عدّل سطر في واحدة ونسي التانية.

الرسم بـ WeasyPrint (HTML/CSS → PDF) مش برسم النص حرف حرف. السبب إن الفاتورة
عربية: WeasyPrint بيمرّر النص على Pango اللي بيوصّل الحروف ويرتّب الـ bidi صح
(رقم أو كلمة إنجليزي جوه جملة عربية بيفضلوا في مكانهم)، والالتفاف على سطر تاني
بيفضل مظبوط. المكتبات اللي بترسم النص مباشرة محتاجة reshaper و bidi يدوي
وبتكسر أول ما سطر يلتفّ.

الفونت متبعت جوه الريبو (نسخ static من فونت Cairo الرسمي) عشان الـ image
مفيهاش أي فونت مثبّت أصلاً. وعشان كده مفيش إيموجي في الـ PDF: أي كودبوينت مش
موجود في Cairo بيطلع مربع فاضي — ✅ و ✓ و → كلهم مش فيه، فختم "مدفوعة" مكتوب
نص جوه شريط ليموني بدل علامة صح.
"""
import base64
import logging
import os
import unicodedata
from pathlib import Path

from app.services.email_service import (
    _CURRENCY_AR_DEFINITE,
    _INVOICE_DURATION_LABELS,
    _INVOICE_PLAN_LABELS,
    _LINK_TERMS,
    _esc_html,
    _first_name,
    _fmt_money,
    _invoice_activation_rows,
    _invoice_customer_rows,
    _invoice_seller_rows,
    _invoice_transaction_rows,
)

logger = logging.getLogger(__name__)

_ASSETS_DIR = Path(__file__).resolve().parent / "invoice_assets"
_FONT_REGULAR = _ASSETS_DIR / "Cairo-Regular.ttf"
_FONT_BOLD = _ASSETS_DIR / "Cairo-Bold.ttf"
# نفس لوجو الإيميلات — مصدر واحد للأصول البراندية مش نسختين.
_LOGO_PATH = Path(__file__).resolve().parent / "email_campaign_assets" / "logo.png"


def invoice_pdf_filename(inv: dict) -> str:
    """اسم الملف اللي هيتحمّل. ASCII بالكامل ومن غير مسافات — أسماء الملفات
    العربية بتتكسر في شوية عملاء إيميل قديمة، ورقم الفاتورة لوحده كفاية عشان
    العميل يعرف كل ملف تبع إيه."""
    number = "".join(
        ch for ch in str(inv.get("invoice_number") or "invoice")
        if ch.isalnum() or ch in "-_"
    )
    return f"Ghawy-Invoice-{number or 'invoice'}.pdf"


def _text_dir(value) -> str:
    """اتجاه القيمة حسب أول حرف "قوي" فيها — بالظبط اللي المفروض
    unicode-bidi:plaintext يعمله، بس WeasyPrint مش بينفّذه، فبنحسبه هنا
    ونحطّه dir على الخانة نفسها.

    من غيره "منصة غاوي — Ghawy" في خانة اتجاهها ltr بتتقلب وتتقري
    "Ghawy — منصة غاوي"، والعكس بيحصل للقيم اللاتينية في خانة rtl.
    """
    for ch in str(value or ""):
        bidi = unicodedata.bidirectional(ch)
        if bidi in ("R", "AL"):
            return "rtl"
        if bidi == "L":
            return "ltr"
    return "ltr"


def _logo_data_uri() -> str:
    """اللوجو base64 جوه الـ HTML — الـ PDF بيتولد مرة واحدة والصورة صغيرة،
    فأبسط من إن WeasyPrint يفتح الملف بنفسه."""
    try:
        return "data:image/png;base64," + base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
    except Exception as exc:
        logger.warning("⚠️ Invoice PDF logo missing (%s) — rendering without it", exc)
        return ""


_CSS = """
@font-face { font-family:'Cairo'; font-weight:400; font-style:normal; src:url('__FONT_REGULAR__') format('truetype'); }
@font-face { font-family:'Cairo'; font-weight:700; font-style:normal; src:url('__FONT_BOLD__') format('truetype'); }

@page {
  size: A4;
  margin: 12mm 12mm 14mm;
  @bottom-right {
    content: "صفحة " counter(page) " من " counter(pages);
    font-family:'Cairo'; font-size:7.5pt; color:#9aa0a6;
  }
  @bottom-left {
    content: "فاتورة صادرة إلكترونياً — support@ghawy.ai";
    font-family:'Cairo'; font-size:7.5pt; color:#9aa0a6;
  }
}

* { box-sizing:border-box; }
body { font-family:'Cairo'; font-size:8.5pt; line-height:1.55; color:#1a1a1a; direction:rtl; margin:0; }
table { width:100%; border-collapse:collapse; }
td, th { vertical-align:top; }

/* الترويسة: اللوجو والاسم يمين، بيانات المستند شمال */
.head td { vertical-align:middle; padding:0; }
.head .logo { width:40pt; height:40pt; vertical-align:middle; margin-left:7pt; }
.brand-text { display:inline-block; vertical-align:middle; text-align:right; }
.brand-name { font-weight:700; font-size:12pt; line-height:1.35; }
.brand-site { color:#6b7280; font-size:8pt; line-height:1.35; }
.head-doc { text-align:left; }
.doc-title { font-weight:700; font-size:13pt; line-height:1.35; }
.doc-num { color:#3f8ff9; font-weight:700; font-size:10.5pt; direction:ltr; text-align:left; }
.paid {
  display:inline-block; background:#d6ff3f; color:#0a0a0a;
  font-weight:700; font-size:8pt; padding:2pt 9pt; border-radius:99pt; margin-top:3pt;
}
.rule { height:2.5pt; background:#d6ff3f; border-radius:2pt; margin:7pt 0 8pt; }
.lead { margin:0 0 9pt; color:#4b4b52; font-size:9pt; }

/* الكروت: عنوان + جدول تسمية/قيمة */
.cols { border-spacing:9pt 0; border-collapse:separate; }
.cols > tbody > tr > td { width:50%; padding:0; }
.card { border:0.6pt solid #e8e8e8; border-radius:6pt; padding:7pt 10pt; page-break-inside:avoid; }
.card-title { font-weight:700; font-size:9pt; margin-bottom:3pt; }
.kv td { padding:2.2pt 0; font-size:8pt; border-bottom:0.5pt solid #f2f2f2; }
.kv tr:last-child td { border-bottom:0; }
.kv .k { color:#6b7280; text-align:right; white-space:nowrap; padding-left:8pt; }
.kv .v { font-weight:700; text-align:left; }

.section-title { font-weight:700; font-size:9.5pt; margin:10pt 0 4pt; }

/* جدول البنود */
.items { border:0.6pt solid #e8e8e8; border-radius:6pt; page-break-inside:avoid; }
.items th {
  background:#fafafa; color:#6b7280; font-size:8pt; font-weight:700; padding:5pt 9pt;
  border-bottom:0.6pt solid #e8e8e8;
}
.items td { padding:6pt 9pt; font-size:8.5pt; }
.item-name { font-weight:700; }
.item-sub { color:#6b7280; font-weight:400; font-size:7.8pt; }
.t-right { text-align:right; } .t-center { text-align:center; }
.money { text-align:left; direction:ltr; white-space:nowrap; }

/* الحساب */
.totals-wrap { page-break-inside:avoid; }
.totals td { padding:3pt 0; font-size:8.5pt; }
.totals .lbl { color:#6b7280; text-align:right; }
.totals .off { color:#16a34a; font-weight:700; }
.totals .grand td { border-top:1.2pt solid #1a1a1a; padding-top:6pt; font-weight:700; font-size:10.5pt; }
.totals .grand .lbl { color:#1a1a1a; white-space:nowrap; }

.notes {
  background:#fafafa; border-radius:6pt; padding:8pt 10pt; margin-top:10pt;
  color:#6b7280; font-size:7.5pt; line-height:1.7; page-break-inside:avoid;
}
.notes a { color:#3f8ff9; text-decoration:none; }
.stamp {
  margin-top:8pt; padding-top:6pt; border-top:0.6pt solid #e8e8e8;
  color:#9aa0a6; font-size:7.5pt; text-align:center;
}
"""


def _kv_table(rows: list) -> str:
    body = "".join(
        f'<tr><td class="k">{_esc_html(label)}</td>'
        f'<td class="v" dir="{_text_dir(value)}">{_esc_html(value)}</td></tr>'
        for label, value in rows
    )
    return f'<table class="kv">{body}</table>'


def _card(title: str, rows: list) -> str:
    return (
        f'<div class="card"><div class="card-title">{_esc_html(title)}</div>'
        f'{_kv_table(rows)}</div>'
    )


def _two_cards(right: str, left: str) -> str:
    return f'<table class="cols"><tr><td>{right}</td><td>{left}</td></tr></table>'


def _totals_html(inv: dict, currency: str) -> str:
    discount = inv.get("discount_amount") or 0
    rows = (
        f'<tr><td class="lbl">سعر الباقة</td>'
        f'<td class="money">{_esc_html(_fmt_money(inv.get("original_amount"), currency))}</td></tr>'
    )
    if discount:
        # الخصم ممكن يكون مؤكد من غير اسم كوبون مؤكد — ساعتها بنكتب "الخصم"
        # ساكت، زي إيميل الفاتورة بالظبط.
        note = ""
        if inv.get("coupon_code"):
            note = f' (كوبون {inv["coupon_code"]}'
            percent = inv.get("coupon_percent")
            if percent:
                percent_str = f"{percent:g}" if isinstance(percent, (int, float)) else str(percent)
                note += f" — {percent_str}%"
            note += ")"
        rows += (
            f'<tr><td class="lbl">الخصم{_esc_html(note)}</td>'
            f'<td class="money off">- {_esc_html(_fmt_money(discount, currency))}</td></tr>'
        )
    rows += (
        f'<tr class="grand"><td class="lbl">الإجمالي المدفوع</td>'
        f'<td class="money">{_esc_html(_fmt_money(inv.get("amount"), currency))}</td></tr>'
    )
    # الحساب بياخد الشمال بس (نص الصفحة تقريباً) — الخانة الفاضية على اليمين
    # بتزقّه هناك من غير ما نعتمد على float في محرك طباعة.
    return (
        '<table class="totals-wrap"><tr><td></td><td style="width:58%;padding:0;">'
        f'<table class="totals">{rows}</table>'
        "</td></tr></table>"
    )


def _invoice_document_html(inv: dict) -> str:
    """صفحة الفاتورة كاملة — HTML مستقل بذاته (الفونت واللوجو جوّاه)."""
    currency = inv.get("currency") or "EGP"
    number = str(inv.get("invoice_number") or "")
    name = _first_name(inv.get("user_name") or "")
    plan_label = _INVOICE_PLAN_LABELS.get(inv.get("plan_key"), "اشتراك منصة غاوي")
    duration_label = _INVOICE_DURATION_LABELS.get(inv.get("duration_type"), "")
    logo = _logo_data_uri()
    logo_img = f'<img class="logo" src="{logo}" alt="">' if logo else ""

    css = (_CSS
           .replace("__FONT_REGULAR__", _FONT_REGULAR.as_uri())
           .replace("__FONT_BOLD__", _FONT_BOLD.as_uri()))

    head = f"""
    <table class="head"><tr>
      <td>{logo_img}<span class="brand-text">
        <span class="brand-name">منصة غاوي</span><br>
        <span class="brand-site">ghawy.ai</span>
      </span></td>
      <td class="head-doc">
        <div class="doc-title">فاتورة دفع</div>
        <div class="doc-num">{_esc_html(number)}</div>
        <span class="paid">مدفوعة</span>
      </td>
    </tr></table>
    <div class="rule"></div>
    <p class="lead">أهلاً يا {_esc_html(name)} — استلمنا دفعتك بنجاح واشتراكك اتفعّل. دي فاتورتك بكل تفاصيل العملية.</p>"""

    parties = _two_cards(
        _card("بيانات مُصدر الفاتورة", _invoice_seller_rows()),
        _card("بيانات العميل", _invoice_customer_rows(inv)),
    )

    items = f"""
    <div class="section-title">تفاصيل الاشتراك</div>
    <table class="items">
      <tr>
        <th class="t-right">البيان</th>
        <th class="t-center">الكمية</th>
        <th class="money">القيمة</th>
      </tr>
      <tr>
        <td class="t-right">
          <div class="item-name">{_esc_html(plan_label)}</div>
          <div class="item-sub">{_esc_html(duration_label)}</div>
        </td>
        <td class="t-center">1</td>
        <td class="money item-name">{_esc_html(_fmt_money(inv.get('original_amount'), currency))}</td>
      </tr>
    </table>
    {_totals_html(inv, currency)}"""

    details = _two_cards(
        _card("تفعيل الاشتراك", _invoice_activation_rows(inv)),
        _card("بيانات عملية الدفع", _invoice_transaction_rows(inv)),
    )

    currency_definite = _CURRENCY_AR_DEFINITE.get(currency.upper(), currency)
    notes = f"""
    <div class="notes">
      • الفاتورة دي صادرة إلكترونياً ومعتمدة من غير توقيع أو ختم.<br>
      • كل المبالغ محصّلة بـ{_esc_html(currency_definite)} وشاملة أي رسوم.<br>
      • مفيش تجديد تلقائي — الاشتراك بينتهي لوحده بانتهاء مدته من غير أي خصم تاني.<br>
      • المبالغ المدفوعة غير قابلة للاسترداد وفقاً لـ<a href="{_LINK_TERMS}">الشروط والأحكام</a>.<br>
      • لأي استفسار بخصوص الفاتورة دي، كلّمنا على support@ghawy.ai واذكر رقم الفاتورة.
    </div>
    <div class="stamp">شكراً لثقتك في غاوي — فريق غاوي</div>"""

    return f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<title>فاتورة {_esc_html(number)} — منصة غاوي</title>
<meta name="author" content="{_esc_html(os.getenv('COMPANY_LEGAL_NAME', 'منصة غاوي — Ghawy'))}">
<meta name="description" content="فاتورة دفع اشتراك منصة غاوي رقم {_esc_html(number)}">
<style>{css}</style>
</head>
<body>{head}{parties}{items}{details}{notes}</body>
</html>"""


def build_invoice_pdf(inv: dict) -> bytes:
    """بايتات الـ PDF بتاع الفاتورة.

    بترمي لو حاجة وقعت (فونت ناقص، WeasyPrint مش متسطّب...) — اللي بينده عليها
    هو اللي بيقرّر يعمل إيه، وقراره دايماً إنه يبعت الإيميل من غير مرفق بدل ما
    العميل ميستلمش فاتورته أصلاً.
    """
    from weasyprint import HTML  # ثقيل في الاستيراد — بيتحمّل وقت أول فاتورة بس
    from weasyprint.text.fonts import FontConfiguration

    font_config = FontConfiguration()
    html = _invoice_document_html(inv)
    pdf = HTML(string=html, base_url=str(_ASSETS_DIR)).write_pdf(font_config=font_config)
    logger.info("🧾 Invoice PDF built for %s (%d bytes)", inv.get("invoice_number"), len(pdf))
    return pdf
