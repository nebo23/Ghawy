// ═══════════════════════════════════════════
//  ADMIN COURSES JS — Lesson CRUD + CF Upload
// ═══════════════════════════════════════════

const token = getToken();
if (!token) window.location.href = 'login.html';
const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

// Get course ID from URL
const urlParams = new URLSearchParams(window.location.search);
const courseId = urlParams.get('id');
if (!courseId) window.location.href = 'courses.html';

let selectedVideoFile = null;
let pollingTimers = {};

// ═══ TOAST ═══
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const toast = document.createElement('div');
  const bg = type === 'error' ? 'rgba(239,68,68,.9)' : type === 'success' ? 'rgba(34,197,94,.9)' : 'rgba(63,143,249,.9)';
  toast.style.cssText = `padding:12px 20px;background:${bg};color:#fff;border-radius:8px;font-size:14px;font-weight:600;box-shadow:0 4px 20px rgba(0,0,0,.3);animation:slideIn .3s;max-width:380px;`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity .3s'; setTimeout(() => toast.remove(), 300); }, 3500);
}

// ═══ API HELPER ═══
async function apiFetch(url, opts = {}) {
  opts.headers = { ...headers, ...opts.headers };
  const res = await fetch(API + url, opts);
  if (res.status === 401) { localStorage.removeItem('token'); window.location.href = 'login.html'; }
  return res;
}

function logout() { localStorage.removeItem('token'); window.location.href = 'login.html'; }

// ═══ LOAD PROFILE ═══
async function loadProfile() {
  try {
    const res = await apiFetch('/profile/me');
    if (!res.ok) return;
    const u = await res.json();
    const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    setTxt('sidebarName', u.full_name);
    setTxt('sidebarBadge', u.badge || 'Member');
    setTxt('topbarName', u.full_name);
    ['sidebarAvatar', 'topbarAvatar'].forEach(id => {
      const el = document.getElementById(id);
      if (el && u.avatar_url) el.innerHTML = `<img src="${u.avatar_url}" alt=""/>`;
    });
  } catch (e) { console.error(e); }
}

// ═══ LOAD COURSE DETAIL ═══
async function loadCourseDetail() {
  try {
    const res = await apiFetch(`/courses/admin/${courseId}`);
    if (!res.ok) throw new Error('Course not found');
    const course = await res.json();

    document.getElementById('courseTitle').textContent = course.title;
    document.getElementById('breadcrumbTitle').textContent = course.title;
    document.getElementById('courseLessonCount').textContent = course.lessons ? course.lessons.length : 0;
    document.getElementById('courseStatus').textContent = course.is_published ? '✅ Published' : '📝 Draft';
    document.getElementById('courseStatus').style.color = course.is_published ? '#22c55e' : '#f59e0b';

    renderLessons(course.lessons || []);
  } catch (e) {
    console.error(e);
    showToast('Failed to load course', 'error');
  }
}

