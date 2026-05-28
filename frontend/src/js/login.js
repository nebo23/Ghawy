// لو عنده token بالفعل — وجهه للصفحة المناسبة
(async function checkExistingToken() {
  // Fail-safe: extract token if it got caught in the redirect param (e.g. from cached dashboard.html)
  const urlParams = new URLSearchParams(window.location.search);
  const redirectParam = urlParams.get('redirect');
  if (redirectParam && redirectParam.includes('token=')) {
    try {
      const redirectSearch = redirectParam.split('?')[1];
      if (redirectSearch) {
        const nestedParams = new URLSearchParams(redirectSearch);
        const nestedToken = nestedParams.get('token');
        if (nestedToken) {
          localStorage.setItem('token', nestedToken);
          // Redirect to the clean page without the token in URL
          window.location.href = redirectParam.split('?')[0];
          return;
        }
      }
    } catch(e) {}
  }

  const t = getToken();
  if (!t) return;
  try {
    const profileRes = await fetch(`${API}/profile/me`, {
      headers: { 'Authorization': `Bearer ${t}` }
    });

    // Token فاسد أو منتهي
    if (profileRes.status === 401) {
      localStorage.removeItem('token');
      return;
    }

    // المستخدم مش active — وجهه للدفع
    if (profileRes.status === 403) {
      window.location.href = 'payment.html';
      return;
    }

    if (!profileRes.ok) return;

    const profile = await profileRes.json();
    if (!profile.is_active) {
      window.location.href = 'payment.html';
      return;
    }

    window.location.href = profile.onboarding_completed ? 'dashboard.html' : 'onboarding.html';
  } catch(e) {
    // Network error — stay on login page
  }
})();

async function login() {
  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;

  if (!email || !password) {
    showAlert('من فضلك اكمل كل الحقول', 'error');
    return;
  }

  setLoading('loginBtn', true);

  try {
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json();

    if (res.ok) {
      saveToken(data.access_token);

      // حفظ بيانات اليوزر في localStorage
      if (data.user) {
        localStorage.setItem('user', JSON.stringify(data.user));
      }

      showAlert('تم الدخول بنجاح! ✅ جاري تحويلك...', 'success');

      let redirect = 'onboarding.html';
      
      // أولاً: لو في رابط رجوع (redirect parameter) نستخدمه (بشرط ما يكونش تسجيل دخول أو رجوع غير آمن)
      const urlParams = new URLSearchParams(window.location.search);
      let redirectParam = urlParams.get('redirect');
      if (redirectParam && !redirectParam.includes('login') && redirectParam.startsWith('/')) {
        redirect = redirectParam.split('?')[0]; // نأخذ الرابط النظيف بدون توكنات
      } else {
        // ثانياً: لو مفيش، نحدد بناءً على حالة الحساب
        if (data.user) {
          if (!data.user.is_active) {
            redirect = 'payment.html';
          } else if (data.user.onboarding_completed) {
            redirect = 'dashboard.html';
          }
        }
      }

      setTimeout(() => { window.location.href = redirect; }, 1200);
    } else {
      showAlert(data.detail || 'إيميل أو باسورد غلط', 'error');
    }

  } catch {
    showAlert('مفيش اتصال بالـ server', 'error');
  } finally {
    setLoading('loginBtn', false);
  }
}

document.addEventListener('keydown', (e) => { if (e.key === 'Enter') login(); });
