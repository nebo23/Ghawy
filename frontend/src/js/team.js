(async () => {
  const user = await requireActiveUser();
  if (!user) return;
})();

// ═══ AUTH GUARD ═══
const token = localStorage.getItem('token');
if (!token) window.location.href = 'login.html';

const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };
function authHeaders() { return headers; }

let allUsers = [];
let filteredUsers = [];
let currentPage = 1;
const LIMIT = 20;
let selectedUserId = null;

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
    'courses': 'Courses Management',
    'projects': 'Projects Review'
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
    });
  });
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
                const fullUrl = window.getAvatarSrc(u);
                el.innerHTML = `<img src="${fullUrl}" alt="" />`;
            }
        });
    }
  } catch (e) { }
  await loadUsers();

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
      document.getElementById('users-tbody').innerHTML = `<tr><td colspan="8" style="text-align:center;color:#ef4444;padding:40px">⛔ Admin access required</td></tr>`;
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
    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;color:#888;padding:40px">No members found</td></tr>`;
    document.getElementById('pagination').innerHTML = '';
    return;
  }

  tbody.innerHTML = paginated.map(user => {
    // Subscription type cell
    const subType = user.subscription_type || null;
    const subCell = subType
      ? `<span class="sub-badge ${subType}">${subType === 'monthly' ? '📅 Monthly' : '📆 Yearly'}</span>`
      : `<span class="sub-badge none">—</span>`;

    // Next charge cell
    let chargeCell = '—';
    if (user.next_charge_at) {
      const nextDate = new Date(user.next_charge_at);
      const days = user.days_until_charge;
      const isOverdue = days !== null && days < 0;
      const isSoon = days !== null && days <= 3 && days >= 0;

      chargeCell = `
        <div class="charge-info">
          <div class="charge-date">${nextDate.toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric' })}</div>
          <div class="charge-days ${isOverdue ? 'overdue' : isSoon ? 'soon' : ''}">
            ${isOverdue ? '⚠️ Overdue' : isSoon ? `⚡ ${days}d left` : `${days}d`}
          </div>
        </div>`;
    } else if (user.has_card_token) {
      chargeCell = '<span style="color:#888">Token saved</span>';
    }

    return `
    <tr>
      <td>
        <div class="member-cell">
          <img src="${user.avatar_url || '/static/avatars/default.png'}" class="member-avatar" onerror="this.src='./imgs/ghawi-logo.png'"/>
          <div>
            <div class="member-name">${escapeHtml(user.full_name)}</div>
            <div class="member-badge">${getBadgeLabel(user.badge)}</div>
          </div>
        </div>
      </td>
      <td class="text-secondary">${escapeHtml(user.email)}</td>
      <td class="text-secondary">${user.phone || '—'}</td>
      <td class="text-secondary">${user.country || '—'}</td>
      <td>
        <div style="font-size:13px">${formatDate(user.created_at)}</div>
        ${user.subscription_start ?
        `<div style="font-size:11px;color:#3f8ff9">💳 Since ${formatDate(user.subscription_start)}</div>`
        : ''}
      </td>
      <td>${subCell}</td>
      <td>${chargeCell}</td>
      <td>
        <label class="t-switch">
          <input type="checkbox" ${user.is_active ? 'checked' : ''} onchange="toggleActive(${user.id}, this)"/>
          <span class="t-slider"></span>
        </label>
      </td>
      <td>
        <span class="role-badge ${user.is_admin ? 'admin' : 'member'}" onclick="toggleAdmin(${user.id})" style="cursor:pointer; display:inline-flex; align-items:center;" title="Click to toggle role">
          ${user.is_admin ? '<i data-lucide="shield-check" style="width:14px;height:14px;margin-right:4px;"></i> Admin' : '<i data-lucide="user" style="width:14px;height:14px;margin-right:4px;"></i> Member'}
        </span>
      </td>
      <td>
        <div class="action-btns">
          ${user.failed_charge_count > 0 ?
        `<span class="failed-badge" title="${user.failed_charge_count} failed charge(s)"><i data-lucide="alert-triangle" style="width:12px;height:12px;margin-right:2px;"></i>${user.failed_charge_count}</span>`
        : ''}
          <button class="btn-action reset" onclick="openResetPasswordModal(${user.id})" title="Reset Password"><i data-lucide="key" style="width:14px;height:14px;"></i></button>
          <button class="btn-action delete" onclick="confirmDelete(${user.id}, '${escapeHtml(user.full_name).replace(/'/g, "\\'")}')" title="Delete"><i data-lucide="trash-2" style="width:14px;height:14px;"></i></button>
        </div>
      </td>
    </tr>
  `}).join('');

  renderPagination();
  setTimeout(() => { if (typeof lucide !== 'undefined') lucide.createIcons(); }, 10);
}

