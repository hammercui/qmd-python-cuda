# QMD 统一 Server 架构方案

## 背景

之前的方案将 HTTP Server 和 MCP Server 作为两个独立的实现，导致：
- ❌ 代码重复（两个 Server 各自加载模型）
- ❌ 两个进程 = 8GB+ VRAM（如果同时运行）
- ❌ 维护成本高（两套代码库）

**2026-02-15 更新**：添加**自动服务发现机制**
- ✅ 默认端口改为 18765（IANA非标准端口，冲突概率极低）
- ✅ 端口冲突时自动递增（18765 → 18766 → 18767...）
- ✅ OpenClaw CLI自动检测并启动Server（如需要）
- ✅ 进程检测避免重复启动
- ✅ 零配置体验（用户无需关心Server状态）

## 统一架构

### 核心思想

**单一 Server 进程**，通过**多种 Transport** 对外提供服务：

```
                     QMD Server (单一进程，共享模型)
                     ├─ 核心引擎（单例，4GB VRAM）
                     │  ├─ Embeddings (bge-small-zh-v1.5)
                     │  ├─ BM25 搜索
                     │  ├─ 向量搜索
                     │  └─ 混合搜索
                     │
                     ├─ 自动服务发现
                     │  ├─ 端口检测（默认18765，冲突时递增）
                     │  ├─ 端口存储（~/.qmd/server_port.txt）
                     │  └─ 进程检测（psutil）
                     │
                     └─ 多种 Transport（对外接口）
                        ├─ HTTP Transport (port 18765)
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

## 自动服务发现机制（2026-02-15 新增）

### 核心问题

OpenClaw使用QMD时需要：
- ✅ 自动检测Server是否运行
- ✅ Server未运行时自动启动
- ✅ 端口冲突时自动调整
- ✅ 避免重复启动Server进程

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                     OpenClaw CLI 调用                        │
│                 qmd.exe search "query"                       │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
         ┌──────────────────────────────────────┐
         │   Client自动服务发现逻辑              │
         │   (qmd/server/client.py)             │
         └──────────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
    尝试18765        读取端口文件        检查进程
    连接默认端口      ~/.qmd/...          psutil检测
         │                  │                  │
         │             ┌────┴────┐             │
         │             │         │             │
      成功✅          失败✅      失败✅       不存在✅
         │             │         │             │
         │             │         │         ┌───┴───┐
         │             │         │         │       │
         │             │      连接成功   启动Server
         │             │         │         │       │
         │             │         │         │   等待启动
         │             │         │         │       │
         │             │         │         │   连接成功
         │             └─────────┴─────────┴───────┘
         │
         ▼
    使用HTTP API
```

### 实现细节

#### 1. Server端：端口检测和自动递增

```python
# qmd/server/port_manager.py (新文件)
import socket
from pathlib import Path

def find_available_port(start_port: int = 18765, max_attempts: int = 100) -> int:
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No available ports in range {start_port}-{start_port + max_attempts}")

def save_server_port(port: int):
    """Save the actual server port to ~/.qmd/server_port.txt"""
    qmd_dir = Path.home() / '.qmd'
    qmd_dir.mkdir(parents=True, exist_ok=True)
    (qmd_dir / 'server_port.txt').write_text(str(port))

def get_saved_port() -> int | None:
    """Get the saved server port if exists."""
    port_file = Path.home() / '.qmd' / 'server_port.txt'
    if port_file.exists():
        return int(port_file.read_text().strip())
    return None
```

```python
# qmd/cli.py (修改server命令）
@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=18765, type=int, help="Port to bind to (auto-increment if occupied)")
@click.option("--log-level", default="info", help="Log level")
def server(host, port, log_level):
    """Start QMD MCP Server for embedding service"""
    from qmd.server.port_manager import find_available_port, save_server_port

    # 端口检测和自动递增
    try:
        actual_port = find_available_port(port)
        if actual_port != port:
            console.print(f"[yellow]Port {port} occupied, using {actual_port}[/yellow]")
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        return

    # 保存端口到文件
    save_server_port(actual_port)

    # 启动Server
    console.print(f"[cyan]Starting QMD MCP Server[/cyan]")
    console.print(f"Host: [magenta]{host}[/magenta], Port: [magenta]{actual_port}[/magenta]")
    uvicorn.run(app, host=host, port=actual_port, log_level=log_level)
```

#### 2. Client端：智能连接和自动启动

