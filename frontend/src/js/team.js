(async () => {
  const user = await requireActiveUser();
  if (!user) return;
})();

// ═══ AUTH GUARD ═══
const token = localStorage.getItem('token');
if (!token) { localStorage.removeItem('user'); window.location.href = '/login'; }

const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };
function authHeaders() { return headers; }

let allUsers = [];
let filteredUsers = [];
let currentPage = 1;
const LIMIT = 20;
let selectedUserId = null;
let currentUserIsAdmin = false;
let currentUserIsOwner = false;

// ═══ TAB SWITCHING ═══
let paymentsLoaded = false;
let analyticsLoaded = false;

function initTabs() {
  const tabs = document.querySelectorAll('.team-section-btn');
  const panels = document.querySelectorAll('.tab-panel');
  const breadcrumb = document.getElementById('page-breadcrumb');
  const heading = document.getElementById('page-heading');

  const titleMap = {
    'users': 'Team Dashboard',
    'payments': 'Payments & Subscriptions',
    'analytics': 'Platform Analytics',
    'pending-requests': 'Pending Requests',
    'live-sessions': 'Live Sessions',
    'guest-of-honors': 'Guest of Honors',
    'courses': 'Courses Management',
    'projects': 'Projects Review',
    'reports': 'Daily Reports',
    'feedbacks': 'Community Feedbacks'
  };

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      const target = tab.dataset.tab;
      panels.forEach(p => p.style.display = 'none');

      const targetPanel = document.getElementById(`tab-${target}`);
      if (targetPanel) targetPanel.style.display = 'block';

      if (breadcrumb && heading && titleMap[target]) {
        breadcrumb.textContent = titleMap[target];
        heading.textContent = titleMap[target];
      }

      if (target === 'payments' && !paymentsLoaded) {
        loadPaymentsTab();
        paymentsLoaded = true;
      }
      if (target === 'analytics' && !analyticsLoaded) {
        loadAnalyticsTab();
        analyticsLoaded = true;
      }
      if (target === 'pending-requests') {
        mprCurrentPage = 1;
        loadPendingRequestsTab();
      }
      if (target === 'live-sessions') {
        loadLiveSessionsTab();
      }
      if (target === 'courses') {
        loadCoursesTab();
      }
      if (target === 'projects') {
        loadProjectsTab();
      }
      if (target === 'guest-of-honors') {
        loadGohTab();
      }
      if (target === 'reports') {
        if (typeof loadReportsTab === 'function') loadReportsTab();
      }
      if (target === 'feedbacks') {
        if (typeof loadFeedbacksTab === 'function') loadFeedbacksTab();
      }
    });
  });

  // 🔒 Hide owner-only tabs from non-owner admins
  // This runs after profile is loaded — called from loadTeamPage() after setting currentUserIsOwner
  function applyTabVisibility() {
    // 'users' (Members), 'payments', 'pending-requests' and 'analytics' are visible
    // to admins too — contact details/delete are restricted per-row below and enforced
    // server-side. The remaining content-management tabs stay owner-only.
    const ownerOnlyTabs = ['live-sessions', 'guest-of-honors', 'courses'];
    ownerOnlyTabs.forEach(tabId => {
      const btn = document.querySelector(`.team-section-btn[data-tab="${tabId}"]`);
      if (btn) {
        btn.style.display = currentUserIsOwner ? '' : 'none';
      }
    });

    // If the active tab is now hidden (non-owner admin landing on Members),
    // switch to the first visible tab so the page isn't blank.
    if (!currentUserIsOwner) {
      const activeBtn = document.querySelector('.team-section-btn.active');
      if (!activeBtn || activeBtn.style.display === 'none') {
        const firstVisible = Array.from(document.querySelectorAll('.team-section-btn'))
          .find(b => b.style.display !== 'none');
        if (firstVisible) firstVisible.click();
      }
    }
  }
  window.applyTabVisibility = applyTabVisibility;
}

// ── Load ────────────────────────────────────────────
async function loadTeamPage() {
  // Initialize tabs
  initTabs();

  // Load sidebar user info
  try {
    const res = await fetch(API + '/profile/me', { headers });
    if (res.ok) {
      const u = await res.json();
      const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
      setTxt('sidebarName', u.full_name);
      setTxt('topbarName', u.full_name);
      setTxt('dropdownName', u.full_name);

      // Update Badge
      const badgeLabel = getBadgeLabel(u.badge);
      currentUserIsAdmin = !!u.is_admin;
      currentUserIsOwner = !!u.is_owner;
      if (typeof applyTabVisibility === 'function') applyTabVisibility();
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
    }
  } catch (e) { }
  // Members list is available to admins (owners + non-owner admins).
  // Contact details are redacted server-side for non-owner admins.
  if (currentUserIsAdmin) await loadUsers();

  // Set up listeners for Users tab
  document.getElementById('search-input')?.addEventListener('keyup', (e) => {
    if (e.key === 'Enter') { currentPage = 1; loadUsersTab(); }
  });
  document.getElementById('status-filter')?.addEventListener('change', () => {
    currentPage = 1; loadUsersTab();
  });
  document.getElementById('role-filter')?.addEventListener('change', () => {
    currentPage = 1; loadUsersTab();
  });

  // Set up listeners for Payments tab
  document.getElementById('pay-search')?.addEventListener('keyup', (e) => {
    if (e.key === 'Enter') { payCurrentPage = 1; loadPaymentsTab(); }
  });
  document.getElementById('pay-status-filter')?.addEventListener('change', () => {
    payCurrentPage = 1; loadPaymentsTab();
  });
  document.getElementById('pay-method-filter')?.addEventListener('change', () => {
    payCurrentPage = 1; loadPaymentsTab();
  });

  document.getElementById('project-search')?.addEventListener('keyup', (e) => {
    if (e.key === 'Enter') loadProjectsTab();
  });
  document.getElementById('project-status-filter')?.addEventListener('change', () => {
    loadProjectsTab();
  });

  loadManualPaymentStats(); // fetch badge count
}

async function loadUsers() {
  showTableLoading();
  try {
    const res = await fetch(API + '/admin/users', { headers });
    if (res.status === 403) {
      showToast('❌ Admin access required', 'error');
      document.getElementById('users-tbody').innerHTML = `<tr><td colspan="11" style="text-align:center;color:#ef4444;padding:40px">⛔ Admin access required</td></tr>`;
      return;
    }
    if (!res.ok) { showToast('❌ Failed to load users', 'error'); return; }
    allUsers = await res.json();
    filteredUsers = [...allUsers];
    updateStats();
    renderTable();
  } catch (e) {
    showToast('❌ Failed to load users', 'error');
  }
}

// ── Stats ────────────────────────────────────────────
function updateStats() {
  document.getElementById('stat-total').textContent = allUsers.length;
  document.getElementById('stat-active').textContent = allUsers.filter(u => u.is_active).length;
  document.getElementById('stat-inactive').textContent = allUsers.filter(u => !u.is_active).length;
  document.getElementById('stat-admins').textContent = allUsers.filter(u => u.is_admin).length;
}

