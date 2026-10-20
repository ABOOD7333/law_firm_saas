from datetime import datetime
from typing import Optional
import json

from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from core.error_handler import safe_error_html
from database.database import get_db
from database.models import (
    AccessProfiles, LawOffices, LawClients, LawCases,
    LawTrustAccounts, LawTrustTransactions, LawTransactions,
    LawAuditLog
)
from dependencies import get_current_user, templates, check_user_permission

router = APIRouter(tags=["Client Trust Accounts (حسابات أمانات الموكلين)"])


def log_trust_audit(db: Session, office_id: int, user: AccessProfiles, action: str, details: str = ""):
    try:
        audit = LawAuditLog(
            office_id=office_id,
            user_id=user.id,
            action=action,
            entity_type="LawTrustAccounts",
            entity_id=0,
            details=details
        )
        db.add(audit)
        db.commit()
    except Exception:
        db.rollback()


@router.get("/trust-accounts", response_class=HTMLResponse)
async def list_trust_accounts(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user),
    client_filter: Optional[int] = None,
    status_filter: Optional[str] = None,
    q: Optional[str] = None
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'accounting', 'view'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بعرض حسابات الأمانات")

    office_id = user.office_id
    query = db.query(LawTrustAccounts).filter(
        LawTrustAccounts.office_id == office_id,
        LawTrustAccounts.is_deleted == 0
    )

    if client_filter:
        query = query.filter(LawTrustAccounts.client_id == client_filter)
    if status_filter and status_filter.strip():
        query = query.filter(LawTrustAccounts.status_key == status_filter.strip())
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                LawTrustAccounts.title.ilike(term),
                LawTrustAccounts.account_number.ilike(term),
                LawTrustAccounts.bank_name.ilike(term),
                LawTrustAccounts.iban.ilike(term)
            )
        )

    accounts = query.order_by(LawTrustAccounts.id.desc()).all()

    # Calculate Office-Wide Trust KPI Metrics
    all_accounts = db.query(LawTrustAccounts).filter(
        LawTrustAccounts.office_id == office_id,
        LawTrustAccounts.is_deleted == 0
    ).all()

    total_balance = sum(acc.current_balance for acc in all_accounts)
    total_deposited = sum(acc.total_deposited for acc in all_accounts)
    total_disbursed = sum(acc.total_disbursed for acc in all_accounts)
    active_count = len([acc for acc in all_accounts if acc.status_key == 'active'])

    # Total fee transfers across all trust accounts
    fee_transfers_sum = db.query(func.sum(LawTrustTransactions.amount)).filter(
        LawTrustTransactions.office_id == office_id,
        LawTrustTransactions.transaction_type == 'fee_transfer'
    ).scalar() or 0.0

    stats = {
        "total_balance": total_balance,
        "total_deposited": total_deposited,
        "total_disbursed": total_disbursed,
        "total_fee_transfers": fee_transfers_sum,
        "active_accounts": active_count,
        "total_accounts": len(all_accounts)
    }

    # Clients & Cases for Modals & Filter
    clients = db.query(LawClients).filter(
        LawClients.office_id == office_id,
        LawClients.is_deleted == 0
    ).order_by(LawClients.name.asc()).all()

    cases = db.query(LawCases).filter(
        LawCases.office_id == office_id,
        LawCases.is_deleted == 0
    ).order_by(LawCases.id.desc()).all()

    return templates.TemplateResponse(
        request=request,
        name="trust_accounts.html",
        context={
            "user": user,
            "active_page": "trust_accounts",
            "accounts": accounts,
            "stats": stats,
            "clients": clients,
            "cases": cases,
            "client_filter": client_filter,
            "status_filter": status_filter,
            "q": q
        }
    )


