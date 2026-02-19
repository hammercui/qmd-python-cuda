import sqlite3
import os
import re
import sqlite_vec
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from .schema import SCHEMA, FTS_SCHEMA, TRIGGERS

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, db_path: str = "qmd.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        # Load sqlite-vec extension
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys=ON")

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
                (name, path, glob_pattern),
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
    def upsert_document(
        self,
        collection: str,
        path: str,
        doc_hash: str,
        title: str,
        content: str,
        context: Optional[str] = None,
    ):
        with self._get_connection() as conn:
            # 1. Upsert content
            conn.execute(
                "INSERT OR IGNORE INTO content (hash, doc, created_at) VALUES (?, ?, datetime('now'))",
                (doc_hash, content),
            )

            # 2. Upsert document metadata
            conn.execute(
                """
                INSERT INTO documents (collection, path, hash, title, created_at, modified_at)
                VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(collection, path) DO UPDATE SET
                    hash = excluded.hash,
                    title = excluded.title,
                    modified_at = excluded.modified_at,
                    active = 1
                """,
                (collection, path, doc_hash, title),
            )
            conn.commit()

    def get_document_by_hash(self, doc_hash: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT d.*, c.doc FROM documents d JOIN content c ON d.hash = c.hash WHERE d.hash = ?",
                (doc_hash,),
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
                "unique_contents": content_count,
            }

    def list_files(
        self, collection: Optional[str] = None, path_prefix: Optional[str] = None
    ) -> List[Dict[str, Any]]:
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

    def get_document_by_path(
        self, collection: str, path: str
    ) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT d.*, c.doc as content FROM documents d JOIN content c ON d.hash = c.hash WHERE d.collection = ? AND d.path = ? AND d.active = 1",
                (collection, path),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_detailed_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            stats = self.get_stats()

            # Index file size
            db_size = (
                os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            )

            # Count unique hashes from active documents (consistent with what `embed` processes)
            total_content = conn.execute(
                "SELECT count(DISTINCT hash) FROM documents WHERE active = 1"
            ).fetchone()[0]

            # Embedded count limited to active document hashes
            embedded_count = conn.execute(
                """
                SELECT count(DISTINCT cv.hash)
                FROM content_vectors cv
                WHERE cv.hash IN (SELECT DISTINCT hash FROM documents WHERE active = 1)
                """
            ).fetchone()[0]

            # Orphaned content: rows in content with no active document reference
            orphaned_content = conn.execute(
                """
                SELECT count(*) FROM content c
                WHERE NOT EXISTS (
                    SELECT 1 FROM documents d WHERE d.hash = c.hash AND d.active = 1
                )
                """
            ).fetchone()[0]

            # Collection stats
            cursor = conn.execute(
                "SELECT collection, count(*) as count FROM documents WHERE active = 1 GROUP BY collection"
            )
            col_stats = {row["collection"]: row["count"] for row in cursor.fetchall()}

            # Last modified (approximate for index age)
            last_mod = conn.execute(
                "SELECT MAX(modified_at) FROM documents"
            ).fetchone()[0]

            stats.update(
                {
                    "db_size": db_size,
                    "embedded_contents": embedded_count,
                    "total_contents": total_content,
                    "orphaned_content": orphaned_content,
                    "collection_details": col_stats,
                    "last_index_update": last_mod,
                }
            )
            return stats

    def rename_collection(self, old_name: str, new_name: str):
        with self._get_connection() as conn:
            # Check if new name exists
            exists = conn.execute(
                "SELECT 1 FROM collections WHERE name = ?", (new_name,)
            ).fetchone()
            if exists:
                raise ValueError(f"Collection '{new_name}' already exists")

            conn.execute(
                "UPDATE collections SET name = ? WHERE name = ?", (new_name, old_name)
            )
            conn.execute(
                "UPDATE documents SET collection = ? WHERE collection = ?",
                (new_name, old_name),
            )
            conn.execute(
                "UPDATE path_contexts SET collection = ? WHERE collection = ?",
                (new_name, old_name),
            )
            conn.commit()

    def get_all_active_documents(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT d.*, c.doc as content FROM documents d JOIN content c ON d.hash = c.hash WHERE d.active = 1"
            )
            return [dict(row) for row in cursor.fetchall()]

    # Path context operations
    def set_path_context(self, collection: str, path: str, context: str):
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO path_contexts (collection, path, context)
                VALUES (?, ?, ?)
                ON CONFLICT(collection, path) DO UPDATE SET context = excluded.context
                """,
                (collection, path, context),
            )
            conn.commit()

    def list_path_contexts(
        self, collection: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            if collection:
                cursor = conn.execute(
                    "SELECT * FROM path_contexts WHERE collection = ?", (collection,)
                )
            else:
                cursor = conn.execute("SELECT * FROM path_contexts")
            return [dict(row) for row in cursor.fetchall()]

    def remove_path_context(self, collection: str, path: str):
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM path_contexts WHERE collection = ? AND path = ?",
                (collection, path),
            )
            conn.commit()

    def get_context_for_path(self, collection: str, path: str) -> str:
        """Get the inherited context for a path.
        It finds all parent paths that have a context and joins them.
        """
        # path is relative to collection root, e.g. "docs/api/index.md"
        parts = path.split("/")
        contexts = []

        with self._get_connection() as conn:
            # Check for root context (empty path or ".")
            cursor = conn.execute(
                "SELECT context FROM path_contexts WHERE collection = ? AND (path = '' OR path = '.')",
                (collection,),
            )
            row = cursor.fetchone()
            if row:
                contexts.append(row["context"])

            # Check for each parent directory
            current_path = ""
            for i in range(len(parts) - 1):  # exclude the file itself
                if current_path:
                    current_path += "/" + parts[i]
                else:
                    current_path = parts[i]

                cursor = conn.execute(
                    "SELECT context FROM path_contexts WHERE collection = ? AND path = ?",
                    (collection, current_path),
                )
                row = cursor.fetchone()
                if row:
                    contexts.append(row["context"])

        return "\n".join(contexts) if contexts else ""

    # ========== Vector Embedding Methods ==========

    def ensure_vec_table(self, dimensions: int) -> None:
        """
        动态创建 vectors_vec 虚拟表，或验证现有表维度是否匹配。

        Args:
            dimensions: 向量维度（Jina ZH 为 768）
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='vectors_vec'"
            ).fetchone()

            if row:
                # Parse existing dimensions from CREATE statement
                match = re.search(r"float\[(\d+)\]", row["sql"])
                existing_dims = int(match.group(1)) if match else None
                has_hash_seq = "hash_seq" in row["sql"]
                has_cosine = "distance_metric=cosine" in row["sql"]

                if existing_dims == dimensions and has_hash_seq and has_cosine:
                    return  # Already exists and correct

                # Drop and recreate if dimensions mismatch
                conn.execute("DROP TABLE IF EXISTS vectors_vec")

            # Create new vectors_vec table
            conn.execute(f"""
                CREATE VIRTUAL TABLE vectors_vec USING vec0(
                    hash_seq TEXT PRIMARY KEY,
                    embedding float[{dimensions}] distance_metric=cosine
                )
            """)
            conn.commit()

    def insert_embedding(
        self,
        doc_hash: str,
        seq: int,
        pos: int,
        embedding: bytes,
        model: str = "BAAI/bge-m3",
        embedded_at: Optional[str] = None,
    ) -> None:
        """
        写入 chunk 级向量元数据到 content_vectors 表。

        Args:
            doc_hash: 文档 hash
            seq: chunk 序号
            pos: chunk 在原文中的字符位置
            embedding: 向量数据（bytes 格式）
            model: 模型名称
            embedded_at: 时间戳（默认 datetime('now')）
        """
        if embedded_at is None:
            embedded_at = datetime.now().isoformat()

        with self._get_connection() as conn:
            # Insert metadata
            conn.execute(
                """
                INSERT OR REPLACE INTO content_vectors (hash, seq, pos, model, embedded_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (doc_hash, seq, pos, model, embedded_at),
            )

            # Insert vector — vec0 virtual tables do NOT support INSERT OR REPLACE,
            # so we must DELETE first then INSERT.
            hash_seq = f"{doc_hash}_{seq}"
            conn.execute(
                "DELETE FROM vectors_vec WHERE hash_seq = ?",
                (hash_seq,),
            )
            conn.execute(
                "INSERT INTO vectors_vec VALUES (?, ?)",
                (hash_seq, embedding),
            )

            conn.commit()

    def clear_all_embeddings(self) -> None:
        """
        清空所有向量数据（用于重建）。

        注意：如果 vectors_vec 表不存在（旧数据库），会自动忽略。
        建议在升级后删除旧数据库重新索引。
        """
        with self._get_connection() as conn:
            # 清空 content_vectors 表
            conn.execute("DELETE FROM content_vectors")

            # 尝试清空 vectors_vec 表（如果存在）
            try:
                conn.execute("DELETE FROM vectors_vec")
            except sqlite3.OperationalError as e:
                if "no such table" in str(e):
                    # 表不存在，这是旧数据库的正常情况
                    logger.warning(
                        "vectors_vec table does not exist - old database detected"
                    )
                else:
                    raise

            conn.commit()

    def get_hashes_for_embedding(self, limit: Optional[int] = None) -> List[str]:
        """
        获取未 embed 的文档 hash 列表。

        Args:
            limit: 限制返回数量（可选）

        Returns:
            List of doc_hash
        """
        with self._get_connection() as conn:
            sql = """
                SELECT DISTINCT d.hash
                FROM documents d
                LEFT JOIN content_vectors cv ON d.hash = cv.hash
                WHERE d.active = 1 AND cv.hash IS NULL
            """
            if limit:
                sql += f" LIMIT {limit}"

            cursor = conn.execute(sql)
            return [row["hash"] for row in cursor.fetchall()]

    def count_hashes_needing_embedding(self) -> int:
        """Count distinct active document hashes that have no embedding yet."""
        with self._get_connection() as conn:
            return conn.execute(
                """
                SELECT count(DISTINCT d.hash)
                FROM documents d
                LEFT JOIN content_vectors cv ON d.hash = cv.hash
                WHERE d.active = 1 AND cv.hash IS NULL
                """
            ).fetchone()[0]

    def get_chunks_for_hash(self, doc_hash: str) -> List[Dict[str, Any]]:
        """
        获取文档的所有 chunks（用于重新 embed）。

        Args:
            doc_hash: 文档 hash

        Returns:
            List of {"hash", "seq", "pos", "doc"}
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT d.hash, c.doc
                FROM documents d
                JOIN content c ON d.hash = c.hash
                WHERE d.hash = ? AND d.active = 1
                """,
                (doc_hash,),
            )
            row = cursor.fetchone()

            if not row:
                return []

            # Use chunker to split document
            from qmd.utils.chunker import chunk_document

            chunks = chunk_document(row["doc"])

            return [
                {
                    "hash": doc_hash,
                    "seq": chunk["seq"],
                    "pos": chunk["pos"],
                    "doc": chunk["text"],
                }
                for chunk in chunks
            ]
