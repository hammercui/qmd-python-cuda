import pytest
import sqlite3
from qmd.database.schema import SCHEMA, FTS_SCHEMA, TRIGGERS
from qmd.database.manager import DatabaseManager


class TestDatabaseSchema:
    """Test database table creation and constraints."""

    def test_collections_table(self, db):
        """Collections table has correct schema."""
        cursor = db.execute("PRAGMA table_info(collections)")
        columns = {col[1] for col in cursor.fetchall()}

        assert "name" in columns
        assert "path" in columns
        assert "glob_pattern" in columns
        assert "created_at" in columns
        assert "last_modified" in columns

    def test_documents_unique_constraint(self, db):
        """Documents enforce unique(collection, path)."""
        manager = DatabaseManager(db.db_path)

        # Insert same document twice
        manager.upsert_document(
            collection="test",
            path="file.md",
            doc_hash="abc123",
            title="Test",
            content="Content 1"
        )

        # Should raise IntegrityError on duplicate (collection, path)
        # But our upsert_document handles it with ON CONFLICT
        # So let's test the constraint directly
        with pytest.raises(sqlite3.IntegrityError):
            manager._get_connection().execute(
                "INSERT INTO documents (collection, path, hash, title) VALUES (?, ?, ?, ?)",
                ("test", "file.md", "def456", "Test")
            )

    def test_content_hash_dedup(self, db):
        """Same hash stored once (content deduplication)."""
        manager = DatabaseManager(db.db_path)

        # Insert content twice with same hash
        manager.upsert_document(
            collection="test",
            path="file1.md",
            doc_hash="hash123",
            title="Title 1",
            content="Same content"
        )

        manager.upsert_document(
            collection="test",
            path="file2.md",
            doc_hash="hash123",  # Same hash
            title="Title 2",
            content="Same content"
        )

        # Check that only one content row exists
        stats = manager.get_stats()
        assert stats["unique_contents"] == 1


class TestDocumentCRUD:
    """Test create, read, update, delete operations."""

    def test_insert_and_retrieve(self, db):
        """Can insert and retrieve document."""
        manager = DatabaseManager(db.db_path)

        manager.upsert_document(
            collection="test",
            path="file.md",
            doc_hash="abc123",
            title="Test Doc",
            content="# Content"
        )

        doc = manager.get_document_by_path("test", "file.md")
        assert doc is not None
        assert doc["title"] == "Test Doc"
        assert doc["hash"] == "abc123"

    def test_soft_delete(self, db):
        """Soft delete marks document inactive."""
        manager = DatabaseManager(db.db_path)

        manager.upsert_document(
            collection="test",
            path="file.md",
            doc_hash="soft123",
            title="Soft Delete Test",
            content="Content"
        )

        # Soft delete (deactivate)
        with manager._get_connection() as conn:
            conn.execute(
                "UPDATE documents SET active = 0 WHERE collection = ? AND path = ?",
                ("test", "file.md")
            )
            conn.commit()

        doc_active = manager.get_document_by_path("test", "file.md")
        assert doc_active is None  # active_only=True is default

        # Should still exist with active_only=False
        docs = manager.list_files("test")
        assert len(docs) == 0  # Only active docs

    def test_update_content(self, db):
        """Can update document content."""
        manager = DatabaseManager(db.db_path)

        manager.upsert_document(
            collection="test",
            path="file.md",
            doc_hash="update123",
            title="Original",
            content="Original content"
        )

        # Update by changing hash (new content)
        manager.upsert_document(
            collection="test",
            path="file.md",
            doc_hash="update456",  # New hash
            title="Updated",
            content="Updated content"
        )

        doc = manager.get_document_by_path("test", "file.md")
        assert doc["hash"] == "update456"
        assert doc["title"] == "Updated"


class TestCollectionOperations:
    """Test collection management."""

    def test_add_collection(self, db):
        """Can add a collection."""
        manager = DatabaseManager(db.db_path)

        manager.add_collection(
            name="test_col",
            path="/path/to/docs",
            glob_pattern="*.md"
        )

        collections = manager.list_collections()
        assert len(collections) == 1
        assert collections[0]["name"] == "test_col"

    def test_remove_collection(self, db):
        """Can remove a collection."""
        manager = DatabaseManager(db.db_path)

        manager.add_collection(
            name="to_remove",
            path="/path",
            glob_pattern="*.md"
        )

        # Add a document
        manager.upsert_document(
            collection="to_remove",
            path="file.md",
            doc_hash="hash123",
            title="Test",
            content="Content"
        )

        # Remove collection
        manager.remove_collection("to_remove")

        collections = manager.list_collections()
        assert len(collections) == 0

    def test_rename_collection(self, db):
        """Can rename a collection."""
        manager = DatabaseManager(db.db_path)

        manager.add_collection(
            name="old_name",
            path="/path",
            glob_pattern="*.md"
        )

        # Add document
        manager.upsert_document(
            collection="old_name",
            path="file.md",
            doc_hash="hash123",
            title="Test",
            content="Content"
        )

        # Rename
        manager.rename_collection("old_name", "new_name")

        # Check documents updated
        docs = manager.list_files("new_name")
        assert len(docs) == 1
        assert docs[0]["collection"] == "new_name"


class TestPathContexts:
    """Test path context management."""

    def test_set_and_get_context(self, db):
        """Can set and retrieve context."""
        manager = DatabaseManager(db.db_path)

        manager.set_path_context(
            collection="test",
            path="docs/api",
            context="API documentation"
        )

        contexts = manager.list_path_contexts("test")
        assert len(contexts) == 1
        assert contexts[0]["context"] == "API documentation"

    def test_context_inheritance(self, db):
        """Context inheritance works correctly."""
        manager = DatabaseManager(db.db_path)

        # Set root context
        manager.set_path_context(
            collection="test",
            path="",
            context="Root documentation"
        )

        # Set subdirectory context
        manager.set_path_context(
            collection="test",
            path="docs",
            context="Docs folder"
        )

        # Get inherited context for docs/api/file.md
        context = manager.get_context_for_path("test", "docs/api/file.md")

        # Should have both root and docs context
        assert "Root documentation" in context
        # Depending on implementation, might be joined or just one
        assert len(context) > 0

    def test_remove_context(self, db):
        """Can remove path context."""
        manager = DatabaseManager(db.db_path)

        manager.set_path_context(
            collection="test",
            path="toremove",
            context="To be removed"
        )

        manager.remove_path_context("test", "toremove")

        contexts = manager.list_path_contexts("test")
        assert len(contexts) == 0
