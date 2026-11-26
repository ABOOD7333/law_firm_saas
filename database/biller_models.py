"""
Centralized Electronic Billing & Payment Hub Models
====================================================
Database models for Waziruk Biller Engine:
- PaymentProviders: Bank & digital wallet providers + API credentials
- BillerInvoices: Official system-of-record bills (subscriptions, renewals, extra seats)
- BillerTransactions: Idempotent transaction logs for all payment attempts
- BillerAuditLogs: Immutable financial & security audit trail
"""

from typing import Optional
from sqlalchemy import Integer, Text, ForeignKey, REAL, CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from database.models import Base


class PaymentProviders(Base):
    __tablename__ = 'payment_providers'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    name_ar: Mapped[str] = mapped_column(Text, nullable=False)
    name_en: Mapped[str] = mapped_column(Text, nullable=False)
    adapter_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'generic'"))
    is_active: Mapped[int] = mapped_column(Integer, CheckConstraint('is_active IN (0, 1)'), nullable=False, server_default=text('1'))
    is_sandbox: Mapped[int] = mapped_column(Integer, CheckConstraint('is_sandbox IN (0, 1)'), nullable=False, server_default=text('0'))
    api_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    api_secret: Mapped[str] = mapped_column(Text, nullable=False)
    default_currency: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'AUTO'"))
    webhook_url: Mapped[Optional[str]] = mapped_column(Text)
    allowed_ips: Mapped[Optional[str]] = mapped_column(Text)
    config_json: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class BillerInvoices(Base):
    __tablename__ = 'biller_invoices'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_no: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id', ondelete='CASCADE'), nullable=False, index=True)
    subscriber_phone: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    invoice_type: Mapped[str] = mapped_column(Text, nullable=False)  # 'subscription_renewal', 'extra_seat', 'tier_upgrade'
    plan_id: Mapped[str] = mapped_column(Text, nullable=False)       # 'solo', 'pro', 'enterprise', 'extra_seat'
    billing_cycle: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'monthly'"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    amount_usd: Mapped[float] = mapped_column(REAL, nullable=False)
    extra_seat_renewal_usd: Mapped[float] = mapped_column(REAL, nullable=False, server_default=text('0.0'))
    total_usd: Mapped[float] = mapped_column(REAL, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"), index=True)  # pending|paid|cancelled|expired
    due_date: Mapped[str] = mapped_column(Text, nullable=False)
    paid_at: Mapped[Optional[str]] = mapped_column(Text)
    paid_currency: Mapped[Optional[str]] = mapped_column(Text)
    paid_amount: Mapped[Optional[float]] = mapped_column(REAL)
    exchange_rate_applied: Mapped[Optional[float]] = mapped_column(REAL)
    provider_code: Mapped[Optional[str]] = mapped_column(Text)
    bank_txn_ref: Mapped[Optional[str]] = mapped_column(Text)
    target_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey('access_profiles.id', ondelete='SET NULL'), nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class BillerTransactions(Base):
    __tablename__ = 'biller_transactions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    biller_invoice_id: Mapped[int] = mapped_column(ForeignKey('biller_invoices.id', ondelete='CASCADE'), nullable=False, index=True)
    office_id: Mapped[int] = mapped_column(ForeignKey('law_offices.id', ondelete='CASCADE'), nullable=False, index=True)
    provider_code: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    bank_reference: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    amount_paid: Mapped[float] = mapped_column(REAL, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    amount_usd_equivalent: Mapped[float] = mapped_column(REAL, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)  # success|failed|pending|reversed
    error_code: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    raw_request_json: Mapped[Optional[str]] = mapped_column(Text)
    raw_response_json: Mapped[Optional[str]] = mapped_column(Text)
    ip_address: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class BillerAuditLogs(Base):
    __tablename__ = 'biller_audit_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    provider_code: Mapped[Optional[str]] = mapped_column(Text, index=True)
    subscriber_phone: Mapped[Optional[str]] = mapped_column(Text, index=True)
    invoice_no: Mapped[Optional[str]] = mapped_column(Text, index=True)
    details_json: Mapped[Optional[str]] = mapped_column(Text)
    ip_address: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text('CURRENT_TIMESTAMP'))
