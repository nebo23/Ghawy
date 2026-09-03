/**
 * dashboard-new.js — Ghawy Dashboard v10
 * Handles: Auth guard, Stats, Courses, Guests, AI Updates,
 *          Live Sessions, Upcoming countdown, WebSocket chat
 */

'use strict';

// ═══════════════════════════════════════════════════════
// 1. CONSTANTS & HELPERS
// ═══════════════════════════════════════════════════════

const AUTH_HEADERS = {
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'Content-Type': 'application/json'
};

/** Fetch wrapper — auto-handles 401 and 402 */
async function api(path, opts = {}) {
    const currentToken = localStorage.getItem('token');
    opts.headers = { 
        'Authorization': `Bearer ${currentToken}`,
        'Content-Type': 'application/json',
        ...(opts.headers || {}) 
    };
    const res = await fetch(API + path, opts);
    if (res.status === 401) {
        localStorage.removeItem('token');
        if (!window.location.pathname.endsWith('login.html')) {
            localStorage.removeItem('user'); window.location.href = '/login';
        }
        throw new Error('Unauthorized');
    }
    if (res.status === 402) {
        // Subscription expired — keep the session and renew inside the platform.
        // /renewal needs the token to read the subscription and create the payment.
        const p = window.location.pathname;
        if (!p.endsWith('login.html') && !p.endsWith('login') && !p.endsWith('renewal.html') && !p.endsWith('renewal')) {
            window.location.href = '/renewal';
        }
        throw new Error('PaymentRequired');
    }
    return res;
}

/** Time-ago helper */
function timeAgo(dt) {
    if (!dt) return '';
    if (typeof dt === 'string' && !dt.endsWith('Z') && !dt.includes('+')) dt += 'Z';
    const diff = (Date.now() - new Date(dt).getTime()) / 1000;
    if (diff < 60) return 'Now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
}

/** Escape HTML */
function esc(s) {
    const d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
}

/** Get initials from name */
function initials(name) {
    return (name || '?').split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase();
}

/** Stable color for a user_id */
const AVATAR_COLORS = ['#4fc3f7', '#69f0ae', '#ce93d8', '#ffd54f', '#ff8a65', '#80cbc4', '#f48fb1'];
function avatarColor(id) {
    return AVATAR_COLORS[(id || 0) % AVATAR_COLORS.length];
}

/** Build avatar HTML (img or initials) */
function buildAvatarHtml(name, avatarUrl, userId, size = 28) {
    const bg = avatarColor(userId);
    const init = initials(name);
    // Validated, not escaped: safeAvatarUrl returns a value with no quote or
    // angle bracket in it, which this needs — the string lands in src="..." and
    // in a nested single-quoted onerror handler at the same time.
    const full = safeAvatarUrl(avatarUrl);
    if (full) {
        return `<img src="${full}" alt="" style="width:${size}px;height:${size}px;object-fit:cover;border-radius:50%;" onerror="this.outerHTML='<div style=\'width:${size}px;height:${size}px;border-radius:50%;background:${bg}22;color:${bg};display:flex;align-items:center;justify-content:center;font-size:${Math.floor(size * 0.35)}px;font-weight:800;\'>${init}</div>'" />`;
    }
    return `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${bg}22;color:${bg};display:flex;align-items:center;justify-content:center;font-size:${Math.floor(size * 0.35)}px;font-weight:800;">${init}</div>`;
}

/** Estimated reading time */
function readTime(text) {
    if (!text) return '1 min read';
    const words = text.trim().split(/\s+/).length;
    return Math.max(1, Math.round(words / 200)) + ' min read';
}

// ═══════════════════════════════════════════════════════
// 2. WELCOME MODAL (after onboarding)
// ═══════════════════════════════════════════════════════

(function checkWelcomeModal() {
    if (localStorage.getItem('just_onboarded') === 'true') {
        localStorage.removeItem('just_onboarded');
        setTimeout(() => showWelcomeToast(), 800);
    }
})();

function showWelcomeToast() {
    const t = document.createElement('div');
    t.style.cssText = 'position:fixed;bottom:24px;right:24px;background:#12121f;border:1px solid rgba(193,255,17,.2);border-radius:12px;padding:16px 20px;display:flex;align-items:center;gap:12px;z-index:9999;animation:msgSlide .3s ease;max-width:320px;';
    t.innerHTML = `<span style="font-size:1.5rem">🎉</span><div><div style="font-weight:800;color:#f1f0ea;font-size:.88rem;">Welcome to Ghawy!</div><div style="font-size:.75rem;color:#888;">Start your learning journey now.</div></div><button onclick="this.parentElement.remove()" style="margin-left:auto;background:none;border:none;color:#666;font-size:1rem;cursor:pointer;">✕</button>`;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 6000);
}

// ═══════════════════════════════════════════════════════
// 3. USER PROFILE
// ═══════════════════════════════════════════════════════

