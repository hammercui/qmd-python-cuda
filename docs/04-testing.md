# QMD-Python: Testing Strategy & Documentation

## Overview

**Testing Philosophy**: Comprehensive test coverage with focus on:
- Correctness (unit tests)
- Performance (benchmarks)
- Integration (end-to-end workflows)

**Target Coverage**: >80% code coverage

**Test Framework**: `pytest` + `pytest-cov` + `pytest-benchmark`

---

## 1. Unit Testing

### 1.1 Database Layer (`tests/unit/test_database.py`)

#### Test Schema

```python
import pytest
import sqlite3
from qmd.database.schema import create_tables
from qmd.database.manager import DatabaseManager

@pytest.fixture
def db(tmp_path):
    """In-memory database for testing."""
    db = sqlite3.connect(":memory:")
    create_tables(db)
    return db

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
        manager = DatabaseManager(db)
        
        # Insert same document twice
        manager.insert_document(
            collection="test",
            path="file.md",
            hash="abc123",
            title="Test"
        )
        
        with pytest.raises(sqlite3.IntegrityError):
            manager.insert_document(
                collection="test",
                path="file.md",  # Same path
                hash="def456",
                title="Test"
            )

    def test_content_hash_dedup(self, db):
        """Same hash stored once (content deduplication)."""
        manager = DatabaseManager(db)
        
        id1 = manager.insert_content(
            hash="abc123",
            doc="# Same content"
        )
        id2 = manager.insert_content(
            hash="abc123",  # Same hash
            doc="# Same content"
        )
        
        assert id1 == id2  # Returns existing row ID
```

#### Test CRUD Operations

```python
class TestDocumentCRUD:
    """Test create, read, update, delete operations."""

    def test_insert_and_retrieve(self, db):
        """Can insert and retrieve document."""
        manager = DatabaseManager(db)
        
        manager.insert_document(
            collection="test",
            path="file.md",
            hash="abc123",
            doc="# Hello",
            title="Test Doc"
        )
        
        doc = manager.get_document("test", "file.md")
        assert doc["title"] == "Test Doc"
        assert doc["hash"] == "abc123"

    def test_soft_delete(self, db):
        """Soft delete marks document inactive."""
        manager = DatabaseManager(db)
        
        manager.insert_document(
            collection="test",
            path="file.md",
            hash="abc123",
            doc="# Content"
        )
        
        manager.deactivate_document("test", "file.md")
        
        doc = manager.get_document("test", "file.md", active_only=True)
        assert doc is None
        
        doc = manager.get_document("test", "file.md", active_only=False)
        assert doc is not None

    def test_update_title(self, db):
        """Can update document title."""
        manager = DatabaseManager(db)
        
        manager.insert_document(
            collection="test",
            path="file.md",
            hash="abc123",
            doc="# Content"
        )
        
        manager.update_title("test", "file.md", "New Title")
        
        doc = manager.get_document("test", "file.md")
        assert doc["title"] == "New Title"
```

### 1.2 Search Layer (`tests/unit/test_search.py`)

#### Test BM25 Search

```python
from qmd.search.fts import search_fts
from qmd.database.manager import DatabaseManager

class TestBM25Search:
    """Test full-text search ranking."""

    @pytest.fixture
    def indexed_db(self, db):
        """Populate DB with test data."""
        manager = DatabaseManager(db)
        
        # Insert documents
        manager.insert_document(
            collection="test",
            path="python.md",
            hash="aaa111",
            doc="# Python Tutorial\nLearn Python programming",
            title="Python Guide"
        )
        manager.insert_document(
            collection="test",
            path="javascript.md",
            hash="bbb222",
            doc="# JavaScript Tutorial\nLearn JS programming",
            title="JavaScript Guide"
        )
        manager.insert_document(
            collection="test",
            path="golang.md",
            hash="ccc333",
            doc="# Go Tutorial\nLearn Go programming",
            title="Go Guide"
        )
        
        # Create FTS index
        manager.update_fts_index()
        return db

    def test_keyword_match(self, indexed_db):
        """Keyword query returns relevant docs."""
        results = search_fts(
            db=indexed_db,
            query="Python",
            collection="test",
            limit=5
        )
        
        assert len(results) > 0
        assert "python.md" in results[0]["file"]
        assert results[0]["score"] > 0.5  # High relevance

    def test_phrase_search(self, indexed_db):
        """Phrase search works."""
        results = search_fts(
            db=indexed_db,
            query='"Learn programming"',
            collection="test"
        )
        
        # Should match docs with "Learn ... programming"
        assert len(results) == 3

    def test_boolean_and(self, indexed_db):
        """AND operator narrows results."""
        results = search_fts(
            db=indexed_db,
            query="Python AND tutorial",
            collection="test"
        )
        
        assert len(results) == 1
        assert "python.md" in results[0]["file"]

    def test_negation(self, indexed_db):
        """NOT operator excludes results."""
        results = search_fts(
            db=indexed_db,
            query="programming -JavaScript",
            collection="test"
        )
        
        files = [r["file"] for r in results]
        assert "javascript.md" not in files
```