// ── Render Table ────────────────────────────────────
function renderTable() {
  const start = (currentPage - 1) * LIMIT;
  const paginated = filteredUsers.slice(start, start + LIMIT);
  const tbody = document.getElementById('users-tbody');

  if (paginated.length === 0) {
    tbody.innerHTML = `<tr><td colspan="11" style="text-align:center;color:#888;padding:40px">No members found</td></tr>`;
    document.getElementById('pagination').innerHTML = '';
    return;
  }

  tbody.innerHTML = paginated.map(user => {
    // End date cell
    let endCell = '—';
    if (user.end_at) {
      const endDate = new Date(user.end_at);
      const days = Math.floor((endDate - new Date()) / (1000 * 60 * 60 * 24));
      const isOverdue = days < 0;
      const isSoon = days <= 3 && days >= 0;

      endCell = `
        <div class="charge-info">
          <div class="charge-date">${formatDate(user.end_at)}</div>
          <div class="charge-days ${isOverdue ? 'overdue' : isSoon ? 'soon' : ''}">
            ${isOverdue ? '⚠️ Expired' : isSoon ? `⚡ ${days}d left` : `${days}d`}
          </div>
        </div>`;
    }

    return `
    <tr>
      <td>
        <div class="member-cell">
          <img src="${user.avatar_url || '/static/avatars/default.png'}" class="member-avatar" onerror="this.src='./imgs/ghawi-logo.png'"/>
          <div>
            <div class="member-name">${escapeHtml(user.full_name)}</div>
            <div class="member-badge">${escapeHtml(getRoleLabel(user))}</div>
            <div class="member-id" style="font-size:11px;color:#888;font-weight:600;margin-top:2px;">🆔 ID: ${user.id}</div>
          </div>
        </div>
      </td>
      <td class="text-secondary">${currentUserIsOwner ? escapeHtml(user.email || '—') : '<span style="color:#666" title="Owners only">🔒</span>'}</td>
      <td class="text-secondary">${currentUserIsOwner ? (user.phone || '—') : '<span style="color:#666" title="Owners only">🔒</span>'}</td>
      <td class="text-secondary">${user.country || '—'}</td>
      <td class="text-secondary">${escapeHtml(user.governorate || '—')}</td>
      <td class="text-secondary">${formatBirthDate(user.birth_date)}</td>
      <td>
        <div style="font-size:13px">${formatDate(user.created_at)}</div>
        ${user.subscription_start ?
        `<div style="font-size:11px;color:#3f8ff9">💳 Since ${formatDate(user.subscription_start)}</div>`
        : ''}
      </td>
      <td>${endCell}</td>
      <td>
        <label class="t-switch">
          <input type="checkbox" ${user.is_active ? 'checked' : ''} onchange="toggleActive(${user.id}, this)"/>
          <span class="t-slider"></span>
        </label>
        ${user.winback_sent_at ? `<div style="font-size:10px;color:#f59e0b;margin-top:3px;white-space:nowrap;" title="Winback email sent ${formatDate(user.winback_sent_at)}">💌 Emailed</div>` : ''}
      </td>
      <td>
        <div style="display:flex;flex-direction:column;gap:4px;align-items:flex-start;">
          <span class="role-badge ${user.is_owner ? 'owner' : user.is_admin ? 'admin' : 'member'}"
            style="cursor:default;display:inline-flex;align-items:center;gap:4px;">
            ${user.is_owner
              ? '<i data-lucide="crown" style="width:14px;height:14px;margin-right:4px;"></i> Owner'
              : user.is_admin
                ? '<i data-lucide="shield-check" style="width:14px;height:14px;margin-right:4px;"></i> Admin'
                : '<i data-lucide="user" style="width:14px;height:14px;margin-right:4px;"></i> Member'}
          </span>
          <div style="display:flex;gap:4px;flex-wrap:wrap;">
            ${currentUserIsOwner ? `
              <button onclick="toggleAdmin(${user.id})"
                style="font-size:10px;padding:2px 7px;border-radius:4px;border:1px solid #444;background:transparent;color:#888;cursor:pointer;white-space:nowrap;"
                title="${user.is_admin ? 'Remove Admin' : 'Make Admin'}">
                ${user.is_admin ? '− Admin' : '+ Admin'}
              </button>
              <button onclick="toggleOwner(${user.id})"
                style="font-size:10px;padding:2px 7px;border-radius:4px;border:1px solid #a855f7;background:transparent;color:#a855f7;cursor:pointer;white-space:nowrap;"
                title="${user.is_owner ? 'Remove Owner' : 'Make Owner'}">
                ${user.is_owner ? '− Owner' : '+ Owner'}
              </button>
            ` : ''}
          </div>
        </div>
      </td>
      <td>
        <div class="action-btns">
          ${user.failed_charge_count > 0 ?
        `<span class="failed-badge" title="${user.failed_charge_count} failed charge(s)"><i data-lucide="alert-triangle" style="width:12px;height:12px;margin-right:2px;"></i>${user.failed_charge_count}</span>`
        : ''}
          <button class="btn-action" style="color:#3f8ff9" onclick="openExtendModal(${user.id}, '${escapeHtml(user.full_name).replace(/'/g, "\\'")}')" title="Extend Subscription"><i data-lucide="calendar-plus" style="width:14px;height:14px;"></i></button>
          <button class="btn-action reset" onclick="openResetPasswordModal(${user.id})" title="Reset Password"><i data-lucide="key" style="width:14px;height:14px;"></i></button>
          ${currentUserIsOwner && user.social_media_url ? `
          <a href="${escapeHtml(user.social_media_url)}" target="_blank" rel="noopener noreferrer"
            class="btn-action" style="color:#a855f7;text-decoration:none;display:inline-flex;align-items:center;"
            title="Social Link">
            <i data-lucide="link" style="width:14px;height:14px;"></i>
          </a>` : ''}
          ${currentUserIsOwner ? `<button class="btn-action delete" onclick="confirmDelete(${user.id}, '${escapeHtml(user.full_name).replace(/'/g, "\\'")}')" title="Delete"><i data-lucide="trash-2" style="width:14px;height:14px;"></i></button>` : ''}
        </div>
      </td>
    </tr>
  `}).join('');

  renderPagination();
  setTimeout(() => { if (typeof lucide !== 'undefined') lucide.createIcons(); }, 10);
}

// ── Search & Filter ──────────────────────────────────
let searchTimeout;
function handleSearch(val) {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    applyFilters(val, document.getElementById('status-filter').value);
  }, 300);
}

function handleFilter(status) {
  applyFilters(document.getElementById('search-input').value, status);
}

function applyFilters(search, status) {
  filteredUsers = allUsers.filter(u => {
    const matchSearch = !search ||
      u.full_name.toLowerCase().includes(search.toLowerCase()) ||
      (u.email && u.email.toLowerCase().includes(search.toLowerCase())) ||
      (u.phone && u.phone.toLowerCase().includes(search.toLowerCase()));
    const matchStatus = status === 'all' ||
      (status === 'active' && u.is_active) ||
      (status === 'inactive' && !u.is_active);
    return matchSearch && matchStatus;
  });
  currentPage = 1;
  renderTable();
}

// ── Toggle Active ────────────────────────────────────
async function toggleActive(userId, checkbox) {
  try {
    const res = await fetch(`${API}/admin/users/${userId}/toggle-active`, {
      method: 'PATCH', headers
    });
    const data = await res.json();
    if (res.ok) {
      const user = allUsers.find(u => u.id === userId);
      if (user) {
        user.is_active = data.is_active;
        user.end_at = data.end_at || null;
      }
      updateStats();
      renderTable();
      showToast(data.is_active ? '✅ User activated (30 days)' : '⏸️ User deactivated', 'success');
    } else {
      checkbox.checked = !checkbox.checked;
      showToast('❌ Failed to update', 'error');
    }
  } catch (e) {
    checkbox.checked = !checkbox.checked;
    showToast('❌ Network error', 'error');
  }
}

// ── Extend Subscription ──────────────────────────────
function openExtendModal(userId, userName) {
  selectedUserId = userId;
  const nameEl = document.getElementById('extend-user-name');
  if (nameEl) nameEl.textContent = userName;
  document.getElementById('extend-days').value = '30';
  document.getElementById('extend-modal').style.display = 'flex';
}

async function submitExtend() {
  const days = parseInt(document.getElementById('extend-days').value);
  if (!days || days < 1) { showToast('❌ Enter valid number of days', 'error'); return; }
  try {
    const res = await fetch(`${API}/admin/users/${selectedUserId}/set-subscription`, {
      method: 'PATCH', headers,
      body: JSON.stringify({ days })
    });
    const data = await res.json();
    if (res.ok) {
      const user = allUsers.find(u => u.id === selectedUserId);
      if (user) { user.is_active = true; user.end_at = data.end_at; }
      closeModal('extend-modal');
      updateStats();
      renderTable();
      showToast(`✅ Subscription extended for ${days} days`, 'success');
    } else {
      showToast(`❌ ${data.detail || 'Failed'}`, 'error');
    }
  } catch (e) {
    showToast('❌ Network error', 'error');
  }
}

// ── Toggle Admin ─────────────────────────────────────
async function toggleAdmin(userId) {
  try {
    const res = await fetch(`${API}/admin/users/${userId}/toggle-admin`, {
      method: 'PATCH', headers
    });
    if (res.ok) {
      const data = await res.json();
      const user = allUsers.find(u => u.id === userId);
      if (user) user.is_admin = data.is_admin;
      updateStats();
      renderTable();
      showToast(data.is_admin ? '🛡️ Made Admin' : '👤 Removed Admin', 'success');
    }
  } catch (e) {
    showToast('❌ Failed', 'error');
  }
}

// ── Toggle Owner ─────────────────────────────────────
async function toggleOwner(userId) {
  if (!currentUserIsOwner) return showToast('👑 Owners only', 'error');
  try {
    const res = await fetch(`${API}/admin/users/${userId}/toggle-owner`, {
      method: 'PATCH', headers
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed');
    }
    const data = await res.json();
    // Update the cache
    const user = allUsers.find(u => u.id === userId);
    if (user) {
      user.is_owner = data.is_owner;
      user.is_admin = data.is_admin;
    }
    renderTable();
    if (typeof lucide !== 'undefined') lucide.createIcons();
    showToast(data.is_owner ? '👑 Made Owner' : '👤 Removed Owner', 'success');
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}

// ── Add Member ───────────────────────────────────────
function openAddModal() {
  document.getElementById('add-name').value = '';
  document.getElementById('add-email').value = '';
  document.getElementById('add-password').value = '';
  document.getElementById('add-phone').value = '';
  document.getElementById('add-country').value = '';
  document.getElementById('add-active').checked = true;
  document.getElementById('add-admin').checked = false;
  document.getElementById('add-modal').style.display = 'flex';
}

async function submitAddMember() {
  const name = document.getElementById('add-name').value.trim();
  const email = document.getElementById('add-email').value.trim();
  const password = document.getElementById('add-password').value;

  if (!name || !email || !password) {
    showToast('❌ Name, email, and password are required', 'error');
    return;
  }
  if (password.length < 6) {
    showToast('❌ Password must be at least 6 characters', 'error');
    return;
  }

  try {
    const res = await fetch(API + '/admin/users/add', {
      method: 'POST', headers,
      body: JSON.stringify({
        full_name: name, email, password,
        phone: document.getElementById('add-phone').value.trim() || null,
        country: document.getElementById('add-country').value.trim() || null,
        is_active: document.getElementById('add-active').checked,
        is_admin: document.getElementById('add-admin').checked,
      })
    });
    const data = await res.json();
    if (res.ok) {
      closeModal('add-modal');
      showToast('✅ Member added successfully', 'success');
      await loadUsers();
    } else {
      showToast(`❌ ${data.detail || 'Failed to add member'}`, 'error');
    }
  } catch (e) {
    showToast('❌ Network error', 'error');
  }
}

// ── Reset Password ───────────────────────────────────
function openResetPasswordModal(userId) {
  selectedUserId = userId;
  document.getElementById('reset-password').value = '';
  document.getElementById('reset-modal').style.display = 'flex';
}

async function submitResetPassword() {
  const newPassword = document.getElementById('reset-password').value;
  if (!newPassword || newPassword.length < 6) {
    showToast('❌ Password must be at least 6 characters', 'error');
    return;
  }
  try {
    const res = await fetch(`${API}/admin/users/${selectedUserId}/reset-password`, {
      method: 'POST', headers,
      body: JSON.stringify({ new_password: newPassword })
    });
    if (res.ok) {
      closeModal('reset-modal');
      showToast('✅ Password reset successfully', 'success');
    } else {
      showToast('❌ Failed to reset password', 'error');
    }
  } catch (e) {
    showToast('❌ Network error', 'error');
  }
}

// ── Delete ───────────────────────────────────────────
function confirmDelete(userId, userName) {
  selectedUserId = userId;
  document.getElementById('delete-name').textContent = userName;
  document.getElementById('delete-modal').style.display = 'flex';
}

async function submitDelete() {
  try {
    const res = await fetch(`${API}/admin/users/${selectedUserId}`, {
      method: 'DELETE', headers
    });
    if (res.ok) {
      closeModal('delete-modal');
      showToast('✅ Member deleted', 'success');
      await loadUsers();
    } else {
      const data = await res.json();
      showToast(`❌ ${data.detail || 'Failed to delete'}`, 'error');
    }
  } catch (e) {
    showToast('❌ Network error', 'error');
  }
}

// ── Pagination ────────────────────────────────────────
// Windowed pager: prev/next arrows + a compact window of page numbers with
// ellipses, so the control never overflows no matter how many pages there are.
function buildPager(el, current, total, goFn) {
  if (!el) return;
  if (total <= 1) { el.innerHTML = ''; return; }

  const items = [1];
  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);
  if (start > 2) items.push('…');
  for (let i = start; i <= end; i++) items.push(i);
  if (end < total - 1) items.push('…');
  if (total > 1) items.push(total);

  let html = `<button class="page-btn page-arrow" ${current <= 1 ? 'disabled' : ''} onclick="${goFn}(${current - 1})" aria-label="Previous page">‹</button>`;
  html += items.map(p =>
    p === '…'
      ? `<span class="page-ellipsis">…</span>`
      : `<button class="page-btn ${p === current ? 'active' : ''}" onclick="${goFn}(${p})">${p}</button>`
  ).join('');
  html += `<button class="page-btn page-arrow" ${current >= total ? 'disabled' : ''} onclick="${goFn}(${current + 1})" aria-label="Next page">›</button>`;
  el.innerHTML = html;
}

function renderPagination() {
  const total = Math.ceil(filteredUsers.length / LIMIT);
  buildPager(document.getElementById('pagination'), currentPage, total, 'goToPage');
}

function goToPage(page) {
  currentPage = page;
  renderTable();
  window.scrollTo(0, 0);
}

// ── Helpers ───────────────────────────────────────────
function openModal(id) { document.getElementById(id).style.display = 'flex'; }
function closeModal(id) { document.getElementById(id).style.display = 'none'; }

// Backend sends naive UTC (no tz marker). Mark it UTC, then render in Egypt time
// (Africa/Cairo handles DST +2/+3) so dates aren't shown ~3h early.
function toEgyptDate(dateStr) {
  let s = String(dateStr);
  if (!/([zZ]|[+-]\d{2}:?\d{2})$/.test(s)) s += 'Z';
  return new Date(s);
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  const d = toEgyptDate(dateStr);
  if (isNaN(d)) return '—';
  return d.toLocaleDateString('en', { timeZone: 'Africa/Cairo', year: 'numeric', month: 'short', day: 'numeric' });
}

// Payment timestamps: date + time, in Egypt time.
function formatDateTime(dateStr) {
  if (!dateStr) return '—';
  const d = toEgyptDate(dateStr);
  if (isNaN(d)) return '—';
  return d.toLocaleString('en-GB', { timeZone: 'Africa/Cairo', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

// Birth date cell: "12 Mar 2001" plus the member's current age.
function formatBirthDate(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr + 'T00:00:00');
  if (isNaN(d)) return '—';
  const now = new Date();
  let age = now.getFullYear() - d.getFullYear();
  if (now.getMonth() < d.getMonth() || (now.getMonth() === d.getMonth() && now.getDate() < d.getDate())) age--;
  const dateTxt = d.toLocaleDateString('en', { year: 'numeric', month: 'short', day: 'numeric' });
  return `<div style="font-size:13px">${dateTxt}</div><div style="font-size:11px;color:#888">${age} yrs</div>`;
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function showTableLoading() {
  document.getElementById('users-tbody').innerHTML = `<tr><td colspan="11" style="text-align:center;color:#888;padding:40px">Loading...</td></tr>`;
}

// Close modal on overlay click
document.querySelectorAll('.modal-overlay-team').forEach(overlay => {
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) overlay.style.display = 'none';
  });
});


// ══════════════════════════════════════════════════════════
//  PAYMENTS TAB
// ══════════════════════════════════════════════════════════

let payCurrentPage = 1;
const PAY_LIMIT = 20;
let paySearchTimeout;

async function loadPaymentsTab() {
  await Promise.all([loadPaymentStats(), loadPayments()]);
  initPaymentFilters();
}

function initPaymentFilters() {
  const searchInput = document.getElementById('pay-search');
  const statusFilter = document.getElementById('pay-status-filter');
  const methodFilter = document.getElementById('pay-method-filter');

  searchInput.addEventListener('input', () => {
    clearTimeout(paySearchTimeout);
    paySearchTimeout = setTimeout(() => { payCurrentPage = 1; loadPayments(); }, 400);
  });
  statusFilter.addEventListener('change', () => { payCurrentPage = 1; loadPayments(); });
  methodFilter.addEventListener('change', () => { payCurrentPage = 1; loadPayments(); });
}

async function loadPaymentStats() {
  try {
    const res = await fetch(API + '/admin/payments/stats', { headers });
    if (!res.ok) return;
    const d = await res.json();
    document.getElementById('pay-stat-revenue').textContent = `EGP ${Number(d.total_revenue || 0).toLocaleString()}`;
    document.getElementById('pay-stat-month').textContent = `EGP ${Number(d.this_month || 0).toLocaleString()}`;
    document.getElementById('pay-stat-failed').textContent = d.failed_count || 0;
    document.getElementById('pay-stat-pending').textContent = d.pending_count || 0;
  } catch (e) { }
}

async function loadPayments() {
  const tbody = document.getElementById('payments-tbody');
  // Skeleton
  tbody.innerHTML = Array.from({ length: 3 }, () => `
    <tr class="skeleton-row">
      <td><div class="skeleton-bar" style="width:120px"></div></td>
      <td><div class="skeleton-bar" style="width:100px"></div></td>
      <td><div class="skeleton-bar" style="width:70px"></div></td>
      <td><div class="skeleton-bar" style="width:60px"></div></td>
      <td><div class="skeleton-bar" style="width:50px"></div></td>
      <td><div class="skeleton-bar" style="width:80px"></div></td>
      <td><div class="skeleton-bar" style="width:60px"></div></td>
    </tr>
  `).join('');

  const search = document.getElementById('pay-search').value;
  const status = document.getElementById('pay-status-filter').value;
  const method = document.getElementById('pay-method-filter').value;

  try {
    const params = new URLSearchParams({ page: payCurrentPage, limit: PAY_LIMIT });
    if (search) params.set('search', search);
    if (status !== 'all') params.set('status', status);
    if (method !== 'all') params.set('method', method);

    const res = await fetch(`${API}/admin/payments?${params}`, { headers });
    if (!res.ok) { showToast('❌ Failed to load payments', 'error'); return; }
    const data = await res.json();

    if (!data.payments || data.payments.length === 0) {
      tbody.innerHTML = `
        <tr><td colspan="7">
          <div class="payments-empty">
            <div><i data-lucide="receipt" style="width:48px;height:48px;stroke:#555;"></i></div>
            <p>No payments found</p>
          </div>
        </td></tr>`;
      document.getElementById('payments-pagination').innerHTML = '';
      setTimeout(() => { if (typeof lucide !== 'undefined') lucide.createIcons(); }, 10);
      return;
    }

    tbody.innerHTML = data.payments.map(p => {
      const dateFormatted = formatDateTime(p.date);
      const statusClass = p.status || 'pending';
      const statusLabel = (p.status || 'pending').charAt(0).toUpperCase() + (p.status || 'pending').slice(1);
      const methodLabel = (p.method || '').charAt(0).toUpperCase() + (p.method || '').slice(1);
      const refShort = p.reference ? (p.reference.length > 12 ? p.reference.slice(0, 12) + '…' : p.reference) : '—';
      const refFull = p.reference || '';

      let actionBtns = '';
      if (p.status === 'failed') {
        actionBtns = `<button class="pay-action-btn retry" onclick="retryPayment(${p.id})" title="Retry">↺ Retry</button>`;
      } else if (p.status === 'paid') {
        actionBtns = `<button class="pay-action-btn refund" onclick="refundPayment(${p.id})" title="Refund">↩ Refund</button>`;
      }

      return `
      <tr>
        <td>
          <div class="member-cell">
            <div style="width:32px;height:32px;border-radius:50%;background:#2a2a2a;display:flex;align-items:center;justify-content:center;color:#888;font-size:13px;font-weight:600;flex-shrink:0;">${(p.member_name || '?').charAt(0).toUpperCase()}</div>
            <span style="color:#fff;font-size:14px;">${escapeHtml(p.member_name || 'Unknown')}</span>
          </div>
        </td>
        <td style="color:#888;font-size:13px;">${dateFormatted}</td>
        <td style="color:#fff;font-weight:600;">${p.currency || 'EGP'} ${Number(p.amount || 0).toLocaleString()}</td>
        <td style="color:#888;">${methodLabel}</td>
        <td><span class="status-pill ${statusClass}">${statusLabel}</span></td>
        <td>
          <div class="ref-cell">
            <span>${refShort}</span>
            ${refFull ? `<button class="copy-btn" onclick="copyRef('${escapeHtml(refFull)}')" title="Copy reference"><i data-lucide="copy" style="width:14px;height:14px;"></i></button>` : ''}
          </div>
        </td>
        <td>${actionBtns}</td>
      </tr>`;
    }).join('');

    // Pagination
    renderPaymentsPagination(data.page, data.pages);
    setTimeout(() => { if (typeof lucide !== 'undefined') lucide.createIcons(); }, 10);
  } catch (e) {
    console.error(e);
    showToast('❌ Failed to load payments: ' + e.message, 'error');
  }
}

function renderPaymentsPagination(current, total) {
  buildPager(document.getElementById('payments-pagination'), current, total, 'goToPayPage');
}

function goToPayPage(page) {
  payCurrentPage = page;
  loadPayments();
}

function copyRef(ref) {
  navigator.clipboard.writeText(ref).then(() => showToast('📋 Reference copied', 'success'));
}

async function retryPayment(id) {
  try {
    const res = await fetch(`${API}/admin/payments/${id}/retry`, { method: 'POST', headers });
    if (res.ok) {
      showToast('↺ Payment retry initiated', 'success');
      await loadPayments();
      await loadPaymentStats();
    } else {
      const d = await res.json();
      showToast(`❌ ${d.detail || 'Retry failed'}`, 'error');
    }
  } catch (e) {
    showToast('❌ Network error', 'error');
  }
}

async function refundPayment(id) {
  try {
    const res = await fetch(`${API}/admin/payments/${id}/refund`, { method: 'POST', headers });
    if (res.ok) {
      showToast('↩ Payment refunded', 'success');
      await loadPayments();
      await loadPaymentStats();
    } else {
      const d = await res.json();
      showToast(`❌ ${d.detail || 'Refund failed'}`, 'error');
    }
  } catch (e) {
    showToast('❌ Network error', 'error');
  }
}

function exportMembersCSV() {
  const rows = filteredUsers;
  if (!rows.length) { showToast('No members to export', 'error'); return; }

  const showContact = currentUserIsOwner;
  const headers = ['ID', 'Name', 'Role', ...(showContact ? ['Email', 'Phone'] : []),
    'Country', 'Governorate', 'Birth Date', 'Joined', 'Subscription Start', 'End Date', 'Status'];

  const cell = (v) => {
    const s = (v === null || v === undefined) ? '' : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const roleOf = (u) => u.is_owner ? 'Owner' : u.is_admin ? 'Admin' : 'Member';
  const dateOf = (v) => v ? new Date(v).toISOString().slice(0, 10) : '';

  const lines = [headers.map(cell).join(',')];
  rows.forEach(u => {
    const row = [u.id, u.full_name, roleOf(u),
      ...(showContact ? [u.email || '', u.phone || ''] : []),
      u.country || '', u.governorate || '', u.birth_date || '', dateOf(u.created_at),
      dateOf(u.subscription_start), dateOf(u.end_at), u.is_active ? 'Active' : 'Inactive'];
    lines.push(row.map(cell).join(','));
  });

  const blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = `ghawy_members_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(blobUrl);
  showToast('⬇ CSV exported', 'success');
}

function exportPaymentsCSV() {
  const search = document.getElementById('pay-search').value;
  const status = document.getElementById('pay-status-filter').value;
  const method = document.getElementById('pay-method-filter').value;
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (status !== 'all') params.set('status', status);
  if (method !== 'all') params.set('method', method);

  const url = `${API}/admin/payments/export-csv?${params}`;
  fetch(url, { headers }).then(r => r.blob()).then(blob => {
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = `ghawy_payments_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(blobUrl);
    showToast('⬇ CSV exported', 'success');
  }).catch(() => showToast('❌ Export failed', 'error'));
}


// ══════════════════════════════════════════════════════════
//  ANALYTICS TAB
// ══════════════════════════════════════════════════════════

let analyticsRange = '30d';
let chartMembers = null;
let chartRevenue = null;
let chartSubs = null;

async function loadAnalyticsTab() {
  // Set Chart.js defaults
  if (typeof Chart !== 'undefined') {
    Chart.defaults.color = '#9ca3af';
    Chart.defaults.borderColor = '#2a2a2a';
    Chart.defaults.font.family = 'inherit';
  }

  initRangeButtons();
  await refreshAnalytics();
}

function initRangeButtons() {
  document.querySelectorAll('.range-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      analyticsRange = btn.dataset.range;
      refreshAnalytics();
    });
  });
}

async function refreshAnalytics() {
  await Promise.all([
    loadKPIs(),
    loadMembersChart(),
    loadRevenueChart(),
    loadSubsChart()
  ]);
}

async function loadKPIs() {
  try {
    const res = await fetch(`${API}/admin/analytics/kpis?range=${analyticsRange}`, { headers });
    if (!res.ok) return;
    const d = await res.json();
    document.getElementById('kpi-total-members').textContent = d.total_members || 0;
    document.getElementById('kpi-growth-rate').textContent = `${(d.growth_rate || 0).toFixed(1)}%`;
    document.getElementById('kpi-total-revenue').textContent = `EGP ${Number(d.total_revenue || 0).toLocaleString()}`;
    document.getElementById('kpi-churn-rate').textContent = `${(d.churn_rate || 0).toFixed(1)}%`;
  } catch (e) { }
}

async function loadMembersChart() {
  try {
    const res = await fetch(`${API}/admin/analytics/members-over-time?range=${analyticsRange}`, { headers });
    if (!res.ok) return;
    const data = await res.json();
    const labels = data.map(d => d.date);
    const values = data.map(d => d.count);

    if (chartMembers) chartMembers.destroy();
    const ctx = document.getElementById('chart-members').getContext('2d');
    chartMembers = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'New Members',
          data: values,
          backgroundColor: '#3f8ff9',
          borderRadius: 6,
          borderSkipped: false,
          maxBarThickness: 32,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { stepSize: 1 } }
        }
      }
    });
    document.getElementById('chart-members').parentElement.style.height = '260px';
  } catch (e) { }
}

async function loadRevenueChart() {
  try {
    const res = await fetch(`${API}/admin/analytics/revenue-over-time?range=${analyticsRange}`, { headers });
    if (!res.ok) return;
    const data = await res.json();
    const labels = data.map(d => d.date);
    const values = data.map(d => d.amount);
    const totalRev = values.reduce((a, b) => a + b, 0);

    document.getElementById('revenue-total-label').textContent = `Total: EGP ${totalRev.toLocaleString()}`;

    if (chartRevenue) chartRevenue.destroy();
    const ctx = document.getElementById('chart-revenue').getContext('2d');
    chartRevenue = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Revenue',
          data: values,
          borderColor: '#22c55e',
          backgroundColor: 'rgba(34,197,94,0.08)',
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: '#22c55e',
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true }
        }
      }
    });
    document.getElementById('chart-revenue').parentElement.style.height = '260px';
  } catch (e) { }
}

async function loadSubsChart() {
  try {
    const res = await fetch(`${API}/admin/analytics/subscription-breakdown`, { headers });
    if (!res.ok) return;
    const data = await res.json();
    const total = (data.monthly || 0) + (data.quarterly || 0) + (data.yearly || 0) + (data.none || 0);

    if (chartSubs) chartSubs.destroy();
    const ctx = document.getElementById('chart-subs').getContext('2d');
    chartSubs = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Monthly (600)', 'Quarterly (1200)', 'Yearly (4000)', 'None'],
        datasets: [{
          data: [data.monthly || 0, data.quarterly || 0, data.yearly || 0, data.none || 0],
          backgroundColor: ['#3f8ff9', '#22c55e', '#f59e0b', '#333'],
          borderWidth: 0,
          hoverOffset: 8,
        }]
      },
      options: {
        responsive: true,
        cutout: '65%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: { padding: 16, usePointStyle: true, pointStyleWidth: 10 }
          }
        }
      },
      plugins: [{
        id: 'centerText',
        beforeDraw(chart) {
          const { ctx, chartArea } = chart;
          const centerX = (chartArea.left + chartArea.right) / 2;
          const centerY = (chartArea.top + chartArea.bottom) / 2;
          ctx.save();
          ctx.font = 'bold 28px inherit';
          ctx.fillStyle = '#fff';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(total, centerX, centerY);
          ctx.restore();
        }
      }]
    });
  } catch (e) { }
}


// ═══ PENDING REQUESTS (Manual Payments) ═══

let mprCurrentPage = 1;
let currentRejectId = null;

async function authFetch(url, options = {}) {
  options.headers = { ...headers, ...(options.headers || {}) };
  return fetch(url, options);
}

async function loadManualPaymentStats() {
  try {
    const res = await authFetch(`${API}/manual-payments/stats`);
    if (res.ok) {
      const data = await res.json();
      const badge = document.getElementById('pending-badge');
      if (data.pending_count > 0) {
        badge.innerText = data.pending_count;
        badge.style.display = 'inline-flex';
      } else {
        badge.style.display = 'none';
      }
    }
  } catch (e) { }
}

async function loadPendingRequestsTab() {
  const container = document.getElementById('mpr-cards-container');
  container.innerHTML = `<div style="padding: 40px; text-align: center; color: #888; grid-column: 1 / -1;">Loading...</div>`;

  const status = document.getElementById('mpr-status-filter').value;

  try {
    const res = await authFetch(`${API}/manual-payments?status=${status}&page=${mprCurrentPage}&limit=12`);
    if (!res.ok) throw new Error("Failed to load requests");
    const data = await res.json();

    // Update labels and badges
    document.getElementById('mpr-count-label').innerText = `(${data.total})`;
    const badge = document.getElementById('pending-badge');
    if (data.counts.pending > 0) {
      badge.innerText = data.counts.pending;
      badge.style.display = 'inline-flex';
    } else {
      badge.style.display = 'none';
    }

    if (data.requests.length === 0) {
      container.innerHTML = `<div style="padding: 40px; text-align: center; color: #888; grid-column: 1 / -1;">No requests found.</div>`;
      document.getElementById('mpr-pagination').innerHTML = '';
      return;
    }

    renderMprCards(data.requests, container);
    renderMprPagination(data.page, data.pages);

  } catch (e) {
    container.innerHTML = `<div style="padding: 40px; text-align: center; color: #ef4444; grid-column: 1 / -1;">Error loading requests</div>`;
  }
}

// Normalize an Egyptian phone number into a wa.me-friendly international form.
function toWaMeNumber(phone) {
  let p = (phone || '').replace(/[\s\-+()]/g, '');
  if (p.startsWith('00')) p = p.slice(2);
  else if (p.startsWith('0')) p = '20' + p.slice(1);
  return p;
}

const MPR_PLAN_LABELS = {
  monthly: 'Monthly (30 days)',
  quarterly: '3 Months (90 days)',
  yearly: 'Yearly (365 days)',
};

function renderMprCards(requests, container) {
  container.innerHTML = '';

  requests.forEach(req => {
    // Backend sends naive UTC timestamps — mark as UTC then render in Egypt time.
    const rawTs = req.created_at || '';
    const d = new Date(/Z|[+-]\d{2}:?\d{2}$/.test(rawTs) ? rawTs : rawTs + 'Z');
    const dateStr = isNaN(d) ? '—' : d.toLocaleString('en-GB', {
      timeZone: 'Africa/Cairo',
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });

    let statusClass = 'pending';
    if (req.status === 'approved') statusClass = 'approved';
    if (req.status === 'rejected') statusClass = 'rejected';

    const phoneHtml = req.phone
      ? `<a class="mpr-phone" href="https://wa.me/${toWaMeNumber(req.phone)}" target="_blank" rel="noopener" title="Open WhatsApp">${escapeHtml(req.phone)}</a>`
      : `<div class="mpr-phone">No phone</div>`;
    const planLabel = MPR_PLAN_LABELS[req.plan] || (req.plan ? req.plan : '—');

    let actionsHtml = '';

    if (req.status === 'pending') {
      actionsHtml = `
        <button class="mpr-btn-approve" onclick="approveRequest(${req.id})"><i data-lucide="check"></i> Approve</button>
        <button class="mpr-btn-reject" onclick="rejectRequestPrompt(${req.id})"><i data-lucide="x"></i> Reject</button>
      `;
    } else if (req.status === 'approved') {
      actionsHtml = `
        <button class="mpr-btn-outline" onclick="resendInvite(${req.id})"><i data-lucide="mail"></i> Resend Invite</button>
      `;
    } else if (req.status === 'rejected') {
      actionsHtml = `
        <div class="mpr-reject-reason" title="${req.rejection_reason || ''}">
          Reason: ${req.rejection_reason || 'N/A'}
        </div>
      `;
    }

    const card = document.createElement('div');
    card.className = 'mpr-card';
    card.innerHTML = `
      <div class="mpr-card-header">
        <div class="mpr-user-info">
          <div class="mpr-name">${req.full_name}</div>
          <div class="mpr-email">${req.email}</div>
          ${phoneHtml}
        </div>
        <div class="mpr-status-badge ${statusClass}">${req.status.toUpperCase()}</div>
      </div>
      
      <div class="mpr-details">
        <div class="mpr-detail-row">
          <span>Amount</span>
          <strong>${req.amount ? req.amount + ' EGP' : '--'}</strong>
        </div>
        <div class="mpr-detail-row">
          <span>Plan</span>
          <strong>${planLabel}</strong>
        </div>
        <div class="mpr-detail-row">
          <span>Date</span>
          <strong>${dateStr}</strong>
        </div>
        <div class="mpr-detail-row">
          <span>Ref ID</span>
          <strong>#${req.id}</strong>
        </div>
      </div>
      
      <div class="mpr-receipt" onclick="openLightbox('${API}${req.receipt_url}')">
        <i data-lucide="image"></i> View Receipt
      </div>
      
      <div class="mpr-actions">
        ${actionsHtml}
      </div>
    `;
    container.appendChild(card);
  });
  lucide.createIcons();
}

function renderMprPagination(page, pages) {
  const p = document.getElementById('mpr-pagination');
  p.innerHTML = '';
  if (pages <= 1) return;

  if (page > 1) {
    const b = document.createElement('button');
    b.innerText = 'Prev';
    b.onclick = () => { mprCurrentPage--; loadPendingRequestsTab(); };
    p.appendChild(b);
  }

  const span = document.createElement('span');
  span.innerText = `Page ${page} of ${pages}`;
  p.appendChild(span);

  if (page < pages) {
    const b = document.createElement('button');
    b.innerText = 'Next';
    b.onclick = () => { mprCurrentPage++; loadPendingRequestsTab(); };
    p.appendChild(b);
  }
}

async function approveRequest(id) {
  try {
    const res = await authFetch(`${API}/manual-payments/${id}/approve`, { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      if (data.whatsapp_url) {
        window.open(data.whatsapp_url, '_blank');
        showToast("Approved! Opening WhatsApp...", "success");
      } else {
        showToast("Request approved! No phone number provided for WhatsApp.", "success");
      }
      loadPendingRequestsTab();
      loadManualPaymentStats();
    } else {
      const data = await res.json();
      showToast(data.detail || "Error approving request", "error");
    }
  } catch (e) {
    showToast("Network error", "error");
  }
}

function rejectRequestPrompt(id) {
  currentRejectId = id;
  document.getElementById('reject-reason').value = '';
  openModal('reject-modal');
}

async function submitRejectRequest() {
  const reason = document.getElementById('reject-reason').value.trim();
  if (!reason) {
    showToast("Please provide a reason", "error");
    return;
  }

  try {
    const res = await authFetch(`${API}/manual-payments/${currentRejectId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason })
    });

    if (res.ok) {
      showToast("Request rejected. Email sent.", "success");
      closeModal('reject-modal');
      loadPendingRequestsTab();
      loadManualPaymentStats();
    } else {
      const data = await res.json();
      showToast(data.detail || "Error rejecting request", "error");
    }
  } catch (e) {
    showToast("Network error", "error");
  }
}

