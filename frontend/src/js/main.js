
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

    // Watch Intro button — scroll into view / play
    const watchBtn = document.getElementById('watchIntroBtn');
    if (watchBtn) {
        watchBtn.addEventListener('click', () => {
            video.closest('.vsl-player-box')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
            video.muted = false;
            video.currentTime = 0;
            video.play();
            if (unmuteBtn) { unmuteBtn.classList.add('hide'); setTimeout(() => unmuteBtn.style.display = 'none', 300); }
        });
    }

    // Seek bar click
    if (seekWrap) {
        seekWrap.addEventListener('click', (e) => {
            if (!video.duration) return;
            const rect = seekWrap.getBoundingClientRect();
            const ratio = (e.clientX - rect.left) / rect.width;
            video.currentTime = ratio * video.duration;
        });
    }

    // Autoplay attempt
    video.play().catch(() => { });
})();

// ═══════════════════════════════════════════
//   SUPABASE — Live Purchase Popup
// ═══════════════════════════════════════════
let lastId = null;

async function checkPurchases() {
    try {
        const res = await fetch(
            "https://opetjxxzbmqzmqouqare.supabase.co/rest/v1/purchases?select=*&order=created_at.desc&limit=1",
            {
                headers: {
                    apikey: "sb_publishable_j-hpKwGwIf40c9vT8V2QYw_VbjbtSQF",
                    Authorization: "Bearer sb_publishable_j-hpKwGwIf40c9vT8V2QYw_VbjbtSQF",
                    "Content-Type": "application/json",
                    Prefer: "count=exact",
                },
            },
        );

        const range = res.headers.get("content-range");
        let totalPurchases = 0;
        if (range) totalPurchases = parseInt(range.split("/")[1]);

        updateProgressBarUI(totalPurchases);

        const data = await res.json();
        if (!data.length) return;

        const p = data[0];
        if (p.id !== lastId) {
            if (lastId !== null) showPopup(`${p.name} اشترك في الكورس منذ لحظات`);
            lastId = p.id;
        }
    } catch (err) {
        console.error("Supabase Error:", err);
    }
}

function updateProgressBarUI(totalPurchases) {
    let cycle = totalPurchases % 50;
    let registeredCount = cycle === 0 && totalPurchases > 0 ? 100 : 50 + cycle;
    let remaining = 100 - registeredCount;

    localStorage.setItem("courseProgressCache", JSON.stringify({ registeredCount, remaining }));

    const labels = document.querySelectorAll(".progress-labels span");
    const barFill = document.querySelector(".progress-bar-fill");

    if (labels.length >= 2) {
        labels[0].textContent = `اتسجل ${registeredCount} / 100`;
        labels[1].textContent = `باقي ${remaining}`;
    }
    if (barFill) {
        barFill.style.width = `${registeredCount}%`;
        barFill.style.transition = "width 1s ease, background 0.5s ease";
    }

    const slotsNumberLabel = document.querySelector(".slots-label span:last-child");
    const slotsFill = document.querySelector(".slots-fill");

    if (slotsNumberLabel) slotsNumberLabel.textContent = `${remaining} مقعد متبقي`;
    if (slotsFill) {
        slotsFill.style.width = `${registeredCount}%`;
        slotsFill.style.transition = "width 1s ease";
    }
}

function showPopup(text) {
    const div = document.createElement("div");
    div.innerHTML = `
      <div style="display:flex; align-items:center; gap:10px;">
        <div style="width:10px; height:10px; background:var(--green); border-radius:50%; box-shadow:0 0 10px var(--green);"></div>
        <span>${text}</span>
      </div>
    `;
    div.style = `
        position: fixed; bottom: 20px; left: 20px;
        background: rgba(21, 24, 12, 0.95);
        backdrop-filter: blur(10px);
        color: #fff; font-weight: bold;
        padding: 16px 20px; border-radius: 12px;
        z-index: 9999;
        box-shadow: 0 2px 40px rgba(193, 255, 17, 0.3);
        border: 1px solid rgba(193, 255, 17, 0.25);
        font-family: "Cairo";
        animation: slideIn 0.5s ease-out;
    `;
    document.body.appendChild(div);
    setTimeout(() => {
        div.style.animation = "slideOut 0.5s ease-in";
        setTimeout(() => div.remove(), 500);
    }, 7000);
}

