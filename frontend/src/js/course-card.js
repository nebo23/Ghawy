/* ═══ COURSE CARD — one renderer, both member pages ═══════════════
 *
 * The dashboard (dashboard-new.js → renderCourses) and the courses page
 * (courses.js) each drew their own copy of this card, with the same class
 * names and slightly different markup. Two copies of a card is two cards: the
 * dashboard grew a status pill the courses page never had, and the courses
 * page grew a footer the dashboard never showed. Whichever file you edited,
 * the other page kept the old look.
 *
 * So the markup lives here and both pages call `GhawyCourseCard.html(course)`.
 * The file draws a card and nothing else — no fetching, no state, no DOM
 * beyond the string it returns.
 *
 * ── The card ──
 * A 16:9 thumbnail with the track name over it and, once the member has
 * started, a progress ring; the title; who teaches it; then the two numbers
 * that people actually scan for — lessons and runtime — as pills big enough
 * to read at a glance instead of the 0.7rem grey line they used to be.
 *
 * ── Why the whole card is not an <a> ──
 * The instructor's name links to their page, and an <a> inside an <a> is
 * invalid HTML — the browser closes the outer one early and the card falls
 * apart. The fix here is the "stretched link": ONE real <a> on the title whose
 * ::after covers the whole card, and the instructor link sitting above it on
 * z-index. Result: the entire card is clickable and keyboard-focusable through
 * a genuine link (so Enter, middle-click, "open in new tab" and the status bar
 * URL all work for free), and the instructor link still wins its own clicks
 * with no JS at all. No role="link", no keydown handler, no stopPropagation.
 *
 * ── Two kinds of text, two ways of translating them ──
 * The generic vocabulary this card emits — "Lessons", "Duration" — is written
 * in English and translated by community-i18n.js, like every other word in the
 * community. Its DICT has an entry for each.
 *
 * The catalog's own strings — the course title, the track name, the
 * instructor's name — are NOT. They already exist in both languages, written
 * by the client, and DICT is a poor place to restate them: a title that has to
 * carry search highlighting is no longer one whole text node, so exact-match
 * translation cannot reach it and an Arabic reader searching in Arabic would
 * get English fragments back. Those come out of the catalog in the current
 * language instead, and `onLangChange` re-renders the grid when the language
 * flips — which is the same guarantee DICT gives, obtained by redrawing rather
 * than by rewriting text nodes.
 */
