# QMD-Python: Model Specifications

## Overview

**Purpose**: Complete reference for all LLM models used in QMD-Python.

**Model Strategy**: 
- Use **quantized GGUF** models for local inference
- All models from **HuggingFace** (auto-downloaded on first use)
- **Cached locally** in `~/.qmd/models/` (one-time download)

**Total Storage**: ~2GB for all models

---

## 1. Embedding Model

### Model: `embeddingemma-2b`

**Full Name**: `embeddingemma-300M-GGUF`

**Purpose**: Generate 384-dimensional vector embeddings for semantic search

**Specifications**:
| Attribute | Value |
|-----------|-------|
| **Base Model** | Gemma 2B (Google) |
| **Quantization** | Q8_0 (8-bit per weight) |
| **File Size** | ~300MB |
| **Embedding Dim** | 384 |
| **Context Window** | 512 tokens |
| **HuggingFace URI** | `hf:ggml-org/embeddinggemma-300M-GGUF/embeddinggemma-300M-Q8_0.gguf` |

**Prompt Format**:
```
# For queries
task: search result | query: {user_query}

# For documents
title: {document_title} | text: {document_content}
```

**Usage Example**:
```python
from llama_cpp import Llama

llama = Llama(model_path="~/.qmd/models/embeddinggemma-300M-Q8_0.gguf")
embedding = llama.embed("How to authenticate?")  # Returns list[float] (384-dim)
```

**Performance**:
- First query: 500-2000ms (model loading)
- Subsequent: 50-200ms per embedding
- Batch: ~50 chunks/second

**Alternatives** (if model unavailable):
```python
# Fallback models (same API)
hf:nousresearch/gemma-2b-it-GGUF/gemma-2b-it-Q8_0.gguf
hf:lm-studio/gemma-2b-GGUF
```

---

## 2. Reranking Model

### Model: `qwen3-reranker`

**Full Name**: `Qwen3-Reranker-0.6B-Q8_0-GGUF`

**Purpose**: Cross-encoder reranking for result relevance scoring

**Specifications**:
| Attribute | Value |
|-----------|-------|
| **Base Model** | Qwen3 0.6B (Alibaba) |
| **Quantization** | Q8_0 |
| **File Size** | ~640MB |
| **Output** | Relevance score (0.0 - 1.0) |
| **Context Window** | 512 tokens |
| **HuggingFace URI** | `hf:ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF/qwen3-reranker-0.6b-q8_0.gguf` |

**Prompt Format**:
```python
# Input: (query, [doc1, doc2, ...])
llama.rerank(query, documents)

# Output: [{file: doc1, score: 0.85}, {file: doc2, score: 0.32}, ...]
```

**Usage Example**:
```python
from llama_cpp import Llama

llama = Llama(model_path="~/.qmd/models/qwen3-reranker-0.6b-q8_0.gguf")

results = llama.rerank(
    query="how to authenticate",
    documents=[
        "The API uses OAuth2 for authentication",
        "Docker compose configuration",
        "Database schema design"
    ]
)
# Returns: [{"file": ..., "score": 0.92}, ...]
```

**Performance**:
- Latency: 100-300ms per 30 documents
- Throughput: ~100-300 docs/second

---

## 3. Query Expansion Model

### Model: `qwen3-query-expansion`

**Full Name**: `qmd-query-expansion-1.7B-gguf`

**Purpose**: Generate query variants for improved retrieval

**Specifications**:
| Attribute | Value |
|-----------|-------|
| **Base Model** | Qwen3 1.7B (Alibaba) |
| **Quantization** | Q4_K_M (4-bit, memory-optimized) |
| **File Size** | ~1.1GB |
| **Context Window** | 2048 tokens |
| **Output** | 2-3 query variants |
| **HuggingFace URI** | `hf:tobil/qmd-query-expansion-1.7B-gguf/qmd-query-expansion-1.7B-q4_k_m.gguf` |

