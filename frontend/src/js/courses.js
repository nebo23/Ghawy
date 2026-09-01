/* ═══ MEMBER COURSES PAGE — search, filters, cards ═══════════════
 *
 * Drives dashboard-courses.html and nothing else. The card markup itself is
 * shared with the dashboard and lives in course-card.js.
 *
 * ── Three requests, not N+1 ──
 * The page used to fetch /courses and then loop over the result calling
 * /courses/{id}/progress once per course. Sorting by progress would have meant
 * waiting for every one of those before the first card could move. It now makes
 * exactly three calls, in parallel:
 *
 *   GET /courses                  the published list
 *   GET /courses/progress/summary this member's progress in all of them
 *   GET /courses/stats            learners / completions / rating per course
 *
 * The last two are new (backend/app/routers/courses.py). Neither is required
 * for the page to work: without progress the bars sit at zero, without stats the
 * two popularity sorts fall back to the catalogue order.
 *
 * ── Everything else is client-side ──
 * There are nine courses. Sending a request per keystroke to filter nine rows
 * would be a worse experience and a worse server. Search, filters and sorting
 * all run over the list already in memory; the only cost of a keystroke is a
 * re-render, debounced by 200ms.
 *
 * ── State lives in the URL ──
 * ?q=&sort=&track=&instructor=&progress=&duration= — so a filtered view can be
 * refreshed, shared, or returned to with the Back button and still be the same
 * view. The URL is the single source of truth on load and is rewritten (via
 * replaceState, so typing does not fill the history) on every change.
 */

(async () => {
  const user = await requireActiveUser();
  if (!user) return;
})();

// ═══ AUTH GUARD ═══
const token = getToken();
if (!token) { localStorage.removeItem('user'); window.location.href = '/login'; }

const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

async function apiFetch(url, opts = {}) {
    opts.headers = { ...headers, ...opts.headers };
    const res = await fetch(API + url, opts);
    if (res.status === 401) { localStorage.removeItem('token'); localStorage.removeItem('user'); window.location.href = '/login'; }
    return res;
}

function logout() { localStorage.removeItem('token'); localStorage.removeItem('user'); window.location.href = '/login'; }

// NOT `esc`: dashboard-new.js declares `function esc` at global scope and is
// loaded on this page too. A `const esc` here is a redeclaration, which is a
// SyntaxError that kills that entire file — taking the notification bell and
// the sidebar badges down with it, on a page that otherwise looks fine.
const escHTML = (s) => (window.escapeHtml ? window.escapeHtml(s) : String(s == null ? '' : s));
const CARD = () => window.GhawyCourseCard;

// ═══ LOAD PROFILE ═══
async function loadProfile() {
    try {
        const res = await apiFetch('/profile/me');
        if (!res.ok) return;
        const u = await res.json();
        const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        setTxt('sidebarName', u.full_name);
        setTxt('topbarName', u.full_name);
        setTxt('dropdownName', u.full_name);

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
                if (typeof buildAvatarHtml === 'function') {
                    el.innerHTML = buildAvatarHtml(u.full_name, u.avatar_url, u.id, 40);
                } else {
                    const fullUrl = window.getAvatarSrc(u);
                    el.innerHTML = `<img src="${fullUrl}" alt="" onerror="this.style.display='none'" style="width:100%;height:100%;object-fit:cover;border-radius:50%;" />`;
                }
            }
        });
    } catch (e) { console.error(e); }
}

/* ═══════════════════════════════════════════════════════════════
   SEARCH — normalisation
   ═══════════════════════════════════════════════════════════════
   Nothing is compared before it goes through here, on both sides. Arabic
   typed in a hurry is not the Arabic in the data: people leave off the hamza
   ("اساسيات" for "أساسيات"), end words with ه instead of ة, write ى for ي,
   paste Arabic-Indic digits, and type with or without diacritics. Folding all
   of those to one form is what makes the search find things instead of being
   technically correct and useless. */

