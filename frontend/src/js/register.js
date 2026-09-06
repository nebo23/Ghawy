// Localised string helper — i18n.js exposes window.i18nT (Arabic by default).
function t(key, fallback) {
  return (typeof window.i18nT === 'function') ? window.i18nT(key, fallback) : (fallback || key);
}

let isPasswordStrong = false;
let isTermsAgreed = false;
let inviteToken = null;

// Password toggle
function togglePasswordVisibility() {
  const input = document.getElementById('password');
  const icon = document.getElementById('toggleIcon');
  if (input.type === 'password') {
    input.type = 'text';
    icon.classList.remove('fa-eye-slash');
    icon.classList.add('fa-eye');
  } else {
    input.type = 'password';
    icon.classList.remove('fa-eye');
    icon.classList.add('fa-eye-slash');
  }
}

// Password strength logic
document.getElementById('password').addEventListener('input', function (e) {
  const val = e.target.value;

  const hasLength = val.length >= 8;
  const hasUpperLower = /[a-z]/.test(val) && /[A-Z]/.test(val);
  const hasNumSpec = /[0-9]/.test(val) || /[^a-zA-Z0-9]/.test(val);

  // Update checks
  updateCheck('checkLength', hasLength);
  updateCheck('checkCase', hasUpperLower);
  updateCheck('checkNumber', hasNumSpec);

  let score = 0;
  if (hasLength) score++;
  if (hasUpperLower) score++;
  if (hasNumSpec) score++;

  const b1 = document.getElementById('bar1');
  const b2 = document.getElementById('bar2');
  const b3 = document.getElementById('bar3');
  const b4 = document.getElementById('bar4');
  const sText = document.getElementById('strengthText');

  // reset classes
  [b1, b2, b3, b4].forEach(b => b.className = 'strength-bar flex-1');

  if (val.length === 0) {
    sText.innerText = '';
    isPasswordStrong = false;
  } else if (score === 1) {
    b1.classList.add('active', 'weak');
    sText.innerText = t('strengthWeak');
    sText.className = 'text-[10px] font-medium w-12 text-end text-red-500';
    isPasswordStrong = false;
  } else if (score === 2) {
    b1.classList.add('active', 'medium');
    b2.classList.add('active', 'medium');
    sText.innerText = t('strengthMedium');
    sText.className = 'text-[10px] font-medium w-12 text-end text-yellow-500';
    isPasswordStrong = false;
  } else if (score === 3) {
    b1.classList.add('active', 'strong');
    b2.classList.add('active', 'strong');
    b3.classList.add('active', 'strong');

    // Extra bar if very long and strong
    if (val.length >= 12) {
      b4.classList.add('active', 'strong');
    }

    sText.innerText = t('strengthStrong');
    sText.className = 'text-[10px] font-medium w-12 text-end text-brand';
    isPasswordStrong = true;
  }

  updateSubmitButton();
});

const termsEl = document.getElementById('terms');
if (termsEl) {
  termsEl.addEventListener('change', function (e) {
    isTermsAgreed = e.target.checked;
    updateSubmitButton();
  });
}

function updateSubmitButton() {
  const submitBtn = document.getElementById('submitRegBtn');
  if (submitBtn) {
    submitBtn.disabled = !(isPasswordStrong && isTermsAgreed);
  }
}

function updateCheck(id, isValid) {
  const el = document.getElementById(id);
  const icon = el.querySelector('i');
  if (isValid) {
    el.classList.add('valid');
    icon.classList.remove('fa-regular', 'fa-circle-check');
    icon.classList.add('fa-solid', 'fa-circle-check');
  } else {
    el.classList.remove('valid');
    icon.classList.add('fa-regular', 'fa-circle-check');
    icon.classList.remove('fa-solid');
  }
}

// IP Geolocation — fills the two hidden fields this form submits.
//
// It used to also write a dial code and a flag emoji into #dialCode and
// #countryFlag. This page has no phone field and neither element exists, so
// both writes threw: once in the `try`, and then again in the `catch` on the
// very same element — which meant the catch died before its own defaults on
// the lines below it. Whenever ipapi was blocked or rate-limited, that is a
// registration submitted with country and governorate empty, and 344 of 1945
// member rows carry exactly that. The dial code itself was dead too: nothing
// ever read the variable it was assigned to.
//
// So this writes the two fields that exist, and both paths leave a value.
async function getGeoLocation() {
  const countryInput = document.getElementById('country');
  const govInput = document.getElementById('governorate');

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);
    const res = await fetch('https://ipapi.co/json/', { signal: controller.signal });
    clearTimeout(timeoutId);
    const data = await res.json();

    // ipapi answers a rate limit with HTTP 429 and CORS headers, so fetch
    // resolves and this parses — the body carries error:true. Verified live.
    if (data.error) throw new Error('ipapi unavailable');

    countryInput.value = data.country_name || 'Egypt';
    govInput.value = data.region || data.city || 'Unknown';
  } catch (err) {
    // The same defaults the Google signup path applies server-side
    // (google_auth.py) when its own lookup fails. Never blank.
    countryInput.value = 'Egypt';
    govInput.value = 'Unknown';
  }
}

