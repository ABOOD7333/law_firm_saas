# -*- coding: utf-8 -*-
"""
LawSaaS Project Deployment & Git Mastery Guide Generator
Compiles 6 comprehensive, production-grade PDF guides inside PROJECT_DEPLOYMENT_GUIDE.
"""

import os
import sys
import subprocess
import shutil

ROOT = os.getcwd()
OUT_DIR = os.path.join(ROOT, "PROJECT_DEPLOYMENT_GUIDE")
os.makedirs(OUT_DIR, exist_ok=True)

EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

# Stylesheet for high quality print
BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&family=Tajawal:wght@400;500;700;800&family=Fira+Code:wght@400;500;600&display=swap');

@page {
    size: A4 portrait;
    margin: 16mm 14mm 18mm 14mm;
    @bottom-center {
        content: counter(page);
        font-family: 'Cairo', sans-serif;
        font-size: 9pt;
        color: #64748b;
    }
    @bottom-left {
        content: "دليل نشر وإدارة LawSaaS";
        font-family: 'Cairo', sans-serif;
        font-size: 8pt;
        color: #94a3b8;
    }
    @bottom-right {
        content: "منصة وزيرك (Waziruk)";
        font-family: 'Cairo', sans-serif;
        font-size: 8pt;
        color: #94a3b8;
    }
}

*, *:before, *:after { box-sizing: border-box; }

body {
    font-family: 'Cairo', 'Tajawal', Tahoma, sans-serif;
    direction: rtl;
    text-align: right;
    background-color: #ffffff;
    color: #0f172a;
    font-size: 10pt;
    line-height: 1.65;
    margin: 0;
    padding: 0;
}

