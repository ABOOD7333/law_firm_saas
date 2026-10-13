"""
[CENTRALIZED SYSTEM-WIDE ERROR HANDLING ENGINE]
يوفر تجربة مستخدم واضحة ومهنية باللغة العربية لجميع أنواع الأخطاء (400, 401, 403, 404, 422, 429, 500).
يمنع ظهور الشاشات السوداء والرسائل التقنية المبهمة للمستخدمين، مع الاحتفاظ بالسجلات الكاملة للمطورين.
"""
import os
import traceback
from typing import Optional
from fastapi.responses import HTMLResponse, JSONResponse
from core.logger import app_logger

IS_PRODUCTION = os.getenv("APP_ENV", "production").lower() == "production"
SHOW_DEBUG_ERRORS = os.getenv("APP_DEBUG", "0").lower() in {"1", "true", "yes"} and not IS_PRODUCTION

# القاموس الموحد لتوضيح الأخطاء باللغة العربية للمستخدم
ERROR_CATALOG = {
    400: {
        "title": "خطأ في البيانات المدخلة",
        "description": "البيانات المرسلة تحتوي على حقول غير مطابقة للشروط أو قيم ناقصة أو غير صالحة.",
        "icon": "fa-circle-exclamation",
        "color": "#ea580c"
    },
    401: {
        "title": "انتهت الجلسة أو غير مسجل الدخول",
        "description": "يرجى تسجيل الدخول إلى حسابك أولاً للوصول إلى هذا القسم أو تنفيذ الإجراء.",
        "icon": "fa-lock",
        "color": "#4f46e5"
    },
    403: {
        "title": "طلب غير مصرح به أو انتهاء رمز الأمان",
        "description": "ليس لديك الصلاحية الكافية للقيام بهذا الإجراء، أو أن رمز التحقق الأمني (CSRF) منتهي الصلاحية.",
        "icon": "fa-shield-halved",
        "color": "#dc2626"
    },
    404: {
        "title": "الصفحة أو السجل غير موجود",
        "description": "الرابط المطلوب غير متوفر أو ربما تم حذفه أو نقله إلى مكان آخر.",
        "icon": "fa-file-circle-question",
        "color": "#64748b"
    },
    405: {
        "title": "طريقة الطلب غير مسموح بها",
        "description": "طريقة الإرسال المستخدمة غير مدعومة لهذا المسار في النظام.",
        "icon": "fa-ban",
        "color": "#dc2626"
    },
    422: {
        "title": "خطأ في التحقق من صحة المدخلات",
        "description": "بعض الحقول المدخلة تحتوي على بيانات غير صالحة أو غير متوافقة مع نوع الحقل المطلوب.",
        "icon": "fa-pen-ruler",
        "color": "#d97706"
    },
    429: {
        "title": "تجاوز الحد المسموح من الطلبات",
        "description": "تم تسجيل عدد كبير من المحاولات في وقت قصير. يرجى الانتظار دقيقة واحدة ثم المحاولة مجدداً.",
        "icon": "fa-hourglass-half",
        "color": "#b45309"
    },
    500: {
        "title": "حدث خطأ تقني في معالجة الطلب",
        "description": "واجه الخادم مشكلة غير متوقعة أثناء معالجة طلبك. تم تسجيل الخطأ فوراً في سجلات النظام لمعالجته.",
        "icon": "fa-triangle-exclamation",
        "color": "#dc2626"
    }
}