// ── One /dashboard/summary per page load, shared ────────────────────────────
// Three separate functions each fetched this endpoint — and loadStatsCards
// fetched it four times by itself — so a dashboard load asked for the same
// payload five or six times. Measured in production nginx logs: 5-6 requests to
// /api/dashboard/summary within 6 seconds of a single page load.
//
// They are all rendering different parts of the same object, so they can share
// one in-flight promise. The cache-buster stays on that one request, keeping the
// original intent (never a stale summary on load) without paying for it five
// more times. Pass force=true to deliberately refetch after a mutation.
let _summaryPromise = null;
function getDashboardSummary(force) {
    if (!_summaryPromise || force) {
        _summaryPromise = api('/dashboard/summary?_t=' + Date.now())
            .then(r => (r.ok ? r.json() : null))
            .catch(() => null);
    }
    return _summaryPromise;
}

async function loadUserProfile() {
    try {
        const data = await getDashboardSummary();
        if (!data) return;

        renderUser(data.user);
        renderCourses(data.courses || []);
        renderAiUpdates(data.recent_posts || []);
        // Note: chat messages are loaded separately via loadGeneralMessages()
        // to ensure we get the correct 'general' channel data
    } catch (e) {
        console.error('Dashboard load error:', e);
    }
}

function renderUser(u) {
    if (!u) return;
    _currentUser = u; // cache for optimistic chat messages

    // Topbar
    const topName = document.getElementById('topbarName');
    const topNameWelcome = document.getElementById('topbarNameWelcome');
    const dropdownName = document.getElementById('dropdownName');
    if (topName) topName.textContent = u.full_name || '—';
    if (topNameWelcome) topNameWelcome.innerHTML = (u.full_name || '—') + ' 👋';
    if (dropdownName) dropdownName.textContent = u.full_name || '—';

    // Sidebar
    const sbName = document.getElementById('sidebarName');
    if (sbName) sbName.textContent = u.full_name || '—';

    const sbBadge = document.getElementById('sidebarBadge');
    if (sbBadge) sbBadge.textContent = (typeof getRoleLabel === 'function')
        ? getRoleLabel(u)
        : ((u.custom_title || '').trim() || (u.is_admin ? 'Admin' : (getBadgeLabel(u.badge) || 'Member')));

    // Level + XP
    const level = u.level || 1;
    const xp = u.xp || 0;
    const nextXp = u.next_level_xp || (level * 300);

    const sbLevel = document.getElementById('sidebarLevelNum');
    const sbLevelTitle = document.getElementById('sidebarLevelTitle');
    if (sbLevel) sbLevel.textContent = level;
    if (sbLevelTitle) sbLevelTitle.textContent = getBadgeLabel(u.badge);

    const sbXpBar = document.getElementById('sidebarXpBar');
    if (sbXpBar) sbXpBar.style.width = Math.min(100, Math.round((xp / nextXp) * 100)) + '%';

    const sbXpText = document.getElementById('sidebarXpText');
    if (sbXpText) sbXpText.textContent = `${xp} / ${nextXp} XP`;

    // Streak
    const streakEl = document.getElementById('streakCount');
    if (streakEl) streakEl.textContent = u.streak_days || 0;

    // Avatar
    const avatarHtml = buildAvatarHtml(u.full_name, u.avatar_url, u.id, 40);
    ['sidebarAvatar', 'topbarAvatar', 'dropdownAvatarDiv'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            if (typeof buildAvatarHtml === 'function') {
                el.innerHTML = buildAvatarHtml(u.full_name, u.avatar_url, u.id, 40);
            } else {
                const fullUrl = window.getAvatarSrc(u);
                el.innerHTML = `<img src="${fullUrl}" alt="" onerror="this.style.display='none'" style="width:100%;height:100%;object-fit:cover;border-radius:50%;" />`;
            }
        }
    });

    // Show/hide Team Dashboard
    const teamNav = document.getElementById('nav-team');
    if (teamNav) teamNav.style.display = u.is_admin ? '' : 'none';
}

// ═══════════════════════════════════════════════════════
// 4. STATS CARDS (5 cards from separate endpoints)
// ═══════════════════════════════════════════════════════

