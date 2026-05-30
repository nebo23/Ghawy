import os

filepath = 'src/js/team.js'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\`', '`')
content = content.replace('\\${', '${')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed team.js syntax")