const FOLD = {
    'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا',
    'ة': 'ه',
    'ى': 'ي', 'ی': 'ي',   /* alef maqsura, and Farsi yeh U+06CC */
    'ؤ': 'و',
    'ئ': 'ي',
    'ک': 'ك', 'گ': 'ك',
};

/* Latin letters, digits, and the Arabic block. Everything else separates words. */
const KEEP = /[0-9a-z\u0600-\u06FF]/;

/**
 * Normalise, and keep a map back to the original string.
 *
 * The map is what lets the highlighter put <mark> around the right slice of
 * the ORIGINAL text: map[i] is the index in the input of the character that
 * became normalised character i (-1 for a space this function inserted).
 * Without it, highlighting would have to re-find the match in unnormalised
 * text — which is exactly the comparison the normalisation exists to avoid.
 */
function normalizeParts(input) {
    const s = String(input == null ? '' : input);
    let out = '';
    const map = [];
    let pendingSpace = false;

    for (let i = 0; i < s.length; i++) {
        const ch = s[i];
        const code = s.charCodeAt(i);

        // Arabic diacritics (tashkeel) and the tatweel stretch character carry
        // no meaning for matching — drop them entirely.
        if ((code >= 0x064B && code <= 0x0652) || code === 0x0670 || code === 0x0640) continue;

        let c = FOLD[ch];
        if (c === undefined) {
            if (code >= 0x0660 && code <= 0x0669) c = String(code - 0x0660);        // ٠-٩
            else if (code >= 0x06F0 && code <= 0x06F9) c = String(code - 0x06F0);   // ۰-۹
            else c = ch.toLowerCase();
        }
        if (c.length !== 1) c = c[0];   // a locale-expanding lowercase, e.g. İ

        // Anything that is not a letter or a digit separates words.
        if (!KEEP.test(c)) {
            if (out.length) pendingSpace = true;
            continue;
        }
        if (pendingSpace) { out += ' '; map.push(-1); pendingSpace = false; }
        out += c;
        map.push(i);
    }
    return { text: out, map };
}

function normalizeSearchText(s) { return normalizeParts(s).text; }

function tokenize(s) {
    const t = normalizeSearchText(s);
    return t ? t.split(' ').filter(Boolean) : [];
}

/**
 * Levenshtein distance, abandoned as soon as it cannot come in under `max`.
 *
 * Only used for tokens of 4 characters or more, and only with max=1: at three
 * characters a single edit is most of the word, so "ml" would fuzzily match
 * half the catalogue. The early exit matters because this runs for every
 * token × every field token × every course on each keystroke.
 */
function levenshtein(a, b, max) {
    if (a === b) return 0;
    const la = a.length, lb = b.length;
    if (Math.abs(la - lb) > max) return max + 1;
    if (!la) return lb;
    if (!lb) return la;

    let prev = new Array(lb + 1);
    let cur = new Array(lb + 1);
    for (let j = 0; j <= lb; j++) prev[j] = j;

    for (let i = 1; i <= la; i++) {
        cur[0] = i;
        let best = i;
        const ca = a.charCodeAt(i - 1);
        for (let j = 1; j <= lb; j++) {
            const cost = ca === b.charCodeAt(j - 1) ? 0 : 1;
            cur[j] = Math.min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost);
            if (cur[j] < best) best = cur[j];
        }
        if (best > max) return max + 1;   // the whole row is already over budget
        const swap = prev; prev = cur; cur = swap;
    }
    return prev[lb];
}

/* ═══ SEARCH — the haystack ═══
   Weights say what a hit is worth. A course whose TITLE is "Machine Learning"
   should beat one that merely mentions machine learning in its description, so
   the same word is worth five times as much in one place as the other. */
const FIELDS = [
    { key: 'title', weight: 5 },
    { key: 'instructor', weight: 4 },
    { key: 'track', weight: 3 },
    { key: 'keywords', weight: 2 },
    { key: 'description', weight: 1 },
];

function buildField(values) {
    const text = normalizeSearchText((values || []).filter(Boolean).join(' '));
    return { text, tokens: text ? text.split(' ').filter(Boolean) : [] };
}

