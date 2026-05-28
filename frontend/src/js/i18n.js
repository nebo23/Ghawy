/* ═══════════════════════════════════
   i18n — Arabic / English Translation System
   ═══════════════════════════════════*/

const translations = {
  ar: {
    // Navigation
    dashboard: "الرئيسية",
    teamDashboard: "Team Dashboard",
    courses: "الكورسات",
    buildWithMe: "ابني معايا (لايف)",
    guestOfHonors: "ضيوف الشرف",
    aiUpdates: "أخبار الذكاء الاصطناعي",
    communityChat: "شات المجتمع",
    toolsResources: "أدوات ومصادر",
    achievements: "الإنجازات",
    settings: "الإعدادات",

    // Dashboard
    heroTitle: "احترف الـ AI. ابني نفوذ. اصنع حرية.",
    heroSubtitle: "كورسات عملية. مشاريع حقيقية. نتائج فعلية.",
    continueLearning: "كمّل التعلم",
    yourCourses: "كورساتك",
    viewAll: "عرض الكل",
    lessons: "درس",
    guestOfHonorsTitle: "ضيوف الشرف",
    newAiUpdates: "أخبار الذكاء الاصطناعي",
    buildWithMeLive: "ابني معايا لايف",
    liveNow: "لايف الآن",
    joinLive: "انضم للايف",
    upcomingSessions: "الجلسات القادمة",
    online: "أونلاين",
    typeMessage: "اكتب رسالة...",
    daysStreak: "يوم متواصل",

    // Courses
    allCourses: "جميع الكورسات",
    beginner: "مبتدئ",
    intermediate: "متوسط",
    advanced: "متقدم",
    curriculum: "المنهج",
    overview: "نظرة عامة",
    projects: "مشاريع",
    resources: "مصادر",
    reviews: "تقييمات",
    expandAll: "توسيع الكل",
    collapseAll: "تصغير الكل",
    yourProgress: "تقدمك",
    courseProgress: "تقدم الكورس",
    complete: "مكتمل",
    completedOf: "درس مكتمل من",
    resumeLesson: "كمّل من آخر درس",
    whatYoullLearn: "هتتعلم إيه",
    topStudents: "أفضل الطلاب",
    viewLeaderboard: "عرض المتصدرين",
    filterSearch: "بحث وتصفية الدروس",
    searchLessons: "ابحث في الدروس...",
    searchCourses: "ابحث في الكورسات...",
    all: "الكل",
    videos: "فيديوهات",
    quizzes: "اختبارات",
    previewCourse: "معاينة الكورس",
    aboutThisCourse: "عن هذا الكورس",
    courseCurriculum: "محتوى الكورس",
    loadingCourses: "جاري تحميل الكورسات...",
    noCourses: "لا توجد كورسات متاحة بعد",

    // Community
    newPost: "منشور جديد",
    postTitle: "عنوان المنشور",
    postContent: "محتوى المنشور",
    category: "الفئة",
    publish: "نشر",
    cancel: "إلغاء",
    likes: "إعجاب",
    comments: "تعليقات",
    writeComment: "اكتب تعليق...",
    addComment: "أضف تعليق",
    wins: "انتصارات",
    questions: "أسئلة",
    tools: "أدوات",

    // Chat
    channels: "القنوات",
    readBy: "قرأها",
    sendMessage: "إرسال",
    noMessages: "لا توجد رسائل بعد",
    searchMessages: "ابحث في الرسائل...",

    // Profile
    profile: "الملف الشخصي",
    editProfile: "تعديل الملف الشخصي",
    level: "المستوى",
    recentActivity: "النشاط الأخير",

    // Profile Settings
    personalInfo: "المعلومات الشخصية",
    fullName: "الاسم الكامل",
    bio: "نبذة شخصية",
    changePhoto: "تغيير الصورة",
    saveChanges: "حفظ التغييرات",
    account: "الحساب",
    email: "البريد الإلكتروني",
    currentPassword: "كلمة المرور الحالية",
    newPassword: "كلمة المرور الجديدة",
    confirmPassword: "تأكيد كلمة المرور",
    changePassword: "تغيير كلمة المرور",
    notifications: "الإشعارات",
    emailNotifications: "إشعارات البريد",
    newCourseAlerts: "تنبيهات الكورسات الجديدة",
    communityMentions: "إشارات المجتمع",
    chatNotifications: "إشعارات الشات",
    dangerZone: "منطقة الخطر",
    deleteAccount: "حذف الحساب",
    deleteConfirm: "هل أنت متأكد؟ سيتم حذف حسابك نهائياً",
    deleteWarning: "بمجرد حذف حسابك لا يمكن التراجع عن ذلك.",
    delete: "حذف",
    yesDelete: "نعم، احذف",
    uploadImage: "رفع صورة",
    saved: "✓ تم الحفظ",

    // Auth
    login: "تسجيل الدخول",
    register: "إنشاء حساب",
    logout: "تسجيل الخروج",
    emailPlaceholder: "example@gmail.com",
    passwordPlaceholder: "••••••••",
    namePlaceholder: "اكتب اسمك هنا",
    alreadyHaveAccount: "عندك حساب بالفعل؟",
    dontHaveAccount: "مش عندك حساب؟",
    registerNow: "سجّل دلوقتي",
    loginNow: "سجّل دخولك",
    welcomeBack: "أهلاً بك مجدداً 👋",
    createAccountSub: "سجّل الآن وابدأ رحلتك مع الـ AI",
    loginTitle: "تسجيل الدخول",
    enterBtn: "دخول",
    orDivider: "أو",
    googleLogin: "الدخول باستخدام جوجل",

    // Payment
    subscriptionPlan: "خطة الاشتراك",
    monthlySubscription: "اشتراك شهري",
    perMonth: "جنيه / شهر",
    subscribeNow: "انضم الآن 🚀",
    securePay: "الدفع آمن 100% عبر Kashier",
    accessAll: "وصول لجميع الكورسات والشروحات",
    hours: "60+ ساعة من المحتوى الحصري",
    community: "مجتمع ومتابعة شخصية",
    newContent: "محتوى جديد بإستمرار",
    oneSubOpensAll: "اشتراك واحد يفتح لك جميع المحتويات",

    // Verify Email
    verifyEmail: "تأكيد البريد",
    enterOtp: "أدخل الكود المكوّن من 6 أرقام الذي تم إرساله إلى:",
    verify: "تحقق",
    resendCode: "إعادة إرسال الكود",
    resendIn: "إعادة الإرسال خلال",
    backToRegister: "رجوع إلى إنشاء حساب",

    // General
    loading: "جاري التحميل...",
    error: "حدث خطأ",
    success: "تم بنجاح",
    save: "حفظ",
    edit: "تعديل",
    close: "إغلاق",
    back: "رجوع",
    next: "التالي",
    previous: "السابق",
    search: "بحث",
    noData: "لا توجد بيانات",
    serverError: "مفيش اتصال بالـ server",
    member: "عضو",
    searchGeneral: "بحث...",

    // Landing Page — Nav
    lp_navReviews: "الاراء",
    lp_navCourses: "الكورسات",
    lp_navFeatures: "المميزات",
    lp_navPrice: "السعر",
    lp_login: "تسجيل الدخول",
    lp_startNow: "ابدا الان",
    lp_logout: "تسجيل الخروج",

    // Landing Page — Hero
    lp_badge: "منصة تعليم الذكاء الاصطناعي #1 في الوطن العربي",
    lp_heroLine1: "احترف الـ AI.",
    lp_heroLine2: "ابني نفوذ.",
    lp_heroLine3: "اصنع حريتك.",
    lp_heroSub: "كورسات عملية، مشاريع حقيقية ومجتمع قوي يساعدك تحترف الـ AI وتبني دخل حقيقي.",
    lp_statCourses: "كورسات",
    lp_statProjects: "مشاريع",
    lp_statMembers: "أعضاء",
    lp_statLive: "لايف",
    lp_statSessions: "جلسات",
    lp_joinNow: "انضم لـ Ghawy الآن",
    lp_watchIntro: "شاهد المقدمة",
    lp_unmuteBtn: "تشغيل الصوت",
    lp_ratingText: "حاصل علي تقييم 5.0 من اكثر من 30 مراجعة",

    // Landing Page — Mobile Drawer
    lp_mobileLogin: "تسجيل الدخول",
    lp_mobileStart: "ابدا الان",
  },

  en: {
    // Navigation
    dashboard: "Dashboard",
    teamDashboard: "Team Dashboard",
    courses: "Courses",
    buildWithMe: "Build With Me (Live)",
    guestOfHonors: "Guest of Honors",
    aiUpdates: "AI Updates",
    communityChat: "Community Chat",
    toolsResources: "Tools & Resources",
    achievements: "Achievements",
    settings: "Settings",

    // Dashboard
    heroTitle: "Master AI. Build Leverage. Create Freedom.",
    heroSubtitle: "Practical courses. Real projects. Real results.",
    continueLearning: "Continue Learning",
    yourCourses: "Your Courses",
    viewAll: "View all",
    lessons: "Lessons",
    guestOfHonorsTitle: "Guest of Honors",
    newAiUpdates: "New AI Updates",
    buildWithMeLive: "Build With Me Live",
    liveNow: "LIVE NOW",
    joinLive: "Join Live",
    upcomingSessions: "Upcoming Sessions",
    online: "Online",
    typeMessage: "Type a message...",
    daysStreak: "Days Streak",

    // Courses
    allCourses: "All Courses",
    beginner: "Beginner",
    intermediate: "Intermediate",
    advanced: "Advanced",
    curriculum: "Curriculum",
    overview: "Overview",
    projects: "Projects",
    resources: "Resources",
    reviews: "Reviews",
    expandAll: "Expand All",
    collapseAll: "Collapse All",
    yourProgress: "Your Progress",
    courseProgress: "Course Progress",
    complete: "Complete",
    completedOf: "lessons completed of",
    resumeLesson: "Resume Lesson",
    whatYoullLearn: "What You'll Learn",
    topStudents: "Top Students",
    viewLeaderboard: "View Leaderboard",
    filterSearch: "Filter & Search Lessons",
    searchLessons: "Search lessons...",
    searchCourses: "Search courses...",
    all: "All",
    videos: "Videos",
    quizzes: "Quizzes",
    previewCourse: "Preview Course",
    aboutThisCourse: "About This Course",
    courseCurriculum: "Course Curriculum",
    loadingCourses: "Loading courses...",
    noCourses: "No courses available yet",

    // Community
    newPost: "New Post",
    postTitle: "Post Title",
    postContent: "Post Content",
    category: "Category",
    publish: "Publish",
    cancel: "Cancel",
    likes: "Likes",
    comments: "Comments",
    writeComment: "Write a comment...",
    addComment: "Add Comment",
    wins: "Wins",
    questions: "Questions",
    tools: "Tools",

    // Chat
    channels: "Channels",
    readBy: "Read by",
    sendMessage: "Send",
    noMessages: "No messages yet",
    searchMessages: "Search messages...",

    // Profile
    profile: "Profile",
    editProfile: "Edit Profile",
    level: "Level",
    recentActivity: "Recent Activity",

    // Profile Settings
    personalInfo: "Personal Info",
    fullName: "Full Name",
    bio: "Bio",
    changePhoto: "Change Photo",
    saveChanges: "Save Changes",
    account: "Account",
    email: "Email",
    currentPassword: "Current Password",
    newPassword: "New Password",
    confirmPassword: "Confirm Password",
    changePassword: "Change Password",
    notifications: "Notifications",
    emailNotifications: "Email notifications",
    newCourseAlerts: "New course alerts",
    communityMentions: "Community mentions",
    chatNotifications: "Chat notifications",
    dangerZone: "Danger Zone",
    deleteAccount: "Delete Account",
    deleteConfirm: "Are you sure? Your account will be permanently deleted.",
    deleteWarning: "Once you delete your account, there is no going back.",
    delete: "Delete",
    yesDelete: "Yes, Delete",
    uploadImage: "Upload Image",
    saved: "✓ Saved",

    // Auth
    login: "Login",
    register: "Create Account",
    logout: "Logout",
    emailPlaceholder: "example@gmail.com",
    passwordPlaceholder: "••••••••",
    namePlaceholder: "Enter your name",
    alreadyHaveAccount: "Already have an account?",
    dontHaveAccount: "Don't have an account?",
    registerNow: "Register now",
    loginNow: "Login",
    welcomeBack: "Welcome back 👋",
    createAccountSub: "Register now and start your AI journey",
    loginTitle: "Login",
    enterBtn: "Login",
    orDivider: "or",
    googleLogin: "Sign in with Google",

    // Payment
    subscriptionPlan: "Subscription Plan",
    monthlySubscription: "Monthly Subscription",
    perMonth: "EGP / month",
    subscribeNow: "Join Now 🚀",
    securePay: "100% Secure payment via Kashier",
    accessAll: "Access to all courses and explanations",
    hours: "60+ hours of exclusive content",
    community: "Community and personal follow-up",
    newContent: "New content continuously",
    oneSubOpensAll: "One subscription unlocks all content",

    // Verify Email
    verifyEmail: "Verify Email",
    enterOtp: "Enter the 6-digit code sent to:",
    verify: "Verify",
    resendCode: "Resend Code",
    resendIn: "Resend in",
    backToRegister: "Back to Create Account",

    // General
    loading: "Loading...",
    error: "An error occurred",
    success: "Done successfully",
    save: "Save",
    edit: "Edit",
    close: "Close",
    back: "Back",
    next: "Next",
    previous: "Previous",
    search: "Search",
    noData: "No data available",
    serverError: "Cannot connect to server",
    member: "Member",
    searchGeneral: "Search...",

    // Landing Page — Nav
    lp_navReviews: "Reviews",
    lp_navCourses: "Courses",
    lp_navFeatures: "Features",
    lp_navPrice: "Pricing",
    lp_login: "Login",
    lp_startNow: "Start Now",
    lp_logout: "Logout",

    // Landing Page — Hero
    lp_badge: "#1 AI Learning Platform In The Arab World",
    lp_heroLine1: "Master AI.",
    lp_heroLine2: "Build Leverage.",
    lp_heroLine3: "Create Freedom.",
    lp_heroSub: "Practical courses, real projects and a powerful community to help you master AI and build real income.",
    lp_statCourses: "Courses",
    lp_statProjects: "Projects",
    lp_statMembers: "Members",
    lp_statLive: "Live",
    lp_statSessions: "Sessions",
    lp_joinNow: "Join Ghawy Now",
    lp_watchIntro: "Watch Intro",
    lp_unmuteBtn: "Unmute",
    lp_ratingText: "Rated 5.0 from over 30 reviews",

    // Landing Page — Mobile Drawer
    lp_mobileLogin: "Login",
    lp_mobileStart: "Start Now",
  }
};