async function loadStatsCards() {
    const statsRow = document.getElementById('statsRow');
    if (!statsRow) return;

    // Every card on this row comes out of the one summary object. The comment
    // that used to sit here said the same thing — "use the single dashboard
    // summary for all stats to avoid N+1 calls" — and it was true of how the
    // data was *read*: only the last of five results was ever used. But the
    // fetches were left behind, so this function requested /dashboard/summary
    // four times and /courses/my once, then threw four of the five away.
    // courseCount, achievCount, streakData and xpData were bound and never
    // referenced, and /courses/my is not needed at all: the course list this
    // row counts is dashData.courses.
    const dashData = await getDashboardSummary();

    const user = dashData?.user || {};
    const courses = dashData?.courses || [];
    const inProgressCount = courses.filter(c => c.percent > 0 && c.percent < 100).length;
    const achievUnlocked = user.achievements_count || 0;
    // Auto-calculated streak from video watching (backend prefers days_streak).
    const streak = (user.days_streak ?? user.streak_days) || 0;
    const xp = user.xp || 0;

    // Total number of fully completed courses (all time), from the dashboard summary.
    const coursesCompleted = user.courses_completed || 0;

    const stats = [
        {
            icon: '<i class="fa-solid fa-book-open"></i>',
            iconClass: 'blue',
            value: inProgressCount,
            label: 'Courses In Progress'
        },
        {
            icon: '<i class="fa-solid fa-graduation-cap"></i>',
            iconClass: 'green',
            value: coursesCompleted,
            label: 'Courses Completed'
        },
        {
            icon: '<i class="fa-solid fa-trophy"></i>',
            iconClass: 'purple',
            value: achievUnlocked,
            label: 'Achievements Unlocked'
        },
        {
            icon: '<i class="fa-solid fa-fire"></i>',
            iconClass: 'orange',
            value: streak,
            label: 'Days Streak'
        }
    ];

    statsRow.innerHTML = stats.map(s => `
        <div class="stat-card">
            <div class="stat-icon ${s.iconClass}">${s.icon}</div>
            <div class="stat-info">
                <div class="stat-value">${s.value}</div>
                <div class="stat-label">${s.label}</div>
            </div>
        </div>
    `).join('');
}

// ═══════════════════════════════════════════════════════
// 5. COURSES GRID
// ═══════════════════════════════════════════════════════

// Last list handed to renderCourses. The card takes the course title, its track
// and its instructor from the catalog in the reader's language, so a language
// switch has to redraw them — community-i18n only rewrites text it has a
// dictionary entry for, and these deliberately have none.
let _dashCourses = [];
if (window.GhawyCourseCard && window.GhawyCourseCard.onLangChange) {
    window.GhawyCourseCard.onLangChange(() => {
        if (_dashCourses.length) renderCourses(_dashCourses);
    });
}

function renderCourses(courses) {
    // Only run on the dashboard page — the member courses page (dashboard-courses)
    // has its own loader (courses.js) and must not be double-rendered.
    // Note: nginx strips .html, so the path may be /dashboard-courses OR
    // /dashboard-courses.html. Match the dashboard page specifically: the PUBLIC
    // marketing page lives at /courses and never loads this script, so a bare
    // `endsWith('/courses')` check would be both wrong and misleading here.
    const path = window.location.pathname;
    if (path.endsWith('/dashboard-courses') || path.includes('dashboard-courses.html')) return;
    const grid = document.getElementById('coursesGrid');
    if (!grid) return;

    _dashCourses = courses || [];

    if (!_dashCourses.length) {
        grid.innerHTML = `<div class="empty-state-new" style="grid-column:1/-1">
            <i class="fa-solid fa-book-open"></i>
            <p>No courses enrolled yet. <a href="dashboard-courses.html" style="color:var(--accent-gold)">Browse courses →</a></p>
        </div>`;
        return;
    }

    // The card itself is drawn by src/js/course-card.js — the same renderer the
    // courses page uses. Before it existed the two pages each had their own copy
    // of this markup and had already drifted apart; whichever one you restyled,
    // the other kept the old card.
    const card = window.GhawyCourseCard;
    if (!card) return;   // script missing: leave the skeleton rather than half a card

    grid.innerHTML = _dashCourses.slice(0, 4).map(c => card.html({
        id: c.id,
        title: c.title,
        thumbnail_url: c.thumbnail_url,
        total_lessons: c.total_lessons,
        course_time: c.course_time,
        pct: Math.round(c.percent || 0),
    })).join('');
}

// ═══════════════════════════════════════════════════════
// 6. GUEST OF HONORS
// ═══════════════════════════════════════════════════════

async function loadGuests() {
    const row = document.getElementById('gohRow');
    if (!row) return;

    try {
        const res = await api('/guests/?featured=true');
        if (!res.ok) throw new Error('Failed');
        const guests = await res.json();

        if (!guests || guests.length === 0) {
            row.innerHTML = `<div class="empty-state-new"><i class="fa-solid fa-user-tie"></i><p>No featured guests yet.</p></div>`;
            return;
        }

        const colors = ['goh-av-c0', 'goh-av-c1', 'goh-av-c2', 'goh-av-c3', 'goh-av-c4'];
        row.innerHTML = guests.map((g, i) => {
            const colorClass = colors[i % colors.length];
            const init = (g.avatar_initials || initials(g.name));
            const avatarContent = g.avatar_url
                ? `<img src="${safeAvatarUrl(g.avatar_url)}" alt="${esc(g.name)}" onerror="this.outerHTML='<span>${esc(init)}</span>'" />`
                : `<span>${esc(init)}</span>`;

            return `<div class="goh-item" onclick="window.location.href='guest-of-honors.html'" title="${esc(g.name)}">
                <div class="goh-avatar ${!g.avatar_url ? colorClass : ''}" style="border-color:${g.avatar_color || ''}">
                    ${avatarContent}
                </div>
                <div class="goh-name">${esc(g.name)}</div>
                <div class="goh-role">${esc(g.title || '')}</div>
            </div>`;
        }).join('');
    } catch (e) {
        // Fall back: show placeholder guests
        row.innerHTML = ['SA', 'LF', 'AN', 'IA', 'AA'].map((init, i) => `
            <div class="goh-item">
                <div class="goh-avatar goh-av-c${i % 5}">${init}</div>
                <div class="goh-name">Guest ${i + 1}</div>
                <div class="goh-role">AI Expert</div>
            </div>`).join('');
    }
}

