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
// الصلاحيات اللي الـ owner فاتحها للأدمن ده (جاية من /profile/me). الـ owner
// بيرجع بكل المفاتيح، فمفيش حالة خاصة ليه في أي فحص هنا.
let currentUserPerms = [];
function hasPerm(key) { return currentUserIsOwner || currentUserPerms.includes(key); }
window.hasPerm = hasPerm;

// ═══ TAB SWITCHING ═══
let paymentsLoaded = false;
let analyticsLoaded = false;
let studentsProgressLoaded = false;
let emailsLoaded = false;

function initTabs() {
  const tabs = document.querySelectorAll('.team-section-btn');
  const panels = document.querySelectorAll('.tab-panel');
  const breadcrumb = document.getElementById('page-breadcrumb');
  const heading = document.getElementById('page-heading');

  const titleMap = {
    'users': 'Team Dashboard',
    'students-progress': 'Students Progress',
    'payments': 'Payments & Subscriptions',
    'analytics': 'Platform Analytics',
    'pending-requests': 'Pending Requests',
    'coupons': 'Discount Coupons',
    'live-sessions': 'Live Sessions',
    'guest-of-honors': 'Guest of Honors',
    'courses': 'Courses Management',
    'projects': 'Projects Review',
    'reports': 'Daily Reports',
    'feedbacks': 'Community Feedbacks',
    'emails': 'Email Campaigns',
    'permissions': 'Staff Permissions'
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
      if (target === 'students-progress' && !studentsProgressLoaded) {
        loadStudentsProgressTab();
        studentsProgressLoaded = true;
      }
      if (target === 'analytics' && !analyticsLoaded) {
        loadAnalyticsTab();
        analyticsLoaded = true;
      }
      if (target === 'pending-requests') {
        mprCurrentPage = 1;
        loadPendingRequestsTab();
        loadBirthdayClaims();
      }
      if (target === 'coupons') {
        // Reloaded on every visit rather than cached: the whole point of the
        // panel is the remaining count, and a stale one is worse than a
        // second's wait.
        loadCouponsTab();
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
      if (target === 'permissions') {
        loadPermissionsTab();
      }
      if (target === 'emails') {
        // دايماً افتح على قائمة الحملات كصفحة أولى (حتى لو رجعنا للتاب بعد ما كنا في المنشئ)
        if (!emailsLoaded) { loadEmailsTab(); emailsLoaded = true; }
        else { ecShowListView(); loadEmailsList(); }
      }
    });
  });

  // 🔒 Show only the tabs this staff member is allowed to see.
  // Runs after /profile/me lands, from loadTeamPage(). The permission keys are
  // the data-tab values themselves, so the list needs no translation table —
  // and hiding a button is the convenience, not the lock: every tab here is
  // enforced again server-side.
  function applyTabVisibility() {
    document.querySelectorAll('.team-section-btn').forEach(btn => {
      const tabId = btn.dataset.tab;
      // Permissions is where the owner hands the other tabs out — owner-only by
      // definition, and never one of the keys an owner can grant away.
      const allowed = tabId === 'permissions' ? currentUserIsOwner : hasPerm(tabId);
      btn.style.display = allowed ? '' : 'none';
    });

    // If the active tab is now hidden, switch to the first visible one so the
    // page isn't blank.
    const activeBtn = document.querySelector('.team-section-btn.active');
    const firstVisible = Array.from(document.querySelectorAll('.team-section-btn'))
      .find(b => b.style.display !== 'none');
    if (!activeBtn || activeBtn.style.display === 'none') {
      if (firstVisible) firstVisible.click();
    }

    // An admin the owner closed everything on: say so, rather than leaving them
    // staring at an empty page wondering what broke.
    if (!firstVisible) {
      document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
      const area = document.querySelector('.team-content-area');
      if (area && !document.getElementById('perm-no-access')) {
        const msg = document.createElement('div');
        msg.id = 'perm-no-access';
        msg.className = 'perm-empty';
        msg.textContent = 'مالكش صلاحية على أي قسم في لوحة الفريق. كلّم الـ owner لو المفروض تشوف حاجة هنا.';
        area.appendChild(msg);
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
      currentUserPerms = Array.isArray(u.permissions) ? u.permissions : [];
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
  // Members is the landing tab, so it loads up front — but only for whoever
  // the owner left it open to; for anyone else this is a guaranteed 403 and an
  // "access required" toast on a page that is behaving correctly.
  // Contact details are redacted server-side without `member-contacts`.
  if (hasPerm('users')) await loadUsers();

  // A restored or autofilled search box shows a name while the table below it
  // is unfiltered — the filters live in JS state that starts empty. Clearing
  // the boxes on load is what keeps the two telling the same story.
  ['search-input', 'sp-search', 'pay-search', 'project-search'].forEach(id => {
    const box = document.getElementById(id);
    if (box) box.value = '';
  });

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

  // Only whoever can open Pending Requests fetches its badge counts — for
  // anyone else these would just be two guaranteed 403s on every page load.
  if (hasPerm('pending-requests')) {
    loadManualPaymentStats(); // fetch badge count
    loadBirthdayClaims();     // birthday gift claims count into the same badge
  }
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
    updateStats();
    updateExpiringCount();
    applyAllFilters();
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
          <img src="${safeAvatarUrl(user.avatar_url) || './imgs/ghawi-logo.png'}" class="member-avatar" onerror="this.src='./imgs/ghawi-logo.png'"/>
          <div>
            <div class="member-name">${escapeHtml(user.full_name)}</div>
            <div class="member-badge">${escapeHtml(getRoleLabel(user))}</div>
            <div class="member-id" style="font-size:11px;color:#888;font-weight:600;margin-top:2px;">🆔 ID: ${user.id}</div>
            ${isUnpaidActive(user) ? '<span class="np-tag" title="Active without a recorded payment — غير دافع">Not paid</span>' : ''}
          </div>
        </div>
      </td>
      <td class="text-secondary">${hasPerm('member-contacts') ? escapeHtml(user.email || '—') : '<span style="color:#666" title="مالكش صلاحية بيانات التواصل">🔒</span>'}</td>
      <td class="text-secondary">${hasPerm('member-contacts') ? (user.phone || '—') : '<span style="color:#666" title="مالكش صلاحية بيانات التواصل">🔒</span>'}</td>
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
          ${hasPerm('member-contacts') && user.social_media_url ? `
          <a href="${window.safeExternalUrl(user.social_media_url)}" target="_blank" rel="noopener noreferrer"
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
  setTimeout(() => { if (typeof lucide !== 'undefined') window.lucide && window.lucide.createIcons(); }, 10);
}

// ── Search, Filter & Sort ─────────────────────────────
// All filters combine with AND logic; sorting keeps registration order accurate
// and uses paid-status only as a tie-breaker (a not-actually-paid member never
// outranks a paying one when the primary sort key is equal).
const EXPIRING_SOON_DAYS = 7;

const filterState = {
  search: '',
  status: 'all',        // all | active | inactive
  package: 'all',       // all | monthly | quarterly | yearly | legacy | none
  sort: 'reg_new',      // reg_new | reg_old | exp_near | exp_far | bday_near | age_old | age_young
  dateRange: 'all',     // 24h | 7d | 14d | 30d | 60d | 90d | all | custom
  customFrom: null,
  customTo: null,
  expiringSoon: false,
};

// Map a member's latest confirmed plan_key (+ legacy source) to a package bucket.
function packageBucket(u) {
  const pk = (u.plan_key || '').toLowerCase();
  if (pk.startsWith('monthly')) return 'monthly';
  if (pk.startsWith('quarterly')) return 'quarterly';
  if (pk.startsWith('yearly')) return 'yearly';
  if (u.subscription_source === 'legacy_promo') return 'legacy';
  return 'none';
}

// Whole-day difference from now to a UTC timestamp (negative = already passed).
function daysUntil(dateStr) {
  if (!dateStr) return null;
  const d = toEgyptDate(dateStr);
  if (isNaN(d)) return null;
  return Math.floor((d.getTime() - Date.now()) / 86400000);
}

function isExpiringSoon(u) {
  const dd = daysUntil(u.end_at);
  return dd !== null && dd >= 0 && dd <= EXPIRING_SOON_DAYS;
}

// Active member with neither a confirmed payment nor a subscription source —
// i.e. activated manually by an admin, not an actual paying/legacy subscriber.
function isUnpaidActive(u) {
  return !!u.is_active && !u.has_paid && !u.subscription_source;
}

// Days until the member's next birthday (same month/day next occurrence).
function daysToBirthday(dateStr) {
  if (!dateStr) return Infinity;
  const d = new Date(dateStr + 'T00:00:00');
  if (isNaN(d)) return Infinity;
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  let next = new Date(now.getFullYear(), d.getMonth(), d.getDate());
  if (next < today) next = new Date(now.getFullYear() + 1, d.getMonth(), d.getDate());
  return Math.round((next - today) / 86400000);
}

function withinDateRange(u) {
  if (filterState.dateRange === 'all') return true;
  const created = u.created_at ? toEgyptDate(u.created_at) : null;
  if (!created || isNaN(created)) return false;
  if (filterState.dateRange === 'custom') {
    if (filterState.customFrom) {
      const f = new Date(filterState.customFrom + 'T00:00:00');
      if (created < f) return false;
    }
    if (filterState.customTo) {
      const t = new Date(filterState.customTo + 'T23:59:59');
      if (created > t) return false;
    }
    return true;
  }
  const days = { '24h': 1, '7d': 7, '14d': 14, '30d': 30, '60d': 60, '90d': 90 }[filterState.dateRange];
  if (!days) return true;
  return created.getTime() >= Date.now() - days * 86400000;
}

function ts(dateStr) {
  if (!dateStr) return null;
  const d = toEgyptDate(dateStr);
  return isNaN(d) ? null : d.getTime();
}
function birthTs(dateStr) {
  if (!dateStr) return null;
  const d = new Date(dateStr + 'T00:00:00');
  return isNaN(d) ? null : d.getTime();
}

function sortUsers(arr) {
  const paidRank = u => (u.has_paid ? 1 : 0);
  // Ascending with nulls always last.
  const ascNullsLast = (a, b) => {
    if (a === null && b === null) return 0;
    if (a === null) return 1;
    if (b === null) return -1;
    return a - b;
  };
  let cmp;
  switch (filterState.sort) {
    case 'reg_old':
      cmp = (a, b) => ascNullsLast(ts(a.created_at), ts(b.created_at)); break;
    case 'exp_near':
      cmp = (a, b) => ascNullsLast(ts(a.end_at), ts(b.end_at)); break;
    case 'exp_far':
      cmp = (a, b) => ascNullsLast(ts(b.end_at), ts(a.end_at)); break;
    case 'bday_near':
      cmp = (a, b) => daysToBirthday(a.birth_date) - daysToBirthday(b.birth_date); break;
    case 'age_old':   // oldest = earliest birth date first
      cmp = (a, b) => ascNullsLast(birthTs(a.birth_date), birthTs(b.birth_date)); break;
    case 'age_young': // youngest = latest birth date first
      cmp = (a, b) => ascNullsLast(birthTs(b.birth_date), birthTs(a.birth_date)); break;
    case 'reg_new':
    default:
      cmp = (a, b) => ascNullsLast(ts(b.created_at), ts(a.created_at)); break;
  }
  return arr.sort((a, b) => {
    const primary = cmp(a, b);
    if (primary !== 0) return primary;
    return paidRank(b) - paidRank(a); // tie-breaker: paid first
  });
}

let searchTimeout;
function handleSearch(val) {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    filterState.search = val;
    applyAllFilters();
  }, 300);
}

function handleFilter(status) {
  filterState.status = status;
  applyAllFilters();
}

function setPackageFilter(pkg) {
  filterState.package = pkg;
  applyAllFilters();
}

function setSortFilter(sort) {
  filterState.sort = sort;
  applyAllFilters();
}

function setDateRange(range) {
  filterState.dateRange = range;
  if (range !== 'custom') {
    filterState.customFrom = null;
    filterState.customTo = null;
    const df = document.getElementById('date-from'); if (df) df.value = '';
    const dt = document.getElementById('date-to'); if (dt) dt.value = '';
  }
  document.querySelectorAll('#team-quickdates .qd-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.range === range));
  applyAllFilters();
}

function applyCustomRange() {
  const from = document.getElementById('date-from').value || null;
  const to = document.getElementById('date-to').value || null;
  if (!from && !to) { setDateRange('all'); return; }
  filterState.dateRange = 'custom';
  filterState.customFrom = from;
  filterState.customTo = to;
  document.querySelectorAll('#team-quickdates .qd-btn').forEach(b => b.classList.remove('active'));
  applyAllFilters();
}

function toggleExpiringSoon() {
  filterState.expiringSoon = !filterState.expiringSoon;
  const btn = document.getElementById('expiring-toggle');
  if (btn) btn.classList.toggle('active', filterState.expiringSoon);
  applyAllFilters();
}

function updateExpiringCount() {
  const el = document.getElementById('expiring-count');
  if (el) el.textContent = allUsers.filter(isExpiringSoon).length;
}

function applyAllFilters() {
  const search = (filterState.search || '').toLowerCase();

  // Typing an ID has to land on that one member. Left as a plain substring
  // match it never would: every phone number holding those digits comes back
  // too, and "65" buries member 65 under a page of 010…65… numbers. So an
  // exact ID hit takes over the search, and everything else falls back to the
  // substring behaviour. Members read their ID off their settings page, where
  // it now sits with a copy button; "#65" works as well as "65".
  const idQuery = search.replace(/^#/, '');
  const exactId = /^[0-9]{1,7}$/.test(idQuery)
    ? allUsers.find(u => String(u.id) === idQuery)
    : null;

  const matched = allUsers.filter(u => {
    const matchSearch = !search || (exactId
      ? u.id === exactId.id
      : (u.full_name && u.full_name.toLowerCase().includes(search)) ||
        (u.email && u.email.toLowerCase().includes(search)) ||
        (u.phone && u.phone.toLowerCase().includes(search)));
    const matchStatus = filterState.status === 'all' ||
      (filterState.status === 'active' && u.is_active) ||
      (filterState.status === 'inactive' && !u.is_active);
    const matchPackage = filterState.package === 'all' || packageBucket(u) === filterState.package;
    const matchExpiring = !filterState.expiringSoon || isExpiringSoon(u);
    const matchDate = withinDateRange(u);
    return matchSearch && matchStatus && matchPackage && matchExpiring && matchDate;
  });
  filteredUsers = sortUsers(matched);
  currentPage = 1;
  renderTable();
}

// Back-compat: some callers still invoke applyFilters directly.
function applyFilters() { applyAllFilters(); }

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
    if (typeof lucide !== 'undefined') window.lucide && window.lucide.createIcons();
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

// What the rail is CALLED on screen. The API stopped saying "manual" — that
// was two different wallets under one word, and an admin looking at a row
// still had to open the request to find out which account to check. Anything
// unrecognised falls back to InstaPay, which is what every manual payment
// filed before Vodafone Cash existed was.
const RAIL_LABELS = {
  kashier: 'Kashier',
  instapay: 'InstaPay',
  vodafone_cash: 'Vodafone Cash',
};

function railLabel(rail) {
  return RAIL_LABELS[rail] || RAIL_LABELS.instapay;
}

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
      setTimeout(() => { if (typeof lucide !== 'undefined') window.lucide && window.lucide.createIcons(); }, 10);
      return;
    }

    tbody.innerHTML = data.payments.map(p => {
      const dateFormatted = formatDateTime(p.date);
      const statusClass = p.status || 'pending';
      const statusLabel = (p.status || 'pending').charAt(0).toUpperCase() + (p.status || 'pending').slice(1);
      const methodLabel = railLabel(p.method);
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
    setTimeout(() => { if (typeof lucide !== 'undefined') window.lucide && window.lucide.createIcons(); }, 10);
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

  const showContact = hasPerm('member-contacts');
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
//  STUDENTS PROGRESS TAB
// ══════════════════════════════════════════════════════════

let spData = null;          // full API response
let spFiltered = [];        // students after search/filter/sort
let spPage = 1;
const SP_LIMIT = 20;
let spExpanded = new Set(); // expanded student rows
let spListenersBound = false;

async function loadStudentsProgressTab() {
  const tbody = document.getElementById('sp-tbody');
  if (tbody) tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:#888;padding:40px">Loading...</td></tr>`;
  try {
    const res = await fetch(`${API}/admin/students-progress`, { headers });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    spData = await res.json();
  } catch (e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:#ef4444;padding:40px">Failed to load students progress — try Refresh</td></tr>`;
    return;
  }

  // Course filter options (published courses first, then unpublished marked)
  const sel = document.getElementById('sp-course-filter');
  if (sel) {
    const prev = sel.value;
    sel.innerHTML = '<option value="all">All Courses</option>' +
      spData.courses.filter(c => c.total_lessons > 0).map(c =>
        `<option value="${c.id}">${escapeHtml(c.title)}${c.is_published ? '' : ' (unpublished)'}</option>`
      ).join('');
    if ([...sel.options].some(o => o.value === prev)) sel.value = prev;
  }

  if (!spListenersBound) {
    spListenersBound = true;
    let t;
    document.getElementById('sp-search')?.addEventListener('input', () => {
      clearTimeout(t); t = setTimeout(() => { spPage = 1; applySpFilters(); }, 300);
    });
    ['sp-course-filter', 'sp-status-filter', 'sp-sort'].forEach(id => {
      document.getElementById(id)?.addEventListener('change', () => { spPage = 1; applySpFilters(); });
    });
  }

  spPage = 1;
  spExpanded = new Set();
  applySpFilters();
}

function reloadStudentsProgress() {
  studentsProgressLoaded = true;
  loadStudentsProgressTab();
}

// Progress numbers for a student in the currently-selected scope
// (overall, or one course when the course filter is set).
function spScopeOf(s, courseId) {
  if (courseId === 'all') {
    return { percent: s.overall_percent, done: s.overall_completed, total: s.overall_total, started: s.courses_started > 0 };
  }
  const c = (s.courses || []).find(x => x.course_id === Number(courseId));
  if (c) return { percent: c.percent, done: c.completed_lessons, total: c.total_lessons, started: true };
  const meta = (spData.courses || []).find(x => x.id === Number(courseId));
  return { percent: 0, done: 0, total: meta ? meta.total_lessons : 0, started: false };
}

function applySpFilters() {
  if (!spData) return;
  const search = (document.getElementById('sp-search')?.value || '').trim().toLowerCase();
  const courseId = document.getElementById('sp-course-filter')?.value || 'all';
  const status = document.getElementById('sp-status-filter')?.value || 'started';
  const sort = document.getElementById('sp-sort')?.value || 'progress-desc';

  spFiltered = spData.students.filter(s => {
    if (search && !s.full_name.toLowerCase().includes(search) && String(s.id) !== search) return false;
    const scope = spScopeOf(s, courseId);
    if (status === 'started' && !scope.started) return false;
    if (status === 'not-started' && scope.started) return false;
    if (status === 'completed') {
      if (courseId === 'all' ? s.courses_completed === 0 : scope.percent < 100) return false;
    }
    return true;
  });

  spFiltered.sort((a, b) => {
    const pa = spScopeOf(a, courseId), pb = spScopeOf(b, courseId);
    if (sort === 'progress-desc') return pb.percent - pa.percent || pb.done - pa.done;
    if (sort === 'progress-asc') return pa.percent - pb.percent || pa.done - pb.done;
    if (sort === 'recent') return new Date(b.last_activity || 0) - new Date(a.last_activity || 0);
    return a.full_name.localeCompare(b.full_name);
  });

  // Header label follows the selected scope
  const th = document.getElementById('sp-progress-th');
  if (th) {
    const meta = courseId === 'all' ? null : (spData.courses || []).find(c => c.id === Number(courseId));
    th.textContent = meta ? `Progress — ${meta.title}` : 'Overall Progress';
  }

  renderSpStats();
  renderSpTable();
}

function renderSpStats() {
  const students = spData.students;
  const learners = students.filter(s => s.courses_started > 0);
  const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
  const active7d = learners.filter(s => s.last_activity && new Date(s.last_activity + 'Z').getTime() >= weekAgo).length;
  const avg = learners.length ? Math.round(learners.reduce((sum, s) => sum + s.overall_percent, 0) / learners.length) : 0;
  const completions = students.reduce((sum, s) => sum + s.courses_completed, 0);

  const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  set('sp-stat-students', learners.length);
  set('sp-stat-active7d', active7d);
  set('sp-stat-avg', avg + '%');
  set('sp-stat-completions', completions);
}

function spBarColor(p) {
  return p >= 100 ? '#22c55e' : p >= 60 ? '#3f8ff9' : p >= 25 ? '#f59e0b' : '#ef4444';
}

function spProgressBar(percent, done, total) {
  const p = Math.max(0, Math.min(100, percent || 0));
  return `
    <div class="sp-bar-wrap">
      <div class="sp-bar-top"><span class="sp-bar-pct" style="color:${spBarColor(p)}">${p}%</span>
        <span class="sp-bar-count">${done} / ${total} lessons</span></div>
      <div class="sp-bar"><div class="sp-bar-fill" style="width:${p}%;background:${spBarColor(p)}"></div></div>
    </div>`;
}

function renderSpTable() {
  const tbody = document.getElementById('sp-tbody');
  if (!tbody) return;
  const courseId = document.getElementById('sp-course-filter')?.value || 'all';

  if (!spFiltered.length) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:#888;padding:40px">No students match the current filters</td></tr>`;
    document.getElementById('sp-pagination').innerHTML = '';
    return;
  }

  const start = (spPage - 1) * SP_LIMIT;
  const rows = spFiltered.slice(start, start + SP_LIMIT);

  tbody.innerHTML = rows.map(s => {
    const scope = spScopeOf(s, courseId);
    const role = s.is_owner ? '<span class="role-badge owner" style="font-size:10px;padding:1px 6px;">Owner</span>'
      : s.is_admin ? '<span class="role-badge admin" style="font-size:10px;padding:1px 6px;">Admin</span>' : '';
    const expanded = spExpanded.has(s.id);
    const main = `
    <tr class="sp-row ${expanded ? 'sp-row-open' : ''}" onclick="toggleSpDetail(${s.id})" style="cursor:pointer">
      <td>
        <div class="member-cell">
          <img src="${safeAvatarUrl(s.avatar_url) || './imgs/ghawi-logo.png'}" class="member-avatar" onerror="this.src='./imgs/ghawi-logo.png'"/>
          <div>
            <div class="member-name">${escapeHtml(s.full_name)} ${role}</div>
            <div class="member-id" style="font-size:11px;color:#888;font-weight:600;">🆔 ID: ${s.id} ${s.is_active ? '' : '· <span style="color:#ef4444">inactive</span>'}</div>
          </div>
        </div>
      </td>
      <td>${spProgressBar(scope.percent, scope.done, scope.total)}</td>
      <td class="text-secondary">${s.courses_started} started${s.courses_completed ? ` · <span style="color:#22c55e">${s.courses_completed} done</span>` : ''}</td>
      <td class="text-secondary">${s.overall_completed} / ${s.overall_total}</td>
      <td class="text-secondary">${s.exams_passed || '—'}</td>
      <td class="text-secondary">${s.certificates ? `🏆 ${s.certificates}` : '—'}</td>
      <td class="text-secondary" style="white-space:nowrap">${s.last_activity ? formatDateTime(s.last_activity) : '<span style="color:#666">never</span>'}</td>
      <td style="text-align:center"><i data-lucide="${expanded ? 'chevron-up' : 'chevron-down'}" style="width:16px;height:16px;stroke:#888"></i></td>
    </tr>`;
    return main + (expanded ? spDetailRow(s) : '');
  }).join('');

  renderSpPagination();
  setTimeout(() => { if (typeof lucide !== 'undefined') window.lucide && window.lucide.createIcons(); }, 10);
}

function spDetailRow(s) {
  if (!s.courses.length) {
    return `<tr class="sp-detail-row"><td colspan="8"><div style="padding:16px;color:#888;text-align:center">This member hasn't started any course yet.</div></td></tr>`;
  }
  const cards = s.courses.map(c => `
    <div class="sp-course-card">
      <div class="sp-course-head">
        <div class="sp-course-title">${escapeHtml(c.title)}${c.is_published ? '' : ' <span style="color:#f59e0b;font-size:10px">(unpublished)</span>'}</div>
        ${c.has_certificate ? '<span class="sp-cert-badge" title="Certificate earned">🏆 Certified</span>' : ''}
      </div>
      ${spProgressBar(c.percent, c.completed_lessons, c.total_lessons)}
      <div class="sp-course-meta">
        <span title="Last activity in this course">🕐 ${c.last_activity ? formatDateTime(c.last_activity) : 'never'}</span>
        ${c.exams_total ? `<span title="Exams passed">📝 ${c.exams_passed}/${c.exams_total} exams${c.best_exam_score != null ? ` · best ${c.best_exam_score}%` : ''}</span>` : ''}
        <button class="sp-lessons-btn" onclick="event.stopPropagation(); openSpLessons(${s.id}, ${c.course_id}, '${escapeHtml(s.full_name).replace(/'/g, "\\'")}')">
          View Lessons
        </button>
      </div>
    </div>`).join('');
  return `<tr class="sp-detail-row"><td colspan="8"><div class="sp-detail-grid">${cards}</div></td></tr>`;
}

function toggleSpDetail(userId) {
  if (spExpanded.has(userId)) spExpanded.delete(userId); else spExpanded.add(userId);
  renderSpTable();
}

function renderSpPagination() {
  const el = document.getElementById('sp-pagination');
  if (!el) return;
  const pages = Math.max(1, Math.ceil(spFiltered.length / SP_LIMIT));
  if (pages <= 1) { el.innerHTML = ''; return; }
  let html = `<button class="page-btn" ${spPage === 1 ? 'disabled' : ''} onclick="spGoPage(${spPage - 1})">‹</button>`;
  for (let i = 1; i <= pages; i++) {
    if (i === 1 || i === pages || Math.abs(i - spPage) <= 2) {
      html += `<button class="page-btn ${i === spPage ? 'active' : ''}" onclick="spGoPage(${i})">${i}</button>`;
    } else if (Math.abs(i - spPage) === 3) {
      html += `<span style="color:#666;padding:0 4px">…</span>`;
    }
  }
  html += `<button class="page-btn" ${spPage === pages ? 'disabled' : ''} onclick="spGoPage(${spPage + 1})">›</button>`;
  el.innerHTML = html;
}

function spGoPage(p) {
  spPage = p;
  renderSpTable();
}

async function openSpLessons(userId, courseId, studentName) {
  const body = document.getElementById('sp-lessons-body');
  const title = document.getElementById('sp-lessons-title');
  if (title) title.textContent = `📚 ${studentName || 'Student'} — Lessons`;
  if (body) body.innerHTML = '<div style="text-align:center;color:#888;padding:30px">Loading...</div>';
  openModal('sp-lessons-modal');
  try {
    const res = await fetch(`${API}/admin/students-progress/${userId}/courses/${courseId}/lessons`, { headers });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const d = await res.json();
    if (title) title.textContent = `📚 ${d.student.full_name} — ${d.course.title}`;
    if (!d.lessons.length) {
      body.innerHTML = '<div style="text-align:center;color:#888;padding:30px">This course has no lessons yet.</div>';
      return;
    }
    const doneCount = d.lessons.filter(l => l.completed).length;
    let lastSection = null;
    let html = `<div style="color:#888;font-size:13px;margin-bottom:12px">${doneCount} of ${d.lessons.length} lessons completed</div>`;
    d.lessons.forEach(l => {
      if (l.section_title && l.section_title !== lastSection) {
        lastSection = l.section_title;
        html += `<div class="sp-lesson-section">${escapeHtml(l.section_title)}</div>`;
      }
      html += `
        <div class="sp-lesson-row ${l.completed ? 'done' : ''}">
          <span class="sp-lesson-check">${l.completed ? '✅' : '⭕'}</span>
          <span class="sp-lesson-title">${escapeHtml(l.title)}</span>
          <span class="sp-lesson-when">${l.completed ? formatDateTime(l.completed_at) : (l.video_status !== 'ready' ? '<span style="color:#f59e0b">not ready</span>' : '')}</span>
        </div>`;
    });
    body.innerHTML = html;
  } catch (e) {
    if (body) body.innerHTML = '<div style="text-align:center;color:#ef4444;padding:30px">Failed to load lessons</div>';
  }
}

function exportStudentsProgressCSV() {
  if (!spData || !spFiltered.length) { showToast('No students to export', 'error'); return; }

  const cell = (v) => {
    const s = (v === null || v === undefined) ? '' : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const publishedCourses = spData.courses.filter(c => c.is_published && c.total_lessons > 0);
  const headers = ['ID', 'Name', 'Overall %', 'Lessons Done', 'Lessons Total', 'Courses Started',
    'Courses Completed', 'Exams Passed', 'Certificates', 'Last Activity',
    ...publishedCourses.map(c => `${c.title} %`)];

  const lines = [headers.map(cell).join(',')];
  spFiltered.forEach(s => {
    const perCourse = publishedCourses.map(pc => {
      const c = (s.courses || []).find(x => x.course_id === pc.id);
      return c ? c.percent : 0;
    });
    lines.push([s.id, s.full_name, s.overall_percent, s.overall_completed, s.overall_total,
      s.courses_started, s.courses_completed, s.exams_passed, s.certificates,
      s.last_activity ? new Date(s.last_activity + 'Z').toISOString() : '',
      ...perCourse].map(cell).join(','));
  });

  const blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = `ghawy_students_progress_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(blobUrl);
  showToast('⬇ CSV exported', 'success');
}


// ══════════════════════════════════════════════════════════
//  ANALYTICS TAB
// ══════════════════════════════════════════════════════════

let analyticsRange = '30d';
let chartMembers = null;
let chartRevenue = null;
let chartRevenueMonth = null;
let chartSubs = null;
let chartMethods = null;

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
    loadMonthlyRevenue(),
    loadSubsChart(),
    loadMethodsChart()
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


// Revenue by month — one fetch, two readings of it. The chart is for the shape
// (is the line going up, and which rail is carrying it), the table is for the
// exact figure, because nobody can read "162,000" off a bar.
//
// All time, deliberately: it ignores the range buttons above, since a month
// chart clipped to 30 days has nothing left to compare against.
async function loadMonthlyRevenue() {
  try {
    const res = await fetch(`${API}/admin/analytics/revenue-by-month`, { headers });
    if (!res.ok) return;
    const data = await res.json();
    const months = data.months || [];

    renderMonthlyChart(months);
    renderMonthlyTable(months, data);
  } catch (e) { }
}

const MONEY = n => Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });

// "August 2026" → "Aug 26", so twelve months still fit on one axis.
function shortMonth(month) {
  const [year, index] = month.split('-');
  const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${names[Number(index) - 1]} ${year.slice(2)}`;
}

function renderMonthlyChart(months) {
  const canvas = document.getElementById('chart-revenue-month');
  if (!canvas) return;

  const rails = ['kashier', 'instapay', 'vodafone_cash'];
  const colors = { kashier: '#3f8ff9', instapay: '#7c3aed', vodafone_cash: '#ef4444' };
  const total = months.reduce((sum, m) => sum + (m.revenue || 0), 0);

  const label = document.getElementById('revenue-month-label');
  if (label) {
    label.textContent = months.length
      ? `${months.length} month${months.length === 1 ? '' : 's'} · EGP ${MONEY(total)} all time`
      : 'No confirmed payments yet';
  }

  if (chartRevenueMonth) chartRevenueMonth.destroy();
  chartRevenueMonth = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: months.map(m => shortMonth(m.month)),
      datasets: rails.map(rail => ({
        label: railLabel(rail),
        data: months.map(m => (m.rails || {})[rail] || 0),
        backgroundColor: colors[rail],
        borderRadius: 4,
        maxBarThickness: 64,
      }))
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { padding: 16, usePointStyle: true, pointStyleWidth: 10 } },
        tooltip: {
          callbacks: {
            label: item => ` ${item.dataset.label}: EGP ${MONEY(item.parsed.y)}`,
            // The stack hides the one number the month is actually judged on.
            footer(items) {
              const month = months[items[0].dataIndex];
              return `Total: EGP ${MONEY(month.revenue)} · ${month.payments} payment${month.payments === 1 ? '' : 's'}`;
            }
          }
        }
      },
      scales: {
        x: { stacked: true, grid: { display: false } },
        y: { stacked: true, beginAtZero: true, ticks: { callback: v => MONEY(v) } }
      }
    }
  });
  canvas.parentElement.style.height = '300px';
}

