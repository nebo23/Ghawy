/**
 * Build With Me (Live) - Frontend Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    initBWM();
});

let liveSocket = null;
let currentTab = 'live';

async function initBWM() {
    setupTabs();
    await loadSessions();
    setupCalendar();
    loadTopProjects();
    connectLiveSocket();
}

// --- TABS ---
function setupTabs() {
    const tabs = document.querySelectorAll('.bwm-tabs .tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentTab = tab.dataset.tab;
            loadSessions();
        });
    });
}

// --- DATA FETCHING ---
async function fetchSessions(status) {
    try {
        let url = `/api/live-sessions${status ? '?status_filter=' + status : ''}`;
        if (status === 'booked') {
            url = '/api/live-sessions/booked';
        }
        // In a real scenario, use authenticated fetch
        const res = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
        });
        if (!res.ok) return [];
        return await res.json();
    } catch (e) {
        console.error('Failed to fetch sessions', e);
        return [];
    }
}

async function loadSessions() {
    const container = document.getElementById('bwmTabContent');
    container.innerHTML = `<div class="bwm-loading"><i class="fa-solid fa-circle-notch fa-spin"></i> Loading...</div>`;

    // Map tab to status
    let statusFilter = currentTab;
    if (currentTab === 'live' || currentTab === 'upcoming' || currentTab === 'ended' || currentTab === 'booked') {
        // valid
    } else if (currentTab === 'past' || currentTab === 'recordings') {
        statusFilter = 'ended';
    }

    const sessions = await fetchSessions(statusFilter);
    renderSessions(sessions, currentTab, container);
}

// --- RENDERING ---
function renderSessions(sessions, tab, container) {
    if (!sessions || sessions.length === 0) {
        container.innerHTML = `
            <div style="text-align:center; padding: 60px 0; color: #666;">
                <i class="fa-regular fa-folder-open" style="font-size: 2rem; margin-bottom: 12px;"></i>
                <p>No ${tab} sessions found.</p>
            </div>
        `;
        return;
    }

    let html = '';

    if (tab === 'live') {
        sessions.forEach(s => {
            html += `
                <div class="section-title">
                    <span><span style="color:#3f8ff9;">●</span> 1 Live Session</span>
                </div>
                <div class="live-session-card">
                    <div class="badge-live">Live Now</div>
                    <div class="live-image-col">
                        <img src="${s.thumbnail_url || 'https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=800&q=80'}" alt="Session Thumbnail" onerror="this.src='./imgs/ghawi-logo.png'">
                    </div>
                    <div class="live-info-col">
                        <span class="difficulty-badge">${s.difficulty}</span>
                        <h2>${s.title}</h2>
                        <p class="live-desc">${s.description || 'Join us for this live building session.'}</p>
                        
                        <div class="instructor-row">
                            <img src="${s.instructor?.avatar_url || 'https://ui-avatars.com/api/?name=' + (s.instructor?.name || 'I')}" alt="Instructor">
                            <div>
                                <div class="instructor-name">${s.instructor?.name || 'Instructor'}</div>
                                <div class="instructor-title"><i class="fa-solid fa-circle-check" style="color:#3f8ff9;"></i> Verified Expert</div>
                            </div>
                        </div>

                        <div class="live-meta">
                            <span><i class="fa-solid fa-users"></i> <span id="viewers-${s.id}">${s.current_viewers || 0}</span> watching</span>
                            <span><i class="fa-regular fa-clock"></i> Live Now</span>
                            <span><i class="fa-regular fa-comments"></i> Q&A Open</span>
                        </div>

                        <div class="what-we-build">
                            <h4>What We'll Build</h4>
                            <ul>
                                <li><i class="fa-regular fa-circle-check"></i> Real-world project from scratch</li>
                                <li><i class="fa-regular fa-circle-check"></i> Best practices & architecture</li>
                                <li><i class="fa-regular fa-circle-check"></i> Live deployment</li>
                            </ul>
                        </div>

                        <button class="btn-primary" onclick="joinLive(${s.id})"><i class="fa-solid fa-podcast"></i> Join Live Session</button>
                    </div>
                </div>
            `;
        });
    } else {
        html += `<div class="section-title"><span>${tab === 'upcoming' ? 'Upcoming Sessions' : 'Sessions'}</span></div>`;
        html += `<div class="upcoming-list">`;
        sessions.forEach(s => {
            const startDate = new Date(s.start_time);
            const day = startDate.getDate();
            const month = startDate.toLocaleString('en-US', { month: 'short' }).toUpperCase();
            const time = startDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            html += `
                <div class="upcoming-card">
                    <div class="date-block">
                        <div class="day">${day}</div>
                        <div class="month">${month}</div>
                    </div>
                    <div class="session-details">
                        <span class="difficulty-badge" style="margin-bottom:8px;">${s.difficulty || 'ALL LEVELS'}</span>
                        <h3>${s.title}</h3>
                        <p class="session-desc">${s.description?.substring(0, 80) || ''}...</p>
                        <div class="instructor-mini">
                            <img src="${s.instructor?.avatar_url || 'https://ui-avatars.com/api/?name=I'}" alt="">
                            <span>${s.instructor?.name || 'Instructor'}</span>
                        </div>
                    </div>
                    <div>
                        <div class="session-time">${time} EET</div>
                        ${tab === 'upcoming' ? 
                            `<button class="btn-reminder" onclick="toggleReminder(${s.id}, this)"><i class="fa-regular fa-bell"></i> Remind Me</button>` : 
                            `<button class="btn-outline-accent" onclick="viewRecording(${s.id})">View Recording</button>`
                        }
                    </div>
                </div>
            `;
        });
        html += `</div>`;
    }

    container.innerHTML = html;
}

// --- ACTIONS ---
async function toggleReminder(sessionId, btn) {
    try {
        const res = await fetch(`/api/live-sessions/${sessionId}/reminder`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        if (res.ok) {
            const data = await res.json();
            if (data.reminder_active) {
                btn.classList.add('active');
                btn.innerHTML = `<i class="fa-solid fa-bell"></i> Reminder Set`;
            } else {
                btn.classList.remove('active');
                btn.innerHTML = `<i class="fa-regular fa-bell"></i> Remind Me`;
            }
        }
    } catch (e) {
        console.error(e);
    }
}

function joinLive(sessionId) {
    alert("Redirecting to live room...");
    // window.location.href = `/live-room.html?id=${sessionId}`;
}

function viewRecording(sessionId) {
    alert("Opening recording...");
}

// --- RIGHT SIDEBAR WIDGETS ---
function setupCalendar() {
    const daysContainer = document.getElementById('calendarDays');
    let html = '';
    const days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];
    const start = 20;
    
    for(let i=0; i<7; i++) {
        const active = i === 2 ? 'active' : '';
        html += `
            <div class="cal-day ${active}">
                <span class="name">${days[i]}</span>
                <span class="num">${start + i}</span>
            </div>
        `;
    }
    daysContainer.innerHTML = html;

    // Hardcode schedule items for demo
    const scheduleContainer = document.getElementById('scheduleList');
    scheduleContainer.innerHTML = `
        <div class="schedule-item live">
            <div class="schedule-status live">LIVE NOW</div>
            <div class="schedule-title">Building AI Automations From Scratch</div>
            <div class="schedule-meta">
                <div class="instructor-mini">
                    <img src="https://ui-avatars.com/api/?name=MH" alt="">
                    <span>Mohamed Hakim</span>
                </div>
                <button class="btn-icon-sm"><i class="fa-solid fa-users"></i></button>
            </div>
        </div>
        <div class="schedule-item">
            <div class="schedule-status">8:00 PM</div>
            <div class="schedule-title">Build an AI Agent That Works For You</div>
            <div class="schedule-meta">
                <div class="instructor-mini">
                    <img src="https://ui-avatars.com/api/?name=AA" alt="">
                    <span>Ali Abdaal</span>
                </div>
                <button class="btn-icon-sm"><i class="fa-regular fa-bell"></i></button>
            </div>
        </div>
    `;
}

function loadTopProjects() {
    const container = document.getElementById('topProjectsList');
    container.innerHTML = `
        <div class="project-item">
            <div class="project-rank">1</div>
            <div class="project-icon"><i class="fa-solid fa-robot"></i></div>
            <div class="project-info">
                <div class="project-title">AI Lead Generation Bot</div>
                <div class="project-author">Built by Community</div>
            </div>
            <div class="project-rating">
                <i class="fa-solid fa-star"></i> 4.9
            </div>
        </div>
        <div class="project-item">
            <div class="project-rank">2</div>
            <div class="project-icon"><i class="fa-solid fa-chart-pie"></i></div>
            <div class="project-info">
                <div class="project-title">Smart Data Analyzer</div>
                <div class="project-author">Built by Mostafa</div>
            </div>
            <div class="project-rating">
                <i class="fa-solid fa-star"></i> 4.8
            </div>
        </div>
        <div class="project-item">
            <div class="project-rank">3</div>
            <div class="project-icon"><i class="fa-solid fa-pen-nib"></i></div>
            <div class="project-info">
                <div class="project-title">Content Creation Engine</div>
                <div class="project-author">Built by Nourhan</div>
            </div>
            <div class="project-rating">
                <i class="fa-solid fa-star"></i> 4.9
            </div>
        </div>
    `;
}

// --- WEBSOCKET ---
function connectLiveSocket() {
    const token = localStorage.getItem('token');
    if (!token) return;

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Assume backend is on port 8000 for local dev
    const wsUrl = `${wsProtocol}//127.0.0.1:8000/api/live-sessions/ws/${token}`;
    
    liveSocket = new WebSocket(wsUrl);

    liveSocket.onopen = () => {
        console.log("Connected to Live WS");
        // We could join sessions based on what is displayed on the screen
        // But for this demo, we can just listen to broadcasts.
    };

    liveSocket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.event === "viewer_count") {
                const el = document.getElementById(`viewers-${data.session_id}`);
                if (el) {
                    el.innerText = data.count;
                }
            }
        } catch (e) {
            console.error("WS error", e);
        }
    };

    liveSocket.onclose = () => {
        console.log("Disconnected from Live WS. Reconnecting in 5s...");
        setTimeout(connectLiveSocket, 5000);
    };
}
