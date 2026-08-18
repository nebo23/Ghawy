/**
 * renewal.js — صفحة تجديد الاشتراك (/renewal)
 *
 * وضعين على نفس الصفحة:
 *   1) قفل  (is_active === false) → الداشبورد مموّه ورا overlay مالوش قفل،
 *      وقدام المستخدم كروت الدفع علطول. الخروج الوحيد = logout.
 *   2) تجديد مبكّر (is_active === true + ?intent=renew) → "باقي معاك X يوم"
 *      + معاينة حيّة للتاريخ الجديد بعد التجديد + زرار رجوع للداشبورد.
 *
 * الصفحة دي وجهة كل حُرّاس "الاشتراك خلص" في الفرونت، فمفيهاش حارس بنفسها
 * (أي حارس هنا = لوب لا نهائي). والقفل الحقيقي server-side على أي حال:
 * get_current_active_member بيرجّع 402 لكل APIs الأعضاء.
 *
 * ⚠️ فرونت إند بالكامل — مفيش أي تعديل في الباك إند. أي حساب أيام هنا
 * معاينة تقديرية بس؛ التمديد الفعلي بيحصل في payment_service.py.
 */

'use strict';

// نفس منطق utils.js — بس الصفحة مستقلة عشان متجرش وراها الـ polling
// والـ heartbeat اللي بيرجّعوا 402 للمستخدم المنتهي.
const API = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
    ? 'http://127.0.0.1:8000'
    : '/api';

// ─── اللغة ──────────────────────────────────────────────────
// الصفحة دي كانت مكتوبة عربي ثابت و<html lang="ar" dir="rtl"> متسمّر في
// الماركب، فالعضو اللي مختار إنجليزي كان بيتحوّل عليها (الحارس بتاع الاشتراك
// المنتهي بيوديه هنا) ويلاقي صفحة عربي — وده جزء من إحساس إن اللغة "مش متصلة".
// المصدر واحد: window.currentLang() من src/js/i18n.js، اللي بيقرا ghawy_lang.
function lang() {
    if (typeof window.currentLang === 'function') return window.currentLang();
    return document.documentElement.getAttribute('lang') === 'en' ? 'en' : 'ar';
}

/** يختار النص المناسب من {ar, en}. */
function L(pair) {
    if (pair == null) return '';
    if (typeof pair === 'string') return pair;
    return pair[lang()] || pair.ar || '';
}

