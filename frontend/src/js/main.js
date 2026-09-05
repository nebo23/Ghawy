
/* ═══════════════════════════════════════════
   Ghawy — Main JS (Redesigned)
═══════════════════════════════════════════ */

// === GTM ===
(function (w, d, s, l, i) {
    w[l] = w[l] || [];
    w[l].push({ "gtm.start": new Date().getTime(), event: "gtm.js" });
    var f = d.getElementsByTagName(s)[0],
        j = d.createElement(s),
        dl = l != "dataLayer" ? "&l=" + l : "";
    j.async = true;
    j.src = "https://www.googletagmanager.com/gtm.js?id=" + i + dl;
    f.parentNode.insertBefore(j, f);
})(window, document, "script", "dataLayer", "GTM-WQXDPWM2");

// === VSL Video Player JS ===
(function () {
    const video = document.getElementById('mainNativeVsl');
    const overlay = document.getElementById('vslOverlay');
    const unmuteBtn = document.getElementById('customUnmuteBtn');
    const progress = document.getElementById('vslProgress');
    const playBtn = document.getElementById('vslPlayBtn');
    const playIcon = document.getElementById('vslPlayIcon');
    const skipBtn = document.getElementById('vslSkipBtn');
    const loopBtn = document.getElementById('vslLoopBtn');
    const pipBtn = document.getElementById('vslPipBtn');
    const muteBtn = document.getElementById('vslMuteBtn');
    const volIcon = document.getElementById('vslVolIcon');
    const fullBtn = document.getElementById('vslFullBtn');
    const timeEl = document.getElementById('vslTime');
    const seekFill = document.getElementById('vslSeekFill');
    const seekWrap = document.querySelector('.vsl-seek-bar-wrap');

    if (!video) return;

    // Format seconds
    function fmt(s) {
        const m = Math.floor(s / 60);
        const sec = Math.floor(s % 60).toString().padStart(2, '0');
        return `${m}:${sec}`;
    }

    // Hide overlay when playing
    video.addEventListener('playing', () => {
        if (overlay) { overlay.style.opacity = '0'; setTimeout(() => overlay.style.display = 'none', 500); }
    });

    // Update progress + time
    video.addEventListener('timeupdate', () => {
        if (!video.duration) return;
        const pct = (video.currentTime / video.duration) * 100;
        if (progress) progress.style.width = pct + '%';
        if (seekFill) seekFill.style.width = pct + '%';
        if (timeEl) timeEl.textContent = `${fmt(video.currentTime)} / ${fmt(video.duration)}`;
    });

    // Play / Pause toggle button
    if (playBtn) {
        playBtn.addEventListener('click', () => {
            video.paused ? video.play() : video.pause();
        });
        video.addEventListener('play', () => { if (playIcon) { playIcon.classList.remove('fa-play'); playIcon.classList.add('fa-pause'); } });
        video.addEventListener('pause', () => { if (playIcon) { playIcon.classList.remove('fa-pause'); playIcon.classList.add('fa-play'); } });
    }

    // Unmute button
    if (unmuteBtn) {
        unmuteBtn.addEventListener('click', () => {
            video.muted = false;
            video.volume = 1;
            video.currentTime = 0;
            video.play();
            unmuteBtn.classList.add('hide');
            setTimeout(() => unmuteBtn.style.display = 'none', 300);
        });
    }

    // Skip 10s
    if (skipBtn) skipBtn.addEventListener('click', () => { video.currentTime = Math.min(video.duration, video.currentTime + 10); });

    // Loop toggle
    if (loopBtn) loopBtn.addEventListener('click', () => {
        video.loop = !video.loop;
        loopBtn.style.color = video.loop ? 'var(--green, #c1ff11)' : '#fff';
    });

    // Mute toggle
    if (muteBtn) muteBtn.addEventListener('click', () => {
        video.muted = !video.muted;
        if (volIcon) {
            volIcon.className = video.muted ? 'fa-solid fa-volume-xmark' : 'fa-solid fa-volume-high';
        }
    });

    // Fullscreen
    if (fullBtn) fullBtn.addEventListener('click', () => {
        const box = video.closest('.vsl-player-box');
        if (document.fullscreenElement) { document.exitFullscreen(); }
        else { (box || video).requestFullscreen?.(); }
    });

    // PiP
    if (pipBtn) pipBtn.addEventListener('click', () => {
        if (document.pictureInPictureElement) { document.exitPictureInPicture(); }
        else { video.requestPictureInPicture?.(); }
    });

    // (The "Watch Intro" button and its handler are gone — the hero's second
    //  CTA is "Browse Courses" and links straight to /courses.)

    // Seek bar click.
    // This maps left→right, which matches `.vsl-seek-fill` growing with
    // `width`. Both are only ever consistent because `.vsl-controls` is
    // pinned to `direction: ltr` in main.css — do not remove that rule, or
    // clicking in Arabic will seek to the mirrored point again.
    if (seekWrap) {
        seekWrap.addEventListener('click', (e) => {
            if (!video.duration) return;
            const rect = seekWrap.getBoundingClientRect();
            const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
            video.currentTime = ratio * video.duration;
        });
    }

    // Autoplay attempt
    video.play().catch(() => { });
})();

