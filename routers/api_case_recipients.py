from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawClients, LawParties
from dependencies import get_current_user

router = APIRouter()

@router.get("/api/case/{case_id}/recipients")
async def get_case_recipients(
    case_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return JSONResponse({"error": "unauthorized"}, status_code=401)
    office_id = user.office_id or 1
    case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
    if not case: return JSONResponse({"error": "not found"}, status_code=404)
    
    recipients = []
    # Clients
    clients = db.query(LawClients).filter(LawClients.case_id == case_id).all()
    for c in clients:
        recipients.append({
            "id": f"client_{c.id}", "name": c.name,
            "type": "موكل", "phone": c.phone or "",
            "email": c.email or "", "has_phone": bool(c.phone), "has_email": bool(c.email)
        })
    # Parties
    parties = db.query(LawParties).filter(LawParties.case_id == case_id).all()
    for p in parties:
        recipients.append({
            "id": f"party_{p.id}", "name": p.name,
            "type": p.role_key, "phone": p.phone or "",
            "email": p.email or "", "has_phone": bool(p.phone), "has_email": bool(p.email)
        })
    return JSONResponse({"recipients": recipients})