const T = {
    loading: { ar: 'بنجيب تفاصيل اشتراكك...', en: 'Fetching your subscription details…' },
    currency: { ar: 'جنيه', en: 'EGP' },
    // وضع القفل
    lockedTitle: { ar: 'اشتراكك خلص — جدّد دلوقتي وكمّل من غير ما تخرج', en: 'Your subscription has ended — renew now and carry on where you left off' },
    lockedSub: { ar: 'حسابك ومحتواك ومحادثاتك كلها مستنياك زي ما هي. اختار باقتك، ادفع في دقيقة، وهترجع للداشبورد على طول.', en: 'Your account, your content and your conversations are all still here. Pick a plan, pay in a minute, and you are back on your dashboard right away.' },
    endedOn: { ar: 'اشتراكك انتهى يوم', en: 'Your subscription ended on' },
    renewCta: { ar: 'جدّد اشتراكك 🚀', en: 'Renew your subscription 🚀' },
    logout: { ar: 'تسجيل الخروج', en: 'Sign out' },
    // وضع التجديد المبكّر
    renewTitle: { ar: 'تجديد الاشتراك', en: 'Renew your subscription' },
    renewSub: { ar: 'اشتراكك لسه شغّال — أي تجديد دلوقتي بيتضاف <b>فوق</b> الأيام الباقية، مش بيلغيها.', en: 'Your subscription is still running — renewing now is added <b>on top of</b> the days you have left, not instead of them.' },
    youHaveLeft: { ar: 'باقي معاك', en: 'You have left' },
    endsOn: { ar: 'اشتراكك بيخلص يوم', en: 'Your subscription ends on' },
    currentPlan: { ar: 'باقتك الحالية', en: 'Your current plan' },
    noEndDate: { ar: 'من غير تاريخ انتهاء', en: 'No end date' },
    lessThanADay: { ar: 'أقل من يوم', en: 'Less than a day' },
    openEnded: { ar: 'مفتوح', en: 'Open-ended' },
    freeMembership: { ar: 'عضوية مجانية', en: 'Free membership' },
    renewNowCta: { ar: 'جدّد دلوقتي 🚀', en: 'Renew now 🚀' },
    backToDashboard: { ar: 'ارجع للداشبورد', en: 'Back to dashboard' },
    // الدفع
    securePay: { ar: 'الدفع آمن 100% عبر Kashier', en: '100% secure payment via Kashier' },
    or: { ar: 'أو', en: 'or' },
    payInstapay: { ar: 'ادفع عبر انستاباي', en: 'Pay with InstaPay' },
    payVodafone: { ar: 'ادفع عبر فودافون كاش', en: 'Pay with Vodafone Cash' },
    manualNoteRenew: { ar: 'التحويل اليدوي بيتراجع بإيدينا، والاشتراك بيتحسب من <b>يوم الموافقة</b> — يعني الأيام الباقية معاك دلوقتي مش هتتضاف عليه. لو عايز الأيام تتجمّع، ادفع بالكارت.', en: 'A manual transfer is reviewed by hand and the subscription is counted from the <b>day it is approved</b> — the days you have left now will not be added to it. If you want the days to stack, pay by card.' },
    manualNoteLocked: { ar: 'التحويل اليدوي محتاج مراجعة من الفريق، فالتفعيل مش فوري زي الكارت.', en: 'A manual transfer needs a review by the team, so activation is not instant the way card payment is.' },
    // المعاينة
    willRunUntil: { ar: 'اشتراكك هيشتغل لحد {date}', en: 'Your subscription will run until {date}' },
    totalUntil: { ar: 'المجموع <b>{days}</b> · لحد {date}', en: 'Total <b>{days}</b> · until {date}' },
    addedUntil: { ar: '<b>{days}</b> · لحد {date}', en: '<b>{days}</b> · until {date}' },
    previewRenewStacked: { ar: 'لو جدّدت دلوقتي هيبقى معاك مجموع <b>{days}</b>', en: 'Renewing now gives you a total of <b>{days}</b>' },
    previewRenewPlain: { ar: 'لو جدّدت دلوقتي هيبقى معاك <b>{days}</b>', en: 'Renewing now gives you <b>{days}</b>' },
    previewRenewTail: { ar: ' — واشتراكك هيخلص يوم <b>{date}</b>.', en: ' — and your subscription will end on <b>{date}</b>.' },
    previewLocked: { ar: 'لو دفعت دلوقتي هيترجعلك الوصول فورًا لمدة <b>{days}</b> — لحد يوم <b>{date}</b>.', en: 'Paying now restores your access immediately for <b>{days}</b> — until <b>{date}</b>.' },
    // الأخطاء
    errTitle: { ar: 'مش قادرين نجيب تفاصيل اشتراكك', en: 'We could not load your subscription details' },
    retry: { ar: 'حاول تاني', en: 'Try again' },
    errNetwork: { ar: 'مشكلة في الاتصال بالسيرفر. جرّب تاني بعد شوية.', en: 'There was a problem reaching the server. Please try again shortly.' },
    errServer: { ar: 'السيرفر رجّعلنا خطأ غير متوقع. جرّب تاني، ولو فضلت المشكلة كلّم الدعم.', en: 'The server returned an unexpected error. Please try again, and contact support if it keeps happening.' },
    errParse: { ar: 'رد السيرفر مش مفهوم. جرّب تاني.', en: 'We could not read the server response. Please try again.' },
    redirecting: { ar: 'جارٍ التحويل لصفحة الدفع... ✅', en: 'Taking you to the payment page… ✅' },
    sessionExpired: { ar: 'انتهت الجلسة، سجّل دخولك تاني', en: 'Your session expired — please sign in again' },
    payFailed: { ar: 'حصل خطأ وإحنا بنجهّز الدفع، حاول تاني', en: 'Something went wrong while preparing the payment. Please try again.' },
    noConnection: { ar: 'مفيش اتصال بالسيرفر — اتأكد من النت وحاول تاني', en: 'No connection to the server — check your internet and try again' },
};

