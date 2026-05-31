from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database.database import get_db
from database.models import (
    AccessProfiles, LawCases, LawClients, LawHearings, LawTasks, 
    LawDocuments, LawNotes, LawTransactions
)
from dependencies import get_current_user

router = APIRouter(prefix="/api/mobile/sync", tags=["Mobile Sync"])

class SyncRequest(BaseModel):
    last_sync: Optional[str] = None # format YYYY-MM-DD HH:MM:SS
    device_id: str

def get_delta(db_query, last_sync: str):
    if not last_sync:
        return db_query.all()
    # Filter by updated_at or created_at if updated_at is null
    return db_query.filter(
        or_(
            getattr(db_query.column_descriptions[0]['type'], 'updated_at') >= last_sync,
            getattr(db_query.column_descriptions[0]['type'], 'created_at') >= last_sync
        )
    ).all()

@router.post("/pull")
async def pull_sync(req: SyncRequest, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")
        
    office_id = user.office_id or 1
    last_sync = req.last_sync
    
    response_data: Dict[str, Any] = {
        "sync_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "cases": [],
        "clients": [],
        "tasks": [],
        "hearings": [],
        "documents": [],
    }

    # Helper function to convert model to dict safely
    def model_to_dict(obj):
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

    # 1. Cases
    cases_query = db.query(LawCases).filter(LawCases.office_id == office_id)
    if user.role in ['محامي', 'محامٍ'] and getattr(user, "can_view_all_cases", 0) == 0:
        cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)
    elif user.role == 'موكل':
        # Mapped indirectly if needed, skipped simplified here
        pass
        
    cases = get_delta(cases_query, last_sync)
    response_data["cases"] = [model_to_dict(c) for c in cases]

    # Collect accessible case IDs to filter related data
    case_ids = [c.id for c in cases_query.all()]
    
    if case_ids:
        # 2. Clients
        clients_query = db.query(LawClients).filter(LawClients.office_id == office_id, LawClients.case_id.in_(case_ids))
        response_data["clients"] = [model_to_dict(c) for c in get_delta(clients_query, last_sync)]

        # 3. Tasks
        tasks_query = db.query(LawTasks).filter(LawTasks.office_id == office_id, LawTasks.case_id.in_(case_ids))
        response_data["tasks"] = [model_to_dict(c) for c in get_delta(tasks_query, last_sync)]

        # 4. Hearings
        hearings_query = db.query(LawHearings).filter(LawHearings.office_id == office_id, LawHearings.case_id.in_(case_ids))
        response_data["hearings"] = [model_to_dict(c) for c in get_delta(hearings_query, last_sync)]

        # 5. Documents
        docs_query = db.query(LawDocuments).filter(LawDocuments.office_id == office_id, LawDocuments.case_id.in_(case_ids))
        response_data["documents"] = [model_to_dict(c) for c in get_delta(docs_query, last_sync)]

    return response_data
