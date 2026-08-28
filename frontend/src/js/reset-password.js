// reset-password.js — the three steps of /reset-password.
//
// Step 1 asks the server to mail a code, step 2 trades a correct code for a
// short-lived reset token, step 3 spends that token on a new password. The code
// is never held while the member is choosing a password, and the token is dead
// the moment it has been used once.
//
// The server answers step 1 with the same message whether or not the address is
// registered, so nothing here may branch on "user found" — showing a different
// message for a hit would hand back the account-enumeration the endpoint went
// out of its way to avoid.

const otpInputs = Array.from(document.querySelectorAll('.otp-input'));
const resendBtn = document.getElementById('resendBtn');
const resendTimer = document.getElementById('resendTimer');

let email = '';
let resetToken = '';
let countdown = 60;
let countdownInterval = null;

// Prefilled when the member came from a login attempt that already had their
// address typed in.
const params = new URLSearchParams(window.location.search);
const prefill = params.get('email') ? decodeURIComponent(params.get('email')) : '';
if (prefill) document.getElementById('email').value = prefill;

function showStep(id) {
  ['stepEmail', 'stepCode', 'stepPassword'].forEach(s => {
    const el = document.getElementById(s);
    if (el) el.style.display = (s === id) ? 'block' : 'none';
  });
}

function getCode() {
  return otpInputs.map(i => i.value).join('');
}

function setOtpHandlers() {
  otpInputs.forEach((input, idx) => {
    input.addEventListener('input', (e) => {
      e.target.value = e.target.value.replace(/\D/g, '');
      if (e.target.value && idx < otpInputs.length - 1) otpInputs[idx + 1].focus();
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace' && !input.value && idx > 0) otpInputs[idx - 1].focus();
    });
    input.addEventListener('paste', (e) => {
      e.preventDefault();
      const pasted = (e.clipboardData.getData('text') || '').replace(/\D/g, '').slice(0, 6);
      pasted.split('').forEach((digit, i) => { if (otpInputs[i]) otpInputs[i].value = digit; });
      otpInputs[Math.min(pasted.length, otpInputs.length - 1)].focus();
    });
  });
}

function startResendCountdown() {
  clearInterval(countdownInterval);
  countdown = 60;
  resendBtn.disabled = true;
  resendTimer.textContent = `إعادة الإرسال خلال ${countdown}ث`;
  countdownInterval = setInterval(() => {
    countdown -= 1;
    if (countdown <= 0) {
      clearInterval(countdownInterval);
      resendBtn.disabled = false;
      resendTimer.textContent = 'يمكنك إعادة إرسال الكود الآن';
      return;
    }
    resendTimer.textContent = `إعادة الإرسال خلال ${countdown}ث`;
  }, 1000);
}

// ── Step 1 ────────────────────────────────────────────────────────────────
async function sendResetCode() {
  const typed = (document.getElementById('email').value || '').trim();
  if (!typed || !typed.includes('@')) {
    showAlert('من فضلك اكتب إيميل صحيح', 'error');
    return;
  }

  setLoading('sendCodeBtn', true);
  try {
    const res = await fetch(`${API}/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: typed }),
    });
    const data = await res.json().catch(() => ({}));

    // A Google account is the one case the server answers differently, because
    // there is no password on it to reset and waiting for a code would never help.
    if (!res.ok) {
      showAlert(data.detail || 'حصل خطأ، حاول تاني', 'error');
      return;
    }

    email = typed;
    document.getElementById('emailHint').textContent = email;
    showAlert(data.message || 'لو الإيميل ده مسجّل عندنا، هيوصلك كود.', 'success');
    showStep('stepCode');
    startResendCountdown();
    otpInputs[0].focus();
  } catch {
    showAlert('مفيش اتصال بالـ server', 'error');
  } finally {
    setLoading('sendCodeBtn', false);
  }
}

async function resendResetCode() {
  if (!email || resendBtn.disabled) return;
  resendBtn.disabled = true;
  try {
    const res = await fetch(`${API}/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok) {
      showAlert(data.message || 'بعتنالك كود جديد 📩', 'success');
      startResendCountdown();
      otpInputs.forEach(i => { i.value = ''; });
      otpInputs[0].focus();
    } else {
      showAlert(data.detail || 'تعذر إعادة إرسال الكود', 'error');
      resendBtn.disabled = false;
    }
  } catch {
    showAlert('مفيش اتصال بالـ server', 'error');
    resendBtn.disabled = false;
  }
}

// ── Step 2 ────────────────────────────────────────────────────────────────
async function verifyResetCode() {
  const code = getCode();
  if (!/^\d{6}$/.test(code)) {
    showAlert('من فضلك ادخل كود مكوّن من 6 أرقام', 'error');
    return;
  }

  setLoading('verifyCodeBtn', true);
  try {
    const res = await fetch(`${API}/auth/verify-reset-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, code }),
    });
    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      showAlert(data.detail || 'الكود غير صحيح أو انتهت صلاحيته', 'error');
      otpInputs.forEach(i => { i.value = ''; });
      otpInputs[0].focus();
      return;
    }

    resetToken = data.reset_token;
    clearInterval(countdownInterval);
    // The code has done its job — clear the cells so it is not left sitting in
    // the DOM while the member types a password.
    otpInputs.forEach(i => { i.value = ''; });
    showAlert('', '');
    showStep('stepPassword');
    document.getElementById('password').focus();
  } catch {
    showAlert('مفيش اتصال بالـ server', 'error');
  } finally {
    setLoading('verifyCodeBtn', false);
  }
}

// ── Step 3 ────────────────────────────────────────────────────────────────
async function submitNewPassword() {
  const password = document.getElementById('password').value;
  const confirm = document.getElementById('passwordConfirm').value;

  if (!password || password.length < 6) {
    showAlert('كلمة المرور لازم تكون 6 حروف على الأقل', 'error');
    return;
  }
  if (password !== confirm) {
    showAlert('كلمتا المرور مش زي بعض', 'error');
    return;
  }

  setLoading('resetBtn', true);
  try {
    const res = await fetch(`${API}/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reset_token: resetToken, password }),
    });
    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      showAlert(data.detail || 'حصل خطأ، اطلب كود جديد', 'error');
      return;
    }

    // The reset bumped token_version, which killed every session this account
    // had — including this browser's. Carrying the stale token to /login gets it
    // bounced straight back out, so drop it here.
    localStorage.removeItem('token');
    localStorage.removeItem('user');

    showAlert(data.message || 'تم تغيير كلمة المرور. سجّل دخولك بكلمة المرور الجديدة.', 'success');
    setTimeout(() => { window.location.href = 'login.html'; }, 1500);
  } catch {
    showAlert('مفيش اتصال بالـ server', 'error');
  } finally {
    setLoading('resetBtn', false);
  }
}

setOtpHandlers();

document.addEventListener('keydown', (e) => {
  if (e.key !== 'Enter') return;
  if (document.getElementById('stepEmail').style.display !== 'none') sendResetCode();
  else if (document.getElementById('stepCode').style.display !== 'none') verifyResetCode();
  else submitNewPassword();
});
