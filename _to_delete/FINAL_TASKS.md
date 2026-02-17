# QMD-Python 最终任务清单

**生成时间**: 2026-02-15 13:25
**项目路径**: `D:\MoneyProjects\qmd-python`
**总估算时间**: **4.5小时** ⬇️（节省25%）

---

## 📊 项目状态

### 当前完成度
- ✅ **75%** (6/8 阶段完成)
- ✅ 基础HTTP Server已实现
- ✅ LLMEngine双模式支持
- ✅ --mode选项已添加
- ✅ Queue改为Lock（真正串行）
- ✅ 文档完整（4个核心文档）
- ✅ **核心架构理解确认**（2026-02-15 13:20）

### 待实现（本次任务）
- ❌ Phase 0: 自动服务发现
- ❌ Phase 1: HTTP Server（精简为3个端点）
- ❌ Phase 2: HTTP客户端（智能连接）
- ❌ Phase 3: CLI智能路由（简化）

---

## 🎯 核心目标

**主要问题**: 多进程并发时显存暴增（6-12GB VRAM）

**解决方案**: Client-Server分离 + 智能路由
- ✅ 单一进程（4GB VRAM）
- ✅ **只有模型操作走Server**（embed, vsearch, query）
- ✅ **其他操作直接CLI**（search, collection, index, config）
- ✅ HTTP MCP Server（不是stdio）
- ✅ 自动服务发现（零配置）

**架构简化**（基于Boss确认）:
```
HTTP端点：精简为3个核心端点（embed, vsearch, query） + 1个health
  - 比之前简化50%（8个 → 4个）
  - 实现时间减少25%（6小时 → 4.5小时）

CLI智能路由：
  - 需要模型的操作 → HTTP Client（自动检测Server）
  - 不需要模型的操作 → 直接执行（零等待）
```

**核心架构理解**（2026-02-15 13:20确认）:
```
问题本质：
  3个模型实例 × 4GB显存/个 = 12GB显存爆炸
解决：
  单进程Server + 1套模型 + 队列串行 = 4GB显存 ✅

关键决策：
  ✅ Client-Server分离（必须）
  ✅ HTTP MCP Server（不是stdio）
  ✅ 队列串行（防止显存溢出）
  ✅ 智能路由（按是否需要模型）
```

---

## 📋 任务清单

### Phase 0: 自动服务发现（P0 - 1.5小时）

**文件**:
- `qmd/server/port_manager.py`（新建）
- `qmd/server/process.py`（新建）
- `qmd/server/client.py`（修改）

#### Task 0.1: 端口管理器（30分钟）

**文件**: `qmd/server/port_manager.py`（新建）

**功能**:
```python
def find_available_port(start_port=18765, max_attempts=100) -> int:
    """检测可用端口，冲突时递增"""
    
def save_server_port(port) -> None:
    """保存实际端口到 ~/.qmd/server_port.txt"""
    
def get_saved_port() -> int | None:
    """读取保存的端口"""
```

**验收标准**:
- [ ] 端口冲突时自动递增（18765 → 18766 → 18767）
- [ ] 保存端口到 `~/.qmd/server_port.txt`
- [ ] 读取保存的端口

---

#### Task 0.2: 进程检测器（30分钟）

**文件**: `qmd/server/process.py`（新建）

**功能**:
```python
def find_server_processes() -> list[psutil.Process]:
    """查找所有qmd server进程"""
    
def get_server_port_from_process(proc) -> int | None:
    """从命令行提取端口号"""
    
def kill_server_processes():
    """停止所有qmd server进程（调试用）"""
```

**验收标准**:
- [ ] 检测进程是否存在
- [ ] 提取进程端口号
- [ ] 支持Windows/Linux跨平台

---

#### Task 0.3: 智能客户端（30分钟）

**文件**: `qmd/server/client.py`（修改）

**功能**:
```python
class QmdHttpClient:
    def __init__(self, base_url: str | None = None):
        """初始化，自动服务发现"""
        
    def _discover_server(self) -> str:
        """发现或启动Server"""
        # 1. 尝试连接localhost:18765
        # 2. 读取 ~/.qmd/server_port.txt
        # 3. 检查进程是否存在
        # 4. 不存在则自动启动
        
    def _try_connect(self, url: str) -> bool:
        """尝试连接"""
        
    def _is_server_running(self) -> bool:
        """检查Server是否运行"""
        
    def _auto_start_server(self) -> str:
        """自动启动Server"""
```

**验收标准**:
- [ ] 自动检测Server是否运行
- [ ] Server不存在时自动启动
- [ ] 等待Server启动（最多10秒）
- [ ] 支持Windows后台启动

