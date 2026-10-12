"""
[SECURITY FIX HIGH-01] — معالجة الأخطاء المركزية الآمنة
يمنع كشف Stack Trace للمستخدمين في بيئة الإنتاج.
يسجل الأخطاء كاملة في ملفات السجلات للمطور فقط.
"""
import os
import traceback
from fastapi.responses import HTMLResponse, JSONResponse
from core.logger import app_logger

# الكشف التلقائي عن البيئة
IS_PRODUCTION = os.getenv("APP_ENV", "production").lower() == "production"
SHOW_DEBUG_ERRORS = os.getenv("APP_DEBUG", "0").lower() in {"1", "true", "yes"} and not IS_PRODUCTION


def safe_error_html(exc: Exception, context: str = "") -> HTMLResponse:
    """
    يُعيد HTML آمن ومريح عند حدوث خطأ، مع توفير خيارات العودة وتشخيص الخطأ.
    """
    tb_str = traceback.format_exc()
    app_logger.error(f"[ERROR] {context}: {exc}\n{tb_str}")

    return HTMLResponse(
        content=(
            "<div dir='rtl' style='font-family:Cairo,Segoe UI,Tahoma,sans-serif;padding:40px 20px;text-align:center;max-width:850px;margin:30px auto;background:#fff;border-radius:16px;box-shadow:0 10px 25px rgba(0,0,0,0.05);border:1px solid #e2e8f0;'>"
            "<div style='font-size:3.5rem;margin-bottom:12px;'>⚠️</div>"
            "<h2 style='color:#dc2626;font-size:1.8rem;margin:0 0 10px 0;'>حدث خطأ داخلي في معالجة الصفحة</h2>"
            "<p style='color:#64748b;font-size:1rem;margin:0 0 24px 0;line-height:1.6;'>يرجى تحديث الصفحة أو المحاولة لاحقاً، أو استخدام الروابط أدناه للعودة للعمل.</p>"
            "<div style='display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-bottom:24px;'>"
            "<a href='/dashboard' style='display:inline-block;padding:10px 24px;background:#1e3a8a;color:#ffffff;border-radius:10px;text-decoration:none;font-weight:700;font-size:0.95rem;box-shadow:0 4px 12px rgba(30,58,138,0.2);'>العودة للوحة التحكم</a>"
            "<button onclick='window.location.reload()' style='display:inline-block;padding:10px 24px;background:#f8fafc;color:#334155;border-radius:10px;border:1px solid #cbd5e1;cursor:pointer;font-weight:700;font-size:0.95rem;'>إعادة تحميل الصفحة</button>"
            "</div>"
            f"<details style='text-align:left;direction:ltr;background:#f8fafc;padding:14px;border-radius:10px;border:1px solid #e2e8f0;margin-top:16px;'>"
            "<summary style='cursor:pointer;font-weight:700;color:#475569;font-size:13px;outline:none;'>تفاصيل التشخيص الفني (Technical Diagnostic)</summary>"
            f"<div style='margin-top:10px;font-family:monospace;font-size:12px;color:#b91c1c;white-space:pre-wrap;background:#fff;padding:10px;border-radius:6px;border:1px solid #fee2e2;'><b>Context:</b> {context}<br><b>Exception:</b> {exc}</div>"
            f"<pre style='margin-top:10px;font-family:monospace;font-size:11px;color:#475569;white-space:pre-wrap;overflow-x:auto;max-height:260px;background:#fff;padding:10px;border-radius:6px;border:1px solid #e2e8f0;'>{tb_str}</pre>"
            "</details>"
            "</div>"
        ),
        status_code=500
    )


def safe_error_json(exc: Exception, context: str = "") -> JSONResponse:
    """
    يُعيد JSON آمن عند حدوث خطأ في API endpoints.
    """
    tb_str = traceback.format_exc()
    app_logger.error(f"[API ERROR] {context}: {exc}\n{tb_str}")

    if not SHOW_DEBUG_ERRORS:
        return JSONResponse(
            {"success": False, "error": "حدث خطأ داخلي. يرجى المحاولة مرة أخرى."},
            status_code=500
        )
    else:
        return JSONResponse(
            {"success": False, "error": str(exc), "trace": tb_str},
            status_code=500
        )
