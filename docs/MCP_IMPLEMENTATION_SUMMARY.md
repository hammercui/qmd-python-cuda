# MCP Server 实现总结

## 文件关系

| 文件 | 说明 |
|------|------|
| `MCP_SERVER_PROPOSAL.md` | 方案概述：如何通过 MCP Server 解决 CUDA OOM 问题 |
| `MCP_COMPATIBILITY_ANALYSIS.md` | 接口规范：原始 QMD MCP Server 的详细分析 |
| `ARCHITECTURE_ANALYSIS.md` | 架构分析：OpenClaw 与 QMD 的交互方式 |

---

## 核心发现

### 1. 原始 QMD MCP Server 架构

```
原始 QMD (TypeScript/Bun)
├── src/mcp.ts (627 lines)
├── 使用 @modelcontextprotocol/sdk
├── StdioTransport (STDIO)
└── 暴露 6 Tools + 1 Resource + 1 Prompt
```

### 2. qmd-python 需实现的 MVP

| 阶段 | 功能 | 优先级 |
|------|------|----------|
| **MCP Server** | Stdio transport, 核心 Tools | P0 |
| **Tools** | search, vsearch, query, get, multi_get, status | P0 |
| **Resource** | `qmd://{path}` 文档访问 | P1 |
| **Prompt** | query guide (使用指南） | P2 |

### 3. 与原始 QMD 的关键差异

| 方面 | 原始 QMD | qmd-python (Python) |
|------|----------|------------------------|
| **实现语言** | TypeScript + Bun | Python |
| **MCP SDK** | @modelcontextprotocol/sdk | mcp (Python SDK) |
| **Transport** | Stdio only | Stdio + 可选 SSE/WebSocket |
| **数据库** | SQLite (Bun.sql) | SQLite (python-sqlite3) |
| **底层引擎** | 完全相同 | BM25 + Vector + Hybrid |

---

## 实现策略

### Phase 1: 核心 MCP Server (P0)

**目标**: 最小可用实现，通过所有 Tools 基本测试

**实现内容**:
1. MCP Server 基架 (`qmd/mcp/server.py`)
2. 核心 Tools 实现 (`qmd/mcp/tools.py`)
   - ✅ `search` - BM25 搜索
   - ✅ `vsearch` - 向量搜索
   - ✅ `query` - 混合搜索
   - ✅ `get` - 获取文档
   - ✅ `multi_get` - 批量获取
   - ✅ `status` - 状态查询
3. Stdio Transport (`qmd/mcp/transport.py`)
4. CLI 入口 (`qmd/commands/mcp_server.py`)

**验收标准**:
- [ ] `qmd-mcp-server` 启动成功
- [ ] Claude Desktop 能连接
- [ ] 所有 6 Tools 可用
- [ ] `call_tool("qmd_search", ...)` 返回有效结果

### Phase 2: 资源与 Prompt (P1)

**目标**: 完全兼容原始 QMD 的 Resource 和 Prompt

**实现内容**:
1. `qmd://` URI Resource (`qmd/mcp/resources.py`)
2. Query Guide Prompt (`qmd/mcp/prompts.py`)

**验收标准**:
- [ ] `resources/read` with `uri: qmd://notes/meeting.md`
- [ ] `prompts/list` 返回 `query` prompt

### Phase 3: 优化与扩展 (P2)

**目标**: 超越原始 QMD 的功能

**实现内容**:
1. SSE Transport (`qmd/mcp/transports/sse.py`)
2. WebSocket Transport (`qmd/mcp/transports/ws.py`)
3. 健康改进（错误处理、日志）

---

## 兼容性保证

### 必须保持 (MUST)

1. **Tool 名称**: 完全相同 (`search`, `vsearch`, `query`, `get`, `multi_get`, `status`)
2. **参数 Schema**: 相同名称和类型
3. **输出结构**: `content` + `structuredContent` 双响应
4. **URI 格式**: `qmd://{encoded_path}`
5. **DocID 格式**: `#{hash}`
6. **行号格式**: `{line}: {content}`

### 可以改进 (MAY)

1. **Transport**: 支持 SSE/WebSocket（原始 QMD 只有 stdio）
2. **错误处理**: 更详细的错误信息
3. **配置灵活性**: YAML 配置 vs JSON

---

## 工作流程

### 用户视角

```bash
# 1. 首次使用：启动 MCP Server
qmd-mcp-server --port 8080

# 2. OpenClaw 无需修改配置
# qmd.exe 会自动检测 MCP Server

# 3. 搜索工作（透明）
qmd search "my query"  # 内部转发到 MCP Server
```

### 开发视角

```python
# 1. 实现 MCP Server
# qmd/mcp/server.py
async def start_mcp_server():
    server = McpServer("qmd", "1.0.0")
    server.register_tool("search", search_handler)
    server.register_tool("vsearch", vsearch_handler)
    # ...

# 2. 确保兼容性
# qmd/mcp/tools.py
async def search_handler(query: str, limit: int = 10):
    results = store.search_fts(query, limit)
    return {
        "content": [{"type": "text", "text": format_summary(results)}],
        "structuredContent": {"results": results}
    }

# 3. CLI 入口
# qmd/commands/mcp_server.py
@click.command()
def mcp_server():
    asyncio.run(start_mcp_server())
```

---

## 下一步

**推荐**：开始 Phase 1 实现核心 MCP Server

**需要做的决策**：
1. Python MCP SDK 选择：[mcp](https://github.com/jlowin/mcp) vs 自行实现
2. 配置管理：YAML 文件 vs 命令行参数
3. 日志级别：DEBUG/INFO/WARN/ERROR

**实现检查清单**：见 `MCP_COMPATIBILITY_ANALYSIS.md` 的 Phase 1
