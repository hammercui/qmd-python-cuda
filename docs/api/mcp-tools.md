# QMD MCP Tools 规范

**版本**: 1.0.0
**协议**: Model Context Protocol (MCP) 2025-06-18
**Transport**: Stdio (stdio://)
**SDK**: mcp (Python) 或 @modelcontextprotocol/sdk (TypeScript)

---

## 概述

QMD MCP Server 提供 **6个 Tools**、**1个 Resource** 和 **1个 Prompt**，用于文档搜索和检索。

### 组成

| 类型 | 数量 | 说明 |
|------|------|------|
| **Tools** | 6个 | 搜索和检索工具 |
| **Resources** | 1个 | 文档访问接口 |
| **Prompts** | 1个 | 使用指南提示 |

### 启动方式

```bash
# 仅 MCP Transport (stdio)
qmd server --transport mcp

# 同时启动 MCP 和 HTTP
qmd server --transport both
```

---

## MCP Tools

### 快速索引

| Tool | 功能 | 延迟 | 显存 |
|------|------|------|------|
| **search** | BM25 全文搜索 | ~750ms | 0GB |
| **vsearch** | 向量语义搜索 | 15-30ms | 4GB |
| **query** | 混合搜索 | ~75ms | 4GB |
| **get** | 获取单个文档 | <10ms | 0GB |
| **multi_get** | 批量获取文档 | <50ms | 0GB |
| **status** | 索引状态 | <10ms | 0GB |

---

### 1. `search` - BM25 全文搜索

**描述**: 快速关键词搜索，使用 BM25 全文索引

#### 输入参数

```json
{
  "query": "string (required)",     // 搜索查询
  "limit": "number (optional, default: 10)",      // 最大结果数
  "minScore": "number (optional, default: 0)",    // 最小相关性分数 0-1
  "collection": "string (optional)"  // 集合名称过滤
}
```

#### 输出格式

```json
{
  "content": [
    {
      "type": "text",
      "text": "Found 3 results for \"query\":\n\n#abc123 85% path/to/file.md - Title\n#def456 72% another/file.md - Another Title"
    }
  ],
  "structuredContent": {
    "results": [
      {
        "docid": "#abc123",
        "file": "path/to/file.md",
        "title": "Title",
        "score": 0.85,
        "context": "meeting notes",
        "snippet": "1: First line of snippet\n2: Second line\n3: Matched content here"
      }
    ]
  }
}
```

#### 行为规范

- ✅ 使用 BM25 FTS 搜索
- ✅ 后过滤集合（collection 参数）
- ✅ 提取文本摘录（300 字符）
- ✅ 默认添加行号格式（`N: content`）
- ✅ 分数四舍五入到 2 位小数
- ✅ 空结果返回：`"No results found for \"query\""`

---

### 2. `vsearch` - 向量语义搜索

**描述**: 使用向量嵌入进行语义相似度搜索

#### 输入参数

```json
{
  "query": "string (required)",     // 自然语言查询
  "limit": "number (optional, default: 10)",      // 最大结果数
  "minScore": "number (optional, default: 0.3)",  // 最小相关性分数 0-1
  "collection": "string (optional)"  // 集合名称过滤
}
```

#### 输出格式

```json
{
  "content": [
    {
      "type": "text",
      "text": "Found 2 results for \"semantic query\"..."
    }
  ],
  "structuredContent": {
    "results": [/* 同上 */]
  }
}
```

#### 行为规范

- ✅ **向量索引检查**：不存在时返回 `isError: true`
- ✅ 查询扩展（可选高级功能）
- ✅ 多查询并行搜索
- ✅ 合并去重结果（取最高分数）
- ✅ 默认 minScore=0.3（高于 search 的 0）

#### 错误处理

向量索引不存在时：
```json
{
  "content": [{"type": "text", "text": "Vector index not found. Run 'qmd embed' first to create embeddings."}],
  "isError": true
}
```

---

### 3. `query` - 混合搜索（最高质量）

**描述**: 结合 BM25 + 向量 + 查询扩展 + LLM 重排序

#### 输入参数

```json
{
  "query": "string (required)",     // 自然语言查询
  "limit": "number (optional, default: 10)",      // 最大结果数
  "minScore": "number (optional, default: 0)",    // 最小相关性分数 0-1
  "collection": "string (optional)"  // 集合名称过滤
}
```

#### 输出格式

```json
{
  "content": [{"type": "text", "text": "..."}],
  "structuredContent": {
    "results": [/* 同上 */]
  }
}
```

#### 行为规范

- ✅ 查询扩展（使用 LLM 生成多个变体）
- ✅ 并行 FTS + 向量搜索
- ✅ Reciprocal Rank Fusion (RRF) 融合
  - 权重：前 2 个查询×2.0，后续×1.0
- ✅ LLM 重排（Top 30 候选）
- ✅ 加权混合分数：
  - Top 3: 75% RRF + 25% rerank
  - 4-10: 60% RRF + 40% rerank
  - 11+: 40% RRF + 60% rerank
- ✅ **降级策略**：无向量索引时仅使用 FTS

---

### 4. `get` - 获取单个文档

**描述**: 通过文件路径或 docid 检索完整文档内容

#### 输入参数

```json
{
  "file": "string (required)",     // 文件路径、docid (#abc123) 或带行号 (file.md:100)
  "fromLine": "number (optional)", // 起始行号（1-indexed）
  "maxLines": "number (optional)", // 最大行数
  "lineNumbers": "boolean (optional, default: false)"  // 添加行号
}
```

#### 特殊语法

- `file.md:120` → 从第 120 行开始（优先于 `fromLine` 参数）

#### 输出格式

```json
{
  "content": [
    {
      "type": "resource",
      "resource": {
        "uri": "qmd://path%20to%2Ffile.md",
        "name": "path to/file.md",
        "title": "Document Title",
        "mimeType": "text/markdown",
        "text": "<!-- Context: meeting notes -->\n\n1: Line 1\n2: Line 2\n..."
      }
    }
  ]
}
```

#### 错误处理

文档未找到时：
```json
{
  "content": [
    {
      "type": "text",
      "text": "Document not found: unknown.md\n\nDid you mean one of these?\n  - known/similar.md\n  - another/path.md"
    }
  ],
  "isError": true
}
```

#### 行为规范

- ✅ 支持 `file.md:120` 语法
- ✅ 未找到时建议相似文件（Levenshtein 距离）
- ✅ 行号格式：`N: content`（从 fromLine 或 1 开始）
- ✅ 上下文注释：`<!-- Context: {description} -->`
- ✅ URI 编码路径（但保留斜杠）

---

### 5. `multi_get` - 批量获取文档

**描述**: 通过 glob 模式或逗号分隔列表检索多个文档

#### 输入参数

```json
{
  "pattern": "string (required)",  // glob模式或逗号分隔列表
  "maxLines": "number (optional)", // 每文件最大行数
  "maxBytes": "number (optional, default: 10240)",  // 跳过大于此值的文件（字节）
  "lineNumbers": "boolean (optional, default: false)"  // 添加行号
}
```

#### 参数说明

- `pattern`: glob 模式或逗号分隔列表
  - Glob 模式：`"journals/2025-05*.md"`
  - 逗号分隔：`"file1.md, file2.md, file3.md"`
- `maxBytes`: 跳过大于此值的文件（字节，默认 10240=10KB）
- `maxLines`: 每文件最大行数
- `lineNumbers`: 是否添加行号

#### 输出格式

```json
{
  "content": [
    {
      "type": "resource",
      "resource": {
        "uri": "qmd://file1.md",
        "name": "file1.md",
        "title": "...",
        "mimeType": "text/markdown",
        "text": "1: Content..."
      }
    },
    {
      "type": "text",
      "text": "[SKIPPED: file2.md - File too large (15KB). Use 'qmd get' with file=\"file2.md\" to retrieve.]"
    }
  ]
}
```

#### 行为规范

- ✅ 超大文件跳过（不读取内容）
- ✅ 跳过的文件返回 `type: "text"` 通知
- ✅ 错误和跳过信息在 content 数组开头
- ✅ 默认 maxBytes=10240（10KB）
- ✅ 无匹配文件：`isError: true`

#### 截断格式

超过 maxLines 时添加：`\n\n[... truncated {N} more lines]`

---

### 6. `status` - 索引状态

**描述**: 显示 QMD 索引的状态、集合和健康信息

#### 输入参数

```json
{}
```

#### 输出格式

```json
{
  "content": [
    {
      "type": "text",
      "text": "QMD Index Status:\n  Total documents: 1234\n  Needs embedding: 56\n  Vector index: yes\n  Collections: 2\n    - /path/to/docs (1000 docs)\n    - /another/path (234 docs)"
    }
  ],
  "structuredContent": {
    "totalDocuments": 1234,
    "needsEmbedding": 56,
    "hasVectorIndex": true,
    "collections": [
      {
        "name": "my-docs",
        "path": "/path/to/docs",
        "pattern": "**/*.md",
        "documents": 1000,
        "lastUpdated": "2025-06-18T12:34:56.789Z"
      }
    ]
  }
}
```

#### 行为规范

- ✅ 格式化可读文本摘要
- ✅ 包含结构化数据供程序使用
- ✅ lastUpdated 格式：ISO 8601 日期字符串

---

## MCP Resources

### `qmd://{+path}` - 文档访问

**URI 模板**: `qmd://{+path}`

**描述**: 通过路径只读访问文档

**MIME 类型**: `text/markdown`

#### Resource 配置

```json
{
  "title": "QMD Document",
  "description": "A markdown document from your QMD knowledge base. Use search tools to discover documents.",
  "mimeType": "text/markdown"
}
```

#### 重要特性

**`list: undefined`** - **不提供资源列表**（通过搜索工具发现）

#### 路径解析

**格式**: `{collection}/{relative-path}`

**示例**:
- `notes/meeting.md` → collection=`notes`, path=`meeting.md`
- `docs/2025/plan.md` → collection=`docs`, path=`2025/plan.md`

#### URI 编码规则

**函数**: `encodeQmdPath(path)`

```typescript
function encodeQmdPath(path: string): string {
  return path.split('/').map(segment => encodeURIComponent(segment)).join('/');
}
```

**规则**: 每个路径段单独编码，保留 `/` 分隔符

**示例**:
- `notes/2025/ meeting.md` → `qmd://notes%2F2025%2F%20meeting.md`
- `docs/File with spaces.md` → `qmd://docs%2FFile%20with%20spaces.md`

#### 行为规范

- ✅ URL 解码路径（MCP 客户端发送编码后的 URI）
- ✅ 精确匹配优先
- ✅ 后缀匹配回退（`LIKE %{path}`）
- ✅ 添加行号（默认）
- ✅ 上下文注释（`<!-- Context: ... -->`）

---

## MCP Prompts

### `query` - 查询指南

**名称**: `query`

**描述**: 如何有效使用 QMD 搜索知识库

**返回**: 单条 user 角色消息，包含 Markdown 格式使用指南

#### 内容结构

```markdown
# QMD - Quick Markdown Search

QMD is your on-device search engine for markdown knowledge bases. Use it to find information across your notes, documents, and meeting transcripts.

## Available Tools

### 1. search (Fast keyword search)
Best for: Finding documents with specific keywords or phrases.
- Uses BM25 full-text search
- Fast, no LLM required
- Good for exact matches
- Use `collection` parameter to filter to a specific collection

### 2. vsearch (Semantic search)
Best for: Finding conceptually related content even without exact keyword matches.
- Uses vector embeddings
- Understands meaning and context
- Good for "how do I..." or conceptual queries
- Use `collection` parameter to filter to a specific collection

### 3. query (Hybrid search - highest quality)
Best for: Important searches where you want the best results.
- Combines keyword + semantic search
- Expands your query with variations
- Re-ranks results with LLM
- Slower but most accurate
- Use `collection` parameter to filter to a specific collection

### 4. get (Retrieve document)
Best for: Getting the full content of a single document you found.
- Use the file path from search results
- Supports line ranges: `file.md:100` or fromLine/maxLines parameters
- Suggests similar files if not found

### 5. multi_get (Retrieve multiple documents)
Best for: Getting content from multiple files at once.
- Use glob patterns: `journals/2025-05*.md`
- Or comma-separated: `file1.md, file2.md`
- Skips files over maxBytes (default 10KB) - use get for large files

### 6. status (Index info)
Shows collection info, document counts, and embedding status.

## Resources

You can also access documents directly via the `qmd://` URI scheme:
- List all documents: `resources/list`
- Read a document: `resources/read` with uri `qmd://path/to/file.md`

## Search Strategy

1. **Start with search** for quick keyword lookups
2. **Use vsearch** when keywords aren't working or for conceptual queries
3. **Use query** for important searches or when you need high confidence
4. **Use get** to retrieve a single full document
5. **Use multi_get** to batch retrieve multiple related files

## Tips

- Use `minScore: 0.5` to filter low-relevance results
- Use `collection: "notes"` to search only in a specific collection
- Check the "Context" field - it describes what kind of content the file contains
- File paths are relative to their collection (e.g., `pages/meeting.md`)
- For glob patterns, match on display_path (e.g., `journals/2025-*.md`)
```

---

## 数据结构

### SearchResultItem

```typescript
type SearchResultItem = {
  docid: string;           // 短 ID (#abc123)
  file: string;            // 显示路径
  title: string;           // 文档标题
  score: number;           // 相关性分数 0-1
  context: string | null;  // 上下文描述
  snippet: string;         // 带行号的摘录
};
```

### StatusResult

```typescript
type StatusResult = {
  totalDocuments: number;
  needsEmbedding: number;
  hasVectorIndex: boolean;
  collections: {
    name: string;
    path: string;
    pattern: string;
    documents: number;
    lastUpdated: string;  // ISO date string
  }[];
};
```

---

## 相关文档

- [HTTP 端点规范](http-endpoints.md) - REST API 接口
- [兼容性分析](compatibility.md) - 与原版 QMD 的兼容性
- [实现指南](implementation-guide.md) - 实现细节和测试用例

---

**最后更新**: 2026-02-17
**维护者**: QMD-Python Team