/** يملا {name} في النص المترجم. */
function fill(pair, vars) {
    let s = L(pair);
    for (const k in vars) s = s.split('{' + k + '}').join(vars[k]);
    return s;
}

// نفس باقات payment.js — المنصة بتعرض EGP بس.
// الأسعار هنا للعرض فقط؛ المصدر الرسمي هو PLAN_PRICES في backend/app/routers/payment.py.
// و`days` مطابقة لـ plan_duration() في backend/app/services/payment_service.py.
const PLANS = {
    monthly_egp: {
        amount: 600, currency: 'EGP', days: 30,
        label: { ar: 'شهري', en: 'Monthly' },
        period: { ar: 'شهر', en: 'month' },
        badge: null,
    },
    quarterly_egp: {
        amount: 1200, currency: 'EGP', days: 90,
        label: { ar: 'ربع سنوي', en: 'Quarterly' },
        period: { ar: '3 شهور', en: '3 months' },
        badge: { ar: 'وفّر 600 جنيه', en: 'Save 600 EGP' },
    },
    yearly_egp: {
        amount: 3500, currency: 'EGP', days: 365,
        label: { ar: 'سنوي', en: 'Yearly' },
        period: { ar: 'سنة', en: 'year' },
        badge: { ar: 'وفّر 3700 جنيه', en: 'Save 3,700 EGP' },
    },
};
const PLAN_ORDER = ['monthly_egp', 'quarterly_egp', 'yearly_egp'];

let selectedPlan = 'monthly_egp';
let sub = null;          // payload بتاع /profile/subscription-info
let mode = 'locked';     // 'locked' | 'renew'

const cardEl = document.getElementById('renewalCard');

// ─── Helpers ────────────────────────────────────────────────
function getToken() { return localStorage.getItem('token'); }

function clearSession() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
}

function goLogin() {
    clearSession();
    window.location.replace('/login');
}

function logout() { goLogin(); }

function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
}

/** الباك إند بيبعت UTC "naive" من غير Z — من غير ما نضيفها الوقت بيتقري
 *  local ويطلع التاريخ غلط بـ ~3 ساعات (توقيت مصر). */
function parseUtc(iso) {
    if (!iso) return null;
    let s = String(iso);
    if (!/[zZ]$/.test(s) && !/[+-]\d{2}:?\d{2}$/.test(s)) s += 'Z';
    const d = new Date(s);
    return isNaN(d.getTime()) ? null : d;
}

/** تاريخ واضح بأرقام لاتينية (عشان يبقى متسق مع باقي الأرقام في الصفحة) */
function fmtDate(d) {
    if (!d) return '—';
    const opts = { timeZone: 'Africa/Cairo', day: 'numeric', month: 'long', year: 'numeric' };
    // en-GB زي العربي: يوم ثم شهر ثم سنة، فترتيب المعلومة ما بتتغيرش مع اللغة.
    const locales = lang() === 'en' ? ['en-GB'] : ['ar-EG-u-nu-latn', 'ar-EG'];
    for (const loc of locales) {
        try { return d.toLocaleDateString(loc, opts); } catch (e) { /* جرّب اللي بعده */ }
    }
    return d.toISOString().slice(0, 10);
}

/** جمع التكسير العربي مقابل جمع إنجليزي بسيط. */
function daysWord(n) {
    if (lang() === 'en') return n === 1 ? '1 day' : n + ' days';
    if (n === 1) return 'يوم واحد';
    if (n === 2) return 'يومين';
    if (n >= 3 && n <= 10) return n + ' أيام';
    return n + ' يوم';
}

function showAlert(msg, type) {
    const el = document.getElementById('rnAlert');
    if (!el) return;
    el.textContent = msg;
    el.className = 'rn-alert show ' + (type || 'error');
}

