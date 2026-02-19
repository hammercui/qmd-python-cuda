# TypeScript vs Python 实现差距分析

> 生成时间：2026-02-19  
> 目的：逐命令、逐算法对比原始 TypeScript 实现（`D:\MoneyProjects\qmd\src\`）与 Python 版本（`qmd/`）的差异，供后续统一修复参考。  
> **架构约束（不变）**：Python 保留 server-client 架构；所有 LLM/Embedding 资源由 server 单例持有，client 通过 HTTP 调用；资源争用时 asyncio.Lock 等待。其他流程和算法必须与 TS 版本一模一样。

---

## 目录

1. [BM25 分数归一化](#1-bm25-分数归一化)
2. [FTS 查询构建（buildFTS5Query）](#2-fts-查询构建buildfts5query)
3. [Embedding 格式化（formatDocForEmbedding / formatQueryForEmbedding）](#3-embedding-格式化)
4. [文档分块（chunkDocument）](#4-文档分块chunkdocument)
5. [embed 命令（vectorIndex）](#5-embed-命令vectorindex)
6. [RRF 算法（reciprocalRankFusion）](#6-rrf-算法reciprocalrankfusion)
7. [query 命令（querySearch）全流程](#7-query-命令querysearch全流程)
8. [vsearch 命令（vectorSearch）](#8-vsearch-命令vectorsearch)
9. [search 命令（search）](#9-search-命令search)
10. [Query Expansion（expandQueryStructured）](#10-query-expansionexpandquerystructured)
11. [Rerank（rerank）](#11-rerankrerank)
12. [cleanup 命令](#12-cleanup-命令)
13. [context 命令接口差异](#13-context-命令接口差异)
14. [collection add 命令](#14-collection-add-命令)
15. [输出格式（outputResults）](#15-输出格式outputresults)
16. [min-score 默认值](#16-min-score-默认值)
17. [缺失功能汇总](#17-缺失功能汇总)

---

## 1. BM25 分数归一化

### TS 实现（`store.ts` `searchFTS`）

```typescript
// SQLite FTS5 bm25() 返回负数，越小（绝对值越大）越相关
// 转换为 (0, 1] 区间，越大越相关，且不依赖 per-query 归一化
// 这样 topScore >= 0.85 的"强信号"判断才有意义
const score = 1 / (1 + Math.abs(row.bm25_score));
```

同时 SQL 使用**加权 bm25**：
```sql
bm25(documents_fts, 10.0, 1.0) as bm25_score
-- 列权重：title 权重 10，content 权重 1
```

### Python 实现（`qmd/search/fts.py`）

```python
# 无分数字段，只有 rank（从 1 开始的整数序号）
res["rank"] = i
# SQL 使用无权重 bm25：
ORDER BY bm25(documents_fts)
```

### 差距

| 维度 | TS | Python | 影响 |
|------|-----|--------|------|
| SQL bm25 权重 | `bm25(..., 10.0, 1.0)` 标题权重×10 | 无权重 | 标题匹配优先级缺失 |
| 分数归一化 | `1/(1+abs(bm25_score))` → (0,1] | 无归一化（只有 rank 整数） | 强信号判断（≥0.85）完全失效 |
| 字段名 | `score` | `rank` | query pipeline 无法比较分数阈值 |

### 修复要点

- `fts.py` SQL 加 `bm25(documents_fts, 10.0, 1.0)` 权重
- 返回 `score = 1 / (1 + abs(bm25_score))` 替代 `rank`
- `hybrid.py` 和 `app.py` 中所有引用 `r["rank"]` 的地方改为 `r["score"]`

---

## 2. FTS 查询构建（buildFTS5Query）

### TS 实现（`store.ts`）

```typescript
function buildFTS5Query(query: string): string | null {
  const terms = query.split(/\s+/)
    .map(t => sanitizeFTS5Term(t))
    .filter(t => t.length > 0);
  if (terms.length === 0) return null;
  if (terms.length === 1) return `"${terms[0]}"*`;         // 前缀匹配
  return terms.map(t => `"${t}"*`).join(' AND ');           // 多词 AND + 前缀
}
```

特点：每个词加 `*` 实现**前缀匹配**；多词用 `AND` 连接。

### Python 实现（`qmd/search/fts.py`）

```python
sanitized_query = query.replace('"', '""')
fts_query = f'"{sanitized_query}"'   # 整句作为短语匹配，无前缀
```

### 差距

| 维度 | TS | Python |
|------|-----|--------|
| 多词处理 | 每词独立 `"term"*`，用 AND 连接 | 整句作为一个短语 `"full query"` |
| 前缀匹配 | ✅ 有 `*` | ❌ 无 |
| sanitize | `sanitizeFTS5Term()` 逐词处理 | 只替换 `"` |

