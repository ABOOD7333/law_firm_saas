from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
import traceback

from database.database import get_db
from database.models import (
    AccessProfiles, LawCases, LawDocuments, LawTasks,
    LawHearings, LawPleadings, LawExpenses
)
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/advanced_operations", response_class=HTMLResponse)
async def advanced_operations_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        office_id = user.office_id or 1
        cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).all()
        return templates.TemplateResponse(request=request, name="advanced_operations.html", context={
            "user": user, "active_page": "advanced_operations", "cases": cases
        })
    except Exception:
        import traceback
        return HTMLResponse(content=f"<pre dir='ltr'>{traceback.format_exc()}</pre>", status_code=500)

@router.get("/api/advanced/case_health/{case_id}")
async def get_case_health(case_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    from datetime import datetime
    if not user: return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == user.office_id).first()
    if not case: return JSONResponse({"error": "Case not found"}, status_code=404)
    
    factors = []
    score = 100
    
    # 1. Documents Check
    docs = db.query(LawDocuments).filter(LawDocuments.case_id == case.id).count()
    if docs == 0:
        score -= 15; factors.append("لا توجد مستندات مسجلة للقضية.")
    
    # 2. Tasks Delay Check
    today_str = datetime.now().strftime("%Y-%m-%d")
    late_tasks = db.query(LawTasks).filter(LawTasks.case_id == case.id, LawTasks.due_at < today_str, LawTasks.status_key != 'مكتملة').count()
    if late_tasks > 0:
        score -= (late_tasks * 10); factors.append(f"يوجد {late_tasks} مهام متأخرة لم تنجز.")
        
    # 3. Next Hearing
    next_h = db.query(LawHearings).filter(LawHearings.case_id == case.id, LawHearings.hearing_at >= today_str).order_by(LawHearings.hearing_at.asc()).first()
    next_hearing_str = next_h.hearing_at if next_h else "لا توجد جلسات مجدولة"
    if not next_h and case.status_key not in ['closed', 'مغلقة']:
        score -= 10; factors.append("لا توجد جلسات قادمة مجدولة وقضية مفتوحة.")
        
    # 4. Pleadings
    pleadings = db.query(LawPleadings).filter(LawPleadings.case_id == case.id).count()
    
    score = max(0, score)
    health_label = "سليمة تماماً"
    color = "#10b981"
    if score < 60:
        health_label = "حرجة"
        color = "#e11d48"
    elif score < 85:
        health_label = "تحتاج متابعة"
        color = "#f59e0b"
        
    if not factors: factors.append("لا توجد مخاطر واضحة حالياً.")
    
    # Real Workflow data
    workflow = [
        {"stage": "فتح الملف", "user": "النظام", "status": "مكتمل", "start": case.open_date or "-", "due": "-"},
        {"stage": "جمع المستندات", "user": "-", "status": "مكتمل" if docs > 0 else "قيد العمل", "start": "-", "due": "-"},
        {"stage": "المرافعات", "user": "-", "status": "مكتمل" if pleadings > 0 else "متأخر" if score < 60 else "قيد العمل", "start": "-", "due": "-"},
    ]
    
    # Real Checklist
    checklist = [
        {"item": "رفع وكالة شرعية", "status": "منجز" if docs > 0 else "لم ينجز"},
        {"item": "دفع رسوم المحكمة", "status": "منجز" if db.query(LawExpenses).filter(LawExpenses.case_id == case.id).count() > 0 else "لم ينجز"},
    ]
    
    return JSONResponse({
        "progress": min(100, 20 + (docs * 10) + (pleadings * 15)),
        "health": health_label,
        "color": color,
        "stage": case.case_type_key or "تحت المراجعة",
        "next_hearing": next_hearing_str,
        "factors": factors,
        "workflow": workflow,
        "checklist": checklist
    })

