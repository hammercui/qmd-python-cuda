# QMD-Python (Query Markup Documents)

QMD is a powerful tool for indexing and searching markup documents (Markdown, etc.) using hybrid search techniques.

## Features

- **Multi-Collection Support**: Organize your documents into named collections.
- **Fast Indexing**: SQLite-based metadata and full-text index.
- **Hybrid Search**: Combines BM25 (Full-text) and Semantic (Vector) search using Reciprocal Rank Fusion (RRF).
- **LLM-Powered**: Query expansion and cross-encoder reranking for maximum precision.
- **Persistent Vector Store**: Built-in ChromaDB integration.
- **Embedding Cache**: Content-addressable embedding cache in SQLite for performance.

## Installation

```bash
pip install .
```

Requires:
- Python 3.9+
- ChromaDB
- FastEmbed
- Transformers
- Google GenAI (for query expansion)

## Usage

### 1. Add a collection
```bash
qmd collection add ./docs --name my-docs
```

### 2. Index documents
```bash
qmd index
```

### 3. Generate embeddings
```bash
qmd embed
```

### 4. Search
#### BM25 Search
```bash
qmd search "my query"
```

#### Semantic Search
```bash
qmd vsearch "my query"
```

#### Hybrid Query (Recommended)
```bash
qmd query "my query"
```

## Performance

- Hybrid Search: <3s for 10k documents.
- Embedding Cache: Avoids redundant computation for unchanged documents.
- Batch Processing: High-throughput embedding generation.

## License

MIT
