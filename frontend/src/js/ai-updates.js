// ai-updates.js
let currentUser = null;
let currentCategory = 'all';
let currentSort = 'latest';
let editingPostId = null;        // set while the create modal is in "edit" mode
const postCache = {};            // id -> post object, used to prefill the edit modal

// ── Category metadata (badge label + accent color per editorial category) ──
const CATEGORY_META = {
    news:        { label: 'NEWS',        color: '#3f8ff9' },
    tools:       { label: 'TOOLS',       color: '#a855f7' },
    models:      { label: 'MODELS',      color: '#f59e0b' },
    updates:     { label: 'UPDATES',     color: '#22d3ee' },
    tutorials:   { label: 'TUTORIALS',   color: '#34d399' },
    discussions: { label: 'DISCUSSIONS', color: '#ec4899' },
};
function catMeta(cat) { return CATEGORY_META[cat] || CATEGORY_META.news; }

// Brand logo detection for the post thumbnail fallback (Font Awesome brand icons).
const BRAND_ICONS = [
    { re: /openai|gpt|chatgpt|sora|dall/i,        icon: 'fa-solid fa-robot',   bg: '#10a37f' },
    { re: /anthropic|claude/i,                    icon: 'fa-solid fa-star',    bg: '#d97757' },
    { re: /google|gemini|deepmind|bard/i,         icon: 'fa-brands fa-google', bg: '#4285f4' },
    { re: /meta|llama/i,                          icon: 'fa-brands fa-meta',   bg: '#0866ff' },
    { re: /microsoft|copilot|azure/i,             icon: 'fa-brands fa-microsoft', bg: '#5e5eff' },
    { re: /mistral/i,                             icon: 'fa-solid fa-wind',    bg: '#f97316' },
    { re: /midjourney/i,                          icon: 'fa-solid fa-sailboat', bg: '#111827' },
    { re: /nvidia/i,                              icon: 'fa-solid fa-microchip', bg: '#76b900' },
];
function brandFor(text) {
    for (const b of BRAND_ICONS) { if (b.re.test(text || '')) return b; }
    return null;
}

