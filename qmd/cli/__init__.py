"""CLI module - contains all CLI command implementations.

This module exports:
- Context: CLI context class
- _index_collection: Helper function for indexing
- check_virtual_env: Virtual environment check helper
- console: Rich console for output
"""

import os

from rich.console import Console
from rich.table import Table

from qmd.database.manager import DatabaseManager
from qmd.index.crawler import Crawler
from qmd.models.config import AppConfig, CollectionConfig

console = Console()


class Context:
    """CLI context that holds config and database manager."""

    def __init__(self):
        self.config = AppConfig.load()
        self.db = DatabaseManager(self.config.db_path)


def _index_collection(col: CollectionConfig, db: DatabaseManager) -> int:
    """Scan and upsert all documents for a single collection. Returns indexed count."""
    crawler = Crawler(col.path, col.glob_pattern)
    count = 0
    for rel_path, content, doc_hash, title in crawler.scan():
        context_text = db.get_context_for_path(col.name, rel_path)
        db.upsert_document(
            col.name, rel_path, doc_hash, title, content, context=context_text
        )
        count += 1
    return count


def print_table(title: str, columns: list[tuple[str, str]]) -> Table:
    """Create and print a table with given columns and data."""
    table = Table(title=title)
    for col_name, style in columns:
        table.add_column(col_name, style=style)
    return table


def format_size(size: int) -> str:
    """Format file size in human-readable format."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


def check_virtual_env() -> bool:
    """Check if running in a virtual environment."""
    import sys

    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )

    if not in_venv:
        console.print("[yellow]Warning: Not running in a virtual environment[/yellow]")
        console.print(
            "[dim]Recommendation: Create and activate a virtual environment[/dim]"
        )
        console.print("[dim]  python -m venv .venv[/dim]")
        console.print("[dim]  .venv\\Scripts\\activate  (Windows)[/dim]")
        console.print("[dim]  source .venv/bin/activate  (Linux/macOS)[/dim]")
        console.print("")

    return in_venv
