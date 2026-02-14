# QMD MCP Server 兼容性分析

## 概述

本文档分析原始 QMD (TypeScript/Bun) 的 MCP Server 实现，并定义 qmd-python 的 MCP Server 需要保持兼容的接口规范。

---

## 原始 QMD MCP Server 分析

### 文件位置
- **实现**: `D:\MoneyProjects\qmd\src\mcp.ts`
- **测试**: `D:\MoneyProjects\qmd\src\mcp.test.ts`
- **文档**: `D:\MoneyProjects\qmd\skills\qmd\references\mcp-setup.md`

### 启动方式

```bash
qmd mcp
```

**Transport**: Stdio (通过 `@modelcontextprotocol/sdk/server/stdio.js`)

**MCP SDK**: `@modelcontextprotocol/sdk/server/mcp.js`

**版本**: MCP spec 2025-06-18

---

## MCP Tools 接口规范

### Tool 1: `search` (BM25 全文搜索)

**描述**: Fast keyword-based full-text search using BM25.

**输入参数** (Zod Schema):
```typescript
{
  query: string;           // Required: 搜索查询
  limit?: number;          // Optional: 结果数量，默认 10
  minScore?: number;       // Optional: 最小相关性 0-1，默认 0
  collection?: string;     // Optional: 按集合名称过滤
}
```

**输出结构**:
```typescript
{
  content: [{ type: "text", text: string }];  // 人类可读摘要
  structuredContent: {
    results: Array<{
      docid: string;      // 短 ID (#abc123)
      file: string;       // 显示路径
      title: string;      // 文档标题
      score: number;      // 相关性 0-1
      context: string | null;  // 上下文描述
      snippet: string;    // 带行号的摘录
    }>;
  };
}
```

**行为**:
- 使用 BM25 FTS 搜索
- 后处理过滤集合
- 提取文本摘录 (300 chars)
- 添加行号到摘录

---

### Tool 2: `vsearch` (向量语义搜索)

**描述**: Semantic similarity search using vector embeddings.

**输入参数**:
```typescript
{
  query: string;           // Required: 自然语言查询
  limit?: number;          // Optional: 结果数量，默认 10
  minScore?: number;       // Optional: 最小相关性 0-1，默认 0.3
  collection?: string;     // Optional: 按集合名称过滤
}
```

**输出结构**:
```typescript
{
  content: [{ type: "text", text: string }];
  structuredContent: {
    results: Array<{ /* 同上 */ }>;
  };
}
```

**特殊行为**:
- 检查向量表是否存在 → 不存在返回错误
- 使用 LLM 扩展查询 (query expansion)
- 多查询并行搜索
- 合并去重结果

---

### Tool 3: `query` (混合搜索 + 重排)

**描述**: Highest quality combining BM25 + vector + LLM reranking.

**输入参数**:
```typescript
{
  query: string;           // Required: 自然语言查询
  limit?: number;          // Optional: 结果数量，默认 10
  minScore?: number;       // Optional: 最小相关性 0-1，默认 0
  collection?: string;     // Optional: 按集合名称过滤
}
```

**输出结构**:
```typescript
{
  content: [{ type: "text", text: string }];
  structuredContent: {
    results: Array<{ /* 同上 */ }>;
  };
}
```

**特殊行为**:
- 查询扩展
- 并行 FTS + 向量搜索
- Reciprocal Rank Fusion (RRF)
- LLM 重排 (Top 30 candidates)
- 加权混合分数 (75% RRF + 25% rerank for Top 3)

---

### Tool 4: `get` (获取单个文档)

**描述**: Retrieve the full content of a document by its file path or docid.

**输入参数**:
```typescript
{
  file: string;            // Required: 文件路径、docid (#abc123) 或带行号 (file.md:100)
  fromLine?: number;       // Optional: 起始行号 (1-indexed)
  maxLines?: number;       // Optional: 最大行数
  lineNumbers?: boolean;   // Optional: 添加行号，默认 false
}
```

