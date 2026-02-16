# QMD-Python 项目审计报告

**审计日期**: 2026-02-14
**审计人**: AI 项目接收方
**审计范围**: 全栈代码实现 vs 重构需求文档
**审计标准**: 01-06 系列需求文档

---

## 执行摘要

**总体评估**: ✅ **高度符合，部分增强**

当前 QMD-Python 实现与重构需求文档 **高度一致**，核心功能已完整实现，并在某些方面进行了合理增强。项目已经达到 **Milestone 1 (MVP)** 阶段，部分达到 **Milestone 2 (Vector Search)** 要求。

**符合度评分**: **85/100**

| 评估维度 | 符合度 | 状态 | 备注 |
|---------|--------|------|------|
| **功能需求 (FR-1~6)** | 95% | ✅ 优秀 | 所有核心功能已实现 |
| **架构设计** | 90% | ✅ 优秀 | 符合设计文档并有增强 |
| **数据模型** | 95% | ✅ 优秀 | Schema 完全符合并有扩展 |
| **LLM 集成** | 70% | ⚠️ 部分符合 | 技术栈不同但功能等同 |
| **测试覆盖** | 50% | ❌ 不足 | 基础测试存在，覆盖率未知 |
| **性能指标** | 40% | ❌ 不足 | 简单基准，无自动化回归检查 |
| **文档质量** | 100% | ✅ 优秀 | 需求文档完整详尽 |

---

## 详细审计结果

### 1. 数据库层 (Database Layer)

**对比文档**: `02-design-document.md` + `06-models.md`

#### 1.1 Schema 实现

**设计文档要求**:
```sql
-- Collections 配置
CREATE TABLE collections (
    name TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    glob_pattern TEXT NOT NULL,
    created_at TEXT,
    last_modified TEXT
);

-- 文档元数据
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection TEXT NOT NULL,
    path TEXT NOT NULL,
    hash TEXT NOT NULL,
    title TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT,
    modified_at TEXT,
    UNIQUE(collection, path)
);

-- 文档内容（hash 去重）
CREATE TABLE content (
    hash TEXT PRIMARY KEY,
    doc TEXT NOT NULL
);

-- 全文搜索索引 (BM25)
CREATE VIRTUAL TABLE documents_fts USING fts5(
    title,
    content,
    content=documents,
    docid=documents,
    tokenize='unicode61'
);

-- 路径上下文（层级）
CREATE TABLE path_contexts (
    collection TEXT,
    path TEXT,
    context TEXT,
    PRIMARY KEY (collection, path)
);
```

**实际实现** (`qmd/database/schema.py`):
```sql
✅ 完全符合设计文档
✅ 额外字段:
  - documents.context: 存储路径上下文
  - content.embedding: 缓存向量嵌入（设计为 ChromaDB 存储）
✅ 自动触发器: 保持 FTS 索引同步
✅ 安全约束: IF NOT EXISTS 防止重复创建
```

**符合度**: **95%** (完全符合 + 有益增强)

**增强点**:
1. **context 字段** - 文档表直接存储上下文，简化查询
2. **embedding BLOB** - content 表缓存嵌入，加速向量搜索
3. **自动触发器** - FTS 索引自动同步，无需手动维护

**潜在问题**:
- ⚠️ **设计差异**: embedding 缓存在 SQLite vs ChromaDB
  - 设计文档: 向量存储在 ChromaDB
  - 实际: SQLite 也缓存 (BLOB)
  - **影响**: 数据冗余，但提高查询速度
  - **建议**: 保持现状（性能优化），但需文档说明

#### 1.2 DatabaseManager 实现

**设计文档要求**:
- CRUD 操作: insert, update, delete, select
- 事务管理: WAL 模式，原子操作
- 上下文管理: 添加、删除、查询