#### Test Vector Search

```python
import chromadb
from qmd.search.vector import search_vector
from qmd.llm.engine import LlamaEngine

class TestVectorSearch:
    """Test semantic search."""

    @pytest.fixture
    def vector_collection(self, tmp_path):
        """Temporary ChromaDB collection."""
        collection = chromadb.PersistentClient(
            path=str(tmp_path / "chroma")
        ).create_collection("test")
        return collection

    @pytest.fixture
    def llm(self):
        """Mock LLM engine (avoid slow model loading)."""
        # Use mock or lightweight model
        return MockLlamaEngine()

    def test_semantic_similarity(self, vector_collection, llm):
        """Semantic search finds similar docs."""
        # Add embeddings
        vector_collection.add(
            documents=["Python programming language"],
            ids=["doc1"],
            embeddings=[llm.embed("Python programming")]
        )
        vector_collection.add(
            documents=["JavaScript web language"],
            ids=["doc2"],
            embeddings=[llm.embed("JavaScript language")]
        )
        
        # Search for "coding language"
        results = search_vector(
            db=db,
            collection=vector_collection,
            llm=llm,
            query="programming language",
            limit=2
        )
        
        # Should return both (semantically similar)
        assert len(results) == 2
        
        # Python doc should be higher relevance
        assert results[0]["score"] > results[1]["score"]
```

### 1.3 LLM Layer (`tests/unit/test_llm.py`)

#### Test Embeddings

```python
from qmd.llm.engine import LlamaEngine

class TestEmbeddings:
    """Test embedding generation."""

    @pytest.fixture
    def llm(self):
        """Initialize LLM engine."""
        return LlamaEngine(model_path="~/.qmd/models/")

    def test_embedding_shape(self, llm):
        """Embedding returns 384-dim vector."""
        vector = llm.embed("test query")
        
        assert isinstance(vector, list)
        assert len(vector) == 384
        assert all(isinstance(x, float) for x in vector)

    def test_embedding_deterministic(self, llm):
        """Same text produces same embedding."""
        text = "repeatable query"
        
        vec1 = llm.embed(text)
        vec2 = llm.embed(text)
        
        assert vec1 == vec2  # Bit-identical

    def test_embedding_batch(self, llm):
        """Batch embedding is faster."""
        texts = ["doc1", "doc2", "doc3"]
        
        # Time batch vs individual
        start = time.time()
        vecs_batch = llm.embed_batch(texts)
        batch_time = time.time() - start
        
        start = time.time()
        vecs_individual = [llm.embed(t) for t in texts]
        individual_time = time.time() - start
        
        assert batch_time < individual_time  # Should be faster
```

---

## 2. Integration Testing

### 2.1 End-to-End Workflows (`tests/integration/test_workflow.py`)

#### Test Complete Indexing & Search

```python
class TestIndexSearchWorkflow:
    """Test real-world usage patterns."""

    def test_new_collection_workflow(self, tmp_dir, llm):
        """Create collection, index, search."""
        # Setup: Create markdown files
        (tmp_dir / "doc1.md").write_text("# Python\nTutorial")
        (tmp_dir / "doc2.md").write_text("# JavaScript\nGuide")
        
        # Initialize
        db = DatabaseManager(":memory:")
        llm = LlamaEngine()
        
        # Add collection
        add_collection(
            name="test",
            path=str(tmp_dir),
            pattern="*.md"
        )
        
        # Index
        index_files(db=db, path=str(tmp_dir), collection="test")
        
        # Verify indexed
        stats = get_index_stats(db)
        assert stats["total_docs"] == 2
        
        # Search
        results = search_fts(db, query="tutorial", collection="test")
        assert len(results) == 2
        
        # Cleanup
        remove_collection(db, "test")

    def test_hybrid_search_workflow(self, tmp_dir, llm):
        """Index, embed, hybrid search."""
        # Setup
        (tmp_dir / "api.md").write_text("# API Reference\nAuthentication flow")
        (tmp_dir / "auth.md").write_text("# Auth Guide\nHow to login")
        
        db = DatabaseManager(":memory:")
        llm = LlamaEngine()
        
        # Index
        add_collection(..., index_files(...)
        
        # Embed
        embed_documents(db=db, llm=llm, collection="test")
        
        # Hybrid search
        results = search_hybrid(
            db=db,
            llm=llm,
            query="how to authenticate",
            collection="test"
        )
        
        # Should find both docs (semantic match)
        assert len(results) >= 1
        assert results[0]["score"] > 0.3  # Confidence
```

