/* ═══════════════════════════════════════════
   Onboarding Flow — JS Controller
═══════════════════════════════════════════ */

// ── اللغة ──
// الصفحة بتقرا الاختيار من نفس المصدر الوحيد (ghawy_lang عن طريق
// window.currentLang() في src/js/i18n.js). كانت رسايل الـ toast هنا عربي
// ثابت جنب ماركب إنجليزي ثابت، فالشاشة كانت بتتكلم لغتين في نفس الوقت.
function obLang() {
  if (typeof window.currentLang === 'function') return window.currentLang();
  return document.documentElement.getAttribute('lang') === 'en' ? 'en' : 'ar';
}
function L(pair) {
  if (pair == null) return '';
  if (typeof pair === 'string') return pair;
  return pair[obLang()] || pair.ar || '';
}
const OB_T = {
  onlyImages: { ar: 'الصور المسموحة JPG أو PNG أو WEBP بس', en: 'Only JPG, PNG and WEBP files are allowed' },
  tooBig: { ar: 'الملف لازم يكون أقل من 5 ميجا', en: 'File size must be under 5MB' },
  loading: { ar: 'لحظة...', en: 'Loading...' },
  uploadFailed: { ar: 'الرفع مانجحش. حاول تاني.', en: 'Upload failed. Please try again.' },
  uploadError: { ar: 'حصلت مشكلة في الرفع. حاول تاني.', en: 'Error uploading. Please try again.' },
  continueBtn: { ar: 'كمّل →', en: 'Continue →' },
  startExploring: { ar: 'يلا نبدأ →', en: 'Start Exploring →' },
  welcome: { ar: 'أهلاً بيك!', en: 'Welcome!' },
  wrongDial: { ar: 'الرقم مش بيبدأ بـ {code} — اختار الدولة الصح', en: 'The number does not start with {code} — pick the right country' },
  badNumber: { ar: 'اكتب رقم {country} صحيح — {hint}', en: 'Enter a valid {country} number — {hint}' },
  codeSent: { ar: 'تم إرسال الكود ✅', en: 'Code sent ✅' },
  genericErr: { ar: 'حصل خطأ، حاول تاني', en: 'Something went wrong, please try again' },
  noConnection: { ar: 'مفيش اتصال بالسيرفر', en: 'No connection to the server' },
  sixDigits: { ar: 'اكتب الكود المكوّن من 6 أرقام كامل', en: 'Enter the full 6-digit code' },
  reenterPhone: { ar: 'اكتب رقمك تاني واطلب كود جديد', en: 'Enter your number again and request a new code' },
  eg: { ar: 'مثال: {n}', en: 'e.g. {n}' },
};

/** نص المثال تحت خانة الرقم — الرقم نفسه ثابت واللي بيتترجم كلمة "مثال". */
function hintText(cfg) {
  return (cfg && cfg.hintEg) ? obFill(OB_T.eg, { n: cfg.hintEg }) : '';
}
function obFill(pair, vars) {
  let out = L(pair);
  for (const k in vars) out = out.split('{' + k + '}').join(vars[k]);
  return out;
}

// Auth guard
const token = localStorage.getItem('token');
if (!token) { localStorage.removeItem('user'); window.location.href = '/login'; }

const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

// State
let currentStep = 1;
let selectedAvatar = null;
let uploadedAvatarUrl = null;
let uploadedFile = null;
let birthDate = null;
let socialMediaUrl = null;
let userName = '';
// هل نسأل العضو ده يكتب اسمه بالعربي؟ السيرفر بيقرر — على الاسم المتخزّن، مش
// على طريقة التسجيل — وبيبعت معاها الاقتراح اللي الخانة بتتملي بيه.
let needsArabicName = false;
let latinNameOk = false;

// ── Load user name ──
(async function loadUserName() {
  try {
    const res = await fetch(`${API}/profile/me`, { headers });
    if (res.ok) {
      const u = await res.json();
      userName = u.full_name || '';
    }
  } catch(e) {}
})();