// ═══════════════════════════════════════════
//   Live-purchase widget — REMOVED (Phase 4)
// ═══════════════════════════════════════════
// This block polled a third-party Supabase table from every landing-page
// visitor's browser. It is gone because none of it reached the page:
//
//   .progress-bar-fill  — no such element, and it is this file's own guard, so
//                         checkPurchases() and its 5s interval never started
//   #livePurchaseText   — no such element, so updateLiveText() returned early
//                         every second while fetchLastPurchase() kept polling
//   #initialBar         — no such element, so the cached-bar block did nothing
//   #initialSlotsFill   — no such element, same
//
// Verified absent from index.html (the only page that loads main.js), from the
// live page served in production, and from every commit in this repo's history:
// `git log -S` finds no commit that ever added that markup anywhere.
//
// What it actually cost: fetchLastPurchase was the one unguarded caller, so
// every landing-page visitor made 6 requests/minute to a third party for a row
// that fed nothing, plus a 1-second timer that did nothing.
//
// It could not have shown anything useful even with the markup present: the
// newest row in that table is 2026-07-01, so the "someone just bought" popup
// could never fire (the id never changes) and the live text would have read
// "اشترى منذ ٦٣ يوم".
//
// If live social proof is wanted back it needs three things this never had:
// the markup, a data source that is still being written to, and an interval
// derived from the real purchase rate (median gap in that table: ~2 hours) —
// not a 5-second poll. See docs/PHASE-4-REPORT.md.

