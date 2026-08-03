import base64

def _get_tlv_hex(tag: int, value: str) -> bytes:
    """
    Generate TLV (Tag-Length-Value) format for ZATCA
    tag: 1 to 5
    value: string value
    """
    value_bytes = str(value).encode('utf-8')
    length = len(value_bytes)
    
    # Tag is 1 byte, Length is 1 byte, Value is N bytes
    tlv = bytes([tag, length]) + value_bytes
    return tlv

def generate_zatca_qr(seller_name: str, vat_number: str, timestamp: str, invoice_total: float, vat_total: float) -> str:
    """
    Generate the Base64 string for ZATCA Phase 1 QR Code.
    
    Args:
        seller_name (str): The name of the law firm / seller.
        vat_number (str): The 15-digit VAT registration number.
        timestamp (str): ISO 8601 format e.g., '2023-10-25T15:30:00Z'
        invoice_total (float): Total invoice amount including VAT.
        vat_total (float): Total VAT amount.
        
    Returns:
        str: Base64 encoded string to be embedded in the QR Code.
    """
    
    tlv_1 = _get_tlv_hex(1, seller_name)
    tlv_2 = _get_tlv_hex(2, vat_number)
    tlv_3 = _get_tlv_hex(3, timestamp)
    tlv_4 = _get_tlv_hex(4, f"{invoice_total:.2f}")
    tlv_5 = _get_tlv_hex(5, f"{vat_total:.2f}")
    
    full_tlv = tlv_1 + tlv_2 + tlv_3 + tlv_4 + tlv_5
    
    qr_base64 = base64.b64encode(full_tlv).decode('utf-8')
    return qr_base64
