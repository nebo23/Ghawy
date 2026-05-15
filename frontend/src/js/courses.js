// ═══ AUTH GUARD ═══
const token = getToken();
if (!token) window.location.href = 'login.html';

const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

async function apiFetch(url, opts = {}) {
    opts.headers = { ...headers, ...opts.headers };
    const res = await fetch(API + url, opts);
    if (res.status === 401) { localStorage.removeItem('token'); window.location.href = 'login.html'; }
    return res;
}

function logout() { localStorage.removeItem('token'); window.location.href = 'login.html'; }

// ═══ LOAD PROFILE ═══
async function loadProfile() {
    try {
        const res = await apiFetch('/profile/me');
        if (!res.ok) return;
        const u = await res.json();
        const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        setTxt('sidebarName', u.full_name);
        setTxt('sidebarBadge', u.badge || 'Member');
        setTxt('topbarName', u.full_name);
        setTxt('streakCount', u.streak_days || 0);
        ['sidebarAvatar', 'topbarAvatar'].forEach(id => {
            const el = document.getElementById(id);
            if (el && u.avatar_url) el.innerHTML = `<img src="${u.avatar_url}" alt=""/>`;
        });
    } catch (e) { console.error(e); }
}

// ═══ COURSE ICONS ═══
const courseIcons = {
    'automation': '⚡', 'prompt': '✍️', 'aaa': '🏢', 'foundation': '🧠',
    'ai': '🤖', 'agent': '🤖', 'default': '📚'
};
function getCourseIcon(title) {
    const t = title.toLowerCase();
    for (const [key, icon] of Object.entries(courseIcons)) {
        if (t.includes(key)) return icon;
    }
    return courseIcons.default;
}

// ═══ LOAD COURSES ═══
async function loadCourses() {
    try {
        const res = await apiFetch('/courses');
        const courses = await res.json();
        const grid = document.getElementById('coursesGrid');

        if (!courses || courses.length === 0) {
            grid.innerHTML = '<div class="empty-state"><i class="fa-solid fa-graduation-cap"></i><p>No courses available yet</p></div>';
            return;
        }

        grid.innerHTML = courses.map(c => {
            const icon = getCourseIcon(c.title);
            const desc = c.description ? c.description.substring(0, 80) + '...' : '';
            return `<div class="course-card" onclick="window.location.href='course-detail.html?id=${c.id}'">
                <div class="course-thumb">
                    <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:3rem;z-index:1">${icon}</div>
                    <div class="course-thumb-overlay"></div>
                    <div style="position:absolute;top:10px;left:10px;background:var(--gold);color:#000;padding:3px 10px;border-radius:6px;font-size:.7rem;font-weight:800;z-index:2">AI</div>
                </div>
                <div class="course-body">
                    <h3>${c.title}</h3>
                    <p style="font-size:.75rem;color:var(--text-muted);margin-bottom:8px;line-height:1.4">${desc}</p>
                    <div class="course-meta">
                        <span><i class="fa-solid fa-book"></i> ${c.total_lessons} Lessons</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:10px;margin-top:8px">
                        <div class="course-progress" style="flex:1"><div class="course-progress-bar" style="width:0%"></div></div>
                        <span class="course-progress-text" style="min-width:30px">0%</span>
                    </div>
                </div>
            </div>`;
        }).join('');

        // Load progress for each course
        for (const c of courses) {
            try {
                const pRes = await apiFetch(`/courses/${c.id}/progress`);
                const prog = await pRes.json();
                const pct = Math.round(prog.percent || 0);
                const card = grid.querySelector(`[onclick*="id=${c.id}"]`);
                if (card) {
                    card.querySelector('.course-progress-bar').style.width = pct + '%';
                    card.querySelector('.course-progress-text').textContent = pct + '%';
                }
            } catch (e) { /* skip */ }
        }
    } catch (e) { console.error('Course load error:', e); }
}

// ═══ HAMBURGER ═══
const hamburger = document.getElementById('hamburgerDash');
const sidebar = document.getElementById('dashSidebar');
if (hamburger) hamburger.addEventListener('click', () => sidebar.classList.toggle('open'));

// ═══ INIT ═══
loadProfile();
loadCourses();



