from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional

from database.database import get_db
from database.models import (
    AccessProfiles, LawCases, LawClients, LawParties,
    LawHearings, LawPleadings, LawJudgments, LawNotes, LawDocuments
)
from dependencies import get_current_user, templates, check_user_permission, require_user_permission

router = APIRouter()


@router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: str = "",
    scope: str = "all",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    case_status: Optional[str] = None,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "cases", "view")

    results = {
        "cases": [],
        "documents": [],
        "clients": [],
        "parties": [],
        "hearings": [],
        "pleadings": [],
        "judgments": [],
        "notes": []
    }

    office_id = user.office_id
    if not office_id:
        raise HTTPException(status_code=403, detail="حسابك غير مرتبط بمكتب")

    if q and q.strip():
        term = q.strip()
        like = f"%{term}%"

        # Multi-Tenant & RBAC case scoping
        visible_case_ids = db.query(LawCases.id).filter(
            LawCases.office_id == office_id,
            LawCases.is_deleted == 0,
        )
        if user.role in ["محامي", "محامٍ"] and getattr(user, 'can_view_all_cases', 1) == 0:
            visible_case_ids = visible_case_ids.filter(LawCases.lead_lawyer_id == user.id)
        case_ids = [row[0] for row in visible_case_ids.all()]

        # 1. Cases
        if scope in ("all", "cases") and check_user_permission(user, "cases", "view"):
            cq = db.query(LawCases).filter(
                LawCases.office_id == office_id,
                LawCases.is_deleted == 0,
                *([LawCases.lead_lawyer_id == user.id] if user.role in ["محامي", "محامٍ"] and getattr(user, 'can_view_all_cases', 1) == 0 else []),
                or_(
                    LawCases.title.ilike(like),
                    LawCases.case_number.ilike(like),
                    LawCases.summary.ilike(like),
                    LawCases.description.ilike(like)
                )
            )
            if case_status and case_status.strip():
                cq = cq.filter(LawCases.status_key == case_status.strip())
            if date_from and date_from.strip():
                cq = cq.filter(LawCases.created_at >= date_from.strip())
            if date_to and date_to.strip():
                cq = cq.filter(LawCases.created_at <= date_to.strip() + " 23:59:59")
            results["cases"] = cq.limit(20).all()

        # 2. Documents & Contracts (New Enterprise Feature)
        if scope in ("all", "documents") and check_user_permission(user, "documents", "view"):
            dq = db.query(LawDocuments).filter(
                LawDocuments.office_id == office_id,
                LawDocuments.is_deleted == 0,
                LawDocuments.case_id.in_(case_ids) if case_ids else LawDocuments.id == -1,
                or_(
                    LawDocuments.name.ilike(like),
                    LawDocuments.doc_code.ilike(like),
                    LawDocuments.document_type_key.ilike(like),
                    LawDocuments.description.ilike(like),
                    LawDocuments.keywords.ilike(like),
                    LawDocuments.notes.ilike(like)
                )
            )
            if date_from and date_from.strip():
                dq = dq.filter(LawDocuments.doc_date >= date_from.strip())
            if date_to and date_to.strip():
                dq = dq.filter(LawDocuments.doc_date <= date_to.strip())
            results["documents"] = dq.limit(20).all()

        # 3. Clients
        if scope in ("all", "clients") and check_user_permission(user, "clients", "view"):
            results["clients"] = db.query(LawClients).filter(
                LawClients.office_id == office_id,
                LawClients.is_deleted == 0,
                LawClients.case_id.in_(case_ids) if case_ids else LawClients.id == -1,
                or_(
                    LawClients.name.ilike(like),
                    LawClients.phone.ilike(like),
                    LawClients.national_id.ilike(like),
                    LawClients.email.ilike(like)
                )
            ).limit(20).all()

        # 4. Parties
        if scope in ("all", "parties") and check_user_permission(user, "parties", "view"):
            results["parties"] = db.query(LawParties).filter(
                LawParties.office_id == office_id,
                LawParties.is_deleted == 0,
                LawParties.case_id.in_(case_ids) if case_ids else LawParties.id == -1,
                or_(
                    LawParties.name.ilike(like),
                    LawParties.phone.ilike(like),
                    LawParties.id_number.ilike(like),
                    LawParties.lawyer_name.ilike(like)
                )
            ).limit(20).all()

        # 5. Hearings
        if scope in ("all", "hearings") and check_user_permission(user, "hearings", "view"):
            hq = db.query(LawHearings).filter(
                LawHearings.office_id == office_id,
                LawHearings.is_deleted == 0,
                LawHearings.case_id.in_(case_ids) if case_ids else LawHearings.id == -1,
                or_(
                    LawHearings.title.ilike(like),
                    LawHearings.court_name.ilike(like),
                    LawHearings.judge_name.ilike(like),
                    LawHearings.result_summary.ilike(like),
                    LawHearings.decision_text.ilike(like)
                )
            )
            if date_from and date_from.strip():
                hq = hq.filter(LawHearings.hearing_at >= date_from.strip())
            if date_to and date_to.strip():
                hq = hq.filter(LawHearings.hearing_at <= date_to.strip())
            results["hearings"] = hq.limit(20).all()

        # 6. Pleadings
        if scope in ("all", "pleadings") and check_user_permission(user, "pleadings", "view"):
            results["pleadings"] = db.query(LawPleadings).filter(
                LawPleadings.office_id == office_id,
                LawPleadings.is_deleted == 0,
                LawPleadings.case_id.in_(case_ids) if case_ids else LawPleadings.id == -1,
                or_(
                    LawPleadings.title.ilike(like),
                    LawPleadings.content_html.ilike(like),
                    LawPleadings.pleading_type_key.ilike(like)
                )
            ).limit(20).all()

        # 7. Judgments
        if scope in ("all", "judgments") and check_user_permission(user, "judgments", "view"):
            jq = db.query(LawJudgments).filter(
                LawJudgments.office_id == office_id,
                LawJudgments.is_deleted == 0,
                LawJudgments.case_id.in_(case_ids) if case_ids else LawJudgments.id == -1,
                or_(
                    LawJudgments.court_name.ilike(like),
                    LawJudgments.judge_name.ilike(like),
                    LawJudgments.judgment_text.ilike(like),
                    LawJudgments.status_key.ilike(like)
                )
            )
            if date_from and date_from.strip():
                jq = jq.filter(LawJudgments.judgment_date >= date_from.strip())
            if date_to and date_to.strip():
                jq = jq.filter(LawJudgments.judgment_date <= date_to.strip())
            results["judgments"] = jq.limit(20).all()

        # 8. Notes
        if scope in ("all", "notes") and check_user_permission(user, "notes", "view"):
            results["notes"] = db.query(LawNotes).filter(
                LawNotes.office_id == office_id,
                LawNotes.is_deleted == 0,
                LawNotes.case_id.in_(case_ids) if case_ids else LawNotes.id == -1,
                or_(
                    LawNotes.title.ilike(like),
                    LawNotes.content.ilike(like)
                )
            ).limit(20).all()

    total = sum(len(v) for v in results.values())
    return templates.TemplateResponse(
        request=request,
        name="search.html",
        context={
            "user": user,
            "q": q,
            "scope": scope,
            "date_from": date_from or "",
            "date_to": date_to or "",
            "case_status": case_status or "",
            "results": results,
            "total": total,
            "active_page": "search"
        }
    )