function renderMonthlyTable(months, data) {
  const tbody = document.getElementById('monthly-sales-tbody');
  const tfoot = document.getElementById('monthly-sales-tfoot');
  if (!tbody) return;

  if (!months.length) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;color:#888;padding:24px">No confirmed payments yet</td></tr>`;
    if (tfoot) tfoot.innerHTML = '';
    return;
  }

  const currentMonth = months[months.length - 1].month;
  const num = (value, extra = '') =>
    `<td class="${value ? extra : 'm-zero'}">${value ? MONEY(value) : '—'}</td>`;

  tbody.innerHTML = months.map(m => {
    // The running month is compared against months that had all thirty days to
    // earn their number, so it is flagged rather than quietly called a drop.
    const isCurrent = m.month === currentMonth;
    let change = '<td class="m-zero">—</td>';
    if (m.change_pct !== null && m.change_pct !== undefined) {
      const cls = m.change_pct >= 0 ? 'm-up' : 'm-down';
      change = `<td class="${cls}">${m.change_pct >= 0 ? '▲' : '▼'} ${Math.abs(m.change_pct).toFixed(1)}%</td>`;
    }
    const plans = m.plans || {};

    return `
    <tr>
      <td class="m-name">${escapeHtml(m.label)}${isCurrent ? '<span class="m-partial">so far</span>' : ''}</td>
      <td class="m-revenue">${m.revenue ? 'EGP ' + MONEY(m.revenue) : '<span class="m-zero">—</span>'}</td>
      ${change}
      <td title="${m.members} member${m.members === 1 ? '' : 's'} paid this month">${m.payments || '<span class="m-zero">—</span>'}</td>
      ${num(m.new_members)}
      ${num(m.renewals)}
      ${num(plans.monthly)}
      ${num(plans.quarterly)}
      ${num(plans.yearly)}
    </tr>`;
  }).join('');

  if (tfoot) {
    const sum = key => months.reduce((total, m) => total + (m[key] || 0), 0);
    const sumPlan = plan => months.reduce((total, m) => total + ((m.plans || {})[plan] || 0), 0);
    tfoot.innerHTML = `
      <tr>
        <td>All time</td>
        <td class="m-revenue">EGP ${MONEY(data.total)}</td>
        <td></td>
        <td>${sum('payments')}</td>
        <td>${MONEY(sum('new_members'))}</td>
        <td>${MONEY(sum('renewals'))}</td>
        <td>${MONEY(sumPlan('monthly'))}</td>
        <td>${MONEY(sumPlan('quarterly'))}</td>
        <td>${MONEY(sumPlan('yearly'))}</td>
      </tr>`;
  }
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
        labels: ['Monthly (600)', 'Quarterly (1200)', 'Yearly (3500)', 'None'],
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