**Prompt Format**:
```python
prompt = f"""Generate 2 alternative search queries for: {user_query}
Queries:"""

response = llama(prompt, max_tokens=50)
# Output: "authentication methods\nlogin process"
```

**Usage Example**:
```python
from llama_cpp import Llama

llama = Llama(model_path="~/.qmd/models/qmd-query-expansion-1.7B-q4_k_m.gguf")

def expand_query(query: str) -> list[str]:
    prompt = f"Generate 2 alternative search queries for: {query}\nQueries:"
    response = llama(prompt, max_tokens=50)
    return parse_queries(response)  # Returns ["query 1", "query 2"]
```

**Performance**:
- Latency: 500-1500ms per expansion
- Caching: Highly effective (same queries repeat)

---

## 4. Model Management

### 4.1 Download Process

**Automatic Download** (first use):
```python
from llama_cpp import Llama

# HuggingFace URIs auto-resolved
llama = Llama(
    model_path="hf:ggml-org/embeddinggemma-300M-GGUF/embeddinggemma-300M-Q8_0.gguf"
)
# Downloads to ~/.cache/llama_cpp/ or ~/.qmd/models/
```

**Manual Download** (optional):
```bash
# Using HuggingFace CLI
pip install huggingface-hub
huggingface-cli download ggml-org/embeddinggemma-300M-GGUF \
  --local-dir ~/.qmd/models/ \
  --local-dir-use-symlinks False
```

**Download Progress**:
```python
from llama_cpp import Llama
from rich.progress import Progress

with Progress() as progress:
    task = progress.add_task("[cyan]Downloading...", total=100)
    llama = Llama(model_path="hf:...", verbose=True)  # Shows progress
```

### 4.2 Model Caching

**Cache Location**:
```python
import os
from pathlib import Path

# Priority order:
model_paths = [
    Path("~/.qmd/models/").expanduser(),      # Custom (user-set)
    Path("~/.cache/llama_cpp/").expanduser(),  # Default llama-cpp
    Path("~/.cache/huggingface/").expanduser(), # HF hub
]
```

**Cache Verification**:
```python
def verify_models() -> dict[str, bool]:
    """Check which models are downloaded."""
    models = {
        "embedding": "embeddinggemma-300M-Q8_0.gguf",
        "reranker": "qwen3-reranker-0.6b-q8_0.gguf",
        "expansion": "qmd-query-expansion-1.7B-q4_k_m.gguf"
    }
    
    status = {}
    for name, filename in models.items():
        path = Path("~/.qmd/models/") / filename
        status[name] = path.expanduser().exists()
    
    return status
```

**Status Output**:
```bash
$ qmd status --models

Model Status:
  ✅ embeddingemma-2b (300MB) - Cached
  ✅ qwen3-reranker (640MB) - Cached
  ❌ qwen3-query-expansion (1.1GB) - Not cached
     Run 'qmd download --models' to fetch
```

### 4.3 Model Storage

**Disk Usage**:
| Model | File | Size |
|-------|------|------|
| Embedding | `embeddinggemma-300M-Q8_0.gguf` | 300MB |
| Reranker | `qwen3-reranker-0.6b-q8_0.gguf` | 640MB |
| Expansion | `qmd-query-expansion-1.7B-q4_k_m.gguf` | 1.1GB |
| **Total** | | **~2GB** |

**Cleanup** (optional):
```bash
# Remove all models
rm -rf ~/.qmd/models/

# Remove specific model
rm ~/.qmd/models/embeddinggemma-300M-Q8_0.gguf

# Re-download
qmd download --models
```

---

## 5. Model Configuration

### 5.1 llama-cpp-python Parameters

**Shared Settings**:
```python
Llama(
    model_path="path/to/model.gguf",
    n_threads=4,              # Autodetect CPU cores
    n_ctx=2048,               # Context window
    n_batch=512,              # Batch size (prompt processing)
    n_gpu_layers=0,           # GPU layers (0 = CPU only)
    verbose=False,            # Disable llama.cpp logging
    use_mmap=True,            # Memory-map model (faster load)
    use_mlock=False,          # Don't lock model in RAM
)
```