// ═══ RENDER LESSONS TABLE ═══
function renderLessons(lessons) {
  const tbody = document.getElementById('lessonsBody');

  if (!lessons.length) {
    tbody.innerHTML = `
      <tr><td colspan="6">
        <div class="lessons-empty">
          <i class="fa-solid fa-film"></i>
          <p>No lessons yet. Click "Add Lesson" to create one.</p>
        </div>
      </td></tr>`;
    return;
  }

  // Sort by order
  lessons.sort((a, b) => a.order - b.order);

  tbody.innerHTML = lessons.map(l => {
    const statusClass = l.video_status || 'pending';
    const statusLabels = { pending: 'Pending', processing: 'Processing...', ready: 'Ready ✅', error: 'Error ❌' };
    const statusLabel = statusLabels[statusClass] || statusClass;
    const pdfIcon = l.pdf_url ? '📄' : '—';

    return `
    <tr data-lesson-id="${l.id}">
      <td style="color:#555;font-weight:600;">${l.order}</td>
      <td>
        <div style="font-weight:600;color:#fff;">${escapeHtml(l.title)}</div>
        ${l.section_title ? `<div style="font-size:12px;color:#555;margin-top:2px;">${escapeHtml(l.section_title)}</div>` : ''}
      </td>
      <td style="color:#888;">${l.duration_minutes} min</td>
      <td>
        <span class="video-badge ${statusClass}" id="badge-${l.id}">
          <span class="dot"></span> ${statusLabel}
        </span>
      </td>
      <td>${l.pdf_url ? `<a href="${l.pdf_url}" target="_blank" style="color:#f59e0b;text-decoration:none;">📄 View</a>` : '—'}</td>
      <td>
        <div class="lesson-actions">
          ${statusClass === 'processing' || statusClass === 'pending' ? `<button class="lesson-action-btn" onclick="pollStatus(${l.id})" title="Refresh status">🔄</button>` : ''}
          <button class="lesson-action-btn pdf" onclick="uploadPdf(${l.id})" title="Upload PDF">📎 PDF</button>
          <button class="lesson-action-btn" onclick="openEditLessonModal(${l.id}, '${escapeHtml(l.title)}', '${escapeHtml(l.section_title || '')}', ${l.order}, ${l.duration_minutes})" title="Edit">✏️</button>
          <button class="lesson-action-btn danger" onclick="openDeleteModal(${l.id})" title="Delete">🗑️</button>
        </div>
      </td>
    </tr>`;
  }).join('');

  // Start polling for processing videos
  lessons.filter(l => l.video_status === 'processing' || l.video_status === 'pending').forEach(l => {
    startPolling(l.id);
  });

  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

// ═══ ADD LESSON MODAL ═══
function openAddLessonModal() {
  selectedVideoFile = null;
  document.getElementById('lessonTitle').value = '';
  document.getElementById('lessonSection').value = '';
  document.getElementById('lessonOrder').value = '0';
  document.getElementById('lessonDuration').value = '0';
  document.getElementById('selectedFileName').style.display = 'none';
  document.getElementById('uploadProgressWrap').style.display = 'none';
  document.getElementById('addLessonSubmit').disabled = false;
  document.getElementById('addLessonModal').classList.add('active');
}

function closeAddLessonModal() {
  document.getElementById('addLessonModal').classList.remove('active');
}

// ═══ VIDEO FILE SELECTION ═══
const dropZone = document.getElementById('videoDropZone');
const fileInput = document.getElementById('videoFileInput');

if (dropZone) {
  dropZone.addEventListener('click', () => fileInput.click());
  dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      selectedVideoFile = e.dataTransfer.files[0];
      showSelectedFile(selectedVideoFile);
    }
  });
}

if (fileInput) {
  fileInput.addEventListener('change', e => {
    if (e.target.files.length) {
      selectedVideoFile = e.target.files[0];
      showSelectedFile(selectedVideoFile);
    }
  });
}

function showSelectedFile(file) {
  const el = document.getElementById('selectedFileName');
  const sizeMB = (file.size / 1024 / 1024).toFixed(1);
  el.textContent = `✅ ${file.name} (${sizeMB} MB)`;
  el.style.display = 'block';
}

// ═══ SUBMIT ADD LESSON ═══
async function submitAddLesson() {
  const title = document.getElementById('lessonTitle').value.trim();
  if (!title) return showToast('Title is required', 'error');
  if (!selectedVideoFile) return showToast('Please select a video file', 'error');

  const btn = document.getElementById('addLessonSubmit');
  btn.disabled = true;
  btn.textContent = 'Creating...';

  try {
    // 1. Create lesson + get upload URL
    const res = await apiFetch(`/courses/admin/${courseId}/lessons`, {
      method: 'POST',
      body: JSON.stringify({
        title: title,
        section_title: document.getElementById('lessonSection').value.trim() || null,
        order: parseInt(document.getElementById('lessonOrder').value) || 0,
        duration_minutes: parseInt(document.getElementById('lessonDuration').value) || 0,
      }),
    });

    if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Failed'); }
    const data = await res.json();

    showToast('Lesson created! Uploading video...', 'success');

    // 2. Upload video directly to Cloudflare
    if (data.upload_url) {
      btn.textContent = 'Uploading...';
      await uploadVideoToCloudflare(data.upload_url, selectedVideoFile, data.lesson_id);
    }

    closeAddLessonModal();
    loadCourseDetail();
  } catch (e) {
    console.error(e);
    showToast('Error: ' + e.message, 'error');
    btn.disabled = false;
    btn.textContent = 'Create & Upload';
  }
}

// ═══ UPLOAD VIDEO TO CLOUDFLARE ═══
async function uploadVideoToCloudflare(uploadUrl, file, lessonId) {
  const progressWrap = document.getElementById('uploadProgressWrap');
  const progressFill = document.getElementById('uploadProgressFill');
  const progressText = document.getElementById('uploadProgressText');
  progressWrap.style.display = 'block';

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', uploadUrl, true);
    xhr.setRequestHeader('Content-Type', file.type || 'video/mp4');

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 100);
        progressFill.style.width = pct + '%';
        progressText.textContent = pct + '%';
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 400) {
        progressFill.style.width = '100%';
        progressText.textContent = '100% — Processing...';
        showToast('Video uploaded! Processing on Cloudflare...', 'success');
        // Start polling for status
        startPolling(lessonId);
        resolve();
      } else {
        showToast('Upload failed: ' + xhr.statusText, 'error');
        reject(new Error(xhr.statusText));
      }
    };

    xhr.onerror = () => {
      showToast('Upload network error', 'error');
      reject(new Error('Network error'));
    };

    xhr.send(file);
  });
}

