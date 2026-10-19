# -*- coding: utf-8 -*-
"""
Conflict of Interest (COI) Router — LawSaaS
يوفر واجهة فحص تعارض المصالح المستقلة ونقاط نهاية الـ API اللحظية
"""

from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import AccessProfiles
from dependencies import get_current_user, templates, check_user_permission, require_user_permission
from core.conflict_checker import perform_conflict_check

router = APIRouter()


@router.get("/conflict-check", response_class=HTMLResponse)
async def conflict_check_page(
    request: Request,
    q_name: str = Query(None),
    q_id: str = Query(None),
    q_cr: str = Query(None),
    q_phone: str = Query(None),
    target_role: str = Query("خصم"),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    """صفحة فحص تعارض وتضارب المصالح المتقدمة للمحامين"""
    if not user:
        return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id
    if not office_id:
        raise HTTPException(status_code=403, detail="الحساب غير مرتبط بمكتب محاماة")

    has_searched = bool((q_name and q_name.strip()) or (q_id and q_id.strip()) or (q_cr and q_cr.strip()) or (q_phone and q_phone.strip()))
    result = None

    if has_searched:
        result = perform_conflict_check(
            db=db,
            office_id=office_id,
            query_name=q_name,
            id_number=q_id,
            cr_number=q_cr,
            phone=q_phone,
            target_role=target_role or "خصم"
        )

    return templates.TemplateResponse(
        "conflict_check.html",
        {
            "request": request,
            "user": user,
            "active_page": "conflict_check",
            "q_name": q_name or "",
            "q_id": q_id or "",
            "q_cr": q_cr or "",
            "q_phone": q_phone or "",
            "target_role": target_role or "خصم",
            "result": result,
            "has_searched": has_searched
        }
    )


@router.get("/api/conflict-check")
async def api_conflict_check(
    name: str = Query(None),
    id_number: str = Query(None),
    cr_number: str = Query(None),
    phone: str = Query(None),
    role: str = Query("خصم"),
    exclude_party_id: int = Query(None),
    exclude_case_id: int = Query(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    """
    نقطة نهاية سريعة (AJAX API) للاستعلام اللحظي من النوافذ المنبثقة
    مثل نافذة إضافة طرف أو إضافة عميل
    """
    if not user or not user.office_id:
        raise HTTPException(status_code=401, detail="غير مصرح بالوصول")

    res = perform_conflict_check(
        db=db,
        office_id=user.office_id,
        query_name=name,
        id_number=id_number,
        cr_number=cr_number,
        phone=phone,
        target_role=role or "خصم",
        exclude_party_id=exclude_party_id,
        exclude_case_id=exclude_case_id
    )
    return JSONResponse(content=res)
