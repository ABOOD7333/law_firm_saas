"""
محرك فحص تعارض المصالح (Conflict of Interest Engine)
يفحص أسماء الأطراف والخصوم لمنع تمثيل أطراف متنازعة قانونياً
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from database.models import LawClients, LawParties, LawCases

def clean_arabic_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = text.strip()
    # Normalize common arabic letters
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    return text.lower()

def check_conflict_of_interest(
    db: Session,
    office_id: int,
    client_name: str,
    client_national_id: Optional[str] = None,
    client_phone: Optional[str] = None,
    opposing_name: Optional[str] = None,
    opposing_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    يفحص ما إذا كان العميل أو الخصم موجوداً مسبقاً في قضايا المكتب (كموكل أو كخصم).
    """
    conflicts: List[Dict[str, Any]] = []
    
    clean_c_name = clean_arabic_text(client_name)
    clean_opp_name = clean_arabic_text(opposing_name)
    
    # 1. فحص هل الخصم (Opposing Party) هو موكل حالي للمكتب؟ (تعارض خطير جداً!)
    if opposing_name:
        existing_clients = db.query(LawClients).filter(
            LawClients.office_id == office_id,
            LawClients.is_deleted == 0
        ).all()
        
        for client in existing_clients:
            c_norm = clean_arabic_text(client.name)
            if clean_opp_name in c_norm or c_norm in clean_opp_name:
                conflicts.append({
                    "severity": "CRITICAL",
                    "type": "opposing_is_existing_client",
                    "message": f"تحذير حرج: الخصم المذكور '{opposing_name}' مسجل حالياً كموكل في المكتب ({client.name})!",
                    "matched_id": client.id,
                    "matched_name": client.name
                })
            elif opposing_id and client.national_id and opposing_id.strip() == client.national_id.strip():
                conflicts.append({
                    "severity": "CRITICAL",
                    "type": "opposing_national_id_match",
                    "message": f"تحذير حرج: رقم هوية الخصم '{opposing_id}' يطابق رقم هوية الموكل الحالي ({client.name})!",
                    "matched_id": client.id,
                    "matched_name": client.name
                })

    # 2. فحص هل الموكل الجديد (Client) مسجل كخصم في قضايا سابقة للمكتب؟
    if client_name:
        existing_parties = db.query(LawParties).filter(
            LawParties.office_id == office_id,
            LawParties.is_deleted == 0
        ).all()
        
        for party in existing_parties:
            p_norm = clean_arabic_text(party.name)
            if clean_c_name in p_norm or p_norm in clean_c_name:
                conflicts.append({
                    "severity": "HIGH",
                    "type": "client_is_previous_adverse_party",
                    "message": f"تنبيه: المتقدم '{client_name}' مسجل كطرف/خصم سابق في قضية رقم {party.case_id} باسم ({party.name})!",
                    "matched_id": party.case_id,
                    "matched_name": party.name
                })
            elif client_national_id and party.id_number and client_national_id.strip() == party.id_number.strip():
                conflicts.append({
                    "severity": "HIGH",
                    "type": "client_id_matches_adverse_party",
                    "message": f"تنبيه: رقم هوية المتقدم يطابق رقم هوية طرف في قضية سابقة ({party.name})!",
                    "matched_id": party.case_id,
                    "matched_name": party.name
                })

    # 3. فحص هل الموكل الجديد مسجل بالفعل كموكل سابق (تكرار موكل)
    if client_phone:
        dup_phone = db.query(LawClients).filter(
            LawClients.office_id == office_id,
            LawClients.phone == client_phone.strip(),
            LawClients.is_deleted == 0
        ).first()
        if dup_phone:
            conflicts.append({
                "severity": "INFO",
                "type": "existing_client_returning",
                "message": f"ملاحظة: هذا الموكل مسجل مسبقاً في النظام باسم ({dup_phone.name}).",
                "matched_id": dup_phone.id,
                "matched_name": dup_phone.name
            })

    has_critical = any(c["severity"] == "CRITICAL" for c in conflicts)
    has_high = any(c["severity"] == "HIGH" for c in conflicts)
    
    status = "safe"
    if has_critical:
        status = "conflict_detected"
    elif has_high:
        status = "warning"
        
    return {
        "status": status,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "summary": "آمن تماماً ولا يوجد أي تعارض مصالح مسجل." if not conflicts else f"تم رصد {len(conflicts)} ملاحظات تعارض مصالح محتملة."
    }
