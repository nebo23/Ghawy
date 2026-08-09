// ═══ GHAWY PRICING — one source for the plans, the checkout and the badges ═══
//
// The three plan cards used to be written out by hand in index.html, with a
// second copy of the amounts in an inline `pricingPlans` object right beneath
// them, and /pricing was a placeholder. Two copies of a price is one copy too
// many, so everything lives here now and both pages render from it:
//
//   index.html   → a SHORT version: the three cards, the methods row, and a
//                  link to /pricing for the detail.
//   pricing.html → the whole thing: cards, the comparison, the methods, FAQ.
//
// ── What the plans actually are ──
// All three give identical access. That is not a marketing line, it is the
// product: there is no content gate between the tiers, so the cards carry no
// feature list — a column of the same seven ticks three times over invites the
// reader to hunt for a difference that isn't there. What differs is the
// duration and the price per month, and that is what `compareHTML` lays out.
//
// ── Prices ──
//   monthly    600 EGP   — no discount, it is the reference price
//   quarterly  1200 EGP  — against 1800 (3 × 600)
//   yearly     3500 EGP  — against 7200 (12 × 600)
//
// `was` is therefore not an invented anchor: it is what the same period costs
// at the monthly rate, which is the only honest thing a struck-through number
// can mean here. Change `monthly.amount` and the two `was` values have to move
// with it — they are written out rather than computed so a price change is a
// deliberate edit in one place and not a surprise arithmetic result.
//
// ── Payment ──
// The Kashier and PayPal calls below are lifted from the inline script that
// used to sit in index.html, unchanged. What changed is what comes before
// them: the card's button no longer starts a payment. It opens a step with two
// options, because Instapay is manual, Egypt-only, and does NOT open access
// immediately — a visitor who picks it needs to be told that before they pay,
// not after.