// How the money came in. Same doughnut as Subscription Types, and deliberately
// so — it is the same question asked of the payment instead of the plan.
//
// It counts payments that WENT THROUGH (the endpoint filters to confirmed), so
// it is not comparable to the raw row count in the Payments tab: most Kashier
// rows there are abandoned checkouts. Neither chart follows the range buttons
// above them; both are all-time.
async function loadMethodsChart() {
  try {
    const res = await fetch(`${API}/admin/analytics/payment-method-breakdown`, { headers });
    if (!res.ok) return;
    const data = await res.json();

    const rails = ['kashier', 'instapay', 'vodafone_cash'];
    const values = rails.map(r => data[r] || 0);
    const total = values.reduce((a, b) => a + b, 0);
    const memberCounts = data.members || {};
    const revenue = data.revenue || {};

    const label = document.getElementById('methods-total-label');
    if (label) {
      label.textContent = total
        ? `${total} completed payment${total === 1 ? '' : 's'} — all time`
        : 'No completed payments yet';
    }

    if (chartMethods) chartMethods.destroy();
    const ctx = document.getElementById('chart-methods').getContext('2d');
    chartMethods = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: rails.map(railLabel),
        datasets: [{
          data: values,
          backgroundColor: ['#3f8ff9', '#7c3aed', '#ef4444'],
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
          },
          tooltip: {
            callbacks: {
              // "40 payments" on its own hides the renewals: the member count
              // is the other half of the answer, and the revenue says which
              // rail is actually carrying the business.
              label(item) {
                const count = values[item.dataIndex];
                const share = total ? Math.round((count / total) * 100) : 0;
                return ` ${count} payment${count === 1 ? '' : 's'} (${share}%)`;
              },
              afterLabel(item) {
                const rail = rails[item.dataIndex];
                const people = memberCounts[rail] || 0;
                const money = Number(revenue[rail] || 0);
                return ` ${people} member${people === 1 ? '' : 's'} · EGP ${money.toLocaleString()}`;
              }
            }
          }
        }
      },
      plugins: [{
        id: 'centerTextMethods',
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

// Pending badge = manual payments + birthday gift claims (both live under the
// Pending Requests tab), so the two loaders feed shared counters.
let mprPendingCount = 0;
let bgcPendingCount = 0;

function renderPendingBadge() {
  const badge = document.getElementById('pending-badge');
  if (!badge) return;
  const total = (mprPendingCount || 0) + (bgcPendingCount || 0);
  if (total > 0) {
    badge.innerText = total;
    badge.style.display = 'inline-flex';
  } else {
    badge.style.display = 'none';
  }
}

async function loadManualPaymentStats() {
  try {
    const res = await authFetch(`${API}/manual-payments/stats`);
    if (res.ok) {
      const data = await res.json();
      mprPendingCount = data.pending_count || 0;
      renderPendingBadge();
    }
  } catch (e) { }
}

// ── Birthday gift claims (7 free days) — approve adds the days + auto-DM ──
async function loadBirthdayClaims() {
  const section = document.getElementById('bgc-section');
  const container = document.getElementById('bgc-cards-container');
  if (!section || !container) return;

  try {
    const res = await authFetch(`${API}/birthday/claims?status=pending`);
    if (!res.ok) throw new Error('Failed to load birthday claims');
    const data = await res.json();

    bgcPendingCount = data.pending_count || 0;
    renderPendingBadge();

    const claims = data.claims || [];
    const label = document.getElementById('bgc-count-label');
    if (label) label.innerText = `(${claims.length})`;

    if (!claims.length) {
      section.style.display = 'none';
      container.innerHTML = '';
      return;
    }

    section.style.display = '';
    container.innerHTML = '';

    claims.forEach(c => {
      // Backend sends naive UTC timestamps — mark as UTC then render in Egypt time.
      const rawTs = c.created_at || '';
      const d = new Date(/Z|[+-]\d{2}:?\d{2}$/.test(rawTs) ? rawTs : rawTs + 'Z');
      const dateStr = isNaN(d) ? '—' : d.toLocaleString('en-GB', {
        timeZone: 'Africa/Cairo',
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
      const bday = c.birth_date
        ? new Date(c.birth_date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
        : '—';
      const rawEnd = c.end_at || '';
      const endD = rawEnd ? new Date(/Z|[+-]\d{2}:?\d{2}$/.test(rawEnd) ? rawEnd : rawEnd + 'Z') : null;
      const endStr = endD && !isNaN(endD)
        ? endD.toLocaleDateString('en-GB', { timeZone: 'Africa/Cairo', day: '2-digit', month: 'short', year: 'numeric' })
        : '—';
      const phoneHtml = c.phone
        ? `<a class="mpr-phone" href="https://wa.me/${toWaMeNumber(c.phone)}" target="_blank" rel="noopener" title="Open WhatsApp">${escapeHtml(c.phone)}</a>`
        : '';

      const card = document.createElement('div');
      card.className = 'mpr-card';
      card.innerHTML = `
        <div class="mpr-card-header">
          <div class="mpr-user-info">
            <div class="mpr-name">${escapeHtml(c.full_name || '')}</div>
            <div class="mpr-email">${escapeHtml(c.email || '')}</div>
            ${phoneHtml}
          </div>
          <div class="mpr-status-badge pending">🎂 BIRTHDAY</div>
        </div>

        <div class="mpr-details">
          <div class="mpr-detail-row"><span>Gift</span><strong>+7 free days</strong></div>
          <div class="mpr-detail-row"><span>Birthday</span><strong>${bday}</strong></div>
          <div class="mpr-detail-row"><span>Current expiry</span><strong>${endStr}</strong></div>
          <div class="mpr-detail-row"><span>Requested</span><strong>${dateStr}</strong></div>
        </div>

        <div class="mpr-actions">
          <button class="mpr-btn-approve" onclick="approveBirthdayClaim(${c.id})"><i class="fa-solid fa-check"></i> Approve + DM</button>
          <button class="mpr-btn-reject" onclick="rejectBirthdayClaim(${c.id})"><i class="fa-solid fa-xmark"></i> Reject</button>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (e) {
    bgcPendingCount = 0;
    renderPendingBadge();
    section.style.display = 'none';
  }
}

async function approveBirthdayClaim(id) {
  try {
    const res = await authFetch(`${API}/birthday/claims/${id}/approve`, { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (res.ok) {
      if (data.detail === 'already_gifted') {
        showToast('Already gifted this year — request closed without extending.', 'success');
      } else {
        showToast('Approved! +7 days added & congrats DM sent 🎂', 'success');
      }
      loadBirthdayClaims();
    } else {
      showToast(data.detail || 'Error approving claim', 'error');
    }
  } catch (e) {
    showToast('Network error', 'error');
  }
}

async function rejectBirthdayClaim(id) {
  if (!confirm('Reject this birthday gift request?')) return;
  try {
    const res = await authFetch(`${API}/birthday/claims/${id}/reject`, { method: 'POST' });
    if (res.ok) {
      showToast('Birthday gift request rejected.', 'success');
      loadBirthdayClaims();
    } else {
      const data = await res.json().catch(() => ({}));
      showToast(data.detail || 'Error rejecting claim', 'error');
    }
  } catch (e) {
    showToast('Network error', 'error');
  }
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
    mprPendingCount = (data.counts && data.counts.pending) || 0;
    renderPendingBadge();

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

// Which wallet the transfer landed in. The two manual rails settle into
// different accounts, so a reviewer who does not know which one this receipt
// belongs to is checking the wrong statement. Requests filed before the second
// rail existed have no method and were all Instapay.
const MPR_METHOD_LABELS = {
  instapay: 'InstaPay',
  vodafone_cash: 'Vodafone Cash',
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
    const methodLabel = MPR_METHOD_LABELS[req.method] || MPR_METHOD_LABELS.instapay;

    // What the member OWED, worked out server-side, next to what they say they
    // sent. Without this the reviewer compares a discounted transfer against
    // the full list price, sees a shortfall, and rejects a perfectly good
    // payment — which is the specific mistake a coupon on a manual rail
    // invites. "Claimed" above is relabelled from "Amount" for the same reason:
    // that number is typed by the payer and was never authoritative.
    const expectedHtml = req.expected_amount != null ? `
        <div class="mpr-detail-row mpr-expected">
          <span>Expected</span>
          <strong>${req.expected_amount} EGP</strong>
        </div>` : '';

    const couponHtml = req.coupon_code ? `
        <div class="mpr-detail-row mpr-coupon">
          <span>Coupon</span>
          <strong>${escapeHtml(req.coupon_code)}</strong>
        </div>` : '';

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
        <div class="mpr-reject-reason" title="${escapeHtml(req.rejection_reason || '')}">
          Reason: ${escapeHtml(req.rejection_reason || 'N/A')}
        </div>
      `;
    }

    const card = document.createElement('div');
    card.className = 'mpr-card';
    card.innerHTML = `
      <div class="mpr-card-header">
        <div class="mpr-user-info">
          <div class="mpr-name">${escapeHtml(req.full_name)}</div>
          <div class="mpr-email">${escapeHtml(req.email)}</div>
          ${phoneHtml}
        </div>
        <div class="mpr-status-badge ${statusClass}">${req.status.toUpperCase()}</div>
      </div>
      
      <div class="mpr-details">
        <div class="mpr-detail-row">
          <span>Claimed</span>
          <strong>${req.amount ? req.amount + ' EGP' : '--'}</strong>
        </div>
        ${expectedHtml}
        ${couponHtml}
        <div class="mpr-detail-row">
          <span>Plan</span>
          <strong>${planLabel}</strong>
        </div>
        <div class="mpr-detail-row">
          <span>Sent via</span>
          <strong>${escapeHtml(methodLabel)}</strong>
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
  window.lucide && window.lucide.createIcons();
}

// ═══════════════════════════════════════════════════════════
//  COUPONS
// ═══════════════════════════════════════════════════════════
//
// The client's question is "how close is this code to running out", so
// `used / max` and the bar are the headline and the redemption list sits
// under it.
//
// `used` counts confirmed redemptions PLUS live holds — a hold is a Kashier
// checkout opened at the discount but not yet paid, and it expires by itself
// after 30 minutes. It is shown separately rather than folded in silently,
// because a panel that says 30/30 and then reads 27/30 half an hour later with
// no explanation looks broken.
//
// Creating and editing codes is OWNER-ONLY, and the buttons below only hide
// themselves for everyone else — the actual refusal is the 403 from
// POST/PATCH /coupons/admin. There is no delete: coupon_redemptions cascades
// off the coupon row, so removing a code would delete the record of who paid
// what. Disable does the job and keeps the history.

const COUPON_STATUS_LABELS = {
  active: 'Used',
  pending: 'Holding',
  expired: 'Abandoned',
  released: 'Released',
};

// Cards as the server last described them, by id — the edit form reads its
// starting values from here rather than scraping them back off the DOM.
let couponsById = {};

async function loadCouponsTab() {
  const container = document.getElementById('coupons-container');
  container.innerHTML = `<div style="padding: 40px; text-align: center; color: #888; grid-column: 1 / -1;">Loading...</div>`;

  const newBtn = document.getElementById('coupon-new-btn');
  if (newBtn) newBtn.style.display = hasPerm('coupons') ? '' : 'none';

  try {
    const res = await authFetch(`${API}/coupons/admin`);
    if (!res.ok) throw new Error('Failed to load coupons');
    const data = await res.json();

    couponsById = {};
    (data.coupons || []).forEach(c => { couponsById[c.id] = c; });

    if (!data.coupons || data.coupons.length === 0) {
      container.innerHTML = `<div style="padding: 40px; text-align: center; color: #888; grid-column: 1 / -1;">No coupons configured.</div>`;
      return;
    }

    container.innerHTML = data.coupons.map(renderCouponCard).join('');
    window.lucide && window.lucide.createIcons();
  } catch (e) {
    console.error(e);
    container.innerHTML = `<div style="padding: 40px; text-align: center; color: #ef4444; grid-column: 1 / -1;">Error loading coupons</div>`;
  }
}

function renderCouponCard(c) {
  const pct = c.max_redemptions ? Math.min(100, Math.round((c.used / c.max_redemptions) * 100)) : 0;
  // Amber past three-quarters, red when it is gone — the panel exists so the
  // client sees a code running low without having to read the numbers.
  let barClass = 'ok';
  if (c.remaining === 0) barClass = 'gone';
  else if (pct >= 75) barClass = 'low';

  const holdsNote = c.holds
    ? `<div class="coupon-admin-holds">${c.holds} unpaid hold${c.holds === 1 ? '' : 's'} — released automatically if not paid within 30 minutes</div>`
    : '';

  const rows = c.redemptions.length
    ? c.redemptions.map(r => `
        <tr class="cr-${r.status}">
          <td>${r.slot_no != null ? '#' + r.slot_no : '—'}</td>
          <td>
            <div class="cr-name">${escapeHtml(r.user_name || '—')}</div>
            <div class="cr-email">${escapeHtml(r.user_email || '')}</div>
          </td>
          <td>${escapeHtml(COUPON_STATUS_LABELS[r.status] || r.status)}</td>
          <td>${r.method === 'instapay' ? 'InstaPay' : 'Card'}</td>
          <td class="cr-amount">${r.final_amount != null ? r.final_amount + ' ' + (r.currency || '') : '—'}</td>
        </tr>`).join('')
    : `<tr><td colspan="5" style="text-align:center;color:#888;padding:18px;">Nobody has used this code yet.</td></tr>`;

  const actions = hasPerm('coupons') ? `
      <div class="coupon-admin-actions">
        <button class="coupon-admin-btn" onclick="openCouponModal(${c.id})">
          <i data-lucide="pencil"></i> Edit
        </button>
        <button class="coupon-admin-btn ${c.is_active ? 'danger' : ''}"
                id="coupon-toggle-${c.id}"
                onclick="toggleCouponActive(${c.id})">
          <i data-lucide="${c.is_active ? 'ban' : 'check'}"></i> ${c.is_active ? 'Disable' : 'Enable'}
        </button>
      </div>` : '';

  return `
    <div class="coupon-admin-card${c.is_active ? '' : ' is-disabled'}" id="coupon-card-${c.id}">
      <div class="coupon-admin-head">
        <div>
          <div class="coupon-admin-code">${escapeHtml(c.code)}</div>
          <div class="coupon-admin-sub">${c.discount_percent}% off${c.is_active ? '' : ' · disabled'}</div>
        </div>
        <div class="coupon-admin-count">
          <strong>${c.used}</strong><span>/ ${c.max_redemptions}</span>
        </div>
      </div>

      <div class="coupon-admin-bar"><span class="${barClass}" style="width:${pct}%"></span></div>
      <div class="coupon-admin-remaining">${c.remaining} left</div>
      ${holdsNote}
      ${actions}

      <table class="coupon-admin-table">
        <thead>
          <tr><th>Slot</th><th>Member</th><th>Status</th><th>Method</th><th>Paid</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

// ── Create / edit ────────────────────────────────────────────
//
// One modal for both. `couponEditingId` is null when it is a new code, and the
// difference that matters is the first field: on a new coupon it is the code
// itself, on an existing one it is only the display spelling. See the note in
// backend/app/schemas.py for why the code is frozen after creation.

let couponEditingId = null;

function couponFormEl(id) { return document.getElementById(id); }

function openCouponModal(id = null) {
  if (!hasPerm('coupons')) return showToast('🚫 مالكش صلاحية الكوبونات', 'error');

  couponEditingId = id;
  const c = id != null ? couponsById[id] : null;

  couponFormEl('coupon-modal-title').textContent = c ? `Edit ${c.code}` : 'New Coupon';
  couponFormEl('coupon-code').value = c ? c.code : '';
  couponFormEl('coupon-percent').value = c ? c.discount_percent : '';
  couponFormEl('coupon-max').value = c ? c.max_redemptions : '';
  couponFormEl('coupon-error').textContent = '';
  couponFormEl('coupon-max-warning').style.display = 'none';

  // The code is the lookup key once it exists: it is matched lowercase, it
  // travels in `pay.html?coupon=...` links people already have, and a member
  // may be sitting on a 30-minute hold taken with it. Only its capitalisation
  // can move.
  couponFormEl('coupon-code-label').textContent = c ? 'Display spelling' : 'Code *';
  couponFormEl('coupon-code-hint').textContent = c
    ? `Capitalisation only — “${c.lookup_code}” stays the code people type.`
    : 'Letters and numbers only. Case does not matter when a member types it.';

  // "Active from the start" is a create-time choice; afterwards the card's
  // Disable/Enable button is the one place that switches a coupon off, so the
  // form does not offer a second way to do the same thing.
  couponFormEl('coupon-active-row').style.display = c ? 'none' : '';
  couponFormEl('coupon-active').checked = true;

  const btn = couponFormEl('coupon-save-btn');
  btn.disabled = false;
  btn.textContent = c ? 'Save Changes' : 'Create Coupon';

  openModal('coupon-modal');
}

// Lowering the cap under what has already been taken is allowed — nobody is
// thrown out, the code just stops accepting new people. Said out loud before
// the save, because "10" looks like it means ten users and it does not when
// twenty are already in.
function checkCouponMaxWarning() {
  const el = couponFormEl('coupon-max-warning');
  const c = couponEditingId != null ? couponsById[couponEditingId] : null;
  const val = parseInt(couponFormEl('coupon-max').value, 10);
  if (!c || isNaN(val) || val >= c.used) {
    el.style.display = 'none';
    return;
  }
  el.textContent = `⚠️ ${c.used} ${c.used === 1 ? 'person has' : 'people have'} already used this code. `
    + `Lowering the limit to ${val} keeps every one of them — it only stops new redemptions.`;
  el.style.display = '';
}

// Whatever the backend said, verbatim. 422 arrives as FastAPI's array of
// per-field problems; the rest as a plain string.
async function couponErrorText(res) {
  if (res.status === 403) return 'Owners only';
  let data = null;
  try { data = await res.json(); } catch (e) { /* empty or non-JSON body */ }
  const detail = data && data.detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map(d => String(d.msg || '').replace(/^Value error,\s*/, '')).join(' · ');
  }
  if (typeof detail === 'string' && detail) return detail;
  return `Request failed (${res.status})`;
}

async function saveCoupon() {
  const btn = couponFormEl('coupon-save-btn');
  const errEl = couponFormEl('coupon-error');
  errEl.textContent = '';

  const codeText = couponFormEl('coupon-code').value.trim();
  const percent = couponFormEl('coupon-percent').value.trim();
  const max = couponFormEl('coupon-max').value.trim();

  if (!codeText) { errEl.textContent = 'Code is required'; return; }
  if (!percent)  { errEl.textContent = 'Discount is required'; return; }
  if (!max)      { errEl.textContent = 'Number of people is required'; return; }

  const editing = couponEditingId != null;
  const body = editing
    ? { display_code: codeText, discount_percent: Number(percent), max_redemptions: parseInt(max, 10) }
    : {
        code: codeText,
        discount_percent: Number(percent),
        max_redemptions: parseInt(max, 10),
        is_active: couponFormEl('coupon-active').checked,
      };

  // Locked for the round trip: two clicks on Create is two coupons.
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Saving...';

  try {
    const res = await authFetch(
      editing ? `${API}/coupons/admin/${couponEditingId}` : `${API}/coupons/admin`,
      {
        method: editing ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }
    );

    if (!res.ok) {
      errEl.textContent = await couponErrorText(res);
      btn.disabled = false;
      btn.textContent = original;
      return;
    }

    closeModal('coupon-modal');
    showToast(editing ? '🎟️ Coupon updated' : '🎟️ Coupon created', 'success');
    loadCouponsTab();
  } catch (e) {
    errEl.textContent = 'Network error';
    btn.disabled = false;
    btn.textContent = original;
  }
}

// Disable, not delete. `is_active = false` makes preview and checkout refuse
// the code with reason `inactive`, and every redemption already recorded
// against it stays exactly where it is.
async function toggleCouponActive(id) {
  if (!hasPerm('coupons')) return showToast('🚫 مالكش صلاحية الكوبونات', 'error');

  const c = couponsById[id];
  if (!c) return;

  const btn = document.getElementById(`coupon-toggle-${id}`);
  if (btn) btn.disabled = true;

  try {
    const res = await authFetch(`${API}/coupons/admin/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: !c.is_active }),
    });

    if (!res.ok) {
      showToast(await couponErrorText(res), 'error');
      if (btn) btn.disabled = false;
      return;
    }

    const updated = await res.json();
    couponsById[id] = updated;
    const card = document.getElementById(`coupon-card-${id}`);
    if (card) {
      card.outerHTML = renderCouponCard(updated);
      window.lucide && window.lucide.createIcons();
    }
    showToast(updated.is_active ? '🎟️ Coupon enabled' : '🎟️ Coupon disabled', 'success');
  } catch (e) {
    showToast('Network error', 'error');
    if (btn) btn.disabled = false;
  }
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
  // الاقتباسات لازم تتهرّب هي كمان: نفس الدالة بتتحط جوه title="..."
  // و value="..."، وبدونها اسم فيه " بيخرج من الخاصية ويكتب خاصية جديدة.
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
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
              <td style="padding:8px;color:#888;">${escapeHtmlTeam(a.email)}</td>
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

  if (typeof lucide !== 'undefined') window.lucide && window.lucide.createIcons();
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
            <div><strong style="color:#fff;">Member:</strong> ${escapeHtml(project.member_name || 'Unknown')}${project.member_email ? ` (${escapeHtml(project.member_email)})` : ''}</div>
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
      <a href="${escapeHtml(API + p.url)}" target="_blank"
        style="flex:1;font-size:12px;color:#3f8ff9;text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
        title="${escapeHtml(p.name)}">${escapeHtml(p.name)}</a>
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
  if (typeof lucide !== 'undefined') window.lucide && window.lucide.createIcons();
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
  if (typeof lucide !== 'undefined') window.lucide && window.lucide.createIcons();
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
  if (typeof lucide !== 'undefined') window.lucide && window.lucide.createIcons();
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

// ══════════════════════════════════════════════════════════
//  EMAIL CAMPAIGNS TAB (owner-only)
//  ينده /admin/email-campaigns/*  — الجمهور من الداتابيز الحية،
//  الوضع الافتراضي test، الحقيقي محتاج جملة GHAWY-OFFICIAL-SEND.
// ══════════════════════════════════════════════════════════
const EC_LIMIT = 50;
let ecAllRecipients = [];      // كل الأعضاء المطابقين للفلتر (من السيرفر)
let ecSelected = new Map();    // email -> recipient object (بيفضل عبر الصفحات/الفلاتر)
let ecPage = 1;
let ecStatusTimer = null;
let ecFilterQuality = null;    // ملخّص جودة كل المطابقين للفلتر (جاي مع /recipients)
let ecFacetsLoaded = false;    // قوائم البلاد/المحافظات اتحمّلت (مش محتاجينها كل نداء)
let ecQualityReq = 0;          // توكن — يمنع نتيجة جودة قديمة إنها تسبق الجديدة
let ecPreviewReq = 0;          // نفس الفكرة للمعاينة الحيّة
let ecRecipReq = 0;            // ونفسها لتحميل الجمهور (الفلاتر بتتغيّر بسرعة)
let ecLastQualityKey = '';     // بصمة آخر جمهور اتحسبت جودته (يمنع نداء مكرر)
let ecLastPreviewKey = '';     // بصمة آخر محتوى اتعملت له معاينة (يمنع نداء مكرر)

// debounce بسيط — بيأجّل التنفيذ لحد ما اليوزر يبطّل تغيير/كتابة
function ecDebounce(fn, ms) {
  let t = null;
  return function (...args) {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), ms);
  };
}

// ── حالة المنشئ الحالية: null = حملة جديدة، أو { campaign_id, send_mode, active, trigger } ──
let ecEditing = null;
let ecEditorInited = false;

// فتح التاب دايماً على **قائمة الحملات** كصفحة أولى
function loadEmailsTab() {
  ecInitEditorControls();
  ecShowListView();
  loadEmailsList();
}

// listeners المنشئ بتتظبط مرة واحدة بس (بتفضل موجودة عبر التنقّل list↔editor)
function ecInitEditorControls() {
  if (ecEditorInited) return;
  ecEditorInited = true;
  document.querySelectorAll('input[name="ec-mode"]').forEach(r => r.addEventListener('change', ecOnModeChange));
  const s = document.getElementById('ec-f-search');
  if (s) s.addEventListener('keydown', e => { if (e.key === 'Enter') loadRecipients(); });
  ecInitToolbar();
  ecInitVars();
  ecInitLiveFilters();
  ecInitLivePreview();
}

// ── الفلاتر بتتطبّق لوحدها (debounced) عشان العدّاد يتحدّث لحظياً ─────────
const EC_FILTER_TEXT = ['ec-f-search', 'ec-f-country', 'ec-f-gov', 'ec-f-expiring'];
const EC_FILTER_PICK = ['ec-f-status', 'ec-f-plan', 'ec-f-staff'];
const ecReloadRecipients = ecDebounce(() => loadRecipients(), 400);

function ecInitLiveFilters() {
  EC_FILTER_TEXT.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', ecReloadRecipients);
  });
  EC_FILTER_PICK.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', () => loadRecipients());
  });
}

// ── المعاينة الحيّة: أي تعديل في المحتوى → معاينة جديدة بعد ~400ms ────────
const EC_CONTENT_FIELDS = ['ec-subject', 'ec-hero', 'ec-btn-text', 'ec-btn-link', 'ec-closing', 'ec-signoff', 'ec-name-fallback'];
const ecSchedulePreview = ecDebounce(() => previewEmail({ auto: true }), 400);

function ecInitLivePreview() {
  EC_CONTENT_FIELDS.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input', ecSchedulePreview);
  });
  // كلمة الـ fallback بتأثّر على ملخّص الجودة كمان
  const nf = document.getElementById('ec-name-fallback');
  if (nf) nf.addEventListener('input', () => { ecLastQualityKey = ''; ecScheduleQuality(); });
  const editor = document.getElementById('ec-body-editor');
  if (editor) editor.addEventListener('input', ecSchedulePreview);
}

// ══ محرر المحتوى الغني (Rich Text) ═══════════════════════════════
// contentEditable + toolbar (H1/H2/H3/Bold/Italic/List/Link/Divider/Image).
// الناتج بيتعقّم (sanitize) لـ HTML آمن للإيميل وبيتخزّن في #ec-body (المخفي).

// الوسوم المسموحة + ستايلات inline آمنة للإيميل (نفس أزرق الفوتر للينكات)
const EC_ALLOWED = { H1:1, H2:1, H3:1, P:1, STRONG:1, EM:1, A:1, HR:1, IMG:1, UL:1, OL:1, LI:1, BR:1 };
const EC_STYLES = {
  H1: 'margin:0 0 14px;font-size:26px;line-height:1.4;font-weight:800;color:#111;',
  H2: 'margin:0 0 12px;font-size:22px;line-height:1.4;font-weight:800;color:#111;',
  H3: 'margin:0 0 10px;font-size:18px;line-height:1.4;font-weight:700;color:#111;',
  P:  'margin:0 0 14px;font-size:16px;line-height:1.9;color:#1a1a1a;',
  A:  'color:#3f8ff9;text-decoration:underline;',
  HR: 'border:0;border-top:1px solid #e5e5e5;margin:22px 0;',
  IMG:'max-width:100%;height:auto;display:block;border-radius:8px;margin:0 0 14px;',
  UL: 'margin:0 0 14px;padding-inline-start:22px;',
  OL: 'margin:0 0 14px;padding-inline-start:22px;',
  LI: 'margin:0 0 6px;font-size:16px;line-height:1.9;color:#1a1a1a;',
};

function ecSanitizeInto(src, out) {
  src.childNodes.forEach(child => {
    if (child.nodeType === 3) { out.appendChild(document.createTextNode(child.textContent)); return; }
    if (child.nodeType !== 1) return;
    let tag = child.tagName;
    if (tag === 'B') tag = 'STRONG';
    if (tag === 'I') tag = 'EM';
    if (tag === 'DIV') tag = 'P';
    if (!EC_ALLOWED[tag]) { ecSanitizeInto(child, out); return; } // وسم مرفوض → نسيب المحتوى بس
    const el = document.createElement(tag.toLowerCase());
    if (EC_STYLES[tag]) el.setAttribute('style', EC_STYLES[tag]);
    if (tag === 'A') {
      let href = child.getAttribute('href') || '';
      if (/^\s*javascript:/i.test(href)) href = '';
      el.setAttribute('href', href);
      el.setAttribute('target', '_blank');
      el.setAttribute('rel', 'noopener');
    }
    if (tag === 'IMG') {
      let src2 = child.getAttribute('src') || '';
      if (!/^(https?:\/\/|data:image\/)/i.test(src2)) src2 = '';
      el.setAttribute('src', src2);
      el.setAttribute('alt', child.getAttribute('alt') || '');
    }
    if (tag !== 'BR' && tag !== 'HR' && tag !== 'IMG') ecSanitizeInto(child, el);
    out.appendChild(el);
  });
}

function ecSanitizeHtml(html) {
  const tmp = document.createElement('div');
  tmp.innerHTML = html || '';
  const out = document.createElement('div');
  ecSanitizeInto(tmp, out);
  return out.innerHTML;
}

function ecSyncBody() {
  const editor = document.getElementById('ec-body-editor');
  const hidden = document.getElementById('ec-body');
  if (!editor || !hidden) return;
  const html = ecSanitizeHtml(editor.innerHTML).trim();
  hidden.value = html;
}

function ecInitToolbar() {
  const tb = document.getElementById('ec-toolbar');
  const editor = document.getElementById('ec-body-editor');
  if (!tb || !editor) return;
  // منع فقدان التحديد وقت الضغط على زرار الأدوات
  tb.addEventListener('mousedown', e => e.preventDefault());
  tb.querySelectorAll('.ec-tb').forEach(b => b.addEventListener('click', () => ecExecCmd(b.dataset.cmd)));
  editor.addEventListener('input', ecSyncBody);
  editor.addEventListener('blur', ecSyncBody);
  editor.addEventListener('focus', () => { ecLastField = editor; });
}

function ecExecCmd(cmd) {
  const editor = document.getElementById('ec-body-editor');
  if (!editor) return;
  editor.focus();
  switch (cmd) {
    case 'h1': document.execCommand('formatBlock', false, 'H1'); break;
    case 'h2': document.execCommand('formatBlock', false, 'H2'); break;
    case 'h3': document.execCommand('formatBlock', false, 'H3'); break;
    case 'bold': document.execCommand('bold'); break;
    case 'italic': document.execCommand('italic'); break;
    case 'ul': document.execCommand('insertUnorderedList'); break;
    case 'hr': document.execCommand('insertHTML', false, '<hr><p><br></p>'); break;
    case 'link': {
      const url = (prompt('لينك (URL):', 'https://') || '').trim();
      if (url && !/^javascript:/i.test(url)) document.execCommand('createLink', false, url);
      break;
    }
    case 'image': {
      const url = (prompt('رابط الصورة (URL):', 'https://') || '').trim();
      if (url && /^(https?:\/\/|data:image\/)/i.test(url)) {
        document.execCommand('insertHTML', false, `<img src="${url.replace(/"/g, '&quot;')}" alt=""><p><br></p>`);
      }
      break;
    }
  }
  ecSyncBody();
  ecSchedulePreview();
}

function ecInsertAtCaret(editor, text) {
  const sel = window.getSelection();
  if (sel && sel.rangeCount && editor.contains(sel.anchorNode)) {
    const range = sel.getRangeAt(0);
    range.deleteContents();
    const node = document.createTextNode(text);
    range.insertNode(node);
    range.setStartAfter(node); range.setEndAfter(node);
    sel.removeAllRanges(); sel.addRange(range);
  } else {
    editor.appendChild(document.createTextNode(text));
  }
}

// ── تبديل العروض ──────────────────────────────────────────────
function ecShowListView() {
  document.getElementById('emails-list-view').style.display = '';
  document.getElementById('emails-editor-view').style.display = 'none';
}
function ecShowEditorView() {
  document.getElementById('emails-list-view').style.display = 'none';
  document.getElementById('emails-editor-view').style.display = '';
  if (typeof lucide !== 'undefined') setTimeout(() => window.lucide && window.lucide.createIcons(), 10);
}

// ── قائمة الحملات ─────────────────────────────────────────────
async function loadEmailsList() {
  const grid = document.getElementById('ec-campaigns-grid');
  if (grid) grid.innerHTML = '<div class="ec-empty">جاري التحميل...</div>';
  try {
    const res = await fetch(`${API}/admin/email-campaigns/campaigns`, { headers });
    if (res.status === 403) { showToast('👑 Owners only', 'error'); if (grid) grid.innerHTML = ''; return; }
    if (!res.ok) { if (grid) grid.innerHTML = '<div class="ec-empty">❌ فشل تحميل الحملات</div>'; return; }
    const data = await res.json();
    ecRenderCampaignCards(data.campaigns || []);
  } catch (e) {
    if (grid) grid.innerHTML = `<div class="ec-empty">❌ خطأ شبكة: ${escapeHtml(e.message)}</div>`;
  }
  if (typeof lucide !== 'undefined') setTimeout(() => window.lucide && window.lucide.createIcons(), 10);
}

function ecStatusMeta(c) {
  if (c.type === 'automated') {
    return c.status === 'active'
      ? { cls: 'active', label: 'Active — أوتوميشن شغّال' }
      : { cls: 'stopped', label: 'متوقف — أوتوميشن' };
  }
  return { cls: 'draft', label: 'مسودة' };
}

function ecRenderCampaignCards(items) {
  const grid = document.getElementById('ec-campaigns-grid');
  if (!grid) return;
  if (!items.length) {
    grid.innerHTML = '<div class="ec-empty">مفيش حملات لسه. اضغط "حملة جديدة" عشان تبدأ. ✨</div>';
    return;
  }
  grid.innerHTML = items.map(c => {
    const st = ecStatusMeta(c);
    const trig = c.trigger_type
      ? `<span class="ec-card-trigger">⚡ ${escapeHtml(c.trigger_type)}</span>` : '';
    return `<div class="ec-camp-card" onclick="ecOpenCampaign('${encodeURIComponent(c.campaign_id)}')" title="فتح / تعديل">
      <div class="ec-camp-top">
        <span class="ec-status-badge ${st.cls}">${st.label}</span>
        ${trig}
      </div>
      <div class="ec-camp-title">${escapeHtml(c.title || c.campaign_id)}</div>
      <div class="ec-camp-desc">${escapeHtml(c.description || '—')}</div>
      <div class="ec-camp-foot">
        <span class="ec-camp-sent">📨 إجمالي المرسل لهم: <b>${c.sent_total || 0}</b></span>
        <span class="ec-camp-open">فتح / تعديل ›</span>
      </div>
    </div>`;
  }).join('');
}

// ── فتح حملة موجودة → المنشئ متعبّي ────────────────────────────
async function ecOpenCampaign(encId) {
  const cid = decodeURIComponent(encId);
  try {
    const res = await fetch(`${API}/admin/email-campaigns/campaigns/${encodeURIComponent(cid)}`, { headers });
    if (res.status === 404) { showToast('❌ الحملة مش موجودة', 'error'); loadEmailsList(); return; }
    if (!res.ok) { showToast('❌ فشل فتح الحملة', 'error'); loadEmailsList(); return; }
    const camp = await res.json();
    ecFillEditor(camp);
    ecShowEditorView();
    loadRecipients();
  } catch (e) {
    showToast('❌ خطأ شبكة: ' + e.message, 'error');
    loadEmailsList();
  }
}

// ── حملة جديدة → منشئ فاضي ─────────────────────────────────────
function ecNewCampaign() {
  ecResetEditor();
  ecShowEditorView();
  const cid = document.getElementById('ec-campaign-id');
  if (cid) {
    const d = new Date();
    cid.value = `campaign-${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }
  loadRecipients();
}

// ── رجوع للقائمة (مع refresh) ─────────────────────────────────
function ecBackToList() {
  ecShowListView();
  loadEmailsList();
}

const EC_TEXT_FIELDS = ['ec-title', 'ec-description', 'ec-campaign-id', 'ec-subject', 'ec-body', 'ec-hero', 'ec-btn-text', 'ec-btn-link', 'ec-closing'];

function ecResetEditor() {
  ecEditing = null;
  EC_TEXT_FIELDS.forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  const editor = document.getElementById('ec-body-editor'); if (editor) editor.innerHTML = '';
  const so = document.getElementById('ec-signoff'); if (so) so.value = 'محمد - غاوي';
  const nf = document.getElementById('ec-name-fallback'); if (nf) nf.value = 'صديقنا';
  const idEl = document.getElementById('ec-campaign-id'); if (idEl) idEl.readOnly = false;
  const t = document.getElementById('ec-editor-title'); if (t) t.textContent = '📧 حملة جديدة';
  ecApplyAudience({});
  const rb = document.getElementById('ec-send-result'); if (rb) rb.style.display = 'none';
  const subj = document.getElementById('ec-preview-subject'); if (subj) subj.textContent = '— العنوان هيظهر هنا —';
  const frame = document.getElementById('ec-preview-frame'); if (frame) frame.srcdoc = '';
  const testRadio = document.querySelector('input[name="ec-mode"][value="test"]'); if (testRadio) testRadio.checked = true;
  ecSelected.clear();
  ecFilterQuality = null;
  ecLastQualityKey = '';
  ecLastPreviewKey = '';
  ['ec-audience-quality', 'ec-send-quality'].forEach(id => {
    const el = document.getElementById(id); if (el) el.style.display = 'none';
  });
  ecUpdateEditorChrome();
}

function ecFillEditor(camp) {
  ecEditing = {
    campaign_id: camp.campaign_id,
    send_mode: camp.send_mode || 'manual',
    active: !!camp.active,
    trigger: camp.trigger || null,
    type: camp.type,
    status: camp.status,
  };
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = (v == null ? '' : v); };
  set('ec-title', camp.title || '');
  set('ec-description', camp.description || '');
  set('ec-campaign-id', camp.campaign_id || '');
  const c = camp.content || {};
  set('ec-subject', c.subject_template || '');
  // جسم الرسالة → المحرر الغني (بيتعقّم عند التحميل) + مزامنة للـ hidden field
  const bodyHtml = c.body_html || (Array.isArray(c.body_paragraphs_html)
    ? c.body_paragraphs_html.map(p => `<p>${p}</p>`).join('') : '');
  const editor = document.getElementById('ec-body-editor');
  if (editor) editor.innerHTML = ecSanitizeHtml(bodyHtml);
  ecSyncBody();
  set('ec-name-fallback', c.name_ar_fallback || 'صديقنا');
  set('ec-hero', c.hero_emoji || '');
  let bt = c.button_text || '', bl = c.button_link || '';
  if ((!bt || !bl) && Array.isArray(c.buttons) && c.buttons.length) {
    bt = c.buttons[0].text || bt; bl = c.buttons[0].link || bl;
  }
  set('ec-btn-text', bt);
  set('ec-btn-link', bl);
  set('ec-closing', c.closing_line || '');
  set('ec-signoff', c.signoff_html || 'محمد - غاوي');
  ecApplyAudience(camp.audience || {});
  const t = document.getElementById('ec-editor-title');
  if (t) t.textContent = '📧 ' + (camp.title || camp.campaign_id);
  const idEl = document.getElementById('ec-campaign-id'); if (idEl) idEl.readOnly = true;
  ecSelected.clear();
  const rb = document.getElementById('ec-send-result'); if (rb) rb.style.display = 'none';
  ecUpdateEditorChrome();
  // معاينة فورية للحملة المفتوحة (من غير ما اليوزر يضغط حاجة)
  ecLastPreviewKey = '';
  ecSchedulePreview();
}

// شكل رأس المنشئ: البادج + بانر الأوتوميشن + تقييد الإرسال اليدوي للأوتوماتيك
function ecUpdateEditorChrome() {
  const badge = document.getElementById('ec-editor-badge');
  const banner = document.getElementById('ec-auto-banner');
  const isAuto = !!(ecEditing && ecEditing.send_mode === 'automated');
  if (badge) {
    let cls = 'new', label = 'حملة جديدة';
    if (ecEditing) {
      if (isAuto) { cls = ecEditing.active ? 'active' : 'stopped'; label = ecEditing.active ? 'Active — أوتوميشن شغّال' : 'متوقف — أوتوميشن'; }
      else { cls = 'draft'; label = 'مسودة'; }
    }
    badge.className = 'ec-status-badge ' + cls;
    badge.textContent = label;
  }
  if (banner) {
    if (isAuto) {
      banner.style.display = 'flex';
      const sub = document.getElementById('ec-auto-sub');
      const trigType = ecEditing.trigger && ecEditing.trigger.type ? ecEditing.trigger.type : null;
      if (sub) sub.textContent = trigType
        ? `Trigger: ${trigType} — بتتبعت تلقائياً عبر الـ runner (مش بإرسال يدوي).`
        : 'بتتبعت تلقائياً عبر الـ runner حسب الـ trigger (مش بإرسال يدوي).';
      const tbtn = document.getElementById('ec-toggle-btn');
      if (tbtn) {
        tbtn.textContent = ecEditing.active ? '⏸ إيقاف الأوتوميشن' : '▶ تفعيل الأوتوميشن';
        tbtn.className = 'ec-toggle-btn ' + (ecEditing.active ? 'on' : 'off');
      }
    } else {
      banner.style.display = 'none';
    }
  }
  ecApplySendRestrictions(isAuto);
}

// الأوتوماتيك: يتقفل عليه وضع الإرسال الحقيقي اليدوي (بيتبعت عبر الـ runner)
function ecApplySendRestrictions(isAuto) {
  const realRadio = document.querySelector('input[name="ec-mode"][value="real"]');
  const realOpt = realRadio ? realRadio.closest('.ec-mode-opt') : null;
  if (isAuto) {
    const testRadio = document.querySelector('input[name="ec-mode"][value="test"]');
    if (testRadio) testRadio.checked = true;
    if (realRadio) realRadio.disabled = true;
    if (realOpt) realOpt.style.display = 'none';
  } else {
    if (realRadio) realRadio.disabled = false;
    if (realOpt) realOpt.style.display = '';
  }
  ecOnModeChange();
}

// ── فلاتر الجمهور: قراءة/تطبيق (بتتحفظ مع الحملة وتترجّع عند الفتح) ──
function ecGetAudience() {
  const g = id => (document.getElementById(id)?.value || '').trim();
  const exp = g('ec-f-expiring');
  return {
    source: ecSource(),
    status: g('ec-f-status') || 'all',
    plan: g('ec-f-plan') || 'all',
    country: g('ec-f-country'),
    governorate: g('ec-f-gov'),
    expiring_days: exp ? Number(exp) : null,
    include_staff: !!document.getElementById('ec-f-staff')?.checked,
    search: g('ec-f-search'),
  };
}
function ecApplyAudience(a) {
  a = a || {};
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = (v == null ? '' : v); };
  set('ec-f-search', a.search || '');
  set('ec-f-country', a.country || '');
  set('ec-f-gov', a.governorate || '');
  const st = document.getElementById('ec-f-status'); if (st) st.value = a.status || 'all';
  const pl = document.getElementById('ec-f-plan'); if (pl) pl.value = a.plan || 'all';
  set('ec-f-expiring', a.expiring_days != null ? a.expiring_days : '');
  const staff = document.getElementById('ec-f-staff'); if (staff) staff.checked = !!a.include_staff;
  // الحملات القديمة اتحفظت من غير source — الافتراضي أعضاء المنصة زي ما كانت.
  const src = document.getElementById('ec-f-source');
  if (src) { src.value = a.source === 'atlas' ? 'atlas' : 'platform'; }
  const atlas = ecSource() === 'atlas';
  ['ec-f-country', 'ec-f-gov', 'ec-f-status', 'ec-f-plan', 'ec-f-expiring']
    .forEach(id => { const el = document.getElementById(id); if (el) el.style.display = atlas ? 'none' : ''; });
  const staffWrap = staff?.closest('label');
  if (staffWrap) staffWrap.style.display = atlas ? 'none' : '';
}

// ── حفظ الحملة (POST جديد / PUT موجود) — مايبعتش أي إيميل ──────
async function ecSaveCampaign() {
  const title = (document.getElementById('ec-title')?.value || '').trim();
  const content = ecBuildContent();
  if (!title && !content.subject_template) {
    showToast('❌ لازم اسم للحملة أو عنوان رسالة (Subject)', 'error');
    return;
  }
  const payload = {
    title,
    description: (document.getElementById('ec-description')?.value || '').trim(),
    content,
    audience: ecGetAudience(),
  };
  let url, method;
  if (ecEditing && ecEditing.campaign_id) {
    url = `${API}/admin/email-campaigns/campaigns/${encodeURIComponent(ecEditing.campaign_id)}`;
    method = 'PUT';
    payload.send_mode = ecEditing.send_mode;
  } else {
    url = `${API}/admin/email-campaigns/campaigns`;
    method = 'POST';
    payload.send_mode = 'manual';
    payload.campaign_id = (document.getElementById('ec-campaign-id')?.value || '').trim() || null;
  }
  try {
    const res = await fetch(url, { method, headers, body: JSON.stringify(payload) });
    const data = await res.json();
    if (!res.ok) { showToast(`❌ ${data.detail || 'فشل الحفظ'}`, 'error'); return; }
    showToast('✅ اتحفظت الحملة', 'success');
    ecShowListView();
    loadEmailsList();
  } catch (e) {
    showToast('❌ خطأ شبكة: ' + e.message, 'error');
  }
}

// ── تفعيل/إيقاف الأوتوميشن (زرار صريح بس) ─────────────────────
async function ecToggleActive() {
  if (!ecEditing || !ecEditing.campaign_id || ecEditing.send_mode !== 'automated') return;
  const newActive = !ecEditing.active;
  const verb = newActive ? 'تفعيل' : 'إيقاف';
  if (!confirm(`متأكد إنك عايز ${verb} الأوتوميشن دي؟`)) return;
  try {
    const res = await fetch(`${API}/admin/email-campaigns/campaigns/${encodeURIComponent(ecEditing.campaign_id)}/active`, {
      method: 'POST', headers, body: JSON.stringify({ active: newActive })
    });
    const data = await res.json();
    if (!res.ok) { showToast(`❌ ${data.detail || 'فشل'}`, 'error'); return; }
    ecEditing.active = !!data.active;
    ecUpdateEditorChrome();
    showToast(newActive ? '▶ اتفعّلت الأوتوميشن' : '⏸ اتوقفت الأوتوميشن', 'success');
  } catch (e) {
    showToast('❌ خطأ شبكة: ' + e.message, 'error');
  }
}

// ── متغيّرات الإيميل: سحب/إفلات + ضغط لإضافتها عند المؤشّر ──────────
let ecVarsInited = false;
let ecLastField = null;
function ecInitVars() {
  if (ecVarsInited) return;
  ecVarsInited = true;
  // الخانات اللي بتقبل المتغيّرات — بنتتبّع آخر واحدة اتعملها focus عشان الضغط يحطّها فيها.
  // جسم الرسالة بقى محرر غني (contentEditable) بدل textarea — بيتضاف لنفس التتبّع.
  const fieldIds = ['ec-subject', 'ec-closing', 'ec-btn-text', 'ec-signoff'];
  const fields = fieldIds.map(id => document.getElementById(id)).filter(Boolean);
  const editor = document.getElementById('ec-body-editor');
  if (editor) fields.push(editor);
  fields.forEach(el => {
    el.addEventListener('focus', () => { ecLastField = el; });
    // تمييز بصري وقت السحب فوق الخانة (الإفلات نفسه بيتعامل معاه المتصفح تلقائي)
    el.addEventListener('dragover', e => { e.preventDefault(); el.classList.add('ec-drop-active'); });
    el.addEventListener('dragleave', () => el.classList.remove('ec-drop-active'));
    el.addEventListener('drop', () => {
      el.classList.remove('ec-drop-active');
      setTimeout(() => { ecLastField = el; if (el.isContentEditable) ecSyncBody(); }, 0);
    });
  });
  document.querySelectorAll('#ec-vars .ec-var').forEach(chip => {
    chip.addEventListener('dragstart', e => {
      e.dataTransfer.setData('text/plain', chip.dataset.var);
      e.dataTransfer.effectAllowed = 'copy';
    });
    chip.addEventListener('click', () => {
      ecInsertVar(chip.dataset.var);
      chip.classList.remove('ec-inserted'); void chip.offsetWidth; chip.classList.add('ec-inserted');
    });
  });
}

function ecInsertVar(text) {
  const el = ecLastField || document.getElementById('ec-body-editor');
  if (!el) return;
  el.focus();
  if (el.isContentEditable) {
    ecInsertAtCaret(el, text);
    ecSyncBody();
    ecLastField = el;
    ecSchedulePreview();
    return;
  }
  const start = (el.selectionStart != null) ? el.selectionStart : el.value.length;
  const end = (el.selectionEnd != null) ? el.selectionEnd : el.value.length;
  el.value = el.value.slice(0, start) + text + el.value.slice(end);
  const pos = start + text.length;
  try { el.setSelectionRange(pos, pos); } catch (e) {}
  ecLastField = el;
  ecSchedulePreview();
}

function ecGetMode() {
  const el = document.querySelector('input[name="ec-mode"]:checked');
  return el ? el.value : 'test';
}

function ecOnModeChange() {
  const mode = ecGetMode();
  const warn = document.getElementById('ec-real-warn');
  const btn = document.getElementById('ec-send-btn');
  if (warn) warn.style.display = mode === 'real' ? 'block' : 'none';
  if (btn) {
    btn.classList.toggle('real', mode === 'real');
    btn.innerHTML = mode === 'real'
      ? '<i data-lucide="alert-triangle" style="width:15px;height:15px;"></i> إرسال حقيقي'
      : '<i data-lucide="send" style="width:15px;height:15px;"></i> إرسال تجريبي';
  }
  ecUpdateCounts();
  if (typeof lucide !== 'undefined') setTimeout(() => window.lucide && window.lucide.createIcons(), 10);
}

// مصدر الجمهور الحالي: 'platform' (جدول users) أو 'atlas' (جدول legacy_emails).
function ecSource() {
  return (document.getElementById('ec-f-source')?.value || 'platform');
}

// فلاتر الأعضاء (بلد/محافظة/حالة/باقة/انتهاء/فريق) معناها مربوط بجدول users — مالهاش
// أي معنى على روستر اطلس، فبتتخفي بدل ما تفضل باينة وهي مش بتعمل حاجة.
function ecOnSourceChange() {
  const atlas = ecSource() === 'atlas';
  ['ec-f-country', 'ec-f-gov', 'ec-f-status', 'ec-f-plan', 'ec-f-expiring']
    .forEach(id => { const el = document.getElementById(id); if (el) el.style.display = atlas ? 'none' : ''; });
  const staffWrap = document.getElementById('ec-f-staff')?.closest('label');
  if (staffWrap) staffWrap.style.display = atlas ? 'none' : '';
  ecSelected.clear();
  ecAllRecipients = [];
  ecPage = 1;
  ecRenderRecipients();
  ecUpdateCounts();
  loadRecipients();
}

async function loadRecipients() {
  const tbody = document.getElementById('ec-recipients-tbody');
  tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:#888;padding:30px;">جاري التحميل...</td></tr>`;
  const params = new URLSearchParams();
  const g = id => (document.getElementById(id)?.value || '').trim();
  const atlas = ecSource() === 'atlas';
  if (g('ec-f-search')) params.set('search', g('ec-f-search'));
  if (!atlas) {
    if (g('ec-f-country')) params.set('country', g('ec-f-country'));
    if (g('ec-f-gov')) params.set('governorate', g('ec-f-gov'));
    const st = g('ec-f-status'); if (st && st !== 'all') params.set('status', st);
    const pl = g('ec-f-plan'); if (pl && pl !== 'all') params.set('plan', pl);
    if (g('ec-f-expiring')) params.set('expiring_days', g('ec-f-expiring'));
    if (document.getElementById('ec-f-staff')?.checked) params.set('include_staff', 'true');
    // قوائم البلاد/المحافظات ثابتة — نجيبها مرة واحدة بس (الفلاتر بتتنده كل ما اليوزر يكتب)
    params.set('include_facets', ecFacetsLoaded ? 'false' : 'true');
  }
  params.set('name_fallback', ecNameFallback());

  // نفس شكل الرد بالظبط في الحالتين (recipients + quality)، فكل اللي تحت مايتغيرش.
  const path = atlas ? 'atlas-recipients' : 'recipients';

  const my = ++ecRecipReq;
  try {
    const res = await fetch(`${API}/admin/email-campaigns/${path}?${params}`, { headers });
    if (my !== ecRecipReq) return;   // فلتر أحدث سبقه — نتجاهل النتيجة القديمة
    if (res.status === 403) { showToast('👑 Owners only', 'error'); tbody.innerHTML = ''; return; }
    if (!res.ok) { showToast('❌ فشل تحميل الأعضاء', 'error'); return; }
    const data = await res.json();
    if (my !== ecRecipReq) return;
    ecAllRecipients = data.recipients || [];
    ecFilterQuality = data.quality || null;
    if (data.countries || data.governorates) {
      ecFillDatalist('ec-countries', data.countries);
      ecFillDatalist('ec-govs', data.governorates);
      ecFacetsLoaded = true;
    }
    ecPage = 1;
    ecRenderRecipients();
    ecUpdateCounts();
    ecSchedulePreview();   // عيّنة المعاينة اتغيّرت مع الجمهور الجديد
    if (data.truncated) showToast(`⚠️ العدد كبير — اتحمّل أول ${ecAllRecipients.length}`, 'info');
  } catch (e) {
    if (my === ecRecipReq) showToast('❌ خطأ شبكة: ' + e.message, 'error');
  }
}

function ecFillDatalist(id, arr) {
  const dl = document.getElementById(id);
  if (!dl || !arr) return;
  dl.innerHTML = arr.map(v => `<option value="${escapeHtml(v)}"></option>`).join('');
}

function ecRenderRecipients() {
  const tbody = document.getElementById('ec-recipients-tbody');
  if (!ecAllRecipients.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:#888;padding:30px;">مفيش أعضاء مطابقين للفلتر</td></tr>`;
    document.getElementById('ec-pagination').innerHTML = '';
    return;
  }
  const start = (ecPage - 1) * EC_LIMIT;
  const rows = ecAllRecipients.slice(start, start + EC_LIMIT);
  tbody.innerHTML = rows.map(r => {
    const checked = ecSelected.has(r.email) ? 'checked' : '';
    const statusPill = r.is_active
      ? '<span class="ec-pill active">Active</span>'
      : '<span class="ec-pill inactive">Inactive</span>';
    const plan = r.plan_group ? escapeHtml(r.plan_group) : '—';
    return `<tr>
      <td><input type="checkbox" class="ec-cb" ${checked} onchange="ecToggle('${encodeURIComponent(r.email)}', this.checked)"></td>
      <td>${escapeHtml(r.name || '—')}</td>
      <td style="direction:ltr;text-align:right;font-size:12px;color:#aaa;">${escapeHtml(r.email)}</td>
      <td>${escapeHtml(r.governorate || '—')}</td>
      <td>${plan}</td>
      <td>${statusPill}</td>
    </tr>`;
  }).join('');
  const totalPages = Math.ceil(ecAllRecipients.length / EC_LIMIT);
  buildPager(document.getElementById('ec-pagination'), ecPage, totalPages, 'ecGoPage');
}

function ecGoPage(p) { ecPage = p; ecRenderRecipients(); }

function ecToggle(encEmail, checked) {
  const email = decodeURIComponent(encEmail);
  const rec = ecAllRecipients.find(r => r.email === email);
  if (!rec) return;
  if (checked) ecSelected.set(email, rec); else ecSelected.delete(email);
  ecUpdateCounts();
}

function ecSelectAll(sel) {
  if (sel) ecAllRecipients.forEach(r => ecSelected.set(r.email, r));
  else ecAllRecipients.forEach(r => ecSelected.delete(r.email));
  ecRenderRecipients();
  ecUpdateCounts();
}

// الجمهور اللي الأرقام بتتحسب عليه: المحدّدين فعلاً، ولو مفيش تحديد → كل المطابقين للفلتر
function ecTargetList() {
  return ecSelected.size ? ecSelectedList() : ecAllRecipients;
}

function ecNameFallback() {
  return (document.getElementById('ec-name-fallback')?.value || '').trim() || 'صديقنا';
}

// عدّاد المستقبلين — بيتكتب في مكانين: تحت جدول الجمهور وجنب زرار الإرسال
function ecUpdateCounts() {
  const selected = ecSelected.size;
  const matched = ecAllRecipients.length;
  const chip = document.getElementById('ec-count-chip');
  if (chip) chip.textContent = matched;
  const selinfo = document.getElementById('ec-selinfo');
  if (selinfo) selinfo.textContent = `${selected} محدد`;

  const main = `هيتبعت لـ <b>${selected}</b> شخص`;
  const sub = selected
    ? `من ${matched} مطابقين للفلتر`
    : (matched ? `${matched} مطابقين للفلتر — حدّد اللي عايزهم أو اضغط "تحديد الكل"` : 'مفيش أعضاء مطابقين للفلتر');
  const testNote = ecGetMode() === 'test'
    ? '<span class="ec-target-test">🧪 وضع تجريبي — الرسالة هتروح لإيميلات التست بس</span>' : '';
  const html = `<span class="ec-target-main">${main}</span><span class="ec-target-sub">${sub}</span>${testNote}`;

  ['ec-audience-summary', 'ec-send-summary'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  });
  ecScheduleQuality();
}

// ══ ملخّص جودة الداتا — كله محسوب في الـ backend من نفس build_template_vars ══
const ecScheduleQuality = ecDebounce(() => ecRefreshQuality(), 350);

async function ecRefreshQuality() {
  const boxes = ['ec-audience-quality', 'ec-send-quality']
    .map(id => document.getElementById(id)).filter(Boolean);
  if (!boxes.length) return;

  const list = ecTargetList();
  const isSelection = ecSelected.size > 0;
  if (!list.length) { boxes.forEach(b => b.style.display = 'none'); ecLastQualityKey = ''; return; }

  const fallback = ecNameFallback();
  const key = `${isSelection ? 'sel' : 'all'}|${fallback}|${list.length}|${list.map(r => r.email).join(',')}`;
  if (key === ecLastQualityKey) return;   // نفس الجمهور ونفس الـ fallback — مفيش داعي لنداء
  ecLastQualityKey = key;

  // مفيش تحديد + نفس كلمة الـ fallback؟ الملخّص جه أصلاً مع /recipients — من غير نداء زيادة
  if (!isSelection && ecFilterQuality && ecFilterQuality.fallback_word === fallback) {
    ecRenderQuality(ecFilterQuality, false);
    return;
  }

  const my = ++ecQualityReq;
  try {
    const res = await fetch(`${API}/admin/email-campaigns/audience-quality`, {
      method: 'POST', headers,
      body: JSON.stringify({
        recipients: list.map(r => ({
          name: r.name, email: r.email, country: r.country, country_ar: r.country_ar,
          governorate: r.governorate, governorate_ar: r.governorate_ar, name_ar: r.name_ar
        })),
        name_ar_fallback: fallback
      })
    });
    if (my !== ecQualityReq) return;               // نتيجة قديمة اتخطّتها واحدة أحدث
    if (!res.ok) { ecLastQualityKey = ''; boxes.forEach(b => b.style.display = 'none'); return; }
    const q = await res.json();
    if (my !== ecQualityReq) return;
    ecRenderQuality(q, isSelection);
  } catch (e) {
    ecLastQualityKey = '';
  }
}

function ecRenderQuality(q, isSelection) {
  // ملاحظة: أي كلمة لاتيني جوه نص عربي بتتلف في الـ bidi — بنعزلها بـ <bdi>
  const parts = [];
  if (q.name_fallback) {
    parts.push(`<b>${q.name_fallback}</b> اسمهم مش هيتترجم فهيتنادوا بالكلمة الاحتياطية (<bdi class="ec-q-word">${escapeHtml(q.fallback_word || '')}</bdi>)`);
  }
  if (q.missing_governorate) parts.push(`<b>${q.missing_governorate}</b> محافظتهم ناقصة`);
  if (q.invalid_contact) parts.push(`<b>${q.invalid_contact}</b> بياناتهم مشبوهة (اسم/إيميل)`);

  const scope = isSelection ? '' :
    '<span class="ec-q-scope">الأرقام دي لكل المطابقين للفلتر — لسه مفيش تحديد.</span>';
  const html = parts.length
    ? `<span class="ec-q-head">⚠️ هيتبعت لـ <b>${q.total}</b> — منهم ${parts.join('، و')}.</span>${scope}
       <span class="ec-q-note">ده تنبيه بس ومش بيمنع الإرسال — الرسالة هتتبعت عادي بالكلمة الاحتياطية.</span>`
    : `<span class="ec-q-head">✅ داتا الـ <b>${q.total}</b> دول كاملة — كل الأسماء والمحافظات هتظهر صح.</span>${scope}`;

  ['ec-audience-quality', 'ec-send-quality'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.className = 'ec-quality ' + (parts.length ? 'warn' : 'ok');
    el.innerHTML = html;
    el.style.display = 'flex';   // لازم flex (الـ inline بيتغلّب على الـ CSS) عشان كل سطر لوحده
  });
}

function ecSelectedList() { return Array.from(ecSelected.values()); }

function ecBuildContent() {
  ecSyncBody(); // يعقّم محتوى المحرر ويكتبه في #ec-body قبل القراءة
  const g = id => (document.getElementById(id)?.value || '');
  const content = {
    subject_template: g('ec-subject').trim(),
    body_html: g('ec-body'),
    signoff_html: g('ec-signoff').trim() || 'محمد - غاوي',
  };
  const nf = g('ec-name-fallback').trim();
  if (nf) content.name_ar_fallback = nf;
  const hero = g('ec-hero').trim();
  if (hero) content.hero_emoji = hero;
  const bt = g('ec-btn-text').trim(), bl = g('ec-btn-link').trim();
  if (bt && bl) { content.button_text = bt; content.button_link = bl; }
  const cl = g('ec-closing').trim();
  if (cl) content.closing_line = cl;
  return content;
}

function ecValidateContent(content) {
  if (!content.subject_template) { showToast('❌ لازم عنوان للرسالة', 'error'); return false; }
  if (!content.body_html || !content.body_html.trim()) { showToast('❌ لازم نص للرسالة', 'error'); return false; }
  return true;
}

function ecPreviewDot(state) {
  const dot = document.getElementById('ec-preview-live');
  if (!dot) return;
  dot.className = 'ec-live-dot' + (state === 'busy' ? ' busy' : '');
  dot.textContent = state === 'busy' ? '● بيحدّث...' : '● حيّة';
}

/**
 * المعاينة — نفس الـ HTML النهائي اللي هيتبعت بالظبط (من /preview).
 * بتتنده تلقائياً (debounced) مع أي تعديل في المحتوى، أو يدوياً من الزرار.
 * opts.auto = true → من التحديث التلقائي: من غير toasts ومن غير رسائل تحميل مزعجة.
 */
async function previewEmail(opts) {
  const auto = !!(opts && opts.auto === true);
  const content = ecBuildContent();
  if (auto) {
    // تلقائي: مانضغطش على السيرفر طول ما المحتوى لسه ناقص
    if (!content.subject_template || !(content.body_html || '').trim()) return;
  } else if (!ecValidateContent(content)) {
    return;
  }

  const sample = ecSelectedList()[0] || ecAllRecipients[0] || null;
  const sampleBody = sample ? {
    name: sample.name, governorate: sample.governorate, country: sample.country,
    email: sample.email, governorate_ar: sample.governorate_ar,
    name_ar: sample.name_ar, country_ar: sample.country_ar
  } : null;

  const key = JSON.stringify([content, sample ? sample.email : null]);
  if (auto && key === ecLastPreviewKey) return;   // مفيش أي تغيير — مفيش نداء
  ecLastPreviewKey = key;

  const subjEl = document.getElementById('ec-preview-subject');
  const frame = document.getElementById('ec-preview-frame');
  if (!auto && subjEl) subjEl.textContent = 'جاري بناء المعاينة...';
  ecPreviewDot('busy');

  const my = ++ecPreviewReq;
  try {
    const res = await fetch(`${API}/admin/email-campaigns/preview`, {
      method: 'POST', headers,
      body: JSON.stringify({ content, sample: sampleBody })
    });
    if (my !== ecPreviewReq) return;   // تعديل أحدث سبقه
    const data = await res.json();
    if (my !== ecPreviewReq) return;
    if (!res.ok) {
      ecLastPreviewKey = '';
      if (subjEl && !auto) subjEl.textContent = '—';
      if (!auto) showToast(`❌ ${data.detail || 'فشل المعاينة'}`, 'error');
      return;
    }
    if (subjEl) subjEl.textContent = data.subject || '—';
    if (frame) frame.srcdoc = data.html || '';
  } catch (e) {
    ecLastPreviewKey = '';
    if (subjEl && !auto) subjEl.textContent = '—';
    if (!auto) showToast('❌ خطأ شبكة: ' + e.message, 'error');
  } finally {
    if (my === ecPreviewReq) ecPreviewDot('idle');
  }
}

function sendCampaign() {
  const content = ecBuildContent();
  if (!ecValidateContent(content)) return;
  if (ecGetMode() === 'real') {
    const selected = ecSelected.size;
    if (!selected) { showToast('❌ اختار أعضاء الأول', 'error'); return; }
    document.getElementById('ec-confirm-count').textContent = selected;
    document.getElementById('ec-confirm-input').value = '';
    openModal('ec-confirm-modal');
    setTimeout(() => document.getElementById('ec-confirm-input').focus(), 100);
    return;
  }
  ecDoSend('test', null);
}

function confirmRealSend() {
  const phrase = (document.getElementById('ec-confirm-input').value || '').trim();
  if (phrase !== 'GHAWY-OFFICIAL-SEND') { showToast('❌ الجملة مش مظبوطة', 'error'); return; }
  closeModal('ec-confirm-modal');
  ecDoSend('real', phrase);
}

async function ecDoSend(mode, confirmPhrase) {
  const content = ecBuildContent();
  const btn = document.getElementById('ec-send-btn');
  const resultBox = document.getElementById('ec-send-result');
  const campaignId = (document.getElementById('ec-campaign-id').value || '').trim();
  const testEmails = (document.getElementById('ec-test-emails').value || '')
    .split(',').map(s => s.trim()).filter(Boolean);
  const recipients = ecSelectedList().map(r => ({
    name: r.name, email: r.email, phone: r.phone, country: r.country,
    governorate: r.governorate, governorate_ar: r.governorate_ar,
    name_ar: r.name_ar, country_ar: r.country_ar, age: r.age, plan: r.plan
  }));

  const payload = { recipients, content, campaign_id: campaignId, mode, test_emails: testEmails };
  if (confirmPhrase) payload.confirm_phrase = confirmPhrase;

  btn.disabled = true;
  const orig = btn.innerHTML;
  btn.innerHTML = 'جاري الإرسال...';
  resultBox.style.display = 'block';
  resultBox.className = 'ec-result';
  resultBox.innerHTML = 'شغّال...';

  try {
    const res = await fetch(`${API}/admin/email-campaigns/send`, {
      method: 'POST', headers, body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) {
      resultBox.className = 'ec-result err';
      resultBox.innerHTML = `❌ ${escapeHtml(data.detail || 'فشل الإرسال')}`;
      return;
    }
    if (mode === 'test') {
      const fails = (data.failures || []).map(f => `<div>• ${escapeHtml(f[0])}: ${escapeHtml(String(f[1]))}</div>`).join('');
      resultBox.className = 'ec-result ok';
      resultBox.innerHTML = `✅ تم إرسال التست — نجح ${data.success_count}, فشل ${data.fail_count}<br>
        <span style="color:#888;font-size:12px;">راح لـ: ${escapeHtml((data.test_emails_used || []).join(', '))}</span>${fails ? `<div class="ec-fails">${fails}</div>` : ''}`;
      showToast('✅ اتبعت التست', 'success');
    } else if (data.started === false) {
      resultBox.className = 'ec-result ok';
      resultBox.innerHTML = `ℹ️ ${escapeHtml(data.message || '')}`;
    } else {
      resultBox.className = 'ec-result ok';
      resultBox.innerHTML = `🚀 ${escapeHtml(data.message || 'بدأ الإرسال')} <div id="ec-progress" style="margin-top:8px;color:#888;"></div>`;
      showToast('🚀 بدأ الإرسال الحقيقي', 'success');
      ecPollStatus(campaignId, data.queued || 0);
    }
  } catch (e) {
    resultBox.className = 'ec-result err';
    resultBox.innerHTML = `❌ خطأ شبكة: ${escapeHtml(e.message)}`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = orig;
    if (typeof lucide !== 'undefined') setTimeout(() => window.lucide && window.lucide.createIcons(), 10);
  }
}

function ecPollStatus(campaignId, queuedTotal) {
  if (ecStatusTimer) clearInterval(ecStatusTimer);
  const tick = async () => {
    try {
      const res = await fetch(`${API}/admin/email-campaigns/status?campaign_id=${encodeURIComponent(campaignId)}`, { headers });
      if (!res.ok) return;
      const d = await res.json();
      const el = document.getElementById('ec-progress');
      if (el) {
        const total = d.queued_total || queuedTotal || d.processed;
        el.innerHTML = `تم إرسال <b style="color:#D0FA06;">${d.sent}</b>${d.failed ? ` · فشل ${d.failed}` : ''}${total ? ` من ${total}` : ''} ${d.running ? '⏳' : '✅ خلص'}`;
      }
      if (!d.running) { clearInterval(ecStatusTimer); ecStatusTimer = null; }
    } catch (e) { }
  };
  tick();
  ecStatusTimer = setInterval(tick, 4000);
}


// ═══ STAFF PERMISSIONS (owner-only tab) ═══
// الـ owner بيفتح/يقفل تابات لوحة الفريق لكل أدمن لوحده. الشاشة دي بترسم
// الكتالوج اللي السيرفر بيرجعه — أي صلاحية جديدة في permissions.py بتظهر هنا
// لوحدها من غير أي تعديل في الفرونت.

let permCatalog = [];      // [{key,label,label_ar,group}]
let permGroups = {};       // {group: {label,label_ar}}
let permStaff = [];        // [{id,full_name,...,permissions:[]}]
let permDraft = {};        // user_id -> Set(keys) — اللي المستخدم شخبط عليه لسه ماحفظش

async function loadPermissionsTab() {
  const box = document.getElementById('perm-staff-list');
  if (!box) return;
  box.innerHTML = '<div class="perm-empty">Loading...</div>';

  try {
    const res = await authFetch(`${API}/admin/staff`);
    if (res.status === 403) {
      box.innerHTML = '<div class="perm-empty">👑 الشاشة دي للـ owner بس</div>';
      return;
    }
    if (!res.ok) throw new Error('Failed');
    const data = await res.json();

    permCatalog = data.catalog || [];
    permGroups = data.groups || {};
    permStaff = data.staff || [];
    permDraft = {};
    renderPermissionsList();
  } catch (e) {
    box.innerHTML = '<div class="perm-empty" style="color:#ef4444;">❌ مقدرناش نجيب قايمة الفريق</div>';
  }
}

function permDraftFor(userId) {
  if (!permDraft[userId]) {
    const staff = permStaff.find(u => u.id === userId);
    permDraft[userId] = new Set(staff ? staff.permissions : []);
  }
  return permDraft[userId];
}

function permIsDirty(userId) {
  const staff = permStaff.find(u => u.id === userId);
  if (!staff) return false;
  const draft = permDraftFor(userId);
  const saved = new Set(staff.permissions);
  if (draft.size !== saved.size) return true;
  for (const k of draft) if (!saved.has(k)) return true;
  return false;
}

function renderPermissionsList() {
  const box = document.getElementById('perm-staff-list');
  if (!box) return;

  const admins = permStaff.filter(u => !u.is_owner);
  const owners = permStaff.filter(u => u.is_owner);

  const adminsHtml = admins.length ? admins.map(u => renderPermCard(u)).join('') : `
    <div class="perm-empty">مفيش أدمن دلوقتي. اعمل حد أدمن من تاب الأعضاء الأول، وهيظهر هنا.</div>`;

  // الـ owners سطر واحد في الآخر: مفيش حاجة تتظبط ليهم، بس المفروض تعرف مين فيهم.
  const ownersHtml = owners.length ? `
    <div class="perm-card perm-card-owner">
      <div class="perm-owner-note">👑 الـ owners شايفين كل حاجة في اللوحة ومفيش صلاحيات تتشال منهم من هنا:
        ${owners.map(u => `<span class="perm-owner-chip">${escapeHtml(u.full_name || '—')}</span>`).join('')}
      </div>
    </div>` : '';

  box.innerHTML = adminsHtml + ownersHtml;
  if (window.lucide) lucide.createIcons();
}

function renderPermCard(u) {
  const draft = permDraftFor(u.id);
  const order = ['people', 'money', 'content', 'extra'];
  const groups = order.filter(g => permCatalog.some(p => p.group === g));

  const grid = groups.map(g => {
    const items = permCatalog.filter(p => p.group === g).map(p => {
      const on = draft.has(p.key);
      return `
        <label class="perm-item ${on ? 'on' : ''}">
          <input type="checkbox" ${on ? 'checked' : ''}
                 onchange="togglePerm(${u.id}, '${p.key}', this.checked)">
          <span class="perm-item-label">${escapeHtml(p.label_ar || p.label)}</span>
          <span class="perm-item-sub">${escapeHtml(p.label)}</span>
        </label>`;
    }).join('');
    const gl = permGroups[g] || {};
    return `
      <div class="perm-group">
        <div class="perm-group-title">${escapeHtml(gl.label_ar || g)}</div>
        <div class="perm-group-items">${items}</div>
      </div>`;
  }).join('');

  const dirty = permIsDirty(u.id);
  const count = draft.size;

  return `
    <div class="perm-card" id="perm-card-${u.id}">
      <div class="perm-card-head">
        <div class="perm-who">
          <div class="perm-name">${escapeHtml(u.full_name || '—')} <span class="perm-role">Admin</span></div>
          <div class="perm-email">${escapeHtml(u.email || '')}</div>
        </div>
        <div class="perm-head-actions">
          <span class="perm-count">${count} / ${permCatalog.length}</span>
          <button class="perm-btn ghost" onclick="permSelectAll(${u.id}, true)">فتح الكل</button>
          <button class="perm-btn ghost" onclick="permSelectAll(${u.id}, false)">قفل الكل</button>
          <button class="perm-btn save ${dirty ? '' : 'disabled'}"
                  onclick="savePermissions(${u.id})" ${dirty ? '' : 'disabled'}>
            ${dirty ? 'احفظ' : 'متسجّل'}
          </button>
        </div>
      </div>
      ${u.is_default ? '<div class="perm-default-note">لسه على الوضع الافتراضي (تابات الناس بس).</div>' : ''}
      <div class="perm-grid">${grid}</div>
    </div>`;
}

function togglePerm(userId, key, on) {
  const draft = permDraftFor(userId);
  if (on) draft.add(key); else draft.delete(key);
  refreshPermCard(userId);
}

function permSelectAll(userId, on) {
  const draft = permDraftFor(userId);
  draft.clear();
  if (on) permCatalog.forEach(p => draft.add(p.key));
  refreshPermCard(userId);
}

function refreshPermCard(userId) {
  const card = document.getElementById(`perm-card-${userId}`);
  const u = permStaff.find(x => x.id === userId);
  if (!card || !u) return;
  card.outerHTML = renderPermCard(u);
  if (window.lucide) lucide.createIcons();
}

async function savePermissions(userId) {
  const draft = permDraftFor(userId);
  // بترتيب الكتالوج، عشان اللي بيتبعت يبقى نفس اللي السيرفر بيرجعه بالظبط
  const permissions = permCatalog.map(p => p.key).filter(k => draft.has(k));

  const btn = document.querySelector(`#perm-card-${userId} .perm-btn.save`);
  if (btn) { btn.disabled = true; btn.textContent = '...'; }

  try {
    const res = await authFetch(`${API}/admin/staff/${userId}/permissions`, {
      method: 'PUT',
      body: JSON.stringify({ permissions }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed');
    }
    const saved = await res.json();

    const idx = permStaff.findIndex(u => u.id === userId);
    if (idx >= 0) permStaff[idx] = { ...permStaff[idx], ...saved };
    delete permDraft[userId];
    refreshPermCard(userId);
    showToast('✅ اتحفظت — هتشتغل عنده على طول', 'success');
  } catch (e) {
    if (btn) { btn.disabled = false; btn.textContent = 'احفظ'; }
    showToast(`❌ ${e.message || 'مقدرناش نحفظ'}`, 'error');
  }
}
