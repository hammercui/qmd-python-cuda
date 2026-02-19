# 重排序与查询扩展模型 ONNX 迁移分析文档

> **目标**：将 Reranker 和 Query Expansion 从 PyTorch (transformers) 替换为 ONNX 量化版本，降低显存占用、减少依赖。  
> **日期**：2026-02

---

## 1. 当前实现分析

### 1.1 当前模型栈（`qmd/search/rerank.py`）

| 组件 | 当前模型 | 框架 | 大小 | 类型 |
|------|---------|------|------|------|
| Reranker | `Qwen/Qwen3-Reranker-0.6B` | PyTorch (transformers) | ~1200 MB | `AutoModelForSequenceClassification` |
| Query Expansion | `Qwen/Qwen2.5-0.5B-Instruct` | PyTorch (transformers) | ~1000 MB | `AutoModelForCausalLM` |

### 1.2 当前依赖

```toml
# pyproject.toml 中 cuda/cpu 选项均包含
"torch>=2.0.0"
"transformers>=4.30.0"
```

PyTorch 本身约 2~3 GB（CUDA 版本），其中 `torch` 是为 reranker/expansion 专门引入的。  
**embed 模型已经不依赖 torch**（fastembed/ONNX）——意味着 reranker/expansion 是 torch 的唯一使用者。

### 1.3 当前推理流程

**Reranker（前向推理，最简单）：**
```python
# rerank.py L174~190
inputs = self._tokenizer(pairs, padding=True, truncation=True, return_tensors="pt")
inputs = {k: v.to(self._device) for k, v in inputs.items()}
outputs = self._model(**inputs)
scores = outputs.logits.squeeze(-1)
```

**Query Expansion（自回归生成，较复杂）：**
```python
# rerank.py L143~155
outputs = self._expansion_model.generate(
    **inputs,
    max_new_tokens=50,
    temperature=0.7,
    do_sample=True,
    pad_token_id=self._expansion_tokenizer.eos_token_id,
)
```

---

## 2. ONNX 替换方案

### 2.1 Reranker → ONNX

#### 可行性评估：✅ **高度可行（最简单）**

Reranker 是纯**前向推理**（forward pass），无需自回归解码：
- 输入：`[query, document]` 文本对
- 输出：`logits`（relevance score）
- 无 KV Cache、无 token-by-token 循环

ONNX 对纯前向推理的支持最成熟，**可以做到 API 级别无感替换**。

#### 候选 ONNX 模型

| 仓库 | 量化 | 文件大小 | 显存占用 | 推荐度 |
|------|------|---------|---------|-------|
| `dandingzai/qwen3-reranker-0.6b-onnx` | q4f16 | ~300 MB | ~400-600 MB | — |
| `onnx-community/Qwen3-Reranker-0.6B` | q4f16 | ~350 MB | ~500-700 MB | ✅ **已选定** |

对比当前 PyTorch 版（~1200 MB，显存 ~800-1000 MB），**体积缩减 4x，显存缩减约 50%**。

#### 推荐方案：`optimum[onnxruntime]`

`Hugging Face optimum` 库提供 `ORTModelForSequenceClassification`，与 `AutoModelForSequenceClassification` 接口**完全兼容**：

```python
# 旧（PyTorch）
from transformers import AutoTokenizer, AutoModelForSequenceClassification

self._tokenizer = AutoTokenizer.from_pretrained(model_path)
self._model = AutoModelForSequenceClassification.from_pretrained(model_path)
self._model.to(self._device)
self._model.eval()

# ─────────────────────────────────────────────

# 新（ONNX via optimum）
from optimum.onnxruntime import ORTModelForSequenceClassification
from transformers import AutoTokenizer

provider = "CUDAExecutionProvider" if self._device == "cuda" else "CPUExecutionProvider"

self._tokenizer = AutoTokenizer.from_pretrained(model_path)
self._model = ORTModelForSequenceClassification.from_pretrained(
    model_path,
    file_name="onnx/model_q4f16.onnx",   # 指定量化文件
    provider=provider,               # GPU/CPU 由此控制，无需 .to(device)
)
# 无需 .to(device)，无需 .eval()
```

**推理代码改动量：0 行**（`model(**inputs)` 接口完全相同）。

---

