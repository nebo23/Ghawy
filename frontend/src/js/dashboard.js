(async () => {
    const user = await requireActiveUser();
    if (!user) return;
})();

// ═══ AUTH GUARD ═══
const token = localStorage.getItem('token');
if (!token) window.location.href = 'login.html';

const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

async function apiFetch(url, opts = {}) {
    opts.headers = { ...headers, ...opts.headers };
    const res = await fetch(API + url, opts);
    if (res.status === 401) { localStorage.removeItem('token'); window.location.href = 'login.html'; }
    return res;
}

// ═══ WELCOME MODAL (after onboarding) ═══
if (localStorage.getItem('just_onboarded') === 'true') {
    localStorage.removeItem('just_onboarded');
    showWelcomeModal();
}

async function showWelcomeModal() {
    let avatarHtml = '<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:2rem;color:var(--gold);">🎉</div>';
    let name = '';
    try {
        const res = await fetch(`${API}/profile/me`, { headers });
        if (res.ok) {
            const u = await res.json();
            name = u.full_name || '';
            if (u.avatar_url) avatarHtml = `<img src="${u.avatar_url}" alt="" style="width:100%;height:100%;object-fit:cover;"/>`;
        }
    } catch (e) { }

    const overlay = document.createElement('div');
    overlay.className = 'ob-modal-overlay';
    overlay.innerHTML = `
        <div style="background:#0a0a0a;border:1px solid rgba(193,255,17,0.2);border-radius:20px;padding:40px;max-width:420px;width:90%;text-align:center;animation:obFadeUp 0.4s ease;">
            <div style="font-size:2.5rem;margin-bottom:12px;">🎉</div>
            <h2 style="font-size:1.4rem;font-weight:900;color:#f1f0ea;margin-bottom:8px;">Welcome to Ghawy!</h2>
            <div style="width:80px;height:80px;border-radius:50%;margin:16px auto;border:3px solid #c1ff11;overflow:hidden;box-shadow:0 0 20px rgba(193,255,17,0.2);">${avatarHtml}</div>
            <p style="font-size:1rem;color:#f1f0ea;margin-bottom:6px;">Welcome ${name}! 👋</p>
            <p style="font-size:0.85rem;color:#888;margin-bottom:24px;">Start your journey by watching the intro video in the Start Here section</p>
            <button onclick="window.location.href='chat.html?v=4&channel=start_here'" style="width:100%;background:#c1ff11;color:#000;border:none;border-radius:12px;padding:14px;font-family:'Cairo',sans-serif;font-size:0.95rem;font-weight:800;cursor:pointer;margin-bottom:12px;">🚀 Go to Start Here</button>
            <button onclick="this.closest('.ob-modal-overlay').remove()" style="background:none;border:none;color:#888;font-family:'Cairo',sans-serif;font-size:0.85rem;cursor:pointer;">Skip</button>
        </div>
    `;
    document.body.appendChild(overlay);
    // Load onboarding CSS for modal styles
    if (!document.querySelector('link[href*="onboarding.css"]')) {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = 'src/css/onboarding.css';
        document.head.appendChild(link);
    }
}

// ═══ LOAD DASHBOARD ═══
async function loadDashboard() {
    try {
        const res = await apiFetch(`/dashboard/summary?_t=${Date.now()}`);
        if (!res.ok) return;
        const data = await res.json();
        renderUser(data.user);
        renderCourses(data.courses);
        renderPosts(data.recent_posts);
        renderChatPreview(data.recent_messages ? data.recent_messages.reverse() : []);
    } catch (e) { console.error('Dashboard load error:', e); }
}

