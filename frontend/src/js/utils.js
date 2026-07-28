// Auto-detect API base: use /api prefix in production (via Nginx), direct port in local dev
const API = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
  ? 'http://127.0.0.1:8000'
  : '/api';

// 🔒 Escape HTML to prevent XSS when inserting user-supplied data into innerHTML
// Usage: el.innerHTML = `<div>${escapeHtml(user.name)}</div>`;
// IMPORTANT: still safer to use textContent when you don't need HTML formatting.
window.escapeHtml = function(unsafe) {
    if (unsafe === null || unsafe === undefined) return '';
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
};

// 🔤 Base paragraph direction for a piece of user text.
// `dir="auto"` uses the FIRST strong character, which mis-detects an Arabic
// message that happens to start with an English word/number/emoji (e.g.
// "GPT-4 هو أحسن موديل") and flips the whole line to LTR. We instead force RTL
// whenever the text contains any Arabic letter — the Unicode bidi algorithm
// then keeps inline English/number runs LTR without breaking the line.
window.bidiDir = function(text) {
  // Arabic + Supplement + Extended-A + Presentation Forms A/B
  return /[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]/.test(text || '')
    ? 'rtl' : 'ltr';
};

// 🔗 Shared URL matcher + inline linkifier for chat/DM message bodies.
window.CHAT_URL_RE = /(https?:\/\/[^\s<]+|www\.[^\s<]+)/g;

// Turn one already-escaped URL match into a clickable link (new tab, LTR).
function chatUrlAnchor(escapedUrl) {
  let url = escapedUrl;
  let trail = '';
  const t = url.match(/[.,!?;:)\]}'"]+$/);   // keep trailing punctuation out of the link
  if (t) { trail = t[0]; url = url.slice(0, -trail.length); }
  const href = url.startsWith('www.') ? 'https://' + url : url;
  return `<a href="${href}" target="_blank" rel="noopener noreferrer" dir="ltr" class="msg-link">${url}</a>${trail}`;
}

// Full render pipeline for a chat/DM text body:
//   escape (XSS-safe) → linkify URLs → highlight @admin mentions on the text runs.
// URLs and mentions are handled on separate segments so neither corrupts the other.
window.formatChatText = function(rawContent) {
  const escaped = window.escapeHtml(rawContent || '');
  const parts = escaped.split(window.CHAT_URL_RE);   // capture group keeps URLs at odd indices
  const fmtMentions = window.formatAdminMentions || ((s) => s);
  return parts.map((part, i) => i % 2 === 1 ? chatUrlAnchor(part) : fmtMentions(part)).join('');
};

function showAlert(msg, type) {
  const el = document.getElementById('alert');
  if (el) {
    el.textContent = msg;
    el.className = `alert ${type}`;
  }
}

