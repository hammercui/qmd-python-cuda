# QMD-Python: Complete Documentation Suite

## 📋 Documentation Index

This directory contains the complete analysis and specification for rewriting QMD (Query Markup Documents) in Python.

### 📁 Document Structure

```
docs/python-rewrite/
├── README.md                           # THIS FILE - Overview & index
├── 01-root-cause-analysis.md          # Why Node.js/Bun failed
├── 02-design-document.md              # Technical architecture
├── 03-requirements.md                 # Functional & non-functional requirements
├── 04-testing.md                      # Testing strategy & benchmarks
└── 05-metrics.md                      # Performance targets & measurement
```

---

## 🎯 Executive Summary

**Decision**: Rewrite QMD in Python

**Rationale**: 
- **Root Cause**: `node-llama-cpp` + Windows + Bun/Node.js = Segmentation fault
- **Solution**: `llama-cpp-python` (official bindings, stable)
- **Confidence**: HIGH (technical analysis + proven architecture)

**Timeline**: 3-4 weeks to MVP

---

## 📊 Quick Reference

| Aspect | QMD (TypeScript) | QMD-Python | Status |
|--------|-----------------|--------------|--------|
| **Installation** | `bun install` (compile) | `pip install` | ✅ Better |
| **Windows Support** | ❌ Crashes | ✅ Stable | ✅ Fixed |
| **Dependencies** | 15 packages | 5 packages | ✅ Simpler |
| **Code Volume** | ~5800 lines | ~4000 lines | ✅ 30% less |
| **Vector Search** | ❌ Broken | ✅ Functional | ✅ Fixed |

---

## 📚 Document Guide

### 1️⃣ Root Cause Analysis ([`01-root-cause-analysis.md`](01-root-cause-analysis.md))

**Purpose**: Understand why QMD (TypeScript) fails on Windows

**Key Findings**:
- **Phase 1 (Bun)**: Segmentation fault during vector operations
  - Affected: `qmd vsearch`, `qmd query`, `qmd embed`
  - Working: `qmd search`, `qmd get`, `qmd status`
- **Phase 2 (Node.js)**: Native addon compilation failure
  - `better-sqlite3` requires C++ build tools
  - Missing Visual Studio on Windows
  - Type definitions missing
- **Phase 3 (Platform)**: `node-llama-cpp` instability
  - Third-party bindings (unofficial)
  - Windows-specific crashes

**Decision Matrix**:
- Fix Bun crashes: HIGH effort → LOW reward
- Finish Node.js port: MEDIUM effort → MEDIUM risk
- Rewrite in Python: MEDIUM effort → HIGH reward ✅

**Read Next**: [Design Document](02-design-document.md)

---

### 2️⃣ Design Document ([`02-design-document.md`](02-design-document.md))

**Purpose**: Technical architecture for Python rewrite

**Core Components**:
1. **CLI Layer**: `click` + `typer` + `rich`
2. **Search Engine**: BM25 (SQLite FTS5) + Vector (ChromaDB) + Hybrid (RRF)
3. **Database**: `sqlite3` (built-in, stable)
4. **ML Engine**: `llama-cpp-python` (official bindings)

**Data Model**:
- Collections (YAML config)
- Documents (metadata + hash-deduped content)
- FTS index (BM25)
- Vector store (ChromaDB)

**Search Pipeline**:
```
Query → [FTS] → [Vector] → [RRF] → [LLM Rerank] → Ranked
```

**Key Design Decisions**:
- ChromaDB vs sqlite-vec: Maturity > API similarity
- Hash deduplication: Same content stored once
- Hierarchical contexts: Path-based inheritance

**Directory Structure**:
```
qmd-python/            # ~30 files (vs QMD's ~15)
├── qmd/
│   ├── cli.py
│   ├── database/
│   ├── search/
│   ├── llm/
│   └── index/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── benchmarks/
└── docs/
```

**Read Next**: [Requirements](03-requirements.md)

---

### 3️⃣ Requirements ([`03-requirements.md`](03-requirements.md))

**Purpose**: Detailed functional and non-functional requirements

