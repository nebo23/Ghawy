// ═══ LANGUAGE SYSTEM ═══
// Supports two attribute systems:
//   1. data-ar / data-en            (used by index.html)
//   2. data-i18n / data-i18n-placeholder  (used by login, register, payment)

const translations = {
    ar: {
        dir: 'rtl',
        lang: 'ar',
        toggleBtn: 'English',
        fontFamily: "'Cairo', sans-serif",
    },
    en: {
        dir: 'ltr',
        lang: 'en',
        toggleBtn: 'عربي',
        fontFamily: "'Cairo', sans-serif",
    }
};

// ─── Translation dictionary for data-i18n keys ──────────────
const i18nDict = {
    // login.html
    loginTitle:       { ar: 'تسجيل الدخول',              en: 'Sign In' },
    email:            { ar: 'البريد الإلكتروني',           en: 'Email' },
    emailPlaceholder: { ar: 'example@gmail.com',           en: 'example@gmail.com' },
    currentPassword:  { ar: 'كلمة المرور',                en: 'Password' },
    passwordPlaceholder:{ ar: '••••••••',                 en: '••••••••' },
    enterBtn:         { ar: 'دخول',                       en: 'Sign In' },
    orDivider:        { ar: 'أو',                         en: 'or' },
    googleLogin:      { ar: 'الدخول باستخدام جوجل',       en: 'Continue with Google' },
    dontHaveAccount:  { ar: 'مش عندك حساب؟',             en: "Don't have an account?" },
    registerNow:      { ar: 'سجّل الآن',                  en: 'Register Now' },
    // register.html
    register:         { ar: 'إنشاء حساب',                 en: 'Create Account' },
    createAccountSub: { ar: 'سجّل الآن وابدأ رحلتك مع الـ AI', en: 'Register now and start your AI journey' },
    alreadyHaveAccount:{ ar: 'عندك حساب بالفعل؟',        en: 'Already have an account?' },
    loginNow:         { ar: 'سجّل دخولك',                 en: 'Sign In' },
    // payment.html
    logout:           { ar: 'تسجيل الخروج',               en: 'Logout' },
    subscriptionPlan: { ar: 'خطة الاشتراك',               en: 'Subscription Plan' },
    oneSubOpensAll:   { ar: 'اشتراك واحد يفتح لك جميع المحتويات', en: 'One subscription unlocks all content' },
    accessAll:        { ar: 'وصول لجميع الكورسات والشروحات', en: 'Access to all courses and content' },
    hours:            { ar: '60+ ساعة من المحتوى الحصري', en: '60+ hours of exclusive content' },
    community:        { ar: 'مجتمع ومتابعة شخصية',        en: 'Community & personal mentoring' },
    newContent:       { ar: 'محتوى جديد بإستمرار',        en: 'Constantly updated content' },
    subscribeNow:     { ar: 'انضم الآن 🚀',               en: 'Join Now 🚀' },
    securePay:        { ar: '🔒 الدفع آمن 100% عبر Kashier', en: '🔒 100% secure payment via Kashier' },
};

function applyLanguage(lang) {
    const config = translations[lang];
    if (!config) return;
    const html = document.getElementById('htmlRoot') || document.documentElement;

    // 1. Set direction and lang attribute
    html.setAttribute('dir', config.dir);
    html.setAttribute('lang', config.lang);

    // 2. data-ar / data-en (index.html style)
    document.querySelectorAll('[data-ar]').forEach(el => {
        el.textContent = lang === 'ar'
            ? el.getAttribute('data-ar')
            : el.getAttribute('data-en');
    });

    // 3. data-ar-placeholder (index.html style)
    document.querySelectorAll('[data-ar-placeholder]').forEach(el => {
        el.placeholder = lang === 'ar'
            ? el.getAttribute('data-ar-placeholder')
            : el.getAttribute('data-en-placeholder');
    });

    // 4. data-i18n (login / register / payment style)
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        const entry = i18nDict[key];
        if (!entry) return;
        // loginTitle has an inner <span> — use innerHTML to preserve styling
        if (key === 'loginTitle') {
            el.innerHTML = lang === 'ar'
                ? 'تسجيل <span class="cyan">الدخول</span>'
                : 'Sign <span class="cyan">In</span>';
        } else {
            el.textContent = entry[lang] || entry['ar'];
        }
    });

    // 5. data-i18n-placeholder (login / register style)
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        const entry = i18nDict[key];
        if (entry) el.placeholder = entry[lang] || entry['ar'];
    });

    // 6. Update toggle button (desktop + mobile)
    const toggleText = document.getElementById('langToggleText');
    if (toggleText) toggleText.textContent = config.toggleBtn;

    const mobileToggleText = document.getElementById('mobileLangToggleText');
    if (mobileToggleText) mobileToggleText.textContent = config.toggleBtn;

    // 7. Force reflow for flex containers (fix RTL/LTR layout shift)
    document.querySelectorAll('.hero-split, .features-section, .pricing-section, .main-nav').forEach(el => {
        el.style.display = 'none';
        el.offsetHeight;
        el.style.display = '';
    });

    // 8. Save preference — persists across all pages
    localStorage.setItem('ghawy_lang', lang);
}

function toggleLanguage() {
    const current = localStorage.getItem('ghawy_lang') || 'ar';
    const next = current === 'ar' ? 'en' : 'ar';
    applyLanguage(next);
}

// On every page load — apply saved preference (default Arabic)
(function () {
    const saved = localStorage.getItem('ghawy_lang') || 'ar';
    applyLanguage(saved);
})();
