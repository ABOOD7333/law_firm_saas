"""
Waziruk Unified Biller API Router
=================================
Centralized, provider-agnostic Payment Integration API for Banks & Digital Wallets.
Endpoints:
- POST /api/v1/biller/inquire
- GET  /api/v1/biller/inquire
- POST /api/v1/biller/pay
- POST /api/v1/biller/notify
- GET  /api/v1/biller/status/{reference}
- POST /api/v1/biller/refund
- GET  /developer/biller-api
"""

import json
import secrets
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Header, Query
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.orm import Session

from dependencies import get_db, templates
from database.biller_models import PaymentProviders, BillerInvoices, BillerTransactions
from core.payment_hub.adapters import get_adapter_for_provider
from core.payment_hub.engine import (
    inquire_subscriber,
    process_payment,
    log_biller_audit,
    seed_default_providers,
)

router = APIRouter(tags=["Waziruk Biller API"])


async def authenticate_provider(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
    x_waziruk_signature: Optional[str] = Header(None, alias="X-Waziruk-Signature"),
):
    """
    Authenticate incoming bank/wallet server using X-API-KEY & HMAC-SHA256 signature.
    """
    seed_default_providers(db)

    if not x_api_key:
        log_biller_audit(
            db, "AUTH_FAILED", details={"reason": "Missing X-API-KEY"},
            ip_address=request.client.host if request.client else None
        )
        raise HTTPException(
            status_code=401,
            detail={"status": "ERROR", "error_code": "MISSING_API_KEY", "message": "X-API-KEY header is required"}
        )

    provider = db.query(PaymentProviders).filter(PaymentProviders.api_key == x_api_key.strip()).first()
    if not provider:
        log_biller_audit(
            db, "AUTH_FAILED", details={"reason": "Invalid X-API-KEY"},
            ip_address=request.client.host if request.client else None
        )
        raise HTTPException(
            status_code=401,
            detail={"status": "ERROR", "error_code": "INVALID_API_KEY", "message": "Invalid API Key"}
        )

    if not provider.is_active:
        raise HTTPException(
            status_code=403,
            detail={"status": "ERROR", "error_code": "PROVIDER_DISABLED", "message": "Payment provider is currently disabled"}
        )

    # IP Allowlist check if configured
    client_ip = request.client.host if request.client else ""
    if provider.allowed_ips:
        allowed = [ip.strip() for ip in provider.allowed_ips.split(",") if ip.strip()]
        if allowed and client_ip not in allowed:
            log_biller_audit(
                db, "AUTH_FAILED", provider_code=provider.code,
                details={"reason": "IP_NOT_ALLOWED", "ip": client_ip}, ip_address=client_ip
            )
            raise HTTPException(
                status_code=403,
                detail={"status": "ERROR", "error_code": "IP_FORBIDDEN", "message": "IP address not whitelisted"}
            )

    adapter = get_adapter_for_provider(provider)

    # Verify HMAC signature on POST/PUT requests
    if request.method in ("POST", "PUT", "PATCH"):
        raw_body = await request.body()
        if not adapter.verify_signature(raw_body, x_waziruk_signature, provider.api_secret):
            log_biller_audit(
                db, "AUTH_FAILED", provider_code=provider.code,
                details={"reason": "INVALID_SIGNATURE"}, ip_address=client_ip
            )
            raise HTTPException(
                status_code=401,
                detail={"status": "ERROR", "error_code": "INVALID_SIGNATURE", "message": "HMAC-SHA256 signature verification failed"}
            )

    return provider, adapter


@router.post("/api/v1/biller/inquire")
async def biller_inquire_post(
    request: Request,
    db: Session = Depends(get_db),
    auth=Depends(authenticate_provider),
):
    """
    Unified Bill Inquiry Endpoint (POST).
    Bank sends subscriber's phone number; Waziruk returns active bills with multi-currency payable_options.
    """
    provider, adapter = auth
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    phone = adapter.parse_inquiry_request(payload)
    if not phone:
        return JSONResponse(
            {"status": "ERROR", "error_code": "MISSING_PHONE", "message_ar": "يرجى إدخال رقم هاتف المشترك", "message_en": "subscriber_phone is required"},
            status_code=400,
        )

    client_ip = request.client.host if request.client else None
    result = inquire_subscriber(db, phone, provider_code=provider.code, ip_address=client_ip)
    formatted = adapter.format_inquiry_response(result)
    status_code = 200 if result.get("status") == "SUCCESS" else 404
    return JSONResponse(formatted, status_code=status_code)


@router.get("/api/v1/biller/inquire")
async def biller_inquire_get(
    request: Request,
    subscriber_phone: str = Query(..., description="رقم هاتف صاحب المكتب المشترك"),
    db: Session = Depends(get_db),
    auth=Depends(authenticate_provider),
):
    """Unified Bill Inquiry Endpoint (GET)."""
    provider, adapter = auth
    client_ip = request.client.host if request.client else None
    result = inquire_subscriber(db, subscriber_phone, provider_code=provider.code, ip_address=client_ip)
    formatted = adapter.format_inquiry_response(result)
    status_code = 200 if result.get("status") == "SUCCESS" else 404
    return JSONResponse(formatted, status_code=status_code)