async function resendInvite(id) {
  try {
    const res = await authFetch(`${API}/manual-payments/${id}/resend-invite`, { method: 'POST' });
    if (res.ok) {
      showToast("Invite resent successfully!", "success");
    } else {
      const data = await res.json();
      showToast(data.detail || "Error resending invite", "error");
    }
  } catch (e) {
    showToast("Network error", "error");
  }
}

// Lightbox logic
function openLightbox(url) {
  const lb = document.getElementById('receipt-lightbox');
  const img = document.getElementById('lightbox-img');
  img.src = url;
  lb.style.display = 'flex';
}

function closeLightbox(e) {
  // Only close if clicking outside the image or on the close button
  if (e.target.id === 'receipt-lightbox' || e.target.classList.contains('lightbox-close')) {
    document.getElementById('receipt-lightbox').style.display = 'none';
    document.getElementById('lightbox-img').src = '';
  }
}

// ═══ HAMBURGER ═══
(function initSidebar() {
  const hamburger = document.getElementById('hamburgerBtn');
  const sidebar = document.getElementById('dashSidebar');
  const overlay = document.getElementById('sidebarOverlay');
  if (!hamburger || !sidebar) return;
  const nh = hamburger.cloneNode(true);
  hamburger.parentNode.replaceChild(nh, hamburger);
  nh.addEventListener('click', (e) => {
    e.stopPropagation();
    sidebar.classList.toggle('open');
    if (overlay) overlay.classList.toggle('visible');
    nh.classList.toggle('active');
  });
  if (overlay) {
    overlay.addEventListener('click', () => {
      sidebar.classList.remove('open');
      overlay.classList.remove('visible');
      nh.classList.remove('active');
    });
  }
})();

// ═══ INIT ═══
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadTeamPage);
} else {
  loadTeamPage();
}

// ═══════════════════════════════════════════════════════
//  LIVE SESSIONS TAB
// ═══════════════════════════════════════════════════════

let liveSessionsCache = [];

async function loadLiveSessionsTab() {
  const tbody = document.getElementById('live-sessions-body');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:40px;color:#555;">Loading...</td></tr>';

  try {
    const res = await fetch(API + '/admin/live/sessions', { headers });
    if (!res.ok) throw new Error('Failed to load');
    const sessions = await res.json();
    liveSessionsCache = sessions;

    if (!sessions.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:40px;color:#555;">📺 No sessions yet. Click "+ Add Session" to create one.</td></tr>';
      return;
    }

    tbody.innerHTML = sessions.map(s => {
      const dt = s.scheduled_at ? new Date(s.scheduled_at).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' }) : 'TBD';
      return `
      <tr>
        <td style="color:#fff;font-weight:500;">${escapeHtmlTeam(s.title)}</td>
        <td style="color:#888;">${dt}</td>
        <td>
          <label class="t-switch">
            <input type="checkbox" ${s.is_published ? 'checked' : ''} onchange="togglePublishSession(${s.id}, this.checked)">
            <span class="t-slider"></span>
          </label>
        </td>
        <td>
          <button class="btn-action" onclick="viewAttendees(${s.id})" style="font-size:13px;">
            👥 ${s.attendee_count || 0}
          </button>
        </td>
        <td>
          <div class="action-btns">
            <button class="btn-action" onclick="notifySession(${s.id})" title="Notify all">📧</button>
            <button class="btn-action" onclick="openEditSessionModal(${s.id})" title="Edit">✏️</button>
            <button class="btn-action delete" onclick="openDeleteSessionModal(${s.id})" title="Delete">🗑️</button>
          </div>
        </td>
      </tr>`;
    }).join('');
  } catch (e) {
    console.error(e);
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:40px;color:#ef4444;">Failed to load sessions</td></tr>';
  }
}

