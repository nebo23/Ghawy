/* ═══ COMMUNITY ANNOUNCEMENTS — in-app member campaigns ═══
 *
 * The counterpart to the Emails tab: same idea, different delivery. A campaign
 * here reaches the member while they are on the site — either in their
 * notification bell (`delivery: "bell"`, the default) or as a real private
 * message from a chosen admin (`delivery: "dm"`).
 *
 * Loaded AFTER team.js, which is where authFetch / showToast / escapeHtml /
 * API come from — this file deliberately re-declares none of them, so there is
 * one implementation of each rather than a second copy drifting out of sync.
 *
 * Rules the UI enforces alongside the server:
 *   • The audience is never sent as a list of ids. The filter goes up, the
 *     server resolves who that is. A client-supplied id list would let anyone
 *     with this tab message any account.
 *   • A real send needs the confirm phrase typed exactly. The test button
 *     sends to the operator alone and is always one click away, so there is
 *     never a reason to "just try it live".
 *   • The two delivery modes never look interchangeable. A bell notification
 *     is one-way; a DM is an invitation to reply, and a DM campaign to the
 *     whole roster lands thousands of real conversations in one person's
 *     inbox. The mode is a deliberate choice on screen, and the consequence is
 *     spelled out in the confirm dialog — next to the button, not in a
 *     tooltip.
 *   • The sender dropdown is a convenience. Whether this operator may send as
 *     that account is decided by the server on every save and every send.
 */

const AN_CONFIRM_PHRASE = 'GHAWY-OFFICIAL-SEND';

let anCampaigns = [];
let anCurrent = null;      // the campaign being edited (null = new, unsaved)
let anAudienceTimer = null;
let anFacetsLoaded = false;
let anSending = false;
let anSenders = [];        // accounts this operator may send as
let anSegments = [];       // saved audience filters
let anAudMode = 'filter';  // 'filter' | 'picked'
let anPicked = [];         // hand-picked members: {id, full_name, email, ...}
let anPickTimer = null;
let anPickSeesContacts = false;
// Last `personalization` block from the audience preview. The composer preview
// re-renders on every keystroke; the audience query is debounced. Holding the
// last answer here lets the preview resolve {{name}} against a REAL member
// without firing a query per character.
let anPersonal = null;

// List paging/search state. The list used to be an unpaged `.limit(200)`,
// which is fine right up until campaign 201 disappears without anybody being
// told.
let anList = { q: '', status: 'all', delivery: 'all', offset: 0, limit: 30, total: 0, hasMore: false };
let anListTimer = null;

const AN_TYPE_META = {
  info:    { icon: 'info',          color: '#3f8ff9', label: 'معلومة' },
  success: { icon: 'check-circle',  color: '#22c55e', label: 'خبر كويس' },
  warning: { icon: 'alert-triangle', color: '#f59e0b', label: 'تنبيه' },
  promo:   { icon: 'gift',          color: '#c1ff11', label: 'عرض' },
};

function anTypeMeta(t) { return AN_TYPE_META[t] || AN_TYPE_META.info; }

function anDelivery() {
  const el = document.getElementById('an-delivery');
  return (el && el.value) === 'dm' ? 'dm' : 'bell';
}

// ═══ ENTRY ═══

async function loadAnnouncementsTab() {
  anShowListView();
  anBindPicker();
  await Promise.all([loadAnnouncementsList(), anLoadSenders(), anLoadSegments()]);
}

// Bound once. Debounced because every keystroke is an ILIKE over the roster.
let anPickerBound = false;
function anBindPicker() {
  if (anPickerBound) return;
  const box = document.getElementById('an-pick-search');
  if (!box) return;
  box.addEventListener('input', () => {
    clearTimeout(anPickTimer);
    anPickTimer = setTimeout(anPickSearch, 300);
  });
  anPickerBound = true;
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
  anList.offset = 0;
  loadAnnouncementsList();
}

// ═══ LIST ═══

// Debounced so typing in the search box is one request when you stop, not one
// per keystroke — the server runs an ILIKE over title and body for each.
function anListFilterChanged() {
  clearTimeout(anListTimer);
  anListTimer = setTimeout(() => {
    anList.q = ((document.getElementById('an-search') || {}).value || '').trim();
    anList.status = (document.getElementById('an-filter-status') || {}).value || 'all';
    anList.delivery = (document.getElementById('an-filter-delivery') || {}).value || 'all';
    anList.offset = 0;
    loadAnnouncementsList();
  }, 300);
}

function anLoadMore() {
  anList.offset += anList.limit;
  loadAnnouncementsList(true);
}

async function loadAnnouncementsList(append) {
  const grid = document.getElementById('an-grid');
  if (!grid) return;
  if (!append) grid.innerHTML = anStateHTML('loader-circle', 'جاري التحميل…');

  const qs = new URLSearchParams({ limit: anList.limit, offset: anList.offset });
  if (anList.q) qs.set('q', anList.q);
  if (anList.status && anList.status !== 'all') qs.set('status', anList.status);
  if (anList.delivery && anList.delivery !== 'all') qs.set('delivery', anList.delivery);

  try {
    const res = await authFetch(`${API}/admin/announcements?${qs}`);
    if (res.status === 403) {
      grid.innerHTML = '<div class="an-empty">🔒 مالكش صلاحية الحملات دي</div>';
      return;
    }
    if (!res.ok) throw new Error('failed');
    const data = await res.json();

    anCampaigns = append ? anCampaigns.concat(data.items || []) : (data.items || []);
    anList.total = data.total || 0;
    anList.hasMore = !!data.has_more;

    if (!anCampaigns.length) {
      const filtered = !!(anList.q || anList.status !== 'all' || anList.delivery !== 'all');
      grid.innerHTML = filtered
        ? anStateHTML('search-x', 'مفيش حملة مطابقة للبحث ده',
            'جرّب كلمة تانية، أو امسح الفلاتر عشان تشوف كل الحملات.',
            '<button class="an-ghost-btn" onclick="anClearFilters()">امسح الفلاتر</button>')
        // The first campaign should be one click away from the empty screen,
        // not a hunt back up to the toolbar.
        : anStateHTML('megaphone', 'لسه مفيش حملات',
            'الحملة بتوصل للأعضاء وهُمّ على الموقع — في جرس الإشعارات، أو كرسالة خاصة.',
            '<button class="an-new-btn" onclick="anNewCampaign()"><i data-lucide="plus" style="width:16px;height:16px;"></i> ابدأ أول حملة</button>');
    } else {
      grid.innerHTML = anCampaigns.map(anCardHTML).join('');
    }

    const count = document.getElementById('an-list-count');
    if (count) {
      count.textContent = anList.total
        ? `${anCampaigns.length} من ${anList.total}`
        : '';
    }
    const more = document.getElementById('an-more-btn');
    if (more) more.style.display = anList.hasMore ? '' : 'none';

    if (window.lucide) lucide.createIcons();
  } catch (e) {
    if (!append) grid.innerHTML = anStateHTML('triangle-alert', 'مقدرناش نجيب الحملات',
      'في مشكلة في الاتصال بالسيرفر.',
      '<button class="an-ghost-btn" onclick="loadAnnouncementsList()">جرّب تاني</button>', 'error');
  }
}