// ═══════════════════════════════════════════════════════
// 7. AI UPDATES
// ═══════════════════════════════════════════════════════

async function loadAiUpdates() {
    const grid = document.getElementById('aiUpdatesGrid');
    if (!grid) return;

    try {
        const res = await api('/ai-updates/posts?page=1&limit=3');
        if (!res.ok) throw new Error('Failed');
        const data = await res.json();
        const posts = data.posts || [];
        renderAiUpdates(posts);
    } catch (e) {
        // Use dashboard summary data (already rendered via renderAiUpdates)
    }
}

function renderAiUpdates(posts) {
    const grid = document.getElementById('aiUpdatesGrid');
    if (!grid) return;

    if (!posts || posts.length === 0) {
        grid.innerHTML = `<div class="empty-state-new" style="grid-column:1/-1">
            <i class="fa-solid fa-sparkles"></i>
            <p>No AI updates yet.</p>
        </div>`;
        return;
    }

    grid.innerHTML = posts.slice(0, 3).map(p => {
        const author = p.author || {};
        const authorName = author.full_name || p.author_name || 'Ghawy';
        const authorAvatar = author.avatar_url || p.author_avatar_url || null;
        const authorId = author.id || 0;
        const avHtml = buildAvatarHtml(authorName, authorAvatar, authorId, 30);
        const excerpt = (p.body || '').substring(0, 100);
        const rt = readTime(p.body || '');
        const ago = p.time_ago || timeAgo(p.created_at);
        const comments = p.comment_count || 0;
        const likes = p.like_count || p.likes_count || 0;

        return `<a class="update-card" href="ai-updates.html#post-${p.id}">
            <div class="update-author-row">
                <div class="update-av">${avHtml}</div>
                <span class="update-author-name">${esc(authorName)}</span>
                <span class="update-time">${ago}</span>
            </div>
            <div class="update-title">${esc(p.title || '')}</div>
            ${excerpt ? `<div class="update-excerpt">${esc(excerpt)}</div>` : ''}
            <div class="update-stats-row">
                <span><i class="fa-regular fa-comment"></i>${comments}</span>
                <span><i class="fa-regular fa-heart"></i>${likes}</span>
                <span class="update-read-time"><i class="fa-regular fa-clock"></i>${rt}</span>
            </div>
        </a>`;
    }).join('');
}

// ═══════════════════════════════════════════════════════
// 8. LIVE SESSION WIDGET
// ═══════════════════════════════════════════════════════

async function loadLiveSessions() {
    const widget = document.getElementById('liveSessionWidget');
    const upcomingCard = document.getElementById('upcomingCard');
    if (!widget) return;

    try {
        const res = await api('/live/sessions');
        if (!res.ok) throw new Error('Failed');
        const sessions = await res.json();

        const now = new Date();

        // Find a currently live session (status === 'live' or within window)
        // For now: first session with is_published=true and scheduled_at in past 4h
        let liveSession = null;
        let upcomingSession = null;

        for (const s of sessions) {
            if (!s.scheduled_at) continue;
            const sat = new Date(s.scheduled_at);
            const diffMs = sat - now;
            const diffMinutes = diffMs / 60000;

            // Live = within past 4 hours to +30min
            if (diffMinutes >= -240 && diffMinutes <= 30 && !liveSession) {
                liveSession = s;
            }
            // Upcoming = future sessions
            if (diffMs > 30 * 60000 && !upcomingSession) {
                upcomingSession = s;
            }
        }

        // Render live widget
        if (liveSession) {
            widget.innerHTML = `
                <div class="live-widget">
                    <div class="live-top-row">
                        <div class="live-badge-pill"><span class="live-dot-anim"></span>Live Now</div>
                        <div class="live-viewers"><i class="fa-solid fa-eye"></i> ${liveSession.attendee_count || 0} watching</div>
                    </div>
                    <div class="live-title">${esc(liveSession.title)}</div>
                    <div class="live-host">
                        <div class="live-host-av"></div>
                        With ${esc(liveSession.instructor_name || 'Instructor')}
                    </div>
                    ${liveSession.youtube_url || liveSession.zoom_url
                    ? `<a href="${esc(liveSession.youtube_url || liveSession.zoom_url)}" target="_blank" class="btn-join-live">
                                <span>Join Live</span> <span class="join-red-dot"></span>
                           </a>`
                    : `<button class="btn-join-live" onclick="showToast('Session link coming soon!', 'info')">
                                <span>Join Live</span> <span class="join-red-dot"></span>
                           </button>`}
                </div>`;
        } else {
            widget.innerHTML = `<div class="no-live-card">
                <i class="fa-regular fa-circle-play" style="font-size:1.5rem;margin-bottom:8px;display:block;color:var(--txt-muted)"></i>
                <div style="font-weight:700;margin-bottom:4px;">No Live Session Right Now</div>
                <div style="font-size:.7rem;">Check upcoming sessions below</div>
            </div>`;
        }

        // Render upcoming session
        if (upcomingSession && upcomingCard) {
            const upDate = new Date(upcomingSession.scheduled_at);
            document.getElementById('upcomingTitle').textContent = upcomingSession.title;
            document.getElementById('upcomingDate').innerHTML = `<i class="fa-regular fa-calendar"></i> ${upDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })} at ${upDate.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}`;

            // Start countdown
            startCountdown(upDate);
        } else if (upcomingCard) {
            document.getElementById('upcomingTitle').textContent = 'No upcoming sessions';
            document.getElementById('timerDisplay').textContent = '—';
        }

    } catch (e) {
        widget.innerHTML = `<div class="no-live-card">Could not load session info.</div>`;
        console.error('Live sessions error:', e);
    }
}