// ── Arabic-name step: shown only when the stored name is not Arabic ──
(async function loadNameStep() {
  try {
    const res = await fetch(`${API}/profile/onboarding-status`, { headers });
    if (!res.ok) return;
    const st = await res.json();
    if (!st.needs_arabic_name) return;
    needsArabicName = true;
    const group = document.getElementById('arabicNameGroup');
    const input = document.getElementById('arabicNameInput');
    if (group) group.style.display = '';
    // الاقتراح للعرض بس. اللي بيتخزّن هو اللي العضو بيسيبه في الخانة بعد ما
    // يشوفه — عمرنا ما بنكتب اسم مولّد من غير ما صاحبه يوافق عليه.
    if (input && st.suggested_name) input.value = st.suggested_name;
  } catch (e) {}
})();

// ═══ STEP NAVIGATION ═══
function goToStep(n) {
  currentStep = n;
  document.querySelectorAll('.onboarding-step').forEach(el => el.style.display = 'none');
  const step = document.getElementById('step' + n);
  if (step) step.style.display = '';

  // Update stepper
  const c1 = document.getElementById('stepCircle1');
  const c2 = document.getElementById('stepCircle2');
  const c3 = document.getElementById('stepCircle3');
  const l1 = document.getElementById('stepLine1');
  const l2 = document.getElementById('stepLine2');

  // Reset
  [c1, c2, c3].forEach(c => c.className = 'ob-step locked');
  [l1, l2].forEach(l => l.className = 'ob-step-line');

  // Step 1 is always done (payment)
  c1.className = 'ob-step done';
  c1.textContent = '✓';
  l1.className = 'ob-step-line done';

  if (n === 1) {
    c2.className = 'ob-step active';
    c2.textContent = '2';
    c3.className = 'ob-step locked';
    c3.textContent = '3';
  } else if (n === 2) {
    c2.className = 'ob-step done';
    c2.textContent = '✓';
    l2.className = 'ob-step-line done';
    c3.className = 'ob-step active';
    c3.textContent = '3';
  } else if (n === 3) {
    c2.className = 'ob-step done';
    c2.textContent = '✓';
    l2.className = 'ob-step-line done';
    c3.className = 'ob-step done';
    c3.textContent = '✓';
  }

  // Scroll to top
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ═══ STEP 1: Avatar Selection ═══
function handleAvatarSelect(filename, el) {
  selectedAvatar = filename;
  uploadedFile = null;
  uploadedAvatarUrl = null;

  // Clear upload preview
  const box = document.getElementById('uploadBox');
  box.classList.remove('has-preview');
  document.getElementById('fileInput').value = '';

  // Update selection
  document.querySelectorAll('.ob-avatar-item').forEach(item => item.classList.remove('selected'));
  el.classList.add('selected');

  // Enable continue
  document.getElementById('step1Btn').disabled = false;
}

// File upload
document.getElementById('fileInput').addEventListener('change', function(e) {
  const file = e.target.files[0];
  if (!file) return;

  // Validate type
  const allowed = ['image/jpeg', 'image/png', 'image/webp'];
  if (!allowed.includes(file.type)) {
    showToast(L(OB_T.onlyImages), 'error');
    return;
  }

  // Validate size (5MB)
  if (file.size > 5 * 1024 * 1024) {
    showToast(L(OB_T.tooBig), 'error');
    return;
  }

  uploadedFile = file;
  selectedAvatar = null;

  // Clear avatar selection
  document.querySelectorAll('.ob-avatar-item').forEach(item => item.classList.remove('selected'));

  // Show preview
  const reader = new FileReader();
  reader.onload = function(ev) {
    document.getElementById('previewImg').src = ev.target.result;
    document.getElementById('uploadBox').classList.add('has-preview');
  };
  reader.readAsDataURL(file);

  // Enable continue
  document.getElementById('step1Btn').disabled = false;
});

// Submit Step 1
async function submitStep1() {
  const btn = document.getElementById('step1Btn');
  btn.disabled = true;
  btn.textContent = L(OB_T.loading);

  try {
    if (uploadedFile) {
      const formData = new FormData();
      formData.append('file', uploadedFile);
      const res = await fetch(`${API}/profile/upload-avatar`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });
      if (res.ok) {
        const data = await res.json();
        uploadedAvatarUrl = data.avatar_url;
      } else {
        showToast(L(OB_T.uploadFailed), 'error');
        btn.disabled = false;
        btn.textContent = L(OB_T.continueBtn);
        return;
      }
    }
    goToPhoneStep();
  } catch (e) {
    showToast(L(OB_T.uploadError), 'error');
    btn.disabled = false;
    btn.textContent = L(OB_T.continueBtn);
  }
}

