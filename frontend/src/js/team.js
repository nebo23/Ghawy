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

// ── Load ────────────────────────────────────────────
async function loadTeamPage() {
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
