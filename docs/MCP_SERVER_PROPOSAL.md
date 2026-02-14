# QMD MCP Server 方案（统一架构）

## 背景

OpenClaw 通过 `memory.backend: "qmd"` 使用 QMD 作为记忆搜索后端。当前实现通过 CLI spawn 进程方式调用 QMD，对于 4GB/6GB VRAM 用户会导致 CUDA OOM 问题。

**核心问题**：每次搜索都创建新进程 → 每个进程加载模型 → 显存不足。

## 方案概述

**不修改 OpenClaw 源码**，通过在 qmd-python 中实现 **单一 Server** 来解决 OOM 问题：

```
                    ┌─────────────────────────────────┐
                    │                                 OpenClaw                          │
                    │  (QmdMemoryManager - 无需修改)                  │
                    └───────────────┬───────────────────────┘
                                  │ spawn (现有逻辑)
                                  ▼
                         ┌────────────────────────┐
                         │  qmd.exe (MCP Client) │
                         └─────────────┬─────────────┘
                                       │ stdio/HTTP 协议通信
                                       ▼
                            ┌────────────────────────────┐
                            │  QMD Server (单一共享进程)  │
                            │  - 核心引擎（共享模型）     │
                            │  - 队列处理（单一队列）     │
                            └─────────────┬────────────────┘
                                         │
                      ┌───────────┴────────────┐
                      │     多种 Transport     │
                      ├───────────┴────────────┤
                      │                              │
                      ▼                              ▼
            ┌────────────────┐   ┌────────────────┘
            │ HTTP Transport   │   │ MCP Transport (stdio)
            └────────────────┘   └────────────────┘
         (CLI 命令使用)          (Claude Desktop 使用)
```

## 架构优势

| 特性 | 说明 |
|------|------|
| ✅ **不动 OpenClaw** | 继续使用 `qmd` backend，无需修改源码 |
| ✅ **解决 OOM** | 单一 Server 进程 = 单一模型实例（4GB VRAM） |
| ✅ **向后兼容** | CLI 模式依然可用（不启动 MCP Server 时） |
| ✅ **职责分离** | qmd-python 负责 QMD，OpenClaw 负责 Agent |
| ✅ **通用性强** | MCP 是标准协议，其他工具也可使用 |
| ✅ **代码复用** | 核心引擎逻辑共享，避免重复 |
| ✅ **维护简单** | 单一代码库，统一测试和发布 |

## 工作流程

### 1. 用户启动 QMD Server（首次使用）

```bash
# 方式 1：HTTP Transport（CLI 命令使用）
qmd server --transport http

# 方式 2：MCP Transport（Claude Desktop 使用）
qmd server --transport mcp

# 方式 3：同时启动（推荐）
qmd server --transport both

# 后台运行
qmd server --transport both --daemon
```

### 2. Server 自动检测模式

```python
# qmd/llm/engine.py (已有逻辑)
def _detect_mode(mode: str) -> str:
    if mode != "auto":
        return mode

    # VRAM 检测
    vram = _detect_vram()
    
    # VRAM < 8GB → 提示用户启动 Server
    if vram < 8192:
        logger.warning("Low VRAM detected. Start 'qmd server --transport http' for better performance")
        return "mcp"  # 或提示用户
    
    # VRAM >= 8GB → standalone (最佳性能)
    return "standalone"
```

### 3. OpenClaw 使用（透明，无需修改）

```typescript
// qmd-manager.ts (现有逻辑，无需修改)
const child = spawn(this.qmd.command, ["query", query, "--json"], {
  env: this.env,
  cwd: this.workspaceDir,
});

// qmd.exe 内部逻辑（已有）
// 1. 检测 Server 是否可用
// 2. 如果可用 → HTTP 调用
// 3. 如果不可用 → 本地 standalone 模式
```

### 2. qmd.exe 自动检测 MCP Server