function renderUser(u) {
    const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    setTxt('sidebarName', u.full_name);
        setTxt('topbarName', u.full_name);
        
        // Update Badge
        const badgeLabel = getBadgeLabel(u.badge);
        const badgeEl = document.getElementById('sidebarBadge');
        if (badgeEl) {
            badgeEl.innerHTML = `<span>${badgeLabel}</span>`;
        }

        // Update Level & XP
        const level = u.level || 1;
        const xp = u.xp || 0;
        const nextLevelXp = u.next_level_xp || (level * 100);
        
        setTxt('sidebarLevelNum', level);
        setTxt('sidebarLevelTitle', badgeLabel);
        setTxt('sidebarXpText', `${xp} / ${nextLevelXp} XP`);
        
        const xpBar = document.getElementById('sidebarXpBar');
        if (xpBar) {
            const pct = Math.min(100, Math.round((xp / nextLevelXp) * 100));
            xpBar.style.width = `${pct}%`;
        }

        // Update Streak
        setTxt('streakCount', u.streak_days || 0);
        
        ['sidebarAvatar', 'topbarAvatar', 'dropdownAvatarDiv'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                const fullUrl = window.getAvatarSrc(u);
                el.innerHTML = `<img src="${fullUrl}" alt="" />`;
            }
        });
}

function renderCourses(courses) {
    const grid = document.getElementById('coursesGrid');
    const empty = document.getElementById('coursesEmpty');
    if (!courses || courses.length === 0) { if (empty) empty.style.display = ''; return; }

    grid.innerHTML = courses.map(c => {
        const pct = Math.round(c.percent || 0);
        const thumb = c.thumbnail_url ? (c.thumbnail_url.startsWith('/') ? API + c.thumbnail_url : c.thumbnail_url) : '';
        return `<div class="course-card" onclick="window.location.href='course-detail.html?id=${c.id}'">
            <div class="course-thumb">${thumb ? `<img src="${thumb}" alt="${c.title}"/>` : ''}<div class="course-thumb-overlay"></div>
                <div style="position:absolute;top:10px;left:10px;background:var(--gold);color:#000;padding:3px 10px;border-radius:6px;font-size:.7rem;font-weight:800">AI</div>
            </div>
            <div class="course-body">
                <h3>${c.title}</h3>
                <div class="course-meta" style="display:flex;justify-content:space-between;width:100%;">
                    <span><i class="fa-solid fa-book"></i> ${c.total_lessons} Lessons</span>
                    <span>${c.completed_lessons || 0}/${c.total_lessons} Completed</span>
                </div>
                <div style="display:flex;align-items:center;gap:10px;margin-top:8px;">
                    <div class="course-progress" style="flex:1"><div class="course-progress-bar" style="width:${pct}%"></div></div>
                    <span style="font-size:.72rem;color:var(--text-muted)">${pct}%</span>
                </div>
            </div>
        </div>`;
    }).join('');
}

function renderPosts(posts) {
    const grid = document.getElementById('aiUpdatesGrid');
    if (!grid) return;

    if (!posts || posts.length === 0) {
        // Show placeholder AI updates
        grid.innerHTML = [
            { icon: '🤖', source: 'OpenAI', title: 'OpenAI launches new reasoning model', desc: 'Stronger, faster and more accurate than ever.', time: '2h ago' },
            { icon: '🧠', source: 'Anthropic', title: 'Anthropic releases Claude 3.5', desc: 'The most advanced Claude model yet.', time: '5h ago' },
            { icon: '🔧', source: 'Tools', title: 'Revolutionary AI tool for creators', desc: 'Create, edit and automate like never before.', time: '1d ago' },
            { icon: '🌐', source: 'Google', title: 'New Gemini features announced', desc: 'Google\'s latest updates will blow your mind.', time: '1d ago' },
        ].map(p => `<div class="post-card-dash" onclick="window.location.href='ai-updates.html?v=5'" style="cursor:pointer">
            <div class="post-author"><div class="avatar-sm" style="display:flex;align-items:center;justify-content:center;font-size:1rem">${p.icon}</div> ${p.source}</div>
            <h4>${p.title}</h4>
            <div class="post-preview">${p.desc}</div>
            <div class="post-stats"><span>${p.time}</span><span>${p.source}</span></div>
        </div>`).join('');
        return;
    }

    grid.innerHTML = posts.map(p => {
        // Build avatar HTML
        let avatarHtml = '';
        const avUrl = p.author_avatar_url;
        const selAv = p.author_selected_avatar;
        if (avUrl) {
            const fullUrl = avUrl.startsWith('http') ? avUrl : API + avUrl;
            avatarHtml = `<img src="${fullUrl}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;" />`;
        } else if (selAv) {
            avatarHtml = `<img src="./imgs/avatars/${selAv}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;" />`;
        } else {
            const initials = (p.author_name || '?').split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase();
            avatarHtml = `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:.65rem;font-weight:700;color:var(--gold);">${initials}</div>`;
        }

        // Truncate body for preview
        const bodyPreview = p.body ? (p.body.length > 80 ? p.body.substring(0, 80) + '...' : p.body) : '';

        return `<div class="post-card-dash" onclick="window.location.href='ai-updates.html?v=5#post-${p.id}'" style="cursor:pointer">
            <div class="post-author">
                <div class="avatar-sm" style="overflow:hidden;">${avatarHtml}</div>
                <span>${p.author_name || 'Unknown'}</span>
            </div>
            <h4>${p.title}</h4>
            ${bodyPreview ? `<div class="post-preview">${bodyPreview}</div>` : ''}
            <div class="post-stats">
                <span><i class="fa-solid fa-heart"></i> ${p.likes_count || 0}</span>
                <span><i class="fa-regular fa-comment"></i> ${p.comment_count || 0}</span>
                <span>${timeAgo(p.created_at)}</span>
            </div>
        </div>`;
    }).join('');
}

