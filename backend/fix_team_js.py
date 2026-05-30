import re

filepath = r'c:\Users\nabil\Code\Ghawy\frontend\src\js\team.js'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace renderCourses function
old_start = 'function renderCourses() {'
# Find start index
idx = content.find(old_start)
if idx == -1:
    print("ERROR: Could not find renderCourses function")
    exit(1)

# Find the matching closing brace
brace_count = 0
i = idx
found_first = False
end_idx = -1
for i in range(idx, len(content)):
    if content[i] == '{':
        brace_count += 1
        found_first = True
    elif content[i] == '}':
        brace_count -= 1
        if found_first and brace_count == 0:
            end_idx = i + 1
            break

if end_idx == -1:
    print("ERROR: Could not find end of renderCourses function")
    exit(1)

old_func = content[idx:end_idx]
print(f"Found renderCourses at char {idx}, length {len(old_func)}")

new_func = r'''function renderCourses() {
  const tbody = document.getElementById('courses-body');
  if (coursesCache.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;color:#555;">No courses found. Add one above.</td></tr>`;
    return;
  }
  tbody.innerHTML = coursesCache.map(c => {
    const thumbSrc = c.thumbnail_url ? (c.thumbnail_url.startsWith('/') ? API + c.thumbnail_url : c.thumbnail_url) : '';
    const pdfHref = c.pdf_url ? (c.pdf_url.startsWith('/') ? API + c.pdf_url : c.pdf_url) : '';
    return `
    <tr>
      <td>
        <div style="display:flex;align-items:center;gap:6px;">
          ${thumbSrc
            ? `<img src="${thumbSrc}" style="width:80px;height:45px;border-radius:4px;object-fit:cover;" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
               <div style="display:none;width:80px;height:45px;border-radius:4px;background:#222;align-items:center;justify-content:center;color:#555;font-size:10px;">No img</div>`
            : `<div style="width:80px;height:45px;border-radius:4px;background:#222;display:flex;align-items:center;justify-content:center;color:#555;font-size:10px;">No img</div>`
          }
          <button class="btn-action" style="font-size:11px;padding:3px 6px;" onclick="uploadCourseThumbnail(${c.id})" title="Upload thumbnail"><i class="fa-solid fa-image"></i></button>
          <input type="file" id="course-thumb-upload-${c.id}" accept="image/*" style="display:none" onchange="handleCourseThumbSelected(event, ${c.id})">
        </div>
      </td>
      <td><strong>${escapeHtml(c.title)}</strong><br><small style="color:#888;">${escapeHtml((c.description||'').substring(0,30))}...</small></td>
      <td>${c.total_lessons || 0} lessons</td>
      <td>
        <div style="display:flex;align-items:center;gap:6px;">
          ${pdfHref ? '<a href="' + pdfHref + '" target="_blank" style="color:#ef4444;text-decoration:none;"><i class="fa-solid fa-file-pdf"></i> View</a>' : '<span style="color:#555;">No PDF</span>'}
          <button class="btn-action" style="font-size:12px;padding:4px 8px;" onclick="uploadCoursePdf(${c.id})">${c.pdf_url ? 'Replace' : 'Upload'}</button>
          <input type="file" id="course-pdf-upload-${c.id}" accept="application/pdf" style="display:none" onchange="handleCoursePdfSelected(event, ${c.id})">
        </div>
      </td>
      <td>
        <label class="switch">
          <input type="checkbox" ${c.is_published ? 'checked' : ''} onchange="toggleCoursePublish(${c.id}, this)">
          <span class="slider round"></span>
        </label>
      </td>
      <td>
        <button class="btn-action" onclick="showLessonsManager(${c.id}, '${escapeHtml(c.title).replace(/'/g, "\\\\'")}')\" style="margin-right:8px;"><i class="fa-solid fa-list"></i> Lessons</button>
        <button class="btn-action" onclick="openEditCourseModal(${c.id})"><i class="fa-solid fa-pen"></i></button>
        <button class="btn-action" onclick="openDeleteCourseModal(${c.id})" style="color:#ef4444;"><i class="fa-solid fa-trash"></i></button>
      </td>
    </tr>`;
  }).join('');
}'''

content = content[:idx] + new_func + content[end_idx:]

# Also replace the old handleCoursePdfSelected (R2-based) with direct file upload
old_pdf_handler = content.find("async function handleCoursePdfSelected(event, courseId)")
if old_pdf_handler != -1:
    # Find end of this function
    brace_count = 0
    found_first = False
    end_pdf = -1
    for i in range(old_pdf_handler, len(content)):
        if content[i] == '{':
            brace_count += 1
            found_first = True
        elif content[i] == '}':
            brace_count -= 1
            if found_first and brace_count == 0:
                end_pdf = i + 1
                break
    
    if end_pdf != -1:
        new_pdf_handler = r'''async function handleCoursePdfSelected(event, courseId) {
  const file = event.target.files[0];
  if (!file) return;
  if (file.type !== 'application/pdf') return showToast('Must be a PDF file', 'error');

  showToast('Uploading PDF...', 'info');
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    const res = await fetch(API + `/courses/admin/courses/${courseId}/upload-pdf`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Upload failed');
    }
    
    showToast('Course PDF uploaded successfully!', 'success');
    loadCoursesTab();
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}'''
        content = content[:old_pdf_handler] + new_pdf_handler + content[end_pdf:]
        print("Replaced handleCoursePdfSelected")

# Add uploadCourseThumbnail and handleCourseThumbSelected functions
# Insert them right after handleCoursePdfSelected
insert_marker = "// ==========================================\n//  LESSONS MANAGER (LEVEL 2)"
insert_idx = content.find(insert_marker)
if insert_idx == -1:
    insert_marker = "// ==========================================\r\n//  LESSONS MANAGER (LEVEL 2)"
    insert_idx = content.find(insert_marker)

if insert_idx != -1:
    thumb_functions = r'''
// -- Course Thumbnail Upload --
function uploadCourseThumbnail(courseId) {
  document.getElementById(`course-thumb-upload-${courseId}`).click();
}

async function handleCourseThumbSelected(event, courseId) {
  const file = event.target.files[0];
  if (!file) return;
  if (!file.type.startsWith('image/')) return showToast('Must be an image file', 'error');

  showToast('Uploading thumbnail...', 'info');
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    const res = await fetch(API + `/courses/admin/courses/${courseId}/upload-thumbnail`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Upload failed');
    }
    
    showToast('Thumbnail uploaded successfully!', 'success');
    loadCoursesTab();
  } catch (e) {
    showToast('Error: ' + e.message, 'error');
  }
}

'''
    content = content[:insert_idx] + thumb_functions + content[insert_idx:]
    print("Added thumbnail upload functions")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done! File updated successfully.")
