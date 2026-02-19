from typing import List, Dict, Any, Optional, Callable
from .fts import FTSSearcher
from .vector import VectorSearch, SearchResult
from ..database.manager import DatabaseManager
from collections import defaultdict


class HybridSearcher:
    """
    Hybrid search combining BM25 and Vector search using RRF.

    Args:
        db: Database manager
        vector_db_dir: Directory for ChromaDB persistence
        mode: Embedding mode - "auto", "standalone", or "server"
        server_url: MCP Server URL (used when mode="server")
        embed_fn: Optional callable (text -> embedding) to inject into VectorSearch.
                  When provided, mode/server_url are ignored for vector embedding.
    """

    def __init__(
        self,
        db: DatabaseManager,
        vector_db_dir: Optional[str] = None,
        mode: str = "auto",
        server_url: str = "http://localhost:18765",
        embed_fn: Optional[Callable[[str], List[float]]] = None,
    ):
        self.fts = FTSSearcher(db)
        self.vector = VectorSearch(
            vector_db_dir,
            mode=mode,
            server_url=server_url,
            embed_fn=embed_fn,
        )
        self.db = db

    def search(
        self, query: str, collection: Optional[str] = None, limit: int = 10, k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search using Reciprocal Rank Fusion (RRF).
        score = sum(1 / (k + rank))
        """
        # 1. Get BM25 results
        # SQLite BM25 rank: lower is better. Results are already sorted.
        fts_results = self.fts.search(query, limit=limit * 2)
        if collection:
            fts_results = [r for r in fts_results if r["collection"] == collection]

        # 2. Get Vector results
        # Vector score: higher is better. Results are already sorted.
        # collection=None → VectorSearch.search() will search ALL collections
        vector_results = self.vector.search(
            query, collection_name=collection or None, limit=limit * 2
        )

        # 3. RRF Fusion
        scores = defaultdict(float)
        doc_info = {}

        # Process FTS results
        for rank, res in enumerate(fts_results, 1):
            doc_id = f"{res['collection']}:{res['path']}"
            scores[doc_id] += 1.0 / (k + rank)
            doc_info[doc_id] = {
                "title": res["title"],
                "collection": res["collection"],
                "path": res["path"],
                "content": res.get(
                    "content", ""
                ),  # FTS might not have full content by default
                "type": "fts",
            }

        # Process Vector results
        for rank, res in enumerate(vector_results, 1):
            doc_id = f"{res.collection}:{res.path}"
            scores[doc_id] += 1.0 / (k + rank)
            if doc_id not in doc_info:
                doc_info[doc_id] = {
                    "title": res.metadata.get("title", "N/A"),
                    "collection": res.collection,
                    "path": res.path,
                    "content": res.content,
                    "type": "vector",
                }
            else:
                doc_info[doc_id]["type"] = "hybrid"

        # 4. Sort and format
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        final_results = []
        for doc_id, score in sorted_ids[:limit]:
            info = doc_info[doc_id]
            final_results.append({"id": doc_id, "score": score, **info})

        return final_results
