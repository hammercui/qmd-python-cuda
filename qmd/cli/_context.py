"""Context command group."""

import os
import click

from qmd.cli import console


@click.group()
def context():
    """Manage path contexts"""
    pass


@context.command(name="add")
@click.option("--collection", help="Collection name (for explicit mode)")
@click.option("--path", default="", help="Relative path (default: root)")
@click.argument("text")
@click.argument("path_arg", required=False)
@click.pass_obj
def context_add(ctx_obj, collection, path, text, path_arg):
    """Add/Update context for a path.

    Supports two modes:
    1. Path-based: qmd context add <text> [path]
       - Supports virtual paths: qmd://collection/path
       - Supports filesystem paths (auto-detects collection)

    2. Explicit: qmd context add --collection <name> [--path <path>] <text>
       - Legacy mode for backward compatibility

    Note: Due to CLI parsing limitations, when using path-based mode with
    special characters in text, use quotes: qmd context add "your text" [path]
    """
    target_collection = None
    target_path = ""

    if path_arg:
        # Mode 1: Path-based parameter (Node.js compatible)
        # Parse virtual path (qmd://collection/path)
        if path_arg.startswith("qmd://"):
            from urllib.parse import urlparse

            parsed = urlparse(path_arg)
            parts = parsed.path.lstrip("/").split("/", 1)
            target_collection = parts[0]
            target_path = parts[1] if len(parts) > 1 else ""
        else:
            # Filesystem path - detect collection
            abs_path = os.path.abspath(path_arg)
            for col in ctx_obj.config.collections:
                if abs_path.startswith(col.path + os.sep) or abs_path == col.path:
                    target_collection = col.name
                    rel_path = os.path.relpath(abs_path, col.path)
                    target_path = rel_path if rel_path != "." else ""
                    break

            if not target_collection:
                console.print(
                    f"[red]Error:[/red] Path is not in any indexed collection: {path_arg}"
                )
                console.print(f"[dim]Run 'qmd status' to see indexed collections[/dim]")
                return
    elif collection:
        # Mode 2: Explicit parameters (legacy mode)
        target_collection = collection
        target_path = path.strip("/")
    else:
        # No path_arg and no collection - apply to all collections (not supported yet)
        console.print(
            "[yellow]Warning:[/yellow] No path specified. Use --collection to specify a collection."
        )
        console.print("[dim]Usage: qmd context add <text> [path][/dim]")
        console.print("[dim]       qmd context add --collection <name> <text>[/dim]")
        return

    try:
        ctx_obj.db.set_path_context(target_collection, target_path, text)
        display_path = (
            f"qmd://{target_collection}/{target_path}"
            if target_path
            else f"qmd://{target_collection}/"
        )
        console.print(f"[green]Added context for:[/green] {display_path}")
        console.print(f"[dim]Context: {text}[/dim]")
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
@click.argument("path_arg")
@click.pass_obj
def context_remove(ctx_obj, path_arg):
    """Remove a path context.

    Usage:
      qmd context remove qmd://collection/path
      qmd context remove /path/to/dir

    Supports virtual paths (qmd://) and filesystem paths.
    """
    # Parse virtual path
    if path_arg.startswith("qmd://"):
        from urllib.parse import urlparse

        parsed = urlparse(path_arg)
        parts = parsed.path.lstrip("/").split("/", 1)
        collection = parts[0]
        path = parts[1] if len(parts) > 1 else ""
    else:
        # Filesystem path - detect collection
        abs_path = os.path.abspath(path_arg)
        collection = None
        path = ""
        for col in ctx_obj.config.collections:
            if abs_path.startswith(col.path + os.sep) or abs_path == col.path:
                collection = col.name
                rel_path = os.path.relpath(abs_path, col.path)
                path = rel_path if rel_path != "." else ""
                break

        if not collection:
            console.print(
                f"[red]Error:[/red] Path is not in any indexed collection: {path_arg}"
            )
            console.print(f"[dim]Run 'qmd status' to see indexed collections[/dim]")
            return

    try:
        ctx_obj.db.remove_path_context(collection, path)
        display_path = f"qmd://{collection}/{path}" if path else f"qmd://{collection}/"
        console.print(f"[green]Removed context for:[/green] {display_path}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")


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
