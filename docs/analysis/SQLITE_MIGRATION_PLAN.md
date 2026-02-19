# SQLite 迁移计划：Python → 对齐 TypeScript 实现

> **目标**：将 Python 版本的向量存储从 ChromaDB 迁移回 SQLite + sqlite-vec，完全对齐 TypeScript 实现。  
> **状态**：分析文档，**不修改代码**。  
> **日期**：2025-01

---

## 1. 总体差异概览

| 维度 | TypeScript 实现 | Python 现状 | 差距 |
|------|----------------|------------|------|
| 向量存储 | sqlite-vec（vec0 虚拟表） | ChromaDB（独立进程/文件） | ❌ 完全不同 |
| 向量元数据 | `content_vectors` 表 | `content.embedding BLOB` 列 | ❌ 设计不同 |
| FTS 列 | `filepath, title, body` | `title, context, content` | ❌ |
| FTS tokenizer | `porter unicode61` | `unicode61` | ❌ 缺少 Porter 词干 |
| FTS 触发器 | 条件触发（`WHEN new.active=1`） | 无条件触发 | ⚠️ |
| collections 管理 | YAML 配置 | SQLite `collections` 表 | ⚠️ 有额外表 |
| path_contexts 管理 | YAML 配置 | SQLite `path_contexts` 表 | ⚠️ 有额外表 |
| LLM 缓存 | `llm_cache` 表 | 无 | ❌ 缺少 |
| `documents.title` | `NOT NULL` | 可为 NULL | ⚠️ |
| `documents.context` | 无此列 | 有此列 | ⚠️ 多余列 |
| `content.embedding` | 无此列 | 有此列 | ⚠️ 多余列 |
| `content.created_at` | 有 | 无 | ❌ 缺少 |
| 索引 | 3 个复合索引 | 无索引 | ❌ |
| 外键约束 | ON DELETE CASCADE | 无 | ⚠️ |

---

## 2. Schema 逐表对比

### 2.1 `content` 表

**TypeScript（目标）**
```sql
CREATE TABLE IF NOT EXISTS content (
  hash TEXT PRIMARY KEY,
  doc  TEXT NOT NULL,
  created_at TEXT NOT NULL          -- ← 有时间戳
);
```

**Python（现状）**
```sql
CREATE TABLE IF NOT EXISTS content (
  hash TEXT PRIMARY KEY,
  doc  TEXT NOT NULL,
  embedding BLOB                    -- ← 多余！向量应在单独表
                                    -- ← 缺少 created_at
);
```

**变更项**：
- 删除 `embedding BLOB` 列（SQLite 不支持 DROP COLUMN，需重建表）
- 新增 `created_at TEXT NOT NULL`（可默认 `datetime('now')`）

---

### 2.2 `documents` 表

**TypeScript（目标）**
```sql
CREATE TABLE IF NOT EXISTS documents (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  collection  TEXT NOT NULL,
  path        TEXT NOT NULL,
  title       TEXT NOT NULL,        -- ← NOT NULL
  hash        TEXT NOT NULL,
  created_at  TEXT NOT NULL,        -- ← 有
  modified_at TEXT NOT NULL,
  active      INTEGER NOT NULL DEFAULT 1,
  FOREIGN KEY (hash) REFERENCES content(hash) ON DELETE CASCADE,
  UNIQUE(collection, path)
);
-- 3 个复合索引（Python 无）
CREATE INDEX IF NOT EXISTS idx_documents_collection ON documents(collection, active);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(hash);
CREATE INDEX IF NOT EXISTS idx_documents_path ON documents(path, active);
```

**Python（现状）**
```sql
CREATE TABLE IF NOT EXISTS documents (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  collection  TEXT NOT NULL,
  path        TEXT NOT NULL,
  hash        TEXT NOT NULL,
  title       TEXT,                 -- ← 可为 NULL（TS 要求 NOT NULL）
  context     TEXT,                 -- ← 多余列（TS 无此列）
  active      INTEGER DEFAULT 1,
  created_at  TEXT,
  modified_at TEXT,
  UNIQUE(collection, path)
                                    -- ← 无外键约束
                                    -- ← 无索引
);
```

