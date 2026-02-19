"""
Vector search implementation using sqlite-vec (two-step query).

Replaces ChromaDB with sqlite-vec for better performance and
compatibility with TypeScript implementation.
"""

import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from qmd.llm.engine import LLMEngine
from qmd.utils.chunker import embedding_to_bytes

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    filepath: str  # "qmd://collection/path"
    display_path: str  # "collection/path"
    title: str
    body: str
    score: float
    hash: str
    collection: str  # extracted from display_path prefix

    @property
    def path(self) -> str:
        """Document path within the collection (everything after first '/')."""
        parts = self.display_path.split("/", 1)
        return parts[1] if len(parts) > 1 else self.display_path


class VectorSearch:
    """
    Vector search implementation using sqlite-vec.

    Uses two-step query approach to avoid JOIN + MATCH deadlock.
    See: SQLITE_MIGRATION_PLAN.md section 4.1
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        mode: str = "auto",
        server_url: str = "http://localhost:18765",
        embed_fn: Optional[callable] = None,
    ):
        """
        Args:
            db_path: Path to SQLite database (default: ~/.qmd/qmd.db)
            mode: Embedding mode - "auto", "standalone", or "server"
            server_url: MCP Server URL (used when mode="server")
            embed_fn: Optional custom embed function
        """
        if db_path is None:
            from pathlib import Path

            db_path = str(Path.home() / ".qmd" / "qmd.db")

        self.db_path = db_path
        self.embed_fn = embed_fn
        self.llm = None if embed_fn else LLMEngine(mode=mode, server_url=server_url)

    def _embed_query(self, text: str) -> bytes:
        """
        Embed query and convert to bytes for sqlite-vec.

        Returns:
            bytes: float32 little-endian packed embedding
        """
        if self.embed_fn:
            embedding = self.embed_fn(text)
        else:
            embedding = self.llm.embed_query(text)

        return embedding_to_bytes(embedding)

    def search(
        self,
        query: str,
        collection_name: Optional[str] = None,
        limit: int = 5,
    ) -> List[SearchResult]:
        """
        Perform semantic search using sqlite-vec two-step approach.

        Step 1: Query vectors_vec for nearest neighbors (no JOIN)
        Step 2: Fetch document metadata using hash_seq

        Args:
            query: Search query string
            collection_name: Filter by collection (optional, for API compatibility)
            limit: Max results to return

        Returns:
            List of SearchResult sorted by score descending
        """
        import sqlite3
        import sqlite_vec

        # Get query embedding as bytes
        query_bytes = self._embed_query(query)

        # Connect to database and load sqlite-vec
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        try:
            # Step 1: Query vectors_vec (no JOIN - avoids deadlock)
            vec_rows = conn.execute(
                """
                SELECT hash_seq, distance
                FROM vectors_vec
                WHERE embedding MATCH ? AND k = ?
                """,
                (query_bytes, limit * 3),  # Get 3x for dedup
            ).fetchall()

            if not vec_rows:
                return []

            # Extract hash_seqs
            hash_seqs = [row["hash_seq"] for row in vec_rows]
            placeholders = ",".join(["?" for _ in hash_seqs])

            # Step 2: Fetch document metadata with JOIN
            sql = f"""
                SELECT
                    cv.hash || '_' || cv.seq as hash_seq,
                    cv.hash,
                    cv.pos,
                    'qmd://' || d.collection || '/' || d.path as filepath,
                    d.collection || '/' || d.path as display_path,
                    d.title,
                    d.collection,
                    c.doc as body
                FROM content_vectors cv
                JOIN documents d ON d.hash = cv.hash AND d.active = 1
                JOIN content c ON c.hash = d.hash
                WHERE cv.hash || '_' || cv.seq IN ({placeholders})
            """
            params = list(hash_seqs)

            if collection_name:
                sql += " AND d.collection = ?"
                params.append(collection_name)

            doc_rows = conn.execute(sql, params).fetchall()

            # Map hash_seq to distance
            dist_map = {row["hash_seq"]: row["distance"] for row in vec_rows}

            # Merge and dedup by (collection, path)
            seen: set = set()
            results: List[SearchResult] = []

            for row in doc_rows:
                key = (row["collection"], row["display_path"])
                if key in seen:
                    continue

                seen.add(key)
                distance = dist_map.get(row["hash_seq"], 1.0)
                score = 1.0 - distance  # Convert cosine distance to similarity

                results.append(
                    SearchResult(
                        filepath=row["filepath"],
                        display_path=row["display_path"],
                        title=row["title"],
                        body=row["body"],
                        score=score,
                        hash=row["hash"],
                        collection=row["collection"],
                    )
                )

            # Sort by score descending and take top-N
            results.sort(key=lambda x: x.score, reverse=True)
            return results[:limit]

        finally:
            conn.close()

    def add_documents_with_embeddings(
        self, collection_name: str, documents: List[Dict[str, Any]]
    ):
        """
        Legacy method for compatibility - now embeddings are handled
        by DatabaseManager.insert_embedding().

        This method is kept for API compatibility but does nothing.
        """
        logger.warning(
            "add_documents_with_embeddings() is deprecated. "
            "Use DatabaseManager.insert_embedding() instead."
        )
        pass
