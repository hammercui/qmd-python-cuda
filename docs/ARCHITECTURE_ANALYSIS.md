# OpenClaw 与 QMD 交互模式分析报告

**日期**: 2026-02-14
**项目**: qmd-python (Python 重写版)

---

## 一、OpenClaw 与 QMD 交互的三种模式

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    OpenClaw 与 QMD 交互架构                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        OpenClaw Gateway                             │   │
│  │                                                                     │   │
│  │   ┌──────────────────────┐  ┌──────────────────────┐            │   │
│  │   │   Memory Backend     │  │   MCP Client         │            │   │
│  │   │   (CLI Spawn)        │  │   (Claude Desktop)   │            │   │
│  │   └──────────┬───────────┘  └──────────┬───────────┘            │   │
│  │              │                         │                          │   │
│  │              │ spawn()                │ stdio                   │   │
│  │              ▼                         ▼                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                    ┌──────────────────┼──────────────────┐                │
│                    ▼                  ▼                  ▼                │
│          ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│          │ qmd search    │  │ qmd vsearch   │  │ qmd query     │       │
│          │ qmd collection │  │ qmd embed     │  │ qmd mcp       │       │
│          └───────────────┘  └───────────────┘  └───────────────┘       │
│                                                                             │
│  模式 1: CLI 子进程模式 (当前 OpenClaw 使用)                               │
│  模式 2: MCP Stdio 模式 (Claude Desktop 使用)                             │
│  模式 3: HTTP Server 模式 (我们新增，解决显存问题)                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 模式 1: CLI 子进程模式 (当前使用)

**调用链**:
```
QmdMemoryManager.runQmd()
  → spawn("qmd", ["search"|"vsearch"|"query", ...])
  → 每次调用创建新进程
  → 每个进程加载独立模型 → 显存爆炸 ❌
```

**代码位置**: `openclaw/src/memory/qmd-manager.ts:553-606`

```typescript
private async runQmd(args: string[], opts?: { timeoutMs?: number }) {
  const child = spawn(command, commandArgs, { env: this.env, cwd: this.workspaceDir });
  // ... 处理 stdout/stderr
}
```

**命令示例**:
```bash
qmd search "query" --limit 6
qmd vsearch "query" --collection memory
qmd query "query" --limit 6
```

---

### 模式 2: MCP Stdio 模式

**调用链**:
```
Claude Desktop / AI 助手
  → MCP Client (通过 stdio)
  → qmd mcp 命令
  → McpServer + StdioServerTransport
  → 返回搜索结果
```

**命令**: `qmd mcp`

**代码位置**: `qmd/src/mcp.ts` + `qmd/src/qmd.ts:2655-2658`

```typescript
case "mcp": {
  const { startMcpServer } = await import("./mcp.js");
  await startMcpServer();
  break;
}
```

**特点**:
- 使用 `@modelcontextprotocol/sdk` 库
- 通过标准输入输出通信
- 暴露工具: `search`, `vsearch`, `query`, `get`, `multi_get`, `status`
- 暴露资源: `qmd://{path}`

---

### 模式 3: HTTP Server 模式 (我们新增)

**目的**: 解决显存问题

```
qmd server  → 启动 HTTP Server (单例模型 + 队列)
qmd vsearch --mode server  → HTTP 客户端调用
```

**当前实现**: `qmd-python` 的 Server 模式

---

## 二、OpenClaw 当前使用方式

### 2.1 QmdMemoryManager

**文件**: `openclaw/src/memory/qmd-manager.ts`

```typescript
// 每次搜索都 spawn 一个新进程
const result = await this.runQmd(args, { timeoutMs: this.qmd.limits.timeoutMs });

// 搜索命令配置
const qmdSearchCommand = this.qmd.searchMode; // "search" | "vsearch" | "query"
const args = this.buildSearchArgs(qmdSearchCommand, trimmed, limit);
```

### 2.2 配置选项

```typescript
// openclaw/src/config/schema.hints.ts
interface QmdConfig {
  command: string;           // qmd 二进制路径
  searchMode: "search" | "vsearch" | "query";
  update: {
    intervalMs: number;
    onBoot: boolean;
    commandTimeoutMs: number;
  };
  limits: {
    maxResults: number;
    maxSnippetChars: number;
    timeoutMs: number;
  };
}
```

---

## 三、qmd-python 需要做的兼容性适配

### 3.1 必须支持 (CLI 模式)

| 命令 | 参数 | 说明 |
|------|------|------|
| `qmd search` | `query [--limit N] [--collection X]` | BM25 搜索 |
| `qmd vsearch` | `query [--limit N] [--collection X]` | 向量搜索 |
| `qmd query` | `query [--limit N] [--collection X]` | 混合搜索 |
| `qmd collection list` | `[--json]` | 列出集合 |
| `qmd collection add` | `PATH --name NAME [--glob PATTERN]` | 添加集合 |
| `qmd update` | - | 更新索引 |
| `qmd embed` | `[--collection X]` | 生成向量 |
| `qmd status` | - | 索引状态 |
| `qmd get` | `PATH [--from N] [--lines N]` | 获取文档 |
| `qmd ls` | `[PATH]` | 列出文件 |

