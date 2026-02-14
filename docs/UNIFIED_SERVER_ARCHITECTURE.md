# QMD 统一 Server 架构方案

## 背景

之前的方案将 HTTP Server 和 MCP Server 作为两个独立的实现，导致：
- ❌ 代码重复（两个 Server 各自加载模型）
- ❌ 两个进程 = 8GB+ VRAM（如果同时运行）
- ❌ 维护成本高（两套代码库）

## 统一架构

### 核心思想

**单一 Server 进程**，通过**多种 Transport** 对外提供服务：

```
                    QMD Server (单一进程，共享模型)
                    ├─ 核心引擎（单例）
                    │  ├─ Embeddings (bge-small-zh-v1.5)
                    │  ├─ BM25 搜索
                    │  ├─ 向量搜索
                    │  └─ 混合搜索
                    │
                    └─ 多种 Transport（对外接口）
                       ├─ HTTP Transport (port 8000)
                       │  └─ 端点：/search, /vsearch, /query, /embed, /health
                       │
                       └─ MCP Transport (stdio)
                          └─ 工具：search, vsearch, query, get, status
```

### 架构优势

| 维度 | 分离设计 | 统一架构 |
|------|----------|----------|
| **进程数** | 2 个 | 1 个 |
| **显存占用** | 8GB（两个模型） | 4GB（单例） |
| **代码复用** | 低（重复逻辑） | 高（共享核心） |
| **维护成本** | 高（两套代码） | 低（单一代码库） |
| **用户体验** | 困惑（两个命令） | 简单（一个命令） |

---

## 实现方案

### 核心类设计

```python
# qmd/server/app.py (重构)
class QmdServer:
    """统一的 QMD Server"""
    
    def __init__(self):
        # 单例模型加载
        self.llm = LLMEngine(mode="standalone")
        
        # 单一队列（真正的序列化）
        self.lock = asyncio.Lock()
        
        # 核心搜索引擎
        self.core = SearchCore(self.llm)
        
        # 多个 Transport
        self.transports = []
    
    async def search(self, query: str, collection: str = None, limit: int = 10):
        """核心搜索逻辑（所有 Transport 共享）"""
        async with self.lock:  # 串行化
            return await self.core.search(query, collection, limit)
    
    async def vsearch(self, query: str, ...):
        """向量搜索（共享）"""
        async with self.lock:
            return await self.core.vsearch(query, ...)
    
    async def query(self, query: str, ...):
        """混合搜索（共享）"""
        async with self.lock:
            return await self.core.query(query, ...)
    
    def add_transport(self, transport):
        """添加 Transport"""
        self.transports.append(transport)
    
    async def start(self, transport_config: dict):
        """启动指定的 Transport"""
        transport_type = transport_config.get("type", "http")
        
        if transport_type == "http":
            from qmd.server.transports.http import HttpTransport
            http = HttpTransport(self, transport_config)
            await http.start()
        
        elif transport_type == "mcp":
            from qmd.server.transports.mcp import McpTransport
            mcp = McpTransport(self)
            await mcp.start()
        
        elif transport_type == "both":
            # 同时启动两个 Transport
            await self.start({"type": "http", **transport_config})
            await self.start({"type": "mcp", **transport_config})
```

### Transport 实现

#### HTTP Transport

```python
# qmd/server/transports/http.py
class HttpTransport:
    """HTTP Transport - 为 CLI 命令提供 API"""
    
    def __init__(self, server: QmdServer, config: dict):
        self.server = server
        self.app = FastAPI()
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 8000)
        self._setup_routes()
    
    def _setup_routes(self):
        @self.app.post("/search")
        async def search(query: str, collection: str = None, limit: int = 10):
            return await self.server.search(query, collection, limit)
        
        @self.app.post("/vsearch")
        async def vsearch(query: str, ...):
            return await self.server.vsearch(query, ...)
        
        @self.app.post("/query")
        async def query(query: str, ...):
            return await self.server.query(query, ...)
        
        @self.app.post("/embed")
        async def embed(texts: List[str]):
            return await self.server.llm.embed_texts(texts)
        
        @self.app.get("/health")
        async def health():
            return {"status": "healthy", "model_loaded": True}
    
    async def start(self):
        """启动 HTTP Server"""
        import uvicorn
        uvicorn.run(self.app, host=self.host, port=self.port)
```

