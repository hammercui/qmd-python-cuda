# 模型下载时机说明

> **版本**: qmd-python 0.1.0 (BGE-M3)
> **更新日期**: 2026-02-19

---

## 📥 什么时候会下载新模型？

### 快速答案

**首次使用需要模型的功能时**，会自动从 HuggingFace 或 ModelScope 下载模型到本地缓存。

---

## 🔄 模型下载触发点

### 1. CLI Embed 命令

**命令**: `qmd embed`

**触发时机**:
```python
# qmd/cli.py, line 649-654
@cli.command()
@click.option("--mode", default="auto")
def embed(ctx_obj, collection, force, mode):
    from qmd.llm.engine import LLMEngine
    llm = LLMEngine(mode=mode)  # ← 首次调用时下载模型
    ...
```

**下载内容**:
- **BGE-M3 INT8**: 542 MB (来自 `Xenova/bge-m3`)
- **缓存位置**: `~/.cache/huggingface/hub/models--Xenova--bge-m3/`

**首次 embed 时间**:
- CPU: ~5-10 分钟 (下载 + 初始化)
- GPU: ~2-5 分钟 (下载 + 初始化)

**后续 embed 时间**:
- CPU: ~15-30ms/chunk (已缓存)
- GPU: ~5-10ms/chunk (已缓存)

---

### 2. CLI Server 启动

**命令**: `qmd server`

**触发时机**:
```python
# qmd/server/app.py, line 63-96
@app.on_event("startup")
async def startup_event():
    ...
    from fastembed import TextEmbedding
    _model = TextEmbedding(model_name=DEFAULT_MODEL)  # ← 启动时下载模型
    ...
```

**下载内容**: 同上 (BGE-M3 INT8, 542 MB)

**启动时间**:
- 首次: ~5-10 分钟 (下载 + 加载)
- 后续: ~10-30 秒 (仅加载，已缓存)

---

### 3. CLI VSearch / Query 命令

**命令**: `qmd vsearch` 或 `qmd query`

**触发时机**:
```python
# qmd/cli.py, line 794-831
@cli.command()
def vsearch(ctx_obj, query, collection, limit):
    from qmd.server.client import EmbedServerClient
    client = EmbedServerClient()
    results = client.vsearch(query, ...)  # ← 如果 Server 未运行，自动启动 Server
    ...
```

**注意**: 这些命令**不会直接下载模型**，而是：
1. 尝试连接已运行的 Server
2. 如果 Server 未运行，自动启动 Server (此时下载模型)
3. 通过 HTTP API 调用 Server

---

### 4. 手动下载命令

**命令**: `qmd check --download` 或 `python -m qmd.models.downloader`

**触发时机**: 用户主动执行

**下载内容**:
- **BGE-M3 INT8**: 542 MB (embed 模型)
- **Qwen3-Reranker**: ~400 MB (重排序模型)
- **Qwen3-0.6B-Instruct**: ~400 MB (查询扩展模型)
- **总计**: ~1.3 GB

**缓存位置**: `~/.cache/qmd/models/`

---

## 📍 模型缓存位置

### FastEmbed 缓存 (BGE-M3)

**默认位置**:
```
~/.cache/huggingface/hub/models--Xenova--bge-m3/
  ├── onnx/
  │   ├── model_int8.onnx        # 542 MB (主文件)
  │   ├── tokenizer.json
  │   ├── tokenizer_config.json
  │   └── sentencepiece.bpe.model
  └── ...
```

**自定义缓存位置**:
```python
llm = LLMEngine(cache_dir="/custom/path")
```

### ModelDownloader 缓存 (手动下载的模型)

**默认位置**:
```
~/.cache/qmd/models/
  ├── onnx-int8_embedding/       # BGE-M3 (如果手动下载)
  ├── onnx-reranker_reranker/    # Qwen3-Reranker
  └── onnx-causal-lm_expansion/  # Qwen3-0.6B-Instruct
```

---

## 🔍 模型下载检测机制

### FastEmbed 自动检测

**逻辑**:
```python
# qmd/llm/engine.py, line 184-228
def _ensure_model(self) -> None:
    """Load model if not already loaded (standalone mode)."""
    if self._model is not None:
        return  # 已加载，直接返回

    # 注册 BGE-M3 自定义模型
    if self.model_name == "BAAI/bge-m3":
        _register_bge_m3()  # 只注册一次

    # 尝试使用本地缓存
    if self._downloader is None:
        self._downloader = ModelDownloader()

    cached_path = self._downloader.get_model_path("embedding")
    if cached_path:
        model_path = str(cached_path)  # 使用缓存
    else:
        model_path = self.model_name  # 触发下载

    # 加载模型 (如果本地没有，fastembed 会自动下载)
    from fastembed import TextEmbedding
    self._model = TextEmbedding(
        model_name=model_path,  # ← 这里触发下载
        cache_dir=self.cache_dir,
        providers=providers,
    )
```