document.addEventListener('DOMContentLoaded', async () => {
    try {
        const token = localStorage.getItem('token');
        if (!token) throw new Error("No token in localStorage");
        
        const res = await fetch(API + '/profile/me', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) throw new Error("Failed to fetch user profile");
        
        currentUser = await res.json();
        localStorage.setItem('user', JSON.stringify(currentUser));
        
        // Setup UI
        const u = currentUser;
        const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        
        setTxt('sidebarName', u.full_name);
        setTxt('topbarName', u.full_name);
        setTxt('dropdownName', u.full_name);
        
        // Update Badge
        const badgeLabel = getBadgeLabel(u.badge);
        const badgeEl = document.getElementById('sidebarBadge');
        if (badgeEl) {
            badgeEl.innerHTML = `<span>${getRoleLabel(u)}</span>`;
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
        
        if (currentUser.is_admin) {
            document.getElementById('newPostBtn').style.display = 'block';
        }

        setupAdminControls();
        setupToolbar();
        await loadFeed();
        loadOverview();
        if (typeof loadActiveUsers === 'function') {
            loadActiveUsers();
        }

    } catch (err) {
        console.error("AI Updates Crash:", err);
        // Fallback or alert instead of infinite reload
    }
});

// ── Helpers ───────────────────────────────────────────────

// ── Read marker (clears the sidebar AI Updates badge) ─────
async function markAiUpdatesRead() {
    if (document.visibilityState !== 'visible') return;
    try {
        await fetch(`${API}/ai-updates/read`, {
            method: 'PUT',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        // Refresh sidebar + bell badges now instead of waiting for the 30s poll
        if (typeof fetchGlobalNotifications === 'function') fetchGlobalNotifications();
    } catch (e) { }
}
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') markAiUpdatesRead();
});

// ── Feed ──────────────────────────────────────────────────
async function loadFeed(page = 1) {
    const feed = document.getElementById('aiFeed');
    if (page === 1) feed.innerHTML = '<div class="skeleton-card"></div><div class="skeleton-card"></div>';

    try {
        const params = new URLSearchParams({ page, limit: 20, sort: currentSort });
        if (currentCategory && currentCategory !== 'all') params.set('category', currentCategory);
        const res = await fetch(`${API}/ai-updates/posts?${params.toString()}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        if (!res.ok) throw new Error('Failed to load posts');

        const data = await res.json();
        if (page === 1) markAiUpdatesRead();

        if (page === 1) feed.innerHTML = '';

        if (data.posts.length === 0 && page === 1) {
            const isFiltered = currentCategory && currentCategory !== 'all';
            feed.innerHTML = `
                <div class="ai-empty-state">
                    <i data-lucide="sparkles"></i>
                    <h3>${isFiltered ? 'Nothing here yet' : 'No AI Updates Yet'}</h3>
                    <p>${isFiltered ? 'No posts in this category. Try another filter.' : 'Check back later for the latest news and polls.'}</p>
                </div>
            `;
            lucide.createIcons();
            return;
        }

        data.posts.forEach(post => {
            feed.appendChild(createPostElement(post));
        });
        
        lucide.createIcons();

        // Handle scrolling to a specific post if a hash is present
        if (page === 1 && window.location.hash) {
            const targetId = window.location.hash.substring(1); // remove the '#'
            const targetEl = document.getElementById(targetId);
            if (targetEl) {
                setTimeout(() => {
                    targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    // Optional: Add a brief highlight effect
                    targetEl.style.transition = 'box-shadow 0.5s ease';
                    targetEl.style.boxShadow = '0 0 15px rgba(193, 255, 17, 0.5)';
                    setTimeout(() => {
                        targetEl.style.boxShadow = '';
                    }, 2000);
                }, 100);
            }
        }

    } catch (err) {
        console.error(err);
        if (page === 1) {
            feed.innerHTML = `<div class="ai-empty-state"><p style="color:#ef4444;">Error loading feed. Please try again.</p></div>`;
        }
    }
}

// ── Rendering ─────────────────────────────────────────────
const EXCERPT_LEN = 160;

function postHasMedia(post) {
    return postMediaList(post).length > 0;
}

// Normalized media list: new `media` array, falling back to legacy single columns.
function postMediaList(post) {
    if (Array.isArray(post.media) && post.media.length) return post.media;
    const list = [];
    if (post.image_url) list.push({ type: 'image', url: post.image_url });
    if (post.video_url) list.push({ type: 'video', url: post.video_url });
    return list;
}

// Full-width media rendered inline inside the post body (always visible).
// Multiple images render as a grid; multiple videos stack.
function postMediaHtml(post) {
    const items = postMediaList(post);
    if (!items.length) return '';

    const images = items.filter(m => m.type === 'image');
    const videos = items.filter(m => m.type === 'video');
    let html = '';

    if (images.length) {
        const cols = (images.length === 2 || images.length === 4) ? 2 : 3;
        const gridCls = images.length > 1 ? ` ai-media-grid cols-${cols}` : '';
        html += `<div class="ai-post-media${gridCls}">` + images.map(m => {
            const url = m.url.startsWith('http') ? m.url : API + m.url;
            return `<img src="${escapeHtml(url)}" alt="Post Image" loading="lazy" onclick="openLightbox(this.src)">`;
        }).join('') + `</div>`;
    }

    videos.forEach(m => {
        html += `<div class="ai-post-media">
            <iframe src="${escapeHtml(m.url)}" loading="lazy" allow="accelerometer; gyroscope; autoplay; encrypted-media; picture-in-picture;" allowfullscreen></iframe>
        </div>`;
    });

    return html;
}

// Fullscreen image viewer for post galleries.
function openLightbox(src) {
    let lb = document.getElementById('aiLightbox');
    if (!lb) {
        lb = document.createElement('div');
        lb.id = 'aiLightbox';
        lb.className = 'ai-lightbox';
        lb.innerHTML = `<img id="aiLightboxImg" src="" alt="">`;
        lb.addEventListener('click', () => { lb.style.display = 'none'; });
        document.body.appendChild(lb);
    }
    document.getElementById('aiLightboxImg').src = src;
    lb.style.display = 'flex';
}

function createPostElement(post) {
    const div = document.createElement('div');
    div.className = `ai-post-card ${post.is_pinned ? 'pinned' : ''}`;
    div.id = `post-${post.id}`;
    div.dataset.cat = post.category || 'news';

    postCache[post.id] = post;   // keep for the edit modal

    const meta = catMeta(post.category);

    let adminActions = '';
    if (currentUser.is_admin) {
        adminActions = `
            <div class="ai-post-admin-actions">
                <button class="admin-action-btn edit-btn" onclick="openEditModal(${post.id})" title="Edit">
                    <i data-lucide="pencil"></i>
                </button>
                <button class="admin-action-btn pin-btn" onclick="togglePin(${post.id})" title="${post.is_pinned ? 'Unpin' : 'Pin'}">
                    <i data-lucide="pin"></i>
                </button>
                <button class="admin-action-btn delete" onclick="deletePost(${post.id})" title="Delete">
                    <i data-lucide="trash-2"></i>
                </button>
            </div>
        `;
    }

    // Badges row
    let badgesHtml = '<div class="ai-post-badges">';
    if (post.is_pinned) badgesHtml += `<span class="ai-badge featured"><i data-lucide="pin"></i> FEATURED</span>`;
    badgesHtml += `<span class="ai-badge" style="color:${meta.color};background:${meta.color}1f;border-color:${meta.color}44;">${meta.label}</span>`;
    badgesHtml += '</div>';

    // Excerpt / read-more (controls the TEXT body only; media stays inline & visible).
    // URLs stay INLINE in the text, rendered as buttons in place (see renderRich).
    // Full body renders **bold** / *italic* / __underline__; excerpt uses plain text
    // (markers stripped) so a cut never lands mid-marker.
    const body = post.body || '';
    const plain = stripMd(body);
    const needsExpand = plain.length > EXCERPT_LEN;

    let bodyBlock;
    if (needsExpand) {
        const excerpt = plain.slice(0, EXCERPT_LEN).trim() + '…';
        bodyBlock = `<div class="ai-post-excerpt" dir="auto">${linkifyHtml(excerpt)}</div>`;
        bodyBlock += `<div class="ai-post-full" dir="auto" style="display:none;">${renderRich(body)}</div>`;
        bodyBlock += `<button class="read-more-btn" onclick="toggleReadMore(${post.id}, this)">Read More <i data-lucide="chevron-down"></i></button>`;
    } else {
        bodyBlock = `<div class="ai-post-excerpt" dir="auto">${renderRich(body)}</div>`;
    }

    // Media (photo/video) rendered inline in the body, always visible
    const mediaHtml = postMediaHtml(post);

    // Poll (always visible, interactive)
    const pollHtml = (post.post_type === 'poll' && post.poll) ? renderPollHtml(post.poll) : '';

    // Reactions
    const heartCount = post.reaction_counts['❤️'] || 0;
    const isHeartActive = post.user_reactions.includes('❤️');
    let reactionsHtml = `
        <button class="reaction-btn ${isHeartActive ? 'active' : ''}" onclick="toggleReaction(${post.id}, '❤️')">
            <i data-lucide="heart" class="${isHeartActive ? 'filled-heart' : ''}"></i>
            <span class="count">${heartCount}</span>
        </button>
    `;

    div.innerHTML = `
        ${adminActions}
        <div class="ai-post-inner">
            <div class="ai-post-main">
                ${badgesHtml}
                <div class="ai-post-header">
                    <img src="${getAvatarSrc(post.author)}" class="ai-post-avatar" onclick="openUserProfile(${post.author?.id})" style="cursor: pointer;">
                    <div class="ai-post-meta">
                        <div class="ai-post-author">
                            ${escapeHtml(post.author?.full_name || 'Admin')}
                            ${post.author?.is_admin ? '<span class="admin-badge">Admin</span>' : ''}
                        </div>
                        <div class="ai-post-time">${post.time_ago}</div>
                    </div>
                </div>
                <div class="ai-post-title" dir="auto">${escapeHtml(post.title)}</div>
                ${bodyBlock}
                ${mediaHtml}
                ${pollHtml}
            </div>
        </div>

        <div class="ai-post-actions">
            ${reactionsHtml}
            <button class="comment-toggle-btn" onclick="toggleComments(${post.id})">
                <i data-lucide="message-circle-more"></i>
                <span id="comment-count-${post.id}">${post.comment_count || 0}</span>
            </button>
        </div>

        <div class="ai-comments-section" id="comments-${post.id}">
            <div class="comments-list" id="comments-list-${post.id}"></div>
            <div class="ai-comment-input-wrapper">
                <img src="${getAvatarSrc(currentUser)}" class="ai-comment-avatar">
                <textarea class="ai-comment-input" id="comment-input-${post.id}" placeholder="Write a comment..." rows="1"></textarea>
                <button class="ai-comment-send" onclick="submitComment(${post.id})"><i data-lucide="send" size="16"></i></button>
            </div>
        </div>
    `;

    return div;
}

function toggleReadMore(postId, btn) {
    const card = document.getElementById(`post-${postId}`);
    if (!card) return;
    const excerpt = card.querySelector('.ai-post-excerpt');
    const full = card.querySelector('.ai-post-full');
    if (!full) return;
    const expanded = full.style.display === 'block';
    if (expanded) {
        full.style.display = 'none';
        if (excerpt) excerpt.style.display = '';
        btn.innerHTML = 'Read More <i data-lucide="chevron-down"></i>';
    } else {
        full.style.display = 'block';
        if (excerpt) excerpt.style.display = 'none';
        btn.innerHTML = 'Show Less <i data-lucide="chevron-up"></i>';
    }
    if (window.lucide) lucide.createIcons();
}

// ── Toolbar: filters, sort, view toggle, subscribe ────────
function setupToolbar() {
    // Category filter tabs
    document.querySelectorAll('.ai-filter-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.ai-filter-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentCategory = tab.dataset.cat;
            loadFeed(1);
        });
    });

    // "View All" links in sidebar rails jump to a category filter
    document.querySelectorAll('[data-cat-link]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            selectCategory(link.dataset.catLink);
        });
    });

    // Sort dropdown
    const sortBtn = document.getElementById('aiSortBtn');
    const sortMenu = document.getElementById('aiSortMenu');
    if (sortBtn && sortMenu) {
        sortBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            sortMenu.classList.toggle('open');
        });
        sortMenu.querySelectorAll('button').forEach(opt => {
            opt.addEventListener('click', () => {
                currentSort = opt.dataset.sort;
                sortMenu.querySelectorAll('button').forEach(b => b.classList.remove('active'));
                opt.classList.add('active');
                document.getElementById('aiSortLabel').textContent = opt.textContent;
                sortMenu.classList.remove('open');
                loadFeed(1);
            });
        });
        document.addEventListener('click', () => sortMenu.classList.remove('open'));
    }

    // View toggle (list / grid)
    const feed = document.getElementById('aiFeed');
    document.querySelectorAll('#aiViewToggle button').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#aiViewToggle button').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            feed.classList.toggle('grid-view', btn.dataset.view === 'grid');
            try { localStorage.setItem('ai_view', btn.dataset.view); } catch (e) {}
        });
    });
    // Restore saved view
    try {
        const savedView = localStorage.getItem('ai_view');
        if (savedView === 'grid') {
            feed.classList.add('grid-view');
            document.querySelectorAll('#aiViewToggle button').forEach(b => b.classList.toggle('active', b.dataset.view === 'grid'));
        }
    } catch (e) {}

}

function selectCategory(cat) {
    const tab = document.querySelector(`.ai-filter-tab[data-cat="${cat}"]`);
    if (tab) tab.click();
    document.querySelector('.dash-content')?.scrollTo?.({ top: 0, behavior: 'smooth' });
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Overview: header stats + sidebar rails ────────────────
async function loadOverview() {
    try {
        const res = await fetch(`${API}/ai-updates/overview`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        if (!res.ok) throw new Error('overview failed');
        const data = await res.json();

        // Stats
        const s = data.stats || {};
        setStat('statUpdates', s.updates_this_week);
        setStat('statTools', s.tools_this_week);
        setStat('statModels', s.models_this_week);
        setStat('statDiscussions', s.discussions_this_week);

        renderMostPopular(data.most_popular || []);
        renderNewTools(data.new_tools || []);
        renderWhatsNew(data.whats_new || []);
        renderContributors(data.top_contributors || []);

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.warn('Overview load failed:', err);
    }
}

function setStat(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = (val != null ? val : 0);
}

function goToPost(postId) {
    const el = document.getElementById(`post-${postId}`);
    if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.style.transition = 'box-shadow 0.5s ease';
        el.style.boxShadow = '0 0 15px rgba(193, 255, 17, 0.5)';
        setTimeout(() => { el.style.boxShadow = ''; }, 2000);
    }
}

function renderMostPopular(list) {
    const box = document.getElementById('railMostPopular');
    if (!box) return;
    if (!list.length) { box.innerHTML = emptyRail('No posts yet'); return; }
    box.innerHTML = list.map((p, i) => {
        const meta = catMeta(p.category);
        return `
        <div class="rail-item rank" onclick="goToPost(${p.id})">
            <span class="rail-rank">${i + 1}</span>
            <div class="rail-item-body">
                <div class="rail-item-title" dir="auto">${escapeHtml(p.title)}</div>
                <div class="rail-item-sub"><span style="color:${meta.color}">${meta.label}</span></div>
            </div>
            <span class="rail-item-metric"><i data-lucide="flame"></i> ${p.engagement}</span>
        </div>`;
    }).join('');
}

function renderNewTools(list) {
    const box = document.getElementById('railNewTools');
    if (!box) return;
    if (!list.length) { box.innerHTML = emptyRail('No tools yet'); return; }
    box.innerHTML = list.map(p => `
        <div class="rail-item" onclick="goToPost(${p.id})">
            <span class="rail-dot" style="background:${catMeta('tools').color}"></span>
            <div class="rail-item-body">
                <div class="rail-item-title" dir="auto">${escapeHtml(p.title)}</div>
                <div class="rail-item-sub">${p.time_ago}</div>
            </div>
            <span class="rail-new-badge">NEW</span>
        </div>
    `).join('');
}

function renderWhatsNew(list) {
    const box = document.getElementById('railWhatsNew');
    if (!box) return;
    if (!list.length) { box.innerHTML = emptyRail('Nothing new'); return; }
    box.innerHTML = list.map(p => {
        const brand = brandFor(p.title);
        const meta = catMeta(p.category);
        const icon = brand
            ? `<span class="rail-brand" style="background:${brand.bg}22;color:${brand.bg}"><i class="${brand.icon}"></i></span>`
            : `<span class="rail-brand" style="background:${meta.color}22;color:${meta.color}"><i data-lucide="sparkles"></i></span>`;
        return `
        <div class="rail-item" onclick="goToPost(${p.id})">
            ${icon}
            <div class="rail-item-body">
                <div class="rail-item-title" dir="auto">${escapeHtml(p.title)}</div>
                <div class="rail-item-sub">${p.time_ago}</div>
            </div>
        </div>`;
    }).join('');
}

function renderContributors(list) {
    const box = document.getElementById('railContributors');
    if (!box) return;
    if (!list.length) { box.innerHTML = emptyRail('No contributors yet'); return; }
    box.innerHTML = list.map((u, i) => `
        <div class="rail-item contributor" onclick="openUserProfile(${u.id})">
            <span class="rail-rank ${i === 0 ? 'gold' : ''}">${i + 1}</span>
            <img src="${getAvatarSrc(u)}" class="rail-avatar" alt="">
            <div class="rail-item-body">
                <div class="rail-item-title" dir="auto">${escapeHtml(u.full_name)}</div>
                <div class="rail-item-sub">${escapeHtml(getRoleLabel(u))}</div>
            </div>
            <span class="rail-points">${u.points} pts</span>
        </div>
    `).join('');
}

function emptyRail(msg) {
    return `<div class="rail-empty">${msg}</div>`;
}

function renderPollHtml(poll) {
    const hasVoted = poll.user_voted_option_id !== null;
    let html = `
        <div class="ai-poll-container" id="poll-${poll.id}">
            <div class="ai-poll-question" dir="auto">${escapeHtml(poll.question)}</div>
    `;

    poll.options.forEach(opt => {
        let thumbHtml = '';
        if (opt.image_url) {
            const src = opt.image_url.startsWith('http') ? opt.image_url : API + opt.image_url;
            thumbHtml = `<img src="${escapeHtml(src)}" class="poll-option-img" alt="" loading="lazy" onclick="event.preventDefault(); event.stopPropagation(); openLightbox(this.src)">`;
        }
        if (hasVoted) {
            const isUserChoice = (opt.id === poll.user_voted_option_id);
            const customIcon = isUserChoice
                ? `<span class="voted-check"><i data-lucide="check" style="width:12px;height:12px;stroke-width:3;"></i></span>`
                : `<span class="unvoted-circle"></span>`;

            html += `
                <div class="ai-poll-option voted ${isUserChoice ? 'user-choice' : ''}">
                    <div class="poll-progress" style="width: ${opt.percentage}%"></div>
                    <div style="display:flex; align-items:center; gap:12px; position:relative; z-index:1;">
                        ${customIcon}
                        ${thumbHtml}
                        <span class="poll-option-text" dir="auto">${escapeHtml(opt.text)}</span>
                    </div>
                    <span class="poll-option-pct">${opt.percentage}%</span>
                </div>
            `;
        } else {
            html += `
                <label class="ai-poll-option unvoted">
                    <input type="radio" name="poll-${poll.id}" value="${opt.id}" onchange="submitVote(${poll.id}, ${opt.id})">
                    <span class="radio-custom"></span>
                    ${thumbHtml}
                    <span class="poll-option-text" dir="auto">${escapeHtml(opt.text)}</span>
                </label>
            `;
        }
    });

    html += `<div class="ai-poll-total">${poll.total_votes} votes</div></div>`;
    return html;
}

// ── Interactions ──────────────────────────────────────────
async function toggleReaction(postId, emoji) {
    try {
        const res = await fetch(`${API}/ai-updates/posts/${postId}/react`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({ emoji })
        });
        if (!res.ok) throw new Error('Failed to react');
        
        const data = await res.json();
        
        // Optimistic UI update for reactions
        const postCard = document.getElementById(`post-${postId}`);
        const reactionContainer = postCard.querySelector('.ai-post-actions');
        
        const heartCount = data.reaction_counts['❤️'] || 0;
        const isHeartActive = data.user_reactions.includes('❤️');
        let newHtml = `
            <button class="reaction-btn ${isHeartActive ? 'active' : ''}" onclick="toggleReaction(${postId}, '❤️')">
                <i data-lucide="heart" class="${isHeartActive ? 'filled-heart' : ''}"></i>
                <span class="count">${heartCount}</span>
            </button>
        `;
        
        // Preserve the comment button
        const commentBtnHtml = reactionContainer.querySelector('.comment-toggle-btn').outerHTML;
        reactionContainer.innerHTML = newHtml + commentBtnHtml;
        lucide.createIcons();

    } catch (err) {
        showToast("Error toggling reaction", "error");
    }
}

async function submitVote(pollId, optionId) {
    try {
        const res = await fetch(`${API}/ai-updates/polls/${pollId}/vote`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({ option_id: optionId })
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to vote');
        }
        
        const poll = await res.json();
        
        const container = document.getElementById(`poll-${pollId}`);
        container.outerHTML = renderPollHtml(poll);
        
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function toggleComments(postId) {
    const section = document.getElementById(`comments-${postId}`);
    const isVisible = section.style.display === 'block';
    
    if (isVisible) {
        section.style.display = 'none';
    } else {
        section.style.display = 'block';
        await loadComments(postId);
    }
}

async function loadComments(postId) {
    const list = document.getElementById(`comments-list-${postId}`);
    list.innerHTML = '<div style="text-align:center;color:#888;font-size:0.8rem;">Loading...</div>';
    
    try {
        const res = await fetch(`${API}/ai-updates/posts/${postId}/comments`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        if (!res.ok) throw new Error();
        
        const comments = await res.json();
        list.innerHTML = '';
        
        if (comments.length === 0) {
            list.innerHTML = '<div style="color:#888;font-size:0.85rem;margin-bottom:12px;">No comments yet.</div>';
            return;
        }

        comments.forEach(c => {
            list.appendChild(createCommentElement(c));
        });
        lucide.createIcons();

    } catch (err) {
        list.innerHTML = '<div style="color:#ef4444;font-size:0.85rem;">Failed to load comments</div>';
    }
}

function createCommentElement(comment, isReply = false) {
    const isAuthor = currentUser.id === comment.author?.id;
    const canDelete = isAuthor || currentUser.is_admin;

    // Check local storage for mocked likes to persist them across reloads
    const localLikes = JSON.parse(localStorage.getItem('ai_comment_likes') || '{}');
    if (localLikes[comment.id]) {
        comment.user_liked = true;
        comment.likes_count = (comment.likes_count || 0) + 1;
    }

    let actionsHtml = `
        <button class="comment-action-btn like ${comment.user_liked ? 'active' : ''}" onclick="likeComment(${comment.post_id}, ${comment.id}, this)">
            <i data-lucide="heart" class="${comment.user_liked ? 'filled-heart' : ''}"></i> <span class="like-count">${comment.likes_count || 0}</span>
        </button>
    `;

    // Reply is only allowed on top-level comments (backend enforces 1-level nesting)
    if (!isReply) {
        actionsHtml += `<button class="comment-action-btn reply" onclick="toggleReplyBox(${comment.post_id}, ${comment.id})"><i data-lucide="reply"></i> Reply</button>`;
    }

    if (canDelete) {
        actionsHtml += `<button class="comment-action-btn delete" onclick="deleteComment(${comment.post_id}, ${comment.id})"><i data-lucide="trash-2"></i></button>`;
    }

    const div = document.createElement('div');
    div.className = isReply ? 'ai-comment ai-comment-reply' : 'ai-comment';
    div.id = `comment-${comment.id}`;
    div.innerHTML = `
        <img src="${getAvatarSrc(comment.author)}" class="ai-comment-avatar" onclick="openUserProfile(${comment.author?.id})" style="cursor: pointer;">
        <div style="flex:1;">
            <div class="ai-comment-content">
                <div class="ai-comment-header">
                    <span class="ai-comment-author">${comment.author?.full_name || 'User'}</span>
                    <span class="ai-comment-time">${comment.time_ago}</span>
                </div>
                <div class="ai-comment-body" dir="auto">${linkifyHtml(comment.body)}</div>
            </div>
            <div class="ai-comment-actions">
                ${actionsHtml}
            </div>
            ${!isReply ? `<div class="ai-reply-box" id="reply-box-${comment.id}" style="display:none;"></div>` : ''}
            ${!isReply ? `<div class="ai-comment-replies" id="replies-${comment.id}"></div>` : ''}
        </div>
    `;

    // Append replies as real DOM nodes (recursively). String interpolation of
    // DOM elements would render as "[object HTMLDivElement]", so we append here.
    if (!isReply && comment.replies && comment.replies.length > 0) {
        const repliesContainer = div.querySelector(`#replies-${comment.id}`);
        comment.replies.forEach(r => repliesContainer.appendChild(createCommentElement(r, true)));
    }

    return div;
}

// Toggle inline reply input under a top-level comment
function toggleReplyBox(postId, parentId) {
    const box = document.getElementById(`reply-box-${parentId}`);
    if (!box) return;
    if (box.style.display === 'block') {
        box.style.display = 'none';
        box.innerHTML = '';
        return;
    }
    box.style.display = 'block';
    box.innerHTML = `
        <div class="ai-comment-input-wrapper ai-reply-input-wrapper">
            <img src="${getAvatarSrc(currentUser)}" class="ai-comment-avatar">
            <textarea class="ai-comment-input" id="reply-input-${parentId}" placeholder="Write a reply..." rows="1" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();submitReply(${postId}, ${parentId});}"></textarea>
            <button class="ai-comment-send" onclick="submitReply(${postId}, ${parentId})"><i data-lucide="send" size="16"></i></button>
        </div>
    `;
    if (window.lucide) lucide.createIcons();
    const ta = document.getElementById(`reply-input-${parentId}`);
    if (ta) ta.focus();
}

async function submitReply(postId, parentId) {
    const input = document.getElementById(`reply-input-${parentId}`);
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    try {
        const res = await fetch(`${API}/ai-updates/posts/${postId}/comments`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({ body: text, parent_id: parentId })
        });

        if (!res.ok) throw new Error('Failed to post reply');

        input.value = '';
        await loadComments(postId); // reload list (shows the new reply nested)

        // update count visually (backend counts replies too)
        const countSpan = document.getElementById(`comment-count-${postId}`);
        if (countSpan) countSpan.textContent = (parseInt(countSpan.textContent) || 0) + 1;

    } catch (err) {
        showToast("Error adding reply", "error");
    }
}

async function submitComment(postId) {
    const input = document.getElementById(`comment-input-${postId}`);
    const text = input.value.trim();
    if (!text) return;

    try {
        const res = await fetch(`${API}/ai-updates/posts/${postId}/comments`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            },
            body: JSON.stringify({ body: text })
        });
        
        if (!res.ok) throw new Error('Failed to post comment');
        
        input.value = '';
        await loadComments(postId); // reload list
        
        // update count visually
        const countSpan = document.getElementById(`comment-count-${postId}`);
        let currentCount = parseInt(countSpan.textContent) || 0;
        countSpan.textContent = currentCount + 1;

    } catch (err) {
        showToast("Error adding comment", "error");
    }
}

