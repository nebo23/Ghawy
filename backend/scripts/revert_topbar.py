import os
import glob
import re

html_files = glob.glob(r"c:\Users\nabil\Code\Ghawy\frontend\*.html")

titles = {
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
    "admin-course-detail.html": ("Admin Course Details", "تفاصيل الكورس (مسؤول)", "adminCourseDetails")
}

remove_pattern = re.compile(r'\s*<div class="topbar-page-title">.*?<\/div>', re.DOTALL)

for file in html_files:
    filename = os.path.basename(file)
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    content = remove_pattern.sub('', content)

    if filename in titles:
        en_title, ar_title, i18n_key = titles[filename]
        
        breadcrumb_html = f'''
                <div class="breadcrumb">
                    <a href="dashboard.html?v=2"><i data-lucide="layout-grid" class="nav-icon"></i></a>
                    <i data-lucide="chevron-right" style="width:12px;height:12px;"></i>
                    <span data-i18n="{i18n_key}">{ar_title}</span>
                </div>'''

        # Check if dash-content already has a breadcrumb right after it
        # We need to inject breadcrumb if it's missing.
        # Let's search for <div class="dash-content">
        if '<div class="dash-content">' in content:
            dash_content_idx = content.find('<div class="dash-content">')
            # Look at the next few lines to see if there is already a breadcrumb
            sub_content = content[dash_content_idx:dash_content_idx+300]
            if 'class="breadcrumb"' not in sub_content and 'class="goh-breadcrumb"' not in sub_content and 'class="bwm-breadcrumb"' not in sub_content:
                # Inject breadcrumb
                content = content.replace('<div class="dash-content">', '<div class="dash-content">' + breadcrumb_html, 1)

    if content != original_content:
        with open(file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filename}")

print("Done")
