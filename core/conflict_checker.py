# -*- coding: utf-8 -*-
"""
Core Conflict of Interest (COI) Screening Engine — LawSaaS
فحص تعارض وتضارب المصالح الآلي لبيئة مكاتب وشركات المحاماة.
يقوم بفحص الأسماء، الهويات، السجلات، وأرقام الهواتف عبر الموكلين وأطراف النزاع والقضايا القائمة.
"""

import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from database.models import LawClients, LawParties, LawCases, LawIncomingCases


def normalize_arabic(text: Optional[str]) -> str:
    """Normalize Arabic characters for fuzzy and robust conflict matching."""
    if not text:
        return ""
    s = str(text).strip()
    s = re.sub(r"[إأآا]", "ا", s)
    s = re.sub(r"ى", "ي", s)
    s = re.sub(r"ة", "ه", s)
    s = re.sub(r"[\u064B-\u065F\u0670]", "", s)  # Remove Tashkeel/Diacritics
    s = re.sub(r"ـ+", "", s)  # Remove Tatweel
    s = re.sub(r"\s+", " ", s)  # Collapse spaces
    return s.lower()


def perform_conflict_check(
    db: Session,
    office_id: int,
    query_name: Optional[str] = None,
    id_number: Optional[str] = None,
    cr_number: Optional[str] = None,
    phone: Optional[str] = None,
    target_role: str = "خصم",  # 'خصم' or 'موكل' or 'طرف'
    exclude_party_id: Optional[int] = None,
    exclude_case_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Performs comprehensive Conflict of Interest screening across:
    1. LawClients (Active and Past Clients)
    2. LawParties (Plaintiffs, Defendants, Witnesses, Experts)
    3. LawCases (Active and Archived Cases)
    """
    cleaned_name = (query_name or "").strip()
    norm_name = normalize_arabic(cleaned_name)
    cleaned_id = (id_number or "").strip()
    cleaned_cr = (cr_number or "").strip()
    cleaned_phone = (phone or "").strip()

    # If completely empty, return clear
    if not cleaned_name and not cleaned_id and not cleaned_cr and not cleaned_phone:
        return {
            "status": "CLEAR",
            "has_conflict": False,
            "badge_color": "success",
            "badge_text": "سليم - لا توجد بيانات للبحث",
            "summary": "لم يتم إدخال بيانات كافية لإجراء الفحص.",
            "total_matches": 0,
            "client_matches": [],
            "party_matches": [],
            "matches": []
        }

    client_matches: List[Dict[str, Any]] = []
    party_matches: List[Dict[str, Any]] = []

    # 1. Search LawClients
    client_filters = [LawClients.office_id == office_id]
    client_or_clauses = []

    if len(cleaned_name) >= 3:
        client_or_clauses.append(LawClients.name.ilike(f"%{cleaned_name}%"))
    if cleaned_id:
        client_or_clauses.append(LawClients.national_id == cleaned_id)
    if cleaned_phone and len(cleaned_phone) >= 6:
        client_or_clauses.append(LawClients.phone.ilike(f"%{cleaned_phone}%"))

    if client_or_clauses:
        client_filters.append(or_(*client_or_clauses))
        existing_clients = db.query(LawClients).filter(*client_filters).limit(10).all()

        for c in existing_clients:
            # Check for name match or id match
            match_reasons = []
            if cleaned_name and cleaned_name.lower() in (c.name or "").lower():
                match_reasons.append("تطابق الاسم مع موكل مسجل")
            elif norm_name and norm_name in normalize_arabic(c.name):
                match_reasons.append("تشابه متقارب في الاسم مع موكل مسجل")

            if cleaned_id and c.national_id and cleaned_id == c.national_id:
                match_reasons.append("تطابق تام في رقم الهوية الوطنية")

            if cleaned_phone and c.phone and cleaned_phone in c.phone:
                match_reasons.append("تطابق في رقم الهاتف")

            # Count cases for this client via LawParties where role_key == 'موكل'
            cases_count = db.query(LawParties).filter(
                LawParties.office_id == office_id,
                LawParties.is_deleted == 0,
                LawParties.role_key == "موكل",
                LawParties.name.ilike(f"%{c.name}%")
            ).count()

            client_matches.append({
                "type": "موكل مسجل",
                "client_id": c.id,
                "name": c.name,
                "national_id": c.national_id or "-",
                "phone": c.phone or "-",
                "cases_count": cases_count,
                "match_reasons": match_reasons or ["تطابق في سجل الموكلين"]
            })

    # 2. Search LawParties
    party_filters = [
        LawParties.office_id == office_id,
        LawParties.is_deleted == 0
    ]
    if exclude_party_id:
        party_filters.append(LawParties.id != exclude_party_id)
    if exclude_case_id:
        party_filters.append(LawParties.case_id != exclude_case_id)

    party_or_clauses = []
    if len(cleaned_name) >= 3:
        party_or_clauses.append(LawParties.name.ilike(f"%{cleaned_name}%"))
    if cleaned_id:
        party_or_clauses.append(LawParties.id_number == cleaned_id)
    if cleaned_cr:
        party_or_clauses.append(LawParties.cr_number == cleaned_cr)
    if cleaned_phone and len(cleaned_phone) >= 6:
        party_or_clauses.append(LawParties.phone.ilike(f"%{cleaned_phone}%"))

    if party_or_clauses:
        party_filters.append(or_(*party_or_clauses))
        existing_parties = db.query(LawParties).filter(*party_filters).limit(15).all()

        for p in existing_parties:
            match_reasons = []
            if cleaned_name and cleaned_name.lower() in (p.name or "").lower():
                match_reasons.append("تطابق الاسم مع طرف في قضية")
            elif norm_name and norm_name in normalize_arabic(p.name):
                match_reasons.append("تشابه في الاسم مع طرف في قضية")

            if cleaned_id and p.id_number and cleaned_id == p.id_number:
                match_reasons.append("تطابق تام في رقم الهوية")

            if cleaned_cr and p.cr_number and cleaned_cr == p.cr_number:
                match_reasons.append("تطابق في رقم السجل التجاري")

            case_info = None
            if p.case_id:
                c_obj = db.query(LawCases).filter(
                    LawCases.id == p.case_id,
                    LawCases.office_id == office_id,
                    LawCases.is_deleted == 0
                ).first()
                if c_obj:
                    # Find client of this case via LawParties where role_key == 'موكل'
                    c_client = db.query(LawParties).filter(
                        LawParties.case_id == c_obj.id,
                        LawParties.role_key == "موكل",
                        LawParties.is_deleted == 0
                    ).first()
                    client_name = c_client.name if c_client else "غير محدد"

                    case_info = {
                        "id": c_obj.id,
                        "case_number": c_obj.case_number or f"#{c_obj.id}",
                        "title": c_obj.title or "بدون عنوان",
                        "status": c_obj.status_key or "قيد النظر",
                        "client_name": client_name
                    }

            party_matches.append({
                "type": f"طرف ({p.role_key or 'طرف'})",
                "party_id": p.id,
                "name": p.name,
                "role_key": p.role_key or "طرف",
                "legal_capacity": p.legal_capacity or "-",
                "id_number": p.id_number or "-",
                "phone": p.phone or "-",
                "case": case_info,
                "match_reasons": match_reasons or ["تطابق في سجل أطراف القضايا"]
            })

    # 3. Conflict Severity Assessment
    total_matches = len(client_matches) + len(party_matches)
    has_conflict = False
    status = "CLEAR"
    badge_color = "success"
    badge_text = "سليم — لا يوجد تعارض مسجل"
    summary = "تم فحص قاعدة البيانات ولم يتم العثور على أي موكلين أو خصوم سابقين يحملون هذه البيانات."

    # Analyze critical conflicts
    is_high_conflict = False
    is_potential_conflict = False

    # Scenario A: Target is 'خصم' (Opponent) but is found in LawClients!
    if target_role in ["خصم", "مستأنف ضده", "مدعى عليه", "مطعون ضده"]:
        if client_matches:
            is_high_conflict = True
            summary = f"⚠️ تعارض مصالح حرج للغاية! الطرف المطلوب إضافته كخصم مسجل رسمياً كـ (موكل) لدى المكتب ({client_matches[0]['name']}). يمنع قانوناً وأخلاقياً تمثيل الخصومة ضد موكليك!"
        else:
            # Check if this person was a client's ally in another active case
            for pm in party_matches:
                if pm['role_key'] in ["موكل", "طرفنا"] and pm['case'] and pm['case']['status'] in ["قيد النظر", "نشطة", "open", "active"]:
                    is_high_conflict = True
                    summary = f"⚠️ تعارض مصالح حرج: الطرف مسجل كـ (طرفنا/موكل) في القضية النشطة رقم ({pm['case']['case_number']}). لا يمكن الترافع ضده كخصم!"
                    break

    # Scenario B: Target is 'موكل' (Client) but is found as 'خصم' in an active case!
    if target_role in ["موكل", "طرفنا", "مدعي", "مستأنف", "طاعن"]:
        for pm in party_matches:
            if pm['role_key'] in ["خصم", "مدعى عليه"] and pm['case'] and pm['case']['status'] in ["قيد النظر", "نشطة", "open", "active"]:
                is_high_conflict = True
                summary = f"⚠️ تعارض مصالح حرج: الشخص المطلوب تمثيله كموكل هو (خصم معارض) لموكلك ({pm['case']['client_name']}) في القضية النشطة رقم ({pm['case']['case_number']})!"
                break

    # If not high conflict, check potential conflicts
    if not is_high_conflict and total_matches > 0:
        is_potential_conflict = True
        if target_role in ["خصم"]:
            summary = f"تنبيه: تم العثور على {total_matches} سجلات مطابقة في النظام (أطراف في قضايا أخرى). يرجى مراجعة التفاصيل أدناه للتأكد من عدم وجود تضارب مصالح موضوعي."
        else:
            summary = f"ملاحظة: هذا الاسم أو الهوية مسجل بالفعل في النظام ({total_matches} سجلات مطابقة). قد يكون موكلاً حالياً أو طرفاً في ملف سابق."

    if is_high_conflict:
        has_conflict = True
        status = "HIGH_CONFLICT"
        badge_color = "danger"
        badge_text = "🔴 تعارض مصالح حرج ومباشر"
    elif is_potential_conflict:
        has_conflict = True
        status = "POTENTIAL_CONFLICT"
        badge_color = "warning"
        badge_text = "🟡 تنبيه: سوابق مطابقة / تعارض محتمل"

    # Unified flat matches list for convenient display
    all_matches = []
    for cm in client_matches:
        all_matches.append({
            "category": "سجل الموكلين",
            "name": cm["name"],
            "role": "موكل مسجل",
            "id_number": cm["national_id"],
            "phone": cm["phone"],
            "case_number": f"{cm['cases_count']} قضية مرتبطة",
            "case_title": "ملف عميل بالمكتب",
            "reasons": cm["match_reasons"],
            "risk_level": "عالي" if target_role == "خصم" else "منخفض"
        })
    for pm in party_matches:
        c_title = pm["case"]["title"] if pm["case"] else "-"
        c_num = pm["case"]["case_number"] if pm["case"] else "-"
        risk = "عالي" if (target_role == "خصم" and pm["role_key"] == "موكل") or (target_role == "موكل" and pm["role_key"] == "خصم") else "متوسط"
        all_matches.append({
            "category": "سجل أطراف القضايا",
            "name": pm["name"],
            "role": pm["role_key"],
            "id_number": pm["id_number"],
            "phone": pm["phone"],
            "case_number": c_num,
            "case_title": c_title,
            "reasons": pm["match_reasons"],
            "risk_level": risk
        })

    return {
        "status": status,
        "has_conflict": has_conflict,
        "badge_color": badge_color,
        "badge_text": badge_text,
        "summary": summary,
        "total_matches": total_matches,
        "client_matches": client_matches,
        "party_matches": party_matches,
        "matches": all_matches
    }
