# QMD 自动服务发现机制

**日期**: 2026-02-15
**状态**: 设计完成，待实现
**优先级**: P0（核心功能）

---

## 概述

自动服务发现机制允许OpenClaw和其他AI工具**透明地使用QMD Server**，无需用户手动启动或管理Server进程。

### 核心价值

| 维度 | 分离设计 | 自动服务发现 |
|------|----------|----------------|
| **用户操作** | 手动启动server | 零操作 |
| **进程管理** | 可能重复启动 | 自动检测避免重复 |
| **端口冲突** | 启动失败 | 自动递增 |
| **配置复杂度** | 需要知道端口 | 零配置 |

---

## 架构设计

### 工作流程图

```
┌─────────────────────────────────────────────────────┐
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
         │             │         │         │   等待启动
         │             │         │         │   连接成功
         │             └─────────┴─────────┴───────┘
         │
         ▼
    使用HTTP API
```

---

## 核心组件

### 1. Server端：端口管理器

**文件**: `qmd/server/port_manager.py`

#### 功能

| 函数 | 功能 | 返回值 |
|------|------|--------|
| `find_available_port(start_port, max_attempts)` | 检测可用端口，冲突时递增 | int |
| `save_server_port(port)` | 保存实际端口到文件 | None |
| `get_saved_port()` | 读取保存的端口 | int \| None |

#### 实现细节

```python
import socket
from pathlib import Path

def find_available_port(start_port: int = 18765, max_attempts: int = 100) -> int:
    """
    Find an available port starting from start_port.
    
    Args:
        start_port: Starting port number (default: 18765)
        max_attempts: Maximum ports to try (default: 100)
    
    Returns:
        First available port in range
    
    Raises:
        RuntimeError: If no available port found
    """
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No available ports in range {start_port}-{start_port + max_attempts}")

def save_server_port(port: int):
    """
    Save the actual server port to ~/.qmd/server_port.txt.
    
    Args:
        port: The actual port the server is listening on
    """
    qmd_dir = Path.home() / '.qmd'
    qmd_dir.mkdir(parents=True, exist_ok=True)
    (qmd_dir / 'server_port.txt').write_text(str(port))

def get_saved_port() -> int | None:
    """
    Get the saved server port if exists.
    
    Returns:
        Port number if file exists, None otherwise
    """
    port_file = Path.home() / '.qmd' / 'server_port.txt'
    if port_file.exists():
        return int(port_file.read_text().strip())
    return None
```

#### 测试

```python
# 测试端口检测
from qmd.server.port_manager import find_available_port
port = find_available_port()
print(f"Available port: {port}")  # 预期：18765

# 测试端口保存
from qmd.server.port_manager import save_server_port, get_saved_port
save_server_port(18766)
saved = get_saved_port()
print(f"Saved port: {saved}")  # 预期：18766
```

---

### 2. 进程检测器

**文件**: `qmd/server/process.py`

#### 功能

| 函数 | 功能 | 返回值 |
|------|------|--------|
| `find_server_processes()` | 查找所有qmd server进程 | list[psutil.Process] |
| `get_server_port_from_process(proc)` | 从命令行提取端口号 | int \| None |
| `kill_server_processes()` | 调试停止所有server进程 | None |

#### 实现细节

```python
import psutil
import re

def find_server_processes() -> list[psutil.Process]:
    """
    Find all 'qmd server' processes.
    
    Returns:
        List of running qmd server processes
    """
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
    """
    Extract port from server process command line.
    
    Args:
        proc: Process object
    
    Returns:
        Port number if found, None otherwise
    """
    try:
        cmdline = ' '.join(proc.info.get('cmdline', []))
        
        # 查找--port参数
        match = re.search(r'--port\s+(\d+)', cmdline)
        if match:
            return int(match.group(1))
        
        # 默认端口
        return 18765
    
    except Exception:
        return None

def kill_server_processes():
    """
    Attempt to kill all qmd server processes.
    
    Warning: Use only for debugging/testing!
    """
    procs = find_server_processes()
    for proc in procs:
        try:
            console.print(f"[yellow]Killing server process PID {proc.pid}[/yellow]")
            proc.terminate()
        except psutil.NoSuchProcess:
            pass
```

#### 测试

```python
# 测试进程检测
from qmd.server.process import find_server_processes, get_server_port_from_process

procs = find_server_processes()
print(f"Found {len(procs)} server processes")

for proc in procs:
    port = get_server_port_from_process(proc)
    print(f"PID {proc.pid}: port {port}")
```

