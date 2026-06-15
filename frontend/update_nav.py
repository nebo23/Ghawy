import os
import re

# Read dashboard.html
with open('dashboard.html', 'r', encoding='utf-8') as f:
    dash_content = f.read()

# Extract sidebar
sidebar_match = re.search(r'(<aside class="dash-sidebar" id="dashSidebar">.*?</aside>)', dash_content, re.DOTALL)
if not sidebar_match:
    print("Could not find sidebar in dashboard.html")
    exit(1)

new_sidebar = sidebar_match.group(1)

# Mapping of filenames to the ID of the nav-item that should be active
active_map = {
    'dashboard.html': 'nav-dashboard',
    'courses.html': 'nav-courses',
    'course-detail.html': 'nav-courses',
    'admin-course-detail.html': 'nav-courses',
    'course-detail-test.html': 'nav-courses',
    'chat.html': 'nav-chat',
    'direct-messages.html': 'nav-dm',
    'ai-updates.html': 'nav-ai',
    'build-with-me.html': 'nav-bwm',
    'guest-of-honors.html': 'nav-goh',
    'profile.html': 'nav-ach',
    'profile-settings.html': 'nav-settings',
    'teamdashboard.html': 'nav-team',
    'help-center.html': 'nav-help'
}

html_files = [f for f in os.listdir('.') if f.endswith('.html')]

for file in html_files:
    if file == 'login.html' or file == 'register.html' or file == 'payment.html':
        continue
        
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Replace sidebar
    if '<aside class="dash-sidebar" id="dashSidebar">' in content:
        content = re.sub(r'<aside class="dash-sidebar" id="dashSidebar">.*?</aside>', new_sidebar, content, flags=re.DOTALL)
        
        # Add CSS if missing
        if 'dashboard-new.css' not in content:
            content = re.sub(r'(</head>)', r'    <link rel="stylesheet" href="src/css/dashboard-new.css?v=10" />\n\1', content, count=1, flags=re.IGNORECASE)
            
        # Add JS if missing
        if 'dashboard-new.js' not in content:
            content = re.sub(r'(</body>)', r'<script src="src/js/dashboard-new.js?v=10"></script>\n\1', content, count=1, flags=re.IGNORECASE)
            
        # Set active class
        # First remove active from all
        content = re.sub(r'(class="nav-item)\s+active(")', r'\1\2', content)
        
        # Then add active to the correct one
        active_id = active_map.get(file)
        if active_id:
            content = re.sub(rf'(id="{active_id}")', r'class="nav-item active" \1', content)
            # Remove class="nav-item" since we added it
            content = re.sub(rf'class="nav-item"\s+class="nav-item active" id="{active_id}"', rf'class="nav-item active" id="{active_id}"', content)
            
        with open(file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {file}")
