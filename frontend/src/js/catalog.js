// ═══ GHAWY CATALOG — one source for courses, instructors and tracks ═══
//
// Everything the public site says about a course or an instructor comes from
// this file. Before it existed, the six course cards were written by hand in
// index.html, again (with different fields) in course-details.html, and a
// third time in the /courses shell — changing a duration meant three edits and
// they had already drifted apart.
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
// track it belongs to. That lives in COURSES below and is merged onto the API
// response by `courseId`. If the API is unreachable the static values below
// are used as-is, so the page still renders.
//
// ── Curation ──
// COURSES is also the running order of the public site: a course appears on
// the marketing pages because it has an entry here, not because it is
// published in the platform. That is deliberate — publishing a course for
// members should not silently put it on the home page. To add one: add an
// entry with its `courseId` and it shows up everywhere (home, /courses,
// /course-details, /instructors) with no other change.
//
// ── Adding an instructor ──
// Add an entry to INSTRUCTORS and point a course's `instructor` at its slug.
// Nothing else needs to change: the card, the instructor bar, the instructor
// list and the instructor detail page all read from here.
//
// ── Assets ──
// Instructor photos, client logos and intro videos have not been delivered
// yet. Every one of those fields accepts `null`, and the renderers below draw
// a clean placeholder for it. Dropping the real asset in later is a one-line
// change in THIS file — no HTML or CSS is touched.

