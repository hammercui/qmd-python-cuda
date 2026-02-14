# QMD MCP Server 接口协议规范

**版本**: 1.0.0
**协议**: Model Context Protocol (MCP) 2025-06-18
**Transport**: Stdio (stdio://)
**SDK**: @modelcontextprotocol/sdk (TypeScript) → mcp (Python)

---

## 概述

QMD MCP Server提供6个工具、1个资源和1个提示，用于文档搜索和检索。

**统一架构**：单一QMD Server进程，通过多种传输协议对外服务
- **MCP Transport (stdio)**: 为Claude Desktop/OpenCode等AI Agent提供工具接口
- **HTTP Transport**: 为CLI命令、OpenClaw等提供REST API

### 启动方式

```bash
# 原始QMD (TypeScript) - MCP only
qmd mcp

# qmd-python - 同时支持MCP和HTTP
qmd server --transport both    # 推荐：同时启动两种传输
qmd server --transport mcp      # 仅MCP (stdio)
qmd server --transport http     # 仅HTTP (REST API)
```

### Server信息

```yaml
name: qmd
version: 1.0.0

# HTTP Transport
http:
  url: http://localhost:18765
  default_port: 18765
```

---

## HTTP Transport 接口规范

**版本**: 1.0.0
**协议**: HTTP/1.1
**Content-Type**: `application/json`
**端口**: 18765 (默认，可通过`--port`配置)

### 概述

HTTP Transport提供与MCP Tools功能对应的REST API端点，用于：
- CLI命令的server模式（`qmd search --mode server`）
- OpenClaw的HTTP客户端
- 其他需要程序化访问的场景

### 认证

**当前版本**: 无需认证（localhost only）
**未来版本**: 可选API Key或OAuth

### 错误处理

所有端点遵循统一的错误响应格式：

```json
{
  "detail": "Error message",
  "status_code": 400
}
```

**常见HTTP状态码**:
- `200 OK` - 请求成功
- `400 Bad Request` - 参数验证失败
- `404 Not Found` - 资源不存在（仅`/get`端点）
- `500 Internal Server Error` - 服务器内部错误
- `503 Service Unavailable` - 模型未加载或Server未就绪

---

## HTTP端点规范

### A. 搜索和检索指令（核心）

### 1. `POST /search` - BM25全文搜索

**对应MCP Tool**: `search`

**请求参数**:
```json
{
  "query": "string (required)",
  "limit": "number (optional, default: 10)",
  "min_score": "number (optional, default: 0.0)",
  "collection": "string (optional)"
}
```

**响应格式**:
```json
{
  "results": [
    {
      "docid": "#abc123",
      "file": "path/to/file.md",
      "title": "Document Title",
      "score": 0.85,
      "context": "meeting notes",
      "snippet": "1: First line of snippet\n2: Second line\n3: Matched content"
    }
  ],
  "content": "Found 3 results for \"query\"\n\n#abc123 85% path/to/file.md - Title\n\n#def456 72% another/file.md - Another Title"
}
```

**示例**:
```bash
# Request
curl -X POST http://localhost:18765/search \
  -H "Content-Type: application/json" \
  -d '{"query": "meeting notes", "limit": 5, "min_score": 0.5}'

# Response
{
  "results": [...],
  "content": "Found 2 results for \"meeting notes\"\n\n#abc123 85% notes/meeting.md - Meeting Notes..."
}
```

---

### 2. `POST /vsearch` - 向量语义搜索

**对应MCP Tool**: `vsearch`

**请求参数**:
```json
{
  "query": "string (required)",
  "limit": "number (optional, default: 10)",
  "min_score": "number (optional, default: 0.3)",
  "collection": "string (optional)"
}
```

**响应格式**:
```json
{
  "results": [
    {
      "docid": "#abc123",
      "file": "path/to/file.md",
      "title": "Document Title",
      "score": 0.92,
      "context": "project documentation",
      "snippet": "1: Content here\n2: More content"
    }
  ],
  "content": "Found 5 results for \"semantic query\"\n\n#abc123 92% ..."
}
```

**特殊行为**:
- ✅ 向量索引不存在时返回HTTP 503
  ```json
  {
    "detail": "Vector index not found. Run 'qmd embed' first to create embeddings.",
    "status_code": 503
  }
  ```

---

### 3. `POST /query` - 混合搜索（最高质量）

**对应MCP Tool**: `query`

**请求参数**:
```json
{
  "query": "string (required)",
  "limit": "number (optional, default: 10)",
  "min_score": "number (optional, default: 0.0)",
  "collection": "string (optional)"
}
```

**响应格式**:
```json
{
  "results": [
    {
      "docid": "#abc123",
      "file": "path/to/file.md",
      "title": "Document Title",
      "score": 0.95,
      "context": "meeting notes",
      "snippet": "1: First line\n2: Second line"
    }
  ],
  "content": "Found 3 results for \"hybrid query\"\n\n#abc123 95% ..."
}
```

**特殊行为**:
- ✅ 无向量索引时降级为FTS搜索（不报错）
- ✅ 查询扩展：使用LLM生成查询变体（可选高级功能）
- ✅ RRF融合：FTS和向量结果合并
- ✅ LLM重排：Top 30候选文档重新排序

---

### 4. `POST /get` - 获取单个文档

**对应MCP Tool**: `get`

**请求参数**:
```json
{
  "file": "string (required)",
  "from_line": "number (optional)",
  "max_lines": "number (optional)",
  "line_numbers": "boolean (optional, default: false)"
}
```

**参数说明**:
- `file`: 文档路径、docid (`#abc123`) 或带行号 (`file.md:100`)
- `from_line`: 起始行号（1-indexed）
- `max_lines`: 最大行数
- `line_numbers`: 是否添加行号

**响应格式**:
```json
{
  "document": {
    "uri": "qmd://path/to/file.md",
    "name": "path/to/file.md",
    "title": "Document Title",
    "mimeType": "text/markdown",
    "text": "1: First line\n2: Second line\n...\n"
  },
  "content": null
}
```

**错误处理**:
```json
// 文档未找到
{
  "detail": "Document not found: unknown.md\n\nDid you mean one of these?\n  - known/similar.md\n  - another/path.md",
  "status_code": 404
}
```

---

### 5. `POST /multi_get` - 批量获取文档

**对应MCP Tool**: `multi_get`

**请求参数**:
```json
{
  "pattern": "string (required)",
  "max_lines": "number (optional)",
  "max_bytes": "number (optional, default: 10240)",
  "line_numbers": "boolean (optional, default: false)"
}
```

**参数说明**:
- `pattern`: glob模式或逗号分隔列表
  - 示例：`"journals/2025-05*.md"`
  - 示例：`"file1.md, file2.md, file3.md"`
- `max_bytes`: 跳过大于此值的文件（字节，默认10240=10KB）
- `max_lines`: 每文件最大行数
- `line_numbers`: 是否添加行号

**响应格式**:
```json
{
  "results": [
    {
      "uri": "qmd://file1.md",
      "name": "file1.md",
      "title": "...",
      "mimeType": "text/markdown",
      "text": "1: Content..."
    },
    {
      "type": "text",
      "text": "[SKIPPED: bigfile.md - File too large (15KB). Use 'qmd get' with file=\"bigfile.md\" to retrieve.]"
    }
  ],
  "content": null
}
```

**截断格式**:
- 超过maxLines时添加：`\n\n[...truncated {N} more lines]`

---

### 6. `GET /status` - 索引状态

**对应MCP Tool**: `status`

**请求参数**: 无（GET请求）

**响应格式**:
```json
{
  "total_documents": 1234,
  "needs_embedding": 56,
  "has_vector_index": true,
  "collections": [
    {
      "name": "my-docs",
      "path": "/path/to/docs",
      "pattern": "**/*.md",
      "documents": 1000,
      "last_updated": "2025-06-18T12:34:56.789Z"
    }
  ],
  "content": "QMD Index Status:\n  Total documents: 1234\n  Needs embedding: 56\n  Vector index: yes\n  Collections: 2\n    - /path/to/docs (1000 docs)\n    - /another/path (234 docs)"
}
```

**示例**:
```bash
# Request
curl http://localhost:18765/status

# Response
{
  "total_documents": 1234,
  "needs_embedding": 56,
  "has_vector_index": true,
  "collections": [...],
  "content": "QMD Index Status:\n  Total documents: 1234..."
}
```

---

### 7. `POST /embed` - 批量生成嵌入

**用途**: 为多个文本生成向量嵌入（初始化或更新向量索引）

**请求参数**:
```json
{
  "texts": ["string (required)", ...]  // 文本列表（最多1000个）
}
```

**响应格式**:
```json
{
  "embeddings": [
    [0.1, 0.2, ..., 0.8]  // 384维向量（text1）
  ]
}
```

**错误处理**:
```json
// 空列表
{
  "detail": "Empty texts list",
  "status_code": 400
}

// 太多texts
{
  "detail": "Too many texts (1001 > 1000)",
  "status_code": 413
}

// 模型未加载
{
  "detail": "Model not loaded",
  "status_code": 503
}
```

**限制**:
- ✅ 最多1000个文本
- ✅ 串行处理（队列）
- ✅ 单例模型（4GB VRAM）

**示例**:
```bash
# Request
curl -X POST http://localhost:18765/embed \
  -H "Content-Type: application/json" \
  -d '{"texts": ["First text", "Second text"]}'

# Response
{
  "embeddings": [
    [0.123, 0.456, ..., 0.789],
    [0.234, 0.567, ..., 0.890]
  ]
}
```

---

### B. 管理指令（必需）

### 9. `POST /collections/add` - 添加文档集合

**对应CLI**: `qmd collection add [path] --name <name> --mask <pattern>`

**请求参数**:
```json
{
  "name": "string (required)",
  "path": "string (required)",
  "glob_pattern": "string (optional, default: \"**/*.md\")"
}
```

**响应格式**:
```json
{
  "status": "added",
  "name": "my-docs",
  "path": "/path/to/docs",
  "documents": 100,
  "content": "Added collection 'my-docs' with 100 documents"
}
```

**行为**:
- ✅ 添加到配置文件
- ✅ 扫描文档并添加到数据库
- ✅ 队列串行处理

---

### 10. `GET /collections` - 列出所有集合

**对应CLI**: `qmd collection list`

**请求参数**: 无（GET请求）

**响应格式**:
```json
{
  "collections": [
    {
      "name": "my-docs",
      "path": "/path/to/docs",
      "pattern": "**/*.md",
      "documents": 100
    }
  ],
  "content": "Collections: 1\n- my-docs (100 docs)"
}
```

---

### 11. `GET /collections/{name}` - 获取集合详情

**对应CLI**: -（隐含在collection list中）

**请求参数**: 无（GET请求）

**响应格式**:
```json
{
  "name": "my-docs",
  "path": "/path/to/docs",
  "pattern": "**/*.md",
  "documents": 100,
  "last_indexed": "2025-06-18T12:34:56Z"
}
```

---

### 12. `DELETE /collections/{name}` - 删除集合

**对应CLI**: `qmd collection remove <name>`

**请求参数**: 无（DELETE请求）

**响应格式**:
```json
{
  "status": "removed",
  "name": "my-docs",
  "content": "Removed collection 'my-docs'"
}
```

---

### 13. `PUT /collections/{name}` - 重命名集合

**对应CLI**: `qmd collection rename <old> <new>`

**请求参数**:
```json
{
  "new_name": "string (required)"
}
```

**响应格式**:
```json
{
  "status": "renamed",
  "old_name": "my-docs",
  "new_name": "my-docs-v2",
  "content": "Renamed 'my-docs' to 'my-docs-v2'"
}
```

---

### C. 索引指令（必需）

### 14. `POST /index` - 索引所有集合

**对应CLI**: `qmd index`

**请求参数**: 无（POST请求，空body）

**响应格式**:
```json
{
  "status": "indexed",
  "collections": 1,
  "total_documents": 1234,
  "content": "Indexed 1 collection: 1234 documents"
}
```

**行为**:
- ✅ 扫描所有集合
- ✅ 添加新文档到数据库
- ✅ 更新已存在的文档
- ✅ 队列串行处理

---

### 15. `POST /update` - 更新所有集合

**对应CLI**: `qmd update [--pull]`

**请求参数**:
```json
{
  "pull": "boolean (optional, default: false)"
}
```

**响应格式**:
```json
{
  "status": "updated",
  "collections": 1,
  "content": "Updated 1 collection"
}
```

**行为**:
- ✅ 如果`pull=true`：先执行`git pull`
- ✅ 重新索引所有集合
- ✅ 队列串行处理

---

### D. 上下文指令（可选）

### 16. `POST /contexts/add` - 添加上下文

**对应CLI**: `qmd context add [path] "text"`

**请求参数**:
```json
{
  "path": "string (required)",
  "text": "string (required)"
}
```

**响应格式**:
```json
{
  "status": "added",
  "path": "/path/to/docs",
  "content": "Added context for /path/to/docs"
}
```

---

### 17. `GET /contexts` - 列出所有上下文

**对应CLI**: `qmd context list`

**请求参数**: 无（GET请求）

**响应格式**:
```json
{
  "contexts": [
    {
      "path": "/path/to/docs",
      "text": "Project documentation"
    }
  ]
}
```

---

### 18. `DELETE /contexts/{path}` - 删除上下文

**对应CLI**: `qmd context rm <path>`

**请求参数**: 无（DELETE请求）

**响应格式**:
```json
{
  "status": "removed",
  "path": "/path/to/docs"
}
```

---

### E. 健康检查（必需）

### 19. `GET /health` - 健康检查

**用途**: 检查Server是否就绪

**请求参数**: 无（GET请求）

**响应格式**:
```json
{
  "status": "healthy" | "unhealthy",
  "model_loaded": true | false
}
```

**示例**:
```bash
# Request
curl http://localhost:18765/health

# Response
{
  "status": "healthy",
  "model_loaded": true
}
```

---

## MCP Tools (6个)

---

## MCP Tools (6个)

### 1. `search` - BM25全文搜索

**描述**: 快速关键词搜索，使用BM25全文索引

**输入参数**:
```json
{
  "query": "string (required)",     // 搜索查询
  "limit": "number (optional, default: 10)",      // 最大结果数
  "minScore": "number (optional, default: 0)",    // 最小相关性分数 0-1
  "collection": "string (optional)"  // 集合名称过滤
}
```

**输出格式**:
```json
{
  "content": [
    {
      "type": "text",
      "text": "Found 3 results for \"query\":\\n\\n#abc123 85% path/to/file.md - Title\\n#def456 72% another/file.md - Another Title"
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
        "snippet": "1: First line of snippet\\n2: Second line\\n3: Matched content here"
      }
    ]
  }
}
```

**行为规范**:
- ✅ 使用BM25 FTS搜索
- ✅ 后过滤集合（collection参数）
- ✅ 提取文本摘录（300字符）
- ✅ 默认添加行号格式（`N: content`）
- ✅ 分数四舍五入到2位小数
- ✅ 空结果返回：`"No results found for \"query\""`

---

### 2. `vsearch` - 向量语义搜索

**描述**: 使用向量嵌入进行语义相似度搜索

**输入参数**:
```json
{
  "query": "string (required)",     // 自然语言查询
  "limit": "number (optional, default: 10)",      // 最大结果数
  "minScore": "number (optional, default: 0.3)",  // 最小相关性分数 0-1
  "collection": "string (optional)"  // 集合名称过滤
}
```

**输出格式**:
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

**行为规范**:
- ✅ **向量索引检查**：不存在时返回 `isError: true`
  ```json
  {
    "content": [{"type": "text", "text": "Vector index not found. Run 'qmd embed' first to create embeddings."}],
    "isError": true
  }
  ```
- ✅ 查询扩展（可选高级功能）
- ✅ 多查询并行搜索
- ✅ 合并去重结果（取最高分数）
- ✅ 默认minScore=0.3（高于search的0）

---

### 3. `query` - 混合搜索（最高质量）

**描述**: 结合BM25+向量+查询扩展+LLM重排序

**输入参数**:
```json
{
  "query": "string (required)",     // 自然语言查询
  "limit": "number (optional, default: 10)",      // 最大结果数
  "minScore": "number (optional, default: 0)",    // 最小相关性分数 0-1
  "collection": "string (optional)"  // 集合名称过滤
}
```

**输出格式**:
```json
{
  "content": [{"type": "text", "text": "..."}],
  "structuredContent": {
    "results": [/* 同上 */]
  }
}
```

**行为规范**:
- ✅ 查询扩展（使用LLM生成多个变体）
- ✅ 并行FTS + 向量搜索
- ✅ Reciprocal Rank Fusion (RRF)融合
  - 权重：前2个查询×2.0，后续×1.0
- ✅ LLM重排（Top 30候选）
- ✅ 加权混合分数：
  - Top 3: 75% RRF + 25% rerank
  - 4-10: 60% RRF + 40% rerank
  - 11+: 40% RRF + 60% rerank
- ✅ **降级策略**：无向量索引时仅使用FTS

---

### 4. `get` - 获取单个文档

**描述**: 通过文件路径或docid检索完整文档内容

**输入参数**:
```json
{
  "file": "string (required)",     // 文件路径、docid (#abc123) 或带行号 (file.md:100)
  "fromLine": "number (optional)", // 起始行号（1-indexed）
  "maxLines": "number (optional)", // 最大行数
  "lineNumbers": "boolean (optional, default: false)"  // 添加行号
}
```

**特殊语法**:
- `file.md:120` → 从第120行开始（优先于`fromLine`参数）

**输出格式**:
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
        "text": "<!-- Context: meeting notes -->\\n\\n1: Line 1\\n2: Line 2\\n..."
      }
    }
  ]
}
```

**错误处理**:
```json
{
  "content": [
    {
      "type": "text",
      "text": "Document not found: unknown.md\\n\\nDid you mean one of these?\\n  - known/similar.md\\n  - another/path.md"
    }
  ],
  "isError": true
}
```

**行为规范**:
- ✅ 支持 `file.md:120` 语法
- ✅ 未找到时建议相似文件（Levenshtein距离）
- ✅ 行号格式：`N: content`（从fromLine或1开始）
- ✅ 上下文注释：`<!-- Context: {description} -->`
- ✅ URI编码路径（但保留斜杠）

---

### 5. `multi_get` - 批量获取文档

**描述**: 通过glob模式或逗号分隔列表检索多个文档

**输入参数**:
```json
{
  "pattern": "string (required)",  // glob模式或逗号分隔列表
  "maxLines": "number (optional)", // 每文件最大行数
  "maxBytes": "number (optional, default: 10240)",  // 跳过大于此值的文件（字节）
  "lineNumbers": "boolean (optional, default: false)"  // 添加行号
}
```

**示例**:
- Glob模式：`"journals/2025-05*.md"`
- 逗号分隔：`"file1.md, file2.md, file3.md"`

**输出格式**:
```json
{
  "content": [
    {
      "type": "text",
      "text": "Errors:\\nFile too large: bigfile.md (skipped)"
    },
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
      "text": "[SKIPPED: file2.md - File too large (15KB). Use 'qmd_get' with file=\"file2.md\" to retrieve.]"
    },
    {
      "type": "resource",
      "resource": { /* 第3个文件 */ }
    }
  ]
}
```

**截断格式**:
- 超过maxLines时添加：`\\n\\n[... truncated {N} more lines]`

**行为规范**:
- ✅ 超大文件跳过（不读取内容）
- ✅ 跳过的文件返回 `type: "text"` 通知
- ✅ 错误和跳过信息在content数组开头
- ✅ 默认maxBytes=10240（10KB）
- ✅ 无匹配文件：`isError: true`

---

### 6. `status` - 索引状态

**描述**: 显示QMD索引的状态、集合和健康信息

**输入参数**:
```json
{}
```

**输出格式**:
```json
{
  "content": [
    {
      "type": "text",
      "text": "QMD Index Status:\\n  Total documents: 1234\\n  Needs embedding: 56\\n  Vector index: yes\\n  Collections: 2\\n    - /path/to/docs (1000 docs)\\n    - /another/path (234 docs)"
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

**行为规范**:
- ✅ 格式化可读文本摘要
- ✅ 包含结构化数据供程序使用
- ✅ lastUpdated格式：ISO 8601日期字符串

---

## MCP Resources (1个)

### `qmd://{+path}` - 文档访问

**URI模板**: `qmd://{+path}`

**描述**: 通过路径只读访问文档

**MIME类型**: `text/markdown`

**Resource配置**:
```json
{
  "title": "QMD Document",
  "description": "A markdown document from your QMD knowledge base. Use search tools to discover documents.",
  "mimeType": "text/markdown"
}
```

**重要**: `list: undefined` - **不提供资源列表**（通过搜索工具发现）

#### 路径解析

**格式**: `{collection}/{relative-path}`

**示例**:
- `notes/meeting.md` → collection=`notes`, path=`meeting.md`
- `docs/2025/plan.md` → collection=`docs`, path=`2025/plan.md`

#### URI编码规则

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

- ✅ URL解码路径（MCP客户端发送编码后的URI）
- ✅ 精确匹配优先
- ✅ 后缀匹配回退（`LIKE %{path}`）
- ✅ 添加行号（默认）
- ✅ 上下文注释（`<!-- Context: ... -->`）

---

## MCP Prompts (1个)

### `query` - 查询指南

**名称**: `query`

**描述**: 如何有效使用QMD搜索知识库

**返回**: 单条user角色消息，包含Markdown格式使用指南

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

## 实现细节

### 1. 辅助函数

#### `encodeQmdPath(path: string): string`
```typescript
function encodeQmdPath(path: string): string {
  return path.split('/').map(segment => encodeURIComponent(segment)).join('/');
}
```
- **用途**: 编码qmd:// URI路径
- **规则**: 每段单独编码，保留斜杠

#### `addLineNumbers(text: string, startLine: number = 1): string`
```typescript
function addLineNumbers(text: string, startLine: number = 1): string {
  const lines = text.split('\n');
  return lines.map((line, i) => `${startLine + i}: ${line}`).join('\n');
}
```
- **用途**: 添加行号到文本
- **格式**: `{lineNum}: {content}`

#### `formatSearchSummary(results: SearchResultItem[], query: string): string`
```typescript
function formatSearchSummary(results: SearchResultItem[], query: string): string {
  if (results.length === 0) {
    return `No results found for "${query}"`;
  }
  const lines = [`Found ${results.length} result${results.length === 1 ? '' : 's'} for "${query}":\n`];
  for (const r of results) {
    lines.push(`${r.docid} ${Math.round(r.score * 100)}% ${r.file} - ${r.title}`);
  }
  return lines.join('\n');
}
```
- **用途**: 格式化搜索结果摘要
- **格式**: `#abc123 85% path/to/file.md - Title`

### 2. 数据结构

#### `SearchResultItem`
```typescript
type SearchResultItem = {
  docid: string;           // 短ID (#abc123)
  file: string;            // 显示路径
  title: string;           // 文档标题
  score: number;           // 相关性分数 0-1
  context: string | null;  // 上下文描述
  snippet: string;         // 带行号的摘录
};
```

#### `StatusResult`
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

### 3. 特殊行为

#### 文档未找到时的相似文件建议
- 使用Levenshtein距离计算相似度
- 返回前3个最相似的文件路径
- 格式：`Did you mean one of these?\\n  - file1.md\\n  - file2.md`

#### 向量索引不存在
- `vsearch`: 返回 `isError: true`
- `query`: 降级到仅FTS搜索（不报错）

#### 查询扩展（高级功能）
- 使用LLM生成3-5个查询变体
- 并行执行所有查询
- 合并去重结果

---

## 实现检查清单

### Phase 1: 核心 Tools (P0 - 必须实现)

**Tool: `search`**
- [ ] 参数: `query`, `limit`, `minScore`, `collection`
- [ ] 输出: `content.text` + `structuredContent.results`
- [ ] 结果字段: `docid`, `file`, `title`, `score`, `context`, `snippet`
- [ ] 摘录带行号（默认）
- [ ] 默认值: `limit=10`, `minScore=0`
- [ ] 分数四舍五入到2位小数

**Tool: `vsearch`**
- [ ] 参数: `query`, `limit`, `minScore`, `collection`
- [ ] 向量索引检查 → 不存在返回 `isError: true`
- [ ] 默认值: `limit=10`, `minScore=0.3`

**Tool: `query`**
- [ ] 参数: `query`, `limit`, `minScore`, `collection`
- [ ] RRF融合
- [ ] 降级策略：无向量索引时仅FTS

**Tool: `get`**
- [ ] 参数: `file`, `fromLine`, `maxLines`, `lineNumbers`
- [ ] 支持 `file.md:120` 语法
- [ ] 相似文件建议
- [ ] 输出: `content.resource` with `qmd://` URI
- [ ] 行号格式: `N: content`
- [ ] 上下文注释

**Tool: `multi_get`**
- [ ] 参数: `pattern`, `maxLines`, `maxBytes`, `lineNumbers`
- [ ] Glob模式或逗号分隔列表
- [ ] 超大文件跳过机制
- [ ] 默认值: `maxBytes=10240`

**Tool: `status`**
- [ ] 无参数
- [ ] 输出: `content.text` + `structuredContent`
- [ ] 字段: `totalDocuments`, `needsEmbedding`, `hasVectorIndex`, `collections`

### Phase 2: Resources (P1 - 推荐实现)

**Resource: `qmd://{+path}`**
- [ ] `list: undefined`（不提供列表）
- [ ] MIME type: `text/markdown`
- [ ] URI编码（保留斜杠）
- [ ] 路径解析: `{collection}/{relative-path}`
- [ ] 后缀匹配回退
- [ ] 行号 + 上下文注释

### Phase 3: Prompts (P2 - 可选)

**Prompt: `query`**
- [ ] Markdown使用指南
- [ ] 6个工具说明
- [ ] 搜索策略

---

## 测试用例

### Tool测试

**`search`**:
```json
// 输入
{"query": "meeting", "limit": 5, "minScore": 0.5}

// 预期输出
{
  "content": [{"type": "text", "text": "Found 2 results for \"meeting\":..."}],
  "structuredContent": {"results": [{...}, {...}]}
}
```

**`get` with line syntax**:
```json
// 输入
{"file": "notes/meeting.md:120", "maxLines": 20}

// 预期行为
// fromLine = 120, file = "notes/meeting.md"
// 返回第120-140行，带行号
```

**`multi_get` with glob**:
```json
// 输入
{"pattern": "journals/2025-*.md", "maxBytes": 5120}

// 预期行为
// 匹配所有 journals/2025- 开头的 .md 文件
// 跳过大于5KB的文件
```

### Resource测试

**URI解析**:
```
qmd://notes%2F2025%2F%20meeting.md
→ collection: "notes"
→ path: "2025/ meeting.md"
→ 解码: notes/2025/ meeting.md
```

---

## 参考资源

- **MCP规范**: [Model Context Protocol](https://modelcontextprotocol.io/)
- **原始实现**: `D:\MoneyProjects\qmd\src\mcp.ts` (627 lines)
- **测试文件**: `D:\MoneyProjects\qmd\src\mcp.test.ts`
- **配置文档**: `D:\MoneyProjects\qmd\skills\qmd\references\mcp-setup.md`

---

**最后更新**: 2026-02-15
**维护者**: QMD-Python Team
