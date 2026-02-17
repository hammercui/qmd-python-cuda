# QMD HTTP 端点规范

**版本**: 1.0.0
**协议**: HTTP/1.1
**Content-Type**: `application/json`
**端口**: 18765 (默认，可通过 `--port` 配置)

---

## 概述

HTTP Transport 提供 REST API 端点，用于：
- CLI 命令的 server 模式（`qmd search --mode server`）
- OpenClaw 的 HTTP 客户端
- 其他需要程序化访问的场景

### Server 信息

```yaml
name: qmd
version: 1.0.0
http:
  url: http://localhost:18765
  default_port: 18765
```

### 认证

**当前版本**: 无需认证（localhost only）
**未来版本**: 可选 API Key 或 OAuth

---

## 错误处理

所有端点遵循统一的错误响应格式：

```json
{
  "detail": "Error message",
  "status_code": 400
}
```

### 常见 HTTP 状态码

| 状态码 | 含义 | 使用场景 |
|--------|------|----------|
| `200 OK` | 请求成功 | 正常响应 |
| `400 Bad Request` | 参数验证失败 | 缺少必需参数、类型错误 |
| `404 Not Found` | 资源不存在 | 仅 `/get` 端点 |
| `500 Internal Server Error` | 服务器内部错误 | 未预期的异常 |
| `503 Service Unavailable` | 服务不可用 | 模型未加载或 Server 未就绪 |

---

## 核心端点（5个）

### 设计原则

**只有模型操作需要 HTTP 接口**：
- ✅ 嵌入生成（embed）
- ✅ 向量搜索（vsearch）
- ✅ 混合搜索（query）
- ✅ BM25 搜索（可选，search）
- ✅ 健康检查（health）

**SQLite 操作保持 CLI-only**：
- collection add/list/remove/rename
- index, update
- get, multi_get
- status
- context add/list/rm

---

### 1. `POST /embed` - 生成嵌入

**优先级**: P0 | **对应 CLI**: `qmd embed`

#### 请求参数

```json
{
  "texts": ["string (required)", ...]  // 文本列表（最多1000个）
}
```

#### 响应格式

```json
{
  "embeddings": [
    [0.1, 0.2, ..., 0.8]  // 384维向量（text1）
  ]
}
```

#### 错误处理

```json
// 空列表
{
  "detail": "Empty texts list",
  "status_code": 400
}

// 太多 texts
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

#### 限制

- ✅ 最多 1000 个文本
- ✅ 串行处理（队列）
- ✅ 单例模型（4GB VRAM）

#### 示例

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

### 2. `POST /vsearch` - 向量语义搜索

**优先级**: P0 | **对应 CLI**: `qmd vsearch`

#### 请求参数

```json
{
  "query": "string (required)",
  "limit": "number (optional, default: 10)",
  "min_score": "number (optional, default: 0.3)",
  "collection": "string (optional)"
}
```

#### 响应格式

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

#### 行为

- ✅ 向量索引不存在时返回 HTTP 503
- ✅ 查询扩展（可选高级功能）
- ✅ 多查询并行搜索
- ✅ 合并去重结果（取最高分数）

---

### 3. `POST /query` - 混合搜索（最高质量）

**优先级**: P0 | **对应 CLI**: `qmd query`

#### 请求参数

```json
{
  "query": "string (required)",
  "limit": "number (optional, default: 10)",
  "min_score": "number (optional, default: 0.0)",
  "collection": "string (optional)"
}
```

#### 响应格式

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

#### 行为

- ✅ 无向量索引时降级为 FTS 搜索（不报错）
- ✅ 查询扩展：使用 LLM 生成查询变体（可选高级功能）
- ✅ RRF 融合：FTS 和向量结果合并
- ✅ LLM 重排：Top 30 候选文档重新排序

---

### 4. `POST /search` - BM25 全文搜索

**优先级**: P1 | **对应 CLI**: `qmd search`

#### 说明

BM25 搜索不需要模型，可以直接 SQLite 操作。提供 HTTP 接口是为了**统一体验**。

#### 请求参数

```json
{
  "query": "string (required)",
  "limit": "number (optional, default: 10)",
  "min_score": "number (optional, default: 0.0)",
  "collection": "string (optional)"
}
```

#### 响应格式

```json
{
  "results": [
    {
      "docid": "#abc123",
      "file": "path/to/file.md",
      "title": "Document Title",
      "score": 0.85,
      "context": "meeting notes",
      "snippet": "1: Matched content\n2: Another line"
    }
  ],
  "content": "Found 2 results for \"query\"\n\n#abc123 85% path/to/file.md - Title\n\n#def456 72% another/file.md - Another Title"
}
```

#### 行为

- ✅ 使用 BM25 FTS 搜索
- ✅ 后过滤集合
- ✅ 提取文本摘录（300 字符）
- ✅ 添加行号到摘录
- ✅ 分数四舍五入到 2 位小数

---

### 5. `GET /health` - 健康检查

**优先级**: P0

#### 用途

检查 Server 是否就绪

#### 请求参数

无（GET 请求）

#### 响应格式

```json
{
  "status": "healthy" | "unhealthy",
  "model_loaded": true | false
}
```

#### 示例

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

## 其他端点（可选）

以下端点当前未实现，保留用于未来扩展：

### 6. `POST /get` - 获取单个文档

对应 MCP Tool: `get`

### 7. `POST /multi_get` - 批量获取文档

对应 MCP Tool: `multi_get`

### 8. `GET /status` - 索引状态

对应 MCP Tool: `status`

---

## CLI 直接操作（SQLite）

以下命令**不提供 HTTP 接口**，保持 CLI-only：

### 管理指令

| 命令 | 说明 | 实现方式 |
|------|------|---------|
| `collection add` | 添加集合 | 直接 SQLite |
| `collection list` | 列出集合 | 直接 SQLite |
| `collection remove` | 删除集合 | 直接 SQLite |
| `collection rename` | 重命名集合 | 直接 SQLite |
| `index` | 索引文档 | 直接 SQLite |
| `update` | 更新集合 | 直接 SQLite |
| `context add` | 添加上下文 | 直接 SQLite |
| `context list` | 列出上下文 | 直接 SQLite |
| `context rm` | 删除上下文 | 直接 SQLite |

### 为什么不需要 HTTP 接口？

- ✅ 不涉及模型操作
- ✅ SQLite 操作简单快速
- ✅ CLI 直接操作更灵活
- ✅ 减少 HTTP 接口数量

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

---

## 相关文档

- [MCP Tools 规范](mcp-tools.md) - MCP 协议接口
- [兼容性分析](compatibility.md) - 与原版 QMD 的兼容性
- [实现指南](implementation-guide.md) - 实现细节和测试用例

---

**最后更新**: 2026-02-17
**维护者**: QMD-Python Team