function showToast(message, type) {
  const toast = document.createElement('div');
  toast.className = `toast ${type || 'success'}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  btn.disabled = loading;
  btn.classList.toggle('loading', loading);
}

window.getBadgeLabel = function (badge) {
  if (!badge) return 'Member';
  const b = badge.toLowerCase();
  if (b.includes('admin') || b.includes('إدارة')) return 'Admin';
  if (b.includes('pro')) return 'Pro Member';
  if (b.includes('vip')) return 'VIP';
  if (b.includes('عضو') || b.includes('member')) return 'Member';
  return 'Member'; // safe fallback
};

// Resolve the role label shown on profile/member cards & badges.
// Priority: custom_title (if set) > admin > existing badge label (default "Member").
window.getRoleLabel = function (user) {
  if (!user) return 'Member';
  const ct = (user.custom_title || '').trim();
  if (ct) return ct;
  if (user.is_admin) return 'Admin';
  return window.getBadgeLabel ? window.getBadgeLabel(user.badge) : (user.badge || 'Member');
};

window.getAvatarSrc = function (user) {
  if (!user) return './imgs/default-avatar.png';
  if (user.avatar_url) {
    if (user.avatar_url.startsWith('http')) return user.avatar_url;
    if (user.avatar_url.startsWith('/')) return window.location.origin + user.avatar_url;
    return (window.API || '/api') + user.avatar_url;
  }
  if (user.selected_avatar) return user.selected_avatar;
  return './imgs/default-avatar.png';
};

function getToken() {
  return localStorage.getItem('token');
}

function saveToken(token) {
  localStorage.setItem('token', token);
}

// Auto-capture token from URL (Google OAuth redirect)
(function () {
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
  localStorage.removeItem('user'); window.location.href = '/login';
}

// ─── Auth Guard ─────────────────────────────────────────────
async function enforceAuthGuard() {
  const currentPath = window.location.pathname;

  // Match both /dashboard and /dashboard.html style paths
  const communityPaths = [
    'dashboard', 'chat', 'direct-messages',
    'build-with-me', 'guest-of-honors', 'teamdashboard', 'profile',
    'profile-settings', 'ai-updates', 'help-center', 'achievements'
  ];
  const isCommunityPage = communityPaths.some(p =>
    currentPath === '/' + p ||
    currentPath.startsWith('/' + p + '?') ||
    currentPath.endsWith('/' + p + '.html')
  );

  if (!isCommunityPage) return;

  // Hide body immediately to prevent flash of content before auth check
  document.documentElement.style.visibility = 'hidden';

  const token = getToken();
  if (!token) {
    localStorage.removeItem('user');
    window.location.href = '/login';
    return;
  }

  try {
    const res = await fetch(`${API}/profile/me?_t=${Date.now()}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (res.status === 401) {
      // Token invalid or user deleted — logout
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
      return;
    }

    if (res.status === 402) {
      // Subscription expired — keep the session and send them to the in-app
      // renewal page. /renewal needs the token to read the subscription and
      // create the payment, so DON'T clear it here.
      window.location.href = '/renewal';
      return;
    }

    if (res.status === 403) {
      // Logged in but not allowed through — same in-app renewal flow, token kept
      window.location.href = '/renewal';
      return;
    }

    if (res.ok) {
      const u = await res.json();
      localStorage.setItem('user', JSON.stringify(u));
      if (!u.is_active) {
        // Still logged in — renew inside the platform instead of being kicked out
        window.location.href = '/renewal';
        return;
      }
      // If active but onboarding not yet completed — redirect there
      if (!u.onboarding_completed && !currentPath.endsWith('onboarding.html') && currentPath !== '/onboarding') {
        window.location.href = '/onboarding';
        return;
      }
      // Auth passed — show page
      document.documentElement.style.visibility = '';
    } else {
      // Any other error — redirect to login for safety
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
  } catch (e) {
    // Network error — show page (don't block on connectivity issues)
    document.documentElement.style.visibility = '';
  }
}

enforceAuthGuard();

// ─── Require Active User (used by page-level guards) ────────
async function requireActiveUser() {
  const token = getToken();
  if (!token) {
    localStorage.removeItem('user'); window.location.href = '/login';
    return null;
  }

  try {
    const res = await fetch(`${API}/profile/me?_t=`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (res.status === 401) {
      logout();
      return null;
    }

    if (res.status === 402) {
      // Subscription expired — keep the token; /renewal needs it to read the
      // subscription and start the payment.
      window.location.href = '/renewal';
      return null;
    }

    if (res.status === 403) {
      window.location.href = '/renewal';
      return null;
    }

    if (!res.ok) return null;

    const user = await res.json();
    localStorage.setItem('user', JSON.stringify(user));

    if (!user.is_active) {
      window.location.href = '/renewal';
      return null;
    }

    // If active but onboarding not yet completed — redirect to complete profile
    if (!user.onboarding_completed) {
      const currentPath = window.location.pathname;
      if (!currentPath.endsWith('onboarding.html')) {
        window.location.href = 'onboarding.html';
        return null;
      }
    }

    return user;
  } catch (e) {
    return null;
  }
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
  }).catch(() => { });

  // Send heartbeat every 30 seconds
  setInterval(() => {
    fetch(`${API}/profile/heartbeat`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    }).catch(() => { });
  }, 30000);

  // Notify offline on page unload
  window.addEventListener('beforeunload', () => {
    fetch(`${API}/profile/offline`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      keepalive: true
    }).catch(() => { });
  });
}