function clearAlert() {
    const el = document.getElementById('rnAlert');
    if (el) el.className = 'rn-alert';
}

// ─── معاينة التجديد ─────────────────────────────────────────
// لازم تطابق payment_service.confirm_kashier_payment:
//   base = end_at لو (end_at موجود و end_at > now) وإلا now
//   end_at_new = base + مدة_الباقة
function previewFor(planKey) {
    const plan = PLANS[planKey];
    const now = new Date();
    const end = parseUtc(sub && sub.subscription_end);
    const stillRunning = !!(end && end.getTime() > now.getTime());
    const base = stillRunning ? end : now;
    const newEnd = new Date(base.getTime() + plan.days * 86400000);

    // الأيام المتبقية جاية من الباك إند نفسه — مش بنحسبها هنا
    const remaining = (stillRunning && typeof sub.days_remaining === 'number') ? sub.days_remaining : 0;

    return {
        newEnd: newEnd,
        addedDays: plan.days,
        totalDays: remaining + plan.days,
        stillRunning: stillRunning,
    };
}

// ─── بناء الواجهة ───────────────────────────────────────────
function plansHtml() {
    return PLAN_ORDER.map(key => {
        const p = PLANS[key];
        const pv = previewFor(key);
        const active = key === selectedPlan;
        const badge = p.badge ? `<span class="rn-plan-badge">${esc(L(p.badge))}</span>` : '';
        // في وضع التجديد بنقول "المجموع" بس لما يكون فيه أيام باقية فعلاً تتضاف عليها
        const note = mode !== 'renew'
            ? fill(T.willRunUntil, { date: fmtDate(pv.newEnd) })
            : (pv.stillRunning
                ? fill(T.totalUntil, { days: daysWord(pv.totalDays), date: fmtDate(pv.newEnd) })
                : fill(T.addedUntil, { days: daysWord(pv.addedDays), date: fmtDate(pv.newEnd) }));

        return `
      <button type="button" class="rn-plan${active ? ' active' : ''}" data-plan="${key}"
              aria-pressed="${active ? 'true' : 'false'}">
        ${badge}
        <div class="rn-plan-name">${esc(L(p.label))}</div>
        <div class="rn-plan-price">${p.amount.toLocaleString('en-US')}<span>${esc(L(T.currency))} / ${esc(L(p.period))}</span></div>
        <div class="rn-plan-note">${note}</div>
      </button>`;
    }).join('');
}

function previewBoxHtml() {
    const pv = previewFor(selectedPlan);
    if (mode === 'renew') {
        const head = pv.stillRunning
            ? fill(T.previewRenewStacked, { days: daysWord(pv.totalDays) })
            : fill(T.previewRenewPlain, { days: daysWord(pv.addedDays) });
        return `<div class="rn-preview" id="rnPreview">
      <i class="fa-solid fa-circle-info"></i>
      ${head}${fill(T.previewRenewTail, { date: fmtDate(pv.newEnd) })}
    </div>`;
    }
    return `<div class="rn-preview" id="rnPreview">
    <i class="fa-solid fa-circle-info"></i>
    ${fill(T.previewLocked, { days: daysWord(pv.addedDays), date: fmtDate(pv.newEnd) })}
  </div>`;
}

/** رابط الدفع اليدوي (انستاباي أو فودافون كاش) — نفس اللي بيعمله startManual()
 *  في pricing.js: pay.html بياخد الـ cycle من غير لاحقة العملة. و`intent=renew`
 *  بيخلّي pay.js يسيب العضو المفعّل يكمّل بدل ما يرميه على الداشبورد.
 *
 *  انستاباي هو الافتراضي على /pay، فرابطه بيفضل زي ما هو من غير `method` —
 *  أي لينك قديم لسه بيوصل نفس المكان. */
function manualUrl(method) {
    const cycle = selectedPlan.replace(/_(egp|usd)$/, '');
    const methodQS = (method && method !== 'instapay') ? `&method=${encodeURIComponent(method)}` : '';
    return `/pay?plan=${encodeURIComponent(cycle)}` + (mode === 'renew' ? '&intent=renew' : '') + methodQS;
}