**输出结构**:
```typescript
{
  content: [{
    type: "resource";
    resource: {
      uri: string;         // qmd://encoded/path
      name: string;        // 显示路径
      title?: string;      // 文档标题
      mimeType: string;    // "text/markdown"
      text: string;        // 文档内容
    };
  }];
}
```

**特殊行为**:
- 支持 `file.md:120` 语法（优先于 `fromLine`）
- 未找到时建议相似文件
- 行号格式: `N: content`
- 前置上下文注释: `<!-- Context: ... -->`

---

### Tool 5: `multi_get` (批量获取文档)

**描述**: Retrieve multiple documents by glob pattern or comma-separated list.

**输入参数**:
```typescript
{
  pattern: string;         // Required: Glob 模式或逗号分隔列表
  maxLines?: number;       // Optional: 每文件最大行数
  maxBytes?: number;       // Optional: 跳过大于此值的文件，默认 10240 (10KB)
  lineNumbers?: boolean;   // Optional: 添加行号，默认 false
}
```

**输出结构**:
```typescript
{
  content: Array<
    | { type: "text"; text: string }  // 错误消息或跳过通知
    | { type: "resource"; resource: { /* 同上 */ } }
  >;
}
```

**特殊行为**:
- 超大文件跳过（不读取）
- 跳过的文件返回 text 类型的通知
- 截断消息: `[... truncated N more lines]`

---

### Tool 6: `status` (索引状态)

**描述**: Show the status of the QMD index.

**输入参数**: `{}`

**输出结构**:
```typescript
{
  content: [{ type: "text", text: string }];  // 人类可读摘要
  structuredContent: {
    totalDocuments: number;
    needsEmbedding: number;
    hasVectorIndex: boolean;
    collections: Array<{
      name: string;
      path: string;
      pattern: string;
      documents: number;
      lastUpdated: string;  // ISO date string
    }>;
  };
}
```

---

## MCP Resources 接口规范

### Resource: `qmd://{+path}` (文档访问)

**URI 模板**: `qmd://{+path}`

**描述**: Read-only access to documents by path.

**MIME Type**: `text/markdown`

**行为**:
- `path` 解析: `{collection}/{relative-path}`
- URL 解码 (MCP clients 发送编码后的 URI)
- 后缀匹配回退 (精确匹配失败时)
- 行号格式
- 上下文注释

**注意**: `list: undefined` - 不提供资源列表（通过搜索工具发现）

---

## MCP Prompts 接口规范

### Prompt: `query` (查询指南)

**名称**: `query`

**描述**: How to effectively search your knowledge base with QMD

**返回**: 单条 user 角色的消息，包含 Markdown 格式的使用指南

**内容包含**:
- 6 个工具的描述
- 搜索策略建议
- 参数说明
- 使用技巧

---

## 兼容性检查清单

### Phase 1: 核心 Tools (P0 - 必须实现)

- [ ] **Tool: `search`**
  - [ ] 参数: `query`, `limit`, `minScore`, `collection`
  - [ ] 输出: `content.text` + `structuredContent.results`
  - [ ] 结果字段: `docid`, `file`, `title`, `score`, `context`, `snippet`
  - [ ] 摘录带行号
  - [ ] 默认值: `limit=10`, `minScore=0`

- [ ] **Tool: `vsearch`**
  - [ ] 参数: `query`, `limit`, `minScore`, `collection`
  - [ ] 检查向量索引存在性 → 不存在返回 `isError: true`
  - [ ] 查询扩展 (可选高级功能)
  - [ ] 默认值: `limit=10`, `minScore=0.3`

- [ ] **Tool: `query`**
  - [ ] 参数: `query`, `limit`, `minScore`, `collection`
  - [ ] 混合 FTS + 向量
  - [ ] RRF 融合
  - [ ] LLM 重排 (可选高级功能，可简化为加权融合)

