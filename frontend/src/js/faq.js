// ═══ GHAWY FAQ — one source for the frequently-asked questions ═══
//
// The questions appear in TWO places: under the pricing cards on /pricing, and
// at the bottom of the home page. They used to be written out by hand in
// index.html, which is how they ended up wrong — the set that shipped talked
// about receiving login details on Whop and about a 3-day money-back
// guarantee, neither of which is how the platform works. Answers a visitor
// reads before paying cannot be allowed to drift, so they live here and both
// pages render from this array.
//
// Adding a question is one entry. Deleting one is one deletion. There is no
// second copy anywhere.
//
// The wording below is the client's, approved verbatim. If you are tempted to
// soften an answer, don't: "لأ، التقسيط مش متاح حالياً" being blunt is the
// point — the alternative is someone paying and then asking support.

(function () {
    'use strict';

    const FAQ = [
        {
            q: {
                ar: 'هل ليا وصول للمنصة بعد انتهاء فترة اشتراكي؟',
                en: 'Do I still have access after my subscription ends?',
            },
            a: {
                ar: 'لا، لما فترة اشتراكك تنتهي الوصول للمجتمع والكورسات بيتقفل لحد ما تجدد اشتراكك تاني.',
                en: 'No. When your subscription period ends, access to the community and the courses closes until you renew.',
            },
        },
        {
            q: {
                ar: 'هل كل الباقات فيها وصول لكل الكورسات؟',
                en: 'Do all plans include every course?',
            },
            a: {
                ar: 'أيوه، كل الباقات (شهري، ربع سنوي، سنوي) بتديك وصول كامل لكل الكورسات من غير أي استثناءات. الفرق بين الباقات في المدة والسعر، مش في المحتوى المتاح.',
                en: 'Yes. Every plan — monthly, quarterly and yearly — gives you full access to every course with no exceptions. The difference between plans is the duration and the price, not the content you can reach.',
            },
        },
        {
            q: {
                ar: 'هل محتاج خبرة سابقة في أي مجال؟',
                en: 'Do I need prior experience in anything?',
            },
            a: {
                ar: 'لا، إحنا بنبدأ معاك من الصفر من خلال كورس الأساسيات.',
                en: 'No. We start with you from zero through the foundations course.',
            },
        },
        {
            q: {
                ar: 'هل فيه فريق دعم لو احتجت مساعدة؟',
                en: 'Is there a support team if I need help?',
            },
            a: {
                ar: 'أيوه، معاك فريق دعم داخل المنصة هيرد على أي استفسار أو مشكلة في أسرع وقت.',
                en: 'Yes. There is a support team inside the platform that will answer any question or problem as quickly as possible.',
            },
        },
        {
            q: {
                ar: 'هل الكورسات مسجلة؟',
                en: 'Are the courses recorded?',
            },
            a: {
                ar: 'أيوه، كل الكورسات متسجلة وتقدر تتفرج عليها في أي وقت يناسبك.',
                en: 'Yes. Every course is recorded and you can watch it whenever suits you.',
            },
        },
        {
            q: {
                ar: 'هل ممكن أقسّط الاشتراك؟',
                en: 'Can I pay for the subscription in instalments?',
            },
            a: {
                ar: 'لأ، التقسيط مش متاح حالياً.',
                en: 'No. Instalments are not available at the moment.',
            },
        },
    ];

    // ─── Helpers ────────────────────────────────────────────────
    // Same three as catalog.js and reviews.js. Copied rather than imported so
    // this file works on its own — it is loaded by pages that do not load
    // either of those.

    // The language comes from i18n.js and nowhere else.
    //
    // This used to read localStorage('ghawy_lang') directly, and that is what
    // made the questions stay Arabic after a visitor pressed English: the
    // re-render below runs on `languagechange`, and at that moment storage
    // still held the language being left behind. The <html> lang attribute
    // that currentLang() reads is set before the event fires, so it is the
    // only source that is correct while a handler is running. The fallback is
    // for the (impossible in practice) case of this file loading without
    // i18n.js — Arabic, the site default.
    function currentLang() {
        return (typeof window.currentLang === 'function') ? window.currentLang() : 'ar';
    }

    /** Pick the current language out of an {ar, en} pair. */
    function L(pair) {
        if (pair == null) return '';
        if (typeof pair === 'string') return pair;
        const lang = currentLang();
        return pair[lang] || pair.ar || '';
    }

    function esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function i18nAttrs(pair) {
        if (pair == null) return '';
        if (typeof pair === 'string') return `data-ar="${esc(pair)}" data-en="${esc(pair)}"`;
        return `data-ar="${esc(pair.ar || '')}" data-en="${esc(pair.en || pair.ar || '')}"`;
    }

    // ─── Render ─────────────────────────────────────────────────

    /**
     * One question. The markup matches the .faq-item / .faq-q / .faq-a rules
     * that were already in main.css, so the accordion keeps the look it had.
     *
     * The question row is a div rather than a <button> for the same reason —
     * the CSS is written for a div and a button would need every one of its
     * defaults undone. What it does NOT inherit from the old markup is the
     * keyboard hole: role, tabindex and aria-expanded are set here, and the
     * handler below listens for Enter and Space, so the accordion works
     * without a mouse and announces its state.
     */
    function itemHTML(entry, index) {
        const id = `faqA${index}`;
        return `
    <div class="faq-item">
        <div class="faq-q" role="button" tabindex="0" aria-expanded="false" aria-controls="${id}">
            <span ${i18nAttrs(entry.q)}>${esc(L(entry.q))}</span>
            <span class="faq-icon" aria-hidden="true">+</span>
        </div>
        <div class="faq-a" id="${id}" ${i18nAttrs(entry.a)}>${esc(L(entry.a))}</div>
    </div>`;
    }

    /**
     * Fill a container with the accordion.
     *
     * The click handler is delegated onto the container instead of bound to
     * each row, so it survives a re-render on language change without leaving
     * a listener behind on every detached row.
     *
     * No skeleton and no empty state: FAQ is a constant in this file, not a
     * list arriving from an API, so there is no waiting and no "nothing here"
     * to represent.
     */
    function renderFAQ(el) {
        if (!el) return;
        el.classList.add('faq-list');
        el.innerHTML = FAQ.map(itemHTML).join('');
        if (el.dataset.faqBound) return;
        el.dataset.faqBound = '1';

        const toggle = (q) => {
            const item = q.parentElement;
            const wasOpen = item.classList.contains('open');
            el.querySelectorAll('.faq-item').forEach(other => {
                other.classList.remove('open');
                const head = other.querySelector('.faq-q');
                if (head) head.setAttribute('aria-expanded', 'false');
            });
            if (!wasOpen) {
                item.classList.add('open');
                q.setAttribute('aria-expanded', 'true');
            }
        };

        el.addEventListener('click', e => {
            const q = e.target.closest('.faq-q');
            if (q) toggle(q);
        });

        el.addEventListener('keydown', e => {
            if (e.key !== 'Enter' && e.key !== ' ') return;
            const q = e.target.closest('.faq-q');
            if (!q) return;
            e.preventDefault();   // Space would otherwise scroll the page
            toggle(q);
        });
    }

    // ─── Structured data ────────────────────────────────────────

    /**
     * Emit a schema.org FAQPage built from FAQ.
     *
     * Written here rather than typed into each page's <head> for the same
     * reason the questions themselves are: a hand-written copy in the markup
     * is a second answer to the same question, and the one Google shows in a
     * rich result would eventually stop matching the one on the page. This
     * cannot drift — it is the array.
     *
     * Only one page may claim FAQPage per URL, and both pages that render the
     * questions are separate URLs, so each gets its own. The guard is for the
     * re-render on `languagechange`: the tag is replaced, never stacked.
     */
    function injectFAQSchema() {
        const data = {
            '@context': 'https://schema.org',
            '@type': 'FAQPage',
            mainEntity: FAQ.map(entry => ({
                '@type': 'Question',
                name: L(entry.q),
                acceptedAnswer: { '@type': 'Answer', text: L(entry.a) },
            })),
        };
        let tag = document.getElementById('faqSchema');
        if (!tag) {
            tag = document.createElement('script');
            tag.type = 'application/ld+json';
            tag.id = 'faqSchema';
            document.head.appendChild(tag);
        }
        tag.textContent = JSON.stringify(data);
    }

    // ─── Auto-init ──────────────────────────────────────────────
    // A page wanting the questions drops `<div id="faqList">` in and loads
    // this file. Re-rendered on `languagechange` because the text is chosen by
    // L() at render time; the open row is deliberately not restored, since the
    // whole list is closed on a fresh render either way.
    function autoInit() {
        const el = document.getElementById('faqList');
        if (!el) return;
        renderFAQ(el);
        injectFAQSchema();
        document.addEventListener('languagechange', () => {
            renderFAQ(el);
            injectFAQSchema();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    window.GhawyFAQ = { FAQ, L, esc, i18nAttrs, itemHTML, renderFAQ, injectFAQSchema };
})();