```python
# qmd/llm/engine.py (新增检测逻辑)
def _detect_mode(mode: str) -> str:
    if mode != "auto":
        return mode

    # 1. 检查环境变量
    if os.getenv("QMD_MCP_SERVER_URL"):
        return "mcp"

    # 2. 检查配置文件
    config = load_config()
    if config.get("mcpServer", {}).get("enabled"):
        return "mcp"

    # 3. 尝试连接
    try:
        response = requests.get("http://localhost:8080/health", timeout=1)
        return "mcp"
    except:
        pass

    # 4. 回退到 auto 模式原有逻辑
    vram = _detect_vram()
    return "mcp" if vram < 8192 else "standalone"
```

### 3. OpenClaw 使用（透明，无需修改）

```typescript
// qmd-manager.ts (现有逻辑，无需修改）
const child = spawn(this.qmd.command, ["query", query, "--json"], {
  env: this.env,
  cwd: this.workspaceDir,
});

// qmd.exe 内部自动检测到 MCP Server
// → 转换为 MCP Client 调用
// → 通过 stdio 发送请求
```

## 实现部分

### Phase 1: 核心重构（统一 Server 架构）

| 步骤 | 文件 | 说明 |
|------|------|------|
| 1.1 | `qmd/server/core.py` | 核心搜索引擎（共享逻辑） |
| 1.2 | `qmd/server/app.py` | QmdServer 类（单例模型 + 队列） |
| 1.3 | `qmd/server/transports/base.py` | Transport 基类 |
| 1.4 | `qmd/server/transports/http.py` | HTTP Transport（已有） |
| 1.5 | `qmd/server/transports/mcp.py` | MCP Transport（新增） |

### Phase 2: MCP Transport 实现

| 步骤 | 文件 | 说明 |
|------|------|------|
| 2.1 | `qmd/server/transports/mcp.py` | MCP Transport |
| 2.2 | `qmd/server/transports/stdio.py` | Stdio 处理 |
| 2.3 | `qmd/server/transports/tools.py` | MCP Tools 映射 |

**MCP Tools 映射**（HTTP 端点 → MCP 工具）：
- `POST /search` → `search` (BM25 全文搜索)
- `POST /vsearch` → `vsearch` (向量搜索)
- `POST /query` → `query` (混合搜索)
- `GET /get` → `get` (读取文档)
- `GET /multi_get` → `multi_get` (批量读取)
- `GET /status` → `status` (状态查询)

### Phase 3: CLI 集成

| 步骤 | 文件 | 说明 |
|------|------|------|
| 3.1 | `qmd/commands/server.py` | 添加 `--transport` 选项 |
| 3.2 | `qmd/cli.py` | 更新 `qmd server` 命令 |
| 3.3 | `qmd/llm/engine.py` | 移除 `server_url`（由 Server 统一管理） |

### Phase 4: 配置与文档

| 步骤 | 内容 |
|------|------|
| 4.1 | `config/server.yml` | Server 配置（transport 模式） |
| 4.2 | `README.md` | 更新使用说明 |
| 4.3 | `docs/MCP_MODE.md` | 架构说明 |

## 配置示例

### qmd-mcp-server 启动

```bash
# 默认配置
qmd-mcp-server

# 自定义
qmd-mcp-server --port 8080 --log-level debug

# 后台运行
qmd-mcp-server --daemon
```

### OpenClaw 使用（无需修改）

```yaml
# openclaw config.yml
memory:
  backend: qmd
  qmd:
    command: qmd  # 依然是 qmd 命令
    # qmd.exe 会自动检测 MCP Server
```

## 错误处理

| 场景 | 行为 |
|------|------|
| MCP Server 不可用 | 自动回退到 CLI 模式 |
| 请求超时 | 重试 3 次，失败后回退 |
| Server 崩溃 | 降级到 standalone 模式 |

## 与原始 QMD 的兼容性

需要确保 qmd-python 的 MCP Server 接口与原始 QMD 的 MCP Server **保持一致**：

1. **Tool 名称** - `qmd_search`, `qmd_vsearch`, etc.
2. **参数格式** - JSON Schema
3. **返回格式** - 标准化的 JSON 响应
4. **Transport** - 支持 stdio, SSE, WebSocket

详细分析见 `docs/ARCHITECTURE_ANALYSIS.md`