// ═══════════════════════════════════════════
//   Courses Carousel
// ═══════════════════════════════════════════
(function () {
    window.initCoursesCarousel = function () {
        const track = document.getElementById("coursesCarouselTrack");
        const nextBtn = document.getElementById("coursesNextBtn");
        const prevBtn = document.getElementById("coursesPrevBtn");
        if (!track || !nextBtn || !prevBtn) return;

        nextBtn.onclick = () => {
            const card = track.querySelector(".course-carousel-card");
            if (!card) return;
            track.scrollBy({ left: card.offsetWidth + 18, behavior: "smooth" });
        };
        prevBtn.onclick = () => {
            const card = track.querySelector(".course-carousel-card");
            if (!card) return;
            track.scrollBy({ left: -(card.offsetWidth + 18), behavior: "smooth" });
        };
    };

    // Counters that are still waiting on GET /stats/public carry
    // [data-stat-pending] and are skipped here; loadPublicStats() clears the
    // attribute once the real target is in place and calls this again. That
    // ordering matters — without it a counter would animate up to the
    // placeholder number and then jump when the API answered.
    // [data-counter-bound] stops the second call re-observing the first batch.
    window.initCounterUp = function () {
        const counters = document.querySelectorAll(
            '.counter-value:not([data-stat-pending]):not([data-counter-bound])'
        );
        if (!counters.length) return;

        const animateCounter = (counter) => {
            const target = +counter.getAttribute('data-target');
            const isFloat = counter.getAttribute('data-decimals') === '1';
            const duration = 2000;
            const startTime = performance.now();

            function step(currentTime) {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                const current = target * eased;

                if (progress < 1) {
                    counter.innerText = isFloat ? current.toFixed(1) : Math.ceil(current);
                    requestAnimationFrame(step);
                } else {
                    counter.innerText = isFloat ? target.toFixed(1) : target;
                }
            }
            requestAnimationFrame(step);
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animateCounter(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });

        counters.forEach(counter => {
            counter.setAttribute('data-counter-bound', '1');
            observer.observe(counter);
        });
    };

    // ── Live member count ────────────────────────────────────────
    // Fills every [data-stat="members"] counter on the page from the public
    // stats endpoint, so the hero card and the stats bar can never disagree.
    // The endpoint is cached server-side for 5 minutes; this is one request
    // per page load.
    const MEMBERS_FALLBACK = 1000;   // shown if the API is slow, down or new
    const MEMBERS_TIMEOUT_MS = 4000;

    window.loadPublicStats = async function () {
        const targets = document.querySelectorAll('[data-stat="members"]');
        if (!targets.length) return;

        let total = null;
        try {
            const base = (typeof API !== 'undefined' && API) ? API : '/api';
            // AbortController rather than a bare fetch: a hanging request must
            // not leave the skeleton shimmering forever.
            const ctrl = new AbortController();
            const timer = setTimeout(() => ctrl.abort(), MEMBERS_TIMEOUT_MS);
            try {
                const res = await fetch(`${base}/stats/public`, { signal: ctrl.signal });
                if (res.ok) {
                    const data = await res.json();
                    const n = Number(data && data.total_members);
                    if (Number.isFinite(n) && n > 0) total = Math.floor(n);
                }
            } finally {
                clearTimeout(timer);
            }
        } catch (e) {
            // Deliberately silent. The endpoint is decorative — a stat must
            // never put an error in a visitor's console.
        }

        const value = total !== null ? total : MEMBERS_FALLBACK;
        targets.forEach(el => {
            el.setAttribute('data-target', String(value));
            el.removeAttribute('data-stat-pending');   // reveals it, hides the skeleton
        });

        // Now — and only now — let the counter animation observe them.
        if (window.initCounterUp) window.initCounterUp();
    };
})();

// ═══════════════════════════════════════════
//   DOMContentLoaded — Init All Components
// ═══════════════════════════════════════════
// ═══════════════════════════════════════════
//   Final CTA headline
// ═══════════════════════════════════════════
/**
 * "انضم الآن لأكثر من N عضو وابدأ رحلتك في الذكاء الاصطناعي مع أكثر من M كورس"
 *
 * Neither number is written into the page. M is GhawyCatalog.totals().courses
 * — the released courses, the same figure the totals bar shows — so it moves
 * the day a course actually ships. N is a `.counter-value[data-stat=
 * "members"]` span exactly like the hero's — which means loadPublicStats()
 * picks it up in the same pass and fills both from ONE call to /stats/public.
 * That is the point: the previous copy said "+350 مشترك" a screen below a hero
 * already showing the live figure, and the two disagreed.
 *
 * Built here rather than written in the markup because the sentence wraps
 * around the count, so the Arabic and the English need different word order
 * around it and neither can be produced by swapping one <span>.
 */
window.renderFinalCtaTitle = function () {
    const el = document.getElementById('finalCtaTitle');
    if (!el) return;

    // Courses a subscriber can actually open — NOT `COURSES.length`.
    //
    // The raw array now also holds announced-but-unreleased courses, so the
    // length was 9 while the totals bar two sections up said 7. `totals()`
    // counts only what has a runtime, which is the same number the rest of
    // the site quotes.
    const courses = (window.GhawyCatalog && window.GhawyCatalog.totals)
        ? window.GhawyCatalog.totals().courses : 0;
    if (!courses) return;   // no invented number if catalog.js didn't load

    // From i18n.js, not localStorage — this runs on `languagechange`, and
    // storage is not the source of truth while that event is in flight.
    const lang = (typeof window.currentLang === 'function') ? window.currentLang() : 'ar';
    // data-stat-pending keeps the skeleton up until the real count lands; the
    // data-target here is only what it counts to if the endpoint never answers.
    const members = '<span class="counter-value stat-members" data-stat="members"'
        + ' data-stat-pending="1" data-target="1000">0</span>'
        + '<span class="stat-plus">+</span>'
        + '<span class="stat-skeleton" aria-hidden="true"></span>';

    el.innerHTML = lang === 'en'
        ? `Join more than ${members} members and start your journey into AI with more than ${courses} courses`
        : `انضم الآن لأكثر من ${members} عضو وابدأ رحلتك في الذكاء الاصطناعي مع أكثر من ${courses} كورس`;
};

