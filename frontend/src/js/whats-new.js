/* ═══════════════════════════════════════════
   WHAT'S NEW — shared across all sections.
   • Popup: shows once per version (localStorage),
     no matter which page the user lands on first.
   • Dashboard widget: always renders the same
     updates list into #wnWidgetList when present.
   ═══════════════════════════════════════════ */
(function () {
    var KEY = 'ghawy_whatsnew_seen', VER = 'v6';
    var seen = true;
    try { seen = localStorage.getItem(KEY) === VER; } catch (e) { }

    var CSS = '\
.wn-overlay{position:fixed;inset:0;z-index:3000;display:none;place-items:center;padding:20px;background:rgba(0,0,0,.65);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);opacity:0;transition:opacity .25s ease}\
.wn-overlay.show{opacity:1}\
.wn-modal{width:min(680px,100%);background:var(--bg-card,#111);border:1px solid var(--border-light-new,rgba(255,255,255,.1));border-radius:22px;display:grid;grid-template-columns:260px 1fr;overflow:hidden;position:relative;box-shadow:0 30px 80px -20px rgba(0,0,0,.8),0 0 0 1px rgba(193,255,17,.05);transform:translateY(14px) scale(.97);transition:transform .3s cubic-bezier(.2,.9,.3,1.2)}\
.wn-overlay.show .wn-modal{transform:translateY(0) scale(1)}\
.wn-left{padding:26px 24px 22px;display:flex;flex-direction:column;background:radial-gradient(90% 60% at 50% 100%,rgba(193,255,17,.10),transparent 70%),linear-gradient(180deg,#0c100c,#0a0d0a)}\
.wn-brand{display:flex;align-items:center;gap:9px;margin-bottom:30px}\
.wn-brand img{width:28px;height:28px}\
.wn-brand span{font-weight:800;font-size:19px;color:#f2f5f0}\
.wn-headline{font-weight:900;font-size:32px;line-height:1.1;letter-spacing:-.5px;color:#f2f5f0}\
.wn-headline .wn-accent{color:var(--accent-gold,#c1ff11)}\
.wn-ver{display:inline-block;vertical-align:middle;font-size:11px;font-weight:800;background:var(--accent-gold,#c1ff11);color:#0a0d0a;padding:2px 8px;border-radius:6px;margin-inline-start:8px}\
.wn-sub{color:#8b938a;font-size:13px;line-height:1.7;margin-top:14px}\
.wn-art{margin-top:auto;text-align:center;padding:18px 0 6px}\
.wn-art svg{width:170px;filter:drop-shadow(0 0 22px rgba(193,255,17,.25))}\
.wn-art-card{fill:#0f150c;stroke:#c1ff11}\
.wn-art-basket{fill:#111a0d;stroke:#c1ff11}\
.wn-art-dot{fill:#c1ff11}\
.wn-art-line1{fill:#8fd41f}\
.wn-art-line2{fill:#5a7a20}\
.wn-skip{margin-top:10px;align-self:flex-start;background:transparent;color:#f2f5f0;border:1px solid rgba(255,255,255,.12);padding:9px 20px;border-radius:11px;font-family:inherit;font-size:13px;font-weight:600;cursor:pointer;transition:.2s}\
.wn-skip:hover{border-color:rgba(193,255,17,.35);background:rgba(193,255,17,.05)}\
.wn-right{padding:22px 22px 18px;display:flex;flex-direction:column;min-width:0}\
.wn-close{position:absolute;top:16px;inset-inline-end:16px;width:30px;height:30px;border-radius:9px;background:var(--bg-card,#111);border:1px solid var(--border-light-new,rgba(255,255,255,.12));color:var(--txt-muted,#888);cursor:pointer;display:grid;place-items:center;transition:.2s;z-index:5;font-size:14px;line-height:1}\
.wn-close:hover{color:var(--txt-primary,#fff);border-color:rgba(193,255,17,.35)}\
.wn-list{display:flex;flex-direction:column;gap:9px;overflow-y:auto;padding-inline-end:4px;max-height:380px}\
.wn-list::-webkit-scrollbar{width:5px}\
.wn-list::-webkit-scrollbar-thumb{background:rgba(193,255,17,.25);border-radius:9px}\
.wn-item{display:flex;flex-wrap:wrap;gap:13px;align-items:flex-start;background:var(--bg-card2,#0a0a0a);border:1px solid var(--border-subtle,rgba(255,255,255,.06));border-radius:14px;padding:13px 14px;transition:.2s}\
.wn-shot{width:100%;aspect-ratio:16/9;object-fit:cover;display:block;border-radius:11px;border:1px solid rgba(193,255,17,.18);background:var(--bg-card2,#0a0a0a);margin-bottom:2px}\
:root[data-theme="light"] .wn-shot{border-color:rgba(101,163,13,.28)}\
.wn-shot.wn-shot-cert{aspect-ratio:auto}\
.wn-item:hover{background:var(--bg-hover-new,#1a1a1a);border-color:rgba(193,255,17,.3);transform:translateY(-1px)}\
.wn-ic{flex-shrink:0;width:40px;height:40px;border-radius:11px;display:grid;place-items:center;font-size:17px}\
.wn-ic.lime{background:rgba(193,255,17,.10);color:var(--accent-gold,#c1ff11)}\
.wn-ic.blue{background:rgba(79,182,255,.10);color:#4fb6ff}\
.wn-ic.purple{background:rgba(181,123,255,.10);color:#b57bff}\
.wn-ic.orange{background:rgba(255,157,63,.10);color:#ff9d3f}\
.wn-ic.cyan{background:rgba(63,255,216,.10);color:#2dd4bf}\
.wn-ic.green{background:rgba(34,197,94,.10);color:#22c55e}\
.wn-ic.violet{background:rgba(154,123,255,.10);color:#9a7bff}\
.wn-body{flex:1;min-width:0}\
.wn-row{display:flex;align-items:center;gap:8px;margin-bottom:3px;flex-wrap:wrap}\
.wn-title{font-weight:700;font-size:14px;color:var(--txt-primary,#f1f0ea)}\
.wn-desc{color:var(--txt-secondary,#b0b0c0);font-size:12.5px;line-height:1.55}\
.wn-tag{font-size:9.5px;font-weight:800;letter-spacing:.4px;padding:2px 8px;border-radius:6px;margin-inline-start:auto;flex-shrink:0}\
.wn-tag.new{background:rgba(193,255,17,.12);color:var(--accent-gold,#c1ff11);border:1px solid rgba(193,255,17,.3)}\
.wn-tag.improved{background:rgba(169,123,255,.12);color:#a97bff;border:1px solid rgba(169,123,255,.35)}\
.wn-foot{display:flex;align-items:center;justify-content:flex-end;margin-top:14px}\
.wn-done{display:inline-flex;align-items:center;gap:9px;background:var(--accent-gold,#c1ff11);color:#0a0d0a;font-family:inherit;font-weight:800;font-size:14px;border:none;padding:11px 26px;border-radius:12px;cursor:pointer;box-shadow:0 6px 22px -6px rgba(193,255,17,.5);transition:.2s}\
.wn-done:hover{filter:brightness(1.08);transform:translateY(-1px)}\
:root[data-theme="light"] .wn-overlay{background:rgba(15,23,42,.45)}\
:root[data-theme="light"] .wn-left{background:radial-gradient(90% 60% at 50% 100%,rgba(132,204,22,.12),transparent 70%),linear-gradient(180deg,#f8fafc,#eef2e6)}\
:root[data-theme="light"] .wn-brand span,:root[data-theme="light"] .wn-headline{color:#0f172a}\
:root[data-theme="light"] .wn-headline .wn-accent{color:#65a30d}\
:root[data-theme="light"] .wn-sub{color:#64748b}\
:root[data-theme="light"] .wn-skip{color:#0f172a;border-color:rgba(15,23,42,.15)}\
:root[data-theme="light"] .wn-ic.lime{color:#65a30d}\
:root[data-theme="light"] .wn-tag.new{color:#65a30d}\
:root[data-theme="light"] .wn-modal{box-shadow:0 30px 80px -20px rgba(15,23,42,.3)}\
:root[data-theme="light"] .wn-art svg{filter:drop-shadow(0 0 18px rgba(101,163,13,.25))}\
:root[data-theme="light"] .wn-art-card{fill:#ffffff;stroke:#65a30d}\
:root[data-theme="light"] .wn-art-basket{fill:#f0f7e0;stroke:#65a30d}\
:root[data-theme="light"] .wn-art-dot{fill:#65a30d}\
:root[data-theme="light"] .wn-art-line1{fill:#84cc16}\
:root[data-theme="light"] .wn-art-line2{fill:#a3b98a}\
@media (max-width:640px){\
.wn-modal{grid-template-columns:1fr;max-height:92vh;overflow-y:auto}\
.wn-art{display:none}\
.wn-left{padding-bottom:16px}\
.wn-brand{margin-bottom:18px}\
.wn-skip{display:none}\
.wn-list{max-height:none;overflow-y:visible}\
}\
.wn-widget-card{padding:0;overflow:hidden}\
.wn-car-nav{display:flex;gap:6px}\
.wn-car-btn{width:26px;height:26px;border-radius:8px;background:transparent;border:1px solid var(--border-light-new,rgba(255,255,255,.12));color:var(--txt-muted,#888);cursor:pointer;display:grid;place-items:center;font-size:11px;line-height:1;transition:.2s}\
.wn-car-btn:hover{color:var(--accent-gold,#c1ff11);border-color:rgba(193,255,17,.35)}\
:root[data-theme="light"] .wn-car-btn:hover{color:#65a30d;border-color:rgba(101,163,13,.4)}\
.wn-car-viewport{padding:14px 16px 16px}\
.wn-car-clip{overflow:hidden}\
.wn-car-track{display:flex;transition:transform .35s ease}\
.wn-car-track>.wn-item{flex:0 0 100%;min-width:100%;align-content:flex-start}\
.wn-car-track .wn-shot{aspect-ratio:16/9;object-fit:cover}\
.wn-car-dots{display:flex;justify-content:center;gap:6px;margin-top:12px}\
.wn-car-dot{width:7px;height:7px;border-radius:99px;background:var(--border-light-new,rgba(255,255,255,.18));border:none;cursor:pointer;padding:0;transition:.25s}\
.wn-car-dot.active{background:var(--accent-gold,#c1ff11);width:18px}\
:root[data-theme="light"] .wn-car-dot{background:rgba(15,23,42,.18)}\
:root[data-theme="light"] .wn-car-dot.active{background:#65a30d}';

    function item(shotSrc, shotAlt, shotExtra, icClass, faIcon, title, tag, desc) {
        var shot = shotSrc
            ? '<img class="wn-shot' + (shotExtra || '') + '" src="' + shotSrc + '" alt="' + shotAlt + '" loading="lazy" />'
            : '';
        return '<div class="wn-item">' + shot +
            '<div class="wn-ic ' + icClass + '"><i class="fa-solid ' + faIcon + '"></i></div>' +
            '<div class="wn-body">' +
            '<div class="wn-row"><span class="wn-title">' + title + '</span><span class="wn-tag ' + tag.toLowerCase() + '" data-no-i18n>' + tag + '</span></div>' +
            '<p class="wn-desc">' + desc + '</p>' +
            '</div></div>';
    }

    // The updates list — rendered inside both the popup and the dashboard widget.
    var LIST =
        item('/assets/whats-new/whats-new-ai-updates.png', 'AI Updates — New Experience', '', 'lime', 'fa-bolt',
            'AI Updates — New Experience', 'NEW',
            'A completely new design for AI Updates. Stay ahead with the latest news, tools, models &amp; more.') +
        item('/assets/whats-new/whats-new-light-mode.png', 'Light Mode', '', 'blue', 'fa-sun',
            'Light Mode', 'NEW',
            'A beautiful new light mode for a cleaner and brighter experience.') +
        item('/assets/whats-new/whats-new-preferences.png', 'Preferences', '', 'purple', 'fa-sliders',
            'Preferences', 'NEW',
            'Choose your language and theme — customize your experience the way you like it.') +
        item('/assets/whats-new/whats-new-exams.png', 'Exams &amp; Quizzes', '', 'orange', 'fa-file-lines',
            'Exams &amp; Quizzes', 'NEW',
            'Take exams inside your courses, test your knowledge and track your progress.') +
        item('/assets/whats-new/whats-new-certificates.png', 'Course Certificates', ' wn-shot-cert', 'cyan', 'fa-award',
            'Course Certificates', 'NEW',
            'Finish a course and get a certificate with your name on it.') +
        item('/assets/whats-new/whats-new-file-upload.png', 'File Upload in Chat', '', 'green', 'fa-cloud-arrow-up',
            'File Upload in Chat', 'NEW',
            'Share files and images directly in community chat and direct messages.') +
        item(null, '', '', 'violet', 'fa-gauge-high',
            'Performance Improvements', 'IMPROVED',
            'Faster loading, smoother navigation and many under-the-hood improvements.');

    var HTML =
        '<div class="wn-overlay" id="whatsNewOverlay" role="dialog" aria-modal="true" aria-label="What\'s New in Ghawy">' +
        '<div class="wn-modal">' +
        '<button class="wn-close" id="wnClose" aria-label="Close"><i class="fa-solid fa-xmark"></i></button>' +

        '<div class="wn-left">' +
        '<div class="wn-brand"><img src="/imgs/g-icon-logo.png" alt="Ghawy" /><span>Ghawy</span></div>' +
        '<div class="wn-headline"><span>What\'s New</span><br /><span class="wn-accent">in Ghawy</span><span class="wn-ver" data-no-i18n>V1.1</span></div>' +
        '<p class="wn-sub">We\'ve been working hard to bring you a better, faster and smarter learning experience. Check out what\'s new!</p>' +
        '<div class="wn-art"><svg viewBox="0 0 200 150" fill="none">' +
        '<rect class="wn-art-card" x="55" y="30" width="42" height="54" rx="5" stroke-width="1.5" transform="rotate(-12 76 57)" />' +
        '<rect class="wn-art-card" x="90" y="26" width="42" height="54" rx="5" stroke-width="1.5" transform="rotate(9 111 53)" />' +
        '<path class="wn-art-basket" d="M45 70 L100 62 L155 70 L145 118 Q143 124 137 124 L63 124 Q57 124 55 118 Z" stroke-width="1.5" />' +
        '<circle class="wn-art-dot" cx="75" cy="50" r="3.5" />' +
        '<rect class="wn-art-line1" x="100" y="44" width="18" height="2.5" rx="1" />' +
        '<rect class="wn-art-line2" x="100" y="52" width="12" height="2.5" rx="1" />' +
        '</svg></div>' +
        '<button class="wn-skip" id="wnSkip">Skip</button>' +
        '</div>' +

        '<div class="wn-right"><div class="wn-list">' + LIST + '</div>' +
        '<div class="wn-foot"><button class="wn-done" id="wnDone">Let\'s Go! <i class="fa-solid fa-arrow-right"></i></button></div>' +
        '</div>' +

        '</div></div>';

    var cssInjected = false;
    function injectCss() {
        if (cssInjected) return;
        cssInjected = true;
        var style = document.createElement('style');
        style.textContent = CSS;
        document.head.appendChild(style);
    }

    // Dashboard widget: carousel showing one update at a time, arrows + dots to navigate.
    function mountWidget() {
        var el = document.getElementById('wnWidgetList');
        if (!el) return;
        injectCss();
        el.classList.add('wn-car-viewport');
        el.innerHTML = '<div class="wn-car-clip"><div class="wn-car-track">' + LIST + '</div></div><div class="wn-car-dots"></div>';

        var track = el.querySelector('.wn-car-track');
        var dotsEl = el.querySelector('.wn-car-dots');
        var count = track.children.length;
        var idx = 0;

        var dots = [];
        for (var i = 0; i < count; i++) {
            (function (n) {
                var d = document.createElement('button');
                d.className = 'wn-car-dot';
                d.setAttribute('aria-label', 'Update ' + (n + 1));
                d.addEventListener('click', function () { go(n); });
                dotsEl.appendChild(d);
                dots.push(d);
            })(i);
        }

        function go(n) {
            idx = (n + count) % count;
            var rtl = getComputedStyle(el).direction === 'rtl';
            track.style.transform = 'translateX(' + (rtl ? idx * 100 : -idx * 100) + '%)';
            for (var j = 0; j < count; j++) dots[j].classList.toggle('active', j === idx);
        }

        var prev = document.getElementById('wnCarPrev');
        var next = document.getElementById('wnCarNext');
        if (prev) prev.addEventListener('click', function () { go(idx - 1); });
        if (next) next.addEventListener('click', function () { go(idx + 1); });

        go(0);
    }

    function mountPopup() {
        if (seen) return;
        injectCss();
        document.body.insertAdjacentHTML('beforeend', HTML);

        var ov = document.getElementById('whatsNewOverlay');

        function close() {
            ov.classList.remove('show');
            setTimeout(function () { ov.style.display = 'none'; }, 250);
            try { localStorage.setItem(KEY, VER); } catch (e) { }
            document.removeEventListener('keydown', onKey);
        }
        function onKey(e) { if (e.key === 'Escape') close(); }

        document.getElementById('wnClose').addEventListener('click', close);
        document.getElementById('wnSkip').addEventListener('click', close);
        document.getElementById('wnDone').addEventListener('click', close);
        ov.addEventListener('click', function (e) { if (e.target === ov) close(); });
        document.addEventListener('keydown', onKey);

        setTimeout(function () {
            ov.style.display = 'grid';
            requestAnimationFrame(function () { ov.classList.add('show'); });
        }, 900);
    }

    function init() {
        mountWidget();
        mountPopup();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