function escapeHtmlTeam(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ─── Add Session ─────────────────────────────────────
function openAddSessionModal() {
  document.getElementById('session-title').value = '';
  document.getElementById('session-desc').value = '';
  document.getElementById('session-datetime').value = '';
  document.getElementById('session-youtube').value = '';
  document.getElementById('session-zoom').value = '';
  document.getElementById('add-session-modal').style.display = 'flex';
}

async function submitAddSession() {
  const title = document.getElementById('session-title').value.trim();
  if (!title) return showToast('Title is required', 'error');

  const dt = document.getElementById('session-datetime').value;
  const body = {
    title,
    description: document.getElementById('session-desc').value.trim() || null,
    scheduled_at: dt ? new Date(dt).toISOString() : null,
    youtube_url: document.getElementById('session-youtube').value.trim() || null,
    zoom_url: document.getElementById('session-zoom').value.trim() || null,
  };

  try {
    const res = await fetch(API + '/admin/live/sessions', { method: 'POST', headers, body: JSON.stringify(body) });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Failed'); }
    showToast('Session created ✅', 'success');
    closeModal('add-session-modal');
    loadLiveSessionsTab();
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}

// ─── Edit Session ────────────────────────────────────
function openEditSessionModal(id) {
  const s = liveSessionsCache.find(s => s.id === id);
  if (!s) return;
  document.getElementById('edit-session-id').value = id;
  document.getElementById('edit-session-title').value = s.title || '';
  document.getElementById('edit-session-desc').value = s.description || '';
  if (s.scheduled_at) {
    const d = new Date(s.scheduled_at);
    const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    document.getElementById('edit-session-datetime').value = local;
  } else {
    document.getElementById('edit-session-datetime').value = '';
  }
  document.getElementById('edit-session-youtube').value = s.youtube_url || '';
  document.getElementById('edit-session-zoom').value = s.zoom_url || '';
  document.getElementById('edit-session-modal').style.display = 'flex';
}

async function submitEditSession() {
  const id = document.getElementById('edit-session-id').value;
  const dt = document.getElementById('edit-session-datetime').value;
  const body = {
    title: document.getElementById('edit-session-title').value.trim(),
    description: document.getElementById('edit-session-desc').value.trim() || null,
    scheduled_at: dt ? new Date(dt).toISOString() : null,
    youtube_url: document.getElementById('edit-session-youtube').value.trim() || null,
    zoom_url: document.getElementById('edit-session-zoom').value.trim() || null,
  };

  try {
    const res = await fetch(API + `/admin/live/sessions/${id}`, { method: 'PATCH', headers, body: JSON.stringify(body) });
    if (!res.ok) throw new Error('Failed');
    showToast('Session updated ✅', 'success');
    closeModal('edit-session-modal');
    loadLiveSessionsTab();
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}

// ─── Toggle Publish ──────────────────────────────────
async function togglePublishSession(id, checked) {
  try {
    const res = await fetch(API + `/admin/live/sessions/${id}`, {
      method: 'PATCH', headers, body: JSON.stringify({ is_published: checked })
    });
    if (!res.ok) throw new Error('Failed');
    showToast(checked ? 'Session published ✅' : 'Session unpublished', 'success');
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
    loadLiveSessionsTab(); // revert
  }
}

// ─── Delete Session ──────────────────────────────────
function openDeleteSessionModal(id) {
  document.getElementById('delete-session-id').value = id;
  document.getElementById('delete-session-modal').style.display = 'flex';
}

async function confirmDeleteSession() {
  const id = document.getElementById('delete-session-id').value;
  try {
    const res = await fetch(API + `/admin/live/sessions/${id}`, { method: 'DELETE', headers });
    if (!res.ok && res.status !== 204) throw new Error('Failed');
    showToast('Session deleted ✅', 'success');
    closeModal('delete-session-modal');
    loadLiveSessionsTab();
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}

// ─── Notify ──────────────────────────────────────────
async function notifySession(id) {
  const s = liveSessionsCache.find(s => s.id === id);
  if (!s) return;
  // Custom confirm via toast-style approach
  if (!window._confirmNotify) {
    window._confirmNotify = true;
    showToast(`Click Notify again to confirm sending email to all users for "${s.title}"`, 'info');
    window._notifyId = id;
    setTimeout(() => { window._confirmNotify = false; }, 5000);
    return;
  }
  if (window._notifyId !== id) {
    window._confirmNotify = false;
    return notifySession(id);
  }
  window._confirmNotify = false;

  try {
    showToast('Sending notifications...', 'info');
    const res = await fetch(API + `/admin/live/sessions/${id}/notify`, { method: 'POST', headers });
    if (!res.ok) throw new Error('Failed');
    const data = await res.json();
    showToast(`📧 Sent ${data.sent} emails (${data.errors} errors)`, 'success');
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}

// ─── View Attendees ──────────────────────────────────
async function viewAttendees(sessionId) {
  const listEl = document.getElementById('attendees-list');
  listEl.innerHTML = '<div style="text-align:center;padding:20px;color:#888;">Loading...</div>';
  document.getElementById('attendees-modal').style.display = 'flex';

  try {
    const res = await fetch(API + `/admin/live/sessions/${sessionId}/attendees`, { headers });
    if (!res.ok) throw new Error('Failed');
    const data = await res.json();

    if (!data.attendees || !data.attendees.length) {
      listEl.innerHTML = '<div style="text-align:center;padding:20px;color:#555;">No attendees yet</div>';
    } else {
      listEl.innerHTML = `
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
          <thead><tr style="border-bottom:1px solid #2a2a2a;">
            <th style="text-align:left;padding:8px;color:#888;">Name</th>
            <th style="text-align:left;padding:8px;color:#888;">Email</th>
            <th style="text-align:left;padding:8px;color:#888;">Registered</th>
          </tr></thead>
          <tbody>${data.attendees.map(a => `
            <tr style="border-bottom:1px solid #1e1e1e;">
              <td style="padding:8px;color:#fff;">${escapeHtmlTeam(a.full_name)}</td>
              <td style="padding:8px;color:#888;">${a.email}</td>
              <td style="padding:8px;color:#555;">${new Date(a.registered_at).toLocaleDateString()}</td>
            </tr>`).join('')}
          </tbody>
        </table>
        <div style="color:#888;font-size:12px;margin-top:8px;">Total: ${data.total}</div>`;
    }

    // CSV export button
    const csvBtn = document.getElementById('export-csv-btn');
    csvBtn.onclick = () => {
      window.open(API + `/admin/live/sessions/${sessionId}/attendees?export=csv`, '_blank');
    };
  } catch (e) {
    listEl.innerHTML = '<div style="text-align:center;padding:20px;color:#ef4444;">Failed to load attendees</div>';
  }
}

// ==========================================
//  COURSES TAB (LEVEL 1 & 2)
// ==========================================

let coursesCache = [];
let currentCourseId = null;
let uploadPollInterval = null;

// ── Reorder courses (controls public Courses page display order) ──
function moveCourse(id, dir) {
  const idx = coursesCache.findIndex(c => c.id === id);
  if (idx === -1) return;
  const swapWith = dir === 'up' ? idx - 1 : idx + 1;
  if (swapWith < 0 || swapWith >= coursesCache.length) return;
  [coursesCache[idx], coursesCache[swapWith]] = [coursesCache[swapWith], coursesCache[idx]];
  renderCourses();
  persistCourseOrder();
}

async function persistCourseOrder() {
  try {
    const order = coursesCache.map(c => c.id);
    const res = await fetch(API + '/courses/admin/courses/reorder', {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ order })
    });
    if (!res.ok) throw new Error('Failed to save order');
    showToast('Course order saved', 'success');
  } catch (err) {
    showToast('Error saving order — reloading', 'error');
    loadCoursesTab(); // reload to reflect the true saved order
  }
}

async function loadCoursesTab() {
  document.getElementById('courses-list-view').style.display = 'block';
  document.getElementById('lessons-manager-view').style.display = 'none';
  const tbody = document.getElementById('courses-body');
  tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:40px;color:#555;">Loading...</td></tr>`;

  try {
    const res = await fetch(API + '/courses/admin/courses', { headers });
    if (!res.ok) throw new Error('Failed to load courses');
    coursesCache = await res.json();
    renderCourses();
  } catch (err) {
    console.error(err);
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:40px;color:red;">Error loading courses.</td></tr>`;
  }
}

function renderCourses() {
  const tbody = document.getElementById('courses-body');
  if (coursesCache.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;color:#555;">No courses found. Add one above.</td></tr>`;
    return;
  }
  tbody.innerHTML = coursesCache.map((c, idx) => {
    const thumbSrc = c.thumbnail_url ? (c.thumbnail_url.startsWith('/') ? API + c.thumbnail_url : c.thumbnail_url) : '';
    let resources = [];
    try { resources = c.pdf_url ? JSON.parse(c.pdf_url) : []; } catch(e) {
      if (c.pdf_url) resources = [{ name: 'Resource', url: c.pdf_url }];
    }
    return `
    <tr>
      <td>
        <div style="display:flex;align-items:center;gap:6px;">
          ${thumbSrc
        ? `<img src="${thumbSrc}" style="width:80px;height:45px;border-radius:4px;object-fit:cover;" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
               <div style="display:none;width:80px;height:45px;border-radius:4px;background:#222;align-items:center;justify-content:center;color:#555;font-size:10px;">No img</div>`
        : `<div style="width:80px;height:45px;border-radius:4px;background:#222;display:flex;align-items:center;justify-content:center;color:#555;font-size:10px;">No img</div>`
      }
          <button class="btn-action" style="font-size:11px;padding:3px 6px;" onclick="uploadCourseThumbnail(${c.id})" title="Upload thumbnail"><i class="fa-solid fa-image"></i></button>
          <input type="file" id="course-thumb-upload-${c.id}" accept="image/*" style="display:none" onchange="handleCourseThumbSelected(event, ${c.id})">
        </div>
      </td>
      <td><strong>${escapeHtml(c.title)}</strong><br><small style="color:#888;">${escapeHtml((c.description || '').substring(0, 30))}...</small></td>
      <td>${c.total_lessons || 0} lessons</td>
      <td>
        <div style="display:flex;align-items:center;gap:6px;">
          <span style="color:${resources.length ? '#22c55e' : '#555'};font-size:12px;">${resources.length} resource${resources.length !== 1 ? 's' : ''}</span>
          <button class="btn-action" style="font-size:12px;padding:4px 8px;" onclick="openResourcesModal(${c.id})"><i class="fa-solid fa-link"></i> Manage</button>
        </div>
      </td>
      <td>
        <label class="switch">
          <input type="checkbox" ${c.is_published ? 'checked' : ''} onchange="toggleCoursePublish(${c.id}, this)">
          <span class="slider round"></span>
        </label>
      </td>
      <td>
        <button class="btn-action" onclick="moveCourse(${c.id}, 'up')" title="Move up" ${idx === 0 ? 'disabled' : ''} style="margin-right:4px;${idx === 0 ? 'opacity:.35;cursor:not-allowed;' : ''}"><i class="fa-solid fa-arrow-up"></i></button>
        <button class="btn-action" onclick="moveCourse(${c.id}, 'down')" title="Move down" ${idx === coursesCache.length - 1 ? 'disabled' : ''} style="margin-right:8px;${idx === coursesCache.length - 1 ? 'opacity:.35;cursor:not-allowed;' : ''}"><i class="fa-solid fa-arrow-down"></i></button>
        <button class="btn-action" onclick="showLessonsManager(${c.id}, '${escapeHtml(c.title).replace(/'/g, "\\\\'")}')" style="margin-right:8px;"><i class="fa-solid fa-list"></i> Lessons</button>
        <button class="btn-action" onclick="showExamsManager(${c.id}, '${escapeHtml(c.title).replace(/'/g, "\\\\'")}')" style="margin-right:8px;"><i class="fa-solid fa-file-pen"></i> Exams</button>
        <button class="btn-action" onclick="openCertificateModal(${c.id})" style="margin-right:8px;" title="Certificate template"><i class="fa-solid fa-graduation-cap"></i> Certificate</button>
        <button class="btn-action" onclick="openEditCourseModal(${c.id})"><i class="fa-solid fa-pen"></i></button>
        <button class="btn-action" onclick="openDeleteCourseModal(${c.id})" style="color:#ef4444;"><i class="fa-solid fa-trash"></i></button>
      </td>
    </tr>`;
  }).join('');
}

async function toggleCoursePublish(id, checkbox) {
  const isPub = checkbox.checked;
  try {
    const res = await fetch(API + `/courses/admin/courses/${id}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ is_published: isPub })
    });
    if (!res.ok) throw new Error('Failed to update course');
    showToast(`Course ${isPub ? 'published' : 'hidden'} successfully`, 'success');
  } catch (err) {
    checkbox.checked = !isPub;
    showToast('Error updating course', 'error');
  }
}

// -- Course Modals --
function openAddCourseModal() {
  document.getElementById('course-title').value = '';
  document.getElementById('course-desc').value = '';
  document.getElementById('course-thumbnail').value = '';
  document.getElementById('course-total-lessons').value = '0';
  document.getElementById('add-course-modal').style.display = 'flex';
}

async function submitAddCourse() {
  const data = {
    title: document.getElementById('course-title').value,
    description: document.getElementById('course-desc').value,
    thumbnail_url: document.getElementById('course-thumbnail').value,
    total_lessons: parseInt(document.getElementById('course-total-lessons').value) || 0,
    course_time: document.getElementById('course-time').value || null,
    is_published: false
  };
  if (!data.title) return showToast('Title is required', 'error');

  try {
    const res = await fetch(API + '/courses/admin/courses', {
      method: 'POST',
      headers,
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to create course');
    closeModal('add-course-modal');
    showToast('Course created successfully!', 'success');
    loadCoursesTab();
  } catch (e) { showToast(e.message, 'error'); }
}

function openEditCourseModal(id) {
  const c = coursesCache.find(x => x.id === id);
  if (!c) return;
  document.getElementById('edit-course-id').value = c.id;
  document.getElementById('edit-course-title').value = c.title;
  document.getElementById('edit-course-desc').value = c.description || '';
  document.getElementById('edit-course-thumbnail').value = c.thumbnail_url || '';
  document.getElementById('edit-course-total-lessons').value = c.total_lessons || 0;
  document.getElementById('edit-course-time').value = c.course_time || '';
  document.getElementById('edit-course-modal').style.display = 'flex';
}

async function submitEditCourse() {
  const id = document.getElementById('edit-course-id').value;
  const data = {
    title: document.getElementById('edit-course-title').value,
    description: document.getElementById('edit-course-desc').value,
    thumbnail_url: document.getElementById('edit-course-thumbnail').value,
    total_lessons: parseInt(document.getElementById('edit-course-total-lessons').value) || 0,
    course_time: document.getElementById('edit-course-time').value || null
  };
  try {
    const res = await fetch(API + `/courses/admin/courses/${id}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Update failed');
    closeModal('edit-course-modal');
    showToast('Course updated!', 'success');
    loadCoursesTab();
  } catch (e) { showToast(e.message, 'error'); }
}

function openDeleteCourseModal(id) {
  document.getElementById('delete-course-id').value = id;
  document.getElementById('delete-course-modal').style.display = 'flex';
}

async function confirmDeleteCourse() {
  const id = document.getElementById('delete-course-id').value;
  try {
    const res = await fetch(API + `/courses/admin/courses/${id}`, {
      method: 'DELETE', headers
    });
    if (!res.ok) throw new Error('Delete failed');
    closeModal('delete-course-modal');
    showToast('Course deleted', 'info');
    loadCoursesTab();
  } catch (e) { showToast(e.message, 'error'); }
}

// -- Course PDF Upload --
function uploadCoursePdf(courseId) {
  document.getElementById(`course-pdf-upload-${courseId}`).click();
}

async function handleCoursePdfSelected(event, courseId) {
  const file = event.target.files[0];
  if (!file) return;
  if (file.type !== 'application/pdf') return showToast('Must be a PDF file', 'error');

  showToast('Uploading PDF...', 'info');
  try {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(API + `/courses/admin/courses/${courseId}/upload-pdf`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Upload failed');
    }

    showToast('Course PDF uploaded successfully!', 'success');
    loadCoursesTab();
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}


async function loadCoursesTab() {
  document.getElementById('courses-list-view').style.display = 'block';
  document.getElementById('lessons-manager-view').style.display = 'none';
  const tbody = document.getElementById('courses-body');
  tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:40px;color:#555;">Loading...</td></tr>`;

  try {
    const res = await fetch(API + '/courses/admin/courses', { headers });
    if (!res.ok) throw new Error('Failed to load courses');
    coursesCache = await res.json();
    renderCourses();
  } catch (err) {
    console.error(err);
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:40px;color:red;">Error loading courses.</td></tr>`;
  }
}

function renderCourses() {
  const tbody = document.getElementById('courses-body');
  if (coursesCache.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;color:#555;">No courses found. Add one above.</td></tr>`;
    return;
  }
  tbody.innerHTML = coursesCache.map((c, idx) => {
    const thumbSrc = c.thumbnail_url ? (c.thumbnail_url.startsWith('/') ? API + c.thumbnail_url : c.thumbnail_url) : '';
    let resources = [];
    try { resources = c.pdf_url ? JSON.parse(c.pdf_url) : []; } catch(e) {
      if (c.pdf_url) resources = [{ name: 'Resource', url: c.pdf_url }];
    }
    return `
    <tr>
      <td>
        <div style="display:flex;align-items:center;gap:6px;">
          ${thumbSrc
        ? `<img src="${thumbSrc}" style="width:80px;height:45px;border-radius:4px;object-fit:cover;" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
               <div style="display:none;width:80px;height:45px;border-radius:4px;background:#222;align-items:center;justify-content:center;color:#555;font-size:10px;">No img</div>`
        : `<div style="width:80px;height:45px;border-radius:4px;background:#222;display:flex;align-items:center;justify-content:center;color:#555;font-size:10px;">No img</div>`
      }
          <button class="btn-action" style="font-size:11px;padding:3px 6px;" onclick="uploadCourseThumbnail(${c.id})" title="Upload thumbnail"><i class="fa-solid fa-image"></i></button>
          <input type="file" id="course-thumb-upload-${c.id}" accept="image/*" style="display:none" onchange="handleCourseThumbSelected(event, ${c.id})">
        </div>
      </td>
      <td><strong>${escapeHtml(c.title)}</strong><br><small style="color:#888;">${escapeHtml((c.description || '').substring(0, 30))}...</small></td>
      <td>${c.total_lessons || 0} lessons</td>
      <td>
        <div style="display:flex;align-items:center;gap:6px;">
          <span style="color:${resources.length ? '#22c55e' : '#555'};font-size:12px;">${resources.length} resource${resources.length !== 1 ? 's' : ''}</span>
          <button class="btn-action" style="font-size:12px;padding:4px 8px;" onclick="openResourcesModal(${c.id})"><i class="fa-solid fa-link"></i> Manage</button>
        </div>
      </td>
      <td>
        <label class="switch">
          <input type="checkbox" ${c.is_published ? 'checked' : ''} onchange="toggleCoursePublish(${c.id}, this)">
          <span class="slider round"></span>
        </label>
      </td>
      <td>
        <button class="btn-action" onclick="moveCourse(${c.id}, 'up')" title="Move up" ${idx === 0 ? 'disabled' : ''} style="margin-right:4px;${idx === 0 ? 'opacity:.35;cursor:not-allowed;' : ''}"><i class="fa-solid fa-arrow-up"></i></button>
        <button class="btn-action" onclick="moveCourse(${c.id}, 'down')" title="Move down" ${idx === coursesCache.length - 1 ? 'disabled' : ''} style="margin-right:8px;${idx === coursesCache.length - 1 ? 'opacity:.35;cursor:not-allowed;' : ''}"><i class="fa-solid fa-arrow-down"></i></button>
        <button class="btn-action" onclick="showLessonsManager(${c.id}, '${escapeHtml(c.title).replace(/'/g, "\\\\'")}')" style="margin-right:8px;"><i class="fa-solid fa-list"></i> Lessons</button>
        <button class="btn-action" onclick="showExamsManager(${c.id}, '${escapeHtml(c.title).replace(/'/g, "\\\\'")}')" style="margin-right:8px;"><i class="fa-solid fa-file-pen"></i> Exams</button>
        <button class="btn-action" onclick="openCertificateModal(${c.id})" style="margin-right:8px;" title="Certificate template"><i class="fa-solid fa-graduation-cap"></i> Certificate</button>
        <button class="btn-action" onclick="openEditCourseModal(${c.id})"><i class="fa-solid fa-pen"></i></button>
        <button class="btn-action" onclick="openDeleteCourseModal(${c.id})" style="color:#ef4444;"><i class="fa-solid fa-trash"></i></button>
      </td>
    </tr>`;
  }).join('');
}

async function toggleCoursePublish(id, checkbox) {
  const isPub = checkbox.checked;
  try {
    const res = await fetch(API + `/courses/admin/courses/${id}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ is_published: isPub })
    });
    if (!res.ok) throw new Error('Failed to update course');
    showToast(`Course ${isPub ? 'published' : 'hidden'} successfully`, 'success');
  } catch (err) {
    checkbox.checked = !isPub;
    showToast('Error updating course', 'error');
  }
}

// -- Course Modals --
function openAddCourseModal() {
  document.getElementById('course-title').value = '';
  document.getElementById('course-desc').value = '';
  document.getElementById('course-thumbnail').value = '';
  document.getElementById('course-total-lessons').value = '0';
  document.getElementById('add-course-modal').style.display = 'flex';
}

async function submitAddCourse() {
  const data = {
    title: document.getElementById('course-title').value,
    description: document.getElementById('course-desc').value,
    thumbnail_url: document.getElementById('course-thumbnail').value,
    total_lessons: parseInt(document.getElementById('course-total-lessons').value) || 0,
    course_time: document.getElementById('course-time').value || null,
    is_published: false
  };
  if (!data.title) return showToast('Title is required', 'error');

  try {
    const res = await fetch(API + '/courses/admin/courses', {
      method: 'POST',
      headers,
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to create course');
    closeModal('add-course-modal');
    showToast('Course created successfully!', 'success');
    loadCoursesTab();
  } catch (e) { showToast(e.message, 'error'); }
}

function openEditCourseModal(id) {
  const c = coursesCache.find(x => x.id === id);
  if (!c) return;
  document.getElementById('edit-course-id').value = c.id;
  document.getElementById('edit-course-title').value = c.title;
  document.getElementById('edit-course-desc').value = c.description || '';
  document.getElementById('edit-course-thumbnail').value = c.thumbnail_url || '';
  document.getElementById('edit-course-total-lessons').value = c.total_lessons || 0;
  document.getElementById('edit-course-time').value = c.course_time || '';
  document.getElementById('edit-course-modal').style.display = 'flex';
}

async function submitEditCourse() {
  const id = document.getElementById('edit-course-id').value;
  const data = {
    title: document.getElementById('edit-course-title').value,
    description: document.getElementById('edit-course-desc').value,
    thumbnail_url: document.getElementById('edit-course-thumbnail').value,
    total_lessons: parseInt(document.getElementById('edit-course-total-lessons').value) || 0,
    course_time: document.getElementById('edit-course-time').value || null
  };
  try {
    const res = await fetch(API + `/courses/admin/courses/${id}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Update failed');
    closeModal('edit-course-modal');
    showToast('Course updated!', 'success');
    loadCoursesTab();
  } catch (e) { showToast(e.message, 'error'); }
}

function openDeleteCourseModal(id) {
  document.getElementById('delete-course-id').value = id;
  document.getElementById('delete-course-modal').style.display = 'flex';
}

async function confirmDeleteCourse() {
  const id = document.getElementById('delete-course-id').value;
  try {
    const res = await fetch(API + `/courses/admin/courses/${id}`, {
      method: 'DELETE', headers
    });
    if (!res.ok) throw new Error('Delete failed');
    closeModal('delete-course-modal');
    showToast('Course deleted', 'info');
    loadCoursesTab();
  } catch (e) { showToast(e.message, 'error'); }
}

// -- Course Resources Modal (Multiple Links) --
let _resourcesModalCourseId = null;
let _resourcesList = [];

function openResourcesModal(courseId) {
  _resourcesModalCourseId = courseId;
  const course = coursesCache.find(c => c.id === courseId);
  if (!course) return;
  try { _resourcesList = course.pdf_url ? JSON.parse(course.pdf_url) : []; } catch(e) {
    _resourcesList = course.pdf_url ? [{ name: 'Resource', url: course.pdf_url }] : [];
  }
  renderResourcesModalList();
  document.getElementById('resources-modal').style.display = 'flex';
}

function renderResourcesModalList() {
  const list = document.getElementById('resources-modal-list');
  if (_resourcesList.length === 0) {
    list.innerHTML = '<p style="color:#555;text-align:center;padding:12px 0;">No resources yet. Add one below.</p>';
    return;
  }
  list.innerHTML = _resourcesList.map((r, i) => `
    <div style="display:flex;align-items:center;gap:8px;padding:8px 10px;background:#111;border:1px solid #222;border-radius:6px;margin-bottom:6px;">
      <i class="fa-solid fa-link" style="color:#3f8ff9;font-size:13px;flex-shrink:0;"></i>
      <div style="flex:1;min-width:0;">
        <div style="font-size:13px;font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(r.name)}</div>
        <div style="font-size:11px;color:#555;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(r.url)}</div>
      </div>
      <a href="${escapeHtml(r.url)}" target="_blank" style="color:#3f8ff9;font-size:12px;"><i class="fa-solid fa-arrow-up-right-from-square"></i></a>
      <button onclick="removeResourceItem(${i})" style="background:none;border:none;color:#ef4444;cursor:pointer;padding:4px 6px;"><i class="fa-solid fa-trash"></i></button>
    </div>
  `).join('');
}

function removeResourceItem(idx) {
  _resourcesList.splice(idx, 1);
  renderResourcesModalList();
}

function addResourceItem() {
  const nameEl = document.getElementById('res-name-input');
  const urlEl = document.getElementById('res-url-input');
  const name = nameEl.value.trim();
  const url = urlEl.value.trim();
  if (!name || !url) return showToast('Enter both a name and URL', 'error');
  _resourcesList.push({ name, url });
  nameEl.value = '';
  urlEl.value = '';
  renderResourcesModalList();
}

async function saveResourcesList() {
  try {
    const res = await fetch(API + `/courses/admin/courses/${_resourcesModalCourseId}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ pdf_url: _resourcesList.length ? JSON.stringify(_resourcesList) : null })
    });
    if (!res.ok) throw new Error('Failed to save');
    showToast('Resources saved!', 'success');
    document.getElementById('resources-modal').style.display = 'none';
    loadCoursesTab();
  } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

async function uploadResourceFile(event) {
  const file = event.target.files[0];
  if (!file) return;
  if (file.type !== 'application/pdf') return showToast('Must be a PDF file', 'error');

  showToast('Uploading PDF...', 'info');
  try {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(API + `/courses/admin/courses/${_resourcesModalCourseId}/upload-pdf`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Upload failed');
    }

    const data = await res.json();
    showToast('Course PDF uploaded successfully!', 'success');
    
    // Update local list from returned data
    try {
      _resourcesList = data.pdf_url ? JSON.parse(data.pdf_url) : [];
    } catch(e) {
      _resourcesList = [];
    }
    
    renderResourcesModalList();
    loadCoursesTab(); // to update table view in background
    
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  } finally {
    event.target.value = ''; // clear input
  }
}


// -- Course Thumbnail Upload --
function uploadCourseThumbnail(courseId) {
  document.getElementById(`course-thumb-upload-${courseId}`).click();
}

async function handleCourseThumbSelected(event, courseId) {
  const file = event.target.files[0];
  if (!file) return;
  if (!file.type.startsWith('image/')) return showToast('Must be an image file', 'error');

  showToast('Uploading thumbnail...', 'info');
  try {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(API + `/courses/admin/courses/${courseId}/upload-thumbnail`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Upload failed');
    }

    showToast('Thumbnail uploaded successfully!', 'success');
    loadCoursesTab();
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}

// ==========================================
//  LESSONS MANAGER (LEVEL 2)
// ==========================================

function showCoursesList() {
  currentCourseId = null;
  document.getElementById('courses-list-view').style.display = 'block';
  document.getElementById('lessons-manager-view').style.display = 'none';
  const ev = document.getElementById('exams-manager-view');
  if (ev) ev.style.display = 'none';
  if (uploadPollInterval) { clearInterval(uploadPollInterval); uploadPollInterval = null; }
  loadCoursesTab();
}

async function showLessonsManager(courseId, title) {
  currentCourseId = courseId;
  document.getElementById('courses-list-view').style.display = 'none';
  document.getElementById('lessons-manager-view').style.display = 'block';
  const ev = document.getElementById('exams-manager-view');
  if (ev) ev.style.display = 'none';
  document.getElementById('lm-course-title').textContent = title + ' - Lessons';
  await loadLessons();
  startLessonStatusPolling();
}

let lessonsCache = [];
async function loadLessons() {
  const tbody = document.getElementById('lessons-body');
  tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;color:#555;">Loading...</td></tr>`;
  try {
    const res = await fetch(API + `/courses/admin/${currentCourseId}/lessons`, { headers });
    if (!res.ok) throw new Error('Failed');
    lessonsCache = await res.json();
    renderLessons();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;color:red;">Error loading lessons.</td></tr>`;
  }
}

function getUniqueChapters() {
  const seen = new Set();
  return lessonsCache
    .map(l => l.section_title || '')
    .filter(s => { if (seen.has(s)) return false; seen.add(s); return true; });
}

function renderLessons() {
  const tbody = document.getElementById('lessons-body');

  if (lessonsCache.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;color:#555;">No lessons found. Add one above.</td></tr>`;
    return;
  }

  // Group lessons by section_title (chapter)
  const groups = {};
  const groupOrder = [];
  lessonsCache.forEach(l => {
    const chap = l.section_title || '(No Chapter)';
    if (!groups[chap]) { groups[chap] = []; groupOrder.push(chap); }
    groups[chap].push(l);
  });

  let html = '';
  groupOrder.forEach(chap => {
    const lessons = groups[chap];
    const chapEsc = escapeHtml(chap);
    const chapRaw = chap === '(No Chapter)' ? '' : chap;

    // Chapter header row
    html += `
    <tr style="background:rgba(63,143,249,0.06);">
      <td colspan="5" style="padding:10px 16px;">
        <div style="display:flex;align-items:center;gap:10px;">
          <i class="fa-solid fa-layer-group" style="color:#3f8ff9;font-size:13px;"></i>
          <strong style="color:#3f8ff9;font-size:13px;">${chapEsc}</strong>
          <span style="color:#555;font-size:12px;">(${lessons.length} lesson${lessons.length !== 1 ? 's' : ''})</span>
        </div>
      </td>
      <td style="padding:10px 16px;">
        <button class="btn-action" style="font-size:11px;padding:3px 8px;white-space:nowrap;"
          onclick="openAddLessonModal(${JSON.stringify(chapRaw)})"
          title="Add lesson to this chapter">
          <i class="fa-solid fa-plus"></i> Add Lesson
        </button>
      </td>
    </tr>`;

    // Lessons inside chapter
    lessons.forEach(l => {
      let statHtml = '';
      if (l.video_status === 'ready') statHtml = '<span class="video-badge ready"><span class="dot"></span>Ready</span>';
      else if (l.video_status === 'processing') statHtml = '<span class="video-badge processing"><span class="dot"></span>Processing...</span>';
      else if (l.video_status === 'error') statHtml = '<span class="video-badge error"><span class="dot"></span>Error</span>';
      else statHtml = '<span class="video-badge pending"><span class="dot"></span>Pending</span>';

      const hasPdf = !!l.pdf_url;

      html += `
      <tr>
        <td style="color:#888;padding-left:28px;">${l.order}</td>
        <td><strong>${escapeHtml(l.title)}</strong>${l.is_project ? ' <span style="font-size:10px;font-weight:700;color:#a855f7;background:rgba(168,85,247,0.12);border:1px solid rgba(168,85,247,0.35);padding:2px 7px;border-radius:10px;white-space:nowrap;">📋 Project</span>' : ''}</td>
        <td id="dur-cell-${l.id}" onclick="startEditDuration(${l.id})" style="cursor:pointer;" title="Click to edit duration">${l.duration_minutes} min <i class="fa-solid fa-pen" style="font-size:9px;color:#555;margin-left:4px;"></i></td>
        <td id="status-cell-${l.id}">${statHtml}</td>
        <td>
          <div style="display:flex;align-items:center;gap:6px;">
            ${hasPdf ? '<i class="fa-solid fa-file-pdf" style="color:#ef4444;"></i>' : '<span style="color:#555;">No PDF</span>'}
            <button class="btn-action" style="font-size:12px;padding:4px 8px;" onclick="uploadPdf(${l.id})">${hasPdf ? 'Replace' : 'Upload'}</button>
            <input type="file" id="pdf-upload-${l.id}" accept="application/pdf" style="display:none" onchange="handlePdfSelected(event, ${l.id})">
          </div>
        </td>
        <td>
          <button class="btn-action" onclick="openEditLessonModal(${l.id})"><i class="fa-solid fa-pen"></i></button>
          <button class="btn-action" onclick="openDeleteLessonModal(${l.id})" style="color:#ef4444;"><i class="fa-solid fa-trash"></i></button>
        </td>
      </tr>`;
    });
  });

  tbody.innerHTML = html;
}

// -- Inline duration editing (click the "X min" cell in the lessons table) --
function startEditDuration(id) {
  const cell = document.getElementById(`dur-cell-${id}`);
  if (!cell || cell.querySelector('input')) return; // already editing
  const l = lessonsCache.find(x => x.id === id);
  if (!l) return;

  cell.innerHTML = `<input type="number" min="0" value="${l.duration_minutes || 0}"
    style="width:64px;background:#111;border:1px solid #3f8ff9;border-radius:6px;color:#fff;padding:4px 6px;font-size:13px;" /> min`;
  const input = cell.querySelector('input');
  input.focus();
  input.select();

  let done = false;
  const finish = (save) => {
    if (done) return;
    done = true;
    const val = parseInt(input.value) || 0;
    if (!save || val === (l.duration_minutes || 0)) { renderLessons(); return; }
    saveDuration(id, val);
  };
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') input.blur();
    else if (e.key === 'Escape') finish(false);
  });
  input.addEventListener('blur', () => finish(true));
}

async function saveDuration(id, minutes) {
  try {
    const res = await fetch(API + `/courses/admin/lessons/${id}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ duration_minutes: minutes })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Update failed');
    }
    const l = lessonsCache.find(x => x.id === id);
    if (l) l.duration_minutes = minutes;
    showToast('Duration updated ✅', 'success');
  } catch (e) { showToast(e.message, 'error'); }
  renderLessons();
}

// -- Polling CF Stream --
function startLessonStatusPolling() {
  if (uploadPollInterval) clearInterval(uploadPollInterval);
  uploadPollInterval = setInterval(async () => {
    const processingLessons = lessonsCache.filter(l => l.video_status === 'processing' || l.video_status === 'pending');
    if (processingLessons.length === 0) return;

    for (let l of processingLessons) {
      if (!l.cloudflare_video_id) continue;
      try {
        const res = await fetch(API + `/courses/admin/lessons/${l.id}/status`, { headers });
        if (res.ok) {
          const data = await res.json();
          if (data.status !== l.video_status) {
            l.video_status = data.status;
            renderLessons();
          }
        }
      } catch (e) { /* ignore */ }
    }
  }, 4000);
}

async function uploadPdf(lessonId) {
  const url = prompt('Enter the link for the lesson resource (PDF, Docs, etc.):');
  if (url === null) return;

  showToast('Saving link...', 'info');
  try {
    const res = await fetch(API + `/courses/admin/lessons/${lessonId}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ pdf_url: url.trim() || null })
    });
    if (!res.ok) throw new Error('Failed to save link');

    showToast('Resource link updated successfully!', 'success');
    loadLessons();
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}

// ==========================================
//  PROJECTS REVIEW TAB
// ==========================================

let projectsCache = [];

function projectAdminStatusLabel(status) {
  const labels = {
    pending: 'Pending',
    approved: 'Approved',
    changes_requested: 'Changes Requested'
  };
  return labels[status] || status || 'Pending';
}

function projectFileHref(project) {
  if (!project || !project.file_url) return '#';
  return project.file_url.startsWith('http') ? project.file_url : API + project.file_url;
}

async function loadProjectsTab() {
  const tbody = document.getElementById('projects-body');
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;color:#555;">Loading...</td></tr>`;

  const params = new URLSearchParams();
  const status = document.getElementById('project-status-filter')?.value || 'all';
  const search = document.getElementById('project-search')?.value.trim() || '';
  if (status) params.set('status', status);
  if (search) params.set('search', search);

  try {
    const res = await fetch(API + `/admin/projects?${params.toString()}`, { headers });
    if (!res.ok) throw new Error('Failed to load projects');
    projectsCache = await res.json();
    renderProjectsTable();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;color:#ef4444;">Failed to load projects.</td></tr>`;
  }
}

function renderProjectsTable() {
  const tbody = document.getElementById('projects-body');
  if (!tbody) return;

  if (!projectsCache.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;color:#888;">No project submissions found.</td></tr>`;
    return;
  }

  tbody.innerHTML = projectsCache.map(project => {
    return `
      <tr>
        <td>
          <strong style="color:#fff;">${escapeHtml(project.member_name || 'Unknown member')}</strong>
          <div style="color:#888;font-size:12px;margin-top:2px;">${escapeHtml(project.member_email || '')}</div>
        </td>
        <td>${escapeHtml(project.course_title || 'Unknown course')}</td>
        <td>
          <a href="${projectFileHref(project)}" target="_blank" style="color:#3f8ff9;text-decoration:none;">
            ${escapeHtml(project.file_name || 'project.json')}
          </a>
        </td>
        <td><span class="project-admin-status ${project.status}">${projectAdminStatusLabel(project.status)}</span></td>
        <td>${formatDate(project.created_at)}</td>
        <td class="project-actions-cell">
          <div class="project-actions">
            <button class="project-action-btn review" onclick="openProjectReviewModal(${project.id})" title="Review">
              <i class="fa-solid fa-pen-to-square"></i><span>Review</span>
            </button>
            <a class="project-action-btn open" href="${projectFileHref(project)}" target="_blank">
              <i class="fa-solid fa-arrow-up-right-from-square"></i><span>Open</span>
            </a>
            ${currentUserIsAdmin ? `
            <button class="project-action-btn open" onclick="downloadProjectFile(${project.id}, this)" title="Download file">
              <i class="fa-solid fa-download"></i><span>Download</span>
            </button>` : ''}
            <button class="project-action-btn delete" onclick="deleteProjectSubmission(${project.id})" title="Delete">
              <i class="fa-solid fa-trash"></i><span>Delete</span>
            </button>
          </div>
        </td>
      </tr>`;
  }).join('');

  if (typeof lucide !== 'undefined') lucide.createIcons();
}

async function downloadProjectFile(projectId, btnEl) {
  const project = projectsCache.find(item => item.id === projectId);
  const fileName = (project && project.file_name) ? project.file_name : `project_${projectId}`;
  let restore = null;
  if (btnEl) {
    restore = btnEl.innerHTML;
    btnEl.disabled = true;
    btnEl.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>...</span>';
  }
  try {
    const res = await fetch(`${API}/admin/projects/${projectId}/download`, { headers });
    if (!res.ok) throw new Error('Download failed');
    const blob = await res.blob();
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(blobUrl);
    showToast('⬇ File downloaded', 'success');
  } catch (e) {
    showToast('❌ Download failed', 'error');
  } finally {
    if (btnEl && restore !== null) {
      btnEl.disabled = false;
      btnEl.innerHTML = restore;
    }
  }
}

async function getProjectForReview(projectId) {
  const cached = projectsCache.find(item => item.id === projectId);
  if (cached) return cached;
  const res = await fetch(API + `/admin/projects/${projectId}`, { headers });
  if (!res.ok) throw new Error('Failed to load project');
  return res.json();
}

async function openProjectReviewModal(projectId) {
  try {
    const project = await getProjectForReview(projectId);
    let modal = document.getElementById('project-review-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'project-review-modal';
      modal.className = 'modal-overlay-team';
      modal.style.display = 'none';
      document.body.appendChild(modal);
    }

    modal.innerHTML = `
      <div class="modal-box-team">
        <div class="modal-header-team">
          <h3>Review Project</h3>
          <button class="modal-close-team" onclick="closeProjectReviewModal()">x</button>
        </div>
        <div class="modal-body-team">
          <div style="display:grid;gap:10px;margin-bottom:14px;color:#ccc;font-size:14px;">
            <div><strong style="color:#fff;">Member:</strong> ${escapeHtml(project.member_name || 'Unknown')} (${escapeHtml(project.member_email || '')})</div>
            <div><strong style="color:#fff;">Course:</strong> ${escapeHtml(project.course_title || 'Unknown course')}</div>
            <div><strong style="color:#fff;">Status:</strong> <span class="project-admin-status ${project.status}">${projectAdminStatusLabel(project.status)}</span></div>
            <div><strong style="color:#fff;">File:</strong> <a href="${projectFileHref(project)}" target="_blank" style="color:#3f8ff9;">${escapeHtml(project.file_name || 'project.json')}</a></div>
          </div>
          <div class="fg">
            <label>Review Notes</label>
            <textarea id="project-review-notes" class="project-notes-input" placeholder="Write feedback for the member...">${escapeHtml(project.admin_notes || '')}</textarea>
          </div>
        </div>
        <div class="modal-footer-team">
          <button class="btn-cancel-team" onclick="closeProjectReviewModal()">Cancel</button>
          <button class="btn-confirm-team" onclick="saveProjectNotes(${project.id})">Save Notes</button>
          <button class="btn-confirm-team" onclick="approveProject(${project.id})">Approve</button>
          <button class="btn-confirm-team" style="background:#f59e0b;color:#111;" onclick="requestProjectChanges(${project.id})">Request Changes</button>
          <button class="btn-confirm-team danger" onclick="deleteProjectSubmission(${project.id})">Delete</button>
        </div>
      </div>`;
    modal.style.display = 'flex';
  } catch (e) {
    showToast(e.message || 'Failed to open project', 'error');
  }
}

function closeProjectReviewModal() {
  const modal = document.getElementById('project-review-modal');
  if (modal) modal.style.display = 'none';
}

function currentProjectNotes() {
  return document.getElementById('project-review-notes')?.value.trim() || '';
}

async function sendProjectReviewAction(projectId, action, notes) {
  const res = await fetch(API + `/admin/projects/${projectId}/${action}`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ notes })
  });
  if (!res.ok) {
    let message = 'Project review failed';
    try {
      const body = await res.json();
      message = body.detail || message;
    } catch (e) { }
    throw new Error(message);
  }
  return res.json();
}

async function saveProjectNotes(projectId) {
  try {
    await sendProjectReviewAction(projectId, 'notes', currentProjectNotes());
    showToast('Project notes saved', 'success');
    closeProjectReviewModal();
    loadProjectsTab();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function approveProject(projectId) {
  try {
    await sendProjectReviewAction(projectId, 'approve', currentProjectNotes());
    showToast('Project approved', 'success');
    closeProjectReviewModal();
    loadProjectsTab();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function requestProjectChanges(projectId) {
  const notes = currentProjectNotes();
  if (!notes) {
    showToast('Review notes are required when requesting changes', 'error');
    return;
  }

  try {
    await sendProjectReviewAction(projectId, 'request-changes', notes);
    showToast('Change request sent', 'success');
    closeProjectReviewModal();
    loadProjectsTab();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function deleteProjectSubmission(projectId) {
  const project = projectsCache.find(item => item.id === projectId);
  const label = project ? `${project.file_name} by ${project.member_name}` : 'this project submission';
  if (!confirm(`Delete ${label}? This will remove the uploaded file too.`)) return;

  try {
    const res = await fetch(API + `/admin/projects/${projectId}`, {
      method: 'DELETE',
      headers
    });
    if (!res.ok && res.status !== 204) {
      let message = 'Failed to delete project';
      try {
        const body = await res.json();
        message = body.detail || message;
      } catch (e) { }
      throw new Error(message);
    }
    showToast('Project deleted', 'success');
    closeProjectReviewModal();
    loadProjectsTab();
  } catch (e) {
    showToast(e.message || 'Failed to delete project', 'error');
  }
}

// -- Lesson Modals --
let selectedVideoFile = null;
let lessonEntryCount = 0;

function buildLessonEntry(index, defaultOrder) {
  return `
  <div id="lesson-entry-${index}" style="background:#111;border:1px solid #2a2a2a;border-radius:10px;padding:14px;position:relative;">
    ${index > 0 ? `<button type="button" onclick="removeLessonEntry(${index})"
      style="position:absolute;top:10px;right:10px;background:none;border:none;color:#555;cursor:pointer;font-size:14px;"
      title="Remove">✕</button>` : ''}
    <div style="display:flex;flex-direction:column;gap:10px;">
      <div class="fg">
        <label style="font-size:12px;color:#888;">Title *</label>
        <input type="text" id="lesson-title-${index}" placeholder="Lesson title..." />
      </div>
      <div style="display:flex;gap:10px;">
        <div class="fg" style="flex:1;">
          <label style="font-size:12px;color:#888;">Order</label>
          <input type="number" id="lesson-order-${index}" value="${defaultOrder}" style="width:100%;" />
        </div>
      </div>
      <div class="fg" style="display:flex;flex-direction:column;gap:8px;">
        <label style="font-size:12px;color:#888;">Video Provider *</label>
        <div style="display:flex;gap:8px;margin-bottom:4px;">
          <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;color:#ccc;">
            <input type="radio" name="video-provider-${index}" value="vdo" checked
              onchange="toggleVideoProvider(${index})"
              style="accent-color:#3f8ff9;" />
            VdoCipher
          </label>
          <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;color:#ccc;">
            <input type="radio" name="video-provider-${index}" value="bunny"
              onchange="toggleVideoProvider(${index})"
              style="accent-color:#3f8ff9;" />
            Bunny.net
          </label>
        </div>

        <!-- VdoCipher input (shown by default) -->
        <div id="vdo-section-${index}">
          <input type="text" id="lesson-video-url-${index}"
            placeholder="VdoCipher Video ID, e.g. abc123def456..."
            style="width:100%;padding:10px;background:#0a0a0a;border:1px solid #333;border-radius:6px;color:#fff;font-family:inherit;font-size:14px;box-sizing:border-box;" />
          <small style="font-size:11px;color:#555;margin-top:4px;display:block;">الـ Video ID من لوحة تحكم VdoCipher (مش الـ URL كامل)</small>
        </div>

        <!-- Bunny input (hidden by default) -->
        <div id="bunny-section-${index}" style="display:none;">
          <input type="text" id="lesson-bunny-url-${index}"
            placeholder="Bunny embed URL, e.g. https://iframe.mediadelivery.net/embed/..."
            style="width:100%;padding:10px;background:#0a0a0a;border:1px solid #333;border-radius:6px;color:#fff;font-family:inherit;font-size:14px;box-sizing:border-box;" />
          <small style="font-size:11px;color:#555;margin-top:4px;display:block;">الـ iframe embed URL من Bunny Stream</small>
        </div>
      </div>
      <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:13px;color:#ccc;margin-top:4px;">
        <input type="checkbox" id="lesson-is-project-${index}" style="accent-color:#3f8ff9;width:16px;height:16px;" />
        📋 Project — الدرس ده ليه project (هيظهر زرار في صفحة الكورس يودّي على الـ Projects)
      </label>
      <div style="margin-top:8px;padding:8px 10px;background:rgba(63,143,249,0.06);border:1px solid rgba(63,143,249,0.2);border-radius:6px;">
        <p style="font-size:11px;color:#888;margin:0;">
          📎 <strong style="color:#3f8ff9;">Resources (PDFs):</strong>
          بعد إنشاء الـ lesson، افتح Edit عشان تضيف الـ PDF resources.
        </p>
      </div>
    </div>
  </div>`;
}

function addAnotherLessonEntry() {
  const container = document.getElementById('lessons-entries');
  const defaultOrder = lessonsCache.length + lessonEntryCount + 1;
  container.insertAdjacentHTML('beforeend', buildLessonEntry(lessonEntryCount, defaultOrder));
  lessonEntryCount++;
}

function removeLessonEntry(index) {
  const el = document.getElementById(`lesson-entry-${index}`);
  if (el) el.remove();
}

function toggleVideoProvider(index) {
  const selected = document.querySelector(`input[name="video-provider-${index}"]:checked`)?.value;
  const vdoSection = document.getElementById(`vdo-section-${index}`);
  const bunnySection = document.getElementById(`bunny-section-${index}`);
  if (!vdoSection || !bunnySection) return;
  if (selected === 'bunny') {
    vdoSection.style.display = 'none';
    bunnySection.style.display = 'block';
  } else {
    vdoSection.style.display = 'block';
    bunnySection.style.display = 'none';
  }
}

function toggleEditVideoProvider() {
  const selected = document.querySelector('input[name="edit-video-provider"]:checked')?.value;
  const vdoSection = document.getElementById('edit-vdo-section');
  const bunnySection = document.getElementById('edit-bunny-section');
  if (!vdoSection || !bunnySection) return;
  if (selected === 'bunny') {
    vdoSection.style.display = 'none';
    bunnySection.style.display = 'block';
  } else {
    vdoSection.style.display = 'block';
    bunnySection.style.display = 'none';
  }
}

function handleSectionSelectChange(sel) {
  const custom = document.getElementById('lesson-section-custom');
  if (sel.value === '__new__') {
    custom.style.display = 'block';
    custom.focus();
  } else {
    custom.style.display = 'none';
  }
}

function openAddLessonModal(prefilledChapter) {
  lessonEntryCount = 0;
  const container = document.getElementById('lessons-entries');
  container.innerHTML = '';

  // Populate chapter select
  const sel = document.getElementById('lesson-section-select');
  const chapters = getUniqueChapters();
  sel.innerHTML = chapters.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c) || '(No Chapter)'}</option>`).join('')
    + `<option value="__new__">+ New Chapter...</option>`;

  // Pre-select chapter if provided
  if (prefilledChapter !== undefined && prefilledChapter !== null) {
    sel.value = prefilledChapter || chapters[0] || '__new__';
    if (!sel.value || sel.value === '__new__') {
      sel.value = '__new__';
      document.getElementById('lesson-section-custom').style.display = 'block';
      if (prefilledChapter) document.getElementById('lesson-section-custom').value = prefilledChapter;
    } else {
      document.getElementById('lesson-section-custom').style.display = 'none';
      document.getElementById('lesson-section-custom').value = '';
    }
  } else {
    document.getElementById('lesson-section-custom').style.display = 'none';
    document.getElementById('lesson-section-custom').value = '';
  }

  // Add first lesson entry
  container.insertAdjacentHTML('beforeend', buildLessonEntry(lessonEntryCount, lessonsCache.length + 1));
  lessonEntryCount++;

  document.getElementById('addLessonSubmitBtn').disabled = false;
  document.getElementById('addLessonSubmitBtn').textContent = 'Create Lessons';
  document.getElementById('add-lesson-modal').style.display = 'flex';
}

async function submitAddLesson() {
  // Resolve chapter
  const sel = document.getElementById('lesson-section-select');
  let sectionTitle = sel.value === '__new__'
    ? (document.getElementById('lesson-section-custom').value.trim())
    : sel.value;

  // Collect all lesson entries
  const entries = document.querySelectorAll('[id^="lesson-entry-"]');
  const lessons = [];
  for (const entry of entries) {
    const idx = entry.id.split('-').pop();
    const title = document.getElementById(`lesson-title-${idx}`)?.value?.trim();
    const order = parseInt(document.getElementById(`lesson-order-${idx}`)?.value) || 0;

    // Detect which provider was selected for this lesson entry
    const providerSelected = document.querySelector(`input[name="video-provider-${idx}"]:checked`)?.value || 'vdo';
    const vdoUrl = document.getElementById(`lesson-video-url-${idx}`)?.value?.trim() || '';
    const bunnyUrl = document.getElementById(`lesson-bunny-url-${idx}`)?.value?.trim() || '';

    if (!title) return showToast('كل lesson لازم يكون ليه عنوان', 'error');

    const isProject = document.getElementById(`lesson-is-project-${idx}`)?.checked || false;
    const lessonData = { title, section_title: sectionTitle, order, is_project: isProject };

    if (providerSelected === 'bunny') {
      if (!bunnyUrl) return showToast(`Lesson "${title}": Bunny URL مطلوب`, 'error');
      lessonData.bunny_video_url = bunnyUrl;
    } else {
      if (!vdoUrl) return showToast(`Lesson "${title}": VdoCipher Video ID مطلوب`, 'error');
      lessonData.vdo_video_id = vdoUrl;
    }

    lessons.push(lessonData);
  }

  if (lessons.length === 0) return showToast('أضف lesson واحد على الأقل', 'error');

  const btn = document.getElementById('addLessonSubmitBtn');
  btn.disabled = true;
  btn.textContent = `Creating ${lessons.length} lesson${lessons.length > 1 ? 's' : ''}...`;

  let successCount = 0;
  let failCount = 0;
  try {
    for (const lesson of lessons) {
      const res = await fetch(API + `/courses/admin/${currentCourseId}/lessons`, {
        method: 'POST',
        headers,
        body: JSON.stringify(lesson)
      });
      if (res.ok) successCount++;
      else failCount++;
    }

    closeModal('add-lesson-modal');
    if (failCount === 0) {
      showToast(`${successCount} lesson${successCount > 1 ? 's' : ''} created successfully!`, 'success');
    } else {
      showToast(`${successCount} succeeded, ${failCount} failed`, 'error');
    }
    loadLessons();

    // If exactly one lesson was created, offer quick access to add resources
    if (successCount === 1 && failCount === 0) {
      setTimeout(() => {
        showToast('💡 لإضافة PDF resources، افتح Edit على الـ lesson الجديدة', 'info');
      }, 1500);
    }
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Create Lessons';
  }
}

function openEditLessonModal(id) {
  const l = lessonsCache.find(x => x.id === id);
  if (!l) return;
  document.getElementById('edit-lesson-id').value = l.id;
  document.getElementById('edit-lesson-title').value = l.title;
  document.getElementById('edit-lesson-section').value = l.section_title || '';
  document.getElementById('edit-lesson-status').value = l.video_status || 'pending';
  // Pre-select the correct provider based on what's stored
  if (l.bunny_video_url) {
    document.getElementById('edit-provider-bunny').checked = true;
    document.getElementById('edit-lesson-bunny-url').value = l.bunny_video_url;
    document.getElementById('edit-lesson-video-url').value = '';
  } else {
    document.getElementById('edit-provider-vdo').checked = true;
    document.getElementById('edit-lesson-video-url').value = l.vdo_video_id || '';
    document.getElementById('edit-lesson-bunny-url').value = '';
  }
  toggleEditVideoProvider(); // Apply visibility
  document.getElementById('edit-lesson-order').value = l.order || 0;
  document.getElementById('edit-lesson-duration').value = l.duration_minutes || 0;
  const projChk = document.getElementById('edit-lesson-is-project');
  if (projChk) projChk.checked = !!l.is_project;

  // Render existing PDFs
  renderLessonPdfs(l.pdf_url);

  // Reset upload input
  const inp = document.getElementById('lesson-pdf-upload-input');
  if (inp) inp.value = '';
  const prog = document.getElementById('lesson-pdf-upload-progress');
  if (prog) prog.style.display = 'none';

  document.getElementById('edit-lesson-modal').style.display = 'flex';
}

function renderLessonPdfs(pdfUrl) {
  const container = document.getElementById('lesson-pdfs-list');
  if (!container) return;

  let pdfs = [];
  try {
    const parsed = pdfUrl ? JSON.parse(pdfUrl) : [];
    if (Array.isArray(parsed)) {
      pdfs = parsed;
    } else if (typeof pdfUrl === 'string' && pdfUrl.startsWith('/')) {
      pdfs = [{ name: 'Resource', url: pdfUrl }];
    }
  } catch (e) {
    if (pdfUrl) pdfs = [{ name: 'Resource', url: pdfUrl }];
  }

  if (pdfs.length === 0) {
    container.innerHTML = '<p style="font-size:12px;color:#555;margin:0;">No PDFs added yet.</p>';
    return;
  }

  container.innerHTML = pdfs.map((p, i) => `
    <div style="display:flex;align-items:center;gap:8px;background:#111;border:1px solid #222;border-radius:8px;padding:8px 12px;" id="lesson-pdf-row-${i}">
      <i class="fa-solid fa-file-pdf" style="color:#ef4444;font-size:14px;flex-shrink:0;"></i>
      <a href="${API + p.url}" target="_blank"
        style="flex:1;font-size:12px;color:#3f8ff9;text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
        title="${p.name}">${p.name}</a>
      <button onclick="deleteLessonPdf('${encodeURIComponent(p.url)}')"
        style="background:none;border:1px solid #3a1a1a;color:#ef4444;width:26px;height:26px;border-radius:6px;cursor:pointer;font-size:12px;display:flex;align-items:center;justify-content:center;flex-shrink:0;"
        title="Delete PDF">
        <i class="fa-solid fa-trash"></i>
      </button>
    </div>
  `).join('');
}

async function uploadLessonPdf() {
  const lessonId = document.getElementById('edit-lesson-id').value;
  const input = document.getElementById('lesson-pdf-upload-input');
  const btn = document.getElementById('lesson-pdf-upload-btn');
  const progressDiv = document.getElementById('lesson-pdf-upload-progress');
  const bar = document.getElementById('lesson-pdf-upload-bar');
  const status = document.getElementById('lesson-pdf-upload-status');

  if (!input.files || !input.files[0]) {
    showToast('Please select a PDF file first', 'error');
    return;
  }

  const file = input.files[0];
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showToast('Only PDF files are allowed', 'error');
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  btn.disabled = true;
  btn.textContent = '...';
  progressDiv.style.display = 'block';
  bar.style.width = '0%';
  status.textContent = 'Uploading...';

  try {
    await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', API + `/courses/admin/lessons/${lessonId}/pdfs`);
      xhr.setRequestHeader('Authorization', `Bearer ${localStorage.getItem('token')}`);
      xhr.upload.onprogress = e => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100);
          bar.style.width = pct + '%';
          status.textContent = `Uploading... ${pct}%`;
        }
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          const data = JSON.parse(xhr.responseText);
          // Update the lesson in cache
          const l = lessonsCache.find(x => x.id == lessonId);
          if (l) l.pdf_url = JSON.stringify(data.all_pdfs);
          renderLessonPdfs(JSON.stringify(data.all_pdfs));
          input.value = '';
          status.textContent = '✅ Uploaded!';
          bar.style.width = '100%';
          showToast('PDF uploaded successfully', 'success');
          resolve();
        } else {
          reject(new Error('Upload failed'));
        }
      };
      xhr.onerror = () => reject(new Error('Network error'));
      xhr.send(formData);
    });
  } catch (e) {
    showToast(e.message || 'Upload failed', 'error');
    status.textContent = '❌ Failed';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Upload';
    setTimeout(() => { progressDiv.style.display = 'none'; }, 2000);
  }
}

async function deleteLessonPdf(encodedUrl) {
  const lessonId = document.getElementById('edit-lesson-id').value;
  const pdfUrl = decodeURIComponent(encodedUrl);

  if (!confirm('Delete this PDF?')) return;

  try {
    const res = await fetch(API + `/courses/admin/lessons/${lessonId}/pdfs?pdf_url=${encodeURIComponent(pdfUrl)}`, {
      method: 'DELETE',
      headers
    });
    if (!res.ok) throw new Error('Delete failed');
    const data = await res.json();
    // Update cache
    const l = lessonsCache.find(x => x.id == lessonId);
    if (l) l.pdf_url = data.all_pdfs.length > 0 ? JSON.stringify(data.all_pdfs) : null;
    renderLessonPdfs(l ? l.pdf_url : null);
    showToast('PDF deleted', 'info');
  } catch (e) {
    showToast(e.message || 'Delete failed', 'error');
  }
}

async function submitEditLesson() {
  const id = document.getElementById('edit-lesson-id').value;
  const providerSelected = document.querySelector('input[name="edit-video-provider"]:checked')?.value || 'vdo';
  let vdoUrl = document.getElementById('edit-lesson-video-url').value.trim();
  let bunnyUrl = document.getElementById('edit-lesson-bunny-url').value.trim();

  // Handle VdoCipher embed code paste (extract ID from src attribute if pasted as iframe)
  const srcMatch = vdoUrl.match(/src="([^"]+)"/);
  if (srcMatch) vdoUrl = srcMatch[1];

  const hasVideo = providerSelected === 'bunny' ? !!bunnyUrl : !!vdoUrl;
  const status = hasVideo ? 'ready' : 'pending';

  const body = {
    title: document.getElementById('edit-lesson-title').value,
    section_title: document.getElementById('edit-lesson-section').value,
    video_status: status,
    order: parseInt(document.getElementById('edit-lesson-order').value) || 0,
    duration_minutes: parseInt(document.getElementById('edit-lesson-duration').value) || 0,
    is_project: document.getElementById('edit-lesson-is-project')?.checked || false
  };

  if (providerSelected === 'bunny') {
    if (bunnyUrl) {
      body.bunny_video_url = bunnyUrl;
      body.vdo_video_id = null; // 🔒 clear the other provider's field
    }
  } else {
    if (vdoUrl) {
      body.vdo_video_id = vdoUrl;
      body.bunny_video_url = null; // 🔒 clear the other provider's field
    }
  }

  try {
    const res = await fetch(API + `/courses/admin/lessons/${id}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify(body)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Update failed');
    }
    closeModal('edit-lesson-modal');
    showToast('Lesson updated ✅', 'success');
    loadLessons();
  } catch (e) { showToast(e.message, 'error'); }
}

function openDeleteLessonModal(id) {
  document.getElementById('delete-lesson-id').value = id;
  document.getElementById('delete-lesson-modal').style.display = 'flex';
}

async function confirmDeleteLesson() {
  const id = document.getElementById('delete-lesson-id').value;
  try {
    const res = await fetch(API + `/courses/admin/lessons/${id}`, {
      method: 'DELETE', headers
    });
    if (!res.ok) throw new Error('Delete failed');
    closeModal('delete-lesson-modal');
    showToast('Lesson deleted', 'info');
    loadLessons();
  } catch (e) { showToast(e.message, 'error'); }
}

// ══════════════════════════════════════════════════════════
//  GUEST OF HONORS TAB
// ══════════════════════════════════════════════════════════

let allGohGuests = [];
let allGohSessions = [];
let allGohSuggestions = [];

async function loadGohTab() {
  await Promise.all([loadGohGuests(), loadGohSessions(), loadGohSuggestions()]);
  populateGuestSelect();
}

async function loadGohGuests() {
  try {
    const res = await fetch(API + '/guests/', { headers });
    if (!res.ok) throw new Error("Failed to load guests");
    allGohGuests = await res.json();
    renderGohGuests();
  } catch (err) {
    console.error(err);
    document.getElementById('goh-guests-body').innerHTML = `<tr><td colspan="5" style="text-align:center;color:#ef4444;padding:40px;">Failed to load guests</td></tr>`;
  }
}

async function loadGohSessions() {
  try {
    const res = await fetch(API + '/guests/sessions/', { headers });
    if (!res.ok) throw new Error("Failed to load sessions");
    allGohSessions = await res.json();
    renderGohSessions();
  } catch (err) {
    console.error(err);
    document.getElementById('goh-sessions-body').innerHTML = `<tr><td colspan="6" style="text-align:center;color:#ef4444;padding:40px;">Failed to load sessions</td></tr>`;
  }
}

async function loadGohSuggestions() {
  try {
    const res = await fetch(API + '/guests/suggest', { headers });
    if (!res.ok) throw new Error("Failed to load suggested guests");
    allGohSuggestions = await res.json();
    renderGohSuggestions();
  } catch (err) {
    console.error(err);
    document.getElementById('goh-suggestions-body').innerHTML = `<tr><td colspan="5" style="text-align:center;color:#ef4444;padding:40px;">Failed to load suggested guests</td></tr>`;
  }
}

function renderGohGuests() {
  const tbody = document.getElementById('goh-guests-body');
  if (!allGohGuests.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#888;padding:40px;">No guests found</td></tr>`;
    return;
  }
  tbody.innerHTML = allGohGuests.map(g => {
    let uiAvatar = '';
    if (g.avatar_url) {
      uiAvatar = g.avatar_url.startsWith('http') ? g.avatar_url : API + g.avatar_url;
    } else {
      let initials = g.avatar_initials || g.name.substring(0, 2).toUpperCase();
      let color = g.avatar_color || '#c1ff11';
      uiAvatar = `https://ui-avatars.com/api/?name=${encodeURIComponent(initials)}&background=${color.replace('#', '')}&color=fff&size=40&bold=true`;
    }
    return `
    <tr>
      <td><img src="${uiAvatar}" style="border-radius:50%; width:40px; height:40px; object-fit:cover;" /></td>
      <td>${escapeHtml(g.name)} ${g.is_featured ? '<span style="color:#f59e0b;font-size:12px;">★</span>' : ''}</td>
      <td style="color:#888;">${escapeHtml(g.title)}</td>
      <td><span class="status-pill active">${escapeHtml(g.category) || 'None'}</span></td>
      <td>
        <div class="action-btns">
          <button class="btn-action edit" onclick="openEditGuestModal(${g.id})" title="Edit"><i data-lucide="edit-2" style="width:14px;height:14px;"></i></button>
          <button class="btn-action delete" onclick="deleteGuest(${g.id})" title="Delete"><i data-lucide="trash-2" style="width:14px;height:14px;"></i></button>
        </div>
      </td>
    </tr>
  `}).join('');
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function renderGohSessions() {
  const tbody = document.getElementById('goh-sessions-body');
  if (!allGohSessions.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:#888;padding:40px;">No sessions found</td></tr>`;
    return;
  }
  tbody.innerHTML = allGohSessions.map(s => {
    const dateFormatted = new Date(s.session_date).toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    const statusClass = s.status === 'upcoming' ? 'active' : 'inactive';
    return `
    <tr>
      <td>${dateFormatted}</td>
      <td>${escapeHtml(s.guest_name || 'Unknown')}</td>
      <td style="color:#888;">${escapeHtml(s.title)}</td>
      <td>${escapeHtml(s.platform) || 'Online'}</td>
      <td><span class="status-pill ${statusClass}">${escapeHtml(s.status)}</span></td>
      <td>
        <div class="action-btns">
          <button class="btn-action edit" onclick="openEditGuestSessionModal(${s.id})" title="Edit"><i data-lucide="edit-2" style="width:14px;height:14px;"></i></button>
          <button class="btn-action delete" onclick="deleteGuestSession(${s.id})" title="Delete"><i data-lucide="trash-2" style="width:14px;height:14px;"></i></button>
        </div>
      </td>
    </tr>
  `}).join('');
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function populateGuestSelect() {
  const sel = document.getElementById('session-guest-id');
  if (!sel) return;
  sel.innerHTML = '<option value="">Select a Guest...</option>' + allGohGuests.map(g => `<option value="${g.id}">${escapeHtml(g.name)}</option>`).join('');
}

function renderGohSuggestions() {
  const tbody = document.getElementById('goh-suggestions-body');
  if (!allGohSuggestions || !allGohSuggestions.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#888;padding:40px;">No community suggestions yet</td></tr>`;
    return;
  }
  tbody.innerHTML = allGohSuggestions.map(s => {
    const dateFormatted = new Date(s.created_at).toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric' });
    return `
    <tr>
      <td>${dateFormatted}</td>
      <td>${escapeHtml(s.user_name || 'Unknown')}</td>
      <td style="color:#fff; font-weight:600;">${escapeHtml(s.name)}</td>
      <td style="color:#888;">${escapeHtml(s.reason || '—')}</td>
      <td>
        <div class="action-btns">
          <button class="btn-action delete" onclick="deleteSuggestedGuest(${s.id})" title="Delete"><i data-lucide="trash-2" style="width:14px;height:14px;"></i></button>
        </div>
      </td>
    </tr>
  `}).join('');
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

async function deleteSuggestedGuest(id) {
  if (!confirm("Are you sure you want to delete this suggestion?")) return;
  try {
    const res = await fetch(API + '/guests/suggest/' + id, { method: 'DELETE', headers });
    if (!res.ok) throw new Error('Failed to delete suggestion');
    showToast('🗑️ Suggestion deleted', 'success');
    loadGohTab();
  } catch (e) {
    showToast('❌ ' + e.message, 'error');
  }
}

function openGuestModal() {
  document.getElementById('guest-id').value = '';
  document.getElementById('guest-name').value = '';
  document.getElementById('guest-title').value = '';
  document.getElementById('guest-company').value = '';
  document.getElementById('guest-bio').value = '';
  document.getElementById('guest-avatar-file').value = '';
  document.getElementById('guest-category').value = '';
  document.getElementById('guest-sessions-count').value = '0';
  document.getElementById('guest-attendees-count').value = '0';
  document.getElementById('guest-rating').value = '0.0';
  document.getElementById('guest-featured').checked = false;
  document.getElementById('add-guest-modal').style.display = 'flex';
}

async function deleteGuest(id) {
  document.getElementById('delete-goh-id').value = id;
  document.getElementById('delete-guest-modal').style.display = 'flex';
}

async function confirmDeleteGuest() {
  const id = document.getElementById('delete-goh-id').value;
  try {
    const res = await fetch(API + '/guests/' + id, { method: 'DELETE', headers });
    if (!res.ok) throw new Error('Failed to delete guest');
    closeModal('delete-guest-modal');
    showToast('🗑️ Guest deleted successfully!', 'success');
    loadGohTab();
  } catch (e) {
    showToast('❌ ' + e.message, 'error');
  }
}

function openEditGuestModal(id) {
  const g = allGohGuests.find(x => x.id === id);
  if (!g) return;
  document.getElementById('guest-id').value = g.id;
  document.getElementById('guest-name').value = g.name || '';
  document.getElementById('guest-title').value = g.title || '';
  document.getElementById('guest-company').value = g.company || '';
  document.getElementById('guest-bio').value = g.bio || '';
  // We can't set file input value programmatically for security reasons,
  // but we store the existing URL in a data attribute to keep it if no new file is uploaded
  document.getElementById('guest-avatar-file').value = '';
  document.getElementById('guest-avatar-file').dataset.existingUrl = g.avatar_url || '';
  document.getElementById('guest-category').value = g.category || '';
  document.getElementById('guest-sessions-count').value = g.sessions_count || 0;
  document.getElementById('guest-attendees-count').value = g.attendees_count || 0;
  document.getElementById('guest-rating').value = g.rating || 0;
  document.getElementById('guest-featured').checked = g.is_featured;
  document.getElementById('add-guest-modal').style.display = 'flex';
}

async function submitGuest() {
  const id = document.getElementById('guest-id').value;
  let avatarUrl = id ? document.getElementById('guest-avatar-file').dataset.existingUrl || null : null;
  const fileInput = document.getElementById('guest-avatar-file');

  if (fileInput.files && fileInput.files[0]) {
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    try {
      const uploadRes = await fetch(API + '/guests/upload-avatar', {
        method: 'POST',
        headers: { 'Authorization': headers['Authorization'] },
        body: formData
      });
      if (!uploadRes.ok) throw new Error('Avatar upload failed');
      const uploadData = await uploadRes.json();
      avatarUrl = uploadData.avatar_url;
    } catch (e) {
      showToast(e.message, 'error');
      return;
    }
  }

  const data = {
    name: document.getElementById('guest-name').value,
    title: document.getElementById('guest-title').value,
    company: document.getElementById('guest-company').value,
    bio: document.getElementById('guest-bio').value || null,
    avatar_url: avatarUrl,
    avatar_initials: null,
    avatar_color: null,
    category: document.getElementById('guest-category').value || null,
    is_featured: document.getElementById('guest-featured').checked,
    sessions_count: parseInt(document.getElementById('guest-sessions-count').value) || 0,
    attendees_count: parseInt(document.getElementById('guest-attendees-count').value) || 0,
    rating: parseFloat(document.getElementById('guest-rating').value) || 0.0
  };
  if (!data.name || !data.title) { showToast('Name and Title are required', 'error'); return; }

  try {
    const method = id ? 'PUT' : 'POST';
    const url = id ? API + '/guests/' + id : API + '/guests/';
    const res = await fetch(url, { method, headers, body: JSON.stringify(data) });
    if (!res.ok) throw new Error('Request failed');
    showToast('Guest saved!', 'success');
    closeModal('add-guest-modal');
    loadGohTab();
  } catch (e) { showToast(e.message, 'error'); }
}

function openGuestSessionModal() {
  document.getElementById('session-goh-id').value = '';
  document.getElementById('session-guest-id').value = '';
  document.getElementById('session-goh-title').value = '';
  document.getElementById('session-goh-description').value = '';

  // Format current date for datetime-local
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  document.getElementById('session-goh-date').value = now.toISOString().slice(0, 16);

  document.getElementById('session-goh-platform').value = '';
  document.getElementById('session-goh-url').value = '';
  document.getElementById('session-goh-status').value = 'upcoming';
  document.getElementById('session-goh-attendees').value = '0';
  document.getElementById('session-goh-rating').value = '0';
  document.getElementById('add-guest-session-modal').style.display = 'flex';
}

async function deleteSession(id) {
  document.getElementById('delete-goh-session-id').value = id;
  document.getElementById('delete-goh-session-modal').style.display = 'flex';
}

async function confirmDeleteGohSession() {
  const id = document.getElementById('delete-goh-session-id').value;
  try {
    const res = await fetch(API + '/guests/sessions/' + id, { method: 'DELETE', headers });
    if (!res.ok) throw new Error('Failed to delete session');
    closeModal('delete-goh-session-modal');
    showToast('🗑️ Session deleted successfully!', 'success');
    loadGohTab();
  } catch (e) {
    showToast('❌ ' + e.message, 'error');
  }
}

function openEditGuestSessionModal(id) {
  const s = allGohSessions.find(x => x.id === id);
  if (!s) return;
  document.getElementById('session-goh-id').value = s.id;
  document.getElementById('session-guest-id').value = s.guest_id;
  document.getElementById('session-goh-title').value = s.title || '';
  document.getElementById('session-goh-description').value = s.description || '';

  const d = new Date(s.session_date);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  document.getElementById('session-goh-date').value = d.toISOString().slice(0, 16);

  document.getElementById('session-goh-platform').value = s.platform || '';
  document.getElementById('session-goh-url').value = s.session_url || '';
  document.getElementById('session-goh-status').value = s.status || 'upcoming';
  document.getElementById('session-goh-attendees').value = s.attendees_count || 0;
  document.getElementById('session-goh-rating').value = s.rating || 0;
  document.getElementById('add-guest-session-modal').style.display = 'flex';
}

async function submitGuestSession() {
  const id = document.getElementById('session-goh-id').value;
  const guest_id = document.getElementById('session-guest-id').value;
  if (!guest_id) { showToast('Please select a guest', 'error'); return; }

  const data = {
    guest_id: parseInt(guest_id),
    title: document.getElementById('session-goh-title').value,
    session_date: new Date(document.getElementById('session-goh-date').value).toISOString(),
    platform: document.getElementById('session-goh-platform').value,
    session_url: document.getElementById('session-goh-url').value,
    status: document.getElementById('session-goh-status').value,
    attendees_count: parseInt(document.getElementById('session-goh-attendees').value) || 0,
    rating: parseFloat(document.getElementById('session-goh-rating').value) || 0,
    description: document.getElementById('session-goh-description').value || null
  };
  if (!data.title || !data.session_date) { showToast('Title and Date are required', 'error'); return; }

  try {
    const method = id ? 'PUT' : 'POST';
    const url = id ? API + '/guests/sessions/' + id : API + '/guests/sessions/';
    const res = await fetch(url, { method, headers, body: JSON.stringify(data) });
    if (!res.ok) throw new Error('Request failed');
    showToast('Session saved!', 'success');
    closeModal('add-guest-session-modal');
    loadGohTab();
  } catch (e) { showToast(e.message, 'error'); }
}

async function deleteGuestSession(id) {
  if (!confirm('Are you sure you want to delete this session?')) return;
  try {
    const res = await fetch(API + '/guests/sessions/' + id, { method: 'DELETE', headers });
    if (!res.ok) throw new Error('Delete failed');
    showToast('Session deleted!', 'success');
    loadGohTab();
  } catch (e) { showToast(e.message, 'error'); }
}

// ═══════════════════════════════════════════════════════════════
//  COURSE CERTIFICATE TEMPLATE
// ═══════════════════════════════════════════════════════════════
function openCertificateModal(courseId) {
  const c = coursesCache.find(x => x.id === courseId);
  if (!c) return;
  document.getElementById('cert-course-id').value = courseId;
  document.getElementById('cert-modal-title').textContent = 'Certificate — ' + c.title;
  const preview = document.getElementById('cert-preview');
  const removeBtn = document.getElementById('cert-remove-btn');
  if (c.certificate_url) {
    preview.innerHTML = `<img src="${API + c.certificate_url}?t=${Date.now()}" style="max-width:100%;border-radius:8px;border:1px solid #262626;" alt="Certificate template">`;
    removeBtn.style.display = '';
  } else {
    preview.innerHTML = `<div style="padding:30px;text-align:center;color:#666;border:1px dashed #333;border-radius:8px;">No certificate template uploaded yet.<br><small>Upload the certificate image — the member's name, course name and date are added automatically on download.</small></div>`;
    removeBtn.style.display = 'none';
  }
  document.getElementById('cert-file-input').value = '';
  document.getElementById('certificate-modal').style.display = 'flex';
}

async function uploadCertificate() {
  const courseId = document.getElementById('cert-course-id').value;
  const input = document.getElementById('cert-file-input');
  if (!input.files || !input.files[0]) return showToast('Choose an image file first', 'error');
  const file = input.files[0];
  if (!file.type.startsWith('image/')) return showToast('Must be an image file', 'error');

  const btn = document.getElementById('cert-upload-btn');
  btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Uploading...';
  try {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(API + `/courses/admin/${courseId}/certificate`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Upload failed');
    }
    const data = await res.json();
    const c = coursesCache.find(x => x.id == courseId);
    if (c) c.certificate_url = data.certificate_url;
    showToast('Certificate template uploaded!', 'success');
    openCertificateModal(parseInt(courseId)); // refresh the preview
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
  btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-upload"></i> Upload';
}

async function removeCertificate() {
  const courseId = document.getElementById('cert-course-id').value;
  if (!confirm('Remove the certificate template for this course?')) return;
  try {
    const res = await fetch(API + `/courses/admin/${courseId}/certificate`, { method: 'DELETE', headers });
    if (!res.ok) throw new Error('Failed');
    const c = coursesCache.find(x => x.id == courseId);
    if (c) c.certificate_url = null;
    showToast('Certificate template removed', 'info');
    openCertificateModal(parseInt(courseId));
  } catch (e) {
    showToast('Error removing certificate', 'error');
  }
}

// ═══════════════════════════════════════════════════════════════
//  EXAMS MANAGER (per course)
// ═══════════════════════════════════════════════════════════════
let examsCache = [];
let examBuilderQCount = 0;
let examLessonsCache = []; // lessons of the current course, for the placement dropdown

async function loadExamLessons() {
  try {
    const res = await fetch(API + `/courses/admin/${currentCourseId}/lessons`, { headers });
    examLessonsCache = res.ok ? await res.json() : [];
  } catch (e) { examLessonsCache = []; }
}

function examPlacementLabel(ex) {
  if (!ex.after_lesson_id) return '<span style="color:#888;">End of course</span>';
  const idx = examLessonsCache.findIndex(l => l.id === ex.after_lesson_id);
  if (idx === -1) return '<span style="color:#888;">End of course</span>';
  return `After ${idx + 1}. ${escapeHtml(examLessonsCache[idx].title)}`;
}

function populateExamLessonSelect(selectedId) {
  const sel = document.getElementById('exam-builder-lesson');
  if (!sel) return;
  sel.innerHTML = '<option value="">End of course (not tied to a lesson)</option>' +
    examLessonsCache.map((l, i) =>
      `<option value="${l.id}" ${selectedId === l.id ? 'selected' : ''}>After ${i + 1}. ${escapeHtml(l.title)}</option>`
    ).join('');
}

async function showExamsManager(courseId, title) {
  currentCourseId = courseId;
  document.getElementById('courses-list-view').style.display = 'none';
  document.getElementById('lessons-manager-view').style.display = 'none';
  document.getElementById('exams-manager-view').style.display = 'block';
  document.getElementById('em-course-title').textContent = title + ' - Exams';
  if (uploadPollInterval) { clearInterval(uploadPollInterval); uploadPollInterval = null; }
  await loadExams();
}

async function loadExams() {
  const tbody = document.getElementById('exams-body');
  tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:40px;color:#555;">Loading...</td></tr>`;
  try {
    const [res] = await Promise.all([
      fetch(API + `/admin/courses/${currentCourseId}/exams`, { headers }),
      loadExamLessons()
    ]);
    if (!res.ok) throw new Error('Failed');
    examsCache = await res.json();
    renderExams();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:40px;color:red;">Error loading exams.</td></tr>`;
  }
}

function renderExams() {
  const tbody = document.getElementById('exams-body');
  if (!examsCache.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:40px;color:#555;">No exams yet. Add one above.</td></tr>`;
    return;
  }
  tbody.innerHTML = examsCache.map((ex, idx) => `
    <tr>
      <td style="color:#888;">${idx + 1}</td>
      <td><strong>${escapeHtml(ex.title)}</strong>${ex.description ? `<br><small style="color:#888;">${escapeHtml((ex.description || '').substring(0, 50))}</small>` : ''}</td>
      <td>${ex.question_count} question${ex.question_count !== 1 ? 's' : ''}</td>
      <td style="font-size:12.5px;">${examPlacementLabel(ex)}</td>
      <td>${ex.pass_percent}%</td>
      <td>
        <label class="switch">
          <input type="checkbox" ${ex.is_published ? 'checked' : ''} onchange="toggleExamPublish(${ex.id}, this)">
          <span class="slider round"></span>
        </label>
      </td>
      <td>
        <button class="btn-action" onclick="openExamBuilder(${ex.id})"><i class="fa-solid fa-pen"></i></button>
        <button class="btn-action" onclick="deleteExam(${ex.id})" style="color:#ef4444;"><i class="fa-solid fa-trash"></i></button>
      </td>
    </tr>`).join('');
}

async function toggleExamPublish(examId, checkbox) {
  const isPub = checkbox.checked;
  try {
    const res = await fetch(API + `/admin/exams/${examId}`, {
      method: 'PATCH', headers, body: JSON.stringify({ is_published: isPub })
    });
    if (!res.ok) throw new Error('Failed');
    const ex = examsCache.find(e => e.id === examId);
    if (ex) ex.is_published = isPub;
    showToast(`Exam ${isPub ? 'published' : 'hidden'}`, 'success');
  } catch (e) {
    checkbox.checked = !isPub;
    showToast('Error updating exam', 'error');
  }
}

async function deleteExam(examId) {
  if (!confirm('Delete this exam and all its attempts? This cannot be undone.')) return;
  try {
    const res = await fetch(API + `/admin/exams/${examId}`, { method: 'DELETE', headers });
    if (!res.ok) throw new Error('Failed');
    showToast('Exam deleted', 'info');
    loadExams();
  } catch (e) { showToast('Error deleting exam', 'error'); }
}

// -- Exam Builder Modal --
function examQuestionCard(q, idx) {
  const opts = (q && q.options) || ['', '', '', ''];
  while (opts.length < 4) opts.push('');
  const correct = (q && typeof q.correct === 'number') ? q.correct : 0;
  const optionsHtml = opts.slice(0, 4).map((o, oi) => `
    <div class="exam-opt-row" style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
      <input type="radio" name="exam-q-correct-${idx}" class="exam-q-correct" value="${oi}" ${oi === correct ? 'checked' : ''} title="Mark as correct answer" style="width:18px;height:18px;accent-color:#22c55e;cursor:pointer;">
      <input type="text" class="exam-q-opt" value="${escapeHtml(o)}" placeholder="Option ${oi + 1}" style="flex:1;padding:8px 10px;background:#0d0d0d;border:1px solid #262626;border-radius:6px;color:#fff;">
    </div>`).join('');
  return `
    <div class="exam-q-card" data-qidx="${idx}" style="background:#141414;border:1px solid #262626;border-radius:10px;padding:16px;margin-bottom:14px;">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
        <span style="color:#3f8ff9;font-weight:700;font-size:13px;">Q<span class="exam-q-num">${idx + 1}</span></span>
        <input type="text" class="exam-q-text" value="${q ? escapeHtml(q.text || '') : ''}" placeholder="Question text..." style="flex:1;padding:9px 12px;background:#0d0d0d;border:1px solid #262626;border-radius:6px;color:#fff;">
        <button type="button" class="btn-action" onclick="removeExamQuestion(this)" style="color:#ef4444;" title="Remove question"><i class="fa-solid fa-trash"></i></button>
      </div>
      <div style="font-size:11px;color:#666;margin-bottom:8px;"><i class="fa-solid fa-circle-check" style="color:#22c55e;"></i> Select the radio next to the correct answer</div>
      ${optionsHtml}
    </div>`;
}

function addExamQuestion(q) {
  const container = document.getElementById('exam-questions-container');
  const idx = examBuilderQCount++;
  container.insertAdjacentHTML('beforeend', examQuestionCard(q, idx));
}

function removeExamQuestion(btn) {
  const card = btn.closest('.exam-q-card');
  if (card) card.remove();
  // renumber
  document.querySelectorAll('#exam-questions-container .exam-q-card').forEach((c, i) => {
    const num = c.querySelector('.exam-q-num');
    if (num) num.textContent = i + 1;
  });
}

function openExamBuilder(examId) {
  examBuilderQCount = 0;
  document.getElementById('exam-questions-container').innerHTML = '';
  document.getElementById('exam-builder-id').value = '';
  document.getElementById('exam-builder-title').value = '';
  document.getElementById('exam-builder-desc').value = '';
  document.getElementById('exam-builder-pass').value = '70';
  document.getElementById('exam-builder-published').checked = false;
  populateExamLessonSelect(null);

  if (examId) {
    const ex = examsCache.find(e => e.id === examId);
    document.getElementById('exam-builder-heading').textContent = 'Edit Exam';
    // Fetch full exam (with correct answers) since the list summary omits questions
    fetch(API + `/admin/exams/${examId}`, { headers })
      .then(r => r.json())
      .then(full => {
        document.getElementById('exam-builder-id').value = full.id;
        document.getElementById('exam-builder-title').value = full.title || '';
        document.getElementById('exam-builder-desc').value = full.description || '';
        document.getElementById('exam-builder-pass').value = full.pass_percent ?? 70;
        document.getElementById('exam-builder-published').checked = !!full.is_published;
        populateExamLessonSelect(full.after_lesson_id || null);
        (full.questions || []).forEach(q => addExamQuestion(q));
        if (!(full.questions || []).length) addExamQuestion();
      })
      .catch(() => showToast('Error loading exam', 'error'));
  } else {
    document.getElementById('exam-builder-heading').textContent = 'Add Exam';
    addExamQuestion();
  }
  document.getElementById('exam-builder-modal').style.display = 'flex';
}

function collectExamData() {
  const questions = [];
  document.querySelectorAll('#exam-questions-container .exam-q-card').forEach(card => {
    const text = card.querySelector('.exam-q-text').value.trim();
    const options = Array.from(card.querySelectorAll('.exam-q-opt')).map(i => i.value.trim());
    const checked = card.querySelector('.exam-q-correct:checked');
    const correct = checked ? parseInt(checked.value) : 0;
    questions.push({ text, options, correct });
  });
  const lessonSel = document.getElementById('exam-builder-lesson');
  return {
    title: document.getElementById('exam-builder-title').value.trim(),
    description: document.getElementById('exam-builder-desc').value.trim() || null,
    pass_percent: parseInt(document.getElementById('exam-builder-pass').value) || 0,
    is_published: document.getElementById('exam-builder-published').checked,
    after_lesson_id: lessonSel && lessonSel.value ? parseInt(lessonSel.value) : null,
    questions
  };
}

async function submitExam() {
  const data = collectExamData();
  if (!data.title) return showToast('Exam title is required', 'error');
  // client-side validation to avoid silently dropped questions
  const valid = data.questions.filter(q => q.text && q.options.filter(o => o).length >= 2);
  if (!valid.length) return showToast('Add at least one question with a prompt and 2+ options', 'error');

  const examId = document.getElementById('exam-builder-id').value;
  try {
    const url = examId ? API + `/admin/exams/${examId}` : API + `/admin/courses/${currentCourseId}/exams`;
    const method = examId ? 'PATCH' : 'POST';
    const res = await fetch(url, { method, headers, body: JSON.stringify(data) });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Save failed');
    }
    closeModal('exam-builder-modal');
    showToast(examId ? 'Exam updated!' : 'Exam created!', 'success');
    loadExams();
  } catch (e) { showToast(e.message, 'error'); }
}
