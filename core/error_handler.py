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
IS_PRODUCTION = os.getenv("APP_ENV", "development").lower() == "production"


def safe_error_html(exc: Exception, context: str = "") -> HTMLResponse:
    """
    يُعيد HTML آمن عند حدوث خطأ.
    - في الإنتاج: رسالة عامة فقط.
    - في التطوير: Stack Trace كامل للتشخيص.
    """
    tb_str = traceback.format_exc()
    app_logger.error(f"[ERROR] {context}: {exc}\n{tb_str}")

    if IS_PRODUCTION:
        return HTMLResponse(
            content=(
                "<div dir='rtl' style='font-family:sans-serif;padding:40px;text-align:center'>"
                "<h2 style='color:#dc2626'>⚠️ حدث خطأ داخلي</h2>"
                "<p style='color:#64748b'>يرجى المحاولة مرة أخرى أو التواصل مع الدعم الفني.</p>"
                "</div>"
            ),
            status_code=500
        )
    else:
        return HTMLResponse(
            content=f"<pre dir='ltr' style='background:#1e1e1e;color:#f8f8f2;padding:20px'>{tb_str}</pre>",
            status_code=500
        )


def safe_error_json(exc: Exception, context: str = "") -> JSONResponse:
    """
    يُعيد JSON آمن عند حدوث خطأ في API endpoints.
    """
    tb_str = traceback.format_exc()
    app_logger.error(f"[API ERROR] {context}: {exc}\n{tb_str}")

    if IS_PRODUCTION:
        return JSONResponse(
            {"success": False, "error": "حدث خطأ داخلي. يرجى المحاولة مرة أخرى."},
            status_code=500
        )
    else:
        return JSONResponse(
            {"success": False, "error": str(exc), "trace": tb_str},
            status_code=500
        )