**实际实现** (`qmd/database/manager.py`):
```python
✅ 完整 CRUD:
  - add_collection()
  - upsert_document()  # ON CONFLICT 处理
  - get_document_by_path/hash()
  - rename_collection()  # 级联更新

✅ 上下文管理:
  - set_path_context()
  - get_context_for_path()  # 继承逻辑
  - list_path_contexts()
  - remove_path_context()

✅ 统计查询:
  - get_stats()
  - get_detailed_stats()

✅ 嵌入管理:
  - update_content_embedding()
```

**符合度**: **95%**

**优点**:
1. **上下文继承**: `get_context_for_path()` 实现了层级继承
2. **事务安全**: 所有写操作使用 `with` 上下文管理器
3. **原子操作**: `upsert_document()` 使用 `ON CONFLICT`
4. **级联更新**: `rename_collection()` 正确更新 3 个表

**改进建议**:
- ⚠️ **缺失**: WAL 模式未显式启用
  ```python
  # 建议添加:
  conn.execute("PRAGMA journal_mode=WAL")
  conn.execute("PRAGMA synchronous=NORMAL")
  ```

---

### 2. 搜索层 (Search Layer)

**对比文档**: `02-design-document.md` (搜索管道章节)

#### 2.1 BM25 (FTS) Search

**设计文档要求**:
- 算法: BM25 (SQLite FTS5)
- 查询语法: 短语、布尔、否定
- 返回: snippet（高亮）、score
- 性能: <50ms (10k docs)

**实际实现** (`qmd/search/fts.py`):
```python
✅ 使用 FTS5 BM25 排序
✅ 查询清理: 转义特殊字符
✅ 简单 snippet: 基于关键词查找
✅ 错误处理: 降级到简单查询
```

**符合度**: **85%**

**优点**:
1. **稳健性**: 查询清理避免 FTS5 语法错误
2. **排序**: 正确使用 `bm25()` 函数
3. **降级策略**: 失败时返回空结果而非崩溃

**问题与改进**:
1. ❌ **Snippet 不符合设计**:
   ```python
   # 设计文档要求:
   snippet(content.doc, -2, '<b>', '</b>', 30)
   
   # 实际实现 (lines 49-57):
   start = content.lower().find(query.lower())
   snippet = content[max(0, start-30):start+len(query)+30]
   ```
   - **问题**: 不使用 FTS5 内置 `snippet()` 函数
   - **影响**: 没有真正的高亮、上下文不准确
   - **修复**: 修改 SQL 查询添加 snippet 列

2. ⚠️ **性能验证缺失**:
   - 无自动化基准测试
   - 无 p95/p99 延迟统计

#### 2.2 Vector Search

**设计文档要求**:
- 算法: Cosine similarity
- 存储: ChromaDB 持久化
- 维度: 384-dim
- 性能: <500ms (10k docs)

**实际实现** (`qmd/search/vector.py`):
```python
✅ ChromaDB 集成:
  - PersistentClient
  - hnsw:space="cosine"
  - 集合/查询/添加文档

✅ SearchResult 模型
✅ LLM 集成 (embed_texts, embed_query)
✅ 相似度转换: 1.0 - distance
```

**符合度**: **90%**

**优点**:
1. **ChromaDB**: 符合设计文档选择
2. **持久化**: `PersistentClient` 非内存
3. **模型正确**: Cosine 相似度
4. **封装良好**: `add_documents()`, `search()` 清晰

**改进建议**:
- ⚠️ **性能验证**: 无自动化基准测试

#### 2.3 Hybrid Search (RRF)

**设计文档要求**:
- 算法: Reciprocal Rank Fusion (RRF), k=60
- 融合: FTS + Vector + Rerank
- 返回: 融合后排序结果

**实际实现** (`qmd/search/hybrid.py`):
```python
✅ RRF 实现: score = 1 / (k + rank), k=60
✅ 并行搜索: FTS + Vector
✅ 结果融合: defaultdict(float) 累积分数
✅ 类型标记: "fts", "vector", "hybrid"
```

**符合度**: **90%**

**优点**:
1. **RRF 正确**: 符合设计文档公式
2. **文档标识**: `{collection}:{path}` 唯一
3. **类型标记**: 清晰标记结果来源
4. **排序正确**: 按分数降序