```python
# qmd/server/client.py (修改现有文件）
import subprocess
import psutil
import requests
from pathlib import Path
from qmd.server.port_manager import get_saved_port

class EmbedServerClient:
    """Auto-discovering client for QMD MCP Server."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or self._discover_server()

    def _discover_server(self) -> str:
        """Discover or auto-start the QMD server."""
        # 1. 尝试连接默认端口
        if self._try_connect("http://127.0.0.1:18765"):
            return "http://127.0.0.1:18765"

        # 2. 尝试读取保存的端口
        saved_port = get_saved_port()
        if saved_port and self._try_connect(f"http://127.0.0.1:{saved_port}"):
            return f"http://127.0.0.1:{saved_port}"

        # 3. 检查server进程是否存在
        if self._is_server_running():
            raise RuntimeError("QMD server is running but not responding")

        # 4. 进程不存在，自动启动server
        console.print("[cyan]QMD server not running, auto-starting...[/cyan]")
        return self._auto_start_server()

    def _try_connect(self, url: str, timeout: float = 1.0) -> bool:
        """Try to connect to the server."""
        try:
            response = requests.get(f"{url}/health", timeout=timeout)
            return response.status_code == 200
        except Exception:
            return False

    def _is_server_running(self) -> bool:
        """Check if qmd server process is running."""
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and 'qmd.exe' in ' '.join(cmdline) and 'server' in ' '.join(cmdline):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False

    def _auto_start_server(self) -> str:
        """Auto-start the QMD server."""
        try:
            # 启动server进程（后台）
            subprocess.Popen(
                ['qmd', 'server'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )

            # 等待server启动（最多10秒）
            import time
            for attempt in range(20):
                time.sleep(0.5)

                if self._try_connect("http://127.0.0.1:18765"):
                    return "http://127.0.0.1:18765"

                saved_port = get_saved_port()
                if saved_port and self._try_connect(f"http://127.0.0.1:{saved_port}"):
                    return f"http://127.0.0.1:{saved_port}"

            raise RuntimeError("Failed to start QMD server")

        except Exception as e:
            console.print(f"[red]Failed to auto-start server: {e}[/red]")
            raise
```

#### 3. 进程检测增强（跨平台）

```python
# qmd/server/process.py (新文件)
import psutil

def find_server_processes() -> list[psutil.Process]:
    """Find all 'qmd server' processes."""
    server_procs = []

    for proc in psutil.process_iter(['name', 'cmdline', 'create_time']):
        try:
            cmdline = proc.info.get('cmdline', [])
            if not cmdline:
                continue

            cmdline_str = ' '.join(cmdline)

            # 检测是否是qmd server命令
            is_qmd = 'qmd' in cmdline_str
            is_server = 'server' in cmdline_str

            if is_qmd and is_server:
                server_procs.append(proc)

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return server_procs

def get_server_port_from_process(proc: psutil.Process) -> int | None:
    """Extract port from server process command line."""
    try:
        cmdline = ' '.join(proc.info.get('cmdline', []))

        # 查找--port参数
        import re
        match = re.search(r'--port\s+(\d+)', cmdline)
        if match:
            return int(match.group(1))

        # 默认端口
        return 18765

    except Exception:
        return None

def kill_server_processes():
    """Kill all qmd server processes."""
    procs = find_server_processes()
    for proc in procs:
        try:
            console.print(f"[yellow]Killing server process PID {proc.pid}[/yellow]")
            proc.terminate()
        except psutil.NoSuchProcess:
            pass
```

### 使用场景

#### 场景1：OpenClaw CLI（推荐使用）

```bash
# 用户执行OpenClaw搜索（无需手动启动server）
openclaw> /search "how to use qmd"

# OpenClaw内部：
# qmd.exe search "how to use qmd"
# → 自动检测并启动server（如果需要）
# → client模式连接到http://localhost:18765
# → 搜索结果返回

# 结果：用户无感知的自动启动
```

#### 场景2：手动启动server

```bash
# 开发者手动启动
qmd server
# → 输出：Starting on port 18765
# → 保存端口到 ~/.qmd/server_port.txt

# OpenClaw连接时：
# 1. 尝试18765 ✓
# 2. 连接成功
```

#### 场景3：端口冲突

```bash
# 18765被其他服务占用
qmd server
# → 输出：Port 18765 occupied, using 18766
# → 保存端口到 ~/.qmd/server_port.txt

# OpenClaw连接时：
# 1. 尝试18765 ✗
# 2. 读取文件：18766 ✓
# 3. 连接成功
```

### 依赖需求

需要添加到 `pyproject.toml`:

```toml
dependencies = [
    # ... 现有依赖
    "psutil>=5.9.0",  # 进程检测
    "requests>=2.28.0",  # HTTP连接检测
]
```

