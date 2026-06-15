import re
import os

files_to_fix = [
    'chat.html', 
    'direct-messages.html', 
    'profile.html', 
    'profile-settings.html',
    'course-detail.html'
]

dropdown_html = """                <div class="topbar-user" id="topbarUser" onclick="document.getElementById('userDropdown').classList.toggle('open')">
                    <div class="topbar-user-avatar" id="topbarAvatar">
                        <i class="fa-solid fa-user" style="width:16px;height:16px;font-size:12px;"></i>
                    </div>
                    <span class="topbar-user-name" id="topbarName">—</span>
                    <i class="fa-solid fa-chevron-down" style="font-size:.6rem;color:var(--text-muted)"></i>
                </div>
                <div class="user-dropdown whop-style" id="userDropdown">
                    <div class="dropdown-profile-header">
                        <div class="dropdown-avatar" id="dropdownAvatarDiv">
                            <i class="fa-solid fa-user" style="font-size:1.2rem;color:var(--gold)"></i>
                        </div>
                        <div class="dropdown-profile-info">
                            <div class="dropdown-name" id="dropdownName">—</div>
                            <a href="profile.html" class="dropdown-view-profile">View profile</a>
                        </div>
                        <a href="profile-settings.html" class="dropdown-settings-icon"><i class="fa-solid fa-gear"></i></a>
                    </div>
                    <div class="dropdown-section">
                        <a href="profile.html#achievements"><i class="fa-solid fa-award"></i> Achievements</a>
                        <a href="help-center.html"><i class="fa-solid fa-circle-question"></i> Help and support</a>
                    </div>
                    <div class="dropdown-divider"></div>
                    <div class="dropdown-section">
                        <button onclick="logout()"><i class="fa-solid fa-right-from-bracket"></i> Sign out</button>
                    </div>
                </div>"""

script_add = """
<script>
    document.addEventListener('click', e => {
        const d = document.getElementById('userDropdown');
        const u = document.getElementById('topbarUser');
        if (d && !d.contains(e.target) && !u.contains(e.target)) d.classList.remove('open');
        const np = document.getElementById('notifPanel');
        const nw = document.getElementById('notifWrapper');
        if (np && nw && !nw.contains(e.target)) np.classList.remove('open');
    });
</script>"""

for filename in files_to_fix:
    filepath = os.path.join(r'c:\Users\nabil\Code\Ghawy\frontend', filename)
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        continue
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Regex to find the topbar-user div and everything inside it up to the closing div
    pattern = r'<div class="topbar-user" id="topbarUser">.*?<span class="topbar-user-name"\s*id="topbarName">—</span>\s*</div>'
    
    if re.search(pattern, content, re.DOTALL):
        # We replace the old div with the new one containing the dropdown
        content = re.sub(pattern, dropdown_html, content, flags=re.DOTALL)
        
        # Add the script if it's not already there
        if "getElementById('userDropdown')" not in content:
            content = content.replace('</body>', script_add + '\n</body>')
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed {filepath}")
    else:
        print(f"Pattern not found in {filepath}")
