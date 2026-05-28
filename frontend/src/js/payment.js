// تحقق من الـ token
if (!getToken()) window.location.href = 'login.html';

// ─── Plans Configuration ────────────────────────────────────
const PLANS = {
  monthly_egp: { amount: 500, currency: 'EGP', label: 'اشتراك شهري', period: 'شهر', badge: null },
  yearly_egp: { amount: 3000, currency: 'EGP', label: 'اشتراك سنوي', period: 'سنة', badge: 'وفر 2000 جنيه ' },
  monthly_usd: { amount: 15, currency: 'USD', label: 'Monthly Plan', period: 'Month', badge: null },
  yearly_usd: { amount: 100, currency: 'USD', label: 'Yearly Plan', period: 'Year', badge: 'Save $80 ' },
};

let selectedPlan = 'monthly_egp'; // default

// ─── Detect User Region via IP ──────────────────────────────
async function detectUserRegion() {
  try {
    const res = await fetch('https://ipapi.co/json/');
    const data = await res.json();
    return data.country_code === 'EG' ? 'EGP' : 'USD';
  } catch {
    return 'EGP'; // fallback لو فشل
  }
}

// ─── Render Single Plan Card ────────────────────────────────
function renderSinglePlan(planKey) {
  const container = document.getElementById('plans-container');
  const plan = PLANS[planKey];
  if (!plan) return;

  selectedPlan = planKey;

  container.innerHTML = '';

  const card = document.createElement('div');
  card.className = 'plan-card active single';
  card.dataset.plan = planKey;

  card.innerHTML = `
    ${plan.badge ? `<div class="plan-badge">${plan.badge}</div>` : ''}
    <p class="plan-name">${plan.label}</p>
    <div class="new-price">
      ${plan.currency === 'USD' ? '$' : ''}${plan.amount.toLocaleString()}
      <span>${plan.currency === 'EGP' ? 'جنيه' : 'USD'} / ${plan.period}</span>
    </div>
  `;

  container.appendChild(card);
}

// ─── Setup Payment UI ───────────────────────────────────────
async function setupPaymentUI() {
  // Show skeleton loading while detecting region
  const container = document.getElementById('plans-container');
  container.innerHTML = `<div class="plan-card skeleton-card"></div>`;

  // Read plan cycle from URL (?plan=monthly or ?plan=yearly)
  const urlParams = new URLSearchParams(window.location.search);
  const cycle = urlParams.get('plan') || 'monthly'; // default monthly

  // Detect region
  const region = await detectUserRegion();

  // Determine the exact plan key
  const suffix = region === 'EGP' ? '_egp' : '_usd';
  const planKey = cycle + suffix; // e.g. "monthly_egp" or "yearly_usd"

  // Render single plan
  renderSinglePlan(planKey);
}

setupPaymentUI();

// ─── Pay Function ───────────────────────────────────────────
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
      showAlert('جاري تحويلك لصفحة الدفع... ✅', 'success');
      setTimeout(() => { window.location.href = url; }, 800);
    } else if (res.status === 401) {
      showAlert('انتهت جلستك، سجّل دخولك مجدداً', 'error');
      setTimeout(() => { logout(); }, 1500);
    } else {
      showAlert(data.detail || 'حصل خطأ، حاول تاني', 'error');
    }

  } catch {
    showAlert('مفيش اتصال بالـ server', 'error');
  } finally {
    setLoading('payBtn', false);
  }
}
