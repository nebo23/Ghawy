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

// ═══ LOAD COURSES ═══
async function loadCourses() {
    const grid = document.getElementById('coursesGrid');
    const card = window.GhawyCourseCard;
    if (!grid || !card) return;
    grid.innerHTML = card.skeleton(8);

    try {
        const res = await apiFetch('/courses');
        const courses = await res.json();

        if (!courses || courses.length === 0) {
            grid.innerHTML = '<div class="empty-state"><i class="fa-solid fa-graduation-cap"></i><p>No courses available yet</p></div>';
            return;
        }

        // One request for every course's progress instead of one request per
        // course inside a loop — see GET /courses/progress/summary. Progress is
        // enrichment: if it fails the cards still render, with empty bars.
        let progress = [];
        try {
            const pRes = await apiFetch('/courses/progress/summary');
            if (pRes.ok) progress = await pRes.json();
        } catch (e) { /* bars stay at zero */ }
        const pct = new Map(progress.map(p => [p.course_id, Math.round(p.percentage || 0)]));

        _courses = courses.map(c => ({
            id: c.id,
            title: c.title,
            thumbnail_url: c.thumbnail_url,
            total_lessons: c.total_lessons,
            course_time: c.course_time,
            pct: pct.get(c.id) || 0,
        }));
        grid.innerHTML = _courses.map(c => card.html(c)).join('');
    } catch (e) {
        console.error('Course load error:', e);
    }
}

// The card takes the course title, its track and its instructor from the
// catalog in the reader's language, so a language switch has to redraw them.
let _courses = [];
if (window.GhawyCourseCard) {
    window.GhawyCourseCard.onLangChange(() => {
        const grid = document.getElementById('coursesGrid');
        if (grid && _courses.length) grid.innerHTML = _courses.map(c => window.GhawyCourseCard.html(c)).join('');
    });
}

// ═══ HAMBURGER ═══
const hamburger = document.getElementById('hamburgerDash');
const sidebar = document.getElementById('dashSidebar');
if (hamburger) hamburger.addEventListener('click', () => sidebar.classList.toggle('open'));

// ═══ INIT ═══
loadProfile();
loadCourses();



