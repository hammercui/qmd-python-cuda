from typing import List, Dict, Any, Optional, Callable
from .fts import FTSSearcher
from .vector import VectorSearch
from ..database.manager import DatabaseManager
from collections import defaultdict
import math


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

    def _reciprocal_rank_fusion(
        self,
        ranked_lists: List[List[str]],
        weights: Optional[List[float]] = None,
        k: int = 60,
    ) -> Dict[str, float]:
        """
        Compute Reciprocal Rank Fusion scores.

        TS implementation:
        - rank is 0-indexed (rank+1 in denominator)
        - formula: w / (k + rank + 1)
        - Top-rank bonus: +0.05 for rank 0, +0.02 for ranks 1-2

        Args:
            ranked_lists: List of ranked doc_id lists (each list is sorted by relevance)
            weights: Optional weights for each list (default: all 1.0)
            k: RRF constant (default: 60)

        Returns:
            Dict of doc_id -> RRF score
        """
        if weights is None:
            weights = [1.0] * len(ranked_lists)

        # Track: doc_id -> {rrf_score, top_rank}
        doc_scores: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"score": 0.0, "top_rank": math.inf}
        )

        for ranked_list, weight in zip(ranked_lists, weights):
            for rank, doc_id in enumerate(ranked_list):  # rank is 0-indexed
                # RRF contribution: w / (k + rank + 1)
                contribution = weight / (k + rank + 1)
                doc_scores[doc_id]["score"] += contribution
                # Track best rank across all lists
                if rank < doc_scores[doc_id]["top_rank"]:
                    doc_scores[doc_id]["top_rank"] = rank

        # Apply top-rank bonus (TS implementation)
        for doc_id, entry in doc_scores.items():
            top_rank = entry["top_rank"]
            if top_rank == 0:
                # Rank 0 (first position) gets +0.05 bonus
                entry["score"] += 0.05
            elif top_rank <= 2:
                # Ranks 1-2 (positions 2-3) get +0.02 bonus
                entry["score"] += 0.02

        return {doc_id: entry["score"] for doc_id, entry in doc_scores.items()}

    def search(
        self, query: str, collection: Optional[str] = None, limit: int = 10, k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search using Reciprocal Rank Fusion (RRF).

        TS implementation:
        - RRF formula: w / (k + rank + 1) where rank is 0-indexed
        - Top-rank bonus: +0.05 for rank 0, +0.02 for ranks 1-2
        """
        # 1. Get BM25 results (now with normalized scores)
        fts_results = self.fts.search(query, limit=limit * 2, collection=collection)

        # 2. Get Vector results
        # Vector score: higher is better. Results are already sorted.
        # collection=None → VectorSearch.search() will search ALL collections
        vector_results = self.vector.search(
            query, collection_name=collection or None, limit=limit * 2
        )

        # 3. Prepare ranked lists for RRF
        fts_ids = [f"{r['collection']}:{r['path']}" for r in fts_results]
        vec_ids = []
        for res in vector_results:
            parts = res.display_path.split("/", 1)
            col = parts[0] if len(parts) > 1 else ""
            path = parts[1] if len(parts) > 1 else res.display_path
            vec_ids.append(f"{col}:{path}")

        ranked_lists = [fts_ids, vec_ids]
        weights = [1.0, 1.0]  # Equal weight for both

        # 4. Compute RRF scores with top-rank bonus
        rrf_scores = self._reciprocal_rank_fusion(ranked_lists, weights, k)

        # 5. Build doc_info from results
        doc_info = {}

        # From FTS results (now have normalized score)
        for r in fts_results:
            doc_id = f"{r['collection']}:{r['path']}"
            if doc_id not in doc_info:
                doc_info[doc_id] = {
                    "title": r["title"],
                    "collection": r["collection"],
                    "path": r["path"],
                    "content": r.get("content", ""),
                    "fts_score": r.get("score", 0.0),
                    "type": "fts",
                }

        # From Vector results
        for res in vector_results:
            parts = res.display_path.split("/", 1)
            col = parts[0] if len(parts) > 1 else ""
            path = parts[1] if len(parts) > 1 else res.display_path
            doc_id = f"{col}:{path}"
            if doc_id not in doc_info:
                doc_info[doc_id] = {
                    "title": res.title,
                    "collection": col,
                    "path": path,
                    "content": res.body,
                    "vec_score": res.score,
                    "type": "vector",
                }
            else:
                doc_info[doc_id]["type"] = "hybrid"
                doc_info[doc_id]["vec_score"] = res.score

        # 6. Sort by RRF score and format results
        sorted_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        final_results = []
        for doc_id, rrf_score in sorted_ids[:limit]:
            info = doc_info[doc_id]
            final_results.append(
                {
                    "id": doc_id,
                    "score": rrf_score,  # RRF score
                    **{k: v for k, v in info.items() if not k.endswith("_score")},
                }
            )

        return final_results