async function deleteComment(postId, commentId) {
    if (!confirm("Are you sure you want to delete this comment?")) return;
    try {
        const res = await fetch(`${API}/ai-updates/comments/${commentId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        if (!res.ok) throw new Error('Failed to delete comment');
        
        showToast("Comment deleted");
        await loadComments(postId);
    } catch (err) {
        showToast("Error deleting comment", "error");
    }
}

async function likeComment(postId, commentId, btnElement) {
    // Optimistic UI Update
    const countSpan = btnElement.querySelector('.like-count');
    let currentCount = parseInt(countSpan.textContent) || 0;
    const isActive = btnElement.classList.contains('active');
    const localLikes = JSON.parse(localStorage.getItem('ai_comment_likes') || '{}');
    
    if (isActive) {
        btnElement.classList.remove('active');
        countSpan.textContent = currentCount - 1;
        delete localLikes[commentId];
    } else {
        btnElement.classList.add('active');
        countSpan.textContent = currentCount + 1;
        localLikes[commentId] = true;
    }
    localStorage.setItem('ai_comment_likes', JSON.stringify(localLikes));

    try {
        const res = await fetch(`${API}/ai-updates/posts/comments/${commentId}/like`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        
        if (!res.ok) {
            console.warn('Failed to like comment on backend');
        }
    } catch (err) {
        console.warn("Like comment failed (maybe endpoint doesn't exist yet):", err);
    }
}

// ── Admin Actions ─────────────────────────────────────────
function setupAdminControls() {
    const btn = document.getElementById('newPostBtn');

    if (btn) {
        btn.addEventListener('click', () => openCreateModal());
    }

    // Category chips
    const catChips = document.querySelectorAll('#postCatChips .cat-chip');
    catChips.forEach(chip => {
        chip.addEventListener('click', () => {
            catChips.forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            document.getElementById('postCategory').value = chip.dataset.cat;
        });
    });

    // Tabs
    document.querySelectorAll('.post-type-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            selectPostType(tab.dataset.type);
        });
    });

    // Add poll option
    const addOptBtn = document.getElementById('addPollOptionBtn');
    if (addOptBtn) {
        addOptBtn.addEventListener('click', () => {
            const container = document.getElementById('pollOptionsContainer');
            const currentCount = container.querySelectorAll('.poll-option-wrapper').length;
            if (currentCount >= 4) {
                showToast("Maximum 4 options allowed", "error");
                return;
            }
            addPollOptionRow(true);
        });
    }
    resetPollOptions();

    // Add another video URL
    const addVidBtn = document.getElementById('addVideoUrlBtn');
    if (addVidBtn) {
        addVidBtn.addEventListener('click', () => addVideoUrlRow('', true));
    }

    // Formatting toolbar (B / I / U) for the body textarea
    document.querySelectorAll('#fmtToolbar .fmt-btn').forEach(b => {
        b.addEventListener('click', () => wrapSelection('postBody', b.dataset.wrap));
    });

    // Submit form
    const form = document.getElementById('createPostForm');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('submitPostBtn');
            btn.disabled = true;
            btn.textContent = 'Posting...';

            const title = document.getElementById('postTitle').value.trim();
            const body = document.getElementById('postBody').value.trim();
            const currentPostType = document.getElementById('postType').value;

            // Build the media list (photo → kept + newly uploaded images; video → all URL rows)
            let media = [];
            try {
                if (currentPostType === 'photo') {
                    media = modalExistingMedia.filter(m => m.type === 'image').slice();
                    for (const item of modalNewFiles) {
                        const url = await uploadImageFile(item.file);
                        media.push({ type: 'image', url });
                    }
                } else if (currentPostType === 'video') {
                    document.querySelectorAll('#videoUrlsContainer .video-url-input').forEach(i => {
                        const u = i.value.trim();
                        if (u) media.push({ type: 'video', url: u });
                    });
                }
            } catch (e) {
                console.error('Image upload failed:', e);
                showToast('Image upload failed', 'error');
                btn.disabled = false;
                btn.textContent = editingPostId ? 'Save Changes' : 'Post Update';
                return;
            }

            const payload = {
                post_type: currentPostType,
                category: document.getElementById('postCategory')?.value || 'news',
                title: title,
                body: body,
                media: media,
                image_url: media.find(m => m.type === 'image')?.url || null,
                video_url: media.find(m => m.type === 'video')?.url || null,
            };

            // Poll options only apply on create (the API doesn't support editing a poll).
            if (payload.post_type === 'poll' && !editingPostId) {
                const question = document.getElementById('pollQuestion').value;
                const rows = document.querySelectorAll('#pollOptionsContainer .poll-option-wrapper');
                const options = [];
                try {
                    for (const row of rows) {
                        const text = row.querySelector('.poll-option-input')?.value.trim();
                        if (!text) continue;
                        let imgUrl = null;
                        const fileInput = row.querySelector('.poll-opt-file');
                        if (fileInput && fileInput.files.length > 0) {
                            imgUrl = await uploadImageFile(fileInput.files[0]);
                        }
                        options.push({ text: text, image_url: imgUrl });
                    }
                } catch (e) {
                    console.error('Poll image upload failed:', e);
                    showToast('Poll image upload failed', 'error');
                    btn.disabled = false;
                    btn.textContent = 'Post Update';
                    return;
                }

                if (!question || options.length < 2) {
                    showToast("Poll requires a question and at least 2 options", "error");
                    btn.disabled = false;
                    btn.textContent = 'Post Update';
                    return;
                }

                payload.poll = {
                    question: question,
                    options: options
                };
            }

            try {
                const isEdit = !!editingPostId;
                const url = isEdit ? `${API}/ai-updates/posts/${editingPostId}` : `${API}/ai-updates/posts`;
                const res = await fetch(url, {
                    method: isEdit ? 'PATCH' : 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${localStorage.getItem('token')}`
                    },
                    body: JSON.stringify(payload)
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || (isEdit ? 'Failed to update post' : 'Failed to create post'));
                }

                showToast(isEdit ? "Post updated successfully" : "Post created successfully");
                closeCreateModal();
                form.reset();
                // Reset category chips to default
                document.querySelectorAll('#postCatChips .cat-chip').forEach(c => c.classList.toggle('active', c.dataset.cat === 'news'));
                document.getElementById('postCategory').value = 'news';
                resetModalMedia();
                resetVideoUrls();
                resetPollOptions();

                await loadFeed(1);
                loadOverview();

            } catch (err) {
                showToast(err.message, "error");
            } finally {
                btn.disabled = false;
                btn.textContent = editingPostId ? 'Save Changes' : 'Post Update';
            }
        });
    }
}

