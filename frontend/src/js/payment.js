// Verify the token
if (!getToken()) {
  localStorage.removeItem('user'); window.location.href = '/login';
} else {
  fetch(`${API}/profile/me`, {
    headers: { 'Authorization': `Bearer ${getToken()}` }
  })
    .then(res => { if (res.ok) return res.json(); })
    .then(user => {
      if (user && user.is_active) {
        localStorage.setItem('user', JSON.stringify(user));
        window.location.href = user.onboarding_completed ? 'dashboard.html' : 'onboarding.html';
      }
    })
    .catch(() => { });
}

// ─── Plans Configuration ─────────────────────────────────────
const PLANS = {
  monthly_egp: { amount: 600, currency: 'EGP', label: 'شهري', labelEn: 'Monthly', period: 'شهر', periodEn: 'Month', badge: null },
  quarterly_egp: { amount: 1200, currency: 'EGP', label: 'ربع سنوي', labelEn: 'Quarterly', period: '3 أشهر', periodEn: '3 Months', badge: 'وفّر 600 جنيه' },
  yearly_egp: { amount: 3500, currency: 'EGP', label: 'سنوي', labelEn: 'Annual', period: 'سنة', periodEn: 'Year', badge: 'وفّر 3700 جنيه' },
  monthly_usd: { amount: 20, currency: 'USD', label: 'Monthly', labelEn: 'Monthly', period: 'Month', periodEn: 'Month', badge: null },
  quarterly_usd: { amount: 35, currency: 'USD', label: 'Quarterly', labelEn: 'Quarterly', period: '3 Months', periodEn: '3 Months', badge: 'Save $10' },
  yearly_usd: { amount: 100, currency: 'USD', label: 'Annual', labelEn: 'Annual', period: 'Year', periodEn: 'Year', badge: 'Save $80' },
};

let selectedPlan = 'monthly_egp'; // default

// The language, read fresh from i18n.js on every use.
//
// This was `let currentLang = localStorage.getItem('ghawy_lang')`, and the
// name was the problem: i18n.js (loaded just before this file on
// payment.html) declares a global function `currentLang`, so a top-level
// `let` of the same name threw "Identifier 'currentLang' has already been
// declared" — a SyntaxError, which meant NONE of this file ever ran and the
// plan cards never rendered at all. Renamed, and turned into a function so it
// also picks up a language change instead of snapshotting at load.
const payLang = () => (typeof window.currentLang === 'function' ? window.currentLang() : 'ar');

// ─── Render All 3 Plans for the Region ──────────────────────
function renderPlans(region) {
  const container = document.getElementById('plans-container');
  const suffix = region === 'EGP' ? '_egp' : '_usd';
  const planKeys = ['monthly', 'quarterly', 'yearly'].map(c => c + suffix);

  // Set default to monthly
  selectedPlan = planKeys[0];

  container.innerHTML = planKeys.map((key, idx) => {
    const p = PLANS[key];
    const isActive = idx === 0;
    const label = payLang() === 'ar' ? p.label : p.labelEn;
    const period = payLang() === 'ar' ? p.period : p.periodEn;
    const symbol = p.currency === 'USD' ? '$' : '';
    const curr = p.currency === 'USD' ? 'USD' : 'EGP';
    const badge = p.badge ? `<div class="plan-badge">${p.badge}</div>` : '';
    const instaLabel = payLang() === 'ar' ? 'ادفع عبر انستاباي' : 'Pay via Instapay';

    return `
      <div class="plan-card${isActive ? ' active' : ''}" data-plan="${key}" onclick="selectPlan('${key}')">
        ${badge}
        <p class="plan-name">${label}</p>
        <div class="new-price">
          ${symbol}${p.amount.toLocaleString()}
          <span>${curr} / ${period}</span>
        </div>
        <button class="plan-instapay-btn" type="button" onclick="event.stopPropagation(); goManual('${key}')">
          <i data-lucide="wallet"></i>
          <span>${instaLabel}</span>
        </button>
      </div>`;
  }).join('');

  // Re-render lucide icons for the freshly injected buttons
  if (window.lucide) lucide.createIcons();
}

function selectPlan(key) {
  // Remove active from all, add to selected
  document.querySelectorAll('.plan-card').forEach(c => c.classList.remove('active'));
  const card = document.querySelector(`.plan-card[data-plan="${key}"]`);
  if (card) card.classList.add('active');
  selectedPlan = key;
}

// ─── Setup Payment UI ────────────────────────────────────────
// كل الاشتراكات بتتدفع بالجنيه المصري (Kashier بيسوّي كل حاجة بالمصري).
// اللي برا مصر بيدفع نفس السعر بالمصري — مفيش عرض بالدولار.
function setupPaymentUI() {
  renderPlans('EGP');
}

setupPaymentUI();

// ─── Pay Function ────────────────────────────────────────────
async function pay() {
  setLoading('payBtn', true);
  const plan = PLANS[selectedPlan];

  try {
    const res = await fetch(`${API}/payment/kashier/create`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}`
      },
      body: JSON.stringify({
        amount: plan.amount,
        currency: plan.currency,
        plan_key: selectedPlan
      })
    });

    const data = await res.json();
    const url = data.payment_url || data.approval_url;

    if (res.ok && url) {
      showAlert(payLang() === 'ar' ? 'جارٍ التحويل لصفحة الدفع... ✅' : 'Redirecting to payment... ✅', 'success');
      setTimeout(() => { window.location.href = url; }, 800);
    } else if (res.status === 401) {
      showAlert(payLang() === 'ar' ? 'انتهت الجلسة، سجّل دخولك مرة أخرى' : 'Session expired, please login again', 'error');
      setTimeout(() => { logout(); }, 1500);
    } else {
      showAlert(data.detail || (payLang() === 'ar' ? 'حدث خطأ، حاول مرة أخرى' : 'An error occurred, try again'), 'error');
    }
  } catch {
    showAlert(payLang() === 'ar' ? 'لا يوجد اتصال بالسيرفر' : 'No connection to server', 'error');
  } finally {
    setLoading('payBtn', false);
  }
}
