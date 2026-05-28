/* ═══════════════════════════════════════════
   Onboarding Flow — JS Controller
═══════════════════════════════════════════ */

// Auth guard
const token = localStorage.getItem('token');
if (!token) window.location.href = 'login.html';

const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

// State
let currentStep = 1;
let selectedAvatar = null;
let uploadedAvatarUrl = null;
let uploadedFile = null;
let birthDate = null;
let socialMediaUrl = null;
let userName = '';

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
    alert('Only JPG, PNG, WEBP files are allowed');
    return;
  }

  // Validate size (5MB)
  if (file.size > 5 * 1024 * 1024) {
    alert('File size must be under 5MB');
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
  btn.textContent = 'Loading...';

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
        alert('Upload failed. Please try again.');
        btn.disabled = false;
        btn.textContent = 'Continue →';
        return;
      }
    }
    goToStep(2);
  } catch (e) {
    alert('Error uploading. Please try again.');
    btn.disabled = false;
    btn.textContent = 'Continue →';
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
  document.getElementById('congratsName').textContent = userName || 'Welcome!';

  // Confetti!
  launchConfetti();
}

// ═══ STEP 3: Complete Onboarding ═══
async function submitStep3() {
  const btn = document.getElementById('step3Btn');
  btn.disabled = true;
  btn.textContent = 'Loading...';

  try {
    const body = {
      birth_date: birthDate || null,
      social_media_url: socialMediaUrl || null,
      avatar_url: uploadedAvatarUrl || (selectedAvatar ? `${window.location.origin}/imgs/avatars/${selectedAvatar}` : null),
      selected_avatar: selectedAvatar || null,
    };

    const res = await fetch(`${API}/profile/complete-onboarding`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });

    if (res.ok) {
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
      
      window.location.href = 'dashboard.html';
    } else {
      const err = await res.json();
      alert(err.detail || 'Something went wrong');
      btn.disabled = false;
      btn.textContent = 'Start Exploring →';
    }
  } catch (e) {
    alert('Connection error. Please try again.');
    btn.disabled = false;
    btn.textContent = 'Start Exploring →';
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