/** How well one query token hits one field: 0 for no hit, up to 1 for exact. */
function fieldMatch(field, token) {
    if (!field || !field.text) return 0;
    const toks = field.tokens;
    for (let i = 0; i < toks.length; i++) if (toks[i] === token) return 1;
    // A prefix is what makes an unfinished word work — "machine" while the
    // member is still typing "machine learning", or "تعلم ال" for "تعلم الآلة".
    for (let i = 0; i < toks.length; i++) if (toks[i].indexOf(token) === 0) return 0.8;
    if (field.text.indexOf(token) !== -1) return 0.55;
    if (token.length >= 4) {
        for (let i = 0; i < toks.length; i++) {
            if (levenshtein(token, toks[i], 1) <= 1) return 0.35;
        }
    }
    return 0;
}

/**
 * Score one course against one query. 0 means "not a result".
 *
 * Every token has to land SOMEWHERE (AND, not OR) — two words the member typed
 * together describe one thing, and a course that answers only the first of them
 * is not what they asked for.
 */
function scoreCourse(course, tokens, normQuery) {
    let total = 0;
    for (const token of tokens) {
        let hit = 0;
        for (const f of FIELDS) {
            const q = fieldMatch(course.hay[f.key], token);
            if (q > 0) { total += f.weight * q; hit = Math.max(hit, q); }
        }
        if (!hit) return 0;
    }
    // Whole-query bonuses: an exact title beats a title that merely starts with
    // the query, which beats a title that contains it somewhere in the middle.
    if (course.normTitle === normQuery) total += 12;
    else if (course.normTitle.indexOf(normQuery) === 0) total += 7;
    else if (course.hay.title.text.indexOf(normQuery) === 0) total += 4;
    return total;
}

/* ═══ SEARCH — highlighting ═══ */

/** Character ranges of the ORIGINAL string that the query tokens matched. */
function matchRanges(original, tokens) {
    const { text, map } = normalizeParts(original);
    if (!text) return [];
    const ranges = [];

    for (const token of tokens) {
        // Prefer a hit at the start of a word — highlighting "ation" inside
        // "Foundations" for the query "ation" is technically a match and reads
        // as a glitch.
        let at = -1;
        let from = 0;
        while (from <= text.length) {
            const i = text.indexOf(token, from);
            if (i === -1) break;
            if (i === 0 || text[i - 1] === ' ') { at = i; break; }
            if (at === -1) at = i;
            from = i + 1;
        }
        if (at === -1) continue;

        const start = map[at];
        const endChar = map[at + token.length - 1];
        if (start == null || start < 0 || endChar == null || endChar < 0) continue;
        ranges.push([start, endChar + 1]);
    }

    ranges.sort((a, b) => a[0] - b[0]);
    const merged = [];
    for (const r of ranges) {
        const last = merged[merged.length - 1];
        if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
        else merged.push(r.slice());
    }
    return merged;
}

/**
 * The title with its matched parts wrapped in <mark>.
 *
 * Built out of escaped slices, never by running a replace over raw text — a
 * course title is admin-entered, so treating it as markup is the same mistake
 * as trusting any other stored string.
 */
function highlightTitle(original, tokens) {
    const ranges = tokens.length ? matchRanges(original, tokens) : [];
    if (!ranges.length) return null;
    let out = '';
    let pos = 0;
    for (const [start, end] of ranges) {
        out += escHTML(original.slice(pos, start)) + '<mark>' + escHTML(original.slice(start, end)) + '</mark>';
        pos = end;
    }
    return out + escHTML(original.slice(pos));
}

/* ═══════════════════════════════════════════════════════════════
   FILTER DEFINITIONS
   ═══════════════════════════════════════════════════════════════
   One table drives the dropdowns, the chips, the URL keys and the filtering.
   Adding a filter means adding an entry here and one case in `passes()`. */

const DEFAULTS = { q: '', sort: 'default', track: 'all', instructor: 'all', progress: 'all', duration: 'any' };
const state = { ...DEFAULTS };

