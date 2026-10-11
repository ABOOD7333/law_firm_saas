import os
import re

pattern = re.compile(r'TemplateResponse\s*\(\s*["\']')
matches = []

for root, _, files in os.walk('.'):
    if any(x in root for x in ['.git', 'venv', '__pycache__']):
        continue
    for f in files:
        if f.endswith('.py'):
            filepath = os.path.join(root, f)
            with open(filepath, encoding='utf-8', errors='ignore') as fp:
                for idx, line in enumerate(fp):
                    if pattern.search(line):
                        matches.append(f"{filepath}:{idx+1}: {line.strip()}")

print(f"Total matching lines: {len(matches)}")
for m in matches:
    print(m)
