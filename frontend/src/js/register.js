let isPasswordStrong = false;
let isTermsAgreed = false;
let dialCodeValue = '';
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
    sText.innerText = 'Weak';
    sText.className = 'text-[10px] font-medium w-12 text-right text-red-500';
    isPasswordStrong = false;
  } else if (score === 2) {
    b1.classList.add('active', 'medium');
    b2.classList.add('active', 'medium');
    sText.innerText = 'Medium';
    sText.className = 'text-[10px] font-medium w-12 text-right text-yellow-500';
    isPasswordStrong = false;
  } else if (score === 3) {
    b1.classList.add('active', 'strong');
    b2.classList.add('active', 'strong');
    b3.classList.add('active', 'strong');

    // Extra bar if very long and strong
    if (val.length >= 12) {
      b4.classList.add('active', 'strong');
    }

    sText.innerText = 'Strong';
    sText.className = 'text-[10px] font-medium w-12 text-right text-brand';
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

// IP Geolocation
async function getGeoLocation() {
  const countryInput = document.getElementById('country');
  const govInput = document.getElementById('governorate');
  const dialCodeSpan = document.getElementById('dialCode');
  const flagSpan = document.getElementById('countryFlag');

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);
    const res = await fetch('https://ipapi.co/json/', { signal: controller.signal });
    clearTimeout(timeoutId);
    const data = await res.json();

    if (data.error) throw new Error();

    countryInput.value = data.country_name || '';
    govInput.value = data.region || data.city || 'Unknown';
    dialCodeValue = data.country_calling_code || '';
    dialCodeSpan.innerText = dialCodeValue;

    // Set flag emoji
    if (data.country_code) {
      flagSpan.innerText = data.country_code.toUpperCase().replace(/./g, char => String.fromCodePoint(char.charCodeAt(0) + 127397));
    }
  } catch (err) {
    // defaults
    dialCodeSpan.innerText = '+20';
    flagSpan.innerText = '🇪🇬';
    dialCodeValue = '+20';
    countryInput.value = 'Egypt';
    govInput.value = 'Unknown';
  }
}

async function initInviteFlow() {
  const urlParams = new URLSearchParams(window.location.search);
  inviteToken = urlParams.get('token');

  if (!inviteToken) {
    getGeoLocation();
    return; // Normal flow
  }

  // Invite flow
  try {
    const apiBase = (typeof API !== 'undefined') ? API : 'http://127.0.0.1:8000';
    const res = await fetch(`${apiBase}/auth/invite/${inviteToken}`);
    const data = await res.json();

    if (!res.ok) {
      showFormMessage(data.detail || 'Invalid or expired invite link', 'error');
      // Disable form
      document.getElementById('registerForm').style.pointerEvents = 'none';
      document.getElementById('registerForm').style.opacity = '0.5';
      return;
    }

    // Prefill data
    const nameInput = document.getElementById('fullName');
    const emailInput = document.getElementById('email');
    
    nameInput.value = data.full_name;
    emailInput.value = data.email;
    
    // HIDE name and phone, KEEP email visible but disabled
    if (nameInput.closest('.mb-4')) nameInput.closest('.mb-4').style.display = 'none';
    
    emailInput.disabled = true;
    emailInput.style.opacity = '0.6';
    emailInput.style.cursor = 'not-allowed';
    // Remove the icon for email if it exists so it doesn't look like an editable field
    const emailIcon = emailInput.nextElementSibling;
    if (emailIcon && emailIcon.tagName === 'I') {
       emailIcon.style.display = 'none';
    }
    document.getElementById('phone-section').style.display = 'none';
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
        <h2 style="color:#fff; margin:0 0 4px;">أهلاً ${data.full_name}!</h2>
        <p style="color:#888; margin:0;">اختر كلمة مرور لإكمال تسجيلك</p>
      </div>
    `;
    document.getElementById('registerForm').prepend(welcomeEl);
    
    document.getElementById('password-label').innerText = 'كلمة المرور';
    document.getElementById('submitRegBtn').querySelector('span').innerHTML = 'إكمال التسجيل &rarr;';

  } catch (err) {
    showFormMessage('Failed to verify invite link', 'error');
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
    showFormMessage('Please create a strong password.', 'error');
    return;
  }
  if (!isTermsAgreed) {
    showFormMessage('You must agree to the Terms and Conditions.', 'error');
    return;
  }

  const fullName = document.getElementById('fullName').value.trim();
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
    const apiBase = (typeof API !== 'undefined') ? API : 'http://127.0.0.1:8000';

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
        showFormMessage('Setup complete! Redirecting...', 'success');
        // Save token and go straight to onboarding
        if (data.access_token) {
          localStorage.setItem('token', data.access_token);
          if (data.user) {
            localStorage.setItem('user', JSON.stringify(data.user));
          }
          setTimeout(() => { window.location.href = '/onboarding.html'; }, 1200);
        } else {
          setTimeout(() => { window.location.href = 'login.html'; }, 1200);
        }
      } else {
        showFormMessage(data.detail || 'An error occurred. Please try again.', 'error');
        btn.disabled = false;
      }
    } else {
      // Normal flow submit
      const res = await fetch(`${apiBase}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: fullName,
          email,
          password,
          country,
          governorate
        })
      });

      const data = await res.json();

      if (res.ok) {
        showFormMessage('Account created successfully! Redirecting...', 'success');
        const nextUrl = `verify-email.html?email=${encodeURIComponent(email)}`;
        setTimeout(() => { window.location.href = nextUrl; }, 1200);
      } else {
        showFormMessage(data.detail || 'An error occurred. Please try again.', 'error');
        btn.disabled = false;
      }
    }

  } catch (e) {
    showFormMessage('No connection to the server.', 'error');
    btn.disabled = false;
  } finally {
    spinner.classList.add('hidden');
    btnText.classList.remove('opacity-0');
  }
}

function googleSignIn() {
  // Trigger google sign in flow
  const apiBase = (typeof API !== 'undefined') ? API : 'http://127.0.0.1:8000';
  window.location.href = `${apiBase}/auth/google/login`;
}

