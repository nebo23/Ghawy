// ═══ GHAWY CATALOG — one source for courses, instructors and tracks ═══
//
// Everything the public site says about a course or an instructor comes from
// here. Before it existed, the six course cards were written by hand in
// index.html, again (with different fields) in course-details.html, and a
// third time in the /courses shell — changing a duration meant three edits and
// they had already drifted apart.
//
// ── Two files, one catalog ──
// The FACTS (INSTRUCTORS, FAMILIES, TRACKS, COURSES) live in catalog-data.js;
// this file holds the renderers that turn them into pages. Every page that
// loads catalog.js must load catalog-data.js first. The split exists because
// the members' area needs the same facts without the rendering — see the note
// where the data used to sit, a few lines into the IIFE below.
//
// ── Where the data actually comes from ──
// The backend exposes two UNAUTHENTICATED endpoints, and we use both:
//
//   GET /api/courses          → every published course: title, thumbnail,
//                               total_lessons, course_time, sort_order
//   GET /api/courses/{id}     → the same plus its lessons (title +
//                               duration_minutes), already filtered to
//                               video_status == "ready"
//
// So live numbers — lesson counts, durations, thumbnails — are read from the
// API and are never stale. What the API does NOT have is the marketing layer:
// a stable slug, an English title, which instructor teaches it, and which
// track it belongs to. That lives in COURSES (catalog-data.js) and is merged
// onto the API response by `courseId`. If the API is unreachable the static
// values there are used as-is, so the page still renders.
//
// ── Curation ──
// COURSES is also the running order of the public site: a course appears on
// the marketing pages because it has an entry there, not because it is
// published in the platform. That is deliberate — publishing a course for
// members should not silently put it on the home page. To add one: add an
// entry with its `courseId` and it shows up everywhere (home, /courses,
// /course-details, /instructors) with no other change.
//
// ── Adding an instructor ──
// Add an entry to INSTRUCTORS (catalog-data.js) and point a course's
// `instructor` at its slug. Nothing else needs to change: the card, the
// instructor bar, the instructor list and the instructor detail page all read
// from there through this file.
//
// ── Assets ──
// Instructor photos, client logos and intro videos have not been delivered
// yet. Every one of those fields accepts `null`, and the renderers below draw
// a clean placeholder for it. Dropping the real asset in later is a one-line
// change in catalog-data.js — no HTML, no CSS and nothing here is touched.

