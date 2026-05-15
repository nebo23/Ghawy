import codecs
import re

with codecs.open('frontend/index.html', 'r', 'utf-8', errors='ignore') as f:
    html = f.read()

# We need to find <div class="lessons-accordion"> and its matching closing tag.
# A regex to match the accordion div and its entire contents:
pattern = re.compile(r'<div class="lessons-accordion">.*?</ul>\s*</div>\s*</div>', re.DOTALL)

button_html = '''<a href="course.html" class="course-content-btn" style="display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; padding: 12px; background: rgba(193, 255, 17, 0.05); border: 1px solid rgba(193, 255, 17, 0.2); color: var(--gold); border-radius: 8px; text-decoration: none; font-weight: 700; transition: all 0.3s; margin-top: auto;">
                                        <i class="fa-solid fa-list-check"></i> محتويات الكورس
                                    </a>'''

new_html = pattern.sub(button_html, html)

with codecs.open('frontend/index.html', 'w', 'utf-8') as f:
    f.write(new_html)

print("Replaced lessons-accordion with buttons")
