from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List
import os
import shutil
import uuid
from pathlib import Path

from database.database import get_db, SessionLocal
from database.models import AccessProfiles, KnowledgeDocument, DocumentChunkMetadata
from dependencies import get_current_user, check_user_permission
from core.security import validate_file_signature
from core.rate_limiter import is_rate_limited, record_attempt

# RAG Engine Imports
from rag_engine.config import KNOWLEDGE_DATA_DIR, SUPPORTED_EXTENSIONS
from rag_engine.loaders.pdf_loader import document_loader
from rag_engine.core.vector_store import vector_store
from rag_engine.services.analyzer_service import analyzer_service
from rag_engine.services.summarizer_service import summarizer_service
from rag_engine.services.drafter_service import drafter_service
from rag_engine.services.db_integration import db_integration

router = APIRouter(
    prefix="/api/rag",
    tags=["RAG Engine"]
)


def _authorize_ai_processing(request: Request, user: AccessProfiles) -> None:
    if not user or not user.office_id or not check_user_permission(user, "knowledge", "view"):
        raise HTTPException(status_code=403, detail="لا تملك صلاحية استخدام معالجة المستندات")
    client_ip = request.client.host if request.client else "unknown"
    if is_rate_limited(client_ip, "rag_ai_processing", max_attempts=10, window_seconds=3600):
        raise HTTPException(status_code=429, detail="تجاوزت حد معالجة المستندات. حاول لاحقاً.")
    record_attempt(client_ip, "rag_ai_processing")

# ---------------------------------------------------------
# Background Task for Processing Documents
# ---------------------------------------------------------
def process_document_bg(document_id: int, file_path: str):
    db = SessionLocal()
    try:
        # 1. Fetch document record
        doc_record = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
        if not doc_record:
            return
            
        doc_record.status = 'indexing'
        db.commit()
        
        # 2. Extract Text
        text = document_loader.load_file(file_path)
        if text.startswith("Error"):
            doc_record.status = 'failed'
            db.commit()
            print(f"Extraction Error for {document_id}: {text}")
            return
            
        # 3. Add to Vector DB
        metadata = {
            "category": doc_record.category,
            "file_name": doc_record.file_name,
            "office_id": int(doc_record.office_id),
            "is_system_law": False,
        }
        num_chunks = vector_store.add_document(document_id, text, metadata)
        
        # 4. Update Database
        doc_record.chunk_count = num_chunks
        doc_record.status = 'indexed'
        db.commit()
        print(f"Successfully indexed document {document_id} into {num_chunks} chunks.")
        
    except Exception as e:
        print(f"Error processing document {document_id} in background: {str(e)}")
        # Optionally set status to failed if db is still available
        try:
            doc_record = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
            if doc_record:
                doc_record.status = 'failed'
                db.commit()
        except:
            pass
    finally:
        db.close()


async def _save_validated_upload(upload: UploadFile, prefix: str) -> str:
    ext = os.path.splitext(upload.filename or "")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="نوع الملف غير مدعوم")
    data = await upload.read(20 * 1024 * 1024 + 1)
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="حجم الملف يتجاوز 20 ميجابايت")
    if not validate_file_signature(data, ext.lstrip(".")):
        raise HTTPException(status_code=400, detail="محتوى الملف لا يطابق امتداده")
    path = f"temp_{prefix}_{uuid.uuid4().hex}{ext}"
    with open(path, "wb") as output:
        output.write(data)
    return path


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------

