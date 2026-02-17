# QMD Search vs VSearch - 架构对比

## 概述

QMD有两种搜索方式：

1. **`search`** - 全文搜索 (FTS)
2. **`vsearch`** - 向量语义搜索 (Vector Search)

---

## Search (FTS 全文搜索)

### TypeScript 版本
```typescript
// 文件: src/qmd.ts line 1939
const results = searchFTS(db, query, fetchLimit, collectionName);
```

**技术栈**:
- SQLite FTS5 虚拟表 (`documents_fts`)
- BM25 排序算法
- 纯 SQL 查询

**SQL 查询**:
```sql
SELECT
  d.id, d.collection, d.path, d.hash, d.title,
  snippet(c.doc, -2, '[b]', '[/b]', 30) as snippet,
  c.doc as content
FROM documents_fts
JOIN documents d ON documents_fts.rowid = d.id
JOIN content c ON d.hash = c.hash
WHERE documents_fts MATCH ?
ORDER BY bm25(documents_fts)
LIMIT ?
```

**特点**:
- ✅ 纯 SQLite 操作
- ✅ 不需要模型
- ✅ 速度快 (1-2秒)
- ⚠️ 只能匹配关键词

---

### Python 版本
```python
# 文件: qmd/search/fts.py
class FTSSearcher:
    def search(self, query: str, limit: int = 10):
        with self.db._get_connection() as conn:
            cursor = conn.execute("""
                SELECT
                    d.id, d.collection, d.path, d.hash, d.title,
                    snippet(c.doc, -2, '[b]', '[/b]', 30) as snippet,
                    c.doc as content
                FROM documents_fts
                JOIN documents d ON documents_fts.rowid = d.id
                JOIN content c ON d.hash = c.hash
                WHERE documents_fts MATCH ?
                ORDER BY bm25(documents_fts)
                LIMIT ?
            """, (fts_query, limit))
```

**技术栈**:
- SQLite FTS5 虚拟表
- Python sqlite3 模块
- 与 TS 版本相同的 SQL 查询

**性能**:
- ⚡ **1.5秒** (测试结果)
- 无需模型加载
- 直接在数据库中查询

---

## VSearch (向量语义搜索)

### TypeScript 版本
```typescript
// 文件: src/qmd.ts line 2013
const vecResults = await searchVec(db, q, model, perQueryLimit, collectionName, session);
```

**技术栈**:
- sqlite-vec 扩展 (SQLite 向量虚拟表)
- node-llama-cpp (LLM 模型)
- 两步查询策略

**查询流程**:
```typescript
// Step 1: 生成 query embedding
const embedding = await getEmbedding(query, model, true, session);

// Step 2: 向量搜索 (sqlite-vec)
const vecResults = db.prepare(`
  SELECT hash_seq, distance
  FROM vectors_vec
  WHERE embedding MATCH ? AND k = ?
`).all(new Float32Array(embedding), limit * 3);

// Step 3: JOIN 获取文档内容 (单独查询)
const docRows = db.prepare(`
  SELECT
    cv.hash || '_' || cv.seq as hash_seq,
    cv.hash, cv.pos,
    'qmd://' || d.collection || '/' || d.path as filepath,
    d.collection || '/' || d.path as display_path,
    d.title,
    content.doc as body
  FROM content_vectors cv
  JOIN documents d ON d.hash = cv.hash AND d.active = 1
  JOIN content ON content.hash = d.hash
  WHERE cv.hash || '_' || cv.seq IN (...)
`).all(...hashSeqs);
```

**关键点**:
- ⚠️ **两步查询** (不能JOIN sqlite-vec虚拟表)
- 需要 LLM 模型生成 embedding
- sqlite-vec 使用余弦距离

**性能**:
- 首次加载模型: 慢
- 后续查询: 取决于 GPU 加速
- TS 版本使用 node-llama-cpp (支持 CUDA)

---

### Python 版本
```python
# 文件: qmd/search/vector.py
class VectorSearch:
    def search(self, query: str, collection_name: str, limit: int = 5):
        # Step 1: 生成 query embedding
        query_embedding = self.llm.embed_query(query)

        # Step 2: 向量搜索 (ChromaDB)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )
```

**技术栈**:
- **ChromaDB** (独立向量数据库,不是SQLite扩展)
- **fastembed-gpu** (生成 embeddings)
- QMD Server (HTTP API)

**架构差异**:
```
TypeScript 版本:
  SQLite + sqlite-vec 扩展
  └─ vectors_vec 虚拟表 (在 SQLite 内)

Python 版本:
  SQLite (元数据)
  + ChromaDB (向量索引,独立数据库)
  + QMD Server (HTTP API)
```