function payButtonHtml(label) {
    // ⚠️ الموافقة اليدوية في الباك إند بتحسب end_at = وقت الموافقة + مدة الباقة
    //    (مش بتمدّد من end_at الحالي زي Kashier)، فالعضو اللي لسه معاه أيام
    //    لازم يعرف إنه ممكن يخسرها لو دفع انستاباي.
    const manualNote = mode === 'renew'
        ? `<div class="rn-manual-note">
         <i class="fa-solid fa-triangle-exclamation"></i>
         ${L(T.manualNoteRenew)}
       </div>`
        : `<div class="rn-manual-note">
         <i class="fa-solid fa-clock"></i>
         ${L(T.manualNoteLocked)}
       </div>`;

    return `<button type="button" class="rn-pay" id="rnPayBtn">
    <span class="rn-spinner"></span>
    <span class="rn-pay-text">${label}</span>
  </button>
  <div class="rn-secure"><i class="fa-solid fa-lock"></i> ${esc(L(T.securePay))}</div>
  <div class="rn-or"><span>${esc(L(T.or))}</span></div>
  <button type="button" class="rn-instapay" id="rnManualBtn">
    <i class="fa-solid fa-wallet"></i>
    <span>${esc(L(T.payInstapay))}</span>
  </button>
  <button type="button" class="rn-instapay" id="rnVodafoneBtn">
    <i class="fa-solid fa-mobile-screen-button"></i>
    <span>${esc(L(T.payVodafone))}</span>
  </button>
  ${manualNote}`;
}

function renderLocked() {
    mode = 'locked';
    const end = parseUtc(sub && sub.subscription_end);
    const endLine = end
        ? `<div class="rn-status"><div class="rn-stat">
         <div class="rn-stat-label">${esc(L(T.endedOn))}</div>
         <div class="rn-stat-value">${fmtDate(end)}</div>
       </div></div>`
        : '';

    cardEl.innerHTML = `
    <img class="rn-logo" src="./imgs/community-logo.png" alt="Ghawy" />
    <div class="rn-icon danger"><i class="fa-solid fa-lock"></i></div>
    <h1 class="rn-title" id="rnTitle">${esc(L(T.lockedTitle))}</h1>
    <p class="rn-sub">${esc(L(T.lockedSub))}</p>
    ${endLine}
    <div class="rn-plans" id="rnPlans">${plansHtml()}</div>
    ${previewBoxHtml()}
    <div class="rn-alert" id="rnAlert"></div>
    ${payButtonHtml(esc(L(T.renewCta)))}
    <div class="rn-actions">
      <button type="button" class="rn-ghost-btn danger" id="rnLogoutBtn">
        <i class="fa-solid fa-right-from-bracket"></i> ${esc(L(T.logout))}
      </button>
    </div>`;

    bindCard();
}

