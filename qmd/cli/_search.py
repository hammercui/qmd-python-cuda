"""Search commands (BM25, vector, hybrid)."""

import click
import json

from qmd.cli import console
from qmd.search.fts import FTSSearcher


@click.command()
@click.argument("query")
@click.option("--limit", "-n", default=10, help="Maximum number of results")
@click.option(
    "--min-score", type=float, default=0.0, help="Minimum score threshold (0-1)"
)
@click.option("--collection", "-c", help="Filter by collection")
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON")
@click.pass_obj
def search(ctx_obj, query, limit, min_score, collection, as_json):
    """BM25 full-text search with score normalization and filtering.

    Features:
    - Weighted BM25 (title ×10, content ×1)
    - Score normalization: 1/(1+abs(bm25_score)) → (0,1]
    - Per-term prefix matching with AND operator
    - Min-score filtering
    """
    searcher = FTSSearcher(ctx_obj.db)
    results = searcher.search(
        query, limit=limit, collection=collection, min_score=min_score
    )

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    if as_json:
        # Output as JSON (for MCP tools)
        output = []
        for r in results:
            output.append(
                {
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "collection": r.get("collection"),
                    "path": r.get("path"),
                    "score": r.get("score"),
                    "snippet": r.get("snippet"),
                }
            )
        console.print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    from rich.table import Table

    table = Table(title=f"Search Results for: {query}")
    table.add_column("Score", style="green", width=8)
    table.add_column("Title", style="cyan")
    table.add_column("Collection", style="magenta", width=15)
    table.add_column("Snippet", style="white")

    for r in results:
        table.add_row(
            f"{r.get('score', 0):.4f}",
            r["title"],
            r["collection"],
            r["snippet"][:80] + "..."
            if len(r.get("snippet", "")) > 80
            else r.get("snippet", ""),
        )

    console.print(table)


@click.command()
@click.argument("query")
@click.option("--collection", "-c", help="Collection to search in")
@click.option("--limit", "-n", default=5, help="Number of results")
@click.option(
    "--min-score", type=float, default=0.3, help="Minimum score threshold (0-1)"
)
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON")
@click.pass_obj
def vsearch(ctx_obj, query, collection, limit, min_score, as_json):
    """Semantic search using vector embeddings (via HTTP Server)

    Features:
    - Query expansion (vec/hyde variants only, no lex)
    - Best score across multiple queries for same doc
    - Min-score filtering (default 0.3)
    """
    from qmd.server.client import EmbedServerClient

    scope = (
        f"collection=[cyan]{collection}[/cyan]"
        if collection
        else "[dim]all collections[/dim]"
    )
    console.print(f"[dim]Searching via QMD Server ({scope})...[/dim]")

    try:
        client = EmbedServerClient()
        results = client.vsearch(
            query, limit=limit, collection=collection, min_score=min_score
        )

        if not results:
            console.print("[yellow]No results found.[/yellow]")
            return

        if as_json:
            console.print(json.dumps(results, ensure_ascii=False, indent=2))
            return

        from rich.table import Table

        table = Table(title=f"Semantic Search Results for: {query}")
        table.add_column("Score", style="green", width=8)
        table.add_column("Title", style="cyan")
        table.add_column("Collection", style="magenta", width=15)
        table.add_column("Path", style="white")

        for r in results:
            table.add_row(
                f"{r.get('score', 0):.4f}",
                r.get("title", "N/A"),
                r.get("collection", "N/A"),
                r.get("path", "N/A"),
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")


@click.command()
@click.argument("query")
@click.option("--collection", "-c", help="Collection to search in")
@click.option("--limit", "-n", default=5, help="Number of results")
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON")
@click.pass_obj
def query(ctx_obj, query, collection, limit, as_json):
    """Hybrid search (BM25 + Vector) via HTTP Server

    Features:
    - Strong signal detection (skip LLM expansion if topScore >= 0.85)
    - LLM query expansion with type distinction (lex/vec/hyde)
    - Weighted RRF with top-rank bonus
    - Cross-encoder reranking
    - Position-aware score blending
    - Result deduplication
    """
    from qmd.server.client import EmbedServerClient

    scope = (
        f"collection=[cyan]{collection}[/cyan]"
        if collection
        else "[dim]all collections[/dim]"
    )
    console.print(f"Searching for: [bold cyan]{query}[/bold cyan] ({scope})...")
    console.print("[dim]Using QMD Server (hybrid search)[/dim]")

    try:
        client = EmbedServerClient()
        results = client.query(query, limit=limit, collection=collection)

        if not results:
            console.print("[yellow]No results found.[/yellow]")
            return

        if as_json:
            console.print(json.dumps(results, ensure_ascii=False, indent=2))
            return

        from rich.table import Table

        table = Table(title=f"Hybrid Search Results for: {query}")
        table.add_column("Rank", style="dim", width=6)
        table.add_column("Score", style="green", width=8)
        table.add_column("Title", style="cyan")
        table.add_column("Collection", style="magenta", width=15)

        for i, r in enumerate(results, 1):
            table.add_row(
                str(i),
                f"{r.get('score', 0):.4f}",
                r.get("title", "N/A"),
                r.get("collection", "N/A"),
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