// Switch the create/edit modal to a given post type (updates tab + visible fields).
function selectPostType(type) {
    document.querySelectorAll('.post-type-tab').forEach(t => t.classList.toggle('active', t.dataset.type === type));
    document.getElementById('postType').value = type;
    document.getElementById('videoFields').style.display = type === 'video' ? 'block' : 'none';
    document.getElementById('photoFields').style.display = type === 'photo' ? 'block' : 'none';
    document.getElementById('pollFields').style.display = type === 'poll' ? 'block' : 'none';
}

// Highlight one category chip and sync the hidden input.
function selectCategoryChip(cat) {
    document.querySelectorAll('#postCatChips .cat-chip').forEach(c => c.classList.toggle('active', c.dataset.cat === cat));
    document.getElementById('postCategory').value = cat;
}

// ── Modal media state (photo posts) ───────────────────────
let modalExistingMedia = [];   // [{type:'image', url}] kept from the post being edited
let modalNewFiles = [];        // [{file, previewUrl}] picked in this session

function resetModalMedia() {
    modalNewFiles.forEach(item => { try { URL.revokeObjectURL(item.previewUrl); } catch (e) {} });
    modalExistingMedia = [];
    modalNewFiles = [];
    renderMediaPreviews();
}

// Called by the file input (multiple) — accumulates picks across several chooses.
function addPickedImages(input) {
    const room = 10 - (modalExistingMedia.length + modalNewFiles.length);
    const files = Array.from(input.files || []).slice(0, Math.max(room, 0));
    if (Array.from(input.files || []).length > files.length) {
        showToast('Maximum 10 images per post', 'error');
    }
    files.forEach(f => modalNewFiles.push({ file: f, previewUrl: URL.createObjectURL(f) }));
    input.value = '';   // allow re-picking the same file later
    renderMediaPreviews();
}