@router.get("/api/search/live")
async def live_search(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    """بحث حي وتلقائي سريع (Instant Typeahead API) مع مراعاة كامل الصلاحيات وعزل المكاتب"""
    if not user or not user.office_id:
        raise HTTPException(status_code=401, detail="غير مصرح")

    office_id = user.office_id
    term = q.strip()
    like = f"%{term}%"

    visible_case_ids = db.query(LawCases.id).filter(
        LawCases.office_id == office_id,
        LawCases.is_deleted == 0,
    )
    if user.role in ["محامي", "محامٍ"] and getattr(user, 'can_view_all_cases', 1) == 0:
        visible_case_ids = visible_case_ids.filter(LawCases.lead_lawyer_id == user.id)
    case_ids = [row[0] for row in visible_case_ids.all()]

    quick_results = []

    # Cases
    if check_user_permission(user, "cases", "view"):
        cases = db.query(LawCases).filter(
            LawCases.office_id == office_id,
            LawCases.is_deleted == 0,
            or_(LawCases.title.ilike(like), LawCases.case_number.ilike(like))
        ).limit(5).all()
        for c in cases:
            quick_results.append({
                "type": "case",
                "badge": "قضية",
                "title": f"{c.case_number} - {c.title}",
                "url": f"/cases/{c.id}"
            })

    # Documents
    if check_user_permission(user, "documents", "view"):
        docs = db.query(LawDocuments).filter(
            LawDocuments.office_id == office_id,
            LawDocuments.is_deleted == 0,
            LawDocuments.case_id.in_(case_ids) if case_ids else LawDocuments.id == -1,
            or_(LawDocuments.name.ilike(like), LawDocuments.doc_code.ilike(like))
        ).limit(5).all()
        for d in docs:
            quick_results.append({
                "type": "doc",
                "badge": "مستند",
                "title": f"{d.doc_code or ''} {d.name}",
                "url": f"/cases/{d.case_id}" if d.case_id else "/documents"
            })

    # Clients
    if check_user_permission(user, "clients", "view"):
        clients = db.query(LawClients).filter(
            LawClients.office_id == office_id,
            LawClients.is_deleted == 0,
            or_(LawClients.name.ilike(like), LawClients.phone.ilike(like))
        ).limit(5).all()
        for cl in clients:
            quick_results.append({
                "type": "client",
                "badge": "موكل",
                "title": f"{cl.name} ({cl.phone or 'بلا هاتف'})",
                "url": f"/clients"
            })

    return {"success": True, "results": quick_results}

