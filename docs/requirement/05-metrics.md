# QMD-Python: Metrics & Benchmarks

## Overview

**Purpose**: Define performance targets and measurement methodology for QMD-Python.

**Key Metrics**:
- Search latency (p50, p95, p99)
- Indexing throughput
- Memory usage
- Storage overhead

**Baseline Comparison**: Original QMD (TypeScript) where applicable

---

## 1. Performance Targets

### 1.1 Search Latency

| Operation | Target (p95) | Target (p99) | Measurement |
|-----------|--------------|--------------|-------------|
| **BM25 Search** | <50ms | <100ms | 10,000 docs |
| **Vector Search** | <500ms | <1000ms | 10,000 docs |
| **Hybrid Search** | <3s | <5s | 10,000 docs (LLM-bound) |

**Acceptance Criteria**:
- [ ] 95% of queries complete within target
- [ ] No query exceeds 2x target
- [ ] p95 latency meets target on Windows/macOS/Linux

### 1.2 Indexing Performance

| Operation | Target | Measurement |
|-----------|--------|-------------|
| **File Scanning** | >100 files/s | Markdown files |
| **Hash Calculation** | >50 MB/s | SHA-256 throughput |
| **Database Insert** | >500 docs/s | SQLite writes |
| **Embedding Generation** | >50 chunks/s | llama-cpp (CPU) |

**Acceptance Criteria**:
- [ ] Index 10,000 documents in <2 minutes (SSD)
- [ ] Index 1,000 documents in <30 seconds
- [ ] Progress updates every 1 second

### 1.3 Memory Usage

| Scenario | Target | Limit |
|----------|--------|-------|
| **Idle (CLI)** | <100MB |  |
| **BM25 Search** | <150MB | 10k docs |
| **Vector Search** | <2GB | Model loaded |
| **Embedding** | <2.5GB | Peak |

**Acceptance Criteria**:
- [ ] No memory leaks (stable after 1000 operations)
- [ ] Respects system limits (4GB RAM minimum)
- [ ] Graceful degradation (swap slow, not crash)

### 1.4 Storage Overhead

| Component | Overhead | Notes |
|-----------|----------|-------|
| **Document Content** | 1x | Original text |
| **SQLite Index** | ~2x | FTS5 index |
| **Embeddings (Chroma)** | ~2x | Vector data |
| **Total** | ~5x | Est. 25MB per 1000 docs |

**Example**:
- 1000 documents × 5KB average = 5GB
- Total storage: ~25GB (5GB × 5)

---

## 2. Benchmark Methodology

### 2.1 Test Data Sets

| Dataset | Size | Source | Purpose |
|---------|------|--------|---------|
| **Small** | 100 docs | Synthetic fixtures | Unit tests |
| **Medium** | 1,000 docs | Subset of real | Integration |
| **Large** | 10,000 docs | Full corpus | Performance |
| **Stress** | 100,000 docs | Generated | Load testing |

**Document Distribution**:
```
Titles: [API Guide, Tutorial, Reference, Setup, Troubleshooting]
Sizes: 1KB - 50KB (log-normal)
Content: Markdown with headings, code blocks
```

### 2.2 Query Sets

**BM25 Queries** (20 queries):
```python
BENCHMARK_QUERIES = [
    "authentication",
    "docker compose",
    "api reference",
    "database schema",
    "deployment process",
    # ... (20 total)
]
```

**Vector Queries** (20 queries):
```python
SEMANTIC_QUERIES = [
    "how to authenticate",
    "container orchestration",
    "rest api documentation",
    "data storage design",
    "production deployment steps",
    # ... (20 total)
]
```

**Hybrid Queries** (10 natural language):
```python
HYBRID_QUERIES = [
    "what's the command to deploy?",
    "how do I reset the admin password",
    "where is the api documentation",
    # ... (10 total)
]
```

### 2.3 Measurement Protocol

#### Benchmark Tool

**Tool**: `pytest-benchmark`

**Installation**:
```bash
pip install pytest pytest-benchmark
```

**Execution**:
```bash
# Run all benchmarks
pytest tests/benchmarks/ --benchmark-only

# Save baseline
pytest tests/benchmarks/ --benchmark-only --benchmark-autosave

# Compare to baseline
pytest tests/benchmarks/ --benchmark-only --benchmark-autosave --benchmark-compare
```

#### Environment

