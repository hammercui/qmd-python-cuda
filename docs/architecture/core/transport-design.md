# Transport 层设计

**版本**: 1.0.0
**状态**: 设计完成
**最后更新**: 2026-02-18

---

## 概述

Transport 层是 QMD Server 对外提供服务的接口层，支持多种传输协议：

```
                QMD Server（单一进程，共享模型）
                      ├─ 核心搜索引擎
                      └─ Transport 层（对外接口）
                         ├─ HTTP Transport (port 18765)
                         └─ MCP Transport (stdio)
```

---

## 核心类设计

### QmdServer 类

```python
# qmd/server/app.py
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

---

## HTTP Transport

### 设计目标

为 CLI 命令提供 HTTP API 接口，支持跨进程通信。

### 实现

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

### API 端点

| 端点 | 方法 | 功能 | 是否需要模型 |
|------|------|------|-------------|
| `/embed` | POST | 生成嵌入向量 | ✅ |
| `/vsearch` | POST | 向量搜索 | ✅ |
| `/query` | POST | 混合搜索 | ✅ |
| `/search` | POST | BM25搜索 | ❌ |
| `/health` | GET | 健康检查 | ❌ |

---

## MCP Transport

### 设计目标

为 AI Agent（如 Claude Desktop）提供 MCP 协议接口。

### 实现

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

### MCP Tools

| Tool | 功能 | 是否需要模型 |
|------|------|-------------|
| `search` | BM25搜索 | ❌ |
| `vsearch` | 向量搜索 | ✅ |
| `query` | 混合搜索 | ✅ |
| `get` | 获取文档 | ❌ |
| `multi_get` | 批量获取 | ❌ |
| `status` | 状态查询 | ❌ |

---

## CLI 使用

### 启动 Server

```bash
# 方式 1：只启动 HTTP Transport（CLI 命令使用）
qmd server --transport http

# 方式 2：只启动 MCP Transport（Claude Desktop 使用）
qmd server --transport mcp

# 方式 3：同时启动（推荐）
qmd server --transport both

# 自定义 HTTP 端口
qmd server --transport both --http-port 18000

# 后台运行
qmd server --transport both --daemon
```

### OpenClaw 使用（自动服务发现）

```typescript
// qmd-manager.ts (现有逻辑，无需修改)
const child = spawn(this.qmd.command, ["query", query, "--json"], {
  env: this.env,
  cwd: this.workspaceDir,
});

// qmd.exe 内部逻辑（自动服务发现）
// 1. 尝试连接 localhost:18765
// 2. 失败则读取 ~/.qmd/server_port.txt
// 3. 失败则检查进程是否存在
// 4. 进程不存在则自动启动Server
// 5. 等待Server就绪并连接
// → 零配置，用户无感知
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

## 文件结构

```
qmd/
├── server/
│   ├── __init__.py
│   ├── core.py                  # 核心搜索引擎
│   ├── app.py                   # QmdServer 类
│   ├── transports/              # Transport 层
│   │   ├── __init__.py
│   │   ├── base.py              # Transport 基类
│   │   ├── http.py              # HTTP Transport
│   │   ├── mcp.py               # MCP Transport
│   │   └── stdio.py             # Stdio 处理
│   ├── tools.py                 # MCP Tools 映射
│   └── models.py                # 数据模型
├── llm/
│   └── engine.py                # LLM 引擎
├── commands/
│   └── server.py                # server 命令
└── cli.py                       # CLI 入口
```

---

## 相关文档

- [架构总览](../core/overview.md) - 完整架构设计
- [自动服务发现](../auto-discovery/overview.md) - 零配置服务发现机制
- [Client-Server分离决策](../decisions/2026-02-15-client-server-separation.md) - 决策记录

---

**文档版本**: 1.0.0
**最后更新**: 2026-02-18