function removeExistingMedia(i) {
    modalExistingMedia.splice(i, 1);
    renderMediaPreviews();
}

function removeNewFile(i) {
    const item = modalNewFiles.splice(i, 1)[0];
    if (item) { try { URL.revokeObjectURL(item.previewUrl); } catch (e) {} }
    renderMediaPreviews();
}

function renderMediaPreviews() {
    const box = document.getElementById('mediaPreviewList');
    if (!box) return;
    let html = '';
    modalExistingMedia.forEach((m, i) => {
        const src = m.url.startsWith('http') ? m.url : API + m.url;
        html += `<div class="media-preview-item"><img src="${escapeHtml(src)}" alt=""><button type="button" class="media-preview-remove" onclick="removeExistingMedia(${i})" title="Remove">&times;</button></div>`;
    });
    modalNewFiles.forEach((item, i) => {
        html += `<div class="media-preview-item"><img src="${item.previewUrl}" alt=""><button type="button" class="media-preview-remove" onclick="removeNewFile(${i})" title="Remove">&times;</button></div>`;
    });
    box.innerHTML = html;

    const disp = document.getElementById('fileNameDisplay');
    const total = modalExistingMedia.length + modalNewFiles.length;
    if (disp) disp.textContent = total ? `${total} image${total > 1 ? 's' : ''} selected` : 'No files chosen';
}

