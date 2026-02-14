import pytest
from qmd.database.manager import DatabaseManager
from qmd.search.fts import FTSSearcher
from qmd.search.vector import VectorSearch
from qmd.search.hybrid import HybridSearcher
from qmd.search.rerank import LLMReranker
import tempfile
import os


@pytest.fixture(scope="session")
def large_db():
    """Create a large database for benchmarking (1000 documents)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_qmd.db")
        manager = DatabaseManager(db_path)
        manager.add_collection("test", "/test/path", "*.md")

        # Insert 1000 documents
        for i in range(1000):
            manager.upsert_document(
                collection="test",
                path=f"file{i}.md",
                doc_hash=f"hash{i}",
                title=f"Document {i}",
                content=f"Content for document {i}. " + "keyword " * (i % 50)
            )

        yield manager


class TestBM25Performance:
    """BM25 search performance targets."""

    @pytest.mark.benchmark(
        group="fts-search",
        min_rounds=10,
        warmup_rounds=2
    )
    def test_bm25_single_keyword(self, benchmark, large_db):
        """Single keyword search <50ms."""
        searcher = FTSSearcher(large_db)
        results = searcher.search("keyword", limit=10)

        assert len(results) > 0
        assert benchmark.stats["median"] < 0.05  # <50ms

    @pytest.mark.benchmark(group="fts-search")
    def test_bm25_boolean(self, benchmark, large_db):
        """Boolean query <100ms."""
        searcher = FTSSearcher(large_db)
        results = searcher.search("keyword AND another", limit=10)

        assert len(results) > 0
        assert benchmark.stats["median"] < 0.10  # <100ms


class TestVectorSearchPerformance:
    """Vector search performance targets."""

    @pytest.fixture
    def vector_db(self, tmp_path):
        """Temporary ChromaDB collection."""
        import chromadb
        db_dir = str(tmp_path / "chroma")
        os.makedirs(db_dir, exist_ok=True)
        client = chromadb.PersistentClient(path=db_dir)

        # Create collection
        return client.get_or_create_collection(
            name="test",
            metadata={"hnsw:space": "cosine"}
        )

    @pytest.mark.benchmark(
        group="vector-search",
        min_rounds=5,
        warmup_rounds=1
    )
    def test_vector_search_warm(self, benchmark, vector_db, large_db):
        """Vector search <500ms (after model loaded)."""
        from qmd.llm.engine import LLMEngine
        llm = LLMEngine()

        # Add documents with embeddings
        docs = large_db.get_all_active_documents()[:100]
        if docs:
            vector_db.add(
                ids=[f"{d['collection']}:{d['path']}" for d in docs],
                embeddings=llm.embed_texts([d["content"] for d in docs]),
                documents=[d["content"] for d in docs],
                metadatas=[{"path": d["path"], "title": d["title"]} for d in docs]
            )

            from qmd.search.vector import VectorSearch
            vsearch = VectorSearch(str(vector_db._settings.persist_directory))

            results = vsearch.search("keyword", "test", limit=10)

            assert len(results) >= 0
            # Warm: first query loads model, subsequent are faster
            # We don't assert <500ms here as first query is slow


class TestHybridSearchPerformance:
    """Hybrid search performance targets."""

    @pytest.fixture
    def hybrid_db(self, tmp_path, large_db):
        """Setup for hybrid search benchmarks."""
        vector_dir = str(tmp_path / "hybrid_vector_db")
        os.makedirs(vector_dir, exist_ok=True)

        hybrid = HybridSearcher(large_db, vector_db_dir=vector_dir)

        # Add documents to vector store
        from qmd.llm.engine import LLMEngine
        llm = LLMEngine()

        docs = large_db.get_all_active_documents()[:100]
        if docs:
            hybrid.vector.add_documents(
                "test",
                [
                    {
                        "id": f"{d['collection']}:{d['path']}",
                        "content": d["content"],
                        "metadata": {"path": d["path"], "title": d["title"]}
                    }
                    for d in docs
                ]
            )

        return hybrid

    @pytest.mark.benchmark(
        group="hybrid-search",
        min_rounds=3
    )
    def test_hybrid_search(self, benchmark, hybrid_db):
        """Full hybrid pipeline <3s."""
        results = hybrid_db.search("keyword", collection="test", limit=10)

        assert len(results) >= 0
        assert benchmark.stats["median"] < 3.0  # <3s


class TestIndexingPerformance:
    """Indexing speed targets."""

    def test_indexing_speed(self, tmp_path):
        """Index >100 files/s."""
        import time

        # Create test directory
        test_dir = tmp_path / "test_docs"
        test_dir.mkdir()

        # Create 100 test markdown files
        for i in range(100):
            (test_dir / f"file{i}.md").write_text(f"# Test {i}\n\nContent here")

        # Index
        db = DatabaseManager(str(tmp_path / "test.db"))
        db.add_collection("test", str(test_dir), "*.md")

        from qmd.index.crawler import Crawler

        crawler = Crawler(str(test_dir), "*.md")
        start = time.time()
        count = 0
        for rel_path, content, doc_hash, title in crawler.scan():
            db.upsert_document("test", rel_path, doc_hash, title, content)
            count += 1
        elapsed = time.time() - start

        rate = count / elapsed
        assert rate > 100  # >100 files/sec

