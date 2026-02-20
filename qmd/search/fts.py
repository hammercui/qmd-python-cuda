from typing import List, Dict, Any, Optional
from ..database.manager import DatabaseManager
import re


def _sanitize_fts5_term(term: str) -> str:
    """
    Sanitize a single term for FTS5 query.

    Removes characters that could break FTS5 syntax.
    Keeps alphanumeric, unicode characters, and apostrophes.

    Args:
        term: Raw search term

    Returns:
        Sanitized term safe for FTS5 query
    """
    # Remove FTS5 special characters that could cause syntax errors
    # TS version uses /[^\p{L}\p{N}']/gu but Python re doesn't support \p{}
    # This is a conservative approximation that works well
    sanitized = re.sub(r'["\^\(\)\-\:\{\}\[\]!~*]', "", term)
    return sanitized.strip().lower()


def build_fts5_query(query: str) -> Optional[str]:
    """
    Build FTS5 query with prefix matching and AND operator.

    TS implementation (store.ts:1838-1845):
    - Split query on whitespace only
    - Each term gets prefix match ("term"*)
    - Multiple terms joined with AND

    Args:
        query: Raw search query

    Returns:
        FTS5 query string or None if no valid terms
    """
    # Split on whitespace (same as TS version)
    terms = query.split()

    # Sanitize each term
    sanitized_terms = []
    for term in terms:
        sanitized = _sanitize_fts5_term(term)
        if sanitized and len(sanitized) > 0:
            sanitized_terms.append(sanitized)

    if not sanitized_terms:
        return None

    # Single term: "term"* (prefix match)
    if len(sanitized_terms) == 1:
        return f'"{sanitized_terms[0]}"*'

    # Multiple terms: "term1"* AND "term2"* AND ...
    return " AND ".join(f'"{t}"*' for t in sanitized_terms)


class FTSSearcher:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def search(
        self,
        query: str,
        limit: int = 10,
        collection: Optional[str] = None,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Perform BM25 full-text search with weighted scoring.

        TS implementation features:
        - Weighted bm25: title weight 10.0, content weight 1.0
        - Score normalization: 1 / (1 + abs(bm25_score)) -> (0, 1]
        - FTS5 prefix matching for each term

        Args:
            query: Search query string
            limit: Maximum number of results
            collection: Optional collection filter
            min_score: Minimum score threshold (0-1)

        Returns:
            List of results with normalized 'score' field (0-1, higher is better)
        """
        # Build FTS5 query with prefix matching
        fts_query = build_fts5_query(query)
        if not fts_query:
            return []

        with self.db._get_connection() as conn:
            try:
                # Use weighted bm25: title weight 10.0, body weight 1.0
                # FTS5 table has columns: filepath, title, body
                # bm25(documents_fts, weight_filepath, weight_title, weight_body)
                # Lower bm25_score (more negative) = more relevant
                cursor = conn.execute(
                    """
                    SELECT 
                        d.id, 
                        d.collection, 
                        d.path, 
                        d.hash, 
                        d.title,
                        bm25(documents_fts, 1.0, 10.0, 1.0) as bm25_score,
                        snippet(documents_fts, 2, '[b]', '[/b]', '...', 30) as snippet,
                        c.doc as content
                    FROM documents_fts
                    JOIN documents d ON documents_fts.rowid = d.id
                    JOIN content c ON d.hash = c.hash
                    WHERE documents_fts MATCH ?
                    ORDER BY bm25_score
                    LIMIT ?
                    """,
                    (fts_query, limit * 2),  # Get extra for filtering
                )
                rows = cursor.fetchall()
            except Exception as e:
                # Fallback to simpler query if FTS fails
                print(f"FTS search error: {e}")
                return []

            results = []
            for row in rows:
                # Normalize BM25 score: 1 / (1 + abs(score))
                # BM25 returns negative values, more negative = more relevant
                # This converts to (0, 1] range where higher is better
                bm25_raw = row["bm25_score"]
                score = 1.0 / (1.0 + abs(bm25_raw)) if bm25_raw is not None else 0.0

                # Filter by collection if specified
                if collection and row["collection"] != collection:
                    continue

                # Filter by min_score
                if score < min_score:
                    continue

                results.append(
                    {
                        "id": row["id"],
                        "collection": row["collection"],
                        "path": row["path"],
                        "hash": row["hash"],
                        "title": row["title"],
                        "snippet": row["snippet"],
                        "content": row["content"],
                        "score": score,  # Normalized score (0-1)
                    }
                )

            # Sort by score descending and limit
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:limit]