// ═══ STEP 2: Profile Details ═══
function submitStep2() {
  const social = document.getElementById('socialInput').value.trim();
  const birth = document.getElementById('birthDateInput').value;
  const errorEl = document.getElementById('socialError');

  // Validate social media
  if (!social || !social.startsWith('https://')) {
    errorEl.classList.add('show');
    document.getElementById('socialInput').focus();
    return;
  }
  errorEl.classList.remove('show');

  // الاسم بالعربي. نفس قاعدة السيرفر بالحرف (src/js/arabic-name.js)؛ لو الملف
  // مش محمّل بنعدّي والسيرفر هو اللي بيقرر.
  if (needsArabicName) {
    latinNameOk = !!document.getElementById('latinNameOk')?.checked;
    const nameEl = document.getElementById('arabicNameInput');
    const nameErr = document.getElementById('arabicNameError');
    const typed = (nameEl?.value || '').trim();
    if (!latinNameOk && typeof window.isArabicName === 'function' && !window.isArabicName(typed)) {
      if (nameErr) nameErr.classList.add('show');
      nameEl?.focus();
      return;
    }
    if (nameErr) nameErr.classList.remove('show');
    if (!latinNameOk && typed) userName = typed;
  }

  socialMediaUrl = social;

  // Format birth date to DD/MM/YYYY if provided
  if (birth) {
    const d = new Date(birth);
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const yyyy = d.getFullYear();
    birthDate = `${dd}/${mm}/${yyyy}`;
  }

  // Show congrats
  goToStep(3);

  // Show avatar in congrats
  const avatarEl = document.getElementById('congratsAvatar');
  if (uploadedAvatarUrl) {
    avatarEl.innerHTML = `<img src="${uploadedAvatarUrl}" alt=""/>`;
  } else if (selectedAvatar) {
    avatarEl.innerHTML = `<img src="imgs/avatars/${selectedAvatar}" alt=""/>`;
  } else {
    avatarEl.innerHTML = '<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:2.5rem;">🎉</div>';
  }

  // Show user name
  document.getElementById('congratsName').textContent = userName || L(OB_T.welcome);

  // Confetti!
  launchConfetti();
}

// ═══ STEP 3: Complete Onboarding ═══
async function submitStep3() {
  const btn = document.getElementById('step3Btn');
  btn.disabled = true;
  btn.textContent = L(OB_T.loading);

  try {
    const body = {
      birth_date: birthDate || null,
      social_media_url: socialMediaUrl || null,
      avatar_url: uploadedAvatarUrl || (selectedAvatar ? `${window.location.origin}/imgs/avatars/${selectedAvatar}` : null),
      selected_avatar: selectedAvatar || null,
    };
    if (needsArabicName) {
      if (latinNameOk) body.latin_name_ok = true;
      else body.full_name = (document.getElementById('arabicNameInput')?.value || '').trim();
    }

    const res = await fetch(`${API}/profile/complete-onboarding`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });

    if (res.ok) {
      // Onboarding is now completed on the backend. Immediately sync the
      // cached user state so the dashboard's synchronous auth guard (which
      // reads localStorage['user']) doesn't see a stale onboarding_completed
      // = false and bounce the user straight back to onboarding (the loop).
      try {
        const cachedUser = JSON.parse(localStorage.getItem('user') || '{}');
        cachedUser.onboarding_completed = true;
        localStorage.setItem('user', JSON.stringify(cachedUser));
      } catch (err) {
        localStorage.setItem('user', JSON.stringify({ onboarding_completed: true }));
      }

      localStorage.setItem('just_onboarded', 'true');

      // Update has_completed_onboarding just in case
      try {
        await fetch(`${API}/users/me/complete-onboarding`, {
          method: 'PATCH',
          headers: { 'Authorization': `Bearer ${token}` }
        });
      } catch (err) {
        console.error("Failed to patch onboarding status", err);
      }

      // Use replace() so onboarding is not kept in history — prevents the
      // back button from looping back to onboarding after completion.
      window.location.replace('dashboard.html');
    } else {
      const err = await res.json();
      alert(err.detail || 'Something went wrong');
      btn.disabled = false;
      btn.textContent = L(OB_T.startExploring);
    }
  } catch (e) {
    showToast('Connection error. Please try again.', 'error');
    btn.disabled = false;
    btn.textContent = L(OB_T.startExploring);
  }
}