### 修复要点

- `fts.py` 改为逐词 sanitize + `"term"*` + `AND` 拼接
- 单词时返回 `"term"*`，多词时 `"t1"* AND "t2"*`

---

## 3. Embedding 格式化

### TS 实现（`llm.ts`）

```typescript
// 查询 embedding 加前缀
export function formatQueryForEmbedding(query: string): string {
  return `task: search result | query: ${query}`;
}

// 文档 embedding 加标题前缀
export function formatDocForEmbedding(text: string, title?: string): string {
  return `title: ${title || "none"} | text: ${text}`;
}
```

这两个格式化函数与 `embeddingemma-300M` 模型的训练格式对齐（见 `docs/requirement/06-models.md`）。

### Python 实现（`qmd/search/vector.py` 和 `qmd/cli.py`）

```python
# embed 时直接传原始内容，无任何格式化
contents = [doc["content"] for doc in to_embed]
embeddings = vsearch.llm.embed_texts(contents)

# 查询时也直接传原始文本
embeddings = [self._embed_fn(text) for text in contents]
```

### 差距

| 维度 | TS | Python |
|------|-----|--------|
| 查询 embedding | `task: search result | query: {q}` | 原始文本 |
| 文档 embedding | `title: {t} | text: {content}` | 原始内容 |
| 模型对齐 | ✅ 与 embeddinggemma 训练格式一致 | ❌ 格式不匹配，召回率下降 |

