(async () => {
  const user = await requireActiveUser();
  if (!user) return;
})();

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

let currentUser = null;

// ═══ LOAD PROFILE ═══
async function loadProfile() {
    try {
        const res = await apiFetch('/profile/me');
        if (!res.ok) return;
        currentUser = await res.json();
        const u = currentUser;

        // Sidebar
        const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        setTxt('sidebarName', u.full_name);
        setTxt('sidebarBadge', u.badge || 'Member');
        setTxt('topbarName', u.full_name);
        setTxt('streakCount', u.streak_days || 0);

        ['sidebarAvatar', 'topbarAvatar'].forEach(id => {
            const el = document.getElementById(id);
            if (el && u.avatar_url) el.innerHTML = `<img src="${u.avatar_url}" alt=""/>`;
        });

        // Profile page elements
        setTxt('profileName', u.full_name);
        setTxt('profileBio', u.bio || '');
        setTxt('statLevel', u.level || 1);
        setTxt('statXP', u.xp || 0);
        setTxt('statStreak', u.streak_days || 0);
        setTxt('statCourses', 0);

        const badgeEl = document.getElementById('profileBadge');
        if (badgeEl) badgeEl.innerHTML = `<i class="fa-solid fa-shield"></i> ${u.badge || 'Member'}`;

        const avatarLg = document.getElementById('profileAvatarLg');
        if (avatarLg && u.avatar_url) avatarLg.innerHTML = `<img src="${u.avatar_url}" alt=""/>`;

        // Update online dot on profile page
        const dot = document.getElementById('profileOnlineDot');
        if (dot) {
            // Current user is always online on their own profile
            dot.className = 'profile-online-dot online';
            dot.title = 'أونلاين الآن';
        }

        // Settings form
        const nameInput = document.getElementById('settingsName');
        if (nameInput) nameInput.value = u.full_name || '';
        const bioInput = document.getElementById('settingsBio');
        if (bioInput) bioInput.value = u.bio || '';
        const emailInput = document.getElementById('settingsEmail');
        if (emailInput) emailInput.value = u.email || '';
        const previewBox = document.getElementById('avatarPreviewBox');
        if (previewBox && u.avatar_url) previewBox.innerHTML = `<img src="${u.avatar_url}" style="width:100%;height:100%;object-fit:cover" />`;
        const socialInput = document.getElementById('settingsSocial');
        if (socialInput) socialInput.value = u.social_media_url || '';
        const toggleShowSocial = document.getElementById('toggleShowSocial');
        if (toggleShowSocial) {
            if (u.show_social_media === false) {
                toggleShowSocial.classList.remove('on');
            } else {
                toggleShowSocial.classList.add('on');
            }
        }

    } catch (e) { console.error('Profile load error:', e); }
}

// ═══ SAVE PROFILE ═══
const saveBtn = document.getElementById('saveProfileBtn');
if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
        const data = {
            full_name: document.getElementById('settingsName')?.value,
            bio: document.getElementById('settingsBio')?.value,
            social_media_url: document.getElementById('settingsSocial')?.value || null,
            show_social_media: document.getElementById('toggleShowSocial')?.classList.contains('on') ?? true,
        };
        console.log("Saving profile data:", data);
        try {
            const res = await apiFetch('/profile/me', { method: 'PUT', body: JSON.stringify(data) });
            const status = document.getElementById('saveStatus');
            if (res.ok) {
                if (status) { status.style.display = 'inline'; status.style.color = 'var(--gold)'; status.textContent = '✓ Saved'; setTimeout(() => status.style.display = 'none', 2000); }
                loadProfile();
            } else {
                if (status) { status.style.display = 'inline'; status.style.color = 'var(--red-notif)'; status.textContent = '✗ Error'; }
            }
        } catch (e) { console.error(e); }
    });
}

const toggleShowSocial = document.getElementById('toggleShowSocial');
if (toggleShowSocial) {
    toggleShowSocial.addEventListener('click', async () => {
        // Since the onclick in HTML already toggles 'on', we just read the new state
        const data = {
            show_social_media: toggleShowSocial.classList.contains('on')
        };
        try {
            await apiFetch('/profile/me', { method: 'PUT', body: JSON.stringify(data) });
            // Optionally show a quick save indicator somewhere, or just silently save
        } catch (e) { console.error('Auto-save toggle error:', e); }
    });
}

// ═══ AVATAR UPLOAD ═══
const avatarUpload = document.getElementById('avatarUploadInput');
if (avatarUpload) {
    avatarUpload.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        const status = document.getElementById('uploadStatus');
        if(status) {
            status.style.color = 'var(--text-muted)';
            status.textContent = 'Uploading...';
        }
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            // Note: Content-Type must be omitted to let the browser set it with the boundary for FormData
            const hdrs = { 'Authorization': `Bearer ${token}` };
            const res = await fetch(API + '/profile/avatar', {
                method: 'POST',
                headers: hdrs,
                body: formData
            });
            
            if (res.ok) {
                const data = await res.json();
                if(status) {
                    status.style.color = 'var(--gold)';
                    status.textContent = 'Uploaded successfully!';
                }
                
                // Update preview
                const previewBox = document.getElementById('avatarPreviewBox');
                if (previewBox) {
                    previewBox.innerHTML = `<img src="${data.avatar_url}" style="width:100%;height:100%;object-fit:cover" />`;
                }
                
                // Refresh topbar and sidebar avatars
                loadProfile();
                
                if(status) setTimeout(() => status.textContent = '', 3000);
            } else {
                if(status) {
                    status.style.color = 'var(--red-notif)';
                    status.textContent = 'Failed to upload image.';
                }
            }
        } catch (err) {
            console.error(err);
            if(status) {
                status.style.color = 'var(--red-notif)';
                status.textContent = 'Error during upload.';
            }
        }
    });
}

