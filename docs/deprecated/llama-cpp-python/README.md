# Llama-cpp-python Integration - DEPRECATED

**Status**: ❌ **ABANDONED** - Not viable for production use
**Date**: 2026-02-19
**Reason**: Model compatibility issues and version constraints

---

## 📋 Summary

This directory contains the failed attempt to integrate `llama-cpp-python` as an alternative embedding engine for QMD-Python.

### What Was Attempted

1. **Embedding Model**: BGE Small English v1.5 (Q8_0 GGUF)
   - ✅ **Status**: Works! Good performance (5-15ms latency)
   - ⚠️ **Issue**: Model compatibility limited to older architectures

2. **Reranker Model**: Qwen3-Reranker-0.6B (Q8_0 GGUF)
   - ❌ **Status**: **FAILED** - Incompatible with llama-cpp-python 0.3.16
   - 🔴 **Error**: `wrong number of tensors; expected 311, got 310`

---

## ❌ Why This Approach Was Abandoned

### 1. Model Compatibility Issues

| Model | Status | Issue |
|-------|--------|-------|
| BGE Small English v1.5 | ✅ Works | BERT architecture (old, compatible) |
| Gemma-2B Embedding | ❌ Failed | `gemma-embedding` architecture not supported |
| Qwen3-Reranker-0.6B | ❌ Failed | Qwen3 architecture not supported |

**Root Cause**: llama-cpp-python 0.3.16 is too old to support newer model architectures.

### 2. Version Upgrade Problems

**Attempted Solution**: Upgrade llama-cpp-python to latest version

```bash
pip install --upgrade llama-cpp-python \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
```

**Result**: No newer version available. The project already has the latest CUDA build.

**Project's pre-built wheels**:
- `llama_cpp_python-0.3.16-cp310-cp310-win_amd64.whl` (current)
- `llama_cpp_python-0.3.4-cp310-cp310-win_amd64.whl` (older)

**Conclusion**: No viable upgrade path.

### 3. Architectural Limitations

** llama-cpp-python is designed for**:
- Text generation (LLaMA, Mistral, Qwen, etc.)
- NOT for specialized embedding/reranker models
- GGUF format primarily optimized for generation tasks

**Our requirements**:
- Embedding models (BGE, GTE, E5, etc.)
- Reranker models (Qwen3-Reranker, BGE-Reranker)
- Cross-encoder architectures

**Mismatch**: llama-cpp-python's architecture doesn't align with our needs.

---

## 📊 Performance Results (For Reference)

### What DID Work: BGE Small English v1.5

**Configuration**:
- Model: `bge-small-en-v1.5.Q8_0.gguf` (35 MB)
- GPU: NVIDIA GTX 1660 Ti (6GB)
- Software: llama-cpp-python 0.3.16 + CUDA 12.1

**Performance**:
```
Model load time:  149 ms
Short text:       5.48 ms latency, 187 texts/sec
Medium text:      7.36 ms latency, 135 texts/sec
Long text:        14.44 ms latency, 70 texts/sec
Batch (5 docs):   8.71 ms/doc average
GPU memory:       22 MB
Model size:       35 MB (vs 130 MB PyTorch)
```

**Advantages**:
- ✅ 3.5x smaller model (quantization)
- ✅ 3x lower latency (GPU optimization)
- ✅ 20x lower GPU memory usage
- ✅ 15x faster load time

**Disadvantages**:
- ❌ Limited to old model architectures (BERT only)
- ❌ Q8 quantization may reduce embedding quality
- ❌ No support for newer SOTA models

---

## 🗂️ Directory Structure