#### MCP Transport

```python
# qmd/server/transports/mcp.py
class McpTransport:
    """MCP Transport - 为 AI Agent 提供工具接口"""
    
    def __init__(self, server: QmdServer):
        self.server = server
        self.mcp_server = None
        self._setup_tools()
    
    def _setup_tools(self):
        """注册 MCP Tools"""
        from mcp import McpServer
        
        self.mcp_server = McpServer("qmd", "1.0.0")
        
        # Tool: search
        self.mcp_server.register_tool(
            "search",
            {
                "query": str,
                "collection": str,
                "limit": int
            },
            self._search_handler
        )
        
        # Tool: vsearch
        self.mcp_server.register_tool(
            "vsearch",
            {...},
            self._vsearch_handler
        )
        
        # Tool: query
        self.mcp_server.register_tool(
            "query",
            {...},
            self._query_handler
        )
        
        # Tool: get, multi_get, status...
    
    async def _search_handler(self, query: str, collection: str = None, limit: int = 10):
        """MCP Tool 处理器 → 调用 Server 核心逻辑"""
        return await self.server.search(query, collection, limit)
    
    async def _vsearch_handler(self, query: str, ...):
        return await self.server.vsearch(query, ...)
    
    async def _query_handler(self, query: str, ...):
        return await self.server.query(query, ...)
    
    async def start(self):
        """启动 MCP Server (stdio)"""
        from mcp import StdioServerTransport
        
        transport = StdioServerTransport()
        await self.mcp_server.connect(transport)
```

---

## CLI 使用

### 单一命令，多种模式

```bash
# 方式 1：只启动 HTTP Transport（CLI 命令使用）
qmd server --transport http

# 方式 2：只启动 MCP Transport（Claude Desktop 使用）
qmd server --transport mcp

# 方式 3：同时启动（推荐）
qmd server --transport both

# 自定义 HTTP 端口
qmd server --transport both --http-port 8000

# 后台运行
qmd server --transport both --daemon
```

### OpenClaw 使用（透明，无需修改）

```typescript
// qmd-manager.ts (现有逻辑，无需修改)
const child = spawn(this.qmd.command, ["query", query, "--json"], {
  env: this.env,
  cwd: this.workspaceDir,
});

// qmd.exe 内部逻辑（已有）
// 1. 检测 Server 是否可用（HTTP health check）
// 2. 如果可用 → HTTP 调用
// 3. 如果不可用 → 本地 standalone 模式
```

### Claude Desktop 配置

```json
// ~/.claude/settings.json 或 claude_desktop_config.json
{
  "mcpServers": {
    "qmd": {
      "command": "qmd",
      "args": ["server", "--transport", "mcp"]
    }
  }
}
```

---

## 配置文件

### YAML 配置

```yaml
# ~/.config/qmd/server.yml
server:
  # Transport 模式：http | mcp | both
  transport: both
  
  # HTTP 配置
  http:
    host: 127.0.0.1
    port: 8000
    log_level: info
  
  # MCP 配置
  mcp:
    enabled: true
  
  # 队列配置
  queue:
    max_concurrent: 1  # 串行执行
    timeout: 30        # 超时时间（秒）
```

### 环境变量

```bash
# 强制 Server 模式
export QMD_FORCE_SERVER=1

# 指定 HTTP 端口
export QMD_HTTP_PORT=8000

# 指定 Transport
export QMD_TRANSPORT=both  # http | mcp | both
```

---

## 实施步骤

### Phase 1: 核心重构（P0）