---

### Phase 1: HTTP端点实现（P0 - 1小时）⬇️

**文件**:
- `qmd/server/models.py`（扩展）
- `qmd/server/app.py`（扩展）

**精简说明**：
- 只需要**3个核心端点** + 1个健康检查（共4个）
- 去掉了search端点（不需要模型，直接CLI）
- 时间节省：1小时（2小时 → 1小时）

#### Task 1.1: 数据模型（20分钟）

**文件**: `qmd/server/models.py`

**需要添加**（精简为4个模型）:
```python
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class EmbedRequest(BaseModel):
    texts: List[str]

class EmbedResponse(BaseModel):
    embeddings: List[List[float]]

class VSearchRequest(BaseModel):
    query: str
    limit: int = 10
    min_score: float = 0.3
    collection: Optional[str] = None

class VSearchResponse(BaseModel):
    results: List[Dict[str, Any]]

class QueryRequest(BaseModel):
    query: str
    limit: int = 10
    min_score: float = 0.0
    collection: Optional[str] = None

class QueryResponse(BaseModel):
    results: List[Dict[str, Any]]

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    queue_size: int  # 队列大小
```

**验收标准**:
- [ ] 4个端点的请求/响应模型（精简后）
- [ ] 类型注解完整
- [ ] Pydantic验证

---

#### Task 1.2: HTTP端点实现（40分钟）

**文件**: `qmd/server/app.py`

**需要添加的端点**（精简为3个核心 + 1个health）:

1. **POST /embed**（10分钟）
```python
@app.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest):
    """生成嵌入向量（需要bge模型）"""
    async with _processing_lock:
        embeddings = await _model.encode(request.texts)
    return EmbedResponse(embeddings=embeddings)
```

2. **POST /vsearch**（10分钟）
```python
@app.post("/vsearch", response_model=VSearchResponse)
async def vsearch(request: VSearchRequest):
    """向量语义搜索（需要embed模型）"""
    async with _processing_lock:
        # 1. embed query
        query_emb = await _model.encode([request.query])
        # 2. vector search
        results = await _vector_search(query_emb, request.limit, request.min_score)
    return VSearchResponse(results=results)
```

3. **POST /query**（15分钟）
```python
@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """混合搜索（需要embed + reranker + LLM）"""
    async with _processing_lock:
        # 1. query expansion (LLM)
        expanded = await _llm.expand_query(request.query)
        # 2. embed queries
        embeddings = await _model.encode(expanded)
        # 3. vector search
        results = await _vector_search(embeddings, request.limit)
        # 4. rerank
        reranked = await _reranker.rerank(request.query, results)
    return QueryResponse(results=reranked)
```

4. **GET /health**（5分钟）
```python
@app.get("/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    return HealthResponse(
        status="healthy" if _model is not None else "unhealthy",
        model_loaded=_model is not None,
        queue_size=_queue.qsize() if _queue else 0
    )
```

**验收标准**:
- [ ] 4个端点实现完整（embed, vsearch, query, health）
- [ ] 队列处理（asyncio.Lock）
- [ ] 错误处理（400, 503等）
- [ ] 符合MCP规范（HTTP Transport）

---

### Phase 2: HTTP客户端（P0 - 1小时）

**文件**: `qmd/server/client.py`（扩展）

#### Task 2.1: QmdHttpClient类（1小时）

**功能**:
```python
class QmdHttpClient:
    """HTTP客户端（自动服务发现）"""
    
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or self._discover_server()
    
    # 必需方法（P0）
    def embed(self, texts: List[str]) -> List[List[float]]:
        """生成嵌入"""
        return self._post("/embed", {"texts": texts})
    
    def vsearch(self, query: str, **kwargs) -> Dict:
        """向量搜索"""
        return self._post("/vsearch, {"query": query, **kwargs})
    
    def query(self, query: str, **kwargs) -> Dict:
        """混合搜索"""
        return self._post("/query", {"query": query, **kwargs})
    
    def health(self) -> Dict:
        """健康检查"""
        return self._get("/health")
    
    # 可选方法（P1）
    def search(self, query: str, **kwargs) -> Dict:
        """BM25搜索"""
        return self._post("/search", {"query": query, **kwargs})
    
    # 辅助方法
    def _discover_server(self) -> str:
        """自动服务发现"""
        
    def _try_connect(self, url: str) -> bool:
        """尝试连接"""
        
    def _is_server_running(self) -> bool:
        """检查进程"""
        
    def _auto_start_server(self) -> str:
        """自动启动"""
        
    def _post(self, endpoint, data):
        """POST请求"""
        
    def _get(self, endpoint):
        """GET请求"""
```

