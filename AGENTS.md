# AGENTS.md

This file provides coding guidelines and project information for AI agents working in this repository.

## Project Overview

**QMD-Python** (Query Markup Documents) - A hybrid search tool for indexing and searching markup documents using BM25 full-text search and vector embeddings.

### Project Structure
- `qmd/` - Main source code
  - `cli.py` - Click-based CLI interface
  - `database/` - SQLite database manager and schema
  - `search/` - Search engines (FTS, Vector, Hybrid, Rerank)
  - `llm/` - LLM integration for query expansion and reranking
  - `index/` - Document crawler and indexer
  - `models/` - Pydantic data models
- `tests/` - Test suite (unit, integration, benchmarks)

---

## Build, Lint, Test Commands

### Installation
```bash
pip install .
```

### Running Tests
```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/unit/test_search.py

# Run a specific test function
pytest tests/unit/test_search.py::test_fts_search

# Run with coverage
pytest --cov=qmd --cov-report=html
```

### Test Configuration
- Test paths defined in `pyproject.toml`: `[tool.pytest.ini_options] testpaths = ["tests"]`
- Python path includes project root: `pythonpath = ["."]`

---

## Code Style Guidelines

### Import Organization
Imports follow standard Python ordering:
1. Standard library imports
2. Third-party imports
3. Local application imports

Example:
```python
import os
from pathlib import Path
from typing import List, Optional

import click
import yaml
from pydantic import BaseModel

from qmd.database.manager import DatabaseManager
```

### Type Hints
- Use `typing` module for type annotations
- Pydantic `BaseModel` for data models
- Return type annotations on functions
- Use `Optional[T]` for nullable types
- Use `List[T]`, `Dict[K, V]` for collections

Example:
```python
from typing import List, Dict, Any, Optional

def search(query: str, collection: Optional[str] = None) -> List[Dict[str, Any]]:
    ...
```

### Naming Conventions
- **Classes**: PascalCase (`DatabaseManager`, `FTSSearcher`, `AppConfig`)
- **Functions/Methods**: snake_case (`search_documents`, `upsert_document`)
- **Variables**: snake_case (`doc_hash`, `collection_name`)
- **Constants**: UPPER_SNAKE_CASE (rarely used in this codebase)
- **Private members**: underscore prefix (`_init_db`, `_get_connection`)

### Error Handling
- Use `try/except` for error recovery
- Raise descriptive `ValueError` for invalid inputs
- Click CLI commands catch exceptions and display user-friendly errors

Example:
```python
try:
    new_col = CollectionConfig(name=name, path=abs_path, glob_pattern=glob)
    ctx_obj.config.collections.append(new_col)
except Exception as e:
    console.print(f"[red]Error:[/red] {e}")
```

### Database Connections
- Use context managers for SQLite connections
- Set `row_factory = sqlite3.Row` for dict-like row access
- Always commit after writes

Example:
```python
def _get_connection(self):
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row
    return conn

def add_document(self, ...):
    with self._get_connection() as conn:
        conn.execute("INSERT INTO documents ...")
        conn.commit()
```

### CLI Command Pattern
- Use Click decorators for command groups and commands
- Pass context via `@click.pass_obj`
- Use `@click.argument()` for required arguments
- Use `@click.option()` for optional flags

Example:
```python
@click.group()
@click.pass_context
def cli(ctx):
    ctx.obj = Context()

@cli.command()
@click.argument("query")
@click.pass_obj
def search(ctx_obj, query):
    searcher = FTSSearcher(ctx_obj.db)
    results = searcher.search(query)
```

### File Organization
- `__init__.py` files are minimal, mainly for package imports
- Main modules are imported directly (e.g., `from qmd.cli import cli`)
- Related functionality grouped in subdirectories (database/, search/, models/)

---

## Project Dependencies

### Core Dependencies
- `click>=8.1.0` - CLI framework
- `rich>=12.0.0` - Terminal formatting
- `chromadb>=0.4.0` - Vector database
- `llama-cpp-python>=0.2.0` - LLM inference
- `pydantic>=2.0.0` - Data validation
- `pyyaml>=6.0` - YAML config parsing

### Python Version
- Python 3.9+

---

## Testing Guidelines

### Test Organization
- `tests/unit/` - Unit tests for individual components
- `tests/integration/` - End-to-end CLI tests using CliRunner
- `tests/benchmarks/` - Performance benchmarks

### Test Framework
- `pytest` for all testing
- `unittest.TestCase` for some legacy tests
- `pytest` fixtures for setup/teardown

### Common Fixtures
```python
@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test_qmd.db")
    manager = DatabaseManager(db_path)
    yield manager
```

### Test Naming
- Test files: `test_<module>.py`
- Test functions: `test_<functionality>[_<scenario>]`
- Test classes: `Test<ClassName>`

---

## Architecture Notes

### Database Schema
- SQLite-based with FTS5 extension for full-text search
- Separate tables for metadata (`documents`, `collections`) and content (`content`)
- Content-addressable storage with hash-based deduplication
- Embedding cache stored as BLOB in `content` table

### Search Architecture
- **BM25 (FTS)**: SQLite full-text search for keyword matching
- **Vector Search**: ChromaDB for semantic similarity
- **Hybrid Search**: Reciprocal Rank Fusion (RRF) combining both
- **Reranking**: LLM-powered query expansion and cross-encoder reranking

### CLI Flow
1. `collection add` - Add document collections
2. `index` - Scan and index documents
3. `embed` - Generate vector embeddings
4. `search/vsearch/query` - Search documents

---

## Additional Notes

- No formal linting/formatting configuration found (black, ruff, mypy not configured)
- No CI/CD pipeline configured (.github/workflows not present)
- Tests generate temporary directories using pytest's `tmp_path` fixture
- Console output uses `rich` library for colored, formatted output
