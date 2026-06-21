// ═══ LANGUAGE SYSTEM ═══
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

function applyLanguage(lang) {
    const config = translations[lang];
    const html = document.getElementById('htmlRoot') || document.documentElement;

    // 1. Set direction and lang
    html.setAttribute('dir', config.dir);
    html.setAttribute('lang', config.lang);

    // 2. Update all text elements
    document.querySelectorAll('[data-ar]').forEach(el => {
        el.textContent = lang === 'ar'
            ? el.getAttribute('data-ar')
            : el.getAttribute('data-en');
    });

    // 3. Update placeholders
    document.querySelectorAll('[data-ar-placeholder]').forEach(el => {
        el.placeholder = lang === 'ar'
            ? el.getAttribute('data-ar-placeholder')
            : el.getAttribute('data-en-placeholder');
    });

    // 4. Update toggle button (desktop + mobile)
    const toggleText = document.getElementById('langToggleText');
    if (toggleText) {
        toggleText.textContent = config.toggleBtn;
    }
    const mobileToggleText = document.getElementById('mobileLangToggleText');
    if (mobileToggleText) {
        mobileToggleText.textContent = config.toggleBtn;
    }

    // 5. Force reflow for flex containers (fix layout on toggle)
    document.querySelectorAll('.hero-split, .features-section, .pricing-section, .main-nav').forEach(el => {
        el.style.display = 'none';
        el.offsetHeight; // trigger reflow
        el.style.display = '';
    });

    // 6. Save preference
    localStorage.setItem('ghawy_lang', lang);
}

function toggleLanguage() {
    const current = localStorage.getItem('ghawy_lang') || 'ar';
    const next = current === 'ar' ? 'en' : 'ar';
    applyLanguage(next);
}

// On page load — default Arabic
(function () {
    const saved = localStorage.getItem('ghawy_lang') || 'ar';
    applyLanguage(saved);
})();