### 3.2 必须支持 (MCP 模式)

```bash
qmd mcp  # 启动 MCP Server (Stdio 传输)
```

**MCP 工具**:
- `search` - BM25 搜索
- `vsearch` - 向量搜索
- `query` - 混合搜索
- `get` - 获取文档
- `multi_get` - 批量获取
- `status` - 索引状态

### 3.3 新增支持 (HTTP Server 模式)

```bash
qmd server  # 启动 HTTP Server
qmd vsearch --mode server  # 使用 server 模式
```

---

## 四、实施计划

### 4.1 优先级 P0 - 必须完成

| 任务 | 说明 |
|------|------|
| CLI 命令兼容 | 确保所有 OpenClaw 使用的命令格式兼容 |
| `--mode` 选项 | 支持 `standalone/server/auto` 模式切换 |
| JSON 输出 | 部分命令需要 `--json` 输出格式 |

### 4.2 优先级 P1 - 应该完成

| 任务 | 说明 |
|------|------|
| `qmd mcp` 命令 | 实现 MCP Server (Stdio 传输) |
| MCP 工具注册 | search, vsearch, query, get, multi_get, status |

### 4.3 优先级 P2 - 优化

| 任务 | 说明 |
|------|------|
| 文档完善 | 更新 MCP setup 文档 |
| OpenClaw 集成 | 修改 QmdMemoryManager 使用 HTTP 模式 |

---

## 五、总结

| 模式 | 协议 | 用途 | 显存问题 |
|------|------|------|----------|
| CLI (spawn) | 子进程 | OpenClaw 当前使用 | ❌ 存在 |
| MCP (stdio) | Stdio | Claude Desktop | ❌ 存在 |
| HTTP Server | HTTP | 我们的方案 | ✅ 解决 |

**qmd-python 需要同时支持三种模式**:
1. **CLI 模式** - 向后兼容 OpenClaw
2. **MCP 模式** - 服务 AI 助手集成
3. **HTTP Server 模式** - 解决显存问题

---

## 六、原始 QMD MCP Server 设计分析

### 6.1 定位

原始 QMD (`D:\MoneyProjects\qmd`) 的 MCP Server 是**让 AI 助手调用 QMD 搜索的工具**：

```
┌─────────────────────────────────────────────────────────────────┐
│  原始 QMD MCP Server                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  目的：将 QMD 作为 AI 助手的"记忆工具"                           │
│  协议：Model Context Protocol (MCP)                            │
│  传输：Stdio (标准输入输出)                                     │
│                                                                 │
│  暴露的工具：                                                   │
│  ├── search (BM25 全文搜索)                                    │
│  ├── vsearch (向量语义搜索)                                    │
│  ├── query (混合搜索 + 重排序)                                 │
│  ├── get (获取单个文档)                                        │
│  ├── multi_get (批量获取文档)                                  │
│  └── status (索引状态)                                         │
│                                                                 │
│  暴露的资源：                                                   │
│  └── qmd://{path} - 文档读取                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 核心代码结构

**文件**: `src/mcp.ts`

```typescript
// 使用 @modelcontextprotocol/sdk
import { McpServer, ResourceTemplate } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

