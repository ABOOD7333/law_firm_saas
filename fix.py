import os

main_path = os.path.join(os.path.dirname(__file__), "main.py")

with open(main_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_block = """@app.get("/cases/export_report", response_class=HTMLResponse)
async def export_case_report(
    request: Request,
    case_number: str = Query(None),
    case_title: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
    office_id = user.office_id or 1
    query = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)
    
    if user.role in ['محامي', 'محامٍ'] and user.can_view_all_cases == 0:
        query = query.filter(LawCases.lead_lawyer_id == user.id)
        
    if case_number:
        query = query.filter(LawCases.case_number.like(f"%{str(case_number).replace('%', '').replace('_', '')}%"))
    elif case_title:
        query = query.filter(LawCases.title.like(f"%{str(case_title).replace('%', '').replace('_', '')}%"))
        
    if start_date:
        query = query.filter(LawCases.created_at >= f"{start_date} 00:00:00")
    if end_date:
        query = query.filter(LawCases.created_at <= f"{end_date} 23:59:59")
        
    cases_result = query.all()
    
    cases_data = []
    for c in cases_result:
        h_query = db.query(LawHearings).filter(LawHearings.case_id == c.id)
        t_query = db.query(LawTasks).filter(LawTasks.case_id == c.id)
        d_query = db.query(LawDocuments).filter(LawDocuments.case_id == c.id)
        
        if start_date:
            h_query = h_query.filter(LawHearings.hearing_at >= f"{start_date}")
            t_query = t_query.filter(LawTasks.created_at >= f"{start_date} 00:00:00")
            d_query = d_query.filter(LawDocuments.created_at >= f"{start_date} 00:00:00")
        if end_date:
            h_query = h_query.filter(LawHearings.hearing_at <= f"{end_date} 23:59:59")
            t_query = t_query.filter(LawTasks.created_at <= f"{end_date} 23:59:59")
            d_query = d_query.filter(LawDocuments.created_at <= f"{end_date} 23:59:59")
            
        cases_data.append({
            "case": c,
            "hearings": h_query.all(),
            "tasks": t_query.all(),
            "documents": d_query.all()
        })
        
    office = db.query(LawOffices).filter(LawOffices.id == office_id).first()
        
    return templates.TemplateResponse(
        request=request,
        name="case_report.html",
        context={
            "user": user,
            "office": office,
            "cases_data": cases_data,
            "start_date": start_date,
            "end_date": end_date,
            "is_single": bool(case_number or case_title)
        }
    )

@app.get("/cases/{case_id}", response_class=HTMLResponse)
async def case_details_page(case_id: int, request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
    try:
        office_id = user.office_id or 1
        case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
        if not case:
            return HTMLResponse(content="القضية غير موجودة أو لا تملك صلاحية الوصول لها", status_code=404)
            
        # منع المحامي من دخول قضية غير تابعة له
        if user.role in ['محامي', 'محامٍ'] and case.lead_lawyer_id != user.id:
            return HTMLResponse(content="<script>alert('غير مصرح لك بالدخول لهذه القضية'); window.location.href='/cases';</script>", status_code=403)
            
        hearings = db.query(LawHearings).filter(LawHearings.case_id == case_id).order_by(LawHearings.hearing_at.desc()).all()
        lawyer = db.query(AccessProfiles).filter(AccessProfiles.id == case.lead_lawyer_id).first() if case.lead_lawyer_id else None
        
        clients = db.query(LawClients).filter(LawClients.office_id == office_id).all()
        lawyers = db.query(AccessProfiles).filter(AccessProfiles.role.in_(['محامٍ', 'مدير', 'مدير المكتب']), AccessProfiles.office_id == office_id).all()
        
        documents = db.query(LawDocuments).filter(LawDocuments.case_id == case_id).order_by(LawDocuments.created_at.desc()).all()
        
        return templates.TemplateResponse(
            request=request, 
            name="case_details.html", 
            context={"user": user, "case": case, "hearings": hearings, "lawyer": lawyer, "clients": clients, "lawyers": lawyers, "documents": documents, "active_page": "cases"}
        )
    except Exception as e:
        import traceback
        return _safe_error(traceback.format_exc())

@app.post("/cases/{case_id}/edit")
async def edit_case(
    case_id: int,
    request: Request,
    title: str = Form(...),
    case_number: str = Form(...),
    client_id: int = Form(...),
    lead_lawyer_id: int = Form(None),
    status_key: str = Form(...),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
    office_id = user.office_id or 1
    case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
    
    if user.role in ['محامي', 'محامٍ'] and case and case.lead_lawyer_id != user.id:
        return HTMLResponse(content="<script>alert('غير مصرح لك بتعديل هذه القضية'); window.history.back();</script>", status_code=403)
        
    if case:
        case.title = title
        case.case_number = case_number
        case.lead_lawyer_id = lead_lawyer_id
        case.status_key = status_key
        db.commit()
        
        # Check if client was changed/updated
        client = db.query(LawClients).filter(LawClients.id == client_id, LawClients.office_id == office_id).first()
        if client and client.case_id != case.id:
            client.case_id = case.id
            client.case_number = case.case_number
            db.commit()
            
    return RedirectResponse(url=f"/cases/{case_id}", status_code=303)
"""

# The corrupted part starts from @app.get("/cases/{case_id}") which was at line 633, and ends right before @app.get("/hearings")
# Let's find @app.get("/cases/{case_id}")
start_idx = -1
for i, line in enumerate(lines):
    if '@app.get("/cases/{case_id}"' in line:
        start_idx = i
        break

# Let's find @app.get("/hearings")
end_idx = -1
for i, line in enumerate(lines):
    if '@app.get("/hearings"' in line:
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    lines = lines[:start_idx] + [new_block + "\n"] + lines[end_idx:]
    with open(main_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("Fixed main.py successfully!")
else:
    print("Could not find boundaries to fix.")