---

### 3. 智能客户端

**文件**: `qmd/server/client.py`

#### 核心方法：`_discover_server()`

```python
import subprocess
import psutil
import requests
import time
import os
from pathlib import Path
from qmd.server.port_manager import get_saved_port

class EmbedServerClient:
    """Auto-discovering client for QMD MCP Server."""
    
    def __init__(self, base_url: str | None = None):
        """
        Initialize client with auto-discovery.
        
        Args:
            base_url: Explicit server URL (skips auto-discovery)
        """
        self.base_url = base_url or self._discover_server()
    
    def _discover_server(self) -> str:
        """
        Discover or auto-start the QMD server.
        
        Discovery sequence:
        1. Try connecting to default port (18765)
        2. Try reading saved port from file
        3. Check if server process exists
        4. If no process, auto-start server
        
        Returns:
            Server URL
            
        Raises:
            RuntimeError: If server exists but not accessible
        """
        # 1. 尝试连接默认端口
        if self._try_connect("http://127.0.0.1:18765"):
            return "http://127.0.0.1:18765"
        
        # 2. 尝试读取保存的端口
        saved_port = get_saved_port()
        if saved_port and self._try_connect(f"http://127.0.0.1:{saved_port}"):
            return f"http://127.0.0.1:{saved_port}"
        
        # 3. 检查server进程是否存在
        if self._is_server_running():
            console.print("[red]Error: Server process exists but not accessible[/red]")
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
        from qmd.server.process import find_server_processes
        procs = find_server_processes()
        return len(procs) > 0
    
    def _auto_start_server(self) -> str:
        """
        Auto-start the QMD server.
        
        Returns:
            Server URL after successful startup
            
        Raises:
            RuntimeError: If startup fails
        """
        try:
            # 启动server进程（后台）
            subprocess.Popen(
                ['qmd', 'server'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            
            # 等待server启动（最多10秒）
            for attempt in range(20):
                time.sleep(0.5)
                
                # 尝试连接默认端口
                if self._try_connect("http://127.0.0.1:18765"):
                    return "http://127.0.0.1:18765"
                
                # 尝试读取保存的端口
                saved_port = get_saved_port()
                if saved_port and self._try_connect(f"http://127.0.0.1:{saved_port}"):
                    return f"http://127.0.0.1:{saved_port}"
            
            raise RuntimeError("Failed to start QMD server")
        
        except Exception as e:
            console.print(f"[red]Failed to auto-start server: {e}[/red]")
            raise
```

---

## CLI集成

### Server命令更新

**文件**: `qmd/cli.py`

```python
@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=18765, type=int, help="Port to bind to (auto-increment if occupied)")
@click.option("--log-level", default="info", help="Log level")
def server(host, port, log_level):
    """Start QMD MCP Server for embedding service"""
    import logging
    import signal
    import sys

    logging.basicConfig(level=getattr(logging, log_level.upper()))

    import uvicorn
    from qmd.server.app import app
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
    console.print(f"[dim]Embed model: BAAI/bge-small-zh-v1.5[/dim]")
    console.print(f"[dim]VRAM usage: Single model instance (~2-4GB)[/dim]")
    console.print(f"[dim]Max queue size: 100 requests[/dim]")
    console.print("[yellow]Press Ctrl+C to stop[/yellow]")

    def signal_handler(sig, frame):
        console.print("\n[yellow]Shutting down server...[/yellow]")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    uvicorn.run(app, host=host, port=actual_port, log_level=log_level)
```

---

## 依赖管理

### pyproject.toml

```toml
[project.optional-dependencies]
# MCP Server dependencies (for low VRAM systems)
server = [
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.23.0",
    "httpx>=0.24.0",
    "psutil>=5.9.0",      # Process detection for auto-discovery
    "requests>=2.28.0",   # HTTP connection checking
]
```

### 安装

```bash
# 安装server依赖
pip install -e .[server]

# 验证安装
pip list | grep -E "psutil|requests"
```

---

## 使用场景

### 场景1：首次使用（无server）