### 2.2 Query Expansion → ONNX

#### 可行性评估：✅ **可行（有一定复杂度）**

Query Expansion 使用**自回归 LLM 生成**（`model.generate()`），ONNX 处理此类任务有两个路径：

| 方案 | 库 | API 兼容性 | 性能 | 复杂度 |
|------|----|-----------|------|-------|
| **A：optimum ORTModelForCausalLM** | `optimum[onnxruntime]` | ✅ `generate()` 相同 | 中 | 低 |
| **B：onnxruntime-genai** | `onnxruntime-genai` | ❌ 全新 API | 高 | 高 |
| **C：GGUF (llama.cpp)** | `llama-cpp-python` | 不同 API | 高 | 中 |

**推荐选择方案 A**（`ORTModelForCausalLM`），理由：
- `generate()` 方法与 PyTorch `AutoModelForCausalLM` 签名**完全相同**
- 当前代码仅需改 2 行（import + from_pretrained）
- 已有 `onnxruntime-gpu` 环境

#### 候选 ONNX 模型（均为 Qwen3-0.6B）

| 仓库 | 量化类型 | 大小 | 显存 | 特点 |
|------|---------|------|------|------|
| `onnx-community/Qwen3-0.6B-Instruct-ONNX` | q4f16 | ~300 MB | ~600-800 MB | ✅ **已选定**，官方 Instruct 格式 |
| `onnx-community/Qwen3-0.6B-DQ-ONNX` | 动态量化 | ~300 MB | ~600-800 MB | 动态量化，推理速度可能更快 |

> **注意**：当前代码用的是 `Qwen/Qwen2.5-0.5B-Instruct`，升级到 `Qwen3-0.6B-Instruct` 是同时升级模型版本（Qwen2.5 → Qwen3），prompt 格式需确认兼容性。

#### 推荐方案：`ORTModelForCausalLM`

```python
# 旧（PyTorch）
from transformers import AutoTokenizer, AutoModelForCausalLM

self._expansion_tokenizer = AutoTokenizer.from_pretrained(model_path)
self._expansion_model = AutoModelForCausalLM.from_pretrained(model_path)
self._expansion_model.to(self._device)
self._expansion_model.eval()

# ─────────────────────────────────────────────

# 新（ONNX via optimum）
from optimum.onnxruntime import ORTModelForCausalLM
from transformers import AutoTokenizer

provider = "CUDAExecutionProvider" if self._device == "cuda" else "CPUExecutionProvider"

self._expansion_tokenizer = AutoTokenizer.from_pretrained(model_path)
self._expansion_model = ORTModelForCausalLM.from_pretrained(
    model_path,
    file_name="onnx/model_q4f16.onnx",
    provider=provider,
    use_cache=True,       # 启用 KV Cache 加速生成
    use_io_binding=True,  # GPU 上进一步优化
)
```

**`generate()` 调用代码完全不变**：
```python
# expand_query() 中的 generate() 调用保持原样
outputs = self._expansion_model.generate(
    **inputs,
    max_new_tokens=50,
    temperature=0.7,
    do_sample=True,
    pad_token_id=self._expansion_tokenizer.eos_token_id,
)
```

---

## 3. 与 Qwen3 Prompt 格式变化

从 `Qwen2.5-0.5B-Instruct` → `Qwen3-0.6B-Instruct` 时，两者均使用 ChatML 格式，**prompt 模板基本兼容**：

```
<|im_start|>system\n{system}<|im_end|>\n
<|im_start|>user\n{user}<|im_end|>\n
<|im_start|>assistant\n
```

当前代码用的是原始 prompt（非 ChatML），对两个模型均可用。若要最优效果，可改为 `apply_chat_template`：

```python
messages = [
    {"role": "user", "content": f"给以下搜索词生成 2 个同义变体，每行一个：\n{query}"}
]
prompt = self._expansion_tokenizer.apply_chat_template(
    messages, tokenize=False, add_generation_prompt=True
)
```

---

## 4. 依赖变更

### 4.1 新增依赖

```toml
# pyproject.toml 新增 onnx 可选组
[project.optional-dependencies]
onnx = [
    "optimum[onnxruntime]>=1.20.0",   # 提供 ORTModelFor* 系列
    # onnxruntime-gpu 已由 fastembed-gpu 引入，无需重复声明
]
```

