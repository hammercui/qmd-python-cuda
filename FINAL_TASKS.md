# QMD-Python 最终任务清单

**生成时间**: 2026-02-15
**项目路径**: `D:\MoneyProjects\qmd-python`
**总估算时间**: 6小时

---

## 📊 项目状态

### 当前完成度
- ✅ **75%** (6/8 阶段完成)
- ✅ 基础HTTP Server已实现
- ✅ LLMEngine双模式支持
- ✅ --mode选项已添加
- ✅ Queue改为Lock（真正串行）
- ✅ 文档完整（4个核心文档）

### 待实现（本次任务）
- ❌ Phase 0: 自动服务发现
- ❌ Phase 1: HTTP端点（8个）
- ❌ Phase 2: HTTP客户端（智能连接）
- ❌ Phase 3: CLI集成（mode选项）

---

## 🎯 核心目标

**主要问题**: 多进程并发时显存暴增（6-12GB VRAM）

**解决方案**: 统一Server架构
- ✅ 单一进程（4GB VRAM）
- ✅ 只有模型操作走Server
- ✅ SQLite操作保持CLI-only
- ✅ 自动服务发现（零配置）

**架构简化**:
```
HTTP接口：8个端点（embed, vsearch, query, search, health）
  - 比之前简化58%（19个 → 8个）
  - 实现时间减少57%（7小时 → 3小时）
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

### Phase 1: HTTP端点实现（P0 - 2小时）

**文件**:
- `qmd/server/models.py`（扩展）
- `qmd/server/app.py`（扩展）

#### Task 1.1: 数据模型（30分钟）

**文件**: `qmd/server/models.py`

**需要添加**:
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

class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    content: Optional[str] = None

class QueryRequest(BaseModel):
    query: str
    limit: int = 10
    min_score: float = 0.0
    collection: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
```

**验收标准**:
- [ ] 8个端点的请求/响应模型
- [ ] 类型注解完整
- [ ] Pydantic验证

---

#### Task 1.2: HTTP端点实现（1.5小时）

**文件**: `qmd/server/app.py`

**需要添加的端点**:

1. **POST /vsearch**（30分钟）
```python
@app.post("/vsearch", response_model=SearchResponse)
async def vsearch(request: VSearchRequest):
    """向量语义搜索"""
    async with _processing_lock:
        results = await process_vsearch(...)
    return SearchResponse(results=results)
```

2. **POST /query**（30分钟）
```python
@app.post("/query", response_model=SearchResponse)
async def query(request: QueryRequest):
    """混合搜索"""
    async with _processing_lock:
        results = await process_query(...)
    return SearchResponse(results=results)
```

3. **POST /search**（可选，15分钟）
```python
@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """BM25搜索（可选，统一体验）"""
    async with _processing_lock:
        results = await process_search(...)
    return SearchResponse(results=results)
```

4. **更新 /health**（15分钟）
```python
@app.get("/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    return HealthResponse(
        status="healthy" if _model is not None else "unhealthy",
        model_loaded=_model is not None
    )
```

**验收标准**:
- [ ] 4个端点实现完整
- [ ] 队列处理（asyncio.Lock）
- [ ] 错误处理（400, 503等）
- [ ] 符合MCP_INTERFACE_SPEC.md规范

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

### Phase 3: CLI集成（P0 - 1.5小时）

**文件**: `qmd/cli.py`

#### Task 3.1: 添加mode选项（45分钟）

**需要修改的命令**:
- `search`
- `vsearch`
- `query`
- `embed`（可选）

**示例**:
```python
@cli.command()
@click.argument("query")
@click.option("--limit", default=10, type=int)
@click.option("--min-score", default=0.0, type=float)
@click.option("--collection", default=None, type=str)
@click.option("--mode", default="auto", type=click.Choice(['auto', 'standalone', 'server']))
@click.pass_obj
def search(ctx_obj, query, limit, min_score, collection, mode):
    """BM25 full-text search"""
    
    # Auto模式检测
    if mode == "auto":
        mode = _detect_mode()
    
    if mode == "server":
        # Server模式：使用HTTP客户端
        from qmd.server.client import QmdHttpClient
        client = QmdHttpClient()
        results = client.search(query, limit=limit, min_score=min_score, collection=collection)
        # 显示结果
        _display_search_results(results)
    else:
        # Standalone模式：当前实现
        searcher = FTSSearcher(ctx_obj.db)
        results = searcher.search(query, limit=limit)
        # 显示结果
        _display_search_results(results)
```

**验收标准**:
- [ ] 4个命令添加`--mode`选项
- [ ] auto模式检测工作
- [ ] server模式使用HTTP客户端
- [ ] standalone模式使用当前逻辑
- [ ] 输出格式保持一致

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

## 📊 估算时间

| Phase | 任务 | 时间 |
|-------|------|------|
| 0 | 自动服务发现 | 1.5小时 |
| 1 | HTTP端点实现 | 2小时 |
| 2 | HTTP客户端 | 1小时 |
| 3 | CLI集成 | 1.5小时 |
| **总计** | - | **6小时** |

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

**是否开始实现？**