**Per-Model Settings**:

**Embedding Model**:
```python
Llama(
    model_path="embeddinggemma...",
    n_ctx=512,                # Short context (docs)
    embedding=True,           # Enable embedding mode
)
```

**Reranker**:
```python
Llama(
    model_path="qwen3-reranker...",
    n_ctx=512,                # Query + doc snippets
    reranking=True,           # Enable reranking mode
)
```

**Query Expansion**:
```python
Llama(
    model_path="qwen3-query-expansion...",
    n_ctx=2048,               # Longer context
    n_batch=512,              # Larger batch
)
```

### 5.2 Environment Variables

```bash
# Model directory (override default)
export LLAMA_CPP_MODELS_PATH="/custom/path"

# Thread count (auto-detect if not set)
export LLAMA_CPP_THREADS=8

# GPU layers (NVIDIA CUDA only)
export LLAMA_CPP_N_GPU_LAYERS=99

# Memory lock (prevent swap)
export LLAMA_CPP_USE_MLOCK=1
```

---

## 6. Prompt Engineering

### 6.1 Embedding Prompts

**Query Embedding**:
```python
def format_query_for_embedding(query: str) -> str:
    return f"task: search result | query: {query}"
```

**Document Embedding**:
```python
def format_doc_for_embedding(title: str, content: str) -> str:
    # Truncate to 512 tokens (~2048 chars)
    truncated = content[:2000]  # 4 chars/token approximation
    
    return f"""title: {title} | text: {truncated}"""
```

**Why This Format?**
- Prefix (`task:`, `title:`) guides model
- Separator (`|`) disambiguates sections
- Truncation prevents context overflow

### 6.2 Query Expansion Prompts

**System Prompt** (implicit):
```python
# Qwen3 is instruction-tuned, so:
prompt = f"""Generate 2 alternative search queries for: {query}
Queries:"""

response = llama(prompt, max_tokens=50)
```

**Expected Output**:
```
authentication methods
login process
```

**Parsing**:
```python
def parse_expansion(response: str) -> list[str]:
    lines = response.strip().split('\n')
    return [line.strip() for line in lines if line.strip()]
```

### 6.3 Reranking Prompts

**No Prompt Required** (automatic):
```python
# llama-cpp's rerank() handles it
results = llama.rerank(query, documents)
# Returns sorted by relevance score
```

---

## 7. Performance Tuning

### 7.1 CPU Optimization

**Thread Count**:
```python
import os

# Auto-detect
n_threads = os.cpu_count() or 4

# Or set explicitly
llama = Llama(..., n_threads=8)
```

**Batch Size**:
```python
# Larger batch = faster throughput, more memory
llama = Llama(..., n_batch=512)  # Default
llama = Llama(..., n_batch=1024)  # Faster (if RAM available)
```

### 7.2 Memory Optimization

**Context Window**:
```python
# Reduce to save RAM
llama = Llama(..., n_ctx=512)   # ~1GB
llama = Llama(..., n_ctx=2048)  # ~1.5GB
```

**Quantization Trade-off**:
| Quantization | Size | Quality | RAM |
|--------------|------|--------|-----|
| **Q4_K_M** | 1.1GB | Good (4-bit) | 1GB |
| **Q8_0** | 300MB | Best (8-bit) | 1.5GB |
| **F16** | 2GB | Excellent | 2GB |

**Recommendation**: Use Q8_0 for embedding (quality matters), Q4_K_M for expansion (speed matters).

### 7.3 GPU Acceleration (Optional)

**Requirements**:
- NVIDIA GPU with CUDA support
- `pip install llama-cpp-python` (with CUDA)