**性能问题**:
- ❌ **修复前**: 35.3秒 (未使用 GPU)
- ✅ **修复后**: 3.3秒 (启用 CUDA)
- 📈 **性能提升**: 10.7倍

**修复内容**:
```python
# 文件: qmd/server/app.py line 52
# 修复前:
_model = TextEmbedding(model_name=DEFAULT_MODEL)

# 修复后:
providers = ["CUDAExecutionProvider"]  # 启用 GPU
_model = TextEmbedding(
    model_name=DEFAULT_MODEL,
    providers=providers
)
```

---

## SQLite 参与环节

### Search (FTS)
✅ **全程参与**
- FTS5 虚拟表 (`documents_fts`)
- 文档表 (`documents`)
- 内容表 (`content`)
- BM25 排序

**无外部依赖**

---

### VSearch (Vector)

#### TypeScript 版本
✅ **全程参与**
- sqlite-vec 扩展 (`vectors_vec` 虚拟表)
- 向量块表 (`content_vectors`)
- 文档表 (`documents`)
- 内容表 (`content`)

**外部依赖**:
- node-llama-cpp (生成 embedding)

#### Python 版本
⚠️ **部分参与**
- SQLite 只存元数据 (`documents`, `content`)
- 向量索引在 **ChromaDB** (独立数据库)

**外部依赖**:
- fastembed-gpu (生成 embedding)
- ChromaDB (向量数据库)
- QMD Server (HTTP API)

---

## 性能对比

| 操作 | Search (FTS) | VSearch (Vector) |
|------|--------------|------------------|
| **TS 版本** | ~1秒 | 取决于模型 |
| **Python 版本 (修复前)** | 1.5秒 | 35.3秒 ❌ |
| **Python 版本 (修复后)** | 1.5秒 | 3.3秒 ✅ |
| **GPU 加速效果** | 无需 | **10.7倍** 📈 |
| **模型加载时间** | 无 | 首次 5-10秒 |

---

## 架构差异总结

### TypeScript 版本 (统一架构)
```
┌─────────────────────────────────┐
│         SQLite 数据库            │
├─────────────────────────────────┤
│ • documents (元数据)            │
│ • content (全文)                │
│ • documents_fts (FTS5 索引)     │
│ • vectors_vec (sqlite-vec 索引) │
│ • content_vectors (向量块)      │
└─────────────────────────────────┘
         ↓              ↓
      search        vsearch
      (FTS)         (Vector)
```

**优点**:
- ✅ 单一数据库
- ✅ 事务一致性
- ✅ 简化部署

**缺点**:
- ⚠️ 需要 sqlite-vec 扩展
- ⚠️ SQLite 并发限制

---

### Python 版本 (分离架构)
```
┌──────────────────┐      ┌──────────────────┐
│   SQLite 数据库   │      │   ChromaDB 向量库 │
├──────────────────┤      ├──────────────────┤
│ • documents      │      │ • 向量索引        │
│ • content        │      │ • embeddings     │
│ • collections    │      └──────────────────┘
└──────────────────┘               ↓
         ↓                    QMD Server
      search                 (HTTP API)
      (FTS)                      ↓
                            vsearch
                            (Vector)
```

**优点**:
- ✅ ChromaDB 专业向量搜索
- ✅ HTTP API (多进程共享)
- ✅ 模块化设计

**缺点**:
- ⚠️ 两个数据库
- ⚠️ 需要同步维护
- ⚠️ HTTP 开销

---

## 何时使用哪种搜索？

### 使用 Search (FTS) 当:
- ✅ 查询明确的关键词
- ✅ 需要快速结果
- ✅ 查询文件名、标题
- ✅ 精确匹配需求

### 使用 VSearch (Vector) 当:
- ✅ 语义相似度搜索
- ✅ 查询概念而非关键词
- ✅ 需要理解查询意图
- ✅ 同义词、相关概念

### 使用 Query (混合) 当:
- ✅ 两种搜索结合
- ✅ RRK (Reciprocal Rank Fusion)
- ✅ 最相关结果
- ⚠️ **最慢** (需要两次查询)

---

## 推荐配置

### 小项目 (< 1000 文档)
- **Search (FTS)** 足够
- 无需 GPU

### 中项目 (1000-10000 文档)
- **Search (FTS)** + **VSearch (Vector)**
- 建议启用 GPU 加速

### 大项目 (> 10000 文档)
- **Query (混合搜索)**
- **必须启用 GPU**
- 考虑分布式部署

---

## 参考资料

- **TypeScript 版本**: `D:\MoneyProjects\qmd\src\store.ts`
- **Python 版本**: `D:\MoneyProjects\qmd-python\qmd\search\`
- **SQLite FTS5**: https://www.sqlite.org/fts5.html
- **sqlite-vec**: https://github.com/asg017/sqlite-vec
- **ChromaDB**: https://www.trychroma.com/