const SORTS = [
    { value: 'default', label: 'All Courses' },
    { value: 'newest', label: 'Newest' },
    { value: 'oldest', label: 'Oldest' },
    { value: 'watched', label: 'Most Watched' },
    { value: 'engaged', label: 'Most Engaged' },
    { value: 'shortest', label: 'Shortest' },
    { value: 'longest', label: 'Longest' },
    { value: 'az', label: 'A–Z' },
    { value: 'za', label: 'Z–A' },
];

const PROGRESS_OPTS = [
    { value: 'all', label: 'All' },
    { value: 'not-started', label: 'Not Started' },
    { value: 'in-progress', label: 'In Progress' },
    { value: 'completed', label: 'Completed' },
];

const DURATION_OPTS = [
    { value: 'any', label: 'Any' },
    { value: 'under5', label: 'Under 5h' },
    { value: '5to10', label: '5–10h' },
    { value: 'over10', label: 'Over 10h' },
];

/* `idle` is the button's caption while the filter is on its default: the name
   of the thing it filters, because "All" on its own says nothing about what. */
const FILTERS = [
    { key: 'sort', idle: 'All Courses', options: () => SORTS, values: () => SORTS.map(o => o.value) },
    { key: 'track', idle: 'All Tracks', options: trackOptions, values: () => catalogKeys('TRACKS') },
    { key: 'instructor', idle: 'All Instructors', options: instructorOptions, values: () => catalogKeys('INSTRUCTORS') },
    { key: 'progress', idle: 'My Progress', options: () => PROGRESS_OPTS, values: () => PROGRESS_OPTS.map(o => o.value) },
    { key: 'duration', idle: 'Duration', options: () => DURATION_OPTS, values: () => DURATION_OPTS.map(o => o.value) },
];

/* `values()` is every value the URL may legally carry; `options()` is the
   shorter list actually worth offering. They differ because the URL is read
   BEFORE the courses arrive: validating a ?track= against the tracks the loaded
   courses happen to use would reject every one of them and silently drop the
   member's filter on refresh. */
function catalogKeys(bucket) {
    return ['all'].concat(Object.keys((window.GhawyCatalogData || {})[bucket] || {}));
}

function trackOptions() {
    const tracks = (window.GhawyCatalogData || {}).TRACKS || {};
    const seen = new Set(allCourses.map(c => c.trackSlug).filter(Boolean));
    const opts = [{ value: 'all', label: 'All Tracks' }];
    Object.keys(tracks).forEach(slug => {
        // Only tracks some course on THIS page belongs to — a filter that can
        // only ever return nothing is a trap, not a choice. The one already
        // selected always stays listed, so the dropdown can name what it is
        // showing even when that selection matches nothing.
        if (!seen.has(slug) && state.track !== slug) return;
        opts.push({ value: slug, label: CARD().L(tracks[slug].name), raw: true });
    });
    return opts;
}

function instructorOptions() {
    const people = (window.GhawyCatalogData || {}).INSTRUCTORS || {};
    const seen = new Set(allCourses.map(c => c.instructorSlug).filter(Boolean));
    const opts = [{ value: 'all', label: 'All Instructors' }];
    Object.keys(people).forEach(slug => {
        if (!seen.has(slug) && state.instructor !== slug) return;
        const p = people[slug];
        opts.push({ value: slug, label: CARD().L(p.name), photo: p.photo, raw: true });
    });
    return opts;
}

function optionLabel(key, value) {
    const filter = FILTERS.find(f => f.key === key);
    if (!filter) return value;
    const opt = filter.options().find(o => o.value === value);
    return opt ? opt.label : value;
}

/* ═══════════════════════════════════════════════════════════════
   MODEL
   ═══════════════════════════════════════════════════════════════ */

let allCourses = [];
let loaded = false;

