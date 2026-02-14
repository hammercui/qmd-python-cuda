import unittest
import os
import shutil
from qmd.database.manager import DatabaseManager
from qmd.index.crawler import Crawler

class TestQMD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_db = "test_qmd.db"
        cls.test_dir = "test_files"
        if not os.path.exists(cls.test_dir):
            os.makedirs(cls.test_dir)
        
        with open(os.path.join(cls.test_dir, "test1.md"), "w", encoding="utf-8") as f:
            f.write("# Test 1\nContent of test 1")
        with open(os.path.join(cls.test_dir, "test2.md"), "w", encoding="utf-8") as f:
            f.write("# Test 2\nContent of test 2")

    @classmethod
    def tearDownClass(cls):
        import gc
        gc.collect() # Try to force collection of sqlite objects
        try:
            if os.path.exists(cls.test_db):
                os.remove(cls.test_db)
        except PermissionError:
            print(f"Warning: Could not remove {cls.test_db}")
            
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir)

    def setUp(self):
        self.db = DatabaseManager(self.test_db)

    def test_collection_management(self):
        self.db.add_collection("test_col", os.path.abspath(self.test_dir), "**/*.md")
        cols = self.db.list_collections()
        self.assertEqual(len(cols), 1)
        self.assertEqual(cols[0]["name"], "test_col")
        
        self.db.remove_collection("test_col")
        cols = self.db.list_collections()
        self.assertEqual(len(cols), 0)

    def test_crawler_and_indexing(self):
        crawler = Crawler(self.test_dir)
        docs = list(crawler.scan())
        self.assertEqual(len(docs), 2)
        
        for rel_path, content, doc_hash, title in docs:
            self.db.upsert_document("test_col", rel_path, doc_hash, title, content)
            
        stats = self.db.get_stats()
        self.assertEqual(stats["documents"], 2)

    def test_search(self):
        from qmd.search.fts import FTSSearcher
        
        # Index something
        crawler = Crawler(self.test_dir)
        for rel_path, content, doc_hash, title in crawler.scan():
            self.db.upsert_document("test_col", rel_path, doc_hash, title, content)
            
        searcher = FTSSearcher(self.db)
        results = searcher.search("Test")
        self.assertGreater(len(results), 0)
        self.assertIn("Test", results[0]["title"])

if __name__ == "__main__":
    unittest.main()