### 实现优先级

| 任务 | 优先级 | 预估时间 |
|------|--------|----------|
| 端口检测和递增 | P0 | 1小时 |
| 端口存储机制 | P0 | 30分钟 |
| 进程检测 | P0 | 1小时 |
| 自动启动逻辑 | P0 | 1.5小时 |
| 测试和调试 | P0 | 1小时 |
| **总计** | - | **5小时** |

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
# → 默认端口：18765
# → 端口冲突时自动递增

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
    port: 18765  # 默认端口（非标准，冲突概率低）
    log_level: info
  
  # MCP 配置
  mcp:
    enabled: true
  
  # 自动服务发现
  auto_discovery:
    enabled: true
    port_file: ~/.qmd/server_port.txt
    max_attempts: 100  # 端口递增最大尝试次数
  
  # 队列配置
  queue:
    max_concurrent: 1  # 串行执行
    timeout: 30        # 超时时间（秒）
```

### 环境变量

```bash
# 强制 Server 模式
export QMD_FORCE_SERVER=1

# 指定 HTTP 端口（覆盖默认18765）
export QMD_HTTP_PORT=18000

# 指定 Transport
export QMD_TRANSPORT=both  # http | mcp | both
```

---

## 实施步骤

### Phase 0: 自动服务发现（P0，2026-02-15 新增）

| 步骤 | 文件 | 说明 |
|------|------|------|
| 0.1 | `qmd/server/port_manager.py` | 端口检测和自动递增 |
| 0.2 | `qmd/server/process.py` | 进程检测和端口提取 |
| 0.3 | `qmd/server/client.py` | 智能连接和自动启动 |
| 0.4 | `qmd/cli.py` (server命令） | 端口存储，默认18765 |
| 0.5 | 测试 | 自动服务发现功能 |

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
│   ├── core.py                  # 核心搜索引擎（新增）
│   ├── app.py                   # QmdServer 类（重构）
│   ├── port_manager.py           # 端口检测和递增（新增）
│   ├── process.py                # 进程检测（新增）
│   ├── client.py                 # 智能客户端（重构）
│   ├── transports/               # Transport 层（新增）
│   │   ├── __init__.py
│   │   ├── base.py               # Transport 基类
│   │   ├── http.py               # HTTP Transport（重构）
│   │   ├── mcp.py                # MCP Transport（新增）
│   │   └── stdio.py              # Stdio 处理（新增）
│   ├── tools.py                  # MCP Tools 映射（新增）
│   └── models.py                 # 保持不变
├── llm/
│   └── engine.py                 # 移除 server_url（统一管理）
├── commands/
│   └── server.py                 # 添加 --transport 选项
└── cli.py                        # 更新 server 命令
```

---

## 兼容性保证

### 向后兼容

| 功能 | 兼容性 |
|------|--------|
| **现有 HTTP Server** | ✅ 完全兼容（`qmd server` 默认行为，端口8000→18765） |
| **CLI 命令** | ✅ 完全兼容（`--mode` 选项保留） |
| **OpenClaw 集成** | ✅ 完全兼容（自动服务发现，无需修改） |
| **配置文件** | ✅ 向后兼容（添加新字段） |
| **端口变更** | ⚠️ 默认8000→18765（非标准端口，冲突概率低） |

### MCP 兼容性

| 接口 | 原始 QMD | qmd-python |
|------|----------|------------|
| **Tool 名称** | ✅ 完全相同 | 完全相同 |
| **参数 Schema** | ✅ 完全相同 | 完全相同 |
| **输出结构** | ✅ 完全相同 | 完全相同 |
| **URI 格式** | ✅ 完全相同 | 完全相同 |

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
4. **用户体验**：
   - 单一 `qmd server` 命令
   - **自动服务发现**（2026-02-15 新增）
   - 零配置（OpenClaw无需手动启动Server）
5. **智能端口管理**：
   - 默认18765（IANA非标准端口）
   - 冲突时自动递增
   - 端口信息持久化

### 下一步

- [ ] Phase 0: 自动服务发现实现（P0）
- [ ] Phase 1: 核心重构
- [ ] Phase 2: HTTP Transport
- [ ] Phase 3: MCP Transport
- [ ] Phase 4: 文档与测试

---

**相关文档**：
- [MCP Server Proposal](./MCP_SERVER_PROPOSAL.md) - 方案概述
- [MCP Compatibility Analysis](./MCP_COMPATIBILITY_ANALYSIS.md) - 接口规范
- [Architecture Analysis](./ARCHITECTURE_ANALYSIS.md) - OpenClaw 集成分析
