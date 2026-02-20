# 推理引擎选型历程：从 llama-cpp 到 ONNX Runtime

> 日期：2026-02  
> 关联文件：`qmd/search/rerank.py`、`qmd/llm/engine.py`、`docs/deprecated/llama-cpp-python/`

---

## 背景

QMD-Python 的 TypeScript 原版（`qmd`）使用 `llama-cpp` 作为统一推理引擎，驱动三个模型：

| 角色 | TypeScript 方案 |
|------|----------------|
| Embedding | `embeddinggemma-300M-Q8_0.gguf`（Google Gemma 2B, 384d）|
| Reranker | `qwen3-reranker-0.6b-q8_0.gguf`（Qwen3 0.6B, `rankAndSort` API）|
| Query Expansion | `qmd-query-expansion-1.7B-q4_k_m.gguf`（Qwen3 0.6B Instruct）|

Python 移植的初始目标是：**沿用相同的 GGUF 模型 + llama-cpp-python 引擎**，保持架构对等。

---

## 第一阶段：llama-cpp-python 方案

### 方案描述

使用 `llama-cpp-python 0.3.16`（CUDA 12.1 预编译版本），通过 GGUF 格式加载所有模型。

```python
from llama_cpp import Llama

# Embedding
llama = Llama(model_path="embeddinggemma-300M-Q8_0.gguf", embedding=True)
vec = llama.embed("search query")   # → list[float] 384d

# Reranker
llama_reranker = Llama(model_path="qwen3-reranker-0.6b-q8_0.gguf")
scores = llama_reranker.rankAndSort(query, documents)
```

### Embedding 测试结果（BGE Small English v1.5 Q8_0）

BGE Small 兼容 BERT 架构，llama-cpp-python 正常加载，性能优秀：

| 指标 | 数值 |
|------|------|
| 模型大小 | 35 MB |
| 显存占用 | 22 MB |
| 加载时间 | 142 ms |
| 短文本延迟 | 5.48 ms |
| 吞吐量 | 187 texts/sec |

**结论：BGE 可用，但这是老架构（BERT）的特例。**

---

## 遇到的关键问题

### 问题一：Gemma Embedding 模型不受支持

原版 TypeScript 使用 `embeddinggemma-300M-Q8_0.gguf`（Google EmbeddingGemma，基于 Gemma 2B，384 维），  
但 `llama-cpp-python 0.3.16` **不支持** `gemma-embedding` 架构：

```
# 尝试加载 embeddinggemma-300M-Q8_0.gguf 时的错误：
llama_model_load: error loading model: unsupported model architecture: gemma-embedding
```

这是架构级的不兼容，不是参数问题。

**影响**：与 TypeScript 版本无法使用同一个 embedding 模型，向量维度（384d）也无法对齐。

---

### 问题二：Qwen3 Reranker GGUF 张量数不匹配

尝试加载 `qwen3-reranker-0.6b-q8_0.gguf`（与 TypeScript 版本相同的文件）：

```
load_tensors: wrong number of tensors; expected 311, got 310
```

llama-cpp-python 0.3.16 对 Qwen3 架构的 GGUF 格式支持不完整，模型内部张量数量与预期不符，无法加载。

---

### 问题三：无升级路径

尝试升级 llama-cpp-python 以支持新架构：

```bash
pip install --upgrade llama-cpp-python \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
```

**结果**：wheel index 上只有 0.3.16 和更旧的 0.3.4，没有更新的 CUDA 12.1 预编译版本。  
从源码编译需要本地 CUDA 工具链且风险较高，不在当前开发资源内。

**工程目录遗留文件**：
```
docs/deprecated/llama-cpp-python/wheels/
├── llama_cpp_python-0.3.16-cp310-cp310-win_amd64.whl
└── llama_cpp_python-0.3.4-cp310-cp310-win_amd64.whl
```

---

### 问题四：架构定位不匹配

llama-cpp 的设计目标是**自回归文本生成**（LLaMA、Mistral、Qwen 等），其 GGUF 格式和 `rankAndSort` API  
是为生成模型的 logit 排序设计的，并非 cross-encoder 类 reranker 的原生格式。

现代高质量 embedding/reranker 模型（Jina、BGE-M3、E5、Qwen3-Reranker seq-cls 等）主要以  
Transformer encoder 或 seq-cls 形式分发，GGUF 社区的量化覆盖明显滞后。

---

## 决策：放弃 llama-cpp-python

综合上述问题，llama-cpp-python 方案在当时（2026-02-19）正式归档：

| 问题 | 严重程度 | 是否可解 |
|------|----------|----------|
| Gemma embedding 架构不支持 | 🔴 阻断 | 否（需等上游支持）|
| Qwen3 Reranker 张量数错误 | 🔴 阻断 | 否（无升级路径）|
| 无更新版预编译 wheel | 🟡 高 | 需手动编译，成本高 |
| 生成模型定位 ≠ encoder 模型需求 | 🟠 中 | 架构性问题 |

归档目录：`docs/deprecated/llama-cpp-python/`

> **注**：llama-cpp-python 本身没有问题，它在自己的定位（LLM 生成推理）中非常优秀。
> 问题在于 encoder-class 模型（embedding、cross-encoder reranker）的 GGUF 支持在当时尚未成熟。

---

## 第二阶段：PyTorch + transformers 过渡方案

放弃 llama-cpp 后，临时改用 PyTorch 直接加载 HuggingFace 模型：