**检测优先级**:
1. **已加载**: `_model is not None` → 直接返回
2. **本地缓存**: `~/.cache/qmd/models/` → 使用缓存
3. **HuggingFace 缓存**: `~/.cache/huggingface/hub/` → 使用缓存
4. **自动下载**: 从 `Xenova/bge-m3` 下载

---

## 🚀 下载流程

### 完整下载流程

```
用户执行: qmd embed
    ↓
CLI 调用: LLMEngine(mode="auto")
    ↓
LLMEngine._ensure_model()
    ↓
注册 BGE-M3: _register_bge_m3()
    ├─ TextEmbedding.add_custom_model(...)
    └─ 设置 sources=ModelSource(hf="Xenova/bge-m3")
    ↓
检查缓存: ModelDownloader().get_model_path("embedding")
    ├─ 找到缓存 → 使用本地路径
    └─ 未找到 → 继续
    ↓
FastEmbed 加载: TextEmbedding(model="BAAI/bge-m3")
    ├─ 检查 ~/.cache/huggingface/hub/models--Xenova--bge-m3/
    ├─ 存在 → 直接加载
    └─ 不存在 → 触发下载
        ↓
    从 HuggingFace 下载:
    └─ https://huggingface.co/Xenova/bge-m3
        ├─ onnx/model_int8.onnx (542 MB)
        ├─ onnx/tokenizer.json
        ├─ onnx/tokenizer_config.json
        └─ onnx/sentencepiece.bpe.model
        ↓
    保存到: ~/.cache/huggingface/hub/models--Xenova--bge-m3/
        ↓
    加载到内存 (ONNX Runtime)
        ↓
    开始 embed 处理
```

### 下载时间估算

**网络条件**: 100 Mbps 家用宽带

| 模型 | 大小 | 下载时间 | 初始化时间 | 总计 |
|------|------|----------|-----------|------|
| **BGE-M3 INT8** | 542 MB | ~45 秒 | ~30 秒 | **~75 秒** |
| Qwen3-Reranker | 400 MB | ~30 秒 | ~20 秒 | ~50 秒 |
| Qwen3-0.6B-Instruct | 400 MB | ~30 秒 | ~20 秒 | ~50 秒 |
| **总计** | 1.3 GB | ~105 秒 | ~70 秒 | **~175 秒** |

**加速方案**:
- ✅ 国内用户 → 自动使用 ModelScope (速度提升 5-10x)
- ✅ 提前下载 → `qmd check --download` (后台下载)

---

## 🛠️ 手动下载命令

### 方法 1: qmd check (推荐)

```bash
# 检测系统状态并自动下载缺失的模型
qmd check --download

# 输出示例:
# [bold yellow]Starting model download...[/bold yellow]
# [dim]Cache directory: C:\Users\YourName\.cache\qmd\models[/dim]
# [cyan][ModelScope] Downloading embedding...[/cyan]
# ████████████████████████████████████████ 100%
# [green][MoT] OK Downloaded to ...\onnx-int8_embedding[/green]
# [bold green]Download complete![/bold green]
```

### 方法 2: Python 模块

```bash
# 直接运行下载器
python -m qmd.models.downloader

# 效果同上，支持双源并行下载
```

### 方法 3: 预下载 (离线场景)

```bash
# 1. 在有网络的机器上下载
python -m qmd.models.downloader

# 2. 复制缓存目录到离线机器
# 源: ~/.cache/huggingface/hub/
# 目标: ~/.cache/huggingface/hub/

# 3. 在离线机器上直接使用
qmd embed  # 无需下载，直接使用缓存
```

---

## 🌐 下载源选择

### 自动检测 (默认)

**逻辑**:
```python
# qmd/models/downloader.py, line 28-66
def _detect_location() -> str:
    """Detect if running in China or Overseas."""
    # 1. 检查时区
    if "Asia/Shanghai" in time.tzname:
        return "cn"  # 中国 → ModelScope

    # 2. 回退到 IP 检测
    response = requests.get("http://ip-api.com/json/")
    if response.json()["country_code"] == "CN":
        return "cn"  # 中国 IP → ModelScope

    return "global"  # 其他 → HuggingFace
```

**规则**:
- 🇨🇳 **中国用户** → 自动使用 **ModelScope** (魔搭社区)
  - 速度快 (国内服务器)
  - 无需翻墙
- 🌍 **海外用户** → 自动使用 **HuggingFace**
  - 速度快 (全球 CDN)
  - 模型更新快

### 手动指定下载源

**编辑配置文件**:
```yaml
# ~/.qmd/index.yml
model_source: "modelscope"  # 强制使用 ModelScope
# 或
model_source: "huggingface"  # 强制使用 HuggingFace
```

