import os, json, subprocess, base64, shutil
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PROD_DIR = os.path.abspath('LawSaaS_Media_Production')
DESKTOP_DIR = os.path.abspath(r'C:\Users\Roots\Desktop\ترويج')
FFMPEG = r'C:\Program Files\FormatFactory5.20.0.0\ffmpeg.exe'

# Load metadata
meta_path = os.path.join(PROD_DIR, '07_Scripts_And_Voiceovers', 'waziruk_scenes_meta.json')
with open(meta_path, 'r', encoding='utf-8') as f:
    meta = json.load(f)

scenes = meta['scenes']
ui_dir = os.path.join(PROD_DIR, '08_Project_Source_Files', 'ui_captures')
logo_file = os.path.join(PROD_DIR, '01_Brand_Identity', 'lawsaas_logo_golden_scales.jpg')

def get_base64_data_uri(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    mime = 'image/jpeg' if ext in ['.jpg', '.jpeg'] else 'image/png'
    with open(file_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')
    return f"data:{mime};base64,{b64}"

logo_b64 = get_base64_data_uri(logo_file)
landing_b64 = get_base64_data_uri(os.path.join(ui_dir, 'waziruk_landing_1920.png'))
login_b64 = get_base64_data_uri(os.path.join(ui_dir, 'waziruk_login_1920.png'))
dashboard_b64 = get_base64_data_uri(os.path.join(ui_dir, 'real_ui_dashboard_1920.png'))
cases_b64 = get_base64_data_uri(os.path.join(ui_dir, 'real_ui_cases_1920.png'))
hearings_b64 = get_base64_data_uri(os.path.join(ui_dir, 'real_ui_hearings_1920.png'))
finance_b64 = get_base64_data_uri(os.path.join(ui_dir, 'real_ui_finance_1920.png'))

scene_visuals = [
    {
        'index': 1,
        'title': 'إدارة الأمس لم تعد تكفي لمكتبك القانوني',
        'subtitle': 'تشتت الملفات وضياع المواعيد بين مئات الأوراق والمستندات',
        'badge': 'التحديات الإدارية اليومية',
        'badge_color': '#f43f5e',
        'image_b64': logo_b64,
        'type': 'problem'
    },
    {
        'index': 2,
        'title': 'منظومة وزيرك السحابية المتكاملة',
        'subtitle': 'الحل الرقمي الذكي الذي يجمع كافة أعمال مكتبك في منصة واحدة آمنة',
        'badge': 'الحل السحابي الشامل',
        'badge_color': '#10b981',
        'image_b64': landing_b64,
        'type': 'browser'
    },
    {
        'index': 3,
        'title': 'لوحة تحكم ذكية وإدارة مركزية للقضايا',
        'subtitle': 'تتبع مراحل التقاضي، أطراف النزاع، والمؤشرات اللحظية بدقة متناهية',
        'badge': 'إدارة القضايا والنزاعات',
        'badge_color': '#818cf8',
        'image_b64': dashboard_b64,
        'type': 'browser'
    },
    {
        'index': 4,
        'title': 'التقويم القضائي الذكي وجدولة الجلسات',
        'subtitle': 'تنبيهات مسبقة وتتبع آلي للمدد والمهل القانونية لتفادي أي سقوط إجرائي',
        'badge': 'الجلسات والمهل القانونية',
        'badge_color': '#f59e0b',
        'image_b64': hearings_b64,
        'type': 'browser'
    },
    {
        'index': 5,
        'title': 'أمانات العملاء والفوترة الإلكترونية المعتمدة',
        'subtitle': 'عزل حسابات الأمانات، فواتير إلكترونية وسندات صرف وقبض موثقة بالكامل',
        'badge': 'أمانات العملاء والمالية',
        'badge_color': '#10b981',
        'image_b64': finance_b64,
        'type': 'browser'
    },
    {
        'index': 6,
        'title': 'إدارة مهام الفريق والوصول السحابي من أي مكان',
        'subtitle': 'بوابة خاصة للموكلين، بيئة عمل تعاونية وتوافق فوري مع الهاتف والكمبيوتر',
        'badge': 'العمل الجماعي والأمان السحابي',
        'badge_color': '#818cf8',
        'image_b64': login_b64,
        'type': 'browser'
    },
    {
        'index': 7,
        'title': 'ابدأ الآن مع منصة وزيرك',
        'subtitle': 'انضم إلى نخبة مكاتب المحاماة الأكثر تطوراً واستفد من جميع المزايا فوراً',
        'badge': 'سجّل حسابك اليوم',
        'badge_color': '#d4af37',
        'image_b64': logo_b64,
        'type': 'cta'
    }
]

def generate_scene_html(sc_idx, width=1920, height=1080):
    vis = scene_visuals[sc_idx]
    sc_data = scenes[sc_idx]
    
    title_size = '42px'
    sub_size = '22px'
    v_text = sc_data['text']
    
    if vis['type'] == 'problem':
        content_html = f"""
        <div class="problem-container">
            <div class="logo-box">
                <img src="{vis['image_b64']}" class="hero-logo glow">
            </div>
            <div class="badge-pill" style="border-color: {vis['badge_color']}; color: {vis['badge_color']};">
                <i class="fa-solid fa-triangle-exclamation"></i> {vis['badge']}
            </div>
            <h1 class="main-title">{vis['title']}</h1>
            <p class="subtitle">{vis['subtitle']}</p>
            <div class="challenge-cards">
                <div class="c-card"><i class="fa-solid fa-folder-tree"></i> تشتت ملفات القضايا</div>
                <div class="c-card"><i class="fa-solid fa-clock"></i> خطر فوات المواعيد</div>
                <div class="c-card"><i class="fa-solid fa-receipt"></i> صعوبة حصر الأمانات</div>
            </div>
        </div>
        """
    elif vis['type'] == 'cta':
        content_html = f"""
        <div class="cta-container">
            <img src="{vis['image_b64']}" class="hero-logo glow-gold">
            <h1 class="brand-name">منصة وزيرك</h1>
            <div class="cta-slogan">المنظومة السحابية المتكاملة لإدارة مكاتب المحاماة</div>
            <div class="domain-pill">
                <span class="url-text">waziruk.tech</span>
                <i class="fa-solid fa-arrow-left"></i>
            </div>
            <p class="cta-call">سجّل حسابك الآن • ارتقِ بأعمال مكتبك القانوني</p>
        </div>
        """
    else: # Browser UI
        content_html = f"""
        <div class="ui-container">
            <div class="header-tags">
                <div class="badge-pill" style="border-color: {vis['badge_color']}; color: {vis['badge_color']};">
                    <i class="fa-solid fa-circle-check"></i> {vis['badge']}
                </div>
                <h1 class="main-title">{vis['title']}</h1>
                <p class="subtitle">{vis['subtitle']}</p>
            </div>
            <div class="browser-frame shadow-2xl">
                <div class="browser-top">
                    <div class="dots">
                        <span class="dot red"></span>
                        <span class="dot yellow"></span>
                        <span class="dot green"></span>
                    </div>
                    <div class="address-bar">
                        <i class="fa-solid fa-lock" style="color: #10b981; font-size: 11px;"></i>
                        <span>https://waziruk.tech/app</span>
                    </div>
                </div>
                <div class="browser-body">
                    <img src="{vis['image_b64']}" class="ui-screen">
                </div>
            </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Cairo', sans-serif; }}
        body {{
            width: {width}px;
            height: {height}px;
            background: radial-gradient(circle at 50% 20%, #1e1b4b 0%, #070d19 100%);
            color: #fff;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 30px 50px;
            overflow: hidden;
            position: relative;
        }}
        
        body::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background-image: 
                linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
            background-size: 50px 50px;
            pointer-events: none;
        }}
        
        .brand-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 10;
        }}
        .brand-pill {{
            display: inline-flex;
            align-items: center;
            gap: 12px;
            background: rgba(255, 255, 255, 0.06);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.12);
            padding: 8px 20px;
            border-radius: 30px;
            font-size: 16px;
            font-weight: 800;
        }}
        .brand-pill img {{ width: 28px; height: 28px; border-radius: 8px; }}
        
        .main-center {{
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            z-index: 10;
            text-align: center;
        }}
        
        .badge-pill {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 5px 16px;
            border-radius: 30px;
            border: 1px solid;
            background: rgba(0, 0, 0, 0.4);
            font-size: 15px;
            font-weight: 700;
            margin-bottom: 10px;
        }}
        
        .main-title {{
            font-size: {title_size};
            font-weight: 900;
            line-height: 1.3;
            margin-bottom: 8px;
            background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .subtitle {{
            font-size: {sub_size};
            color: #94a3b8;
            font-weight: 600;
            max-width: 900px;
            line-height: 1.4;
            margin-bottom: 16px;
        }}
        
        .problem-container {{
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .logo-box {{ margin-bottom: 20px; }}
        .hero-logo {{
            width: 155px;
            height: 155px;
            border-radius: 30px;
            border: 2px solid rgba(212, 175, 55, 0.5);
        }}
        .glow {{ box-shadow: 0 0 50px rgba(79, 70, 229, 0.5); }}
        .glow-gold {{ box-shadow: 0 0 65px rgba(212, 175, 55, 0.65); }}
        
        .challenge-cards {{
            display: flex;
            gap: 16px;
            margin-top: 14px;
            flex-wrap: wrap;
            justify-content: center;
        }}
        .c-card {{
            background: rgba(244, 63, 94, 0.12);
            border: 1px solid rgba(244, 63, 94, 0.35);
            color: #fda4af;
            padding: 10px 22px;
            border-radius: 12px;
            font-size: 17px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .ui-container {{
            width: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .browser-frame {{
            width: 94%;
            background: #0f172a;
            border-radius: 14px;
            border: 1px solid rgba(255, 255, 255, 0.15);
            box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.7);
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }}
        .browser-top {{
            height: 34px;
            background: #1e293b;
            display: flex;
            align-items: center;
            padding: 0 14px;
            gap: 14px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .dots {{ display: flex; gap: 6px; }}
        .dot {{ width: 10px; height: 10px; border-radius: 50%; }}
        .dot.red {{ background: #f43f5e; }}
        .dot.yellow {{ background: #f59e0b; }}
        .dot.green {{ background: #10b981; }}
        .address-bar {{
            background: #0f172a;
            padding: 3px 14px;
            border-radius: 6px;
            font-size: 11px;
            color: #94a3b8;
            display: flex;
            align-items: center;
            gap: 6px;
            direction: ltr;
        }}
        .browser-body {{
            width: 100%;
            max-height: 540px;
            overflow: hidden;
            background: #0f172a;
        }}
        .ui-screen {{
            width: 100%;
            height: auto;
            display: block;
        }}
        
        .cta-container {{
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .brand-name {{
            font-size: 58px;
            font-weight: 900;
            color: #fff;
            margin-top: 14px;
            letter-spacing: -1px;
        }}
        .cta-slogan {{
            font-size: 24px;
            color: #d4af37;
            font-weight: 700;
            margin: 10px 0 22px 0;
        }}
        .domain-pill {{
            background: linear-gradient(135deg, #4f46e5 0%, #3730a3 100%);
            padding: 16px 44px;
            border-radius: 50px;
            font-size: 32px;
            font-weight: 900;
            color: #fff;
            display: inline-flex;
            align-items: center;
            gap: 16px;
            box-shadow: 0 12px 35px rgba(79, 70, 229, 0.5);
            border: 2px solid rgba(255, 255, 255, 0.2);
            direction: ltr;
        }}
        .cta-call {{
            margin-top: 22px;
            font-size: 20px;
            color: #cbd5e1;
            font-weight: 600;
        }}
        
        .caption-bar {{
            width: 100%;
            background: rgba(15, 23, 42, 0.9);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.12);
            padding: 14px 24px;
            border-radius: 14px;
            text-align: center;
            z-index: 20;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }}
        .caption-text {{
            font-size: 22px;
            font-weight: 700;
            color: #f8fafc;
            line-height: 1.4;
        }}
    </style>
</head>
<body>
    <div class="brand-header">
        <div class="brand-pill">
            <img src="{logo_b64}">
            <span>منصة وزيرك | المنظومة القانونية السحابية</span>
        </div>
        <div style="font-size: 15px; color: #94a3b8; font-weight: 700;">
            <i class="fa-solid fa-shield-halved" style="color: #10b981;"></i> بيئة سحابية مشفرة ومحمية
        </div>
    </div>
    
    <div class="main-center">
        {content_html}
    </div>
    
    <div class="caption-bar">
        <div class="caption-text">
            <i class="fa-solid fa-volume-high" style="color: #818cf8; margin-left: 8px;"></i>
            {v_text}
        </div>
    </div>
</body>
</html>"""

def render_single_promo():
    width, height = 1920, 1080
    print(f"=== RENDERING THE SINGLE MASTER PROMO FOR WAZIRUK (16:9 {width}x{height}) ===")
    render_dir = os.path.join(PROD_DIR, '08_Project_Source_Files', 'render_waziruk_master')
    os.makedirs(render_dir, exist_ok=True)
    
    scene_video_segments = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': width, 'height': height})
        
        for sc_idx, sc_data in enumerate(scenes):
            html = generate_scene_html(sc_idx, width, height)
            page.set_content(html, wait_until='networkidle')
            frame_png = os.path.join(render_dir, f'scene_{sc_idx+1}.png')
            page.screenshot(path=frame_png)
            
            seg_mp4 = os.path.join(render_dir, f'seg_{sc_idx+1}.mp4')
            audio_f = sc_data['file']
            dur = sc_data['duration']
            
            cmd = [
                FFMPEG, '-y',
                '-loop', '1', '-i', frame_png,
                '-i', audio_f,
                '-c:v', 'libx264', '-tune', 'stillimage', '-preset', 'fast', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '192k',
                '-t', str(dur),
                seg_mp4
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            scene_video_segments.append(seg_mp4)
            print(f"Rendered segment {sc_idx+1} ({dur:.2f}s)")
            
        browser.close()
        
    concat_list = os.path.join(render_dir, 'concat.txt')
    with open(concat_list, 'w', encoding='utf-8') as f:
        for seg in scene_video_segments:
            f.write(f"file '{seg.replace('\\', '/')}'\n")
            
    concat_mp4 = os.path.join(render_dir, 'waziruk_voiceover_raw.mp4')
    subprocess.run([
        FFMPEG, '-y',
        '-f', 'concat', '-safe', '0', '-i', concat_list,
        '-c', 'copy',
        concat_mp4
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    
    music_f = os.path.join(PROD_DIR, '08_Project_Source_Files', 'ambient_corporate_score.mp3')
    
    # Destination single master file
    out_name = "إعلان_منصة_وزيرك_الرئيسي.mp4"
    target_local = os.path.join(PROD_DIR, '02_Main_Promo', out_name)
    target_desktop = os.path.join(DESKTOP_DIR, out_name)
    
    mix_cmd = [
        FFMPEG, '-y',
        '-i', concat_mp4,
        '-i', music_f,
        '-filter_complex',
        '[1:a]volume=0.18[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=3[aout]',
        '-map', '0:v',
        '-map', '[aout]',
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '192k',
        target_local
    ]
    subprocess.run(mix_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    shutil.copy2(target_local, target_desktop)
    
    print("\nSUCCESSFULLY_CREATED_SINGLE_MASTER_PROMO:")
    print(" -> Local file:", target_local, f"({os.path.getsize(target_local)} bytes)")
    print(" -> Desktop file:", target_desktop, f"({os.path.getsize(target_desktop)} bytes)")

if __name__ == '__main__':
    render_single_promo()
