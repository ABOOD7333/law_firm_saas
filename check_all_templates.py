import os
import re

template_files = sorted([f for f in os.listdir('templates') if f.endswith('.html')])
print(f"Total templates on disk: {len(template_files)}")

# Find all occurrences of template responses in routes
pattern1 = re.compile(r'TemplateResponse\s*\(\s*request\s*=\s*request\s*,\s*name\s*=\s*["\']([^"\']+)["\']')
pattern2 = re.compile(r'TemplateResponse\s*\(\s*["\']([^"\']+)["\']')
pattern3 = re.compile(r'name\s*=\s*["\']([^"\']+\.html)["\']')

used_templates = set()
route_map = {}

for root, _, files in os.walk('.'):
    if any(x in root for x in ['.git', 'venv', '__pycache__', 'tests', 'node_modules']):
        continue
    for f in files:
        if f.endswith('.py'):
            filepath = os.path.join(root, f)
            with open(filepath, encoding='utf-8', errors='ignore') as fp:
                for idx, line in enumerate(fp):
                    for pat in [pattern1, pattern2, pattern3]:
                        m = pat.search(line)
                        if m:
                            tpl = m.group(1)
                            used_templates.add(tpl)
                            if tpl not in route_map:
                                route_map[tpl] = []
                            route_map[tpl].append(f"{filepath}:{idx+1}")

print(f"\nTemplates used in python code: {len(used_templates)}")
for t in template_files:
    routes = route_map.get(t, [])
    status = f"USED ({len(routes)} places)" if routes else "NOT FOUND DIRECTLY"
    print(f"  {t:25} -> {status}")
