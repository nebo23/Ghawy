// ═══ GHAWY REVIEWS — one source for member testimonials ═══
//
// Everything the public site says in a testimonial comes from REVIEWS below.
//
// ── Adding a review ──
// Add ONE entry to REVIEWS and it appears on the home page. Nothing else has
// to change — no HTML, no CSS, no renderer edit. The order of the array is the
// order on the page.
//
//   {
//     name:  { ar: 'الاسم', en: 'Name' },     // required
//     city:  { ar: 'المدينة', en: 'City' },   // optional — omit to hide the line
//     stars: 5,                               // 1–5, defaults to 5
//     quote: { ar: '…', en: '…' },            // required — the review itself
//     win:   { ar: '…', en: '…' },            // optional — a short achievement chip
//     photo: null,                            // optional — path to a real photo
//     video: null,                            // optional — a Wistia media id
//   }
//
// ── Why this is a file of its own and not part of catalog.js ──
// catalog.js is the source for courses, instructors and tracks, and its whole
// shape is built around merging static marketing fields onto live
// `GET /api/courses` data. Reviews have no API side at all — they are static
// copy — and catalog.js is already ~1300 lines. Keeping them apart is what
// makes "adding a review is one line" actually true, and lets /reviews (still
// a placeholder page) read the same source later without pulling the whole
// catalogue in.
//
// ── Photos ──
// `photo` is null on every entry on purpose. The client has not sent photos of
// the people quoted here, and putting an unattributed stock face next to a
// real person's name claims it is them. Until real photos arrive the card
// draws initials on the brand gradient, the same placeholder the instructor
// cards use. Dropping a path into `photo` swaps it, no other change.
//
// ── Video ──
// These seven reviews were filmed and used to play as Wistia embeds inside a
// carousel nobody could work out how to open. The section is text cards now,
// but the media ids are kept in `video` so a card can get its clip back later
// without hunting for them. The renderer deliberately ignores the field today.

