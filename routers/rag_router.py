from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List
import os
import shutil
import uuid
from pathlib import Path

from database.database import get_db
from database.models import User, KnowledgeDocument, DocumentChunkMetadata
from dependencies import get_current_user

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

# ---------------------------------------------------------
# Background Task for Processing Documents
# ---------------------------------------------------------
def process_document_bg(document_id: int, file_path: str, db: Session):
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
            "file_name": doc_record.file_name
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


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------

@router.post("/upload")
async def upload_knowledge_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """رفع مستند قانوني (قانون، حكم) إلى قاعدة المعرفة وفهرسته بالخلفية"""
    if not current_user:
        raise HTTPException(status_code=401, detail="غير مصرح")
        
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"نوع الملف غير مدعوم. المسموح: {SUPPORTED_EXTENSIONS}")
        
    # إنشاء مجلد القسم إذا لم يكن موجوداً
    category_dir = Path(KNOWLEDGE_DATA_DIR) / category
    os.makedirs(category_dir, exist_ok=True)
    
    # اسم ملف فريد
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = category_dir / unique_filename
    
    # حفظ الملف
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
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
    background_tasks.add_task(process_document_bg, new_doc.id, str(file_path), db)
    
    return {
        "success": True, 
        "message": "تم رفع المستند وجاري فهرسته.", 
        "document_id": new_doc.id
    }


@router.get("/documents")
async def get_knowledge_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """عرض المستندات المرفوعة وحالتها"""
    if not current_user:
        raise HTTPException(status_code=401)
        
    docs = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.office_id == current_user.office_id,
        KnowledgeDocument.is_deleted == 0
    ).order_by(KnowledgeDocument.created_at.desc()).all()
    
    return {
        "success": True,
        "data": [{
            "id": d.id,
            "file_name": d.file_name,
            "category": d.category,
            "status": d.status,
            "chunk_count": d.chunk_count,
            "created_at": d.created_at
        } for d in docs]
    }


@router.post("/search")
async def semantic_search(
    request: Request,
    db: Session = Depends(get_db)
):
    """بحث دلالي في القوانين"""
    data = await request.json()
    query = data.get("query")
    category_filter = data.get("category", None)
    n_results = data.get("n_results", 5)
    
    if not query:
        return {"success": False, "error": "Query is required"}
        
    where_filter = {"category": category_filter} if category_filter else None
    
    results = vector_store.semantic_search(query, n_results=n_results, filter_meta=where_filter)
    
    return {"success": True, "results": results}


@router.post("/analyze-contract")
async def analyze_contract(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """استخراج المعلومات الأساسية من عقد"""
    if not current_user:
        raise HTTPException(status_code=401)
        
    # Save temporarily
    temp_path = f"temp_contract_{uuid.uuid4().hex}.pdf"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Extract text
    text = document_loader.load_file(temp_path)
    
    # Analyze
    analysis = analyzer_service.analyze_contract(text)
    
    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)
        
    return {"success": True, "analysis": analysis}


@router.post("/summarize")
async def summarize_text(
    request: Request,
    db: Session = Depends(get_db)
):
    """تلخيص نص طويل (حكم، قضية)"""
    data = await request.json()
    text = data.get("text")
    if not text:
        return {"success": False, "error": "Text is required"}
        
    summary = summarizer_service.summarize(text)
    return {"success": True, "summary": summary}