.doc-header {
    background: linear-gradient(135deg, #0b132b 0%, #1c2541 100%);
    color: #ffffff;
    padding: 22px 20px;
    border-radius: 8px;
    margin-bottom: 20px;
    border-right: 6px solid #d4af37;
    box-shadow: 0 4px 10px rgba(0,0,0,0.08);
}

.doc-badge {
    display: inline-block;
    background: rgba(212, 175, 55, 0.2);
    color: #d4af37;
    border: 1px solid #d4af37;
    padding: 3px 12px;
    border-radius: 20px;
    font-size: 9pt;
    font-weight: 700;
    margin-bottom: 6px;
}

.doc-title {
    font-size: 18pt;
    font-weight: 900;
    margin: 0 0 4px 0;
    color: #ffffff;
}

.doc-subtitle {
    font-size: 10.5pt;
    color: #cbd5e1;
    margin: 0;
}

h1, h2, h3 {
    font-family: 'Cairo', sans-serif;
    color: #0f172a;
    font-weight: 800;
}

h1 {
    font-size: 14pt;
    border-right: 5px solid #1e3a8a;
    padding-right: 10px;
    background: #f8fafc;
    padding-top: 5px;
    padding-bottom: 5px;
    margin-top: 22px;
    border-radius: 0 4px 4px 0;
}

h2 {
    font-size: 12pt;
    color: #1e3a8a;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 4px;
    margin-top: 18px;
}

h3 {
    font-size: 10.5pt;
    color: #334155;
    margin-top: 12px;
}

p { margin: 5px 0 8px 0; text-align: justify; }

.callout {
    padding: 10px 14px;
    border-radius: 6px;
    margin: 10px 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
}

.callout-info { background: #eff6ff; border-right: 4px solid #3b82f6; color: #1e40af; }
.callout-warn { background: #fffbeb; border-right: 4px solid #f59e0b; color: #92400e; }
.callout-danger { background: #fef2f2; border-right: 4px solid #ef4444; color: #991b1b; }
.callout-success { background: #f0fdf4; border-right: 4px solid #10b981; color: #065f46; }

.callout-title {
    font-weight: 800;
    margin-bottom: 3px;
    font-size: 10pt;
}

.term-box {
    background: #0f172a;
    border-radius: 6px;
    margin: 12px 0;
    overflow: hidden;
    border: 1px solid #334155;
    page-break-inside: avoid;
}

.term-header {
    background: #1e293b;
    padding: 5px 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #334155;
}

.term-dots { display: flex; gap: 5px; }
.term-dot { width: 9px; height: 9px; border-radius: 50%; }
.dot-red { background: #ef4444; }
.dot-yellow { background: #f59e0b; }
.dot-green { background: #10b981; }

.term-title {
    color: #94a3b8;
    font-size: 8pt;
    font-family: 'Fira Code', monospace;
    direction: ltr;
}

.term-body {
    padding: 10px 14px;
    font-family: 'Fira Code', monospace;
    font-size: 8.5pt;
    line-height: 1.5;
    color: #38bdf8;
    direction: ltr;
    text-align: left;
    white-space: pre-wrap;
    word-break: break-all;
}

.cmd-comment { color: #64748b; }
.cmd-prompt { color: #10b981; font-weight: bold; }
.cmd-text { color: #f8fafc; font-weight: bold; }
.cmd-arg { color: #fbbf24; }

table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0 14px 0;
    font-size: 9pt;
    page-break-inside: avoid;
}

th {
    background: #1e293b;
    color: #ffffff;
    font-weight: 700;
    padding: 6px 8px;
    border: 1px solid #334155;
    text-align: right;
}

td {
    padding: 6px 8px;
    border: 1px solid #e2e8f0;
    vertical-align: top;
    line-height: 1.45;
}

tbody tr:nth-child(even) { background-color: #f8fafc; }

.step-card {
    display: flex;
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    margin: 8px 0;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    page-break-inside: avoid;
}

.step-num-badge {
    background: #1e3a8a;
    color: #ffffff;
    font-weight: 800;
    font-size: 11pt;
    width: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.step-details {
    padding: 8px 12px;
    flex-grow: 1;
}

.step-name {
    font-weight: 700;
    font-size: 10pt;
    color: #0f172a;
    margin-bottom: 2px;
}

.step-text {
    font-size: 9pt;
    color: #475569;
}

.page-break { page-break-before: always; }
"""

def wrap_html(title, subtitle, badge_text, body_html):
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>{BASE_CSS}</style>
</head>
<body>
    <div class="doc-header">
        <div class="doc-badge">{badge_text}</div>
        <div class="doc-title">{title}</div>
        <div class="doc-subtitle">{subtitle}</div>
    </div>
    {body_html}
</body>
</html>"""

def compile_pdf(html_path, pdf_path):
    cmd = [
        EDGE_EXE,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        html_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if not (os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1000):
        cmd[1] = "--headless"
        subprocess.run(cmd, capture_output=True, text=True)
    size = os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0
    print(f"Generated: {os.path.basename(pdf_path)} ({size:,} bytes)")
    return os.path.exists(pdf_path) and size > 1000

# =========================================================================
# GUIDE 1: Git and GitHub Guide
# =========================================================================
g1_html = wrap_html(
    title="الدليل الشامل لـ Git و GitHub للمبتدئين",
    subtitle="دليل تأسيسي عملي: من فهم المفاهيم الأساسية وحتى إدارة الفروع والتعامل مع الأخطاء",
    badge_text="الدليل 01 • الأساسيات والنظرية",
    body_html="""
<h1>1. ما هو Git وما هو GitHub؟ وما الفرق الجوهري بينهما؟</h1>
<p>
كثير من المبتدئين يخلطون بين Git و GitHub ويعتقدون أنهما شيء واحد. الحقيقة أنهما أداتان مختلفتان تعملان معاً:
</p>

<table>
    <thead>
        <tr>
            <th style="width: 20%;">المعيار</th>
            <th style="width: 40%;">Git (الأداة المحلية)</th>
            <th style="width: 40%;">GitHub (المنصة السحابية)</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>ما هو؟</strong></td>
            <td>برنامج مثبت على جهاز الكمبيوتر الخاص بك، وظيفته تسجيل تاريخ تعديلات الملفات مثل (آلة الزمن).</td>
            <td>موقع ويب وخدمة سحابية على الإنترنت تستضيف المستودعات التي تدار بواسطة Git لمشاركتها وحفظها.</td>
        </tr>
        <tr>
            <td><strong>أين يعمل؟</strong></td>
            <td>محلياً على جهازك (Offline) دون الحاجة لاتصال بالإنترنت.</td>
            <td>على خوادم شركة مايكروسوفت/GitHub وتتطلب اتصالاً بالإنترنت للوصول إليها.</td>
        </tr>
        <tr>
            <td><strong>المسؤولية</strong></td>
            <td>تتبع التغييرات، إنشاء الفروع، دمج الأكواد، وتسجيل الالتزامات (Commits).</td>
            <td>النسخ الاحتياطي السحابي، إدارة الفرق، مراجعة الأكواد (Pull Requests)، والأتمتة (Actions).</td>
        </tr>
        <tr>
            <td><strong>المكافئ الواقعي</strong></td>
            <td>دفتر يومياتك الشخصي الذي تدون فيه كل خطوة بيدك.</td>
            <td>المكتبة العامة أو الخزينة السحابية التي تضع فيها نسخة من دفترك ليعود إليها الجميع.</td>
        </tr>
    </tbody>
</table>

<h1>2. كيف تعرف المستودع المرتبط بمشروعك؟</h1>
<p>
لمعرفة رابط المستودع السحابي على GitHub المرتبط بمجلد مشروعك الحالي، افتح نافذة الأوامر (Terminal) في مجلد المشروع واكتب:
</p>

<div class="term-box">
    <div class="term-header">
        <div class="term-dots"><span class="term-dot dot-red"></span><span class="term-dot dot-yellow"></span><span class="term-dot dot-green"></span></div>
        <div class="term-title">PowerShell / Bash</div>
    </div>
    <div class="term-body"><span class="cmd-prompt">PS ></span> <span class="cmd-text">git remote -v</span>
<span class="cmd-comment"># النتيجة في مشروع LawSaaS الفعلي:</span>
origin  https://ABOOD7333@github.com/ABOOD7333/law_firm_saas.git (fetch)
origin  https://ABOOD7333@github.com/ABOOD7333/law_firm_saas.git (push)</div>
</div>

<p>
<strong>شرح النتيجة:</strong> كلمة <code>origin</code> هي الاسم المستعار الافتراضي للمستودع السحابي، والرابط يوضح أن مشروعك مرتبط بحساب <code>ABOOD7333</code> في المستودع <code>law_firm_saas</code>.
</p>

<h1>3. دورة حياة الملفات في Git (المراحل الثلاث)</h1>
<p>
عندما تعدل أي ملف في مشروعك، يمر الملف بثلاث مناطق رئيسية قبل أن يصل إلى GitHub:
</p>

<div class="step-card">
    <div class="step-num-badge">1</div>
    <div class="step-details">
        <div class="step-name">منطقة العمل المحلية (Working Directory)</div>
        <div class="step-text">الملفات التي فتحتها في المحرر وقمت بتعديلها أو إضافتها. تظهر باللون الأحمر عند فحص الحالة لأن Git رصد التغيير لكنه لم يجهزه للحفظ بعد.</div>
    </div>
</div>

<div class="step-card">
    <div class="step-num-badge">2</div>
    <div class="step-details">
        <div class="step-name">منطقة التجهيز (Staging Area)</div>
        <div class="step-text">تصل إليها بعد تنفيذ أمر <code>git add</code>. تعني أنك اخترت هذه التعديلات بالتحديد لتكون جزءاً من الحزمة القادمة. تظهر باللون الأخضر.</div>
    </div>
</div>

<div class="step-card">
    <div class="step-num-badge">3</div>
    <div class="step-details">
        <div class="step-name">المستودع المحلي المحفوظ (Local Repository)</div>
        <div class="step-text">تصل إليها بعد تنفيذ أمر <code>git commit</code>. هنا يُسجل التعديل نهائياً في سجل تاريخ المشروع المحلي برمز تجزئة فريد (Commit Hash) ورسالة وصفية.</div>
    </div>
</div>

<div class="step-card">
    <div class="step-num-badge">4</div>
    <div class="step-details">
        <div class="step-name">المستودع السحابي (Remote GitHub)</div>
        <div class="step-text">تصل إليها بعد تنفيذ أمر <code>git push</code>. تُرسل الحزم المحفوظة من جهازك عبر الإنترنت لتستقر في خوادم GitHub.</div>
    </div>
</div>

<h1>4. الأوامر الأساسية اليومية بالتفصيل</h1>

<h2>أ) فحص التغييرات: git status و git diff</h2>
<div class="term-box">
    <div class="term-body"><span class="cmd-prompt">PS ></span> <span class="cmd-text">git status</span>
<span class="cmd-comment"># يخبرك: ما هو الفرع الحالي؟ ما هي الملفات التي عدلتها؟ وما هي الملفات الجديدة؟</span>

<span class="cmd-prompt">PS ></span> <span class="cmd-text">git diff</span>
<span class="cmd-comment"># يوضح لك بالتفصيل الأسطر التي حذفتها (-) والأسطر التي أضفتها (+) داخل الأكواد</span></div>
</div>

<h2>ب) تجهيز الملفات: git add</h2>
<div class="term-box">
    <div class="term-body"><span class="cmd-comment"># لتجهيز ملف واحد محدد:</span>
<span class="cmd-prompt">PS ></span> <span class="cmd-text">git add</span> <span class="cmd-arg">routers/incoming_cases.py</span>

<span class="cmd-comment"># لتجهيز كافة الملفات المعدلة والجديدة دفعة واحدة:</span>
<span class="cmd-prompt">PS ></span> <span class="cmd-text">git add .</span></div>
</div>

<h2>ج) حفظ الالتزام: git commit</h2>
<div class="term-box">
    <div class="term-body"><span class="cmd-prompt">PS ></span> <span class="cmd-text">git commit -m</span> <span class="cmd-arg">"إضافة حقول الدعاوى الجديدة وتحديث التوجيه"</span>
<span class="cmd-comment"># الرمز -m اختصار لـ Message. اكتب دائماً رسالة واضحة تلخص ما قمت بعمله.</span></div>
</div>

<h2>د) رفع التعديلات وسحبها: git push و git pull</h2>
<div class="term-box">
    <div class="term-body"><span class="cmd-comment"># رفع تعديلاتك من جهازك إلى فرع main على GitHub:</span>
<span class="cmd-prompt">PS ></span> <span class="cmd-text">git push origin main</span>

<span class="cmd-comment"># سحب آخر التعديلات الموجودة على GitHub وتحديث جهازك بها:</span>
<span class="cmd-prompt">PS ></span> <span class="cmd-text">git pull origin main</span></div>
</div>

<div class="page-break"></div>
<h1>5. الفروع (Branches) وإدارتها باحتراف</h1>
<p>
<strong>ما هو الفرع؟</strong> الفرع هو مسار عمل مستقل ومنعزل تماماً عن الكود الأصلي. تخيل أنك تبني ميزة تجريبية جديدة، بدلاً من تعديل كود <code>main</code> المستقر، تفتح فرعاً مستقلاً وتجرب فيه بحرية؛ إن نجحت دمجته، وإن فشلت حذفته دون أن يتأثر موقعك الحي!
</p>

<table>
    <thead>
        <tr>
            <th style="width: 35%;">الأمر</th>
            <th style="width: 65%;">الوظيفة العملية</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><code>git branch</code></td>
            <td>عرض قائمة بكافة الفروع المحلية مع وضع علامة (*) بجانب الفرع الفعال حالياً.</td>
        </tr>
        <tr>
            <td><code>git checkout -b feature-name</code></td>
            <td>إنشاء فرع جديد باسم <code>feature-name</code> والانتقال إليه فوراً.</td>
        </tr>
        <tr>
            <td><code>git switch main</code></td>
            <td>التبديل والرجوع إلى الفرع الرئيسي <code>main</code>.</td>
        </tr>
        <tr>
            <td><code>git merge feature-name</code></td>
            <td>دمج تعديلات الفرع <code>feature-name</code> داخل الفرع الذي تقف عليه حالياً.</td>
        </tr>
        <tr>
            <td><code>git branch -d feature-name</code></td>
            <td>حذف الفرع محلياً بعد الانتهاء من دمجه بنجاح.</td>
        </tr>
    </tbody>
</table>

<h1>6. أشهر أخطاء Git وحلولها السريعة للمبتدئين</h1>

<div class="callout callout-danger">
    <div class="callout-title">⚠️ الخطأ الأول: Updates were rejected because the remote contains work (التعارض عند الرفع)</div>
    <p>
        <strong>السبب:</strong> يوجد تعديل جديد على GitHub لم تسحبه إلى جهازك أولاً (قام به زميل أو تم تعديله على السيرفر).
        <br><strong>الحل السحري:</strong> قم بسحب التعديلات أولاً ثم أعد الرفع:
        <br><code>git pull --rebase origin main</code> ثم <code>git push origin main</code>
    </p>
</div>

<div class="callout callout-warn">
    <div class="callout-title">⚠️ الخطأ الثاني: تراجعت عن تعديلات ملف معين قبل عمل Commit</div>
    <p>
        إذا عدلت ملفاً بالخطأ وأردت إلغاء كل تعديلاتك وإرجاعه تماماً كما كان في آخر Commit:
        <br><code>git restore path/to/file.py</code>
    </p>
</div>

<div class="callout callout-info">
    <div class="callout-title">💡 الخطأ الثالث: كتبت رسالة Commit خاطئة وتريد تعديلها</div>
    <p>
        طالما أنك لم ترفع التعديل بعد بـ Push، يمكنك تعديل آخر رسالة عبر:
        <br><code>git commit --amend -m "الرسالة الصحيحة الجديدة"</code>
    </p>
</div>
"""
)

# =========================================================================
# GUIDE 2: Upload Project to GitHub
# =========================================================================
g2_html = wrap_html(
    title="الدليل التطبيقي لرفع وتحديث LawSaaS على GitHub",
    subtitle="خطوات عملية حقيقية خطوة بخطوة للعمل على مستودع ABOOD7333/law_firm_saas",
    badge_text="الدليل 02 • التطبيق العملي للرفع",
    body_html="""
<h1>1. تجهيز بيئة العمل المحلية على جهازك</h1>
<p>
في مشروع LawSaaS الفعلي، يوجد مسار عملك المحلي في المسار:
<br><code>C:\\Users\\Roots\\.gemini\\antigravity\\worktrees\\law_firm1\\analyze_missing_features</code>
</p>

<p>
قبل أن تفكر في كتابة أي أمر رفع، هناك قاعدة أمنية ذهبية في هندسة البرمجيات:
<strong>إياك أن ترفع ملفات الأسرار (.env) أو قواعد البيانات المحلية (.db) إلى GitHub!</strong>
</p>

<h2>التحقق من ملف .gitignore</h2>
<p>
ملف <code>.gitignore</code> هو الحارس الأمين؛ يخبر Git بالملفات والمجلدات التي يجب تجاهلها تماماً وعدم رؤيتها أو رفعها أبداً. تأكد دائماً أن الأسطر التالية موجودة داخله:
</p>

<div class="term-box">
    <div class="term-header">
        <div class="term-title">.gitignore</div>
    </div>
    <div class="term-body">.env
.env.local
*.db
*.sqlite3
__pycache__/
*.pyc
uploads/
poppler/
.pytest_cache/</div>
</div>

<h1>2. خطوات رفع التعديلات خطوة بخطوة (سيناريو حقيقي)</h1>

<div class="step-card">
    <div class="step-num-badge">1</div>
    <div class="step-details">
        <div class="step-name">الخطوة الأولى: فتح نافذة الأوامر والتحقق من الحالة</div>
        <div class="step-text">افتح PowerShell في مسار المشروع واكتب <code>git status</code> لمعرفة الملفات التي قمت بتعديلها والتأكد من عدم وجود ملفات حساسة غير مرغوبة.</div>
    </div>
</div>

<div class="term-box">
    <div class="term-body"><span class="cmd-prompt">PS C:\\...\\law_firm1></span> <span class="cmd-text">git status</span></div>
</div>

<div class="step-card">
    <div class="step-num-badge">2</div>
    <div class="step-details">
        <div class="step-name">الخطوة الثانية: تجهيز الملفات (Staging)</div>
        <div class="step-text">أضف الملفات التي تريد رفعها. يفضل تحديد الملفات بالاسم لضمان الدقة، أو استخدام <code>git add .</code> إذا كنت واثقاً من نظافة كافة الملفات المعدلة.</div>
    </div>
</div>

<div class="term-box">
    <div class="term-body"><span class="cmd-prompt">PS C:\\...\\law_firm1></span> <span class="cmd-text">git add routers/incoming_cases.py database/models.py templates/incoming_cases/</span></div>
</div>

<div class="step-card">
    <div class="step-num-badge">3</div>
    <div class="step-details">
        <div class="step-name">الخطوة الثالثة: توثيق التعديل وحفظه محلياً (Commit)</div>
        <div class="step-text">احفظ التعديل برسالة معبرة وواضحة تشرح التحديث باللغة العربية أو الإنجليزية.</div>
    </div>
</div>

<div class="term-box">
    <div class="term-body"><span class="cmd-prompt">PS C:\\...\\law_firm1></span> <span class="cmd-text">git commit -m</span> <span class="cmd-arg">"تحديث واجهة القضايا الواردة وإضافة نموذج قيد الدعوى الجديد"</span></div>
</div>

<div class="step-card">
    <div class="step-num-badge">4</div>
    <div class="step-details">
        <div class="step-name">الخطوة الرابعة: سحب أي تحديثات جديدة لمنع التعارض (Pull)</div>
        <div class="step-text">قبل الرفع، تأكد أنك تملك أحدث نسخة عبر سحب أي تعديلات تم دمجها على السحابة.</div>
    </div>
</div>

<div class="term-box">
    <div class="term-body"><span class="cmd-prompt">PS C:\\...\\law_firm1></span> <span class="cmd-text">git pull origin main</span></div>
</div>

<div class="step-card">
    <div class="step-num-badge">5</div>
    <div class="step-details">
        <div class="step-name">الخطوة الخامسة: رفع التعديلات نهائياً إلى GitHub (Push)</div>
        <div class="step-text">أرسل التعديلات إلى مستودعك الرسمي على GitHub.</div>
    </div>
</div>

<div class="term-box">
    <div class="term-body"><span class="cmd-prompt">PS C:\\...\\law_firm1></span> <span class="cmd-text">git push origin main</span>
<span class="cmd-comment"># سيظهر ناتج يوضح ضغط الكائنات ورفعها بنجاح:</span>
Enumerating objects: 15, done.
Writing objects: 100% (15/15), 12.45 KiB | 2.49 MiB/s, done.
To https://github.com/ABOOD7333/law_firm_saas.git
   793d3b0..a1b2c3d  main -> main</div>
</div>

<div class="page-break"></div>
<h1>3. العمل الاحترافي عبر الفروع (Feature Branch Workflow)</h1>
<p>
في الشركات الكبرى، لا يرفع المطورون تعديلاتهم مباشرة إلى فرع <code>main</code>، بل ينشئون فرعاً باسم الميزة، يرفعونه إلى GitHub، ثم يفتحون طلب دمج (Pull Request) لمراجعة الكود قبل اعتماده. إليك الطريقة خطوة بخطوة:
</p>

<div class="term-box">
    <div class="term-body"><span class="cmd-comment"># 1. إنشاء فرع جديد والتبديل إليه:</span>
<span class="cmd-prompt">PS ></span> <span class="cmd-text">git checkout -b</span> <span class="cmd-arg">add-zatca-invoice-feature</span>

<span class="cmd-comment"># 2. قم بتعديل أكوادك واختبرها محلياً...</span>

<span class="cmd-comment"># 3. حفظ التعديل على الفرع الجديد:</span>
<span class="cmd-prompt">PS ></span> <span class="cmd-text">git add .</span>
<span class="cmd-prompt">PS ></span> <span class="cmd-text">git commit -m</span> <span class="cmd-arg">"إضافة باركود زاتكا في راوتر المحاسبة"</span>

<span class="cmd-comment"># 4. رفع الفرع الجديد إلى GitHub:</span>
<span class="cmd-prompt">PS ></span> <span class="cmd-text">git push -u origin</span> <span class="cmd-arg">add-zatca-invoice-feature</span></div>
</div>

<h2>كيف تدمج التعديل عبر واجهة موقع GitHub؟</h2>
<ol>
    <li>ادخل إلى صفحة مستودعك: <code>https://github.com/ABOOD7333/law_firm_saas</code></li>
    <li>ستجد شريطاً أصفر ينبهك بوجود فرع جديد مع زر أخضر يسمى <strong>Compare & pull request</strong>. اضغط عليه.</li>
    <li>اكتب وصفاً للتعديلات واضغط على <strong>Create pull request</strong>.</li>
    <li>بعد التأكد من سلامة الفحص التلقائي (CI)، اضغط على <strong>Merge pull request</strong> ثم <strong>Confirm merge</strong>.</li>
    <li>مبروك! أصبحت تعديلاتك مدمجة الآن في الفرع الرئيسي <code>main</code> وجاهزة للنشر على السيرفر!</li>
</ol>
"""
)

# =========================================================================
# GUIDE 3: Deploy Project to Hosting
# =========================================================================
g3_html = wrap_html(
    title="دليل النشر والاستضافة السحابية لـ LawSaaS",
    subtitle="تشغيل وإدارة المنصة على السيرفر الفعلي، ربط الدومين، وحاويات Docker",
    badge_text="الدليل 03 • الاستضافة السحابية و VPS",
    body_html="""
<h1>1. كيف يعمل مشروع LawSaaS على السيرفر الفعلي؟</h1>
<p>
تم نشر واستضافة منصة <strong>LawSaaS (وزيرك)</strong> على سيرفر سحابي خاص (VPS) بإعدادات إنتاج متطورة تضمن الاستقرار والأداء العالي:
</p>

<table>
    <thead>
        <tr>
            <th style="width: 25%;">المكون</th>
            <th style="width: 35%;">الإعداد الفعلي للمشروع</th>
            <th style="width: 40%;">الدور والمسؤولية</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>عنوان السيرفر (IP)</strong></td>
            <td><code>179.198.198.38</code></td>
            <td>الخادم السحابي المستضيف لنظام Linux Ubuntu.</td>
        </tr>
        <tr>
            <td><strong>اسم النطاق (Domain)</strong></td>
            <td><code>https://waziruk.tech</code></td>
            <td>الدومين الرسمي الموجه للسيرفر والمحمي بشهادة أمان SSL (Let's Encrypt).</td>
        </tr>
        <tr>
            <td><strong>مسار المشروع</strong></td>
            <td><code>/opt/lawsaas/</code></td>
            <td>المجلد الفعلي الذي يحتوي على أكواد وملفات المشروع على السيرفر.</td>
        </tr>
        <tr>
            <td><strong>حاوية التطبيق</strong></td>
            <td><code>lawsaas_app</code> (Docker)</td>
            <td>الحاوية التي تشغل خادم FastAPI بواسطة Uvicorn على المنفذ الداخلي <code>8000</code>.</td>
        </tr>
        <tr>
            <td><strong>الخادم الوكيل (Proxy)</strong></td>
            <td><code>Nginx</code></td>
            <td>يستقبل الزوار على المنفذ 443 و 80 ويمرر الطلبات بأمان إلى الحاوية.</td>
        </tr>
    </tbody>
</table>

<h1>2. الدخول إلى السيرفر عبر SSH</h1>
<p>
للتحكم في السيرفر وإدارته من جهازك، افتح نافذة PowerShell واكتب أمر الاتصال الآمن (SSH):
</p>

<div class="term-box">
    <div class="term-header">
        <div class="term-title">الاتصال بالسيرفر</div>
    </div>
    <div class="term-body"><span class="cmd-prompt">PS ></span> <span class="cmd-text">ssh root@179.198.198.38</span>
<span class="cmd-comment"># أدخل كلمة المرور الخاصة بالسيرفر عند طلبها</span>
<span class="cmd-prompt">root@lawsaas-vps:~#</span> <span class="cmd-comment"># أنت الآن داخل السيرفر بنجاح!</span></div>
</div>

<h1>3. خطوات نشر تحديث جديد على السيرفر (Production Deployment)</h1>
<p>
عندما ترفع كوداً جديداً إلى GitHub وتريد تحديث الموقع الحي على السيرفر، اتبع الخطوات الأربع التالية:
</p>

<div class="step-card">
    <div class="step-num-badge">1</div>
    <div class="step-details">
        <div class="step-name">الدخول إلى مجلد المشروع على السيرفر</div>
        <div class="step-text">انتقل للمجلد الرسمي للتطبيق: <code>cd /opt/lawsaas</code></div>
    </div>
</div>

<div class="step-card">
    <div class="step-num-badge">2</div>
    <div class="step-details">
        <div class="step-name">سحب آخر التعديلات من GitHub</div>
        <div class="step-text">اكتب <code>git pull origin main</code> لجلب التعديلات الجديدة التي رفعتها.</div>
    </div>
</div>

<div class="step-card">
    <div class="step-num-badge">3</div>
    <div class="step-details">
        <div class="step-name">إعادة بناء وتشغيل الحاوية السحابية</div>
        <div class="step-text">اكتب <code>docker compose -f docker-compose.yml up -d --build app</code> لتطبيق التحديث وتحديث الحاوية في الخلفية.</div>
    </div>
</div>

<div class="step-card">
    <div class="step-num-badge">4</div>
    <div class="step-details">
        <div class="step-name">مراقبة السجلات والتأكد من انطلاق الخادم</div>
        <div class="step-text">اكتب <code>docker logs -f --tail 50 lawsaas_app</code> للتأكد من رسالة <code>Application startup complete</code>.</div>
    </div>
</div>

<div class="term-box">
    <div class="term-header">
        <div class="term-title">الأوامر مجمعة للنشر السريع</div>
    </div>
    <div class="term-body"><span class="cmd-prompt">root@lawsaas-vps:~#</span> <span class="cmd-text">cd /opt/lawsaas</span>
<span class="cmd-prompt">root@lawsaas-vps:/opt/lawsaas#</span> <span class="cmd-text">git pull origin main</span>
<span class="cmd-prompt">root@lawsaas-vps:/opt/lawsaas#</span> <span class="cmd-text">docker compose up -d --build app</span>
<span class="cmd-prompt">root@lawsaas-vps:/opt/lawsaas#</span> <span class="cmd-text">docker logs --tail 30 lawsaas_app</span></div>
</div>

<div class="page-break"></div>
<h1>4. إدارة متغيرات البيئة (.env) على السيرفر</h1>
<p>
ملف <code>.env</code> على السيرفر يحتوي على البيانات الحقيقية السرية لقاعدة البيانات ومفاتيح الـ API. لتعديل أي إعداد (مثل إضافة مفتاح جديد لـ Gemini أو إعدادات بريد SMTP):
</p>

<div class="term-box">
    <div class="term-body"><span class="cmd-prompt">root@lawsaas-vps:/opt/lawsaas#</span> <span class="cmd-text">nano .env</span>
<span class="cmd-comment"># عدل القيمة المطلوبة في المحرر، ثم اضغط Ctrl + O للحفظ، ثم Enter، ثم Ctrl + X للخروج.</span>

<span class="cmd-comment"># بعد تعديل .env، يجب دائماً إعادة تشغيل الحاوية لتقرأ القيم الجديدة:</span>
<span class="cmd-prompt">root@lawsaas-vps:/opt/lawsaas#</span> <span class="cmd-text">docker restart lawsaas_app</span></div>
</div>

<h1>5. كيف تتأكد أن الموقع يعمل بنجاح بعد التحديث؟</h1>
<ol>
    <li><strong>الفحص السريع من الطرفية (Terminal):</strong>
        <br>اكتب <code>curl -I https://waziruk.tech</code> وتأكد من استلام كود الحالة <code>HTTP/2 200</code> أو <code>HTTP/2 303</code>.
    </li>
    <li><strong>الفحص البصري من المتصفح:</strong>
        <br>افتح المتصفح في وضع التصفح الخفي (Incognito) وادخل إلى <code>https://waziruk.tech</code>، وتأكد من تسجيل الدخول وتجربة الميزة الجديدة التي قمت بنشرها.
    </li>
    <li><strong>فحص سجلات الأخطاء في Nginx:</strong>
        <br>اكتب <code>tail -f /var/log/nginx/error.log</code> للتأكد من عدم وجود أخطاء في تمرير الاتصال.
    </li>
</ol>
"""
)

# =========================================================================
# GUIDE 4: Database and Backups
# =========================================================================
g4_html = wrap_html(
    title="إدارة قواعد البيانات والنسخ الاحتياطي لـ LawSaaS",
    subtitle="حماية بيانات المكاتب، تشغيل الترقية التلقائية، وعمليات النسخ والاسترجاع",
    badge_text="الدليل 04 • قواعد البيانات والأمان",
    body_html="""
<h1>1. بيئتا قاعدة البيانات في مشروع LawSaaS</h1>
<p>
يستخدم نظام LawSaaS تقنية <strong>SQLAlchemy ORM</strong> المرنة، والتي تتيح للمشروع العمل مع بيئتين مختلفتين دون تغيير كود الاستعلامات:
</p>

<table>
    <thead>
        <tr>
            <th style="width: 25%;">المعيار</th>
            <th style="width: 35%;">البيئة المحلية (Development)</th>
            <th style="width: 40%;">بيئة الإنتاج السحابية (Production)</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>نوع المحرك</strong></td>
            <td>SQLite (ملف محلي <code>law_firm.db</code>)</td>
            <td>PostgreSQL السحابي القوي (<code>lawsaas_db</code>)</td>
        </tr>
        <tr>
            <td><strong>السرعة والتنصيب</strong></td>
            <td>فوري وسريع ولا يحتاج سيرفر مستقل.</td>
            <td>مخصص لتحمل ملايين السجلات والاتصالات المتزامنة.</td>
        </tr>
        <tr>
            <td><strong>رابط الاتصال (URL)</strong></td>
            <td><code>sqlite:///./law_firm.db</code></td>
            <td><code>postgresql://lawsaas:pass@localhost:5432/lawsaas_db</code></td>
        </tr>
    </tbody>
</table>

<h1>2. كيف تعمل ترقية وتحديث الجداول تلقائياً (Auto-Migration)؟</h1>
<p>
يتميز مشروع LawSaaS بوجود <strong>محرك ترقية تلقائي مبتكر داخل <code>database/database.py</code></strong>. عندما تضيف عموداً جديداً في نموذج <code>database/models.py</code> وتنشره على السيرفر، يقوم الكود عند بدء التشغيل بما يلي:
</p>
<ol>
    <li>فحص كافة الجداول في قاعدة بيانات الإنتاج.</li>
    <li>مقارنة الأعمدة الموجودة في قاعدة البيانات بالأعمدة المعرفة في كود بايثون.</li>
    <li>إذا وجد عموداً جديداً (مثل <code>claim_amount</code> أو <code>target_authority</code>)، يُنفذ تلقائياً استعلام:
        <br><code>ALTER TABLE law_incoming_cases ADD COLUMN claim_amount VARCHAR;</code>
    </li>
    <li>تتم هذه العملية بسلاسة تامة <strong>دون حذف أي بيانات سابقة أو التأثير على العملاء الحاليين</strong>!</li>
</ol>

<h1>3. كيفية أخذ نسخة احتياطية حية (Backup) لقاعدة البيانات</h1>
<p>
النسخ الاحتياطي الدوري هو صمام الأمان لأي منصة سحابية. لحفظ بيانات المكاتب والقضايا:
</p>

<h2>أ) على السيرفر الفعلي (PostgreSQL Backup)</h2>
<div class="term-box">
    <div class="term-header">
        <div class="term-title">أخذ نسخة احتياطية على السيرفر</div>
    </div>
    <div class="term-body"><span class="cmd-comment"># أخذ نسخة مدمجة ومضغوطة من قاعدة بيانات PostgreSQL:</span>
<span class="cmd-prompt">root@lawsaas-vps:~#</span> <span class="cmd-text">docker exec -t lawsaas_db pg_dump -U lawsaas lawsaas_db > /opt/backups/lawsaas_backup_$(date +%Y%m%d).sql</span>
<span class="cmd-comment"># يتم حفظ النسخة في مجلد آمن خارج الحاوية</span></div>
</div>

<h2>ب) محلياً على جهازك (تصدير الجداول عبر السكربت)</h2>
<div class="term-box">
    <div class="term-body"><span class="cmd-comment"># تشغيل سكربت التصدير الشامل المضمن في المشروع:</span>
<span class="cmd-prompt">PS ></span> <span class="cmd-text">python export_all_databases.py</span>
<span class="cmd-comment"># يقوم السكربت بحفظ كافة الجداول في ملفات CSV و SQL آمنة</span></div>
</div>

<div class="page-break"></div>
<h1>4. كيفية استعادة النسخة الاحتياطية عند الطوارئ (Restore)</h1>
<p>
إذا حدث خطأ غير متوقع وأردت استعادة قاعدة البيانات تماماً كما كانت في النسخة الاحتياطية:
</p>

<div class="callout callout-danger">
    <div class="callout-title">⚠️ تنبيه حرج قبل الاستعادة</div>
    <p>استعادة النسخة الاحتياطية ستستبدل البيانات الحالية ببيانات النسخة. تأكد دائماً أنك تستعيد النسخة الصحيحة.</p>
</div>

<div class="term-box">
    <div class="term-header">
        <div class="term-title">أمر استعادة قاعدة البيانات على السيرفر</div>
    </div>
    <div class="term-body"><span class="cmd-comment"># استرجاع ملف النسخة الاحتياطية إلى قاعدة بيانات PostgreSQL:</span>
<span class="cmd-prompt">root@lawsaas-vps:~#</span> <span class="cmd-text">cat /opt/backups/lawsaas_backup_20261122.sql | docker exec -i lawsaas_db psql -U lawsaas -d lawsaas_db</span>

<span class="cmd-comment"># بعد الاستعادة، أعد تشغيل التطبيق لتحديث الاتصالات:</span>
<span class="cmd-prompt">root@lawsaas-vps:~#</span> <span class="cmd-text">docker restart lawsaas_app</span></div>
</div>

<h1>5. إرشادات الأمان والحماية لبيانات المكاتب</h1>
<ul>
    <li><strong>منع الحذف الصلب (Soft Delete Enforced):</strong> لا تستخدم أمر <code>DELETE</code> المباشر في قواعد البيانات. اعتمد دائماً على تعيين <code>is_deleted = 1</code> لتبقى كافة المعاملات محفوظة في الأرشيف.</li>
    <li><strong>عزل المكاتب الصارم (Tenant Isolation):</strong> تأكد أن كل استعلام SQL يتضمن دائماً شرط <code>office_id == current_user.office_id</code> لضمان عدم اطلاع أي مكتب محاماة على بيانات مكتب آخر.</li>
    <li><strong>حظر الملفات الاحتياطية من الوصول العام:</strong> إياك أن تحفظ ملفات <code>.sql</code> أو <code>.dump</code> داخل مجلد <code>static/</code> أو <code>templates/</code>، لأن أي شخص قد يحملها من المتصفح! احتفظ بالنسخ في مجلد مستقل ومحمي مثل <code>/opt/backups/</code>.</li>
</ul>
"""
)

# =========================================================================
# GUIDE 5: Troubleshooting and Rollback
# =========================================================================
g5_html = wrap_html(
    title="دليل استكشاف الأعطال والإصلاح والرجوع لإصدار سابق",
    subtitle="حل مشكلات السيرفر، أخطاء 500 و 502، والتعافي السريع من أخطاء النشر",
    badge_text="الدليل 05 • استكشاف الأخطاء و Rollback",
    body_html="""
<h1>1. تشخيص وحل أشهر 5 مشاكل تواجه المطورين عند النشر</h1>

<div class="callout callout-danger">
    <div class="callout-title">🔥 المشكلة 1: خطأ 502 Bad Gateway بعد النشر</div>
    <p>
        <strong>المعنى:</strong> خادم Nginx يعمل بنجاح، لكنه عاجز عن الاتصال بتطبيق FastAPI لأن الحاوية متوقفة أو فشلت في الإقلاع.
        <br><strong>خطوات التشخيص الفوري:</strong>
        <br>1. افحص حالة الحاوية: <code>docker ps -a</code> (ستجد حالتها Exited).
        <br>2. اقرأ سبب الانهيار: <code>docker logs --tail 50 lawsaas_app</code>
        <br><strong>أشهر سبب:</strong> وجود خطأ تركيبي (SyntaxError) أو استيراد مفقود (ImportError) في ملف بايثون. أصلح الخطأ في الكود وأعد بناء الحاوية.
    </p>
</div>

<div class="callout callout-warn">
    <div class="callout-title">⚠️ المشكلة 2: خطأ 500 Internal Server Error في صفحة معينة</div>
    <p>
        <strong>المعنى:</strong> الموقع يعمل، ولكن عند الدخول لصفحة محددة (مثل القضايا الواردة) يظهر خطأ 500.
        <br><strong>السبب:</strong> وجود متغير ناقص في قالب Jinja2، أو استعلام قاعدة بيانات يستعلم عن حقل غير موجود.
        <br><strong>طريقة الحل:</strong> افتح سجلات التطبيق أثناء تحديث الصفحة لمشاهدة الـ Traceback الدقيق:
        <br><code>docker logs -f lawsaas_app</code>
    </p>
</div>

<div class="callout callout-info">
    <div class="callout-title">💡 المشكلة 3: التعديلات لا تظهر في المتصفح بعد النشر</div>
    <p>
        <strong>السبب:</strong> المتصفح يحتفظ بنسخة قديمة مؤقتة من ملفات الـ CSS والـ JavaScript (Browser Cache).
        <br><strong>الحل السريع:</strong> اضغط في المتصفح على <strong>Ctrl + Shift + R</strong> أو <strong>Ctrl + F5</strong> لفرض تحديث كامل بدون كاش، أو افتح نافذة تصفح خفي (Incognito).
    </p>
</div>

<h1>2. السيناريوهات العملية الخمسة لإدارة التحديثات</h1>

<h2>السيناريو 1: عدلت قالباً أو صفحة HTML وأريد نشرها بسرعة</h2>
<ol>
    <li>عدل القالب محلياً واختبره.</li>
    <li>احفظ وادفع التعديل: <code>git add . && git commit -m "تعديل واجهة القضايا" && git push origin main</code></li>
    <li>على السيرفر: <code>cd /opt/lawsaas && git pull origin main</code></li>
    <li>أعد تشغيل التطبيق: <code>docker restart lawsaas_app</code> (لا حاجة لإعادة البناء الكامل لأن القوالب تُحدث فوراً).</li>
</ol>

<h2>السيناريو 2: أضفت ميزة جديدة تتضمن عموداً جديداً في قاعدة البيانات</h2>
<ol>
    <li>أضف العمود في <code>database/models.py</code> ومحرك الترقية التلقائية في <code>database/database.py</code>.</li>
    <li>ارفع التعديل إلى GitHub بـ <code>git push origin main</code>.</li>
    <li>على السيرفر: اسحب التعديلات وأعد بناء الحاوية:
        <br><code>docker compose up -d --build app</code>
    </li>
    <li>يقوم التطبيق عند انطلاقه بفحص الجدول وإضافة العمود تلقائياً.</li>
</ol>

<h2>السيناريو 3: حدث خطأ طارئ بعد النشر وأريد الرجوع فوراً لإصدار سابق (Rollback)</h2>
<p>
إذا نشرت تحديثاً وتسبب في مشكلة وتريد إرجاع الموقع خلال ثوانٍ إلى النسخة السابقة التي كانت تعمل:
</p>

<div class="term-box">
    <div class="term-header">
        <div class="term-title">خطوات الـ Rollback الفوري</div>
    </div>
    <div class="term-body"><span class="cmd-comment"># 1. الدخول لمجلد المشروع على السيرفر:</span>
<span class="cmd-prompt">root@lawsaas-vps:~#</span> <span class="cmd-text">cd /opt/lawsaas</span>

<span class="cmd-comment"># 2. عرض آخر التعديلات لمعرفة رقم الـ Commit السابق:</span>
<span class="cmd-prompt">root@lawsaas-vps:/opt/lawsaas#</span> <span class="cmd-text">git log --oneline -n 5</span>
<span class="cmd-comment"># يظهر مثلاً:</span>
a1b2c3d (HEAD -> main) التحديث الجديد الذي سبب المشكلة
793d3b0 التحديث القديم المستقر

<span class="cmd-comment"># 3. العودة الفورية للإصدار القديم المستقر:</span>
<span class="cmd-prompt">root@lawsaas-vps:/opt/lawsaas#</span> <span class="cmd-text">git checkout 793d3b0</span>

<span class="cmd-comment"># 4. إعادة تشغيل الحاوية فوراً:</span>
<span class="cmd-prompt">root@lawsaas-vps:/opt/lawsaas#</span> <span class="cmd-text">docker compose up -d --build app</span>
<span class="cmd-comment"># عاد موقعك الآن للعمل بسلام في أقل من دقيقة!</span></div>
</div>
"""
)

# =========================================================================
# GUIDE 6: Daily Workflow
# =========================================================================
g6_html = wrap_html(
    title="دليل دورة العمل اليومية للمطور (Daily Workflow)",
    subtitle="بطاقة الإجراءات السريعة (Cheat Sheet) لتطوير واختبار ورفع ونشر التحديثات بأمان",
    badge_text="الدليل 06 • بطاقة العمل اليومية السريعة",
    body_html="""
<h1>دورة العمل اليومية المعتمدة في 8 خطوات مرتبة</h1>
<p class="lead-text">
احتفظ بهذه الخطوات الثمانية كمرجع يومي معتمد في كل مرة تبدأ فيها بالعمل على منصة LawSaaS:
</p>

<div class="step-card">
    <div class="step-num-badge">1</div>
    <div class="step-details">
        <div class="step-name">1. فتح المشروع وسحب آخر التحديثات من السحابة</div>
        <div class="step-text">قبل كتابة أي حرف، تأكد دائماً أن جهازك يملك أحدث كود عبر: <code>git pull origin main</code></div>
    </div>
</div>

<div class="step-card">
    <div class="step-num-badge">2</div>
    <div class="step-details">
        <div class="step-name">2. تنفيذ التعديل المطلوب في الكود</div>
        <div class="step-text">قم بتعديل ملفات الواجهة أو الراوترات أو القواعد وفق المهمة المطلوبة منك.</div>
    </div>
</div>

<div class="step-card">
    <div class="step-num-badge">3</div>
    <div class="step-details">
        <div class="step-name">3. الاختبار المحلي على جهازك</div>
        <div class="step-text">شغل التطبيق محلياً وتأكد من فتح الصفحة في المتصفح وتجربة كافة الوظائف وعدم ظهور أخطاء.</div>
    </div>
</div>

<div class="step-card">
    <div class="step-num-badge">4</div>
    <div class="step-details">
        <div class="step-name">4. فحص الملفات المتغيرة والتأكد من عدم وجود أسرار</div>
        <div class="step-text">اكتب <code>git status</code> للتأكد أنك لا ترفع ملفات <code>.env</code> أو بيانات غير مرغوبة.</div>
    </div>
</div>

<div class="step-card">
    <div class="step-num-badge">5</div>
    <div class="step-details">
        <div class="step-name">5. حفظ التعديل محلياً (Commit)</div>
        <div class="step-text">اكتب <code>git add .</code> ثم <code>git commit -m "رسالة توضح التعديل"</code></div>
    </div>
</div>

<div class="step-card">
    <div class="step-num-badge">6</div>
    <div class="step-details">
        <div class="step-name">6. رفع التعديل إلى مستودع GitHub (Push)</div>
        <div class="step-text">ارفع تعديلاتك بثقة عبر الأمر: <code>git push origin main</code></div>
    </div>
</div>

<div class="step-card">
    <div class="step-num-badge">7</div>
    <div class="step-details">
        <div class="step-name">7. نشر التعديل على السيرفر الفعلي</div>
        <div class="step-text">ادخل للسيرفر عبر SSH، ونفذ: <code>cd /opt/lawsaas && git pull origin main && docker compose up -d --build app</code></div>
    </div>
</div>

<div class="step-card">
    <div class="step-num-badge">8</div>
    <div class="step-details">
        <div class="step-name">8. التحقق من السجلات واختبار الموقع الحي</div>
        <div class="step-text">افحص <code>docker logs --tail 30 lawsaas_app</code> ثم افتح <code>https://waziruk.tech</code> وتأكد من عمل الميزة الجديدة.</div>
    </div>
</div>

<div class="page-break"></div>
<h1>جدول الأوامر السريعة الأكثر استخداماً (Cheat Sheet)</h1>

<table>
    <thead>
        <tr>
            <th style="width: 35%;">الأمر</th>
            <th style="width: 25%;">مكان التنفيذ</th>
            <th style="width: 40%;">ماذا يفعل؟</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><code>git status</code></td>
            <td>جهازك المحلي</td>
            <td>معرفة الملفات المعدلة والتي تنتظر الرفع.</td>
        </tr>
        <tr>
            <td><code>git diff</code></td>
            <td>جهازك المحلي</td>
            <td>عرض الأسطر التي تغيرت داخل الأكواد بدقة.</td>
        </tr>
        <tr>
            <td><code>git add .</code></td>
            <td>جهازك المحلي</td>
            <td>تجهيز كافة الملفات المعدلة للحفظ.</td>
        </tr>
        <tr>
            <td><code>git commit -m "..."</code></td>
            <td>جهازك المحلي</td>
            <td>حفظ التعديلات في سجل تاريخ المشروع.</td>
        </tr>
        <tr>
            <td><code>git push origin main</code></td>
            <td>جهازك المحلي</td>
            <td>إرسال ورفع التعديلات إلى مستودع GitHub.</td>
        </tr>
        <tr>
            <td><code>git pull origin main</code></td>
            <td>جهازك أو السيرفر</td>
            <td>جلب وسحب آخر التعديلات من GitHub.</td>
        </tr>
        <tr>
            <td><code>docker ps</code></td>
            <td>السيرفر الفعلي</td>
            <td>عرض الحاويات الشغالة وحالتها الصحية ومنافذها.</td>
        </tr>
        <tr>
            <td><code>docker restart lawsaas_app</code></td>
            <td>السيرفر الفعلي</td>
            <td>إعادة تشغيل التطبيق في ثانيتين.</td>
        </tr>
        <tr>
            <td><code>docker logs -f lawsaas_app</code></td>
            <td>السيرفر الفعلي</td>
            <td>مراقبة سجلات وأخطاء التطبيق الحية لحظة بلحظة.</td>
        </tr>
        <tr>
            <td><code>docker compose up -d --build app</code></td>
            <td>السيرفر الفعلي</td>
            <td>إعادة بناء وتشغيل التحديثات في الخلفية.</td>
        </tr>
    </tbody>
</table>

<div class="callout callout-success">
    <div class="callout-title">🏆 نصيحة هندسية للتميز</div>
    <p>
        الفرق بين المطور العادي والمطور المحترف ليس حفظ الأوامر عن ظهر قلب، بل فهم دورة حياة البيانات والتأكد دائماً قبل الرفع من أمان الكود ونظافة بيئة العمل. باتباعك هذا الدليل، أصبحت تملك زمام مشروعك بالكامل وقادراً على تطويره ونشره بنفسك بثقة تامة!
    </p>
</div>
"""
)

# Guides inventory
guides = [
    ("01_Git_and_GitHub_Guide", g1_html),
    ("02_Upload_Project_to_GitHub", g2_html),
    ("03_Deploy_Project_to_Hosting", g3_html),
    ("04_Database_and_Backups", g4_html),
    ("05_Troubleshooting_and_Rollback", g5_html),
    ("06_Daily_Workflow", g6_html),
]

print("Writing HTML files and compiling PDFs...")

success_count = 0
for name, html_content in guides:
    html_file = os.path.join(OUT_DIR, f"{name}.html")
    pdf_file = os.path.join(OUT_DIR, f"{name}.pdf")
    
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    ok = compile_pdf(html_file, pdf_file)
    if ok:
        success_count += 1

print(f"Compilation Complete! {success_count} / {len(guides)} PDFs generated in {OUT_DIR}.")
