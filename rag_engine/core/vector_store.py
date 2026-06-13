"""
ChromaDB Vector Store - Lazy Loading
إدارة تخزين وبحث النصوص القانونية في قاعدة بيانات متجهة (Vector DB) محلية

تحسين: Lazy Loading الكامل — لا يتصل بـ ChromaDB ولا يُحمَّل أي نموذج
عند استيراد الملف. يتم الاتصال فقط عند أول استخدام فعلي.
هذا يضمن بدء تشغيل الخادم فوراً على Railway دون أي تأخير.
"""
import uuid
from typing import List, Dict, Any

from ..config import VECTOR_DB_DIR, CHROMA_COLLECTION_NAME


class VectorStore:
    def __init__(self):
        # Lazy: لا نتصل بـ ChromaDB الآن، بل عند أول استخدام
        self._client = None
        self._collection = None

    def _get_collection(self):
        """الاتصال بـ ChromaDB عند الحاجة الفعلية فقط (Lazy Init)"""
        if self._collection is None:
            try:
                # ChromaDB sqlite3 override للإنتاج
                try:
                    __import__('pysqlite3')
                    import sys
                    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
                except ImportError:
                    pass

                import chromadb
                from chromadb.config import Settings
                self._client = chromadb.PersistentClient(
                    path=str(VECTOR_DB_DIR),
                    settings=Settings(anonymized_telemetry=False)
                )
                self._collection = self._client.get_or_create_collection(
                    name=CHROMA_COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"}
                )
                print("[VectorStore] ChromaDB connected successfully.")
            except Exception as e:
                print(f"[VectorStore] ChromaDB init error: {e}")
                raise
        return self._collection

    @property
    def collection(self):
        """خاصية للوصول الآمن للـ collection مع Lazy Init"""
        return self._get_collection()

    def add_document(self, document_id: int, text: str, metadata: Dict[str, Any] = None):
        """
        يستقبل نصاً كاملاً (مثل قانون أو حكم)، يقطعه، ويخزنه في الـ Vector DB
        """
        from .embedder import embedder
        from .chunker import chunker

        if not metadata:
            metadata = {}

        metadata['document_id'] = str(document_id)

        # 1. Chunk the text
        chunks = chunker.chunk_text(text)
        if not chunks:
            return 0

        # 2. Generate Embeddings
        embeddings = embedder.embed_batch(chunks)

        # 3. Prepare IDs and Metadata
        ids = [f"{document_id}_{i}" for i in range(len(chunks))]
        metadatas = []
        for i in range(len(chunks)):
            chunk_meta = metadata.copy()
            chunk_meta['chunk_index'] = i
            metadatas.append(chunk_meta)

        # 4. Insert into ChromaDB
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas
        )

        return len(chunks)

    def semantic_search(self, query: str, n_results: int = 5, filter_meta: Dict[str, Any] = None) -> List[Dict]:
        """يبحث عن السياق الأقرب للسؤال في القوانين"""
        from .embedder import embedder

        query_embedding = embedder.embed_text(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_meta
        )

        formatted_results = []
        if results and results['documents'] and len(results['documents']) > 0:
            docs = results['documents'][0]
            metas = results['metadatas'][0]
            dists = results['distances'][0]

            for i in range(len(docs)):
                formatted_results.append({
                    "text": docs[i],
                    "metadata": metas[i],
                    "distance": dists[i]
                })

        return formatted_results

    def delete_document(self, document_id: int):
        """حذف مستند كامل من الفهرس"""
        self.collection.delete(
            where={"document_id": str(document_id)}
        )

    def index_system_laws_if_needed(self, documents: List[Dict[str, Any]]):
        """
        فهرسة القوانين اليمنية المدمجة في قاعدة البيانات المتجهة (إذا لم تكن مفهرسة بالفعل)
        """
        try:
            # التحقق مما إذا كان هناك أي قانون نظام مسجل بالفعل
            existing = self.collection.get(
                where={"is_system_law": True},
                limit=1
            )
            if existing and existing['ids']:
                print("[VectorStore] System laws already indexed in ChromaDB.")
                return

            print(f"[VectorStore] Indexing {len(documents)} system laws into ChromaDB...")
            
            doc_texts = []
            temp_docs = []
            for idx, doc in enumerate(documents):
                law_name = doc.get("law", "")
                article = doc.get("article", "")
                title = doc.get("title", "")
                text_content = doc.get("text", "")
                keywords = doc.get("keywords", [])
                category = doc.get("category", "")
                
                doc_text = f"قانون {law_name} - مادة {article} ({title}): {text_content}"
                if keywords:
                    doc_text += f"\nالكلمات المفتاحية: {', '.join(keywords)}"
                
                doc_texts.append(doc_text)
                temp_docs.append((f"system_law_{idx}", law_name, article, title, category))
                
            # توليد المتجهات دفعة واحدة (أسرع بكثير)
            from .embedder import embedder
            print(f"[VectorStore] Generating embeddings in batches...")
            embeddings = embedder.embed_batch(doc_texts)
            
            ids = []
            metadatas = []
            documents_to_add = []
            embeddings_to_add = []
            
            for i, (doc_id, law_name, article, title, category) in enumerate(temp_docs):
                ids.append(doc_id)
                embeddings_to_add.append(embeddings[i])
                documents_to_add.append(doc_texts[i])
                metadatas.append({
                    "is_system_law": True,
                    "document_id": doc_id,
                    "law": law_name,
                    "article": str(article),
                    "title": str(title),
                    "category": str(category),
                    "source": "system_law"
                })
                
                if len(ids) >= 100:
                    self.collection.add(
                        ids=ids,
                        embeddings=embeddings_to_add,
                        documents=documents_to_add,
                        metadatas=metadatas
                    )
                    ids, embeddings_to_add, documents_to_add, metadatas = [], [], [], []
                    
            if ids:
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings_to_add,
                    documents=documents_to_add,
                    metadatas=metadatas
                )
                
            print(f"[VectorStore] Successfully indexed all system laws into ChromaDB.")
        except Exception as e:
            print(f"[VectorStore] Error indexing system laws: {str(e)}")

# Singleton instance
vector_store = VectorStore()