| 步骤 | 文件 | 说明 |
|------|------|------|
| 1.1 | `qmd/server/core.py` | 提取核心搜索引擎 |
| 1.2 | `qmd/server/app.py` | 重构为 QmdServer 类 |
| 1.3 | `qmd/server/transports/` | 创建 Transport 目录 |
| 1.4 | `qmd/server/transports/__init__.py` | Transport 基类 |

### Phase 2: HTTP Transport（P0）

| 步骤 | 文件 | 说明 |
|------|------|------|
| 2.1 | `qmd/server/transports/http.py` | 重构现有 HTTP 逻辑 |
| 2.2 | `qmd/commands/server.py` | 添加 `--transport` 选项 |
| 2.3 | 测试 | HTTP Transport 功能 |

### Phase 3: MCP Transport（P1）

| 步骤 | 文件 | 说明 |
|------|------|------|
| 3.1 | `qmd/server/transports/mcp.py` | MCP Transport |
| 3.2 | `qmd/server/transports/stdio.py` | Stdio 处理 |
| 3.3 | `qmd/server/transports/tools.py` | MCP Tools 映射 |
| 3.4 | 测试 | MCP Transport 功能 |

### Phase 4: 文档与测试（P2）

| 步骤 | 内容 |
|------|------|
| 4.1 | 更新 README.md |
| 4.2 | 更新 docs/MCP_SERVER.md |
| 4.3 | 集成测试 |
| 4.4 | 性能测试 |

---

## 文件结构（重构后）

```
qmd/
├── server/
│   ├── __init__.py
│   ├── core.py               # 核心搜索引擎（新增）
│   ├── app.py                # QmdServer 类（重构）
│   ├── transports/           # Transport 层（新增）
│   │   ├── __init__.py
│   │   ├── base.py           # Transport 基类
│   │   ├── http.py           # HTTP Transport（重构）
│   │   ├── mcp.py            # MCP Transport（新增）
│   │   └── stdio.py          # Stdio 处理（新增）
│   ├── tools.py              # MCP Tools 映射（新增）
│   └── models.py             # 保持不变
├── llm/
│   └── engine.py             # 移除 server_url（统一管理）
├── commands/
│   └── server.py             # 添加 --transport 选项
└── cli.py                    # 更新 server 命令
```

---

## 兼容性保证

### 向后兼容

| 功能 | 兼容性 |
|------|--------|
| **现有 HTTP Server** | ✅ 完全兼容（`qmd server` 默认行为） |
| **CLI 命令** | ✅ 完全兼容（`--mode` 选项保留） |
| **OpenClaw 集成** | ✅ 完全兼容（无需修改） |
| **配置文件** | ✅ 向后兼容（添加新字段） |

### MCP 兼容性

| 接口 | 原始 QMD | qmd-python |
|------|----------|------------|
| **Tool 名称** | ✅ 完全相同 | 完全相同 |
| **参数 Schema** | ✅ 完全相同 | 完全相同 |
| **输出结构** | ✅ 完全相同 | 完全相同 |
| **URI 格式** | ✅ 完全相同 | 完全相同 |

---

## 总结

### 核心改进

1. **单一进程**：4GB VRAM（vs 分离设计的 8GB）
2. **代码复用**：共享核心搜索引擎
3. **维护简单**：单一代码库
4. **用户体验**：单一 `qmd server` 命令

### 下一步

- [ ] Phase 1: 核心重构
- [ ] Phase 2: HTTP Transport
- [ ] Phase 3: MCP Transport
- [ ] Phase 4: 文档与测试

---

**相关文档**：
- [MCP Server Proposal](./MCP_SERVER_PROPOSAL.md) - 方案概述
- [MCP Compatibility Analysis](./MCP_COMPATIBILITY_ANALYSIS.md) - 接口规范
- [Architecture Analysis](./ARCHITECTURE_ANALYSIS.md) - OpenClaw 集成分析