// ═══ CONFETTI ═══
function launchConfetti() {
  const container = document.getElementById('confettiContainer');
  if (!container) return;
  const colors = ['#c1ff11', '#d4ff4a', '#4ade80', '#ffffff', '#f59e0b', '#ef4444', '#8b5cf6'];
  for (let i = 0; i < 40; i++) {
    const dot = document.createElement('div');
    dot.className = 'ob-confetti-dot';
    dot.style.left = Math.random() * 100 + '%';
    dot.style.top = '-10px';
    dot.style.width = (Math.random() * 8 + 4) + 'px';
    dot.style.height = dot.style.width;
    dot.style.background = colors[Math.floor(Math.random() * colors.length)];
    dot.style.animationDuration = (Math.random() * 2 + 2) + 's';
    dot.style.animationDelay = (Math.random() * 1.5) + 's';
    container.appendChild(dot);
  }
  setTimeout(() => { container.innerHTML = ''; }, 5000);
}

// Hide social error on input
document.getElementById('socialInput').addEventListener('input', function() {
  document.getElementById('socialError').classList.remove('show');
});


// ═══ PHONE VERIFICATION ═══
function goToPhoneStep() {
  currentStep = 'phone';
  document.querySelectorAll('.onboarding-step').forEach(el => el.style.display = 'none');
  const step = document.getElementById('step-phone');
  if (step) step.style.display = '';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Country Configuration ────────────────────────────────
const COUNTRY_CONFIG = {
  EG: { dialCode: '+20',  digits: 11, placeholder: '01XXXXXXXXX',  hintEg: '01012345678',  stripZero: true,  regex: /^01[0-9]{9}$/ },
  SA: { dialCode: '+966', digits: 10, placeholder: '05XXXXXXXX',   hintEg: '0512345678',   stripZero: true,  regex: /^05[0-9]{8}$/ },
  AE: { dialCode: '+971', digits: 10, placeholder: '05XXXXXXXX',   hintEg: '0512345678',   stripZero: true,  regex: /^05[0-9]{8}$/ },
  KW: { dialCode: '+965', digits: 8,  placeholder: 'XXXXXXXX',     hintEg: '51234567',     stripZero: false, regex: /^[569][0-9]{7}$/ },
  QA: { dialCode: '+974', digits: 8,  placeholder: 'XXXXXXXX',     hintEg: '33123456',     stripZero: false, regex: /^[3567][0-9]{7}$/ },
  BH: { dialCode: '+973', digits: 8,  placeholder: 'XXXXXXXX',     hintEg: '36123456',     stripZero: false, regex: /^[3689][0-9]{7}$/ },
  OM: { dialCode: '+968', digits: 8,  placeholder: 'XXXXXXXX',     hintEg: '91234567',     stripZero: false, regex: /^[279][0-9]{7}$/ },
  JO: { dialCode: '+962', digits: 10, placeholder: '07XXXXXXXX',   hintEg: '0791234567',   stripZero: true,  regex: /^07[789][0-9]{7}$/ },
  LB: { dialCode: '+961', digits: 8,  placeholder: '03XXXXXX',     hintEg: '03123456',     stripZero: true,  regex: /^0?(3[0-9]{6}|(7[0-9]|8[0-9])[0-9]{6})$/ },
  IQ: { dialCode: '+964', digits: 11, placeholder: '07XXXXXXXXX',  hintEg: '07901234567',  stripZero: true,  regex: /^07[0-9]{9}$/ },
  SY: { dialCode: '+963', digits: 10, placeholder: '09XXXXXXXX',   hintEg: '0912345678',   stripZero: true,  regex: /^09[0-9]{8}$/ },
  PS: { dialCode: '+970', digits: 10, placeholder: '059XXXXXXX',   hintEg: '0591234567',   stripZero: true,  regex: /^05[69][0-9]{7}$/ },
  YE: { dialCode: '+967', digits: 9,  placeholder: '7XXXXXXXX',    hintEg: '712345678',    stripZero: true,  regex: /^0?7[0-9]{8}$/ },
  SD: { dialCode: '+249', digits: 10, placeholder: '09XXXXXXXX',   hintEg: '0912345678',   stripZero: true,  regex: /^09[0-9]{8}$/ },
  LY: { dialCode: '+218', digits: 10, placeholder: '09XXXXXXXX',   hintEg: '0912345678',   stripZero: true,  regex: /^09[1-6][0-9]{7}$/ },
  TN: { dialCode: '+216', digits: 8,  placeholder: 'XXXXXXXX',     hintEg: '21234567',     stripZero: false, regex: /^[2-9][0-9]{7}$/ },
  DZ: { dialCode: '+213', digits: 10, placeholder: '0XXXXXXXXX',   hintEg: '0551234567',   stripZero: true,  regex: /^0[5-7][0-9]{8}$/ },
  MA: { dialCode: '+212', digits: 10, placeholder: '06XXXXXXXX',   hintEg: '0612345678',   stripZero: true,  regex: /^0[67][0-9]{8}$/ },
  MR: { dialCode: '+222', digits: 8,  placeholder: 'XXXXXXXX',     hintEg: '31234567',     stripZero: false, regex: /^[2-4][0-9]{7}$/ },
  SO: { dialCode: '+252', digits: 9,  placeholder: '6XXXXXXXX',    hintEg: '612345678',    stripZero: true,  regex: /^0?[6-9][0-9]{7,8}$/ },
  DJ: { dialCode: '+253', digits: 8,  placeholder: '77XXXXXX',     hintEg: '77123456',     stripZero: false, regex: /^77[0-9]{6}$/ },
  KM: { dialCode: '+269', digits: 7,  placeholder: 'XXXXXXX',      hintEg: '3212345',      stripZero: false, regex: /^[347][0-9]{6}$/ },
};

// ── Helpers ──────────────────────────────────────────────
function getSelectedCountry() {
  const sel = document.getElementById('countrySelect');
  return (sel && sel.value) ? sel.value : 'EG';
}

function buildE164(localNumber, countryCode) {
  const cfg = COUNTRY_CONFIG[countryCode];
  if (!cfg) return localNumber;
  const digits = localNumber.replace(/[^0-9]/g, '');
  if (cfg.stripZero && digits.startsWith('0')) {
    return cfg.dialCode + digits.slice(1);
  }
  return cfg.dialCode + digits;
}

function onCountryChange() {
  const code = getSelectedCountry();
  const cfg = COUNTRY_CONFIG[code];
  if (!cfg) return;
  const input = document.getElementById('phoneInput');
  const hint  = document.getElementById('phoneHint');
  if (input) {
    input.placeholder = cfg.placeholder;
    input.maxLength   = 20;
    input.value       = '';
    input.focus();
  }
  if (hint) hint.textContent = hintText(cfg);
}

let enteredPhone = '';

function setLoadingBtn(btnId, isLoading) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  const text = btn.querySelector('.btn-text');
  const spinner = btn.querySelector('.spinner');
  
  if (isLoading) {
    btn.disabled = true;
    if(text) text.style.opacity = '0';
    if(spinner) spinner.style.display = 'block';
  } else {
    btn.disabled = false;
    if(text) text.style.opacity = '1';
    if(spinner) spinner.style.display = 'none';
  }
}