@router.post("/trust-accounts/add")
async def add_trust_account(
    request: Request,
    title: str = Form(...),
    client_id: int = Form(...),
    case_id: Optional[int] = Form(None),
    account_number: Optional[str] = Form(None),
    bank_name: Optional[str] = Form(None),
    iban: Optional[str] = Form(None),
    currency: str = Form("SAR"),
    initial_deposit: Optional[float] = Form(0.0),
    deposit_method: Optional[str] = Form("bank_transfer"),
    deposit_ref: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'accounting', 'add'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بفتح حساب أمانة")

    office_id = user.office_id

    # Auto-generate account number if not provided
    if not account_number or not account_number.strip():
        now_year = datetime.now().year
        cnt = db.query(LawTrustAccounts).filter(LawTrustAccounts.office_id == office_id).count()
        account_number = f"TRU-{now_year}-{cnt + 1:04d}"
    else:
        account_number = account_number.strip()
        exists = db.query(LawTrustAccounts).filter(
            LawTrustAccounts.account_number == account_number,
            LawTrustAccounts.office_id == office_id
        ).first()
        if exists:
            account_number = f"{account_number}-{int(datetime.now().timestamp()) % 1000}"

    new_account = LawTrustAccounts(
        office_id=office_id,
        client_id=client_id,
        case_id=case_id if case_id and case_id > 0 else None,
        account_number=account_number,
        title=title.strip(),
        bank_name=bank_name.strip() if bank_name else None,
        iban=iban.strip() if iban else None,
        currency=currency,
        current_balance=0.0,
        total_deposited=0.0,
        total_disbursed=0.0,
        status_key="active",
        notes=notes.strip() if notes else None,
        created_by_user_id=user.id
    )
    db.add(new_account)
    db.commit()
    db.refresh(new_account)

    # Initial Deposit if provided
    if initial_deposit and initial_deposit > 0:
        now_str = datetime.now().strftime("%Y-%m-%d")
        vch_cnt = db.query(LawTrustTransactions).filter(LawTrustTransactions.office_id == office_id).count() + 1
        voucher_no = f"VCH-DEP-{now_year}-{vch_cnt:04d}"

        tx = LawTrustTransactions(
            trust_account_id=new_account.id,
            office_id=office_id,
            voucher_number=voucher_no,
            transaction_type="deposit",
            amount=initial_deposit,
            balance_after=initial_deposit,
            transaction_date=now_str,
            payment_method=deposit_method or "bank_transfer",
            reference_number=deposit_ref.strip() if deposit_ref else None,
            payee_or_payer="المودع الأساسي",
            description="إيداع الرصيد الافتتاحي في حساب الأمانة",
            created_by_user_id=user.id
        )
        db.add(tx)
        new_account.current_balance = initial_deposit
        new_account.total_deposited = initial_deposit
        db.commit()

    log_trust_audit(db, office_id, user, "فتح حساب أمانة جديد", f"[{new_account.account_number}] {new_account.title}")
    return RedirectResponse(url=f"/trust-accounts/{new_account.id}?msg=added", status_code=303)


@router.get("/trust-accounts/{account_id}", response_class=HTMLResponse)
async def trust_account_details(
    account_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'accounting', 'view'):
        raise HTTPException(status_code=403, detail="غير مصرح")

    account = db.query(LawTrustAccounts).filter(
        LawTrustAccounts.id == account_id,
        LawTrustAccounts.office_id == user.office_id,
        LawTrustAccounts.is_deleted == 0
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="حساب الأمانة غير موجود")

    transactions = db.query(LawTrustTransactions).filter(
        LawTrustTransactions.trust_account_id == account.id,
        LawTrustTransactions.office_id == user.office_id
    ).order_by(LawTrustTransactions.id.desc()).all()

    client = db.query(LawClients).filter(LawClients.id == account.client_id).first()
    law_case = db.query(LawCases).filter(LawCases.id == account.case_id).first() if account.case_id else None

    return templates.TemplateResponse(
        request=request,
        name="trust_account_details.html",
        context={
            "user": user,
            "active_page": "trust_accounts",
            "account": account,
            "transactions": transactions,
            "client": client,
            "law_case": law_case
        }
    )


@router.post("/trust-accounts/{account_id}/transactions/add")
async def add_trust_transaction(
    account_id: int,
    transaction_type: str = Form(...), # 'deposit', 'disbursement', 'fee_transfer'
    amount: float = Form(...),
    transaction_date: str = Form(...),
    payment_method: str = Form("bank_transfer"),
    reference_number: Optional[str] = Form(None),
    payee_or_payer: Optional[str] = Form(None),
    description: str = Form(...),
    transfer_to_firm_revenue: bool = Form(False),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'accounting', 'edit'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بإجراء حركات على حساب الأمانة")

    account = db.query(LawTrustAccounts).filter(
        LawTrustAccounts.id == account_id,
        LawTrustAccounts.office_id == user.office_id,
        LawTrustAccounts.is_deleted == 0
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="حساب الأمانة غير موجود")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="يجب أن يكون المبلغ أكبر من صفر")

    # Strict Bar Regulation: Trust Account can NEVER have a negative balance (overdraft violation)
    if transaction_type in ['disbursement', 'fee_transfer'] and amount > account.current_balance:
        return RedirectResponse(
            url=f"/trust-accounts/{account_id}?err=insufficient_trust_funds",
            status_code=303
        )

    now_year = datetime.now().year
    vch_count = db.query(LawTrustTransactions).filter(LawTrustTransactions.office_id == user.office_id).count() + 1
    type_prefix = "DEP" if transaction_type == "deposit" else ("DISB" if transaction_type == "disbursement" else "FEE")
    voucher_no = f"VCH-{type_prefix}-{now_year}-{vch_count:04d}"

    # Calculate balance
    if transaction_type == "deposit":
        new_balance = account.current_balance + amount
        account.total_deposited += amount
    else: # disbursement or fee_transfer
        new_balance = account.current_balance - amount
        account.total_disbursed += amount

    account.current_balance = new_balance
    account.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    tx = LawTrustTransactions(
        trust_account_id=account.id,
        office_id=user.office_id,
        voucher_number=voucher_no,
        transaction_type=transaction_type,
        amount=amount,
        balance_after=new_balance,
        transaction_date=transaction_date,
        payment_method=payment_method,
        reference_number=reference_number.strip() if reference_number else None,
        payee_or_payer=payee_or_payer.strip() if payee_or_payer else None,
        description=description.strip(),
        created_by_user_id=user.id
    )
    db.add(tx)

    # If fee_transfer and user opted to link to firm transactions:
    if transaction_type == "fee_transfer" and account.case_id:
        firm_tx = LawTransactions(
            case_id=account.case_id,
            office_id=user.office_id,
            title=f"أتعاب محولة من حساب الأمانات [{voucher_no}]",
            amount=amount,
            transaction_at=transaction_date,
            status_key="completed",
            notes=f"سند أمانة: {voucher_no} - {description}",
            currency=account.currency,
            exchange_rate=1.0,
            payment_method=payment_method,
            reference_number=voucher_no,
            client_id=account.client_id
        )
        db.add(firm_tx)

    db.commit()
    log_trust_audit(db, user.office_id, user, f"حركة أمانة: {transaction_type}", f"[{voucher_no}] بمبلغ {amount} {account.currency}")
    return RedirectResponse(url=f"/trust-accounts/{account.id}?msg=tx_added", status_code=303)


@router.get("/trust-accounts/{account_id}/statement", response_class=HTMLResponse)
async def print_trust_statement(
    account_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)

    account = db.query(LawTrustAccounts).filter(
        LawTrustAccounts.id == account_id,
        LawTrustAccounts.office_id == user.office_id,
        LawTrustAccounts.is_deleted == 0
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="الحساب غير موجود")

    office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first()
    client = db.query(LawClients).filter(LawClients.id == account.client_id).first()
    law_case = db.query(LawCases).filter(LawCases.id == account.case_id).first() if account.case_id else None

    transactions = db.query(LawTrustTransactions).filter(
        LawTrustTransactions.trust_account_id == account.id,
        LawTrustTransactions.office_id == user.office_id
    ).order_by(LawTrustTransactions.id.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="trust_statement_print.html",
        context={
            "account": account,
            "office": office,
            "client": client,
            "law_case": law_case,
            "transactions": transactions,
            "user": user,
            "print_date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    )


@router.get("/trust-accounts/transactions/{tx_id}/receipt", response_class=HTMLResponse)
async def print_trust_receipt(
    tx_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)

    tx = db.query(LawTrustTransactions).filter(
        LawTrustTransactions.id == tx_id,
        LawTrustTransactions.office_id == user.office_id
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="السند غير موجود")

    account = tx.trust_account
    office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first()
    client = account.client

    return templates.TemplateResponse(
        request=request,
        name="trust_receipt_print.html",
        context={
            "tx": tx,
            "account": account,
            "office": office,
            "client": client,
            "user": user,
            "print_date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    )