**变更项**：
- `title` 改为 `NOT NULL`
- 删除 `context` 列（重建表）
- 新增外键约束 `REFERENCES content(hash) ON DELETE CASCADE`
- 新增 3 个索引
- 确保 `created_at`、`modified_at`、`active` 均为 `NOT NULL`

---

### 2.3 `llm_cache` 表（新增）

**TypeScript（目标）**
```sql
CREATE TABLE IF NOT EXISTS llm_cache (
  hash       TEXT PRIMARY KEY,
  result     TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

**Python（现状）**：❌ 无此表

**变更项**：新增 `llm_cache` 表，用于缓存 LLM API 调用（`expandQuery` / `rerank` 结果）。

---

### 2.4 `content_vectors` 表（新增）

**TypeScript（目标）**
```sql
CREATE TABLE IF NOT EXISTS content_vectors (
  hash        TEXT NOT NULL,
  seq         INTEGER NOT NULL DEFAULT 0,   -- chunk 序号（0-based）
  pos         INTEGER NOT NULL DEFAULT 0,   -- chunk 在原文中的字符位置
  model       TEXT NOT NULL,
  embedded_at TEXT NOT NULL,
  PRIMARY KEY (hash, seq)
);
```

**Python（现状）**：❌ 无此表（向量元数据存在 ChromaDB 中）

**变更项**：新增 `content_vectors` 表存储 chunk 级元数据。

---

### 2.5 `vectors_vec` 虚拟表（新增）

**TypeScript（目标）**
```sql
-- 动态创建，维度在首次 embed 时确定
CREATE VIRTUAL TABLE vectors_vec USING vec0(
  hash_seq  TEXT PRIMARY KEY,       -- 格式："{hash}_{seq}"
  embedding float[{dimensions}] distance_metric=cosine
);
```

**Python（现状）**：❌ 无此表（用 ChromaDB 的 HNSW 索引）

**已验证**：sqlite-vec 0.1.6 支持 TEXT PRIMARY KEY：
```python
conn.execute("CREATE VIRTUAL TABLE v USING vec0(hash_seq TEXT PRIMARY KEY, embedding float[4] distance_metric=cosine)")
conn.execute("INSERT INTO v VALUES ('abc_0', ?)", (vector_bytes,))
rows = conn.execute("SELECT hash_seq, distance FROM v WHERE embedding MATCH ? AND k=1", (query_bytes,)).fetchall()
# → [('abc_0', 0.0)]  ✅ 正常工作
```

---

### 2.6 `documents_fts` 虚拟表

**TypeScript（目标）**
```sql
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
  filepath, title, body,            -- filepath = "collection/path"
  tokenize='porter unicode61'       -- Porter 词干算法
);
```

**Python（现状）**
```sql
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
  title,
  context,                          -- 多余，TS 无此列
  content,                          -- TS 用 body，且触发器里从 content 表取
  tokenize='unicode61'              -- 缺少 porter
);
```

**差异详解**：
1. **`filepath` 列缺失**：TS 的 FTS 通过 `filepath`（`collection/path`）识别文档，Python 没有
2. **`porter` 词干缺失**：Porter 词干算法使 `running`/`run` 等词匹配相同词根，搜索更宽泛
3. **`body` vs `content`**：列名不同，BM25 权重配置也不同
4. **`bm25()` 权重**：TS 用 `bm25(documents_fts, 10.0, 1.0)` 给 `filepath` 权重 10，Python 未配权重

---

### 2.7 触发器对比

**TypeScript 触发器（条件触发）**
```sql
-- INSERT 触发器：仅当 active=1 时才插入 FTS
CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents
WHEN new.active = 1
BEGIN
  INSERT INTO documents_fts(rowid, filepath, title, body)
  SELECT new.id, new.collection || '/' || new.path, new.title,
         (SELECT doc FROM content WHERE hash = new.hash)
  WHERE new.active = 1;
END;

-- UPDATE 触发器：区分 active 变化
CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents
BEGIN
  -- 变为非活跃：从 FTS 删除
  DELETE FROM documents_fts WHERE rowid = old.id AND new.active = 0;
  -- 变为活跃：插入/更新 FTS
  INSERT OR REPLACE INTO documents_fts(rowid, filepath, title, body)
  SELECT new.id, new.collection || '/' || new.path, new.title,
         (SELECT doc FROM content WHERE hash = new.hash)
  WHERE new.active = 1;
