"""
Payment Provider Adapters
=========================
Pluggable adapter architecture allowing Waziruk to connect with any bank or digital wallet
without changing core billing, invoicing, or subscription activation logic.
"""

import hmac
import hashlib
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BasePaymentAdapter(ABC):
    """Abstract base class for all bank/wallet payment adapters."""

    def __init__(self, provider_code: str, is_sandbox: bool = False, default_currency: str = "AUTO"):
        self.provider_code = provider_code
        self.is_sandbox = is_sandbox
        self.default_currency = default_currency

    def verify_signature(self, raw_body: bytes, signature: Optional[str], secret: str) -> bool:
        """Verify HMAC-SHA256 signature sent in X-Waziruk-Signature header."""
        if self.is_sandbox and not signature:
            return True
        if not signature or not secret:
            return False
        expected = hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        # Accept optional 'sha256=' prefix
        sig_clean = signature.replace("sha256=", "").strip().lower()
        return hmac.compare_digest(expected.lower(), sig_clean)

    @abstractmethod
    def parse_inquiry_request(self, payload: Dict[str, Any]) -> str:
        """Extract subscriber phone number from incoming bank inquiry payload."""
        pass

    @abstractmethod
    def format_inquiry_response(self, inquiry_result: Dict[str, Any]) -> Dict[str, Any]:
        """Format Waziruk core inquiry output into bank-compatible response."""
        pass

    @abstractmethod
    def parse_payment_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract standardized payment fields from incoming bank payment payload."""
        pass

    @abstractmethod
    def format_payment_response(self, payment_result: Dict[str, Any]) -> Dict[str, Any]:
        """Format Waziruk core payment confirmation into bank-compatible response."""
        pass


class GenericBillerAdapter(BasePaymentAdapter):
    """
    Standard Unified Waziruk Biller Protocol Adapter.
    Works out-of-the-box for any bank/wallet integrating via Waziruk's official API specs.
    """

    def parse_inquiry_request(self, payload: Dict[str, Any]) -> str:
        return str(
            payload.get("subscriber_phone")
            or payload.get("phone")
            or payload.get("subscriber_id")
            or ""
        ).strip()

    def format_inquiry_response(self, inquiry_result: Dict[str, Any]) -> Dict[str, Any]:
        return inquiry_result

    def parse_payment_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "invoice_no": str(payload.get("invoice_no") or payload.get("bill_id") or "").strip(),
            "amount_paid": float(payload.get("amount_paid") or payload.get("amount") or 0),
            "currency": str(payload.get("currency") or "USD").upper().strip(),
            "bank_reference": str(payload.get("bank_reference") or payload.get("txn_ref") or "").strip(),
            "idempotency_key": str(payload.get("idempotency_key") or payload.get("bank_reference") or "").strip(),
        }

    def format_payment_response(self, payment_result: Dict[str, Any]) -> Dict[str, Any]:
        return payment_result


class SandboxAdapter(GenericBillerAdapter):
    """Sandbox / Demo simulator adapter."""

    def verify_signature(self, raw_body: bytes, signature: Optional[str], secret: str) -> bool:
        return True


class KuraimiAdapter(GenericBillerAdapter):
    """Adapter ready for Al-Kuraimi Bank (Hasib / Kuraimi Express) custom mapping."""
    pass


class JeebAdapter(GenericBillerAdapter):
    """Adapter ready for Jeeb Wallet custom mapping."""
    pass


class SabaCashAdapter(GenericBillerAdapter):
    """Adapter ready for SabaCash Wallet custom mapping."""
    pass


class OneCashAdapter(GenericBillerAdapter):
    """Adapter ready for OneCash Wallet custom mapping."""
    pass


ADAPTER_REGISTRY = {
    "generic": GenericBillerAdapter,
    "sandbox": SandboxAdapter,
    "kuraimi": KuraimiAdapter,
    "jeeb": JeebAdapter,
    "saba_cash": SabaCashAdapter,
    "one_cash": OneCashAdapter,
}


def get_adapter_for_provider(provider) -> BasePaymentAdapter:
    """Instantiate the appropriate adapter for a database PaymentProviders row."""
    adapter_cls = ADAPTER_REGISTRY.get(
        (getattr(provider, "adapter_type", None) or "generic").lower(),
        GenericBillerAdapter
    )
    return adapter_cls(
        provider_code=provider.code,
        is_sandbox=bool(provider.is_sandbox),
        default_currency=provider.default_currency or "AUTO"
    )