@router.post("/upload")
async def upload_knowledge_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str = Form(...),
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user)
):
    """رفع مستند قانوني (قانون، حكم) إلى قاعدة المعرفة وفهرسته بالخلفية"""
    if not current_user:
        raise HTTPException(status_code=401, detail="غير مصرح")
        
    if not current_user.office_id or not check_user_permission(current_user, "knowledge", "add"):
        raise HTTPException(status_code=403, detail="غير مصرح برفع مستندات المعرفة")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"نوع الملف غير مدعوم. المسموح: {SUPPORTED_EXTENSIONS}")
    from rag_engine.config import LEGAL_CATEGORIES
    if category not in LEGAL_CATEGORIES:
        raise HTTPException(status_code=400, detail="قسم المعرفة غير صالح")

    file_bytes = await file.read(20 * 1024 * 1024 + 1)
    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="حجم الملف يتجاوز 20 ميجابايت")
    if not validate_file_signature(file_bytes, ext.lstrip(".")):
        raise HTTPException(status_code=400, detail="محتوى الملف لا يطابق امتداده")

    # إنشاء مجلد القسم بعد التحقق من القسم لتجنب اجتياز المسار.
    category_dir = Path(KNOWLEDGE_DATA_DIR) / category
    os.makedirs(category_dir, exist_ok=True)
    
    # اسم ملف فريد
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = category_dir / unique_filename
    
    # حفظ الملف
    with open(file_path, "wb") as buffer:
        buffer.write(file_bytes)
        
    # إنشاء سجل في قاعدة البيانات
    new_doc = KnowledgeDocument(
        office_id=current_user.office_id,
        file_name=file.filename,
        file_path=str(file_path),
        file_type=ext.replace('.', ''),
        category=category,
        status='pending',
        document_hash=unique_filename,
        uploaded_by=current_user.id
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    
    # تشغيل عملية الفهرسة في الخلفية (Background Task)
    background_tasks.add_task(process_document_bg, new_doc.id, str(file_path))
    
    return {
        "success": True, 
        "message": "تم رفع المستند وجاري فهرسته.", 
        "document_id": new_doc.id
    }


@router.post("/add-text")
async def add_knowledge_text(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    category: str = Form(...),
    content: str = Form(...),
    keywords: Optional[str] = Form(None),
    source_reference: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user)
):
    """إضافة سابقة قضائية أو مادة أو استشارة كنص مباشر إلى قاعدة المعرفة"""
    if not current_user:
        raise HTTPException(status_code=401, detail="غير مصرح")
    if not current_user.office_id or not check_user_permission(current_user, "knowledge", "add"):
        raise HTTPException(status_code=403, detail="غير مصرح بإضافة نصوص لقاعدة المعرفة")

    if not title or not title.strip() or not content or not content.strip():
        raise HTTPException(status_code=400, detail="العنوان والمحتوى مطلوبان")

    from rag_engine.config import LEGAL_CATEGORIES
    if category not in LEGAL_CATEGORIES:
        raise HTTPException(status_code=400, detail="قسم المعرفة غير صالح")

    # حفظ النص كملف txt في مجلد القسم
    category_dir = Path(KNOWLEDGE_DATA_DIR) / category
    os.makedirs(category_dir, exist_ok=True)
    unique_filename = f"text_{uuid.uuid4().hex}.txt"
    file_path = category_dir / unique_filename

    full_payload = f"العنوان: {title.strip()}\n"
    if source_reference:
        full_payload += f"المرجع/السند: {source_reference.strip()}\n"
    if keywords:
        full_payload += f"الكلمات الدلالية: {keywords.strip()}\n"
    full_payload += f"\nالمحتوى القانوني:\n{content.strip()}"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(full_payload)

    new_doc = KnowledgeDocument(
        office_id=current_user.office_id,
        file_name=title.strip()[:200],
        file_path=str(file_path),
        file_type="txt",
        category=category,
        status="pending",
        document_hash=unique_filename,
        uploaded_by=current_user.id
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    background_tasks.add_task(process_document_bg, new_doc.id, str(file_path))

    return {
        "success": True,
        "message": "تم حفظ النص القانوني وجاري فهرسته في قاعدة المعرفة.",
        "document_id": new_doc.id
    }


@router.get("/documents")
async def get_knowledge_documents(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user)
):
    """عرض المستندات المرفوعة وحالتها مع إحصائيات المعرفة"""
    if not current_user:
        raise HTTPException(status_code=401)
    if not current_user.office_id or not check_user_permission(current_user, "knowledge", "view"):
        raise HTTPException(status_code=403, detail="غير مصرح بعرض مستندات المعرفة")

    query = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.office_id == current_user.office_id,
        KnowledgeDocument.is_deleted == 0
    )
    if category and category.strip():
        query = query.filter(KnowledgeDocument.category == category.strip())

    docs = query.order_by(KnowledgeDocument.created_at.desc()).all()

    # حساب الإحصائيات
    total_docs = len(docs)
    indexed_docs = sum(1 for d in docs if d.status == "indexed")
    total_chunks = sum(d.chunk_count or 0 for d in docs)
    failed_docs = sum(1 for d in docs if d.status == "failed")

    return {
        "success": True,
        "stats": {
            "total_docs": total_docs,
            "indexed_docs": indexed_docs,
            "total_chunks": total_chunks,
            "failed_docs": failed_docs
        },
        "data": [{
            "id": d.id,
            "file_name": d.file_name,
            "file_type": d.file_type,
            "category": d.category,
            "status": d.status,
            "chunk_count": d.chunk_count,
            "created_at": d.created_at
        } for d in docs]
    }


