from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawClients, LawParties
from dependencies import get_current_user, require_user_permission, user_can_access_case

router = APIRouter()

@router.get("/api/case/{case_id}/recipients")
async def get_case_recipients(
    case_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return JSONResponse({"error": "unauthorized"}, status_code=401)
    if not user.office_id:
        raise HTTPException(status_code=403, detail="الحساب غير مرتبط بمكتب")
    require_user_permission(user, "correspondences", "add")
    office_id = user.office_id
    if not user_can_access_case(db, user, case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بالوصول لهذه القضية")
    
    recipients = []
    # Clients
    clients = db.query(LawClients).filter(
        LawClients.case_id == case_id,
        LawClients.office_id == office_id,
        LawClients.is_deleted == 0,
    ).all()
    for c in clients:
        recipients.append({
            "id": f"client_{c.id}", "name": c.name,
            "type": "موكل", "phone": c.phone or "",
            "email": c.email or "", "has_phone": bool(c.phone), "has_email": bool(c.email)
        })
    # Parties
    parties = db.query(LawParties).filter(
        LawParties.case_id == case_id,
        LawParties.office_id == office_id,
        LawParties.is_deleted == 0,
    ).all()
    for p in parties:
        recipients.append({
            "id": f"party_{p.id}", "name": p.name,
            "type": p.role_key, "phone": p.phone or "",
            "email": p.email or "", "has_phone": bool(p.phone), "has_email": bool(p.email)
        })
    return JSONResponse({"recipients": recipients})
