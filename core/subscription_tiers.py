"""
Subscription Tiers & Exchange Rate Engine
==========================================
Defines the 3 commercial SaaS tiers, feature flags, limits, and multi-currency pricing logic.
Supports dynamic daily exchange rate storage via AppSettings.
"""

from typing import Dict, Any, List, Optional
from decimal import Decimal, ROUND_HALF_UP
import json
from sqlalchemy.orm import Session
from database.models import AppSettings

# --- تعريف الباقات الثلاث المعتمدة ---
TIERS: Dict[str, Dict[str, Any]] = {
    "solo": {
        "id": "solo",
        "name_ar": "المحامي المستقل",
        "name_en": "Solo Lawyer",
        "badge": "الممارس الفردي",
        "color": "#10b981",
        "price_monthly_usd": 19.99,
        "price_yearly_usd": 180.00,
        "max_users": 1,
        "max_active_cases": 50,
        "storage_gb": 5,
        "disabled_modules": [
            "yemeni_laws",           # ملغية حسب توجيه الإدارة للمحامي المستقل
            "kanban",
            "conflict_check",
            "timesheet",
            "matters",
            "trust_accounts",
            "intake",
            "advanced_operations",
        ],
        "features": [
            "إدارة القضايا والموكلين والجلسات",
            "التقويم القضائي والمواعيد والتنبيهات",
            "سندات القبض والصرف البسيطة والفواتير",
            "تطبيق الهاتف الذكي (iOS & Android)",
            "دعم فني عبر البريد والتذاكر",
        ],
    },
    "pro": {
        "id": "pro",
        "name_ar": "المكتب الاحترافي",
        "name_en": "Pro Law Firm",
        "badge": "الأكثر طلباً ⭐",
        "color": "#3b82f6",
        "price_monthly_usd": 49.99,
        "price_yearly_usd": 480.00,
        "max_users": 5,
        "max_active_cases": 300,
        "storage_gb": 50,
        "disabled_modules": [
            "trust_accounts",
            "intake",
            "advanced_operations",
        ],
        "features": [
            "كافة ميزات باقة المستقل",
            "مكتبة القوانين والتشريعات اليمنية المحدثة",
            "لوحة كانبان الذكية لإدارة المهام وتدفق القضايا",
            "فحص تضارب المصالح القضائي (Conflict Check)",
            "سجل الساعات والأتعاب المستحقة (Timesheet)",
            "إدارة المسائل والاستشارات القانونية (Matters)",
            "أولوية في الدعم الفني",
        ],
    },
    "enterprise": {
        "id": "enterprise",
        "name_ar": "الشركات والمجموعات",
        "name_en": "Enterprise Legal Group",
        "badge": "النخبة 👑",
        "color": "#8b5cf6",
        "price_monthly_usd": 99.99,
        "price_yearly_usd": 950.00,
        "max_users": 7,
        "max_active_cases": 500,
        "storage_gb": 500,
        "disabled_modules": [],       # كافة الميزات مفتوحة 100% (مع حصر SOC للمشرف العام فقط)
        "features": [
            "كافة ميزات باقة المكتب الاحترافي",
            "حسابات الأمانات المصرفية المقيدة (IOLTA Trust Accounts)",
            "استمارات استقبال الموكلين والتوقيع الإلكتروني (Client Intake & E-Sign)",
            "العمليات المؤسسية المتقدمة وتقارير الذكاء المالي",
            "تخصيص الهوية والشعار على المستندات والتقارير",
            "أولوية قصوى ومدير حساب مخصص على مدار الساعة",
        ],
    },
    "trial": {
        "id": "trial",
        "name_ar": "الفترة التجريبية",
        "name_en": "Free Trial",
        "badge": "تجريبي",
        "color": "#f59e0b",
        "price_monthly_usd": 0.0,
        "price_yearly_usd": 0.0,
        "max_users": 3,
        "max_active_cases": 20,
        "storage_gb": 2,
        "disabled_modules": ["trust_accounts", "intake", "advanced_operations"],
        "features": ["تجربة المنظومة مجاناً"],
    },
    "lifetime": {
        "id": "lifetime",
        "name_ar": "الترخيص الشامل الدائم",
        "name_en": "Lifetime Unlimited",
        "badge": "غير محدود",
        "color": "#d97706",
        "price_monthly_usd": 0.0,
        "price_yearly_usd": 0.0,
        "max_users": 999,
        "max_active_cases": 99999,
        "storage_gb": 1000,
        "disabled_modules": [],
        "features": ["ترخيص دائم غير محدود لكافة الميزات"],
    },
}

# أسعار الصرف الافتراضية
DEFAULT_EXCHANGE_RATES = {
    "USD": 1.0,
    "YER": 535.0,     # 1 USD = 535 YER
    "SAR": 3.75,      # 1 USD = 3.75 SAR
    "YER_SAR": 141.0, # 1 SAR = 141 YER
}

EXCHANGE_RATES_KEY = "exchange_rates"