@router.delete("/documents/{doc_id}")
async def delete_knowledge_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user)
):
    """حذف مستند من قاعدة المعرفة ومن محرك المتجهات بأمان"""
    if not current_user:
        raise HTTPException(status_code=401)
    if not current_user.office_id or not check_user_permission(current_user, "knowledge", "delete"):
        raise HTTPException(status_code=403, detail="غير مصرح بحذف مستندات المعرفة")

    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.office_id == current_user.office_id,
        KnowledgeDocument.is_deleted == 0
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")

    # حذف من Vector DB
    try:
        vector_store.delete_document(doc_id)
    except Exception as e:
        print(f"Vector delete warning for {doc_id}: {e}")

    # حذف الملف الفعلي إن وجد
    try:
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except Exception as e:
        print(f"File remove warning for {doc_id}: {e}")

    # وسم المستند كمحذوف
    doc.is_deleted = 1
    db.commit()

    return {"success": True, "message": "تم حذف المستند بنجاح من قاعدة المعرفة ومحرك البحث"}


@router.post("/documents/{doc_id}/reindex")
async def reindex_knowledge_document(
    doc_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user)
):
    """إعادة فهرسة مستند في الخلفية"""
    if not current_user:
        raise HTTPException(status_code=401)
    if not current_user.office_id or not check_user_permission(current_user, "knowledge", "edit"):
        raise HTTPException(status_code=403, detail="غير مصرح بإعادة فهرسة المستندات")

    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.office_id == current_user.office_id,
        KnowledgeDocument.is_deleted == 0
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")

    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=400, detail="الملف الفعلي غير متوفر على القرص لإعادة الفهرسة")

    doc.status = "pending"
    db.commit()

    background_tasks.add_task(process_document_bg, doc.id, doc.file_path)
    return {"success": True, "message": "بدأت إعادة الفهرسة في الخلفية"}


@router.post("/search")
async def semantic_search(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user),
):
    """بحث دلالي في القوانين"""
    if not current_user:
        raise HTTPException(status_code=401, detail="غير مصرح")
    if not current_user.office_id or not check_user_permission(current_user, "knowledge", "view"):
        raise HTTPException(status_code=403, detail="غير مصرح بالبحث في قاعدة المعرفة")
    data = await request.json()
    query = data.get("query")
    category_filter = data.get("category", None)
    n_results = data.get("n_results", 5)
    
    if not query:
        return {"success": False, "error": "Query is required"}
    if not isinstance(query, str) or len(query) > 2000:
        raise HTTPException(status_code=400, detail="نص البحث طويل أو غير صالح")
    try:
        n_results = max(1, min(int(n_results), 20))
    except (TypeError, ValueError):
        n_results = 5

    from rag_engine.config import LEGAL_CATEGORIES
    if category_filter and category_filter not in LEGAL_CATEGORIES:
        raise HTTPException(status_code=400, detail="قسم البحث غير صالح")

    # System laws are shared; uploaded materials are strictly scoped to the current office.
    system_filter = {"is_system_law": True}
    office_filter = {"office_id": int(current_user.office_id)} if current_user.office_id else None
    if category_filter:
        system_filter = {"$and": [system_filter, {"category": category_filter}]}
        if office_filter:
            office_filter = {"$and": [office_filter, {"category": category_filter}]}
    results = vector_store.semantic_search(query, n_results=n_results, filter_meta=system_filter)
    if office_filter:
        results.extend(vector_store.semantic_search(query, n_results=n_results, filter_meta=office_filter))
    results.sort(key=lambda item: item.get("distance", 1))
    results = results[:n_results]
    
    return {"success": True, "results": results}