实际安装命令：
```bash
pip install "optimum[onnxruntime]>=1.20.0"
```

> `optimum[onnxruntime]` 会依赖 `onnxruntime`（CPU 版）或可与已有的 `onnxruntime-gpu` 共存。  
> 当前已安装 `onnxruntime-gpu==1.22.0`，**无需重新安装**，`optimum` 会自动使用它。

### 4.2 可以移除的依赖

ONNX 化后，`torch` 仅剩 device detection 用途，可用纯 `onnxruntime` 方式替代：

```python
# 旧（需要 torch）
import torch
device = "cuda" if torch.cuda.is_available() else "cpu"

# 新（不需要 torch）
import onnxruntime as ort
providers = ort.get_available_providers()
device = "cuda" if "CUDAExecutionProvider" in providers else "cpu"
```

若完成此改造，可将 `pyproject.toml` 中的 `"torch>=2.0.0"` 从 `cuda/cpu` 依赖组移除，**显著减小安装体积**。

### 4.3 依赖体积对比

| 组件 | 当前（PyTorch） | ONNX 后 |
|------|----------------|---------|
| `torch` (CUDA) | ~2500 MB | ❌ 可移除 |
| `transformers` | ~10 MB | ✅ 保留（tokenizer 仍需用） |
| `optimum[onnxruntime]` | ❌ 未安装 | ~15 MB |
| `onnxruntime-gpu` | 已安装 | ✅ 已有 |
| **安装包净减少** | — | **~2500 MB** |

---

## 5. 需要修改的文件

### 5.1 `qmd/search/rerank.py`

**Reranker 加载部分（`model` property，约 L55~L82）：**

```python
# 旧
from transformers import AutoTokenizer, AutoModelForSequenceClassification
self._tokenizer = AutoTokenizer.from_pretrained(model_path)
self._model = AutoModelForSequenceClassification.from_pretrained(model_path)
self._model.to(self._device)
self._model.eval()
self._torch = torch

# 新
from optimum.onnxruntime import ORTModelForSequenceClassification
from transformers import AutoTokenizer
provider = "CUDAExecutionProvider" if self._device == "cuda" else "CPUExecutionProvider"
self._tokenizer = AutoTokenizer.from_pretrained(model_path)
self._model = ORTModelForSequenceClassification.from_pretrained(
    model_path, file_name="onnx/model_q4f16.onnx", provider=provider
)
# self._torch 不再需要
```

**Expansion 加载部分（`expansion_model` property，约 L85~L115）：**

```python
# 旧
from transformers import AutoTokenizer, AutoModelForCausalLM
self._expansion_model = AutoModelForCausalLM.from_pretrained(model_path)
self._expansion_model.to(self._device)

# 新
from optimum.onnxruntime import ORTModelForCausalLM
from transformers import AutoTokenizer
provider = "CUDAExecutionProvider" if self._device == "cuda" else "CPUExecutionProvider"
self._expansion_model = ORTModelForCausalLM.from_pretrained(
    model_path, file_name="onnx/model_q4f16.onnx", provider=provider,
    use_cache=True
)
```

**`rerank()` 方法中的 torch 引用（L174~190）：**

```python
# 旧
with self._torch.no_grad():
    inputs = {k: v.to(self._device) for k, v in inputs.items()}
    outputs = self._model(**inputs)

# 新（ORTModel 不需要 torch.no_grad 和 .to(device)）
outputs = self._model(**inputs)
```

**`expand_query()` 方法中的 torch 引用（L143~155）：**

```python
# 旧
import torch
inputs = {k: v.to(self._device) for k, v in inputs.items()}
with torch.no_grad():
    outputs = self._expansion_model.generate(...)

# 新（移除 torch 依赖和 .to(device)）
outputs = self._expansion_model.generate(...)
```

**`_get_device()` 函数（L1~L20）：**

```python
# 旧（依赖 torch）
def _get_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        ...

# 新（依赖 onnxruntime）
def _get_device() -> str:
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        if "CUDAExecutionProvider" in providers:
            return "cuda"
        elif "CoreMLExecutionProvider" in providers:
            return "mps"
    except ImportError:
        pass
    return "cpu"
```

