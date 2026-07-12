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

let currentUser = null;

// ─── Check if viewing another user's profile ───────────────────
const _profileUserId = new URLSearchParams(window.location.search).get('user_id');
const _isViewingOther = !!_profileUserId;

// ═══ LOAD PROFILE ═══
async function loadProfile() {
    try {
        // ── Load sidebar (always the logged-in user) ──
        const sidebarRes = await apiFetch('/profile/me');
        if (sidebarRes.ok) {
            const me = await sidebarRes.json();
            const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
            setTxt('sidebarName', me.full_name);
            setTxt('topbarName', me.full_name);
            setTxt('dropdownName', me.full_name);
            const badgeLabel = getBadgeLabel(me.badge);
            const badgeEl = document.getElementById('sidebarBadge');
            if (badgeEl) badgeEl.innerHTML = `<span>${getRoleLabel(me)}</span>`;
            setTxt('sidebarLevelNum', me.level || 1);
            setTxt('sidebarLevelTitle', badgeLabel);
            setTxt('sidebarXpText', `${me.xp || 0} / ${me.next_level_xp || (me.level || 1) * 100} XP`);
            const xpBar = document.getElementById('sidebarXpBar');
            if (xpBar) {
                const pct = Math.min(100, Math.round(((me.xp || 0) / (me.next_level_xp || (me.level || 1) * 100)) * 100));
                xpBar.style.width = `${pct}%`;
            }
            setTxt('streakCount', me.streak_days || 0);
            ['sidebarAvatar', 'topbarAvatar', 'dropdownAvatarDiv'].forEach(id => {
                const el = document.getElementById(id);
                if (el) {
                    if (typeof buildAvatarHtml === 'function') {
                        el.innerHTML = buildAvatarHtml(me.full_name, me.avatar_url, me.id, 40);
                    } else {
                        const fullUrl = window.getAvatarSrc(me);
                        el.innerHTML = `<img src="${fullUrl}" alt="" onerror="this.style.display='none'" style="width:100%;height:100%;object-fit:cover;border-radius:50%;" />`;
                    }
                }
            });
        }

        // ── Load profile content ──
        let u;
        if (_isViewingOther) {
            // Viewing someone else's public profile
            const pubRes = await apiFetch(`/profile/${_profileUserId}/public`);
            if (!pubRes.ok) throw new Error('User not found');
            u = await pubRes.json();

            // Update page title
            document.title = `${u.full_name}'s Profile — Ghawy`;

            // Hide Edit Profile button
            const editBtn = document.getElementById('editProfileBtn');
            if (editBtn) editBtn.style.display = 'none';

            // Remove active from Achievements nav (user navigated from leaderboard, not from nav)
            const navAch = document.getElementById('navAchievements');
            if (navAch) navAch.classList.remove('active');

            // Show "← Back" in breadcrumb
            const breadcrumb = document.querySelector('.breadcrumb');
            if (breadcrumb) {
                const back = document.createElement('a');
                back.href = 'javascript:history.back()';
                back.innerHTML = '← Back';
                back.style.cssText = 'font-size:13px; color:#3f8ff9; font-weight:600; margin-right:12px;';
                breadcrumb.prepend(back);
            }
        } else {
            // Own profile
            const res = await apiFetch('/profile/me');
            if (!res.ok) return;
            u = await res.json();
            currentUser = u;

            // Highlight Achievements nav as active (own profile)
            const navAch = document.getElementById('navAchievements');
            if (navAch) navAch.classList.add('active');
        }

        const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };

        // Profile page elements
        setTxt('profileName', u.full_name);
        setTxt('profileBio', u.bio || '');
        setTxt('statLevel', u.level || 1);
        setTxt('statXP', u.xp || 0);
        setTxt('statStreak', u.streak_days || 0);
        setTxt('statCourses', 0);

        const memberSinceEl = document.querySelector('.member-since');
        if (memberSinceEl && u.created_at) {
            const d = new Date(u.created_at);
            const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
            memberSinceEl.textContent = `Member since ${months[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
        }

        // Quick Stats & Badges
        setTxt('qsXP', u.xp || 0);
        setTxt('qsLongestStreak', (u.streak_days || 0) + ' Days');
        setTxt('avatarLevel', u.level || 1);
        setTxt('xpLevelNum', u.level || 1);

        // Update XP Progress Bar
        const xpCurrent = u.xp || 0;
        const xpTarget = (u.level || 1) * 1000;
        setTxt('xpCurrent', xpCurrent);
        setTxt('xpTarget', xpTarget);
        const profileXpBar = document.getElementById('xpProgressBar');
        if (profileXpBar) profileXpBar.style.width = Math.min((xpCurrent / xpTarget) * 100, 100) + '%';

        const profileBadgeEl = document.getElementById('profileBadge');
        if (profileBadgeEl) profileBadgeEl.innerHTML = `<i class="fa-solid fa-shield"></i> ${getRoleLabel(u)}`;

        const avatarLg = document.getElementById('profileAvatarLg');
        if (avatarLg && u.avatar_url) avatarLg.innerHTML = `<img src="${u.avatar_url}" alt=""/>`;

        // Online dot
        const dot = document.getElementById('profileOnlineDot');
        if (dot) {
            if (_isViewingOther) {
                dot.className = u.is_online ? 'profile-online-dot online' : 'profile-online-dot offline';
                dot.title = u.is_online ? 'Online Now' : 'Offline';
            } else {
                dot.className = 'profile-online-dot online';
                dot.title = 'Online Now';
            }
        }

        // Settings form (own profile only)
        if (!_isViewingOther) {
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
        if (status) {
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
                if (status) {
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

                if (status) setTimeout(() => status.textContent = '', 3000);
            } else {
                if (status) {
                    status.style.color = 'var(--red-notif)';
                    status.textContent = 'Failed to upload image.';
                }
            }
        } catch (err) {
            console.error(err);
            if (status) {
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
const deleteConfirmInput = document.getElementById('deleteConfirmInput');

if (deleteConfirmInput && confirmDeleteBtn) {
    deleteConfirmInput.addEventListener('input', (e) => {
        if (e.target.value === 'delete my account') {
            confirmDeleteBtn.disabled = false;
            confirmDeleteBtn.style.opacity = '1';
            confirmDeleteBtn.style.cursor = 'pointer';
        } else {
            confirmDeleteBtn.disabled = true;
            confirmDeleteBtn.style.opacity = '0.5';
            confirmDeleteBtn.style.cursor = 'not-allowed';
        }
    });
}

if (confirmDeleteBtn) {
    confirmDeleteBtn.addEventListener('click', async () => {
        if (confirmDeleteBtn.disabled) return;
        try {
            await apiFetch('/auth/account', { method: 'DELETE' });
            localStorage.removeItem('token');
            window.location.href = 'index.html';
        } catch (e) { console.error(e); showToast('Error deleting account', 'error'); }
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

// ═══ PROGRESS STATS ═══
function setBar(id, pct) {
    const el = document.getElementById(id);
    if (!el) return;
    setTimeout(() => { el.style.width = pct + '%'; }, 300);
}

function getMotivation(pct) {
    if (pct === 0) return 'Start now!';
    if (pct < 25) return 'Get started!';
    if (pct < 50) return 'Keep going!';
    if (pct < 75) return 'Great job!';
    return 'Amazing!!';
}

async function loadProgressStats() {
    try {
        const res = await apiFetch('/dashboard/summary');
        if (!res.ok) return;
        const data = await res.json();
        const courses = data.courses || [];

        // Calculate totals
        let totalLessons = 0;
        let completedLessons = 0;
        let completedCourses = 0;
        courses.forEach(c => {
            totalLessons += (c.total_lessons || 0);
            completedLessons += Math.round((c.percent || 0) / 100 * (c.total_lessons || 0));
            if (c.percent >= 100) completedCourses++;
        });

        const qsCourses = document.getElementById('qsCourses');
        if (qsCourses) qsCourses.textContent = completedCourses;
        const statCourses = document.getElementById('statCourses');
        if (statCourses) statCourses.textContent = courses.length;

        // Videos percentage
        const videoPct = totalLessons > 0 ? Math.round((completedLessons / totalLessons) * 100) : 0;
        setBar('barVideos', videoPct);
        const pctV = document.getElementById('pctVideos');
        if (pctV) pctV.textContent = videoPct + '%';
        const countV = document.getElementById('countVideos');
        if (countV) countV.textContent = completedLessons;
        const totalV = document.getElementById('totalVideos');
        if (totalV) totalV.textContent = totalLessons;

        // Exams — real numbers from /dashboard/summary (published exams + best attempts)
        const ex = data.exams || {};
        const totalExams = ex.total || 0;
        const completedExams = ex.completed || 0;
        const examPct = totalExams > 0 ? Math.round((completedExams / totalExams) * 100) : 0;
        setBar('barExams', examPct);
        const pctE = document.getElementById('pctExams');
        if (pctE) pctE.textContent = examPct + '%';
        const countE = document.getElementById('countExams');
        if (countE) countE.textContent = completedExams;
        const totalE = document.getElementById('totalExams');
        if (totalE) totalE.textContent = totalExams;
        const motE = document.getElementById('motExams');
        if (motE) motE.textContent = completedExams > 0 ? `Best Score: ${ex.best_score || 0}%` : 'No exams taken yet';

        // Average Score — mean of the user's best score per exam
        const avgScore = ex.average_score || 0;
        const avgVal = document.getElementById('avgScoreVal');
        if (avgVal) avgVal.textContent = completedExams > 0 ? avgScore + '%' : '--';
        setBar('barLevel', completedExams > 0 ? avgScore : 0);
        const pctL = document.getElementById('pctLevel');
        if (pctL) pctL.textContent = (completedExams > 0 ? avgScore : 0) + '%';
        const motL = document.getElementById('motLevel');
        if (motL) motL.textContent = `Community Avg: ${ex.community_average || 0}%`;

        // ── Achievement Unlock Logic ──
        const u = data.user;

        // Helper: unlock or lock a card
        function setAch(achKey, unlocked) {
            const card = document.querySelector(`[data-ach="${achKey}"]`);
            if (!card) return;
            if (unlocked) {
                card.classList.remove('locked');
                // Remove the lock indicator icon if present
                const lockEl = card.querySelector('.lock-indicator');
                if (lockEl) lockEl.remove();
            } else {
                if (!card.classList.contains('locked')) card.classList.add('locked');
            }
        }

        // First Login: always unlocked
        setAch('first-login', true);

        // First Post in introduce-yourself
        setAch('first-post', !!u.has_first_post);

        // 7-Day Streak
        setAch('streak-7', !!u.has_7day_streak);

        // Top Student
        setAch('top-student', !!u.is_top_student);

        // Course Complete
        setAch('course-complete', !!u.has_course_complete);

        // 100% Progress
        setAch('all-progress', !!u.has_all_courses);

        // Pro Member
        setAch('pro-member', !!u.has_pro_member);

        // Update unlocked counter
        const unlockedAchs = [true, !!u.has_first_post, !!u.has_7day_streak, !!u.is_top_student, !!u.has_course_complete, !!u.has_all_courses, !!u.has_pro_member];
        const unlockedCount = unlockedAchs.filter(Boolean).length;
        const achCountEl = document.getElementById('achUnlockedCount');
        if (achCountEl) achCountEl.textContent = `${unlockedCount} / 7 Unlocked`;

        // Next Achievement Widget — update streak progress
        const streakDays = u.streak_days || 0;
        const nextAchProgressEl = document.getElementById('nextAchProgress');
        if (nextAchProgressEl) nextAchProgressEl.textContent = streakDays;
        const nextAchBar = document.getElementById('nextAchBar');
        if (nextAchBar) nextAchBar.style.width = Math.min((streakDays / 7) * 100, 100) + '%';

    } catch (e) { console.error('Progress stats error:', e); }
}

// ═══ INIT ═══
loadProfile();
loadProgressStats();