**Standardized Test Machine**:
- CPU: 4 cores (AMD/Intel)
- RAM: 8GB
- Storage: SSD (NVMe preferred)
- OS: Windows 10/Ubuntu 22.04/macOS 12

**Variables to Control**:
- [ ] Cold vs warm (model loaded)
- [ ] Database size (1k vs 10k docs)
- [ ] CPU governor (performance mode)
- [ ] Background processes (none)

#### Data Collection

For each benchmark run, collect:
- Latency (ms): min, median, p95, p99, max
- Throughput (ops/sec)
- Memory (MB): peak, average
- CPU (%): user, system

**Output Format** (JSON):
```json
{
  "name": "test_search_single_keyword",
  "group": "fts-search",
  "stats": {
    "min": 0.032,
    "median": 0.041,
    "max": 0.087,
    "q95": 0.058
  },
  "extra_info": {
    "warmup": true,
    "doc_count": 10000
  }
}
```

---

## 3. Benchmark Scenarios

### 3.1 BM25 Search

```python
# tests/benchmarks/bench_fts.py
import pytest_benchmark

def test_bm25_single_keyword(benchmark, large_db):
    """Single keyword query."""
    results = search_fts(
        db=large_db,
        query="authentication",
        collection="test",
        limit=5
    )
    
    # Target: <50ms
    assert len(results) > 0

@pytest.mark.benchmark(group="fts-complex")
def test_bm25_boolean_complex(benchmark, large_db):
    """Complex boolean query."""
    results = search_fts(
        db=large_db,
        query="(authentication AND user) -password",
        collection="test"
    )
    
    # Target: <100ms
    assert len(results) > 0
```

### 3.2 Vector Search

```python
# tests/benchmarks/bench_vector.py
@pytest.mark.benchmark(
    group="vector-search",
    min_rounds=5
)
def test_vector_search_warm(benchmark, vector_db, llm):
    """Vector search (model loaded)."""
    results = search_vector(
        db=vector_db,
        llm=llm,
        collection="test",
        query="how to authenticate"
    )
    
    # Target: <500ms
    assert benchmark.stats["median"] < 0.50
```

### 3.3 Hybrid Search

```python
# tests/benchmarks/bench_hybrid.py
@pytest.mark.benchmark(
    group="hybrid-search",
    min_rounds=3
)
def test_hybrid_search(benchmark, hybrid_db, llm):
    """Full hybrid pipeline."""
    results = search_hybrid(
        db=hybrid_db,
        llm=llm,
        query="how do I reset admin password?"
    )
    
    # Target: <3s
    assert benchmark.stats["median"] < 3.0
```

---

## 4. Baseline Targets (Original QMD)

Where applicable, compare to TypeScript QMD:

| Metric | QMD (TS) | QMD-Python | Target |
|--------|-----------|--------------|--------|
| **BM25 (10k docs)** | 30-50ms | <50ms | ≥ |
| **Vector (10k docs)** | 200-500ms | <500ms | ≥ |
| **Indexing** | 100-200 files/s | >100 files/s | ≥ |

**Note**: Original QMD crashes on Windows, so Python baseline only needs macOS/Linux comparison.

---

## 5. Memory Profiling

### 5.1 Measurement Tools

**Tool**: `memory_profiler`

```bash
pip install memory_profiler
```

**Usage**:
```python
from qmd.search import fts
from memory_profiler import profile

@profile
def test_memory_leak():
    """Check for memory leaks over 1000 searches."""
    for _ in range(1000):
        search_fts(db, query, "test")
```

**Output**:
```
Filename: tests/performance/test_memory.py
Line #    Mem usage    Increment    Line Contents
====================================================
     42     10.5 MB     0.0 MB      @profile
     43     12.1 MB     1.6 MB          results = search_fts(...)
     44     13.8 MB     1.7 MB      return results
```

### 5.2 Leak Detection

**Scenario**: Repeated operations

- [ ] 1000 × `qmd search`
- [ ] 100 × `qmd embed`
- [ ] 1000 × `qmd query`

**Pass Criteria**: Memory growth <10% over 1000 ops

---

## 6. Regression Testing

### 6.1 Continuous Benchmarking

**Trigger**: Every pull request

**Workflow**:
```yaml
# .github/workflows/benchmark.yml
on: [pull_request]

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - name: Run benchmarks
        run: |
          pytest tests/benchmarks/ --benchmark-only \
            --benchmark-json=benchmark.json
      - name: Check regressions
        run: |
          python scripts/check_regression.py \
            --baseline=baseline.json \
            --current=benchmark.json
```