async function initInviteFlow() {
  const urlParams = new URLSearchParams(window.location.search);
  inviteToken = urlParams.get('token');

  // The Google callback bounces fake/disposable signups back here.
  if (urlParams.get('error') === 'fake_email') {
    showFormMessage(t('errFakeEmail'), 'error');
  }

  if (!inviteToken) {
    getGeoLocation();
    return; // Normal flow
  }

  // Invite flow
  try {
    const apiBase = (typeof API !== 'undefined') ? API : '/api';
    const res = await fetch(`${apiBase}/auth/invite/${inviteToken}`);
    const data = await res.json();

    if (!res.ok) {
      showFormMessage(data.detail || t('inviteInvalid'), 'error');
      // Disable form
      document.getElementById('registerForm').style.pointerEvents = 'none';
      document.getElementById('registerForm').style.opacity = '0.5';
      return;
    }

    // Prefill data — the invite carries a single full_name, so split it across
    // the first/last inputs on the first space.
    const firstInput = document.getElementById('firstName');
    const lastInput = document.getElementById('lastName');
    const emailInput = document.getElementById('email');

    const parts = splitFullName(data.full_name);
    firstInput.value = parts.first;
    lastInput.value = parts.last;
    emailInput.value = data.email;

    // HIDE name and phone, KEEP email visible but disabled
    const nameSection = document.getElementById('name-section');
    if (nameSection) nameSection.style.display = 'none';
    
    emailInput.disabled = true;
    emailInput.style.opacity = '0.6';
    emailInput.style.cursor = 'not-allowed';
    // Remove the icon for email if it exists so it doesn't look like an editable field
    const emailIcon = emailInput.nextElementSibling;
    if (emailIcon && emailIcon.tagName === 'I') {
       emailIcon.style.display = 'none';
    }
    const phoneSection = document.getElementById('phone-section');
    if (phoneSection) phoneSection.style.display = 'none';
    document.getElementById('social-divider').style.display = 'none';
    document.getElementById('google-btn').style.display = 'none';
    document.getElementById('login-footer').style.display = 'none';
    
    // UI Changes
    document.getElementById('default-header').style.display = 'none';
    document.getElementById('invite-header').style.display = 'none';
    
    // Show welcome message above password field
    const welcomeEl = document.createElement('div');
    welcomeEl.className = 'invite-welcome';
    welcomeEl.innerHTML = `
      <div style="text-align:center; margin-bottom:24px;">
        <div style="font-size:32px; margin-bottom:8px;">🎉</div>
        <h2 style="color:#fff; margin:0 0 4px;">${t('welcomeName')} ${window.escapeHtml(data.full_name)}!</h2>
        <p style="color:#888; margin:0;">${t('inviteWelcomeSub')}</p>
      </div>
    `;
    document.getElementById('registerForm').prepend(welcomeEl);
    
    document.getElementById('password-label').innerText = t('password');
    const submitSpan = document.getElementById('submitRegBtn').querySelector('span');
    submitSpan.removeAttribute('data-i18n');       // stop applyLanguage overwriting the invite label
    submitSpan.removeAttribute('data-i18n-html');
    submitSpan.innerHTML = t('completeRegistration') + ' &rarr;';

  } catch (err) {
    showFormMessage(t('inviteFailed'), 'error');
  }
}

window.onload = initInviteFlow;

function showFormMessage(msg, type) {
  const alertEl = document.getElementById('formAlert');
  alertEl.innerText = msg;
  alertEl.classList.remove('hidden', 'bg-red-900/50', 'text-red-400', 'border-red-800', 'bg-green-900/50', 'text-green-400', 'border-green-800');
  alertEl.classList.add('border');

  if (type === 'error') {
    alertEl.classList.add('bg-red-900/50', 'text-red-400', 'border-red-800');
  } else {
    alertEl.classList.add('bg-green-900/50', 'text-green-400', 'border-green-800');
  }
}

