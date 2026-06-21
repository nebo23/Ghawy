(async () => {
    const user = await requireActiveUser();
    if (!user) return;
})();

/**
 * Build With Me (Live) - Frontend Logic
 * Uses new /live/sessions endpoints with user registration
 */

const token = localStorage.getItem('token');
if (!token) { localStorage.removeItem('user'); window.location.href = '/login'; }
const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

let liveSocket = null;
let currentTab = 'upcoming';
let allSessions = [];

document.addEventListener('DOMContentLoaded', () => {
    initBWM();
});

async function initBWM() {
    setupTabs();
    await loadSessions();
    setupCalendar();
    loadTopProjects();
    connectLiveSocket();
}

// ═══ TOAST ═══
function showToast(message, type = 'info') {
    let container = document.getElementById('toastContainerBwm');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainerBwm';
        container.style.cssText = 'position:fixed;top:20px;right:20px;z-index:99999;display:flex;flex-direction:column;gap:8px;';
        document.body.appendChild(container);
    }
    const bg = type === 'error' ? 'rgba(239,68,68,.9)' : type === 'success' ? 'rgba(34,197,94,.9)' : 'rgba(63,143,249,.9)';
    const toast = document.createElement('div');
    toast.style.cssText = `padding:12px 20px;background:${bg};color:#fff;border-radius:8px;font-size:14px;font-weight:600;box-shadow:0 4px 20px rgba(0,0,0,.3);animation:slideIn .3s;max-width:380px;`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity .3s'; setTimeout(() => toast.remove(), 300); }, 3500);
}

// --- TABS ---
function setupTabs() {
    const tabs = document.querySelectorAll('.bwm-tabs .tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentTab = tab.dataset.tab;
            renderFilteredSessions();
        });
    });
}

// --- DATA FETCHING ---
async function loadSessions() {
    const container = document.getElementById('bwmTabContent');
    container.innerHTML = `<div class="bwm-loading"><i class="fa-solid fa-circle-notch fa-spin"></i> Loading sessions...</div>`;

    try {
        const res = await fetch(API + '/live/sessions', { headers });
        if (!res.ok) throw new Error('Failed');
        allSessions = await res.json();

        // Update stats
        const statEl = document.getElementById('statSessions');
        if (statEl) statEl.textContent = allSessions.length;
        const learnersEl = document.getElementById('statLearners');
        if (learnersEl) {
            const total = allSessions.reduce((sum, s) => sum + (s.attendee_count || 0), 0);
            learnersEl.textContent = total;
        }

        renderFilteredSessions();
    } catch (e) {
        console.error('Failed to fetch sessions', e);
        container.innerHTML = `<div style="text-align:center;padding:60px 0;color:#666;"><i class="fa-regular fa-folder-open" style="font-size:2rem;margin-bottom:12px;"></i><p>Failed to load sessions.</p></div>`;
    }
}

function renderFilteredSessions() {
    const container = document.getElementById('bwmTabContent');
    const now = new Date();

    let sessions = allSessions;
    if (currentTab === 'upcoming') {
        sessions = allSessions.filter(s => !s.scheduled_at || new Date(s.scheduled_at) >= now);
    } else if (currentTab === 'past') {
        sessions = allSessions.filter(s => s.scheduled_at && new Date(s.scheduled_at) < now);
    } else if (currentTab === 'booked') {
        sessions = allSessions.filter(s => s.is_registered);
    }

    renderSessions(sessions, currentTab, container);
}