document.addEventListener('languagechange', () => {
    if (!window.renderFinalCtaTitle) return;
    window.renderFinalCtaTitle();
    // The rebuilt span is a fresh node with no data-counter-bound, so it needs
    // the number put back and the observer re-attached.
    if (window.loadPublicStats) window.loadPublicStats();
});

document.addEventListener("DOMContentLoaded", () => {
    if (window.initCoursesCarousel) window.initCoursesCarousel();
    // Before loadPublicStats: the headline creates one of the member counters
    // it fills, so it has to exist by the time that query runs.
    if (window.renderFinalCtaTitle) window.renderFinalCtaTitle();
    // Static counters start immediately; the member counters are held back
    // until loadPublicStats() has a real number for them.
    if (window.initCounterUp) window.initCounterUp();
    if (window.loadPublicStats) window.loadPublicStats();
});

// ═══════════════════════════════════════════
//   FAQ Accordion
// ═══════════════════════════════════════════
// Moved to src/js/faq.js along with the questions themselves. This ran once at
// load and bound one listener per .faq-q, which no longer works now that the
// rows are rendered — and a second binding here would have toggled every row
// twice, cancelling itself out.

// ═══════════════════════════════════════════
//   Sticky CTA Bar
// ═══════════════════════════════════════════
const stickyBar = document.getElementById("stickyCta");
if (stickyBar) {
    window.addEventListener("scroll", () => {
        if (window.scrollY > 480 && window.scrollY < 7200) {
            stickyBar.classList.add("show");
        } else {
            stickyBar.classList.remove("show");
        }
    }, { passive: true });
}

// ═══════════════════════════════════════════
//   Intersection Observer — Fade-in
// ═══════════════════════════════════════════
const fadeObserver = new IntersectionObserver(
    (entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = "1";
                entry.target.style.transform = "translateY(0)";
                fadeObserver.unobserve(entry.target);
            }
        });
    },
    { threshold: 0.12 },
);

document.querySelectorAll(".chapter-card, .screenshot-card")
    .forEach((el, i) => {
        el.style.opacity = "0";
        el.style.transform = "translateY(24px)";
        el.style.transition = `opacity 0.55s ease ${i * 0.07}s, transform 0.55s ease ${i * 0.07}s`;
        fadeObserver.observe(el);
    });

// ═══════════════════════════════════════════
//   Sidebar toggleModule
// ═══════════════════════════════════════════
function toggleModule(header) {
    const module = header.parentElement;
    module.classList.toggle("active-chapter");
}

// ═══════════════════════════════════════════
//   Copy to Clipboard
// ═══════════════════════════════════════════
function copyText(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
        const orig = btn.textContent;
        btn.textContent = "تم النسخ";
        btn.style.background = "rgba(16,185,129,0.15)";
        btn.style.borderColor = "rgba(16,185,129,0.4)";
        btn.style.color = "#10b981";
        setTimeout(() => {
            btn.textContent = orig;
            btn.style.background = "";
            btn.style.borderColor = "";
            btn.style.color = "";
        }, 2000);
    });
}

// ═══════════════════════════════════════════
//   Auth Utilities
// ═══════════════════════════════════════════
// Auto-detect API base: use /api prefix in production (via Nginx), direct port in local dev
const API = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
    ? 'http://127.0.0.1:8000'
    : '/api';

function showAlert(msg, type) {
    const el = document.getElementById('alert');
    if (!el) return;
    el.textContent = msg;
    el.className = `alert ${type}`;
}

function setLoading(btnId, loading) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    btn.disabled = loading;
    btn.classList.toggle('loading', loading);
}

