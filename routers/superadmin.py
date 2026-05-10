from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import json

from database.database import get_db
from database.models import AccessProfiles, LawOffices
from dependencies import get_current_user, templates
from core.logger import app_logger

router = APIRouter()

def is_superadmin(user: AccessProfiles):
    # Only allow user ID 1 or a specific username to access the superadmin panel
    if not user:
        return False
    if user.id == 1 or user.username == 'ABOOD':
        return True
    return False

@router.get("/superadmin", response_class=HTMLResponse)
async def superadmin_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user or not is_superadmin(user):
        return RedirectResponse(url="/dashboard", status_code=303)
    
    try:
        # Fetch all offices
        offices = db.query(LawOffices).all()
        
        # Fetch the owner details for each office
        office_data = []
        for office in offices:
            owner = db.query(AccessProfiles).filter(AccessProfiles.id == office.owner_user_id).first() if office.owner_user_id else None
            # Count users in this office
            user_count = db.query(AccessProfiles).filter(AccessProfiles.office_id == office.id).count()
            
            office_data.append({
                "id": office.id,
                "name": office.name,
                "status_key": office.status_key,
                "is_active": office.is_active,
                "created_at": office.created_at,
                "user_count": user_count,
                "owner_name": owner.name if owner else "غير محدد",
                "owner_email": owner.email if owner else "غير محدد",
                "owner_phone": owner.phone if owner else "غير محدد"
            })
            
        return templates.TemplateResponse(request=request, name="superadmin.html", context={
            "user": user,
            "active_page": "superadmin",
            "offices": office_data
        })
    except Exception as e:
        import traceback
        app_logger.error(f"Superadmin page error: {e}\n{traceback.format_exc()}")
        return HTMLResponse(content=f"An error occurred: {e}", status_code=500)

@router.post("/api/superadmin/toggle-office/{office_id}")
async def toggle_office(office_id: int, request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user or not is_superadmin(user):
        return JSONResponse({"success": False, "error": "غير مصرح لك بالقيام بهذا الإجراء"}, status_code=403)
        
    try:
        office = db.query(LawOffices).filter(LawOffices.id == office_id).first()
        if not office:
            return JSONResponse({"success": False, "error": "المكتب غير موجود"}, status_code=404)
            
        # Toggle status
        office.is_active = 1 if office.is_active == 0 else 0
        db.commit()
        
        status_text = "تفعيل" if office.is_active == 1 else "إيقاف"
        app_logger.info(f"SUPERADMIN | Office {office.id} toggled to {office.is_active} by user {user.id}")
        
        return JSONResponse({"success": True, "message": f"تم {status_text} المكتب بنجاح", "is_active": office.is_active})
    except Exception as e:
        db.rollback()
        app_logger.error(f"Superadmin toggle error: {e}")
        return JSONResponse({"success": False, "error": "حدث خطأ داخلي"}, status_code=500)
