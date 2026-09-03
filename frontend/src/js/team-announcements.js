/* ═══ COMMUNITY ANNOUNCEMENTS — in-app member campaigns ═══
 *
 * The counterpart to the Emails tab: same idea, different delivery. A campaign
 * here lands in the member's notification bell while they are on the site,
 * not in their inbox.
 *
 * Loaded AFTER team.js, which is where authFetch / showToast / escapeHtml /
 * API come from — this file deliberately re-declares none of them, so there is
 * one implementation of each rather than a second copy drifting out of sync.
 *
 * Two rules the UI enforces alongside the server:
 *   • The audience is never sent as a list of ids. The filter goes up, the
 *     server resolves who that is. A client-supplied id list would let anyone
 *     with this tab message any account.
 *   • A real send needs the confirm phrase typed exactly. The test button
 *     sends to the operator alone and is always one click away, so there is
 *     never a reason to "just try it live".
 */

const AN_CONFIRM_PHRASE = 'GHAWY-OFFICIAL-SEND';

let anCampaigns = [];
let anCurrent = null;      // the campaign being edited (null = new, unsaved)
let anAudienceTimer = null;
let anFacetsLoaded = false;
let anSending = false;

const AN_TYPE_META = {
  info:    { icon: 'info',          color: '#3f8ff9', label: 'معلومة' },
  success: { icon: 'check-circle',  color: '#22c55e', label: 'خبر كويس' },
  warning: { icon: 'alert-triangle', color: '#f59e0b', label: 'تنبيه' },
  promo:   { icon: 'gift',          color: '#c1ff11', label: 'عرض' },
};

function anTypeMeta(t) { return AN_TYPE_META[t] || AN_TYPE_META.info; }

// ═══ ENTRY ═══

async function loadAnnouncementsTab() {
  anShowListView();
  await loadAnnouncementsList();
}

function anShowListView() {
  const l = document.getElementById('an-list-view');
  const e = document.getElementById('an-editor-view');
  if (l) l.style.display = 'block';
  if (e) e.style.display = 'none';
}

function anShowEditorView() {
  const l = document.getElementById('an-list-view');
  const e = document.getElementById('an-editor-view');
  if (l) l.style.display = 'none';
  if (e) e.style.display = 'block';
  if (window.lucide) lucide.createIcons();
}

function anBackToList() {
  anShowListView();
  loadAnnouncementsList();
}

// ═══ LIST ═══

async function loadAnnouncementsList() {
  const grid = document.getElementById('an-grid');
  if (!grid) return;
  grid.innerHTML = '<div class="ec-empty">جاري التحميل...</div>';

  try {
    const res = await authFetch(`${API}/admin/announcements`);
    if (res.status === 403) {
      grid.innerHTML = '<div class="ec-empty">🔒 مالكش صلاحية الحملات دي</div>';
      return;
    }
    if (!res.ok) throw new Error('failed');
    anCampaigns = await res.json();

    if (!anCampaigns.length) {
      grid.innerHTML = `<div class="ec-empty">
        لسه مفيش حملات. اضغط "حملة جديدة" عشان تبدأ أول واحدة.</div>`;
      return;
    }

    grid.innerHTML = anCampaigns.map(anCardHTML).join('');
    if (window.lucide) lucide.createIcons();
  } catch (e) {
    grid.innerHTML = '<div class="ec-empty" style="color:#ef4444">❌ مقدرناش نجيب الحملات</div>';
  }
}