### 5.2 `qmd/models/downloader.py`

更新 MODELS 字典中的 `reranker` 和 `expansion` 配置：

```python
# 旧
MODELS = {
    "reranker": {
        "hf": "Qwen/Qwen3-Reranker-0.6B",   # PyTorch
        "ms": "Qwen/Qwen3-Reranker-0.6B",
        "size_mb": 1200,
        "type": "cross-encoder",
    },
    "expansion": {
        "hf": "Qwen/Qwen2.5-0.5B-Instruct", # PyTorch Qwen2.5
        "ms": "Qwen/Qwen2.5-0.5B-Instruct",
        "size_mb": 1000,
        "type": "llm",
    },
}

# 新
MODELS = {
    "reranker": {
        "hf": "onnx-community/Qwen3-Reranker-0.6B",     # ONNX q4f16（已选定）
        "ms": "Qwen/Qwen3-Reranker-0.6B",              # ModelScope 无 ONNX 版，回退 PyTorch
        "size_mb": 400,
        "type": "onnx-reranker",
        "model_file": "onnx/model_q4f16.onnx",
    },
    "expansion": {
        "hf": "onnx-community/Qwen3-0.6B-Instruct-ONNX",  # ONNX q4f16（已选定）
        "ms": "Qwen/Qwen2.5-0.5B-Instruct",                # ModelScope 回退
        "size_mb": 400,
        "type": "onnx-causal-lm",
        "model_file": "onnx/model_q4f16.onnx",
    },
}
```

### 5.3 `qmd/llm/engine.py`

`LLMEngine` 中的 `_get_device()` 依赖也需同步更新（目前 engine.py 用 torch 检测 VRAM）：

```python
# 当前（engine.py L103~115）：VRAM 检测用 torch，这部分可以保留
# 因为 embed 模型的显存检测逻辑可能仍需要，
# 但如果 torch 完全移除，需改为 onnxruntime 或 pynvml 检测方式
```

---

## 6. 显存占用对比（升级前 vs 升级后）

> 假设同时运行 embed + reranker + expansion：

| 模型 | 当前 PyTorch | ONNX 升级后 |
|------|-------------|------------|
| Embed (BGE-M3 FP16) | 1081 MB | 1081 MB（不变） |
| Embed (BGE-M3 INT8) | — | **542 MB** |
| Reranker | ~800-1000 MB | **~400-600 MB** |
| Query Expansion | ~600-800 MB | **~600-800 MB** |
| torch runtime | ~300-500 MB | **~0 MB**（移除） |
| **合计** | **~2700-3300 MB** | **~1542-1942 MB** |
| **节省** | — | **~1000-1400 MB** |

对于 6GB 显存的 GPU 来说，从可能 OOM → 舒适运行。

---

## 7. ModelScope 镜像问题

`dandingzai/qwen3-reranker-0.6b-onnx` 和 `onnx-community/Qwen3-0.6B-Instruct-ONNX` **在 ModelScope 上暂无对应 ONNX 量化版**。

国内用户的选项：

| 方案 | 说明 |
|------|------|
| **方案 A**：使用 HF 镜像 | `HF_ENDPOINT=https://hf-mirror.com` 设置镜像后下载 |
| **方案 B**：本地手动量化 | 用 `optimum-cli` 从 ModelScope 下载 PyTorch 版再量化 |
| **方案 C**：回退 PyTorch（ModelScope） | downloader.py 中 CN 用户回退到 PyTorch 版 |

**方案 B 命令（本地量化）：**
```bash
# 从 ModelScope 下载 PyTorch 版
modelscope download --model Qwen/Qwen3-Reranker-0.6B --local_dir ./qwen3-reranker-pt

# 量化为 q4f16 ONNX
optimum-cli export onnx \
    --model ./qwen3-reranker-pt \
    --task sequence-classification \
    --quantize \
    --quantization-config avx512_vnni \
    ./qwen3-reranker-onnx/
```

---

## 8. 实施步骤（推荐顺序）

