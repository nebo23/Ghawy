const token = localStorage.getItem('token');
if (!token) { localStorage.removeItem('user'); window.location.href = '/login'; }
const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

async function apiFetch(url, opts = {}) {
    opts.headers = { ...headers, ...opts.headers };
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10s timeout
    try {
        const res = await fetch(API + url, { ...opts, signal: controller.signal });
        clearTimeout(timeoutId);
        if (res.status === 401) { localStorage.removeItem('token'); localStorage.removeItem('user'); window.location.href = '/login'; }
        if (!res.ok) throw new Error("API Error");
        return res.json();
    } catch (err) {
        clearTimeout(timeoutId);
        throw err;
    }
}

let allGuests = [];
let allSessions = [];
let currentTab = 'all';

function logout() { localStorage.removeItem('token'); localStorage.removeItem('user'); window.location.href = '/login'; }

async function loadProfile() {
    try {
        const res = await apiFetch('/profile/me');
        const u = res;
        const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        setTxt('sidebarName', u.full_name);
        setTxt('topbarName', u.full_name);
        setTxt('dropdownName', u.full_name);
        
        // Update Badge
        const badgeLabel = u.badge || 'Member';
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
    } catch (e) { console.error("Profile error:", e); }
}

async function loadPage() {
  try {
    loadProfile();
    await Promise.all([
      loadStats(),
      loadFeaturedGuests(),
      loadUpcomingSessions(),
    ]);
  } catch (err) {
    console.error("Error loading GOH page:", err);
  }
}

async function loadStats() {
  try {
    const res = await apiFetch('/guests/stats');
    if(res && res.total_guests !== undefined) {
      document.getElementById('stat-guests').textContent = res.total_guests;
      document.getElementById('stat-sessions').textContent = res.sessions_this_month;
      
      let attendeesStr = res.total_attendees >= 1000 ? (res.total_attendees/1000).toFixed(1) + 'K' : res.total_attendees;
      document.getElementById('stat-attendees').textContent = attendeesStr;
      document.getElementById('stat-rating').textContent = res.avg_rating.toFixed(1);
      
      // Calculate derived hours (mock for demo if not provided directly)
      const hours = res.total_hours || (res.total_attendees * 1.5) || 0;
      const hoursStr = hours >= 1000 ? (hours/1000).toFixed(1) + 'K' : Math.floor(hours);
      if (document.getElementById('stat-hours')) document.getElementById('stat-hours').textContent = hoursStr;
      
      // Update community impact sidebar
      if (document.getElementById('impactGuests')) document.getElementById('impactGuests').textContent = res.total_guests;
      if (document.getElementById('impactSessions')) document.getElementById('impactSessions').textContent = res.sessions_this_month * 5 || res.sessions_this_month;
      if (document.getElementById('impactHours')) document.getElementById('impactHours').textContent = hoursStr;
      if (document.getElementById('impactRating')) document.getElementById('impactRating').textContent = res.avg_rating.toFixed(1);
    }
  } catch (err) {
    console.error("Failed to load stats:", err);
  }
}

async function loadFeaturedGuests() {
  try {
    const res = await apiFetch('/guests/');
    if(Array.isArray(res)) {
      allGuests = res;
      renderGuests(allGuests);
      
      // Set first featured guest in hero
      const featured = allGuests.find(g => g.is_featured);
      if (featured) {
        updateFeaturedHero(featured);
      } else if (allGuests.length > 0) {
        updateFeaturedHero(allGuests[0]);
      }
    }
  } catch (err) {
    console.error("Failed to load guests:", err);
  }
}

async function loadUpcomingSessions() {
  try {
    const res = await apiFetch('/guests/sessions/?status=upcoming');
    if(Array.isArray(res)) {
      allSessions = res;
      renderSessions(allSessions, 'upcoming-sessions');
    }
  } catch(err) {
    console.error("Failed to load upcoming sessions:", err);
  }
}

async function loadPastSessions() {
  try {
    const res = await apiFetch('/guests/sessions/?status=past');
    if(Array.isArray(res)) {
      allSessions = res;
      renderSessions(allSessions, 'upcoming-sessions');
      document.querySelector('.section-title-wrap h2').textContent = 'Past Sessions';
    }
  } catch(err) {
    console.error("Failed to load past sessions:", err);
  }
}

