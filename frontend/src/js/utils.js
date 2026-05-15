const API = 'http://127.0.0.1:8000';

function showAlert(msg, type) {
  const el = document.getElementById('alert');
  el.textContent = msg;
  el.className = `alert ${type}`;
}

function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  btn.disabled = loading;
  btn.classList.toggle('loading', loading);
}

function getToken() {
  return localStorage.getItem('token');
}

function saveToken(token) {
  localStorage.setItem('token', token);
}

// Auto-capture token from URL (Google OAuth redirect)
(function() {
  const urlParams = new URLSearchParams(window.location.search);
  const urlToken = urlParams.get('token');
  if (urlToken) {
    saveToken(urlToken);
    // Clean URL without reload
    const cleanUrl = window.location.pathname;
    window.history.replaceState({}, document.title, cleanUrl);
  }
})();

function logout() {
  localStorage.removeItem('token');
  window.location.href = 'login.html';
}

async function initCurrency() {
  const cachedCurrency = localStorage.getItem('user_currency');
  if (cachedCurrency) {
    return cachedCurrency;
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);
    const res = await fetch('https://ipapi.co/json/', { signal: controller.signal });
    clearTimeout(timeoutId);
    const data = await res.json();
    
    if (data && data.country_code) {
      if (data.country_code.toUpperCase() === 'EG') {
        localStorage.setItem('user_currency', 'EGP');
        return 'EGP';
      } else {
        localStorage.setItem('user_currency', 'USD');
        return 'USD';
      }
    }
  } catch (err) {
    console.warn('Geolocation failed, defaulting to EGP');
  }

  localStorage.setItem('user_currency', 'EGP');
  return 'EGP';
}

// ─── Heartbeat System ──────────────────────────────────────
function startHeartbeat() {
  const token = getToken();
  if (!token) return;

  // Send initial heartbeat immediately
  fetch(`${API}/profile/heartbeat`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` }
  }).catch(() => {});

  // Send heartbeat every 30 seconds
  setInterval(() => {
    fetch(`${API}/profile/heartbeat`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    }).catch(() => {});
  }, 30000);

  // Notify offline on page unload
  window.addEventListener('beforeunload', () => {
    fetch(`${API}/profile/offline`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      keepalive: true
    }).catch(() => {});
  });
}

// Start heartbeat if token exists
if (getToken()) {
  startHeartbeat();
}