function renderRenew() {
    mode = 'renew';
    const end = parseUtc(sub && sub.subscription_end);
    const remaining = typeof sub.days_remaining === 'number' ? sub.days_remaining : null;

    const dayWord = lang() === 'en' ? (remaining === 1 ? 'day' : 'days') : 'يوم';
    const remainingValue = remaining === null
        ? `<span style="font-size:1.1rem">${esc(L(T.noEndDate))}</span>`
        : (remaining === 0 ? esc(L(T.lessThanADay)) : `${remaining} <small>${dayWord}</small>`);

    const planLine = sub.is_free
        ? esc(L(T.freeMembership))
        : (sub.plan_label ? esc(sub.plan_label) : '—');

    // سهم "الرجوع" بيلف مع اتجاه الصفحة — يمين في RTL، شمال في LTR.
    const backArrow = lang() === 'en' ? 'fa-arrow-left' : 'fa-arrow-right';

    cardEl.innerHTML = `
    <img class="rn-logo" src="./imgs/community-logo.png" alt="Ghawy" />
    <div class="rn-icon"><i class="fa-solid fa-rotate"></i></div>
    <h1 class="rn-title" id="rnTitle">${esc(L(T.renewTitle))}</h1>
    <p class="rn-sub">${L(T.renewSub)}</p>

    <div class="rn-status">
      <div class="rn-stat">
        <div class="rn-stat-label">${esc(L(T.youHaveLeft))}</div>
        <div class="rn-stat-value big">${remainingValue}</div>
      </div>
      <div class="rn-stat">
        <div class="rn-stat-label">${esc(L(T.endsOn))}</div>
        <div class="rn-stat-value">${end ? fmtDate(end) : esc(L(T.openEnded))}</div>
      </div>
      <div class="rn-stat">
        <div class="rn-stat-label">${esc(L(T.currentPlan))}</div>
        <div class="rn-stat-value">${planLine}</div>
      </div>
    </div>

    <div class="rn-plans" id="rnPlans">${plansHtml()}</div>
    ${previewBoxHtml()}
    <div class="rn-alert" id="rnAlert"></div>
    ${payButtonHtml(esc(L(T.renewNowCta)))}
    <div class="rn-actions">
      <a href="/dashboard" class="rn-ghost-btn">
        <i class="fa-solid ${backArrow}"></i> ${esc(L(T.backToDashboard))}
      </a>
    </div>`;

    bindCard();
}

function renderError(msg) {
    cardEl.innerHTML = `
    <img class="rn-logo" src="./imgs/community-logo.png" alt="Ghawy" />
    <div class="rn-icon danger"><i class="fa-solid fa-triangle-exclamation"></i></div>
    <h1 class="rn-title" id="rnTitle">${esc(L(T.errTitle))}</h1>
    <p class="rn-sub">${esc(msg)}</p>
    <div class="rn-actions" style="margin-top:24px">
      <button type="button" class="rn-ghost-btn" id="rnRetryBtn">
        <i class="fa-solid fa-rotate-right"></i> ${esc(L(T.retry))}
      </button>
      <button type="button" class="rn-ghost-btn danger" id="rnLogoutBtn">
        <i class="fa-solid fa-right-from-bracket"></i> ${esc(L(T.logout))}
      </button>
    </div>`;

    const retry = document.getElementById('rnRetryBtn');
    if (retry) retry.addEventListener('click', () => window.location.reload());
    bindLogout();
}

/** تحديث الكروت + صندوق المعاينة بعد اختيار باقة (من غير إعادة بناء الصفحة) */
function refreshSelection() {
    document.querySelectorAll('.rn-plan').forEach(el => {
        const on = el.getAttribute('data-plan') === selectedPlan;
        el.classList.toggle('active', on);
        el.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    const box = document.getElementById('rnPreview');
    if (box) box.outerHTML = previewBoxHtml();
}

function bindLogout() {
    const btn = document.getElementById('rnLogoutBtn');
    if (btn) btn.addEventListener('click', logout);
}

function bindCard() {
    const plansWrap = document.getElementById('rnPlans');
    if (plansWrap) {
        plansWrap.addEventListener('click', e => {
            const card = e.target.closest('.rn-plan');
            if (!card) return;
            selectedPlan = card.getAttribute('data-plan');
            refreshSelection();
        });
    }
    const payBtn = document.getElementById('rnPayBtn');
    if (payBtn) payBtn.addEventListener('click', pay);
    const manualBtn = document.getElementById('rnManualBtn');
    if (manualBtn) manualBtn.addEventListener('click', () => { window.location.href = manualUrl('instapay'); });
    const vodafoneBtn = document.getElementById('rnVodafoneBtn');
    if (vodafoneBtn) vodafoneBtn.addEventListener('click', () => { window.location.href = manualUrl('vodafone'); });
    bindLogout();
}

// ─── الدفع (نفس منطق pay() في payment.js) ───────────────────
async function pay() {
    const btn = document.getElementById('rnPayBtn');
    if (!btn || btn.disabled) return;

    clearAlert();
    btn.disabled = true;
    btn.classList.add('loading');

    const plan = PLANS[selectedPlan];

    try {
        const res = await fetch(`${API}/payment/kashier/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${getToken()}`
            },
            // amount/currency مطلوبين في السكيما بس الباك إند بيتجاهلهم
            // وبيستخدم PLAN_PRICES server-side — plan_key هو اللي بيحدد السعر فعلاً.
            body: JSON.stringify({
                amount: plan.amount,
                currency: plan.currency,
                plan_key: selectedPlan
            })
        });

        let data = {};
        try { data = await res.json(); } catch (e) { }
        const url = data.payment_url || data.approval_url;

        if (res.ok && url) {
            showAlert(L(T.redirecting), 'success');
            setTimeout(() => { window.location.href = url; }, 700);
            return; // سيب الزرار مقفول — إحنا خارجين من الصفحة
        }

        if (res.status === 401) {
            showAlert(L(T.sessionExpired), 'error');
            setTimeout(goLogin, 1500);
            return;
        }

        showAlert(data.detail || L(T.payFailed), 'error');
    } catch (e) {
        showAlert(L(T.noConnection), 'error');
    }

    btn.disabled = false;
    btn.classList.remove('loading');
}