### Phase 1：验证 ONNX 模型可用性
```bash
# 安装 optimum
pip install "optimum[onnxruntime]>=1.20.0"

# 快速验证 reranker
python -c "
from optimum.onnxruntime import ORTModelForSequenceClassification
from transformers import AutoTokenizer
model = ORTModelForSequenceClassification.from_pretrained(
    'onnx-community/Qwen3-Reranker-0.6B',
    file_name='onnx/model_q4f16.onnx',
    provider='CUDAExecutionProvider'
)
tokenizer = AutoTokenizer.from_pretrained('onnx-community/Qwen3-Reranker-0.6B')
inputs = tokenizer([['search query', 'relevant document']], return_tensors='pt', padding=True)
outputs = model(**inputs)
print('Reranker ONNX OK! logits:', outputs.logits)
"
```

```bash
# 快速验证 query expansion
python -c "
from optimum.onnxruntime import ORTModelForCausalLM
from transformers import AutoTokenizer
model = ORTModelForCausalLM.from_pretrained(
    'onnx-community/Qwen3-0.6B-Instruct-ONNX',
    file_name='onnx/model_q4f16.onnx',
    provider='CUDAExecutionProvider',
    use_cache=True
)
tokenizer = AutoTokenizer.from_pretrained('onnx-community/Qwen3-0.6B-Instruct-ONNX')
inputs = tokenizer('Generate query variants: python async programming', return_tensors='pt')
outputs = model.generate(**inputs, max_new_tokens=30)
print('Expansion ONNX OK!', tokenizer.decode(outputs[0]))
"
```

### Phase 2：修改 `qmd/search/rerank.py`
1. 替换 `_get_device()` 中 torch → onnxruntime
2. 修改 `model` property：`ORTModelForSequenceClassification`
3. 修改 `expansion_model` property：`ORTModelForCausalLM`
4. 清理 `rerank()` 和 `expand_query()` 中的 torch 引用

### Phase 3：修改 `qmd/models/downloader.py`
1. 更新 MODELS 字典中 reranker/expansion 的 HF 仓库地址
2. 添加 `model_file` 字段支持
3. 添加 CN 回退逻辑

### Phase 4：更新 `pyproject.toml`
1. 新增 `onnx` optional dependency 组
2. 评估是否从 cuda/cpu 组移除 `torch`

### Phase 5：验证测试
```bash
pytest tests/unit/test_rerank.py -v
qmd query "python async programming" --rerank --collection my_docs
```

---

## 9. 风险与注意事项

| 风险 | 说明 | 缓解措施 |
|------|------|---------|
| ONNX 文件路径 | `onnx-community/Qwen3-Reranker-0.6B` 下文件名为 `onnx/model_q4f16.onnx`，需下载前确认 | Phase 1 先验证文件结构 |
| `do_sample=True` 生成速度慢 | ONNX 随机采样比 PyTorch 慢约 1.3-2x | 改为 greedy decode（query expansion 精度影响小） |
| ModelScope 无 ONNX 版 | CN 用户下载失败 | 提供手动量化脚本 |
| `torch` 完全移除风险 | `engine.py` 的 VRAM 检测依赖 torch | 用 `pynvml` 或 `onnxruntime` 替代 |
| optimum 版本兼容性 | `ORTModelForCausalLM.generate()` 的参数集可能比 PyTorch 少 | 检查 `temperature` + `do_sample` 是否支持 |
| Qwen2.5 → Qwen3 模型变更 | 两者 tokenizer 格式相同，但输出质量有差异 | 保留原始 prompt 格式，对比扩展质量 |

---

## 10. 最终方案总结

| 组件 | 推荐方案 | 理由 |
|------|---------|------|
| **Reranker** | `onnx-community/Qwen3-Reranker-0.6B` + `ORTModelForSequenceClassification` | 前向推理，ONNX 最成熟，API 零改动 |
| **Query Expansion** | `onnx-community/Qwen3-0.6B-Instruct-ONNX` + `ORTModelForCausalLM` | `generate()` 接口相同，代码改动最小 |
| **新增依赖** | `optimum[onnxruntime]>=1.20.0` | 1 个包，复用已有 `onnxruntime-gpu` |
| **可移除依赖** | `torch>=2.0.0`（~2500 MB） | ONNX 路径完全不需要 PyTorch |
| **总显存节省** | ~1000-1400 MB | 使 6GB 显卡可同时运行所有模型 |
| **代码改动量** | **< 30 行**（仅 import 和 from_pretrained） | 推理逻辑完全不变 |