function anCardHTML(c) {
  const meta = anTypeMeta(c.type);
  const sent = c.status === 'sent';

  // "sending" used to fall through to the draft branch, so a campaign that was
  // mid-fan-out showed as "مسودة" until somebody refreshed. The send returns
  // before the fan-out finishes now, so this state is the normal one to be in
  // for a second or two — it needs its own badge.
  const statusBadge = sent
    ? `<span class="an-status-badge sent">اتبعتت</span>`
    : c.status === 'failed'
      ? `<span class="an-status-badge failed">فشلت</span>`
      : c.status === 'sending'
        ? `<span class="an-status-badge sending">بتتبعت دلوقتي…</span>`
        : `<span class="an-status-badge draft">مسودة</span>`;

  // Stats only mean something once it has gone out — a draft showing "0% read"
  // reads like a failure rather than "not sent yet".
  const stats = sent ? `
    <div class="an-card-stats">
      <div class="an-stat"><span class="an-stat-num">${c.delivered}</span><span class="an-stat-lbl">اتسلّمت</span></div>
      <div class="an-stat"><span class="an-stat-num">${c.read}</span><span class="an-stat-lbl">اتقرت</span></div>
      <div class="an-stat"><span class="an-stat-num" style="color:${meta.color}">${c.read_rate}%</span><span class="an-stat-lbl">نسبة القراءة</span></div>
    </div>` : '';

  const actions = sent
    ? `<button class="ec-mini" onclick="anDuplicate(${c.id})"><i data-lucide="copy" style="width:13px;height:13px;"></i> نسخة</button>`
    : `<button class="ec-mini" onclick="anOpenCampaign(${c.id})"><i data-lucide="pen-line" style="width:13px;height:13px;"></i> تعديل</button>
       <button class="ec-mini danger" onclick="anDelete(${c.id})"><i data-lucide="trash-2" style="width:13px;height:13px;"></i> مسح</button>`;

  return `
    <div class="an-card">
      <div class="an-card-head">
        <span class="an-card-dot" style="background:${meta.color}"></span>
        <div class="an-card-title">${escapeHtml(c.title || '(من غير عنوان)')}</div>
        ${statusBadge}
      </div>
      <div class="an-card-body">${escapeHtml((c.body || '').slice(0, 140))}${(c.body || '').length > 140 ? '…' : ''}</div>
      ${stats}
      <div class="an-card-foot">
        <span class="an-card-when">${sent ? 'اتبعتت ' + anFmtDate(c.sent_at) : 'اتعدّلت ' + anFmtDate(c.updated_at)}</span>
        <div class="an-card-actions">${actions}</div>
      </div>
    </div>`;
}

