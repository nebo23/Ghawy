// لو عنده token بالفعل — شيك الأونبوردينج الأول
(async function checkExistingToken() {
  const t = getToken();
  if (!t) return;
  try {
    const profileRes = await fetch(`${API}/profile/me`, {
      headers: { 'Authorization': `Bearer ${t}` }
    });
    if (!profileRes.ok) {
      localStorage.removeItem('token');
      return;
    }
    const profile = await profileRes.json();
    if (!profile.is_active) {
      window.location.href = 'payment.html';
      return;
    }

    const res = await fetch(`${API}/profile/onboarding-status`, {
      headers: { 'Authorization': `Bearer ${t}` }
    });
    if (res.ok) {
      const data = await res.json();
      window.location.href = data.onboarding_completed ? 'dashboard.html' : 'onboarding.html';
    } else {
      // Token invalid
      localStorage.removeItem('token');
    }
  } catch(e) {
    localStorage.removeItem('token');
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
      showAlert('تم الدخول بنجاح! ✅ جاري تحويلك...', 'success');
      // Check onboarding status before redirect
      try {
        const profileRes = await fetch(`${API}/profile/me`, {
          headers: { 'Authorization': `Bearer ${data.access_token}` }
        });
        const profile = await profileRes.json();
        if (!profile.is_active) {
          setTimeout(() => { window.location.href = 'payment.html'; }, 1200);
          return;
        }

        const statusRes = await fetch(`${API}/profile/onboarding-status`, {
          headers: { 'Authorization': `Bearer ${data.access_token}` }
        });
        const statusData = await statusRes.json();
        const redirect = statusData.onboarding_completed ? 'dashboard.html' : 'onboarding.html';
        setTimeout(() => { window.location.href = redirect; }, 1200);
      } catch(e) {
        // Fallback if onboarding status fails but login succeeded
        setTimeout(() => { window.location.href = 'onboarding.html'; }, 1200);
      }
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