- [ ] **Tool: `get`**
  - [ ] 参数: `file`, `fromLine`, `maxLines`, `lineNumbers`
  - [ ] 支持 `file.md:120` 语法
  - [ ] 相似文件建议 (可选)
  - [ ] 输出: `content.resource` with `qmd://` URI
  - [ ] 行号格式: `N: content`
  - [ ] 上下文注释

- [ ] **Tool: `multi_get`**
  - [ ] 参数: `pattern`, `maxLines`, `maxBytes`, `lineNumbers`
  - [ ] Glob 模式或逗号分隔列表
  - [ ] 超大文件跳过机制
  - [ ] 默认值: `maxBytes=10240`

- [ ] **Tool: `status`**
  - [ ] 无参数
  - [ ] 输出: `content.text` + `structuredContent`
  - [ ] 字段: `totalDocuments`, `needsEmbedding`, `hasVectorIndex`, `collections`

### Phase 2: Resources (P1 - 推荐实现)

- [ ] **Resource: `qmd://{+path}`**
  - [ ] `list: undefined`
  - [ ] MIME type: `text/markdown`
  - [ ] URI 解码
  - [ ] 路径解析: `{collection}/{relative-path}`
  - [ ] 后缀匹配回退
  - [ ] 行号 + 上下文注释

### Phase 3: Prompts (P2 - 可选)

- [ ] **Prompt: `query`**
  - [ ] Markdown 使用指南
  - [ ] 6 个工具说明
  - [ ] 搜索策略

---

## 实现注意事项

### 1. Transport 协议

**原始 QMD**: Stdio only (`StdioServerTransport`)

**qmd-python 推荐实现**:
- Phase 1: Stdio (完全兼容)
- Phase 2: 可选支持 SSE/WebSocket (扩展功能)

### 2. MCP SDK 版本

**原始 QMD**: `@modelcontextprotocol/sdk` (TypeScript)

**qmd-python**: 可以使用:
- [mcp](https://github.com/jlowin/mcp) (Python MCP SDK)
- 或自行实现 MCP 协议 (基于 JSON-RPC 2.0 over stdio)

### 3. 数据库连接

**原始 QMD**: 启动时打开，进程退出时关闭

**qmd-python 推荐**: 同样策略（保持连接，避免重复打开）

### 4. 行号格式

**规范**: `{lineNum}: {content}`

**示例**:
```
1: First line
2: Second line
100: Hundredth line
```

### 5. DocID 格式

**规范**: `#{hash}` (短 hash 前缀)

**示例**: `#abc123`

### 6. URI 编码

**编码**: 每个路径段单独编码，保留 `/` 分隔符

**函数**:
```typescript
function encodeQmdPath(path: string): string {
  return path.split('/').map(segment => encodeURIComponent(segment)).join('/');
}
```

**示例**: `notes/2025/ meeting.md` → `notes%2F2025%2F%20meeting.md`

---

## 测试策略

### 单元测试

1. **Tool 参数验证**
   - 必需参数缺失
   - 参数类型错误
   - 默认值正确

2. **输出格式验证**
   - JSON Schema 匹配
   - `structuredContent` 存在
   - 字段完整性

3. **边界情况**
   - 空结果
   - 文档不存在
   - 向量索引缺失

### 集成测试

1. **与原始 QMD 对比**
   - 相同输入 → 相似输出
   - 差异容忍度: 分数精度、排序微调

2. **Claude Desktop 集成**
   - 手动配置 MCP Server
   - 测试所有 Tools

---

## 参考资源

- **MCP 规范**: [Model Context Protocol](https://modelcontextprotocol.io/)
- **原始实现**: `D:\MoneyProjects\qmd\src\mcp.ts`
- **配置文档**: `D:\MoneyProjects\qmd\skills\qmd\references\mcp-setup.md`