### 2.2 Error Handling (`tests/integration/test_errors.py`)

```python
class TestErrorHandling:
    """Test graceful failure handling."""

    def test_missing_collection(self):
        """Error when collection doesn't exist."""
        with pytest.raises(CollectionNotFoundError):
            get_collection(db, "nonexistent")

    def test_missing_document(self):
        """Error when document not found."""
        with pytest.raises(DocumentNotFoundError):
            get_document(db, "test", "missing.md")

    def test_invalid_glob_pattern(self):
        """Error on invalid glob."""
        with pytest.raises(ValueError):
            add_collection(
                name="test",
                path="/path",
                pattern="***invalid***"  # Bad pattern
            )
```

---

## 3. Performance Testing

### 3.1 Benchmark Suite (`tests/benchmarks/bench_search.py`)

#### BM25 Performance

```python
import pytest_benchmark

class TestBM25Performance:
    """BM25 search performance targets."""

    def setup_benchmark(self, large_db):
        """Create 10,000 document database."""
        # Pre-populate with 10k docs
        ...

    @pytest.mark.benchmark(
        group="fts-search",
        min_rounds=10,
        warmup_rounds=2
    )
    def test_search_single_keyword(self, benchmark, large_db):
        """Single keyword search <50ms."""
        results = search_fts(
            db=large_db,
            query="keyword",
            collection="test"
        )
        
        assert benchmark.stats["median"] < 0.05  # <50ms

    @pytest.mark.benchmark(group="fts-search")
    def test_search_boolean(self, benchmark, large_db):
        """Boolean query <100ms."""
        results = search_fts(
            db=large_db,
            query="keyword AND another",
            collection="test"
        )
        
        assert benchmark.stats["median"] < 0.10
```

#### Vector Search Performance

```python
class TestVectorSearchPerformance:
    """Vector search performance targets."""

    @pytest.mark.benchmark(
        group="vector-search",
        min_rounds=5,
        warmup_rounds=1
    )
    def test_vector_search_warm(self, benchmark, vector_db, llm):
        """Vector search <500ms (after model loaded)."""
        results = search_vector(
            db=vector_db,
            llm=llm,
            collection="test",
            query="semantic query"
        )
        
        # Warm model (first query slow)
        benchmark.extra_info["warmup"] = True
        assert benchmark.stats["median"] < 0.50  # <500ms
```

#### Indexing Performance

```python
class TestIndexingPerformance:
    """Indexing speed targets."""

    @pytest.mark.benchmark(
        group="indexing",
        min_rounds=3
    )
    def test_indexing_speed(self, benchmark, large_source_dir):
        """Index >100 files/second."""
        files = list(large_source_dir.glob("*.md"))[:1000]
        
        start = time.time()
        index_files(db=db, path=..., collection="test")
        elapsed = time.time() - start
        
        rate = len(files) / elapsed
        assert rate > 100  # >100 files/sec
```

---

## 4. Test Execution

### 4.1 Run All Tests

```bash
# Unit tests only
pytest tests/unit/ -v

# Unit + integration
pytest tests/ -v

# With coverage
pytest --cov=qmd --cov-report=html tests/

# Specific test
pytest tests/unit/test_search.py::TestBM25Search::test_keyword_match -v
```

### 4.2 Run Benchmarks

```bash
# All benchmarks
pytest tests/benchmarks/ --benchmark-only

# Specific benchmark
pytest tests/benchmarks/bench_search.py::TestBM25Performance --benchmark-only

# Compare to baseline
pytest tests/benchmarks/ --benchmark-only --benchmark-autosave
# (Second run will compare to saved baseline)
```

