# QMD 当前使用模型说明

> 最后更新：2026-02-20

---

## 总览

QMD Server 启动时加载三个 ONNX 模型，全部在服务端以单例形式持有，CLI 客户端通过 HTTP 共享：

| 角色 | 模型 | 格式 | 大小 | 推理设备 |
|------|------|------|------|----------|
| **Embedding** | `Xenova/jina-embeddings-v2-base-zh` | INT8 ONNX | 161 MB | CUDA（fastembed-gpu 管理）|
| **Reranker** | `zhiqing/Qwen3-Reranker-0.6B-seq-cls-ONNX` | FP32 ONNX | 1138 MB | CUDA |
| **Query Expansion** | `onnx-community/Qwen3-0.6B-ONNX` | q4f16 ONNX | 544 MB | CUDA（fallback CPU）|

---

## 1. Embedding 模型

### 基本信息

| 项目 | 值 |
|------|----|
| HuggingFace | `Xenova/jina-embeddings-v2-base-zh` |
| 本地文件 | `~/.qmd/models/onnx-int8_embedding/onnx/model_int8.onnx` |
| 向量维度 | 768 |
| 量化格式 | INT8 |
| Pooling | Mean Pooling + L2 Normalization |
| 语言支持 | 中文 + 英文 |
| 文件大小 | 161 MB |

### 推理配置

```
框架：fastembed-gpu（TextEmbedding）
Providers：['CUDAExecutionProvider', 'CPUExecutionProvider']
Batch size：32（可在 _state.py 中调整 GPU_EMBED_BATCH_SIZE）
注册方式：_register_jina_zh() → fastembed.TextEmbedding.add_custom_model()
逻辑名称：jinaai/jina-embeddings-v2-base-zh-int8
```

### 特点

- INT8 量化（Xenova 版）：CUDA EP 对嵌入模型的 INT8 算子支持完整，无 fallback 开销
- 中英双语：专为中文检索场景优化，也支持英文
- fastembed-gpu 管理模型生命周期，进程内单例，CLI 客户端无需重复加载

---

## 2. Reranker 模型

### 基本信息

| 项目 | 值 |
|------|----|
| HuggingFace | `zhiqing/Qwen3-Reranker-0.6B-seq-cls-ONNX` |
| 本地文件 | `~/.qmd/models/onnx-seq-cls_reranker/model.onnx` |
| 参数量 | 0.6B |
| 量化格式 | FP32（未量化） |
| 模型类型 | Sequence Classification（交叉编码器） |
| 输出格式 | `(batch, 1)` — 单个相关性 logit |
| 文件大小 | 1138 MB |

### 推理配置

```
框架：onnxruntime-gpu（raw InferenceSession）
Providers：['CUDAExecutionProvider', 'CPUExecutionProvider']
输入：input_ids, attention_mask（批量，padding=True）
批量推理：是（所有候选文档一次 forward）
Prompt 格式：Qwen3 ChatML，含 system prompt + <Query>/<Document> 标签 + <think> 占位
截断：doc_text[:300]，max_length=512
RERANK_TOP_N：10（RRF top-10 送入 reranker，剩余保持 RRF 排名）
```

### Prompt 格式

```
<|im_start|>system
Judge whether the Document meets the requirements based on the Query
and the Candidate Document, output "yes" or "no" to indicate
the relevance of the document.<|im_end|>
<|im_start|>user
<Query>{query}</Query>
<Document>{doc}</Document><|im_end|>
<|im_start|>assistant
<think>

</think>

```

### 特点

- **Sequence Classification 格式**：与 Causal LM 格式相比，前向一次即可评分所有文档（批量），而非逐篇串行
- **FP32 + CUDA**：所有算子原生 CUDA EP 支持，无 fallback 到 CPU 的开销
- **选型原因**：原方案（`thomasht86/Qwen3-Reranker-0.6B-int8-ONNX`）是 Causal LM，逐篇推理且 INT8 算子走 CPU fallback，10篇文档耗时 ~28s；新方案批量 forward 预计 ~0.1-0.2s

> **注**：原 INT8 Causal LM 格式在 CUDA EP 下的性能陷阱：INT8 MatMul 无 CUDA 原生 kernel，
> 每个算子均 fallback 到 CPU，并伴随 PCIe 数据搬运（~16GB/s），
> 导致 GPU 上的 INT8 模型比纯 CPU 推理慢 10 倍以上。

