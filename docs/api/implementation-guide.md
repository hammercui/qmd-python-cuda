# QMD Server 实现指南

**版本**: 1.0.0
**用途**: Server 实现者参考

---

## 辅助函数

### `encodeQmdPath(path: string): string`

编码 qmd:// URI 路径

```typescript
function encodeQmdPath(path: string): string {
  return path.split('/').map(segment => encodeURIComponent(segment)).join('/');
}
```

- **用途**: 编码 qmd:// URI 路径
- **规则**: 每段单独编码，保留斜杠
- **示例**: `"notes/2025 meeting.md"` → `"notes%2F2025%20meeting.md"`

---

### `addLineNumbers(text: string, startLine: number = 1): string`

添加行号到文本

```typescript
function addLineNumbers(text: string, startLine: number = 1): string {
  const lines = text.split('\n');
  return lines.map((line, i) => `${startLine + i}: ${line}`).join('\n');
}
```

- **用途**: 添加行号到文本
- **格式**: `{lineNum}: {content}`
- **示例**: `"First line\nSecond line"` → `"1: First line\n2: Second line"`

---

### `formatSearchSummary(results: SearchResultItem[], query: string): string`

格式化搜索结果摘要

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

## 特殊行为

### 文档未找到时的相似文件建议

**算法**: 使用 Levenshtein 距离计算相似度

**实现**:
```python
from Levenshtein import distance

def suggest_similar_files(target: str, candidates: List[str], top_n: int = 3):
    scored = [(f, distance(target.lower(), f.lower())) for f in candidates]
    scored.sort(key=lambda x: x[1])
    return [f for f, _ in scored[:top_n]]
```

**输出格式**: 
```
Did you mean one of these?
  - file1.md
  - file2.md
```

---

### 向量索引不存在

| Tool | 行为 |
|------|------|
| **vsearch** | 返回 `isError: true`，错误消息："Vector index not found. Run 'qmd embed' first" |
| **query** | 降级到仅 FTS 搜索（不报错） |

**实现**:
```python
def has_vector_index(db) -> bool:
    cursor = db.execute("SELECT COUNT(*) FROM content_vectors")
    return cursor.fetchone()[0] > 0
```

---

### 查询扩展（高级功能）

**流程**:
1. 使用 LLM 生成 3-5 个查询变体
2. 并行执行所有查询
3. 合并去重结果（取最高分数）

**实现示例**:
```python
async def expand_query(query: str, llm) -> List[str]:
    prompt = f"Generate 3-5 search query variations for: {query}"
    variations = await llm.generate(prompt)
    return [query] + variations.split('\n')
```


## 测试用例

### Tool 测试

#### `search` - 基本功能

**输入**:
```json
{"query": "meeting", "limit": 5, "minScore": 0.5}
```

**预期输出**:
```json
{
  "content": [{"type": "text", "text": "Found 2 results for \"meeting\":..."}],
  "structuredContent": {"results": [{...}, {...}]}
}
```

---

#### `get` - 带行语法

**输入**:
```json
{"file": "notes/meeting.md:120", "maxLines": 20}
```

**预期行为**:
- `fromLine = 120`
- `file = "notes/meeting.md"`
- 返回第 120-140 行，带行号

---

#### `multi_get` - Glob 模式

**输入**:
```json
{"pattern": "journals/2025-*.md", "maxBytes": 5120}
```

**预期行为**:
- 匹配所有 `journals/2025-` 开头的 `.md` 文件
- 跳过大于 5KB 的文件

---

### Resource 测试

#### URI 解析

**输入**: `qmd://notes%2F2025%2F%20meeting.md`

**预期解析**:
- `collection`: `"notes"`
- `path`: `"2025/ meeting.md"`
- 解码后: `notes/2025/ meeting.md`

---

## 实现注意事项

### 1. 行号格式

**规范**: `{lineNum}: {content}`

**示例**:
```
1: First line
2: Second line
100: Hundredth line
```

**实现**: 确保冒号后有空格

---

### 2. DocID 格式

**规范**: `#{hash}` (短 hash 前缀)

**示例**: `#abc123`

**实现**: 使用内容 hash 的前 6-7 个字符

---

### 3. URI 编码

**编码**: 每个路径段单独编码，保留 `/` 分隔符

**函数**: 见 `encodeQmdPath` 辅助函数

**实现**: 使用 `encodeURIComponent`（JavaScript）或 `urllib.parse.quote`（Python）

---

### 4. 错误处理

**原则**: 返回有意义的错误消息，包含解决建议

**示例**:
```json
{
  "content": [{"type": "text", "text": "Vector index not found. Run 'qmd embed' first to create embeddings."}],
  "isError": true
}
```

---

### 5. 性能优化

**建议**:
- 使用连接池（数据库、HTTP）
- 实现查询缓存（可选）
- 批量操作限制（如 `embed` 最多 1000 个文本）
- 异步处理（使用 `asyncio`）

---

### 6. 安全考虑

**建议**:
- 验证所有输入参数
- 限制文件访问范围（防止路径遍历攻击）
- 限制资源使用（内存、CPU）
- 记录关键操作（审计日志）

---

## 参考资源

- **MCP 规范**: [Model Context Protocol](https://modelcontextprotocol.io/)
- **原始实现**: `D:\MoneyProjects\qmd\src\mcp.ts` (627 lines)
- **测试文件**: `D:\MoneyProjects\qmd\src\mcp.test.ts`
- **配置文档**: `D:\MoneyProjects\qmd\skills\qmd\references\mcp-setup.md`

---

**最后更新**: 2026-02-17
**维护者**: QMD-Python Team