def render_error_page(
    status_code: int = 500,
    title: Optional[str] = None,
    message: Optional[str] = None,
    detail: str = "",
    context: str = "",
    can_retry: bool = True
) -> HTMLResponse:
    """
    توليد واجهة HTML احترافية باللغة العربية توضح للمستخدم نوع الخطأ وسببه والحل المقترح.
    """
    catalog = ERROR_CATALOG.get(status_code, ERROR_CATALOG[500])
    display_title = title or catalog["title"]
    display_message = message or catalog["description"]
    icon_class = catalog["icon"]
    color = catalog["color"]

    # الكشف عن أخطاء CSRF لتقديم إرشاد دقيق للمستخدم
    is_csrf_error = False
    if "csrf" in str(detail).lower() or "csrf" in str(message).lower() or (status_code == 403 and not title):
        is_csrf_error = True
        display_title = "تنبيه أمان: انتهاء صلاحية جلسة التحقق (CSRF Token)"
        display_message = (
            "انتهت صلاحية رمز الأمان المؤقت الخاص بالنموذج (CSRF) أو تم فتح الصفحة في أكثر من نافذة. "
            "لحماية بياناتك ومنع التلاعب بالنماذج، تم إيقاف العملية مؤقتاً."
        )

    # الحل المقترح بناءً على كود الخطأ
    solution_text = "يرجى الضغط على زر 'تحديث الصفحة' أدناه لإعادة المحاولة فوراً."
    if is_csrf_error:
        solution_text = "الحل الموصى به: اضغط على زر 'تحديث الصفحة ومحاولة الإرسال مجدداً' لتجديد رمز الأمان وإرسال البيانات بنجاح."
    elif status_code == 401:
        solution_text = "الحل الموصى به: اضغط على 'تسجيل الدخول' لإعادة توثيق حسابك."
    elif status_code == 403:
        solution_text = "الحل الموصى به: تحقق من صلاحيات حسابك مع مدير المكتب، أو حدث الصفحة إذا كنت تتوقع أن الإجراء مسموح لك."
    elif status_code == 404:
        solution_text = "الحل الموصى به: تأكد من صحة الرابط أو استخدم زر العودة للوحة التحكم للوصول للبيانات."

    debug_section = ""
    if detail:
        clean_detail = str(detail).replace("<", "&lt;").replace(">", "&gt;")
        debug_section = f"""
        <div style="margin-top: 20px; text-align: right; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 18px;">
            <div style="font-weight: 700; color: #475569; font-size: 0.88rem; margin-bottom: 6px;">
                <i class="fa-solid fa-circle-info" style="color: #3b82f6;"></i> تفاصيل إضافية للخطأ:
            </div>
            <div style="font-family: monospace, 'Cairo'; font-size: 0.85rem; color: #1e293b; background: #ffffff; padding: 8px 12px; border-radius: 6px; border: 1px solid #cbd5e1; direction: rtl; text-align: right;">
                {clean_detail}
            </div>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تنبيه بالنظام ({status_code}) | منصة المحاماة LawSaaS</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            padding: 0;
            font-family: 'Cairo', sans-serif;
            background-color: #f1f5f9;
            color: #0f172a;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            direction: rtl;
        }}
        .error-card {{
            background: #ffffff;
            width: 640px;
            max-width: 92%;
            border-radius: 18px;
            box-shadow: 0 20px 40px -15px rgba(15, 23, 42, 0.12), 0 0 1px rgba(15, 23, 42, 0.1);
            border: 1px solid #e2e8f0;
            padding: 36px 32px;
            text-align: center;
            margin: 20px;
        }}
        .error-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: {color}15;
            color: {color};
            border: 1px solid {color}30;
            padding: 4px 14px;
            border-radius: 30px;
            font-weight: 800;
            font-size: 0.85rem;
            margin-bottom: 16px;
        }}
        .error-icon-box {{
            width: 72px;
            height: 72px;
            border-radius: 20px;
            background: {color}12;
            color: {color};
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2.2rem;
            margin: 0 auto 18px auto;
        }}
        .error-title {{
            font-size: 1.4rem;
            font-weight: 800;
            color: #0f172a;
            margin: 0 0 10px 0;
            line-height: 1.4;
        }}
        .error-desc {{
            font-size: 0.96rem;
            color: #475569;
            line-height: 1.6;
            margin: 0 0 16px 0;
        }}
        .solution-box {{
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            border-radius: 10px;
            padding: 12px 16px;
            font-size: 0.88rem;
            color: #1e40af;
            font-weight: 700;
            margin-bottom: 24px;
            text-align: right;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .error-actions {{
            display: flex;
            gap: 12px;
            justify-content: center;
            flex-wrap: wrap;
        }}
        .btn-action {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 11px 22px;
            border-radius: 10px;
            font-family: 'Cairo', sans-serif;
            font-weight: 700;
            font-size: 0.92rem;
            text-decoration: none;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
        }}
        .btn-primary {{
            background: #1e40af;
            color: #ffffff;
        }}
        .btn-primary:hover {{
            background: #1d4ed8;
            transform: translateY(-1px);
        }}
        .btn-secondary {{
            background: #f8fafc;
            color: #334155;
            border-color: #cbd5e1;
        }}
        .btn-secondary:hover {{
            background: #f1f5f9;
            color: #0f172a;
        }}
    </style>
</head>
<body>
    <div class="error-card">
        <div class="error-badge">
            <i class="fa-solid fa-code"></i> رمز الحالة: {status_code}
        </div>
        <div class="error-icon-box">
            <i class="fa-solid {icon_class}"></i>
        </div>
        <h1 class="error-title">{display_title}</h1>
        <p class="error-desc">{display_message}</p>
        
        <div class="solution-box">
            <i class="fa-solid fa-lightbulb" style="font-size: 1.1rem; flex-shrink: 0;"></i>
            <span>{solution_text}</span>
        </div>

        {debug_section}

        <div class="error-actions" style="margin-top: 24px;">
            <button onclick="window.location.reload()" class="btn-action btn-primary">
                <i class="fa-solid fa-rotate-right"></i> تحديث الصفحة والمحاولة مجدداً
            </button>
            <button onclick="window.history.back()" class="btn-action btn-secondary">
                <i class="fa-solid fa-arrow-right"></i> الرجوع للصفحة السابقة
            </button>
            <a href="/dashboard" class="btn-action btn-secondary">
                <i class="fa-solid fa-house"></i> لوحة التحكم
            </a>
        </div>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html_content, status_code=status_code)


def safe_error_html(exc: Exception, context: str = "", status_code: int = 500) -> HTMLResponse:
    """
    معالجة استثناءات الخادم وإعادتها بصيغة صفحة خطأ عربية مشروحة.
    """
    tb_str = traceback.format_exc()
    app_logger.error(f"[ERROR] {context}: {exc}\n{tb_str}")

    detail_msg = f"{exc}" if not IS_PRODUCTION or SHOW_DEBUG_ERRORS else ""
    return render_error_page(
        status_code=status_code,
        title="حدث خطأ في معالجة طلب الصفحة",
        message="تعذر إكمال الطلب بسبب خطأ داخلي. يرجى المحاولة لاحقاً.",
        detail=detail_msg,
        context=context
    )


def safe_error_json(exc: Exception, context: str = "", status_code: int = 500) -> JSONResponse:
    """
    يُعيد رد JSON منسق ومفهوم للمستخدم عند حدوث خطأ في API endpoints.
    """
    tb_str = traceback.format_exc()
    app_logger.error(f"[API ERROR] {context}: {exc}\n{tb_str}")

    catalog = ERROR_CATALOG.get(status_code, ERROR_CATALOG[500])
    error_msg = catalog["description"]

    return JSONResponse(
        {
            "success": False,
            "status": status_code,
            "error": error_msg,
            "title": catalog["title"]
        },
        status_code=status_code
    )
