# QMD MCP Server 方案

## 背景

OpenClaw 通过 `memory.backend: "qmd"` 使用 QMD 作为记忆搜索后端。当前实现通过 CLI spawn 进程方式调用 QMD，对于 4GB/6GB VRAM 用户会导致 CUDA OOM 问题。

**核心问题**：每次搜索都创建新进程 → 每个进程加载模型 → 显存不足。

## 方案概述

**不修改 OpenClaw 源码**，通过在 qmd-python 中实现 MCP Server 来解决 OOM 问题：

```
OpenClaw (QmdMemoryManager)
    ↓ spawn (现有逻辑，无需修改)
qmd.exe (MCP Client 模式)
    ↓ stdio/HTTP 协议通信
qmd-mcp-server (单一共享进程)
    ↓
实际搜索引擎 + Embeddings 模型 + 数据库
```

## 架构优势

| 特性 | 说明 |
|------|------|
| ✅ **不动 OpenClaw** | 继续使用 `qmd` backend，无需修改源码 |
| ✅ **解决 OOM** | 单一 MCP Server 进程 = 单一模型实例加载 |
| ✅ **向后兼容** | CLI 模式依然可用（不启动 MCP Server 时） |
| ✅ **职责分离** | qmd-python 负责 QMD，OpenClaw 负责 Agent |
| ✅ **通用性强** | MCP 是标准协议，其他工具也可使用 |

## 工作流程

### 1. 用户启动 MCP Server（首次使用）

```bash
# 默认配置
qmd-mcp-server

# 自定义端口
qmd-mcp-server --port 8080 --log-level debug

# 后台运行
qmd-mcp-server --daemon
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

### Phase 1: MCP Server (qmd-python)

| 步骤 | 文件 | 说明 |
|------|------|------|
| 1.1 | `qmd/mcp/server.py` | MCP Server 主逻辑 |
| 1.2 | `qmd/mcp/tools.py` | MCP Tools 定义 |
| 1.3 | `qmd/mcp/transport.py` | Stdio/HTTP transport |
| 1.4 | `qmd/commands/mcp_server.py` | CLI entry point |

**MCP Tools**：
- `qmd_search` - BM25 全文搜索
- `qmd_vsearch` - 向量搜索
- `qmd_query` - 混合搜索
- `qmd_get` / `qmd_multi_get` - 读取文档
- `qmd_status` - 状态查询
- `qmd_sync` / `qmd_embed` - 索引和嵌入

### Phase 2: MCP Client (qmd-python)

| 步骤 | 文件 | 说明 |
|------|------|------|
| 2.1 | `qmd/mcp/client.py` | MCP Client 实现 |
| 2.2 | `qmd/commands/search.py` | 添加 mcp_mode 检测 |
| 2.3 | `qmd/commands/vsearch.py` | 同上 |
| 2.4 | `qmd/commands/query.py` | 同上 |

### Phase 3: 配置与文档

| 步骤 | 内容 |
|------|------|
| 3.1 | `config/mcp-server.yml` | MCP Server 配置 |
| 3.2 | `README.md` | 如何启动 MCP Server |
| 3.3 | `docs/MCP_MODE.md` | 架构说明 |

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