**注意**：当前 Python 使用 `fastembed` 的 `BAAI/bge-small-en-v1.5` 模型，该模型不使用上述格式。  
若切换为 `embeddingemma-300M-GGUF`（`llama-cpp-python`），则必须加格式化。  
当前阶段的修复优先级取决于是否切换 embedding 模型（见[第 5 节](#5-embed-命令vectorindex)）。

---

## 4. 文档分块（chunkDocument）

### TS 实现（`store.ts`）

```
CHUNK_SIZE_TOKENS = 800
CHUNK_OVERLAP_TOKENS = 120  （15%）
CHUNK_SIZE_CHARS = 3200
CHUNK_OVERLAP_CHARS = 480
```

分块逻辑：
1. 从文本末尾 30% 区间找最优断点（优先级：段落 `\n\n` > 句子 `.?!` > 换行 > 空格）
2. 每块向前重叠 480 字符（`charPos = endPos - overlapChars`）
3. 防无限循环：若 overlap 后位置未前进则强制前移

实际 embed 使用 `chunkDocumentByTokens()`（真实 token 计数版本）。

### Python 实现（`qmd/cli.py` embed 命令）

```python
# 无分块！整个文档内容直接作为一个 embedding
contents = [doc["content"] for doc in to_embed]
embeddings = vsearch.llm.embed_texts(contents)
```

ChromaDB 中每个文档只有 1 个 embedding（`id = collection:path`）。

### 差距

| 维度 | TS | Python |
|------|-----|--------|
| 分块策略 | 800 token，15% overlap | ❌ 无分块，整文档 1 个 embedding |
| 长文档支持 | ✅ 多 chunk，向量搜索精准 | ❌ 长文档截断/质量差 |
| chunk 序号 | `seq`, `pos` 存入 DB | ❌ 无 |
| embed ID | `hash_chunk_seq` 格式 | `collection:path` 格式 |

### 修复要点

- `cli.py` embed 命令改为先 `chunkDocument(content)` 分块
- ChromaDB ID 改为 `{collection}:{path}:{seq}`
- 向量搜索结果去重（同文档取 best chunk）

---

## 5. embed 命令（vectorIndex）

### TS 实现（`qmd.ts` `vectorIndex`）

1. `--force` 时先清空所有向量
2. 按 hash 去重（多个 collection 共享同文档只 embed 一次）
3. **真实 token 计数分块**（`chunkDocumentByTokens`，调用 tokenizer）
4. 格式化：`formatDocForEmbedding(chunk.text, title)`
5. 批量 embed，BATCH_SIZE=32
6. 每 chunk 单独存入 `vectors_vec`（sqlite-vec）

### Python 实现（`qmd/cli.py` embed）

1. ✅ 支持 `--collection` 过滤
2. ✅ 有 embedding 缓存（检查 DB 中已有 embedding）
3. ❌ 无分块
4. ❌ 无格式化前缀
5. ❌ 逐条 embed（非批量）→ 实际上调 `embed_texts(contents)` 是批量，但整文档
6. ❌ ChromaDB 存储（而非 sqlite-vec）

**架构说明**：Python 使用 ChromaDB 而非 sqlite-vec，这是有意设计，不需要改变存储引擎，但分块逻辑和格式化需要补齐。

### 差距汇总

| 功能 | TS | Python |
|------|-----|--------|
| `--force` 清空 | ✅ | ❌ 缺 |
| 按 hash 去重 | ✅ | ✅（检查 embedding 缓存） |
| 分块 | ✅ 800 token | ❌ 无 |
| 格式化前缀 | ✅ | ❌ |
| 批量 embed | ✅ batch=32 | ✅（整文档批量） |
| 存储 | sqlite-vec | ChromaDB（可接受） |

---

## 6. RRF 算法（reciprocalRankFusion）

### TS 实现（`store.ts`）

```typescript
// rank 从 0 开始（rank+1 才是 1-indexed 分母）
const rrfContribution = weight / (k + rank + 1);

// ✨ 关键：Top-rank bonus（Python 没有！）
for (const entry of scores.values()) {
  if (entry.topRank === 0) entry.rrfScore += 0.05;     // 第 1 名加 bonus
  else if (entry.topRank <= 2) entry.rrfScore += 0.02; // 前 3 名加小 bonus
}
```

同时维护 `topRank`（该文档在任意列表中出现的最好排名）。

### Python 实现（`qmd/search/hybrid.py` 和 `app.py`）

```python
# rank 从 1 开始（enumerate(ids, 1)）
rrf_scores[did] += w / (k + rank)

# ❌ 无 top-rank bonus
```

### 差距

| 维度 | TS | Python |
|------|-----|--------|
| rank 起始 | 0-indexed（分母 k+rank+1） | 1-indexed（分母 k+rank） |
| top-rank bonus | ✅ 第1名 +0.05，前3名 +0.02 | ❌ 无 |

**数值影响**：两者的 RRF 分数不同，但排名顺序在大多数情况下相近。top-rank bonus 是关键差异，会影响强相关结果的排名。

### 修复要点

- `hybrid.py` 的 RRF 改为 `w / (k + rank + 1)`（rank 从 0 开始）
- 加入 top-rank bonus 逻辑
- `app.py` 的加权 RRF 同步修改

---

## 7. query 命令（querySearch）全流程

### TS 实现（`qmd.ts` `querySearch`）详细步骤

```
① 初始 BM25（limit=20）→ 计算 topScore/secondScore
② 强信号检测：topScore >= 0.85 AND (topScore - secondScore) >= 0.15 → 跳过 LLM expansion
③ Query Expansion（弱信号时）：
   - expandQueryStructured(query, includeLexical=true)
   - lex 类型变体 → ftsQueries
   - vec/hyde 类型变体 → vectorQueries
④ 并发搜索（Promise.all）：所有 ftsQueries → BM25；所有 vectorQueries → Vector
⑤ 加权 RRF（前2个列表权重×2，其余×1）
   - 前2个列表 = 原始 query 的 FTS + 原始 query 的 Vector
⑥ 取 top-40 候选
⑦ 对每个候选选 best chunk（按 queryTerms 命中数）
⑧ LLM cross-encoder rerank（只 rerank 1 chunk/doc，best chunk）
⑨ 位置感知 blending（rrfRank 1-3: 75%RRF+25%rerank；4-10: 60/40；11+: 40/60）
   - rrfScore = 1 / rrfRank（直接用名次倒数，非 RRF 累积分）
⑩ 去重（按 file path）
⑪ 输出
```

### Python 实现（`qmd/server/app.py` `/query` endpoint，本次已改）

```
① Query Expansion（全部走，无强信号检测）
② 多路 BM25 + Vector（所有变体）
③ 加权 RRF（原始 query 权重×2）
④ LLM rerank（整文档内容，非 best chunk）
⑤ 位置感知 blending（使用 RRF 累积分 rrf_s，非 1/rrfRank）
```

### 差距

| 步骤 | TS | Python（当前） |
|------|-----|--------|
| 强信号检测 | ✅ topScore≥0.85 跳过 expansion | ❌ 无（需 BM25 归一化分数先修复）|
| 搜索并发 | `Promise.all`（FTS+Vector 并发） | for 循环顺序执行 |
| 候选 chunk 选择 | per-doc best chunk（queryTerms 命中数）| ❌ 直接用整文档 content |
| Rerank 输入 | best chunk text | 整文档 content（可能很长/截断）|
| rrfScore in blending | `1/rrfRank`（1-indexed rank 倒数）| `rrf_scores[id]`（RRF 累积分）|
| rerank score 归一化 | llama-cpp ranking API 返回 [0,1] | sigmoid 归一化 logit（可接受）|
| 去重 | ✅ seenFiles Set | ❌ 无去重 |

### 修复要点（优先级最高）

1. 强信号检测：需要先修复 BM25 分数归一化（差距#1）
2. best chunk 选择逻辑（需要先修复分块，差距#4）
3. blending 中 `rrfScore = 1 / rrfRank` 替代 RRF 累积分
4. 结果去重
5. 可选：改为 asyncio.gather 并发

---

## 8. vsearch 命令（vectorSearch）

### TS 实现（`qmd.ts` `vectorSearch`）

1. `expandQueryStructured(query, includeLexical=false)` → 只生成 vec/hyde 变体（不生成 lex）
2. 所有向量 query **顺序执行**（注释说明：并发会导致 LlamaEmbeddingContext 挂起）
3. 同一文档取 **最高分**（best score across queries）
4. 排序后 limit
5. 默认 min-score = 0.3

### Python 实现（`qmd/cli.py` `vsearch`）

```python
client.vsearch(query, limit=limit, collection=collection)
# server 端：直接单次向量搜索，无 expansion
```

### 差距

| 维度 | TS | Python |
|------|-----|--------|
| Query expansion | ✅ vec/hyde 变体（不含 lex） | ❌ 无 expansion |
| 多 query 搜索 | ✅ 顺序执行多次 | ❌ 单次 |
| 去重取最高分 | ✅ | ❌ |
| 默认 min-score | 0.3 | 0.0（在 models.py VSearchRequest 里）|

### 修复要点

- server `/vsearch` endpoint 加 expansion（仅 vec/hyde 类型）
- 多 query 顺序搜索，同文档取 best score
- VSearchRequest 默认 min_score 改为 0.3

---

## 9. search 命令（search）

### TS 实现（`qmd.ts` `search`）

- 纯 BM25，无 expansion
- 支持多种输出格式：`cli`/`md`/`xml`/`csv`/`json`/`files`
- `--all`：limit=100000
- `--full`：输出完整文档
- `--line-numbers`：行号
- `--min-score`：过滤
- `--collection`：按 collection 过滤
- 输出含 docid、context、score、snippet（高亮匹配词）

### Python 实现（`qmd/cli.py` `search`）

```python
results = searcher.search(query)
# 输出：Rich Table 格式（固定），只有 title/collection/snippet
```

### 差距

| 维度 | TS | Python |
|------|-----|--------|
| 输出格式 | 6种（cli/md/xml/csv/json/files）| 只有 Rich Table |
| `--all` | ✅ | ❌ |
| `--full` | ✅ | ❌ |
| `--line-numbers` | ✅ | ❌ |
| `--min-score` | ✅ | ❌ |
| `--n` (limit) | ✅ | ❌ |
| `--collection` | ✅ | ❌ |
| score 显示 | ✅ | ❌（无分数字段）|
| docid 显示 | ✅ | ❌ |
| context 显示 | ✅ | ❌ |

### 修复要点

- 加 `--limit`/`--min-score`/`--collection` 参数
- 显示 score（需先修复 BM25 归一化）
- 至少加 `--json` 输出格式

---

## 10. Query Expansion（expandQueryStructured）

### TS 实现（`llm.ts`）

- 使用 **GBNF grammar** 约束输出格式：`type: content\n`，type ∈ {lex, vec, hyde}
- 生成参数：`temperature=0.7, topK=20, topP=0.8, repeatPenalty`
- 有效性过滤：生成的变体必须包含原始 query 中至少一个词
- fallback：生成失败时返回 `[{type:'hyde', text: 'Information about {query}'}, ...]`
- **`includeLexical` 参数**：vsearch 时为 `false`（不生成 lex），query 时为 `true`

### Python 实现（`qmd/search/rerank.py` `LLMReranker.expand_query`）

```python
prompt = f"""Given the following search query, generate 2 alternative search queries...
Query: {query}
"""
# 无 grammar 约束，直接解析换行
# 无类型区分（lex/vec/hyde）
# 无有效性过滤
# 所有变体均视为 lex+vec（无法区分）
```

### 差距

| 维度 | TS | Python |
|------|-----|--------|
| Grammar 约束 | ✅ GBNF `lex:/vec:/hyde:` | ❌ 自由文本换行 |
| 类型区分 | ✅ lex/vec/hyde | ❌ 无类型，全部复用 |
| 有效性过滤 | ✅ 必须含原始词 | ❌ 无过滤 |
| includeLexical 参数 | ✅ | ❌ |
| fallback | ✅ 明确 fallback | ✅（返回 [query]）|
| 模型 | `qmd-query-expansion-1.7B` (GGUF) | `Qwen2.5-0.5B-Instruct` (HF) |

### 修复要点

- 改 prompt 让模型输出 `lex: ...\nvec: ...\nhyde: ...` 格式
- 解析时区分类型
- 加有效性过滤（包含原始 query 中至少一词）
- vsearch 时不传 lex 变体给 FTS

---

## 11. Rerank（rerank）

### TS 实现（`llm.ts`）

- 使用 llama-cpp 的 `context.rankAndSort(query, texts)` API
- 模型：`Qwen3-Reranker-0.6B-Q8_0-GGUF`（专用 ranking context）
- 输入：query + 文档 text 列表
- 输出：`[{file, score, index}]`，score 已归一化为 [0,1]（ranking API 自动处理）

### Python 实现（`qmd/search/rerank.py`）

```python
# 使用 AutoModelForSequenceClassification（cross-encoder）
outputs = self._model(**inputs)
scores = outputs.logits.squeeze(-1)
# logit 未归一化，可正可负
doc["rerank_score"] = float(scores[i])
```

### 差距

| 维度 | TS | Python |
|------|-----|--------|
| 模型格式 | GGUF (llama-cpp) | HuggingFace Transformers |
| score 范围 | [0,1]（ranking API 归一化）| 原始 logit，需手动 sigmoid |
| max_length | 未限制（由 context window 决定）| `max_length=512`（可能截断）|
| 批处理 | `rankAndSort` 一次调用 | `self._model(**inputs)` 批量 |

**注意**：Python 在 blending 中已加 sigmoid 归一化，可接受。模型格式差异是架构差异（HF vs GGUF），暂不要求切换。

---

## 12. cleanup 命令

### TS 实现（`qmd.ts` case "cleanup"）

1. 清空 `llm_cache`（LLM API 缓存）
2. 清理 orphaned vectors（`cleanupOrphanedVectors`）
3. 清理 inactive documents（`deleteInactiveDocuments`）
4. `VACUUM` 数据库

### Python 实现

❌ **Python `cli.py` 中没有 `cleanup` 命令**。

### 修复要点

- 添加 `@cli.command()` cleanup，实现上述 4 步
- `DatabaseManager` 需补充对应的 DB 方法

---

## 13. context 命令接口差异

### TS 实现

```bash
qmd context add [path] "text"    # path 可选，默认当前目录
qmd context add / "text"         # 全局 context
qmd context add qmd://journals/ "text"  # 虚拟路径
qmd context list
qmd context check
qmd context rm <path>
```

### Python 实现

```bash
qmd context add --collection <name> [--path <path>] "text"  # 必须指定 collection
qmd context list [--collection]
qmd context remove --collection <name> [--path]
qmd context check
```

### 差距

| 维度 | TS | Python |
|------|-----|--------|
| collection 指定方式 | 虚拟路径（`qmd://col/path`）自动解析 | `--collection` 强制参数 |
| 全局 context（`/`）| ✅ | ❌ |
| 虚拟路径支持 | ✅ | ❌ |
| 命令名 | `context rm` | `context remove` |

---

## 14. collection add 命令

### TS 实现（`qmd.ts` `collectionAdd`）

```bash
qmd collection add [path] --name <name> --mask <glob>
# path 默认当前目录（getPwd()）
# 立即触发索引（scan + index）
```

### Python 实现

```bash
qmd collection add <path> --name <name> --glob <pattern>
# 仅注册，不触发索引，需另跑 qmd index
```

### 差距

| 维度 | TS | Python |
|------|-----|--------|
| path 默认值 | 当前目录 | 必须提供 |
| 立即索引 | ✅ | ❌（需手动 `qmd index`）|
| glob 参数名 | `--mask` | `--glob` |

---

## 15. 输出格式（outputResults）

### TS 实现

支持 6 种输出格式，由 `--csv/--md/--xml/--files/--json` 控制：
- `cli`（默认）：彩色终端输出，含 docid、score、context、highlighted snippet
- `md`：Markdown
- `xml`：XML
- `csv`：CSV with headers
- `files`：仅路径（用于管道）
- `json`：JSON 数组

所有 search/vsearch/query 命令共享同一输出函数。

### Python 实现

- `search`：只有 Rich Table（title/collection/snippet）
- `vsearch`：Rich Table（score/title/collection/path）
- `query`：Rich Table（rank/score/title/collection）
- 无 `--json`/`--md`/`--xml`/`--csv`/`--files` 格式选项

### 修复要点

至少为 search/vsearch/query 加 `--json` 输出格式（MCP 工具调用时最常用）。

---

## 16. min-score 默认值

### TS 实现

```typescript
// vsearch 默认 min-score = 0.3
if (!cli.values["min-score"]) {
  cli.opts.minScore = 0.3;
}
// search/query 默认 min-score = 0
```

### Python 实现

```python
# VSearchRequest.min_score = 0.0（所有命令相同）
# vsearch 结果无 min-score 过滤（server 端未实现过滤）
```

### 修复要点

- `VSearchRequest` 默认 `min_score = 0.3`
- server 端 `/vsearch` endpoint 加 `score >= min_score` 过滤

---

## 17. 缺失功能汇总

以下 TS 功能在 Python 中完全缺失：

| 功能 | TS 命令 | 优先级 |
|------|---------|--------|
| `cleanup` 命令 | `qmd cleanup` | 中 |
| `pull` 命令（下载模型）| `qmd pull` | 低 |
| `docid` 支持（6位哈希）| `get #abc123` | 低 |
| `qmd get` 虚拟路径 | `qmd get qmd://col/path:line` | 低（已有部分）|
| `multi-get` glob 匹配 | `qmd multi-get journals/2025-*.md` | 低 |
| `--line-numbers` 选项 | 所有搜索命令 | 低 |
| `--full` 选项 | 所有搜索命令 | 低 |
| `--all` 选项 | 所有搜索命令 | 低 |
| Index health check | 搜索前自动检测 | 低 |
| Collection `rename` | `qmd collection rename` | 低（已有）|
| context `check` | `qmd context check` | 低（已有）|

---

## 修复优先级路线图

### P0（影响核心功能正确性）

1. **BM25 分数归一化**（差距#1）：`fts.py` 加权 bm25 + `1/(1+abs(score))` 归一化
2. **FTS 查询构建**（差距#2）：逐词 `"term"*` + AND
3. **文档分块**（差距#4）：embed 时按 800 token/480 char overlap 分块
4. **query 流程 - best chunk 选择**（差距#7）：rerank 前选 best chunk
5. **query 流程 - blending rrfScore**（差距#7）：改为 `1/rrfRank`
6. **query 流程 - 结果去重**（差距#7）：seenFiles 去重
7. **query 流程 - 强信号检测**（依赖 P0#1）

### P1（影响搜索质量）

8. **RRF top-rank bonus**（差距#6）
9. **vsearch expansion**（差距#8）
10. **Query Expansion 类型区分**（差距#10）：lex/vec/hyde 分类
11. **min-score 过滤**（差距#16）

### P2（功能完整性）

12. **Embedding 格式化**（差距#3）：视切换 embedding 模型而定
13. **search 命令参数**（差距#9）：`--limit`/`--min-score`/`--collection`/`--json`
14. **cleanup 命令**（差距#12）
15. **输出格式 `--json`**（差距#15）

---

*本文档由 AI 自动生成，基于 2026-02-19 的代码状态。修复完成后请更新对应章节的"Python 实现"和"差距"列。*
