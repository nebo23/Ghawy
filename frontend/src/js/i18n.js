// ═══ LANGUAGE SYSTEM — single source of truth ═══
//
// This file is THE language engine for the whole site (landing page, auth
// funnel, payment pages, community pages). It used to be duplicated as an
// inline <script> inside index.html with its own storage key, which meant a
// language picked on the landing page never reached the register page (and
// vice-versa). Everything now lives here.
//
// Storage key: 'ghawy_lang' — the ONLY key. The legacy 'ghawy_lang_pref' is
// migrated once on load so users who already picked a language keep it.
//
// Default: Arabic on every page, with no per-page exceptions. An explicit user
// choice (the toggle button) always wins over the default.
//
// Supported markup:
//   data-ar / data-en                 → text swap        (landing-page style)
//   data-ar-placeholder / -en-        → placeholder swap
//   data-ar-alt / -en-alt             → alt swap on an <img>
//   data-html="true"                  → use innerHTML instead of textContent
//   data-i18n="key"                   → text from i18nDict (auth/funnel style)
//   data-i18n-html="true"             → that key's value is HTML
//   data-i18n-placeholder="key"       → placeholder from i18nDict
//   data-i18n-title="key"             → title attribute from i18nDict

// ─── One-time migration off the old key ─────────────────────
(function migrateLegacyLangKey() {
    try {
        const legacy = localStorage.getItem('ghawy_lang_pref');
        if (legacy === 'ar' || legacy === 'en') {
            localStorage.setItem('ghawy_lang', legacy);
        }
        if (legacy !== null) localStorage.removeItem('ghawy_lang_pref');
    } catch (e) { /* private mode / storage disabled — defaults still work */ }
})();

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
    // ── login.html ──
    loginPageTitle:   { ar: 'تسجيل الدخول — Ghawy',        en: 'Sign In — Ghawy' },
    loginTitle:       { ar: 'تسجيل <span class="cyan">الدخول</span>', en: 'Sign <span class="cyan">In</span>' },
    backHome:         { ar: 'رجوع',                        en: 'Back' },
    email:            { ar: 'البريد الإلكتروني',            en: 'Email' },
    emailPlaceholder: { ar: 'example@gmail.com',           en: 'example@gmail.com' },
    currentPassword:  { ar: 'كلمة المرور',                 en: 'Password' },
    passwordPlaceholder: { ar: '••••••••',                 en: '••••••••' },
    showPassword:     { ar: 'إظهار كلمة المرور',           en: 'Show password' },
    enterBtn:         { ar: 'دخول',                        en: 'Sign In' },
    orDivider:        { ar: 'أو',                          en: 'or' },
    googleLogin:      { ar: 'الدخول باستخدام جوجل',        en: 'Continue with Google' },
    dontHaveAccount:  { ar: 'مش عندك حساب؟',              en: "Don't have an account?" },
    registerNow:      { ar: 'سجّل دلوقتي',                 en: 'Register Now' },
    okLoggedIn:       { ar: 'تم تسجيل الدخول ✅ جاري التحويل...', en: 'Logged in successfully! ✅ Redirecting...' },

    // ── register.html ──
    registerPageTitle: { ar: 'إنشاء حساب — Ghawy',         en: 'Create Your Account — Ghawy' },
    register:         { ar: 'إنشاء حساب',                  en: 'Create Account' },
    createAccountSub: { ar: 'سجّل الآن وابدأ رحلتك مع الـ AI', en: 'Register now and start your AI journey' },
    setYourPassword:  { ar: 'اختار كلمة المرور',           en: 'Set Your Password' },
    setYourPasswordSub: { ar: 'أهلاً بيك تاني! اختار كلمة مرور عشان تكمّل حسابك.', en: 'Welcome back! Set a password to complete your account setup.' },
    firstName:        { ar: 'الاسم الأول',                 en: 'First Name' },
    firstNamePlaceholder: { ar: 'مثلا: محمد',              en: 'e.g. Mohamed' },
    lastName:         { ar: 'الاسم الأخير',                en: 'Last Name' },
    lastNamePlaceholder:  { ar: 'مثلا: احمد',              en: 'e.g. Ahmed' },
    emailAddress:     { ar: 'البريد الإلكتروني',            en: 'Email Address' },
    emailAddressPlaceholder: { ar: 'اكتب بريدك الإلكتروني', en: 'Enter your email address' },
    password:         { ar: 'كلمة المرور',                 en: 'Password' },
    passwordCreatePlaceholder: { ar: 'اختر كلمة مرور قوية', en: 'Create a strong password' },
    passwordStrength: { ar: 'قوة كلمة المرور:',            en: 'Password Strength:' },
    strengthWeak:     { ar: 'ضعيفة',                       en: 'Weak' },
    strengthMedium:   { ar: 'متوسطة',                      en: 'Medium' },
    strengthStrong:   { ar: 'قوية',                        en: 'Strong' },
    checkLength:      { ar: '8 حروف على الأقل',            en: 'At least 8 characters' },
    checkCase:        { ar: 'حروف كبيرة وصغيرة',           en: 'Contains uppercase and lowercase letters' },
    checkNumber:      { ar: 'رقم أو رمز خاص',              en: 'Contains number or special character' },
    agreeTerms:       {
        ar: 'أوافق على <a href="terms.html" target="_blank" class="text-brand hover:underline mx-1"><u>الشروط والأحكام</u></a> و<a href="privacy.html" target="_blank" class="text-brand hover:underline mx-1"><u>سياسة الخصوصية</u></a>',
        en: 'I agree to the <a href="terms.html" target="_blank" class="text-brand hover:underline mx-1"><u>Terms &amp; Conditions</u></a> and <a href="privacy.html" target="_blank" class="text-brand hover:underline mx-1"><u>Privacy Policy</u></a>'
    },
    signUpNow:        {
        ar: 'إنشاء الحساب <i class="fa-solid fa-arrow-left" style="margin-inline-start:6px"></i>',
        en: 'Sign Up Now <i class="fa-solid fa-arrow-right" style="margin-inline-start:6px"></i>'
    },
    orDividerCaps:    { ar: 'أو',                          en: 'OR' },
    googleSignUp:     { ar: 'التسجيل باستخدام جوجل',       en: 'Sign in with Google' },
    alreadyHaveAccount: { ar: 'عندك حساب بالفعل؟',        en: 'Already have an account?' },
    loginNow:         { ar: 'سجّل دخولك',                  en: 'Sign In' },
    // register.js runtime messages
    errWeakPassword:  { ar: 'من فضلك اختر كلمة مرور قوية.', en: 'Please create a strong password.' },
    errTermsRequired: { ar: 'لازم توافق على الشروط والأحكام.', en: 'You must agree to the Terms and Conditions.' },
    errNameRequired:  { ar: 'من فضلك اكتب اسمك الأول والأخير (حرفين على الأقل لكل واحد).', en: 'Please enter your first and last name (at least 2 characters each).' },
    errCaptcha:       { ar: "من فضلك أكمل التحقق من إنك مش روبوت.", en: "Please complete the 'I'm not a robot' verification." },
    errGeneric:       { ar: 'حصل خطأ. حاول تاني.',         en: 'An error occurred. Please try again.' },
    errFakeEmail:     { ar: 'من فضلك سجّل بإيميل حقيقي — الإيميلات المؤقتة أو التجريبية مش مقبولة.', en: 'Please sign up with a real email — temporary or test addresses are not accepted.' },
    errFillAllFields: { ar: 'من فضلك املا كل الخانات.',    en: 'Please fill all fields' },
    errWrongCredentials: { ar: 'إيميل أو باسورد غلط',      en: 'Wrong email or password' },
    errNoConnection:  { ar: 'مفيش اتصال بالسيرفر.',        en: 'No connection to the server.' },
    errGoogleFailed:  { ar: 'مكملناش تسجيل الدخول بجوجل. جرّب تاني.', en: "We couldn't finish signing you in with Google. Please try again." },
    errGoogleUnverified: { ar: 'إيميل جوجل ده لسه متأكدش. أكّده من جوجل الأول وبعدين جرّب تاني.', en: 'That Google address is not verified yet. Verify it with Google, then try again.' },
    okAccountCreated: { ar: 'تم إنشاء الحساب بنجاح! جاري التحويل...', en: 'Account created successfully! Redirecting...' },
    okSetupComplete:  { ar: 'تم! جاري التحويل...',         en: 'Setup complete! Redirecting...' },
    inviteInvalid:    { ar: 'لينك الدعوة مش صالح أو انتهت صلاحيته.', en: 'Invalid or expired invite link' },
    inviteFailed:     { ar: 'مقدرناش نتأكد من لينك الدعوة.', en: 'Failed to verify invite link' },
    welcomeName:      { ar: 'أهلاً',                       en: 'Welcome' },
    inviteWelcomeSub: { ar: 'اختار كلمة مرور عشان تكمّل تسجيلك', en: 'Choose a password to complete your registration' },
    completeRegistration: { ar: 'إكمال التسجيل',           en: 'Complete Registration' },

    // ── pay.html (Instapay / Vodafone Cash) ──
    // /pay serves both manual rails off one page. The keys below are the
    // Instapay wording it ships with; pay.js points the same elements at the
    // `…Vf` variants further down when ?method=vodafone, so a language toggle
    // after that keeps whichever rail is on screen.
    payPageTitle:     { ar: 'الدفع عبر انستاباي — Ghawy',   en: 'Pay with Instapay — Ghawy' },
    backToHome:       { ar: 'رجوع للرئيسية',               en: 'Back to Home' },
    payTitle:         { ar: 'انضم لـ غاوي عبر انستاباي',   en: 'Join Ghawy via Instapay' },
    paySubtitle:      { ar: 'اتمّم الدفع بأمان وارفع إيصال التحويل عشان تدخل على طول.', en: 'Complete your payment securely and submit your receipt to get instant access.' },
    payStep1:         { ar: 'الخطوة 1',                    en: 'Step 1' },
    payStep1Title:    { ar: 'حوّل المبلغ',                 en: 'Transfer the amount' },
    payStep1Desc:     { ar: 'ابعت المبلغ بالظبط عبر انستاباي على الرقم اللي تحت، واحتفظ بسكرين شوت الإيصال.', en: 'Send the exact amount via Instapay to the number below. Keep the receipt screenshot.' },
    payAmountDue:     { ar: 'المبلغ المطلوب',              en: 'Amount Due' },
    payInstapayNumber:{ ar: 'رقم انستاباي',                en: 'Instapay Number' },
    payCopy:          { ar: 'نسخ',                         en: 'Copy' },
    payCopied:        { ar: 'اتنسخ',                       en: 'Copied' },
    payNowInstapay:   { ar: 'ادفع دلوقتي عبر انستاباي',    en: 'Pay now via Instapay' },
    // Vodafone Cash — the same five strings, for the same five elements.
    payPageTitleVf:   { ar: 'الدفع عبر فودافون كاش — Ghawy', en: 'Pay with Vodafone Cash — Ghawy' },
    payTitleVf:       { ar: 'انضم لـ غاوي عبر فودافون كاش', en: 'Join Ghawy via Vodafone Cash' },
    payStep1DescVf:   { ar: 'ابعت المبلغ بالظبط من محفظة فودافون كاش على الرقم اللي تحت، واحتفظ بسكرين شوت الإيصال.', en: 'Send the exact amount from your Vodafone Cash wallet to the number below. Keep the receipt screenshot.' },
    payVodafoneNumber:{ ar: 'رقم فودافون كاش',             en: 'Vodafone Cash Number' },
    payNowVodafone:   { ar: 'افتح فودافون كاش (‎*9#‎)',      en: 'Open Vodafone Cash (*9#)' },
    payScreenshotWarn:{ ar: 'خد بالك: لازم تصوّر شاشة نجاح التحويل.', en: 'Please make sure to screenshot the successful transfer screen.' },
    payStep2:         { ar: 'الخطوة 2',                    en: 'Step 2' },
    payStep2Title:    { ar: 'ارفع الإيصال',                en: 'Submit your receipt' },
    payStep2Desc:     { ar: 'اكتب بياناتك وارفع صورة الإيصال.', en: 'Fill in your details and upload the payment screenshot.' },
    payReceiptLabel:  { ar: 'صورة الإيصال *',              en: 'Receipt Screenshot *' },
    payDropHere:      { ar: 'اضغط أو اسحب الإيصال هنا',    en: 'Click or drag receipt here' },
    payFileHint:      { ar: 'JPG أو PNG أو PDF (5 ميجا كحد أقصى)', en: 'JPG, PNG, PDF (Max 5MB)' },
    paySubmit:        { ar: 'إرسال الطلب',                 en: 'Submit Payment' },
    // The receipt preview. The X that used to sit on the uploaded file read as
    // an error to people who had just uploaded successfully, so the state is
    // spelled out instead: the image, then "تم رفع الصورة", then a button that
    // says what it does.
    payUploaded:      { ar: 'تم رفع الصورة',               en: 'Image uploaded' },
    payUploadedFile:  { ar: 'تم رفع الملف',                en: 'File uploaded' },
    payChangeImage:   { ar: 'تغيير الصورة',                en: 'Change image' },
    payChangeFile:    { ar: 'تغيير الملف',                 en: 'Change file' },
    paySuccessTitle:  { ar: 'تم إرسال الطلب!',             en: 'Request Submitted!' },
    paySuccessDesc:   { ar: 'هنراجع طلبك وهنبعتلك تأكيد على الإيميل.', en: 'We will review your request and send you a confirmation by email.' },
    payRefId:         { ar: 'رقم الطلب:',                  en: 'Reference ID:' },
    payReviewWindow:  { ar: 'عادة نقبل طلبك من ثواني إلى 12 ساعة كحد أقصى.', en: 'We usually approve within seconds, and 12 hours at the very most.' },
    payDelayHelp:     { ar: 'لو اتأخرنا أو حصلت أي مشكلة، تواصل مع الدعم على', en: 'If we are late or anything goes wrong, contact support on' },
    payOrEmailUs:     { ar: 'أو على الإيميل',              en: 'or by email at' },
    payReturnHome:    { ar: 'الرجوع للصفحة الرئيسية',      en: 'Return to Homepage' },
    // The success line comes in two shapes. pay.js swaps the key on the same
    // element (the way renderPreview swaps image/file wording) so a language
    // toggle after submitting keeps whichever shape is on screen. The address
    // itself lives in its own dir="ltr" span — never interpolated into the
    // sentence, because an LTR address inside an Arabic line reorders.
    paySuccessDescEmail: { ar: 'هنراجع طلبك وهنبعتلك تأكيد على الإيميل بتاعك:', en: 'We will review your request and send a confirmation to your email:' },

    // ── pay.html → blocked (already-submitted / still-subscribed) ──
    payBlockedPendingTitle: { ar: 'إنت سجّلت طلب خلاص',      en: 'You have already submitted a request' },
    payBlockedPendingDesc:  { ar: 'طلبك لسه تحت المراجعة، فمش محتاج ترفع إيصال تاني.', en: 'Your request is still under review, so there is no need to upload another receipt.' },
    payBlockedEmailNote:    { ar: 'أول ما نقبله هنبعتلك على الإيميل بتاعك:', en: 'As soon as it is approved we will email you at:' },
    payBlockedEmailPlain:   { ar: 'أول ما نقبله هنبعتلك على الإيميل.', en: 'As soon as it is approved we will email you.' },
    payBlockedActiveTitle:  { ar: 'اشتراكك لسه شغال',        en: 'Your subscription is still active' },
    payBlockedActiveDesc:   { ar: 'مش محتاج تدفع تاني دلوقتي. تقدر تكمل تعلّم من الداشبورد.', en: 'There is nothing to pay right now. You can carry on from your dashboard.' },
    payBlockedActiveUntil:  { ar: 'اشتراكك ساري لحد',        en: 'Active until' },
    payBlockedRenewHint:    { ar: 'عايز تجدد بدري؟',          en: 'Want to renew early?' },
    payBlockedRenewLink:    { ar: 'اتفضل من هنا',            en: 'Do it here' },
    payBlockedDashboard:    { ar: 'روح للداشبورد',           en: 'Go to dashboard' },
    // pay.js runtime strings
    planMonthly:      { ar: 'شهري',                        en: 'Monthly' },
    planQuarterly:    { ar: '3 شهور',                      en: '3 Months' },
    planYearly:       { ar: 'سنوي',                        en: 'Yearly' },
    periodMonthly:    { ar: '/ شهر',                       en: '/ month' },
    periodQuarterly:  { ar: '/ 3 شهور',                    en: '/ 3 months' },
    periodYearly:     { ar: '/ سنة',                       en: '/ year' },
    payErrLoadConfig: { ar: 'حصلت مشكلة في تحميل بيانات الدفع', en: 'Error loading payment information' },
    payCopiedToast:   { ar: 'تم نسخ رقم انستاباي!',        en: 'Instapay number copied!' },
    payCopiedToastVf: { ar: 'تم نسخ رقم فودافون كاش!',     en: 'Vodafone Cash number copied!' },
    payCopyFailed:    { ar: 'مقدرناش ننسخ النص',           en: 'Failed to copy text' },
    payErrFileType:   { ar: 'نوع الملف مش مدعوم. ارفع JPG أو PNG أو WebP أو PDF.', en: 'Invalid file type. Please upload a JPG, PNG, WebP, or PDF.' },
    payErrFileSize:   { ar: 'الملف كبير أوي. الحد الأقصى 5 ميجا.', en: 'File too large. Maximum size is 5MB.' },
    payErrNoReceipt:  { ar: 'من فضلك ارفع صورة الإيصال',   en: 'Please upload your receipt screenshot' },
    payErrSubmit:     { ar: 'مقدرناش نبعت الطلب',          en: 'Failed to submit request' },

    // ── coupons (pay.html; the pricing modal carries its own data-ar/data-en) ──
    // The refusal wordings are NOT here: they live in pricing.js keyed by the
    // backend's `reason`, and pay.js reads them from there, so both screens say
    // the same thing about the same code. Only what the /pay markup and its own
    // runtime strings need is in this dictionary.
    couponLabel:      { ar: 'عندك كوبون خصم؟',             en: 'Have a discount code?' },
    couponPlaceholder:{ ar: 'اكتب الكود هنا',              en: 'Enter your code' },
    couponApply:      { ar: 'تطبيق',                       en: 'Apply' },
    couponApplying:   { ar: 'بنتأكد...',                   en: 'Checking…' },
    couponApplied:    { ar: 'تم تطبيق الكوبون',            en: 'Coupon applied' },
    couponEmpty:      { ar: 'اكتب كود الكوبون الأول',      en: 'Type a code first' },
    couponFailed:     { ar: 'مقدرناش نتأكد من الكوبون دلوقتي. جرّب تاني.', en: 'We could not check that code right now. Please try again.' },
    // {pct} and {code} are filled from the backend's answer, never from a
    // number written on this page.
    couponLine:       { ar: 'خصم {pct}% بكوبون {code}',    en: '{pct}% off with code {code}' },

    // (payment.html's nine keys lived here. The page was retired in favour of
    // /pricing — which carries its own data-ar/data-en rather than i18n keys —
    // and no other page ever referenced them.)

    // ── profile-settings.html → Preferences ──
    preferences:      { ar: 'التفضيلات',                   en: 'Preferences' },
    language:         { ar: 'اللغة',                       en: 'Language' },
    appearance:       { ar: 'المظهر',                      en: 'Appearance' },
    dark:             { ar: 'داكن',                        en: 'Dark' },
    light:            { ar: 'فاتح',                        en: 'Light' },

    // ── dashboard-courses.html ──
    courses:          { ar: 'الكورسات',                    en: 'Courses' },
    allCourses:       { ar: 'جميع الكورسات',               en: 'All Courses' },
};

