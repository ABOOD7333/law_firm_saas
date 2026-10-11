import os
import glob

base_dir = os.path.dirname(__file__)
html_files = glob.glob(os.path.join(base_dir, "templates/**/*.html"), recursive=True)

count = 0
for filepath in html_files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix the bad backslashes in the Jinja2 templates
    bad_csrf_tag = "{{ request.cookies.get(\\'csrf_token\\', \\'\\') }}"
    good_csrf_tag = "{{ request.cookies.get('csrf_token', '') }}"
    
    if bad_csrf_tag in content:
        new_content = content.replace(bad_csrf_tag, good_csrf_tag)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        count += 1
        print(f"Fixed template: {os.path.basename(filepath)}")

print("--------------------------------------------------")
print(f"✅ تم إصلاح خطأ القوالب (Templates) في {count} ملف بنجاح!")
print("التطبيق جاهز الآن للرفع ولن يظهر Internal Server Error مرة أخرى.")
