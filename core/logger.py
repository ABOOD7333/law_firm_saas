"""
نظام السجلات المركزي — Law Firm SaaS
يوفر logger موحد لجميع أجزاء التطبيق مع دعم الملفات والـ console.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def get_logger(name: str = "law_firm") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # تجنب تكرار الـ handlers

    logger.setLevel(logging.DEBUG)

    # ─── Format ───────────────────────────────────────────────
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # ─── Console Handler ──────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)

    # ─── File Handler (rotating 5MB × 3 backups) ──────────────
    file_handler = RotatingFileHandler(
        filename=os.path.join(LOG_DIR, "app.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    # ─── Error-only File ──────────────────────────────────────
    error_handler = RotatingFileHandler(
        filename=os.path.join(LOG_DIR, "errors.log"),
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(fmt)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)

    return logger


# ─── Singleton للاستخدام العام ────────────────────────────────
app_logger = get_logger("law_firm")