@router.post("/api/v1/biller/pay")
@router.post("/api/v1/biller/notify")
async def biller_pay(
    request: Request,
    db: Session = Depends(get_db),
    auth=Depends(authenticate_provider),
):
    """
    Unified Payment Execution & Webhook Notification Endpoint.
    Supports Idempotency-Key to prevent duplicate deductions/activations.
    """
    provider, adapter = auth
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"status": "ERROR", "error_code": "INVALID_JSON"}, status_code=400)

    parsed = adapter.parse_payment_request(payload)
    header_idem = request.headers.get("Idempotency-Key")
    idem_key = header_idem or parsed["idempotency_key"]

    if not parsed["invoice_no"]:
        return JSONResponse(
            {"status": "ERROR", "error_code": "MISSING_INVOICE_NO", "message_en": "invoice_no is required"},
            status_code=400,
        )

    client_ip = request.client.host if request.client else None
    result = process_payment(
        db=db,
        invoice_no=parsed["invoice_no"],
        amount_paid=parsed["amount_paid"],
        currency=parsed["currency"],
        bank_reference=parsed["bank_reference"],
        idempotency_key=idem_key,
        provider_code=provider.code,
        raw_request=payload,
        ip_address=client_ip,
    )
    formatted = adapter.format_payment_response(result)
    status_code = 200 if result.get("status") == "SUCCESS" else 400
    return JSONResponse(formatted, status_code=status_code)


@router.get("/api/v1/biller/status/{reference}")
async def biller_status(
    reference: str,
    db: Session = Depends(get_db),
    auth=Depends(authenticate_provider),
):
    """Check transaction status by Waziruk transaction_id or bank_reference."""
    provider, _ = auth
    txn = (
        db.query(BillerTransactions)
        .filter(
            (BillerTransactions.transaction_id == reference)
            | (BillerTransactions.bank_reference == reference)
            | (BillerTransactions.idempotency_key == reference)
        )
        .first()
    )
    if not txn:
        return JSONResponse(
            {"status": "NOT_FOUND", "error_code": "TXN_NOT_FOUND", "message_en": "Transaction not found"},
            status_code=404,
        )

    inv = db.query(BillerInvoices).filter(BillerInvoices.id == txn.biller_invoice_id).first()
    return JSONResponse({
        "status": "SUCCESS",
        "transaction": {
            "transaction_id": txn.transaction_id,
            "bank_reference": txn.bank_reference,
            "invoice_no": inv.invoice_no if inv else None,
            "provider_code": txn.provider_code,
            "amount_paid": txn.amount_paid,
            "currency": txn.currency,
            "usd_equivalent": txn.amount_usd_equivalent,
            "txn_status": txn.status,
            "created_at": txn.created_at,
        }
    })


@router.post("/api/v1/biller/refund")
async def biller_refund(
    request: Request,
    db: Session = Depends(get_db),
    auth=Depends(authenticate_provider),
):
    """Authorized Transaction Reversal / Refund endpoint."""
    provider, _ = auth
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"status": "ERROR", "error_code": "INVALID_JSON"}, status_code=400)

    ref = str(payload.get("transaction_id") or payload.get("bank_reference") or "").strip()
    reason = str(payload.get("reason") or "Bank reversal request").strip()
    if not ref:
        return JSONResponse({"status": "ERROR", "error_code": "MISSING_REFERENCE"}, status_code=400)

    txn = (
        db.query(BillerTransactions)
        .filter(
            (BillerTransactions.transaction_id == ref)
            | (BillerTransactions.bank_reference == ref)
        )
        .first()
    )
    if not txn or txn.provider_code != provider.code:
        return JSONResponse({"status": "ERROR", "error_code": "TXN_NOT_FOUND"}, status_code=404)

    if txn.status == "reversed":
        return JSONResponse({"status": "SUCCESS", "message": "Already reversed", "transaction_id": txn.transaction_id})

    txn.status = "reversed"
    txn.error_message = reason
    inv = db.query(BillerInvoices).filter(BillerInvoices.id == txn.biller_invoice_id).first()
    if inv and inv.status == "paid":
        inv.status = "pending"
        inv.paid_at = None

    db.commit()
    log_biller_audit(
        db, "REVERSAL", provider_code=provider.code,
        invoice_no=inv.invoice_no if inv else None,
        details={"transaction_id": txn.transaction_id, "reason": reason},
        ip_address=request.client.host if request.client else None,
    )
    return JSONResponse({
        "status": "SUCCESS",
        "transaction_id": txn.transaction_id,
        "txn_status": "reversed",
        "message_en": "Transaction reversed and invoice reverted to pending",
    })


@router.get("/developer/biller-api", response_class=HTMLResponse)
async def biller_api_docs(request: Request, db: Session = Depends(get_db)):
    """Official Waziruk Bank & Digital Wallet Integration Specification Page."""
    from core.subscription_tiers import get_exchange_rates
    rates = get_exchange_rates(db)
    return templates.TemplateResponse(
        "biller_docs.html",
        {
            "request": request,
            "rates": rates,
            "base_url": str(request.base_url).rstrip("/"),
        },
    )