END;
```

**Python 触发器（无条件触发）**
```sql
-- INSERT 触发器：无条件插入（不检查 active）
CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
  INSERT INTO documents_fts(rowid, title, context, content)
  SELECT new.id, new.title, new.context, c.doc
  FROM content c WHERE c.hash = new.hash;
END;

-- UPDATE 触发器：直接重新插入（未区分 active 变化）
CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
  DELETE FROM documents_fts WHERE rowid = old.id;
  INSERT INTO documents_fts(rowid, title, context, content)
  SELECT new.id, new.title, new.context, c.doc
  FROM content c WHERE c.hash = new.hash;
END;
```

**问题**：Python 触发器会把 `active=0` 的文档也插入 FTS，导致搜索结果包含已软删除的文档。

---

### 2.8 Python 特有表（TS 已移除）

| 表名 | Python 用途 | TS 对应方案 | 迁移策略 |
|------|------------|------------|---------|
| `collections` | 存储 collection 配置 | YAML `~/.config/qmd/index.yml` | 保留（Python CLI 需要）或迁移到 YAML |
| `path_contexts` | 存储路径上下文 | YAML 配置 | 保留（Python CLI 需要）或迁移到 YAML |

> **注**：TS 在 `initializeDatabase` 中会 `DROP TABLE IF EXISTS path_contexts` 和 `DROP TABLE IF EXISTS collections`（注释："Drop legacy tables that are now managed in YAML"）。Python 暂时可以保留这两个表，作为 YAML 迁移的过渡方案，但应与 `documents_fts` 解耦。

---

## 3. 关键函数差距分析

### 3.1 `DatabaseManager` 需新增/修改的方法

| 方法 | 现状 | 目标实现 |
|------|------|---------|
| `insert_content(hash, doc, created_at)` | ❌ 无（嵌入在 upsert 里） | `INSERT OR IGNORE INTO content VALUES (?,?,?)` |
| `insert_document(collection, path, title, hash, created_at, modified_at)` | ❌ 无（只有 upsert） | `INSERT INTO documents VALUES (?,?,?,?,?,?,1)` |
| `find_active_document(collection, path)` | ❌ 无 | 返回 `{id, hash, title}` |
| `update_document(doc_id, title, hash, modified_at)` | ❌ 无 | `UPDATE documents SET ...` |
| `update_document_title(doc_id, title, modified_at)` | ❌ 无 | 仅更新 title |
| `deactivate_document(collection, path)` | ❌ 无（软删除） | `UPDATE documents SET active=0 ...` |
| `get_active_document_paths(collection)` | ❌ 无 | 返回所有活跃 path 列表 |
| `get_hashes_for_embedding()` | ❌ 无 | LEFT JOIN 找未 embed 的 hash |
| `insert_embedding(hash, seq, pos, embedding, model, embedded_at)` | `update_content_embedding()` | 写入两张表 |
| `clear_all_embeddings()` | ❌ 无 | DELETE + DROP TABLE |
| `ensure_vec_table(dimensions)` | ❌ 无 | 动态创建/验证 vectors_vec |
| `cleanup_orphaned_vectors()` | ❌ 无 | 删孤立向量 |
| `cleanup_orphaned_content()` | ❌ 无 | 删孤立 content |
| `delete_llm_cache()` | ❌ 无 | DELETE FROM llm_cache |
| `delete_inactive_documents()` | ❌ 无 | DELETE WHERE active=0 |
| `vacuum_database()` | ❌ 无 | VACUUM |
| `get_cached_result(cache_key)` | ❌ 无 | SELECT FROM llm_cache |
| `set_cached_result(cache_key, result)` | ❌ 无 | INSERT OR REPLACE INTO llm_cache |
| `search_fts(query, limit, collection?)` | 在 `fts.py` 中 | 移入 manager 或保持在 fts.py，但修正 SQL |
| `search_vec(embedding, limit, collection?)` | 在 `vector.py` ChromaDB 实现 | 两步法 sqlite-vec 查询 |

### 3.2 `upsert_document` 的问题

现有的 `upsert_document` 在一个方法里混合了 `content` 和 `documents` 的写入，且用了 `ON CONFLICT DO UPDATE`。这与 TS 的设计不同：

**TS 的索引流程**：
1. `hashContent(doc)` → 得到 hash
2. `findActiveDocument(collection, path)` → 查询是否已存在
3. 若不存在：`insertContent()` + `insertDocument()`
4. 若已存在且 hash 变化：`insertContent()` + `updateDocument()`
5. 若已存在且 hash 相同：`updateDocumentTitle()`（仅更新 title 和 modified_at）

这样可以避免不必要地覆盖 `created_at`，并精确控制哪些字段需要更新。

---

## 4. 向量搜索实现方案

### 4.1 TS 的两步法查询（Python 必须遵循）

sqlite-vec 的 `vec0` 虚拟表**禁止与普通表 JOIN**，否则会挂死。TS 文档中有明确警告：

```typescript
// IMPORTANT: We use a two-step query approach here because sqlite-vec virtual tables
// hang indefinitely when combined with JOINs in the same query.
// See: https://github.com/tobi/qmd/pull/23
```

**两步法流程**：
```python
# Step 1: 仅从 vectors_vec 取 hash_seq + distance（不做 JOIN）
vec_rows = conn.execute("""
    SELECT hash_seq, distance
    FROM vectors_vec
    WHERE embedding MATCH ? AND k = ?
""", (query_embedding_bytes, limit * 3)).fetchall()

