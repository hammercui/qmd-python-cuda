# QMD-Python: Requirements Specification

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-02-14 | Initial requirements document |

---

## 1. Executive Summary

**Project Goal**: Create a Python-based markdown search engine that provides fast, local, semantic search capabilities with LLM reranking.

**Key Differentiator**: Hybrid search combining BM25 full-text, vector similarity, and LLM reranking—running entirely locally.

**Target Audience**: Developers who want ChatGPT-like search over their personal knowledge base (notes, docs, journals) without privacy concerns.

---

## 2. Functional Requirements

### FR-1: Collection Management

#### FR-1.1: Create Collection
**Priority**: P0 (MVP)

**Description**: User can index a directory of markdown files as a named "collection".

**Acceptance Criteria**:
- [ ] `qmd collection add <directory> --name <collection-name>` creates collection
- [ ] Collection name is required (auto-generate from dirname if omitted)
- [ ] Glob pattern defaults to `**/*.md` (customizable via `--mask`)
- [ ] Collection is persisted in `~/.qmd/index.yml`
- [ ] Error if collection name already exists
- [ ] Error if directory doesn't exist

**Example**:
```bash
qmd collection add ~/Documents/notes --name personal
qmd collection add . --name project-docs --mask "**/*.md"
```

#### FR-1.2: List Collections
**Priority**: P0 (MVP)

**Acceptance Criteria**:
- [ ] `qmd collection list` displays all collections
- [ ] Shows: name, path, file count, last updated timestamp
- [ ] Human-readable time format ("2d ago", "1h ago")

**Output Format**:
```
Collections (3):
  personal (qmd://personal/)
    Pattern:  **/*.md
    Files:    181 (updated 2d ago)
  work (qmd://work/)
    Pattern:  **/*.md
    Files:    42 (updated 5h ago)
```

#### FR-1.3: Remove Collection
**Priority**: P1

**Acceptance Criteria**:
- [ ] `qmd collection remove <name>` deletes collection
- [ ] Prompts for confirmation: "Remove 'personal' and 42 documents? (y/N)"
- [ ] Cascade deletes: documents + orphaned content
- [ ] Error if collection doesn't exist

#### FR-1.4: Rename Collection
**Priority**: P2