// ─── الإقلاع ────────────────────────────────────────────────
async function init() {
    if (!getToken()) {
        window.location.replace('/login');
        return;
    }

    const intent = new URLSearchParams(window.location.search).get('intent');

    let res;
    try {
        // الـ endpoint ده بيشتغل حتى والاشتراك منتهي (get_current_user مش active-member)
        res = await fetch(`${API}/profile/subscription-info?_t=${Date.now()}`, {
            headers: { 'Authorization': `Bearer ${getToken()}` }
        });
    } catch (e) {
        renderError(L(T.errNetwork));
        return;
    }

    // 401 = مش مسجّل دخول أصلاً / التوكن باطل → login (ودي الحالة الوحيدة
    // اللي بنمسح فيها الجلسة؛ المستخدم المنتهي بيفضل ماسك التوكن بتاعه).
    if (res.status === 401) {
        goLogin();
        return;
    }

    if (!res.ok) {
        renderError(L(T.errServer));
        return;
    }

    try {
        sub = await res.json();
    } catch (e) {
        renderError(L(T.errParse));
        return;
    }

    // ── وضع القفل: الاشتراك خلص ──
    if (!sub.is_active) {
        renderLocked();
        return;
    }

    // ── الاشتراك شغّال + جاي يجدّد بإرادته ──
    if (intent === 'renew') {
        renderRenew();
        return;
    }

    // ── الاشتراك شغّال من غير نيّة تجديد ──
    // يعني حارس قديم/كاش قديم رماه هنا وهو أصلاً مفعّل (أو لسه راجع من دفع ناجح).
    // نحدّث اليوزر المخزّن ونرجّعه للداشبورد — بلاش نحبسه.
    try {
        const meRes = await fetch(`${API}/profile/me?_t=${Date.now()}`, {
            headers: { 'Authorization': `Bearer ${getToken()}` }
        });
        if (meRes.ok) {
            const me = await meRes.json();
            localStorage.setItem('user', JSON.stringify(me));
            window.location.replace(me.onboarding_completed ? '/dashboard' : '/onboarding');
            return;
        }
        if (meRes.status === 401) {
            goLogin();
            return;
        }
    } catch (e) { /* شبكة — نكمّل تحت */ }

    // /profile/me فشل رغم إن الاشتراك شغّال (سباق نادر). منرجّعوش للداشبورد
    // عشان مايحصلش لوب — نعرضله واجهة التجديد وهو لسه معاه وصول.
    renderRenew();
}

// الصفحة بتتبني بالكامل في JS، فلازم تعيد رسم نفسها لما اللغة تتغيّر — زي
// باقي الأقسام المرسومة بـ JS في الموقع (pricing.js, catalog.js).
document.addEventListener('languagechange', () => {
    if (!sub || !cardEl) return;
    if (mode === 'renew') renderRenew();
    else renderLocked();
});

init();
