import os
import glob

files = glob.glob('c:/Users/nabil/Code/Ghawy/frontend/*.html')
for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    content = content.replace('href="team.html"', 'href="teamdashboard.html"')
    content = content.replace('<span>Team</span>', '<span>Team Dashboard</span>')
    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)