// ═══ CHANGE PASSWORD ═══
const pwBtn = document.getElementById('changePwBtn');
if (pwBtn) {
    pwBtn.addEventListener('click', async () => {
        const data = {
            current_password: document.getElementById('currentPw')?.value,
            new_password: document.getElementById('newPw')?.value,
            confirm_password: document.getElementById('confirmPw')?.value,
        };
        const status = document.getElementById('pwStatus');
        if (!data.current_password || !data.new_password) {
            if (status) { status.style.display = 'inline'; status.style.color = 'var(--red-notif)'; status.textContent = 'Fill all fields'; }
            return;
        }
        if (data.new_password !== data.confirm_password) {
            if (status) { status.style.display = 'inline'; status.style.color = 'var(--red-notif)'; status.textContent = 'Passwords don\'t match'; }
            return;
        }
        try {
            const res = await apiFetch('/profile/change-password', { method: 'POST', body: JSON.stringify(data) });
            const result = await res.json();
            if (res.ok) {
                if (status) { status.style.display = 'inline'; status.style.color = 'var(--gold)'; status.textContent = '✓ Password changed'; }
                document.getElementById('currentPw').value = '';
                document.getElementById('newPw').value = '';
                document.getElementById('confirmPw').value = '';
            } else {
                if (status) { status.style.display = 'inline'; status.style.color = 'var(--red-notif)'; status.textContent = result.detail || 'Error'; }
            }
        } catch (e) { console.error(e); }
    });
}

// ═══ DELETE ACCOUNT MODAL ═══
const deleteBtn = document.getElementById('deleteAccountBtn');
if (deleteBtn) {
    deleteBtn.addEventListener('click', () => {
        document.getElementById('deleteModal')?.classList.add('open');
    });
}

const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
if (confirmDeleteBtn) {
    confirmDeleteBtn.addEventListener('click', async () => {
        try {
            await apiFetch('/auth/account', { method: 'DELETE' });
            localStorage.removeItem('token');
            window.location.href = 'index.html';
        } catch (e) { console.error(e); alert('Error deleting account'); }
    });
}

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

// ═══ PROGRESS CIRCLES ═══
function setCircle(id, pct) {
    const el = document.getElementById(id);
    if (!el) return;
    const circumference = 427.26; // 2 * PI * 68
    const offset = circumference - (pct / 100) * circumference;
    setTimeout(() => { el.style.strokeDashoffset = offset; }, 300);
}

function getMotivation(pct) {
    if (pct === 0) return 'Start now!';
    if (pct < 25) return 'Get started!';
    if (pct < 50) return 'Keep going!';
    if (pct < 75) return 'Great job!';
    return 'Amazing!!';
}

async function loadProgressCircles() {
    try {
        const res = await apiFetch('/dashboard/summary');
        if (!res.ok) return;
        const data = await res.json();
        const courses = data.courses || [];

        // Calculate totals
        let totalLessons = 0;
        let completedLessons = 0;
        courses.forEach(c => {
            totalLessons += (c.total_lessons || 0);
            completedLessons += Math.round((c.percent || 0) / 100 * (c.total_lessons || 0));
        });

        // Videos percentage
        const videoPct = totalLessons > 0 ? Math.round((completedLessons / totalLessons) * 100) : 0;
        setCircle('circleVideos', videoPct);
        const pctV = document.getElementById('pctVideos');
        if (pctV) pctV.textContent = videoPct + '%';
        const countV = document.getElementById('countVideos');
        if (countV) countV.textContent = completedLessons + ' videos';
        const totalV = document.getElementById('totalVideos');
        if (totalV) totalV.textContent = 'of ' + totalLessons;
        const motV = document.getElementById('motVideos');
        if (motV) motV.textContent = getMotivation(videoPct);

        // Exams
        const totalExams = courses.length * 5;
        const completedExams = 0;
        const examPct = totalExams > 0 ? Math.round((completedExams / totalExams) * 100) : 0;
        setCircle('circleExams', examPct);
        const pctE = document.getElementById('pctExams');
        if (pctE) pctE.textContent = examPct + '%';
        const countE = document.getElementById('countExams');
        if (countE) countE.textContent = completedExams + ' exams';
        const totalE = document.getElementById('totalExams');
        if (totalE) totalE.textContent = 'of ' + totalExams;
        const motE = document.getElementById('motExams');
        if (motE) motE.textContent = getMotivation(examPct);

        // Overall level
        let avgPct = 0;
        if (courses.length > 0) {
            const sum = courses.reduce((s, c) => s + (c.percent || 0), 0);
            avgPct = Math.round(sum / courses.length);
        }
        setCircle('circleLevel', avgPct);
        const pctL = document.getElementById('pctLevel');
        if (pctL) pctL.textContent = avgPct + '%';
        const motL = document.getElementById('motLevel');
        if (motL) motL.textContent = getMotivation(avgPct);

    } catch (e) { console.error('Progress circles error:', e); }
}

// ═══ INIT ═══
loadProfile();
loadProgressCircles();


