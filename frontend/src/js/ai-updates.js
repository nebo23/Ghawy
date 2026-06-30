// ai-updates.js
let currentUser = null;

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
        await loadFeed();
        if (typeof loadActiveUsers === 'function') {
            loadActiveUsers();
        }

    } catch (err) {
        console.error("AI Updates Crash:", err);
        // Fallback or alert instead of infinite reload
    }
});

// ── Helpers ───────────────────────────────────────────────

// ── Feed ──────────────────────────────────────────────────
async function loadFeed(page = 1) {
    const feed = document.getElementById('aiFeed');
    if (page === 1) feed.innerHTML = '<div class="skeleton-card"></div><div class="skeleton-card"></div>';
    
    try {
        const res = await fetch(`${API}/ai-updates/posts?page=${page}&limit=20`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        if (!res.ok) throw new Error('Failed to load posts');
        
        const data = await res.json();
        
        if (page === 1) feed.innerHTML = '';
        
        if (data.posts.length === 0 && page === 1) {
            feed.innerHTML = `
                <div class="ai-empty-state">
                    <i data-lucide="sparkles"></i>
                    <h3>No AI Updates Yet</h3>
                    <p>Check back later for the latest news and polls.</p>
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
function createPostElement(post) {
    const div = document.createElement('div');
    div.className = `ai-post-card ${post.is_pinned ? 'pinned' : ''}`;
    div.id = `post-${post.id}`;

    let pinHtml = post.is_pinned ? `<i data-lucide="pin" class="pin-badge"></i>` : '';
    
    let adminActions = '';
    if (currentUser.is_admin) {
        adminActions = `
            <div class="ai-post-admin-actions">
                <button class="admin-action-btn pin-btn" onclick="togglePin(${post.id})" title="${post.is_pinned ? 'Unpin' : 'Pin'}">
                    <i data-lucide="pin"></i>
                </button>
                <button class="admin-action-btn delete" onclick="deletePost(${post.id})" title="Delete">
                    <i data-lucide="trash-2"></i>
                </button>
            </div>
        `;
    }

    let contentHtml = '';
    
    // Photo
    if (post.post_type === 'photo' && post.image_url) {
        const fullUrl = post.image_url.startsWith('http') ? post.image_url : API + post.image_url;
        contentHtml += `<div class="ai-post-media"><img src="${fullUrl}" alt="Post Image"></div>`;
    }
    
    // Video
    if (post.post_type === 'video' && post.video_url) {
        contentHtml += `
            <div class="ai-post-media">
                <iframe src="${post.video_url}" loading="lazy" allow="accelerometer; gyroscope; autoplay; encrypted-media; picture-in-picture;" allowfullscreen></iframe>
            </div>
        `;
    }

    // Poll
    if (post.post_type === 'poll' && post.poll) {
        contentHtml += renderPollHtml(post.poll);
    }

    // Reactions setup
    const heartCount = post.reaction_counts['❤️'] || 0;
    const isHeartActive = post.user_reactions.includes('❤️');
    let reactionsHtml = `
        <button class="reaction-btn ${isHeartActive ? 'active' : ''}" onclick="toggleReaction(${post.id}, '❤️')">
            <i data-lucide="heart" class="${isHeartActive ? 'filled-heart' : ''}"></i>
            <span class="count">${heartCount}</span>
        </button>
    `;

    div.innerHTML = `
        ${pinHtml}
        <div class="ai-post-header">
            <img src="${getAvatarSrc(post.author)}" class="ai-post-avatar" onclick="openUserProfile(${post.author?.id})" style="cursor: pointer;">
            <div class="ai-post-meta">
                <div class="ai-post-author">
                    ${post.author?.full_name || 'Admin'}
                    ${post.author?.is_admin ? '<span class="admin-badge">Admin</span>' : ''}
                </div>
                <div class="ai-post-time">${post.time_ago}</div>
            </div>
            ${adminActions}
        </div>
        <div class="ai-post-title" dir="auto">${escapeHtml(post.title)}</div>
        <div class="ai-post-body" dir="auto">${escapeHtml(post.body)}</div>
        ${contentHtml}
        
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

function renderPollHtml(poll) {
    const hasVoted = poll.user_voted_option_id !== null;
    let html = `
        <div class="ai-poll-container" id="poll-${poll.id}">
            <div class="ai-poll-question" dir="auto">${escapeHtml(poll.question)}</div>
    `;

    poll.options.forEach(opt => {
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

function createCommentElement(comment) {
    let repliesHtml = '';
    if (comment.replies && comment.replies.length > 0) {
        repliesHtml = `
            <div class="ai-comment-replies">
                ${comment.replies.map(r => createCommentElement(r)).join('')}
            </div>
        `;
    }

    const isAuthor = currentUser.id === comment.author.id;
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

    if (canDelete) {
        actionsHtml += `<button class="comment-action-btn delete" onclick="deleteComment(${comment.post_id}, ${comment.id})"><i data-lucide="trash-2"></i></button>`;
    }

    const div = document.createElement('div');
    div.className = 'ai-comment';
    div.id = `comment-${comment.id}`;
    div.innerHTML = `
        <img src="${getAvatarSrc(comment.author)}" class="ai-comment-avatar" onclick="openUserProfile(${comment.author?.id})" style="cursor: pointer;">
        <div style="flex:1;">
            <div class="ai-comment-content">
                <div class="ai-comment-header">
                    <span class="ai-comment-author">${comment.author?.full_name || 'User'}</span>
                    <span class="ai-comment-time">${comment.time_ago}</span>
                </div>
                <div class="ai-comment-body" dir="auto">${escapeHtml(comment.body)}</div>
            </div>
            <div class="ai-comment-actions">
                ${actionsHtml}
            </div>
            ${repliesHtml}
        </div>
    `;

    return div;
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
    const modal = document.getElementById('createPostModal');
    
    if (btn) {
        btn.addEventListener('click', () => {
            modal.style.display = 'flex';
        });
    }

    // Tabs
    const tabs = document.querySelectorAll('.post-type-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            const type = tab.dataset.type;
            document.getElementById('postType').value = type;
            
            document.getElementById('videoFields').style.display = type === 'video' ? 'block' : 'none';
            document.getElementById('photoFields').style.display = type === 'photo' ? 'block' : 'none';
            document.getElementById('pollFields').style.display = type === 'poll' ? 'block' : 'none';
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
            
            const div = document.createElement('div');
            div.className = 'poll-option-wrapper';
            div.innerHTML = `
                <input type="text" class="form-control poll-option-input" placeholder="Option ${currentCount + 1}">
                <button type="button" class="btn-remove-opt" onclick="this.parentElement.remove()" style="background:none;border:none;color:#ef4444;cursor:pointer;"><i data-lucide="x"></i></button>
            `;
            container.appendChild(div);
            lucide.createIcons();
        });
    }

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
            
            let imageUrl = '';
            if (currentPostType === 'photo') {
                const fileInput = document.getElementById('postImageFile');
                if (fileInput.files.length > 0) {
                    const formData = new FormData();
                    formData.append('file', fileInput.files[0]);
                    try {
                        const uploadRes = await fetch(API + '/chat/upload', {
                            method: 'POST',
                            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
                            body: formData
                        });
                        if (uploadRes.ok) {
                            const uploadData = await uploadRes.json();
                            imageUrl = uploadData.file_url;
                        }
                    } catch (e) {
                        console.error('Image upload failed:', e);
                    }
                }
            }
            
            const payload = {
                post_type: currentPostType,
                title: title,
                body: body,
                video_url: document.getElementById('postVideoUrl')?.value || null,
                image_url: imageUrl || null,
            };

            if (payload.post_type === 'poll') {
                const question = document.getElementById('pollQuestion').value;
                const optInputs = document.querySelectorAll('.poll-option-input');
                const options = [];
                optInputs.forEach(i => {
                    if (i.value.trim()) options.push({ text: i.value.trim() });
                });

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
                const res = await fetch(API + '/ai-updates/posts', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${localStorage.getItem('token')}`
                    },
                    body: JSON.stringify(payload)
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Failed to create post');
                }

                showToast("Post created successfully");
                closeCreateModal();
                form.reset();
                // Reset options to 2
                document.getElementById('pollOptionsContainer').innerHTML = `
                    <label>Options (2-4)</label>
                    <div class="poll-option-wrapper"><input type="text" class="form-control poll-option-input" placeholder="Option 1"></div>
                    <div class="poll-option-wrapper"><input type="text" class="form-control poll-option-input" placeholder="Option 2"></div>
                `;
                
                await loadFeed(1);

            } catch (err) {
                showToast(err.message, "error");
            } finally {
                btn.disabled = false;
                btn.textContent = 'Post Update';
            }
        });
    }
}

function closeCreateModal() {
    document.getElementById('createPostModal').style.display = 'none';
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