async function sendPhoneOTP() {
  const localNumber = document.getElementById('phoneInput').value.trim();
  const countryCode = getSelectedCountry();
  const cfg = COUNTRY_CONFIG[countryCode];

  // Strip formatting characters the user may have typed/pasted
  const normalized = localNumber.replace(/[\s\-\(\)]/g, '');

  let phoneE164;
  if (normalized.startsWith('+') || (cfg && normalized.startsWith(cfg.dialCode.slice(1)))) {
    // User entered international format: +966551996766 or 966551996766
    phoneE164 = normalized.startsWith('+') ? normalized : '+' + normalized;
    if (!cfg || !phoneE164.startsWith(cfg.dialCode)) {
      showToast(obFill(OB_T.wrongDial, { code: cfg ? cfg.dialCode : '' }), 'error');
      return;
    }
    if (!/^\+\d{7,15}$/.test(phoneE164)) {
      showToast(obFill(OB_T.badNumber, { country: document.getElementById('countrySelect')?.selectedOptions[0]?.text?.split('(')[0]?.trim() || '', hint: hintText(cfg) }), 'error');
      return;
    }
  } else {
    // Local format (e.g. 0551996766 for SA, 51234567 for KW)
    if (!cfg || !cfg.regex.test(normalized)) {
      showToast(obFill(OB_T.badNumber, { country: document.getElementById('countrySelect')?.selectedOptions[0]?.text?.split('(')[0]?.trim() || '', hint: hintText(cfg) }), 'error');
      return;
    }
    phoneE164 = buildE164(normalized, countryCode);
  }

  setLoadingBtn('sendOtpBtn', true);

  try {
    const res = await fetch(`${API}/profile/send-phone-otp`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ phone: phoneE164 })
    });

    const data = await res.json();

    if (res.ok) {
      enteredPhone = phoneE164;
      document.getElementById('phoneSent').textContent = localNumber + ' (' + phoneE164 + ')';
      document.getElementById('phone-input-phase').style.display = 'none';
      document.getElementById('otp-input-phase').style.display = 'block';
      showToast(L(OB_T.codeSent), 'success');
      document.querySelectorAll('.otp-box')[0].focus();
    } else {
      showToast(data.detail || L(OB_T.genericErr), 'error');
    }
  } catch (err) {
    showToast(L(OB_T.noConnection), 'error');
  } finally {
    setLoadingBtn('sendOtpBtn', false);
  }
}

