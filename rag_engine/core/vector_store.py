"""
ChromaDB Vector Store
إدارة تخزين وبحث النصوص القانونية في قاعدة بيانات متجهة (Vector DB) محلية
"""
import chromadb
from chromadb.config import Settings
import uuid
from typing import List, Dict, Any

from ..config import VECTOR_DB_DIR, CHROMA_COLLECTION_NAME
from .embedder import embedder
from .chunker import chunker

class VectorStore:
    def __init__(self):
        # Initialize ChromaDB client in persistent mode (saves to disk)
        self.client = chromadb.PersistentClient(
            path=str(VECTOR_DB_DIR),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create the collection
        self.collection = self.client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"} # Cosine similarity is usually best for semantic text
        )

    def add_document(self, document_id: int, text: str, metadata: Dict[str, Any] = None):
        """
        يستقبل نصاً كاملاً (مثل قانون أو حكم)، يقطعه، ويخزنه في الـ Vector DB
        """
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
        # ChromaDB handles batching automatically in python client
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas
        )
        
        return len(chunks)

    def semantic_search(self, query: str, n_results: int = 5, filter_meta: Dict[str, Any] = None) -> List[Dict]:
        """يبحث عن السياق الأقرب للسؤال في القوانين"""
        # Embed the query
        query_embedding = embedder.embed_text(query)
        
        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_meta # e.g. {"category": "civil_law"}
        )
        
        # Format results
        formatted_results = []
        if results and results['documents'] and len(results['documents']) > 0:
            docs = results['documents'][0]
            metas = results['metadatas'][0]
            dists = results['distances'][0]
            
            for i in range(len(docs)):
                formatted_results.append({
                    "text": docs[i],
                    "metadata": metas[i],
                    "distance": dists[i] # Lower is more similar
                })
                
        return formatted_results

    def delete_document(self, document_id: int):
        """حذف مستند كامل من الفهرس"""
        self.collection.delete(
            where={"document_id": str(document_id)}
        )

# Singleton instance
vector_store = VectorStore()
