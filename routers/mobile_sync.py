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
from database.models import LawUserDevices
from dependencies import get_current_user
from core.security import client_records_for_user

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
    if not user.office_id:
        raise HTTPException(status_code=403, detail="الحساب غير مرتبط بمكتب")
    if not req.device_id or len(req.device_id) > 200:
        raise HTTPException(status_code=400, detail="معرف الجهاز غير صالح")
    registered_device = db.query(LawUserDevices).filter(
        LawUserDevices.device_id == req.device_id,
        LawUserDevices.user_id == user.id,
        LawUserDevices.is_active == 1,
        LawUserDevices.is_deleted == 0,
    ).first()
    if not registered_device:
        raise HTTPException(status_code=403, detail="الجهاز غير مسجل لهذا الحساب")

    office_id = user.office_id
    last_sync = req.last_sync
    
    response_data: Dict[str, Any] = {
        "sync_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "cases": [],
        "clients": [],
        "tasks": [],
        "hearings": [],
        "documents": [],
    }

    # Mobile clients receive only fields intended for client-facing workflows.
    # Never serialize internal case summaries, hearing outcomes, staff IDs,
    # internal notes, or storage paths to a client's device.
    client_fields = {
        LawCases: {"id", "case_number", "title", "case_type_key", "status_key", "open_date", "close_date"},
        LawClients: {"id", "case_id", "name", "phone", "email"},
        LawHearings: {"id", "case_id", "title", "hearing_at", "next_hearing_date", "status_key"},
        LawDocuments: {"id", "case_id", "name", "document_type_key", "doc_date", "created_at"},
    }

    def model_to_dict(obj):
        allowed = client_fields.get(type(obj)) if user.role == "موكل" else None
        return {
            column.name: getattr(obj, column.name)
            for column in obj.__table__.columns
            if column.name != "file_path" and (allowed is None or column.name in allowed)
        }

    # 1. Cases
    cases_query = db.query(LawCases).filter(
        LawCases.office_id == office_id,
        LawCases.is_deleted == 0,
    )
    if user.role in ['محامي', 'محامٍ'] and getattr(user, "can_view_all_cases", 0) == 0:
        cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)
    elif user.role == 'موكل':
        client_case_ids = [
            record.case_id for record in client_records_for_user(db, user)
            if record.case_id is not None
        ]
        cases_query = cases_query.filter(
            LawCases.id.in_(client_case_ids) if client_case_ids else LawCases.id == -1
        )
        
    cases = get_delta(cases_query, last_sync)
    response_data["cases"] = [model_to_dict(c) for c in cases]

    # Collect accessible case IDs to filter related data
    case_ids = [c.id for c in cases_query.all()]
    
    if case_ids:
        # 2. Clients
        clients_query = db.query(LawClients).filter(
            LawClients.office_id == office_id,
            LawClients.is_deleted == 0,
            LawClients.case_id.in_(case_ids),
        )
        if user.role == "موكل":
            linked_client_ids = [r.id for r in client_records_for_user(db, user)]
            clients_query = clients_query.filter(
                LawClients.id.in_(linked_client_ids) if linked_client_ids else LawClients.id == -1
            )
        response_data["clients"] = [model_to_dict(c) for c in get_delta(clients_query, last_sync)]

        # Internal task assignments are never exposed to client portal accounts.
        if user.role != "موكل":
            tasks_query = db.query(LawTasks).filter(
                LawTasks.office_id == office_id,
                LawTasks.is_deleted == 0,
                LawTasks.case_id.in_(case_ids),
            )
            if user.role in ['محامي', 'محامٍ']:
                tasks_query = tasks_query.filter(
                    (LawTasks.assignee_user_id == user.id) |
                    (LawTasks.case_id.in_(case_ids))
                )
            response_data["tasks"] = [model_to_dict(c) for c in get_delta(tasks_query, last_sync)]

        # 4. Hearings
        hearings_query = db.query(LawHearings).filter(
            LawHearings.office_id == office_id,
            LawHearings.is_deleted == 0,
            LawHearings.case_id.in_(case_ids),
        )
        response_data["hearings"] = [model_to_dict(c) for c in get_delta(hearings_query, last_sync)]

        # 5. Documents
        docs_query = db.query(LawDocuments).filter(
            LawDocuments.office_id == office_id,
            LawDocuments.is_deleted == 0,
            LawDocuments.case_id.in_(case_ids),
        )
        response_data["documents"] = [model_to_dict(c) for c in get_delta(docs_query, last_sync)]

    return response_data