async function submitRegister() {
  if (!isPasswordStrong) {
    showFormMessage(t('errWeakPassword'), 'error');
    return;
  }
  if (!isTermsAgreed) {
    showFormMessage(t('errTermsRequired'), 'error');
    return;
  }

  const firstName = document.getElementById('firstName').value.trim();
  const lastName = document.getElementById('lastName').value.trim();
  // Both names are required. The invite flow hides them and posts to a
  // different endpoint, so it is exempt.
  if (!inviteToken && (firstName.length < 2 || lastName.length < 2)) {
    showFormMessage(t('errNameRequired'), 'error');
    return;
  }
  // الاسم بالعربي. القاعدة الحقيقية على السيرفر — دي عشان العضو يعرف دلوقتي
  // بدل ما يستنى رد، وهي نفس القاعدة بالحرف (src/js/arabic-name.js).
  //
  // لو الملف مش محمّل لأي سبب (كاش قديم مثلاً) بنعدّي: السيرفر هو اللي بيرفض،
  // والواجهة عمرها ما تبقى هي اللي واقفة قدام حد يسجّل.
  if (!inviteToken && typeof window.isArabicName === 'function'
      && !(window.isArabicName(firstName) && window.isArabicName(lastName))) {
    showFormMessage(t('errArabicName'), 'error');
    return;
  }
  const email = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value;
  const country = document.getElementById('country').value.trim();
  const governorate = document.getElementById('governorate').value.trim();

  const btn = document.getElementById('submitRegBtn');
  const spinner = document.getElementById('spinner');
  const btnText = btn.querySelector('span');

  btn.disabled = true;
  spinner.classList.remove('hidden');
  btnText.classList.add('opacity-0');

  try {
    // API is assumed to be defined globally from utils.js
    const apiBase = (typeof API !== 'undefined') ? API : '/api';

    if (inviteToken) {
      // Invite flow submit
      const res = await fetch(`${apiBase}/auth/register-with-invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: inviteToken,
          password: password
        })
      });

      const data = await res.json();

      if (res.ok) {
        showFormMessage(t('okSetupComplete'), 'success');
        // Save token and go straight to onboarding
        if (data.access_token) {
          localStorage.setItem('token', data.access_token);
          if (data.user) {
            localStorage.setItem('user', JSON.stringify(data.user));
          }
          setTimeout(() => { window.location.href = '/onboarding.html'; }, 1200);
        } else {
          setTimeout(() => { localStorage.removeItem('user'); window.location.href = '/login'; }, 1200);
        }
      } else {
        showFormMessage(data.detail || t('errGeneric'), 'error');
        btn.disabled = false;
      }
    } else {
      // Normal flow submit — require the "I'm not a robot" check to be solved.
      const captchaToken = (window.turnstile && typeof turnstile.getResponse === 'function')
        ? (turnstile.getResponse() || '')
        : (document.querySelector('[name="cf-turnstile-response"]')?.value || '');
      const captchaPresent = !!document.querySelector('.cf-turnstile');
      if (captchaPresent && !captchaToken) {
        showFormMessage(t('errCaptcha'), 'error');
        btn.disabled = false;
        spinner.classList.add('hidden');
        btnText.classList.remove('opacity-0');
        return;
      }

      const res = await fetch(`${apiBase}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          email,
          password,
          country,
          governorate,
          turnstile_token: captchaToken
        })
      });

      const data = await res.json();

      if (res.ok) {
        showFormMessage(t('okAccountCreated'), 'success');
        const nextUrl = `verify-email.html?email=${encodeURIComponent(email)}`;
        setTimeout(() => { window.location.href = nextUrl; }, 1200);
      } else {
        showFormMessage(data.detail || t('errGeneric'), 'error');
        btn.disabled = false;
        // Turnstile tokens are single-use — reset so the user can retry.
        if (window.turnstile && typeof turnstile.reset === 'function') turnstile.reset();
      }
    }

  } catch (e) {
    showFormMessage(t('errNoConnection'), 'error');
    btn.disabled = false;
    if (window.turnstile && typeof turnstile.reset === 'function') turnstile.reset();
  } finally {
    spinner.classList.add('hidden');
    btnText.classList.remove('opacity-0');
  }
}

// Turnstile widget callbacks (referenced from register.html). The real gating
// happens at submit time; these just clear any stale error message.
function onTurnstileSuccess() {
  const alertBox = document.getElementById('formAlert');
  if (alertBox && alertBox.textContent.includes('robot')) alertBox.classList.add('hidden');
}
function onTurnstileExpired() { /* token auto-cleared by the widget; submit will re-prompt */ }

/** Split a display name on the first space: "محمد أحمد علي" -> { first: 'محمد', last: 'أحمد علي' } */
function splitFullName(name) {
  const clean = (name || '').trim().replace(/\s+/g, ' ');
  const idx = clean.indexOf(' ');
  if (idx === -1) return { first: clean, last: '' };
  return { first: clean.slice(0, idx), last: clean.slice(idx + 1) };
}

// The strength label is written by JS — re-render it when the language flips.
document.addEventListener('languagechange', () => {
  const pwd = document.getElementById('password');
  if (pwd && pwd.value) pwd.dispatchEvent(new Event('input'));
});

function googleSignIn() {
  // Trigger google sign in flow
  const apiBase = (typeof API !== 'undefined') ? API : '/api';
  window.location.href = `${apiBase}/auth/google/login`;
}

