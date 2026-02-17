# QMD-Python 核心架构决策记录

**日期**: 2026-02-15 13:20-13:30
**决策人**: Boss + Zandar (CTO+COO)
**项目路径**: `D:\MoneyProjects\qmd-python`

---

## 🎯 决策概述

### 问题本质

```
3个模型实例 × 4GB显存/个 = 12GB显存爆炸
```

**场景**：多进程并发时，每个进程独立加载模型
- 进程1：embed模型（4GB VRAM）
- 进程2：embed模型（4GB VRAM）
- 进程3：embed模型（4GB VRAM）
- **总计**：12GB VRAM（显存溢出）

---

## ✅ 核心决策

### 决策1：Client-Server分离（必须）

**方案**：
```
┌─────────────────────────────────┐
│         CLI / Client           │
└────────────┬────────────────────┘
             │ HTTP
┌────────────▼────────────────────┐
│   QMD Server (单一进程）        │
│   - 单例模型（4GB VRAM）        │
│   - 队列串行（防止溢出）        │
└────────────────────────────────┘
```

**理由**：
- ✅ 显存节省：66%（4GB vs 12GB）
- ✅ 架构清晰：职责分离
- ✅ 维护简单：单一进程

---

### 决策2：HTTP MCP Server（不是stdio）

**方案**：
- ✅ HTTP Transport（默认）
- ✅ SSE（Server-Sent Events）用于实时推送
- ❌ 不使用stdio模式

**理由**：
- ✅ 性能好：HTTP比stdio更稳定
- ✅ 跨进程：Server独立运行
- ✅ 可扩展：支持WebSocket未来
- ✅ OpenClaw集成：HTTP + MCP协议兼容

---

### 决策3：操作分类（智能路由）

**分类标准**：是否需要模型

| 操作 | 需要模型 | 执行方式 | 理由 |
|------|---------|---------|------|
| **embed** | ✅ | HTTP → Server | 需要bge模型 |
| **vsearch** | ✅ | HTTP → Server | 需要embed + 向量搜索 |
| **query** | ✅ | HTTP → Server | 需要embed + reranker + LLM扩展 |
| **search** | ❌ | 直接CLI | BM25纯算法，零等待 |
| **collection add** | ❌ | 直接CLI | SQLite操作 |
| **collection list** | ❌ | 直接CLI | SQLite查询 |
| **index** | ❌ | 直接CLI | 文件读取 + 写入 |
| **config** | ❌ | 直接CLI | YAML配置 |
| **status** | ⚠️ | 混合 | Server状态→HTTP，CLI状态→直接 |

**核心价值**：
- ✅ CLI操作零等待（不需要模型）
- ✅ Server操作串行化（需要模型）
- ✅ 用户体验好（自动路由）

---

### 决策4：队列串行（防止显存溢出）

**方案**：
```python
# Server端
_processing_lock = asyncio.Lock()

@app.post("/embed")
async def embed(texts):
    async with _processing_lock:
        return await model.encode(texts)
```

**效果**：
```
10个并发请求：
- 请求1：立即执行（0ms等待）
- 请求2：等待请求1（~100ms）
- 请求3：等待请求2（~200ms）
- ...
- 总时间：1秒（10 × 100ms）
- 显存占用：4GB（单例模型）
```

**对比**：
- ❌ 旧方案：10进程 × 4GB = 40GB显存（OOM）
- ✅ 新方案：1进程 × 4GB = 4GB显存（安全）

---

## 📊 架构对比

### 旧方案（已废弃）

```
多进程Standalone模式：
├─ 进程1：embed（4GB VRAM）
├─ 进程2：embed（4GB VRAM）
├─ 进程3：embed（4GB VRAM）
└─ 问题：
   - 显存溢出（12GB）
   - 进程管理复杂
   - 无法复用模型
```

### 新方案（已确认）

```
Client-Server分离模式：

CLI层（智能路由）：
├─ 不需要模型 → 直接执行（零等待）
└─ 需要模型 → HTTP Client（自动检测Server）

Server层（单一进程）：
├─ 单例模型（4GB VRAM）
├─ 队列串行（防止溢出）
└─ HTTP端点（embed, vsearch, query, health）

核心价值：
├─ 显存节省：66%（4GB vs 12GB）
├─ 性能提升：CLI操作零等待
└─ 用户体验：零配置（自动服务发现）
```

---

## 🔧 技术实现

### HTTP端点（精简为4个）