**改进建议**:
- ⚠️ **查询扩展未集成**:
  - 设计文档: LLM 生成 2-3 个查询变体
  - 实现: `search()` 只接受单个 query
  - **位置**: 应在 HybridSearcher.search() 中调用

---

### 3. LLM 集成 (LLM Integration)

**对比文档**: `02-design-document.md` (LLM 章节) + `06-models.md`

#### 3.1 模型选择

**设计文档要求**:
- Embedding: `embeddingemma-2b` (300MB, 384-dim, Q8_0)
- Reranking: `qwen3-reranker` (640MB, Q8_0)
- Expansion: `qwen3-query-expansion` (1.1GB, Q4_K_M)
- 总计: ~2GB

**实际实现** (`qmd/llm/engine.py`):
```python
❌ 技术栈不同:
- 设计: llama-cpp-python (GGUF 格式)
- 实现: fastembed + transformers (PyTorch)

✅ 模型选择:
- Embedding: BAAI/bge-small-en-v1.5 (130MB, 384-dim)
- Reranking: cross-encoder/ms-marco-MiniLM-L-6-v2
- Expansion: Gemini API (gemini-2.0-flash)
```

**符合度**: **70%** (功能等同，技术栈不同)

**差异分析**:

| 维度 | 设计文档 | 实际实现 | 影响 |
|------|---------|---------|------|
| **格式** | GGUF (量化) | PyTorch | 文件大小 + 依赖 |
| **Embedding** | embeddingemma | bge-small | 质量 ~相当 |
| **Reranking** | qwen3-reranker | ms-marco | 质量 ~相当 |
| **Expansion** | qwen3 (本地) | Gemini (云) | **隐私问题** |

**关键问题**:
1. ❌ **隐私/NFR-5 违反**:
   - 设计: "所有操作本地运行...无网络调用"
   - 实现: Gemini API 调用 (需要网络 + API key)
   - **严重性**: 高 - 破坏本地承诺

2. ⚠️ **依赖复杂度**:
   - 设计: llama-cpp-python (C++ 绑定，纯 CPU)
   - 实现: transformers + PyTorch (更多依赖，GPU 支持)
   - **影响**: 安装更复杂

3. ✅ **模型质量**:
   - bge-small: State-of-art，优于 embeddingemma
   - ms-marco: 经过微调的 reranker

**建议**:
1. **必须修复**: 移除 Gemini 依赖，使用本地模型
   - 方案 A: llama-cpp-python + qwen3-query-expansion (符合设计)
   - 方案 B: transformers + 本地 qwen3 (保留技术栈，移除 API 调用)

2. **可接受**: embedding/reranker 使用 transformers
   - 质量更高
   - 但需文档说明为什么偏离设计

#### 3.2 LLM Engine 功能

**实际实现** (`qmd/llm/engine.py`):
```python
✅ 批量嵌入: embed_texts()
✅ 单查询嵌入: embed_query()
✅ 模型缓存: _ensure_model()
✅ 线程配置: threads
✅ 缓存目录: cache_dir
```

**符合度**: **85%**

**优点**:
1. **FastEmbed**: 高性能批处理
2. **缓存管理**: 模型加载一次
3. **线程安全**: 可配置线程数

**改进**:
- ❌ **缺失**: 模型下载进度条
  - 设计: "显示 chunk 计数 + ETA"
  - 实现: 静默下载

---

### 4. CLI 层 (CLI Layer)

**对比文档**: `02-design-document.md` + `03-requirements.md`

#### 4.1 命令实现

**设计文档要求** (FR-1~6):