```python
# Reranker（PyTorch）
from transformers import AutoModelForSequenceClassification, AutoTokenizer
model = AutoModelForSequenceClassification.from_pretrained("Qwen/Qwen3-Reranker-0.6B")

# Expansion（PyTorch）
from transformers import AutoModelForCausalLM
model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct")
```

**问题**：PyTorch 本身约 2-3 GB（CUDA 版），且 reranker/expansion 是 torch 的唯一使用者；  
embedding 已切换到 fastembed（ONNX），引入 torch 纯属资源浪费。

---

## 第三阶段：全面迁移至 ONNX Runtime

### 为什么选择 ONNX Runtime

| 维度 | llama-cpp-python | PyTorch | **ONNX Runtime** |
|------|-----------------|---------|-----------------|
| Embedding 模型支持 | ❌ 新架构不兼容 | ✅ | ✅ |
| Reranker seq-cls 支持 | ❌ 无原生 API | ✅ | ✅ |
| Causal LM 生成 | ✅ | ✅ | ✅（手动 KV cache）|
| CUDA 加速 | ✅ | ✅ | ✅（CUDAExecutionProvider）|
| 安装体积 | ~100 MB | ~2-3 GB | ~200 MB（onnxruntime-gpu）|
| torch 依赖 | ❌ 无 | ✅ 必须 | ❌ 无需（fastembed 层独立）|
| 模型可用性 | GGUF 社区（滞后）| HF Hub（完整）| HF Hub ONNX（完整）|
| 量化格式选择 | 仅 GGUF | FP16/BF16 | INT8 / q4f16 / FP32 |

### 推理性能关键发现

迁移过程中发现了 ONNX Runtime 的一个重要性能陷阱：

**INT8 ONNX 模型在 CUDA EP 下的 fallback 问题**

```
providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
# 加载 INT8 量化模型 → 大量算子 fallback 到 CPU
# 每次 fallback: GPU数据 →(PCIe ~16GB/s)→ CPU计算 →(PCIe)→ GPU
# 结果：比纯 CPU 推理慢 10 倍以上
```

各量化格式在不同 EP 下的实际表现：

| 量化格式 | CPU EP | CUDA EP | 原因 |
|---------|--------|---------|------|
| INT8 | ✅ AVX512/VNNI 优化 | ❌ 算子 fallback，极慢 | INT8 MatMul 无 CUDA kernel |
| q4f16 | 🟡 一般 | ✅ `MatMulNBits` 原生 CUDA | onnxruntime-gpu ≥ 1.17 支持 |
| FP32 | 🟡 慢 | ✅ 全部原生支持 | 标准 CUDA 算子 |

### 各模型的最终选型

**Embedding**：`Xenova/jina-embeddings-v2-base-zh`，INT8 ONNX，768d  
→ fastembed-gpu 管理，INT8 embedding 算子 CUDA 支持完整，无 fallback

**Query Expansion**：`onnx-community/Qwen3-0.6B-ONNX`，**q4f16**  
→ 本地已有 5 种格式（FP32/INT8/q4/q4f16/quantized），选 q4f16：  
  - INT8 在 CUDA 上极慢（fallback），q4f16 `MatMulNBits` 原生 CUDA 支持  
  - 耗时：INT8 CUDA ~20s → q4f16 CUDA **~1s**

**Reranker**：`zhiqing/Qwen3-Reranker-0.6B-seq-cls-ONNX`，**FP32 Sequence Classification**  
→ 而非 Causal LM 格式（`thomasht86/Qwen3-Reranker-0.6B-int8-ONNX`）  
  - Causal LM 格式：每篇文档单独 forward，输出 `(1, seq, 151669)` vocab logits，串行 × 10 篇 ~28s  
  - Seq-Cls 格式：批量 forward，输出 `(batch, 1)`，一次完成，~0.1-0.3s  
  - FP32 所有算子原生 CUDA，无 fallback

---

## 优化时间线

| 时间 | 方案 | POST /query 耗时 |
|------|------|----------------|
| 初始 | PyTorch Causal LM reranker + CPU INT8 ONNX | ~26-30s |
| 改 1 | ONNX INT8 Causal LM reranker（CUDA，fallback）| ~28s |
| 改 2 | 强制 CPU EP（INT8 专为 CPU 优化）| ~5s |
| 改 3 | expansion 切换 q4f16 CUDA | ~4.5s |
| 改 4 | reranker 切换 seq-cls FP32 CUDA（批量推理）| **~1.5-2s** |

---

## 经验总结

1. **llama-cpp / GGUF 生态**：擅长 LLM 生成推理，encoder-class 模型支持滞后，不适合 embedding/seq-cls reranker 场景

2. **Gemma Embedding**：Google 的 embedding 变体（`gemma-embedding` 架构）在 llama-cpp 中不被支持，是阻断性问题

3. **INT8 ONNX 的使用场合**：INT8 量化是针对 CPU SIMD（AVX512/VNNI）优化的，不适合 GPU 推理；需要 GPU 推理时应选 q4f16（生成模型）或 FP32（分类模型）

4. **模型格式决定推理模式**：Causal LM 格式的 reranker 必须逐篇串行 forward；Sequence Classification 格式可批量并行，性能差距约 100 倍

5. **优先考察模型输出形状**：在集成一个新模型前，应先确认其输出张量形状（`session.get_outputs()`），避免在集成后才发现格式不匹配
