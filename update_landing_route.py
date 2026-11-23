import subprocess

code = """
with open("/opt/lawsaas/main.py", "r", encoding="utf-8") as f:
    c = f.read()

target = 'return templates.TemplateResponse(request=request, name="login.html")'
replacement = 'return templates.TemplateResponse(request=request, name="landing.html")'

idx = c.find('@app.get("/", response_class=HTMLResponse)')
if idx != -1:
    target_idx = c.find(target, idx)
    if target_idx != -1 and target_idx - idx < 300:
        c = c[:target_idx] + replacement + c[target_idx + len(target):]
        with open("/opt/lawsaas/main.py", "w", encoding="utf-8") as f:
            f.write(c)
        print("REPLACED_SUCCESSFULLY")
    else:
        print("Target not found near root route")
else:
    print("Root route not found")
"""

p = subprocess.Popen(['ssh', 'root@179.198.198.38', 'python3'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
stdout, stderr = p.communicate(input=code)
print("STDOUT:", stdout)
print("STDERR:", stderr)

subprocess.run(['ssh', 'root@179.198.198.38', 'docker restart lawsaas_app'])