(function () {
    'use strict';

    var API_BASE = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
        ? 'http://127.0.0.1:8000'
        : '/api';

    function esc(s) {
        return window.escapeHtml ? window.escapeHtml(s) : String(s == null ? '' : s);
    }

    /* The catalog is optional: without it (or for a course the client has not
       listed yet) the card simply has no instructor row and no track chip. */
    function data() { return window.GhawyCatalogData || {}; }

    function catalogEntry(courseId) {
        var list = data().COURSES || [];
        for (var i = 0; i < list.length; i++) {
            if (list[i].courseId === courseId) return list[i];
        }
        return null;
    }

    function instructorFor(courseId) {
        var entry = catalogEntry(courseId);
        var all = data().INSTRUCTORS || {};
        return entry && entry.instructor ? (all[entry.instructor] || null) : null;
    }

    function trackFor(courseId) {
        var entry = catalogEntry(courseId);
        var all = data().TRACKS || {};
        return entry && entry.track ? (all[entry.track] || null) : null;
    }

    function lang() {
        return (typeof window.currentLang === 'function')
            ? window.currentLang()
            : (document.documentElement.getAttribute('lang') === 'en' ? 'en' : 'ar');
    }

    /* Pick the current language out of an {ar, en} pair, falling back on a
       MISSING side only — never on an empty one, which is sometimes deliberate
       (see the same note in catalog.js). */
    function L(pair) {
        if (pair == null) return '';
        if (typeof pair === 'string') return pair;
        var v = pair[lang()];
        if (v != null) return v;
        return pair.ar != null ? pair.ar : (pair.en != null ? pair.en : '');
    }

    /**
     * Run `fn` whenever the page language changes.
     *
     * Both engines that can flip it (i18n.js from Settings, community-i18n.js
     * on load) do the same one observable thing: set `lang` on <html>. Watching
     * the attribute therefore catches every path, present and future, where
     * subscribing to one engine's own event would catch only its own.
     */
    function onLangChange(fn) {
        var last = lang();
        new MutationObserver(function () {
            var now = lang();
            if (now !== last) { last = now; fn(now); }
        }).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    }

    function mediaURL(url) {
        if (!url) return '';
        return url.charAt(0) === '/' ? API_BASE + url : url;
    }

    function durationToMinutes(text) {
        if (!text) return 0;
        var h = /(\d+)\s*h/i.exec(text);
        var m = /(\d+)\s*m/i.exec(text);
        return (h ? parseInt(h[1], 10) * 60 : 0) + (m ? parseInt(m[1], 10) : 0);
    }

    function initials(name) {
        var parts = String(name || '?').trim().split(/\s+/).slice(0, 2);
        return parts.map(function (w) { return w.charAt(0); }).join('').toUpperCase();
    }

    /* ── Progress ring ──
       34px, drawn as two circles: a faint track and an arc dashed to the
       percentage. It replaces the old square "30%" badge because a ring reads
       as an amount at a distance, where a small number reads as a small number.
       Hidden entirely at 0% — an empty ring on an untouched course is noise,
       and its absence is what makes a started course stand out. */
    var RING_R = 15;
    var RING_C = 2 * Math.PI * RING_R;

    function ringHTML(pct) {
        if (!(pct > 0)) return '';
        var offset = RING_C * (1 - Math.min(100, pct) / 100);
        var done = pct >= 100;
        return '' +
            '<div class="cc-ring' + (done ? ' is-done' : '') + '" role="img"' +
            ' aria-label="' + pct + '% complete">' +
            '<svg viewBox="0 0 34 34" aria-hidden="true">' +
            '<circle class="cc-ring-track" cx="17" cy="17" r="' + RING_R + '"></circle>' +
            '<circle class="cc-ring-arc" cx="17" cy="17" r="' + RING_R + '"' +
            ' stroke-dasharray="' + RING_C.toFixed(2) + '"' +
            ' stroke-dashoffset="' + offset.toFixed(2) + '"></circle>' +
            '</svg>' +
            '<span class="cc-ring-num" aria-hidden="true">' + Math.round(pct) + '</span>' +
            '</div>';
    }

    function avatarHTML(inst) {
        var name = L(inst.name);
        if (inst.photo) {
            return '<span class="cc-inst-av"><img src="' + esc(inst.photo) + '" alt="" loading="lazy"' +
                ' onerror="this.parentElement.textContent=this.getAttribute(\'data-i\')"' +
                ' data-i="' + esc(initials(name)) + '"></span>';
        }
        return '<span class="cc-inst-av cc-inst-av-txt">' + esc(initials(name)) + '</span>';
    }

    /** The course's name as this reader should see it: the catalog's title in
     *  the current language, or the platform's own title for a course the
     *  catalog does not list yet. courses.js searches and highlights against
     *  exactly this string, so what matches is what is on screen. */
    function title(course) {
        var entry = catalogEntry(course.id);
        var fromCatalog = entry ? L(entry.title) : '';
        return fromCatalog || course.title || '';
    }

    /**
     * One card.
     *
     * `course` is the normalised shape both pages build:
     *   { id, title, thumbnail_url, total_lessons, course_time, pct }
     * `opts.highlight` optionally receives the title already escaped AND marked
     * up (the search wraps its matches in <mark>) — it is the only place this
     * renderer accepts HTML, and courses.js is the only caller that passes it.
     */
    function html(course, opts) {
        opts = opts || {};
        var id = course.id;
        var pct = Math.round(course.pct || 0);
        var thumb = mediaURL(course.thumbnail_url);
        var inst = instructorFor(id);
        var track = trackFor(id);
        var lessons = course.total_lessons || 0;
        var titleHTML = opts.highlight != null ? opts.highlight : esc(title(course));

        var state = pct >= 100 ? 'completed' : (pct > 0 ? 'in-progress' : 'not-started');

        var thumbInner = thumb
            ? '<img class="cc-thumb-img" src="' + esc(thumb) + '" alt="" loading="lazy" decoding="async"' +
              ' onerror="this.style.display=\'none\'">'
            : '';

        /* A course the client has not put in the catalog yet has no instructor
           and no track. Draw nothing for it rather than an empty row — an
           unexplained blank line reads as a bug, a missing row reads as a card
           that simply has less to say. */
        var trackChip = track
            ? '<span class="cc-track-chip">' + esc(L(track.name)) + '</span>'
            : '';

        var instRow = inst
            ? '<div class="cc-inst">' + avatarHTML(inst) +
              '<a class="cc-inst-name" href="instructors.html?i=' + encodeURIComponent(inst.slug) + '">' +
              esc(L(inst.name)) + '</a></div>'
            : '';

        var timePill = course.course_time
            ? '<div class="cc-pill cc-pill-time">' +
              '<span class="cc-pill-ico"><i class="fa-regular fa-clock"></i></span>' +
              '<span class="cc-pill-txt"><b>' + esc(course.course_time) + '</b><i>Duration</i></span>' +
              '</div>'
            : '';

        return '' +
            '<article class="course-card" data-course-id="' + id + '" data-state="' + state + '">' +
              '<div class="cc-thumb">' +
                thumbInner +
                '<span class="cc-scrim"></span>' +
                trackChip +
                ringHTML(pct) +
              '</div>' +
              '<div class="cc-body">' +
                '<h3 class="cc-title">' +
                  '<a class="cc-link" href="course-detail.html?id=' + id + '">' + titleHTML + '</a>' +
                '</h3>' +
                instRow +
                '<div class="cc-stats">' +
                  '<div class="cc-pill cc-pill-lessons">' +
                    '<span class="cc-pill-ico"><i class="fa-solid fa-book"></i></span>' +
                    '<span class="cc-pill-txt"><b>' + lessons + '</b><i>Lessons</i></span>' +
                  '</div>' +
                  timePill +
                '</div>' +
                '<div class="cc-prog"><span class="cc-prog-fill ' + state + '"' +
                ' style="width:' + Math.min(100, pct) + '%"></span></div>' +
              '</div>' +
            '</article>';
    }

    /* Shimmering placeholders while the three requests are in flight. A single
       centred spinner told the member nothing about what was coming; these hold
       the grid's shape so nothing jumps when the real cards land. */
    function skeleton(count) {
        var one = '<div class="course-card cc-skeleton" aria-hidden="true">' +
            '<div class="cc-thumb"></div>' +
            '<div class="cc-body">' +
              '<div class="cc-sk-line cc-sk-title"></div>' +
              '<div class="cc-sk-line cc-sk-inst"></div>' +
              '<div class="cc-sk-pills"><div class="cc-sk-pill"></div><div class="cc-sk-pill"></div></div>' +
            '</div></div>';
        return new Array(count || 8).fill(one).join('');
    }

    window.GhawyCourseCard = {
        html: html,
        skeleton: skeleton,
        instructorFor: instructorFor,
        trackFor: trackFor,
        catalogEntry: catalogEntry,
        durationToMinutes: durationToMinutes,
        title: title,
        lang: lang,
        L: L,
        onLangChange: onLangChange,
        mediaURL: mediaURL,
    };
})();
