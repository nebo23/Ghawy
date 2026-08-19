/* ═══ COMMUNITY i18n — Arabic layer for logged-in community pages ONLY ═══
 *
 * Reads the same explicit preference key (ghawy_lang) written by
 * Settings → Preferences. Community default stays English; this file does
 * nothing unless the user explicitly chose Arabic. The public landing page
 * and the auth/checkout funnel are NOT touched (they never load this file).
 *
 * How it works:
 *  - Exact-match dictionary (English → Arabic) applied to whole text nodes
 *    and to placeholder / title / aria-label / alt / data-tooltip attributes.
 *  - Regex patterns for interpolated strings ("5 Lessons", "3m ago", …).
 *  - A MutationObserver re-translates dynamically rendered content
 *    (chat messages UI, course cards, toasts, dropdown menus, …).
 *  - User-generated content never matches whole-node dictionary keys, so it
 *    is left untouched. Elements can opt out with data-no-i18n.
 *  - Live switch: watches <html lang> so the Settings toggle applies/undoes
 *    the translation instantly (originals are kept in WeakMaps).
 */
(function () {
    'use strict';

    /* ─── Legacy storage key migration ──────────────────────────
       The preference key was renamed 'ghawy_lang_pref' → 'ghawy_lang'. The
       migration used to live only in i18n.js, which SIX of the community pages
       never load (dashboard, chat, ai-updates, direct-messages, course-detail,
       help-center). On those pages the read below saw no 'ghawy_lang' at all,
       so everyone who had picked English under the old key was dropped back to
       the Arabic default on every load — and the choice could never stick,
       because nothing here writes the new key either.
       Same keys, same semantics as i18n.js, and idempotent — whichever file
       runs first migrates, the other one no-ops. */
    try {
        var legacyPref = localStorage.getItem('ghawy_lang_pref');
        if (legacyPref === 'ar' || legacyPref === 'en') {
            localStorage.setItem('ghawy_lang', legacyPref);
        }
        if (legacyPref !== null) localStorage.removeItem('ghawy_lang_pref');
    } catch (e) { /* private mode / storage disabled — defaults still work */ }

    /* ─── Dictionary ─────────────────────────────────────────────── */
    var DICT = {
        /* ── Sidebar / nav / topbar (shared chrome) ── */
        'Dashboard': 'الرئيسية',
        'Courses': 'الكورسات',
        'Community Chat': 'شات المجتمع',
        'Direct Messages': 'الرسائل الخاصة',
        'AI Updates': 'تحديثات الـ AI',
        'Build With Me': 'ابني معايا',
        'Guest of Honors': 'ضيوف الشرف',
        'Achievements': 'الإنجازات',
        'Settings': 'الإعدادات',
        'Team Dashboard': 'لوحة الفريق',
        'Help center': 'مركز المساعدة',
        'Help Center': 'مركز المساعدة',
        'Member': 'عضو',
        'Members': 'الأعضاء',
        'Days Streak': 'يوم متواصل 🔥',
        'Day Streak': 'يوم متواصل',
        'Day Streak 🔥': 'يوم متواصل 🔥',
        'Keep going!': 'كمّل!',
        'Welcome back,': 'أهلاً بعودتك،',
        "Let's continue building, learning, and leveling up.": 'يلا نكمّل بناء وتعلّم وتطوّر.',
        'Notifications': 'الإشعارات',
        'No new notifications': 'مفيش إشعارات جديدة',
        'No notifications': 'مفيش إشعارات',
        'Chat': 'الشات',
        'View profile': 'عرض البروفايل',
        'View Profile': 'عرض البروفايل',
        'Help and support': 'المساعدة والدعم',
        'Sign out': 'تسجيل الخروج',
        'Open menu': 'افتح القائمة',
        'Loading...': 'جاري التحميل...',
        'Send': 'إرسال',
        'Cancel': 'إلغاء',
        'Close': 'إغلاق',
        'Delete': 'حذف',
        'Edit': 'تعديل',
        'Save Changes': 'حفظ التغييرات',
        'Saving...': 'جاري الحفظ...',
        'Admin': 'أدمن',
        'Owner': 'المالك',
        'Moderator': 'مشرف',
        'Pro Member': 'عضو Pro',
        'VIP': 'VIP',
        'User': 'مستخدم',
        'Unknown': 'غير معروف',
        'Unknown error': 'خطأ غير معروف',
        'Network error': 'خطأ في الاتصال بالشبكة',
        'Today': 'النهارده',
        'Yesterday': 'امبارح',
        'Now': 'الآن',
        'Online': 'متصل',
        'Offline': 'غير متصل',
        'Online Now': 'متصل الآن',
        'Active now': 'نشط الآن',
        'More': 'المزيد',
        'Level': 'المستوى',
        'LEVEL': 'المستوى',
        'XP': 'XP',
        'Error loading profile': 'حصل خطأ في تحميل البروفايل',
        'Failed to load profile': 'فشل تحميل البروفايل',
        'No bio yet': 'مفيش نبذة لسه',
        'Message': 'رسالة',
        'Messages': 'الرسائل',

        /* ── Page titles (document.title) ── */
        'Dashboard — Ghawy': 'الرئيسية — Ghawy',
        'Courses — Ghawy': 'الكورسات — Ghawy',
        'Community Chat — Ghawy': 'شات المجتمع — Ghawy',
        'AI Updates — Ghawy': 'تحديثات الـ AI — Ghawy',
        'Build With Me (Live) — Ghawy': 'ابني معايا (لايف) — Ghawy',
        'Guest of Honors — Ghawy': 'ضيوف الشرف — Ghawy',
        'Profile — Ghawy': 'البروفايل — Ghawy',
        'Settings — Ghawy': 'الإعدادات — Ghawy',
        'Help Center — Ghawy': 'مركز المساعدة — Ghawy',
        'Course Detail — Ghawy': 'تفاصيل الكورس — Ghawy',

        /* ── What's New popup ── */
        "What's New": 'إيه الجديد',
        'in Ghawy': 'في Ghawy',
        "We've been working hard to bring you a better, faster and smarter learning experience. Check out what's new!": 'اشتغلنا كتير عشان نجيبلك تجربة تعلّم أحسن وأسرع وأذكى. شوف الجديد!',
        'Polls with Photos & Videos': 'استطلاعات بصور وفيديوهات',
        'AI Update polls can now include photos and videos — images show full-size like regular posts, with the poll right below.': 'استطلاعات تحديثات الـ AI بقت تدعم الصور والفيديوهات — الصور بتتعرض بحجمها الكامل زي البوستات العادية والاستطلاع تحتها على طول.',
        'Faster Voice Messages': 'رسايل صوتية أسرع',
        'Voice notes now load instantly — even on mobile — and keep playing while you scroll.': 'الرسايل الصوتية بقت تشتغل فورًا — حتى على الموبايل — وبتكمّل شغل وانت بتعمل سكرول.',
        'Weekly AI Updates Feed': 'تحديثات الـ AI أسبوعيًا',
        "The AI Updates feed now spotlights each week's fresh updates so you never miss what's new.": 'صفحة تحديثات الـ AI بقت تعرض جديد كل أسبوع عشان ماتفوتش أي حاجة جديدة.',
        'AI Updates — New Experience': 'تحديثات الـ AI — تجربة جديدة',
        'A completely new design for AI Updates. Stay ahead with the latest news, tools, models & more.': 'تصميم جديد بالكامل لتحديثات الـ AI. تابع أحدث الأخبار والأدوات والموديلات وأكتر.',
        'Light Mode': 'الوضع الفاتح',
        'A beautiful new light mode for a cleaner and brighter experience.': 'وضع فاتح جديد لتجربة أنضف وأوضح.',
        'Choose your language and theme — customize your experience the way you like it.': 'اختار لغتك والثيم — ظبّط تجربتك زي ما تحب.',
        'Exams & Quizzes': 'الامتحانات والاختبارات',
        'Take exams inside your courses, test your knowledge and track your progress.': 'امتحن جوه كورساتك، اختبر معلوماتك وتابع تقدمك.',
        'Course Certificates': 'شهادات الكورسات',
        'Finish a course and get a certificate with your name on it.': 'خلّص الكورس وخد شهادة باسمك.',
        'File Upload in Chat': 'رفع الملفات في الشات',
        'Share files and images directly in community chat and direct messages.': 'شارك ملفات وصور مباشرة في شات المجتمع والرسائل الخاصة.',
        'Performance Improvements': 'تحسينات في الأداء',
        'Faster loading, smoother navigation and many under-the-hood improvements.': 'تحميل أسرع وتنقّل أسلس وتحسينات كتير من جوه.',
        'Skip': 'تخطي',
        "Let's Go!": 'يلا بينا!',

        /* ── Dashboard ── */
        'AI PATH': 'AI PATH',
        'Master AI. Build Leverage. Create Freedom.': 'احترف الـ AI. ابني نفوذ. اصنع حريتك.',
        'Practical courses. Real projects. Real results.': 'كورسات عملية. مشاريع حقيقية. نتائج حقيقية.',
        'Continue Learning': 'كمّل التعلم',
        'Your Courses': 'كورساتك',
        'View All': 'عرض الكل',
        'View all': 'عرض الكل',
        'See All': 'عرض الكل',
        'New AI Updates': 'أحدث تحديثات الـ AI',
        'Upcoming Session': 'الجلسة الجاية',
        'Type a message...': 'اكتب رسالة...',
        'Courses Completed': 'كورسات مكتملة',
        'Courses In Progress': 'كورسات قيد التنفيذ',
        'Achievements Unlocked': 'إنجازات مفتوحة',
        'No upcoming sessions': 'مفيش جلسات جاية',
        'Starting now!': 'بتبدأ دلوقتي!',
        'Live Now': 'لايف دلوقتي',
        'No Live Session Right Now': 'مفيش جلسة لايف دلوقتي',
        'Check upcoming sessions below': 'شوف الجلسات الجاية تحت',
        'Could not load session info.': 'معرفناش نحمّل بيانات الجلسة.',
        'No messages yet. Say hi! 👋': 'مفيش رسائل لسه. قول هاي! 👋',
        'No courses enrolled yet.': 'مفيش كورسات مشترك فيها لسه.',
        'Start your learning journey now.': 'ابدأ رحلة تعلمك دلوقتي.',
        'Browse courses →': 'تصفح الكورسات ←',
        'No AI updates yet.': 'مفيش تحديثات AI لسه.',
        'No featured guests yet.': 'مفيش ضيوف مميزين لسه.',
        'Welcome to Ghawy!': 'أهلاً بيك في Ghawy!',
        'New message from': 'رسالة جديدة من',
        'Starter': 'مبتدئ',
        'Explorer': 'مستكشف',
        'Builder': 'بنّاء',
        'Innovator': 'مبتكر',
        'Master': 'محترف',
        'Legend': 'أسطورة',
        'AI Expert': 'خبير AI',
        'Instructor': 'مدرّب',

        /* ── Courses / course cards ── */
        'Loading courses...': 'جاري تحميل الكورسات...',
        'Completed': 'مكتمل',
        'In Progress': 'قيد التنفيذ',
        'Not Started': 'لم يبدأ',
        'Start Course': 'ابدأ الكورس',
        'Resume Lesson': 'كمّل الدرس',
        'Lessons': 'الدروس',
        'Lesson': 'درس',

        /* ── Course detail ── */
        'Loading course...': 'جاري تحميل الكورس...',
        'Course': 'كورس',
        'Course Curriculum': 'محتوى الكورس',
        'Curriculum': 'المحتوى',
        'Overview': 'نظرة عامة',
        'Resources': 'الموارد',
        'Reviews': 'التقييمات',
        'Projects': 'المشاريع',
        'Course Progress': 'تقدمك في الكورس',
        'Course progress': 'تقدمك في الكورس',
        'Your Progress': 'تقدمك',
        '0 Lessons': '0 درس',
        '0% Complete': 'مكتمل 0%',
        'Completed 0 of 0 lessons': 'أكملت 0 من 0 درس',
        'Mark lesson as complete': 'علّم الدرس كمكتمل',
        'Lesson completed! 🎉': 'الدرس اكتمل! 🎉',
        'Expand All': 'فتح الكل',
        'Collapse All': 'قفل الكل',
        "What You'll Learn": 'إيه اللي هتتعلمه',
        'Build AI automations from scratch': 'ابني أوتوميشن AI من الصفر',
        'Create real world AI solutions': 'اعمل حلول AI حقيقية',
        'Integrate APIs and workflows': 'اربط الـ APIs والـ workflows',
        'Use AI tools like a pro': 'استخدم أدوات الـ AI باحتراف',
        'Save 10+ hours every week': 'وفّر +10 ساعات كل أسبوع',
        'Learn how to build smart automations and save 10+ hours every week.': 'اتعلم تبني أوتوميشن ذكي وتوفّر +10 ساعات كل أسبوع.',
        'Beginner': 'مبتدئ',
        'Intermediate': 'متوسط',
        'Advanced': 'متقدم',
        'Preview Course': 'معاينة الكورس',
        'Subscribe now to watch this lesson and all course content.': 'اشترك دلوقتي عشان تشوف الدرس ده وكل محتوى الكورس.',
        'Video unavailable': 'الفيديو غير متاح',
        'Course Resources': 'موارد الكورس',
        'Resources coming soon...': 'الموارد جاية قريب...',
        'No resources available for this course.': 'مفيش موارد متاحة للكورس ده.',
        'PDF Resource': 'ملف PDF',
        'Course Resource': 'مورد الكورس',
        'Cheat Sheet': 'ملخص سريع',
        'Prompt Library': 'مكتبة البرومبتات',
        'Workflow Templates': 'قوالب Workflows',
        'Open file': 'افتح الملف',
        'Write a Review': 'اكتب تقييم',
        'Submit Review': 'إرسال التقييم',
        'Share your experience with this course...': 'شاركنا تجربتك مع الكورس ده...',
        'No reviews yet. Be the first to review this course!': 'مفيش تقييمات لسه. كن أول واحد يقيّم الكورس ده!',
        'Delete Review': 'حذف التقييم',
        'Are you sure you want to delete this review?': 'متأكد إنك عايز تحذف التقييم ده؟',
        '✅ Review submitted successfully!': '✅ تم إرسال تقييمك بنجاح!',
        '✅ Review deleted successfully!': '✅ تم حذف التقييم بنجاح!',
        '❌ Error submitting review': '❌ حصل خطأ في إرسال التقييم',
        '❌ Error deleting review': '❌ حصل خطأ في حذف التقييم',
        'Submit Project': 'تسليم المشروع',
        'My Submissions': 'تسليماتي',
        'No project submitted yet.': 'مفيش مشروع متسلم لسه.',
        'No submission': 'مفيش تسليم',
        'Your submission is private': 'تسليمك خاص بيك',
        'Any file type': 'أي نوع ملف',
        'Any project file is accepted': 'أي ملف مشروع مقبول',
        'Drag and drop your file here, or': 'اسحب الملف هنا، أو',
        'click to browse': 'اضغط للاختيار',
        'No file selected': 'مفيش ملف مختار',
        'Max size: 25MB': 'أقصى حجم: 25 ميجا',
        'Choose a project file first': 'اختار ملف المشروع الأول',
        'Project file is empty': 'ملف المشروع فاضي',
        'Project file must be 25MB or smaller': 'ملف المشروع لازم يكون 25 ميجا أو أقل',
        'Project submitted for review': 'تم تسليم المشروع للمراجعة',
        'Project upload failed': 'فشل رفع المشروع',
        'Failed to load projects': 'فشل تحميل المشاريع',
        'Failed to load projects.': 'فشل تحميل المشاريع.',
        'Loading projects...': 'جاري تحميل المشاريع...',
        'Pending review': 'في انتظار المراجعة',
        'Approved': 'مقبول',
        'Changes requested': 'مطلوب تعديلات',
        'Top Students': 'أفضل الطلاب',
        'Top students in this course': 'أفضل الطلاب في الكورس ده',
        'No students yet': 'مفيش طلاب لسه',
        'No students yet. Be the first! 🚀': 'مفيش طلاب لسه. كن الأول! 🚀',
        'Be the first to complete a lesson! 🚀': 'كن أول واحد يكمّل درس! 🚀',
        'View Leaderboard': 'عرض لوحة الصدارة',
        '🏆 Course Leaderboard': '🏆 لوحة صدارة الكورس',
        'Failed to load leaderboard': 'فشل تحميل لوحة الصدارة',
        'Failed to load students': 'فشل تحميل الطلاب',
        '🎓 Download Certificate': '🎓 تحميل الشهادة',
        'Certificate not available yet': 'الشهادة مش متاحة لسه',
        'Your certificate is ready': 'شهادتك جاهزة',
        'Congratulations! You completed the course': 'مبروك! أنهيت الكورس',
        '✨ Well done!': '✨ برافو عليك!',
        'Course not found': 'الكورس مش موجود',
        'Failed to load course': 'فشل تحميل الكورس',
        'Guest of Honor': 'ضيف الشرف',
        'Build With Me Live': 'ابني معايا لايف',
        'Live': 'لايف',
        'Join our live sessions and build real projects with experts.': 'انضم لجلساتنا اللايف وابني مشاريع حقيقية مع خبراء.',
        'View Live Schedule': 'عرض جدول اللايف',
        'Unknown date': 'تاريخ غير معروف',
        'Unknown size': 'حجم غير معروف',
        'PDF': 'PDF',

        /* ── Exams (course detail) ── */
        'Exams': 'الاختبارات',
        'Exam': 'اختبار',
        'Test your knowledge — each exam is multiple choice.': 'اختبر معلوماتك — كل اختبار اختيار من متعدد.',
        'No exams available yet.': 'مفيش اختبارات متاحة لسه.',
        'Not attempted': 'لسه ماتحلّش',
        'Start Exam': 'ابدأ الاختبار',
        'Retake': 'أعد المحاولة',
        'Submit Answers': 'إرسال الإجابات',
        'Submitting...': 'جاري الإرسال...',
        'Passed! 🎉': 'ناجح! 🎉',
        'Not passed yet': 'لسه ماعديتش',
        'Loading exam...': 'جاري تحميل الاختبار...',
        'Could not load this exam.': 'معرفناش نحمّل الاختبار ده.',
        'Go back': 'ارجع',
        'Error submitting exam': 'حصل خطأ في إرسال الاختبار',
        'Back': 'رجوع',

        /* ── Chat / Direct messages ── */
        'CHAT': 'الشات',
        'POSTS': 'المنشورات',
        'Posts': 'المنشورات',
        'Post': 'نشر',
        'Post →': 'نشر ←',
        'General Chat': 'الشات العام',
        'general': 'عام',
        '# general': '# عام',
        '# announcements': '# الإعلانات',
        '# general-questions': '# أسئلة-عامة',
        '# hiring-opportunities': '# فرص-شغل',
        '# introduce-yourself': '# عرّف-بنفسك',
        '# share-your-build': '# شارك-مشروعك',
        '# start_here': '# ابدأ-من-هنا',
        '# wins': '# المكاسب',
        '# workflows-help': '# مساعدة-workflows',
        '(private — admins only)': '(خاص — للأدمن فقط)',
        'Open channels': 'القنوات المفتوحة',
        'PINNED MESSAGES': 'الرسائل المثبتة',
        'TOP TOPICS': 'أهم المواضيع',
        'ACTIVE NOW': 'نشطين دلوقتي',
        'Community Members': 'أعضاء المجتمع',
        'Find members': 'دوّر على الأعضاء',
        'Search members...': 'ابحث عن أعضاء...',
        'Search messages...': 'ابحث في الرسائل...',
        'Members ·': 'الأعضاء ·',
        '0 online': '0 متصل',
        'No messages yet. Start the conversation!': 'مفيش رسائل لسه. ابدأ المحادثة!',
        'Start chatting...': 'ابدأ الدردشة...',
        'Start a conversation': 'ابدأ محادثة',
        'No conversations yet': 'مفيش محادثات لسه',
        'Loading messages...': 'جاري تحميل الرسائل...',
        'Real-time chat': 'شات لحظي',
        'Attach file or image': 'إرفاق ملف أو صورة',
        'Attach Image (optional, max 5MB)': 'إرفاق صورة (اختياري، أقصى حجم 5 ميجا)',
        'Record voice': 'تسجيل صوتي',
        'Play voice message': 'تشغيل الرسالة الصوتية',
        'Microphone access denied': 'تم رفض الوصول للمايك',
        'Please allow microphone access': 'من فضلك اسمح بالوصول للمايك',
        'Failed to send voice message': 'فشل إرسال الرسالة الصوتية',
        'Reply': 'رد',
        'Reply to': 'رد على',
        'React': 'تفاعل',
        'Pin': 'تثبيت',
        'Unpin': 'إلغاء التثبيت',
        'Copy': 'نسخ',
        'Delete Message': 'حذف الرسالة',
        'Confirm Delete': 'تأكيد الحذف',
        'Are you sure you want to delete this message? This action cannot be undone.': 'متأكد إنك عايز تحذف الرسالة دي؟ مش هتقدر ترجع فيها.',
        'This action cannot be undone.': 'مش هتقدر ترجع في الخطوة دي.',
        'Network error while deleting message': 'خطأ في الشبكة أثناء حذف الرسالة',
        '❌ Network error while deleting message': '❌ خطأ في الشبكة أثناء حذف الرسالة',
        '🗑️ Message deleted': '🗑️ تم حذف الرسالة',
        'Failed to upload file': 'فشل رفع الملف',
        'Image must be under 5MB': 'الصورة لازم تكون أقل من 5 ميجا',
        'File size must be under 5MB': 'حجم الملف لازم يكون أقل من 5 ميجا',
        'Create Post': 'إنشاء منشور',
        'Edit Post': 'تعديل المنشور',
        'New Post': 'منشور جديد',
        'Post title *': 'عنوان المنشور *',
        'Post body *': 'محتوى المنشور *',
        'Write your post... *': 'اكتب منشورك... *',
        'Tags (press Enter or comma to add)': 'التاجات (اضغط Enter أو فاصلة للإضافة)',
        'Add tag...': 'أضف تاج...',
        'e.g. Make.com, n8n, Zapier': 'مثال: Make.com, n8n, Zapier',
        '📎 Click to choose image or drag & drop': '📎 اضغط لاختيار صورة أو اسحبها هنا',
        'Title is required': 'العنوان مطلوب',
        'Body must be at least 10 characters': 'المحتوى لازم يكون 10 حروف على الأقل',
        'Post created! ✨': 'تم نشر المنشور! ✨',
        'Post created successfully': 'تم نشر المنشور بنجاح',
        'Post updated! ✅': 'تم تعديل المنشور! ✅',
        'Post deleted': 'تم حذف المنشور',
        'Post deleted successfully': 'تم حذف المنشور بنجاح',
        'Post pinned 📌': 'تم تثبيت المنشور 📌',
        'Post unpinned': 'تم إلغاء تثبيت المنشور',
        'Failed to create post': 'فشل إنشاء المنشور',
        'Failed to edit post': 'فشل تعديل المنشور',
        'Failed to delete post': 'فشل حذف المنشور',
        'Failed to load posts': 'فشل تحميل المنشورات',
        'Failed to toggle pin': 'فشل تغيير التثبيت',
        'Posting...': 'جاري النشر...',
        'Delete Post?': 'حذف المنشور؟',
        'This post and all its comments will be permanently deleted.': 'المنشور ده وكل تعليقاته هيتحذفوا نهائيًا.',
        'Delete Comment?': 'حذف التعليق؟',
        'This comment will be permanently deleted.': 'التعليق ده هيتحذف نهائيًا.',
        'Comment deleted': 'تم حذف التعليق',
        'Comments': 'التعليقات',
        'Write a comment...': 'اكتب تعليق...',
        'Write a reply...': 'اكتب رد...',
        'Failed to post comment': 'فشل إرسال التعليق',
        'Failed to post reply': 'فشل إرسال الرد',
        'Failed to delete comment': 'فشل حذف التعليق',
        'Failed to load comments': 'فشل تحميل التعليقات',
        'Are you sure you want to delete this comment?': 'متأكد إنك عايز تحذف التعليق ده؟',
        'See more': 'شوف أكتر',
        'See less': 'شوف أقل',
        'Latest': 'الأحدث',
        'Top': 'الأعلى',
        '🕐 Latest': '🕐 الأحدث',
        '🔥 Top': '🔥 الأعلى',
        'No posts yet in this channel': 'مفيش منشورات في القناة دي لسه',
        'No posts yet in this channel. Be the first to post!': 'مفيش منشورات في القناة دي لسه. كن أول واحد ينشر!',
        'Be the First to Post': 'كن أول واحد ينشر',
        'Be the first to introduce yourself and start a great conversation!': 'كن أول واحد يعرّف بنفسه ويبدأ محادثة جميلة!',
        '🤝 Post Your Introduction': '🤝 انشر تعريفك بنفسك',
        'Introduce Yourself 👋': 'عرّف بنفسك 👋',
        'New here? Introduce yourself to the community!': 'جديد هنا؟ عرّف نفسك للمجتمع!',
        'Post Introduction': 'انشر التعريف',
        'Back to Messages': 'رجوع للرسائل',
        'New Message': 'رسالة جديدة',
        '✏️ New Message': '✏️ رسالة جديدة',
        'Team': 'الفريق',
        'CEO': 'المدير التنفيذي',
        'Community Manager': 'مدير المجتمع',
        'Technical Engineer': 'مهندس تقني',
        'Next →': 'التالي ←',
        '← Prev': '→ السابق',
        'Welcome To Ghawy': 'أهلاً بيك في Ghawy',
        'Start Here': 'ابدأ من هنا',
        'How to Use the Platform': 'إزاي تستخدم المنصة',
        'Watch this video first to know how to use Ghawy and benefit from it': 'اتفرج على الفيديو ده الأول عشان تعرف تستخدم Ghawy وتستفيد منه',
        'The introductory video will be available soon': 'الفيديو التعريفي هيكون متاح قريب',
        '👋 Welcome! Here you will find everything you need to start your journey with Ghawy': '👋 أهلاً بيك! هنا هتلاقي كل اللي محتاجه عشان تبدأ رحلتك مع Ghawy',
        'Your browser does not support the video tag.': 'متصفحك مش بيدعم تشغيل الفيديو.',
        '🔒 ADMIN NOTES': '🔒 ملاحظات الأدمن',
        'Write a private note about this member...': 'اكتب ملاحظة خاصة عن العضو ده...',
        'Save Note': 'حفظ الملاحظة',
        '✓ Note saved': '✓ تم حفظ الملاحظة',
        'Failed to save': 'فشل الحفظ',
        'Failed to create DM': 'فشل فتح المحادثة',
        'Failed to open DM': 'فشل فتح المحادثة',
        'Failed to mark read': 'فشل تعليم الرسائل كمقروءة',
        'Reaction failed': 'فشل التفاعل',
        'Reaction could not be saved': 'معرفناش نحفظ التفاعل',
        'Reconnecting. Reaction will sync after the socket is back.': 'جاري إعادة الاتصال. التفاعل هيتزامن أول ما الاتصال يرجع.',
        'Attachment': 'مرفق',
        'Ghawy Bot': 'Ghawy Bot',
        'System': 'النظام',
        'Support Team': 'فريق الدعم',

        /* ── AI Updates ── */
        'Post Update': 'نشر تحديث',
        'Create AI Update': 'إنشاء تحديث AI',
        'Update title...': 'عنوان التحديث...',
        "What's new in AI?...": 'إيه الجديد في الـ AI؟...',
        'Title': 'العنوان',
        'Body': 'المحتوى',
        'Text': 'نص',
        'Photo': 'صورة',
        'Video': 'فيديو',
        'Poll': 'استطلاع',
        'Poll Question': 'سؤال الاستطلاع',
        'Options (2-4)': 'الاختيارات (2-4)',
        'Option 1': 'اختيار 1',
        'Option 2': 'اختيار 2',
        'Add Option': 'أضف اختيار',
        'Maximum 4 options allowed': 'أقصى عدد اختيارات هو 4',
        'Poll requires a question and at least 2 options': 'الاستطلاع محتاج سؤال واختيارين على الأقل',
        'Upload Image': 'رفع صورة',
        'Choose File': 'اختار ملف',
        'No file chosen': 'مفيش ملف مختار',
        'Ask a question...': 'اسأل سؤال...',
        'No AI Updates Yet': 'مفيش تحديثات AI لسه',
        'Check back later for the latest news and polls.': 'ارجع تاني بعدين لأحدث الأخبار والاستطلاعات.',
        /* ── AI Updates redesign 2026 ── */
        'Follow the latest AI news, tools and models from everywhere.': 'تابع أحدث أخبار وأدوات ونماذج الذكاء الاصطناعي من كل مكان.',
        'New this week': 'جديد هذا الأسبوع',
        'New tools': 'أدوات جديدة',
        'New models': 'نماذج جديدة',
        'Discussions': 'النقاشات',
        'All': 'الكل',
        'News': 'أخبار',
        'Tools': 'أدوات',
        'Models': 'نماذج',
        'Updates': 'تحديثات',
        'Tutorials': 'شروحات',
        'Latest': 'الأحدث',
        'Most Popular': 'الأكثر تفاعلاً',
        'New Post': 'منشور جديد',
        'View All': 'عرض الكل',
        'New Tools': 'أحدث الأدوات',
        "What's New": 'الجديد',
        'Top Contributors': 'أكثر المساهمين',
        'Get AI updates in your inbox': 'احصل على تحديثات AI في بريدك',
        'A weekly digest of the most important AI news, tools and models.': 'ملخص أسبوعي لأهم أخبار وأدوات ونماذج الذكاء الاصطناعي.',
        'Subscribe Now': 'اشترك الآن',
        'Read More': 'اقرأ المزيد',
        'Show Less': 'عرض أقل',
        'Category': 'التصنيف',
        'Nothing here yet': 'مفيش حاجة هنا لسه',
        'No posts in this category. Try another filter.': 'مفيش منشورات في التصنيف ده. جرّب فلتر تاني.',
        'Error loading feed. Please try again.': 'حصل خطأ في تحميل التحديثات. حاول تاني.',
        'Error adding comment': 'حصل خطأ في إضافة التعليق',
        'Error adding reply': 'حصل خطأ في إضافة الرد',
        'Error deleting comment': 'حصل خطأ في حذف التعليق',
        'Error deleting post': 'حصل خطأ في حذف المنشور',
        'Error pinning post': 'حصل خطأ في تثبيت المنشور',
        'Error toggling reaction': 'حصل خطأ في التفاعل',
        'Failed to react': 'فشل التفاعل',
        'Failed to vote': 'فشل التصويت',
        'Manage': 'إدارة',

        /* ── Build With Me ── */
        'Learn real skills by building real projects live with experts.': 'اتعلم مهارات حقيقية ببناء مشاريع حقيقية لايف مع خبراء.',
        'Live Sessions': 'جلسات لايف',
        'Live Schedule': 'جدول اللايف',
        'Loading sessions...': 'جاري تحميل الجلسات...',
        'My Registrations': 'تسجيلاتي',
        'Upcoming': 'القادمة',
        'Past Sessions': 'الجلسات السابقة',
        'Top Projects Built Live': 'أفضل المشاريع اللي اتبنت لايف',
        'Active Learners': 'متعلمين نشطين',
        'Hours Streamed': 'ساعات بث',
        'Projects Built': 'مشاريع اتبنت',
        'Registered successfully! ✅': 'تم التسجيل بنجاح! ✅',
        'Registration cancelled': 'تم إلغاء التسجيل',
        'Session link coming soon!': 'لينك الجلسة جاي قريب!',

        /* ── Guest of Honors ── */
        'Learn From The Best. Get Inspired.': 'اتعلم من الأفضل. خد إلهامك.',
        'Level Up.': 'ارتقِ بمستواك.',
        'Exclusive talks, workshops, and live sessions with top founders, marketers, engineers, creators, and industry leaders.': 'لقاءات وورش عمل وجلسات لايف حصرية مع أفضل المؤسسين والمسوّقين والمهندسين وصنّاع المحتوى وقادة المجال.',
        'Featured Guest': 'الضيف المميز',
        'Featured Guests': 'الضيوف المميزين',
        'All Guests': 'كل الضيوف',
        'All Categories': 'كل التصنيفات',
        'Categories': 'التصنيفات',
        'Tech': 'تكنولوجيا',
        'Business': 'بيزنس',
        'Marketing': 'تسويق',
        'Design': 'تصميم',
        'AI': 'AI',
        'Sessions': 'الجلسات',
        'Sessions Completed': 'جلسات مكتملة',
        'Sessions This Month': 'جلسات الشهر ده',
        'Upcoming Sessions': 'الجلسات الجاية',
        'Guests Hosted': 'ضيوف استضفناهم',
        'Total Guests': 'إجمالي الضيوف',
        'Total Attendees': 'إجمالي الحضور',
        'Attendees': 'الحضور',
        'Hours Watched': 'ساعات مشاهدة',
        'Average Rating': 'متوسط التقييم',
        'Community Rating': 'تقييم المجتمع',
        'Community Impact': 'أثر المجتمع',
        'Rating': 'التقييم',
        'Watch Latest Session': 'شاهد آخر جلسة',
        'View All Guests →': 'عرض كل الضيوف ←',
        'View Full Schedule →': 'عرض الجدول الكامل ←',
        "What You'll Gain": 'إيه اللي هتكسبه',
        'Learn from industry leaders': 'اتعلم من قادة المجال',
        'Exclusive insights': 'رؤى حصرية',
        'Networking opportunities': 'فرص تواصل',
        'Practical frameworks': 'أطر عملية',
        'Real-world case studies': 'دراسات حالة حقيقية',
        'Career acceleration': 'تسريع مسارك المهني',
        'Know someone inspiring?': 'تعرف حد ملهم؟',
        'Help us find the next great guest.': 'ساعدنا نلاقي الضيف الجاي.',
        'Suggest a Guest': 'اقترح ضيف',
        'Suggest Guest': 'اقترح ضيف',
        'Submit Suggestion': 'إرسال الاقتراح',
        'Guest Name': 'اسم الضيف',
        'e.g. Nabil Ahmed': 'مثال: نبيل أحمد',
        'Why should we invite them?': 'ليه نعزمه؟',
        'Brief reason...': 'سبب مختصر...',
        'Please enter a guest name': 'من فضلك اكتب اسم الضيف',
        'Please provide a reason': 'من فضلك اكتب السبب',
        'Thank you! Your suggestion has been received.': 'شكراً! وصلنا اقتراحك.',
        'Error suggesting guest.': 'حصل خطأ في إرسال الاقتراح.',

        /* ── Profile ── */
        'Profile': 'البروفايل',
        'Edit Profile': 'تعديل البروفايل',
        'Learning Progress': 'تقدم التعلم',
        'Videos Watched': 'فيديوهات اتشافت',
        'Exams Completed': 'اختبارات مكتملة',
        'Average Score': 'متوسط الدرجات',
        'Longest Streak': 'أطول سلسلة أيام',
        'Next Achievement': 'الإنجاز الجاي',
        'Active subscription': 'اشتراك نشط',
        'First Login': 'أول تسجيل دخول',
        'Joined the platform': 'انضم للمنصة',
        'First Post': 'أول منشور',
        'Shared your voice': 'شاركت بصوتك',
        '7-Day Streak': 'سلسلة 7 أيام',
        'Login 7 days in a row': 'سجّل دخول 7 أيام ورا بعض',
        'Course Complete': 'إكمال كورس',
        'Finish a full course': 'خلّص كورس كامل',
        'Complete all modules': 'كمّل كل الوحدات',
        'Top Student': 'الطالب المتفوق',
        'Reach the top of the leaderboard': 'وصّل لقمة لوحة الصدارة',
        'Progress:': 'التقدم:',
        '100% Progress': 'تقدم 100%',
        '0 / 7 Unlocked': '0 / 7 مفتوحة',
        '/ 7 Days': '/ 7 أيام',
        '12 Days': '12 يوم',

        /* ── Profile settings ── */
        'Account': 'الحساب',
        'Subscription': 'الاشتراك',
        'Start Date': 'تاريخ البداية',
        'End Date': 'تاريخ الانتهاء',
        'Remaining Days': 'الأيام المتبقية',
        'Renew Subscription': 'تجديد الاشتراك',
        'Subscription Expired': 'الاشتراك منتهي',
        'Subscribe now to access all content': 'اشترك دلوقتي للوصول لكل المحتوى',
        'Subscribe Now': 'اشترك الآن',
        'Lifetime access (never expires)': 'وصول دائم (لا ينتهي)',
        'Expired': 'منتهي',
        'Member ID': 'رقم العضوية',
        'Send this number to the team when you need help — it is how they find your account.': 'ابعت الرقم ده للفريق لما تحتاج مساعدة — بيه بيلاقوا حسابك على طول.',
        'Copied': 'اتنسخ',
        'Personal Info': 'البيانات الشخصية',
        'Full Name': 'الاسم الكامل',
        'Your name': 'اسمك',
        'Email': 'البريد الإلكتروني',
        'Bio': 'نبذة عنك',
        'Tell us about yourself...': 'قولنا عن نفسك...',
        'Profile Picture': 'صورة البروفايل',
        'Recommended size: 256x256px. Max 2MB.': 'الحجم المقترح: 256×256 بكسل. أقصى حجم 2 ميجا.',
        'Social Media Link': 'لينك السوشيال ميديا',
        'Change Password': 'تغيير كلمة المرور',
        'Current Password': 'كلمة المرور الحالية',
        'New Password': 'كلمة المرور الجديدة',
        'Confirm Password': 'تأكيد كلمة المرور',
        'Preferences': 'التفضيلات',
        'Language': 'اللغة',
        'Appearance': 'المظهر',
        'Dark': 'داكن',
        'Light': 'فاتح',
        'English': 'English',
        'Email Notifications': 'إشعارات البريد',
        'Chat Notifications': 'إشعارات الشات',
        'Community Mentions': 'الإشارات في المجتمع',
        'New Course Alerts': 'تنبيهات الكورسات الجديدة',
        'show your profile to other members': 'إظهار بروفايلك لباقي الأعضاء',
        'Danger Zone': 'منطقة الخطر',
        'Delete Account': 'حذف الحساب',
        '⚠️ Delete Account': '⚠️ حذف الحساب',
        'Once you delete your account, there is no going back.': 'لو حذفت حسابك، مفيش رجوع.',
        'Are you sure you want to delete your account? This action cannot be undone and all your data will be permanently removed.': 'متأكد إنك عايز تحذف حسابك؟ الخطوة دي مش هتقدر ترجع فيها وكل بياناتك هتتمسح نهائيًا.',
        'Please type': 'من فضلك اكتب',
        'to confirm.': 'للتأكيد.',
        'Yes, Delete': 'أيوه، احذف',
        'Error deleting account': 'حصل خطأ في حذف الحساب',
        '✓ Saved': '✓ تم الحفظ',
        'Failed': 'فشل',

        /* ── Help center ── */
        'Email us': 'راسلنا على الإيميل',
        "Send us your issue and we'll get back to you soon": 'بعت مشكلتك وهنرد عليك في أقرب وقت',
        'Open Email': 'فتح الإيميل',
        'Copy Email': 'نسخ الإيميل',
        '✓ Copied': '✓ تم النسخ',
        'Contact us on WhatsApp': 'تواصل معنا على الواتساب',
        "Send a message and we'll reply quickly": 'ابعت رسالة وهنرد عليك بسرعة',
        'Open WhatsApp': 'فتح واتساب',
        'Talk to the support team directly': 'تكلم فريق الدعم مباشرة',
        'You can reach any of our team members inside Ghawy': 'تقدر تتواصل مع أي عضو من فريقنا داخل غاوي',
        'Send Message': 'إرسال رسالة',
        "We're here to help you": 'إحنا هنا نساعدك',
        'Please read our': 'من فضلك اقرأ',
        'Terms & Conditions': 'الشروط والأحكام',
        'Privacy Policy': 'سياسة الخصوصية',
        'before contacting us.': 'قبل التواصل معنا.',
        'and': 'و',

        /* ── Misc toasts / errors ── */
        'Connection error. Please try again.': 'خطأ في الاتصال. حاول تاني.',
        'No connection to server': 'مفيش اتصال بالسيرفر',
        'Upload failed. Please try again.': 'فشل الرفع. حاول تاني.',
        'Error uploading. Please try again.': 'حصل خطأ في الرفع. حاول تاني.',
        'File too large. Maximum size is 5MB.': 'الملف كبير أوي. أقصى حجم 5 ميجا.',
        'Only JPG, PNG, WEBP files are allowed': 'مسموح فقط بملفات JPG وPNG وWEBP',
        'Invalid file type. Please upload a JPG, PNG, WebP, or PDF.': 'نوع ملف غير مدعوم. ارفع JPG أو PNG أو WebP أو PDF.',
        'Must be an image file': 'لازم يكون ملف صورة',
        'Must be a PDF file': 'لازم يكون ملف PDF',
        'Failed to copy text': 'فشل نسخ النص',
        'API Error': 'خطأ في الاتصال بالسيرفر'
    };

    /* ─── Interpolated patterns (dynamic counters, relative time, …) ── */
    var PATTERNS = [
        [/^(\d+)\s*m ago$/, 'منذ $1 د'],
        [/^(\d+)\s*h ago$/, 'منذ $1 س'],
        [/^(\d+)\s*d ago$/, 'منذ $1 يوم'],
        [/^(\d+)\s*(?:seconds?|s) ago$/, 'منذ $1 ث'],
        [/^just now$/i, 'دلوقتي حالاً'],
        [/^(\d+) [Ll]essons?$/, '$1 درس'],
        [/^(\d+)% Complete$/, 'مكتمل $1%'],
        [/^Completed (\d+) of (\d+) lessons$/, 'أكملت $1 من $2 درس'],
        [/^(\d+) posts?$/, '$1 منشور'],
        [/^(\d+) votes?$/, '$1 صوت'],
        [/^(\d+) watching$/, '$1 بيشاهدوا'],
        [/^(\d+) [Oo]nline$/, '$1 متصل'],
        [/^(\d+) min read$/, 'قراءة $1 دقيقة'],
        [/^(\d+) [Mm]embers?$/, '$1 عضو'],
        [/^(\d+) Days?$/, '$1 يوم'],
        [/^(\d+) days?$/, '$1 يوم'],
        [/^scroll to see (\d+) more$/, 'انزل تحت عشان تشوف $1 كمان'],
        [/^With (.+)$/, 'مع $1'],
        [/^Reply to (.+)$/, 'رد على $1'],
        [/^Read by (\d+)$/, 'قرأها $1'],
        [/^Submitted (.+)$/, 'تم التسليم $1'],
        [/^Member since (.+)$/, 'عضو منذ $1'],
        [/^Welcome back, (.+)$/, 'أهلاً بعودتك، $1'],
        [/^Best Score: (\d+)%$/, 'أفضل درجة: $1%'],
        [/^Community Avg: (\d+)%$/, 'متوسط المجتمع: $1%'],
        [/^Message #(.+)$/, 'رسالة في #$1'],
        /* Exams */
        [/^Passed · (\d+)%$/, 'ناجح · $1%'],
        [/^Best: (\d+)%$/, 'أفضل: $1%'],
        [/^(\d+) questions? · Pass mark (\d+)%$/, '$1 سؤال · درجة النجاح $2%'],
        [/^(\d+) questions? · Pass (\d+)%$/, '$1 سؤال · النجاح $2%'],
        [/^(\d+) of (\d+) correct · Pass mark (\d+)%$/, '$1 من $2 صح · درجة النجاح $3%'],
        [/^(\d+) questions?$/, '$1 سؤال'],
        [/^Today (\d{1,2}:\d{2} [AP]M)$/, 'النهارده $1'],
        [/^Yesterday (\d{1,2}:\d{2} [AP]M)$/, 'امبارح $1']
    ];

    var ATTRS = ['placeholder', 'title', 'aria-label', 'alt', 'data-tooltip'];
    var LS_KEY = 'ghawy_lang';

    var active = false;            // Arabic currently applied to the DOM?
    var textOrig = new WeakMap();  // TextNode -> original English value
    var attrOrig = new WeakMap();  // Element  -> { attrName: original }
    var titleOrig = null;

    function lookup(s) {
        if (!s) return null;
        var key = s.replace(/\s+/g, ' ').trim();
        if (key.length < 2) return null;
        if (Object.prototype.hasOwnProperty.call(DICT, key)) return DICT[key];
        for (var i = 0; i < PATTERNS.length; i++) {
            if (PATTERNS[i][0].test(key)) return key.replace(PATTERNS[i][0], PATTERNS[i][1]);
        }
        return null;
    }

    function shouldSkip(el) {
        for (var n = el; n && n.nodeType === 1; n = n.parentElement) {
            var tag = n.tagName;
            if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'TEXTAREA' || tag === 'CODE' || tag === 'PRE') return true;
            if (n.hasAttribute('data-no-i18n')) return true;
        }
        return el && el.isContentEditable ? true : false;
    }

    /* Attribute translation (placeholder/title/…) is UI chrome even on a
       TEXTAREA — only its *content* is user text. Skip less aggressively. */
    function shouldSkipAttrs(el) {
        for (var n = el; n && n.nodeType === 1; n = n.parentElement) {
            var tag = n.tagName;
            if (tag === 'SCRIPT' || tag === 'STYLE') return true;
            if (n.hasAttribute('data-no-i18n')) return true;
        }
        return false;
    }

    function translateTextNode(node) {
        var t = node.nodeValue;
        var ar = lookup(t);
        if (ar == null) return;
        var lead = t.match(/^\s*/)[0];
        var trail = t.match(/\s*$/)[0];
        var out = lead + ar + trail;
        if (out === t) return; // identity translation — writing would loop the observer
        textOrig.set(node, t);
        node.nodeValue = out;
    }

    function translateAttrs(el) {
        for (var i = 0; i < ATTRS.length; i++) {
            var a = ATTRS[i];
            if (!el.hasAttribute(a)) continue;
            var v = el.getAttribute(a);
            var ar = lookup(v);
            if (ar == null || ar === v) continue;
            var store = attrOrig.get(el) || {};
            store[a] = v;
            attrOrig.set(el, store);
            el.setAttribute(a, ar);
        }
    }

    function walk(root) {
        if (root.nodeType === 3) {
            if (root.parentElement && !shouldSkip(root.parentElement)) translateTextNode(root);
            return;
        }
        if (root.nodeType !== 1) return;
        if (!shouldSkipAttrs(root)) translateAttrs(root);
        if (shouldSkip(root)) return;
        var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, null);
        var n;
        while ((n = w.nextNode())) {
            if (n.nodeType === 3) {
                if (n.parentElement && !shouldSkip(n.parentElement)) translateTextNode(n);
            } else if (!shouldSkipAttrs(n)) {
                translateAttrs(n);
            }
        }
    }

    function restoreAll() {
        if (!document.body) return;
        var w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, null);
        var n;
        while ((n = w.nextNode())) {
            if (n.nodeType === 3) {
                if (textOrig.has(n)) { n.nodeValue = textOrig.get(n); textOrig.delete(n); }
            } else if (attrOrig.has(n)) {
                var store = attrOrig.get(n);
                for (var a in store) n.setAttribute(a, store[a]);
                attrOrig.delete(n);
            }
        }
        if (titleOrig != null) { document.title = titleOrig; titleOrig = null; }
    }

    function setDir(lang) {
        var html = document.documentElement;
        if (html.getAttribute('lang') !== lang) html.setAttribute('lang', lang);
        var dir = lang === 'ar' ? 'rtl' : 'ltr';
        if (html.getAttribute('dir') !== dir) html.setAttribute('dir', dir);
    }

    function applyArabic() {
        active = true;
        setDir('ar');
        if (document.body) walk(document.body);
        var tAr = lookup(document.title);
        if (tAr != null) {
            if (titleOrig == null) titleOrig = document.title;
            document.title = tAr;
        }
        startObserver();
    }

    function applyEnglish() {
        active = false;
        setDir('en');
        restoreAll();
    }

    /* ─── Keep dynamically rendered content translated ── */
    var mo = null;
    function startObserver() {
        if (mo || !document.body) return;
        mo = new MutationObserver(function (muts) {
            if (!active) return;
            for (var i = 0; i < muts.length; i++) {
                var m = muts[i];
                if (m.type === 'childList') {
                    for (var j = 0; j < m.addedNodes.length; j++) walk(m.addedNodes[j]);
                } else if (m.type === 'characterData') {
                    var node = m.target;
                    if (node.parentElement && !shouldSkip(node.parentElement)) translateTextNode(node);
                } else if (m.type === 'attributes' && m.target.nodeType === 1) {
                    if (!shouldSkipAttrs(m.target)) translateAttrs(m.target);
                }
            }
        });
        mo.observe(document.body, {
            childList: true,
            subtree: true,
            characterData: true,
            attributes: true,
            attributeFilter: ATTRS
        });
    }

    /* ─── Live switch from Settings (i18n.js sets <html lang>) ── */
    new MutationObserver(function () {
        var lang = document.documentElement.getAttribute('lang') === 'ar' ? 'ar' : 'en';
        if (lang === 'ar' && !active) applyArabic();
        else if (lang === 'en' && active) applyEnglish();
    }).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });

    /* ─── Init ── */
    var pref = null;
    try { pref = localStorage.getItem(LS_KEY); } catch (e) { /* private mode */ }

    // Arabic is the site-wide default now — only an explicit English choice
    // keeps the community pages in English.
    //
    // The decision is made twice on purpose. This file runs in <head>, but the
    // pages that also load i18n.js load it at the END of <body> — so between
    // the read above and DOMContentLoaded another engine can legitimately set
    // the language (i18n.js migrating the legacy key and applying English is
    // exactly that case). Firing the head-time decision blindly on
    // DOMContentLoaded stomped that English back to Arabic *after* the page
    // had already rendered in English, which is what "I pick English, refresh,
    // and it comes back Arabic" looked like from the outside.
    function initApply() {
        var now = null;
        try { now = localStorage.getItem(LS_KEY); } catch (e) { /* ignore */ }
        // setDir('ar') below already put lang=ar on <html>, so finding 'en'
        // here means somebody deliberately switched it after we ran — honour
        // that instead of overwriting it.
        if (now === 'en' || document.documentElement.getAttribute('lang') === 'en') {
            active = false;
            setDir('en');
            return;
        }
        applyArabic();
    }

    if (pref !== 'en') {
        // Flip direction immediately (script is in <head>) to avoid an LTR flash.
        setDir('ar');
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initApply);
        } else {
            initApply();
        }
    }
})();