(function () {
    'use strict';

    const API_BASE = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
        ? 'http://127.0.0.1:8000'
        : '/api';

    // ─── Static data ────────────────────────────────────────────
    // INSTRUCTORS / FAMILIES / TRACKS / COURSES moved to catalog-data.js, with
    // every comment that documented them. They left because the members' area
    // needs the same facts (who teaches what, which track a course is in) and
    // could not load THIS file to get them: autoInit() below renders into
    // `#coursesGrid`, and dashboard-courses.html has a grid by that id — the
    // public cards would replace the member cards on sight.
    //
    // catalog-data.js therefore holds data and nothing else, and every page
    // that loads catalog.js must load it FIRST. Nothing else changed: the
    // names below are the same names the rest of this file has always used.
    const DATA = window.GhawyCatalogData || {};
    const INSTRUCTORS = DATA.INSTRUCTORS || {};
    const FAMILIES = DATA.FAMILIES || {};
    const TRACKS = DATA.TRACKS || {};
    const COURSES = DATA.COURSES || [];


    // The comparison table on /tracks: one row per key, both families side by
    // side. The question each row answers is the row label — they are written
    // as the questions a visitor actually has, not as feature names.
    const COMPARE_ROWS = [
        { key: 'goal', icon: 'fa-solid fa-bullseye', label: { ar: 'الهدف منه إيه؟', en: 'What is it for?' } },
        { key: 'who', icon: 'fa-solid fa-user-check', label: { ar: 'مناسب لمين؟', en: 'Who is it for?' } },
        { key: 'learn', icon: 'fa-solid fa-book-open', label: { ar: 'هتتعلم فيه إيه؟', en: 'What will you learn?' } },
        { key: 'start', icon: 'fa-solid fa-flag-checkered', label: { ar: 'تبدأ منين؟', en: 'Where do you start?' } },
        { key: 'outcome', icon: 'fa-solid fa-trophy', label: { ar: 'هتطلع منه بإيه؟', en: 'What do you walk out with?' } },
    ];



    // ─── Helpers ────────────────────────────────────────────────

    function lang() {
        return (typeof window.currentLang === 'function') ? window.currentLang() : 'ar';
    }

    /**
     * Pick the current language out of an {ar, en} pair.
     *
     * The fallback fires on a MISSING side only, never on an empty one: a pair
     * may deliberately be empty in one language — the course preview says
     * "ضمن مسار <name>" in Arabic but "Part of the <name> track" in English,
     * so the trailing word is `{ ar: '', en: 'track' }`. Falling back on ''
     * would have printed the English word inside the Arabic sentence.
     */
    function L(pair) {
        if (pair == null) return '';
        if (typeof pair === 'string') return pair;
        const v = pair[lang()];
        if (v != null) return v;
        return pair.ar != null ? pair.ar : (pair.en != null ? pair.en : '');
    }

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[c]);
    }

    /** Both-language attributes, so i18n.js can translate rendered markup. */
    function i18nAttrs(pair) {
        if (pair == null) return '';
        if (typeof pair === 'string') return `data-ar="${esc(pair)}" data-en="${esc(pair)}"`;
        return `data-ar="${esc(pair.ar || '')}" data-en="${esc(pair.en || pair.ar || '')}"`;
    }

    /** Media paths from the API are server-relative; the images live behind /api. */
    function mediaURL(url) {
        if (!url) return null;
        return url.startsWith('/') ? API_BASE + url : url;
    }

    /**
     * Is this course announced but not out yet?
     *
     * A released course always has a runtime — the platform gives it one the
     * moment a lesson is ready, and the static fallback in COURSES carries one
     * too. So "no runtime" is the single, self-maintaining signal that a
     * course is not watchable yet, and it needs no extra flag to be kept in
     * sync by hand: the day the API returns a `course_time` for one of these,
     * it stops being "soon" everywhere at once.
     */
    function isSoon(course) {
        return !course || !course.duration;
    }

    /** "12h 11m" → 731 minutes. Returns 0 for anything unparseable. */
    function durationToMinutes(text) {
        if (!text) return 0;
        const h = /(\d+)\s*h/i.exec(text);
        const m = /(\d+)\s*m/i.exec(text);
        return (h ? parseInt(h[1], 10) * 60 : 0) + (m ? parseInt(m[1], 10) : 0);
    }

    function minutesToDuration(mins) {
        const h = Math.floor(mins / 60);
        const m = Math.round(mins % 60);
        return h ? (m ? `${h}h ${m}m` : `${h}h`) : `${m}m`;
    }

    function instructor(slug) {
        return INSTRUCTORS[slug] || null;
    }

    function track(slug) {
        return TRACKS[slug] || null;
    }

    function family(slug) {
        return FAMILIES[slug] || null;
    }

    /** The two families in display order — deep first, it is the main road. */
    function familyList() {
        return ['deep', 'applied'].map(k => FAMILIES[k]);
    }

    /** The tracks of one family, in declaration order. */
    function trackList(familySlug) {
        return Object.keys(TRACKS)
            .map(k => TRACKS[k])
            .filter(t => !familySlug || t.family === familySlug);
    }

    /** Where a track lives on the site. One place builds this URL. */
    function trackHref(slug) {
        return `/tracks?t=${encodeURIComponent(slug)}`;
    }

    // ─── Loading + merging ──────────────────────────────────────

    let loadPromise = null;

    /**
     * The catalog, with live numbers merged in from GET /api/courses.
     * Resolves with the static catalog if the request fails — the site must
     * never render an empty course list because the API blinked. Cached: every
     * consumer on a page shares one request.
     */
    function load() {
        if (loadPromise) return loadPromise;

        const fallback = COURSES.map(c => Object.assign({}, c, { live: false }));

        loadPromise = fetch(`${API_BASE}/courses`, { headers: { 'Accept': 'application/json' } })
            .then(r => r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status)))
            .then(rows => {
                const byId = new Map(rows.map(r => [r.id, r]));
                return COURSES.map(c => {
                    const row = byId.get(c.courseId);
                    if (!row) return Object.assign({}, c, { live: false });
                    return Object.assign({}, c, {
                        live: true,
                        lessons: row.total_lessons || c.lessons,
                        duration: row.course_time || c.duration,
                        image: mediaURL(row.thumbnail_url) || c.image,
                    });
                });
            })
            .catch(err => {
                console.warn('[catalog] falling back to static course data:', err.message);
                return fallback;
            });

        return loadPromise;
    }

    /** One course with its live numbers, or null for an unknown slug. */
    function courseBySlug(slug) {
        return load().then(list => list.find(c => c.slug === slug) || null);
    }

    /** The lessons of one course, straight from the public detail endpoint. */
    function lessonsFor(course) {
        if (!course || !course.courseId) return Promise.resolve([]);
        return fetch(`${API_BASE}/courses/${course.courseId}`, { headers: { 'Accept': 'application/json' } })
            .then(r => r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status)))
            .then(d => (d.lessons || []).map(l => ({
                title: l.title,
                duration: minutesToDuration(l.duration_minutes || 0),
            })))
            .catch(err => {
                console.warn('[catalog] lessons unavailable:', err.message);
                return [];
            });
    }

    /** Every course taught by one instructor, in catalog order. */
    function coursesByInstructor(slug) {
        return load().then(list => list.filter(c => c.instructor === slug));
    }

    /**
     * The courses of one track, in the order they are meant to be taken.
     * This is the ONLY reader of the course↔track relation: tracks carry no
     * course list of their own, so the two can never drift apart. The order is
     * COURSES order, which is the platform's own course numbering.
     */
    function coursesInTrack(slug) {
        return load().then(list => list.filter(c => c.track === slug));
    }

    /**
     * Counts for one track, with its course list.
     *
     * There are THREE states here, not two, and conflating the last two is
     * what would have gone wrong the moment a course was announced without a
     * date:
     *
     *   empty   — nothing announced at all.
     *   soon    — something announced, none of it watchable yet.
     *   normal  — at least one course you can open today.
     *
     * `empty` used to be the only flag, so a track flipped straight from
     * "قريباً" to "1 course · 0 hours" as soon as an unreleased course was
     * added to it — louder AND less true than the state it replaced. Both of
     * the first two states render as "coming soon"; `count`/`hours` describe
     * only what is actually watchable, and `soonCount` carries the rest.
     */
    function trackStats(slug) {
        return coursesInTrack(slug).then(courses => {
            const t = totals(courses);
            return {
                courses: courses,
                empty: courses.length === 0,
                // Announced but nothing to watch — reads as "coming soon" too.
                soon: courses.length > 0 && t.courses === 0,
                soonCount: t.soon,
                count: t.courses,
                announced: t.announced,
                lessons: t.lessons,
                hours: t.hours,
                minutes: t.minutes,
                instructors: Array.from(new Set(courses.map(c => c.instructor)))
                    .map(instructor).filter(Boolean),
            };
        });
    }

    /** Every track with its counts already resolved — for the list views. */
    function trackListWithStats(familySlug) {
        const tracks = trackList(familySlug);
        return Promise.all(tracks.map(t =>
            trackStats(t.slug).then(stats => ({ track: t, stats }))
        ));
    }

    /** Instructors in a stable order, so the list page never reshuffles. */
    function instructorList() {
        return Object.keys(INSTRUCTORS).map(k => INSTRUCTORS[k]);
    }

    /**
     * Totals across the whole catalog — for the "all of Ghawy" bar.
     *
     * `courses`, `lessons`, `minutes` and `hours` count ONLY courses that are
     * actually watchable. An announced-but-unreleased course would otherwise
     * push the headline course count up while adding nothing to the hours,
     * which is the site promising more than a subscriber can open — the
     * numbers on this site are a claim about what you get for your money, and
     * a course with no lessons in it is not part of that.
     *
     * `announced` and `soon` are kept alongside for the places that DO want to
     * say "and two more are on the way".
     */
    function totals(list) {
        const all = list || COURSES;
        const out = all.filter(c => !isSoon(c));
        const mins = out.reduce((s, c) => s + durationToMinutes(c.duration), 0);
        return {
            courses: out.length,
            lessons: out.reduce((s, c) => s + (c.lessons || 0), 0),
            minutes: mins,
            hours: Math.round(mins / 60),
            announced: all.length,
            soon: all.length - out.length,
        };
    }

    // ─── Renderers ──────────────────────────────────────────────

    /** Initials for the avatar placeholder, e.g. "محمد صلاح" → "م ص". */
    function initials(name) {
        return String(name || '?').trim().split(/\s+/).slice(0, 2)
            .map(w => w[0]).join(' ');
    }

    function avatarHTML(inst, cls) {
        const name = L(inst.name);
        if (inst.photo) {
            return `<img class="${cls}" src="${esc(inst.photo)}" alt="${esc(name)}" loading="lazy" />`;
        }
        // Placeholder: initials on the brand gradient. Replaced the moment
        // `photo` gets a path in this file.
        return `<span class="${cls} gi-avatar-fallback" aria-hidden="true">${esc(initials(name))}</span>`;
    }

    /**
     * The instructor bar: photo + name + role, linking to their page. Used
     * under the course preview and on the track pages. The course card no
     * longer uses it — its reference wants the instructor flat on one edge of
     * a row, not in a pill with a role line, so it has `cardInstructorHTML`.
     *
     * There used to be a second `full` variant that boxed the identity, the
     * facts, the client strip and the intro video into one card. It was
     * dropped — the box left a lot of dead space around the video and read
     * badly. The instructor page now lays those parts out flat down the page
     * instead, using the individual renderers below.
     */
    function instructorBarHTML(inst) {
        if (!inst) return '';
        return `
        <a class="gi-bar gi-bar-compact" href="/instructors?i=${encodeURIComponent(inst.slug)}">
            ${avatarHTML(inst, 'gi-avatar')}
            <span class="gi-ident">
                <span class="gi-name">${esc(L(inst.name))}</span>
                <span class="gi-role" ${i18nAttrs(inst.role)}>${esc(L(inst.role))}</span>
            </span>
        </a>`;
    }

    /**
     * "خبرة أكتر من N سنين", or null when we do not know N.
     *
     * Every caller used to build this line unconditionally, which printed
     * "خبرة أكتر من undefined سنين" for an instructor whose figures the client
     * has not sent yet. A fact we do not have is not rendered at all.
     */
    function yearsLineFor(inst) {
        if (!inst || !inst.yearsExperience) return null;
        return {
            ar: `خبرة أكتر من ${inst.yearsExperience} سنين`,
            en: `${inst.yearsExperience}+ years of experience`,
        };
    }

    /** The experience / client-count pills. Omitted entirely if we have neither. */
    function factsHTML(inst) {
        const yearsLine = yearsLineFor(inst);
        const clientsLine = inst.clientsCount ? {
            ar: `اشتغل مع أكتر من ${inst.clientsCount} عميل`,
            en: `Worked with ${inst.clientsCount}+ clients`,
        } : null;
        if (!yearsLine && !clientsLine) return '';
        return `
        <div class="gi-facts">
            ${yearsLine ? `<span class="gi-fact" ${i18nAttrs(yearsLine)}>${esc(L(yearsLine))}</span>` : ''}
            ${clientsLine ? `<span class="gi-fact" ${i18nAttrs(clientsLine)}>${esc(L(clientsLine))}</span>` : ''}
        </div>`;
    }

    /** The brands/creators strip. Chips today, images the moment a logo is set. */
    function clientsHTML(inst) {
        const chips = (inst.clients || []).map(c => c.logo
            ? `<span class="gi-client"><img src="${esc(c.logo)}" alt="${esc(L(c.name))}" loading="lazy" /></span>`
            : `<span class="gi-client gi-client-text" ${i18nAttrs(c.name)}>${esc(L(c.name))}</span>`
        ).join('');
        return chips ? `<div class="gi-clients-row">${chips}</div>` : '';
    }

    /**
     * The course's own intro video for the preview page. Autoplays — which
     * browsers only allow while muted, so `muted` is not optional here — and
     * loops, because it is a short teaser rather than a lesson.
     * `introVideo: null` (all of them, today) renders the placeholder instead.
     */
    function courseVideoHTML(course) {
        if (course && course.introVideo) {
            return `
        <div class="cd-video">
            <video src="${esc(course.introVideo)}" poster="${esc(course.image || '')}"
                   autoplay muted loop playsinline controls></video>
        </div>`;
        }
        return `
        <div class="cd-video cd-video-empty">
            ${course && course.image ? `<img src="${esc(course.image)}" alt="" loading="lazy" />` : ''}
            <div class="cd-video-empty-body">
                <i class="fa-solid fa-circle-play" aria-hidden="true"></i>
                <span data-ar="فيديو مقدمة الكورس قريباً" data-en="Course intro video coming soon">فيديو مقدمة الكورس قريباً</span>
            </div>
        </div>`;
    }

    /** The 2-minute intro video, or a labelled placeholder until it arrives. */
    function introVideoHTML(inst) {
        if (inst.introVideo) {
            return `
        <div class="gi-video">
            <video src="${esc(inst.introVideo)}" controls playsinline preload="none"
                   poster="${esc(inst.introVideoPoster || '')}"></video>
        </div>`;
        }
        return `
        <div class="gi-video gi-video-empty">
            <i class="fa-solid fa-circle-play" aria-hidden="true"></i>
            <span data-ar="الفيديو التعريفي للمدرّب قريباً" data-en="Instructor intro video coming soon">الفيديو التعريفي للمدرّب قريباً</span>
        </div>`;
    }

    /**
     * Social links. Only the platforms actually present on the instructor are
     * rendered, so adding one is a single key in INSTRUCTORS.
     */
    const LINK_ICONS = {
        instagram: 'fa-brands fa-instagram',
        tiktok: 'fa-brands fa-tiktok',
        facebook: 'fa-brands fa-facebook-f',
        youtube: 'fa-brands fa-youtube',
        linkedin: 'fa-brands fa-linkedin-in',
        x: 'fa-brands fa-x-twitter',
        website: 'fa-solid fa-globe',
    };

    function linksHTML(inst) {
        const links = inst.links || {};
        const items = Object.keys(links)
            .filter(k => links[k] && LINK_ICONS[k])
            .map(k => `
            <a class="gi-link" href="${esc(links[k])}" target="_blank" rel="noopener noreferrer"
               aria-label="${esc(k)}"><i class="${LINK_ICONS[k]}" aria-hidden="true"></i></a>`)
            .join('');
        return items ? `<div class="gi-links">${items}</div>` : '';
    }

    /** One instructor card for the /instructors list. */
    function instructorCardHTML(inst) {
        const href = `/instructors?i=${encodeURIComponent(inst.slug)}`;
        const name = L(inst.name);
        // Null for an instructor whose figures we have not been given — the
        // pill is dropped rather than printed with an "undefined" in it.
        const years = yearsLineFor(inst);
        return `
    <article class="gi-card">
        <a class="gi-card-top" href="${href}">
            ${avatarHTML(inst, 'gi-avatar gi-avatar-lg')}
            <span class="gi-ident">
                <span class="gi-name gi-name-lg">${esc(name)}</span>
                <span class="gi-role" ${i18nAttrs(inst.role)}>${esc(L(inst.role))}</span>
            </span>
        </a>
        ${years ? `<span class="gi-fact" ${i18nAttrs(years)}>${esc(L(years))}</span>` : ''}
        <a class="gc-btn" href="${href}" data-ar="صفحة المدرّب" data-en="Instructor page">صفحة المدرّب</a>
    </article>`;
    }

    /**
     * How many courses this instructor teaches on Ghawy.
     *
     * Counted off COURSES rather than `coursesByInstructor`, which is the
     * async one. Both give the same number — `load()` maps over COURSES and
     * only ever refreshes the lesson count, runtime and thumbnail of an entry,
     * so the API can never add or remove a course from the list — and counting
     * here keeps the instructor card synchronous, which means no skeleton and
     * no number that changes under the reader a second after it appears.
     */
    function courseCountFor(slug) {
        return COURSES.filter(c => c.instructor === slug && !isSoon(c)).length;
    }

    /** Announced-but-unreleased courses for one instructor. */
    function soonCountFor(slug) {
        return COURSES.filter(c => c.instructor === slug && isSoon(c)).length;
    }

    /**
     * The instructor card on the home page.
     *
     * The client's ask was "say what this instructor is distinguished at", and
     * everything that answers it is already in INSTRUCTORS: the role, the
     * years, the kinds of client they have worked with. So the card composes
     * that one line out of those fields instead of asking for a new one —
     * adding a second instructor stays a single entry in this file.
     *
     * Different card from `instructorCardHTML`: /instructors is a directory
     * and its card is deliberately sparse, while this one is doing the
     * persuading on a landing page and carries the course count, the
     * distinction line and the social links.
     */
    function homeInstructorCardHTML(inst) {
        const href = `/instructors?i=${encodeURIComponent(inst.slug)}`;
        // Courses out today, and courses announced. An instructor whose only
        // course has not shipped yet gets "كورس واحد قريباً" — saying "كورس
        // واحد على غاوي" would point at something nobody can open.
        const n = courseCountFor(inst.slug);
        const soonN = soonCountFor(inst.slug);
        const courses = n
            ? { ar: `${L(coursesWord(n))} على غاوي`, en: `${L(coursesWord(n))} on Ghawy` }
            : soonN
                ? { ar: `${coursesWord(soonN).ar} قريباً`, en: `${coursesWord(soonN).en} coming soon` }
                : null;

        const years = yearsLineFor(inst);

        // What he is known for. The role is already the line under his name,
        // so this one picks up where that leaves off: who he has actually done
        // it for. `clients` holds CATEGORIES of client, so it reads as a
        // description and never as a name-drop. With no clients on file it
        // falls back to the bio; with no bio either — an instructor whose
        // details the client has not sent yet — the line is left out rather
        // than rendered as an empty paragraph.
        const clientNames = (inst.clients || []).map(c => c.name);
        const distinction = clientNames.length ? {
            ar: `اشتغل مع ${clientNames.map(c => c.ar).join(' و')}، وبيشرح على غاوي اللي بيعمله فعلاً في شغله.`,
            en: `Has worked with ${clientNames.map(c => c.en || c.ar).join(' and ')}, and teaches on Ghawy exactly what he does in that work.`,
        } : inst.bio;

        const facts = [
            courses ? `
            <span class="hi-fact">
                <i class="fa-solid fa-graduation-cap" aria-hidden="true"></i>
                <span ${i18nAttrs(courses)}>${esc(L(courses))}</span>
            </span>` : '',
            years ? `
            <span class="hi-fact">
                <i class="fa-solid fa-briefcase" aria-hidden="true"></i>
                <span ${i18nAttrs(years)}>${esc(L(years))}</span>
            </span>` : '',
        ].join('');

        return `
    <article class="hi-card">
        <a class="hi-top" href="${href}">
            ${avatarHTML(inst, 'hi-avatar')}
            <span class="hi-ident">
                <span class="hi-name">${esc(L(inst.name))}</span>
                <span class="hi-role" ${i18nAttrs(inst.role)}>${esc(L(inst.role))}</span>
            </span>
        </a>

        ${distinction ? `<p class="hi-distinction" ${i18nAttrs(distinction)}>${esc(L(distinction))}</p>` : ''}

        ${facts ? `<div class="hi-facts">${facts}</div>` : ''}

        <div class="hi-foot">
            <a class="gc-btn hi-btn" href="${href}"
               data-ar="صفحة المدرّب" data-en="Instructor page">صفحة المدرّب</a>
            ${linksHTML(inst)}
        </div>
    </article>`;
    }

    /**
     * The home page's instructor section. Reads INSTRUCTORS, so the day a
     * second instructor is added the grid grows on its own.
     *
     * With one instructor the grid is a single centred card rather than one
     * card stranded on the left of a three-column row — `.hi-grid` caps its
     * own width off the number of cards, so both cases look deliberate.
     */
    function renderHomeInstructors(el) {
        if (!el) return;
        const list = instructorList();
        if (!list.length) { el.innerHTML = ''; el.hidden = true; return; }
        el.hidden = false;
        el.className = 'hi-grid';

        // Repaint on `languagechange` like the other renderers: the card's
        // text is picked by L() at render time, so without this it would keep
        // whichever language was current when the page loaded.
        // ...and applyLanguageTo for the bits written as a literal with
        // data-ar/data-en (the button). i18n.js has already made its automatic
        // pass over the document by the time this markup exists, so without
        // this call those stay Arabic in English.
        const paint = () => {
            el.innerHTML = list.map(homeInstructorCardHTML).join('');
            if (typeof window.applyLanguageTo === 'function') window.applyLanguageTo(el);
        };
        paint();
        bindLanguage(el, paint);
    }

    /**
     * The instructor line on a course card: the round photo, then the name
     * with a short role under it.
     *
     * The photo comes FIRST in the markup, which is what puts it on the right
     * in Arabic and on the left in English — a flex row already follows the
     * document direction, so reading order is the only thing that has to be
     * right and there is no `left`/`right` rule anywhere.
     *
     * This is deliberately not `instructorBarHTML`. That one is a bordered
     * pill carrying the full role, sized for the wider layouts. On the card
     * the instructor sits flat on one edge of a row with the runtime on the
     * other, and the role line has to be the short version.
     */
    function cardInstructorHTML(inst) {
        if (!inst) return '<span></span>';   // keeps the row (and its seam) in shape
        const role = inst.roleShort || inst.role;
        return `
            <a class="gc-inst" href="/instructors?i=${encodeURIComponent(inst.slug)}">
                ${avatarHTML(inst, 'gc-avatar')}
                <span class="gc-inst-ident">
                    <span class="gc-inst-name">${esc(L(inst.name))}</span>
                    <span class="gc-inst-role" ${i18nAttrs(role)}>${esc(L(role))}</span>
                </span>
            </a>`;
    }

    /**
     * One course card — the same markup on the home page, on /courses and on
     * an instructor's page. There is never a second copy.
     *
     * The layout came from a reference the client sent: a green band across
     * the top, a big title, and the numbers under it. The band is gone and the
     * numbers have since split into two rows — the lesson count and the
     * runtime on opposite edges, then the instructor under a hairline seam —
     * but the shape is otherwise the reference's. That reference was a white
     * card and the card was built white; the client then asked for the surface
     * to go back to dark like the rest of the site.
     *
     * What the white surface was solving — "the green is taking everything" —
     * is still solved without it: the band and the clock icon are the only
     * green on the card. The version this replaced had a green glow on hover,
     * a green-tinted thumbnail, a green-filled button and a green avatar too.
     *
     * The reference has no course thumbnail; the client asked separately to
     * keep it, so it stays on top and the green band doubles as the seam
     * between it and the body. Dropping the image later means deleting the
     * `.gc-media` anchor and nothing else.
     */
    /**
     * The card thumbnail. A course with no artwork yet gets the same treatment
     * a track with no artwork gets — its track's icon on its family's gradient
     * — rather than `src="null"` and a broken-image glyph.
     */
    function courseMediaHTML(course, href) {
        const inner = course.image
            ? `<img src="${esc(course.image)}" alt="" loading="lazy" />`
            : (() => {
                const tr = track(course.track);
                const fam = tr ? family(tr.family) : null;
                const accent = fam ? fam.accent : 'gold';
                return `<span class="gc-media-ph tr-accent-${accent}" aria-hidden="true">
                    <i class="${esc(tr && tr.icon ? tr.icon : 'fa-solid fa-graduation-cap')}"></i>
                </span>`;
            })();

        // No link on an unreleased course — see the button below.
        return href
            ? `<a class="gc-media" href="${href}" tabindex="-1" aria-hidden="true">${inner}</a>`
            : `<span class="gc-media" aria-hidden="true">${inner}</span>`;
    }

    function courseCardHTML(course) {
        const inst = instructor(course.instructor);
        const soon = isSoon(course);
        // An unreleased course has no content page worth sending anyone to, so
        // the card does not link anywhere at all: not the thumbnail, not the
        // title, not the button. The button stays in place as an inert chip
        // reading "قريباً" so the card keeps its shape in the grid — hiding it
        // would leave this one card short next to its neighbours.
        const href = soon ? null : `/course-details?course=${encodeURIComponent(course.slug)}`;
        const title = L(course.title);

        // The reference writes the runtime as whole hours ("12 ساعة"), not as
        // the platform's "12h 3m". `hoursWord` handles the Arabic dual/plural.
        // With no runtime the slot says "قريباً" — never "0 ساعة", and never
        // an empty gap where a number should be.
        const mins = durationToMinutes(course.duration);
        const hours = soon
            ? SOON
            : (mins ? hoursWord(Math.round(mins / 60)) : { ar: course.duration, en: course.duration });

        // "10 دروس" — the count and its Arabic plural come out of lessonsWord()
        // as ONE string, so nothing below splits them; the chip's flex `gap`
        // only ever separates the icon from the label, and mirrors itself with
        // the document direction.
        // An unreleased course has no lesson count at all — that absence is
        // part of what isSoon() reads — so its slot renders as an empty span
        // rather than a second "قريباً". `space-between` then keeps the runtime
        // chip on exactly the edge it occupies on every other card in the grid.
        const lessons = (!soon && course.lessons) ? lessonsWord(course.lessons) : null;
        const lessonChip = lessons
            ? `<span class="gc-stat">
                    <span class="gc-stat-ico"><i class="fa-solid fa-book" aria-hidden="true"></i></span>
                    <span ${i18nAttrs(lessons)}>${esc(L(lessons))}</span>
                </span>`
            : '<span></span>';

        const btn = soon
            ? `<span class="gc-btn gc-btn-soon" aria-disabled="true"
                     ${i18nAttrs(SOON)}>${esc(L(SOON))}</span>`
            : `<a class="gc-btn" href="${href}" data-ar="محتوى الكورس" data-en="Course content">محتوى الكورس</a>`;

        return `
    <article class="gc-card${soon ? ' is-soon' : ''}">
        ${courseMediaHTML(course, href)}
        <div class="gc-body">
            <h3 class="gc-title" ${i18nAttrs(course.title)}>${esc(title)}</h3>
            <div class="gc-stats">
                ${lessonChip}
                <span class="gc-stat gc-hours${soon ? ' gc-hours-soon' : ''}">
                    <span class="gc-stat-ico"><i class="fa-regular fa-${soon ? 'hourglass-half' : 'clock'}" aria-hidden="true"></i></span>
                    <span ${i18nAttrs(hours)}>${esc(L(hours))}</span>
                </span>
            </div>
            <div class="gc-meta">
                ${cardInstructorHTML(inst)}
            </div>
            ${btn}
        </div>
    </article>`;
    }

    // ═══ Tracks ═════════════════════════════════════════════════

    /**
     * Keep a rendered container following the language.
     *
     * The guard is not just tidiness: /tracks rebuilds its entire body on
     * every `languagechange`, so the container this was bound to is a
     * detached node by the time the next event fires. Without the check each
     * language toggle would leave another listener behind, painting into a
     * node nobody can see. The listener removes itself the first time it
     * finds its element gone.
     */
    function bindLanguage(el, paint) {
        if (el.dataset.langBound) return;
        el.dataset.langBound = '1';
        const onLang = () => {
            if (!el.isConnected) {
                document.removeEventListener('languagechange', onLang);
                return;
            }
            paint();
        };
        document.addEventListener('languagechange', onLang);
    }

    /** "٣ كورسات" / "3 courses" — Arabic counts are not just N + a noun. */
    function coursesWord(n) {
        const ar = n === 1 ? 'كورس واحد'
            : n === 2 ? 'كورسين'
                : n <= 10 ? `${n} كورسات`
                    : `${n} كورس`;
        return { ar, en: n === 1 ? '1 course' : `${n} courses` };
    }

    function lessonsWord(n) {
        const ar = n === 1 ? 'درس واحد'
            : n === 2 ? 'درسين'
                : n <= 10 ? `${n} دروس`
                    : `${n} درس`;
        return { ar, en: n === 1 ? '1 lesson' : `${n} lessons` };
    }

    function hoursWord(n) {
        const ar = n === 1 ? 'ساعة' : n === 2 ? 'ساعتين' : n <= 10 ? `${n} ساعات` : `${n} ساعة`;
        return { ar, en: n === 1 ? '1 hour' : `${n} hours` };
    }

    /** "وكورس كمان قريباً" — the tail on a track that is partly released. */
    function soonMoreWord(n) {
        const ar = n === 1 ? 'وكورس كمان قريباً'
            : n === 2 ? 'وكورسين كمان قريباً'
                : `و${n} كورسات كمان قريباً`;
        return { ar, en: n === 1 ? '1 more coming soon' : `${n} more coming soon` };
    }

    const SOON = { ar: 'قريباً', en: 'Coming soon' };

    /**
     * Track artwork. The client has not sent the images yet, so `image: null`
     * draws a themed panel instead: the track's icon over a gradient tinted by
     * its family — gold for the deep tracks, blue for the applied ones. It is
     * a designed placeholder, not a grey box, and the two families read as
     * different at a glance which is the whole point of this page.
     *
     * Setting `image` in TRACKS swaps it for the real artwork with no change
     * to any HTML or CSS.
     */
    function trackThumbHTML(tr, extraClass) {
        const fam = family(tr.family);
        const accent = fam ? fam.accent : 'gold';
        const cls = `tr-thumb tr-accent-${accent}${extraClass ? ' ' + extraClass : ''}`;
        if (tr.image) {
            return `<span class="${cls}"><img src="${esc(tr.image)}" alt="" loading="lazy" /></span>`;
        }
        return `
        <span class="${cls} tr-thumb-ph" aria-hidden="true">
            <i class="${esc(tr.icon || 'fa-solid fa-route')}"></i>
        </span>`;
    }

    /**
     * One track card — used identically for both families so the visual
     * comparison the client asked for stays intact; only the accent differs.
     * `entry` is {track, stats} from trackListWithStats().
     */
    function trackCardHTML(entry) {
        const tr = entry.track;
        const st = entry.stats;
        const fam = family(tr.family);
        const accent = fam ? fam.accent : 'gold';
        const href = trackHref(tr.slug);

        // Nothing watchable — whether or not a course has been announced — is
        // one badge and no numbers. A "0 hours" on a card is worse than no
        // number at all.
        const nothingYet = st.empty || st.soon;

        // Some courses out, others still coming: say both, in that order.
        const soonTail = (!nothingYet && st.soonCount)
            ? `<span class="tr-meta-item tr-meta-soon">
                <i class="fa-regular fa-hourglass-half" aria-hidden="true"></i>
                <span ${i18nAttrs(soonMoreWord(st.soonCount))}>${esc(L(soonMoreWord(st.soonCount)))}</span>
            </span>`
            : '';

        const meta = nothingYet
            ? `<span class="tr-badge-soon" ${i18nAttrs(SOON)}>${esc(L(SOON))}</span>`
            : `
            <span class="tr-meta-item">
                <i class="fa-solid fa-graduation-cap" aria-hidden="true"></i>
                <span ${i18nAttrs(coursesWord(st.count))}>${esc(L(coursesWord(st.count)))}</span>
            </span>
            <span class="tr-meta-item">
                <i class="fa-regular fa-clock" aria-hidden="true"></i>
                <span ${i18nAttrs(hoursWord(st.hours))}>${esc(L(hoursWord(st.hours)))}</span>
            </span>${soonTail}`;

        const cta = nothingYet
            ? { ar: 'شوف المسار', en: 'See the track' }
            : { ar: 'افتح المسار', en: 'Open the track' };

        return `
    <a class="tr-card tr-accent-${accent}${nothingYet ? ' is-soon' : ''}" href="${href}">
        ${trackThumbHTML(tr, 'tr-thumb-card')}
        <span class="tr-card-body">
            <span class="tr-card-title" ${i18nAttrs(tr.name)}>${esc(L(tr.name))}</span>
            <span class="tr-card-short" ${i18nAttrs(tr.short)}>${esc(L(tr.short))}</span>
            <span class="tr-card-meta">${meta}</span>
            <span class="tr-card-cta" ${i18nAttrs(cta)}>${esc(L(cta))}</span>
        </span>
    </a>`;
    }

    function trackSkeletonHTML(count) {
        let out = '';
        for (let i = 0; i < count; i++) {
            out += `
    <div class="tr-card tr-card-skeleton" aria-hidden="true">
        <div class="tr-thumb gc-sk"></div>
        <div class="tr-card-body">
            <div class="gc-sk gc-sk-line gc-sk-title"></div>
            <div class="gc-sk gc-sk-line gc-sk-short"></div>
            <div class="gc-sk gc-sk-line gc-sk-short"></div>
        </div>
    </div>`;
        }
        return out;
    }

    /**
     * Fill a container with the track cards of one family. Same
     * skeleton → cards → re-render-on-languagechange contract as the course
     * grid, so both grids behave the same way on every page.
     */
    function renderTrackCards(el, familySlug) {
        if (!el) return Promise.resolve([]);
        el.classList.add('tr-grid');
        el.innerHTML = trackSkeletonHTML(trackList(familySlug).length);

        const paint = () => trackListWithStats(familySlug).then(entries => {
            el.innerHTML = entries.length
                ? entries.map(trackCardHTML).join('')
                : emptyHTML();
            return entries;
        });

        return paint().then(entries => {
            bindLanguage(el, paint);
            return entries;
        });
    }

    /**
     * The home-page teaser: one panel per family with its one-line definition
     * and the tracks inside it as chips. Deliberately NOT the comparison —
     * that lives on /tracks. Built from the same FAMILIES/TRACKS data, so the
     * home page can never list a track the tracks page does not have.
     */
    function familyTeaserHTML(fam, entries) {
        const chips = entries.map(e => {
            // Same three-state rule as the track card: a track whose only
            // courses are unreleased is still "قريباً", not "1 course".
            const soon = e.stats.empty || e.stats.soon;
            const label = soon
                ? { ar: `${L(e.track.name)} — قريباً`, en: `${L(e.track.name)} — soon` }
                : {
                    ar: `${e.track.name.ar} · ${coursesWord(e.stats.count).ar}`,
                    en: `${e.track.name.en} · ${coursesWord(e.stats.count).en}`
                };
            return `<a class="tr-chip${soon ? ' is-soon' : ''}" href="${trackHref(e.track.slug)}"
                       ${i18nAttrs(label)}>${esc(L(label))}</a>`;
        }).join('');

        return `
    <article class="tr-family tr-accent-${fam.accent}">
        <div class="tr-family-head">
            <span class="tr-family-icon" aria-hidden="true"><i class="${esc(fam.icon)}"></i></span>
            <div class="tr-family-ident">
                <h3 class="tr-family-name" ${i18nAttrs(fam.name)}>${esc(L(fam.name))}</h3>
                <span class="tr-family-tag" ${i18nAttrs(fam.tagline)}>${esc(L(fam.tagline))}</span>
            </div>
        </div>
        <p class="tr-family-line" ${i18nAttrs(fam.oneLine)}>${esc(L(fam.oneLine))}</p>
        <div class="tr-chips">${chips}</div>
    </article>`;
    }

    function renderFamilyTeaser(el) {
        if (!el) return Promise.resolve([]);
        el.classList.add('tr-family-grid');

        const paint = () => Promise.all(familyList().map(fam =>
            trackListWithStats(fam.slug).then(entries => familyTeaserHTML(fam, entries))
        )).then(html => { el.innerHTML = html.join(''); });

        return paint().then(() => bindLanguage(el, paint));
    }

    /**
     * The two-column comparison. Rendered twice into the same container: as a
     * real table on wide screens and as one stacked block per family on
     * phones, because a 2-column table of long Arabic sentences is unreadable
     * at 360px. Both are built from the same COMPARE_ROWS, so they cannot say
     * different things — CSS picks which one is visible.
     */
    function compareHTML() {
        const fams = familyList();

        const head = fams.map(f => `
            <th class="tr-cmp-head tr-accent-${f.accent}">
                <span class="tr-cmp-head-icon" aria-hidden="true"><i class="${esc(f.icon)}"></i></span>
                <span class="tr-cmp-head-name" ${i18nAttrs(f.name)}>${esc(L(f.name))}</span>
                <span class="tr-cmp-head-tag" ${i18nAttrs(f.tagline)}>${esc(L(f.tagline))}</span>
            </th>`).join('');

        const rows = COMPARE_ROWS.map(row => `
        <tr>
            <th class="tr-cmp-label" scope="row">
                <i class="${esc(row.icon)}" aria-hidden="true"></i>
                <span ${i18nAttrs(row.label)}>${esc(L(row.label))}</span>
            </th>
            ${fams.map(f => `<td ${i18nAttrs(f[row.key])}>${esc(L(f[row.key]))}</td>`).join('')}
        </tr>`).join('');

        const table = `
    <div class="tr-cmp-scroll">
        <table class="tr-cmp">
            <thead>
                <tr>
                    <th class="tr-cmp-corner">
                        <span data-ar="المقارنة" data-en="Side by side">المقارنة</span>
                    </th>
                    ${head}
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    </div>`;

        const stacked = fams.map(f => `
    <section class="tr-cmp-stack tr-accent-${f.accent}">
        <header class="tr-cmp-stack-head">
            <span class="tr-cmp-head-icon" aria-hidden="true"><i class="${esc(f.icon)}"></i></span>
            <span class="tr-cmp-head-name" ${i18nAttrs(f.name)}>${esc(L(f.name))}</span>
            <span class="tr-cmp-head-tag" ${i18nAttrs(f.tagline)}>${esc(L(f.tagline))}</span>
        </header>
        <dl class="tr-cmp-stack-list">
            ${COMPARE_ROWS.map(row => `
            <dt><i class="${esc(row.icon)}" aria-hidden="true"></i>
                <span ${i18nAttrs(row.label)}>${esc(L(row.label))}</span></dt>
            <dd ${i18nAttrs(f[row.key])}>${esc(L(f[row.key]))}</dd>`).join('')}
        </dl>
    </section>`).join('');

        return table + `<div class="tr-cmp-stacked">${stacked}</div>`;
    }

    /** The two "what is a X track" explainer panels above the comparison. */
    function familyExplainerHTML() {
        return familyList().map(f => `
    <article class="tr-explain tr-accent-${f.accent}">
        <span class="tr-explain-icon" aria-hidden="true"><i class="${esc(f.icon)}"></i></span>
        <h3 class="tr-explain-name" ${i18nAttrs(f.name)}>${esc(L(f.name))}</h3>
        <p class="tr-explain-line" ${i18nAttrs(f.oneLine)}>${esc(L(f.oneLine))}</p>
        <p class="tr-explain-eg" ${i18nAttrs(f.example)}>${esc(L(f.example))}</p>
    </article>`).join('');
    }

    /** Grey card while the API answers — one per course we know we will show. */
    function skeletonHTML(count) {
        let out = '';
        for (let i = 0; i < count; i++) {
            out += `
    <article class="gc-card gc-card-skeleton" aria-hidden="true">
        <div class="gc-media gc-sk"></div>
        <div class="gc-body">
            <div class="gc-sk gc-sk-line gc-sk-title"></div>
            <div class="gc-sk-stats">
                <div class="gc-sk gc-sk-chip"></div>
                <div class="gc-sk gc-sk-chip"></div>
            </div>
            <div class="gc-sk-meta">
                <div class="gc-sk gc-sk-inst"></div>
            </div>
            <div class="gc-sk gc-sk-btn"></div>
        </div>
    </article>`;
        }
        return out;
    }

    function emptyHTML() {
        return `
    <div class="gc-empty">
        <i class="fa-solid fa-graduation-cap" aria-hidden="true"></i>
        <p data-ar="مفيش كورسات معروضة دلوقتي. جرّب تعمل ريفريش بعد شوية."
           data-en="No courses to show right now. Try refreshing in a moment.">مفيش كورسات معروضة دلوقتي. جرّب تعمل ريفريش بعد شوية.</p>
    </div>`;
    }

    /**
     * Fill a container with course cards: skeleton → cards, or the empty state
     * if the list comes back with nothing. Re-runs itself on `languagechange`
     * so the cards follow the language like static markup does.
     */
    function renderCourseGrid(el, opts) {
        if (!el) return Promise.resolve([]);
        const o = opts || {};
        el.classList.add('gc-grid');
        el.innerHTML = skeletonHTML(o.limit || COURSES.length);

        // Most of the card is written in the current language by `L()` at
        // render time, but the "محتوى الكورس" button and the empty state are
        // plain data-ar/data-en markup like the rest of the site. i18n.js has
        // already made its page-load pass by the time this paints, so those
        // two have to be handed to it explicitly or they stay Arabic on the
        // English site.
        const paint = html => {
            el.innerHTML = html;
            if (typeof window.applyLanguageTo === 'function') window.applyLanguageTo(el);
        };

        return load().then(list => {
            const shown = o.limit ? list.slice(0, o.limit) : list;
            paint(shown.length ? shown.map(courseCardHTML).join('') : emptyHTML());
            if (!el.dataset.langBound) {
                el.dataset.langBound = '1';
                document.addEventListener('languagechange', () => {
                    load().then(l2 => {
                        const s2 = o.limit ? l2.slice(0, o.limit) : l2;
                        paint(s2.length ? s2.map(courseCardHTML).join('') : emptyHTML());
                    });
                });
            }
            return shown;
        });
    }

    /**
     * Fill a totals bar (`[data-total="courses"]` / `[data-total="hours"]`)
     * with the catalog-wide figures and reveal it.
     */
    function renderTotals(el) {
        if (!el) return Promise.resolve(null);
        return load().then(list => {
            const t = totals(list);
            const set = (key, value) => {
                const node = el.querySelector(`[data-total="${key}"]`);
                if (node) node.textContent = value;
            };
            set('courses', t.courses);
            set('hours', t.hours + '+');
            set('lessons', t.lessons);
            el.classList.remove('is-pending');
            return t;
        });
    }

    // ─── Auto-init ──────────────────────────────────────────────
    // Any page that wants the course grid just puts `<div id="coursesGrid">`
    // (and optionally a totals bar) in its markup and loads this file — the
    // home page and /courses do exactly that and share this one code path,
    // so there is no second copy of the wiring to drift.
    function autoInit() {
        renderCourseGrid(document.getElementById('coursesGrid'));
        renderTotals(document.getElementById('coursesTotals'));
        // The home page's tracks teaser — same deal: drop the container in and
        // this fills it, so the home page holds no track data of its own.
        renderFamilyTeaser(document.getElementById('trackFamilies'));
        // Same deal for the home page's instructor section.
        renderHomeInstructors(document.getElementById('homeInstructors'));
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    window.GhawyCatalog = {
        API_BASE,
        INSTRUCTORS, TRACKS, COURSES, FAMILIES, COMPARE_ROWS,
        L, esc, i18nAttrs, mediaURL,
        durationToMinutes, minutesToDuration, isSoon,
        instructor, track, family,
        load, courseBySlug, lessonsFor, totals,
        coursesByInstructor, instructorList, courseCountFor, soonCountFor,
        yearsLineFor,
        familyList, trackList, trackHref,
        coursesInTrack, trackStats, trackListWithStats,
        coursesWord, lessonsWord, hoursWord, SOON,
        courseCardHTML, instructorCardHTML, linksHTML,
        homeInstructorCardHTML, renderHomeInstructors,
        instructorBarHTML, factsHTML, clientsHTML,
        introVideoHTML, courseVideoHTML,
        trackThumbHTML, trackCardHTML, trackSkeletonHTML,
        renderTrackCards, renderFamilyTeaser,
        compareHTML, familyExplainerHTML,
        skeletonHTML, emptyHTML, renderCourseGrid, renderTotals,
        avatarHTML,
    };
})();
