import os
from playwright.sync_api import sync_playwright

output_dir = os.path.join('LawSaaS_Media_Production', '08_Project_Source_Files', 'ui_captures')
os.makedirs(output_dir, exist_ok=True)

def get_page_html(module_type):
    # CSS tokens directly from dashboard.css
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>LawSaaS | وزيرك للحلول القانونية</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {{
            --primary: #4f46e5;
            --primary-dark: #3730a3;
            --secondary: #0f172a;
            --bg-main: #f8fafc;
            --gold: #d4af37;
            --gold-gradient: linear-gradient(135deg, #f59e0b 0%, #d4af37 100%);
            --sidebar-w: 260px;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Cairo', sans-serif; }}
        body {{ background: #0b1120; color: #f8fafc; display: flex; height: 100vh; overflow: hidden; }}
        
        /* Modern Sidebar */
        .sidebar {{
            width: var(--sidebar-w);
            background: rgba(15, 23, 42, 0.95);
            border-left: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            flex-direction: column;
            padding: 24px 16px;
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding-bottom: 24px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            margin-bottom: 24px;
        }}
        .brand-icon {{
            width: 44px; height: 44px;
            border-radius: 12px;
            background: linear-gradient(135deg, #4f46e5, #3730a3);
            display: flex; align-items: center; justify-content: center;
            font-size: 20px; color: #fbbf24;
            box-shadow: 0 4px 14px rgba(79, 70, 229, 0.4);
        }}
        .brand-text h2 {{ font-size: 20px; font-weight: 800; letter-spacing: -0.5px; color: #fff; }}
        .brand-text span {{ font-size: 11px; color: #94a3b8; font-weight: 600; }}
        
        .nav-list {{ list-style: none; display: flex; flex-direction: column; gap: 8px; flex: 1; }}
        .nav-item a {{
            display: flex; align-items: center; gap: 14px;
            padding: 12px 16px; border-radius: 10px;
            color: #94a3b8; text-decoration: none; font-size: 14px; font-weight: 600;
            transition: all 0.2s;
        }}
        .nav-item.active a {{
            background: #4f46e5; color: #fff;
            box-shadow: 0 4px 14px rgba(79, 70, 229, 0.3);
        }}
        .nav-item a i {{ font-size: 18px; width: 22px; text-align: center; }}
        
        /* Main Container */
        .main-content {{
            flex: 1; display: flex; flex-direction: column;
            background: #0f172a; overflow-y: auto;
        }}
        .header {{
            height: 70px; background: rgba(15, 23, 42, 0.8);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            display: flex; align-items: center; justify-content: space-between;
            padding: 0 32px;
        }}
        .header-title h1 {{ font-size: 22px; font-weight: 800; color: #fff; }}
        .header-title p {{ font-size: 12px; color: #94a3b8; }}
        .user-pill {{
            display: flex; align-items: center; gap: 12px;
            padding: 6px 14px; background: rgba(255, 255, 255, 0.05);
            border-radius: 40px; border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .avatar {{
            width: 36px; height: 36px; border-radius: 50%;
            background: #d4af37; color: #0f172a; display: flex;
            align-items: center; justify-content: center; font-weight: 800;
        }}
        
        .content-body {{ padding: 32px; display: flex; flex-direction: column; gap: 24px; }}
        
        /* Glass Cards */
        .glass-card {{
            background: rgba(30, 41, 59, 0.65);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            padding: 24px;
        }}
        
        /* Stats Grid */
        .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }}
        .stat-card {{
            background: rgba(30, 41, 59, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 14px; padding: 20px;
            display: flex; align-items: center; gap: 18px;
        }}
        .stat-icon {{
            width: 52px; height: 52px; border-radius: 12px;
            display: flex; align-items: center; justify-content: center;
            font-size: 22px;
        }}
        .stat-info h3 {{ font-size: 26px; font-weight: 900; color: #fff; margin-bottom: 2px; }}
        .stat-info span {{ font-size: 13px; color: #94a3b8; font-weight: 600; }}
        
        /* Table Styles */
        .table-responsive {{ width: 100%; border-collapse: collapse; margin-top: 14px; }}
        .table-responsive th {{
            text-align: right; padding: 14px; font-size: 13px;
            color: #94a3b8; border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .table-responsive td {{
            padding: 16px 14px; font-size: 14px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            color: #e2e8f0; font-weight: 500;
        }}
        .badge {{
            display: inline-flex; align-items: center; gap: 6px;
            padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 700;
        }}
        .badge-success {{ background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }}
        .badge-warning {{ background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); }}
        .badge-primary {{ background: rgba(79, 70, 229, 0.15); color: #818cf8; border: 1px solid rgba(79, 70, 229, 0.3); }}
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="brand">
            <div class="brand-icon"><i class="fa-solid fa-scale-balanced"></i></div>
            <div class="brand-text">
                <h2>LawSaaS</h2>
                <span>منصة وزيرك السحابية</span>
            </div>
        </div>
        <ul class="nav-list">
            <li class="nav-item {'active' if module_type == 'dashboard' else ''}"><a href="#"><i class="fa-solid fa-chart-pie"></i> لوحة التحكم المركزية</a></li>
            <li class="nav-item {'active' if module_type == 'cases' else ''}"><a href="#"><i class="fa-solid fa-folder-open"></i> إدارة ملفات القضايا</a></li>
            <li class="nav-item {'active' if module_type == 'hearings' else ''}"><a href="#"><i class="fa-solid fa-calendar-check"></i> الجلسات والتقويم القضائي</a></li>
            <li class="nav-item"><a href="#"><i class="fa-solid fa-users"></i> إدارة الموكلين والشركات</a></li>
            <li class="nav-item {'active' if module_type == 'finance' else ''}"><a href="#"><i class="fa-solid fa-vault"></i> أمانات العملاء والمالية</a></li>
            <li class="nav-item"><a href="#"><i class="fa-solid fa-file-shield"></i> الأرشفة والوثائق الرقمية</a></li>
            <li class="nav-item"><a href="#"><i class="fa-solid fa-wand-magic-sparkles"></i> أتمتة الإشعارات والإنذارات</a></li>
        </ul>
    </div>
    
    <div class="main-content">
        <div class="header">
            <div class="header-title">
                <h1>{'لوحة القيادة والمؤشرات الحية' if module_type == 'dashboard' else ('إدارة القضايا والنزاعات القضائية' if module_type == 'cases' else ('التقويم القضائي والجلسات المقبلة' if module_type == 'hearings' else 'حسابات الأمانات والفواتير السحابية'))}</h1>
                <p>مكتب الأمل للمحاماة والاستشارات القانونية الدولية | النظام السحابي المتكامل</p>
            </div>
            <div class="user-pill">
                <div class="avatar">مح</div>
                <div style="text-align: right;">
                    <div style="font-size: 13px; font-weight: 700;">المستشار / أحمد اليماني</div>
                    <div style="font-size: 11px; color: #10b981;">● متصل بنظام الأمان العالي</div>
                </div>
            </div>
        </div>
        
        <div class="content-body">
            {get_module_content(module_type)}
        </div>
    </div>
</body>
</html>"""

def get_module_content(mod):
    if mod == 'dashboard':
        return """
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(79, 70, 229, 0.2); color: #818cf8;"><i class="fa-solid fa-gavel"></i></div>
                <div class="stat-info"><h3>148</h3><span>إجمالي القضايا النشطة</span></div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24;"><i class="fa-solid fa-calendar-day"></i></div>
                <div class="stat-info"><h3>12</h3><span>جلسات الأسبوع الجاري</span></div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(16, 185, 129, 0.2); color: #34d399;"><i class="fa-solid fa-shield-halved"></i></div>
                <div class="stat-info"><h3>94.8%</h3><span>نسبة الأحكام الإيجابية</span></div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(236, 72, 153, 0.2); color: #f472b6;"><i class="fa-solid fa-coins"></i></div>
                <div class="stat-info"><h3>$ 385K</h3><span>حجم أمانات الموكلين</span></div>
            </div>
        </div>
        <div class="glass-card">
            <h2 style="font-size: 18px; font-weight: 800; color: #fff; margin-bottom: 12px;"><i class="fa-solid fa-clock-rotate-left" style="color: #818cf8;"></i> أحدث القضايا المحدثة فورياً</h2>
            <table class="table-responsive">
                <thead>
                    <tr>
                        <th>رقم القضية</th>
                        <th>الموكل</th>
                        <th>الخصم</th>
                        <th>المحكمة والدائرة</th>
                        <th>مرحلة التقاضي</th>
                        <th>تاريخ الجلسة القادمة</th>
                        <th>الحالة</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style="font-weight: 700; color: #818cf8;">ق/2026/1042</td>
                        <td>مجموعة المجد للاستثمار</td>
                        <td>شركة الأفق للإنشاءات</td>
                        <td>المحكمة التجارية الابتدائية (الدائرة الأولى)</td>
                        <td>تقديم المذكرات الختامية</td>
                        <td>16 نوفمبر 2026</td>
                        <td><span class="badge badge-warning">قيد الترافع</span></td>
                    </tr>
                    <tr>
                        <td style="font-weight: 700; color: #818cf8;">ق/2026/0890</td>
                        <td>شركة ريادة للصناعات</td>
                        <td>المصرف العربي للتمويل</td>
                        <td>محكمة الاستئناف الإدارية</td>
                        <td>النطق بالحكم النهائي</td>
                        <td>19 نوفمبر 2026</td>
                        <td><span class="badge badge-primary">حجز للحكم</span></td>
                    </tr>
                    <tr>
                        <td style="font-weight: 700; color: #818cf8;">ق/2026/1125</td>
                        <td>مؤسسة النور للتجارة</td>
                        <td>وكالة الدلتا اللوجستية</td>
                        <td>محكمة الأموال والمنازعات</td>
                        <td>تنفيذ سند أمر</td>
                        <td>24 نوفمبر 2026</td>
                        <td><span class="badge badge-success">تنفيذ جبري</span></td>
                    </tr>
                </tbody>
            </table>
        </div>
        """
    elif mod == 'cases':
        return """
        <div class="glass-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <div>
                    <h2 style="font-size: 18px; font-weight: 800;">سجل القضايا والملفات النشطة</h2>
                    <p style="font-size: 13px; color: #94a3b8;">تصفية وبحث لحظي في جميع درجات التقاضي (ابتدائي، استئناف، عليا)</p>
                </div>
                <button style="background: #4f46e5; color: #fff; border: none; padding: 10px 20px; border-radius: 8px; font-weight: 700; cursor: pointer; display: flex; align-items: center; gap: 8px;">
                    <i class="fa-solid fa-plus"></i> فتح ملف قضية جديدة
                </button>
            </div>
            <table class="table-responsive">
                <thead>
                    <tr>
                        <th>رقم الملف</th>
                        <th>موضوع الدعوى</th>
                        <th>الموكل</th>
                        <th>المحامي المسؤول</th>
                        <th>درجة التقاضي</th>
                        <th>المستندات المرفقة</th>
                        <th>حالة الملف</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style="color: #818cf8; font-weight: 700;">LAW-2026-001</td>
                        <td>دعوى بطلان شرط تحكيمي ومطالبة بتعويض</td>
                        <td>شركة التطوير العقاري</td>
                        <td>أ. سارة الخالد</td>
                        <td>محكمة الاستئناف</td>
                        <td><i class="fa-solid fa-paperclip" style="color: #94a3b8;"></i> 14 وثيقة مشفرة</td>
                        <td><span class="badge badge-primary">جلسة مرافعة</span></td>
                    </tr>
                    <tr>
                        <td style="color: #818cf8; font-weight: 700;">LAW-2026-002</td>
                        <td>نزاع ملكية فكرية وعلامات تجارية</td>
                        <td>مؤسسة الابتكار الرقمي</td>
                        <td>د. خالد المنصوري</td>
                        <td>المحكمة التجارية العليا</td>
                        <td><i class="fa-solid fa-paperclip" style="color: #94a3b8;"></i> 28 وثيقة مشفرة</td>
                        <td><span class="badge badge-success">جاهزة للحكم</span></td>
                    </tr>
                    <tr>
                        <td style="color: #818cf8; font-weight: 700;">LAW-2026-003</td>
                        <td>مطالبة بأتعاب ومستحقات عقد مقاولة</td>
                        <td>شركة الأوتاد للمقاولات</td>
                        <td>أ. عادل فاروق</td>
                        <td>الابتدائية التجارية</td>
                        <td><i class="fa-solid fa-paperclip" style="color: #94a3b8;"></i> 9 وثائق مشفرة</td>
                        <td><span class="badge badge-warning">تبادل مذكرات</span></td>
                    </tr>
                </tbody>
            </table>
        </div>
        """
    elif mod == 'hearings':
        return """
        <div class="glass-card">
            <h2 style="font-size: 18px; font-weight: 800; margin-bottom: 16px;">التقويم القضائي الذكي وتنبيهات الجلسات</h2>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;">
                <div style="background: rgba(255,255,255,0.03); padding: 18px; border-radius: 12px; border-right: 4px solid #f59e0b;">
                    <span style="font-size: 12px; color: #f59e0b; font-weight: 700;">الأحد 16 نوفمبر 2026 - 09:30 ص</span>
                    <h3 style="font-size: 16px; font-weight: 700; margin: 6px 0;">جلسة مرافعة شفوية</h3>
                    <p style="font-size: 13px; color: #94a3b8;">المحكمة التجارية • الدائرة الأولى • القاعة 4</p>
                    <div style="margin-top: 12px; font-size: 12px; color: #cbd5e1;">القضية: ق/2026/1042 (المجد ضد الأفق)</div>
                </div>
                <div style="background: rgba(255,255,255,0.03); padding: 18px; border-radius: 12px; border-right: 4px solid #4f46e5;">
                    <span style="font-size: 12px; color: #818cf8; font-weight: 700;">الثلاثاء 18 نوفمبر 2026 - 11:00 ص</span>
                    <h3 style="font-size: 16px; font-weight: 700; margin: 6px 0;">سماع شهود الإثبات</h3>
                    <p style="font-size: 13px; color: #94a3b8;">محكمة جنوب العاصمة • الدائرة العمالية</p>
                    <div style="margin-top: 12px; font-size: 12px; color: #cbd5e1;">القضية: ق/2026/0451 (النزاع العمالي الجماعي)</div>
                </div>
                <div style="background: rgba(255,255,255,0.03); padding: 18px; border-radius: 12px; border-right: 4px solid #10b981;">
                    <span style="font-size: 12px; color: #10b981; font-weight: 700;">الخميس 20 نوفمبر 2026 - 10:00 ص</span>
                    <h3 style="font-size: 16px; font-weight: 700; margin: 6px 0;">جلسة النطق بالحكم</h3>
                    <p style="font-size: 13px; color: #94a3b8;">محكمة الاستئناف التجارية • الدائرة الثانية</p>
                    <div style="margin-top: 12px; font-size: 12px; color: #cbd5e1;">القضية: ق/2026/0890 (شركة ريادة للصناعات)</div>
                </div>
            </div>
        </div>
        """
    else: # finance
        return """
        <div class="glass-card">
            <h2 style="font-size: 18px; font-weight: 800; margin-bottom: 16px;">حسابات أمانات العملاء (Trust Accounts) وسندات القبض والصرف</h2>
            <div class="stats-grid" style="margin-bottom: 20px;">
                <div class="stat-card"><div class="stat-info"><h3 style="color: #10b981;">$ 412,500</h3><span>إجمالي رصيد الأمانات المعزولة</span></div></div>
                <div class="stat-card"><div class="stat-info"><h3 style="color: #818cf8;">$ 89,200</h3><span>أتعاب المحاماة المستحقة</span></div></div>
                <div class="stat-card"><div class="stat-info"><h3 style="color: #f59e0b;">$ 15,400</h3><span>رسوم قضائية وخبرة مدفوعة</span></div></div>
                <div class="stat-card"><div class="stat-info"><h3 style="color: #38bdf8;">100%</h3><span>التوافق المحاسبي والرقابي</span></div></div>
            </div>
            <table class="table-responsive">
                <thead>
                    <tr>
                        <th>رقم السند</th>
                        <th>اسم العميل</th>
                        <th>القضية المرتبطة</th>
                        <th>نوع المعاملة</th>
                        <th>المبلغ</th>
                        <th>تاريخ السند</th>
                        <th>الحالة الرقابية</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style="font-weight: 700; color: #818cf8;">TR-2026-901</td>
                        <td>مجموعة المجد للاستثمار</td>
                        <td>ق/2026/1042</td>
                        <td>إيداع أمانة تنفيذ حكم</td>
                        <td style="font-weight: 800; color: #10b981;">+ $ 120,000</td>
                        <td>10 نوفمبر 2026</td>
                        <td><span class="badge badge-success">معتمد ومطابق</span></td>
                    </tr>
                    <tr>
                        <td style="font-weight: 700; color: #818cf8;">TR-2026-902</td>
                        <td>شركة ريادة للصناعات</td>
                        <td>ق/2026/0890</td>
                        <td>صرف أتعاب خبراء هندسيين</td>
                        <td style="font-weight: 800; color: #f43f5e;">- $ 8,500</td>
                        <td>08 نوفمبر 2026</td>
                        <td><span class="badge badge-success">سند رسمي موثق</span></td>
                    </tr>
                </tbody>
            </table>
        </div>
        """

modules = ['dashboard', 'cases', 'hearings', 'finance']

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    for m in modules:
        html = get_page_html(m)
        page.set_content(html, wait_until='networkidle')
        fn = os.path.join(output_dir, f'real_ui_{m}_1920.png')
        page.screenshot(path=fn)
        print(f'Captured {m}: {fn}')
    browser.close()

print('ALL_REAL_UI_VIEWS_SUCCESSFULLY_CAPTURED')