(function () {
    'use strict';

    const REVIEWS = [
        {
            name: { ar: 'عمر عماد', en: 'Omar Emad' },
            city: { ar: 'الإسكندرية', en: 'Alexandria' },
            stars: 5,
            quote: {
                ar: 'وانا لسه في نص الكورس جبت اول عميل ليا وكانت عيادة اسنان ودفعوا فلوس حلوه',
                en: 'Halfway through the course, I landed my first client — a dental clinic. They paid well.',
            },
            win: { ar: 'أول عميل وهو في نص الكورس', en: 'First client mid-course' },
            photo: null,
            video: 'oqg0kwtp2y',
        },
        {
            name: { ar: 'كريم طارق', en: 'Karim Tarek' },
            city: { ar: 'القاهرة', en: 'Cairo' },
            stars: 5,
            quote: {
                ar: 'خلصت الكورس وشامل كل حاجة ومن أحسن الكورسات اللي شوفتها',
                en: "Finished the course — it covers everything. One of the best courses I've ever taken.",
            },
            win: null,
            photo: null,
            video: 'p6kqa3edvy',
        },
        {
            name: { ar: 'زياد تامر', en: 'Ziad Tamer' },
            city: { ar: 'القاهرة', en: 'Cairo' },
            stars: 5,
            quote: {
                ar: 'سبت الميديا باينج وقررت اعمل كارير شيفت وكورس محمد كان احسن كورس انا شفته',
                en: "Left media buying and pivoted my career. Mohamed's course was the best I've ever seen.",
            },
            win: { ar: 'غيّر مساره من الميديا باينج', en: 'Career switch out of media buying' },
            photo: null,
            video: 'vj9ymlhi7z',
        },
        {
            name: { ar: 'منذر', en: 'Munzer' },
            city: { ar: 'الغربية', en: 'Al-Gharbia' },
            stars: 5,
            quote: {
                ar: 'أسست وكالة stirx.ai, أخدت كورسات على Udemy و Coursera بس الكم ده من المعلومات عمري ما شوفته في كورس واحد',
                en: "Founded stirx.ai. I've taken courses on Udemy and Coursera — never seen this much value in a single course.",
            },
            win: { ar: 'أسّس وكالة stirx.ai', en: 'Founded stirx.ai' },
            photo: null,
            video: 'f19iov9z3o',
        },
        {
            name: { ar: 'يوسف دسوقي', en: 'Youssef Dessouky' },
            city: { ar: 'القاهرة', en: 'Cairo' },
            stars: 5,
            quote: {
                ar: 'مفيش كورس متكامل بالشكل ده في الوطن العربي',
                en: 'There is no other course this complete in the Arab world.',
            },
            win: null,
            photo: null,
            video: 'lh58056wkw',
        },
        {
            name: { ar: 'ياسين مصطفى', en: 'Yassin Mostafa' },
            city: { ar: 'الجيزة', en: 'Giza' },
            stars: 5,
            quote: {
                ar: 'جبت أول عميل ليا بعد ما خلصت الكورس بأسبوعين',
                en: 'Got my first client just two weeks after finishing the course.',
            },
            win: { ar: 'أول عميل بعد أسبوعين', en: 'First client in two weeks' },
            photo: null,
            video: 'sn2k9l641c',
        },
        {
            name: { ar: 'معتز', en: 'Moataz' },
            city: { ar: 'القاهرة', en: 'Cairo' },
            stars: 5,
            quote: {
                ar: 'لما دخلت الكورس لقيت حاجات عمري ما سمعت عنها, أنت مش بتشتري كورس، أنت بتشتري باكج كاملة فيها مجتمع ومتابعة شخصية',
                en: "Joined and found things I'd never heard of before. You're not buying a course — you're buying a complete package with community and personal mentoring.",
            },
            win: null,
            photo: null,
            video: '8n571cb98s',
        },
    ];

    // ─── Helpers ────────────────────────────────────────────────
    // Same shapes as catalog.js so the two files read alike. They are copied
    // rather than imported because this file has to work on its own — the
    // /reviews page will load it without the catalogue.

    function lang() {
        return (typeof window.currentLang === 'function') ? window.currentLang() : 'ar';
    }

    /** Pick the current language out of an {ar, en} pair. */
    function L(pair) {
        if (pair == null) return '';
        if (typeof pair === 'string') return pair;
        const v = pair[lang()];
        if (v != null) return v;
        return pair.ar != null ? pair.ar : (pair.en != null ? pair.en : '');
    }

    function esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    /** data-ar/data-en on an element so i18n.js keeps it in sync. */
    function i18nAttrs(pair) {
        if (pair == null) return '';
        if (typeof pair === 'string') return `data-ar="${esc(pair)}" data-en="${esc(pair)}"`;
        return `data-ar="${esc(pair.ar || '')}" data-en="${esc(pair.en || pair.ar || '')}"`;
    }

    function initials(name) {
        return String(name || '?').trim().split(/\s+/).slice(0, 2)
            .map(w => w[0]).join(' ');
    }

    function avatarHTML(rev) {
        const name = L(rev.name);
        if (rev.photo) {
            return `<img class="rv-avatar" src="${esc(rev.photo)}" alt="${esc(name)}" loading="lazy" />`;
        }
        return `<span class="rv-avatar rv-avatar-fallback" aria-hidden="true">${esc(initials(name))}</span>`;
    }

    /**
     * Stars as text, with the count in the label rather than in the glyphs —
     * a screen reader reading "★★★★★" out loud is noise.
     */
    function starsHTML(n) {
        const count = Math.max(1, Math.min(5, Number(n) || 5));
        const label = lang() === 'ar' ? `${count} من 5` : `${count} out of 5`;
        return `<span class="rv-stars" role="img" aria-label="${esc(label)}">${'★'.repeat(count)}</span>`;
    }

    // ─── Card ───────────────────────────────────────────────────

    /**
     * One review card.
     *
     * The quote is clamped to three lines and opened by a real <button>, not
     * by a click handler on the card. That is the whole point of the rebuild:
     * the previous section promoted a card to a hero on click and hid a play
     * button inside it, and the client's report was that people could not work
     * out how to open one. A button gets the pointer cursor, keyboard focus,
     * Enter/Space and touch for free, and says what it does.
     *
     * The button ships hidden (`hidden` attribute) and is revealed by
     * `revealToggles()` only on the cards whose text is actually clamped —
     * a short review with a "read the full review" button under it that does
     * nothing visible is its own small confusion.
     */
    function reviewCardHTML(rev, i) {
        const name = L(rev.name);
        const bodyId = `rvQuote-${i}`;
        const city = rev.city
            ? `<span class="rv-city" ${i18nAttrs(rev.city)}>${esc(L(rev.city))}</span>`
            : '';
        const win = rev.win
            ? `<span class="rv-win"><i class="fa-solid fa-arrow-trend-up" aria-hidden="true"></i>
                   <span ${i18nAttrs(rev.win)}>${esc(L(rev.win))}</span></span>`
            : '';

        return `
    <article class="rv-card">
        <div class="rv-head">
            ${avatarHTML(rev)}
            <div class="rv-ident">
                <span class="rv-name" ${i18nAttrs(rev.name)}>${esc(name)}</span>
                ${city}
            </div>
        </div>
        ${starsHTML(rev.stars)}
        ${win}
        <p class="rv-quote" id="${bodyId}" ${i18nAttrs(rev.quote)}>${esc(L(rev.quote))}</p>
        <button type="button" class="rv-toggle" aria-expanded="false" aria-controls="${bodyId}" hidden>
            <span class="rv-toggle-label"
                  data-ar="اقرا الرأي كامل" data-en="Read full review">اقرا الرأي كامل</span>
            <i class="fa-solid fa-chevron-down" aria-hidden="true"></i>
        </button>
    </article>`;
    }

    function emptyHTML() {
        return `
    <div class="rv-empty">
        <i class="fa-solid fa-comments" aria-hidden="true"></i>
        <p data-ar="مفيش آراء معروضة دلوقتي." data-en="No reviews to show right now.">مفيش آراء معروضة دلوقتي.</p>
    </div>`;
    }

    // ─── Render ─────────────────────────────────────────────────

    /**
     * Show the toggle only where the text is really cut off.
     *
     * Has to run after paint — before layout `scrollHeight` and `clientHeight`
     * are both 0 and every button would stay hidden. It also re-runs on
     * resize and on a language switch, because the same quote clamps at three
     * lines in Arabic and at two in English (or the other way round) depending
     * on the width.
     */
    function revealToggles(el) {
        el.querySelectorAll('.rv-card').forEach(card => {
            const quote = card.querySelector('.rv-quote');
            const btn = card.querySelector('.rv-toggle');
            if (!quote || !btn) return;
            if (card.classList.contains('is-open')) return; // measuring an open card tells us nothing
            btn.hidden = quote.scrollHeight - quote.clientHeight <= 1;
        });
    }

    /**
     * Fill a container with the review cards.
     *
     * No skeleton here on purpose: the data is static and paints in the same
     * tick as the call, so a loading state would be a flash of grey that never
     * corresponded to any wait. Lists that come off the API (the course grid)
     * still get one.
     */
    function renderReviews(el, opts) {
        if (!el) return;
        const o = opts || {};
        const list = o.limit ? REVIEWS.slice(0, o.limit) : REVIEWS;

        el.classList.add('rv-grid');
        el.innerHTML = list.length ? list.map(reviewCardHTML).join('') : emptyHTML();

        // Most of the card is written in the current language at render time,
        // but the toggle label and the empty state are plain data-ar/data-en.
        // i18n.js has already made its page-load pass by now, so they have to
        // be handed to it explicitly or they stay Arabic on the English site.
        if (typeof window.applyLanguageTo === 'function') window.applyLanguageTo(el);
        requestAnimationFrame(() => revealToggles(el));

        if (el.dataset.rvBound) return;
        el.dataset.rvBound = '1';

        // One delegated listener for the whole grid — the cards are rebuilt on
        // every language switch, so per-button listeners would be re-bound (or
        // leaked) each time.
        el.addEventListener('click', e => {
            const btn = e.target.closest('.rv-toggle');
            if (!btn || !el.contains(btn)) return;
            const card = btn.closest('.rv-card');
            if (!card) return;
            const open = !card.classList.contains('is-open');
            card.classList.toggle('is-open', open);
            btn.setAttribute('aria-expanded', String(open));
            const label = btn.querySelector('.rv-toggle-label');
            if (label) {
                const ar = open ? 'اعرض أقل' : 'اقرا الرأي كامل';
                const en = open ? 'Show less' : 'Read full review';
                label.setAttribute('data-ar', ar);
                label.setAttribute('data-en', en);
                label.textContent = lang() === 'ar' ? ar : en;
            }
        });

        document.addEventListener('languagechange', () => {
            if (!document.body.contains(el)) return;
            renderReviews(el, o);
        });

        let resizeTimer;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => revealToggles(el), 150);
        });
    }

    // ─── Auto-init ──────────────────────────────────────────────
    // A page wanting the reviews just drops `<div id="reviewsGrid">` into its
    // markup and loads this file.
    function autoInit() {
        renderReviews(document.getElementById('reviewsGrid'));
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    window.GhawyReviews = {
        REVIEWS,
        L, esc, i18nAttrs,
        reviewCardHTML, emptyHTML, renderReviews,
    };
})();
