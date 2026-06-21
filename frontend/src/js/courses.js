(async () => {
  const user = await requireActiveUser();
  if (!user) return;
})();

// ═══ AUTH GUARD ═══
const token = getToken();
if (!token) { localStorage.removeItem('user'); window.location.href = '/login'; }

const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

async function apiFetch(url, opts = {}) {
    opts.headers = { ...headers, ...opts.headers };
    const res = await fetch(API + url, opts);
    if (res.status === 401) { localStorage.removeItem('token'); localStorage.removeItem('user'); window.location.href = '/login'; }
    return res;
}

function logout() { localStorage.removeItem('token'); localStorage.removeItem('user'); window.location.href = '/login'; }

// ═══ LOAD PROFILE ═══
async function loadProfile() {
    try {
        const res = await apiFetch('/profile/me');
        if (!res.ok) return;
        const u = await res.json();
        const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        setTxt('sidebarName', u.full_name);
        setTxt('topbarName', u.full_name);
        setTxt('dropdownName', u.full_name);
        
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
                if (typeof buildAvatarHtml === 'function') {
                    el.innerHTML = buildAvatarHtml(u.full_name, u.avatar_url, u.id, 40);
                } else {
                    const fullUrl = window.getAvatarSrc(u);
                    el.innerHTML = `<img src="${fullUrl}" alt="" onerror="this.style.display='none'" style="width:100%;height:100%;object-fit:cover;border-radius:50%;" />`;
                }
            }
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
            const thumb = c.thumbnail_url ? (c.thumbnail_url.startsWith('/') ? API + c.thumbnail_url : c.thumbnail_url) : '';
            return `<div class="course-card" onclick="window.location.href='course-detail.html?id=${c.id}'">
                <div class="course-thumb">
                    ${thumb ? `<img src="${thumb}" alt="${c.title}" style="width:100%;height:100%;object-fit:cover;z-index:0;position:relative;" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"/>` : ''}
                    <div style="position:absolute;inset:0;display:${thumb ? 'none' : 'flex'};align-items:center;justify-content:center;font-size:3rem;z-index:1">${icon}</div>
                    <div class="course-thumb-overlay"></div>

                </div>
                <div class="course-body">
                    <h3>${c.title}</h3>
                    <p style="font-size:.75rem;color:var(--text-muted);margin-bottom:8px;line-height:1.4">${desc}</p>
                    <div class="course-meta" style="display:flex; justify-content:space-between; align-items:center; width:100%;">
                        <span><i class="fa-solid fa-book" style="margin-right:6px; color:var(--gold);"></i>${c.total_lessons} Lessons</span>
                        ${c.course_time ? `<span><i class="fa-regular fa-clock" style="margin-right:6px; color:var(--gold);"></i>${c.course_time}</span>` : ''}
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
                const pct = Math.round(prog.percentage || 0);
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



