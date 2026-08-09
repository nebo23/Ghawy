const params = new URLSearchParams(window.location.search);
const email = params.get('email') ? decodeURIComponent(params.get('email')) : '';
const emailHint = document.getElementById('emailHint');
const otpInputs = Array.from(document.querySelectorAll('.otp-input'));
const resendBtn = document.getElementById('resendBtn');
const resendTimer = document.getElementById('resendTimer');

let countdown = 60;
let countdownInterval = null;

if (!email) {
  showAlert('لا يوجد بريد إلكتروني. ارجع لصفحة التسجيل أولًا.', 'error');
} else {
  emailHint.textContent = email;
}

function getVerificationCode() {
  return otpInputs.map((input) => input.value).join('');
}

function setOtpHandlers() {
  otpInputs.forEach((input, idx) => {
    input.addEventListener('input', (e) => {
      const value = e.target.value.replace(/\D/g, '');
      e.target.value = value;
      if (value && idx < otpInputs.length - 1) otpInputs[idx + 1].focus();
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace' && !input.value && idx > 0) {
        otpInputs[idx - 1].focus();
      }
    });

    input.addEventListener('paste', (e) => {
      e.preventDefault();
      const pasted = (e.clipboardData.getData('text') || '').replace(/\D/g, '').slice(0, 6);
      pasted.split('').forEach((digit, i) => {
        if (otpInputs[i]) otpInputs[i].value = digit;
      });
      const nextIndex = Math.min(pasted.length, otpInputs.length - 1);
      otpInputs[nextIndex].focus();
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

async function verifyEmail() {
  if (!email) return;
  const verification_code = getVerificationCode();

  if (!/^\d{6}$/.test(verification_code)) {
    showAlert('من فضلك ادخل كود مكوّن من 6 أرقام', 'error');
    return;
  }

  setLoading('verifyBtn', true);
  try {
    const res = await fetch(`${API}/auth/verify-email`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, verification_code }),
    });
    const data = await res.json();

    if (res.ok) {
      showAlert('تم تأكيد بريدك بنجاح جاري تحويلك...', 'success');
      // Auto-login: save token from verification response
      if (data.access_token) {
        saveToken(data.access_token);
      }
      // Verified and now logged in, but not subscribed — the plans page is
      // the next step. /pricing replaced /payment as the one page that holds
      // the plans and the checkout.
      setTimeout(() => { window.location.href = '/pricing'; }, 1200);
    } else {
      showAlert(data.detail || 'فشل التحقق من الكود', 'error');
    }
  } catch {
    showAlert('مفيش اتصال بالـ server', 'error');
  } finally {
    setLoading('verifyBtn', false);
  }
}

async function resendCode() {
  if (!email || resendBtn.disabled) return;
  resendBtn.disabled = true;

  try {
    const res = await fetch(`${API}/auth/resend-verification-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();

    if (res.ok) {
      showAlert('تم إرسال كود جديد لبريدك 📩', 'success');
      startResendCountdown();
    } else {
      showAlert(data.detail || 'تعذر إعادة إرسال الكود', 'error');
      resendBtn.disabled = false;
    }
  } catch {
    showAlert('مفيش اتصال بالـ server', 'error');
    resendBtn.disabled = false;
  }
}

setOtpHandlers();
startResendCountdown();
otpInputs[0].focus();

document.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') verifyEmail();
});

