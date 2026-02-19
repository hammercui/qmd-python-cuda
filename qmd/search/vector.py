import os
import logging
from pathlib import Path
from typing import Callable, List, Dict, Any, Optional
import chromadb
from pydantic import BaseModel
from qmd.llm.engine import LLMEngine

logger = logging.getLogger(__name__)


def _default_vector_db_dir() -> str:
    """返回与 SQLite DB 同级的向量库绝对路径 ~/.qmd/vector_db。"""
    return str(Path.home() / ".qmd" / "vector_db")


class SearchResult(BaseModel):
    path: str
    collection: str
    content: str
    score: float
    metadata: Dict[str, Any] = {}


class VectorSearch:
    """
    Vector search implementation using ChromaDB.

    Args:
        db_dir: Directory for ChromaDB persistence.
                Defaults to ~/.qmd/vector_db (absolute, shared between
                CLI and server regardless of working directory).
        mode: Embedding mode - "auto", "standalone", or "server"
              - "auto": Auto-detect based on VRAM (default)
              - "standalone": Always use local model
              - "server": Always use MCP Server
        server_url: MCP Server URL (used when mode="server")
    """

    def __init__(
        self,
        db_dir: Optional[str] = None,
        mode: str = "auto",
        server_url: str = "http://localhost:18765",
        embed_fn: Optional[Callable[[str], List[float]]] = None,
    ):
        # Always resolve to an absolute path so CLI and server share the same data
        raw = db_dir or _default_vector_db_dir()
        self.db_dir = str(Path(raw).expanduser().resolve())
        os.makedirs(self.db_dir, exist_ok=True)
        logger.debug("ChromaDB path: %s", self.db_dir)
        self.client = chromadb.PersistentClient(path=self.db_dir)
        # embed_fn takes precedence; falls back to LLMEngine
        self._embed_fn = embed_fn
        self.llm = None if embed_fn else LLMEngine(mode=mode, server_url=server_url)

    def _get_collection(self, collection_name: str):
        """Get or create a ChromaDB collection."""
        return self.client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )

    def _embed_query(self, text: str) -> List[float]:
        """Embed a single query, using injected embed_fn if available."""
        if self._embed_fn:
            return self._embed_fn(text)
        return self.llm.embed_query(text)

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
        if self._embed_fn:
            embeddings = [self._embed_fn(c) for c in contents]
        else:
            embeddings = self.llm.embed_texts(contents)

        collection.add(
            ids=ids, embeddings=embeddings, documents=contents, metadatas=metadatas
        )

    def add_documents_with_embeddings(
        self, collection_name: str, documents: List[Dict[str, Any]]
    ):
        """Add documents with pre-generated embeddings."""
        collection = self._get_collection(collection_name)

        ids = [doc["id"] for doc in documents]
        contents = [doc["content"] for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]
        embeddings = [doc["embedding"] for doc in documents]

        collection.add(
            ids=ids, embeddings=embeddings, documents=contents, metadatas=metadatas
        )

    def _search_one(
        self, query_embedding: List[float], collection_name: str, limit: int
    ) -> List[SearchResult]:
        """Search a single named ChromaDB collection. Returns [] if empty/not ready."""
        collection = self._get_collection(collection_name)
        count = collection.count()
        if count == 0:
            logger.debug("Collection '%s' is empty, skipping.", collection_name)
            return []
        n_results = min(limit, count)
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            err = str(e).lower()
            if "nothing found on disk" in err or "hnsw" in err or "no embeddings" in err:
                logger.warning(
                    "ChromaDB HNSW index not ready for collection '%s': %s",
                    collection_name, e,
                )
                return []
            raise
        search_results = []
        if results["ids"]:
            for i in range(len(results["ids"][0])):
                score = 1.0 - results["distances"][0][i]
                search_results.append(
                    SearchResult(
                        path=results["metadatas"][0][i].get("path", ""),
                        collection=collection_name,
                        content=results["documents"][0][i],
                        score=score,
                        metadata=results["metadatas"][0][i],
                    )
                )
        return search_results

    def search(
        self,
        query: str,
        collection_name: Optional[str] = None,
        limit: int = 5,
    ) -> List[SearchResult]:
        """
        Perform semantic search.

        Args:
            query: Search query string.
            collection_name: ChromaDB collection to search.
                             If None, searches across ALL collections and merges results.
            limit: Maximum number of results to return.

        Returns:
            List of SearchResult sorted by score descending.
        """
        query_embedding = self._embed_query(query)

        if collection_name:
            # Search only the specified collection
            results = self._search_one(query_embedding, collection_name, limit)
        else:
            # Search ALL collections and merge
            all_cols = self.client.list_collections()
            if not all_cols:
                logger.warning(
                    "No ChromaDB collections found in %s. Run 'qmd embed' first.",
                    self.db_dir,
                )
                return []
            results = []
            for col in all_cols:
                partial = self._search_one(query_embedding, col.name, limit)
                results.extend(partial)
            # Merge: sort by score desc, deduplicate by (collection, path), take top-N
            seen: set = set()
            deduped: List[SearchResult] = []
            for r in sorted(results, key=lambda x: x.score, reverse=True):
                key = (r.collection, r.path)
                if key not in seen:
                    seen.add(key)
                    deduped.append(r)
            results = deduped[:limit]

        return results
