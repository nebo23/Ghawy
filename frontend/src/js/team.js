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
    'pending-requests': 'Pending Requests'
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
      setTxt('sidebarBadge', u.badge || 'Member');
      setTxt('topbarName', u.full_name);
      setTxt('streakCount', u.streak_days || 0);
      ['sidebarAvatar', 'topbarAvatar'].forEach(id => {
        const el = document.getElementById(id);
        if (el && u.avatar_url) {
          const fullUrl = u.avatar_url.startsWith('http') ? u.avatar_url : API + u.avatar_url;
          el.innerHTML = `<img src="${fullUrl}" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:50%;"/>`;
        }
      });
    }
  } catch (e) {}
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
          <div class="charge-date">${nextDate.toLocaleDateString('en', {month:'short', day:'numeric', year:'numeric'})}</div>
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
            <div class="member-badge">${user.badge || 'Member'}</div>
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
  } catch(e) {}
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
  } catch(e) {
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

function showToast(message, type) {
  const toast = document.createElement('div');
  toast.className = `toast ${type || 'success'}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('en', { year: 'numeric', month: 'short', day: 'numeric' });
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
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
  } catch(e) {}
}

async function loadPayments() {
  const tbody = document.getElementById('payments-tbody');
  // Skeleton
  tbody.innerHTML = Array.from({length: 3}, () => `
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
      const dateFormatted = p.date ? new Date(p.date).toLocaleDateString('en', { month:'short', day:'numeric', year:'numeric', hour:'2-digit', minute:'2-digit' }) : '—';
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
        <td style="color:#fff;font-weight:600;">EGP ${Number(p.amount || 0).toLocaleString()}</td>
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
  } catch(e) {
    showToast('❌ Failed to load payments', 'error');
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
  } catch(e) {
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
  } catch(e) {
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
    a.download = `ghawy_payments_${new Date().toISOString().slice(0,10)}.csv`;
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
  } catch(e) {}
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
  } catch(e) {}
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
  } catch(e) {}
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
  } catch(e) {}
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
  } catch (e) {}
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
    const dateStr = d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    
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
      showToast("Request approved! Email sent to user.", "success");
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
