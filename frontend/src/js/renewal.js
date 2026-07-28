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

// نفس باقات payment.js — المنصة بتعرض EGP بس.
// الأسعار هنا للعرض فقط؛ المصدر الرسمي هو PLAN_PRICES في backend/app/routers/payment.py.
// و`days` مطابقة لـ plan_duration() في backend/app/services/payment_service.py.
const PLANS = {
    monthly_egp: { amount: 600, currency: 'EGP', label: 'شهري', period: 'شهر', days: 30, badge: null },
    quarterly_egp: { amount: 1200, currency: 'EGP', label: 'ربع سنوي', period: '3 شهور', days: 90, badge: 'وفّر 600 جنيه' },
    yearly_egp: { amount: 4000, currency: 'EGP', label: 'سنوي', period: 'سنة', days: 365, badge: 'وفّر 3200 جنيه' },
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

/** تاريخ عربي واضح بأرقام لاتينية (عشان يبقى متسق مع باقي الأرقام في الصفحة) */
function fmtDate(d) {
    if (!d) return '—';
    const opts = { timeZone: 'Africa/Cairo', day: 'numeric', month: 'long', year: 'numeric' };
    try {
        return d.toLocaleDateString('ar-EG-u-nu-latn', opts);
    } catch (e) {
        try { return d.toLocaleDateString('ar-EG', opts); } catch (e2) { return d.toISOString().slice(0, 10); }
    }
}

function daysWord(n) {
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
        const badge = p.badge ? `<span class="rn-plan-badge">${esc(p.badge)}</span>` : '';
        // في وضع التجديد بنقول "المجموع" بس لما يكون فيه أيام باقية فعلاً تتضاف عليها
        const note = mode !== 'renew'
            ? `اشتراكك هيشتغل لحد ${fmtDate(pv.newEnd)}`
            : (pv.stillRunning
                ? `المجموع <b>${daysWord(pv.totalDays)}</b> · لحد ${fmtDate(pv.newEnd)}`
                : `<b>${daysWord(pv.addedDays)}</b> · لحد ${fmtDate(pv.newEnd)}`);

        return `
      <button type="button" class="rn-plan${active ? ' active' : ''}" data-plan="${key}"
              aria-pressed="${active ? 'true' : 'false'}">
        ${badge}
        <div class="rn-plan-name">${esc(p.label)}</div>
        <div class="rn-plan-price">${p.amount.toLocaleString('en-US')}<span>جنيه / ${esc(p.period)}</span></div>
        <div class="rn-plan-note">${note}</div>
      </button>`;
    }).join('');
}

function previewBoxHtml() {
    const pv = previewFor(selectedPlan);
    if (mode === 'renew') {
        const head = pv.stillRunning
            ? `لو جدّدت دلوقتي هيبقى معاك مجموع <b>${daysWord(pv.totalDays)}</b>`
            : `لو جدّدت دلوقتي هيبقى معاك <b>${daysWord(pv.addedDays)}</b>`;
        return `<div class="rn-preview" id="rnPreview">
      <i class="fa-solid fa-circle-info"></i>
      ${head} — واشتراكك هيخلص يوم <b>${fmtDate(pv.newEnd)}</b>.
    </div>`;
    }
    return `<div class="rn-preview" id="rnPreview">
    <i class="fa-solid fa-circle-info"></i>
    لو دفعت دلوقتي هيترجعلك الوصول فورًا لمدة <b>${daysWord(pv.addedDays)}</b> — لحد يوم <b>${fmtDate(pv.newEnd)}</b>.
  </div>`;
}

function payButtonHtml(label) {
    return `<button type="button" class="rn-pay" id="rnPayBtn">
    <span class="rn-spinner"></span>
    <span class="rn-pay-text">${label}</span>
  </button>
  <div class="rn-secure"><i class="fa-solid fa-lock"></i> الدفع آمن 100% عبر Kashier</div>`;
}

function renderLocked() {
    mode = 'locked';
    const end = parseUtc(sub && sub.subscription_end);
    const endLine = end
        ? `<div class="rn-status"><div class="rn-stat">
         <div class="rn-stat-label">اشتراكك انتهى يوم</div>
         <div class="rn-stat-value">${fmtDate(end)}</div>
       </div></div>`
        : '';

    cardEl.innerHTML = `
    <img class="rn-logo" src="./imgs/community-logo.png" alt="Ghawy" />
    <div class="rn-icon danger"><i class="fa-solid fa-lock"></i></div>
    <h1 class="rn-title" id="rnTitle">اشتراكك خلص — جدّد دلوقتي وكمّل من غير ما تخرج</h1>
    <p class="rn-sub">حسابك ومحتواك ومحادثاتك كلها مستنياك زي ما هي. اختار باقتك، ادفع في دقيقة،
       وهترجع للداشبورد على طول.</p>
    ${endLine}
    <div class="rn-plans" id="rnPlans">${plansHtml()}</div>
    ${previewBoxHtml()}
    <div class="rn-alert" id="rnAlert"></div>
    ${payButtonHtml('جدّد اشتراكك 🚀')}
    <div class="rn-actions">
      <button type="button" class="rn-ghost-btn danger" id="rnLogoutBtn">
        <i class="fa-solid fa-right-from-bracket"></i> تسجيل الخروج
      </button>
    </div>`;

    bindCard();
}