function anFmtDate(iso) {
  if (!iso) return '—';
  try {
    // The backend sends naive UTC with no marker; label it before parsing or
    // the browser reads it as local time.
    const d = new Date(/[Zz]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : iso + 'Z');
    return d.toLocaleDateString('ar-EG', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  } catch (e) { return '—'; }
}

// ═══ EDITOR ═══

function anNewCampaign() {
  anCurrent = null;
  anSetField('an-title', '');
  anSetField('an-body', '');
  anSetField('an-type', 'info');
  anSetField('an-link', '');
  anSetField('an-aud-status', 'all');
  anSetField('an-aud-plan', 'all');
  anSetField('an-aud-country', '');
  anSetField('an-aud-gov', '');
  anSetField('an-aud-expiring', '');
  anSetField('an-aud-search', '');
  const staff = document.getElementById('an-aud-staff');
  if (staff) staff.checked = false;
  anSetField('an-confirm', '');

  document.getElementById('an-editor-title').textContent = '📢 حملة جديدة';
  document.getElementById('an-editor-badge').innerHTML = '<span class="an-status-badge draft">مسودة</span>';

  anShowEditorView();
  anRenderPreview();
  anRefreshAudience();
}

async function anOpenCampaign(id) {
  const c = anCampaigns.find(x => x.id === id);
  if (!c) return;
  anCurrent = c;

  anSetField('an-title', c.title || '');
  anSetField('an-body', c.body || '');
  anSetField('an-type', c.type || 'info');
  anSetField('an-link', c.link || '');

  const a = c.audience || {};
  anSetField('an-aud-status', a.status || 'all');
  anSetField('an-aud-plan', a.plan || 'all');
  anSetField('an-aud-country', a.country || '');
  anSetField('an-aud-gov', a.governorate || '');
  anSetField('an-aud-expiring', a.expiring_days == null ? '' : a.expiring_days);
  anSetField('an-aud-search', a.search || '');
  const staff = document.getElementById('an-aud-staff');
  if (staff) staff.checked = !!a.include_staff;
  anSetField('an-confirm', '');

  document.getElementById('an-editor-title').textContent = '📢 ' + (c.title || 'حملة');
  document.getElementById('an-editor-badge').innerHTML =
    c.status === 'sent' ? '<span class="an-status-badge sent">اتبعتت</span>'
      : '<span class="an-status-badge draft">مسودة</span>';

  anShowEditorView();
  anRenderPreview();
  anRefreshAudience();
}

function anSetField(id, value) {
  const el = document.getElementById(id);
  if (el) el.value = value;
}

function anReadForm() {
  const days = (document.getElementById('an-aud-expiring') || {}).value;
  return {
    title: (document.getElementById('an-title') || {}).value || '',
    body: (document.getElementById('an-body') || {}).value || '',
    type: (document.getElementById('an-type') || {}).value || 'info',
    link: (document.getElementById('an-link') || {}).value || '',
    audience: {
      status: (document.getElementById('an-aud-status') || {}).value || 'all',
      plan: (document.getElementById('an-aud-plan') || {}).value || 'all',
      country: (document.getElementById('an-aud-country') || {}).value || '',
      governorate: (document.getElementById('an-aud-gov') || {}).value || '',
      expiring_days: days === '' || days == null ? null : Number(days),
      search: (document.getElementById('an-aud-search') || {}).value || '',
      include_staff: !!(document.getElementById('an-aud-staff') || {}).checked,
    },
  };
}

// ═══ PREVIEW ═══
// Drawn to match the notification row in utils.js, so what is approved here is
// what the member actually gets.

function anRenderPreview() {
  const box = document.getElementById('an-preview');
  if (!box) return;
  const f = anReadForm();
  const meta = anTypeMeta(f.type);

  if (!f.title.trim() && !f.body.trim()) {
    box.innerHTML = '<div class="an-preview-empty">اكتب العنوان والنص عشان تشوف المعاينة</div>';
    return;
  }

  box.innerHTML = `
    <div class="an-preview-row" style="border-inline-start:3px solid ${meta.color}">
      <div class="an-preview-icon" style="background:${meta.color}1f;color:${meta.color}">
        <i data-lucide="${meta.icon}" style="width:16px;height:16px;"></i>
      </div>
      <div class="an-preview-text">
        <div class="an-preview-title">${escapeHtml(f.title) || '<span style="color:#666">(العنوان)</span>'}</div>
        <div class="an-preview-body">${escapeHtml(f.body) || '<span style="color:#666">(النص)</span>'}</div>
        <div class="an-preview-time">دلوقتي حالاً${f.link ? ' · بيروح لـ ' + escapeHtml(f.link) : ''}</div>
      </div>
    </div>`;
  if (window.lucide) lucide.createIcons();
}

// ═══ AUDIENCE ═══

function anRefreshAudience() {
  anRenderPreview();
  clearTimeout(anAudienceTimer);
  // Debounced: the count re-resolves on every keystroke in the search box, and
  // that is a full audience query on the server each time.
  anAudienceTimer = setTimeout(anLoadAudience, 350);
}

async function anLoadAudience() {
  const countEl = document.getElementById('an-aud-count');
  const subEl = document.getElementById('an-aud-sub');
  const sampleEl = document.getElementById('an-aud-sample');
  if (!countEl) return;

  const a = anReadForm().audience;
  const qs = new URLSearchParams();
  if (a.search) qs.set('search', a.search);
  if (a.country) qs.set('country', a.country);
  if (a.governorate) qs.set('governorate', a.governorate);
  if (a.status) qs.set('status', a.status);
  if (a.plan) qs.set('plan', a.plan);
  if (a.expiring_days != null && !Number.isNaN(a.expiring_days)) qs.set('expiring_days', a.expiring_days);
  if (a.include_staff) qs.set('include_staff', 'true');

  countEl.textContent = '…';
  subEl.textContent = 'بنحسب الجمهور...';

  try {
    const res = await authFetch(`${API}/admin/announcements/audience/preview?${qs}`);
    if (!res.ok) throw new Error('failed');
    const d = await res.json();

    countEl.textContent = d.count;
    subEl.textContent = d.count === 0
      ? 'الفلتر ده مالوش أي عضو — عدّله'
      : `عضو هيوصلهم الإشعار · ${d.online_now} منهم متصل دلوقتي هيشوفه فوراً`
        + (d.truncated ? ' · (متقطوع عند الحد الأقصى)' : '');

    sampleEl.innerHTML = (d.sample || []).map(u =>
      `<span class="an-chip${u.is_active ? '' : ' off'}">${escapeHtml(u.full_name || '—')}</span>`
    ).join('') + (d.count > (d.sample || []).length
      ? `<span class="an-chip more">+${d.count - d.sample.length}</span>` : '');

    if (!anFacetsLoaded) { anFillFacets(d.countries, d.governorates); anFacetsLoaded = true; }
  } catch (e) {
    countEl.textContent = '—';
    subEl.textContent = 'مقدرناش نحسب الجمهور';
    sampleEl.innerHTML = '';
  }
}

function anFillFacets(countries, govs) {
  const fill = (id, values) => {
    const sel = document.getElementById(id);
    if (!sel) return;
    const current = sel.value;
    sel.innerHTML = '<option value="">الكل</option>' +
      (values || []).map(v => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('');
    sel.value = current;
  };
  fill('an-aud-country', countries);
  fill('an-aud-gov', govs);
}

// ═══ SAVE / DELETE / DUPLICATE ═══

async function anSaveCampaign() {
  const body = anReadForm();
  if (!body.title.trim() || !body.body.trim()) {
    showToast('❌ الحملة محتاجة عنوان ونص', 'error');
    return false;
  }

  try {
    const url = anCurrent ? `${API}/admin/announcements/${anCurrent.id}` : `${API}/admin/announcements`;
    const res = await authFetch(url, {
      method: anCurrent ? 'PUT' : 'POST',
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'failed');

    anCurrent = await res.json();
    document.getElementById('an-editor-title').textContent = '📢 ' + (anCurrent.title || 'حملة');
    showToast('✅ اتحفظت — مفيش أي إشعار اتبعت', 'success');
    loadAnnouncementsList();
    return true;
  } catch (e) {
    showToast(`❌ ${e.message || 'مقدرناش نحفظ'}`, 'error');
    return false;
  }
}

async function anDelete(id) {
  if (!confirm('تمسح الحملة دي؟ الإشعارات اللي وصلت للأعضاء هتفضل عندهم.')) return;
  try {
    const res = await authFetch(`${API}/admin/announcements/${id}`, { method: 'DELETE' });
    if (!res.ok && res.status !== 204) throw new Error('failed');
    showToast('🗑️ اتمسحت', 'success');
    loadAnnouncementsList();
  } catch (e) {
    showToast('❌ مقدرناش نمسح', 'error');
  }
}

async function anDuplicate(id) {
  try {
    const res = await authFetch(`${API}/admin/announcements/${id}/duplicate`, { method: 'POST' });
    if (!res.ok) throw new Error('failed');
    const copy = await res.json();
    showToast('📄 اتعملت نسخة كمسودة', 'success');
    await loadAnnouncementsList();
    anOpenCampaign(copy.id);
  } catch (e) {
    showToast('❌ مقدرناش نعمل نسخة', 'error');
  }
}

// ═══ SEND ═══

async function anSend(mode) {
  if (anSending) return;

  // Save first, always. Sending the draft in the editor while the server holds
  // an older version is how you end up mailing the previous wording to
  // everyone — the one mistake here that cannot be taken back.
  const saved = await anSaveCampaign();
  if (!saved || !anCurrent) return;

  const payload = { mode };

  if (mode === 'real') {
    const typed = ((document.getElementById('an-confirm') || {}).value || '').trim();
    if (typed !== AN_CONFIRM_PHRASE) {
      showToast(`❌ اكتب ${AN_CONFIRM_PHRASE} بالظبط في خانة التأكيد`, 'error');
      return;
    }
    const count = (document.getElementById('an-aud-count') || {}).textContent || '?';
    if (!confirm(`هتبعت الحملة دي لـ ${count} عضو دلوقتي. الخطوة دي مش بترجع. تكمّل؟`)) return;
    payload.confirm_phrase = typed;
  }

  anSending = true;
  try {
    const res = await authFetch(`${API}/admin/announcements/${anCurrent.id}/send`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'failed');

    showToast(`✅ ${data.message || 'اتبعتت'}`, 'success');
    anSetField('an-confirm', '');
    await loadAnnouncementsList();
    if (mode === 'real') {
      anBackToList();
      // The request returns while the fan-out is still running, so the list we
      // just loaded says "sending". Follow it until the worker finishes and
      // repaint, instead of leaving the operator to guess and hit refresh.
      anWatchSend(anCurrent.id);
    }
  } catch (e) {
    showToast(`❌ ${e.message || 'الإرسال فشل'}`, 'error');
  } finally {
    anSending = false;
  }
}


// ═══ SEND STATUS ═══

// Polls one campaign until it stops being "sending". The status lives in the
// database, so this survives the tab being reopened; what it cannot see is a
// worker that died mid-send, which the endpoint reports as `stalled`.
async function anWatchSend(id) {
  if (!id) return;
  const started = Date.now();
  const TIMEOUT_MS = 10 * 60 * 1000;

  while (Date.now() - started < TIMEOUT_MS) {
    await new Promise(r => setTimeout(r, 1500));
    let st;
    try {
      const res = await authFetch(`${API}/admin/announcements/${id}/status`);
      if (!res.ok) return;
      st = await res.json();
    } catch (e) {
      return;                       // a dropped poll is not worth an error toast
    }

    if (st.status !== 'sending') {
      await loadAnnouncementsList();
      if (st.status === 'sent') {
        showToast(`✅ الحملة وصلت لـ ${st.delivered} عضو`, 'success');
      } else if (st.status === 'failed') {
        showToast('❌ الإرسال فشل — شوف اللوج', 'error');
      }
      return;
    }

    if (st.stalled) {               // status says sending, nothing is running
      await loadAnnouncementsList();
      showToast('⚠️ الإرسال وقف في النص — الحملة محتاجة مراجعة', 'error');
      return;
    }
  }
}