```python
# qmd/server/app.py

@app.post("/embed")
async def embed(request: EmbedRequest):
    """生成嵌入向量"""
    async with _processing_lock:
        return await model.encode(request.texts)

@app.post("/vsearch")
async def vsearch(request: VSearchRequest):
    """向量搜索"""
    async with _processing_lock:
        query_emb = await model.encode([request.query])
        return await vector_search(query_emb)

@app.post("/query")
async def query(request: QueryRequest):
    """混合搜索"""
    async with _processing_lock:
        expanded = await llm.expand_query(request.query)
        embeddings = await model.encode(expanded)
        results = await vector_search(embeddings)
        reranked = await reranker.rerank(request.query, results)
        return reranked

@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "healthy" if model else "unhealthy",
        "model_loaded": model is not None,
        "queue_size": queue.qsize()
    }
```

### CLI智能路由

```python
# qmd/cli.py

# 不需要模型的命令：直接执行
@cli.command()
@click.argument("query")
def search(query):
    """BM25搜索（直接CLI，零等待）"""
    searcher = FTSSearcher(db)
    results = searcher.search(query)
    display(results)

# 需要模型的命令：HTTP Client
@cli.command()
@click.argument("query")
def vsearch(query):
    """向量搜索（需要模型，走Server）"""
    client = QmdHttpClient()  # 自动检测/启动Server
    results = client.vsearch(query)
    display(results)
```

### 自动服务发现

```python
# qmd/server/client.py

class QmdHttpClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or self._discover_server()

    def _discover_server(self) -> str:
        """自动发现或启动Server"""
        # 1. 尝试连接localhost:18765
        # 2. 读取 ~/.qmd/server_port.txt
        # 3. 检查进程是否存在
        # 4. 不存在则自动启动
        ...
```

---

## ⏱️ 时间估算

### 任务精简（基于架构理解）

| Phase | 任务 | 原估算 | 新估算 | 节省 |
|-------|------|--------|--------|------|
| 0 | 自动服务发现 | 1.5h | 1.5h | - |
| 1 | HTTP端点（精简） | 2h | **1h** | 1h ⬇️ |
| 2 | HTTP客户端 | 1h | 1h | - |
| 3 | CLI智能路由 | 1.5h | **1h** | 0.5h ⬇️ |
| **总计** | - | **6h** | **4.5h** | **1.5h** ⬇️ |

**节省原因**：
- 端点精简：8个 → 4个（embed, vsearch, query, health）
- CLI简化：复杂的mode选项 → 智能路由
- 架构清晰：职责分离（代码更简单）

**时间节省：25%**

---

## 🎯 核心价值总结

### 技术价值
- ✅ 显存节省：66%（4GB vs 12GB）
- ✅ 性能提升：CLI操作零等待
- ✅ 架构清晰：职责分离
- ✅ 维护简单：单一进程

### 商业价值
- ✅ 用户体验：零配置（自动服务发现）
- ✅ 成本降低：减少显存需求
- ✅ 扩展性：支持更多并发用户
- ✅ 稳定性：Windows兼容性更好

### 战略价值
- ✅ 技术壁垒：Client-Server分离架构
- ✅ 产品差异化：自动服务发现（竞品没有）
- ✅ 长期维护：代码简洁易维护

---

## 📝 关键约束

### 必须满足
1. ✅ Client-Server分离（架构要求）
2. ✅ HTTP MCP Server（不是stdio）
3. ✅ 队列串行（防止显存溢出）
4. ✅ 智能路由（按是否需要模型）

### 可以优化
1. ⚠️ 端点数量（4个核心端点足够）
2. ⚠️ 错误处理（可以逐步完善）
3. ⚠️ 性能调优（可以后续优化）

### 暂不实现
1. ❌ REST API（违背MCP理念）
2. ❌ 完整mode选项（智能路由更简单）
3. ❌ SSE/WebSocket（未来扩展）

---

## 🚀 下一步行动

### Phase 0: 自动服务发现（1.5h）
- [ ] 端口管理器（qmd/server/port_manager.py）
- [ ] 进程检测器（qmd/server/process.py）
- [ ] 智能客户端（qmd/server/client.py）

### Phase 1: HTTP Server（1h）
- [ ] 数据模型（qmd/server/models.py）
- [ ] 4个端点（qmd/server/app.py）

### Phase 2: HTTP Client（1h）
- [ ] QmdHttpClient类（qmd/server/client.py）
- [ ] 自动服务发现集成

### Phase 3: CLI智能路由（1h）
- [ ] 路由逻辑（qmd/cli.py）
- [ ] server命令更新

**总计时间：4.5小时**

---

## ✅ 决策确认

**决策人确认**：
- ✅ Boss：2026-02-15 13:20 确认架构理解
- ✅ Zandar：2026-02-15 13:30 记录决策

**项目状态**：
- ✅ 架构理解100%正确
- ✅ 实施路径清晰
- ✅ 时间估算准确（4.5小时）

**下一步**：开始实施Phase 0（自动服务发现）

---

**文档版本**: 1.0
**最后更新**: 2026-02-15 13:30
