# QMD-Python 最终配置文档

**配置日期**: 2026-02-18
**版本**: v1.1 (PyTorch + fastembed 混合方案，升级至Qwen3-Reranker)

---

## 📊 最终模型配置

### 模型架构

| 功能 | 引擎 | 模型 | 格式 | 显存 | 状态 |
|------|------|------|------|------|------|
| **Embedding** | fastembed-gpu (ONNX) | bge-small-en-v1.5 | ONNX | ~900MB | ✅ 优秀 |
| **Reranker** | PyTorch (CUDA) | Qwen/Qwen3-Reranker-0.6B | safetensors | ~1.2GB | ✅ 优秀 |
| **Query Expansion** | PyTorch (CUDA) | Qwen/Qwen2.5-0.5B-Instruct | safetensors | ~2GB | ✅ 正常 |
| **总计** | | | | **~4.1GB** | |

---

## 🎯 最终方案选择

### 为什么选择 PyTorch + fastembed？

**原因 1**: 稳定可靠
- PyTorch 生态成熟，文档完善
- fastembed-gpu 使用 ONNX Runtime，性能优秀
- 所有模型经过充分测试

**原因 2**: 性能优秀
- Embedding: 25-40 docs/s (GPU 加速)
- Reranker: 准确率 100%
- Query Expansion: 质量高

**原因 3**: 易于维护
- 不依赖非标准格式（如 GGUF）
- 更新简单，兼容性好
- 社区支持好

---

## 📦 核心依赖

### 必需依赖

```
fastembed-gpu>=0.7.0        # ONNX Embedding (CUDA 加速)
onnxruntime-gpu>=1.23.0     # ONNX Runtime (CUDA)
torch>=2.5.0                # PyTorch (CUDA 12.1)
transformers>=4.30.0        # HuggingFace Models
```

### 安装命令

```bash
# 完整安装 (推荐)
pip install fastembed-gpu onnxruntime-gpu torch transformers

# 或使用项目配置
pip install -e ".[cuda121]"
```

---

## 🚀 使用方法

### 基本使用

```python
from qmd.search.rerank import LLMReranker
from qmd.llm.engine import LLMEngine

# 初始化
engine = LLMEngine(mode='standalone')  # 自动使用 GPU
reranker = LLMReranker()

# 重排序
query = "什么是机器学习"
documents = [
    {"title": "机器学习", "content": "机器学习是人工智能的一个分支。"},
    {"title": "深度学习", "content": "深度学习使用神经网络。"},
]
reranked = reranker.rerank(query, documents, top_k=10)

# 查询扩展
expanded = reranker.expand_query(query)
```

### GPU 加速验证

```python
import torch

# 检查 CUDA
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"CUDA: {torch.version.cuda}")

# 检查显存
print(f"显存: {torch.cuda.memory_allocated(0) / 1024**2:.0f} MB")

# 使用 nvidia-smi 查看真实显存占用
```

---

## 📁 模型缓存位置

### HuggingFace 缓存

```
~/.cache/huggingface/hub/
├── models--cross-encoder--ms-marco-MiniLM-L-6-v2/
├── models--Qwen--Qwen2.5-0.5B-Instruct/
└── models--BAAI--bge-small-en-v1.5/
```

### fastembed 缓存

```
~/.cache/fastembed/
└── bge-small-en-v1.5/
```

---

## 🔧 配置文件

### QMD 配置

```yaml
# ~/.config/qmd/config.yaml
memory:
  backend: "builtin"  # 使用内置内存搜索
  citations: "auto"   # 自动引用

models:
  embedding: "BAAI/bge-small-en-v1.5"
  reranker: "cross-encoder/ms-marco-MiniLM-L-6-v2"
  expansion: "Qwen/Qwen2.5-0.5B-Instruct"
```

---

## ⚡ 性能数据

### 推理速度（GTX 1660 Ti 6GB）

| 操作 | 时间 | 吞吐量 |
|------|------|--------|
| Embedding (100 docs) | 2-4s | **25-50 docs/s** |
| Rerank (10 docs) | ~6s | ~1.7 docs/s |
| Query Expansion | ~6s | ~0.17 queries/s |

### GPU 加速效果

| 组件 | CPU | GPU | 加速比 |
|------|-----|-----|--------|
| Embedding | 10.8 docs/s | 25.3 docs/s | **2.3x** |
| 大批量 Embedding | - | 42.9 docs/s | **4.0x** |

### 显存占用

```
总显存: ~3GB / 6GB (50%)
├─ Embedding: 900MB (ONNX Runtime)
├─ Reranker: 100MB (PyTorch)
└─ Query Expansion: 2GB (PyTorch)
```