| 命令 | 参数 | 设计要求 | 实现状态 |
|------|------|---------|---------|
| `collection add` | path, --name, --glob | ✅ 完全符合 | ✅ |
| `collection list` | - | ✅ 完全符合 | ✅ |
| `collection remove` | name | ✅ 确认提示 | ✅ |
| `collection rename` | old, new | ✅ 更新虚拟路径 | ✅ |
| `index` | - | ✅ 扫描 + 去重 | ✅ |
| `update` | --pull | ✅ Git 集成 | ✅ |
| `search` | query | ✅ BM25 + snippet | ⚠️ 简单 snippet |
| `vsearch` | query, --collection, --limit | ✅ 语义搜索 | ✅ |
| `query` | query, --rerank/--no-rerank | ✅ 混合 + 重排 | ✅ |
| `get` | hash/path:lines, -l, --line-numbers | ✅ 完全符合 | ✅ |
| `ls` | [collection/]path | ✅ ls -l 风格 | ✅ |
| `status` | - | ✅ 详细统计 | ✅ |
| `embed` | --collection | ✅ 批量 + 进度 | ✅ |
| `context add` | --collection, --path, text | ✅ 自动检测 | ✅ |
| `context list` | --collection | ✅ 完全符合 | ✅ |
| `context remove` | --collection, --path | ✅ 完全符合 | ✅ |
| `context check` | - | ✅ 缺失检查 | ✅ |
| `multi-get` | pattern, --max-bytes, --json/--md/--files | ✅ 完全符合 | ✅ |

**符合度**: **98%**

**优点**:
1. **命令完整**: 所有 FR-1~6 命令已实现
2. **参数正确**: 所有选项符合设计
3. **错误处理**: 路径不存在、名称冲突等
4. **用户体验**: Rich 格式化、彩色输出
5. **特殊命令**:
   - `update --pull`: Git 集成
   - `context check`: 缺失检查建议
   - `multi-get`: 多种输出格式

**改进建议**:
- ⚠️ **snippet**: 如前述，应为 FTS5 snippet()
- ⚠️ **进度条**: `embed` 命令有基础进度，可增强
  - 设计: "Embedding 1200/5000 chunks [====> ] 24% ETA: 2m"
  - 实现: 简单计数，无 ETA

---

### 5. 测试覆盖 (Testing Coverage)

**对比文档**: `04-testing.md`

#### 5.1 测试结构

**设计文档要求**:
```
tests/
├── unit/           # 单元测试
│   ├── test_database.py
│   ├── test_search.py
│   └── test_llm.py
├── integration/    # 集成测试
│   └── test_workflow.py
└── benchmarks/     # 性能测试
    └── bench_search.py
```

**实际结构**:
```
tests/
├── unit/
│   ├── test_search.py      ✅ 存在
│   ├── test_search_ext.py  ✅ 额外
│   ├── test_rerank.py      ✅ 存在
│   ├── test_contexts.py    ✅ 存在
│   ├── test_config.py      ✅ 存在
│   └── test_core.py        ✅ 存在
├── integration/
│   └── test_cli.py        ✅ 存在
└── benchmarks/
    └── search_bench.py     ✅ 存在
```

**符合度**: **80%**

**优点**:
1. **测试分类**: unit/integration/benchmarks 分离
2. **关键测试**: search, rerank, contexts, config
3. **集成测试**: CLI 工作流

**缺失与改进**:

1. ❌ **数据库测试缺失**:
   - 设计要求: `test_database.py`
   - 实际: 无独立文件
   - **影响**: Schema, CRUD 未单独验证

2. ❌ **覆盖率未知**:
   - 设计目标: >80%
   - 实现: 无 `pytest-cov` 配置
   - **建议**: 运行 `pytest --cov=qmd --cov-report=html`

3. ⚠️ **基准测试简陋**:
   - 设计要求: `pytest-benchmark`
   - 实现: 手动 `time.time()`
   - **缺失**:
     - p95/p99 统计
     - 多轮次 (min_rounds)
     - 自动回归检查
   - **建议**: 重写为 pytest-benchmark 格式

4. ❌ **性能目标未验证**:
   - 设计: BM25 <50ms, Vector <500ms
   - 实现: 简单打印时间
   - **建议**: 添加断言
     ```python
     @pytest.mark.benchmark(min_rounds=10)
     def test_bm25_perf(benchmark, large_db):
         results = search_fts(db, query)
         assert benchmark.stats["median"] < 0.05  # <50ms
     ```

