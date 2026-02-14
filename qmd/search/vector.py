import os
import chromadb
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from qmd.llm.engine import LLMEngine

class SearchResult(BaseModel):
    path: str
    collection: str
    content: str
    score: float
    metadata: Dict[str, Any] = {}

class VectorSearch:
    """
    Vector search implementation using ChromaDB.
    """
    def __init__(self, db_dir: str = ".qmd_vector_db"):
        self.db_dir = db_dir
        self.client = chromadb.PersistentClient(path=db_dir)
        self.llm = LLMEngine()

    def _get_collection(self, collection_name: str):
        """Get or create a ChromaDB collection."""
        return self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_documents(self, collection_name: str, documents: List[Dict[str, Any]]):
        """
        Add documents to the vector store.
        documents should have: id, content, metadata
        """
        collection = self._get_collection(collection_name)
        
        ids = [doc["id"] for doc in documents]
        contents = [doc["content"] for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]
        
        # Generate embeddings
        embeddings = self.llm.embed_texts(contents)
        
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=contents,
            metadatas=metadatas
        )

    def add_documents_with_embeddings(self, collection_name: str, documents: List[Dict[str, Any]]):
        """Add documents with pre-generated embeddings."""
        collection = self._get_collection(collection_name)
        
        ids = [doc["id"] for doc in documents]
        contents = [doc["content"] for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]
        embeddings = [doc["embedding"] for doc in documents]
        
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=contents,
            metadatas=metadatas
        )

    def search(
        self, 
        query: str, 
        collection_name: str, 
        limit: int = 5
    ) -> List[SearchResult]:
        """Perform semantic search."""
        collection = self._get_collection(collection_name)
        
        query_embedding = self.llm.embed_query(query)
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            include=["documents", "metadatas", "distances"]
        )
        
        search_results = []
        if results["ids"]:
            for i in range(len(results["ids"][0])):
                # ChromaDB distances: lower is better (usually 1-cosine)
                # We want a score where higher is better, or just return distance
                score = 1.0 - results["distances"][0][i]
                
                search_results.append(SearchResult(
                    path=results["metadatas"][0][i].get("path", ""),
                    collection=collection_name,
                    content=results["documents"][0][i],
                    score=score,
                    metadata=results["metadatas"][0][i]
                ))
        
        return search_results