function buildModel(courses, progress, stats) {
    const progressById = new Map((progress || []).map(p => [p.course_id, p]));
    const statsById = new Map((stats || []).map(s => [s.course_id, s]));
    const card = CARD();

    return (courses || []).map((c, index) => {
        const entry = card.catalogEntry(c.id);
        const inst = card.instructorFor(c.id);
        const track = card.trackFor(c.id);
        const p = progressById.get(c.id) || null;
        const s = statsById.get(c.id) || null;

        const model = {
            id: c.id,
            title: c.title,
            description: c.description || '',
            thumbnail_url: c.thumbnail_url,
            total_lessons: c.total_lessons || 0,
            course_time: c.course_time || '',
            created_at: c.created_at || '',
            order: index,
            pct: p ? Math.round(p.percentage || 0) : 0,
            minutes: card.durationToMinutes(c.course_time),
            learners: s ? (s.learners || 0) : -1,
            engagement: s ? (s.engagement_score || 0) : -1,
            trackSlug: track ? track.slug : '',
            instructorSlug: inst ? inst.slug : '',
        };

        model.display = card.title(model);
        model.normTitle = normalizeSearchText(model.display);
        model.hay = {
            title: buildField([model.display, c.title, entry && entry.title && entry.title.ar, entry && entry.title && entry.title.en]),
            instructor: buildField(inst ? [inst.name && inst.name.ar, inst.name && inst.name.en, inst.slug].concat(inst.aliases || []) : []),
            track: buildField(track ? [track.name && track.name.ar, track.name && track.name.en, track.slug] : []),
            keywords: buildField(entry ? (entry.keywords || []) : []),
            description: buildField([model.description]),
        };
        return model;
    });
}

/* ═══ FILTER + SORT ═══ */

function passesFilters(c) {
    if (state.track !== 'all' && c.trackSlug !== state.track) return false;
    if (state.instructor !== 'all' && c.instructorSlug !== state.instructor) return false;

    if (state.progress !== 'all') {
        const bucket = c.pct >= 100 ? 'completed' : (c.pct > 0 ? 'in-progress' : 'not-started');
        if (bucket !== state.progress) return false;
    }

    if (state.duration !== 'any') {
        // A course with no runtime yet (no lesson is ready) has no length to
        // compare, so it drops out of every length filter rather than being
        // treated as zero minutes and always winning "under 5h".
        if (!c.minutes) return false;
        if (state.duration === 'under5' && c.minutes >= 300) return false;
        if (state.duration === '5to10' && (c.minutes < 300 || c.minutes > 600)) return false;
        if (state.duration === 'over10' && c.minutes <= 600) return false;
    }
    return true;
}

function comparator() {
    const collator = new Intl.Collator(CARD().lang() === 'ar' ? 'ar' : 'en', { numeric: true, sensitivity: 'base' });
    switch (state.sort) {
        case 'newest': return (a, b) => String(b.created_at).localeCompare(String(a.created_at)) || a.order - b.order;
        case 'oldest': return (a, b) => String(a.created_at).localeCompare(String(b.created_at)) || a.order - b.order;
        case 'watched': return (a, b) => b.learners - a.learners || a.order - b.order;
        case 'engaged': return (a, b) => b.engagement - a.engagement || a.order - b.order;
        // Unknown length sorts last in BOTH directions — it is not the shortest
        // course, it is a course whose length nobody knows yet.
        case 'shortest': return (a, b) => (a.minutes || Infinity) - (b.minutes || Infinity) || a.order - b.order;
        case 'longest': return (a, b) => (b.minutes || -1) - (a.minutes || -1) || a.order - b.order;
        case 'az': return (a, b) => collator.compare(a.display, b.display);
        case 'za': return (a, b) => collator.compare(b.display, a.display);
        default: return (a, b) => a.order - b.order;
    }
}

function currentResults() {
    const tokens = tokenize(state.q);
    const normQuery = normalizeSearchText(state.q);
    const base = allCourses.filter(passesFilters);
    if (!tokens.length) return { list: base.sort(comparator()), tokens };

    const scored = [];
    for (const c of base) {
        const score = scoreCourse(c, tokens, normQuery);
        if (score > 0) scored.push({ c, score });
    }
    const tie = comparator();
    scored.sort((x, y) => y.score - x.score || tie(x.c, y.c));
    return { list: scored.map(x => x.c), tokens };
}

/** The three closest courses to a query that matched nothing — scored with OR
 *  instead of AND, so "machine automation" still suggests both. */