async function verifyPhoneOTP() {
  const boxes = document.querySelectorAll('.otp-box');
  const code = Array.from(boxes).map(b => b.value).join('');

  if (code.length !== 6) {
    showToast(L(OB_T.sixDigits), 'error');
    return;
  }

  setLoadingBtn('verifyOtpBtn', true);

  try {
    const res = await fetch(`${API}/profile/verify-phone-otp`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ phone: enteredPhone, code })
    });

    const data = await res.json();

    if (res.ok) {
      if (typeof showToast !== 'undefined') showToast('Verified successfully 🎉', 'success');
      setTimeout(() => goToStep(2), 800);
    } else {
      if (typeof showToast !== 'undefined') showToast(data.detail || 'Invalid code', 'error');
      else alert(data.detail || 'Invalid code');
    }
  } catch (err) {
    if (typeof showToast !== 'undefined') showToast('No connection to server', 'error');
    else showToast('No connection to server', 'error');
  } finally {
    setLoadingBtn('verifyOtpBtn', false);
  }
}

async function resendOTP() {
  document.getElementById('otp-input-phase').style.display = 'none';
  document.getElementById('phone-input-phase').style.display = 'block';
  // Re-apply country config in case user wants to switch country on resend
  onCountryChange();
  showToast(L(OB_T.reenterPhone), 'info');
}

// Initialize country config on load (sets correct placeholder/maxlength for default Egypt)
if (typeof onCountryChange === 'function') onCountryChange();

// Auto-focus between OTP boxes
document.querySelectorAll('.otp-box').forEach((box, index, boxes) => {
  box.addEventListener('input', () => {
    // only numeric
    box.value = box.value.replace(/[^0-9]/g, '');
    if (box.value && index < boxes.length - 1) {
      boxes[index + 1].focus();
    }
  });
  box.addEventListener('keydown', (e) => {
    if (e.key === 'Backspace' && !box.value && index > 0) {
      boxes[index - 1].focus();
    }
  });
  box.addEventListener('paste', (e) => {
    e.preventDefault();
    const paste = (e.clipboardData || window.clipboardData).getData('text');
    const numericPaste = paste.replace(/[^0-9]/g, '');
    let curr = index;
    for(let i=0; i<numericPaste.length && curr < boxes.length; i++) {
        boxes[curr].value = numericPaste[i];
        if (curr < boxes.length - 1) {
            boxes[curr+1].focus();
        }
        curr++;
    }
  });
});



