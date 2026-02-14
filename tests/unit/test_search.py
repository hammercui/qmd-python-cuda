import pytest
from qmd.database.manager import DatabaseManager
from qmd.search.fts import FTSSearcher
from qmd.search.vector import VectorSearch
from qmd.search.hybrid import HybridSearcher
import os
import shutil

@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test_qmd.db")
    manager = DatabaseManager(db_path)
    yield manager
    # Connection should be closed by garbage collector or we could add a close() method

@pytest.fixture
def vector_db(tmp_path):
    db_dir = str(tmp_path / "vector_db")
    vs = VectorSearch(db_dir)
    yield vs

def test_fts_search(db):
    db.add_collection("test", "path", "*.md")
    db.upsert_document("test", "file1.md", "hash1", "Title 1", "Content about Python")
    
    searcher = FTSSearcher(db)
    results = searcher.search("Python")
    assert len(results) > 0
    assert results[0]["title"] == "Title 1"

def test_vector_search(vector_db):
    docs = [
        {"id": "1", "content": "Python programming", "metadata": {"title": "Python"}},
        {"id": "2", "content": "Java development", "metadata": {"title": "Java"}}
    ]
    vector_db.add_documents("test", docs)
    
    results = vector_db.search("coding in python", "test")
    assert len(results) > 0
    assert "Python" in results[0].metadata["title"]

def test_hybrid_search(db, tmp_path):
    # This might be tricky because HybridSearcher creates its own VectorSearch
    # but we can pass the dir
    db.add_collection("test", "path", "*.md")
    db.upsert_document("test", "file1.md", "hash1", "Title 1", "Python is great")
    
    vector_dir = str(tmp_path / "hybrid_vector_db")
    hybrid = HybridSearcher(db, vector_db_dir=vector_dir)
    # Need to add to vector db too
    hybrid.vector.add_documents("test", [
        {"id": "test:file1.md", "content": "Python is great", "metadata": {"title": "Title 1"}}
    ])
    
    results = hybrid.search("Python", collection="test")
    assert len(results) > 0
    assert results[0]["title"] == "Title 1"