function renderChatPreview(messages) {
    const el = document.getElementById('chatPreview');
    if (!el) return;

    // Show channels with last message
    const channels = [
        { name: 'general', icon: '#' },
        { name: 'ai-tools', icon: '#' },
        { name: 'projects', icon: '#' },
    ];

    if (!messages || messages.length === 0) {
        el.innerHTML = channels.map(ch => `<div class="chat-channel-item" onclick="window.location.href='chat.html?v=4'" style="cursor:pointer">
            <span class="chat-channel-icon">${ch.icon}</span>
            <div class="chat-channel-info">
                <div class="chat-channel-name">${ch.name}</div>
                <div class="chat-channel-msg">No messages yet</div>
            </div>
            <i class="fa-solid fa-chevron-right" style="color:var(--text-muted);font-size:.6rem"></i>
        </div>`).join('');
        return;
    }

    el.innerHTML = messages.map(m => {
        let avatarHtml = '';
        const avUrl = m.avatar_url || m.author_avatar_url;
        if (avUrl) {
            const fullUrl = avUrl.startsWith('http') ? avUrl : API + avUrl;
            avatarHtml = `<img src="${fullUrl}"/>`;
        } else {
            const initials = (m.author_name || '?').split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase();
            avatarHtml = `<div style="font-size:0.6rem;font-weight:bold;color:var(--gold);">${initials}</div>`;
        }

        let text = formatPreviewText(m.content);

        return `<div class="chat-msg-preview" onclick="window.location.href='chat.html?v=4&channel=${m.channel}'" style="cursor:pointer">
        <div class="av">${avatarHtml}</div>
        <div class="info">
            <div class="name">${m.author_name || 'Unknown'}</div>
            <div class="txt">${escHtml(text)}</div>
        </div>
        <span class="time">${timeAgo(m.created_at)}</span>
    </div>`}).join('');
}