function suggestions(tokens) {
    const scored = allCourses.map(c => {
        let score = 0;
        for (const token of tokens) {
            for (const f of FIELDS) score += f.weight * fieldMatch(c.hay[f.key], token);
        }
        return { c, score };
    }).filter(x => x.score > 0);
    scored.sort((a, b) => b.score - a.score);
    return (scored.length ? scored : allCourses.map(c => ({ c, score: 0 }))).slice(0, 3).map(x => x.c);
}

/* ═══════════════════════════════════════════════════════════════
   URL STATE
   ═══════════════════════════════════════════════════════════════ */

function readURL() {
    const params = new URLSearchParams(location.search);
    Object.keys(DEFAULTS).forEach(key => {
        const raw = params.get(key);
        if (raw == null) { state[key] = DEFAULTS[key]; return; }
        if (key === 'q') { state.q = raw; return; }
        // Anything unrecognised falls back to the default instead of filtering
        // to an empty grid — a hand-edited or stale URL should degrade, not break.
        const filter = FILTERS.find(f => f.key === key);
        const known = filter && filter.values().indexOf(raw) !== -1;
        state[key] = known ? raw : DEFAULTS[key];
    });
}

function writeURL() {
    const params = new URLSearchParams(location.search);
    Object.keys(DEFAULTS).forEach(key => {
        if (state[key] && state[key] !== DEFAULTS[key]) params.set(key, state[key]);
        else params.delete(key);
    });
    const qs = params.toString();
    // replaceState, not push: a debounced keystroke must not add a history
    // entry, or Back becomes "delete one character".
    history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
}

function activeFilters() {
    return FILTERS.filter(f => state[f.key] !== DEFAULTS[f.key]);
}

/* ═══════════════════════════════════════════════════════════════
   RENDER
   ═══════════════════════════════════════════════════════════════ */

function stateHTML(icon, title, body, actions) {
    return `<div class="cx-state">
        <i class="cx-state-ico fa-solid ${icon}"></i>
        <h4>${title}</h4>
        <p>${body}</p>
        ${actions || ''}
    </div>`;
}

function renderGrid() {
    const grid = document.getElementById('coursesGrid');
    if (!grid) return;

    // Before the first response there is nothing to say about the results —
    // the skeleton is already on screen and must stay there.
    if (!loaded) return;

    const { list, tokens } = currentResults();

    if (!allCourses.length) {
        grid.innerHTML = stateHTML('fa-graduation-cap', 'No courses yet',
            'New courses show up here as soon as they are published.');
        renderCount(0);
        return;
    }

    if (!list.length) {
        const near = tokens.length ? suggestions(tokens) : [];
        const nearHTML = near.length ? `
            <div class="cx-suggest">
                <div class="cx-suggest-title">Closest matches</div>
                <div class="cx-suggest-list">
                    ${near.map(c => `<a class="cx-suggest-item" href="course-detail.html?id=${c.id}">
                        ${escHTML(c.display)}<span>${c.total_lessons} Lessons</span></a>`).join('')}
                </div>
            </div>` : '';
        grid.innerHTML = stateHTML('fa-magnifying-glass', 'Nothing matched',
            'Try a shorter word, or clear the filters.',
            `<div class="cx-state-actions">
                <button class="cx-state-btn" type="button" onclick="clearAll()">Clear search</button>
             </div>${nearHTML}`);
        renderCount(0);
        return;
    }

    const card = CARD();
    grid.innerHTML = list.map(c => card.html(c, { highlight: highlightTitle(c.display, tokens) })).join('');
    renderCount(list.length);
}

function renderCount(n) {
    const el = document.getElementById('cxCount');
    if (!el) return;
    const filtered = state.q || activeFilters().length;
    // The count is only news when something is filtering; otherwise it just
    // restates the number of cards the member can already see.
    el.textContent = filtered ? (n === 1 ? '1 result' : `${n} results`) : '';
}

