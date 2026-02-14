import unittest
import os
from qmd.database.manager import DatabaseManager

class TestContexts(unittest.TestCase):
    def setUp(self):
        self.test_db = "test_contexts.db"
        self.db = DatabaseManager(self.test_db)
    
    def tearDown(self):
        import gc
        gc.collect()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_context_inheritance(self):
        col = "test_col"
        # Root context
        self.db.set_path_context(col, "", "Root Context")
        # Folder context
        self.db.set_path_context(col, "docs", "Docs Context")
        # Subfolder context
        self.db.set_path_context(col, "docs/api", "API Context")
        
        # Test inheritance for a file in API folder
        ctx = self.db.get_context_for_path(col, "docs/api/index.md")
        self.assertIn("Root Context", ctx)
        self.assertIn("Docs Context", ctx)
        self.assertIn("API Context", ctx)
        
        # Test inheritance for a file in root
        ctx = self.db.get_context_for_path(col, "readme.md")
        self.assertEqual(ctx, "Root Context")
        
        # Test inheritance for a file in docs (but not api)
        ctx = self.db.get_context_for_path(col, "docs/intro.md")
        self.assertIn("Root Context", ctx)
        self.assertIn("Docs Context", ctx)
        self.assertNotIn("API Context", ctx)

    def test_remove_context(self):
        col = "test_col"
        self.db.set_path_context(col, "docs", "Docs Context")
        ctx = self.db.get_context_for_path(col, "docs/intro.md")
        self.assertIn("Docs Context", ctx)
        
        self.db.remove_path_context(col, "docs")
        ctx = self.db.get_context_for_path(col, "docs/intro.md")
        self.assertEqual(ctx, "")