### 4.3 CI/CD Integration

**GitHub Actions** (`.github/workflows/test.yml`):

```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ["3.10", "3.11", "3.12"]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install poetry
        poetry install --with dev
    
    - name: Run tests
      run: poetry run pytest --cov=qmd
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## 5. Test Data Management

### 5.1 Fixtures

**Location**: `tests/fixtures/`

```
fixtures/
├── markdown/
│   ├── simple.md
│   ├── headings.md
│   ├── code-blocks.md
│   └── large.md (100KB)
├── collections/
│   ├── personal/
│   └── work/
└── models/
    └── (empty, use real GGUF files)
```

**Usage**:

```python
@pytest.fixture
def sample_doc(tmp_path):
    """Load sample markdown document."""
    source = FIXTURES_DIR / "markdown" / "simple.md"
    return source.read_text()
```

### 5.2 Mocks

**Mock LLM Engine** (avoid slow model loading):

```python
class MockLlamaEngine:
    """Fast mock for testing."""
    
    def embed(self, text: str) -> list[float]:
        # Return deterministic pseudo-random vector
        hash_val = hash(text)
        random.seed(hash_val)
        return [random.uniform(-1, 1) for _ in range(384)]
    
    def rerank(self, query: str, docs: list) -> dict:
        # Return mock scores
        return {doc: random.random() for doc in docs}
```

---

## 6. Coverage Targets

| Module | Target Coverage | Status |
|--------|-----------------|--------|
| `qmd.database` | >85% |  |
| `qmd.search.fts` | >90% |  |
| `qmd.search.vector` | >85% |  |
| `qmd.search.hybrid` | >80% |  |
| `qmd.llm.engine` | >75% |  (LLM external) |
| `qmd.cli` | >70% |  (CLI complex) |

**Overall**: >80%

---

## 7. Continuous Performance Monitoring

### 7.1 Performance Regression Tests

**Automated Benchmarks**: Run on every PR

```yaml
# .github/workflows/benchmark.yml
name: Performance Check

on: [pull_request]

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v3
        with:
          python-version: "3.11"
      - name: Install
        run: pip install -e .
      - name: Run benchmarks
        run: |
          pytest tests/benchmarks/ --benchmark-only \
            --benchmark-json=output.json
      - name: Check regressions
        run: |
          python scripts/check_benchmarks.py output.json
```

**Failure Criteria**:
- BM25 median > 1.2x baseline
- Vector search median > 1.2x baseline
- Indexing rate < 0.8x baseline

### 7.2 Load Testing

**Stress Test** (manual, pre-release):

```python
# tests/stress/test_large_index.py
def test_100k_documents():
    """Test with 100,000 documents."""
    # Generate 100k markdown files
    # Index
    # Search
    # Verify <5s response time
```

---

## 8. Test Checklist

### Pre-Merge Checklist

- [ ] All unit tests pass
- [ ] >80% code coverage
- [ ] No regression in benchmarks (<1.2x)
- [ ] Integration tests pass (all workflows)
- [ ] Manual smoke test (install + search)
- [ ] Documentation updated

### Pre-Release Checklist

- [ ] Load test: 100k documents
- [ ] Windows smoke test (primary target)
- [ ] Error handling verified (all error paths)
- [ ] Performance validated (all NFRs met)
- [ ] Dependencies security scanned

---

## 9. Troubleshooting

### Tests Failing

**Issue**: Tests fail on Windows

**Diagnosis**:
```bash
# Run with verbose output
pytest tests/unit/test_search.py -vv -s

# Check for path separators
pytest tests/unit/test_search.py::TestBM25Search::test_keyword_match -vv
```

**Common Fixes**:
- Path separators: Use `pathlib.Path` instead of `/`
- Line endings: Git autocrlf (`git config core.autocrlf true`)
- Temp files: Use `tmp_path` fixture (cross-platform)

### Benchmarks Slow

**Issue**: Benchmarks taking too long

**Fixes**:
- Reduce `min_rounds`
- Skip warmup: `--benchmark-skip-warmup`
- Use smaller dataset: `--benchmark-min-rounds=1`

---

## 10. Resources

- **Pytest Docs**: https://docs.pytest.org/
- **pytest-benchmark**: https://pytest-benchmark.readthedocs.io/
- **Coverage**: https://coverage.readthedocs.io/
- **ChromaDB Testing**: https://docs.trychroma.com/usage-guide/testing