// --- RENDERING ---
function renderSessions(sessions, tab, container) {
    if (!sessions || sessions.length === 0) {
        const labels = {
            upcoming: 'No upcoming sessions.',
            past: 'No past sessions.',
            booked: 'You haven\'t registered for any sessions yet.'
        };
        container.innerHTML = `
            <div style="text-align:center; padding: 60px 0; color: #666;">
                <i class="fa-regular fa-folder-open" style="font-size: 2rem; margin-bottom: 12px;"></i>
                <p>${labels[tab] || 'No sessions found.'}</p>
            </div>
        `;
        return;
    }

    let html = `<div class="section-title"><span>${tab === 'upcoming' ? 'Upcoming Sessions' : tab === 'booked' ? 'My Registrations' : 'Past Sessions'}</span></div>`;
    html += `<div class="upcoming-list">`;

    sessions.forEach(s => {
        const scheduled = s.scheduled_at ? new Date(s.scheduled_at) : null;
        const day = scheduled ? scheduled.getDate() : '—';
        const month = scheduled ? scheduled.toLocaleString('en-US', { month: 'short' }).toUpperCase() : '';
        const time = scheduled ? scheduled.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'TBD';

        const registerBtn = s.is_registered
            ? `<button class="btn-reminder active" onclick="unregisterSession(${s.id}, this)" style="background:rgba(34,197,94,.15);color:#22c55e;border-color:#22c55e33;">✅ Registered</button>`
            : `<button class="btn-reminder" onclick="registerSession(${s.id}, this)"><i class="fa-regular fa-hand"></i> RSVP</button>`;

        const joinBtn = s.is_registered && (s.youtube_url || s.zoom_url)
            ? `<a href="${s.zoom_url || s.youtube_url}" target="_blank" class="btn-primary" style="margin-top:8px;font-size:13px;padding:8px 16px;display:inline-block;text-decoration:none;">🚀 Join Now</a>`
            : '';

        html += `
            <div class="upcoming-card">
                <div class="date-block">
                    <div class="day">${day}</div>
                    <div class="month">${month}</div>
                </div>
                <div class="session-details">
                    <h3>${escapeHtml(s.title)}</h3>
                    <p class="session-desc">${escapeHtml((s.description || '').substring(0, 120))}${(s.description || '').length > 120 ? '...' : ''}</p>
                    <div style="font-size:12px;color:#888;margin-top:4px;">
                        <i class="fa-solid fa-users" style="color:#3f8ff9;"></i> ${s.attendee_count || 0} registered
                    </div>
                </div>
                <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px;">
                    <div class="session-time">${time} EET</div>
                    ${registerBtn}
                    ${joinBtn}
                </div>
            </div>
        `;
    });
    html += `</div>`;

    container.innerHTML = html;
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// --- REGISTRATION ---
async function registerSession(sessionId, btn) {
    try {
        const res = await fetch(API + `/live/sessions/${sessionId}/register`, {
            method: 'POST', headers
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed');
        }
        btn.classList.add('active');
        btn.innerHTML = '✅ Registered';
        btn.style.background = 'rgba(34,197,94,.15)';
        btn.style.color = '#22c55e';
        btn.onclick = () => unregisterSession(sessionId, btn);
        showToast('Registered successfully! ✅', 'success');

        // Update local cache
        const s = allSessions.find(s => s.id === sessionId);
        if (s) { s.is_registered = true; s.attendee_count = (s.attendee_count || 0) + 1; }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

async function unregisterSession(sessionId, btn) {
    try {
        const res = await fetch(API + `/live/sessions/${sessionId}/register`, {
            method: 'DELETE', headers
        });
        if (!res.ok) throw new Error('Failed');
        btn.classList.remove('active');
        btn.innerHTML = '<i class="fa-regular fa-hand"></i> RSVP';
        btn.style.background = '';
        btn.style.color = '';
        btn.onclick = () => registerSession(sessionId, btn);
        showToast('Registration cancelled', 'info');

        const s = allSessions.find(s => s.id === sessionId);
        if (s) { s.is_registered = false; s.attendee_count = Math.max(0, (s.attendee_count || 1) - 1); }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

// --- RIGHT SIDEBAR WIDGETS ---
function setupCalendar() {
    const daysContainer = document.getElementById('calendarDays');
    if (!daysContainer) return;
    const days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];
    const now = new Date();
    const dayOfWeek = (now.getDay() + 6) % 7; // 0=Mon

    let html = '';
    for (let i = 0; i < 7; i++) {
        const d = new Date(now);
        d.setDate(d.getDate() - dayOfWeek + i);
        const active = i === dayOfWeek ? 'active' : '';
        html += `<div class="cal-day ${active}"><span class="name">${days[i]}</span><span class="num">${d.getDate()}</span></div>`;
    }
    daysContainer.innerHTML = html;

    // Dynamic schedule from upcoming sessions
    const scheduleContainer = document.getElementById('scheduleList');
    if (!scheduleContainer) return;

    const upcoming = allSessions.filter(s => s.scheduled_at && new Date(s.scheduled_at) >= now).slice(0, 3);
    if (!upcoming.length) {
        scheduleContainer.innerHTML = '<div style="text-align:center;color:#555;padding:20px;">No upcoming sessions</div>';
        return;
    }

    scheduleContainer.innerHTML = upcoming.map(s => {
        const dt = new Date(s.scheduled_at);
        const time = dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        return `
        <div class="schedule-item">
            <div class="schedule-status">${time}</div>
            <div class="schedule-title">${escapeHtml(s.title)}</div>
            <div class="schedule-meta">
                <span style="font-size:12px;color:#888;"><i class="fa-solid fa-users"></i> ${s.attendee_count || 0}</span>
            </div>
        </div>`;
    }).join('');
}

function loadTopProjects() {
    const container = document.getElementById('topProjectsList');
    if (!container) return;
    container.innerHTML = `
        <div class="project-item">
            <div class="project-rank">1</div>
            <div class="project-icon"><i class="fa-solid fa-robot"></i></div>
            <div class="project-info">
                <div class="project-title">AI Lead Generation Bot</div>
                <div class="project-author">Built by Community</div>
            </div>
            <div class="project-rating"><i class="fa-solid fa-star"></i> 4.9</div>
        </div>
        <div class="project-item">
            <div class="project-rank">2</div>
            <div class="project-icon"><i class="fa-solid fa-chart-pie"></i></div>
            <div class="project-info">
                <div class="project-title">Smart Data Analyzer</div>
                <div class="project-author">Built by Mostafa</div>
            </div>
            <div class="project-rating"><i class="fa-solid fa-star"></i> 4.8</div>
        </div>
    `;
}

// --- WEBSOCKET ---
function connectLiveSocket() {
    const token = localStorage.getItem('token');
    if (!token) return;

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const apiHost = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
        ? '127.0.0.1:8000'
        : window.location.host;
    const wsUrl = `${wsProtocol}//${apiHost}/api/live-sessions/ws/${token}`;

    liveSocket = new WebSocket(wsUrl);

    liveSocket.onopen = () => console.log("Connected to Live WS");

    liveSocket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.event === "viewer_count") {
                const el = document.getElementById(`viewers-${data.session_id}`);
                if (el) el.innerText = data.count;
            }
        } catch (e) { console.error("WS error", e); }
    };

    liveSocket.onclose = () => {
        console.log("Disconnected from Live WS. Reconnecting in 5s...");
        setTimeout(connectLiveSocket, 5000);
    };
}