**Functional Requirements**:
- **FR-1**: Collection Management (add, list, remove, rename)
- **FR-2**: Document Indexing (scan, update, status)
- **FR-3**: Search Functionality (BM25, Vector, Hybrid)
- **FR-4**: Document Retrieval (get, multi-get, list)
- **FR-5**: Context Management (add, remove, check)
- **FR-6**: Embedding (generate, status)

**Non-Functional Requirements**:
- **NFR-1**: Performance (BM25 <50ms, Vector <500ms)
- **NFR-2**: Reliability (WAL mode, atomic ops)
- **NFR-3**: Compatibility (Windows 10+, macOS 12+, Linux)
- **NFR-4**: Usability (progress, help, colors)
- **NFR-5**: Privacy (local-only, no telemetry)
- **NFR-6**: Security (model sandboxing, file permissions)

**User Stories**:
- Epic 1: First-Time Setup (install + index)
- Epic 2: Daily Usage (search workflows)
- Epic 3: Maintenance (update + embed)

**Success Criteria**:
- **MVP**: Installation + BM25 + Vector search + Windows compatible
- **Production**: All NFRs met + >80% coverage

**Read Next**: [Testing](04-testing.md)

---

### 4️⃣ Testing ([`04-testing.md`](04-testing.md))

**Purpose**: Comprehensive testing strategy

**Test Framework**:
- `pytest` (test runner)
- `pytest-cov` (coverage)
- `pytest-benchmark` (performance)

**Unit Tests** (`tests/unit/`):
- Database schema & CRUD
- BM25 search ranking
- Vector search similarity
- LLM embedding generation

**Integration Tests** (`tests/integration/`):
- End-to-end workflows
  - Create collection → Index → Search
  - Index → Embed → Hybrid search
- Error handling (missing collections, documents)

**Benchmarks** (`tests/benchmarks/`):
- BM25 latency (<50ms target)
- Vector search latency (<500ms target)
- Hybrid search (<3s target)
- Indexing throughput (>100 files/s)

**Coverage Targets**:
- Overall: >80%
- Database: >85%
- Search: >85% (BM25), >80% (hybrid)
- LLM: >75% (external dependency)

**CI/CD**:
- Matrix: Windows/macOS/Linux × Python 3.10/3.11/3.12
- Automated: Tests + benchmarks on every PR
- Regression check: <1.2x baseline

**Read Next**: [Metrics](05-metrics.md)

---

### 5️⃣ Metrics ([`05-metrics.md`](05-metrics.md))

**Purpose**: Performance targets and measurement methodology

**Performance Targets**:
| Operation | Target (p95) |
|-----------|--------------|
| BM25 Search | <50ms (10k docs) |
| Vector Search | <500ms (10k docs) |
| Hybrid Search | <3s (10k docs) |
| Indexing | >100 files/s |

**Memory Usage**:
- Idle: <100MB
- BM25 search: <150MB
- Vector search: <2GB (model loaded)
- Embedding: <2.5GB (peak)

**Storage Overhead**:
- Total: ~5x original size
- Example: 5GB docs → ~25GB total
- Breakdown: Content (1x) + SQLite (2x) + Vectors (2x)

**Benchmark Methodology**:
- Datasets: 100, 1k, 10k, 100k docs
- Queries: 20 BM25 + 20 semantic + 10 hybrid
- Tool: `pytest-benchmark`
- Reporting: JSON + PR comments

**Regression Testing**:
- Trigger: Every pull request
- Failure threshold: >20% slower
- Automated checks: CI/CD

---

## 🚀 Implementation Roadmap

### Milestone 1: MVP (Week 1)

**Goal**: Basic search working

- [ ] Database schema + migrations
- [ ] CLI skeleton (all commands defined)
- [ ] BM25 search functional
- [ ] Document indexing working

**Deliverables**:
- `qmd collection add` works
- `qmd search "query"` returns results
- `qmd status` displays stats

### Milestone 2: Vector Search (Week 2)

**Goal**: Semantic search functional

- [ ] ChromaDB integration
- [ ] llama-cpp-python bindings
- [ ] Embedding generation
- [ ] Vector search command

