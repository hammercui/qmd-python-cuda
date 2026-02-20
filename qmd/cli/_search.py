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
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["cli", "json", "files", "md", "csv"]),
    default="cli",
    help="Output format (default: cli)",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output results as JSON (alias for --format=json)",
)
@click.pass_obj
def search(ctx_obj, query, limit, min_score, collection, output_format, as_json):
    """BM25 full-text search with score normalization and filtering.

    Features:
    - Weighted BM25 (title ×10, content ×1)
    - Score normalization: 1/(1+abs(bm25_score)) → (0,1]
    - Per-term prefix matching with AND operator
    - Min-score filtering
    - Multiple output formats (cli, json, files, md, csv)
    """
    # Handle --json alias for backward compatibility
    if as_json:
        output_format = "json"

    searcher = FTSSearcher(ctx_obj.db)
    results = searcher.search(
        query, limit=limit, collection=collection, min_score=min_score
    )

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    # Output based on format
    if output_format == "json":
        _output_json(results)
    elif output_format == "files":
        _output_files(results)
    elif output_format == "md":
        _output_markdown(results, query)
    elif output_format == "csv":
        _output_csv(results)
    else:  # cli (default)
        _output_cli(results, query)


def _output_json(results):
    """Output results as JSON."""
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


def _output_files(results):
    """Output results as file list only."""
    for r in results:
        console.print(f"qmd://{r['collection']}/{r['path']}")


def _output_markdown(results, query):
    """Output results as Markdown."""
    for i, r in enumerate(results, 1):
        console.print(f"---\n# {i}. {r.get('title', 'N/A')}\n")
        console.print(f"**Path:** qmd://{r['collection']}/{r['path']}\n")
        console.print(f"**Score:** {r.get('score', 0):.4f}\n")
        snippet = r.get("snippet", "")[:300]
        if snippet:
            console.print(f"{snippet}...\n")


def _output_csv(results):
    """Output results as CSV."""
    console.print("score,collection,path,title,snippet")
    for r in results:
        score = f"{r.get('score', 0):.4f}"
        collection = r["collection"]
        path = r["path"]
        title = r.get("title", "").replace(",", ",")
        snippet = r.get("snippet", "")[:100].replace(",", ",").replace("\n", " ")
        console.print(f"{score},{collection},{path},{title},{snippet}")


def _output_cli(results, query):
    """Output results as CLI table (default)."""
    from rich.table import Table
    from rich.text import Text

    table = Table(title=f"Search Results for: {query}")
    table.add_column("Score", style="green", width=8)
    table.add_column("Title", style="cyan")
    table.add_column("Collection", style="magenta", width=15)
    table.add_column("Snippet", style="white")

    for r in results:
        # Escape Rich markup in snippet to prevent parsing errors
        # FTS5 snippet uses [b] and [/b] for highlighting, but content may contain brackets
        snippet_text = r.get("snippet", "")
        snippet_display = Text.from_markup(snippet_text, style="white")

        # Truncate if too long
        if len(snippet_text) > 80:
            snippet_display = Text.from_markup(snippet_text[:77] + "...", style="white")

        table.add_row(
            f"{r.get('score', 0):.4f}",
            r["title"],
            r["collection"],
            snippet_display,
        )

    console.print(table)


@click.command()
@click.argument("query")
@click.option("--collection", "-c", help="Collection to search in")
@click.option("--limit", "-n", default=5, help="Number of results")
@click.option(
    "--min-score", type=float, default=0.3, help="Minimum score threshold (0-1)"
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["cli", "json", "files", "md", "csv"]),
    default="cli",
    help="Output format (default: cli)",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output results as JSON (alias for --format=json)",
)
@click.pass_obj
def vsearch(ctx_obj, query, collection, limit, min_score, output_format, as_json):
    """Semantic search using vector embeddings (via HTTP Server)

    Features:
    - Query expansion (vec/hyde variants only, no lex)
    - Best score across multiple queries for same doc
    - Min-score filtering (default 0.3)
    - Multiple output formats (cli, json, files, md, csv)
    """
    # Handle --json alias for backward compatibility
    if as_json:
        output_format = "json"

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

        # Output based on format
        if output_format == "json":
            console.print(json.dumps(results, ensure_ascii=False, indent=2))
        elif output_format == "files":
            for r in results:
                console.print(
                    f"qmd://{r.get('collection', 'N/A')}/{r.get('path', 'N/A')}"
                )
        elif output_format == "md":
            for i, r in enumerate(results, 1):
                console.print(f"---\n# {i}. {r.get('title', 'N/A')}\n")
                console.print(
                    f"**Path:** qmd://{r.get('collection', 'N/A')}/{r.get('path', 'N/A')}\n"
                )
                console.print(f"**Score:** {r.get('score', 0):.4f}\n")
        elif output_format == "csv":
            console.print("score,collection,path,title")
            for r in results:
                title_safe = r.get("title", "").replace(",", ",")
                console.print(
                    f"{r.get('score', 0):.4f},{r.get('collection', 'N/A')},{r.get('path', 'N/A')},{title_safe}"
                )
        else:  # cli (default)
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
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["cli", "json", "files", "md", "csv"]),
    default="cli",
    help="Output format (default: cli)",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output results as JSON (alias for --format=json)",
)
@click.pass_obj
def query(ctx_obj, query, collection, limit, output_format, as_json):
    """Hybrid search (BM25 + Vector) via HTTP Server

    Features:
    - Strong signal detection (skip LLM expansion if topScore >= 0.85)
    - LLM query expansion with type distinction (lex/vec/hyde)
    - Weighted RRF with top-rank bonus
    - Cross-encoder reranking
    - Position-aware score blending
    - Result deduplication
    - Multiple output formats (cli, json, files, md, csv)
    """
    # Handle --json alias for backward compatibility
    if as_json:
        output_format = "json"

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

        # Output based on format
        if output_format == "json":
            console.print(json.dumps(results, ensure_ascii=False, indent=2))
        elif output_format == "files":
            for r in results:
                console.print(
                    f"qmd://{r.get('collection', 'N/A')}/{r.get('path', 'N/A')}"
                )
        elif output_format == "md":
            for i, r in enumerate(results, 1):
                console.print(f"---\n# {i}. {r.get('title', 'N/A')}\n")
                console.print(
                    f"**Path:** qmd://{r.get('collection', 'N/A')}/{r.get('path', 'N/A')}\n"
                )
                console.print(f"**Score:** {r.get('score', 0):.4f}\n")
        elif output_format == "csv":
            console.print("rank,score,collection,path,title")
            for i, r in enumerate(results, 1):
                title_safe = r.get("title", "").replace(",", ",")
                console.print(
                    f"{i},{r.get('score', 0):.4f},{r.get('collection', 'N/A')},{r.get('path', 'N/A')},{title_safe}"
                )
        else:  # cli (default)
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
