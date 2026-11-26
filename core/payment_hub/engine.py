"""
Waziruk Central Billing & Collection Engine
===========================================
Single source of truth for:
- Subscriber lookup by phone number
- Auto-generating renewal bills 3 days prior to expiration
- On-demand extra seat invoices ($100 setup, 19% renewal)
- Multi-currency calculation (USD, YER_SOUTH القعيطي, YER_NORTH القديم, SAR)
- Idempotent payment execution & instant account/subscription activation
- Immutable audit trail
"""

import json
import re
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.models import LawOffices, AccessProfiles
from database.biller_models import (
    PaymentProviders,
    BillerInvoices,
    BillerTransactions,
    BillerAuditLogs,
)
from core.subscription_tiers import (
    get_tier,
    get_disabled_modules_for_tier,
    get_exchange_rates,
    get_payable_options,
    calculate_price_in_currency,
    EXTRA_SEAT_SETUP_FEE_USD,
    EXTRA_SEAT_RENEWAL_FEE_USD,
)


def normalize_phone(phone: str) -> str:
    """Normalize Yemeni/international phone numbers for reliable subscriber matching."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if digits.startswith("00967"):
        digits = digits[5:]
    elif digits.startswith("967") and len(digits) >= 12:
        digits = digits[3:]
    elif digits.startswith("0") and len(digits) == 10:
        digits = digits[1:]
    return digits


def find_office_by_phone(db: Session, raw_phone: str) -> Tuple[Optional[LawOffices], Optional[AccessProfiles]]:
    """
    Find a law office and its owner by the subscriber's registered phone number.
    """
    norm = normalize_phone(raw_phone)
    if not norm or len(norm) < 7:
        return None, None

    # Exact match or suffix match on active users
    candidates = (
        db.query(AccessProfiles)
        .filter(AccessProfiles.is_deleted == 0)
        .filter(AccessProfiles.phone.isnot(None))
        .all()
    )
    matched_user = None
    for u in candidates:
        if normalize_phone(u.phone) == norm:
            matched_user = u
            break

    if not matched_user:
        return None, None

    office = None
    if matched_user.office_id:
        office = (
            db.query(LawOffices)
            .filter(LawOffices.id == matched_user.office_id, LawOffices.is_deleted == 0)
            .first()
        )
    if not office:
        office = (
            db.query(LawOffices)
            .filter(LawOffices.owner_user_id == matched_user.id, LawOffices.is_deleted == 0)
            .first()
        )

    if not office:
        return None, matched_user

    # Ensure we return the owner profile if a staff member's phone wasn't intended,
    # or return the matched user as subscriber contact
    owner = matched_user
    if office.owner_user_id and office.owner_user_id != matched_user.id:
        owner_row = db.query(AccessProfiles).filter(AccessProfiles.id == office.owner_user_id).first()
        if owner_row:
            owner = owner_row

    return office, owner


def log_biller_audit(
    db: Session,
    event_type: str,
    provider_code: Optional[str] = None,
    subscriber_phone: Optional[str] = None,
    invoice_no: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
):
    """Write an immutable audit entry."""
    entry = BillerAuditLogs(
        event_type=event_type,
        provider_code=provider_code,
        subscriber_phone=subscriber_phone,
        invoice_no=invoice_no,
        details_json=json.dumps(details or {}, ensure_ascii=False),
        ip_address=ip_address,
        created_at=datetime.utcnow().isoformat(timespec="seconds"),
    )
    db.add(entry)
    db.commit()


def generate_invoice_no(db: Session) -> str:
    """Generate unique human-friendly invoice number e.g. WZ-202611-0001."""
    prefix = f"WZ-{datetime.utcnow().strftime('%Y%m')}"
    count = db.query(BillerInvoices).filter(BillerInvoices.invoice_no.like(f"{prefix}-%")).count()
    seq = count + 1
    while True:
        candidate = f"{prefix}-{seq:04d}"
        exists = db.query(BillerInvoices).filter(BillerInvoices.invoice_no == candidate).first()
        if not exists:
            return candidate
        seq += 1


def _parse_iso_dt(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    clean = str(dt_str).strip().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(clean[:26], fmt)
        except ValueError:
            continue
    return None


def ensure_office_renewal_bill(
    db: Session,
    office: LawOffices,
    owner: AccessProfiles,
    force: bool = False,
) -> Optional[BillerInvoices]:
    """
    Auto-generate a subscription renewal bill if the office subscription
    expires within 3 days (or has already expired), and no pending renewal bill exists.
    Never generates bills for 'lifetime' accounts.
    """
    plan_id = (office.subscription_plan or "trial").lower().strip()
    if plan_id == "lifetime":
        return None

    # Check if an unpaid renewal bill already exists
    existing = (
        db.query(BillerInvoices)
        .filter(
            BillerInvoices.office_id == office.id,
            BillerInvoices.invoice_type == "subscription_renewal",
            BillerInvoices.status == "pending",
        )
        .order_by(desc(BillerInvoices.id))
        .first()
    )
    if existing:
        return existing

    now = datetime.utcnow()
    end_dt = _parse_iso_dt(office.subscription_end)

    # Generate bill if <= 3 days remaining, or already expired, or forced
    should_generate = force
    if end_dt is None:
        should_generate = True
    elif (end_dt - now) <= timedelta(days=3):
        should_generate = True

    if not should_generate:
        return None

    # For trial accounts, default renewal target is 'pro' unless changed
    target_plan = "pro" if plan_id == "trial" else plan_id
    if target_plan not in ("solo", "pro", "enterprise"):
        target_plan = "pro"

    tier = get_tier(target_plan)
    base_usd = float(tier["price_monthly_usd"])
    extra_seats = int(getattr(office, "extra_seats", 0) or 0)
    extra_fee = EXTRA_SEAT_RENEWAL_FEE_USD if (extra_seats >= 1 and target_plan in ("pro", "enterprise")) else 0.0
    total_usd = round(base_usd + extra_fee, 2)

    due_dt = end_dt if (end_dt and end_dt > now) else now
    title = f"تجديد اشتراك باقة {tier['name_ar']}"
    if extra_fee > 0:
        title += " + رسوم تجديد المقعد الإضافي (19%)"

    inv = BillerInvoices(
        invoice_no=generate_invoice_no(db),
        office_id=office.id,
        subscriber_phone=normalize_phone(owner.phone),
        invoice_type="subscription_renewal",
        plan_id=target_plan,
        billing_cycle="monthly",
        title=title,
        amount_usd=base_usd,
        extra_seat_renewal_usd=extra_fee,
        total_usd=total_usd,
        status="pending",
        due_date=due_dt.strftime("%Y-%m-%d"),
        created_at=now.isoformat(timespec="seconds"),
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def create_extra_seat_invoice(
    db: Session,
    office: LawOffices,
    owner: AccessProfiles,
    target_user_id: int,
    target_user_name: str,
) -> BillerInvoices:
    """
    Create an immediate pending invoice ($100) when an office adds an extra user
    beyond its tier's base limit. Activating this invoice immediately activates the user.
    """
    now = datetime.utcnow()
    inv = BillerInvoices(
        invoice_no=generate_invoice_no(db),
        office_id=office.id,
        subscriber_phone=normalize_phone(owner.phone),
        invoice_type="extra_seat",
        plan_id="extra_seat",
        billing_cycle="one_time",
        title=f"تفعيل مستخدم إضافي ({target_user_name})",
        amount_usd=EXTRA_SEAT_SETUP_FEE_USD,
        extra_seat_renewal_usd=0.0,
        total_usd=EXTRA_SEAT_SETUP_FEE_USD,
        status="pending",
        due_date=now.strftime("%Y-%m-%d"),
        target_user_id=target_user_id,
        metadata_json=json.dumps({"target_user_name": target_user_name}, ensure_ascii=False),
        created_at=now.isoformat(timespec="seconds"),
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def inquire_subscriber(
    db: Session,
    subscriber_phone: str,
    provider_code: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Core inquiry handler: looks up office by owner's phone, ensures 3-day pre-expiry bills
    are generated, and returns all pending bills with Method 1 Multi-Currency payable_options.
    """
    office, owner = find_office_by_phone(db, subscriber_phone)
    if not office or not owner:
        log_biller_audit(
            db, "INQUIRY_NOT_FOUND", provider_code=provider_code,
            subscriber_phone=subscriber_phone, ip_address=ip_address
        )
        return {
            "status": "NOT_FOUND",
            "error_code": "SUBSCRIBER_NOT_FOUND",
            "message_ar": "لم يتم العثور على مكتب مشترك مسجل بهذا الرقم",
            "message_en": "No subscriber office found with this phone number",
            "invoices": [],
        }

    # Ensure 3-day pre-expiration renewal bill exists if due
    ensure_office_renewal_bill(db, office, owner)

    pending_invoices = (
        db.query(BillerInvoices)
        .filter(BillerInvoices.office_id == office.id, BillerInvoices.status == "pending")
        .order_by(BillerInvoices.id.asc())
        .all()
    )

    tier_info = get_tier(office.subscription_plan)
    invoices_out = []
    for inv in pending_invoices:
        payable_options = get_payable_options(inv.total_usd, db)
        invoices_out.append({
            "invoice_no": inv.invoice_no,
            "invoice_type": inv.invoice_type,
            "plan_id": inv.plan_id,
            "title": inv.title,
            "base_amount_usd": round(float(inv.total_usd), 2),
            "base_currency": "USD",
            "payable_options": payable_options,
            "due_date": inv.due_date,
            "status": "UNPAID",
        })

    log_biller_audit(
        db, "INQUIRY", provider_code=provider_code,
        subscriber_phone=normalize_phone(owner.phone),
        details={"office_id": office.id, "pending_count": len(invoices_out)},
        ip_address=ip_address,
    )

    return {
        "status": "SUCCESS",
        "subscriber": {
            "office_id": office.id,
            "office_name": office.name,
            "owner_name": owner.name,
            "phone": normalize_phone(owner.phone),
            "current_plan": tier_info.get("name_ar", office.subscription_plan),
            "subscription_end": office.subscription_end,
        },
        "invoices": invoices_out,
    }


