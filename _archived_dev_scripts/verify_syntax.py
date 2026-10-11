import os
import glob

base_dir = os.path.dirname(__file__)
py_files = glob.glob(os.path.join(base_dir, "**/*.py"), recursive=True)

for filepath in py_files:
    if "site-packages" in filepath or ".venv" in filepath: continue
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if "\\'%" in content or "\\'_" in content:
        print(f"WARNING: Found escaped quotes in {filepath}")
    
    if "f\"" in content and "\"\"." in content and "filename" in content:
        print(f"WARNING: Potential double quote inside f-string in {filepath}")