# Step 2: 根据 hash_seq 反查文档（JOIN 在此步做）
hash_seqs = [row['hash_seq'] for row in vec_rows]
placeholders = ','.join(['?'] * len(hash_seqs))
sql = f"""
    SELECT
        cv.hash || '_' || cv.seq as hash_seq,
        cv.hash,
        cv.pos,
        'qmd://' || d.collection || '/' || d.path as filepath,
        d.collection || '/' || d.path as display_path,
        d.title,
        content.doc as body
    FROM content_vectors cv
    JOIN documents d ON d.hash = cv.hash AND d.active = 1
    JOIN content ON content.hash = d.hash
    WHERE cv.hash || '_' || cv.seq IN ({placeholders})
"""
params = list(hash_seqs)
if collection_name:
    sql += " AND d.collection = ?"
    params.append(collection_name)
doc_rows = conn.execute(sql, params).fetchall()

# 同一文档取 bestDist，score = 1 - bestDist
```

### 4.2 Embedding bytes 格式

TS 传 `new Float32Array(embedding)` 给 sqlite-vec，Python 对应：

```python
import struct

def embedding_to_bytes(embedding: List[float]) -> bytes:
    """将 float 列表转换为 sqlite-vec 所需的 bytes 格式（float32 小端序）"""
    return struct.pack(f'{len(embedding)}f', *embedding)
```

### 4.3 `ensure_vec_table` 逻辑

```python
def ensure_vec_table(self, dimensions: int) -> None:
    """动态创建 vectors_vec 虚拟表，或验证现有表维度是否匹配。"""
    with self._get_connection() as conn:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='vectors_vec'"
        ).fetchone()
        if row:
            import re
            match = re.search(r'float\[(\d+)\]', row['sql'])
            existing_dims = int(match.group(1)) if match else None
            has_hash_seq = 'hash_seq' in row['sql']
            has_cosine = 'distance_metric=cosine' in row['sql']
            if existing_dims == dimensions and has_hash_seq and has_cosine:
                return  # 已存在且正确
            conn.execute("DROP TABLE IF EXISTS vectors_vec")
        
        conn.execute(f"""
            CREATE VIRTUAL TABLE vectors_vec USING vec0(
                hash_seq TEXT PRIMARY KEY,
                embedding float[{dimensions}] distance_metric=cosine
            )
        """)
        conn.commit()
```

---

## 5. FTS 搜索修正

### 5.1 FTS Schema 修改

```sql
-- 目标 FTS 表
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    filepath, title, body,
    tokenize='porter unicode61'
);

