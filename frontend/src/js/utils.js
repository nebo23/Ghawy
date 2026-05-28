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

// ─── Auth Guard ─────────────────────────────────────────────
async function enforceAuthGuard() {
  const currentPath = window.location.pathname;
  const communityPages = ['dashboard.html', 'chat.html', 'courses.html', 'course-detail.html', 'build-with-me.html', 'guest-of-honors.html', 'teamdashboard.html', 'profile.html', 'profile-settings.html'];
  const isCommunityPage = communityPages.some(p => currentPath.endsWith(p));

  if (!isCommunityPage) return;

  const token = getToken();
  if (!token) {
    window.location.href = 'login.html';
    return;
  }

  try {
    const res = await fetch(`${API}/profile/me`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (res.ok) {
      const u = await res.json();
      if (!u.is_active || u.subscription_type === 'none') {
        window.location.href = 'payment.html';
      }
    } else {
      logout();
    }
  } catch(e) {}
}

enforceAuthGuard();

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
  fetchGlobalNotifications();
  setInterval(fetchGlobalNotifications, 10000); // Poll every 10s

  // Hide admin-only sidebar links for non-admins
  (async function hideAdminLinks() {
    try {
      const res = await fetch(`${API}/profile/me`, { headers: { 'Authorization': `Bearer ${getToken()}` } });
      if (!res.ok) return;
      const u = await res.json();
      if (!u.is_admin) {
        document.querySelectorAll('[data-admin-only="true"]').forEach(el => el.style.display = 'none');
      }
    } catch(e) {}
  })();
}

// ─── Global Notifications ──────────────────────────────────────
async function fetchGlobalNotifications() {
    // chat.html has its own polling loop for loadDmList which handles this
    if (window.location.pathname.endsWith('chat.html')) return;
    
    const token = getToken();
    if (!token) return;
    try {
        const res = await fetch(`${API}/chat/dm/list`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) return;
        const dms = await res.json();
        
        let totalUnread = 0;
        dms.forEach(dm => { totalUnread += dm.unread_count; });

        const notifBadge = document.getElementById('notifBadge');
        const notifDot = document.getElementById('notifDot');
        
        if (totalUnread > 0) {
            if(notifBadge) {
                notifBadge.textContent = totalUnread > 99 ? '99+' : totalUnread;
                notifBadge.style.display = 'flex';
            }
            if (notifDot) notifDot.style.display = 'none';
        } else {
            if(notifBadge) notifBadge.style.display = 'none';
            if (notifDot) notifDot.style.display = 'none';
        }
        
        const dmBadge = document.getElementById('dmTotalBadge');
        if (dmBadge) {
            if (totalUnread > 0) {
                dmBadge.textContent = totalUnread > 99 ? '99+' : totalUnread;
                dmBadge.style.display = '';
            } else {
                dmBadge.style.display = 'none';
            }
        }

        renderGlobalNotifList(dms);
    } catch(e) { console.error('Global notif error:', e); }
}

function renderGlobalNotifList(dms) {
    const el = document.getElementById('notifList');
    if (!el) return;
    
    if (!dms || dms.length === 0) {
        el.innerHTML = `<div class="notif-empty">No notifications</div>`;
        return;
    }
    
    let html = '';
    const isChat = window.location.pathname.endsWith('chat.html');
    dms.forEach(dm => {
        const u = dm.user;
        const av = u.avatar_url ? (u.avatar_url.startsWith('http') ? u.avatar_url : API + u.avatar_url) : '?';
        
        let formattedMsg = dm.last_message || '';
        if (dm.last_message_type === 'image') formattedMsg = '📷 صورة';
        else if (dm.last_message_type === 'voice') formattedMsg = '🎤 رسالة صوتية';
        
        const preview = formattedMsg ? formattedMsg.substring(0, 40) + (formattedMsg.length > 40 ? '...' : '') : 'Sent you a message';
        
        const safeName = u.full_name.replace(/'/g, "\\'");
        const onClickAction = isChat 
            ? `activeDmUserName='${safeName}'; selectChannel('${dm.channel_name}'); toggleNotifPanel();`
            : `window.location.href='chat.html?v=4&channel=${dm.channel_name}'`;
        
        html += `
        <div class="notif-item" onclick="${onClickAction}">
            <div class="notif-item-av"><img src="${av}" onerror="this.src='./imgs/ghawi-logo.png'"/></div>
            <div class="notif-item-body">
                <div class="notif-item-name">${u.full_name}</div>
                <div class="notif-item-text">${preview}</div>
            </div>
            ${dm.unread_count > 0 ? `<div class="notif-item-count">${dm.unread_count}</div>` : ''}
        </div>
        `;
    });
    el.innerHTML = html;
}

function toggleNotifPanel() {
    const np = document.getElementById('notifPanel');
    if (np) np.classList.toggle('open');
}

// Close dropdowns when clicking outside
document.addEventListener('click', e => {
  const d = document.getElementById('userDropdown');
  const u = document.getElementById('topbarUser');
  if (d && u && !d.contains(e.target) && !u.contains(e.target)) d.classList.remove('open');

  const np = document.getElementById('notifPanel');
  const nw = document.getElementById('notifWrapper');
  if (np && nw && !nw.contains(e.target)) np.classList.remove('open');
});