**Deliverables**:
- `qmd embed` generates vectors
- `qmd vsearch "semantic query"` works
- Progress bars during embedding

### Milestone 3: Hybrid + Polish (Week 3)

**Goal**: Full feature parity

- [ ] RRF fusion algorithm
- [ ] LLM reranking
- [ ] Query expansion
- [ ] Error handling

**Deliverables**:
- `qmd query "natural language"` works
- Context management system
- Multi-get functionality

### Milestone 4: Production Ready (Week 4)

**Goal**: Polished, documented, tested

- [ ] Performance optimization
- [ ] Documentation (README + man pages)
- [ ] Test coverage >80%
- [ ] PyPI publish

**Deliverables**:
- `pip install qmd-python`
- Complete README
- Benchmark suite passing

---

## 🔧 Technical Stack

### Core Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.10"           # Runtime
click = "^8.1"              # CLI
rich = "^13.0"             # Formatting
pyyaml = "^6.0"            # Config
chromadb = "^0.4"           # Vector DB
llama-cpp-python = "^0.2"  # LLM
```

### Dev Dependencies

```toml
[tool.poetry.group.dev.dependencies]
pytest = "^7.0"            # Testing
pytest-cov = "^4.0"        # Coverage
pytest-benchmark = "^4.0"  # Perf
ruff = "^0.1"               # Linting
```

### Models

| Model | Purpose | Size |
|-------|---------|------|
| `embeddingemma` | Embeddings | 300MB |
| `qwen3-reranker` | Reranking | 640MB |
| `qwen3-query-expansion` | Variants | 1.1GB |

**Total**: ~2GB (one-time download)

---

## 📈 Success Metrics

### MVP Definition (Must-Have)

- [ ] **Installation**: `pip install qmd-python` succeeds
- [ ] **Indexing**: `qmd collection add .` succeeds
- [ ] **BM25**: Returns results <50ms
- [ ] **Vector**: Returns semantic results <500ms
- [ ] **Windows**: All features work on Windows 10+

### Production Ready (Should-Have)

- [ ] **Performance**: Meets all NFR-1 targets
- [ ] **Testing**: >80% code coverage
- [ ] **Documentation**: Complete README
- [ ] **Hybrid**: RRF + reranking functional
- [ ] **Contexts**: At least 1 configured

### Delighters (Nice-to-Have)

- [ ] **Shell Completion**: Bash/zsh auto-complete
- [ ] **MCP Server**: Model Context Protocol
- [ ] **Progress Bars**: Rich TUI
- [ ] **Export Formats**: JSON, CSV

---

## 🎓 Conclusion

**Recommendation**: ✅ **Proceed with Python Rewrite**

**Confidence Level**: **HIGH**

**Key Drivers**:
1. ✅ Solves root cause (node-llama-cpp instability)
2. ✅ Reduces code volume (30% less)
3. ✅ Improves stability (official bindings)
4. ✅ Lowers maintenance burden
5. ✅ Faster time-to-working (proven architecture)

**Risk Assessment**: **LOW** (mature tech stack)

---

## 🔗 References

- **Original QMD**: https://github.com/tobi/qmd
- **llama-cpp-python**: https://github.com/abetlen/llama-cpp-python
- **ChromaDB**: https://docs.trychroma.com/
- **BM25**: https://en.wikipedia.org/wiki/Okapi_BM25
- **RRF**: https://en.wikipedia.org/wiki/Reciprocal_rank_fusion

---

## 📝 Next Steps

**Immediate Actions**:
1. Initialize Python project: `mkdir qmd-python && cd qmd-python`
2. Set up Poetry: `poetry init`
3. Install dependencies: `poetry add click rich pyyaml chromadb llama-cpp-python`
4. Create directory structure: `mkdir -p qmd/{database,search,llm} tests/{unit,integration,benchmarks}`
5. Start with Milestone 1 (Database + CLI skeleton)

**Development Order**:
1. Database layer (schema + CRUD)
2. Indexing (file scanner)
3. BM25 search
4. CLI commands (basic)
5. Vector search (Milestone 2)
6. Hybrid + polish (Milestone 3-4)

---

*Last Updated: 2025-02-14*
*Status: Ready for Implementation*