-- 目标 INSERT 触发器（仅 active=1 时插入）
CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents
WHEN new.active = 1
BEGIN
  INSERT INTO documents_fts(rowid, filepath, title, body)
  SELECT new.id,
         new.collection || '/' || new.path,
         new.title,
         (SELECT doc FROM content WHERE hash = new.hash)
  WHERE new.active = 1;
END;

-- 目标 DELETE 触发器
CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
  DELETE FROM documents_fts WHERE rowid = old.id;
END;

-- 目标 UPDATE 触发器（区分 active 变化）
CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents
BEGIN
  DELETE FROM documents_fts WHERE rowid = old.id AND new.active = 0;
  INSERT OR REPLACE INTO documents_fts(rowid, filepath, title, body)
  SELECT new.id,
         new.collection || '/' || new.path,
         new.title,
         (SELECT doc FROM content WHERE hash = new.hash)
  WHERE new.active = 1;
END;
```

### 5.2 FTS 搜索 SQL 修正

**当前 Python FTS 搜索**（`fts.py`）：
```sql
-- 问题：没有 bm25 列权重配置，列名不对（content 而非 body）
SELECT d.id, d.collection, d.path, d.hash, d.title, ...
FROM documents_fts
JOIN documents d ON documents_fts.rowid = d.id
JOIN content c ON d.hash = c.hash
WHERE documents_fts MATCH ? ORDER BY bm25(documents_fts)
```

**目标 FTS 搜索**（对齐 TS）：
```sql
-- filepath 权重 10.0（路径匹配更重要），title/body 权重 1.0
SELECT
    'qmd://' || d.collection || '/' || d.path as filepath,
    d.collection || '/' || d.path as display_path,
    d.title,
    content.doc as body,
    d.hash,
    bm25(documents_fts, 10.0, 1.0, 1.0) as bm25_score
FROM documents_fts f
JOIN documents d ON d.id = f.rowid
JOIN content ON content.hash = d.hash
WHERE documents_fts MATCH ? AND d.active = 1
  [AND d.collection = ?]
ORDER BY bm25_score ASC   -- bm25 越小越好（越负越相关）
LIMIT ?
```

---

## 6. 文件变更清单

### 6.1 需要修改的文件

| 文件 | 变更内容 | 影响范围 |
|------|---------|---------|
| `qmd/database/schema.py` | 完全重写 Schema/FTS/Triggers | 核心 |
| `qmd/database/manager.py` | 新增 ~15 个方法，修改 `_init_db`，加载 sqlite-vec | 核心 |
| `qmd/search/fts.py` | 修正 SQL（新列名、bm25 权重） | 搜索 |
| `qmd/search/vector.py` | 完全替换为 sqlite-vec 两步法 | 搜索 |
| `qmd/search/hybrid.py` | 调整结果字段名（对齐新格式） | 搜索 |
| `qmd/index/crawler.py` | 使用新的 `insert_content` / `insert_document` / `find_active_document` 方法 | 索引 |
| `qmd/server/app.py` | 更新 embed 和 vsearch 端点，使用新 DB 方法 | 服务器 |
| `pyproject.toml` | 删除 `chromadb`，新增 `sqlite-vec` | 依赖 |

### 6.2 新建文件

无需新建文件，但需要在 `manager.py` 中加入 sqlite-vec 加载逻辑。

---

## 7. 依赖变更

### 7.1 `pyproject.toml` 变更

**删除**：
```toml
"chromadb>=0.4.0",
```

**新增**：
```toml
"sqlite-vec>=0.1.6",
```

**已验证版本**：`sqlite-vec==0.1.6`（`pip install sqlite-vec` 安装成功）

### 7.2 sqlite-vec 加载方式

```python
import sqlite3
import sqlite_vec

def _get_connection(self):
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")  # 启用外键约束（TS 也有）
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn
```

---

## 8. 数据迁移说明

### 8.1 现有数据处理策略

由于 Schema 变化较大（删除列、新增表、修改 FTS 结构），**无法原地升级**，需要重新建库：

1. **内容数据**（`content` 表的 `hash`/`doc`）：可迁移，但需要重建
2. **文档元数据**（`documents` 表）：可迁移，但需填充 `created_at`
3. **向量数据**（ChromaDB）：**完全作废**，需要重新 `qmd embed`
4. **FTS 索引**：重建（触发器会自动维护）

### 8.2 迁移方案

**推荐方案**：删除旧库，重新索引

```bash
# 备份旧数据库
cp ~/.qmd/qmd.db ~/.qmd/qmd.db.bak