function escHtml(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

function generateInitialsAvatar(name) {
    const canvas = document.createElement('canvas');
    canvas.width = 88; canvas.height = 88;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#1a1a1a';
    ctx.beginPath(); ctx.arc(44, 44, 44, 0, Math.PI * 2); ctx.fill();
    const initials = (name || '?').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
    ctx.fillStyle = '#c1ff11'; ctx.font = 'bold 36px "Cairo", sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(initials, 44, 44 + 4);
    return canvas.toDataURL();
}

function formatPreviewText(text) {
    if (!text) return '';
    if (text.startsWith('[IMAGE|')) return '📷 Image';
    if (text.startsWith('[AUDIO|')) return '🎤 Voice message';
    if (text.startsWith('[REPLY|')) {
        const parts = text.split(']');
        if (parts.length > 1) return '↩️ ' + parts.slice(1).join(']').trim();
    }
    return text;
}



function timeAgo(dt) {
    if (!dt) return '';
    if (typeof dt === 'string' && !dt.endsWith('Z') && !dt.includes('+')) dt += 'Z';
    const diff = (Date.now() - new Date(dt).getTime()) / 1000;
    if (diff < 60) return 'Now';
    if (diff < 3600) return Math.floor(diff / 60) + ' Minute';
    if (diff < 86400) return Math.floor(diff / 3600) + ' Hour';
    return Math.floor(diff / 86400) + ' Day';
}

// ═══ ONLINE COUNT ═══
async function fetchOnlineCount() {
    try {
        const res = await apiFetch('/chat/online-count');
        const data = await res.json();
        const el = document.getElementById('dashOnlineCount');
        if (el) el.textContent = data.online_count || 0;
    } catch (e) { }
}

// ═══ COUNTDOWN TIMER ═══
function startCountdown() {
    const timerEl = document.getElementById('upcomingTimer');
    if (!timerEl) return;
    // Set target to next 8 PM today or tomorrow
    const now = new Date();
    const target = new Date();
    target.setHours(20, 0, 0, 0);
    if (now >= target) target.setDate(target.getDate() + 1);

    setInterval(() => {
        const diff = Math.max(0, target - Date.now()) / 1000;
        const h = Math.floor(diff / 3600);
        const m = Math.floor((diff % 3600) / 60);
        const s = Math.floor(diff % 60);
        timerEl.innerHTML = `<span class="timer-badge">⏳</span> ${h}h ${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}s`;
    }, 1000);
}

// ═══ TABS ═══
document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
        t.classList.add('active');
    });
});

// ═══ FILTER PILLS ═══
document.querySelectorAll('.filter-pill').forEach(p => {
    p.addEventListener('click', () => {
        document.querySelectorAll('.filter-pill').forEach(x => x.classList.remove('active'));
        p.classList.add('active');
    });
});

// ═══ HAMBURGER ═══
(function initSidebar() {
    const hamburger = document.getElementById('hamburgerBtn');
    const sidebar = document.getElementById('dashSidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (!hamburger || !sidebar) return;

    const newHamburger = hamburger.cloneNode(true);
    hamburger.parentNode.replaceChild(newHamburger, hamburger);

    newHamburger.addEventListener('click', (e) => {
        e.stopPropagation();
        sidebar.classList.toggle('open');
        if (overlay) overlay.classList.toggle('visible');
        newHamburger.classList.toggle('active');
    });

    if (overlay) {
        overlay.addEventListener('click', () => {
            sidebar.classList.remove('open');
            overlay.classList.remove('visible');
            newHamburger.classList.remove('active');
        });
    }

    sidebar.querySelectorAll('a, button').forEach(el => {
        el.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                sidebar.classList.remove('open');
                if (overlay) overlay.classList.remove('visible');
                newHamburger.classList.remove('active');
            }
        });
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            sidebar.classList.remove('open');
            if (overlay) overlay.classList.remove('visible');
            newHamburger.classList.remove('active');
        }
    });
})();

// ═══ DASHBOARD CHAT SEND ═══
async function sendDashboardMessage() {
    const input = document.getElementById('dashChatInput');
    if (!input) return;
    const content = input.value.trim();
    if (!content) return;
    input.value = '';
    try {
        await apiFetch('/chat/messages', {
            method: 'POST',
            body: JSON.stringify({ channel: 'general', content })
        });
        // Refresh chat preview
        const res = await apiFetch(`/chat/messages?channel=general&limit=4&_t=${Date.now()}`);
        const msgs = await res.json();
        // /chat/messages returns chronological, which is what we want for dashboard
        renderChatPreview(msgs);
    } catch (e) { console.error('Send error:', e); }
}

const dashSendBtn = document.getElementById('dashChatSendBtn');
if (dashSendBtn) dashSendBtn.addEventListener('click', sendDashboardMessage);

const dashChatInput = document.getElementById('dashChatInput');
if (dashChatInput) {
    dashChatInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') { e.preventDefault(); sendDashboardMessage(); }
    });
}

// ═══ LOGOUT ═══
function logout() { localStorage.removeItem('token'); window.location.href = 'login.html'; }

// ═══ INIT ═══
loadDashboard();
fetchOnlineCount();
setInterval(fetchOnlineCount, 30000);
startCountdown();