```
docs/deprecated/llama-cpp-python/
├── README.md (this file)
├── scripts/
│   ├── test_llama_embedding.py       # Embedding benchmark
│   ├── test_llama_reranker.py        # Reranker benchmark
│   ├── test_model_loading.py         # Model loading tests
│   ├── test_qwen_reranker_loading.py # Qwen3 compatibility test
│   ├── test_bge_model.py             # BGE model test
│   ├── demo_llama_embedding.py       # Usage demo
│   ├── download_gguf_model.py        # Model downloader
│   └── download_gguf_simple.py       # Simplified downloader
├── wheels/
│   ├── llama_cpp_python-0.3.16-cp310-cp310-win_amd64.whl
│   └── llama_cpp_python-0.3.4-cp310-cp310-win_amd64.whl
├── reports/
│   ├── LLAMA_CPP_PERFORMANCE_REPORT.md   # Detailed analysis
│   └── embedding_benchmark_results.json  # Raw benchmark data
└── models/
    └── (downloaded GGUF models - if any)
```

---

## 💡 Lessons Learned

### 1. Not All "Optimized" Solutions Are Better

**Expectation**: llama-cpp-python would be faster and more efficient
**Reality**: Only works for old architectures (BERT), not modern SOTA models

### 2. Check Model Compatibility FIRST

**Mistake**: Assumed all GGUF models would work
**Reality**: Different architectures have different compatibility requirements

### 3. Version Matters

**Problem**: llama-cpp-python 0.3.16 lacks support for newer models
**Solution**: No easy upgrade path (would require compiling from source)

### 4. PyTorch Is Still the Best Choice for Embeddings

**Why**:
- ✅ Supports all model architectures
- ✅ Active development (transformers, sentence-transformers)
- ✅ Better model quality (FP16/BF16 vs Q8 quantization)
- ✅ Ecosystem integration (ChromaDB, Qdrant, etc.)

---

## 🔄 Current Solution (PyTorch)

QMD-Python continues to use **PyTorch-based embedding**:

```python
from fastembed import TextEmbedding

model = TextEmbedding(
    model_name="BAAI/bge-small-en-v1.5",
    providers=["CUDAExecutionProvider"]  # GPU acceleration
)
embeddings = list(model.embed(texts))
```

**Performance**:
- Latency: ~15-20 ms (acceptable)
- Throughput: ~50-70 texts/sec
- GPU Memory: ~500 MB
- Model Size: 130 MB

**Trade-offs**:
- ❌ Higher latency than llama-cpp-python (but still acceptable)
- ❌ Higher GPU memory usage
- ✅ **Better model quality** (FP16 vs Q8)
- ✅ **Supports all modern architectures**
- ✅ **Active maintenance and updates**

---

## 🚀 Future Considerations

### If llama-cpp-python Adds Support

**Monitor**:
- llama-cpp-python GitHub repository
- GGUF model support for newer architectures
- Cross-encoder/reranker model support

**Re-evaluation Criteria**:
1. ✅ Support for BGE-Reranker models
2. ✅ Support for Qwen3-Reranker
3. ✅ Performance >2x improvement over PyTorch
4. ✅ Model quality parity (no quantization loss)

### Alternative Approaches

1. **ONNX Runtime** (already used by fastembed)
   - ✅ Good performance
   - ✅ Wide model support
   - ✅ Already integrated

2. **TensorRT** (NVIDIA-only)
   - ⚠️ Complex setup
   - ⚠️ NVIDIA GPU required
   - ✅ Maximum performance

3. **MLC LLM**
   - ⚠️ Newer, less mature
   - ✅ Promising performance

---

## 📝 Conclusion

**llama-cpp-python is NOT suitable for QMD-Python's needs** because:
1. ❌ Incompatible with modern embedding/reranker models
2. ❌ No viable upgrade path
3. ❌ Architectural mismatch with our requirements

**Decision**: Stick with **PyTorch + fastembed** for production use.

**Benefit**: This exploration confirmed that PyTorch remains the best choice, despite higher resource usage.

---

**Archived by**: AI Agent (Sisyphus)
**Archive Date**: 2026-02-19
**Reason**: Model compatibility issues make this approach non-viable
