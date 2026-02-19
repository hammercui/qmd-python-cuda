"""Collection command group."""

import os

import click

from qmd.cli import console, _index_collection
from qmd.models.config import CollectionConfig


@click.group()
def collection():
    """Manage document collections"""
    pass


@collection.command(name="add")
@click.argument("path")
@click.option("--name", required=True, help="Collection name")
@click.option("--glob", default="**/*.md", help="Glob pattern (default: **/*.md)")
@click.pass_obj
def collection_add(ctx_obj, path, name, glob):
    """Add a new collection and immediately index it"""
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        console.print(f"[red]Error:[/red] Path {abs_path} does not exist")
        return

    # Check if name already exists
    if any(c.name == name for c in ctx_obj.config.collections):
        console.print(f"[red]Error:[/red] Collection with name '{name}' already exists")
        return

    # Check if same path+glob already registered
    for c in ctx_obj.config.collections:
        if c.path == abs_path and c.glob_pattern == glob:
            console.print(
                f"[yellow]A collection already exists for this path and pattern:[/yellow]\n"
                f"  Name: {c.name} (qmd://{c.name}/)\n"
                f"  Pattern: {glob}\n"
                f"\nUse '[bold]qmd update[/bold]' to re-index it, or remove it first with "
                f"'[bold]qmd collection remove {c.name}[/bold]'"
            )
            return

    try:
        new_col = CollectionConfig(name=name, path=abs_path, glob_pattern=glob)
        ctx_obj.config.collections.append(new_col)
        ctx_obj.config.save()
        ctx_obj.db.add_collection(name, abs_path, glob)
        console.print(f"[green]Added collection:[/green] {name} -> {abs_path}")

        # Auto-index immediately (mirrors TS collectionAdd behaviour)
        console.print(f"Indexing [cyan]{name}[/cyan]...")
        count = _index_collection(new_col, ctx_obj.db)
        console.print(f"  Indexed [green]{count}[/green] documents")
        if count > 0:
            console.print(
                f"[dim]Tip: Run 'qmd embed' to generate vector embeddings.[/dim]"
            )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")


@collection.command(name="list")
@click.pass_obj
def collection_list(ctx_obj):
    """List all collections from config"""
    if not ctx_obj.config.collections:
        console.print("No collections found in config.")
        return

    from rich.table import Table

    table = Table(title="Collections (from config)")
    table.add_column("Name", style="cyan")
    table.add_column("Path", style="magenta")
    table.add_column("Glob", style="green")

    for c in ctx_obj.config.collections:
        table.add_row(c.name, c.path, c.glob_pattern)

    console.print(table)


@collection.command(name="remove")
@click.argument("name")
@click.pass_obj
def collection_remove(ctx_obj, name):
    """Remove a collection"""
    original_len = len(ctx_obj.config.collections)
    ctx_obj.config.collections = [
        c for c in ctx_obj.config.collections if c.name != name
    ]

    if len(ctx_obj.config.collections) < original_len:
        ctx_obj.config.save()
        ctx_obj.db.remove_collection(name)
        console.print(f"[yellow]Removed collection:[/yellow] {name}")
    else:
        console.print(f"[red]Error:[/red] Collection '{name}' not found")


@collection.command(name="rename")
@click.argument("old")
@click.argument("new")
@click.pass_obj
def collection_rename(ctx_obj, old, new):
    """Rename a collection"""
    try:
        # Update DB
        ctx_obj.db.rename_collection(old, new)

        # Update Config
        found = False
        for c in ctx_obj.config.collections:
            if c.name == old:
                c.name = new
                found = True

        if found:
            ctx_obj.config.save()
            console.print(f"[green]Renamed collection '{old}' to '{new}'[/green]")
        else:
            console.print(
                f"[yellow]Note: Collection '{old}' not found in config, but DB update attempted.[/yellow]"
            )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