(function () {
    'use strict';

    const API_BASE = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
        ? 'http://127.0.0.1:8000'
        : '/api';

    // ─── Instructors ────────────────────────────────────────────
    // `clients` are the brands/creators they have worked with — shown as the
    // client strip in the instructor bar. `logo: null` renders the name as a
    // chip; give it a path and it renders the image instead.
    const INSTRUCTORS = {
        'mohamed-salah': {
            slug: 'mohamed-salah',
            name: { ar: 'محمد صلاح', en: 'Mohamed Salah' },
            photo: null,                       // → placeholder avatar
            role: {
                ar: 'مؤسس غاوي ومدرّب AI Automation',
                en: 'Founder of Ghawy — AI Automation instructor'
            },
            yearsExperience: 4,
            clientsCount: 35,
            clients: [
                { name: { ar: 'بولتكس', en: 'Poltex' }, logo: null },
                { name: { ar: 'أبو فولة', en: 'Abo Flah' }, logo: null },
                { name: { ar: 'مروان ريحان', en: 'Marwan Rayhan' }, logo: null },
                { name: { ar: 'بشر جيماوي', en: 'Bishr Gemawi' }, logo: null },
            ],
            links: {
                instagram: 'https://instagram.com/ghawy_official',
                tiktok: 'https://tiktok.com/@ghawy_official',
                facebook: 'https://facebook.com/ghawyofficial',
            },
            introVideo: null,                  // → "coming soon" placeholder
            bio: {
                ar: 'بدأ أونلاين بيزنس وهو عنده 14 سنة، واشتغل في البرمجة والجرافيك والتسويق قبل ما يستقر على الـ AI والأوتوميشن. أسّس غاوي عشان يبني المصدر العربي اللي كان ناقصه هو نفسه وهو بيتعلّم.',
                en: 'Started an online business at 14 and worked through programming, design and marketing before settling on AI and automation. He founded Ghawy to build the Arabic resource he could not find while learning it himself.'
            }
        },
    };

    // ─── Tracks ─────────────────────────────────────────────────
    // The learning paths courses are grouped under. /tracks is still a shell,
    // so every track links to the page itself with its slug in the hash —
    // when that page ships it can read the hash and open the right one.
    const TRACKS = {
        'foundations': {
            slug: 'foundations',
            name: { ar: 'مسار الأساسيات', en: 'Foundations track' },
        },
        'automation': {
            slug: 'automation',
            name: { ar: 'مسار الأوتوميشن', en: 'Automation track' },
        },
        'agency': {
            slug: 'agency',
            name: { ar: 'مسار الوكالة والبيزنس', en: 'Agency & business track' },
        },
    };

    // ─── Courses ────────────────────────────────────────────────
    // `courseId` is the row id in the platform database — the join key for the
    // API merge. `lessons`/`duration` here are only the offline fallback; the
    // API overwrites them when it answers.
    const COURSES = [
        {
            slug: 'ai-foundations',
            courseId: 5,
            title: { ar: 'أساسيات الذكاء الاصطناعي', en: 'AI Foundations' },
            image: './imgs/course1.jpg',
            lessons: 10,
            duration: '12h 3m',
            track: 'foundations',
            instructor: 'mohamed-salah',
        },
        {
            slug: 'aaa-core',
            courseId: 6,
            title: { ar: 'AAA Core', en: 'AAA Core' },
            image: './imgs/course2.jpg',
            lessons: 7,
            duration: '12h 11m',
            track: 'agency',
            instructor: 'mohamed-salah',
        },
        {
            slug: 'prompt-engineering',
            courseId: 7,
            title: { ar: 'Prompt Engineering', en: 'Prompt Engineering' },
            image: './imgs/course3.jpg',
            lessons: 4,
            duration: '5h 3m',
            track: 'foundations',
            instructor: 'mohamed-salah',
        },
        {
            slug: 'ai-automation-lab',
            courseId: 8,
            title: { ar: 'AI Automation Lab', en: 'AI Automation Lab' },
            image: './imgs/course4.jpg',
            lessons: 11,
            duration: '9h 36m',
            track: 'automation',
            instructor: 'mohamed-salah',
        },
        {
            slug: 'client-acquisition',
            courseId: 9,
            title: { ar: 'Client Acquisition', en: 'Client Acquisition' },
            image: './imgs/course6.jpg',
            lessons: 6,
            duration: '7h 47m',
            track: 'agency',
            instructor: 'mohamed-salah',
        },
        {
            slug: 'practical-ai-systems',
            courseId: 10,
            title: { ar: 'Practical AI Systems', en: 'Practical AI Systems' },
            image: './imgs/course5.jpg',
            lessons: 3,
            duration: '4h 7m',
            track: 'automation',
            instructor: 'mohamed-salah',
        },
    ];

    // ─── Helpers ────────────────────────────────────────────────

    function lang() {
        return (typeof window.currentLang === 'function') ? window.currentLang() : 'ar';
    }

    /** Pick the current language out of an {ar, en} pair. */
    function L(pair) {
        if (pair == null) return '';
        if (typeof pair === 'string') return pair;
        return pair[lang()] || pair.ar || pair.en || '';
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

    /** Instructors in a stable order, so the list page never reshuffles. */
    function instructorList() {
        return Object.keys(INSTRUCTORS).map(k => INSTRUCTORS[k]);
    }

    /** Totals across the whole catalog — for the "all of Ghawy" bar. */
    function totals(list) {
        const courses = list || COURSES;
        const mins = courses.reduce((s, c) => s + durationToMinutes(c.duration), 0);
        return {
            courses: courses.length,
            lessons: courses.reduce((s, c) => s + (c.lessons || 0), 0),
            minutes: mins,
            hours: Math.round(mins / 60),
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
     * The instructor bar — the one component used everywhere an instructor is
     * shown. `compact` is the row inside a course card (photo + name + role);
     * `full` adds the client strip, the experience line and the intro video,
     * and is what the course preview and the instructor pages use.
     */
    function instructorBarHTML(inst, opts) {
        if (!inst) return '';
        const o = opts || {};
        const variant = o.variant === 'full' ? 'full' : 'compact';
        const href = `/instructors?i=${encodeURIComponent(inst.slug)}`;
        const name = L(inst.name);

        if (variant === 'compact') {
            return `
        <a class="gi-bar gi-bar-compact" href="${href}">
            ${avatarHTML(inst, 'gi-avatar')}
            <span class="gi-ident">
                <span class="gi-name">${esc(name)}</span>
                <span class="gi-role" ${i18nAttrs(inst.role)}>${esc(L(inst.role))}</span>
            </span>
        </a>`;
        }

        const yearsLine = {
            ar: `خبرة أكتر من ${inst.yearsExperience} سنين`,
            en: `${inst.yearsExperience}+ years of experience`,
        };
        const clientsLine = inst.clientsCount ? {
            ar: `اشتغل مع أكتر من ${inst.clientsCount} عميل`,
            en: `Worked with ${inst.clientsCount}+ clients`,
        } : null;

        const clientChips = (inst.clients || []).map(c => c.logo
            ? `<span class="gi-client"><img src="${esc(c.logo)}" alt="${esc(L(c.name))}" loading="lazy" /></span>`
            : `<span class="gi-client gi-client-text" ${i18nAttrs(c.name)}>${esc(L(c.name))}</span>`
        ).join('');

        return `
        <div class="gi-bar gi-bar-full">
            <div class="gi-head">
                <a class="gi-head-link" href="${href}">${avatarHTML(inst, 'gi-avatar gi-avatar-lg')}</a>
                <div class="gi-ident">
                    <a class="gi-name gi-name-lg" href="${href}">${esc(name)}</a>
                    <span class="gi-role" ${i18nAttrs(inst.role)}>${esc(L(inst.role))}</span>
                    <span class="gi-facts">
                        <span class="gi-fact" ${i18nAttrs(yearsLine)}>${esc(L(yearsLine))}</span>
                        ${clientsLine ? `<span class="gi-fact" ${i18nAttrs(clientsLine)}>${esc(L(clientsLine))}</span>` : ''}
                    </span>
                </div>
            </div>

            ${clientChips ? `
            <div class="gi-clients">
                <span class="gi-clients-label" data-ar="اشتغل مع" data-en="Worked with">اشتغل مع</span>
                <div class="gi-clients-row">${clientChips}</div>
            </div>` : ''}

            ${o.video === false ? '' : introVideoHTML(inst)}
        </div>`;
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
        const years = {
            ar: `خبرة أكتر من ${inst.yearsExperience} سنين`,
            en: `${inst.yearsExperience}+ years of experience`,
        };
        return `
    <article class="gi-card">
        <a class="gi-card-top" href="${href}">
            ${avatarHTML(inst, 'gi-avatar gi-avatar-lg')}
            <span class="gi-ident">
                <span class="gi-name gi-name-lg">${esc(name)}</span>
                <span class="gi-role" ${i18nAttrs(inst.role)}>${esc(L(inst.role))}</span>
            </span>
        </a>
        <span class="gi-fact" ${i18nAttrs(years)}>${esc(L(years))}</span>
        <a class="gc-btn" href="${href}" data-ar="صفحة المدرّب" data-en="Instructor page">صفحة المدرّب</a>
    </article>`;
    }

    /** One course card. The same markup on the home page and on /courses. */
    function courseCardHTML(course) {
        const inst = instructor(course.instructor);
        const href = `/course-details?course=${encodeURIComponent(course.slug)}`;
        const title = L(course.title);
        const hours = {
            ar: `${course.duration} من الفيديوهات`,
            en: `${course.duration} of video`,
        };

        return `
    <article class="gc-card">
        <a class="gc-media" href="${href}" tabindex="-1" aria-hidden="true">
            <img src="${esc(course.image)}" alt="" loading="lazy" />
        </a>
        <div class="gc-body">
            <h3 class="gc-title" ${i18nAttrs(course.title)}>${esc(title)}</h3>
            ${instructorBarHTML(inst, { variant: 'compact' })}
            <div class="gc-hours">
                <i class="fa-regular fa-clock" aria-hidden="true"></i>
                <span ${i18nAttrs(hours)}>${esc(L(hours))}</span>
            </div>
            <a class="gc-btn" href="${href}" data-ar="محتوى الكورس" data-en="Course content">محتوى الكورس</a>
        </div>
    </article>`;
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
            <div class="gc-sk gc-sk-inst"></div>
            <div class="gc-sk gc-sk-line gc-sk-short"></div>
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

        return load().then(list => {
            const shown = o.limit ? list.slice(0, o.limit) : list;
            el.innerHTML = shown.length ? shown.map(courseCardHTML).join('') : emptyHTML();
            if (!el.dataset.langBound) {
                el.dataset.langBound = '1';
                document.addEventListener('languagechange', () => {
                    load().then(l2 => {
                        const s2 = o.limit ? l2.slice(0, o.limit) : l2;
                        el.innerHTML = s2.length ? s2.map(courseCardHTML).join('') : emptyHTML();
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
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    window.GhawyCatalog = {
        API_BASE,
        INSTRUCTORS, TRACKS, COURSES,
        L, esc, i18nAttrs, mediaURL,
        durationToMinutes, minutesToDuration,
        instructor, track,
        load, courseBySlug, lessonsFor, totals,
        coursesByInstructor, instructorList,
        courseCardHTML, instructorCardHTML, linksHTML,
        instructorBarHTML, introVideoHTML, courseVideoHTML,
        skeletonHTML, emptyHTML, renderCourseGrid, renderTotals,
        avatarHTML,
    };
})();