// ═══════════════════════════════════════════════════════
// 9. COUNTDOWN TIMER
// ═══════════════════════════════════════════════════════

let countdownInterval = null;

function startCountdown(targetDate) {
    if (countdownInterval) clearInterval(countdownInterval);
    const el = document.getElementById('timerDisplay');
    if (!el) return;

    function update() {
        const diff = Math.max(0, targetDate - Date.now()) / 1000;
        if (diff === 0) { el.textContent = 'Starting now!'; clearInterval(countdownInterval); return; }
        const h = Math.floor(diff / 3600);
        const m = Math.floor((diff % 3600) / 60);
        const s = Math.floor(diff % 60);
        el.textContent = `${h}h ${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}s`;
    }
    update();
    countdownInterval = setInterval(update, 1000);
}

// ═══════════════════════════════════════════════════════
// 10. WEBSOCKET — COMMUNITY CHAT
// ═══════════════════════════════════════════════════════

let dnWs = null;
let wsReconnectTimer = null;
let chatMessages = []; // local cache
let _currentUser = null; // populated after profile load

function connectWebSocket() {
    if (dnWs && dnWs.readyState <= 1) return; // Already connected/connecting

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    // If API is a relative path (e.g. '/api' in production), use window.location.host
    // If API is absolute (e.g. 'http://127.0.0.1:8000' in local dev), strip protocol
    const host = API.startsWith('/') ? window.location.host : API.replace(/^https?:\/\//, '');
    const wsUrl = `${protocol}//${host}/ws`;

    try {
        dnWs = new WebSocket(wsUrl);

        dnWs.onopen = () => {
            console.log('[WS] Connected to community chat');
            // 🔒 Send token as first message — keeps it out of the URL/logs
            dnWs.send(JSON.stringify({ token: localStorage.getItem('token') }));
            clearTimeout(wsReconnectTimer);
            const statusEl = document.querySelector('.chat-connecting');
            if (statusEl) statusEl.remove();
        };

        dnWs.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data);
                handleWsMessage(payload);
            } catch (e) { }
        };

        dnWs.onerror = (e) => {
            console.warn('[WS] Error', e);
        };

        dnWs.onclose = (event) => {
            // code 4003 = Account deactivated (server-forced disconnect)
            if (event.code === 4003) {
                console.warn('[WS] Account deactivated — redirecting to login');
                localStorage.removeItem('token');
                localStorage.removeItem('user');
                window.location.href = '/login';
                return; // Don't reconnect
            }
            console.log('[WS] Disconnected — reconnecting in 3s');
            scheduleWsReconnect();
        };
    } catch (e) {
        console.warn('[WS] Could not connect:', e);
        scheduleWsReconnect();
    }
}

function scheduleWsReconnect() {
    clearTimeout(wsReconnectTimer);
    wsReconnectTimer = setTimeout(connectWebSocket, 3000);
}

function handleWsMessage(payload) {
    const event = payload.event || payload.type;

    if (event === 'connected') {
        // Initial connection
        const onlineEl = document.getElementById('dashOnlineCount');
        if (onlineEl && payload.data?.online_count !== undefined) {
            onlineEl.textContent = payload.data.online_count;
        }
    }

    if (event === 'new_message') {
        const msg = payload.data || payload;
        // Only show general channel messages in the dashboard widget
        const generalId = window.__generalChannelId;
        if (generalId && msg.channel_id && msg.channel_id !== generalId) {
            if (msg.sender_id && window.currentUserId && msg.sender_id !== window.currentUserId) {
                if (typeof fetchGlobalNotifications === 'function') fetchGlobalNotifications();
                if (typeof notifyToast === 'function') {
                    notifyToast('New message from ' + (msg.sender_name || 'someone'), 'info');
                }
            }
            return; // Skip DM or other channel messages
        }
        appendChatMessage({
            id: msg.id,
            author_name: msg.sender_name || msg.author_name,
            avatar_url: msg.sender_avatar || msg.avatar_url,
            sender_id: msg.sender_id,
            sender_is_admin: msg.sender_is_admin,
            author_badge: msg.author_badge,
            content: msg.content,
            created_at: msg.created_at || new Date().toISOString()
        });
    }

    if (event === 'user_online' || event === 'user_offline') {
        // Could update online count — skip for now
        fetchOnlineCount();
    }
    
    if (event === 'message_deleted') {
        const msgId = payload.data?.message_id;
        if (msgId) {
            chatMessages = chatMessages.filter(m => m.id !== msgId);
            renderChatMessages(chatMessages);
        }
    }
}