# 删除旧数据库和 ChromaDB
rm ~/.qmd/qmd.db
rm -rf ~/.qmd/vector_db/

# 重新索引
qmd index

# 重新生成向量
qmd embed
```

**原因**：文档内容本身在文件系统上，重新索引成本低；而 Schema 改动太多，原地迁移脚本复杂度高且风险大。

---

## 9. `chunkDocument` 实现

TS 中有完整的 `chunkDocument` 函数（`CHUNK_SIZE_CHARS=8000`, `CHUNK_OVERLAP_CHARS=200`），按段落/句子/行/词边界切分。Python 中索引器目前是否有 chunking 需要检查。

**TS 切分策略（优先级顺序）**：
1. 段落分隔（`\n\n`）
2. 句子结尾（`. `、`.\n`、`? `、`! ` 等）
3. 换行（`\n`）
4. 空格（` `）

Python 的 `embed` 命令需要实现相同的 chunking，才能保证向量搜索的 `pos` 字段意义一致。

---

## 10. 实施优先级建议

### Phase 1（核心 Schema + 基础 DB 方法）
1. 重写 `schema.py`（新 Schema、新 FTS、新 Triggers）
2. 重写 `manager.py` 的 `_init_db`（加载 sqlite-vec，新 Schema）
3. 新增基础 CRUD 方法（`insert_content`, `insert_document`, `find_active_document`, `update_document`, `deactivate_document`, `get_active_document_paths`）

### Phase 2（向量存储迁移）
4. 新增 `ensure_vec_table`, `insert_embedding`, `get_hashes_for_embedding`
5. 重写 `vector.py`（两步法 sqlite-vec 查询，替换 ChromaDB）
6. 新增 `clear_all_embeddings`, `cleanup_orphaned_vectors`

### Phase 3（维护功能 + FTS 修正）
7. 新增 `llm_cache` 相关方法（`get_cached_result`, `set_cached_result`, `delete_llm_cache`）
8. 新增维护方法（`delete_inactive_documents`, `cleanup_orphaned_content`, `vacuum_database`）
9. 修正 `fts.py` 的 SQL（新列名、bm25 权重配置）

### Phase 4（索引器 + 服务器对接）
10. 更新 `crawler.py`（使用新 DB 方法）
11. 更新 `app.py`（embed/vsearch 端点使用新 DB 方法）
12. 更新 `pyproject.toml`（换依赖）

---

## 11. 风险与注意事项

| 风险 | 说明 | 缓解措施 |
|------|------|---------|
| sqlite-vec 加载失败 | Windows 上 SQLite 可能不支持动态扩展加载 | sqlite-vec 的 Python 包内置了预编译的扩展，应该可以正常加载；已验证 |
| vec0 MATCH 挂死 | JOIN + MATCH 组合会死锁 | 严格使用两步法，加注释警告 |
| porter tokenizer 支持 | Python SQLite 内置版本可能不支持 porter | 需测试；FTS5 的 porter 是内置的，应该可用 |
| 数据丢失 | 迁移时向量数据需重建 | 提前备份，向量重建成本可接受 |
| `collections` 表是否保留 | TS 删除了它，Python CLI 依赖它 | 暂时保留，作为 YAML 迁移的过渡方案 |

---

## 附录：sqlite-vec 验证结果

```
✅ TEXT PRIMARY KEY 可用：
   INSERT INTO v VALUES ('abc_0', ?)
   SELECT hash_seq, distance FROM v WHERE embedding MATCH ? AND k=1
   → [('abc_0', 0.0)]

✅ 多条目查询：
   → [('hash1_0', 0.0), ('hash1_1', 0.031...), ('hash2_0', 0.456...)]
   距离排序正确，cosine distance 语义正确

✅ sqlite-vec 版本：0.1.6
✅ 安装命令：pip install sqlite-vec
```
