# Deprecated Approaches Archive

This directory contains failed or abandoned experimental approaches that were explored during QMD-Python development.

## 📁 Current Archives

### [llama-cpp-python/](./llama-cpp-python/)

**Status**: ❌ ABANDONED (2026-02-19)

**Summary**: Attempted to use llama-cpp-python as an alternative embedding engine for better performance and lower resource usage.

**Why Failed**:
- Model compatibility issues (Qwen3-Reranker, Gemma-embedding not supported)
- No viable upgrade path (llama-cpp-python 0.3.16 too old)
- Architectural mismatch with embedding/reranker models

**What Worked**:
- BGE Small English v1.5 (Q8_0) performed well (5-15ms latency)
- GPU acceleration worked on GTX 1660 Ti
- 3.5x smaller model size (35 MB vs 130 MB)

**What Didn't**:
- Qwen3-Reranker-0.6B failed to load (tensor count mismatch)
- Gemma-embedding models not supported
- No support for modern SOTA embedding architectures

**Decision**: Stick with PyTorch + fastembed for production use.

**Files**:
- `scripts/`: Test and benchmark scripts
- `wheels/`: Pre-built llama-cpp-python packages
- `reports/`: Performance analysis and results
- `README.md`: Detailed analysis and lessons learned

---

## 📝 Purpose of This Archive

### Why Keep Failed Experiments?

1. **Documentation**: Record what was tried and why it failed
2. **Learning**: Capture lessons learned for future reference
3. **Re-evaluation**: Allow re-assessment if technology improves
4. **Transparency**: Show the development process and decisions

### When to Revisit?

Re-evaluate archived approaches if:
- New versions release with breaking improvements
- Project requirements change significantly
- New information suggests viability
- Time/resources allow deeper investigation

---

## 🔍 Quick Reference

| Archive | Date | Status | Main Issue |
|---------|------|--------|------------|
| llama-cpp-python | 2026-02-19 | ❌ Abandoned | Model compatibility |
| (Future archives) | - | - | - |

---

## 💡 Archive Maintenance

**Adding New Archives**:
1. Create subdirectory with descriptive name
2. Move all related files
3. Write comprehensive README.md explaining:
   - What was attempted
   - Why it failed
   - What was learned
   - When/if to re-evaluate
4. Update this index

**Removing Archives**:
- **DON'T** - Keep for historical reference
- Exception: Security vulnerabilities (then document why deleted)

---

**Archive Maintained**: 2026-02-19
**Total Archives**: 1
