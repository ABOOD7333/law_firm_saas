"""
Contract Analyzer Router — صفحة محلل العقود الذكي
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database.database import get_db
from dependencies import get_current_user
from database.models import AccessProfiles

router = APIRouter(tags=["Contract Analyzer"])
templates = Jinja2Templates(directory="templates")


@router.get("/contract-analyzer", response_class=HTMLResponse)
async def contract_analyzer_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user)
):
    """صفحة محلل العقود الذكي"""
    if not current_user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("contract_analyzer.html", {
        "request": request,
        "current_user": current_user,
        "page_title": "محلل العقود الذكي"
    })