// Start heartbeat if token exists
if (getToken()) {
  startHeartbeat();
  fetchGlobalNotifications();
  // Poll every 30s, and only while the tab is visible — hidden tabs were
  // hammering the API (4 requests per tick per tab) for badges nobody sees.
  setInterval(() => { if (!document.hidden) fetchGlobalNotifications(); }, 30000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) fetchGlobalNotifications(); });

  // Show admin-only sidebar links for admins
  (async function showAdminLinks() {
    try {
      const res = await fetch(`${API}/profile/me?_t=`, { headers: { 'Authorization': `Bearer ${getToken()}` } });
      if (!res.ok) return;
      const u = await res.json();
      if (u.is_admin) {
        document.querySelectorAll('[data-admin-only="true"]').forEach(el => {
          el.style.setProperty('display', 'flex', 'important');
        });
      } else {
        document.querySelectorAll('[data-admin-only="true"]').forEach(el => {
          el.style.setProperty('display', 'none', 'important');
        });
      }
    } catch (e) { }
  })();
}

// ─── Global Notifications ──────────────────────────────────────
async function fetchGlobalNotifications() {

  const token = getToken();
  if (!token) return;
  try {
    const res = await fetch(`${API}/chat/dm/list`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const dms = res.ok ? await res.json() : [];

    let notifications = [];
    try {
        // MUST use trailing slash to avoid 307 Redirect stripping Auth header!
        const notifRes = await fetch(`${API}/notifications/`, { headers: { 'Authorization': `Bearer ${token}` } });
        if (notifRes.ok) notifications = await notifRes.json();
    } catch(e) {}

    let communityUnread = 0;
    let communityChannels = {};
    try {
        const commRes = await fetch(`${API}/chat/community/unread`, { headers: { 'Authorization': `Bearer ${token}` } });
        if (commRes.ok) {
            const commData = await commRes.json();
            communityUnread = commData.unread_count || 0;
            communityChannels = commData.channels || {};
        }
    } catch(e) {}

    let aiUpdatesUnread = 0;
    try {
        const aiRes = await fetch(`${API}/ai-updates/unread`, { headers: { 'Authorization': `Bearer ${token}` } });
        if (aiRes.ok) aiUpdatesUnread = (await aiRes.json()).unread_count || 0;
    } catch(e) {}

    let unreadDmsOnly = 0;
    dms.forEach(dm => { unreadDmsOnly += dm.unread_count; });

    let unreadNotifs = notifications.filter(n => !n.is_read).length;
    let totalUnread = unreadDmsOnly + unreadNotifs + communityUnread + aiUpdatesUnread;

    const notifBadge = document.getElementById('notifBadge');
    const notifDot = document.getElementById('notifDot');

    if (totalUnread > 0) {
      if (notifBadge) {
        notifBadge.textContent = totalUnread > 99 ? '99+' : totalUnread;
        notifBadge.style.display = 'flex';
      }
      if (notifDot) notifDot.style.display = 'none';
    } else {
      if (notifBadge) notifBadge.style.display = 'none';
      if (notifDot) notifDot.style.display = 'none';
    }

    const dmBadge = document.getElementById('dmTotalBadge');
    if (dmBadge) {
      if (unreadDmsOnly > 0) {
        dmBadge.textContent = unreadDmsOnly > 99 ? '99+' : unreadDmsOnly;
        dmBadge.style.display = '';
      } else {
        dmBadge.style.display = 'none';
      }
    }

    const communityBadge = document.getElementById('communityTotalBadge');
    if (communityBadge) {
      if (communityUnread > 0) {
        communityBadge.textContent = communityUnread > 10 ? '+10' : communityUnread;
        communityBadge.style.display = '';
      } else {
        communityBadge.style.display = 'none';
      }
    }

    // Per-channel badges inside the community chat page (chat + post channels)
    document.querySelectorAll('[data-unread-channel]').forEach(el => {
      const n = communityChannels[el.getAttribute('data-unread-channel')] || 0;
      if (n > 0) {
        el.textContent = n > 10 ? '+10' : n;
        el.style.display = '';
      } else {
        el.style.display = 'none';
      }
    });

    const aiBadge = document.getElementById('aiUpdatesTotalBadge');
    if (aiBadge) {
      if (aiUpdatesUnread > 0) {
        aiBadge.textContent = aiUpdatesUnread > 10 ? '+10' : aiUpdatesUnread;
        aiBadge.style.display = '';
      } else {
        aiBadge.style.display = 'none';
      }
    }

    renderGlobalNotifList(dms, notifications, communityUnread, aiUpdatesUnread);
  } catch (e) { console.error('Global notif error:', e); }
}

function renderGlobalNotifList(dms, notifs, communityUnread, aiUpdatesUnread) {
  const el = document.getElementById('notifList');
  if (!el) return;

  dms = dms || [];
  notifs = notifs || [];
  communityUnread = communityUnread || 0;
  aiUpdatesUnread = aiUpdatesUnread || 0;

  if (dms.length === 0 && notifs.length === 0 && communityUnread === 0 && aiUpdatesUnread === 0) {
    el.innerHTML = `<div class="notif-empty">No notifications</div>`;
    return;
  }

  let html = '';

  // Quick "mark all read" action when there are unread bell notifications
  const unreadNotifCount = notifs.filter(n => !n.is_read).length;
  if (unreadNotifCount > 0) {
    html += `
        <div class="notif-item" style="cursor:pointer; justify-content:center; text-align:center;" onclick="window.markAllNotifsRead(event)">
            <div class="notif-item-text" style="color:var(--gold, #c1ff11); font-weight:700; width:100%;">✓ Mark all as read (${unreadNotifCount})</div>
        </div>
    `;
  }

  if (communityUnread > 0) {
    const commCount = communityUnread > 10 ? '+10' : communityUnread;
    html += `
        <div class="notif-item" style="cursor:pointer;" onclick="window.location.href='chat.html?channel=general'">
            <div class="notif-item-av"><i class="fa-solid fa-comments" style="color:var(--gold)"></i></div>
            <div class="notif-item-body">
                <div class="notif-item-name">Community Chat</div>
                <div class="notif-item-text">${commCount} new message${communityUnread > 1 ? 's' : ''}</div>
            </div>
            <div class="notif-item-count">${commCount}</div>
        </div>
    `;
  }

  if (aiUpdatesUnread > 0) {
    const aiCount = aiUpdatesUnread > 10 ? '+10' : aiUpdatesUnread;
    html += `
        <div class="notif-item" style="cursor:pointer;" onclick="window.location.href='ai-updates.html'">
            <div class="notif-item-av"><i class="fa-solid fa-wand-magic-sparkles" style="color:var(--gold)"></i></div>
            <div class="notif-item-body">
                <div class="notif-item-name">AI Updates</div>
                <div class="notif-item-text">${aiCount} new post${aiUpdatesUnread > 1 ? 's' : ''}</div>
            </div>
            <div class="notif-item-count">${aiCount}</div>
        </div>
    `;
  }

  notifs.forEach(n => {
     html += `
        <div class="notif-item" style="cursor:pointer;" onclick="window.markNotifRead(${n.id}, '${n.link || '#'}')">
            <div class="notif-item-av"><i class="fa-solid fa-bell" style="color:var(--gold)"></i></div>
            <div class="notif-item-body">
                <div class="notif-item-name">${n.title}</div>
                <div class="notif-item-text">${n.body}</div>
            </div>
            ${!n.is_read ? `<div class="notif-item-count">1</div>` : ''}
        </div>
     `;
  });

  const isDmChat = window.location.pathname.endsWith('direct-messages.html');
  dms.forEach(dm => {
    const u = dm.user;
    const av = u.avatar_url ? (u.avatar_url.startsWith('http') ? u.avatar_url : API + u.avatar_url) : '?';

    let formattedMsg = dm.last_message || '';
    if (dm.last_message_type === 'image') formattedMsg = '📷 Image';
    else if (dm.last_message_type === 'voice') formattedMsg = '🎤 Voice message';

    const preview = formattedMsg ? formattedMsg.substring(0, 40) + (formattedMsg.length > 40 ? '...' : '') : 'Sent you a message';

    const safeName = u.full_name.replace(/'/g, "\\'");
    const onClickAction = isDmChat
      ? `activeDmUserName='${safeName}'; selectChannel('${dm.channel_name}'); toggleNotifPanel();`
      : `window.location.href='direct-messages.html?v=4&channel=${dm.channel_name}'`;

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

window.markNotifRead = async function(id, link) {
    try {
        await fetch(`${API}/notifications/${id}/read`, {
            method: 'PATCH',
            headers: { 'Authorization': `Bearer ${getToken()}` }
        });
    } catch(e) {}
    if (link && link !== '#' && link !== 'null') {
        window.location.href = link;
    } else {
        // No destination — refresh the panel/badges immediately so the item
        // doesn't look "stuck" until the next 30s poll.
        fetchGlobalNotifications();
    }
}

window.markAllNotifsRead = async function(e) {
    if (e) e.stopPropagation();
    try {
        await fetch(`${API}/notifications/read-all`, {
            method: 'PATCH',
            headers: { 'Authorization': `Bearer ${getToken()}` }
        });
    } catch(e2) {}
    fetchGlobalNotifications();
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



// == Sidebar Initialization ==
function initSidebar() {
  const hamburger = document.getElementById('hamburgerBtn');
  const sidebar = document.querySelector('.dash-sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  const hamburgerDash = document.getElementById('hamburgerDash');
  function toggleSidebar() {
    if (sidebar) sidebar.classList.toggle('open');
    if (overlay) overlay.classList.toggle('visible');
  }
  function closeSidebar() {
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('visible');
  }
  if (hamburger) hamburger.addEventListener('click', toggleSidebar);
  if (hamburgerDash) hamburgerDash.addEventListener('click', toggleSidebar);
  if (overlay) overlay.addEventListener('click', closeSidebar);
  if (sidebar) {
    sidebar.querySelectorAll('a, button').forEach(link => {
      link.addEventListener('click', () => {
        if (window.innerWidth <= 768) closeSidebar();
      });
    });
  }

  // ── Desktop collapse (icons-only) — shared across every community page ──
  // The state lives on <body> + localStorage so it persists as you navigate
  // between dashboard / courses / chat / etc. CSS gates the visuals to desktop.
  if (sidebar) {
    const COLLAPSE_KEY = 'ghawy_sidebar_collapsed';
    const logoRow = sidebar.querySelector('.sidebar-logo');
    let collapseBtn = null;

    // Give each nav item a title so icons-only mode still names it on hover
    sidebar.querySelectorAll('.nav-item').forEach(item => {
      const lbl = item.querySelector('span:not(.nav-icon-wrap):not(.dm-badge)');
      if (lbl && !item.getAttribute('title')) item.setAttribute('title', lbl.textContent.trim());
    });

    function applyCollapsed(on) {
      document.body.classList.toggle('sidebar-collapsed', !!on);
      if (collapseBtn) {
        collapseBtn.setAttribute('aria-expanded', on ? 'false' : 'true');
        collapseBtn.setAttribute('title', on ? 'فتح القائمة' : 'طيّ القائمة');
      }
    }

    if (logoRow) {
      collapseBtn = document.createElement('button');
      collapseBtn.type = 'button';
      collapseBtn.className = 'sidebar-collapse-btn';
      collapseBtn.setAttribute('aria-label', 'Collapse sidebar');
      collapseBtn.innerHTML = '<i class="fa-solid fa-angles-left"></i>';
      logoRow.appendChild(collapseBtn);
      collapseBtn.addEventListener('click', () => {
        const on = !document.body.classList.contains('sidebar-collapsed');
        applyCollapsed(on);
        try { localStorage.setItem(COLLAPSE_KEY, on ? '1' : '0'); } catch (e) {}
      });
    }

    try { applyCollapsed(localStorage.getItem(COLLAPSE_KEY) === '1'); } catch (e) {}
    // Enable the width transition only after first paint so load never animates
    requestAnimationFrame(() => requestAnimationFrame(() => {
      document.body.classList.add('sidebar-anim');
    }));
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initSidebar();
});


// ─── Theme Toggle ─────────────────────────────────────────────
function setTheme(theme) {
    if (theme === 'system') {
        const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    } else {
        document.documentElement.setAttribute('data-theme', theme);
    }
    localStorage.setItem('theme', theme);
    
    document.querySelectorAll('.theme-btn').forEach(btn => {
        if (btn.dataset.theme === theme) btn.classList.add('active');
        else btn.classList.remove('active');
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    setTheme(savedTheme);

    document.querySelectorAll('.theme-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            setTheme(btn.dataset.theme);
        });
    });
});

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
    if (localStorage.getItem('theme') === 'system') {
        setTheme('system');
    }
});

// ─── Mentions Autocomplete ─────────────────────────────────────
(function() {
    let chatAdminsCache = null;
    window.globalChatAdmins = [];

    async function fetchChatAdmins() {
        if (chatAdminsCache) return chatAdminsCache;
        try {
            const token = getToken();
            if(!token) return [];
            const res = await fetch(`${API}/chat/admins`, { headers: { 'Authorization': `Bearer ${token}` } });
            if(res.ok) {
                chatAdminsCache = await res.json();
                window.globalChatAdmins = chatAdminsCache;
                return chatAdminsCache;
            }
        } catch(e) {}
        return [];
    }

    // Prefetch on load
    fetchChatAdmins();

    window.formatAdminMentions = function(escapedText) {
        if (!window.globalChatAdmins || window.globalChatAdmins.length === 0) return escapedText;
        try {
            let newText = escapedText;
            for (const admin of window.globalChatAdmins) {
                const adminName = admin.full_name;
                if (!adminName) continue;
                // Escape regex metacharacters so admin names containing characters like
                // [ ] ( ) * + ? . don't produce an invalid RegExp (which would throw and
                // abort message rendering for the whole chat).
                const safeName = adminName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                const regex = new RegExp(`@${safeName}(?![\\w\\u0600-\\u06FF])`, 'gi');
                newText = newText.replace(regex, `<span style="color:var(--gold, #c1ff11);font-weight:600;">$&</span>`);
            }
            // Also highlight @all
            newText = newText.replace(/@all(?![\\w\\u0600-\\u06FF])/gi, `<span style="color:var(--gold, #c1ff11);font-weight:600;">$&</span>`);
            return newText;
        } catch (e) {
            // Never let mention-highlighting break message rendering.
            console.warn('formatAdminMentions failed:', e);
            return escapedText;
        }
    };

    document.addEventListener('DOMContentLoaded', () => {
        const style = document.createElement('style');
        style.innerHTML = `
        .mentions-dropdown {
            position: absolute;
            bottom: 100%;
            left: 0;
            background: var(--bg-card, #1a1a1a);
            border: 1px solid var(--border-color, #333);
            border-radius: 8px;
            max-height: 200px;
            overflow-y: auto;
            width: 250px;
            z-index: 1000;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            margin-bottom: 8px;
            display: none;
        }
        .mention-item {
            display: flex;
            align-items: center;
            padding: 8px 12px;
            cursor: pointer;
            gap: 8px;
            transition: background 0.2s;
        }
        .mention-item:hover {
            background: var(--bg-hover, #2a2a2a);
        }
        .mention-item img {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            object-fit: cover;
        }
        .mention-item span {
            font-size: 0.85rem;
            color: var(--text-color, #fff);
        }
        .chat-input-bar, .dash-chat-input-row { position: relative; }
        `;
        document.head.appendChild(style);

        const attachMentions = (inputId) => {
            const input = document.getElementById(inputId);
            if(!input) return;
            
            let dropdown = document.createElement('div');
            dropdown.className = 'mentions-dropdown';
            input.parentNode.insertBefore(dropdown, input.nextSibling);

            input.addEventListener('input', async () => {
                const val = input.value;
                const cursor = input.selectionStart;
                const textBeforeCursor = val.substring(0, cursor);
                const match = textBeforeCursor.match(/@([\w\u0600-\u06FF\s]*)$/);
                
                if (match) {
                    const search = match[1].toLowerCase();
                    const admins = await fetchChatAdmins();
                    let filtered = admins.filter(a => a.full_name.toLowerCase().includes(search));
                    
                    try {
                        const u = JSON.parse(localStorage.getItem('user'));
                        if (u && u.is_admin && 'all'.includes(search)) {
                            filtered.push({ full_name: 'all', avatar_url: '/imgs/g-icon-logo.png' });
                        }
                    } catch(e) {}
                    
                    if (filtered.length > 0) {
                        dropdown.innerHTML = filtered.map(a => `
                            <div class="mention-item" data-name="${a.full_name}">
                                <img src="${window.getAvatarSrc(a)}" alt="">
                                <span>${a.full_name}</span>
                            </div>
                        `).join('');
                        dropdown.style.display = 'block';
                        
                        dropdown.querySelectorAll('.mention-item').forEach(item => {
                            item.addEventListener('click', () => {
                                const name = item.getAttribute('data-name');
                                const prefix = val.substring(0, match.index);
                                const suffix = val.substring(cursor);
                                input.value = prefix + '@' + name + ' ' + suffix;
                                input.focus();
                                dropdown.style.display = 'none';
                            });
                        });
                    } else {
                        dropdown.style.display = 'none';
                    }
                } else {
                    dropdown.style.display = 'none';
                }
            });

            document.addEventListener('click', (e) => {
                if (!dropdown.contains(e.target) && e.target !== input) {
                    dropdown.style.display = 'none';
                }
            });
        };

        setTimeout(() => {
            attachMentions('chatInput');
            attachMentions('dashChatInput');
        }, 1000);
    });
})();