**或环境变量**:
```bash
export QMD_MODEL_SOURCE=huggingface  # Linux/macOS
set QMD_MODEL_SOURCE=huggingface     # Windows
```

---

## 🔍 检查模型是否已下载

### 方法 1: qmd status

```bash
$ qmd status

Index size: 5.2 MB
Collections: 1
Documents: 199
Embeddings: 199/199 (100.0%)
```

**注意**: `qmd status` **不会**显示模型是否已下载，只显示数据库状态。

### 方法 2: qmd check

```bash
$ qmd check

System Status Check
====================

Dependencies:
  ✓ torch v2.1.0
  ✓ transformers v4.30.0
  ✓ fastembed Installed

Device:
  OK CUDA: NVIDIA GeForce RTX 3060
  GPU Count: 1
  CUDA Version: 12.1
  GPU 0: RTX 3060 (12.0 GB, Compute 8.6)

Models:
  OK embedding (600MB)  ← 已下载
  X reranker (400MB)     ← 未下载
  X expansion (400MB)    ← 未下载

Recommendations:
  [yellow]Run:[/yellow] qmd download  # Download all models
```

### 方法 3: 检查缓存目录

```bash
# Linux/macOS
ls -lh ~/.cache/huggingface/hub/ | grep bge-m3

# Windows
dir %USERPROFILE%\.cache\huggingface\hub\ | findstr bge-m3
```

**预期输出**:
```
drwxr-xr-x  10 user  staff   320B Feb 19 10:30 models--Xenova--bge-m3
```

---

## ⚡ 最佳实践

### 推荐工作流程

**场景 1: 首次安装**
```bash
# 1. 安装依赖
pip install -e .[cuda]

# 2. 预下载所有模型 (后台，避免首次使用时等待)
qmd check --download

# 3. 索引文档
qmd index

# 4. 生成向量
qmd embed  # 模型已缓存，直接使用
```

**场景 2: 日常使用**
```bash
# 1. 更新文档
git pull  # 或修改 markdown 文件

# 2. 重新索引
qmd index  # 快速 (仅扫描文件系统)

# 3. 搜索
qmd query "your query"  # 即时返回
```

**场景 3: 离线环境**
```bash
# 1. 在线机器上预下载
qmd check --download

# 2. 复制缓存到离线机器
# 源: ~/.cache/huggingface/hub/
# 目标: ~/.cache/huggingface/hub/

# 3. 离线使用 (无需网络)
qmd embed
qmd query "offline query"
```

---

## 🐛 常见问题

### Q1: 下载速度慢

**原因**: 默认从 HuggingFace 下载，海外服务器

**解决**:
```bash
# 方案 1: 使用国内镜像 (自动)
# 确保在时区 "Asia/Shanghai" 或 IP 在中国
# QMD 会自动使用 ModelScope

# 方案 2: 手动指定 ModelScope
# 编辑 ~/.qmd/index.yml
model_source: "modelscope"

# 方案 3: 提前下载
qmd check --download  # 后台下载，避免首次使用时等待
```

### Q2: 下载失败 (网络错误)

**解决**:
```bash
# 方案 1: 重试 (网络波动)
qmd check --download

# 方案 2: 手动下载
# 1. 访问 https://huggingface.co/Xenova/bge-m3
# 2. 下载 onnx/model_int8.onnx (542 MB)
# 3. 手动放置到 ~/.cache/huggingface/hub/models--Xenova--bge-m3/onnx/

# 方案 3: 使用代理
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
qmd check --download
```

### Q3: 磁盘空间不足

**需求**:
- BGE-M3: 542 MB
- Reranker: 400 MB (可选)
- Expansion: 400 MB (可选)
- **总计**: ~1.3 GB

**解决**:
```bash
# 方案 1: 清理缓存
rm -rf ~/.cache/huggingface/hub/  # Linux/macOS
del %USERPROFILE%\.cache\huggingface\hub\  # Windows

# 方案 2: 自定义缓存位置
# 在代码中指定:
llm = LLMEngine(cache_dir="/path/to/larger/disk")
```

### Q4: 模型损坏 (加载失败)

**症状**: `RuntimeError: Failed to load model`

**解决**:
```bash
# 删除损坏的缓存，重新下载
rm -rf ~/.cache/huggingface/hub/models--Xenova--bge-m3/
qmd check --download
```

---

## 📚 相关文档

- **升级完成文档**: [UPGRADE_COMPLETE.md](UPGRADE_COMPLETE.md)
- **快速迁移指南**: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- **模型配置文档**: [../guide/FINAL_CONFIG.md](../guide/FINAL_CONFIG.md)

---

**文档版本**: 1.0
**更新日期**: 2026-02-19
**作者**: AI Assistant (OpenCode + GLM-4.7)