@router.post("/analyze-contract")
async def analyze_contract(
    request: Request,
    file: UploadFile = File(None),
    raw_text: str = Form(None),
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user)
):
    """تحليل عقد كامل باستخدام Gemini AI — دعم رفع ملف أو لصق نص مباشر"""
    _authorize_ai_processing(request, current_user)

    text = ""
    temp_path = None
    try:
        if file and file.filename:
            temp_path = await _save_validated_upload(file, "contract")
            text = document_loader.load_file(temp_path)
        elif raw_text and raw_text.strip():
            text = raw_text.strip()
        else:
            return {"success": False, "error": "يرجى رفع ملف العقد أو إدخال النص لتحليله"}

        if not text or text.startswith("Error"):
            return {"success": False, "error": f"تعذر استخراج النص: {text}"}
        if len(text) > 100_000:
            raise HTTPException(status_code=413, detail="النص يتجاوز الحد المسموح للتحليل")
        analysis = analyzer_service.analyze_contract_ai(text)
        return {"success": True, "analysis": analysis, "text_length": len(text)}
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/detect-risks")
async def detect_contract_risks(
    request: Request,
    file: UploadFile = File(None),
    raw_text: str = Form(None),
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user)
):
    """كشف البنود عالية المخاطر في العقد — دعم رفع ملف أو لصق نص مباشر"""
    _authorize_ai_processing(request, current_user)

    text = ""
    temp_path = None
    try:
        if file and file.filename:
            temp_path = await _save_validated_upload(file, "risk")
            text = document_loader.load_file(temp_path)
        elif raw_text and raw_text.strip():
            text = raw_text.strip()
        else:
            return {"success": False, "error": "يرجى رفع ملف العقد أو إدخال النص لفحص المخاطر"}

        if not text or text.startswith("Error"):
            return {"success": False, "error": f"تعذر استخراج النص: {text}"}
        if len(text) > 100_000:
            raise HTTPException(status_code=413, detail="النص يتجاوز الحد المسموح للتحليل")
        risks = analyzer_service.detect_risks(text)
        return {"success": True, "risks": risks, "text_length": len(text)}
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/compare-contracts")
async def compare_two_contracts(
    request: Request,
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    label1: str = Form(default="النسخة الأولى"),
    label2: str = Form(default="النسخة الثانية"),
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user)
):
    """مقارنة نسختين من العقد وإظهار التعديلات (Document Diff)"""
    _authorize_ai_processing(request, current_user)

    temp1 = await _save_validated_upload(file1, "cmp1")
    temp2 = None
    try:
        temp2 = await _save_validated_upload(file2, "cmp2")

        text1 = document_loader.load_file(temp1)
        text2 = document_loader.load_file(temp2)

        if not text1 or text1.startswith("Error"):
            return {"success": False, "error": f"تعذر قراءة الملف الأول: {text1}"}
        if not text2 or text2.startswith("Error"):
            return {"success": False, "error": f"تعذر قراءة الملف الثاني: {text2}"}

        comparison = analyzer_service.compare_contracts(text1, text2, label1, label2)
        return {"success": True, "comparison": comparison}
    finally:
        for p in (temp1, temp2):
            if p and os.path.exists(p):
                os.remove(p)


@router.post("/summarize")
async def summarize_text(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user),
):
    """تلخيص نص طويل (حكم، قضية)"""
    _authorize_ai_processing(request, current_user)
    data = await request.json()
    text = data.get("text")
    if not text:
        return {"success": False, "error": "Text is required"}
    if not isinstance(text, str) or len(text) > 100_000:
        raise HTTPException(status_code=400, detail="النص طويل أو غير صالح")

    summary = summarizer_service.summarize(text)
    return {"success": True, "summary": summary}