function renderChips() {
    const box = document.getElementById('cxChips');
    if (!box) return;
    const active = activeFilters();
    if (!active.length) { box.innerHTML = ''; return; }

    box.innerHTML = active.map(f => `
        <span class="cx-chip">${escHTML(optionLabel(f.key, state[f.key]))}
            <button class="cx-chip-x" type="button" aria-label="Remove filter"
                    onclick="setFilter('${f.key}', '${escHTML(DEFAULTS[f.key])}')">✕</button>
        </span>`).join('') +
        `<button class="cx-chip-clear" type="button" onclick="clearAll()">Clear all</button>`;
}

function renderDropdowns() {
    FILTERS.forEach(f => {
        ['', 'm-'].forEach(prefix => {
            const dd = document.getElementById(`cx-dd-${prefix}${f.key}`);
            if (!dd) return;
            const value = state[f.key];
            const isDefault = value === DEFAULTS[f.key];
            dd.classList.toggle('active', !isDefault);

            const label = dd.querySelector('.cx-dd-label');
            if (label) {
                const text = isDefault ? f.idle : optionLabel(f.key, value);
                // Catalog names are already in the reader's language and must
                // not be translated again; UI words go through community-i18n.
                const opt = f.options().find(o => o.value === value);
                label.textContent = text;
                label.toggleAttribute('data-no-i18n', !!(opt && opt.raw && !isDefault));
            }

            const list = dd.querySelector('.cx-dd-list');
            if (list) {
                list.innerHTML = f.options().map(o => `
                    <button class="cx-opt" type="button" role="option"
                            aria-selected="${o.value === value}"
                            data-value="${escHTML(o.value)}"
                            onclick="setFilter('${f.key}', this.dataset.value)">
                        ${o.photo ? `<span class="cx-opt-av"><img src="${escHTML(o.photo)}" alt="" loading="lazy"></span>` : ''}
                        <span${o.raw ? ' data-no-i18n' : ''}>${escHTML(o.label)}</span>
                    </button>`).join('');
            }
        });
    });

    const badge = document.getElementById('cxMobileCount');
    const btn = document.getElementById('cxMobileBtn');
    const n = activeFilters().length;
    if (badge) badge.textContent = n;
    if (btn) btn.classList.toggle('has-filters', n > 0);
}

function renderSearchBox() {
    const wrap = document.getElementById('cxSearch');
    const input = document.getElementById('cxSearchInput');
    if (input && input.value !== state.q) input.value = state.q;
    if (wrap) wrap.classList.toggle('has-query', !!state.q);
}

function renderAll() {
    renderSearchBox();
    renderDropdowns();
    renderChips();
    renderGrid();
}

/* ═══ ACTIONS (called from inline handlers) ═══ */

function setFilter(key, value) {
    if (!(key in DEFAULTS)) return;
    state[key] = value;
    closeAllDropdowns();
    writeURL();
    renderAll();
}

function clearAll() {
    Object.assign(state, DEFAULTS);
    writeURL();
    renderAll();
    const input = document.getElementById('cxSearchInput');
    if (input) input.focus();
}

window.setFilter = setFilter;
window.clearAll = clearAll;

/* ═══ DROPDOWN BEHAVIOUR ═══ */

function closeAllDropdowns(except) {
    document.querySelectorAll('.cx-dd.open').forEach(dd => {
        if (dd !== except) {
            dd.classList.remove('open');
            const btn = dd.querySelector('.cx-dd-btn');
            if (btn) btn.setAttribute('aria-expanded', 'false');
        }
    });
}

function wireDropdowns() {
    document.querySelectorAll('.cx-dd').forEach(dd => {
        const btn = dd.querySelector('.cx-dd-btn');
        if (!btn) return;
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const open = dd.classList.contains('open');
            closeAllDropdowns();
            dd.classList.toggle('open', !open);
            btn.setAttribute('aria-expanded', String(!open));
        });
        dd.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && dd.classList.contains('open')) {
                e.stopPropagation();
                dd.classList.remove('open');
                btn.setAttribute('aria-expanded', 'false');
                btn.focus();
            }
        });
    });
    document.addEventListener('click', () => closeAllDropdowns());
}