**Enable GPU**:
```python
llama = Llama(
    model_path="...",
    n_gpu_layers=-1,  # -1 = all layers to GPU
    n_threads=4,       # CPU threads for pre/post-processing
)
```

**Expected Speedup**:
- Embedding: 2-5x faster
- Reranking: 3-10x faster
- Expansion: 2-3x faster

**Caveat**: GPU memory must fit model (check with `nvidia-smi`).

---

## 8. Troubleshooting

### 8.1 Model Download Fails

**Symptom**: `FileNotFoundError: model.gguf`

**Diagnosis**:
```bash
# Check HuggingFace connection
pip install huggingface-hub
huggingface-cli scan ggml-org/embeddinggemma-300M-GGUF
```

**Fixes**:
```bash
# 1. Use proxy (if in China)
export HF_ENDPOINT=https://hf-mirror.com

# 2. Manual download
wget https://huggingface.co/ggml-org/.../model.gguf \
  -O ~/.qmd/models/model.gguf

# 3. Verify download
sha256sum ~/.qmd/models/*.gguf
```

### 8.2 Model Load Slow

**Symptom**: First query takes >10 seconds

**Diagnosis**:
```python
import time
start = time.time()
llama = Llama(model_path="...")
print(f"Load time: {time.time() - start:.1f}s")
```

**Fixes**:
```python
# 1. Use mmap (faster file reading)
llama = Llama(..., use_mmap=True)

# 2. Reduce context window
llama = Llama(..., n_ctx=512)

# 3. Disable verbosity (faster)
llama = Llama(..., verbose=False)
```

### 8.3 OOM (Out of Memory)

**Symptom**: `MemoryError` or system swap

**Diagnosis**:
```bash
# Check RAM usage
free -h  # Linux
wmic OS get FreePhysicalMemory  # Windows
```

**Fixes**:
```python
# 1. Reduce batch size
llama = Llama(..., n_batch=256)

# 2. Use smaller model
# Q4_K_M instead of Q8_0

# 3. Process documents sequentially (not parallel)
```

---

## 9. Model Alternatives

### 9.1 Embedding Models

**Option 1: `all-MiniLM-L6-v2`** (SentenceTransformers)
- **Size**: 80MB
- **Dim**: 384
- **Quality**: Good (but not GGUF)
- **Download**: `pip install sentence-transformers`

**Option 2: `bge-small-en-v1.5`**
- **Size**: 130MB
- **Dim**: 384
- **Quality**: Excellent
- **GGUF**: Not available (use PyTorch)

**Recommendation**: Stick with `embeddingemma` (GGUF format for llama-cpp).

### 9.2 Reranking Models

**Option 1: `bge-reranker-base`**
- **Size**: 1.1GB
- **Quality**: State-of-the-art
- **GGUF**: Not available

**Option 2: FlashRank (lightweight)**
- **Size**: 10MB
- **Quality**: Good enough
- **GGUF**: Not available

**Recommendation**: Use `qwen3-reranker` if GGUF required, else `bge-reranker`.

---

## 10. Glossary

| Term | Definition |
|-------|-----------|
| **GGUF** | Quantized model format (compressed weights) |
| **Q8_0** | 8-bit quantization (near-original quality) |
| **Q4_K_M** | 4-bit quantization (memory-optimized) |
| **Embedding** | Vector representation of text (384-dim) |
| **Reranking** | LLM scoring of document relevance |
| **Query Expansion** | Generating query variants |
| **Context Window** | Max tokens model can process |
| **llama-cpp** | C++ inference engine for GGUF models |

---

## 11. References

- **llama-cpp-python**: https://github.com/abetlen/llama-cpp-python
- **GGUF Models**: https://huggingface.co/models?search=gguf
- **EmbeddingGemma**: https://huggingface.co/ggml-org/embeddinggemma-300M-GGUF
- **Qwen3**: https://huggingface.co/Qwen
- **Quantization**: https://github.com/ggerganov/llama.cpp/master/quantization