def get_exchange_rates(db: Optional[Session] = None) -> Dict[str, float]:
    """Retrieve exchange rates from database settings or return defaults."""
    if not db:
        return dict(DEFAULT_EXCHANGE_RATES)
    try:
        setting = db.query(AppSettings).filter(AppSettings.setting_key == EXCHANGE_RATES_KEY).first()
        if setting and setting.setting_value:
            rates = json.loads(setting.setting_value)
            merged = dict(DEFAULT_EXCHANGE_RATES)
            for k, v in rates.items():
                try:
                    merged[k] = float(v)
                except (ValueError, TypeError):
                    pass
            return merged
    except Exception:
        pass
    return dict(DEFAULT_EXCHANGE_RATES)


def set_exchange_rates(db: Session, rates: Dict[str, float]) -> Dict[str, float]:
    """Save exchange rates to database settings."""
    sanitized = {}
    for k in ["USD", "YER", "SAR", "YER_SAR"]:
        if k in rates:
            try:
                sanitized[k] = float(rates[k])
            except (ValueError, TypeError):
                sanitized[k] = DEFAULT_EXCHANGE_RATES.get(k, 1.0)
        else:
            sanitized[k] = DEFAULT_EXCHANGE_RATES.get(k, 1.0)

    setting = db.query(AppSettings).filter(AppSettings.setting_key == EXCHANGE_RATES_KEY).first()
    if not setting:
        setting = AppSettings(setting_key=EXCHANGE_RATES_KEY, setting_value=json.dumps(sanitized))
        db.add(setting)
    else:
        setting.setting_value = json.dumps(sanitized)
    db.commit()
    return sanitized


def get_tier(tier_id: Optional[str]) -> Dict[str, Any]:
    """Retrieve tier definition by id with fallback to solo."""
    if not tier_id:
        return TIERS["solo"]
    norm = tier_id.strip().lower()
    if norm in ("yearly", "monthly"):
        return TIERS["pro"]
    return TIERS.get(norm, TIERS["solo"])


def get_disabled_modules_for_tier(tier_id: Optional[str]) -> List[str]:
    """Return the list of restricted module keys for a given tier."""
    tier = get_tier(tier_id)
    return list(tier.get("disabled_modules", []))


def calculate_price_in_currency(amount_usd: float, currency: str, rates: Optional[Dict[str, float]] = None) -> Decimal:
    """
    Convert USD amount into target currency (USD, YER, SAR) down to exact cent/unit.
    Uses strict decimal arithmetic to avoid floating point errors.
    """
    if rates is None:
        rates = DEFAULT_EXCHANGE_RATES

    curr = currency.upper().strip()
    rate = Decimal(str(rates.get(curr, 1.0)))
    usd_dec = Decimal(str(amount_usd))

    result = usd_dec * rate

    if curr == "YER":
        # Round to whole Yemeni Rial
        return result.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    else:
        # USD and SAR rounded to 2 decimal places (cents)
        return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ----------------------------------------------------------------------------
# نظام المقعد الإضافي الواحد (Single Extra Seat Add-on System)
# ----------------------------------------------------------------------------
# متاح حصراً للباقة المتوسطة (pro) والباقة الكبرى (enterprise)
# مقعد واحد إضافي كحد أقصى لكل مكتب (extra_seats <= 1)
EXTRA_SEAT_SETUP_FEE_USD: float = 100.00     # رسم تأسيسي يدفع لمرة واحدة عند الشراء
EXTRA_SEAT_MONTHLY_FEE_USD: float = 9.99    # رسم شهري متكرر يضاف إلى فاتورة التجديد الشهرية
MAX_EXTRA_SEATS_PER_OFFICE: int = 1         # مسموح بمقعد واحد إضافي فقط


def get_office_max_users(office: Any) -> int:
    """
    حساب سقف المستخدمين الأقصى المسموح به للمكتب.
    المعادلة: سقف الباقة الأساسي + المقعد الإضافي (بحد أقصى مقعد واحد للباقة المتوسطة أو الكبرى).
    - باقة المستقل: 1
    - الباقة المتوسطة: 5 (مدير + 4 أعضاء) أو 6 مع المقعد الإضافي
    - الباقة الكبرى: 7 (مدير + 6 أعضاء) أو 8 مع المقعد الإضافي
    """
    if not office:
        return 1
    plan_id = (getattr(office, "subscription_plan", None) or "trial").lower().strip()
    tier = get_tier(plan_id)
    base_users = tier.get("max_users", 1)

    if plan_id in ("pro", "enterprise", "monthly", "yearly"):
        extra = getattr(office, "extra_seats", 0) or 0
        extra_allowed = min(max(0, int(extra)), MAX_EXTRA_SEATS_PER_OFFICE)
        return base_users + extra_allowed

    return base_users


def can_office_buy_extra_seat(office: Any) -> bool:
    """
    التحقق من أهلية المكتب لشراء مقعد إضافي:
    1. يجب أن يكون على الباقة المتوسطة (pro) أو الكبرى (enterprise).
    2. لم يسبق له شراء المقعد الإضافي (extra_seats < 1).
    """
    if not office:
        return False
    plan_id = (getattr(office, "subscription_plan", None) or "trial").lower().strip()
    if plan_id not in ("pro", "enterprise", "monthly", "yearly"):
        return False
    current_extra = getattr(office, "extra_seats", 0) or 0
    return int(current_extra) < MAX_EXTRA_SEATS_PER_OFFICE

