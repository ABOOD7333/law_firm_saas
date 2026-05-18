import os
import glob

base_dir = os.path.dirname(__file__)
py_files = glob.glob(os.path.join(base_dir, "**/*.py"), recursive=True)

for filepath in py_files:
    if "site-packages" in filepath or ".venv" in filepath: continue
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    
    # 1. Fix the double-quote inside f-string issue:
    # safe_filename = f"{int(time.time())}_" + "".join(c for c in file.filename if c.isalnum() or c in ' ._-')
    bad_fstring = 'safe_filename = f"{int(time.time())}_{"".join(c for c in file.filename if c.isalnum() or c in \' ._-\')}"'
    good_fstring = 'safe_filename = f"{int(time.time())}_" + "".join(c for c in file.filename if c.isalnum() or c in \' ._-\')'
    new_content = new_content.replace(bad_fstring, good_fstring)
    
    # 2. Fix the .like backslash issue:
    bad_replace_1 = "replace(\\'%\\', \\'\\')"
    good_replace_1 = "replace('%', '')"
    bad_replace_2 = "replace(\\'_\\', \\'\\')"
    good_replace_2 = "replace('_', '')"
    new_content = new_content.replace(bad_replace_1, good_replace_1)
    new_content = new_content.replace(bad_replace_2, good_replace_2)
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"✅ تم إصلاح خطأ التركيب (Syntax Error) في ملف: {os.path.basename(filepath)}")

print("--------------------------------------------------")
print("جاهز الآن للرفع!")