**Failure Threshold**: >20% slower than baseline

### 6.2 Performance Alerts

**Logging**: All slow operations logged

```python
import logging
import time

logger = logging.getLogger("qmd.perf")

def log_slow(operation: str, threshold_ms: int):
    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = (time.time() - start) * 1000
            
            if elapsed > threshold_ms:
                logger.warning(
                    f"[SLOW] {operation} took {elapsed:.0f}ms "
                    f"(threshold: {threshold_ms}ms)"
                )
            return result
        return wrapper
    return decorator

@log_slow("vector_search", threshold_ms=500)
def search_vector(...):
    ...
```

---

## 7. Success Criteria

### 7.1 Performance Gates

**MVP (Minimum)**:
- [ ] BM25 search: <50ms (10k docs)
- [ ] Indexing: >50 files/s
- [ ] No memory leaks

**Production (Target)**:
- [ ] BM25 search: <30ms (p95)
- [ ] Vector search: <300ms (p95)
- [ ] Indexing: >100 files/s
- [ ] >80% benchmark targets met

### 7.2 Regression Prevention

**Pre-Merge Check**:
- [ ] No benchmark >1.2x baseline
- [ ] Memory usage <10% growth
- [ ] No new timeouts

---

## 8. Reporting

### 8.1 Automated Reports

**GitHub Action**: Post benchmark results as PR comment

```yaml
- name: Comment benchmark
  uses: actions/github-script@v6
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    script: |
        gh pr comment ${{ github.event.pull_request.number }} \
          --body-file benchmark_results.md
```

**Format**:
```markdown
## 📊 Benchmark Results

### BM25 Search (10,000 docs)
- Median: **42ms** ✅ (target: <50ms)
- P95: **58ms** ✅
- Throughput: **23.8 ops/sec**

### Vector Search (10,000 docs)
- Median: **312ms** ✅ (target: <500ms)
- P95: **487ms** ⚠️ (target: <500ms)
- Model load: **1.2s** (one-time)

### Indexing (1,000 docs)
- Rate: **142 files/sec** ✅ (target: >100)
- Total: **7.1s** ✅

**Conclusion**: ✅ Ready to merge
```

### 8.2 Manual Validation

**Pre-Release Checklist**:
- [ ] Run full benchmark suite on 3 platforms
- [ ] Load test: 100k documents
- [ ] Memory profiling: 8GB RAM machine
- [ ] Compare to QMD (TypeScript) on macOS/Linux

---

## 9. Optimization Strategies

### 9.1 Database

| Optimization | Impact | Effort |
|-------------|--------|--------|
| **FTS5 Indexes** | High (already fast) | - |
| **Query Caching** | Medium | Low |
| **Prepared Statements** | Low | Done |
| **WAL Mode** | Medium | Done |

### 9.2 Vector Search

| Optimization | Impact | Effort |
|-------------|--------|--------|
| **Batch Embedding** | High | Medium |
| **Embedding Cache** | High | Low |
| **ChromaDB Indexing** | Medium | - |
| **Query Parallelization** | Low | Medium |

### 9.3 LLM

| Optimization | Impact | Effort |
|-------------|--------|--------|
| **Model Quantization** | High (Q8_0) | - |
| **Context Window** | Medium | - |
| **Batch Inference** | Medium | Low |
| **CPU Threads** | High | Low |

---

## 10. Troubleshooting

### Issue: Benchmarks Inconsistent

**Diagnosis**:
```bash
# Run multiple times
for i in {1..5}; do
    pytest tests/benchmarks/ --benchmark-only
done
```

**Fixes**:
- Close background apps
- Disable antivirus (temporarily)
- Ensure power profile = "High Performance"

### Issue: Memory Spikes

**Diagnosis**:
```python
# Profile memory
python -m memory_profiler tests/benchmarks/bench_hybrid.py
```

**Fixes**:
- Reduce batch size
- Clear cache between runs
- Restart Python process

---

## 11. References

- **pytest-benchmark**: https://pytest-benchmark.readthedocs.io/
- **ChromaDB Performance**: https://docs.trychroma.com/usage-guide#performance
- **SQLite Optimization**: https://www.sqlite.org/performance.html
- **llama-cpp Benchmarks**: https://github.com/ggerganov/llama.cpp/master/benchmarks
