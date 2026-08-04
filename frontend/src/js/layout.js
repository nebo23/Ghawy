// ═══ PUBLIC SITE LAYOUT — single source for the navbar + footer ═══
//
// The marketing site is multi-page now (index, /courses, /tracks, /reviews,
// /pricing). Every one of those pages pulls its header and footer from HERE,
// so editing the nav in one place updates all of them. There is deliberately
// no copy of the markup left in the pages themselves — one source only.
//
// ── Load order matters ──
// This file is a plain (non-defer, non-async) script placed INSIDE <body>,
// immediately after the placeholder it fills. Classic in-body scripts run
// during parsing, so the markup is in the DOM before the browser paints past
// it (no layout shift) and — critically — before i18n.js at the bottom of the
// page runs its automatic pass, so every data-ar/data-en in the injected
// markup gets translated by the normal engine. Do NOT add defer/async and do
// NOT move this to <head>: both would push execution past i18n.js.
//
// Usage in a page:
//     <div id="siteHeader"></div>
//     <script src="src/js/layout.js?v=..."></script>
//     ...
//     <div id="siteFooter"></div>
//     <script>GhawyLayout.mountFooter();</script>
//
// This does NOT touch community pages (dashboard/chat/profile…) — those have
// their own sidebar layout entirely.