function appendChatMessage(msg) {
    // If the server confirmed a real message, remove any matching optimistic placeholder
    if (msg.id && !String(msg.id).startsWith('__optimistic_')) {
        chatMessages = chatMessages.filter(m =>
            !(String(m.id).startsWith('__optimistic_') && m.content === msg.content)
        );
    }
    // Avoid exact duplicate real IDs
    if (msg.id && !String(msg.id).startsWith('__optimistic_') && chatMessages.some(m => m.id === msg.id)) {
        return;
    }
    chatMessages.push(msg);
    if (chatMessages.length > 20) chatMessages.shift();
    renderChatMessages(chatMessages);
}

function notifyToast(msg, type = 'info') {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:10px;pointer-events:none;';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.style.cssText = 'background:var(--bg-card,#222);color:#fff;padding:12px 20px;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.5);border-left:4px solid ' + (type === 'error' ? '#ff4d4d' : 'var(--gold,#c1ff11)') + ';animation: slideIn 0.3s ease forwards;pointer-events:auto;cursor:pointer;';
    toast.innerHTML = msg;
    toast.onclick = () => toast.remove();
    container.appendChild(toast);
    
    // Add keyframes if not exists
    if (!document.getElementById('toastStyles')) {
        const style = document.createElement('style');
        style.id = 'toastStyles';
        style.innerHTML = `
        @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        @keyframes fadeOut { from { opacity: 1; } to { opacity: 0; } }
        `;
        document.head.appendChild(style);
    }

    setTimeout(() => {
        if (toast.parentNode) {
            toast.style.animation = 'fadeOut 0.3s ease forwards';
            setTimeout(() => toast.remove(), 300);
        }
    }, 5000);
}

function renderChatMessages(messages) {
    // Dashboard-only widget: chat.html / direct-messages.html reuse the
    // #chatMessages id for the full conversation view — never touch it there.
    if (!document.getElementById('dashChatInput')) return;
    const container = document.getElementById('chatMessages');
    if (!container) return;

    if (!messages || messages.length === 0) {
        container.innerHTML = `<div class="chat-connecting">No messages yet. Say hi! 👋</div>`;
        return;
    }

    container.innerHTML = messages.map(m => {
        const avHtml = buildAvatarHtml(m.author_name, m.avatar_url, m.sender_id || 0, 28);
        // A marker becomes a fixed label (escaped, nothing member-written in it).
        // Anything else is a real message body and goes through the shared
        // escape → linkify → mentions pipeline, so URLs are clickable here the
        // same way they are in the full chat view.
        const labelled = chatLabel(m.content || '');
        const isMarker = labelled.startsWith('📷') || labelled.startsWith('🎤') || labelled.startsWith('↩️');
        let text;
        if (isMarker) {
            text = esc(labelled);
        } else if (window.formatChatText) {
            text = window.formatChatText(labelled);
        } else {
            text = window.formatAdminMentions ? window.formatAdminMentions(esc(labelled)) : esc(labelled);
        }
        
        let badgeHtml = '';
        const isAdminSender = m.sender_is_admin == true || m.sender_is_admin === 1 || (m.author_badge && String(m.author_badge).toLowerCase().includes('admin'));
        if (isAdminSender) {
            badgeHtml = `<span style="display:inline-flex; align-items:center; gap:4px; font-size:0.65rem; font-weight:600; padding:2px 6px; border-radius:4px; background:rgba(193, 255, 17, 0.1); color:#c1ff11; margin-left:6px;">Admin <i class="fa-solid fa-circle-check" style="color: #c1ff11;"></i></span>`;
        } else if (m.author_badge && (String(m.author_badge).toLowerCase().includes('pro') || String(m.author_badge).toLowerCase().includes('gold'))) {
            badgeHtml = `<span style="display:inline-flex; align-items:center; gap:4px; font-size:0.65rem; font-weight:600; padding:2px 6px; border-radius:4px; background:rgba(255, 215, 0, 0.1); color:#ffd700; margin-left:6px;">${m.author_badge}</span>`;
        } else {
            badgeHtml = `<span style="display:inline-flex; align-items:center; gap:4px; font-size:0.65rem; font-weight:500; padding:2px 6px; border-radius:4px; background:rgba(255, 255, 255, 0.05); color:#a0a0a0; margin-left:6px;">Member</span>`;
        }

        return `<div class="chat-msg">
            <div class="chat-msg-av" style="background:${avatarColor(m.sender_id || 0)}22">${avHtml}</div>
            <div class="chat-msg-body">
                <div class="chat-msg-meta" style="display:flex; align-items:center; flex-wrap:wrap; gap:4px;">
                    <span class="chat-msg-name">${esc(m.author_name || 'User')}</span>
                    ${badgeHtml}
                    <span class="chat-msg-time">${timeAgo(m.created_at)}</span>
                </div>
                <div class="chat-msg-text">${text}</div>
            </div>
        </div>`;
    }).join('');

    // Auto-scroll to bottom
    container.scrollTop = container.scrollHeight;
}

// Turn a stored marker into the label the dashboard widget shows, and hand back
// anything else unchanged for the caller to render properly.
//
// This used to be called formatChatText. As a top-level declaration in a classic
// script it became window.formatChatText — and dashboard-new.js loads AFTER
// utils.js on chat.html, direct-messages.html and dashboard.html, so it replaced
// the real one on all three. Every `window.formatChatText(...)` on those pages
// was reaching this function instead, which escapes nothing: message bodies were
// going into innerHTML raw. Renaming it is the fix; the name it shadowed is not
// one this file should be defining.
function chatLabel(text) {
    if (!text) return '';
    if (text.startsWith('[IMAGE|')) return '📷 Image';
    if (text.startsWith('[AUDIO|')) return '🎤 Voice message';
    if (text.startsWith('[REPLY|')) {
        const parts = text.split(']');
        if (parts.length > 1) return '↩️ ' + parts.slice(1).join(']').trim();
    }
    return text;
}

/** Send message via REST (dash widget uses channel_id for 'general') */
async function sendChatMessage() {
    const input = document.getElementById('dashChatInput');
    if (!input) return;
    const content = input.value.trim();
    if (!content) return;
    input.value = '';

    // Build an optimistic message from the current user's info
    const currentUser = _currentUser;
    const optimisticMsg = {
        id: '__optimistic_' + Date.now(),
        author_name: currentUser?.full_name || 'Me',
        avatar_url: currentUser?.avatar_url || null,
        sender_id: currentUser?.id || 0,
        sender_is_admin: currentUser?.is_admin || false,
        author_badge: currentUser?.badge || 'Member',
        content: content,
        created_at: new Date().toISOString()
    };

    // Show message immediately (optimistic update)
    appendChatMessage(optimisticMsg);

    // Try WebSocket first
    if (dnWs && dnWs.readyState === WebSocket.OPEN) {
        const generalChannelId = window.__generalChannelId || 1;
        dnWs.send(JSON.stringify({
            action: 'send_message',
            channel_id: generalChannelId,
            content: content
        }));
    } else {
        // Fallback: REST
        try {
            await api('/chat/messages', {
                method: 'POST',
                body: JSON.stringify({ channel: 'general', content })
            });
            // Refresh to get server-assigned ID
            const res = await api('/chat/messages?channel=general&limit=10&_t=' + Date.now());
            if (res.ok) {
                const msgs = await res.json();
                chatMessages = Array.isArray(msgs) ? msgs : [];
                renderChatMessages(chatMessages);
            }
        } catch (e) { console.error('Send error:', e); }
    }
}

// ═══════════════════════════════════════════════════════
// 11. CONTINUE LEARNING BUTTON
// ═══════════════════════════════════════════════════════

async function loadContinueLearning() {
    const btn = document.getElementById('continueLearnBtn');
    if (!btn) return;

    try {
        // Use dashboard summary courses — find first in-progress
        const data = await getDashboardSummary();
        if (!data) return;
        const inProgress = (data.courses || []).find(c => c.percent > 0 && c.percent < 100);
        if (inProgress) {
            btn.href = `course-detail.html?id=${inProgress.id}`;
        } else if (data.courses && data.courses[0]) {
            btn.href = `course-detail.html?id=${data.courses[0].id}`;
        } else {
            btn.href = 'dashboard-courses.html';
        }
    } catch (e) {
        btn.href = 'dashboard-courses.html';
    }
}

// ═══════════════════════════════════════════════════════
// 12. ONLINE COUNT
// ═══════════════════════════════════════════════════════

async function fetchOnlineCount() {
    try {
        const res = await api('/chat/online-count');
        if (!res.ok) return;
        const data = await res.json();
        const el = document.getElementById('dashOnlineCount');
        if (el) el.textContent = data.online_count || 0;
    } catch (e) { }
}

// ═══════════════════════════════════════════════════════
// 13. NOTIFICATIONS
// ═══════════════════════════════════════════════════════

function toggleNotifPanel() {
    const panel = document.getElementById('notifPanel');
    if (panel) panel.classList.toggle('open');
}

// ═══════════════════════════════════════════════════════
// 14. HAMBURGER / MOBILE SIDEBAR
// ═══════════════════════════════════════════════════════

(function initSidebar() {
    const hamburger = document.getElementById('hamburgerBtn');
    const sidebar = document.getElementById('dashSidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (!hamburger || !sidebar) return;

    hamburger.addEventListener('click', (e) => {
        e.stopPropagation();
        sidebar.classList.toggle('open');
        if (overlay) overlay.classList.toggle('visible');
        hamburger.classList.toggle('active');
    });

    if (overlay) {
        overlay.addEventListener('click', () => {
            sidebar.classList.remove('open');
            overlay.classList.remove('visible');
            hamburger.classList.remove('active');
        });
    }

    sidebar.querySelectorAll('a').forEach(el => {
        el.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                sidebar.classList.remove('open');
                if (overlay) overlay.classList.remove('visible');
                hamburger.classList.remove('active');
            }
        });
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            sidebar.classList.remove('open');
            if (overlay) overlay.classList.remove('visible');
            hamburger.classList.remove('active');
        }
    });
})();