// ═══ POLL VIDEO STATUS ═══
function startPolling(lessonId) {
  if (pollingTimers[lessonId]) return;
  pollingTimers[lessonId] = setInterval(() => pollStatus(lessonId), 3000);
}

async function pollStatus(lessonId) {
  try {
    const res = await apiFetch(`/courses/admin/lessons/${lessonId}/status`);
    if (!res.ok) return;
    const data = await res.json();

    const badge = document.getElementById(`badge-${lessonId}`);
    if (badge) {
      badge.className = `video-badge ${data.status}`;
      const labels = { pending: 'Pending', processing: 'Processing...', ready: 'Ready ✅', error: 'Error ❌' };
      badge.innerHTML = `<span class="dot"></span> ${labels[data.status] || data.status}`;
    }

    if (data.status === 'ready' || data.status === 'error') {
      clearInterval(pollingTimers[lessonId]);
      delete pollingTimers[lessonId];
      if (data.status === 'ready') showToast('Video is ready! ✅', 'success');
      if (data.status === 'error') showToast('Video processing failed ❌', 'error');
    }
  } catch (e) { console.error('Poll error:', e); }
}

// ═══ EDIT LESSON MODAL ═══
function openEditLessonModal(id, title, section, order, duration) {
  document.getElementById('editLessonId').value = id;
  document.getElementById('editLessonTitle').value = title;
  document.getElementById('editLessonSection').value = section;
  document.getElementById('editLessonOrder').value = order;
  document.getElementById('editLessonDuration').value = duration;
  document.getElementById('editLessonModal').classList.add('active');
}

function closeEditLessonModal() {
  document.getElementById('editLessonModal').classList.remove('active');
}

async function submitEditLesson() {
  const id = document.getElementById('editLessonId').value;
  try {
    const res = await apiFetch(`/courses/admin/lessons/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({
        title: document.getElementById('editLessonTitle').value.trim(),
        section_title: document.getElementById('editLessonSection').value.trim() || null,
        order: parseInt(document.getElementById('editLessonOrder').value) || 0,
        duration_minutes: parseInt(document.getElementById('editLessonDuration').value) || 0,
      }),
    });
    if (!res.ok) throw new Error('Failed to update');
    showToast('Lesson updated ✅', 'success');
    closeEditLessonModal();
    loadCourseDetail();
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}

// ═══ DELETE LESSON ═══
function openDeleteModal(id) {
  document.getElementById('deleteLessonId').value = id;
  document.getElementById('confirmDeleteModal').classList.add('active');
}

function closeDeleteModal() {
  document.getElementById('confirmDeleteModal').classList.remove('active');
}

async function confirmDeleteLesson() {
  const id = document.getElementById('deleteLessonId').value;
  try {
    const res = await apiFetch(`/courses/admin/lessons/${id}`, { method: 'DELETE' });
    if (!res.ok && res.status !== 204) throw new Error('Failed to delete');
    showToast('Lesson deleted ✅', 'success');
    closeDeleteModal();
    loadCourseDetail();
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}

// ═══ PDF UPLOAD ═══
async function uploadPdf(lessonId) {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.pdf';
  input.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    showToast('Getting upload URL...', 'info');

    try {
      // 1. Get presigned URL
      const res = await apiFetch(`/courses/admin/lessons/${lessonId}/pdf`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to get upload URL');
      const data = await res.json();

      // 2. Upload to R2
      const uploadRes = await fetch(data.upload_url, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/pdf' },
        body: file,
      });
      if (!uploadRes.ok) throw new Error('Upload failed');

      // 3. Save PDF URL to lesson
      const patchRes = await apiFetch(`/courses/admin/lessons/${lessonId}`, {
        method: 'PATCH',
        body: JSON.stringify({ pdf_url: data.public_url }),
      });
      if (!patchRes.ok) throw new Error('Failed to save PDF URL');

      showToast('PDF uploaded ✅', 'success');
      loadCourseDetail();
    } catch (e) {
      showToast('PDF upload error: ' + e.message, 'error');
    }
  };
  input.click();
}

// ═══ HAMBURGER ═══
const hb = document.getElementById('hamburgerBtn');
const sb = document.getElementById('dashSidebar');
const ov = document.getElementById('sidebarOverlay');
if (hb) hb.addEventListener('click', () => { sb.classList.toggle('open'); ov.classList.toggle('visible'); });
if (ov) ov.addEventListener('click', () => { sb.classList.remove('open'); ov.classList.remove('visible'); });

// ═══ INIT ═══
loadProfile();
loadCourseDetail();