def process_payment(
    db: Session,
    invoice_no: str,
    amount_paid: float,
    currency: str,
    bank_reference: str,
    idempotency_key: str,
    provider_code: str,
    raw_request: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Core payment collection & confirmation handler.
    - Enforces idempotency via idempotency_key
    - Validates invoice status and exact amount against Waziruk exchange rates
    - Atomically activates subscription renewal or pending extra user
    """
    curr = (currency or "USD").upper().strip()
    if curr not in ("USD", "YER_SOUTH", "YER_NORTH", "YER", "SAR"):
        return {
            "status": "FAILED",
            "error_code": "INVALID_CURRENCY",
            "message_ar": f"العملة '{curr}' غير مدعومة",
            "message_en": f"Unsupported currency: {curr}",
        }

    # 1. Idempotency check
    if idempotency_key:
        existing_txn = (
            db.query(BillerTransactions)
            .filter(BillerTransactions.idempotency_key == idempotency_key)
            .first()
        )
        if existing_txn:
            if existing_txn.raw_response_json:
                cached = json.loads(existing_txn.raw_response_json)
                cached["idempotent_replay"] = True
                return cached

    # 2. Fetch invoice
    inv = db.query(BillerInvoices).filter(BillerInvoices.invoice_no == invoice_no).first()
    if not inv:
        return {
            "status": "FAILED",
            "error_code": "INVOICE_NOT_FOUND",
            "message_ar": "رقم الفاتورة غير موجود",
            "message_en": "Invoice not found",
        }

    if inv.status == "paid":
        return {
            "status": "FAILED",
            "error_code": "ALREADY_PAID",
            "message_ar": "هذه الفاتورة مسددة مسبقاً",
            "message_en": "Invoice is already paid",
        }

    if inv.status != "pending":
        return {
            "status": "FAILED",
            "error_code": "INVOICE_NOT_PAYABLE",
            "message_ar": f"حالة الفاتورة ({inv.status}) لا تقبل السداد",
            "message_en": f"Invoice status ({inv.status}) is not payable",
        }

    # 3. Validate payment amount using Waziruk exchange rates
    rates = get_exchange_rates(db)
    expected_amount = float(calculate_price_in_currency(inv.total_usd, curr, rates))
    rate_applied = float(rates.get(curr, 1.0))

    # Tolerance: 1 YER for Yemeni Rials or 0.05 for USD/SAR
    tolerance = 2.0 if curr in ("YER", "YER_NORTH", "YER_SOUTH") else 0.05
    if float(amount_paid) + tolerance < expected_amount:
        failed_txn = BillerTransactions(
            transaction_id=f"TXN-{secrets.token_hex(6).upper()}",
            biller_invoice_id=inv.id,
            office_id=inv.office_id,
            provider_code=provider_code,
            bank_reference=bank_reference or "N/A",
            idempotency_key=idempotency_key or f"FAIL-{secrets.token_hex(8)}",
            amount_paid=float(amount_paid),
            currency=curr,
            amount_usd_equivalent=round(float(amount_paid) / rate_applied, 2) if rate_applied else 0.0,
            status="failed",
            error_code="INSUFFICIENT_AMOUNT",
            error_message=f"Expected {expected_amount} {curr}, got {amount_paid} {curr}",
            raw_request_json=json.dumps(raw_request or {}, ensure_ascii=False),
            ip_address=ip_address,
            created_at=datetime.utcnow().isoformat(timespec="seconds"),
        )
        db.add(failed_txn)
        db.commit()
        log_biller_audit(
            db, "PAYMENT_FAILED", provider_code=provider_code,
            subscriber_phone=inv.subscriber_phone, invoice_no=inv.invoice_no,
            details={"reason": "INSUFFICIENT_AMOUNT", "expected": expected_amount, "received": amount_paid, "currency": curr},
            ip_address=ip_address,
        )
        return {
            "status": "FAILED",
            "error_code": "INSUFFICIENT_AMOUNT",
            "message_ar": f"المبلغ المدفوع غير كافٍ. المطلوب: {expected_amount} {curr}",
            "message_en": f"Insufficient amount. Required: {expected_amount} {curr}",
            "expected_amount": expected_amount,
            "currency": curr,
        }

    # 4. Execute activation atomically
    now = datetime.utcnow()
    now_iso = now.isoformat(timespec="seconds")
    office = db.query(LawOffices).filter(LawOffices.id == inv.office_id).first()
    if not office:
        return {"status": "FAILED", "error_code": "OFFICE_NOT_FOUND", "message_en": "Office not found"}

    activation_note = ""
    if inv.invoice_type == "subscription_renewal":
        days = 365 if inv.billing_cycle == "yearly" else 30
        current_end = _parse_iso_dt(office.subscription_end)
        base_dt = current_end if (current_end and current_end > now) else now
        new_end = base_dt + timedelta(days=days)

        office.subscription_plan = inv.plan_id
        office.subscription_end = new_end.isoformat(timespec="seconds")
        office.status_key = "active"
        office.is_active = 1
        office.disabled_modules_json = json.dumps(get_disabled_modules_for_tier(inv.plan_id))
        activation_note = f"تم تجديد باقة {get_tier(inv.plan_id)['name_ar']} حتى {new_end.strftime('%Y-%m-%d')}"

    elif inv.invoice_type == "extra_seat":
        office.extra_seats = 1
        if inv.target_user_id:
            target_u = db.query(AccessProfiles).filter(AccessProfiles.id == inv.target_user_id).first()
            if target_u:
                target_u.state = "active"
                target_u.is_active = 1
                activation_note = f"تم تفعيل حساب المستخدم الإضافي ({target_u.name}) بنجاح"
        if not activation_note:
            activation_note = "تم تفعيل المقعد الإضافي للمكتب بنجاح"

    # 5. Mark invoice paid
    inv.status = "paid"
    inv.paid_at = now_iso
    inv.paid_currency = curr
    inv.paid_amount = float(amount_paid)
    inv.exchange_rate_applied = rate_applied
    inv.provider_code = provider_code
    inv.bank_txn_ref = bank_reference

    txn_id = f"WZK-{now.strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"
    response_payload = {
        "status": "SUCCESS",
        "transaction_id": txn_id,
        "invoice_no": inv.invoice_no,
        "bank_reference": bank_reference,
        "paid_amount": float(amount_paid),
        "currency": curr,
        "usd_equivalent": round(float(inv.total_usd), 2),
        "paid_at": now_iso,
        "activation_message_ar": activation_note,
        "message_en": "Payment confirmed and service activated",
    }

    txn = BillerTransactions(
        transaction_id=txn_id,
        biller_invoice_id=inv.id,
        office_id=office.id,
        provider_code=provider_code,
        bank_reference=bank_reference or txn_id,
        idempotency_key=idempotency_key or txn_id,
        amount_paid=float(amount_paid),
        currency=curr,
        amount_usd_equivalent=float(inv.total_usd),
        status="success",
        raw_request_json=json.dumps(raw_request or {}, ensure_ascii=False),
        raw_response_json=json.dumps(response_payload, ensure_ascii=False),
        ip_address=ip_address,
        created_at=now_iso,
    )
    db.add(txn)
    db.commit()

    log_biller_audit(
        db, "PAYMENT_SUCCESS", provider_code=provider_code,
        subscriber_phone=inv.subscriber_phone, invoice_no=inv.invoice_no,
        details={"transaction_id": txn_id, "amount": amount_paid, "currency": curr, "activation": activation_note},
        ip_address=ip_address,
    )
    return response_payload


def seed_default_providers(db: Session):
    """Ensure default sandbox & major Yemeni wallet templates exist in PaymentProviders."""
    defaults = [
        {
            "code": "sandbox",
            "name_ar": "محاكي الاختبار والتجارب (Sandbox)",
            "name_en": "Waziruk Sandbox Simulator",
            "adapter_type": "sandbox",
            "is_active": 1,
            "is_sandbox": 1,
            "default_currency": "AUTO",
            "notes": "بيئة اختبار تفاعلية لعرض ومضاهاة عمليات التحصيل للبنوك والمحافظ.",
        },
        {
            "code": "kuraimi",
            "name_ar": "حاسب - بنك الكريمي الإسلامي",
            "name_en": "Al-Kuraimi Hasib",
            "adapter_type": "kuraimi",
            "is_active": 0,
            "is_sandbox": 0,
            "default_currency": "AUTO",
            "notes": "بانتظار استلام مفاتيح الربط الرسمية من بنك الكريمي وتفعيلها.",
        },
        {
            "code": "jeeb",
            "name_ar": "محفظة جيب (Jeeb Wallet)",
            "name_en": "Jeeb Digital Wallet",
            "adapter_type": "jeeb",
            "is_active": 0,
            "is_sandbox": 0,
            "default_currency": "AUTO",
            "notes": "جاهز للربط عبر واجهة التحصيل الموحدة.",
        },
        {
            "code": "saba_cash",
            "name_ar": "محفظة سبأ كاش (SabaCash)",
            "name_en": "SabaCash Wallet",
            "adapter_type": "saba_cash",
            "is_active": 0,
            "is_sandbox": 0,
            "default_currency": "AUTO",
            "notes": "جاهز للربط عبر واجهة التحصيل الموحدة.",
        },
        {
            "code": "one_cash",
            "name_ar": "محفظة ون كاش (ONE Cash)",
            "name_en": "ONE Cash Wallet",
            "adapter_type": "one_cash",
            "is_active": 0,
            "is_sandbox": 0,
            "default_currency": "AUTO",
            "notes": "جاهز للربط عبر واجهة التحصيل الموحدة.",
        },
    ]

    for item in defaults:
        exists = db.query(PaymentProviders).filter(PaymentProviders.code == item["code"]).first()
        if not exists:
            prov = PaymentProviders(
                code=item["code"],
                name_ar=item["name_ar"],
                name_en=item["name_en"],
                adapter_type=item["adapter_type"],
                is_active=item["is_active"],
                is_sandbox=item["is_sandbox"],
                api_key=f"wzk_{item['code']}_{secrets.token_hex(12)}",
                api_secret=f"sec_{secrets.token_hex(24)}",
                default_currency=item["default_currency"],
                notes=item["notes"],
            )
            db.add(prov)
    db.commit()