// ═══════════════════════════════════════════════════════
// 15. AI HERO IMAGE FALLBACK
// ═══════════════════════════════════════════════════════

(function loadHeroImg() {
    const img = document.getElementById('aiHeroImg');
    if (!img) return;
    // Primary source set in HTML — if fails, hide gracefully
    img.addEventListener('error', () => { img.style.display = 'none'; });
})();

// ═══════════════════════════════════════════════════════
// 16. SEND BUTTON & ENTER KEY
// ═══════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    const sendBtn = document.getElementById('dashChatSendBtn');
    if (sendBtn) sendBtn.addEventListener('click', sendChatMessage);

    const chatInput = document.getElementById('dashChatInput');
    if (chatInput) {
        chatInput.addEventListener('keydown', e => {
            if (e.key === 'Enter') { e.preventDefault(); sendChatMessage(); }
        });
    }
});

// ═══════════════════════════════════════════════════════
// 17. LOGOUT
// ═══════════════════════════════════════════════════════

function logout() {
    if (dnWs) { try { dnWs.close(); } catch (e) { } }
    localStorage.removeItem('token');
    localStorage.removeItem('user'); window.location.href = '/login';
}

// ═══════════════════════════════════════════════════════
// 18. BADGE LABEL HELPER
// ═══════════════════════════════════════════════════════