#### 5.2 CI/CD

**设计文档要求**:
- GitHub Actions matrix: Windows/macOS/Linux × Python 3.10/3.11/3.12
- 自动化: 测试 + 基准
- 回归检查: <1.2x baseline

**实际**: **无 CI/CD 配置**

**符合度**: **0%**

**建议**:
1. 添加 `.github/workflows/test.yml`
2. 添加 `pytest-benchmark-autosave` + 回归检查脚本

---

### 6. 性能指标 (Performance Metrics)

**对比文档**: `05-metrics.md`

#### 6.1 目标验证

**设计文档目标**:

| 操作 | 目标 (p95) | 验证状态 |
|------|------------|---------|
| **BM25 Search** | <50ms (10k docs) | ❌ 未自动化验证 |
| **Vector Search** | <500ms (10k docs) | ❌ 未自动化验证 |
| **Hybrid Search** | <3s (10k docs) | ❌ 未自动化验证 |
| **Indexing** | >100 files/s | ❌ 未自动化验证 |

**实际实现** (`tests/benchmarks/search_bench.py`):
```python
❌ 问题:
1. 无断言验证
2. 无 p95/p99 统计
3. 手动 time.time() 测量
4. 无数据集准备 (10k docs)
5. 无自动回归检查
```

**符合度**: **20%**

**关键缺失**:
1. **数据集**: 无 100/1k/10k/100k 文档数据集
2. **统计**: 无中位数、百分位数
3. **自动化**: 无 CI 集成
4. **回归**: 无 baseline 比较

**建议**:
1. 使用 `pytest-benchmark`
2. 生成测试数据集
3. 添加性能断言
4. 集成 CI/CD

---

### 7. 文档质量 (Documentation)

**对比**: 需求文档本身

**评估**: ✅ **100%**

**优点**:
1. **完整性**:
   - 根因分析 (01)
   - 架构设计 (02)
   - 需求规格 (03)
   - 测试策略 (04)
   - 性能指标 (05)
   - 模型规范 (06)

2. **详尽性**:
   - 用例 (User Stories)
   - 示例 (代码片段)
   - 表格 (性能、配置)
   - 决策矩阵 (技术选型)

3. **可追溯性**:
   - FR/NFR 编号
   - 设计 → 需求映射
   - 实现清单 (Milestones)

---

## 优先级改进清单

### P0 - 必须修复 (阻塞发布)

1. **隐私/NFR-5**:
   - ❌ 移除 Gemini API 依赖
   - ✅ 使用本地模型 (llama-cpp-python 或 transformers)
   - **影响**: 破坏"本地运行"承诺

2. **Snippet 功能**:
   - ❌ 修复 FTS snippet 使用 `snippet()` 函数
   - **文件**: `qmd/search/fts.py`

3. **WAL 模式**:
   - ❌ 启用 SQLite WAL 模式
   - **文件**: `qmd/database/manager.py`
   - **代码**: `conn.execute("PRAGMA journal_mode=WAL")`

### P1 - 高优先级 (影响质量)

4. **测试覆盖**:
   - ❌ 添加 `pytest-cov`
   - ❌ 添加数据库单元测试
   - ❌ 验证覆盖率 >80%

5. **性能验证**:
   - ❌ 使用 `pytest-benchmark`
   - ❌ 添加性能断言
   - ❌ 准备测试数据集

6. **CI/CD**:
   - ❌ 添加 GitHub Actions
   - ❌ 自动化测试 + 基准

### P2 - 中优先级 (改进体验)

7. **进度条增强**:
   - ⚠️ `embed` 添加 ETA
   - ⚠️ 模型下载进度

8. **文档**:
   - ⚠️ 说明技术栈偏离原因
   - ⚠️ 添加性能基准结果

---

## 符合度总结

