// ═══ GHAWY REVIEWS — one source for member testimonials ═══
//
// Everything the public site says in a testimonial comes from REVIEWS below.
//
// ── What renders today ──
// Only the FILMED reviews. The client dropped the written-review cards from
// both places they appeared (the home page and /reviews), so `quote`, `stars`,
// `win`, `city` and `photo` are carried but not drawn anywhere. The array was
// deliberately left whole rather than trimmed to the video entries: every one
// of these people is filmed, the words are theirs, and putting the cards back
// is one `<div id="reviewsGrid">` plus a renderer — not a re-transcription.
//
// ── Adding a review ──
// Add ONE entry to REVIEWS. If it carries `video` + `videoPoster` it appears in
// the rail on /reviews with no other change. The order of the array is the
// order on the page.
//
//   {
//     name:  { ar: 'الاسم', en: 'Name' },     // required
//     city:  { ar: 'المدينة', en: 'City' },   // optional — shown under the poster
//     stars: 5,                               // 1–5 — carried, not drawn today
//     quote: { ar: '…', en: '…' },            // the review itself — see above
//     win:   { ar: '…', en: '…' },            // carried, not drawn today
//     photo: null,                            // carried, not drawn today
//     video: 'abc123',                        // a Wistia media id
//     videoPoster: 'imgs/…',                  // required WITH video — local still
//     videoSeconds: 78,                       // required WITH video — runtime
//   }
//
// ── Why this is a file of its own and not part of catalog.js ──
// catalog.js is the source for courses, instructors and tracks, and its whole
// shape is built around merging static marketing fields onto live
// `GET /api/courses` data. Reviews have no API side at all — they are static
// copy — and catalog.js is already ~1300 lines. Keeping them apart is what
// makes "adding a review is one line" actually true, and lets /reviews read
// the same source without pulling the whole catalogue in.
//
// ── Photos ──
// `photo` is null on every entry on purpose. The client has not sent photos of
// the people quoted here, and putting an unattributed stock face next to a
// real person's name claims it is them. Nothing reads it today — it was the
// written card's avatar — but the rule stands for whatever draws it next.
//
// ── Video ──
// All seven of these reviews were filmed. They used to play as Wistia embeds
// inside a carousel nobody could work out how to open, so the home page became
// text cards and the media ids were parked in `video`.
//
// /reviews plays them again, and deliberately not the way that failed: each
// one is a poster with a real play button on it, in a rail you scroll
// sideways, with nothing hidden behind a hover or a card promotion. With the
// text cards now gone too, these are the only thing REVIEWS still draws.
//
// Every id below was checked against Wistia's oEmbed endpoint before it was
// wired up — all seven resolve, and each one's title matches the name on its
// review ("Omar Testimonial" ↔ عمر عماد, and so on down the list). None of
// this was invented; the ids were already in this file.
//
// Nothing loads from Wistia until a visitor presses play:
//   - `videoPoster` is a LOCAL still (imgs/reviews/video/), pulled once from
//     the oEmbed thumbnail and re-encoded to webp. No external image request.
//   - the <iframe> is created by the click handler, not written into the
//     markup, so a page with seven videos on it makes zero third-party
//     requests until somebody actually wants one.
// That also means no `E-v1.js` — the plain iframe embed does not need it.
//
// `videoSeconds` is Wistia's own duration, shown on the poster so the length
// is known before the click.
//
// ── Screenshots ──
// Two arrays of image names, both under `imgs/reviews/`, and adding one is a
// single line in the right array:
//
//   SCREENSHOTS — member messages from the community chat. Scrolls above the
//                 written cards in `#reviews`.
//   RATINGS     — the course rating lists (several members and their stars in
//                 one shot). Feeds the "نتائج بالأرقام" section instead.
//
// They are split so the page never shows the same proof twice. Both live in
// this file rather than beside it because they feed the review sections, and
// a second file would mean a second <script> and two answers to "where do
// reviews live?".
//
// They are member messages lifted out of the community chat, so the person's
// name and words are baked into the pixels. That is also why the marquee is
// `aria-hidden`: the text in a screenshot cannot be read out, and writing an
// alt that paraphrases someone's testimonial would be putting words in their
// mouth. Screen readers get the real thing from the REVIEWS cards under it.

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
            videoPoster: 'imgs/reviews/video/omar-emad.webp',
            videoSeconds: 78,
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
            videoPoster: 'imgs/reviews/video/karim-tarek.webp',
            videoSeconds: 100,
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
            videoPoster: 'imgs/reviews/video/ziad-tamer.webp',
            videoSeconds: 68,
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
            videoPoster: 'imgs/reviews/video/munzer.webp',
            videoSeconds: 112,
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
            videoPoster: 'imgs/reviews/video/youssef-dessouky.webp',
            videoSeconds: 215,
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
            videoPoster: 'imgs/reviews/video/yassin-mostafa.webp',
            videoSeconds: 131,
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
            videoPoster: 'imgs/reviews/video/moataz.webp',
            videoSeconds: 133,
        },
    ];

    // Screenshots of member messages from the community chat, in
    // `imgs/reviews/`. One file name per line — order is the order they are
    // dealt across the marquee rows.
    //
    // Kept out on purpose: three shots the client flagged as needing an edit
    // (their text is cut mid-sentence), the ones carrying a complaint or a
    // feature request rather than a review, an admin's own message, and one
    // with language we are not putting on the home page. The image files for
    // those are not in the repo at all, so nothing here can bring them back by
    // accident.
    const SCREENSHOTS = [
        'chat-01.webp', 'chat-02.webp', 'chat-03.webp', 'chat-04-1.webp',
        'chat-04-2.webp', 'chat-05.webp', 'chat-06.webp', 'chat-08-1.webp',
        'chat-08-2.webp', 'chat-08-3.webp', 'chat-08-4.webp', 'chat-08-5.webp',
        'chat-11-1.webp', 'chat-11-2.webp', 'chat-12.webp',
        'chat-13-2.webp', 'chat-15.webp', 'chat-16.webp', 'chat-17.webp',
        'chat-18.webp', 'chat-19.webp', 'chat-20.webp', 'chat-21.webp',
        'chat-22-1.webp', 'chat-22-2.webp', 'chat-23.webp', 'chat-24.webp',
        'chat-25.webp', 'chat-26.webp', 'chat-27.webp', 'chat-28.webp',
        'chat-29.webp', 'chat-30.webp', 'chat-31.webp', 'chat-32.webp',
        'chat-33.webp', 'chat-34.webp', 'chat-35.webp', 'chat-36.webp',
        'chat-38.webp', 'chat-40.webp',
        // Members posting a first result rather than an opinion. Same kind of
        // shot — a message with a name on it — so they ride the same rows.
        'win-01.webp', 'win-02.webp',
    ];

    // The course rating lists — several members with their stars in one shot.
    // These feed the "نتائج بالأرقام" section, NOT #reviews, so the two walls
    // of proof never show the same picture twice.
    //
    // They are tall single columns rather than chat bubbles, which is why they
    // get their own treatment — `rvs-wrap--tall` in the home-page marquee and
    // `rvg-grid--tall` in the /reviews masonry — instead of being dealt in
    // with the messages above. Both are the SAME masonry as the chat shots,
    // only with a narrower column: these are ~1:2 portraits and the chat shots
    // are wide and short, so one column width cannot flatter both. Neither is
    // cropped — a screenshot made of text has nothing safe to cut.
    const RATINGS = [
        'ratings-01.webp', 'ratings-02.webp', 'ratings-03.webp',
        'ratings-04.webp', 'ratings-05.webp', 'ratings-06.webp',
    ];


    /**
     * Intrinsic pixel size of every screenshot, so an <img> can carry real
     * `width`/`height` attributes.
     *
     * Not decoration. These images are lazy AND laid out in CSS `columns`,
     * and without the attributes the browser has no aspect ratio to reserve
     * space with: every cell is zero-high until its file arrives, the whole
     * masonry collapses to nothing, then snaps to full height as the images
     * decode. With them, the column heights are correct on the first frame.
     *
     * Generated from the files themselves — if you add a screenshot, add its
     * real dimensions here too. A missing entry is not fatal (the attributes
     * are simply omitted, and you get the old jumping behaviour for that one
     * cell).
     */
    const SHOT_SIZES = {
        'chat-01.webp': [900, 628],
        'chat-02.webp': [870, 426],
        'chat-03.webp': [865, 363],
        'chat-04-1.webp': [878, 191],
        'chat-04-2.webp': [791, 136],
        'chat-05.webp': [868, 305],
        'chat-06.webp': [878, 314],
        'chat-08-1.webp': [900, 175],
        'chat-08-2.webp': [900, 289],
        'chat-08-3.webp': [900, 182],
        'chat-08-4.webp': [900, 134],
        'chat-08-5.webp': [900, 182],
        'chat-11-1.webp': [900, 320],
        'chat-11-2.webp': [900, 126],
        'chat-12.webp': [900, 292],
        'chat-13-2.webp': [900, 170],
        'chat-15.webp': [900, 197],
        'chat-16.webp': [900, 261],
        'chat-17.webp': [878, 495],
        'chat-18.webp': [900, 175],
        'chat-19.webp': [870, 364],
        'chat-20.webp': [900, 586],
        'chat-21.webp': [900, 339],
        'chat-22-1.webp': [900, 300],
        'chat-22-2.webp': [900, 220],
        'chat-23.webp': [900, 580],
        'chat-24.webp': [900, 379],
        'chat-25.webp': [900, 312],
        'chat-26.webp': [877, 428],
        'chat-27.webp': [900, 197],
        'chat-28.webp': [900, 356],
        'chat-29.webp': [900, 372],
        'chat-30.webp': [868, 295],
        'chat-31.webp': [900, 182],
        'chat-32.webp': [900, 249],
        'chat-33.webp': [870, 364],
        'chat-34.webp': [864, 232],
        'chat-35.webp': [823, 135],
        'chat-36.webp': [868, 234],
        'chat-38.webp': [878, 189],
        'chat-40.webp': [333, 213],
        'ratings-01.webp': [317, 661],
        'ratings-02.webp': [317, 714],
        'ratings-03.webp': [317, 719],
        'ratings-04.webp': [317, 591],
        'ratings-05.webp': [317, 509],
        'ratings-06.webp': [318, 681],
        'win-01.webp': [283, 249],
        'win-02.webp': [283, 174],
    };

    const SHOT_DIR = 'imgs/reviews/';
    const SHOT_ROWS = 3;

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

    /**
     * How this page is allowed to move things.
     *
     * The CSS honours prefers-reduced-motion for the marquee, but the video
     * rail is scrolled from JS, and `behavior: 'smooth'` in a scrollBy call is
     * animation the stylesheet cannot reach. Read the preference live rather
     * than once at load, so someone turning it on in their OS gets it without
     * a reload.
     */
    function scrollBehavior() {
        const reduce = window.matchMedia
            && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        return reduce ? 'auto' : 'smooth';
    }

    /** data-ar/data-en on an element so i18n.js keeps it in sync. */
    function i18nAttrs(pair) {
        if (pair == null) return '';
        if (typeof pair === 'string') return `data-ar="${esc(pair)}" data-en="${esc(pair)}"`;
        return `data-ar="${esc(pair.ar || '')}" data-en="${esc(pair.en || pair.ar || '')}"`;
    }

    /**
     * The same, but for an element's aria-label instead of its text.
     *
     * MUST be used instead of i18nAttrs() on anything with children: data-ar
     * is applied as textContent, so putting it on a button that wraps an
     * <img> or an icon deletes the child on the first language pass. i18n.js
     * reads these two and writes aria-label only.
     */
    function i18nAria(pair) {
        if (pair == null) return '';
        if (typeof pair === 'string') return `data-ar-aria="${esc(pair)}" data-en-aria="${esc(pair)}"`;
        return `data-ar-aria="${esc(pair.ar || '')}" data-en-aria="${esc(pair.en || pair.ar || '')}"`;
    }

    function emptyHTML(pair, icon) {
        const msg = pair || { ar: 'مفيش آراء معروضة دلوقتي.', en: 'No reviews to show right now.' };
        return `
    <div class="rv-empty">
        <i class="fa-solid fa-${esc(icon || 'comments')}" aria-hidden="true"></i>
        <p ${i18nAttrs(msg)}>${esc(L(msg))}</p>
    </div>`;
    }

    // ─── Video card ─────────────────────────────────────────────

    /** 131 → "2:11". */
    function clock(seconds) {
        const s = Math.max(0, Math.round(Number(seconds) || 0));
        return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
    }

    /**
     * One filmed review: a local poster, the runtime, and a play button.
     *
     * The button is a real <button> carrying the media id in a data attribute
     * — the iframe does not exist until it is pressed. That is what keeps a
     * page of seven testimonials from opening seven third-party connections
     * to show seven stills we already have locally.
     *
     * It is also the fix for the thing that killed the last video section:
     * there is one obvious control, it looks like a play button, and it is
     * focusable and operable from the keyboard. Nothing is hidden behind a
     * hover state or a click on the card body.
     */
    function videoCardHTML(rev, i) {
        const name = L(rev.name);
        const city = rev.city ? `<span class="rvv-city" ${i18nAttrs(rev.city)}>${esc(L(rev.city))}</span>` : '';
        const play = { ar: `شغّل فيديو ${name}`, en: `Play ${name}'s video` };
        return `
    <article class="rvv-card" data-video="${esc(rev.video)}">
        <div class="rvv-frame">
            <img class="rvv-poster" src="${esc(rev.videoPoster)}" alt=""
                 loading="lazy" decoding="async" width="360" height="640" />
            <button type="button" class="rvv-play" aria-label="${esc(L(play))}" ${i18nAria(play)}>
                <i class="fa-solid fa-play" aria-hidden="true"></i>
            </button>
            ${rev.videoSeconds ? `<span class="rvv-time">${esc(clock(rev.videoSeconds))}</span>` : ''}
        </div>
        <div class="rvv-foot">
            <span class="rvv-name" ${i18nAttrs(rev.name)}>${esc(name)}</span>
            ${city}
        </div>
    </article>`;
    }

    /**
     * The filmed reviews, as a horizontal rail you scroll sideways.
     *
     * A wrapping grid was wrong for these: seven 9:16 cards wrap to 4 + 3 and
     * leave a hole where the eighth would be, and shrinking them to fit one
     * row makes each one a stamp. A rail sizes every card the same, fills the
     * row edge to edge whatever the count, and grows by scrolling instead of
     * by getting taller — which matters on a page that already has three more
     * sections under it.
     *
     * Native scrolling does the work: swipe on touch, shift+wheel or a
     * trackpad on desktop, and the arrow buttons for a mouse. Scroll snapping
     * keeps cards from being left half-cut.
     */
    function renderVideos(el) {
        if (!el) return;
        const list = REVIEWS.filter(r => r.video && r.videoPoster);

        const prevLbl = { ar: 'السابق', en: 'Previous' };
        const nextLbl = { ar: 'التالي', en: 'Next' };

        const paint = () => {
            el.className = 'rvv-rail';
            if (!list.length) {
                el.innerHTML = emptyHTML({ ar: 'مفيش فيديوهات لسه.', en: 'No videos yet.' }, 'video');
                return;
            }
            // The arrows sit OUTSIDE the scroller so they never scroll away,
            // and are chevron-left/right as written — CSS mirrors them under
            // RTL, where "next" is to the left.
            el.innerHTML = `
        <button type="button" class="rvv-nav rvv-nav-prev" aria-label="${esc(L(prevLbl))}" ${i18nAria(prevLbl)}>
            <i class="fa-solid fa-chevron-left" aria-hidden="true"></i>
        </button>
        <div class="rvv-scroller" tabindex="0" role="group" aria-label="${esc(L({ ar: 'آراء بالفيديو', en: 'Video reviews' }))}">
            ${list.map(videoCardHTML).join('')}
        </div>
        <button type="button" class="rvv-nav rvv-nav-next" aria-label="${esc(L(nextLbl))}" ${i18nAria(nextLbl)}>
            <i class="fa-solid fa-chevron-right" aria-hidden="true"></i>
        </button>`;
            // Picks up the play button's aria-label via data-ar-aria too.
            if (typeof window.applyLanguageTo === 'function') window.applyLanguageTo(el);
            syncNav();
        };

        /**
         * Enable/disable the arrows, and hide them entirely when everything
         * already fits.
         *
         * Direction-agnostic on purpose. In an RTL scroller `scrollLeft`
         * starts at 0 on the RIGHT and goes NEGATIVE as you move left, so
         * comparing it against 0 the LTR way marks the rail as "at the end"
         * the moment it loads. Taking the absolute value gives one distance
         * that means the same thing in both directions.
         */
        function syncNav() {
            const sc = el.querySelector('.rvv-scroller');
            const prev = el.querySelector('.rvv-nav-prev');
            const next = el.querySelector('.rvv-nav-next');
            if (!sc || !prev || !next) return;
            const overflow = sc.scrollWidth - sc.clientWidth;
            el.classList.toggle('is-static', overflow <= 2);
            const pos = Math.abs(sc.scrollLeft);
            prev.disabled = pos <= 2;
            next.disabled = pos >= overflow - 2;
        }

        function page(dir) {
            const sc = el.querySelector('.rvv-scroller');
            if (!sc) return;
            const rtl = getComputedStyle(sc).direction === 'rtl';
            // Just under a full viewport of the rail, so the card you were
            // looking at stays partly visible as an anchor.
            const step = Math.max(200, sc.clientWidth * 0.8);
            sc.scrollBy({ left: (rtl ? -dir : dir) * step, behavior: scrollBehavior() });
        }

        paint();

        if (el.dataset.rvvBound) return;
        el.dataset.rvvBound = '1';

        el.addEventListener('click', e => {
            const nav = e.target.closest('.rvv-nav');
            if (nav && el.contains(nav)) {
                page(nav.classList.contains('rvv-nav-next') ? 1 : -1);
                return;
            }

            const btn = e.target.closest('.rvv-play');
            if (!btn || !el.contains(btn)) return;
            const card = btn.closest('.rvv-card');
            const id = card && card.getAttribute('data-video');
            if (!id || card.classList.contains('is-playing')) return;

            // First and only Wistia request for this card. `autoplay=1` is
            // honoured because the iframe is created inside a real click.
            const frame = document.createElement('iframe');
            frame.src = `https://fast.wistia.net/embed/iframe/${encodeURIComponent(id)}?autoPlay=1&playsinline=1`;
            frame.title = card.querySelector('.rvv-name')?.textContent || 'Ghawy member review';
            frame.allow = 'autoplay; fullscreen';
            frame.allowFullscreen = true;
            frame.loading = 'lazy';
            frame.className = 'rvv-iframe';
            card.classList.add('is-playing');
            card.querySelector('.rvv-frame').appendChild(frame);

            // Bring the card that just started playing fully into view, so a
            // click on a half-visible card does not leave it half-visible.
            card.scrollIntoView({ behavior: scrollBehavior(), block: 'nearest', inline: 'center' });
        });

        // Delegated to `el` so it survives every repaint of the scroller.
        el.addEventListener('scroll', syncNav, { capture: true, passive: true });
        window.addEventListener('resize', syncNav, { passive: true });

        document.addEventListener('languagechange', () => {
            if (!document.body.contains(el)) return;
            // Never repaint over a playing video — that would kill playback
            // mid-sentence just because somebody pressed the language button.
            if (el.querySelector('.rvv-card.is-playing')) {
                if (typeof window.applyLanguageTo === 'function') window.applyLanguageTo(el);
                return;
            }
            paint();
        });
    }

    // ─── Screenshot marquee ─────────────────────────────────────

    /**
     * Deal the screenshots across `rows` tracks, round-robin.
     *
     * Round-robin rather than slicing into thirds so the rows come out roughly
     * the same height: the shots run from one-liners to ten-line messages and
     * arrive in no particular order, so consecutive entries land on different
     * rows instead of stacking every tall one into the same track.
     */
    function dealRows(list, rows) {
        const out = Array.from({ length: rows }, () => []);
        list.forEach((file, i) => out[i % rows].push(file));
        return out.filter(r => r.length);
    }

    /**
     * One row. The images are emitted twice — the animation translates the
     * track by exactly -50%, so the second copy is what is on screen by the
     * time the first has scrolled past and the loop has no seam. The copy is
     * marked `.rvs-dup` so the reduced-motion rules can drop it and leave a
     * plain grid with no repeats.
     */
    function shotRowHTML(files, index) {
        const imgs = files.map(f => `
            <div class="rvs-card">
                <img src="${esc(SHOT_DIR + f)}" alt="" loading="lazy" decoding="async"${sizeAttrs(f)} />
            </div>`).join('');
        const dup = files.map(f => `
            <div class="rvs-card rvs-dup">
                <img src="${esc(SHOT_DIR + f)}" alt="" loading="lazy" decoding="async"${sizeAttrs(f)} />
            </div>`).join('');
        // even rows drift one way, odd rows the other
        const dir = index % 2 === 0 ? 'rvs-row--fwd' : 'rvs-row--rev';
        return `<div class="rvs-row ${dir}"><div class="rvs-track">${imgs}${dup}</div></div>`;
    }

    /**
     * Fill a container with the scrolling wall of screenshots.
     *
     * `aria-hidden` is deliberate — see the note at the top of the file. No
     * skeleton either: these are static files, not an API list, so there is no
     * wait to represent. Each <img> is lazy, so only the first screenful is
     * fetched even though the markup lists every row twice.
     */
    function renderScreenshots(el, opts) {
        if (!el) return;
        const o = opts || {};
        const files = publishable(o.files || SCREENSHOTS);
        if (!files.length) { el.innerHTML = ''; el.hidden = true; return; }
        el.hidden = false;
        el.className = 'rvs-wrap' + (o.modifier ? ' ' + o.modifier : '');
        el.setAttribute('aria-hidden', 'true');
        el.innerHTML = dealRows(files, o.rows || SHOT_ROWS).map(shotRowHTML).join('');
    }

    // ─── Screenshot grid (the /reviews page) ────────────────────
    //
    // The home page scrolls the screenshots past as a marquee — it is a
    // teaser, and motion is the point. /reviews is the page you land on to
    // actually READ them, so the same files are laid out as a still masonry
    // grid instead: nothing moves, nothing loops, and every shot is reachable.
    //
    // A CSS `columns` layout rather than a grid because these images are all
    // one width and wildly different heights (a one-line message next to a
    // ten-line one). Columns pack them with no gaps and no JS measuring.

    /**
     * Files the client has flagged as needing an edit never render.
     *
     * Today none are in the arrays and none are in the repo, so this filter
     * removes nothing — it is here so that adding one by mistake later cannot
     * put a half-cut sentence on a public page. The check is on the name, so
     * it works no matter which array the file is dropped into.
     */
    function publishable(files) {
        return (files || []).filter(f => !/NEEDS[-_]EDIT/i.test(f));
    }

    /** `width="900" height="628"` for a screenshot, or '' if we have no size. */
    function sizeAttrs(file) {
        const s = SHOT_SIZES[file];
        return s ? ` width="${s[0]}" height="${s[1]}"` : '';
    }

    function shotCellHTML(file, hidden) {
        const src = SHOT_DIR + file;
        const open = { ar: 'كبّر الصورة', en: 'Enlarge image' };
        // A button, not a bare <img>: enlarging is an action, and it has to be
        // reachable by keyboard. The alt stays empty for the reason at the top
        // of this file — the words are someone else's and are in the pixels.
        //
        // `hidden` is the not-yet-revealed tail. The images are lazy, so a
        // hidden cell costs nothing until "show more" is pressed.
        return `
        <button type="button" class="rvg-cell" data-full="${esc(src)}"${hidden ? ' hidden' : ''}
                aria-label="${esc(L(open))}" ${i18nAria(open)}>
            <img src="${esc(src)}" alt="" loading="lazy" decoding="async"${sizeAttrs(file)} />
        </button>`;
    }

    /**
     * Fill a container with the still grid, plus the shared lightbox.
     *
     * `empty` is the message shown when the array is empty — every list on
     * this page has one, because "no screenshots" and "screenshots failed to
     * render" must not look the same.
     */
    function renderShotGrid(el, opts) {
        if (!el) return;
        const o = opts || {};
        const files = publishable(o.files || SCREENSHOTS);

        // How many to show before the "عرض المزيد" button. There are 44 chat
        // screenshots; dropping all of them on the page at once made /reviews
        // about four screens of nothing but screenshots, and the written
        // reviews above them stopped being the point of the page. `0` means
        // no limit — the ratings section, which is six images, uses that.
        const initial = o.initial || 0;
        // Kept outside paint() so a language switch does not silently collapse
        // a grid the visitor had already expanded.
        let expanded = false;

        const paint = () => {
            el.className = 'rvg-grid' + (o.modifier ? ' ' + o.modifier : '');
            if (!files.length) {
                el.innerHTML = emptyHTML(o.empty || { ar: 'مفيش صور هنا دلوقتي.', en: 'No screenshots here yet.' }, 'image');
                if (typeof window.applyLanguageTo === 'function') window.applyLanguageTo(el);
                return;
            }
            const cut = (initial && !expanded) ? initial : files.length;
            el.innerHTML = files.map((f, i) => shotCellHTML(f, i >= cut)).join('');
            if (typeof window.applyLanguageTo === 'function') window.applyLanguageTo(el);
            paintMoreBtn(files.length - cut);
        };

        /**
         * The "show more" button, in its own element after the grid.
         *
         * Outside `el` because `el` is a CSS `columns` container — a button
         * inside it would be dealt into a column like another screenshot
         * instead of sitting centred under the whole block.
         */
        function paintMoreBtn(remaining) {
            let bar = el.nextElementSibling;
            if (!bar || !bar.classList.contains('rvg-more-bar')) {
                bar = document.createElement('div');
                bar.className = 'rvg-more-bar';
                el.insertAdjacentElement('afterend', bar);
                bar.addEventListener('click', e => {
                    if (!e.target.closest('.rvg-more-btn')) return;
                    expanded = true;
                    paint();
                });
            }
            if (remaining <= 0) { bar.innerHTML = ''; bar.hidden = true; return; }
            bar.hidden = false;
            const label = {
                ar: `عرض ${remaining} كمان`,
                en: `Show ${remaining} more`,
            };
            bar.innerHTML = `
            <button type="button" class="rvg-more-btn" ${i18nAttrs(label)}>${esc(L(label))}</button>`;
            if (typeof window.applyLanguageTo === 'function') window.applyLanguageTo(bar);
        }

        paint();

        if (el.dataset.rvgBound) return;
        el.dataset.rvgBound = '1';
        el.addEventListener('click', e => {
            const cell = e.target.closest('.rvg-cell');
            if (cell && el.contains(cell)) openLightbox(cell.getAttribute('data-full'), cell);
        });
        document.addEventListener('languagechange', () => {
            if (document.body.contains(el)) paint();
        });
    }

    // ─── Lightbox ───────────────────────────────────────────────
    //
    // These screenshots are TEXT. At grid width a long message is legible but
    // tight, and on a phone it is not legible at all, so there has to be a way
    // to see one full size. One overlay is built lazily and reused by every
    // grid on the page.
    //
    // No library, and no `window.alert`-style browser chrome: Escape closes,
    // clicking the backdrop closes, focus moves into the overlay and returns
    // to the exact thumbnail that opened it.

    let lightbox = null;
    let lastFocus = null;

    function buildLightbox() {
        const close = { ar: 'إغلاق', en: 'Close' };
        const box = document.createElement('div');
        box.className = 'rvlb';
        box.hidden = true;
        box.setAttribute('role', 'dialog');
        box.setAttribute('aria-modal', 'true');
        box.innerHTML = `
        <button type="button" class="rvlb-close" aria-label="${esc(L(close))}" ${i18nAttrs(close)}>
            <i class="fa-solid fa-xmark" aria-hidden="true"></i>
        </button>
        <img class="rvlb-img" src="" alt="" />`;
        document.body.appendChild(box);

        box.addEventListener('click', e => {
            // Backdrop or the close button — but never the image itself.
            if (e.target.closest('.rvlb-img')) return;
            closeLightbox();
        });
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape' && !box.hidden) closeLightbox();
        });
        return box;
    }

    function openLightbox(src, opener) {
        if (!src) return;
        lightbox = lightbox || buildLightbox();
        lastFocus = opener || null;
        lightbox.querySelector('.rvlb-img').src = src;
        lightbox.hidden = false;
        document.body.classList.add('rvlb-open');
        lightbox.querySelector('.rvlb-close').focus();
    }

    function closeLightbox() {
        if (!lightbox || lightbox.hidden) return;
        lightbox.hidden = true;
        // Drop the src so a closed overlay is not holding a decoded bitmap.
        lightbox.querySelector('.rvlb-img').src = '';
        document.body.classList.remove('rvlb-open');
        if (lastFocus && document.body.contains(lastFocus)) lastFocus.focus();
        lastFocus = null;
    }

    // ─── Auto-init ──────────────────────────────────────────────
    // A page asks for a block by dropping its container id into the markup and
    // loading this file. Nothing is wired up by hand.
    //
    // The home page drifts its screenshots past as a teaser:
    //   #reviewsMarquee  — the wall of chat screenshots
    //   #ratingsMarquee  — the wall of course rating lists
    //
    // /reviews is the page you land on to actually look at them, so it uses
    // the still ids instead — #reviewsVideos, #shotsGrid, #ratingsGrid. The
    // marquee and the grid are two presentations of ONE set of files, never
    // two lists to keep in step.
    function autoInit() {
        renderVideos(document.getElementById('reviewsVideos'));
        renderShotGrid(document.getElementById('shotsGrid'), {
            // 12 fills roughly one screen of the masonry at desktop width;
            // the other 32 are one button away.
            initial: 12,
            empty: { ar: 'مفيش رسايل معروضة دلوقتي.', en: 'No messages to show right now.' },
        });
        renderShotGrid(document.getElementById('ratingsGrid'), {
            files: RATINGS, modifier: 'rvg-grid--tall',
            empty: { ar: 'مفيش تقييمات معروضة دلوقتي.', en: 'No ratings to show right now.' },
        });
        autoInitHome();
    }

    function autoInitHome() {
        renderScreenshots(document.getElementById('reviewsMarquee'));
        // One row, not three: the rating lists are tall columns, so three rows
        // of them would be a screen and a half of nothing else. Six shots at
        // ~300px still overrun any viewport, so the -50% loop stays seamless.
        renderScreenshots(document.getElementById('ratingsMarquee'), {
            files: RATINGS, rows: 1, modifier: 'rvs-wrap--tall',
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    window.GhawyReviews = {
        REVIEWS, SCREENSHOTS, RATINGS, SHOT_DIR, SHOT_SIZES,
        L, esc, i18nAttrs, publishable,
        emptyHTML, renderScreenshots,
        videoCardHTML, renderVideos,
        shotCellHTML, renderShotGrid, openLightbox, closeLightbox, i18nAria,
    };
})();