function getBadgeLabel(badge) {
    const map = {
        member: 'Member', starter: 'Starter', explorer: 'Explorer',
        builder: 'Builder', innovator: 'Innovator', master: 'Master', legend: 'Legend'
    };
    return map[(badge || '').toLowerCase()] || 'Member';
}

// ═══════════════════════════════════════════════════════
// 19. REQUIRE ACTIVE USER CHECK
// ═══════════════════════════════════════════════════════

(async () => {
    if (typeof requireActiveUser === 'function') {
        const user = await requireActiveUser();
        if (!user) return;
    }
})();

// ═══════════════════════════════════════════════════════
// 20. FETCH GENERAL CHANNEL ID
// ═══════════════════════════════════════════════════════

/** Fetch the real ID of the 'general' channel from the API */
async function fetchGeneralChannelId() {
    // The id never changes — cache it so every page load doesn't re-fetch
    // the full channel list just for this one number.
    const cached = parseInt(localStorage.getItem('general_channel_id') || '', 10);
    if (cached) { window.__generalChannelId = cached; return; }
    try {
        const res = await api('/chat/channels');
        if (!res.ok) return;
        const channels = await res.json();
        const general = channels.find(c => c.name === 'general');
        if (general && general.id) {
            window.__generalChannelId = general.id;
            localStorage.setItem('general_channel_id', String(general.id));
            console.log('[Chat] General channel ID:', general.id);
        }
    } catch (e) {
        console.warn('[Chat] Could not fetch channels:', e);
    }
}

/** Load latest messages from the general channel */
async function loadGeneralMessages() {
    // Only the dashboard has the general-chat widget
    if (!document.getElementById('dashChatInput')) return;
    try {
        const res = await api('/chat/messages?channel=general&limit=15&_t=' + Date.now());
        if (!res.ok) return;
        const msgs = await res.json();
        if (Array.isArray(msgs) && msgs.length > 0) {
            // Map REST response fields to the widget format
            chatMessages = msgs.map(m => ({
                id: m.id,
                author_name: m.author_name,
                avatar_url: m.author_avatar_url,
                sender_id: m.author_id,
                sender_is_admin: m.sender_is_admin,
                author_badge: m.author_badge,
                content: m.content,
                created_at: m.created_at
            }));
            renderChatMessages(chatMessages);
        }
    } catch (e) {
        console.warn('[Chat] Could not load general messages:', e);
    }
}

// ═══════════════════════════════════════════════════════
// 21. INITIALISE — load all data in parallel
// ═══════════════════════════════════════════════════════

async function init() {
    if (!localStorage.getItem('token')) return;

    // Fetch general channel ID first (critical for correct message routing)
    await fetchGeneralChannelId();

    // Primary dashboard data (user + courses + posts + messages)
    const mainLoad = loadUserProfile();

    // Secondary: parallel fetches
    await Promise.allSettled([
        mainLoad,
        loadStatsCards(),
        loadGuests(),
        loadAiUpdates(),
        loadLiveSessions(),
        loadContinueLearning(),
        fetchOnlineCount(),
        loadGeneralMessages(),
    ]);

    // WebSocket after data is loaded
    connectWebSocket();
    setInterval(() => { if (!document.hidden) fetchOnlineCount(); }, 30000);
}

init().catch(e => console.error('Init error:', e));