(function () {
    'use strict';

    // ── The four public sections, in the order the client asked for ──
    // `match` is what the current path is tested against for the active state.
    const NAV_ITEMS = [
        { href: '/courses', match: 'courses', ar: 'الكورسات', en: 'Courses' },
        { href: '/tracks', match: 'tracks', ar: 'المسارات', en: 'Tracks' },
        { href: '/reviews', match: 'reviews', ar: 'آراء الأعضاء', en: 'Member Reviews' },
        { href: '/pricing', match: 'pricing', ar: 'الأسعار', en: 'Pricing' },
    ];

    /**
     * Which nav item the current URL belongs to.
     * nginx serves these extensionless (try_files $uri $uri.html) but each page
     * is equally reachable with its .html suffix during local file testing, so
     * the extension is stripped before matching. Returns '' on the home page —
     * home has no active link, by design.
     */
    function currentSection() {
        const file = window.location.pathname.split('/').pop().replace(/\.html$/, '');
        return NAV_ITEMS.some(i => i.match === file) ? file : '';
    }

    const active = currentSection();

    function navLinks(mobile) {
        return NAV_ITEMS.map(item => {
            const isActive = item.match === active;
            const cls = isActive ? ' class="active"' : '';
            const aria = isActive ? ' aria-current="page"' : '';
            const onclick = mobile ? ' onclick="closeDrawer()"' : '';
            const a = `<a href="${item.href}"${cls}${aria}${onclick} data-ar="${item.ar}" data-en="${item.en}">${item.ar}</a>`;
            return mobile ? a : `<li>${a}</li>`;
        }).join('\n');
    }

    // ─── Navbar + mobile drawer ──────────────────────────────────
    function headerHTML() {
        return `
    <nav class="main-nav" id="mainNav">
        <a href="/" class="nav-logo" id="navLogo">
            <img src="./imgs/ghawy-new-logo-transparent.png" alt="Ghawy" />
        </a>
        <ul class="nav-links" id="navLinks">
${navLinks(false)}
        </ul>
        <div class="nav-auth" id="navAuth">
            <button id="langToggleBtn" class="nav-lang-toggle" onclick="toggleLanguage()">
                <span id="langToggleText">English</span>
            </button>
            <!-- Logged out state (default) -->
            <div id="navLoggedOut">
                <a href="login.html" class="nav-auth-btn ghost" data-ar="تسجيل الدخول" data-en="Login">تسجيل الدخول</a>
                <a href="register.html" class="nav-auth-btn primary" data-ar="ابدا الان" data-en="Start Now">ابدا الان</a>
            </div>
            <!-- Logged in state -->
            <div id="navLoggedIn" style="display:none; align-items:center; gap:12px;">
                <button class="nav-auth-btn danger" onclick="logout()" data-ar="تسجيل الخروج" data-en="Logout">تسجيل الخروج</button>
            </div>
        </div>
        <button class="hamburger" id="hamburgerBtn" aria-label="القائمة">
            <span></span><span></span><span></span>
        </button>
    </nav>

    <div class="mobile-drawer" id="mobileDrawer">
${navLinks(true)}
        <div id="mobileAuthLoggedOut">
            <a href="login.html" onclick="closeDrawer()" class="mobile-login-link"
               data-ar="تسجيل الدخول" data-en="Login">تسجيل الدخول</a>
        </div>
        <div id="mobileAuthLoggedIn" style="display:none">
            <button onclick="closeDrawer();logout()" style="color:var(--red)" data-ar="تسجيل الخروج" data-en="Logout">تسجيل الخروج</button>
        </div>
        <div class="mobile-lang-row">
            <button id="mobileLangToggleBtn" class="mobile-lang-toggle-btn" onclick="toggleLanguage()">
                <i class="fa-solid fa-globe"></i>
                <span id="mobileLangToggleText">English</span>
            </button>
        </div>
        <a href="javascript:void(0)" class="mobile-cta" onclick="closeDrawer(); GhawyLayout.join()"
           data-ar="ابدا الان" data-en="Start Now">ابدا الان</a>
    </div>`;
    }

    // ─── Footer ──────────────────────────────────────────────────
    // A straight port of the footer that used to be inline in index.html —
    // same columns, same copy, same links. In particular the quick links still
    // point at the home-page anchors (#modules, #reviews, #features,
    // #checkout) rather than the new standalone pages: rewiring them is a
    // later phase, and they work from every page because they are absolute
    // (index.html#...).
    function footerHTML() {
        const link = (href, ar, en) =>
            `<a href="${href}" class="footer-link" data-ar="${ar}" data-en="${en}">${ar}</a>`;

        return `
    <footer class="site-footer">
        <div class="container">
            <div class="footer-grid">
                <div class="footer-col">
                    <h3 class="footer-heading" data-ar="عن غاوي" data-en="About Ghawy">عن غاوي</h3>
                    <p class="footer-about"
                        data-ar="منصة الغاوي هي المكان الأفضل لتعلم الذكاء الاصطناعي وبناء وكالتك الخاصة خطوة بخطوة."
                        data-en="Ghawy is the best place to learn AI and build your own agency step by step.">
                        منصة الغاوي هي المكان الأفضل لتعلم الذكاء الاصطناعي وبناء وكالتك الخاصة خطوة بخطوة.
                    </p>
                </div>

                <div class="footer-col">
                    <h3 class="footer-heading" data-ar="روابط سريعة" data-en="Quick Links">روابط سريعة</h3>
                    ${link('index.html#modules', 'الكورسات', 'Courses')}
                    ${link('index.html#reviews', 'آراء المشتركين', 'Reviews')}
                    ${link('index.html#features', 'المميزات', 'Features')}
                    ${link('index.html#checkout', 'الأسعار', 'Pricing')}
                </div>

                <div class="footer-col">
                    <h3 class="footer-heading" data-ar="الشروط والسياسات" data-en="Terms &amp; Policies">الشروط والسياسات</h3>
                    ${link('terms.html', 'الشروط والأحكام', 'Terms &amp; Conditions')}
                    ${link('terms.html#privacy', 'سياسة الخصوصية', 'Privacy Policy')}
                </div>

                <div class="footer-col footer-col-contact">
                    <h3 class="footer-heading" data-ar="تواصل معنا" data-en="Contact Us">تواصل معنا</h3>
                    <a href="tel:+201033903334" class="footer-link footer-phone">
                        <i class="fa-solid fa-phone"></i> <span dir="ltr">01033903334</span>
                    </a>
                </div>
            </div>

            <div class="footer-bottom">
                <p class="footer-copy" data-ar="© 2026 Ghawy. جميع الحقوق محفوظة."
                    data-en="© 2026 Ghawy. All rights reserved.">© 2026 Ghawy. جميع الحقوق محفوظة.</p>
                <div class="social-icons">
                    <a href="https://instagram.com/ghawy_official" target="_blank" rel="noopener" class="social-icon" aria-label="Instagram">
                        <i class="fa-brands fa-instagram"></i>
                    </a>
                    <a href="https://facebook.com/ghawyofficial" target="_blank" rel="noopener" class="social-icon" aria-label="Facebook">
                        <i class="fa-brands fa-facebook-f"></i>
                    </a>
                    <a href="https://tiktok.com/@ghawy_official" target="_blank" rel="noopener" class="social-icon" aria-label="TikTok">
                        <i class="fa-brands fa-tiktok"></i>
                    </a>
                </div>
            </div>
        </div>
    </footer>`;
    }

    // ─── Behaviour that travels with the markup ──────────────────

    let wired = false;

    function wireHeader() {
        if (wired) return;
        const nav = document.getElementById('mainNav');
        const hamburger = document.getElementById('hamburgerBtn');
        const drawer = document.getElementById('mobileDrawer');
        if (!nav || !hamburger || !drawer) return;
        wired = true;

        window.addEventListener('scroll', () => {
            nav.classList.toggle('scrolled', window.scrollY > 60);
        }, { passive: true });
        nav.classList.toggle('scrolled', window.scrollY > 60);

        window.toggleDrawer = function () {
            hamburger.classList.toggle('active');
            drawer.classList.toggle('open');
            document.body.style.overflow = drawer.classList.contains('open') ? 'hidden' : '';
        };
        window.closeDrawer = function () {
            hamburger.classList.remove('active');
            drawer.classList.remove('open');
            document.body.style.overflow = '';
        };
        hamburger.addEventListener('click', window.toggleDrawer);

        updateNavAuth();
    }

    /**
     * Logged-in vs logged-out nav, from the token alone.
     * index.html runs its own richer pass afterwards (it also rewrites the hero
     * CTA based on subscription state); both write the same elements to the
     * same values, so running both is harmless.
     */
    function updateNavAuth() {
        const token = (typeof getToken === 'function') ? getToken() : localStorage.getItem('token');
        const show = (id, on, display) => {
            const el = document.getElementById(id);
            if (el) el.style.display = on ? (display || '') : 'none';
        };
        show('navLoggedOut', !token);
        show('navLoggedIn', !!token, 'flex');
        show('mobileAuthLoggedOut', !token, 'block');
        show('mobileAuthLoggedIn', !!token, 'block');
        const cta = document.querySelector('.mobile-cta');
        if (cta) cta.style.display = token ? 'none' : 'block';
    }

    /**
     * Drawer "ابدا الان". On index.html the page defines handleKashierPayment()
     * and we defer to it; on the standalone pages it does not exist, so we fall
     * back to the same plain routing it would do. No payment logic here.
     */
    function join() {
        if (typeof window.handleKashierPayment === 'function') {
            window.handleKashierPayment();
            return;
        }
        const token = (typeof getToken === 'function') ? getToken() : localStorage.getItem('token');
        window.location.href = token ? 'payment.html' : 'register.html';
    }

    // ─── Mounting ────────────────────────────────────────────────

    function mountInto(id, html) {
        const slot = document.getElementById(id);
        if (!slot || slot.dataset.mounted === '1') return false;
        slot.innerHTML = html;
        slot.dataset.mounted = '1';
        return true;
    }

    function mountHeader() {
        if (mountInto('siteHeader', headerHTML())) wireHeader();
    }

    function mountFooter() {
        mountInto('siteFooter', footerHTML());
    }

    window.GhawyLayout = { mountHeader, mountFooter, updateNavAuth, join };

    // Inject the header the moment this script runs (the placeholder sits just
    // above the <script> tag, so it already exists).
    mountHeader();

    // Safety net: if a page put the script somewhere the placeholders weren't
    // parsed yet, mount whatever is still empty once the DOM is ready and
    // re-run the language pass over the late markup.
    document.addEventListener('DOMContentLoaded', () => {
        const headerLate = !!document.getElementById('siteHeader') &&
            document.getElementById('siteHeader').dataset.mounted !== '1';
        const footerLate = !!document.getElementById('siteFooter') &&
            document.getElementById('siteFooter').dataset.mounted !== '1';
        if (!headerLate && !footerLate) return;
        mountHeader();
        mountFooter();
        if (typeof window.applyLanguage === 'function' && typeof window.currentLang === 'function') {
            window.applyLanguage(window.currentLang(), false);
        }
    });
})();