**验收标准**:
- [ ] 自动服务发现完整实现
- [ ] 5个HTTP方法（embed, vsearch, query, health, search）
- [ ] 错误处理（连接失败、超时）
- [ ] 支持自动启动Server

---

### Phase 3: CLI智能路由（P0 - 1小时）⬇️

**文件**: `qmd/cli.py`

**简化说明**：
- 智能路由：根据是否需要模型自动选择
- 不需要复杂的mode选项（大部分情况自动）
- 时间节省：30分钟（1.5小时 → 1小时）

#### Task 3.1: 智能路由实现（45分钟）

**路由策略**（基于Boss确认的架构理解）:

| 命令 | 需要模型？ | 执行方式 | 理由 |
|------|---------|---------|------|
| `search` | ❌ | 直接CLI | BM25纯算法，零等待 |
| `vsearch` | ✅ | HTTP Client | 需要embed模型 |
| `query` | ✅ | HTTP Client | 需要embed + reranker + LLM |
| `collection add` | ❌ | 直接CLI | SQLite操作 |
| `collection list` | ❌ | 直接CLI | SQLite查询 |
| `index` | ❌ | 直接CLI | 文件读取 + 写入 |
| `config` | ❌ | 直接CLI | YAML配置 |

**示例代码**:

```python
# 不需要模型的命令：直接执行
@cli.command()
@click.argument("query")
@click.option("--limit", default=10)
def search(query, limit):
    """BM25搜索（直接CLI，零等待）"""
    searcher = FTSSearcher(ctx_obj.db)
    results = searcher.search(query, limit=limit)
    display(results)

# 需要模型的命令：HTTP Client + 自动服务发现
@cli.command()
@click.argument("query")
@click.option("--limit", default=10)
def vsearch(query, limit):
    """向量搜索（需要模型，走Server）"""
    from qmd.server.client import QmdHttpClient
    client = QmdHttpClient()  # 自动检测/启动Server
    results = client.vsearch(query, limit=limit)
    display(results)
```

**验收标准**:
- [ ] search命令直接执行（不走Server）
- [ ] vsearch/query命令自动使用HTTP Client
- [ ] HTTP Client自动检测/启动Server（复用Phase 0）
- [ ] 输出格式保持一致
- [ ] collection/index/config命令保持原有逻辑

---

#### Task 3.2: server命令更新（15分钟）

---

#### Task 3.2: server命令更新（30分钟）

**文件**: `qmd/cli.py`

**修改**:
```python
@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=18765, type=int, help="Port to bind to (auto-increment if occupied)")
@click.option("--log-level", default="info", help="Log level")
@click.option("--transport", type=click.Choice(['http', 'mcp', 'both']), default="http", help="Transport mode")
def server(host, port, log_level, transport):
    """Start QMD MCP Server"""
    from qmd.server.port_manager import find_available_port, save_server_port
    from qmd.server.app import app
    
    # 端口检测和自动递增
    actual_port = find_available_port(port)
    if actual_port != port:
        console.print(f"[yellow]Port {port} occupied, using {actual_port}[/yellow]")
    
    # 保存端口
    save_server_port(actual_port)
    
    # 启动Server
    uvicorn.run(app, host=host, port=actual_port, log_level=log_level)
```

**验收标准**:
- [ ] 默认端口改为18765
- [ ] 端口冲突自动递增
- [ ] 保存端口到文件
- [ ] 支持--transport选项（http/mcp/both）

---

#### Task 3.3: 自动模式检测（15分钟）

**文件**: `qmd/llm/engine.py`（已存在，可能需要微调）

**确认**:
- [ ] VRAM检测逻辑正确
- [ ] auto模式选择逻辑：
  - VRAM < 8GB → server
  - VRAM >= 8GB → standalone
  - 无CUDA → standalone

---

## ✅ 验收标准

### 功能测试

| 场景 | 验收标准 |
|------|----------|
| **Server启动** | `qmd server` 启动在18765端口 |
| **端口冲突** | 端口被占用时自动递增 |
| **自动服务发现** | CLI自动检测并启动Server |
| **embed端点** | POST /embed 返回384维向量 |
| **vsearch端点** | POST /vsearch 返回搜索结果 |
| **query端点** | POST /query 返回混合搜索结果 |
| **health端点** | GET /health 返回状态 |
| **CLI集成** | `qmd search --mode server` 使用HTTP |

### 性能要求

| 指标 | 要求 |
|------|------|
| **显存占用** | 4GB（单例模型）|
| **并发处理** | 队列串行（无冲突）|
| **延迟** | embed < 100ms |
| **自动启动** | Server启动 < 10秒 |

---

