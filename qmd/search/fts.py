from typing import List, Dict, Any
from ..database.manager import DatabaseManager

class FTSSearcher:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        # Sanitize query for FTS5
        # Escape double quotes and wrap in quotes to handle special characters
        sanitized_query = query.replace('"', '""')
        if sanitized_query:
             # Using double quotes around the query string is a common way to avoid syntax errors in FTS5
             # for input containing characters like -, *, etc.
             fts_query = f'"{sanitized_query}"'
        else:
             return []

        with self.db._get_connection() as conn:
            try:
                cursor = conn.execute(
                    """
                    SELECT 
                        d.id, 
                        d.collection, 
                        d.path, 
                        d.hash, 
                        d.title,
                        c.doc as content
                    FROM documents_fts
                    JOIN documents d ON documents_fts.rowid = d.id
                    JOIN content c ON d.hash = c.hash
                    WHERE documents_fts MATCH ?
                    ORDER BY bm25(documents_fts)
                    LIMIT ?
                    """,
                    (fts_query, limit)
                )
                results = [dict(row) for row in cursor.fetchall()]
            except Exception as e:
                # Fallback to a simpler query if FTS fails
                # This handles cases where even quoting doesn't help
                print(f"FTS search error: {e}")
                return []
            
            # Add rank and snippet
            for i, res in enumerate(results, 1):
                res["rank"] = i
                # Simple snippet: first 100 chars with query highlighted
                content = res.get("content", "")
                # Use the original query for highlighting
                start = content.lower().find(query.lower())
                if start != -1:
                    snippet = content[max(0, start-30):start+len(query)+30]
                    res["snippet"] = f"...{snippet}..."
                else:
                    res["snippet"] = content[:100] + "..."
            
            return results