// Upload one image via the shared chat upload endpoint; returns its URL.
async function uploadImageFile(file) {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch(API + '/chat/upload', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
        body: fd
    });
    if (!res.ok) throw new Error('upload failed');
    const data = await res.json();
    return data.file_url;
}

// ── Video URL rows ────────────────────────────────────────
function addVideoUrlRow(value = '', removable = true) {
    const container = document.getElementById('videoUrlsContainer');
    if (!container) return;
    const div = document.createElement('div');
    div.className = 'video-url-wrapper';
    div.innerHTML = `
        <input type="url" class="form-control video-url-input" placeholder="https://iframe.mediadelivery.net/embed/...">
        ${removable ? `<button type="button" class="btn-remove-opt" onclick="this.parentElement.remove()" style="background:none;border:none;color:#ef4444;cursor:pointer;"><i data-lucide="x"></i></button>` : ''}
    `;
    div.querySelector('input').value = value;
    container.appendChild(div);
    if (window.lucide) lucide.createIcons();
}

function resetVideoUrls(urls) {
    const container = document.getElementById('videoUrlsContainer');
    if (!container) return;
    container.innerHTML = '';
    const list = (urls && urls.length) ? urls : [''];
    list.forEach((u, i) => addVideoUrlRow(u, i > 0));
}

// ── Poll option rows (text + optional image) ──────────────
function addPollOptionRow(removable = false, opt = null) {
    const container = document.getElementById('pollOptionsContainer');
    if (!container) return;
    const n = container.querySelectorAll('.poll-option-wrapper').length + 1;
    const readOnly = !!opt;   // prefilled rows (edit mode) are not editable

    const div = document.createElement('div');
    div.className = 'poll-option-wrapper';
    div.innerHTML = `
        <input type="text" class="form-control poll-option-input" placeholder="Option ${n}" ${readOnly ? 'disabled' : ''}>
        <input type="file" class="poll-opt-file" accept="image/*" style="display:none;" onchange="pollOptFileChanged(this)">
        <img class="poll-opt-thumb" style="display:none;" alt="" title="Remove image" onclick="clearPollOptImage(this)">
        ${readOnly ? '' : `<button type="button" class="poll-opt-img-btn" title="Add image" onclick="this.parentElement.querySelector('.poll-opt-file').click()"><i data-lucide="image"></i></button>`}
        ${removable && !readOnly ? `<button type="button" class="btn-remove-opt" onclick="this.parentElement.remove()" style="background:none;border:none;color:#ef4444;cursor:pointer;"><i data-lucide="x"></i></button>` : ''}
    `;
    if (opt) {
        div.querySelector('.poll-option-input').value = opt.text || '';
        if (opt.image_url) {
            const thumb = div.querySelector('.poll-opt-thumb');
            thumb.src = opt.image_url.startsWith('http') ? opt.image_url : API + opt.image_url;
            thumb.style.display = 'block';
            thumb.onclick = null;
        }
    }
    container.appendChild(div);
    if (window.lucide) lucide.createIcons();
}

// options: existing poll options (edit mode, read-only) or nothing (fresh 2 rows).
function resetPollOptions(options) {
    const container = document.getElementById('pollOptionsContainer');
    if (!container) return;
    container.querySelectorAll('.poll-option-wrapper').forEach(el => el.remove());
    const addBtn = document.getElementById('addPollOptionBtn');
    if (options && options.length) {
        options.forEach(o => addPollOptionRow(false, o));
        if (addBtn) addBtn.style.display = 'none';
    } else {
        addPollOptionRow(false);
        addPollOptionRow(false);
        if (addBtn) addBtn.style.display = '';
    }
}

function pollOptFileChanged(input) {
    const thumb = input.parentElement.querySelector('.poll-opt-thumb');
    if (!thumb) return;
    if (input.files.length > 0) {
        thumb.src = URL.createObjectURL(input.files[0]);
        thumb.style.display = 'block';
    } else {
        thumb.style.display = 'none';
    }
}

function clearPollOptImage(thumb) {
    const fileInput = thumb.parentElement.querySelector('.poll-opt-file');
    if (fileInput) fileInput.value = '';
    thumb.style.display = 'none';
}

