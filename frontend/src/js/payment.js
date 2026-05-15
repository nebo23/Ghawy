// تحقق من الـ token
if (!getToken()) window.location.href = 'login.html';

let AMOUNT = 200;
let CURRENCY = 'EGP';
let ENDPOINT = '/payment/kashier/create';

async function setupPaymentUI() {
  const userCurrency = await initCurrency();

  if (userCurrency === 'USD') {
    AMOUNT = 60;
    CURRENCY = 'USD';
    ENDPOINT = '/payment/paypal/create';

    const oldPrice = document.querySelector('.old-price');
    const newPrice = document.querySelector('.new-price');
    const usdPrice = document.querySelector('.usd-price');
    const secureNote = document.querySelector('.secure-note');

    if (oldPrice) oldPrice.innerText = '80 $';
    if (newPrice) newPrice.innerHTML = '60 <span>$ / Month</span>';
    if (usdPrice) usdPrice.style.display = 'none';
    if (secureNote) secureNote.innerHTML = '🔒 الدفع آمن 100% عبر PayPal';
  } else {
    AMOUNT = 10;
    CURRENCY = 'EGP';
    ENDPOINT = '/payment/kashier/create';

    const oldPrice = document.querySelector('.old-price');
    const newPrice = document.querySelector('.new-price');
    const usdPrice = document.querySelector('.usd-price');
    const secureNote = document.querySelector('.secure-note');

    if (oldPrice) oldPrice.innerText = '3,999 جنيه';
    if (newPrice) newPrice.innerHTML = '10 <span>جنيه / شهر</span>';
    if (usdPrice) usdPrice.style.display = 'block';
    if (secureNote) secureNote.innerHTML = '🔒 الدفع آمن 100% عبر Kashier';
  }
}

setupPaymentUI();

async function pay() {
  setLoading('payBtn', true);

  try {
    const res = await fetch(`${API}${ENDPOINT}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}`
      },
      body: JSON.stringify({ amount: AMOUNT, currency: CURRENCY })
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