function updateFeaturedHero(g) {
  // Desktop Sticky Sidebar Hero
  const sidebarHero = document.getElementById('featuredHeroCard');
  if (sidebarHero) {
      sidebarHero.style.display = 'block';
      document.getElementById('heroName').innerHTML = `${g.name}`;
      document.getElementById('heroTitle').textContent = g.title;
      document.getElementById('heroBio').textContent = g.bio || '';
      if(document.getElementById('heroCompany')) {
          document.getElementById('heroCompany').innerHTML = `<i data-lucide="building-2" style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:4px;"></i> <span>${g.company || 'Industry Leader'}</span>`;
      }
      
      let finalAvatar = '';
      if (g.avatar_url) {
        finalAvatar = g.avatar_url.startsWith('http') ? g.avatar_url : API + g.avatar_url;
      } else {
        finalAvatar = `https://ui-avatars.com/api/?name=${encodeURIComponent(g.name)}&background=${(g.avatar_color || '#c1ff11').replace('#','')}&color=fff&size=200&bold=true`;
      }
      document.getElementById('heroAvatar').src = finalAvatar;
      document.getElementById('heroTotalSessions').textContent = g.sessions_count || 0;
      
      let attendeesStr = g.attendees_count >= 1000 ? (g.attendees_count/1000).toFixed(1) + 'K+' : (g.attendees_count || 0);
      document.getElementById('heroTotalAttendees').textContent = attendeesStr;
      document.getElementById('heroRating').innerHTML = `<i data-lucide="star" style="width:14px;height:14px;color:#facc15;fill:#facc15;"></i> ${(g.rating || 0).toFixed(1)}`;
  }
  
  // Mobile Hero
  const mobileHero = document.getElementById('heroMobileCard');
  if (mobileHero) {
      mobileHero.style.display = 'block';
      document.getElementById('heroMobileName').innerHTML = `${g.name}`;
      document.getElementById('heroMobileTitle').textContent = g.title;
      document.getElementById('heroMobileBio').textContent = g.bio ? g.bio.substring(0,100) + '...' : '';
      if(document.getElementById('heroMobileCompany')) {
          document.getElementById('heroMobileCompany').innerHTML = `<i data-lucide="building-2" style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:4px;"></i> <span>${g.company || 'Industry Leader'}</span>`;
      }
      
      let finalAvatar = '';
      if (g.avatar_url) {
        finalAvatar = g.avatar_url.startsWith('http') ? g.avatar_url : API + g.avatar_url;
      } else {
        finalAvatar = `https://ui-avatars.com/api/?name=${encodeURIComponent(g.name)}&background=${(g.avatar_color || '#c1ff11').replace('#','')}&color=fff&size=200&bold=true`;
      }
      document.getElementById('heroMobileAvatar').src = finalAvatar;
      document.getElementById('heroMobileTotalSessions').textContent = g.sessions_count || 0;
      
      let attendeesStr = g.attendees_count >= 1000 ? (g.attendees_count/1000).toFixed(1) + 'K+' : (g.attendees_count || 0);
      document.getElementById('heroMobileTotalAttendees').textContent = attendeesStr;
      document.getElementById('heroMobileRating').innerHTML = `<i data-lucide="star" style="width:14px;height:14px;color:#facc15;fill:#facc15;"></i> ${(g.rating || 0).toFixed(1)}`;
  }

  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function renderGuests(guests) {
  const container = document.getElementById('featured-guests');
  if(!guests.length) {
    container.innerHTML = '<div style="color:#888; padding:20px;">No guests found.</div>';
    return;
  }
  
  container.innerHTML = guests.map(g => {
    let finalAvatar = '';
    if (g.avatar_url) {
      finalAvatar = g.avatar_url.startsWith('http') ? g.avatar_url : API + g.avatar_url;
    } else {
      let initials = g.avatar_initials;
      if (!initials) {
        initials = g.name.substring(0,2).toUpperCase();
      }
      const color = g.avatar_color || '#c1ff11';
      finalAvatar = `https://ui-avatars.com/api/?name=${encodeURIComponent(initials)}&background=${color.replace('#','')}&color=fff&size=200&bold=true`;
    }
    
    return `
    <div class="guest-card glass-card" onclick="viewGuest(${g.id})">
      <div class="guest-avatar-wrap">
        <img class="guest-avatar" src="${finalAvatar}" style="object-fit:cover;"
             onerror="this.onerror=null; this.src='./imgs/community-logo.png'" />
      </div>
      <h3 class="guest-name">${g.name}</h3>
      <p class="guest-title">${g.title}</p>
      <div class="guest-company"><i data-lucide="building-2" style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:4px;"></i> <span>${g.company || 'Industry Leader'}</span></div>
      
      <div class="guest-stats-mini">
        <span><i data-lucide="users" style="width:14px;height:14px;"></i> ${g.attendees_count || 0}</span>
        <span><i data-lucide="star" style="width:14px;height:14px;color:#facc15;"></i> ${(g.rating || 0).toFixed(1)}</span>
      </div>
      
      <button class="btn-view-profile">View Profile</button>
    </div>
  `}).join('');
  
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function renderSessions(sessions, containerId) {
  const container = document.getElementById(containerId);
  if(!sessions.length) {
    container.innerHTML = `
      <div class="empty-state glass-card">
        <i data-lucide="calendar-x" class="empty-state-icon"></i>
        <h3>No sessions scheduled</h3>
        <p>New expert sessions are added regularly.</p>
      </div>`;
    if (window.lucide) window.lucide.createIcons();
    return;
  }
  
  container.innerHTML = sessions.map(s => {
    const date = new Date(s.session_date);
    const month = date.toLocaleString('en', {month:'short'}).toUpperCase();
    const day = date.getDate();
    const time = date.toLocaleString('en', {hour:'2-digit', minute:'2-digit'});
    
    // Status Logic
    let statusClass = s.status === 'live' ? 'live' : (s.status === 'completed' ? 'completed' : 'upcoming');
    let statusLabel = s.status === 'live' ? 'Live Now' : (s.status === 'completed' ? 'Recorded' : 'Upcoming');
    
    let guestAvatar = s.guest_avatar_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(s.guest_name)}&background=84cc16&color=fff`;
    if (guestAvatar.startsWith('/')) guestAvatar = API + guestAvatar;

    let coverImage = s.cover_url || `./imgs/community-logo.png`;
    
    return `
      <div class="session-card glass-card">
        <div class="session-cover-wrap">
        <img class="session-cover" src="${coverImage}" alt="Session Cover" onerror="this.onerror=null; this.src='./imgs/community-logo.png'" />
        </div>
        <div class="session-content">
            <div class="session-header-row">
                <span class="session-status ${statusClass}">${statusLabel}</span>
                <div class="session-date">
                    <span class="month">${month}</span>
                    <span class="day">${day}</span>
                </div>
            </div>
            
            <h4 class="session-title">${s.title}</h4>
            
            <div class="session-host-row">
                <img class="session-host-avatar" src="${guestAvatar}" alt="${s.guest_name}" />
                <div class="session-host-info">
                    <span class="name">${s.guest_name}</span>
                    <span class="title">${s.guest_title}</span>
                </div>
            </div>
            
            <div class="session-footer">
                <div class="session-meta">
                    <span><i data-lucide="clock" style="width:14px;height:14px;"></i> ${time} EET</span>
                    <span><i data-lucide="users" style="width:14px;height:14px;"></i> ${s.expected_attendees || s.attendees_count || 0} attending</span>
                </div>
                <button class="btn-reserve">Reserve Seat</button>
            </div>
        </div>
      </div>
    `;
  }).join('');
  
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function switchTab(tab, event) {
  currentTab = tab;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  if(event) {
    event.target.classList.add('active');
  }
  
  const guestHeader = document.querySelectorAll('.section-title-wrap h2')[0];
  const sessionsHeader = document.querySelectorAll('.section-title-wrap h2')[1];
  
  if (tab === 'all') {
    renderGuests(allGuests);
    loadUpcomingSessions();
    guestHeader.textContent = 'Featured Guests';
    sessionsHeader.textContent = 'Upcoming Sessions';
  } else if (tab === 'upcoming') {
    loadUpcomingSessions();
    guestHeader.textContent = 'Featured Guests';
    sessionsHeader.textContent = 'Upcoming Sessions';
  } else if (tab === 'past') {
    loadPastSessions();
    sessionsHeader.textContent = 'Past Sessions';
  } else if (tab === 'categories') {
    // Focus on the category select
    document.querySelector('.category-filter').focus();
  }
}

function filterByCategory(category) {
  if (!category || category === 'All Categories') {
    renderGuests(allGuests);
    return;
  }
  const searchCat = category.trim().toLowerCase();
  const filtered = allGuests.filter(g => (g.category || '').trim().toLowerCase() === searchCat);
  renderGuests(filtered);
}

function viewGuest(id) {
  const g = allGuests.find(x => x.id === id);
  if(g) {
    updateFeaturedHero(g);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

function openSuggestModal() {
  document.getElementById('suggestName').value = '';
  document.getElementById('suggestReason').value = '';
  const modal = document.getElementById('suggestModal');
  modal.style.display = 'flex';
  if (window.lucide) window.lucide.createIcons();
  // Close when clicking outside
  modal.onclick = function(e) {
    if (e.target === modal) closeSuggestModal();
  };
}
window.openSuggestModal = openSuggestModal;

function closeSuggestModal() {
  document.getElementById('suggestModal').style.display = 'none';
}
window.closeSuggestModal = closeSuggestModal;

async function submitSuggestion() {
  const name = document.getElementById('suggestName').value.trim();
  if(!name) {
      showToast("Please enter a guest name", 'error');
      return;
  }
  const reason = document.getElementById('suggestReason').value.trim();
  
  try {
    const res = await apiFetch('/guests/suggest', {
      method: 'POST',
      body: JSON.stringify({ name, reason })
    });
    if(res && res.success) {
      closeSuggestModal();
      showToast("Thank you! Your suggestion has been received.", "success");
    }
  } catch(err) {
    showToast("Error suggesting guest.", "error");
  }
}
window.submitSuggestion = submitSuggestion;

// Ensure showToast is defined or fallback
function showToast(msg, type='info') {
    if (typeof window.showToast === 'function') {
        window.showToast(msg, type);
    } else {
        alert(msg);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadPage();
    const btn = document.getElementById('suggestGuestBtn');
    if (btn) btn.addEventListener('click', openSuggestModal);
});

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

function scrollGuests(direction) {
    const container = document.getElementById('featured-guests');
    if (container) {
        const scrollAmount = 300; // Scroll by roughly one and a half cards
        container.scrollBy({ left: direction * scrollAmount, behavior: 'smooth' });
    }
}