// Same function utils.js exposes, repeated here for the same reason showAlert
// and setLoading already are: main.js and utils.js can never be loaded on the
// same page (they both declare a top-level `const API`), so the landing page
// only gets what main.js defines. The checkout calls showToast on a failed
// payment and was hitting a ReferenceError inside its own catch block.
function showToast(message, type) {
    const toast = document.createElement('div');
    toast.className = `toast ${type || 'success'}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function getToken() { return localStorage.getItem('token'); }
function saveToken(token) { localStorage.setItem('token', token); }
function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user'); window.location.href = '/login';
}

// ═══════════════════════════════════════════
//   Course catalog section
// ═══════════════════════════════════════════
// The Swiper carousel that used to live here is gone: there are only six
// courses, and a grid shows all of them at once instead of hiding two thirds
// behind arrows. Everything the section renders now comes from
// src/js/catalog.js — including the totals bar, which is summed from the
// catalog rather than being two numbers typed into the HTML.
document.addEventListener('DOMContentLoaded', () => {

    // 1. The course grid and its totals bar render themselves — catalog.js
    //    picks up #coursesGrid / #coursesTotals on any page that has them,
    //    so the home page and /courses share one code path.

    // 2. Logo Shine Effect
    const navLogo = document.querySelector('.nav-logo');
    if (navLogo) {
        navLogo.addEventListener('click', () => {
            navLogo.classList.remove('logo-shine');
            void navLogo.offsetWidth;
            navLogo.classList.add('logo-shine');
            setTimeout(() => navLogo.classList.remove('logo-shine'), 700);
        });
    }

});
// === Logo Click Shine Effect ===
const navLogo = document.getElementById('navLogo');
if (navLogo) {
    navLogo.addEventListener('click', () => {
        navLogo.classList.remove('logo-shine');
        void navLogo.offsetWidth; // trigger reflow
        navLogo.classList.add('logo-shine');
    });
}


// ═══════════════════════════════════════════
//   Geolocation Auto-fill
// ═══════════════════════════════════════════
const arabCountries = {
    "مصر": ["القاهرة", "الإسكندرية", "الجيزة", "القليوبية", "بورسعيد", "السويس", "الإسماعيلية", "الشرقية", "الدقهلية", "الغربية", "المنوفية", "كفر الشيخ", "البحيرة", "دمياط", "البحر الأحمر", "الوادي الجديد", "مطروح", "شمال سيناء", "جنوب سيناء", "الفيوم", "بني سويف", "المنيا", "أسيوط", "سوهاج", "قنا", "الأقصر", "أسوان"],
    "السعودية": ["الرياض", "مكة المكرمة", "المدينة المنورة", "القصيم", "الشرقية", "عسير", "تبوك", "حائل", "الحدود الشمالية", "جازان", "نجران", "الباحة", "الجوف"],
    "الإمارات": ["أبوظبي", "دبي", "الشارقة", "عجمان", "أم القيوين", "رأس الخيمة", "الفجيرة"],
    "الكويت": ["العاصمة", "حولي", "الفروانية", "الأحمدي", "الجهراء", "مبارك الكبير"],
    "قطر": ["الدوحة", "الريان", "أم صلال", "الخور", "الوكرة", "الشمال", "الضعاين", "الشحانية"],
    "البحرين": ["العاصمة", "المحرق", "الشمالية", "الجنوبية"],
    "عمان": ["مسقط", "ظفار", "مسندم", "البريمي", "الداخلية", "شمال الباطنة", "جنوب الباطنة", "شمال الشرقية", "جنوب الشرقية", "الظاهرة", "الوسطى"],
    "الأردن": ["عمان", "إربد", "الزرقاء", "المفرق", "عجلون", "جرش", "مادبا", "البلقاء", "الكرك", "الطفيلة", "معان", "العقبة"],
    "فلسطين": ["القدس", "غزة", "رام الله", "الخليل", "نابلس", "جنين", "طولكرم", "بيت لحم", "قلقيلية", "أريحا", "طوباس", "سلفيت"],
    "لبنان": ["بيروت", "جبل لبنان", "الشمال", "الجنوب", "البقاع", "النبطية", "بعلبك-الهرمل", "عكار"],
    "سوريا": ["دمشق", "حلب", "حمص", "حماة", "اللاذقية", "دير الزور", "السويداء", "الرقة", "درعا", "إدلب", "طرطوس", "الحسكة", "القنيطرة"],
    "العراق": ["بغداد", "البصرة", "نينوى", "أربيل", "النجف", "ذي قار", "كركوك", "الأنبار", "ديالى", "المثنى", "القادسية", "ميسان", "واسط", "صلاح الدين", "دهوك", "السليمانية", "بابل", "كربلاء"],
    "اليمن": ["صنعاء", "عدن", "تعز", "الحديدة", "إب", "حضرموت", "شبوة", "مأرب", "صعدة", "حجة", "أبين", "لحج", "البيضاء", "المهرة", "الجوف", "عمران", "الضالع", "ريمة", "سقطرى"],
    "السودان": ["الخرطوم", "الجزيرة", "البحر الأحمر", "كسلا", "القضارف", "سنار", "النيل الأبيض", "النيل الأزرق", "الشمالية", "نهر النيل", "شمال كردفان", "جنوب كردفان", "غرب كردفان", "شمال دارفور", "جنوب دارفور", "غرب دارفور", "شرق دارفور", "وسط دارفور"],
    "ليبيا": ["طرابلس", "بنغازي", "مصراتة", "الزاوية", "سبها", "سرت", "البيضاء", "طبرق", "الخمس", "زليتن", "درنة"],
    "تونس": ["تونس", "صفاقس", "سوسة", "بنزرت", "نابل", "القيروان", "قابس", "المنستير", "أريانة", "المهدية", "الكاف", "جندوبة", "سيدي بوزيد", "توزر", "تطاوين"],
    "الجزائر": ["الجزائر", "وهران", "قسنطينة", "عنابة", "باتنة", "البليدة", "سطيف", "سيدي بلعباس", "بسكرة", "تلمسان"],
    "المغرب": ["الدار البيضاء", "الرباط", "فاس", "مراكش", "طنجة", "أكادير", "مكناس", "وجدة", "القنيطرة", "تطوان"],
    "موريتانيا": ["نواكشوط", "نواذيبو", "كيهيدي", "كيفه", "روصو", "أطار"],
    "الصومال": ["مقديشو", "هرجيسا", "بربرة", "بوساسو", "جروي"],
    "جيبوتي": ["جيبوتي", "علي صبيح", "تاجورة", "أوبوك", "دِخيل", "أرتا"],
    "جزر القمر": ["موروني", "موتسامودو", "فومبوني"]
};

const countryMap = {
    'Egypt': 'مصر', 'Saudi Arabia': 'السعودية', 'United Arab Emirates': 'الإمارات',
    'Kuwait': 'الكويت', 'Qatar': 'قطر', 'Bahrain': 'البحرين', 'Oman': 'عمان',
    'Jordan': 'الأردن', 'Palestine': 'فلسطين', 'Lebanon': 'لبنان', 'Syria': 'سوريا',
    'Iraq': 'العراق', 'Yemen': 'اليمن', 'Sudan': 'السودان', 'Libya': 'ليبيا',
    'Tunisia': 'تونس', 'Algeria': 'الجزائر', 'Morocco': 'المغرب', 'Mauritania': 'موريتانيا',
    'Somalia': 'الصومال', 'Djibouti': 'جيبوتي', 'Comoros': 'جزر القمر'
};

const govMap = {
    'Cairo': 'القاهرة', 'Cairo Governorate': 'القاهرة',
    'Alexandria': 'الإسكندرية', 'Alexandria Governorate': 'الإسكندرية',
    'Giza': 'الجيزة', 'Giza Governorate': 'الجيزة',
    'Dakahlia': 'الدقهلية', 'Dakahlia Governorate': 'الدقهلية', 'Ad Daqahliyah': 'الدقهلية', 'Daqahlia': 'الدقهلية', 'Mansoura': 'الدقهلية', 'El Mansoura': 'الدقهلية', 'Mansourah': 'الدقهلية',
    'Red Sea': 'البحر الأحمر', 'Red Sea Governorate': 'البحر الأحمر',
    'Beheira': 'البحيرة', 'Beheira Governorate': 'البحيرة',
    'Faiyum': 'الفيوم', 'Faiyum Governorate': 'الفيوم',
    'Gharbia': 'الغربية', 'Gharbia Governorate': 'الغربية',
    'Suez': 'السويس', 'Suez Governorate': 'السويس',
    'Port Said': 'بورسعيد', 'Port Said Governorate': 'بورسعيد',
    'Ismailia': 'الإسماعيلية', 'Ismailia Governorate': 'الإسماعيلية',
    'Sharqia': 'الشرقية', 'Sharqia Governorate': 'الشرقية',
    'Monufia': 'المنوفية', 'Menofia Governorate': 'المنوفية',
    'Kafr El Sheikh': 'كفر الشيخ', 'Kafr El-Sheikh Governorate': 'كفر الشيخ',
    'Damietta': 'دمياط', 'Damietta Governorate': 'دمياط',
    'New Valley': 'الوادي الجديد', 'New Valley Governorate': 'الوادي الجديد',
    'Matrouh': 'مطروح', 'Matrouh Governorate': 'مطروح',
    'Beni Suef': 'بني سويف', 'Beni Suef Governorate': 'بني سويف',
    'Minya': 'المنيا', 'Minya Governorate': 'المنيا',
    'Asyut': 'أسيوط', 'Asiut Governorate': 'أسيوط',
    'Sohag': 'سوهاج', 'Sohag Governorate': 'سوهاج',
    'Qena': 'قنا', 'Qena Governorate': 'قنا',
    'Luxor': 'الأقصر', 'Luxor Governorate': 'الأقصر',
    'Aswan': 'أسوان', 'Aswan Governorate': 'أسوان',
    'North Sinai': 'شمال سيناء', 'North Sinai Governorate': 'شمال سيناء',
    'South Sinai': 'جنوب سيناء', 'South Sinai Governorate': 'جنوب سيناء',
    'Qalyubia': 'القليوبية', 'Qalyubia Governorate': 'القليوبية'
};

function populateCountries() {
    const countrySelect = document.getElementById('registerModalCountry');
    if (!countrySelect) return;

    let html = '<option value="" disabled selected>اختر دولتك</option>';
    for (const c in arabCountries) {
        html += `<option value="${c}">${c}</option>`;
    }
    countrySelect.innerHTML = html;
}

window.populateGovernorates = function (countryName) {
    const govSelect = document.getElementById('registerModalGov');
    if (!govSelect) return;

    let html = '<option value="" disabled selected>اختر محافظتك</option>';
    const govs = arabCountries[countryName] || [];
    govs.forEach(g => {
        html += `<option value="${g}">${g}</option>`;
    });
    govSelect.innerHTML = html;
};

window.updateWelcomeMessage = function () {
    const statusDiv = document.getElementById('registerModalStatus');
    const countrySelect = document.getElementById('registerModalCountry');
    const govSelect = document.getElementById('registerModalGov');
    if (!statusDiv || !countrySelect) return;

    const selectedCountry = countrySelect.value;
    const selectedGov = govSelect ? govSelect.value : '';

    let locationText = selectedGov ? selectedGov : selectedCountry;
    if (locationText) {
        statusDiv.innerHTML = `<span style="color: var(--gold, #c1ff11); font-weight: bold;">أهلاً بك يا غاوي! منورنا من ${locationText}.</span>`;
        statusDiv.classList.remove('error');
    }
};

// The currency rewrite that lived here is gone. It swapped a table of hard-
// coded EGP amounts for dollar ones when the visitor was placed outside
// Egypt, and every element it looked for (.offer-value, .strike, .price-big,
// #priceAmount, #priceNote) had already been removed from the pages. The
// plans now render from src/js/pricing.js in Egyptian pounds for everyone.

window.handleCountryChange = function (country) {
    populateGovernorates(country);
    if (window.updateWelcomeMessage) window.updateWelcomeMessage();
    // Picking a country no longer changes any price: everyone is quoted in
    // Egyptian pounds.
};

async function getGeoLocation() {
    const statusDivs = [document.getElementById('registerModalStatus'), document.getElementById('geoStatus')];

    // Country and Governorate Inputs (covers both index.html and register.html)
    const countryEls = [document.getElementById('registerModalCountry'), document.getElementById('country')];
    const govEls = [document.getElementById('registerModalGov'), document.getElementById('governorate')];

    // Dial Code Elements
    const flagEls = [document.getElementById('registerModalFlag'), document.getElementById('flagSpan')];
    const dialTextEls = [document.getElementById('registerModalDialText'), document.getElementById('dialCodeText')];
    const dialInputEls = [document.getElementById('registerModalDialCode'), document.getElementById('dialCode')];

    // Initialize dropdowns if they are SELECT elements
    countryEls.forEach(el => { if (el && el.tagName === 'SELECT') populateCountries(); });

    statusDivs.forEach(div => { if (div) div.style.display = 'block'; });

    const applyValues = (country, gov, dial, flag, arabicCountryName) => {
        countryEls.forEach(el => {
            if (!el) return;
            if (el.tagName === 'SELECT') {
                for (let i = 0; i < el.options.length; i++) {
                    if (el.options[i].value === arabicCountryName) {
                        el.selectedIndex = i; break;
                    }
                }
                populateGovernorates(arabicCountryName);
            } else {
                el.value = country;
            }
        });

        govEls.forEach(el => {
            if (!el) return;
            if (el.tagName === 'SELECT') {
                for (let i = 0; i < el.options.length; i++) {
                    if (el.options[i].value === gov) {
                        el.selectedIndex = i; break;
                    }
                }
            } else {
                el.value = gov;
            }
        });

        flagEls.forEach(el => { if (el) el.innerText = flag; });
        dialTextEls.forEach(el => { if (el) el.innerText = dial; });
        dialInputEls.forEach(el => { if (el) el.value = dial; });

        // Special handling for the register.js dialCodeValue variable
        if (typeof window !== 'undefined' && 'dialCodeValue' in window) {
            window.dialCodeValue = dial;
        }

        if (window.updateWelcomeMessage) window.updateWelcomeMessage();
    };

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3000);
        const response = await fetch('https://ipapi.co/json/', { signal: controller.signal });
        clearTimeout(timeoutId);
        const data = await response.json();

        if (data.error) throw new Error("فشل تحديد الموقع");

        const englishCountry = data.country_name || 'Egypt';
        const arabicCountry = typeof countryMap !== 'undefined' && countryMap[englishCountry] ? countryMap[englishCountry] : englishCountry;

        const englishRegion = data.region || data.city || 'Unknown';
        const arabicGov = typeof govMap !== 'undefined' && govMap[englishRegion] ? govMap[englishRegion] : englishRegion;

        const dial = data.country_calling_code || '+20';
        // Convert country code to flag emoji
        let flag = '🇪🇬';
        if (data.country_code && data.country_code.length === 2) {
            flag = data.country_code.toUpperCase().replace(/./g, char => String.fromCodePoint(char.charCodeAt(0) + 127397));
        }

        applyValues(englishCountry, englishRegion, dial, flag, arabicCountry);

        statusDivs.forEach(div => {
            if (div) {
                div.innerHTML = `<span style="color: var(--gold, #c1ff11); font-weight: bold;">أهلاً بك يا غاوي! منورنا من ${arabicCountry}.</span>`;
                div.classList.remove('error');
            }
        });
    } catch (error) {
        // Fallback: check timezone if API fails (e.g., Adblocker)
        const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        const isEgyptFallback = (tz === 'Africa/Cairo');

        const fallbackCountry = isEgyptFallback ? 'Egypt' : 'Unknown';
        const fallbackGov = isEgyptFallback ? 'Cairo' : 'Unknown';
        const fallbackArabicCountry = isEgyptFallback ? 'مصر' : 'غير معروف';

        applyValues(fallbackCountry, fallbackGov, '+20', '🇪🇬', fallbackArabicCountry);

        statusDivs.forEach(div => {
            if (div) {
                div.classList.add('error');
                div.innerText = "تعذر تحديد الموقع تلقائياً، تم تعيين الإعدادات الافتراضية.";
            }
        });
    }
}

// Called when the register modal opens — NOT on page load.
//
// This sends the visitor's IP to a third party to prefill a form, so it should
// happen when that form appears, not on every landing-page view by everyone
// who never opens it. It also stopped being free: ipapi's tier is ~1000 calls
// a day, and past that it answers 429 — which the page cannot suppress, so it
// prints "Failed to load resource: 429" in every visitor's console for the
// rest of the day. Reproduced against production; the request now fires for
// the small fraction of visitors who actually reach the form.
//
// Once per page: reopening the modal must not repeat the lookup.
let geoRequested = false;
window.ensureGeoLocation = function () {
    if (geoRequested) return;
    geoRequested = true;
    getGeoLocation();
};

// Value Stack Animation
document.addEventListener("DOMContentLoaded", () => {
    // We add a small delay to ensure the DOM is fully rendered and the user sees the effect
    setTimeout(() => {
        const revealEl = document.getElementById('vsNewPrice');
        if (revealEl) {
            revealEl.classList.add('show');
        }
    }, 600);
});


