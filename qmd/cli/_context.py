"""Context command group."""

import click

from qmd.cli import console


@click.group()
def context():
    """Manage path contexts"""
    pass


@context.command(name="add")
@click.option("--collection", required=True, help="Collection name")
@click.option("--path", default="", help="Relative path (default: root)")
@click.argument("text")
@click.pass_obj
def context_add(ctx_obj, collection, path, text):
    """Add/Update context for a path"""
    path = path.strip("/")
    try:
        ctx_obj.db.set_path_context(collection, path, text)
        console.print(f"[green]Set context for[/green] {collection}:{path or '(root)'}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")


@context.command(name="list")
@click.option("--collection", help="Filter by collection")
@click.pass_obj
def context_list(ctx_obj, collection):
    """List all path contexts"""
    contexts = ctx_obj.db.list_path_contexts(collection)
    if not contexts:
        console.print("No contexts found.")
        return

    from rich.table import Table

    table = Table(title="Path Contexts")
    table.add_column("Collection", style="cyan")
    table.add_column("Path", style="magenta")
    table.add_column("Context", style="white")

    for c in contexts:
        table.add_row(
            c["collection"],
            c["path"] or "(root)",
            c["context"][:50] + "..." if len(c["context"]) > 50 else c["context"],
        )

    console.print(table)


@context.command(name="remove")
@click.option("--collection", required=True, help="Collection name")
@click.option("--path", default="", help="Relative path")
@click.pass_obj
def context_remove(ctx_obj, collection, path):
    """Remove a path context"""
    path = path.strip("/")
    ctx_obj.db.remove_path_context(collection, path)
    console.print(
        f"[yellow]Removed context for[/yellow] {collection}:{path or '(root)'}"
    )


@context.command(name="check")
@click.pass_obj
def context_check(ctx_obj):
    """Identify missing contexts"""
    all_cols = [c.name for c in ctx_obj.config.collections]
    with_ctx = set(
        c["collection"]
        for c in ctx_obj.db.list_path_contexts()
        if c["path"] == "" or c["path"] == "."
    )

    missing_cols = [c for c in all_cols if c not in with_ctx]

    if missing_cols:
        console.print("Collections without context:")
        for col in missing_cols:
            files = ctx_obj.db.list_files(col)
            console.print(f"  {col} ({len(files)} documents)")
            console.print(
                f'  Suggestion: [dim]qmd context add --collection {col} "Description"[/dim]'
            )
        console.print()

    console.print("Top-level paths without context:")
    for col in all_cols:
        files = ctx_obj.db.list_files(col)
        top_dirs = set()
        for f in files:
            parts = f["path"].split("/")
            if len(parts) > 1:
                top_dirs.add(parts[0])

        ctxs = set(c["path"] for c in ctx_obj.db.list_path_contexts(col))
        missing_dirs = [d for d in top_dirs if d not in ctxs]

        if missing_dirs:
            console.print(f"  [cyan]{col}[/cyan]")
            for d in missing_dirs:
                console.print(f"    {d}")
            console.print(
                f'  Suggestion: [dim]qmd context add --collection {col} --path <path> "Description"[/dim]'
            )