**Acceptance Criteria**:
- [ ] `qmd collection rename <old> <new>` updates name
- [ ] Updates virtual paths (qmd://old/ → qmd://new/)
- [ ] Error if new name already exists

### FR-2: Document Indexing

#### FR-2.1: Initial Indexing
**Priority**: P0 (MVP)

**Description**: Scan directory, parse markdown files, extract metadata, store in database.

**Acceptance Criteria**:
- [ ] `qmd index` scans all collections
- [ ] Ignores: `node_modules`, `.git`, `.cache`, `dist`, `build`
- [ ] Skips hidden files (starting with `.`)
- [ ] Extracts title (first heading or filename)
- [ ] Generates SHA-256 hash of content
- [ ] Stores deduplicated content (same hash = one row)
- [ ] Shows progress bar with ETA
- [ ] Reports: indexed, updated, unchanged counts
- [ ] Handles 10,000+ files without memory issues

**Performance Requirements**:
- Indexing speed: >100 files/second (SSD)
- Hash collision resistance: SHA-256 (collision rate < 2^-256)
- Memory usage: <500MB for 10,000 documents

#### FR-2.2: Update Index
**Priority**: P0 (MVP)

**Acceptance Criteria**:
- [ ] `qmd update` re-scans all collections
- [ ] Detects new files (hash not in DB)
- [ ] Detects modified files (hash changed)
- [ ] Detects deleted files (mark inactive)
- [ ] Updates `last_modified` timestamp
- [ ] `--pull` flag: run `git pull` before scanning

**Example**:
```bash
qmd update --pull  # Updates remote repos then re-indexes
```

#### FR-2.3: Status Health Check
**Priority**: P0 (MVP)

**Acceptance Criteria**:
- [ ] `qmd status` displays:
  - Index file size (human-readable)
  - Total documents
  - Embedded documents (vector search ready)
  - Documents needing embedding
  - Collections with file counts

**Warnings**:
- [ ] Warn if >10% documents need embeddings: "Run 'qmd embed' for better results"
- [ ] Tip if <10% need embeddings: "Tip: 6 documents need embeddings"
- [ ] Warn if index >14 days stale: "Run 'qmd update' to refresh"

### FR-3: Search Functionality

#### FR-3.1: Full-Text Search (BM25)
**Priority**: P0 (MVP)

**Description**: Fast keyword-based search using SQLite FTS5 BM25 ranking.

**Acceptance Criteria**:
- [ ] `qmd search "query" [-n <results>]` works
- [ ] Returns results ranked by BM25 score (relevance)
- [ ] Highlights matching terms in snippet
- [ ] Supports FTS5 query syntax:
  - Phrase search: `"exact phrase"`
  - Boolean: `keyword AND other`
  - Negation: `keyword -unwanted`
  - Wildcards: `prefix*`
- [ ] Default: 5 results (customizable with `-n`)
- [ ] Score display: color-coded (green >70%, yellow >40%)
- [ ] Shows: docid, filepath, title, score, snippet

**Performance**:
- Response time: <50ms for 10,000 documents
- Memory usage: <100MB per query

**Example**:
```bash
qmd search "authentication flow"
qmd search "docker compose" -n 10
```

#### FR-3.2: Vector Search
**Priority**: P1 (High Value)

**Description**: Semantic similarity search using vector embeddings.

**Acceptance Criteria**:
- [ ] `qmd vsearch "semantic query" [-n <results>]` works
- [ ] Generates query embedding (384-dim)
- [ ] Searches ChromaDB collection
- [ ] Returns results ranked by cosine similarity
- [ ] Handles natural language queries (no keywords needed)
- [ ] Respects collection filter: `-c <collection>`

**Performance**:
- First query: 500-2000ms (model loading)
- Subsequent queries: 200-500ms
- Model memory: 1.5GB RAM (quantized)

**Example**:
```bash
qmd vsearch "how to authenticate"
qmd vsearch "deployment process" -c work -n 5
```

#### FR-3.3: Hybrid Search (Best Quality)
**Priority**: P1 (High Value)

**Description**: Combines BM25 + vector + LLM reranking for best relevance.

**Acceptance Criteria**:
- [ ] `qmd query "natural language question"` works
- [ ] Query expansion (generates 2-3 variants)
- [ ] Parallel execution (FTS + vector for each query)
- [ ] RRF fusion (k=60) with top-rank bonuses
- [ ] Top-30 candidates reranked with LLM
- [ ] Position-aware blending:
  - Rank 1-3: 75% RRF / 25% reranker
  - Rank 4-10: 60% RRF / 40% reranker
  - Rank 11+: 40% RRF / 60% reranker
- [ ] Returns confidence scores (0.0-1.0)

**Performance**:
- Total time: 2-5 seconds (LLM-bound)
- Progress indication during reranking
- Caches expansions (avoid repeated LLM calls)

**Example**:
```bash
qmd query "what's the command to deploy?"
qmd query "quarterly planning process" -n 10
```

### FR-4: Document Retrieval

#### FR-4.1: Get by Filepath
**Priority**: P0 (MVP)

**Acceptance Criteria**:
- [ ] `qmd get <filepath>` retrieves document
- [ ] Fuzzy matching (suggests if path incomplete)
- [ ] Auto-detects collection from path
- [ ] Displays full content with syntax highlighting
- [ ] Optional line range: `qmd get <filepath>:50` (starts at line 50)
- [ ] Optional line limit: `qmd get <filepath> -l 100`
- [ ] Adds line numbers: `qmd get <filepath> --line-numbers`

**Example**:
```bash
qmd get qmd://personal/notes/crypto.md
qmd get work/api.md:50 -l 100
```

#### FR-4.2: Get by DocID
**Priority**: P0 (MVP)

**Description**: Short unique identifiers (6-char hash) for quick retrieval.

**Acceptance Criteria**:
- [ ] `qmd get #abc123` retrieves by docid
- [ ] Docid shown in search results
- [ ] Works with multi-get: `qmd multi-get #abc123,#def456`

#### FR-4.3: Multi-Get
**Priority**: P1

**Description**: Retrieve multiple documents by glob or list.

**Acceptance Criteria**:
- [ ] `qmd multi-get <pattern>` fetches matching docs
- [ ] Size limit: `--max-bytes <KB>` (default: 10KB)
- [ ] Output formats: `--json`, `--md`, `--files`
- [ ] Error if file > limit (suggests `qmd get`)

**Example**:
```bash
qmd multi-get "journals/2025-01*.md"
qmd multi-get "meetings/*.md" --json
```

#### FR-4.4: List Files
**Priority**: P0 (MVP)

**Acceptance Criteria**:
- [ ] `qmd ls [collection]` lists files
- [ ] `qmd ls collection/path` filters by prefix
- [ ] Shows: size, date, path
- [ ] Format: `ls -l` style

### FR-5: Context Management

#### FR-5.1: Add Context
**Priority**: P1

**Description**: Attach descriptions to collections/paths to improve search.

**Acceptance Criteria**:
- [ ] `qmd context add [path] "description"` works
- [ ] Path auto-detects current directory
- [ ] Virtual paths: `qmd context add qmd://work/ "API docs"`
- [ ] Global context: `qmd context add / "Knowledge base"`
- [ ] Hierarchical: subpaths inherit parent context
- [ ] `qmd context list` displays all contexts

**Example**:
```bash
# Auto-detect
cd ~/work/api && qmd context add "REST API documentation"

# Explicit path
qmd context add qmd://work/api "REST API documentation"
```

#### FR-5.2: Remove Context
**Priority**: P2

**Acceptance Criteria**:
- [ ] `qmd context rm <path>` removes context
- [ ] Supports virtual paths
- [ ] Error if no context exists

#### FR-5.3: Check Missing Contexts
**Priority**: P2

**Acceptance Criteria**:
- [ ] `qmd context check` identifies gaps
- [ ] Lists collections without context
- [ ] Lists top-level paths without context
- [ ] Suggests commands to add

**Output**:
```
Collections without context:
  personal (42 documents)
  Suggestion: qmd context add qmd://personal/ "Description"

Top-level paths without context:
  work
    api
    design
  Suggestion: qmd context add qmd://work/api "API docs"
```

### FR-6: Embedding

#### FR-6.1: Generate Embeddings
**Priority**: P1 (Core Feature)

**Description**: Create vector embeddings for semantic search.

**Acceptance Criteria**:
- [ ] `qmd embed` generates embeddings
- [ ] Chunks: 800 tokens, 15% overlap
- [ ] Model: `embeddingemma` (quantized, 384-dim)
- [ ] Progress: shows chunk count with ETA
- [ ] Resumes existing embeddings (incremental)
- [ ] Skips already embedded (hash check)

**Performance**:
- Speed: ~50-100 chunks/second (CPU)
- Memory: <2GB during generation
- Storage: ~10MB per 1000 documents

**Example**:
```bash
qmd embed                    # Generate all
qmd embed --force            # Regenerate
qmd embed --collection work    # Specific collection
```

#### FR-6.2: Check Embedding Status
**Priority**: P0 (Feedback)

**Acceptance Criteria**:
- [ ] `qmd status` shows: "495 embedded, 6 need embedding"
- [ ] Calculates unique hashes needing vectors
- [ ] Prompt to run `qmd embed`

---

## 3. Non-Functional Requirements

### NFR-1: Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| **BM25 Search** | <50ms (p95) | 10,000 docs |
| **Vector Search** | <500ms (warm) | 10,000 docs |
| **Hybrid Search** | <5s total | LLM reranking |
| **Indexing** | >100 files/s | SSD |
| **Memory** | <500MB | Idle |
| **Memory** | <2GB | Embedding |
| **Startup** | <100ms | CLI launch |

### NFR-2: Reliability

- [ ] **Zero Data Loss**: Hash-based deduplication prevents corruption
- [ ] **Crash Recovery**: SQLite WAL mode + rollback
- [ ] **Atomic Operations**: Transactions for multi-step writes
- [ ] **Error Messages**: Clear, actionable (not "Error 0x8000")

### NFR-3: Compatibility

| Platform | Status | Notes |
|----------|--------|-------|
| **Windows 10+** | ✅ Supported | Primary target |
| **macOS 12+** | ✅ Supported | Tested |
| **Linux** | ✅ Supported | Ubuntu 22.04+ |
| **Python** | 3.10+ | Minimum version |

### NFR-4: Usability

- [ ] **Progress Indication**: All long operations show progress
- [ ] **Cancel Support**: Ctrl+C cleanly exits (no corruption)
- [ ] **Help Text**: `--help` on all commands
- [ ] **Auto-Completion**: Shell completion (bash/zsh) optional
- [ ] **Color Output**: Enabled by default, respect `NO_COLOR`

### NFR-5: Privacy & Security

- [ ] **Local-First**: All data stored locally (~/.qmd)
- [ ] **No Telemetry**: No network calls (except model download)
- [ ] **No Tracking**: No analytics, user stats
- [ ] **Model Sandboxing**: llama-cpp runs in-process (no shell access)
- [ ] **File Permissions**: Respects OS permissions (no privilege escalation)

### NFR-6: Extensibility

- [ ] **Plugin API**: Future (v2) custom LLM backends
- [ ] **Export Formats**: JSON, CSV, MD, XML
- [ ] **Configuration**: YAML-based (human-editable)
- [ ] **MCP Server**: Model Context Protocol (future)

---

## 4. User Stories

### Epic 1: First-Time Setup

**Story 1.1: Install and Index**
> As a developer, I want to install QMD and index my notes, so I can search them.

**Acceptance**:
- [ ] Installation: `pip install qmd` succeeds
- [ ] Index: `qmd collection add ~/notes --name notes` works
- [ ] Search: `qmd search "docker"` returns results

**Story 1.2: Configure Context**
> As a developer, I want to describe my collection, so searches understand context.

**Acceptance**:
- [ ] Command: `qmd context add qmd://notes/ "Personal notes"`
> So that search results include "Folder: Personal notes"

### Epic 2: Daily Usage

**Story 2.1: Quick Keyword Search**
> As a developer, I want to find documents by keywords, so I can quickly locate info.

**Acceptance**:
- [ ] Command: `qmd search "authentication"` returns in <50ms
- [ ] Results show relevant snippets with highlighting

**Story 2.2: Semantic Discovery**
> As a developer, I want to ask questions naturally, so I don't need exact keywords.

**Acceptance**:
- [ ] Command: `qmd query "how do I reset the admin password?"
- [ ] Returns relevant docs even without exact keywords

**Story 2.3: Retrieve Full Document**
> As a developer, I want to read full document content, so I can implement the feature.

**Acceptance**:
- [ ] Command: `qmd get #abc123` displays full doc
- [ ] Copy-paste friendly (no line wrapping)

### Epic 3: Maintenance

**Story 3.1: Update Index**
> As a developer, I want to refresh the index after adding files, so search is complete.

**Acceptance**:
- [ ] Command: `qmd update` scans for new/modified files
- [ ] Shows: "Indexed 5 new, updated 2, 142 unchanged"

**Story 3.2: Enable Semantic Search**
> As a developer, I want to generate embeddings, so I can use vector search.

**Acceptance**:
- [ ] Command: `qmd embed` generates vectors
- [ ] Progress: "Embedding 1200/5000 chunks [=====>     ] 24% ETA: 2m"

---

## 5. Technical Constraints

### TC-1: Model Storage

- **Location**: `~/.qmd/models/`
- **Size**: ~2GB (3 GGUF files)
- **Download**: One-time (auto-cached)
- **Quantization**: Q8_0 (8-bit per weight, ~4x compression)

### TC-2: Database Location

- **File**: `~/.qmd/index.sqlite`
- **Size**: ~50MB per 1000 documents (est.)
- **Backups**: User's responsibility (provide `qmd backup` command)

### TC-3: Memory Requirements

- **Minimum**: 4GB RAM (2GB models + 1GB index + overhead)
- **Recommended**: 8GB RAM
- **Swap**: Slows embedding significantly (avoid)

### TC-4: Disk Space

| Component | Size (per 1000 docs) |
|-----------|----------------------|
| Document content | ~5MB |
| SQLite index | ~10MB |
| Embeddings (Chroma) | ~10MB |
| **Total** | **~25MB** |

### TC-5: CPU Requirements

- **BM25 Search**: Any (negligible)
- **Vector Search**: 4+ cores recommended (parallel)
- **Embedding**: CPU-bound (slower on 2 cores)

---

## 6. Out of Scope

### Explicitly NOT in MVP

- [ ] **Web UI**: CLI-only (v2)
- [ ] **Real-time Indexing**: No file watcher (manual `qmd update`)
- [ ] **Cloud Sync**: No remote sync (local-only)
- [ ] **Collaboration**: No sharing (personal knowledge base)
- [ ] **PDF/DOCX**: Markdown-only (v2: pandoc integration)
- [ ] **Image OCR**: No image text extraction
- [ ] **LLM Chat**: No ChatGPT interface (search-only)
- [ ] **API Server**: MCP server (future enhancement)

---

## 7. Success Criteria

### MVP Definition (Must-Have)

- [ ] Installation: `pip install qmd-python` works
- [ ] Indexing: `qmd collection add .` succeeds
- [ ] BM25 Search: Returns relevant results <50ms
- [ ] Vector Search: Returns semantic results <500ms
- [ ] Document Retrieval: `qmd get` displays content
- [ ] Windows Compatible: All features work on Windows 10+

### Production Ready (Should-Have)

- [ ] **Performance**: Meets all NFR-1 targets
- [ ] **Testing**: >80% code coverage
- [ ] **Documentation**: Complete README + examples
- [ ] **Error Handling**: Graceful failures, clear messages
- [ ] **Hybrid Search**: RRF + reranking functional
- [ ] **Contexts**: At least 1 collection configured

### Delighters (Nice-to-Have)

- [ ] **Shell Completion**: Bash/zsh auto-complete
- [ ] **MCP Server**: Model Context Protocol integration
- [ ] **Progress Bars**: Rich TUI during long operations
- [ ] **Config Validation**: Warn on misconfigurations
- [ ] **Export Formats**: JSON, CSV for agents

---

## 8. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| **LLM Download Fails** | HIGH | Mirror on HuggingFace, retry logic |
| **Windows llama-cpp** | MEDIUM | Official bindings (stable) |
| **ChromaDB Performance** | MEDIUM | Batch operations, caching |
| **Large Index** | LOW | Pagination, streaming |
| **User Data Loss** | HIGH | Hash dedup, WAL mode, backups |

---

## 9. Dependencies

### Runtime Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.10"
click = "^8.1"              # CLI framework
rich = "^13.0"             # Terminal formatting
pyyaml = "^6.0"            # YAML parsing
chromadb = "^0.4"           # Vector database
llama-cpp-python = "^0.2"  # LLM inference
```

### Development Dependencies

```toml
[tool.poetry.group.dev.dependencies]
pytest = "^7.0"            # Testing
pytest-cov = "^4.0"        # Coverage
pytest-benchmark = "^4.0"  # Performance
ruff = "^0.1"               # Linting
mypy = "^1.0"               # Type checking
```

---

## 10. Glossary

| Term | Definition |
|-------|-----------|
| **BM25** | Best Matching 25: Ranking function for full-text search |
| **ChromaDB** | Vector database for similarity search |
| **Cosine Similarity** | Measure of vector angle (0 = identical, 1 = orthogonal) |
| **DocID** | 6-character hash identifier (e.g., `#abc123`) |
| **Embedding** | 384-dim vector representing text semantics |
| **FTS5** | SQLite Full-Text Search extension |
| **GGUF** | Quantized model format (compressed weights) |
| **LLM** | Large Language Model (qwen3, embeddingemma) |
| **RRF** | Reciprocal Rank Fusion (combines ranked lists) |
| **Reranking** | LLM scoring of document relevance |
| **SHA-256** | Cryptographic hash (deduplication key) |

---

## 11. References

- **Original QMD**: https://github.com/tobi/qmd
- **llama-cpp-python**: https://github.com/abetlen/llama-cpp-python
- **ChromaDB**: https://docs.trychroma.com/
- **BM25 Paper**: https://en.wikipedia.org/wiki/Okapi_BM25
- **RRF Paper**: https://en.wikipedia.org/wiki/Reciprocal_rank_fusion
