import sqlite3
import os
from typing import List, Optional, Dict, Any
from .schema import SCHEMA, FTS_SCHEMA, TRIGGERS

class DatabaseManager:
    def __init__(self, db_path: str = "qmd.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        # Ensure directory exists
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            
        with self._get_connection() as conn:
            conn.executescript(SCHEMA)
            conn.executescript(FTS_SCHEMA)
            conn.executescript(TRIGGERS)
            conn.commit()

    # Collection operations
    def add_collection(self, name: str, path: str, glob_pattern: str):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO collections (name, path, glob_pattern, created_at) VALUES (?, ?, ?, datetime('now'))",
                (name, path, glob_pattern)
            )
            conn.commit()

    def list_collections(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM collections")
            return [dict(row) for row in cursor.fetchall()]

    def remove_collection(self, name: str):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM collections WHERE name = ?", (name,))
            conn.execute("DELETE FROM documents WHERE collection = ?", (name,))
            conn.commit()

    # Document operations
    def upsert_document(self, collection: str, path: str, doc_hash: str, title: str, content: str, context: Optional[str] = None):
        with self._get_connection() as conn:
            # 1. Upsert content
            conn.execute(
                "INSERT OR IGNORE INTO content (hash, doc) VALUES (?, ?)",
                (doc_hash, content)
            )
            
            # 2. Upsert document metadata
            conn.execute(
                """
                INSERT INTO documents (collection, path, hash, title, context, modified_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(collection, path) DO UPDATE SET
                    hash = excluded.hash,
                    title = excluded.title,
                    context = excluded.context,
                    modified_at = excluded.modified_at,
                    active = 1
                """,
                (collection, path, doc_hash, title, context)
            )
            conn.commit()

    def get_document_by_hash(self, doc_hash: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT d.*, c.doc FROM documents d JOIN content c ON d.hash = c.hash WHERE d.hash = ?",
                (doc_hash,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            col_count = conn.execute("SELECT count(*) FROM collections").fetchone()[0]
            doc_count = conn.execute("SELECT count(*) FROM documents").fetchone()[0]
            content_count = conn.execute("SELECT count(*) FROM content").fetchone()[0]
            return {
                "collections": col_count,
                "documents": doc_count,
                "unique_contents": content_count
            }

    def list_files(self, collection: Optional[str] = None, path_prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            query = """
                SELECT d.collection, d.path, d.modified_at, LENGTH(c.doc) as size, d.hash
                FROM documents d
                JOIN content c ON d.hash = c.hash
                WHERE d.active = 1
            """
            params = []
            if collection:
                query += " AND d.collection = ?"
                params.append(collection)
            if path_prefix:
                query += " AND d.path LIKE ?"
                params.append(f"{path_prefix}%")
            
            query += " ORDER BY d.collection, d.path"
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_document_by_path(self, collection: str, path: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT d.*, c.doc as content FROM documents d JOIN content c ON d.hash = c.hash WHERE d.collection = ? AND d.path = ? AND d.active = 1",
                (collection, path)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_detailed_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            stats = self.get_stats()
            
            # Index file size
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            
            # Embedded docs count
            embedded_count = conn.execute("SELECT count(*) FROM content WHERE embedding IS NOT NULL").fetchone()[0]
            total_content = conn.execute("SELECT count(*) FROM content").fetchone()[0]
            
            # Collection stats
            cursor = conn.execute("SELECT collection, count(*) as count FROM documents WHERE active = 1 GROUP BY collection")
            col_stats = {row['collection']: row['count'] for row in cursor.fetchall()}
            
            # Last modified (approximate for index age)
            last_mod = conn.execute("SELECT MAX(modified_at) FROM documents").fetchone()[0]
            
            stats.update({
                "db_size": db_size,
                "embedded_contents": embedded_count,
                "total_contents": total_content,
                "collection_details": col_stats,
                "last_index_update": last_mod
            })
            return stats

    def rename_collection(self, old_name: str, new_name: str):
        with self._get_connection() as conn:
            # Check if new name exists
            exists = conn.execute("SELECT 1 FROM collections WHERE name = ?", (new_name,)).fetchone()
            if exists:
                raise ValueError(f"Collection '{new_name}' already exists")
            
            conn.execute("UPDATE collections SET name = ? WHERE name = ?", (new_name, old_name))
            conn.execute("UPDATE documents SET collection = ? WHERE collection = ?", (new_name, old_name))
            conn.execute("UPDATE path_contexts SET collection = ? WHERE collection = ?", (new_name, old_name))
            conn.commit()

    def get_all_active_documents(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT d.*, c.doc as content, c.embedding FROM documents d JOIN content c ON d.hash = c.hash WHERE d.active = 1"
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_content_embedding(self, doc_hash: str, embedding: bytes):
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE content SET embedding = ? WHERE hash = ?",
                (embedding, doc_hash)
            )
            conn.commit()

    # Path context operations
    def set_path_context(self, collection: str, path: str, context: str):
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO path_contexts (collection, path, context)
                VALUES (?, ?, ?)
                ON CONFLICT(collection, path) DO UPDATE SET context = excluded.context
                """,
                (collection, path, context)
            )
            conn.commit()

    def list_path_contexts(self, collection: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            if collection:
                cursor = conn.execute("SELECT * FROM path_contexts WHERE collection = ?", (collection,))
            else:
                cursor = conn.execute("SELECT * FROM path_contexts")
            return [dict(row) for row in cursor.fetchall()]

    def remove_path_context(self, collection: str, path: str):
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM path_contexts WHERE collection = ? AND path = ?",
                (collection, path)
            )
            conn.commit()

    def get_context_for_path(self, collection: str, path: str) -> str:
        """Get the inherited context for a path.
        It finds all parent paths that have a context and joins them.
        """
        # path is relative to collection root, e.g. "docs/api/index.md"
        parts = path.split('/')
        contexts = []
        
        with self._get_connection() as conn:
            # Check for root context (empty path or ".")
            cursor = conn.execute(
                "SELECT context FROM path_contexts WHERE collection = ? AND (path = '' OR path = '.')",
                (collection,)
            )
            row = cursor.fetchone()
            if row:
                contexts.append(row['context'])
            
            # Check for each parent directory
            current_path = ""
            for i in range(len(parts) - 1): # exclude the file itself
                if current_path:
                    current_path += "/" + parts[i]
                else:
                    current_path = parts[i]
                
                cursor = conn.execute(
                    "SELECT context FROM path_contexts WHERE collection = ? AND path = ?",
                    (collection, current_path)
                )
                row = cursor.fetchone()
                if row:
                    contexts.append(row['context'])
        
        return "\n".join(contexts) if contexts else ""