// ─── Helpers ────────────────────────────────────────────────

/** The language currently applied to the document. */
function currentLang() {
    return document.documentElement.getAttribute('lang') === 'en' ? 'en' : 'ar';
}

/** Look a key up in the current language — for strings built in JS. */
function t(key, fallback) {
    const entry = i18nDict[key];
    if (!entry) return fallback !== undefined ? fallback : key;
    return entry[currentLang()] || entry.ar;
}

function setNodeText(el, value, asHtml) {
    if (value == null) return;
    if (asHtml) el.innerHTML = value;
    else el.textContent = value;
}

// ─── Translate a subtree ────────────────────────────────────
// The markup passes, split out of applyLanguage() so they can be pointed at
// ONE container instead of the whole document.
//
// Why that matters: pages that build their markup in JS (/tracks, /instructors,
// the course preview) inject it AFTER this file has already run its automatic
// pass, so any data-ar/data-en inside that markup would keep whatever literal
// text it was written with — Arabic — even in English. Those pages call
// applyLanguageTo() on the container they just filled. It deliberately does NOT
// dispatch `languagechange` (the pages re-render on that event, which would
// loop) and never persists.
function translateTree(root, lang) {
    const scope = root || document;
    // querySelectorAll skips the root itself, so it is handled separately.
    const each = (sel, fn) => {
        if (scope.matches && scope.matches(sel)) fn(scope);
        scope.querySelectorAll(sel).forEach(fn);
    };

    // data-ar / data-en (landing-page style, honours data-html)
    each('[data-ar]', el => {
        const text = lang === 'ar' ? el.getAttribute('data-ar') : el.getAttribute('data-en');
        setNodeText(el, text, el.getAttribute('data-html') === 'true');
    });

    // data-ar-placeholder / data-en-placeholder
    each('[data-ar-placeholder]', el => {
        const ph = lang === 'ar'
            ? el.getAttribute('data-ar-placeholder')
            : el.getAttribute('data-en-placeholder');
        if (ph != null) el.placeholder = ph;
    });

    // data-i18n (dictionary style, honours data-i18n-html)
    each('[data-i18n]', el => {
        const entry = i18nDict[el.getAttribute('data-i18n')];
        if (!entry) return;
        setNodeText(el, entry[lang] || entry.ar, el.getAttribute('data-i18n-html') === 'true');
    });

    // data-ar-aria / data-en-aria → the aria-label attribute.
    //
    // Needed because data-ar/data-en write textContent, so putting them on a
    // button that CONTAINS something — an icon, an image — deletes its
    // children and replaces them with the string. An icon button whose label
    // has to be translated therefore cannot use data-ar/data-en at all, and
    // before this existed the only way was to re-set innerHTML by hand after
    // every language pass.
    each('[data-ar-aria]', el => {
        const v = lang === 'ar' ? el.getAttribute('data-ar-aria') : el.getAttribute('data-en-aria');
        if (v != null) el.setAttribute('aria-label', v);
    });

    // data-ar-alt / data-en-alt → the alt attribute, same reasoning as above.
    //
    // An <img> has no text node to write into, so data-ar/data-en cannot carry
    // its alt. Without this, a translated logo's alt is whatever language the
    // markup was built in and then never changes — the payment-choice icons
    // are built once and reused for the life of the page.
    each('[data-ar-alt]', el => {
        const v = lang === 'ar' ? el.getAttribute('data-ar-alt') : el.getAttribute('data-en-alt');
        if (v != null) el.setAttribute('alt', v);
    });

    // data-i18n-placeholder / data-i18n-title
    each('[data-i18n-placeholder]', el => {
        const entry = i18nDict[el.getAttribute('data-i18n-placeholder')];
        if (entry) el.placeholder = entry[lang] || entry.ar;
    });
    each('[data-i18n-title]', el => {
        const entry = i18nDict[el.getAttribute('data-i18n-title')];
        if (entry) el.setAttribute('title', entry[lang] || entry.ar);
    });
}

