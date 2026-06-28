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
            const thumb = c.thumbnail_url
                ? (c.thumbnail_url.startsWith('/') ? API + c.thumbnail_url : c.thumbnail_url)
                : '';

            let status = 'not-started';
            let statusLabel = 'Not Started';

            return `<div class="course-card" onclick="window.location.href='course-detail.html?id=${c.id}'" role="button" tabindex="0">
                <div class="course-thumb-wrap">
                    ${thumb ? `<img src="${thumb}" alt="${window.escapeHtml ? window.escapeHtml(c.title) : c.title}" class="course-thumb-img" onerror="this.style.display='none';"/>` : ''}
                    <div class="course-pct-badge" style="display:none">0%</div>
                </div>
                <div class="course-body">
                    <h3>${window.escapeHtml ? window.escapeHtml(c.title) : c.title}</h3>
                    <div class="course-meta-row" style="display:flex; justify-content:space-between; align-items:center; width:100%; margin-bottom:8px;">
                        <span><i class="fa-solid fa-book" style="margin-right:6px; color:var(--gold);"></i>${c.total_lessons || 0} Lessons</span>
                        ${c.course_time ? `<span><i class="fa-regular fa-clock" style="margin-right:6px; color:var(--gold);"></i>${c.course_time}</span>` : ''}
                    </div>
                    <div class="course-prog-wrap">
                        <div class="course-prog-bg">
                            <div class="course-prog-fill" style="width:0%"></div>
                        </div>
                    </div>
                </div>
                <div class="course-footer" style="display:none">
                    <span class="course-status ${status}">${statusLabel}</span>
                    <span class="course-action">
                        Start Course <i class="fa-solid fa-play"></i>
                    </span>
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
                    card.querySelector('.course-prog-fill').style.width = pct + '%';
                    
                    const badge = card.querySelector('.course-pct-badge');
                    if (pct > 0) {
                        badge.style.display = 'block';
                        badge.textContent = pct + '%';
                        
                        const statusEl = card.querySelector('.course-status');
                        const actionEl = card.querySelector('.course-action');
                        
                        if (pct >= 100) {
                            statusEl.className = 'course-status completed';
                            statusEl.textContent = 'Completed';
                            actionEl.innerHTML = 'Review <i class="fa-solid fa-arrow-right"></i>';
                        } else {
                            statusEl.className = 'course-status in-progress';
                            statusEl.textContent = 'In Progress';
                            actionEl.innerHTML = 'Continue <i class="fa-solid fa-arrow-right"></i>';
                        }
                    }
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



