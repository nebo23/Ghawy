import os
import glob
import re

css_code = """
/* === TOPBAR PAGE TITLE === */
.topbar-page-title {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: 16px;
    flex: 1;
}
.topbar-page-title i.tb-icon {
    color: var(--gold);
    width: 20px;
    height: 20px;
}
.topbar-page-title i.tb-sep {
    color: var(--text-muted);
    font-size: 0.75rem;
}
.topbar-page-title .tb-text {
    font-weight: 700;
    color: var(--gold);
    font-size: 0.95rem;
}
[dir="rtl"] .topbar-page-title {
    margin-left: 0;
    margin-right: 16px;
    flex-direction: row-reverse;
}
[dir="rtl"] .topbar-page-title i.tb-sep {
    transform: scaleX(-1);
}
"""

css_file = r"c:\Users\nabil\Code\Ghawy\frontend\src\css\dashboard.css"
with open(css_file, 'r', encoding='utf-8') as f:
    css_content = f.read()

if ".topbar-page-title" not in css_content:
    css_content = css_content.replace("/* === NOTIFICATIONS PANEL === */", css_code + "\n/* === NOTIFICATIONS PANEL === */")
    with open(css_file, 'w', encoding='utf-8') as f:
        f.write(css_content)

html_files = glob.glob(r"c:\Users\nabil\Code\Ghawy\frontend\*.html")

titles = {
    "dashboard.html": ("Dashboard", "الرئيسية", "dashboard"),
    "courses.html": ("Courses", "الكورسات", "courses"),
    "course-detail.html": ("Course", "الكورس", "course"),
    "teamdashboard.html": ("Team Dashboard", "لوحة تحكم الفريق", "teamDashboard"),
    "guest-of-honors.html": ("Guest of Honors", "ضيوف الشرف", "guestOfHonors"),
    "ai-updates.html": ("AI Updates", "تحديثات الذكاء الاصطناعي", "aiUpdates"),
    "chat.html": ("Community Chat", "محادثات المجتمع", "communityChat"),
    "direct-messages.html": ("Direct Messages", "الرسائل المباشرة", "directMessages"),
    "profile.html": ("Profile", "الملف الشخصي", "profile"),
    "profile-settings.html": ("Settings", "الإعدادات", "settings"),
    "build-with-me.html": ("Build With Me", "تطبيق عملي", "buildWithMe"),
    "admin-course-detail.html": ("Admin Course Details", "تفاصيل الكورس (مسؤول)", "adminCourseDetails"),
    "pay.html": None,
    "payment.html": None,
    "login.html": None,
    "register.html": None,
    "verify-email.html": None,
    "index.html": None,
    "privacy.html": None,
    "terms.html": None,
    "onboarding.html": None
}

for file in html_files:
    filename = os.path.basename(file)
    if filename not in titles or titles[filename] is None:
        continue
    
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'class="topbar-page-title"' in content:
        continue # already processed
        
    en_title, ar_title, i18n_key = titles[filename]
    
    breadcrumb_html = f'''
                <div class="topbar-page-title">
                    <i data-lucide="layout-grid" class="tb-icon"></i>
                    <i class="fa-solid fa-chevron-right tb-sep"></i>
                    <span class="tb-text" data-i18n="{i18n_key}">{ar_title}</span>
                </div>'''

    # Find the hamburger button and inject right after it
    # <button class="hamburger-btn" id="hamburgerBtn" aria-label="Open menu">
    #     <span></span><span></span><span></span>
    # </button>
    
    pattern = r'(<button class="hamburger-btn"[^>]*>[\s\S]*?<\/button>)'
    
    if re.search(pattern, content):
        content = re.sub(pattern, r'\1' + breadcrumb_html, content, count=1)
        with open(file, 'w', encoding='utf-8') as f:
            f.write(content)
            print(f"Updated {filename}")
    else:
        print(f"Could not find hamburger button in {filename}")

print("Done")