// ── Formatting toolbar (B / I / U on the body textarea) ───
function wrapSelection(textareaId, marker) {
    const ta = document.getElementById(textareaId);
    if (!ta) return;
    const start = ta.selectionStart, end = ta.selectionEnd;
    const val = ta.value;
    const sel = val.slice(start, end);
    const before = val.slice(0, start), after = val.slice(end);

    if (sel.startsWith(marker) && sel.endsWith(marker) && sel.length >= marker.length * 2) {
        // Selection includes the markers → unwrap
        const inner = sel.slice(marker.length, sel.length - marker.length);
        ta.value = before + inner + after;
        ta.setSelectionRange(start, start + inner.length);
    } else if (before.endsWith(marker) && after.startsWith(marker)) {
        // Markers sit just outside the selection → unwrap
        ta.value = before.slice(0, -marker.length) + sel + after.slice(marker.length);
        ta.setSelectionRange(start - marker.length, end - marker.length);
    } else {
        ta.value = before + marker + sel + marker + after;
        ta.setSelectionRange(start + marker.length, end + marker.length);
    }
    ta.focus();
}

// Reset the modal to a clean "create" state and open it.
function openCreateModal() {
    editingPostId = null;
    const form = document.getElementById('createPostForm');
    if (form) form.reset();
    document.getElementById('modalTitle').textContent = 'Create AI Update';
    document.getElementById('submitPostBtn').textContent = 'Post Update';
    selectCategoryChip('news');
    selectPostType('text');
    resetModalMedia();
    resetVideoUrls();
    resetPollOptions();
    document.getElementById('createPostModal').style.display = 'flex';
    if (window.lucide) lucide.createIcons();
}

// Open the modal pre-filled with an existing post's data (edit mode).
function openEditModal(postId) {
    const post = postCache[postId];
    if (!post) return;
    editingPostId = postId;
    const form = document.getElementById('createPostForm');
    if (form) form.reset();

    document.getElementById('modalTitle').textContent = 'Edit AI Update';
    document.getElementById('submitPostBtn').textContent = 'Save Changes';
    document.getElementById('postTitle').value = post.title || '';
    document.getElementById('postBody').value = post.body || '';
    selectCategoryChip(post.category || 'news');
    selectPostType(post.post_type || 'text');

    const media = postMediaList(post);
    resetModalMedia();
    modalExistingMedia = media.filter(m => m.type === 'image');
    renderMediaPreviews();
    resetVideoUrls(media.filter(m => m.type === 'video').map(m => m.url));

    // Poll content can't be edited via the API — show it read-only.
    if (post.post_type === 'poll' && post.poll) {
        document.getElementById('pollQuestion').value = post.poll.question || '';
        document.getElementById('pollQuestion').disabled = true;
        resetPollOptions(post.poll.options || []);
    } else {
        document.getElementById('pollQuestion').disabled = false;
        resetPollOptions();
    }

    document.getElementById('createPostModal').style.display = 'flex';
    if (window.lucide) lucide.createIcons();
}

function closeCreateModal() {
    document.getElementById('createPostModal').style.display = 'none';
    editingPostId = null;
    const pq = document.getElementById('pollQuestion');
    if (pq) pq.disabled = false;
    resetModalMedia();
}

