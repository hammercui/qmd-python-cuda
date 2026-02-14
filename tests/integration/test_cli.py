import unittest
from click.testing import CliRunner
from qmd.cli import cli
import os
import shutil
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch

class TestCLIIntegration(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.test_dir_path = tempfile.mkdtemp()
        self.test_dir = Path(self.test_dir_path)
        (self.test_dir / "test.md").write_text("# Test Doc\nHello World", encoding="utf-8")
        
        self.old_home = os.environ.get("USERPROFILE") or os.environ.get("HOME")
        self.temp_home_dir = tempfile.mkdtemp()
        self.temp_home = Path(self.temp_home_dir).absolute()
        
        if os.name == 'nt':
            os.environ["USERPROFILE"] = str(self.temp_home)
        else:
            os.environ["HOME"] = str(self.temp_home)

    def tearDown(self):
        if self.old_home:
            if os.name == 'nt':
                os.environ["USERPROFILE"] = self.old_home
            else:
                os.environ["HOME"] = self.old_home
        
        import gc
        gc.collect()
        
        try:
            shutil.rmtree(self.test_dir_path)
            shutil.rmtree(self.temp_home_dir)
        except Exception as e:
            print(f"Warning: cleanup error: {e}")

    def test_full_flow(self):
        # 1. Add collection
        result = self.runner.invoke(cli, ["collection", "add", str(self.test_dir), "--name", "test"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Added collection", result.output)
        
        # 2. List collections
        result = self.runner.invoke(cli, ["collection", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test", result.output)
        
        # 3. Add context
        result = self.runner.invoke(cli, ["context", "add", "--collection", "test", "Internal Knowledge"])
        self.assertEqual(result.exit_code, 0)
        
        # 4. Index
        result = self.runner.invoke(cli, ["index"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Total indexed", result.output)
        
        # 5. Search
        result = self.runner.invoke(cli, ["search", "Hello"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Test Doc", result.output)
        
        # 6. Status
        result = self.runner.invoke(cli, ["status"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Documents", result.output)
        
        # 7. Get (by hash)
        result = self.runner.invoke(cli, ["get", "fakehash"])
        self.assertIn("not found", result.output)

        # 8. Config show
        result = self.runner.invoke(cli, ["config", "show"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("db_path", result.output)

    def test_context_management_cli(self):
        # Add collection
        self.runner.invoke(cli, ["collection", "add", str(self.test_dir), "--name", "test2"])
        
        # Add root context
        result = self.runner.invoke(cli, ["context", "add", "--collection", "test2", "Global Root"])
        self.assertEqual(result.exit_code, 0)
        
        # Add subpath context
        result = self.runner.invoke(cli, ["context", "add", "--collection", "test2", "--path", "subdir", "Subdir context"])
        self.assertEqual(result.exit_code, 0)
        
        # List contexts
        result = self.runner.invoke(cli, ["context", "list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Global Root", result.output)
        self.assertIn("Subdir context", result.output)
        
        # Remove context
        result = self.runner.invoke(cli, ["context", "remove", "--collection", "test2", "--path", "subdir"])
        self.assertEqual(result.exit_code, 0)
        
        result = self.runner.invoke(cli, ["context", "list"])
        self.assertNotIn("Subdir context", result.output)

    @patch('qmd.cli.VectorSearch')
    def test_embed_and_vsearch(self, mock_vsearch_class):
        mock_vsearch = mock_vsearch_class.return_value
        self.runner.invoke(cli, ["collection", "add", str(self.test_dir), "--name", "test4"])
        self.runner.invoke(cli, ["index"])
        
        # Test embed
        # We need to mock LLMEngine inside VectorSearch or handle its failure
        result = self.runner.invoke(cli, ["embed"])
        # Embed might fail if LLM dependencies are missing, but we've mocked VectorSearch
        self.assertEqual(result.exit_code, 0)
        
        # Test vsearch
        from qmd.search.vector import SearchResult
        mock_vsearch.search.return_value = [
            SearchResult(path="test.md", collection="test4", content="Hello", score=0.9, metadata={"title": "T"})
        ]
        result = self.runner.invoke(cli, ["vsearch", "Hello"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("test4", result.output)

    @patch('qmd.cli.HybridSearcher')
    @patch('qmd.cli.LLMReranker')
    def test_hybrid_query(self, mock_reranker_class, mock_hybrid_class):
        mock_hybrid = mock_hybrid_class.return_value
        mock_hybrid.search.return_value = [
            {"title": "T1", "collection": "C1", "type": "hybrid", "score": 0.5}
        ]
        
        # Test query without rerank
        result = self.runner.invoke(cli, ["query", "Hello", "--no-rerank"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("T1", result.output)
        
        # Test query with rerank
        mock_reranker = mock_reranker_class.return_value
        mock_reranker.expand_query.return_value = ["Hello", "Hi"]
        mock_reranker.rerank.return_value = [
            {"title": "T1", "collection": "C1", "type": "hybrid", "rerank_score": 0.9}
        ]
        result = self.runner.invoke(cli, ["query", "Hello"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Reranking", result.output)

if __name__ == "__main__":
    unittest.main()