// ── Recurring Panel ──────────────────────────────────
async function loadRecurringStatus() {
  try {
    const res = await fetch(API + '/admin/recurring-status', { headers });
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById('rec-total').textContent = data.total_subscribers;
    document.getElementById('rec-due').textContent = data.due_now;
    document.getElementById('rec-soon').textContent = data.upcoming_7_days;
  } catch (e) { }
}

function toggleRecurringPanel() {
  const body = document.getElementById('recurring-body');
  const toggle = document.getElementById('recurring-toggle');
  if (body.style.display === 'none') {
    body.style.display = 'block';
    toggle.textContent = '▲';
    loadRecurringStatus();
  } else {
    body.style.display = 'none';
    toggle.textContent = '▼';
  }
}

async function triggerRecurring() {
  if (!confirm('Run recurring charges for all due users now?')) return;
  try {
    const res = await fetch(API + '/admin/trigger-recurring', {
      method: 'POST',
      headers
    });
    const data = await res.json();
    showToast(
      `✅ Done: ${data.charged} charged, ${data.failed} failed, ${data.total_due} total due`,
      data.failed > 0 ? 'error' : 'success'
    );
    await loadUsers();
    await loadRecurringStatus();
  } catch (e) {
    showToast('❌ Failed to trigger recurring', 'error');
  }
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
      u.email.toLowerCase().includes(search.toLowerCase());
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
      if (user) user.is_active = data.is_active;
      updateStats();
      showToast(data.is_active ? '✅ User activated' : '⏸️ User deactivated', 'success');
    } else {
      checkbox.checked = !checkbox.checked;
      showToast('❌ Failed to update', 'error');
    }
  } catch (e) {
    checkbox.checked = !checkbox.checked;
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
function renderPagination() {
  const total = Math.ceil(filteredUsers.length / LIMIT);
  const el = document.getElementById('pagination');
  if (total <= 1) { el.innerHTML = ''; return; }
  let html = '';
  for (let i = 1; i <= total; i++) {
    html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
  }
  el.innerHTML = html;
}

function goToPage(page) {
  currentPage = page;
  renderTable();
  window.scrollTo(0, 0);
}

// ── Helpers ───────────────────────────────────────────
function closeModal(id) { document.getElementById(id).style.display = 'none'; }

function formatDate(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('en', { year: 'numeric', month: 'short', day: 'numeric' });
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function showTableLoading() {
  document.getElementById('users-tbody').innerHTML = `<tr><td colspan="8" style="text-align:center;color:#888;padding:40px">Loading...</td></tr>`;
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
      const dateFormatted = p.date ? new Date(p.date).toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
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
  const el = document.getElementById('payments-pagination');
  if (total <= 1) { el.innerHTML = ''; return; }
  let html = '';
  for (let i = 1; i <= total; i++) {
    html += `<button class="page-btn ${i === current ? 'active' : ''}" onclick="goToPayPage(${i})">${i}</button>`;
  }
  el.innerHTML = html;
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
    const total = (data.monthly || 0) + (data.yearly || 0) + (data.none || 0);

    if (chartSubs) chartSubs.destroy();
    const ctx = document.getElementById('chart-subs').getContext('2d');
    chartSubs = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Monthly', 'Yearly', 'None'],
        datasets: [{
          data: [data.monthly || 0, data.yearly || 0, data.none || 0],
          backgroundColor: ['#3f8ff9', '#f59e0b', '#333'],
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

function renderMprCards(requests, container) {
  container.innerHTML = '';

  requests.forEach(req => {
    const d = new Date(req.created_at);
    const dateStr = d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    let statusClass = 'pending';
    if (req.status === 'approved') statusClass = 'approved';
    if (req.status === 'rejected') statusClass = 'rejected';

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
          <div class="mpr-phone">${req.phone || 'No phone'}</div>
        </div>
        <div class="mpr-status-badge ${statusClass}">${req.status.toUpperCase()}</div>
      </div>
      
      <div class="mpr-details">
        <div class="mpr-detail-row">
          <span>Amount</span>
          <strong>${req.amount ? req.amount + ' EGP' : '--'}</strong>
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
document.addEventListener('DOMContentLoaded', loadTeamPage);

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
  tbody.innerHTML = coursesCache.map(c => {
    const thumbSrc = c.thumbnail_url ? (c.thumbnail_url.startsWith('/') ? API + c.thumbnail_url : c.thumbnail_url) : '';
    const pdfHref = c.pdf_url ? (c.pdf_url.startsWith('/') ? API + c.pdf_url : c.pdf_url) : '';
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
          ${pdfHref ? '<a href="' + pdfHref + '" target="_blank" style="color:#ef4444;text-decoration:none;"><i class="fa-solid fa-file-pdf"></i> View</a>' : '<span style="color:#555;">No PDF</span>'}
          <button class="btn-action" style="font-size:12px;padding:4px 8px;" onclick="uploadCoursePdf(${c.id})">${c.pdf_url ? 'Replace' : 'Upload'}</button>
          <input type="file" id="course-pdf-upload-${c.id}" accept="application/pdf" style="display:none" onchange="handleCoursePdfSelected(event, ${c.id})">
        </div>
      </td>
      <td>
        <label class="switch">
          <input type="checkbox" ${c.is_published ? 'checked' : ''} onchange="toggleCoursePublish(${c.id}, this)">
          <span class="slider round"></span>
        </label>
      </td>
      <td>
        <button class="btn-action" onclick="showLessonsManager(${c.id}, '${escapeHtml(c.title).replace(/'/g, "\\\\'")}')\" style="margin-right:8px;"><i class="fa-solid fa-list"></i> Lessons</button>
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
  document.getElementById('edit-course-modal').style.display = 'flex';
}

async function submitEditCourse() {
  const id = document.getElementById('edit-course-id').value;
  const data = {
    title: document.getElementById('edit-course-title').value,
    description: document.getElementById('edit-course-desc').value,
    thumbnail_url: document.getElementById('edit-course-thumbnail').value,
    total_lessons: parseInt(document.getElementById('edit-course-total-lessons').value) || 0
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
  tbody.innerHTML = coursesCache.map(c => {
    const thumbSrc = c.thumbnail_url ? (c.thumbnail_url.startsWith('/') ? API + c.thumbnail_url : c.thumbnail_url) : '';
    const pdfHref = c.pdf_url ? (c.pdf_url.startsWith('/') ? API + c.pdf_url : c.pdf_url) : '';
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
          ${pdfHref ? '<a href="' + pdfHref + '" target="_blank" style="color:#ef4444;text-decoration:none;"><i class="fa-solid fa-file-pdf"></i> View</a>' : '<span style="color:#555;">No PDF</span>'}
          <button class="btn-action" style="font-size:12px;padding:4px 8px;" onclick="uploadCoursePdf(${c.id})">${c.pdf_url ? 'Replace' : 'Upload'}</button>
          <input type="file" id="course-pdf-upload-${c.id}" accept="application/pdf" style="display:none" onchange="handleCoursePdfSelected(event, ${c.id})">
        </div>
      </td>
      <td>
        <label class="switch">
          <input type="checkbox" ${c.is_published ? 'checked' : ''} onchange="toggleCoursePublish(${c.id}, this)">
          <span class="slider round"></span>
        </label>
      </td>
      <td>
        <button class="btn-action" onclick="showLessonsManager(${c.id}, '${escapeHtml(c.title).replace(/'/g, "\\\\'")}')\" style="margin-right:8px;"><i class="fa-solid fa-list"></i> Lessons</button>
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
  document.getElementById('edit-course-modal').style.display = 'flex';
}

async function submitEditCourse() {
  const id = document.getElementById('edit-course-id').value;
  const data = {
    title: document.getElementById('edit-course-title').value,
    description: document.getElementById('edit-course-desc').value,
    thumbnail_url: document.getElementById('edit-course-thumbnail').value,
    total_lessons: parseInt(document.getElementById('edit-course-total-lessons').value) || 0
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
  if (uploadPollInterval) { clearInterval(uploadPollInterval); uploadPollInterval = null; }
  loadCoursesTab();
}

async function showLessonsManager(courseId, title) {
  currentCourseId = courseId;
  document.getElementById('courses-list-view').style.display = 'none';
  document.getElementById('lessons-manager-view').style.display = 'block';
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
        <td><strong>${escapeHtml(l.title)}</strong></td>
        <td>${l.duration_minutes} min</td>
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

// -- PDF Upload --
function uploadPdf(lessonId) {
  document.getElementById(`pdf-upload-${lessonId}`).click();
}

async function handlePdfSelected(event, lessonId) {
  const file = event.target.files[0];
  if (!file) return;
  if (file.type !== 'application/pdf') return showToast('Must be a PDF file', 'error');

  showToast('Preparing PDF upload...', 'info');
  try {
    const res = await fetch(API + `/courses/admin/lessons/${lessonId}/pdf`, { method: 'POST', headers });
    if (!res.ok) throw new Error('Failed to get upload URL');
    const data = await res.json();

    showToast('Uploading to R2...', 'info');
    const putRes = await fetch(data.upload_url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/pdf' },
      body: file
    });
    if (!putRes.ok) throw new Error('Upload to R2 failed');

    showToast('Saving PDF link...', 'info');
    const patchRes = await fetch(API + `/courses/admin/lessons/${lessonId}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({ pdf_url: data.public_url })
    });
    if (!patchRes.ok) throw new Error('Failed to save link');

    showToast('PDF uploaded successfully!', 'success');
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
            <button class="project-action-btn delete" onclick="deleteProjectSubmission(${project.id})" title="Delete">
              <i class="fa-solid fa-trash"></i><span>Delete</span>
            </button>
          </div>
        </td>
      </tr>`;
  }).join('');

  if (typeof lucide !== 'undefined') lucide.createIcons();
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

function openAddLessonModal() {
  document.getElementById('lesson-title').value = '';
  document.getElementById('lesson-section').value = '';
  document.getElementById('lesson-order').value = lessonsCache.length + 1;
  document.getElementById('lesson-video-url').value = '';

  document.getElementById('addLessonSubmitBtn').disabled = false;
  document.getElementById('add-lesson-modal').style.display = 'flex';
}

// Dropzone logic removed

async function submitAddLesson() {
  const title = document.getElementById('lesson-title').value;
  const section = document.getElementById('lesson-section').value;
  const order = parseInt(document.getElementById('lesson-order').value) || 0;
  let videoUrl = document.getElementById('lesson-video-url').value.trim();

  if (!title) return showToast('Title is required', 'error');
  if (!videoUrl) return showToast('Video URL is required', 'error');

  const srcMatch = videoUrl.match(/src="([^"]+)"/);
  if (srcMatch) videoUrl = srcMatch[1];

  const bunnyPatterns = ['mediadelivery.net', 'b-cdn.net'];
  if (!bunnyPatterns.some(p => videoUrl.includes(p))) {
    return showToast('Link must be from Bunny.net', 'error');
  }

  const btn = document.getElementById('addLessonSubmitBtn');
  btn.disabled = true;
  btn.textContent = 'Creating...';

  try {
    const res = await fetch(API + `/courses/admin/${currentCourseId}/lessons`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        title, section_title: section, order, bunny_video_url: videoUrl
      })
    });

    if (!res.ok) throw new Error('Failed to create lesson');

    closeModal('add-lesson-modal');
    showToast('Lesson created successfully!', 'success');
    loadLessons();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Create Lesson';
  }
}

function openEditLessonModal(id) {
  const l = lessonsCache.find(x => x.id === id);
  if (!l) return;
  document.getElementById('edit-lesson-id').value = l.id;
  document.getElementById('edit-lesson-title').value = l.title;
  document.getElementById('edit-lesson-section').value = l.section_title || '';
  document.getElementById('edit-lesson-status').value = l.video_status || 'pending';
  document.getElementById('edit-lesson-video-url').value = l.bunny_video_url || '';
  document.getElementById('edit-lesson-order').value = l.order || 0;
  document.getElementById('edit-lesson-modal').style.display = 'flex';
}

async function submitEditLesson() {
  const id = document.getElementById('edit-lesson-id').value;
  let videoUrl = document.getElementById('edit-lesson-video-url').value.trim();
  const srcMatch = videoUrl.match(/src="([^"]+)"/);
  if (srcMatch) videoUrl = srcMatch[1];

  let status = document.getElementById('edit-lesson-status').value;
  // Auto update status based on URL if not explicitly changed or if it makes sense
  if (videoUrl && status === 'pending' && !lessonsCache.find(x => x.id == id)?.bunny_video_url) {
    status = 'ready';
  } else if (!videoUrl) {
    status = 'pending';
  }

  try {
    const res = await fetch(API + `/courses/admin/lessons/${id}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify({
        title: document.getElementById('edit-lesson-title').value,
        section_title: document.getElementById('edit-lesson-section').value,
        video_status: status,
        bunny_video_url: videoUrl,
        order: parseInt(document.getElementById('edit-lesson-order').value) || 0
      })
    });
    if (!res.ok) throw new Error('Update failed');
    closeModal('edit-lesson-modal');
    showToast('Lesson updated', 'success');
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