(function () {
    'use strict';

    // ─── Plans ──────────────────────────────────────────────────
    // Order here is the order on screen, left to right: the cards grid is
    // forced to LTR so this reads the same in both languages. The client asked
    // for the 3-month card in the middle and the yearly one on the right.
    const PLAN_ORDER = ['monthly', 'quarterly', 'yearly'];

    const PLANS = {
        EGP: {
            monthly: {
                key: 'monthly',
                planKey: 'monthly_egp',
                amount: 600,
                was: null,                       // the reference price — nothing to strike
                currency: { ar: 'ج.م', en: 'EGP' },
                name: { ar: 'اشتراك شهري', en: 'Monthly subscription' },
                period: { ar: 'شهرياً', en: 'per month' },
                blurb: {
                    ar: 'تجربة شهرية مرنة علشان تبدأ وتشوف بنفسك',
                    en: 'A flexible month so you can start and see for yourself',
                },
                badge: null,
            },
            quarterly: {
                key: 'quarterly',
                planKey: 'quarterly_egp',
                amount: 1200,
                was: 1800,
                currency: { ar: 'ج.م', en: 'EGP' },
                name: { ar: 'اشتراك ربع سنوي', en: 'Quarterly subscription' },
                period: { ar: 'كل 3 شهور', en: 'every 3 months' },
                blurb: {
                    ar: 'أكثر اتزان، للي عايز يبني نتيجة حقيقية خلال أشهر',
                    en: 'The balanced one, for building a real result over months',
                },
                badge: { ar: 'الأكثر مبيعاً', en: 'Best seller' },
                // 1800 − 1200 = 600, which is exactly one month at the monthly price.
                extra: {
                    ar: 'كأنك واخد شهر مجاني',
                    en: 'Like getting a month free',
                },
            },
            yearly: {
                key: 'yearly',
                planKey: 'yearly_egp',
                amount: 3500,
                was: 7200,
                currency: { ar: 'ج.م', en: 'EGP' },
                name: { ar: 'اشتراك سنوي', en: 'Yearly subscription' },
                period: { ar: 'سنوياً', en: 'per year' },
                blurb: {
                    ar: 'أكثر توفير والتزام لجميع الكورسات',
                    en: 'The most saving and the most commitment, across every course',
                },
                badge: { ar: 'أفضل صفقة توفير', en: 'Best value' },
                // 7200 − 3500 = 3700, which is a bit over six months at 600.
                extra: {
                    ar: 'كأنك واخد 6 شهور مجاناً',
                    en: 'Like getting 6 months free',
                },
            },
        },
        // The USD ladder is the old one, converted at the same shape: it is
        // what PayPal is already configured for and the client's brief was
        // about the Egyptian prices. Flagged in the hand-over — if the EGP
        // prices move, someone has to decide whether these follow.
        USD: {
            monthly: {
                key: 'monthly',
                planKey: 'monthly_usd',
                amount: 20,
                was: null,
                currency: { ar: '$', en: '$' },
                name: { ar: 'اشتراك شهري', en: 'Monthly subscription' },
                period: { ar: 'شهرياً', en: 'per month' },
                blurb: {
                    ar: 'تجربة شهرية مرنة علشان تبدأ وتشوف بنفسك',
                    en: 'A flexible month so you can start and see for yourself',
                },
                badge: null,
            },
            quarterly: {
                key: 'quarterly',
                planKey: 'quarterly_usd',
                amount: 35,
                was: 60,
                currency: { ar: '$', en: '$' },
                name: { ar: 'اشتراك ربع سنوي', en: 'Quarterly subscription' },
                period: { ar: 'كل 3 شهور', en: 'every 3 months' },
                blurb: {
                    ar: 'أكثر اتزان، للي عايز يبني نتيجة حقيقية خلال أشهر',
                    en: 'The balanced one, for building a real result over months',
                },
                badge: { ar: 'الأكثر مبيعاً', en: 'Best seller' },
                // 60 − 35 = 25, against a 20 monthly — a month free, same as EGP.
                extra: {
                    ar: 'كأنك واخد شهر مجاني',
                    en: 'Like getting a month free',
                },
            },
            yearly: {
                key: 'yearly',
                planKey: 'yearly_usd',
                amount: 100,
                was: 240,
                currency: { ar: '$', en: '$' },
                name: { ar: 'اشتراك سنوي', en: 'Yearly subscription' },
                period: { ar: 'سنوياً', en: 'per year' },
                blurb: {
                    ar: 'أكثر توفير والتزام لجميع الكورسات',
                    en: 'The most saving and the most commitment, across every course',
                },
                badge: { ar: 'أفضل صفقة توفير', en: 'Best value' },
                extra: {
                    ar: 'كأنك واخد 6 شهور مجاناً',
                    en: 'Like getting 6 months free',
                },
            },
        },
    };

    // ─── The comparison ─────────────────────────────────────────
    // What replaced the tick lists. Every row is a real difference; there is
    // deliberately no row about content, because there is no difference in
    // content and a table saying "✓ ✓ ✓" three times is worse than no table.
    const COMPARE_ROWS = [
        {
            label: { ar: 'مدة الوصول', en: 'Access period' },
            monthly: { ar: 'شهر واحد', en: 'One month' },
            quarterly: { ar: '3 شهور', en: 'Three months' },
            yearly: { ar: 'سنة كاملة', en: 'A full year' },
        },
        {
            label: { ar: 'الكورسات المتاحة', en: 'Courses included' },
            monthly: { ar: 'كل الكورسات', en: 'Every course' },
            quarterly: { ar: 'كل الكورسات', en: 'Every course' },
            yearly: { ar: 'كل الكورسات', en: 'Every course' },
        },
        {
            label: { ar: 'المجتمع واللايفات والدعم', en: 'Community, lives and support' },
            monthly: { ar: 'كامل', en: 'Full' },
            quarterly: { ar: 'كامل', en: 'Full' },
            yearly: { ar: 'كامل', en: 'Full' },
        },
        {
            label: { ar: 'التكلفة الشهرية الفعلية', en: 'What it works out to per month' },
            monthly: { ar: '600 ج.م', en: '600 EGP' },
            quarterly: { ar: '400 ج.م', en: '400 EGP' },
            yearly: { ar: 'أقل من 300 ج.م', en: 'Under 300 EGP' },
        },
        {
            label: { ar: 'التوفير مقارنة بالشهري', en: 'Saving against monthly' },
            monthly: { ar: '—', en: '—' },
            quarterly: { ar: 'توفّر 600 ج.م', en: 'Save 600 EGP' },
            yearly: { ar: 'توفّر 3,700 ج.م', en: 'Save 3,700 EGP' },
        },
        {
            label: { ar: 'مناسب لمين', en: 'Who it suits' },
            monthly: { ar: 'لسه بتجرّب وعايز تشوف بنفسك', en: 'Still trying it out and want to see for yourself' },
            quarterly: { ar: 'داخل تتعلم وتطبّق على مدى شهور', en: 'Learning and applying it over months' },
            yearly: { ar: 'قرّرت إن ده مجالك وعايز أقل تكلفة', en: 'Decided this is your field and want the lowest cost' },
        },
    ];

    // ─── Payment methods ────────────────────────────────────────
    // The row under the cards. These are the real brand marks, served from
    // imgs/payment/ — trimmed of their padding and normalised to one height so
    // that a wide wordmark (Fawry, Etisalat) and a compact mark (InstaPay,
    // Mastercard) carry the same visual weight inside an identical chip.
    //
    // Six methods, six logos. Meeza used to sit here as a name on a chip
    // because the client's folder has no Meeza mark; it was dropped rather
    // than shown without one. (Card checkout still accepts Meeza — the
    // sentence under the card option says so.)
    //
    // Every mark is drawn for a white background (Visa blue, Fawry yellow,
    // Etisalat black/red, Vodafone red on white, InstaPay purple), so each one
    // sits in a white capsule — see .pay-method in main.css. The capsule is
    // pure white on purpose: vodafone-cash.jpg is a JPEG with a baked-in white
    // background, and any off-white would show it as a visible rectangle.
    const METHODS = [
        { logo: 'visa.png', label: { ar: 'فيزا', en: 'Visa' } },
        { logo: 'mastercard.svg', label: { ar: 'ماستركارد', en: 'Mastercard' } },
        { logo: 'instapay.png', label: { ar: 'انستاباي', en: 'InstaPay' } },
        { logo: 'vodafone-cash.jpg', label: { ar: 'فودافون كاش', en: 'Vodafone Cash' } },
        { logo: 'etisalat.png', label: { ar: 'اتصالات كاش', en: 'Etisalat Cash' } },
        { logo: 'fawry.png', label: { ar: 'فوري', en: 'Fawry' } },
    ];

    // ─── Helpers ────────────────────────────────────────────────

    // From i18n.js — see the note in faq.js. Reading localStorage here made
    // the plan cards repaint in the language the visitor had just left,
    // because `languagechange` fires before storage is written.
    function currentLang() {
        return (typeof window.currentLang === 'function') ? window.currentLang() : 'ar';
    }

    function L(pair) {
        if (pair == null) return '';
        if (typeof pair === 'string') return pair;
        return pair[currentLang()] || pair.ar || '';
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

    /** "3500" → "3,500". Plain amounts read as a number; prices read as money. */
    function money(n) {
        return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    }

    /**
     * EGP unless the visitor has been placed outside Egypt.
     *
     * `user_currency` is written by the country picker and the geo lookup in
     * main.js. Reading it rather than calling anything means this file has no
     * network I/O of its own and renders instantly.
     */
    function currency() {
        return localStorage.getItem('user_currency') === 'USD' ? 'USD' : 'EGP';
    }

    function plan(key, cur) {
        return PLANS[cur || currency()][key];
    }

    function planList(cur) {
        const c = cur || currency();
        return PLAN_ORDER.map(k => PLANS[c][k]);
    }

    // ─── Plan cards ─────────────────────────────────────────────

    /**
     * One plan card.
     *
     * No feature list: the plans are identical in what they unlock, so the
     * seven ticks that used to be here were the same seven ticks three times.
     * The card now carries the name, the price with its struck-through
     * reference, the one line the client wrote for it, and the button. The
     * real differences are in the comparison table under the cards.
     */
    function planCardHTML(p) {
        const featured = p.key === 'quarterly';
        const cur = esc(L(p.currency));
        return `
    <div class="pricing-card${featured ? ' pricing-card-featured' : ''}" data-plan-card="${esc(p.key)}">
        <div class="pricing-card-glow"></div>
        ${p.badge
                ? `<span class="pricing-badge" ${i18nAttrs(p.badge)}>${esc(L(p.badge))}</span>`
                : `<span class="pricing-badge pricing-row--empty" aria-hidden="true"></span>`}

        <h3 class="pricing-plan-name" ${i18nAttrs(p.name)}>${esc(L(p.name))}</h3>

        <div class="pricing-price-block">
            ${p.was ? `
            <div class="pricing-was">
                <s>${esc(money(p.was))} ${cur}</s>
            </div>` : `<div class="pricing-was pricing-row--empty" aria-hidden="true"></div>`}
            <div class="pricing-current">
                <span class="pricing-amount">${esc(money(p.amount))}</span>
                <div class="pricing-currency-col">
                    <span class="pricing-currency">${cur}</span>
                    <span class="pricing-period-label" ${i18nAttrs(p.period)}>${esc(L(p.period))}</span>
                </div>
            </div>
            ${p.extra
                ? `<span class="pricing-extra" ${i18nAttrs(p.extra)}>${esc(L(p.extra))}</span>`
                : `<span class="pricing-extra pricing-row--empty" aria-hidden="true"></span>`}
        </div>

        <p class="pricing-plan-sub" ${i18nAttrs(p.blurb)}>${esc(L(p.blurb))}</p>

        <button class="pricing-cta" type="button" data-plan-checkout="${esc(p.key)}"
                data-ar="اشترك الآن" data-en="Subscribe now">اشترك الآن</button>
    </div>`;
    }

    function renderPlans(el) {
        if (!el) return;
        el.classList.add('ghawy-pricing-cards');
        el.innerHTML = planList().map(planCardHTML).join('');
    }

    // ─── Comparison ─────────────────────────────────────────────

    /**
     * The comparison, twice into the same container: a table for wide screens
     * and one stacked block per plan for phones, because a four-column table
     * of Arabic sentences is unreadable at 360px. Both are built from
     * COMPARE_ROWS, so they cannot come to say different things — CSS decides
     * which one is on screen. Same trick /tracks uses for its comparison.
     */
    function compareHTML() {
        const plans = planList();
        const head = plans.map(p =>
            `<th ${i18nAttrs(p.name)}>${esc(L(p.name))}</th>`).join('');
        const rows = COMPARE_ROWS.map(r => `
        <tr>
            <th scope="row" ${i18nAttrs(r.label)}>${esc(L(r.label))}</th>
            ${PLAN_ORDER.map(k =>
            `<td ${i18nAttrs(r[k])}>${esc(L(r[k]))}</td>`).join('')}
        </tr>`).join('');

        const stacked = plans.map(p => `
        <div class="pc-stack-card">
            <h4 class="pc-stack-name" ${i18nAttrs(p.name)}>${esc(L(p.name))}</h4>
            <dl class="pc-stack-list">
                ${COMPARE_ROWS.map(r => `
                <div class="pc-stack-row">
                    <dt ${i18nAttrs(r.label)}>${esc(L(r.label))}</dt>
                    <dd ${i18nAttrs(r[p.key])}>${esc(L(r[p.key]))}</dd>
                </div>`).join('')}
            </dl>
        </div>`).join('');

        return `
    <div class="pc-table-wrap">
        <table class="pc-table">
            <thead><tr><th scope="col"><span class="sr-only" data-ar="الباقة" data-en="Plan">الباقة</span></th>${head}</tr></thead>
            <tbody>${rows}</tbody>
        </table>
    </div>
    <div class="pc-stack">${stacked}</div>`;
    }

    function renderCompare(el) {
        if (!el) return;
        el.classList.add('pc-compare');
        el.innerHTML = compareHTML();
    }

    // ─── Payment methods row ────────────────────────────────────

    function methodsHTML() {
        return METHODS.map(m => {
            // width/height match the .pay-method img box in CSS, so the row
            // reserves its full height before the images arrive and the page
            // does not jump. object-fit: contain does the actual fitting.
            return `
        <span class="pay-method">
            <img src="imgs/payment/${m.logo}" alt="${esc(L(m.label))}"
                 width="52" height="24" loading="lazy" decoding="async" />
        </span>`;
        }).join('');
    }

    function renderMethods(el) {
        if (!el) return;
        el.classList.add('pay-methods');
        el.innerHTML = methodsHTML();
    }

    // ─── Coupons ────────────────────────────────────────────────
    //
    // The rule this widget obeys, and the reason it looks thin: it does not
    // know what a discount is. It sends a typed string to the backend and
    // renders whatever comes back. There is no percentage in this file, no
    // multiplication, and no list of valid codes — a coupon that "worked"
    // according to JavaScript and then charged the full price would be the
    // 3500-vs-4000 bug rebuilt on the client side.
    //
    // `applied` below is display state only. The code is re-checked, and the
    // price recomputed, by /payment/kashier/create when the member actually
    // pays; what is on screen here can be stale and nothing breaks.

    let applied = null;   // the last successful preview, or null

    const COUPON_TEXT = {
        label:      { ar: 'عندك كوبون خصم؟', en: 'Have a discount code?' },
        placeholder:{ ar: 'اكتب الكود هنا', en: 'Enter your code' },
        apply:      { ar: 'تطبيق', en: 'Apply' },
        applying:   { ar: 'بنتأكد...', en: 'Checking…' },
        remove:     { ar: 'شيل الكوبون', en: 'Remove' },
        // The one sentence that is composed here rather than sent whole: the
        // percentage and the code both come from the backend response.
        line:       { ar: 'خصم {pct}% بكوبون {code}', en: '{pct}% off with code {code}' },
        empty:      { ar: 'اكتب كود الكوبون الأول', en: 'Type a code first' },
        failed:     { ar: 'مقدرناش نتأكد من الكوبون دلوقتي. جرّب تاني.', en: 'We could not check that code right now. Please try again.' },
        signin:     { ar: 'سجّل دخولك الأول عشان تستخدم كوبون', en: 'Sign in first to use a coupon' },
    };

    // Arabic wording for each refusal the backend can send. Keyed by its
    // `reason`, never by parsing its message — the page must not be the thing
    // that decides a coupon is finished.
    const COUPON_REASONS = {
        not_found:    { ar: 'الكود غلط', en: 'That code is not valid' },
        inactive:     { ar: 'الكوبون ده مش شغال دلوقتي', en: 'That code is not active right now' },
        exhausted:    { ar: 'الكوبون ده خلص', en: 'That code has run out' },
        already_used: { ar: 'إنت مستخدم الكوبون ده قبل كده', en: 'You have already used that code' },
    };

    function couponReasonText(reason) {
        return L(COUPON_REASONS[reason] || COUPON_TEXT.failed);
    }

    /** The applied code, for whoever is about to start a payment. */
    function appliedCode() {
        return applied ? applied.code : null;
    }

    function clearCoupon() {
        applied = null;
    }

    /**
     * Ask the backend what a code would do. Read-only — trying a code out must
     * not consume one of the thirty.
     */
    async function previewCoupon(code, planKey) {
        const token = typeof getToken === 'function' ? getToken() : localStorage.getItem('token');
        const apiBase = typeof API !== 'undefined' ? API : '/api';
        const res = await fetch(`${apiBase}/coupons/preview`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
            },
            // The code and the plan. No amount, no percentage — the server
            // holds both and we would only be telling it something it knows
            // better.
            body: JSON.stringify({ code: code, plan_key: planKey }),
        });
        if (!res.ok) throw new Error(`coupon preview ${res.status}`);
        return res.json();
    }

    function couponFieldHTML() {
        return `
        <div class="coupon-box" data-coupon-box>
            <label class="coupon-label" for="couponInput" ${i18nAttrs(COUPON_TEXT.label)}>${esc(L(COUPON_TEXT.label))}</label>
            <div class="coupon-row">
                <input class="coupon-input" id="couponInput" type="text" autocomplete="off"
                       spellcheck="false" dir="ltr" data-coupon-input
                       data-ar-placeholder="${esc(COUPON_TEXT.placeholder.ar)}"
                       data-en-placeholder="${esc(COUPON_TEXT.placeholder.en)}"
                       placeholder="${esc(L(COUPON_TEXT.placeholder))}">
                <button class="coupon-apply" type="button" data-coupon-apply
                        ${i18nAttrs(COUPON_TEXT.apply)}>${esc(L(COUPON_TEXT.apply))}</button>
            </div>
            <p class="coupon-note" data-coupon-note hidden></p>
        </div>`;
    }

    /**
     * Redraw the price summary and the coupon note from `applied`.
     *
     * When a coupon is on, the old price is struck through and the new one is
     * the prominent number — the member is about to be sent to a payment page
     * and the figure they see here has to be the figure they are charged.
     */
    function paintCouponState(root, p) {
        const note = root.querySelector('[data-coupon-note]');
        const box = root.querySelector('[data-coupon-box]');
        const summary = root.querySelector('[data-pay-summary]');
        const c = esc(L(p.currency));

        if (applied) {
            const line = L(COUPON_TEXT.line)
                .replace('{pct}', money(applied.discount_percent))
                .replace('{code}', applied.code);
            note.textContent = line;
            note.hidden = false;
            note.className = 'coupon-note is-on';
            if (box) box.classList.add('has-coupon');

            const name = esc(L(p.name));
            summary.innerHTML = `
                <span class="pay-sum-name">${name}</span>
                <span class="pay-sum-prices">
                    <s class="pay-was">${esc(money(applied.original_amount))} ${c}</s>
                    <strong class="pay-now">${esc(money(applied.final_amount))} ${c}</strong>
                </span>`;
        } else {
            note.hidden = true;
            note.textContent = '';
            if (box) box.classList.remove('has-coupon');
            paintPlainSummary(root, p);
        }
    }

    function paintPlainSummary(root, p) {
        const summary = root.querySelector('[data-pay-summary]');
        const c = esc(L(p.currency));
        const line = {
            ar: `${L(p.name)} — ${money(p.amount)} ${L(p.currency)}`,
            en: `${L(p.name)} — ${money(p.amount)} ${L(p.currency)}`,
        };
        summary.innerHTML = p.was
            ? `<span ${i18nAttrs(line)}>${esc(L(line))}</span> <s class="pay-was">${esc(money(p.was))} ${c}</s>`
            : `<span ${i18nAttrs(line)}>${esc(L(line))}</span>`;
    }

    /** The Apply button. Loading state on the button, result in the note. */
    async function handleApply(root, btn) {
        const input = root.querySelector('[data-coupon-input]');
        const note = root.querySelector('[data-coupon-note]');
        const planKey = root.dataset.plan;
        const p = plan(planKey);
        const code = (input.value || '').trim();

        if (!code) {
            note.textContent = L(COUPON_TEXT.empty);
            note.className = 'coupon-note is-off';
            note.hidden = false;
            input.focus();
            return;
        }

        const token = typeof getToken === 'function' ? getToken() : localStorage.getItem('token');
        if (!token) {
            if (typeof showToast === 'function') showToast(L(COUPON_TEXT.signin), 'error');
            return;
        }

        const original = btn.innerHTML;
        btn.disabled = true;
        btn.classList.add('is-loading');
        btn.textContent = L(COUPON_TEXT.applying);

        try {
            const result = await previewCoupon(code, p.planKey);
            if (result.applied) {
                applied = result;
                paintCouponState(root, p);
            } else {
                applied = null;
                // Straight from the backend's `reason`. The page never decides
                // for itself that a code is used up or finished.
                const msg = couponReasonText(result.reason);
                note.textContent = msg;
                note.className = 'coupon-note is-off';
                note.hidden = false;
                if (typeof showToast === 'function') showToast(msg, 'error');
                paintPlainSummary(root, p);
            }
        } catch (err) {
            console.error('Coupon check failed:', err);
            applied = null;
            if (typeof showToast === 'function') showToast(L(COUPON_TEXT.failed), 'error');
            paintPlainSummary(root, p);
        } finally {
            btn.disabled = false;
            btn.classList.remove('is-loading');
            btn.innerHTML = original;
        }
    }

    // ─── Checkout ───────────────────────────────────────────────

    /**
     * Send the visitor to Kashier (card / wallet).
     *
     * This is the old inline handler, moved but not rewritten. The one thing
     * it does differently is that the button that reaches it is now inside the
     * choice modal rather than on the card, so `trigger` is that button.
     *
     * There used to be a branch here that sent a USD visitor to
     * `payment.html?method=paypal`. Nothing on the other side handled it:
     * `window.handlePayPalPayment` was never defined anywhere in the repo, and
     * payment.html ignored `method` and rendered the EGP plans through Kashier
     * regardless. So it was a detour that landed on the same rail one page
     * later. Kashier takes the USD plan keys directly — PLAN_PRICES in
     * backend/app/routers/payment.py carries all six — so both currencies now
     * go straight through the call below.
     */
    async function startCardCheckout(planKey, trigger) {
        const cur = currency();
        const data = plan(planKey, cur);
        const token = typeof getToken === 'function' ? getToken() : localStorage.getItem('token');
        const apiBase = typeof API !== 'undefined' ? API : '/api';

        localStorage.setItem('ghawy_selected_plan', planKey);

        if (!token) {
            window.location.href = `register.html?plan=${encodeURIComponent(planKey)}`;
            return;
        }

        const original = trigger ? trigger.innerHTML : '';
        if (trigger) {
            trigger.disabled = true;
            trigger.textContent = currentLang() === 'en' ? 'Redirecting…' : 'جاري التحويل...';
        }

        try {
            const response = await fetch(`${apiBase}/payment/kashier/create`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
                body: JSON.stringify({
                    // amount and currency are ignored server-side (PLAN_PRICES
                    // is the source of truth) and are only still sent so an
                    // older backend keeps working. plan_key and coupon_code are
                    // the two fields that actually decide anything.
                    amount: data.amount,
                    currency: cur,
                    plan_key: data.planKey,
                    coupon_code: appliedCode(),
                }),
            });
            const result = await response.json();
            const checkoutUrl = result.payment_url || result.approval_url;

            if (response.ok && checkoutUrl) {
                // The backend takes the coupon decision again, under a lock, at
                // this moment — so a code that was fine when Apply was pressed
                // can be finished by now. Say so before the redirect rather
                // than letting the member discover it on the Kashier page,
                // where the amount would silently be the full price.
                if (result.coupon && !result.coupon.applied) {
                    if (typeof showToast === 'function') {
                        showToast(couponReasonText(result.coupon.reason), 'error');
                    }
                    applied = null;
                    // Hold them here for a moment so the toast is readable
                    // before the page navigates away.
                    await new Promise(r => setTimeout(r, 2200));
                }
                window.location.href = checkoutUrl;
                return;
            }
            throw new Error(result.detail || 'Payment unavailable');
        } catch (err) {
            const msg = currentLang() === 'en'
                ? 'We could not start the payment right now. Please try again.'
                : 'تعذر بدء عملية الدفع حالياً. من فضلك جرّب مرة أخرى.';
            if (typeof showToast === 'function') showToast(msg, 'error');
            else console.error(msg, err);
        } finally {
            if (trigger) {
                trigger.disabled = false;
                trigger.innerHTML = original;
            }
        }
    }

    function startInstapay(planKey) {
        localStorage.setItem('ghawy_selected_plan', planKey);
        const token = typeof getToken === 'function' ? getToken() : localStorage.getItem('token');
        if (!token) {
            window.location.href = `register.html?plan=${encodeURIComponent(planKey)}`;
            return;
        }
        // pay.js keys its price table by the bare cycle — monthly / quarterly /
        // yearly — not by the currency-suffixed key the cards use. The strip
        // below is what payment.html's goManual() used to do; it went missing
        // when that page was retired, and without it `monthly_egp` matched
        // nothing there: the transfer screen fell back to the backend's default
        // price, and no `plan` reached /manual-payments/submit at all, so an
        // approved yearly transfer was granted 30 days. renewal.js has always
        // done this correctly — manualUrl() in that file is the same line.
        const cycle = planKey.replace(/_(egp|usd)$/, '');
        // Carry the code across so nobody types it twice. It travels as a bare
        // string and /pay re-checks it against the backend on arrival — the URL
        // is not being trusted for anything, it is saving a member some typing.
        const code = appliedCode();
        const couponQS = code ? `&coupon=${encodeURIComponent(code)}` : '';
        window.location.href = `pay.html?plan=${encodeURIComponent(cycle)}${couponQS}`;
    }

    // ─── The choice step ────────────────────────────────────────

    let modal = null;

    /**
     * "اشترك الآن" opens this instead of starting a payment.
     *
     * Two options, and they are not equivalent: the card/wallet route opens
     * access the moment Kashier confirms, while Instapay is a receipt a human
     * reviews. Someone who pays by Instapay expecting to be let straight in
     * will file a support ticket within the minute, so the warning is on the
     * option itself and not in small print underneath it.
     *
     * Instapay is hidden outside Egypt — it is an Egyptian rail and there is
     * nothing a visitor abroad could do with it.
     */
    function buildModal() {
        const el = document.createElement('div');
        el.className = 'auth-modal-backdrop pay-choice-backdrop';
        el.innerHTML = `
        <div class="auth-modal pay-choice" role="dialog" aria-modal="true" aria-labelledby="payChoiceTitle">
            <button class="auth-modal-close" type="button" data-pay-close aria-label="Close">&times;</button>

            <h3 class="card-title" id="payChoiceTitle" data-ar="اختار طريقة الدفع"
                data-en="Choose how to pay">اختار طريقة الدفع</h3>
            <p class="card-sub" data-pay-summary></p>

            ${couponFieldHTML()}

            <button class="pay-option pay-option--primary" type="button" data-pay-card>
                <span class="pay-option-icon"><img src="imgs/payment/visa.png"
                        alt="فيزا" data-ar-alt="فيزا" data-en-alt="Visa"
                        width="40" height="26" loading="lazy" decoding="async" /></span>
                <span class="pay-option-body">
                    <span class="pay-option-title" data-ar="دفع بالبطاقة أو المحفظة"
                        data-en="Pay by card or wallet">دفع بالبطاقة أو المحفظة</span>
                    <span class="pay-option-note" data-ar="فيزا، ماستركارد، ميزة، ومحافظ الموبايل — متاح للمصريين ودولياً. الوصول بيتفتح فوراً بعد ما الدفع ينجح."
                        data-en="Visa, Mastercard, Meeza and mobile wallets — available in Egypt and internationally. Access opens the moment the payment succeeds.">فيزا،
                        ماستركارد، ميزة، ومحافظ الموبايل — متاح للمصريين ودولياً. الوصول بيتفتح فوراً بعد ما الدفع
                        ينجح.</span>
                </span>
            </button>

            <button class="pay-option" type="button" data-pay-instapay>
                <span class="pay-option-icon"><img src="imgs/payment/instapay.png"
                        alt="انستاباي" data-ar-alt="انستاباي" data-en-alt="InstaPay"
                        width="40" height="26" loading="lazy" decoding="async" /></span>
                <span class="pay-option-body">
                    <span class="pay-option-title" data-ar="انستاباي يدوي — للمصريين بس"
                        data-en="Manual InstaPay — Egypt only">انستاباي يدوي — للمصريين بس</span>
                    <span class="pay-option-warn">
                        <i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i>
                        <span data-ar="الدخول مش فوري: بتحوّل وترفع صورة الإيصال، وإحنا بنراجعه بنفسنا وبنفتحلك الوصول بعد ما نتأكد."
                            data-en="Access is NOT instant: you transfer, upload the receipt, and we review it by hand and open your access once it checks out.">الدخول
                            مش فوري: بتحوّل وترفع صورة الإيصال، وإحنا بنراجعه بنفسنا وبنفتحلك الوصول بعد ما نتأكد.</span>
                    </span>
                </span>
            </button>
        </div>`;
        document.body.appendChild(el);

        const close = () => closeCheckout();
        el.querySelector('[data-pay-close]').addEventListener('click', close);
        el.addEventListener('click', e => { if (e.target === el) close(); });
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape' && el.classList.contains('open')) close();
        });

        el.querySelector('[data-pay-card]').addEventListener('click', function () {
            startCardCheckout(el.dataset.plan, this);
        });
        el.querySelector('[data-pay-instapay]').addEventListener('click', () => {
            startInstapay(el.dataset.plan);
        });

        const applyBtn = el.querySelector('[data-coupon-apply]');
        applyBtn.addEventListener('click', function () { handleApply(el, this); });
        // Enter in the field applies rather than submitting anything — the box
        // sits inside a dialog, and a stray form submit would close it.
        el.querySelector('[data-coupon-input]').addEventListener('keydown', e => {
            if (e.key === 'Enter') { e.preventDefault(); handleApply(el, applyBtn); }
        });

        return el;
    }

    function closeCheckout() {
        if (!modal) return;
        modal.classList.remove('open');
        document.body.style.overflow = '';
    }

    function openCheckout(planKey) {
        if (!modal) modal = buildModal();
        const cur = currency();
        const p = plan(planKey, cur);
        if (!p) return;

        const planChanged = modal.dataset.plan !== planKey;
        modal.dataset.plan = planKey;

        // A coupon is a percentage off ONE plan's price, and the applied state
        // carries that plan's numbers. Switching plans has to drop it, or the
        // modal would show a yearly discount against a monthly price.
        if (planChanged) {
            clearCoupon();
            const input = modal.querySelector('[data-coupon-input]');
            if (input) input.value = '';
        }

        // The summary repeats the price the visitor just clicked, with the
        // struck-through reference still attached — the last screen before a
        // payment is the worst place to make someone remember a number. With a
        // coupon on, the struck-through number becomes the list price and the
        // prominent one is what they will actually be charged.
        paintCouponState(modal, p);

        // Instapay is an Egyptian rail; abroad there is nothing behind it.
        modal.querySelector('[data-pay-instapay]').hidden = cur !== 'EGP';

        if (typeof window.applyLanguageTo === 'function') window.applyLanguageTo(modal);
        modal.classList.add('open');
        document.body.style.overflow = 'hidden';
        modal.querySelector('[data-pay-card]').focus();
    }

    // ─── Wiring ─────────────────────────────────────────────────
    // Delegated from the document, so it covers cards rendered now, cards
    // re-rendered on a language change, and the shortened set on the home page
    // — one listener for all of them.
    document.addEventListener('click', e => {
        const btn = e.target.closest('[data-plan-checkout]');
        if (!btn) return;
        openCheckout(btn.dataset.planCheckout);
    });

    // ─── Auto-init ──────────────────────────────────────────────
    // A page drops in the containers it wants and loads this file:
    //   #pricingPlans   → the three cards
    //   #pricingCompare → the comparison
    //   #payMethods     → the accepted-methods row (can appear more than once,
    //                     so this one is a class as well)
    function paint() {
        renderPlans(document.getElementById('pricingPlans'));
        renderCompare(document.getElementById('pricingCompare'));
        document.querySelectorAll('#payMethods, [data-pay-methods]').forEach(renderMethods);
        // The buttons carry literal Arabic with data-ar/data-en, and i18n.js
        // has already made its pass by now.
        if (typeof window.applyLanguageTo === 'function') {
            ['pricingPlans', 'pricingCompare'].forEach(id => {
                const el = document.getElementById(id);
                if (el) window.applyLanguageTo(el);
            });
            document.querySelectorAll('#payMethods, [data-pay-methods]')
                .forEach(el => window.applyLanguageTo(el));
        }
    }

    /**
     * Kashier bounced the payment.
     *
     * GET /api/payment/kashier/fail sends the visitor back here with
     * `?error=failed`. The page it used to land on read that param and did
     * nothing with it, so a failed card looked identical to arriving on the
     * plans page by choice. Say it out loud, then strip the param so a reload
     * or a back-button does not re-announce a failure that is over.
     */
    function reportRedirectError() {
        const params = new URLSearchParams(location.search);
        if (params.get('error') !== 'failed') return;

        const msg = currentLang() === 'en'
            ? 'The payment did not go through. Nothing was charged — you can try again or pay by InstaPay.'
            : 'الدفع ماتمّش. مااتخصمش منك حاجة — تقدر تجرّب تاني أو تدفع بانستاباي.';
        if (typeof showToast === 'function') showToast(msg, 'error');

        params.delete('error');
        const qs = params.toString();
        history.replaceState({}, document.title, location.pathname + (qs ? '?' + qs : ''));
    }

    function autoInit() {
        paint();
        reportRedirectError();
        document.addEventListener('languagechange', paint);
        // The modal's summary and coupon note are composed in JS from backend
        // numbers, so i18n.js's attribute pass cannot retranslate them — they
        // have to be rebuilt.
        document.addEventListener('languagechange', () => {
            if (modal && modal.classList.contains('open')) {
                const p = plan(modal.dataset.plan);
                if (p) paintCouponState(modal, p);
            }
        });
        // The country picker and the geo lookup both write `user_currency` and
        // then call applyCurrencyUI. Repainting on that is what moves the cards
        // from EGP to USD without a reload.
        const original = window.applyCurrencyUI;
        if (typeof original === 'function' && !original.ghawyPricingWrapped) {
            window.applyCurrencyUI = function () {
                const out = original.apply(this, arguments);
                paint();
                return out;
            };
            window.applyCurrencyUI.ghawyPricingWrapped = true;
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInit);
    } else {
        autoInit();
    }

    window.GhawyPricing = {
        PLANS, PLAN_ORDER, COMPARE_ROWS, METHODS,
        L, esc, i18nAttrs, money, currency, plan, planList,
        planCardHTML, renderPlans,
        compareHTML, renderCompare,
        methodsHTML, renderMethods,
        openCheckout, closeCheckout, startCardCheckout, startInstapay,
        paint, reportRedirectError,
        // Shared with pay.js, which runs the same coupon rules on the Instapay
        // screen. Exported rather than copied so there is one set of refusal
        // wordings and one preview call for the whole site.
        COUPON_TEXT, COUPON_REASONS, couponReasonText, previewCoupon,
        appliedCode, clearCoupon,
    };
})();