// One shape for every "nothing to show here" state on this tab — loading, empty,
// no search results, failed load. Centred, an icon, a muted line, and where
// there is an obvious next step, the button for it. Matches how the rest of
// this dashboard draws its empty states rather than dropping a bare sentence
// into a grid cell.
function anStateHTML(icon, title, sub, action, variant) {
  return `
    <div class="an-state${variant ? ' ' + variant : ''}">
      <div class="an-state-icon"><i data-lucide="${icon}"></i></div>
      <div class="an-state-title">${escapeHtml(title)}</div>
      ${sub ? `<div class="an-state-sub">${escapeHtml(sub)}</div>` : ''}
      ${action ? `<div class="an-state-action">${action}</div>` : ''}
    </div>`;
}

function anClearFilters() {
  anSetField('an-search', '');
  anSetField('an-filter-status', 'all');
  anSetField('an-filter-delivery', 'all');
  anList = { ...anList, q: '', status: 'all', delivery: 'all', offset: 0 };
  loadAnnouncementsList();
}

function anCardHTML(c) {
  const meta = anTypeMeta(c.type);
  const sent = c.status === 'sent';
  const isDm = c.delivery === 'dm';
  const delivered = c.delivered || 0;

  // "sending" used to fall through to the draft branch, so a campaign that was
  // mid-fan-out showed as "مسودة" until somebody refreshed. The send returns
  // before the fan-out finishes now, so this state is the normal one to be in
  // for a second or two — it needs its own badge.
  // The scheduled date used to live inside this badge, which made it long
  // enough to squeeze the title out of the row. It belongs on the footer line
  // with the other timestamps.
  const statusBadge = sent
    ? `<span class="an-status-badge sent">اتبعتت</span>`
    : c.status === 'failed'
      ? `<span class="an-status-badge failed">فشلت</span>`
      : c.status === 'sending'
        ? `<span class="an-status-badge sending">بتتبعت دلوقتي</span>`
        : c.status === 'scheduled'
          ? `<span class="an-status-badge scheduled">مجدولة</span>`
          : `<span class="an-status-badge draft">مسودة</span>`;

  // The delivery mode gets its own badge on every card, sent or not. The two
  // modes have different consequences for the member and for whoever has to
  // answer the replies, so they must not have to be told apart by reading the
  // body text.
  const modeBadge = isDm
    ? `<span class="an-mode-badge dm" title="بتوصل كرسالة خاصة"><i data-lucide="send" style="width:11px;height:11px;"></i> رسالة خاصة${c.sender_name ? ' · ' + escapeHtml(c.sender_name) : ''}</span>`
    : `<span class="an-mode-badge bell" title="بتوصل في جرس الإشعارات"><i data-lucide="bell" style="width:11px;height:11px;"></i> جرس</span>`;

  // Stats only mean something once something has actually gone out. A draft
  // showing "0% read" reads like a failure rather than "not sent yet" — but a
  // FAILED campaign showing nothing is worse: the first thing an operator
  // needs to know about a red card is whether it reached nobody or two-thirds
  // of the list.
  const stats = (sent || delivered > 0) ? `
    <div class="an-card-stats">
      <div class="an-stat"><span class="an-stat-num">${delivered}</span><span class="an-stat-lbl">${sent ? 'اتسلّمت' : 'وصلت لهم'}</span></div>
      <div class="an-stat"><span class="an-stat-num">${c.read || 0}</span><span class="an-stat-lbl">${isDm ? 'فتحوها' : 'اتقرت'}</span></div>
      <div class="an-stat"><span class="an-stat-num" style="color:${meta.color}">${c.read_rate || 0}%</span><span class="an-stat-lbl">نسبة القراءة</span></div>
    </div>` : '';

  // A partially delivered campaign that is not being told how far it got, and
  // why it stopped, is a dead end. Both go on the card.
  const partial = (c.status === 'failed' && delivered > 0)
    ? `<div class="an-card-partial">⚠️ وصلت لـ <b>${delivered}</b> عضو قبل ما تقف — الباقي لسه. «كمّل» بيبعت للباقي بس.</div>`
    : (c.status === 'failed'
        ? '<div class="an-card-partial">مفيش أي عضو استلمها.</div>' : '');
  const reason = (c.status === 'failed' && c.failure_reason)
    ? `<div class="an-card-reason">${escapeHtml(c.failure_reason)}</div>` : '';

  // A campaign mid-fan-out gets no buttons (F-29). Edit is already refused by
  // the server with a 400; delete was not, and offering it here meant offering
  // an action that would report a lie in the log and nothing at all to the
  // operator. The server refuses both now — this stops the card asking.
  const actions = c.status === 'sending'
    ? `<span class="an-card-busy"><i data-lucide="loader" style="width:12px;height:12px;"></i> بتتبعت… استنى لما تخلص</span>`
    : sent
    ? `<button class="an-mini" onclick="anOpenRecipients(${c.id})"><i data-lucide="users" style="width:13px;height:13px;"></i> مين استلمها</button>
       <button class="an-mini" onclick="anDuplicate(${c.id})"><i data-lucide="copy" style="width:13px;height:13px;"></i> نسخة</button>`
    : c.status === 'scheduled'
      ? `<button class="an-mini" onclick="anUnschedule(${c.id})"><i data-lucide="x" style="width:13px;height:13px;"></i> الغي الجدولة</button>`
      : c.status === 'failed'
        ? `<button class="an-mini resume" onclick="anOpenCampaign(${c.id})"><i data-lucide="rotate-cw" style="width:13px;height:13px;"></i> كمّل</button>
           ${delivered > 0 ? `<button class="an-mini" onclick="anOpenRecipients(${c.id})"><i data-lucide="users" style="width:13px;height:13px;"></i> مين استلمها</button>` : ''}
           <button class="an-mini danger" onclick="anDelete(${c.id})"><i data-lucide="trash-2" style="width:13px;height:13px;"></i> مسح</button>`
        : `<button class="an-mini" onclick="anOpenCampaign(${c.id})"><i data-lucide="pen-line" style="width:13px;height:13px;"></i> تعديل</button>
           <button class="an-mini danger" onclick="anDelete(${c.id})"><i data-lucide="trash-2" style="width:13px;height:13px;"></i> مسح</button>`;

  const when = sent
    ? 'اتبعتت ' + anFmtDate(c.sent_at)
    : c.status === 'scheduled'
      ? 'هتتبعت ' + anFmtDate(c.scheduled_for)
      : 'اتعدّلت ' + anFmtDate(c.updated_at);

  return `
    <div class="an-card${isDm ? ' dm' : ''}">
      <div class="an-card-head">
        <span class="an-card-dot" style="background:${meta.color}" title="${escapeHtml(meta.label)}"></span>
        <div class="an-card-title">${escapeHtml(c.label || '(فاضية)')}</div>
      </div>
      <div class="an-card-modes">${statusBadge}${modeBadge}</div>
      <div class="an-card-body">${escapeHtml((c.body || '').slice(0, 140))}${(c.body || '').length > 140 ? '…' : ''}</div>
      ${partial}${reason}${stats}
      <div class="an-card-foot">
        <span class="an-card-when">${escapeHtml(when)}</span>
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

// ═══ SENDERS (DM mode) ═══
//
// Who this operator may send as. The owner gets every admin; anybody else gets
// themselves and nobody else. This list is a convenience — the same rule is
// checked on the server for every save and every send, so an id typed straight
// at the endpoint is refused just the same.

async function anLoadSenders() {
  try {
    const res = await authFetch(`${API}/admin/announcements/senders`);
    if (!res.ok) return;
    anSenders = await res.json();
  } catch (e) { anSenders = []; }
  anFillSenders();
}

function anFillSenders(selected) {
  const sel = document.getElementById('an-sender');
  if (!sel) return;
  const keep = selected != null ? String(selected) : sel.value;
  sel.innerHTML = anSenders.map(s =>
    `<option value="${s.id}">${escapeHtml(s.full_name || '—')}${s.is_self ? ' (إنت)' : ''}${s.is_owner ? ' · owner' : ''}</option>`
  ).join('');
  if (keep && anSenders.some(s => String(s.id) === String(keep))) sel.value = keep;
  const wrap = document.getElementById('an-sender-wrap');
  if (wrap && anSenders.length <= 1) {
    // One option is not a choice; say who it will come from instead of
    // presenting a dropdown that cannot be changed.
    wrap.classList.add('single');
  }
}

function anSenderName() {
  const sel = document.getElementById('an-sender');
  const found = anSenders.find(s => String(s.id) === String(sel && sel.value));
  return found ? found.full_name : 'حسابك';
}

// ═══ DELIVERY MODE ═══

function anRenderDeliveryState() {
  const dm = anDelivery() === 'dm';
  const wrap = document.getElementById('an-sender-wrap');
  const warn = document.getElementById('an-dm-warn');
  const editor = document.getElementById('an-editor-view');
  if (wrap) wrap.style.display = dm ? '' : 'none';
  if (warn) warn.style.display = dm ? '' : 'none';
  // The type drives an icon and an accent colour, and a DM has neither — it is
  // plain text in a chat bubble. Leaving the field enabled let an operator pick
  // "تنبيه (أصفر)" and get nothing; a control with no effect is worse than one
  // that is not there.
  const typeWrap = document.getElementById('an-type-wrap');
  if (typeWrap) typeWrap.style.display = dm ? 'none' : '';
  if (editor) editor.classList.toggle('dm-mode', dm);

  const sendBtn = document.getElementById('an-send-btn');
  if (sendBtn) {
    sendBtn.innerHTML = dm
      ? '<i data-lucide="send" style="width:15px;height:15px;"></i> إرسال حقيقي (رسايل خاصة)'
      : '<i data-lucide="send" style="width:15px;height:15px;"></i> إرسال حقيقي';
  }
  const testBtn = document.getElementById('an-test-btn');
  if (testBtn) {
    testBtn.innerHTML = dm
      ? '<i data-lucide="flask-conical" style="width:15px;height:15px;"></i> إرسال تجريبي (رسالة خاصة ليك إنت)'
      : '<i data-lucide="flask-conical" style="width:15px;height:15px;"></i> إرسال تجريبي (ليك إنت بس)';
  }
  // The preview label names the surface being previewed. Leaving it saying
  // "in the bell" over a chat bubble is the same mistake as previewing the
  // wrong surface in the first place.
  const plabel = document.getElementById('an-preview-label');
  if (plabel) {
    plabel.textContent = dm
      ? 'معاينة — زي ما العضو هيشوفها في الرسايل الخاصة'
      : 'معاينة — زي ما العضو هيشوفها في الجرس';
  }
  anRenderPreview();
  if (window.lucide) lucide.createIcons();
}

// ═══ EDITOR ═══

function anNewCampaign() {
  anCurrent = null;
  anSetField('an-body', '');
  anSetField('an-type', 'info');
  anSetField('an-link', '');
  anSetField('an-delivery', 'bell');
  // The empty filter IS the default audience — one writer, so a new campaign
  // and a re-opened one can never disagree about what a blank panel means.
  anWriteAudienceFields({});
  anSetField('an-confirm', '');
  anSetField('an-sched-at', '');
  anSetField('an-segment', '');
  anSetField('an-pick-search', '');
  anPicked = [];
  anSetAudMode('filter');
  const self = anSenders.find(s => s.is_self);
  anFillSenders(self ? self.id : undefined);
  anRenderSchedState();
  anRenderResumeState();

  document.getElementById('an-editor-title').textContent = '📢 حملة جديدة';
  document.getElementById('an-editor-badge').innerHTML = '<span class="an-status-badge draft">مسودة</span>';

  anShowEditorView();
  anRenderDeliveryState();
  anRefreshAudience();
}

async function anOpenCampaign(id) {
  const c = anCampaigns.find(x => x.id === id);
  if (!c) return;
  anCurrent = c;

  anSetField('an-body', c.body || '');
  anSetField('an-type', c.type || 'info');
  anSetField('an-link', c.link || '');
  anSetField('an-delivery', c.delivery === 'dm' ? 'dm' : 'bell');
  anFillSenders(c.sender_id || ((anSenders.find(s => s.is_self) || {}).id));

  const a = c.audience || {};
  anWriteAudienceFields(a);
  anSetField('an-confirm', '');
  anSetField('an-segment', '');
  anSetField('an-pick-search', '');
  anSetAudMode(a.member_ids && a.member_ids.length ? 'picked' : 'filter');
  anLoadPicked(a.member_ids);
  // datetime-local wants local wall-clock with no zone; the stored value is
  // naive UTC, so mark it before parsing or it lands three hours out.
  anSetField('an-sched-at', c.scheduled_for
    ? new Date(/[Zz]|[+-]\d{2}:?\d{2}$/.test(c.scheduled_for) ? c.scheduled_for : c.scheduled_for + 'Z')
        .toLocaleString('sv').slice(0, 16).replace(' ', 'T')
    : '');
  anRenderSchedState();
  anRenderResumeState();

  document.getElementById('an-editor-title').textContent = '📢 ' + (c.label || 'حملة');
  document.getElementById('an-editor-badge').innerHTML =
    c.status === 'sent' ? '<span class="an-status-badge sent">اتبعتت</span>'
      : c.status === 'failed' ? '<span class="an-status-badge failed">فشلت</span>'
        : '<span class="an-status-badge draft">مسودة</span>';

  anShowEditorView();
  anRenderDeliveryState();
  anRefreshAudience();
}

// A failed campaign that already reached people is frozen: its text cannot be
// edited, only resumed or duplicated. Saying so where the operator is standing
// is the difference between a rule and a mystery 400.
function anRenderResumeState() {
  const box = document.getElementById('an-resume-state');
  if (!box) return;
  const c = anCurrent;
  if (!c || c.status !== 'failed') { box.innerHTML = ''; box.style.display = 'none'; return; }
  box.style.display = '';
  const d = c.delivered || 0;
  box.innerHTML = d > 0
    ? `⚠️ الحملة دي وقفت في النص. <b>${d}</b> عضو استلموها خلاص، والنص متقفل عشان كده —
       «إرسال حقيقي» دلوقتي هيبعت <b>للباقي بس</b>، محدش هياخدها مرتين.
       عايز تغيّر الكلام؟ اعمل نسخة.`
    : `⚠️ الحملة دي فشلت ومحدش استلمها. عدّل اللي عايزه وابعت تاني عادي.`;
}

function anSetField(id, value) {
  const el = document.getElementById(id);
  if (el) el.value = value;
}

function anReadForm() {
  const days = (document.getElementById('an-aud-expiring') || {}).value;
  const course = (document.getElementById('an-aud-course') || {}).value;
  const pct = (document.getElementById('an-aud-progress') || {}).value;
  const senderRaw = (document.getElementById('an-sender') || {}).value;
  return {
    body: (document.getElementById('an-body') || {}).value || '',
    type: (document.getElementById('an-type') || {}).value || 'info',
    link: (document.getElementById('an-link') || {}).value || '',
    delivery: anDelivery(),
    sender_id: senderRaw ? Number(senderRaw) : null,
    audience: {
      // Hand-picked members are the audience on their own — the server drops
      // the other filters when this is set, so sending them would be quoting a
      // shape the server does not use.
      member_ids: anAudMode === 'picked' ? anPicked.map(m => m.id) : null,
      status: (document.getElementById('an-aud-status') || {}).value || 'all',
      plan: (document.getElementById('an-aud-plan') || {}).value || 'all',
      country: (document.getElementById('an-aud-country') || {}).value || '',
      governorate: (document.getElementById('an-aud-gov') || {}).value || '',
      expiring_days: days === '' || days == null ? null : Number(days),
      progress_course_id: course === '' || course == null ? null : Number(course),
      progress_min_percent: pct === '' || pct == null ? null : Number(pct),
      search: (document.getElementById('an-aud-search') || {}).value || '',
      include_staff: !!(document.getElementById('an-aud-staff') || {}).checked,
    },
  };
}

// The audience half of the form, written FROM a saved filter. Two callers —
// opening a campaign and applying a saved segment — and they used to hold the
// same eight lines each. That is not a style problem: adding a filter to one
// and not the other means a saved segment silently drops it, the field stays
// blank, and the campaign goes to everybody. One writer, so a new field can
// only ever be forgotten in both places at once, which is a bug you see.
//
// The mirror of anReadForm().audience — if a field is added there, it is added
// here.
function anWriteAudienceFields(f) {
  f = f || {};
  anSetField('an-aud-status', f.status || 'all');
  anSetField('an-aud-plan', f.plan || 'all');
  anSetField('an-aud-country', f.country || '');
  anSetField('an-aud-gov', f.governorate || '');
  anSetField('an-aud-expiring', f.expiring_days == null ? '' : f.expiring_days);
  anSetField('an-aud-course', f.progress_course_id == null ? '' : f.progress_course_id);
  anSetField('an-aud-progress', f.progress_min_percent == null ? '' : f.progress_min_percent);
  anSetField('an-aud-search', f.search || '');
  const staff = document.getElementById('an-aud-staff');
  if (staff) staff.checked = !!f.include_staff;
}

// ═══ PREVIEW ═══
// Drawn to match what the member actually gets: the notification row from
// utils.js in bell mode, a chat bubble in DM mode. Approving a preview of the
// wrong surface is the same as not previewing at all.

// ═══ {{name}} ═══
//
// One token. It resolves through the same chain the server sends with —
// `name_utils.arabic_first_name` — which is why the preview cannot promise
// something the send does not deliver: the NAME shown here came back from the
// server already resolved, against a member actually in this audience.
//
// These mirror the server's `_NAME_TOKEN_RE` exactly (optional inner spaces,
// case-insensitive). If one changes, the others must.
//
// Two of them, and not by accident: `.test()` on a /g/ regex advances
// `lastIndex` and returns false on the very next identical call. Sharing one
// object between the test and the replace would make the preview show the
// token on every other keystroke.
const AN_NAME_TOKEN_G = /\{\{\s*name\s*\}\}/gi;   // replace
const AN_NAME_TOKEN = /\{\{\s*name\s*\}\}/i;      // test

function anHasNameToken(f) {
  return AN_NAME_TOKEN.test(f.body || '');
}

// Substitution happens on the RAW text, then the result is escaped as one
// string — so a resolved name is escaped exactly like the words around it.
// Escaping first and substituting after would drop a live name into finished
// HTML, which is the bug this ordering exists to prevent.
function anFillName(text, name) {
  return String(text || '').replace(AN_NAME_TOKEN_G, name);
}

// Insert at the caret, not at the end — appending blindly would drop the token
// somewhere the operator did not mean and make the button feel broken.
function anInsertNameToken() {
  const el = document.getElementById('an-body');
  if (!el) return;

  const start = el.selectionStart == null ? el.value.length : el.selectionStart;
  const end = el.selectionEnd == null ? el.value.length : el.selectionEnd;
  el.value = el.value.slice(0, start) + '{{name}}' + el.value.slice(end);
  const caret = start + '{{name}}'.length;
  el.focus();
  try { el.setSelectionRange(caret, caret); } catch (e) { /* not all inputs support it */ }
  anRenderPreview();
}

function anPreviewName(which) {
  const p = anPersonal;
  const s = p && (which === 'unresolved' ? p.sample_unresolved : p.sample_named);
  // No audience resolved yet (or nobody in it): show the token rather than
  // invent a member. A made-up example is worse than an honest gap — it is the
  // hardcoded name this feature exists to avoid.
  return s ? s.resolved : null;
}

function anRenderPreview() {
  const box = document.getElementById('an-preview');
  if (!box) return;
  let f = anReadForm();
  const meta = anTypeMeta(f.type);

  // Rendered from here so that typing {{name}} into the message updates
  // the line under the audience count too — those inputs call this function
  // and nothing else, and a coverage line that only refreshes when a FILTER
  // changes would sit there stale while the operator edits the very text it
  // describes.
  anRenderNameCoverage();

  if (!f.body.trim()) {
    box.innerHTML = '<div class="an-preview-empty">اكتب الرسالة عشان تشوف المعاينة</div>';
    return;
  }

  // {{name}} is resolved BEFORE the surface is drawn, so what follows renders
  // the finished text — the same string the member's row will hold. The second
  // card (the member whose name does not arabise) is drawn after it.
  const raw = f;                      // pre-substitution, for the example below
  const personalized = anHasNameToken(f);
  const shownName = personalized ? anPreviewName('named') : null;
  if (personalized && shownName) {
    f = Object.assign({}, f, { body: anFillName(f.body, shownName) });
  }

  if (f.delivery === 'dm') {
    const from = anSenderName();
    box.innerHTML = `
      <div class="an-dm-preview">
        <div class="an-dm-from"><i data-lucide="user" style="width:12px;height:12px;"></i> ${escapeHtml(from)}</div>
        <div class="an-dm-bubble">
          <div class="an-dm-line">${escapeHtml(f.body) || '<span style="color:#666">(النص)</span>'}</div>
          ${f.link ? `<div class="an-dm-gap"></div><div class="an-dm-line an-dm-url">${escapeHtml(location.origin + '/' + f.link.replace(/^\//, ''))}</div>` : ''}
        </div>
        <div class="an-preview-time">هتوصل في الرسايل الخاصة · الردود بترجع لـ ${escapeHtml(from)}</div>
      </div>` + anNameNoteHTML(personalized, shownName, raw);
    if (window.lucide) lucide.createIcons();
    return;
  }

  box.innerHTML = `
    <div class="an-preview-row" style="border-inline-start:3px solid ${meta.color}">
      <div class="an-preview-icon" style="background:${meta.color}1f;color:${meta.color}">
        <i data-lucide="${meta.icon}" style="width:16px;height:16px;"></i>
      </div>
      <div class="an-preview-text">
        <!-- No heading line: the bell promotes the body into the name slot for
             a title-less notification (renderGlobalNotifList in utils.js), so
             drawing a second line here would preview a row the member never
             gets. -->
        <div class="an-preview-title">${escapeHtml(f.body) || '<span style="color:#666">(الرسالة)</span>'}</div>
        <div class="an-preview-time">دلوقتي حالاً${f.link ? ' · بيروح لـ ' + escapeHtml(f.link) : ''}</div>
      </div>
    </div>` + anNameNoteHTML(personalized, shownName, raw);
  if (window.lucide) lucide.createIcons();
}


// The half of the preview that exists to show the operator the case they would
// otherwise never look at.
//
// A preview that only ever shows `أهلاً محمد` is a preview of the best member
// in the audience. The one that decides whether the wording ships is the member
// whose name does not arabise — they see `أهلاً Radhouane` in the middle of an
// Arabic sentence, or `أهلاً صديقنا` if they have no usable name at all. That
// is a judgement call, and it cannot be made against a sample that excludes it.
function anNameNoteHTML(personalized, shownName, raw) {
  if (!personalized) return '';
  const p = anPersonal;

  if (!shownName) {
    return `<div class="an-name-note warn">
      <b>{{name}}</b> — لسه مامسكناش جمهور نجرّب عليه.
      اضبط الفلتر فوق وهتشوف الاسم بيتحل على عضو حقيقي منهم.
    </div>`;
  }

  const src = (p.sample_named && p.sample_named.full_name) || '';
  let html = `<div class="an-name-note">
      <b>{{name}}</b> اتحل على <b>${escapeHtml(shownName)}</b>
      — من <span class="an-name-src">${escapeHtml(src)}</span>، عضو حقيقي في الجمهور ده.
    </div>`;

  const bad = p.sample_unresolved;
  if (bad) {
    const kind = p.unresolved_kind === 'fallback'
      ? `مالوش اسم نقدر نستخدمه، فهيتنادى <b>${escapeHtml(p.fallback_word)}</b>`
      : `اسمه مش في قايمة التعريب، فهيتعرض زي ما هو كتبه: <b>${escapeHtml(bad.resolved)}</b>`;
    const n = p.unresolved_kind === 'fallback' ? p.fallback_count : p.latin_count;
    html += `<div class="an-name-note warn">
      و<b>${n}</b> من <b>${p.total}</b> ${kind}
      — <span class="an-name-src">${escapeHtml(bad.full_name || '')}</span> هيشوف:
      <div class="an-name-example">${escapeHtml(anFillName(raw.body, bad.resolved))}</div>
    </div>`;
  }
  return html;
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
  if (a.member_ids && a.member_ids.length) {
    a.member_ids.forEach(id => qs.append('member_ids', id));
  }
  if (a.search) qs.set('search', a.search);
  if (a.country) qs.set('country', a.country);
  if (a.governorate) qs.set('governorate', a.governorate);
  if (a.status) qs.set('status', a.status);
  if (a.plan) qs.set('plan', a.plan);
  if (a.expiring_days != null && !Number.isNaN(a.expiring_days)) qs.set('expiring_days', a.expiring_days);
  // The percentage carries the filter; the course only narrows it. Sending a
  // course with no percentage would be a filter that means nothing, and the
  // server would ignore it anyway.
  if (a.progress_min_percent != null && !Number.isNaN(a.progress_min_percent)) {
    qs.set('progress_min_percent', a.progress_min_percent);
    if (a.progress_course_id) qs.set('progress_course_id', a.progress_course_id);
  }
  if (a.include_staff) qs.set('include_staff', 'true');

  countEl.textContent = '…';
  subEl.textContent = 'بنحسب الجمهور...';

  try {
    const res = await authFetch(`${API}/admin/announcements/audience/preview?${qs}`);
    if (!res.ok) throw new Error('failed');
    const d = await res.json();

    countEl.textContent = d.count;
    const dm = anDelivery() === 'dm';
    const picked = anAudMode === 'picked';
    subEl.textContent = d.count === 0
      ? (picked ? 'مختارتش حد لسه — دوّر بالاسم أو الإيميل فوق' : 'الفلتر ده مالوش أي عضو — عدّله')
      : (dm
          ? `محادثة خاصة جديدة هتتفتح · ${d.online_now} منهم متصل دلوقتي`
          : `عضو هيوصلهم الإشعار · ${d.online_now} منهم متصل دلوقتي هيشوفه فوراً`)
        + (d.truncated ? ' · (متقطوع عند الحد الأقصى)' : '');

    sampleEl.innerHTML = (d.sample || []).map(u =>
      `<span class="an-chip${u.is_active ? '' : ' off'}">${escapeHtml(u.full_name || '—')}</span>`
    ).join('') + (d.count > (d.sample || []).length
      ? `<span class="an-chip more">+${d.count - d.sample.length}</span>` : '');

    // The personalization facts are computed on the server from the SAME
    // resolved list the send walks, so this line cannot disagree with what
    // actually goes out. Stored for the composer preview, which resolves
    // {{name}} against these very members.
    anPersonal = d.personalization || null;
    anRenderPreview();          // also refreshes the coverage line

    if (!anFacetsLoaded) { anFillFacets(d); anFacetsLoaded = true; }
  } catch (e) {
    countEl.textContent = '—';
    subEl.textContent = 'مقدرناش نحسب الجمهور';
    sampleEl.innerHTML = '';
    anPersonal = null;
    anRenderNameCoverage();      // clear the stale line; the preview text stands
  }
}


// One line under the count: how many of these people will NOT be greeted by an
// Arabic name.
//
// It lives here, under the number it qualifies, and not in a report — this is
// where the operator decides whether to send now or go fix the wording, and a
// fact that arrives after that decision has not been delivered.
//
// Silent when the campaign has no {{name}} in it: there is nothing to warn
// about, and a permanent zero teaches people to stop reading the line.
function anRenderNameCoverage() {
  const el = document.getElementById('an-aud-names');
  if (!el) return;

  const p = anPersonal;
  if (!p || !p.total || !anHasNameToken(anReadForm())) {
    el.innerHTML = '';
    el.style.display = 'none';
    return;
  }

  el.style.display = '';
  const bits = [];
  if (p.fallback_count) {
    bits.push(`<b>${p.fallback_count}</b> من <b>${p.total}</b> هيتنادوا «${escapeHtml(p.fallback_word)}»`);
  }
  if (p.latin_count) {
    bits.push(`<b>${p.latin_count}</b> من <b>${p.total}</b> هيتنادوا باسمهم اللاتيني زي ما هو`);
  }
  if (!bits.length) {
    el.innerHTML = `<span class="ok">كل الـ ${p.total} هيتنادوا باسمهم بالعربي ✓</span>`;
    return;
  }
  el.innerHTML = `<span class="warn">${bits.join(' · ')}</span>`;
}

// ═══ MEMBER PICKER ═══
//
// "Send to exactly these people, by name or email." The filter and the picker
// are mutually exclusive: the server drops the other filters when a picked list
// is present, so offering both at once would show a count that is not what
// gets sent.
//
// Searching BY email only works for an operator who is allowed to SEE emails
// (`member-contacts`). That is not a detail — a search that matches on a field
// it will not display is an email-guessing tool, which is the thing that
// permission exists to prevent. The server enforces it; this only reflects it.

function anSetAudMode(mode) {
  anAudMode = mode === 'picked' ? 'picked' : 'filter';
  const picked = anAudMode === 'picked';
  const f = document.getElementById('an-filter-wrap');
  const p = document.getElementById('an-picker-wrap');
  if (f) f.style.display = picked ? 'none' : '';
  if (p) p.style.display = picked ? '' : 'none';
  const bf = document.getElementById('an-mode-filter');
  const bp = document.getElementById('an-mode-picked');
  if (bf) bf.classList.toggle('active', !picked);
  if (bp) bp.classList.toggle('active', picked);
  anRenderPicked();
  anRefreshAudience();
  if (window.lucide) lucide.createIcons();
}

function anPickHintText() {
  return anPickSeesContacts
    ? 'بيدوّر في الأسماء والإيميلات.'
    : 'بيدوّر في الأسماء بس — عرض الإيميلات محتاج صلاحية «بيانات التواصل».';
}

async function anPickSearch() {
  const box = document.getElementById('an-pick-search');
  const out = document.getElementById('an-pick-results');
  if (!box || !out) return;
  const term = (box.value || '').trim();
  if (term.length < 2) { out.innerHTML = ''; return; }

  out.innerHTML = '<div class="an-pick-empty">بيدوّر…</div>';
  try {
    const res = await authFetch(`${API}/admin/announcements/members/search?q=${encodeURIComponent(term)}`);
    if (!res.ok) throw new Error('failed');
    const d = await res.json();
    anPickSeesContacts = !!d.sees_contacts;
    const hint = document.getElementById('an-pick-hint');
    if (hint) hint.textContent = anPickHintText();

    const items = (d.items || []).filter(u => !anPicked.some(m => m.id === u.id));
    out.innerHTML = items.length
      ? items.map(u => `
          <button type="button" class="an-pick-row" onclick="anPickAdd(${u.id})">
            <span class="an-pick-name">${escapeHtml(u.full_name || '—')}</span>
            ${u.email ? `<span class="an-pick-mail">${escapeHtml(u.email)}</span>` : ''}
            ${u.is_staff ? '<span class="an-pick-tag staff">أدمن</span>' : ''}
            ${u.is_active ? '' : '<span class="an-pick-tag off">مش نشط</span>'}
            <i data-lucide="plus" style="width:13px;height:13px;"></i>
          </button>`).join('')
      : '<div class="an-pick-empty">مفيش حد مطابق</div>';
    window.__anPickLast = d.items || [];
    if (window.lucide) lucide.createIcons();
  } catch (e) {
    out.innerHTML = '<div class="an-pick-empty">مقدرناش ندوّر</div>';
  }
}

function anPickAdd(id) {
  const found = (window.__anPickLast || []).find(u => u.id === id);
  if (!found || anPicked.some(m => m.id === id)) return;
  anPicked.push(found);
  const box = document.getElementById('an-pick-search');
  if (box) box.value = '';
  const out = document.getElementById('an-pick-results');
  if (out) out.innerHTML = '';
  anRenderPicked();
  anRefreshAudience();
}

function anPickRemove(id) {
  anPicked = anPicked.filter(m => m.id !== id);
  anRenderPicked();
  anRefreshAudience();
}

function anPickClear() {
  anPicked = [];
  anRenderPicked();
  anRefreshAudience();
}

function anRenderPicked() {
  const box = document.getElementById('an-pick-chips');
  if (!box) return;
  if (!anPicked.length) {
    box.innerHTML = '<div class="an-pick-empty">مفيش حد مختار لسه.</div>';
    return;
  }
  box.innerHTML = anPicked.map(m => `
      <span class="an-pick-chip${m.is_active ? '' : ' off'}">
        ${escapeHtml(m.full_name || '—')}
        <button type="button" class="an-pick-x" onclick="anPickRemove(${m.id})" aria-label="شيل">✕</button>
      </span>`).join('')
    + `<button type="button" class="an-mini" onclick="anPickClear()">امسح الكل (${anPicked.length})</button>`;
}

// A saved campaign stores ids. Whoever opens it has to see WHO those are before
// they send, so the names are fetched back rather than shown as numbers.
async function anLoadPicked(ids) {
  anPicked = [];
  if (!ids || !ids.length) { anRenderPicked(); return; }
  const qs = new URLSearchParams();
  ids.forEach(id => qs.append('ids', id));
  try {
    const res = await authFetch(`${API}/admin/announcements/members/resolve?${qs}`);
    if (res.ok) {
      const d = await res.json();
      anPickSeesContacts = !!d.sees_contacts;
      anPicked = d.items || [];
    }
  } catch (e) { /* names unavailable; the ids are still what will be sent */ }
  anRenderPicked();
}

function anFillFacets(d) {
  const fill = (id, options, empty) => {
    const sel = document.getElementById(id);
    if (!sel) return;
    const current = sel.value;
    sel.innerHTML = `<option value="">${empty}</option>` +
      options.map(o => `<option value="${escapeHtml(o.value)}">${escapeHtml(o.text)}</option>`).join('');
    sel.value = current;
  };
  const plain = v => ({ value: v, text: v });
  fill('an-aud-country', (d.countries || []).map(plain), 'الكل');
  fill('an-aud-gov', (d.governorates || []).map(plain), 'الكل');
  fill('an-aud-course', (d.courses || []).map(c => ({ value: c.id, text: c.title })), 'أي كورس');
}

// ═══ SAVED SEGMENTS ═══
//
// A segment stores the FILTER, never a resolved member list — the same reason
// the campaign does. "اللي اشتراكه بيخلص الأسبوع ده" has to mean different
// people next week. Deleting one does not touch the campaigns built from it:
// each campaign copied the filter into its own row when it was saved.

async function anLoadSegments() {
  try {
    const res = await authFetch(`${API}/admin/announcements/segments`);
    if (!res.ok) return;
    anSegments = await res.json();
  } catch (e) { anSegments = []; }
  anFillSegments();
}

function anFillSegments() {
  const sel = document.getElementById('an-segment');
  if (!sel) return;
  sel.innerHTML = '<option value="">— اختار مقطع محفوظ —</option>' +
    anSegments.map(s => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('');
  const del = document.getElementById('an-seg-del');
  if (del) del.style.display = 'none';
}

function anApplySegment() {
  const sel = document.getElementById('an-segment');
  const seg = anSegments.find(s => String(s.id) === String(sel && sel.value));
  const del = document.getElementById('an-seg-del');
  if (del) del.style.display = seg ? '' : 'none';
  if (!seg) return;
  anWriteAudienceFields(seg.filters);
  anRefreshAudience();
  showToast(`🎯 اتطبّق المقطع «${seg.name}»`, 'success');
}

async function anSaveSegment() {
  const name = (prompt('اسم المقطع (مثال: النشطين في مصر)') || '').trim();
  if (!name) return;
  try {
    const res = await authFetch(`${API}/admin/announcements/segments`, {
      method: 'POST',
      body: JSON.stringify({ name, filters: anReadForm().audience }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'failed');
    await anLoadSegments();
    anSetField('an-segment', data.id);
    const del = document.getElementById('an-seg-del');
    if (del) del.style.display = '';
    showToast('🎯 المقطع اتحفظ', 'success');
  } catch (e) {
    showToast(`❌ ${e.message || 'مقدرناش نحفظ المقطع'}`, 'error');
  }
}

async function anDeleteSegment() {
  const sel = document.getElementById('an-segment');
  const seg = anSegments.find(s => String(s.id) === String(sel && sel.value));
  if (!seg) return;
  if (!confirm(`تمسح المقطع «${seg.name}»؟ الحملات اللي اتعملت منه مش هتتأثر.`)) return;
  try {
    const res = await authFetch(`${API}/admin/announcements/segments/${seg.id}`, { method: 'DELETE' });
    if (!res.ok && res.status !== 204) throw new Error('failed');
    await anLoadSegments();
    showToast('🗑️ المقطع اتمسح', 'success');
  } catch (e) {
    showToast('❌ مقدرناش نمسح المقطع', 'error');
  }
}

// ═══ SAVE / DELETE / DUPLICATE ═══

async function anSaveCampaign() {
  const body = anReadForm();
  if (!body.body.trim()) {
    showToast('❌ الحملة محتاجة نص', 'error');
    return false;
  }

  // A failed campaign that already reached members is frozen server-side. Do
  // not send a doomed PUT: skip the save and let the send resume the campaign
  // exactly as it stands.
  if (anCurrent && anCurrent.status === 'failed' && (anCurrent.delivered || 0) > 0) {
    return true;
  }

  try {
    const url = anCurrent ? `${API}/admin/announcements/${anCurrent.id}` : `${API}/admin/announcements`;
    const res = await authFetch(url, {
      method: anCurrent ? 'PUT' : 'POST',
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'failed');

    anCurrent = await res.json();
    document.getElementById('an-editor-title').textContent = '📢 ' + (anCurrent.label || 'حملة');
    showToast('✅ اتحفظت — مفيش أي إشعار اتبعت', 'success');
    loadAnnouncementsList();
    return true;
  } catch (e) {
    showToast(`❌ ${e.message || 'مقدرناش نحفظ'}`, 'error');
    return false;
  }
}

async function anDelete(id) {
  if (!confirm('تمسح الحملة دي؟ اللي وصل للأعضاء هيفضل عندهم.')) return;
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
    anList.offset = 0;
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
  const dm = anDelivery() === 'dm';

  if (mode === 'real') {
    const typed = ((document.getElementById('an-confirm') || {}).value || '').trim();
    if (typed !== AN_CONFIRM_PHRASE) {
      showToast(`❌ اكتب ${AN_CONFIRM_PHRASE} بالظبط في خانة التأكيد`, 'error');
      return;
    }
    if (!anConfirmSend(dm)) return;
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

// The dialog is where the decision is actually made, so the consequence is
// stated here rather than in a tooltip somewhere above it. In DM mode that
// consequence is not "N notifications" — it is N real conversations, all of
// them landing in one named person's inbox, and replies that person did not
// ask for.
function anConfirmSend(dm) {
  const count = (document.getElementById('an-aud-count') || {}).textContent || '?';
  const resuming = anCurrent && anCurrent.status === 'failed' && (anCurrent.delivered || 0) > 0;

  if (!dm) {
    const msg = resuming
      ? `هتكمّل الحملة دي. ${anCurrent.delivered} عضو استلموها خلاص ومش هياخدوها تاني — الباقي بس. تكمّل؟`
      : `هتبعت الحملة دي لـ ${count} عضو دلوقتي. الخطوة دي مش بترجع. تكمّل؟`;
    return confirm(msg);
  }

  const from = anSenderName();
  const head = resuming
    ? `هتكمّل حملة رسايل خاصة. ${anCurrent.delivered} عضو استلموها خلاص، والباقي هياخدوها دلوقتي.`
    : `هتبعت رسالة خاصة لـ ${count} عضو دلوقتي.`;
  return confirm(
    `${head}\n\n` +
    `الرسالة هتوصلهم من حساب: ${from}\n\n` +
    `⚠️ دي مش إشعار — دي محادثة خاصة حقيقية مع كل واحد فيهم.\n` +
    `أي رد هيرجع في الرسايل الخاصة بتاعة ${from}، ` +
    `يعني ${count} محادثة ممكن تتفتح في بريد شخص واحد.\n\n` +
    `الخطوة دي مش بترجع. تكمّل؟`
  );
}


// ═══ SEND STATUS ═══

// Polls one campaign until it stops being "sending". The status lives in the
// database, so this survives the tab being reopened; what it cannot see is a
// worker that died mid-send, which the endpoint reports as `stalled` — and
// which is now a state you resume from rather than a dead end.
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
        showToast(`✅ الحملة وصلت لـ ${st.delivered} ${st.delivery === 'dm' ? 'رسالة خاصة' : 'عضو'}`, 'success');
      } else if (st.status === 'failed') {
        showToast(`❌ الإرسال وقف بعد ${st.delivered} — اضغط «كمّل» عشان يبعت للباقي`, 'error');
      }
      return;
    }

    if (st.stalled) {               // status says sending, nothing is running
      await loadAnnouncementsList();
      showToast(`⚠️ الإرسال وقف في النص بعد ${st.delivered} — «كمّل» بيبعت للباقي بس`, 'error');
      return;
    }
  }
}


// ═══ RECIPIENTS ═══
//
// "نسبة القراءة ٣١%" مابيقولش مين الـ ٦٩%. الداتا كانت موجودة أصلاً — الصفوف
// اللي شايلة الـ announcement_id مربوطة باليوزرز — بس مكانش ليها شاشة.
// الافتراضي هنا "مافتحوهاش" مش "الكل": ده السؤال اللي بيتفتح الدرج عشانه.
// الوضعين (جرس/رسالة خاصة) بيرجّعوا نفس الشكل من السيرفر، فالدرج واحد.

let anRcpState = { id: null, state: 'unread', search: '', offset: 0, limit: 50, items: [] };

function anRcpClose() {
  const d = document.getElementById('an-rcp-drawer');
  if (d) d.remove();
  anRcpState.id = null;
}

async function anOpenRecipients(id) {
  anRcpState = { id, state: 'unread', search: '', offset: 0, limit: 50, items: [] };
  if (!document.getElementById('an-rcp-drawer')) {
    const el = document.createElement('div');
    el.id = 'an-rcp-drawer';
    el.className = 'an-rcp-backdrop';
    // The drawer is appended to <body>, so it sits outside the panel's
    // dir="rtl" and would inherit the document's LTR. Its content is Arabic.
    el.dir = 'rtl';
    el.onclick = (e) => { if (e.target === el) anRcpClose(); };
    el.innerHTML = `
      <div class="an-rcp-panel" role="dialog" aria-modal="true">
        <div class="an-rcp-head">
          <div class="an-rcp-title">مين استلم الحملة</div>
          <button class="an-rcp-x" onclick="anRcpClose()" aria-label="اقفل">✕</button>
        </div>
        <div class="an-rcp-tabs">
          <button class="an-rcp-tab" data-state="unread" onclick="anRcpSetState('unread')">مافتحوهاش</button>
          <button class="an-rcp-tab" data-state="read"   onclick="anRcpSetState('read')">فتحوها</button>
          <button class="an-rcp-tab" data-state="all"    onclick="anRcpSetState('all')">الكل</button>
        </div>
        <input class="an-rcp-search" id="an-rcp-search" type="search" placeholder="دوّر باسم أو إيميل…" />
        <div class="an-rcp-summary" id="an-rcp-summary"></div>
        <div class="an-rcp-list" id="an-rcp-list"></div>
        <div class="an-rcp-foot"><button class="an-mini" id="an-rcp-more" onclick="anRcpMore()">حمّل كمان</button></div>
      </div>`;
    document.body.appendChild(el);
    const box = document.getElementById('an-rcp-search');
    let t = null;
    box.addEventListener('input', () => {
      clearTimeout(t);
      t = setTimeout(() => { anRcpState.search = box.value; anRcpState.offset = 0; anRcpState.items = []; anRcpLoad(); }, 300);
    });
  }
  await anRcpLoad();
}

function anRcpSetState(state) {
  anRcpState.state = state;
  anRcpState.offset = 0;
  anRcpState.items = [];
  anRcpLoad();
}

function anRcpMore() {
  anRcpState.offset += anRcpState.limit;
  anRcpLoad(true);
}

async function anRcpLoad(append) {
  const s = anRcpState;
  if (!s.id) return;
  const list = document.getElementById('an-rcp-list');
  if (list && !append) list.innerHTML = '<div class="an-rcp-empty">بيحمّل…</div>';

  const qs = new URLSearchParams({ state: s.state, limit: s.limit, offset: s.offset });
  if (s.search) qs.set('search', s.search);

  let data;
  try {
    const res = await authFetch(`${API}/admin/announcements/${s.id}/recipients?${qs}`);
    if (!res.ok) throw new Error('failed');
    data = await res.json();
  } catch (e) {
    if (list) list.innerHTML = '<div class="an-rcp-empty">مقدرناش نحمّل القائمة</div>';
    return;
  }

  s.items = append ? s.items.concat(data.items) : data.items;

  document.querySelectorAll('.an-rcp-tab').forEach(b =>
    b.classList.toggle('active', b.dataset.state === s.state));

  const title = document.querySelector('.an-rcp-title');
  if (title) title.textContent = data.delivery === 'dm' ? 'مين وصلته الرسالة' : 'مين استلم الحملة';

  const sum = document.getElementById('an-rcp-summary');
  if (sum) {
    sum.innerHTML = `
      <span><b>${data.delivered}</b> ${data.delivery === 'dm' ? 'وصلتهم' : 'اتسلّمت'}</span>
      <span><b>${data.read}</b> فتحوها</span>
      <span><b>${data.unread}</b> مافتحوهاش</span>`;
  }

  if (list) {
    list.innerHTML = s.items.length
      ? s.items.map(u => `
          <div class="an-rcp-row">
            <div class="an-rcp-av">${u.avatar_url
                ? `<img src="${escapeHtml(u.avatar_url.startsWith('http') ? u.avatar_url : API + u.avatar_url)}" alt="" onerror="this.remove()"/>`
                : ''}</div>
            <div class="an-rcp-who">
              <div class="an-rcp-name">${escapeHtml(u.full_name || '—')}</div>
              <div class="an-rcp-mail">${escapeHtml(u.email || '')}</div>
            </div>
            <span class="an-rcp-flag ${u.is_read ? 'read' : 'unread'}">${u.is_read ? 'فتحها' : 'مافتحهاش'}</span>
          </div>`).join('')
      : '<div class="an-rcp-empty">مفيش حد هنا</div>';
  }

  const more = document.getElementById('an-rcp-more');
  if (more) more.style.display = data.has_more ? '' : 'none';
}


// ═══ SCHEDULING ═══
//
// The confirm phrase is required to SCHEDULE, not to fire. Somebody decides to
// send this text to this audience while they are sitting here; the scheduler
// then carries that decision out at 8pm with nobody present. Asking for the
// phrase at fire time would mean asking nobody.
//
// A campaign that misses its slot by more than a few hours is NOT sent late —
// the server closes it out with a reason instead. See the router docstring.

function anSchedStateHTML(c) {
  if (!c || c.status !== 'scheduled') return '';
  return `⏳ مجدولة: ${escapeHtml(anFmtDate(c.scheduled_for))} — لو فات ميعادها بأكتر من 3 ساعات (توقف أو ديبلوي) مش هتتبعت متأخرة، هتتقفل وتقولك السبب.`;
}

function anRenderSchedState() {
  const box = document.getElementById('an-sched-state');
  const cancel = document.getElementById('an-unsched-btn');
  const scheduled = !!(anCurrent && anCurrent.status === 'scheduled');
  if (box) box.innerHTML = anSchedStateHTML(anCurrent);
  if (cancel) cancel.style.display = scheduled ? '' : 'none';
}

async function anSchedule() {
  if (!anCurrent || !anCurrent.id) {
    showToast('❌ احفظ الحملة الأول', 'error');
    return;
  }
  const when = (document.getElementById('an-sched-at') || {}).value || '';
  if (!when) {
    showToast('❌ اختار التاريخ والوقت الأول', 'error');
    return;
  }
  const typed = ((document.getElementById('an-confirm') || {}).value || '').trim();
  if (typed !== AN_CONFIRM_PHRASE) {
    showToast(`❌ اكتب ${AN_CONFIRM_PHRASE} بالظبط في خانة التأكيد عشان تجدول`, 'error');
    return;
  }
  const count = (document.getElementById('an-aud-count') || {}).textContent || '?';
  const local = new Date(when);
  const dm = anDelivery() === 'dm';
  const extra = dm
    ? `\n\n⚠️ دي رسايل خاصة من حساب ${anSenderName()} — الردود هترجع في الرسايل الخاصة بتاعته.`
    : '';
  if (!confirm(`هتتبعت لـ ${count} عضو في ${local.toLocaleString('ar-EG')}.${extra}\n\nتكمّل؟`)) return;

  try {
    // datetime-local has no zone; the browser read it as local time, so send an
    // absolute instant and let the server store UTC rather than guessing.
    const res = await authFetch(`${API}/admin/announcements/${anCurrent.id}/schedule`, {
      method: 'POST',
      body: JSON.stringify({ scheduled_for: local.toISOString(), confirm_phrase: typed }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'failed');
    anCurrent = data;
    anSetField('an-confirm', '');
    anRenderSchedState();
    showToast('✅ الحملة اتجدولت', 'success');
    await loadAnnouncementsList();
    anBackToList();
  } catch (e) {
    showToast(`❌ ${e.message || 'الجدولة فشلت'}`, 'error');
  }
}

async function anUnschedule(id) {
  const target = id || (anCurrent && anCurrent.id);
  if (!target) return;
  try {
    const res = await authFetch(`${API}/admin/announcements/${target}/unschedule`, { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'failed');
    if (anCurrent && anCurrent.id === target) {
      anCurrent = data;
      anRenderSchedState();
    }
    showToast('✅ اتلغت الجدولة — بقت مسودة', 'success');
    await loadAnnouncementsList();
  } catch (e) {
    showToast(`❌ ${e.message || 'مقدرناش نلغي الجدولة'}`, 'error');
  }
}