/** Translate freshly-injected markup into the language already on the page. */
function applyLanguageTo(root) {
    translateTree(root, currentLang());
}

// ─── Apply ──────────────────────────────────────────────────
// `persist` is false on the automatic page-load pass so a page default never
// silently overwrites a choice the user hasn't made yet.
function applyLanguage(lang, persist = true) {
    const config = translations[lang];
    if (!config) return;
    const html = document.getElementById('htmlRoot') || document.documentElement;

    // 1. Direction + lang attribute
    html.setAttribute('dir', config.dir);
    html.setAttribute('lang', config.lang);

    // 2–5. Every markup pass, over the whole document.
    translateTree(document, lang);

    // 6. Toggle button label (desktop + mobile)
    const toggleText = document.getElementById('langToggleText');
    if (toggleText) toggleText.textContent = config.toggleBtn;
    const mobileToggleText = document.getElementById('mobileLangToggleText');
    if (mobileToggleText) mobileToggleText.textContent = config.toggleBtn;

    // 7. Force reflow for flex containers (fixes RTL/LTR layout shift).
    //    No-op on pages that don't have these sections.
    document.querySelectorAll('.hero-split, .features-section, .pricing-section, .main-nav').forEach(el => {
        el.style.display = 'none';
        el.offsetHeight; // trigger reflow
        el.style.display = '';
    });

    // 8. (The courses carousel used to be rebuilt here so Swiper would pick up
    //    the new direction. The carousel is gone — the courses section is a
    //    plain grid rendered from src/js/catalog.js, which re-renders itself
    //    off the `languagechange` event dispatched in step 10.)

    // 9. (The pricing section used to expose applyPricingCurrency() from an
    //     inline script and be re-run here. The cards come from
    //     src/js/pricing.js now, which repaints itself off the
    //     `languagechange` event dispatched in step 10 like every other
    //     JS-rendered section.)

    // 10. Persist the explicit choice — BEFORE the event, never after.
    //
    // This used to be the last step, after the dispatch below, and that one
    // line was the whole "English keeps showing Arabic" bug: a renderer
    // listening for `languagechange` that read the language out of
    // localStorage read the value from BEFORE the toggle, and repainted itself
    // in the language the user had just left. translateTree() above had
    // already put the correct text on the page, so the re-render actively
    // undid it — which is why only the sections rendered in JS (the FAQ, the
    // plan cards, the final CTA) were wrong while the static markup was right.
    //
    // Every renderer now reads currentLang() off the <html> lang attribute set
    // in step 1, so this ordering is belt-and-braces. It stays first anyway:
    // storage and the DOM should never disagree while a handler is running.
    if (persist) {
        try { localStorage.setItem('ghawy_lang', lang); } catch (e) { /* ignore */ }
    }

    // 11. Let page scripts re-render anything they built in JS.
    document.dispatchEvent(new CustomEvent('languagechange', { detail: { lang } }));
}

/** Explicit, user-chosen language — persists and wins on every page. */
function setLanguagePref(lang) {
    if (lang !== 'ar' && lang !== 'en') return;
    applyLanguage(lang, true);
}

function toggleLanguage() {
    const next = currentLang() === 'ar' ? 'en' : 'ar';
    setLanguagePref(next);
}

function storedLang() {
    try {
        const v = localStorage.getItem('ghawy_lang');
        return (v === 'ar' || v === 'en') ? v : null;
    } catch (e) { return null; }
}

// Expose for inline handlers and page scripts.
window.applyLanguage = applyLanguage;
window.applyLanguageTo = applyLanguageTo;
window.setLanguagePref = setLanguagePref;
window.toggleLanguage = toggleLanguage;
window.currentLang = currentLang;
window.i18nT = t;

// On every page load — the user's explicit choice, otherwise Arabic.
// The automatic pass never persists.
(function () {
    applyLanguage(storedLang() || 'ar', false);
})();