// 注册工具
server.registerTool("search", { ... }, async ({ query, limit, collection }) => {
  const results = store.searchFTS(query, limit);
  return { content: [...], structuredContent: {...} };
});
```

### 6.3 与我们实现的区别

| 维度 | 原始 QMD MCP | 我们的实现 |
|------|--------------|-----------|
| **目的** | AI 助手记忆搜索 | 解决显存问题 |
| **协议** | MCP (Model Context Protocol) | HTTP REST API |
| **传输** | Stdio | TCP/HTTP |
| **模型** | 内嵌在进程内 | 独立 Server 进程 |
| **场景** | Claude Code / Claude Desktop 集成 | 多进程共享模型 |

---

## 七、OpenClaw 如何使用 QMD

### 7.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     OpenClaw 架构                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│   │   Agent 1   │    │   Agent 2   │    │   Agent N   │        │
│   │  (main)     │    │  (ops)      │    │  (custom)  │        │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘        │
│          │                  │                  │               │
│          └──────────────────┼──────────────────┘               │
│                             │                                  │
│                    ┌────────▼────────┐                        │
│                    │  QmdMemoryManager │                        │
│                    │ (src/memory/)    │                        │
│                    └────────┬────────┘                        │
│                             │                                  │
│                    ┌────────▼────────┐                        │
│                    │  qmd CLI 进程   │                        │
│                    │ spawn 子进程    │                        │
│                    └────────┬────────┘                        │
│                             │                                  │
│              ┌──────────────┼──────────────┐                  │
│              │              │              │                  │
│       ┌──────▼──────┐ ┌────▼────┐ ┌──────▼──────┐         │
│       │ collection  │ │  index  │ │   embed     │         │
│       │ management  │ │  (SQLite)│ │  (ML Model) │         │
│       └─────────────┘ └─────────┘ └─────────────┘         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 QmdMemoryManager 关键实现

**文件**: `src/memory/qmd-manager.ts`

#### 核心特性：

1. **进程隔离**: 每个 Agent 有独立的 QMD 索引
   ```typescript
   this.agentStateDir = path.join(this.stateDir, "agents", agentId);
   this.qmdDir = path.join(this.agentStateDir, "qmd");
   this.xdgConfigHome = path.join(this.qmdDir, "xdg-config");
   this.xdgCacheHome = path.join(this.qmdDir, "xdg-cache");
   ```

2. **模型共享**: 通过符号链接共享模型
   ```typescript
   // QMD stores its ML models under $XDG_CACHE_HOME/qmd/models/.
   // Symlink the default models directory into our custom cache
   // so the index stays isolated while models are shared.
   await this.symlinkSharedModels();
   ```

3. **自动更新**: 定时索引更新
   ```typescript
   if (this.qmd.update.intervalMs > 0) {
     this.updateTimer = setInterval(() => {
       this.runUpdate("interval");
     }, this.qmd.update.intervalMs);
   }
   ```

4. **搜索模式**: 支持 search/vsearch/query
   ```typescript
   const qmdSearchCommand = this.qmd.searchMode; // "search" | "vsearch" | "query"
   const args = this.buildSearchArgs(qmdSearchCommand, trimmed, limit);
   ```

### 7.3 OpenClaw 配置选项

根据 `src/config/schema.hints.ts`，OpenClaw 支持的 QMD 配置：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `memory.backend` | 记忆后端 | "builtin" |
| `memory.qmd.command` | QMD 二进制路径 | "qmd" |
| `memory.qmd.paths` | 索引路径列表 | [] |
| `memory.qmd.sessions.enabled` | 会话索引 | false |
| `memory.qmd.update.interval` | 更新间隔 | - |
| `memory.qmd.update.onBoot` | 启动时更新 | true |
| `memory.qmd.limits.maxResults` | 最大结果数 | 6 |
| `memory.qmd.limits.maxSnippetChars` | 最大片段长度 | 700 |
| `memory.qmd.limits.timeoutMs` | 搜索超时 | 4000ms |
| `memory.qmd.searchMode` | 搜索命令 | "query" |

---

## 八、关键发现

### 8.1 原始 QMD 没有"显存问题"

原始 QMD 是 TypeScript/Bun 实现：
- 使用 `node-llama-cpp` 进行本地推理
- 没有设计成多进程共享模型
- MCP Server 是为了让 AI 助手调用 QMD，不是为了解决显存

### 8.2 我们设计的 MCP Server 是原创

```
┌─────────────────────────────────────────────────────────────────┐
│              我们的 MCP Server（原创设计）                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  解决的问题：                                                    │
│  - Python 多进程独立加载模型 → 显存爆炸                          │
│  - 4GB/6GB VRAM 用户无法使用向量搜索                            │
│                                                                 │
│  解决方案：                                                      │
│  - 单一 Server 进程 + 队列串行处理                              │
│  - asyncio.Lock 保证同一时刻只有一个请求处理模型                 │
│                                                                 │
│  使用方式：                                                      │
│  Terminal 1: qmd server  (启动 Server)                        │
│  Terminal 2: qmd vsearch --mode server "query"               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 8.3 OpenClaw 没有使用我们的设计

OpenClaw 使用的是**原始 QMD CLI**：
- 通过 `spawn()` 调用 `qmd search/vsearch/query`
- 每次调用创建新进程
- **存在同样的显存问题**（每个 Agent 独立加载模型）

---

## 九、结论

### 架构对比

| 项目 | 原始 QMD MCP | 我们的 Server | OpenClaw |
|------|--------------|--------------|----------|
| **协议** | MCP (Stdio) | HTTP REST | CLI 子进程 |
| **目的** | AI 记忆 | 显存优化 | AI 记忆 |
| **模型** | 进程内 | 独立进程 | 每次调用加载 |
| **显存问题** | 无 | ✅ 解决 | ❌ 存在 |

### 我们的设计的价值

我们的 MCP Server 设计是**原创的**，专门解决：
1. **Python 多进程显存爆炸问题**
2. **4GB/6GB VRAM 用户无法使用向量搜索**

### 未来可能的改进

如果要让 OpenClaw 也能受益于我们的设计，可以：

1. **OpenClaw 集成 HTTP Server**: 修改 `QmdMemoryManager`，让它调用 HTTP API 而不是 spawn 子进程
2. **添加 MCP Server**: 给我们的 Server 添加 MCP 协议支持，同时服务 AI 助手和解决显存问题