```bash
# 用户执行搜索（无需手动启动server）
qmd search "how to use qmd"

# 内部流程：
# 1. 尝试连接18765 → 失败
# 2. 读取端口文件 → 不存在
# 3. 检查进程 → 不存在
# 4. 自动启动server
# 5. 等待启动（最多10秒）
# 6. 连接成功
# 7. 执行搜索

# 输出：
# [cyan]QMD server not running, auto-starting...[/cyan]
# [cyan]Starting QMD MCP Server[/cyan]
# [cyan]Host: 127.0.0.1, Port: 18765[/cyan]
# (搜索结果...)
```

### 场景2：Server已运行

```bash
# Terminal 1: 启动server
qmd server
# [cyan]Starting QMD MCP Server[/cyan]
# [cyan]Host: 127.0.0.1, Port: 18765[/cyan]

# Terminal 2: 执行搜索
qmd search "test query"

# 内部流程：
# 1. 尝试连接18765 → 成功
# 2. 直接使用现有连接
# 3. 执行搜索

# 输出：
# (无启动日志，直接搜索结果)
```

### 场景3：端口冲突

```bash
# Terminal 1: 占用18765
python -m http.server 18765

# Terminal 2: 执行搜索
qmd search "test query"

# 内部流程：
# 1. 尝试连接18765 → 失败（被占用）
# 2. 读取端口文件 → 不存在
# 3. 检查进程 → 不存在
# 4. 自动启动server
# 5. 端口检测：18765被占用
# 6. 尝试18766 → 成功
# 7. 保存18766到文件
# 8. 连接成功
# 9. 执行搜索

# 输出：
# [cyan]QMD server not running, auto-starting...[/cyan]
# [yellow]Port 18765 occupied, using 18766[/yellow]
# [cyan]Starting QMD MCP Server[/cyan]
# [cyan]Host: 127.0.0.1, Port: 18766[/cyan]
# (搜索结果...)
```

### 场景4：Server退出后重启

```bash
# Terminal 1: 启动server
qmd server
# (Ctrl+C 停止)
# [yellow]Shutting down server...[/yellow]

# Terminal 2: 执行搜索
qmd search "test query"

# 内部流程：
# 1. 尝试连接18765 → 失败
# 2. 读取端口文件：18765 → 失败（进程已退出）
# 3. 检查进程 → 不存在
# 4. 自动启动新server
# 5. 连接成功
# 6. 执行搜索

# 输出：
# [cyan]QMD server not running, auto-starting...[/cyan]
# [cyan]Starting QMD MCP Server[/cyan]
# (搜索结果...)
```

---

## 测试检查清单

### 单元测试

- [ ] `test_find_available_port()` - 端口检测和递增
- [ ] `test_save_server_port()` - 端口保存
- [ ] `test_get_saved_port()` - 端口读取
- [ ] `test_find_server_processes()` - 进程检测
- [ ] `test_get_server_port_from_process()` - 端口提取
- [ ] `test_try_connect()` - 连接检测
- [ ] `test_is_server_running()` - 进程状态
- [ ] `test_auto_start_server()` - 自动启动

### 集成测试

- [ ] 场景1：首次使用（无server）
- [ ] 场景2：Server已运行
- [ ] 场景3：端口冲突
- [ ] 场景4：Server退出后重启
- [ ] OpenClaw集成测试

### 边界测试

- [ ] 端口0-1024（系统保留端口）
- [ ] 端口被系统服务占用
- [ ] 无权限启动进程
- [ ] 启动超时（延迟高的系统）

---

## 实现计划

| 任务 | 优先级 | 预估时间 |
|------|--------|----------|
| 端口检测和递增 | P0 | 1小时 |
| 端口存储机制 | P0 | 30分钟 |
| 进程检测 | P0 | 1小时 |
| 自动启动逻辑 | P0 | 1.5小时 |
| CLI命令更新 | P0 | 30分钟 |
| 依赖添加 | P0 | 10分钟 |
| 单元测试 | P0 | 1.5小时 |
| 集成测试 | P0 | 1小时 |
| **总计** | - | **6-7小时** |

---

## 相关文档

- **统一架构**: `docs/UNIFIED_SERVER_ARCHITECTURE.md` - 完整架构设计
- **MCP提案**: `docs/MCP_SERVER_PROPOSAL.md` - 原始提案
- **兼容性分析**: `docs/MCP_COMPATIBILITY_ANALYSIS.md` - 接口规范
- **项目状态**: `PROJECT_STATUS.md` - 实现进度

---

**最后更新**: 2026-02-15
**下次检查**: 实现完成后更新测试结果