function renderRenew() {
    mode = 'renew';
    const end = parseUtc(sub && sub.subscription_end);
    const remaining = typeof sub.days_remaining === 'number' ? sub.days_remaining : null;

    const remainingValue = remaining === null
        ? '<span style="font-size:1.1rem">من غير تاريخ انتهاء</span>'
        : (remaining === 0 ? 'أقل من يوم' : `${remaining} <small>يوم</small>`);

    const planLine = sub.is_free
        ? 'عضوية مجانية'
        : (sub.plan_label ? esc(sub.plan_label) : '—');

    cardEl.innerHTML = `
    <img class="rn-logo" src="./imgs/community-logo.png" alt="Ghawy" />
    <div class="rn-icon"><i class="fa-solid fa-rotate"></i></div>
    <h1 class="rn-title" id="rnTitle">تجديد الاشتراك</h1>
    <p class="rn-sub">اشتراكك لسه شغّال — أي تجديد دلوقتي بيتضاف <b>فوق</b> الأيام الباقية،
       مش بيلغيها.</p>

    <div class="rn-status">
      <div class="rn-stat">
        <div class="rn-stat-label">باقي معاك</div>
        <div class="rn-stat-value big">${remainingValue}</div>
      </div>
      <div class="rn-stat">
        <div class="rn-stat-label">اشتراكك بيخلص يوم</div>
        <div class="rn-stat-value">${end ? fmtDate(end) : 'مفتوح'}</div>
      </div>
      <div class="rn-stat">
        <div class="rn-stat-label">باقتك الحالية</div>
        <div class="rn-stat-value">${planLine}</div>
      </div>
    </div>

    <div class="rn-plans" id="rnPlans">${plansHtml()}</div>
    ${previewBoxHtml()}
    <div class="rn-alert" id="rnAlert"></div>
    ${payButtonHtml('جدّد دلوقتي 🚀')}
    <div class="rn-actions">
      <a href="/dashboard" class="rn-ghost-btn">
        <i class="fa-solid fa-arrow-right"></i> ارجع للداشبورد
      </a>
    </div>`;

    bindCard();
}

function renderError(msg) {
    cardEl.innerHTML = `
    <img class="rn-logo" src="./imgs/community-logo.png" alt="Ghawy" />
    <div class="rn-icon danger"><i class="fa-solid fa-triangle-exclamation"></i></div>
    <h1 class="rn-title" id="rnTitle">مش قادرين نجيب تفاصيل اشتراكك</h1>
    <p class="rn-sub">${esc(msg)}</p>
    <div class="rn-actions" style="margin-top:24px">
      <button type="button" class="rn-ghost-btn" id="rnRetryBtn">
        <i class="fa-solid fa-rotate-right"></i> حاول تاني
      </button>
      <button type="button" class="rn-ghost-btn danger" id="rnLogoutBtn">
        <i class="fa-solid fa-right-from-bracket"></i> تسجيل الخروج
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
            showAlert('جارٍ التحويل لصفحة الدفع... ✅', 'success');
            setTimeout(() => { window.location.href = url; }, 700);
            return; // سيب الزرار مقفول — إحنا خارجين من الصفحة
        }

        if (res.status === 401) {
            showAlert('انتهت الجلسة، سجّل دخولك تاني', 'error');
            setTimeout(goLogin, 1500);
            return;
        }

        showAlert(data.detail || 'حصل خطأ وإحنا بنجهّز الدفع، حاول تاني', 'error');
    } catch (e) {
        showAlert('مفيش اتصال بالسيرفر — اتأكد من النت وحاول تاني', 'error');
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
        renderError('مشكلة في الاتصال بالسيرفر. جرّب تاني بعد شوية.');
        return;
    }

    // 401 = مش مسجّل دخول أصلاً / التوكن باطل → login (ودي الحالة الوحيدة
    // اللي بنمسح فيها الجلسة؛ المستخدم المنتهي بيفضل ماسك التوكن بتاعه).
    if (res.status === 401) {
        goLogin();
        return;
    }

    if (!res.ok) {
        renderError('السيرفر رجّعلنا خطأ غير متوقع. جرّب تاني، ولو فضلت المشكلة كلّم الدعم.');
        return;
    }

    try {
        sub = await res.json();
    } catch (e) {
        renderError('رد السيرفر مش مفهوم. جرّب تاني.');
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

init();
