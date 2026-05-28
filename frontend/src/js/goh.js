(async () => {
  const user = await requireActiveUser();
  if (!user) return;
})();

const token = localStorage.getItem('token');
if (!token) window.location.href = 'login.html';
const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

async function apiFetch(url, opts = {}) {
    opts.headers = { ...headers, ...opts.headers };
    const res = await fetch(API + url, opts);
    if (res.status === 401) { localStorage.removeItem('token'); window.location.href = 'login.html'; }
    if (!res.ok) throw new Error("API Error");
    return res.json();
}

let allGuests = [];
let allSessions = [];
let currentTab = 'all';

function logout() { localStorage.removeItem('token'); window.location.href = 'login.html'; }

async function loadProfile() {
    try {
        const res = await apiFetch('/profile/me');
        const u = res;
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
    const res = await apiFetch('/guests/sessions/upcoming');
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
    const res = await apiFetch('/guests/sessions/past');
    if(Array.isArray(res)) {
      allSessions = res;
      renderSessions(allSessions, 'upcoming-sessions');
      document.querySelector('.section-header h2').textContent = 'Past Sessions';
    }
  } catch(err) {
    console.error("Failed to load past sessions:", err);
  }
}

function updateFeaturedHero(g) {
  document.getElementById('featuredHeroCard').style.display = 'block';
  document.getElementById('heroName').textContent = g.name;
  document.getElementById('heroTitle').textContent = g.title;
  document.getElementById('heroBio').textContent = g.bio || '';
  
  const uiAvatar = `https://ui-avatars.com/api/?name=${encodeURIComponent(g.name)}&background=1a1a1a&color=84cc16&size=200&bold=true`;
  document.getElementById('heroAvatar').src = g.avatar_url || uiAvatar;
  
  document.getElementById('heroTotalSessions').textContent = g.total_sessions;
  
  let attendeesStr = g.total_attendees >= 1000 ? (g.total_attendees/1000).toFixed(1) + 'K+' : g.total_attendees;
  document.getElementById('heroTotalAttendees').textContent = attendeesStr;
  document.getElementById('heroRating').textContent = '⭐ ' + g.rating.toFixed(1);
}

function renderGuests(guests) {
  const container = document.getElementById('featured-guests');
  if(!guests.length) {
    container.innerHTML = '<div style="color:#888; padding:20px;">No guests found.</div>';
    return;
  }
  
  container.innerHTML = guests.map(g => {
    const uiAvatar = `https://ui-avatars.com/api/?name=${encodeURIComponent(g.name)}&background=1a1a1a&color=84cc16&size=200&bold=true`;
    return `
    <div class="guest-card" onclick="viewGuest(${g.id})">
      <div class="guest-avatar-wrap">
        <img class="guest-avatar" src="${g.avatar_url || uiAvatar}" 
             onerror="this.src='./imgs/ghawi-logo.png'" />
      </div>
      <h3 class="guest-name">${g.name}</h3>
      <p class="guest-title">${g.title}</p>
      <p class="guest-bio">${g.bio ? g.bio.substring(0,80) + '...' : ''}</p>
      <button class="btn-view-profile">View Profile</button>
    </div>
  `}).join('');
}

function renderSessions(sessions, containerId) {
  const container = document.getElementById(containerId);
  if(!sessions.length) {
    container.innerHTML = '<div style="color:#888; padding:20px;">No sessions available.</div>';
    return;
  }
  
  container.innerHTML = sessions.map(s => {
    const date = new Date(s.session_date);
    const month = date.toLocaleString('en', {month:'short'}).toUpperCase();
    const day = date.getDate();
    const time = date.toLocaleString('en', {hour:'2-digit', minute:'2-digit'});
    
    return `
      <div class="session-card">
        <div class="session-date-badge">
          <span class="month">${month}</span>
          <span class="day">${day}</span>
        </div>
        <div class="session-info">
          <span class="session-status ${s.status}">${s.status}</span>
          <h4 class="session-title">${s.title}</h4>
          <div class="session-guest">
            ${s.guest_name} · ${s.guest_title}
          </div>
          <div class="session-time">
            ${time} EET
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function switchTab(tab, event) {
  currentTab = tab;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  if(event) {
    event.target.classList.add('active');
  }
  
  const guestHeader = document.querySelectorAll('.section-header h2')[0];
  const sessionsHeader = document.querySelectorAll('.section-header h2')[1];
  
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
  const filtered = category === 'All Categories' 
    ? allGuests 
    : allGuests.filter(g => g.category === category);
  renderGuests(filtered);
}

function viewGuest(id) {
  // In the future, this could open a modal or redirect to a guest profile page
  const g = allGuests.find(x => x.id === id);
  if(g) {
    updateFeaturedHero(g);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

async function openSuggestModal() {
  const name = prompt("Guest Name:");
  if(!name) return;
  const reason = prompt("Why should we invite them?");
  
  try {
    const res = await apiFetch('/guests/suggest', {
      method: 'POST',
      body: JSON.stringify({ name, reason })
    });
    if(res && res.success) {
      alert("Thank you! Your suggestion has been received.");
    }
  } catch(err) {
    alert("Error suggesting guest.");
  }
}

document.addEventListener('DOMContentLoaded', loadPage);

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