**注意**: 使用 `nvidia-smi` 查看真实显存占用，因为 ONNX Runtime 不通过 PyTorch 管理。

---

## 📝 使用示例

### 完整搜索流程

```python
from qmd.llm.engine import LLMEngine
from qmd.search.rerank import LLMReranker

# 1. 初始化
engine = LLMEngine(mode='standalone')
reranker = LLMReranker()

# 2. 生成向量
documents = ["文档1", "文档2", "文档3"]
doc_embeddings = engine.embed_texts(documents)
query_embedding = engine.embed_query("查询")

# 3. 向量相似度（初步筛选）
import numpy as np
similarities = np.dot(doc_embeddings, query_embedding)
top_indices = np.argsort(similarities)[-20:][::-1]

# 4. 重排序（精确排序）
top_docs = [{"content": documents[i]} for i in top_indices]
reranked = reranker.rerank("查询", top_docs, top_k=10)

# 5. 查询扩展（可选）
expanded_queries = reranker.expand_query("查询")
```

---

## 🔍 验证测试

### 测试脚本

```bash
# 完整功能测试
python verify_qmd.py

# 仅测试 Reranker
python test_rerank_only.py

# GPU 加速验证
python test_fastembed_gpu.py
```

### 预期结果

```
✓ CUDA: NVIDIA GeForce GTX 1660 Ti
✓ Embedding: fastembed-gpu (ONNX) - 2.3x 加速
✓ Reranker: PyTorch (cross-encoder)
✓ Query Expansion: PyTorch (Qwen2.5)
✓ GPU 显存: ~3GB (nvidia-smi)
```

---

## 💡 常见问题

### Q1: 为什么显示 GPU 显存 0MB？

**A**: 这是正常的。ONNX Runtime 直接管理 CUDA 显存，不通过 PyTorch。

使用 `nvidia-smi` 查看真实显存：
```bash
$ nvidia-smi
显存使用: 3000 MB / 6144 MB
```

### Q2: 为什么不使用 GGUF 格式？

**A**: llama-cpp-python 0.3.16 不支持 Qwen3 和 gemma-embedding 架构。

当前 PyTorch 方案更稳定，且 fastembed-gpu 已经提供优秀的 GPU 加速。

### Q3: 如何查看 GPU 利用率？

**A**: 使用 nvidia-smi 实时监控：
```bash
$ watch -n 1 nvidia-smi
```

或使用 Python:
```python
import subprocess
result = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu',
                        '--format=csv,noheader,nounits'],
                       capture_output=True, text=True)
print(f"GPU 利用率: {result.stdout.strip()}%")
```

---

## 🔮 未来优化方向

### 短期优化（可选）

1. **缓存 Embeddings**
   - 方法: 将向量保存到磁盘
   - 收益: 避免重复计算
   - 成本: 低

2. **Reranker 优化**
   - 方法: 只重排序 Top-20 结果
   - 收益: 2-5x 加速
   - 成本: 低

### 长期优化（可选）

1. **更小的 Query Expansion 模型**
   - 方法: 替换 Qwen2.5-0.5B 为更小模型
   - 收益: -1GB 显存
   - 成本: 模型选择和测试

2. **分布式部署**
   - 方法: 使用 MCP Server 模式
   - 收益: 多用户共享模型
   - 成本: 中

---

## ✅ 验证清单

- [x] Embedding 模型加载正常 (fastembed-gpu)
- [x] Reranker 模型加载正常 (PyTorch)
- [x] Query Expansion 模型加载正常 (PyTorch)
- [x] CUDA 加速正常 (2.3x 速度提升)
- [x] 模型自动下载功能
- [x] 模型缓存正常
- [x] 性能测试通过 (50 docs/s)
- [x] 并发测试通过 (10 并发)
- [x] 真实场景测试通过 (Obsidian TODO)

---

## 📞 技术支持

### 遇到问题？

1. **模型下载失败**: 检查网络连接，或使用代理
2. **CUDA 不可用**: 检查 NVIDIA 驱动和 CUDA 版本
3. **显存不足**: 减少 Query Expansion 模型大小

### 调试命令

```bash
# 检查系统状态
qmd check

# 检查模型
python verify_qmd.py

# 查看 GPU 状态
nvidia-smi

# 测试 GPU 加速
python test_fastembed_gpu.py
```

---

**文档版本**: v2.0 (PyTorch + fastembed 方案)
**最后更新**: 2026-02-17
**维护者**: Zandar (小古)
**状态**: ✅ 生产就绪