/* ═══ MOBILE FILTER SHEET ═══ */

function openSheet(open) {
    const sheet = document.getElementById('cxSheet');
    if (!sheet) return;
    sheet.classList.toggle('open', open);
    document.body.style.overflow = open ? 'hidden' : '';
    if (!open) closeAllDropdowns();
}

function wireSheet() {
    const btn = document.getElementById('cxMobileBtn');
    const sheet = document.getElementById('cxSheet');
    if (btn) btn.addEventListener('click', () => openSheet(true));
    if (sheet) {
        sheet.addEventListener('click', (e) => { if (e.target === sheet) openSheet(false); });
        const done = document.getElementById('cxSheetDone');
        if (done) done.addEventListener('click', () => openSheet(false));
    }
}

/* ═══ SEARCH BOX ═══ */

let searchTimer = null;

function wireSearch() {
    const input = document.getElementById('cxSearchInput');
    const clear = document.getElementById('cxSearchClear');
    if (!input) return;

    input.addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            state.q = input.value;
            writeURL();
            renderSearchBox();
            renderGrid();
        }, 200);
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            e.preventDefault();
            input.value = '';
            state.q = '';
            writeURL();
            renderSearchBox();
            renderGrid();
        }
    });

    if (clear) clear.addEventListener('click', () => {
        input.value = '';
        state.q = '';
        writeURL();
        renderSearchBox();
        renderGrid();
        input.focus();
    });

    // "/" focuses the search from anywhere on the page — but never while the
    // member is typing into something else.
    document.addEventListener('keydown', (e) => {
        if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return;
        const el = document.activeElement;
        const tag = el ? el.tagName : '';
        if (tag === 'INPUT' || tag === 'TEXTAREA' || (el && el.isContentEditable)) return;
        e.preventDefault();
        input.focus();
        input.select();
    });
}

/* ═══════════════════════════════════════════════════════════════
   LOAD
   ═══════════════════════════════════════════════════════════════ */

async function getJSON(path) {
    try {
        const res = await apiFetch(path);
        if (!res.ok) return null;
        return await res.json();
    } catch (e) {
        return null;
    }
}

async function loadCourses() {
    const grid = document.getElementById('coursesGrid');
    if (grid) grid.innerHTML = CARD().skeleton(8);

    let courses;
    try {
        const res = await apiFetch('/courses');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        courses = await res.json();
    } catch (e) {
        console.error('Course load error:', e);
        if (grid) {
            grid.innerHTML = stateHTML('fa-triangle-exclamation', "Couldn't load the courses",
                'Check your connection and try again.',
                `<div class="cx-state-actions">
                    <button class="cx-state-btn" type="button" onclick="location.reload()">Try again</button>
                 </div>`);
        }
        return;
    }

    // Progress and stats are enrichment: the page is useful without either, so
    // neither one failing is allowed to take the course list down with it.
    const [progress, stats] = await Promise.all([
        getJSON('/courses/progress/summary'),
        getJSON('/courses/stats'),
    ]);

    allCourses = buildModel(courses, progress, stats);
    loaded = true;
    renderAll();
}

/* ═══ HAMBURGER ═══ */
const hamburger = document.getElementById('hamburgerDash');
const sidebar = document.getElementById('dashSidebar');
if (hamburger) hamburger.addEventListener('click', () => sidebar.classList.toggle('open'));

/* ═══ INIT ═══ */
readURL();
// Rewrite immediately: a URL carrying a value we just rejected (a renamed
// track, a hand-edited sort) would otherwise keep advertising a filter the
// page is not applying.
writeURL();
wireSearch();
wireDropdowns();
wireSheet();

window.addEventListener('popstate', () => { readURL(); renderAll(); });

// Titles, track names and instructor names come out of the catalog in the
// reader's language, so a language switch has to redraw them — community-i18n
// rewrites text nodes it has a dictionary entry for, and these are not in it.
if (window.GhawyCourseCard) {
    window.GhawyCourseCard.onLangChange(() => { if (allCourses.length) renderAll(); });
}

loadProfile();
loadCourses();
