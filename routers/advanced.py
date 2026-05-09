from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawDocuments, LawTasks, LawHearings, LawPleadings, LawExpenses

router = APIRouter()

# get_current_user should be imported from somewhere, but to avoid circular imports, we can import it locally or move it.
# For now, we will import it lazily from main, or better, we should create dependencies.py