| 层级 | 符合度 | 评分 | 主要问题 |
|------|--------|------|---------|
| **数据库** | 95% | ✅ 优秀 | embedding 缓存策略需文档 |
| **搜索** | 85% | ✅ 良好 | snippet 实现不符合设计 |
| **LLM** | 70% | ⚠️ 可接受 | **隐私问题** (Gemini API) |
| **CLI** | 98% | ✅ 优秀 | 微小细节 |
| **测试** | 50% | ❌ 不足 | **无覆盖率报告** |
| **性能** | 40% | ❌ 不足 | **无自动化验证** |
| **文档** | 100% | ✅ 优秀 | - |

**总体符合度**: **85/100**

---

## 结论与建议

### 结论

**当前状态**: QMD-Python 项目已达到 **MVP 基本完成**，核心功能完整，符合大部分设计文档要求。

**主要成就**:
1. ✅ **架构正确**: 符合设计文档
2. ✅ **功能完整**: 所有 FR-1~6 实现
3. ✅ **代码质量**: 良好的封装和错误处理
4. ✅ **用户体验**: Rich CLI，良好的输出

**关键问题**:
1. ❌ **隐私**: Gemini API 破坏本地承诺
2. ❌ **测试**: 无自动化覆盖率和性能验证
3. ⚠️ **性能**: 无基准回归保护

### 建议

**短期 (1-2 周)**:
1. **修复 P0**:
   - 移除 Gemini 依赖
   - 修复 snippet
   - 启用 WAL 模式

2. **添加测试**:
   - pytest-cov 配置
   - 数据库单元测试
   - 验证覆盖率 >60% (短期目标)

**中期 (2-4 周)**:
1. **完善性能**:
   - pytest-benchmark 集成
   - 添加性能断言
   - 准备测试数据集

2. **CI/CD**:
   - GitHub Actions 配置
   - 自动化测试
   - 回归检查

**长期 (4 周+)**:
1. **增强体验**:
   - 进度条优化
   - 错误提示改进
   - 文档完善

2. **发布准备**:
   - PyPI 打包
   - README 完善
   - 性能基准报告

---

## 附录

### A. 文件清单

**符合设计文档的文件**:
```
qmd/
├── cli.py                  ✅ 符合
├── database/
│   ├── schema.py          ✅ 符合 + 增强
│   └── manager.py         ✅ 符合
├── search/
│   ├── fts.py             ✅ 符合 (snippet 修复)
│   ├── vector.py          ✅ 符合
│   ├── hybrid.py          ✅ 符合
│   └── rerank.py         ✅ 符合 (技术栈不同)
├── llm/
│   └── engine.py          ⚠️ 技术栈不同 + 隐私问题
├── index/
│   └── crawler.py         ✅ 符合 (需验证)
└── models/
    └── config.py          ✅ 符合
```

### B. 技术栈对比

| 组件 | 设计文档 | 实际实现 | 符合 |
|------|---------|---------|------|
| **CLI** | click + rich | click + rich | ✅ |
| **数据库** | sqlite3 | sqlite3 | ✅ |
| **FTS** | SQLite FTS5 | SQLite FTS5 | ✅ |
| **向量** | ChromaDB | ChromaDB | ✅ |
| **Embedding** | llama-cpp + GGUF | fastembed + PyTorch | ⚠️ |
| **Reranking** | llama-cpp + GGUF | transformers | ⚠️ |
| **Expansion** | llama-cpp + GGUF | Gemini API | ❌ |

### C. 测试状态

| 测试类型 | 设计要求 | 实际状态 | 缺失 |
|---------|---------|---------|------|
| 单元测试 | test_database.py | ❌ 无 | Schema/CRUD 验证 |
| | test_search.py | ✅ 存在 | - |
| | test_llm.py | ⚠️ 部分 (rerank) | embedding 测试 |
| 集成测试 | test_workflow.py | ✅ test_cli.py | 完整工作流 |
| 基准测试 | pytest-benchmark | ❌ 手动 time.time() | p95/p99 |

---

**审计完成**

**下一步行动**:
1. 与团队审查审计报告
2. 确定 P0 修复优先级
3. 创建 Issue 跟踪改进项
4. 安排代码审查会议

---

**审计人签名**: AI 项目接收方
**日期**: 2026-02-14
