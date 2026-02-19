"""Search commands (BM25, vector, hybrid)."""

import click

from qmd.cli import console
from qmd.search.fts import FTSSearcher


@click.command()
@click.argument("query")
@click.pass_obj
def search(ctx_obj, query):
    """BM25 full-text search"""
    searcher = FTSSearcher(ctx_obj.db)
    results = searcher.search(query)

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    from rich.table import Table

    table = Table(title=f"Search Results for: {query}")
    table.add_column("Title", style="cyan")
    table.add_column("Collection", style="magenta")
    table.add_column("Snippet", style="white")

    for r in results:
        table.add_row(r["title"], r["collection"], r["snippet"])

    console.print(table)


@click.command()
@click.argument("query")
@click.option("--collection", help="Collection to search in")
@click.option("--limit", default=5, help="Number of results")
@click.pass_obj
def vsearch(ctx_obj, query, collection, limit):
    """Semantic search using vector embeddings (via HTTP Server)"""
    from qmd.server.client import EmbedServerClient

    scope = (
        f"collection=[cyan]{collection}[/cyan]"
        if collection
        else "[dim]all collections[/dim]"
    )
    console.print(f"[dim]Searching via QMD Server ({scope})...[/dim]")

    try:
        client = EmbedServerClient()
        results = client.vsearch(query, limit=limit, collection=collection)

        if not results:
            console.print("[yellow]No results found.[/yellow]")
            return

        from rich.table import Table

        table = Table(title=f"Semantic Search Results for: {query}")
        table.add_column("Score", style="green")
        table.add_column("Title", style="cyan")
        table.add_column("Collection", style="magenta")
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
@click.option("--collection", help="Collection to search in")
@click.option("--limit", default=5, help="Number of results")
@click.pass_obj
def query(ctx_obj, query, collection, limit):
    """Hybrid search (BM25 + Vector) via HTTP Server"""
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

        from rich.table import Table

        table = Table(title=f"Hybrid Search Results for: {query}")
        table.add_column("Rank", style="dim")
        table.add_column("Score", style="green")
        table.add_column("Title", style="cyan")
        table.add_column("Collection", style="magenta")

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