// ── Language Management ──

function getLang() {
  return localStorage.getItem('lang') || 'ar';
}

function setLang(lang) {
  localStorage.setItem('lang', lang);
  applyLang(lang);
}

function t(key) {
  const lang = getLang();
  return (translations[lang] && translations[lang][key]) || (translations['en'] && translations['en'][key]) || key;
}

function applyLang(lang) {
  // Set HTML direction and language
  document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
  document.documentElement.lang = lang;

  // Translate all elements with data-i18n attribute
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (translations[lang] && translations[lang][key]) {
      el.textContent = translations[lang][key];
    }
  });

  // Translate placeholders
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    if (translations[lang] && translations[lang][key]) {
      el.placeholder = translations[lang][key];
    }
  });

  // Update toggle button text
  const btn = document.getElementById('langToggle');
  if (btn) {
    btn.innerHTML = lang === 'ar' ? 'EN' : 'AR';
  }

  // Apply RTL-specific CSS fixes
  applyDirectionFixes(lang);
}

function applyDirectionFixes(lang) {
  const isRTL = lang === 'ar';

  // Dashboard sidebar position
  const sidebar = document.querySelector('.dash-sidebar');
  if (sidebar) {
    sidebar.style.right = isRTL ? '0' : 'auto';
    sidebar.style.left = isRTL ? 'auto' : '0';
    sidebar.style.borderRight = isRTL ? 'none' : '1px solid var(--border)';
    sidebar.style.borderLeft = isRTL ? '1px solid var(--border)' : 'none';
  }

  // Main content margin
  const main = document.querySelector('.dash-main');
  if (main) {
    if (window.innerWidth > 768) {
      main.style.marginRight = isRTL ? 'var(--sidebar-w)' : '0';
      main.style.marginLeft = isRTL ? '0' : 'var(--sidebar-w)';
    } else {
      main.style.marginRight = '0';
      main.style.marginLeft = '0';
    }
  }
}