---

## 3. Query Expansion 模型

### 基本信息

| 项目 | 值 |
|------|----|
| HuggingFace | `onnx-community/Qwen3-0.6B-ONNX` |
| 本地文件 | `~/.qmd/models/onnx-causal-lm_expansion/onnx/model_q4f16.onnx` |
| 参数量 | 0.6B |
| 量化格式 | **q4f16**（INT4 weights + FP16 activations） |
| 模型类型 | Causal LM（自回归生成） |
| 文件大小 | 544 MB |

### 推理配置

```
框架：onnxruntime-gpu（raw InferenceSession）
Providers：['CUDAExecutionProvider', 'CPUExecutionProvider']
KV Cache 类型：float16（q4f16 模型要求，自动检测）
KV Cache 结构：28 层 × 8 heads × head_dim=128
解码方式：贪心解码（argmax），手动管理 KV cache
max_new_tokens：25
输入 max_length：512
```

### 推理流程

```
1. 将 query 包装为 ChatML prompt（apply_chat_template）
2. 初始化空 KV cache（float16，shape: [1, 8, 0, 128] × 28层 × key/value）
3. Prefill 阶段（past_seq=0）：处理完整 prompt，获得初始 KV cache
4. Decode 阶段：逐 token 推进，更新 KV cache，最多 25 步
5. 遇到 eos_token 提前终止
6. 解码输出，按换行分割为 query 变体（最多取前 2 条）
```

### 特点

- **q4f16 格式 + CUDA**：`MatMulNBits`（INT4 权重量化算子）在 onnxruntime-gpu ≥ 1.17 中有原生 CUDA kernel，无 fallback，GPU 加速有效
- **选型原因**：原 `model_int8.onnx` 在 CUDA EP 下同样存在 INT8 fallback 问题（约 20s/次）；切换到 q4f16 后约 1s/次
- **本地已有多种格式**：`model.onnx`（FP32, 2GB）、`model_int8.onnx`（590MB）、`model_q4.onnx`（877MB）、`model_q4f16.onnx`（544MB）、`model_quantized.onnx`（590MB）

---

## 4. 模型本地缓存目录

```
C:\Users\Administrator\.qmd\models\
├── onnx-int8_embedding/           # Embedding
│   └── onnx/model_int8.onnx      (161 MB)
├── onnx-seq-cls_reranker/         # Reranker（新）
│   └── model.onnx                (1138 MB)
├── onnx-causal-lm_expansion/      # Query Expansion
│   └── onnx/
│       ├── model_q4f16.onnx      (544 MB) ← 当前使用
│       ├── model_int8.onnx       (590 MB)
│       ├── model_q4.onnx         (877 MB)
│       ├── model_quantized.onnx  (590 MB)
│       └── model.onnx + .onnx_data (~2.3 GB, FP32)
├── embeddinggemma-300M-Q8_0.gguf  # 未使用（旧方案遗留）
└── qwen3-reranker-0.6b-q8_0.gguf  # 未使用（GGUF 格式，备选 llama-cpp 方案）
```

---

## 5. 性能基准（GTX 1660 Ti, 6GB VRAM）

| 步骤 | 耗时 | 设备 |
|------|------|------|
| Query Expansion | ~1.0s（25 decode steps） | CUDA |
| BM25 + Vector Search | ~0.5s | CPU / CUDA |
| RRF Fusion | <0.1s | CPU |
| Reranker（10 docs） | 预计 ~0.1-0.3s | CUDA |
| **总计** | **~2s** | |

> 优化历史：初始版本（PyTorch Causal LM reranker + CPU int8）约 26-30s；
> 经过 ONNX 迁移、格式切换（seq-cls）、批量推理改造，降至约 2s。

---

## 6. 模型选型备忘

| 场景 | 推荐 | 避免 |
|------|------|------|
| CUDA 上 reranker | FP32/FP16 Seq-Cls ONNX | INT8 Causal LM ONNX（CUDA fallback 灾难）|
| CUDA 上生成/扩展 | q4f16 ONNX（MatMulNBits 原生）| INT8 ONNX（同上）|
| CPU 上小模型 | INT8 ONNX（VNNI/AVX512 优化）| FP32（算力浪费）|
| 多进程共享模型 | qmd server 单例 + HTTP | 每进程独立加载（VRAM 翻倍）|