async function deletePost(postId) {
    if (!confirm("Are you sure you want to delete this post?")) return;
    try {
        const res = await fetch(`${API}/ai-updates/posts/${postId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        if (!res.ok) throw new Error('Failed to delete post');
        
        showToast("Post deleted successfully");
        document.getElementById(`post-${postId}`).remove();
        
    } catch (err) {
        showToast("Error deleting post", "error");
    }
}

async function togglePin(postId) {
    try {
        const res = await fetch(`${API}/ai-updates/posts/${postId}/pin`, {
            method: 'PATCH',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        if (!res.ok) throw new Error('Failed to pin post');
        
        showToast("Post pin toggled");
        await loadFeed(1); // reload to sort properly
        
    } catch (err) {
        showToast("Error pinning post", "error");
    }
}

function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

const URL_RE = /(https?:\/\/[^\s<]+|www\.[^\s<]+)/g;
function prettyDomain(href) {
    try { return new URL(href).hostname.replace(/^www\./, ''); }
    catch (e) { return 'Visit Link'; }
}

// Turn one (already-escaped) URL match into a lime pill button labelled with the domain.
function urlButtonHtml(match) {
    // Keep trailing punctuation out of the link.
    let url = match;
    let trail = '';
    const t = url.match(/[.,!?;:)\]}'"]+$/);
    if (t) { trail = t[0]; url = url.slice(0, -trail.length); }
    const href = url.startsWith('www.') ? 'https://' + url : url;
    const label = prettyDomain(href);
    return `<a href="${href}" target="_blank" rel="noopener noreferrer" class="ai-post-link-btn" dir="ltr"><i class="fa-solid fa-arrow-up-right-from-square"></i><span>${escapeHtml(label)}</span></a>${trail}`;
}

// Escape first (XSS-safe), then turn each URL — in place, inline — into a button
// that opens the link in a new tab.
function linkifyHtml(text) {
    const escaped = escapeHtml(text || '');
    return escaped.replace(URL_RE, urlButtonHtml);
}

// Lightweight formatting on escaped text: **bold**, *italic*, __underline__.
function mdFormat(escaped) {
    return escaped
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/__([^_]+)__/g, '<u>$1</u>')
        .replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
}

// Remove formatting markers (matched pairs only) — used for plain-text excerpts.
function stripMd(text) {
    return (text || '')
        .replace(/\*\*([^*]+)\*\*/g, '$1')
        .replace(/__([^_]+)__/g, '$1')
        .replace(/\*([^*\n]+)\*/g, '$1');
}

// Rich post body: escape → linkify URLs → markdown-format the text between them.
// URLs are handled separately so markers inside a URL (e.g. underscores) stay intact.
function renderRich(text) {
    const escaped = escapeHtml(text || '');
    const parts = escaped.split(URL_RE);   // capture group keeps URLs at odd indices
    return parts.map((part, i) => i % 2 === 1 ? urlButtonHtml(part) : mdFormat(part)).join('');
}

// ── Active Users Sidebar ──────────────────────────────────
async function loadActiveUsers() {
    const list = document.getElementById('aiActiveUsersList');
    if (!list) return;
    try {
        // currentUser is already set from DOMContentLoaded — no need for another fetch
        if (currentUser) {
            const streakElem = document.getElementById('streakCount');
            if (streakElem) streakElem.textContent = currentUser.streak_days || 0;
        }
        
        const membersRes = await fetch(API + '/chat/members', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        const members = await membersRes.json();
        
        // Filter to online members, fetch up to 50 for scroll
        const activeMembers = members.filter(m => m.is_online).slice(0, 50);

        const headerEl = document.querySelector('.ai-sidebar-header h3');
        if (headerEl) headerEl.textContent = `Online Now (${activeMembers.length})`;

        if (activeMembers.length === 0) {
            list.innerHTML = '<div style="text-align:center;color:#888;font-size:0.85rem;padding:20px 0;">No one is online right now</div>';
            return;
        }

        const hiddenCount = activeMembers.length - 10;

        list.innerHTML = activeMembers.map(m => `
            <div class="ai-active-user-item">
                <div class="ai-active-user-av" onclick="openUserProfile(${m.id})" style="cursor: pointer;">
                    <img src="${getAvatarSrc(m)}" alt="">
                    <span class="online-dot"></span>
                </div>
                <div class="ai-active-user-info">
                    <div class="ai-active-user-name">${escapeHtml(m.full_name)}</div>
                    <div class="ai-active-user-badge ${getBadgeClass(m.badge)}">${escapeHtml(getRoleLabel(m))}</div>
                </div>
            </div>
        `).join('');

        // Apply scroll container so extra users are accessible via scroll
        list.style.maxHeight = '420px';
        list.style.overflowY = 'auto';
        list.style.scrollbarWidth = 'thin';
        list.style.scrollbarColor = '#333 transparent';
        list.style.paddingRight = '4px';

        if (hiddenCount > 0) {
            list.innerHTML += `<div style="text-align:center;font-size:0.75rem;color:#555;padding:8px 0 4px;border-top:1px solid #222;margin-top:8px;">scroll to see ${hiddenCount} more</div>`;
        }
    } catch(err) {
        list.innerHTML = '<div style="text-align:center;color:#888;font-size:0.85rem;padding:20px 0;">Could not load users</div>';
    }
}

function getBadgeClass(badgeName) {
    if (!badgeName) return 'badge-member';
    const n = badgeName.toLowerCase();
    if (n.includes('admin') || n.includes('Manage')) return 'badge-admin';
    if (n.includes('pro')) return 'badge-pro';
    if (n.includes('vip')) return 'badge-vip';
    return 'badge-member';
}

// ═══════════════════════════════════════
//  USER PROFILE PANEL
// ═══════════════════════════════════════

async function openUserProfile(userId) {
    if (!userId) return;
    const panel = document.getElementById('profilePanel');
    if (!panel) return;
    panel.classList.add('open');

    // Reset state
    showProfileLoading(true);
    document.getElementById('ppError').style.display = 'none';

    try {
        const token = localStorage.getItem('token');
        const res = await fetch(`${API}/profile/${userId}/public`, {
            headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        if (!res.ok) throw new Error('Failed to load profile');
        const profile = await res.json();

        renderProfilePanel(profile);
    } catch (err) {
        console.error('Profile load error:', err);
        showProfileLoading(false);
        document.getElementById('ppError').style.display = 'block';
    }
}

let currentProfileUserId = null;

function renderProfilePanel(p) {
    showProfileLoading(false);
    currentProfileUserId = p.id;

    // Show/hide DM button (hide if viewing own profile)
    const dmBtn = document.getElementById('ppDmBtn');
    if (dmBtn) {
        dmBtn.style.display = (p.id === currentUser?.id) ? 'none' : 'flex';
    }

    // Avatar
    const avatarEl = document.getElementById('ppAvatar');
    if (p.avatar_url) {
        avatarEl.src = p.avatar_url.startsWith('http') ? p.avatar_url : API + p.avatar_url;
    } else if (p.selected_avatar) {
        avatarEl.src = `src/imgs/avatars/${p.selected_avatar}`;
    } else {
        avatarEl.src = generateInitialsAvatar(p.full_name);
    }

    // Online dot
    const dot = document.getElementById('ppOnlineDot');
    dot.className = 'pp-online-dot' + (p.is_online ? ' online' : '');
    dot.title = p.is_online ? 'Online Now' : 'Unavailable';

    // Name
    document.getElementById('ppName').textContent = p.full_name;

    // Badge
    const badgeEl = document.getElementById('ppBadge');
    const resolvedPpBadge = getRoleLabel(p);
    badgeEl.textContent = resolvedPpBadge;
    badgeEl.className = 'pp-badge ' + (
        resolvedPpBadge === 'Admin' ? 'admin' :
        resolvedPpBadge === 'Pro Member' ? 'pro' : 'member'
    );

    // User ID — visible to admins/owners only (owners are always admins)
    const idEl = document.getElementById('ppUserId');
    if (idEl) {
        if (currentUser && (currentUser.is_admin || currentUser.is_owner)) {
            idEl.textContent = `🆔 ID: ${p.id}`;
            idEl.style.display = 'block';
        } else {
            idEl.style.display = 'none';
        }
    }

    // Bio
    const bioEl = document.getElementById('ppBio');
    bioEl.textContent = p.bio || 'No bio yet';
    bioEl.style.fontStyle = p.bio ? 'normal' : 'italic';
    bioEl.style.color = p.bio ? '#b8b8b8' : '#5a5648';

    // Social media
    const socialLink = document.getElementById('ppSocialLink');
    const socialText = document.getElementById('ppSocialText');
    if (p.social_media_url) {
        socialLink.href = p.social_media_url;
        try {
            const url = new URL(p.social_media_url);
            socialText.textContent = url.hostname + url.pathname;
        } catch {
            socialText.textContent = p.social_media_url;
        }
        socialLink.classList.remove('pp-hidden');
    } else {
        socialLink.classList.add('pp-hidden');
    }

    // Stats
    document.getElementById('ppLevel').textContent = p.level || 1;
    document.getElementById('ppXp').textContent = (p.xp || 0).toLocaleString();
    document.getElementById('ppStreak').textContent = p.streak_days || 0;
    document.getElementById('ppPosts').textContent = p.post_count || 0;

    // Joined
    document.getElementById('ppJoined').innerHTML = `📅 ${p.joined_at || 'Recently'}`;
}

function showProfileLoading(show) {
    document.getElementById('ppLoading').style.display = show ? 'flex' : 'none';
    const ppInfo = document.querySelector('.pp-info');
    const ppStats = document.querySelector('.pp-stats');
    const ppBadge = document.getElementById('ppBadge');
    const ppBio = document.getElementById('ppBio');
    const ppJoined = document.getElementById('ppJoined');
    const ppAvatarWrap = document.querySelector('.pp-avatar-wrap');
    if (ppInfo) ppInfo.style.visibility = show ? 'hidden' : 'visible';
    if (ppStats) ppStats.style.visibility = show ? 'hidden' : 'visible';
    if (ppBadge) ppBadge.style.visibility = show ? 'hidden' : 'visible';
    if (ppBio) ppBio.style.visibility = show ? 'hidden' : 'visible';
    if (ppJoined) ppJoined.style.visibility = show ? 'hidden' : 'visible';
    if (ppAvatarWrap) ppAvatarWrap.style.visibility = show ? 'hidden' : 'visible';
}

function closeUserProfile() {
    const panel = document.getElementById('profilePanel');
    if (panel) panel.classList.remove('open');
}

// Close on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeUserProfile();
});

// Generate initials avatar as data URL
function generateInitialsAvatar(name) {
    const canvas = document.createElement('canvas');
    canvas.width = 88;
    canvas.height = 88;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = '#1a1a1a';
    ctx.beginPath();
    ctx.arc(44, 44, 44, 0, Math.PI * 2);
    ctx.fill();

    const initials = (name || '?')
        .split(' ')
        .map(w => w[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);

    ctx.fillStyle = '#c1ff11';
    ctx.font = 'bold 28px Cairo, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(initials, 44, 44);

    return canvas.toDataURL();
}

async function startDmFromProfile() {
    if (!currentProfileUserId || currentProfileUserId === currentUser?.id) return;
    closeUserProfile();
    window.location.href = `direct-messages.html?v=5&dm=${currentProfileUserId}`;
}
