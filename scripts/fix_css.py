import codecs
with codecs.open('frontend/src/css/main.css', 'r', 'utf-8', errors='ignore') as f:
    lines = f.readlines()

clean_lines = []
for line in lines:
    if '/* Custom Select and Password Toggle */' in line:
        break
    if '\x00' in line:
        break
    clean_lines.append(line)

with codecs.open('frontend/src/css/main.css', 'w', 'utf-8') as f:
    f.writelines(clean_lines)
    f.write('\n/* Custom Select and Password Toggle */\n')
    f.write('.custom-select {\n')
    f.write('    appearance: none;\n')
    f.write('    -webkit-appearance: none;\n')
    f.write('    -moz-appearance: none;\n')
    f.write('    background-image: url(\'data:image/svg+xml;utf8,<svg fill="%23ffffff" height="24" viewBox="0 0 24 24" width="24" xmlns="http://www.w3.org/2000/svg"><path d="M7 10l5 5 5-5z"/></svg>\');\n')
    f.write('    background-repeat: no-repeat;\n')
    f.write('    background-position: left 12px center;\n')
    f.write('    padding-left: 40px !important;\n')
    f.write('}\n')
    f.write('.custom-select option {\n')
    f.write('    background-color: #0a0a0a;\n')
    f.write('    color: #ffffff;\n')
    f.write('}\n')
    f.write('.password-wrapper {\n')
    f.write('    position: relative;\n')
    f.write('    display: flex;\n')
    f.write('    align-items: center;\n')
    f.write('}\n')
    f.write('.password-wrapper input {\n')
    f.write('    width: 100%;\n')
    f.write('    padding-right: 40px !important;\n')
    f.write('}\n')
    f.write('.toggle-password {\n')
    f.write('    position: absolute;\n')
    f.write('    right: 12px;\n')
    f.write('    background: none;\n')
    f.write('    border: none;\n')
    f.write('    color: var(--muted);\n')
    f.write('    cursor: pointer;\n')
    f.write('    padding: 0;\n')
    f.write('    display: flex;\n')
    f.write('    align-items: center;\n')
    f.write('    justify-content: center;\n')
    f.write('}\n')
    f.write('.toggle-password:hover {\n')
    f.write('    color: var(--gold);\n')
    f.write('}\n')
    f.write('.eye-icon {\n')
    f.write('    width: 20px;\n')
    f.write('    height: 20px;\n')
    f.write('}\n')
