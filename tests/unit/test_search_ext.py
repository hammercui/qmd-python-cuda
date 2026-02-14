import unittest
from unittest.mock import MagicMock, patch
from qmd.search.hybrid import HybridSearcher
from qmd.search.vector import VectorSearch, SearchResult
from qmd.database.manager import DatabaseManager
import os
import shutil

class TestHybridSearch(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock(spec=DatabaseManager)
        # Mock FTSSearcher and VectorSearch inside HybridSearcher
        with patch('qmd.search.hybrid.FTSSearcher'), \
             patch('qmd.search.hybrid.VectorSearch'):
            self.hybrid = HybridSearcher(self.db)
            self.hybrid.fts.search.return_value = [
                {"collection": "col1", "path": "p1.md", "title": "T1", "content": "C1"}
            ]
            self.hybrid.vector.search.return_value = [
                SearchResult(path="p2.md", collection="col1", content="C2", score=0.8, metadata={"title": "T2"})
            ]

    def test_hybrid_search(self):
        results = self.hybrid.search("test query", limit=10)
        self.assertEqual(len(results), 2)
        # Verify RRF logic (order might depend on k)
        self.assertIn("col1:p1.md", [r["id"] for r in results])
        self.assertIn("col1:p2.md", [r["id"] for r in results])

class TestVectorSearch(unittest.TestCase):
    @patch('chromadb.PersistentClient')
    @patch('qmd.search.vector.LLMEngine')
    def test_vector_add_and_search(self, mock_llm_engine, mock_chroma):
        mock_client = mock_chroma.return_value
        mock_col = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_col
        
        vs = VectorSearch(db_dir="fake_vdb")
        
        # Test add
        docs = [{"id": "1", "content": "hello", "metadata": {"path": "h.md"}}]
        vs.llm.embed_texts.return_value = [[0.1, 0.2]]
        vs.add_documents("test_col", docs)
        
        mock_col.add.assert_called_once()
        
        # Test search
        vs.llm.embed_query.return_value = [0.1, 0.2]
        mock_col.query.return_value = {
            "ids": [["1"]],
            "distances": [[0.1]],
            "documents": [["hello"]],
            "metadatas": [[{"path": "h.md"}]]
        }
        
        results = vs.search("query", "test_col")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].path, "h.md")
        self.assertAlmostEqual(results[0].score, 0.9)