## 📁 文件结构（实现后）

```
qmd/
├── cli.py                          # ✅ 修改：添加--mode选项
├── llm/
│   └── engine.py                    # ✅ 已有：双模式支持
├── server/
│   ├── __init__.py                  # ✅ 已有
│   ├── app.py                       # ✅ 修改：添加4个端点
│   ├── client.py                    # ✅ 修改：QmdHttpClient + 自动发现
│   ├── models.py                    # ✅ 修改：添加8个端点的模型
│   ├── port_manager.py              # 🆕 新建：端口管理器
│   └── process.py                   # 🆕 新建：进程检测器
└── ...
```

---

## 📊 估算时间（2026-02-15 13:25 更新）

| Phase | 任务 | 原估算 | 新估算 | 节省 |
|-------|------|--------|--------|------|
| 0 | 自动服务发现 | 1.5h | 1.5h | - |
| 1 | HTTP端点（精简） | 2h | **1h** | 1h ⬇️ |
| 2 | HTTP客户端 | 1h | 1h | - |
| 3 | CLI智能路由 | 1.5h | **1h** | 0.5h ⬇️ |
| **总计** | - | **6h** | **4.5h** | **1.5h** ⬇️ |

**节省原因**：
- 端点精简：8个 → 4个（embed, vsearch, query, health）
- CLI简化：复杂的mode选项 → 智能路由（按是否需要模型）
- 架构清晰：职责分离（代码更简单）

**时间节省：25%**

---

## 🎯 与需求和设计的对比

### 需求核对

| 需求 | 实现 | 状态 |
|------|------|------|
| 节省VRAM（4GB vs 8GB+） | 单例模型+队列串行 | ✅ 满足 |
| 向后兼容 | 保留standalone模式 | ✅ 满足 |
| 自动模式检测 | VRAM检测 | ✅ 满足 |
| 零配置体验 | 自动服务发现 | ✅ 满足 |
| 简化架构 | 8个端点 | ✅ 满足 |

### 设计核对

| 设计要求 | 实现 | 状态 |
|---------|------|------|
| 统一架构 | 单一Server进程 | ✅ 满足 |
| 简化接口 | 8个端点（模型操作） | ✅ 满足 |
| SQLite-only保持CLI | collection/index等 | ✅ 满足 |
| 自动服务发现 | 端口+进程检测 | ✅ 满足 |
| 默认端口18765 | 端口管理器 | ✅ 满足 |
| 端口冲突处理 | 自动递增 | ✅ 满足 |

---

## 🚀 实施顺序

### 推荐顺序

1. **Phase 0** (1.5h) → 自动服务发现
   - 端口管理器
   - 进程检测器
   - 智能客户端

2. **Phase 1** (2h) → HTTP端点
   - 数据模型
   - 4个端点实现

3. **Phase 2** (1h) → HTTP客户端
   - QmdHttpClient类
   - HTTP方法实现

4. **Phase 3** (1.5h) → CLI集成
   - mode选项
   - 自动检测
   - server命令更新

**优势**：
- 每个Phase都有明确的验收标准
- 可以独立测试
- 逐步验证

---

## 🎯 核心架构理解（2026-02-15 13:20 确认）

### Boss确认的架构决策

**问题本质**：
```
3个模型实例 × 4GB显存/个 = 12GB显存爆炸

解决方案：
单进程Server + 1套模型 + 队列串行 = 4GB显存 ✅
```

**核心决策**：
1. ✅ **Client-Server分离**（必须）
2. ✅ **HTTP MCP Server**（不是stdio）
3. ✅ **队列串行**（防止显存溢出）
4. ✅ **智能路由**（按是否需要模型）

### 操作分类

| 操作类型 | 需要模型 | 执行方式 | 理由 |
|---------|---------|---------|------|
| **embed** | ✅ | HTTP → Server | 需要bge模型 |
| **vsearch** | ✅ | HTTP → Server | 需要embed + 向量搜索 |
| **query** | ✅ | HTTP → Server | 需要embed + reranker + LLM扩展 |
| **search** | ❌ | 直接CLI | BM25纯算法，零等待 |
| **collection add** | ❌ | 直接CLI | SQLite操作 |
| **collection list** | ❌ | 直接CLI | SQLite查询 |
| **index** | ❌ | 直接CLI | 文件读取 + 写入 |
| **config** | ❌ | 直接CLI | YAML配置 |

### 核心价值

- ✅ 显存节省：66%（4GB vs 12GB）
- ✅ 性能提升：CLI操作零等待
- ✅ 架构清晰：职责分离
- ✅ 用户体验：零配置（自动服务发现）

---

**是否开始实现？**