// ── Sidebar Toggle (mobile) ──

function initSidebar() {
  const hamburger = document.getElementById('hamburgerBtn');
  const sidebar = document.querySelector('.dash-sidebar');
  const overlay = document.getElementById('sidebarOverlay');

  // Also support the old hamburger ID
  const hamburgerDash = document.getElementById('hamburgerDash');

  function toggleSidebar() {
    if (sidebar) sidebar.classList.toggle('open');
    if (overlay) overlay.classList.toggle('visible');
  }

  function closeSidebar() {
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('visible');
  }

  if (hamburger) hamburger.addEventListener('click', toggleSidebar);
  if (hamburgerDash) hamburgerDash.addEventListener('click', toggleSidebar);
  if (overlay) overlay.addEventListener('click', closeSidebar);

  // Close on nav link click (mobile)
  if (sidebar) {
    sidebar.querySelectorAll('a, button').forEach(link => {
      link.addEventListener('click', () => {
        if (window.innerWidth <= 768) closeSidebar();
      });
    });
  }
}

// ── Initialize on page load ──

document.addEventListener('DOMContentLoaded', () => {
  applyLang(getLang());
  initSidebar();

  // Re-apply direction fixes on resize
  window.addEventListener('resize', () => applyDirectionFixes(getLang()));
});


