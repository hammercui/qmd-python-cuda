# ⚠️ 历史文档归档说明

本目录包含项目早期探索阶段的技术文档和测试报告。

## 📌 架构变更记录 (2026-02-17)

**原方案**: llama.cpp (GGUF) 全家桶
**当前方案**: PyTorch + fastembed 混合方案

**变更原因**:
- llama-cpp-python 0.3.16 不支持 Qwen3 和 gemma-embedding 架构
- PyTorch 方案更稳定，性能优秀
- fastembed-gpu 提供 2.3x GPU 加速

## 📂 文档清单

### 测试报告

- **TEST_REPORT.md**
  - 核心功能测试
  - 包含已废弃的 llama-cpp 方案说明
  - 当前仍有效的：性能基准数据

- **OBSIDIAN_TEST_REPORT.md**
  - 真实场景测试结果
  - 包含已废弃的 llama-cpp 方案说明
  - 当前仍有效的：准确率 100%

- **BENCHMARK_REPORT.md**
  - Server + CLI 并发测试
  - 性能指标仍然有效

### 配置文档

- **FINAL_CONFIG.md**
  - ✅ 已更新为 PyTorch + fastembed 方案
  - 当前使用版本

## ✅ 当前架构（生产就绪）

```
Embedding:   fastembed-gpu (ONNX + CUDA)  → 25-50 docs/s
Reranker:    PyTorch (CUDA)               → 准确率 100%
Expansion:   PyTorch (CUDA)               → 质量优秀

总显存: ~3GB / 6GB (50%)
```

## 🔍 参考价值

这些历史文档记录了项目的技术探索过程，包括：

1. **GGUF vs PyTorch 对比**
2. **CUDA 环境配置**
3. **性能优化实验**
4. **架构决策过程**

**注意**: 文档中提到的 llama.cpp 和 GGUF 相关内容已废弃，请参考 FINAL_CONFIG.md 获取当前配置。

---

**归档日期**: 2026-02-17
**项目状态**: ✅ 生产就绪 (PyTorch + fastembed)