const style = document.createElement("style");
style.innerHTML = `
    @keyframes slideIn { from { transform: translateX(-100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
    @keyframes slideOut { from { transform: translateX(0); opacity: 1; } to { transform: translateX(-100%); opacity: 0; } }
`;
document.head.appendChild(style);

if (document.querySelector('.progress-bar-fill')) {
    setInterval(checkPurchases, 5000);
    checkPurchases();
}

// ═══════════════════════════════════════════
//   Live Purchase Text Update
// ═══════════════════════════════════════════
let lastPurchase = null;

function timeAgo(dateString) {
    const purchaseTime = new Date(dateString + "Z");
    const now = new Date();
    const diff = Math.floor((now.getTime() - purchaseTime.getTime()) / 1000);
    if (diff < 10) return "الآن";
    if (diff < 60) return `${diff} ثانية`;
    if (diff < 3600) return `${Math.floor(diff / 60)} دقائق`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} ساعة`;
    return `${Math.floor(diff / 86400)} يوم`;
}

async function fetchLastPurchase() {
    try {
        const res = await fetch(
            "https://opetjxxzbmqzmqouqare.supabase.co/rest/v1/purchases?select=name,created_at&order=created_at.desc&limit=1",
            {
                headers: {
                    apikey: "sb_publishable_j-hpKwGwIf40c9vT8V2QYw_VbjbtSQF",
                    Authorization: "Bearer sb_publishable_j-hpKwGwIf40c9vT8V2QYw_VbjbtSQF",
                },
            },
        );
        const data = await res.json();
        if (!data.length) return;
        lastPurchase = data[0];
    } catch (e) {
        console.error("Live purchase error:", e);
    }
}

function updateLiveText() {
    if (!lastPurchase) return;
    const el = document.getElementById("livePurchaseText");
    if (!el) return;
    const ago = timeAgo(lastPurchase.created_at);
    el.textContent = `${lastPurchase.name} اشترى منذ ${ago}`;
}

fetchLastPurchase();
setInterval(updateLiveText, 1000);
setInterval(fetchLastPurchase, 10000);

// ═══════════════════════════════════════════
//   Cache-based initial bar rendering
// ═══════════════════════════════════════════
(function () {
    const cached = localStorage.getItem("courseProgressCache");
    if (cached) {
        const data = JSON.parse(cached);
        const bar = document.getElementById("initialBar");
        if (bar) bar.style.width = data.registeredCount + "%";
        const slotsFill = document.getElementById("initialSlotsFill");
        if (slotsFill) slotsFill.style.width = data.registeredCount + "%";
    }
})();

// ═══════════════════════════════════════════
//   Reviews Carousel (Video Testimonials)
// ═══════════════════════════════════════════
(function () {
    window.initReviewsCarousel = function () {
        const track = document.getElementById("carouselTrack");
        const nextBtn = document.getElementById("nextBtn");
        const prevBtn = document.getElementById("prevBtn");
        if (!track || !nextBtn || !prevBtn) return;

        const originalCards = Array.from(track.children);
        if (track.children.length < originalCards.length * 3) {
            originalCards.forEach((card) => track.appendChild(card.cloneNode(true)));
            originalCards.forEach((card) => track.appendChild(card.cloneNode(true)));
        }

        setTimeout(() => {
            const singleSetWidth = track.scrollWidth / 3;
            track.scrollLeft = -singleSetWidth;
            nextBtn.onclick = () => {
                const card = track.querySelector(".review-video-card");
                if (!card) return;
                track.scrollBy({ left: -(card.offsetWidth + 12), behavior: "smooth" });
            };
            prevBtn.onclick = () => {
                const card = track.querySelector(".review-video-card");
                if (!card) return;
                track.scrollBy({ left: card.offsetWidth + 12, behavior: "smooth" });
            };
        }, 300);
    };

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

    window.initCounterUp = function () {
        const counters = document.querySelectorAll('.counter-value');
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

        counters.forEach(counter => observer.observe(counter));
    };
})();

// ═══════════════════════════════════════════
//   DOMContentLoaded — Init All Components
// ═══════════════════════════════════════════
document.addEventListener("DOMContentLoaded", () => {
    if (window.initReviewsCarousel) window.initReviewsCarousel();
    if (window.initCoursesCarousel) window.initCoursesCarousel();
    if (window.initCounterUp) window.initCounterUp();
});

// ═══════════════════════════════════════════
//   FAQ Accordion
// ═══════════════════════════════════════════
document.querySelectorAll(".faq-q").forEach((btn) => {
    btn.addEventListener("click", () => {
        const item = btn.parentElement;
        const isOpen = item.classList.contains("open");
        document.querySelectorAll(".faq-item").forEach((el) => el.classList.remove("open"));
        if (!isOpen) item.classList.add("open");
    });
});

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

document.querySelectorAll(".chapter-card, .text-review-card, .screenshot-card")
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
const API = 'http://127.0.0.1:8000';

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

function getToken() { return localStorage.getItem('token'); }
function saveToken(token) { localStorage.setItem('token', token); }
function logout() {
    localStorage.removeItem('token');
    window.location.href = 'login.html';
}

// ═══════════════════════════════════════════
//   Premium Course Catalog — Swiper + Accordion
// ═══════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {

    // 1. Swiper Infinite Carousel
    if (document.querySelector('.coursesSwiper')) {
        const coursesSwiper = new Swiper('.coursesSwiper', {
            slidesPerView: 3,
            spaceBetween: 15,
            loop: true,
            grabCursor: true,
            centeredSlides: false,
            speed: 500,
            breakpoints: {
                0: { slidesPerView: 1, spaceBetween: 15 },
                768: { slidesPerView: 2, spaceBetween: 20 },
                1024: { slidesPerView: 3, spaceBetween: 30 }
            }
        });

        const prevBtn = document.getElementById('cPrevBtn');
        const nextBtn = document.getElementById('cNextBtn');
        if (prevBtn) prevBtn.addEventListener('click', () => coursesSwiper.slidePrev());
        if (nextBtn) nextBtn.addEventListener('click', () => coursesSwiper.slideNext());
    }

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

    // 3. Accordion — كل كارت مستقل تماماً ✅
    document.querySelectorAll('.premium-course-card').forEach(card => {
        const toggle = card.querySelector('.accordion-toggle');
        const content = card.querySelector('.accordion-content');
        const icon = card.querySelector('.toggle-icon');

        if (!toggle || !content) return;

        toggle.addEventListener('click', function (e) {
            e.stopPropagation();
            const isOpen = toggle.classList.contains('active');

            // أقفل كل الكروت التانية
            document.querySelectorAll('.premium-course-card').forEach(otherCard => {
                if (otherCard === card) return;
                const t = otherCard.querySelector('.accordion-toggle');
                const c = otherCard.querySelector('.accordion-content');
                const ic = otherCard.querySelector('.toggle-icon');
                if (t) t.classList.remove('active');
                if (ic) ic.style.transform = 'rotate(0deg)';
                if (c) c.style.maxHeight = null;
            });

            // افتح أو أقفل الكارت الحالي
            if (!isOpen) {
                toggle.classList.add('active');
                if (icon) icon.style.transform = 'rotate(180deg)';
                content.style.maxHeight = content.scrollHeight + 'px';
            } else {
                toggle.classList.remove('active');
                if (icon) icon.style.transform = 'rotate(0deg)';
                content.style.maxHeight = null;
            }
        });
    });

    // 4. Course Card Click → course-details.html
    document.addEventListener('click', function (e) {
        if (e.target.closest('.lessons-accordion')) return;
        const card = e.target.closest('.premium-course-card');
        if (!card) return;
        const slug = card.dataset.slug;
        if (slug) window.location.href = `course-details.html?course=${slug}`;
    });

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

// ════════════════════════════════════════
//   PREMIUM REVIEWS LOGIC
// ════════════════════════════════════════
const reviewsData = [
    { id: 'oqg0kwtp2y', name: 'عمر عماد', city: 'الإسكندرية', quote: 'وانا لسه في نص الكورس جبت اول عميل ليا وكانت عيادة اسنان ودفعوا فلوس حلوه', initial: 'ع' },
    { id: 'p6kqa3edvy', name: 'كريم طارق', city: 'القاهرة', quote: 'خلصت الكورس وشامل كل حاجة ومن أحسن الكورسات اللي شوفتها', initial: 'ك' },
    { id: 'vj9ymlhi7z', name: 'زياد تامر', city: 'القاهرة', quote: 'سبت الميديا باينج وقررت اعمل كارير شيفت وكورس محمد كان احسن كورس انا شفته', initial: 'ز' },
    { id: 'f19iov9z3o', name: 'منذر', city: 'الغربية', quote: 'أسست وكالة stirx.ai, أخدت كورسات على Udemy و Coursera بس الكم ده من المعلومات عمري ما شوفته في كورس واحد', initial: 'م' },
    { id: 'lh58056wkw', name: 'يوسف دسوقي', city: 'القاهرة', quote: 'مفيش كورس متكامل بالشكل ده في الوطن العربي', initial: 'ي' },
    { id: 'sn2k9l641c', name: 'ياسين مصطفى', city: 'الجيزة', quote: 'جبت أول عميل ليا بعد ما خلصت الكورس بأسبوعين', initial: 'ي' },
    { id: '8n571cb98s', name: 'معتز', city: 'القاهرة', quote: 'لما دخلت الكورس لقيت حاجات عمري ما سمعت عنها, أنت مش بتشتري كورس، أنت بتشتري باكج كاملة فيها مجتمع ومتابعة شخصية', initial: 'م' }
];

let currentHeroIdx = 0;
let reviewCycleInterval;
let progressStartTime;
const CYCLE_DURATION = 6000;
let isVideoPlaying = false;

function initReviews() {
    const layout = document.getElementById('prLayout');
    if (!layout) return;

    // Generate all cards
    layout.innerHTML = reviewsData.map((rev, i) => `
        <div class="pr-card" id="prCard-${i}" onclick="promoteToHero(${i})">
            <img src="https://fast.wistia.com/embed/medias/${rev.id}/swatch" class="pr-thumb" alt="${rev.name}" />
            
            <div class="pr-quotes-icon">«</div>
            
            <div class="pr-pulse"><div class="pr-dot"></div> جاري المشاهدة</div>
            
            <div class="pr-play-btn" onclick="playWistiaVideo(event, ${i}, '${rev.id}')">
                <i class="fa-solid fa-play"></i>
            </div>
            
            <div class="pr-wistia-wrapper" id="prWistia-${i}"></div>

            <div class="pr-content">
                <div class="pr-chip">
                    <div class="pr-avatar">${rev.initial}</div>
                    <div class="pr-details">
                        <span class="pr-name">${rev.name}</span>
                        <span class="pr-city">${rev.city}</span>
                    </div>
                    <div class="pr-stars">★★★★★</div>
                </div>
                <div class="pr-quote">${rev.quote}</div>
            </div>
            
            <div class="pr-progress"><div class="pr-progress-fill" id="prProg-${i}"></div></div>
        </div>
    `).join('');

    updateReviewClasses();
    startReviewCycle();
}

function updateReviewClasses() {
    reviewsData.forEach((_, i) => {
        const card = document.getElementById(`prCard-${i}`);
        card.className = 'pr-card is-hidden'; // reset

        // Stop any playing video if it's not hero anymore
        const wistiaWrap = document.getElementById(`prWistia-${i}`);
        if (wistiaWrap) wistiaWrap.style.display = 'none';

        // Reset progress bar
        const prog = document.getElementById(`prProg-${i}`);
        if (prog) {
            prog.style.transition = 'none';
            prog.style.width = '0%';
        }
    });

    // Assign hero
    document.getElementById(`prCard-${currentHeroIdx}`).className = 'pr-card is-hero';

    // Assign stack
    for (let j = 1; j <= 3; j++) {
        let stackIdx = (currentHeroIdx + j) % reviewsData.length;
        document.getElementById(`prCard-${stackIdx}`).className = `pr-card is-stack-${j}`;
    }
}

function promoteToHero(idx) {
    if (idx === currentHeroIdx) return;
    currentHeroIdx = idx;
    isVideoPlaying = false; // reset play state
    updateReviewClasses();
    resetReviewCycle();
}

function playWistiaVideo(e, idx, videoId) {
    e.stopPropagation(); // prevent promoteToHero
    if (idx !== currentHeroIdx) return;

    isVideoPlaying = true;
    clearInterval(reviewCycleInterval); // stop cycling

    const wrapper = document.getElementById(`prWistia-${idx}`);
    wrapper.style.display = 'block';
    wrapper.innerHTML = `
        <iframe src="https://fast.wistia.net/embed/iframe/${videoId}?autoPlay=true&seo=false&videoFoam=true" 
                title="Wistia Video" 
                allowtransparency="true" 
                frameborder="0" 
                scrolling="no" 
                class="wistia_embed" 
                name="wistia_embed" 
                allow="autoplay; fullscreen" 
                allowfullscreen mozallowfullscreen webkitallowfullscreen oallowfullscreen msallowfullscreen 
                width="100%" height="100%" 
                style="width:100%; height:100%; border:none;">
        </iframe>
    `;
}

function animateProgressBar() {
    if (isVideoPlaying) return;
    const prog = document.getElementById(`prProg-${currentHeroIdx}`);
    if (!prog) return;

    const elapsed = Date.now() - progressStartTime;
    let percent = (elapsed / CYCLE_DURATION) * 100;
    if (percent > 100) percent = 100;

    prog.style.transition = 'width 0.1s linear';
    prog.style.width = percent + '%';
}

function startReviewCycle() {
    progressStartTime = Date.now();
    reviewCycleInterval = setInterval(() => {
        if (!isVideoPlaying) {
            currentHeroIdx = (currentHeroIdx + 1) % reviewsData.length;
            updateReviewClasses();
            progressStartTime = Date.now();
        }
    }, CYCLE_DURATION);

    // Animation loop for progress bar
    requestAnimationFrame(function loop() {
        animateProgressBar();
        requestAnimationFrame(loop);
    });
}

function resetReviewCycle() {
    clearInterval(reviewCycleInterval);
    if (!isVideoPlaying) {
        startReviewCycle();
    }
}

document.addEventListener('DOMContentLoaded', initReviews);

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

window.applyCurrencyUI = function (currency) {
    const isUSD = currency === 'USD';

    document.querySelectorAll('.offer-value').forEach(el => {
        if (!el.hasAttribute('data-egp')) el.setAttribute('data-egp', el.innerText);
        const egp = el.getAttribute('data-egp');
        if (isUSD) {
            if (egp.includes('15,000')) el.innerText = '300 USD';
            else if (egp.includes('3,500')) el.innerText = '70 USD';
            else if (egp.includes('2,500')) el.innerText = '50 USD';
            else if (egp.includes('5,000')) el.innerText = '100 USD';
            else if (egp.includes('4,000')) el.innerText = '80 USD';
        } else {
            el.innerText = egp;
        }
    });

    document.querySelectorAll('.strike').forEach(el => {
        if (!el.hasAttribute('data-egp')) el.setAttribute('data-egp', el.innerText);
        const egp = el.getAttribute('data-egp');
        if (isUSD && egp.includes('30,000')) el.innerText = '600 USD';
        else el.innerText = egp;
    });

    document.querySelectorAll('.price-big').forEach(el => {
        if (!el.hasAttribute('data-egp')) el.setAttribute('data-egp', el.innerText);
        const egp = el.getAttribute('data-egp');
        if (isUSD && egp.includes('2,999')) el.innerText = '60';
        else el.innerText = egp;
    });

    document.querySelectorAll('.price-currency, .pricing-currency').forEach(el => {
        el.innerText = isUSD ? 'USD' : 'ج.م';
    });

    const priceAmount = document.getElementById('priceAmount');
    if (priceAmount) {
        if (!priceAmount.hasAttribute('data-egp')) priceAmount.setAttribute('data-egp', priceAmount.innerText);
        const egp = priceAmount.getAttribute('data-egp');
        if (isUSD && egp.includes('500')) priceAmount.innerText = '15';
        else if (isUSD && egp.includes('333')) priceAmount.innerText = '10';
        else priceAmount.innerText = egp;
    }

    const priceNote = document.getElementById('priceNote');
    if (priceNote) {
        if (!priceNote.hasAttribute('data-egp')) priceNote.setAttribute('data-egp', priceNote.innerText);
        const egp = priceNote.getAttribute('data-egp');
        if (isUSD && egp.includes('4,000')) {
            priceNote.innerText = 'تدفع $80 سنوياً بدلاً من $120';
        } else {
            priceNote.innerText = egp;
        }
    }

    const vsElements = [
        { id: 'vs-price-main', egp: '10,000 ج.م', usd: '200 USD' },
        { id: 'vs-price-1', egp: '5,000 ج.م', usd: '100 USD' },
        { id: 'vs-price-2', egp: '2,500 ج.م', usd: '50 USD' },
        { id: 'vs-price-3', egp: '8,500 ج.م', usd: '170 USD' },
        { id: 'vs-price-4', egp: '4,000 ج.م', usd: '80 USD' },
        { id: 'vs-price-old', egp: '30,000 ج.م', usd: '600 USD' }
    ];

    vsElements.forEach(item => {
        const el = document.getElementById(item.id);
        if (el) {
            el.innerText = isUSD ? item.usd : item.egp;
        }
    });

    const vsPriceNew = document.getElementById('vs-price-new');
    if (vsPriceNew) {
        if (isUSD) {
            vsPriceNew.innerHTML = '60 <span>USD</span>';
        } else {
            vsPriceNew.innerHTML = '2,999 <span>ج.م</span>';
        }
    }

    document.querySelectorAll('*').forEach(el => {
        if (el.children.length === 0 && el.textContent) {
            if (!el.hasAttribute('data-egp')) el.setAttribute('data-egp', el.textContent);
            const egp = el.getAttribute('data-egp');
            if (isUSD && (egp.includes('ج.م 2,999 فقط') || egp.includes('EGP 2,999 فقط'))) {
                el.textContent = egp.replace(/ج\.م 2,999 فقط|EGP 2,999 فقط/g, '60$ فقط');
            } else if (!isUSD && (egp.includes('ج.م 2,999 فقط') || egp.includes('EGP 2,999 فقط'))) {
                el.textContent = egp;
            }
        }
    });
};

window.handleCountryChange = function (country) {
    populateGovernorates(country);
    if (window.updateWelcomeMessage) window.updateWelcomeMessage();

    if (country && country !== 'مصر') {
        window.applyCurrencyUI('USD');
        localStorage.setItem('user_currency', 'USD');
    } else {
        window.applyCurrencyUI('EGP');
        localStorage.setItem('user_currency', 'EGP');
    }
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
        const isEgypt = (englishCountry === 'Egypt');
        const arabicCountry = typeof countryMap !== 'undefined' && countryMap[englishCountry] ? countryMap[englishCountry] : englishCountry;

        const englishRegion = data.region || data.city || 'Unknown';
        const arabicGov = typeof govMap !== 'undefined' && govMap[englishRegion] ? govMap[englishRegion] : englishRegion;

        const dial = data.country_calling_code || '+20';
        // Convert country code to flag emoji
        let flag = '🇪🇬';
        if (data.country_code && data.country_code.length === 2) {
            flag = data.country_code.toUpperCase().replace(/./g, char => String.fromCodePoint(char.charCodeAt(0) + 127397));
        }

        // Apply currency immediately based on IP
        if (!isEgypt) {
            if (window.applyCurrencyUI) window.applyCurrencyUI('USD');
            localStorage.setItem('user_currency', 'USD');
        } else {
            if (window.applyCurrencyUI) window.applyCurrencyUI('EGP');
            localStorage.setItem('user_currency', 'EGP');
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

        if (!isEgyptFallback) {
            if (window.applyCurrencyUI) window.applyCurrencyUI('USD');
            localStorage.setItem('user_currency', 'USD');
        } else {
            if (window.applyCurrencyUI) window.applyCurrencyUI('EGP');
            localStorage.setItem('user_currency', 'EGP');
        }

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

// Call on window load
window.addEventListener('load', getGeoLocation);

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


