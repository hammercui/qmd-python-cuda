"""Index and update commands."""

import subprocess

import click

from qmd.cli import console, _index_collection


@click.command()
@click.pass_obj
def index(ctx_obj):
    """Index all documents in collections defined in config"""
    if not ctx_obj.config.collections:
        console.print("[yellow]No collections to index.[/yellow]")
        return

    total_indexed = 0
    for col in ctx_obj.config.collections:
        console.print(f"Indexing collection: [cyan]{col.name}[/cyan]...")
        count = _index_collection(col, ctx_obj.db)
        console.print(f"  Indexed [green]{count}[/green] documents")
        total_indexed += count

    console.print(
        f"\n[bold green]Total indexed:[/bold green] {total_indexed} documents"
    )


@click.command()
@click.option("--pull", is_flag=True, help="Run 'git pull' before indexing")
@click.pass_obj
def update(ctx_obj, pull):
    """Update all collections (re-scan, run update hooks)"""
    if not ctx_obj.config.collections:
        console.print("[yellow]No collections to update.[/yellow]")
        return

    import os

    total_indexed = 0
    n = len(ctx_obj.config.collections)
    for i, col in enumerate(ctx_obj.config.collections, 1):
        console.print(
            f"[cyan][{i}/{n}][/cyan] [bold]{col.name}[/bold] "
            f"[dim]({col.glob_pattern})[/dim]"
        )

        # Determine update command:
        # 1. Use col.update from config if set
        # 2. Fall back to git pull when --pull flag given and repo is detected
        update_cmd = col.update
        if not update_cmd and pull and os.path.exists(os.path.join(col.path, ".git")):
            update_cmd = "git pull"

        if update_cmd:
            console.print(f"  [dim]Running: {update_cmd}[/dim]")
            try:
                result = subprocess.run(
                    update_cmd,
                    shell=True,
                    cwd=col.path,
                    capture_output=True,
                    text=True,
                )
                for line in result.stdout.strip().splitlines():
                    console.print(f"  {line}")
                for line in result.stderr.strip().splitlines():
                    console.print(f"  [dim]{line}[/dim]")
                if result.returncode != 0:
                    console.print(
                        f"  [red]Command exited with code {result.returncode}[/red]"
                    )
            except Exception as e:
                console.print(f"  [red]Update command failed: {e}[/red]")

        count = _index_collection(col, ctx_obj.db)
        console.print(f"  Indexed [green]{count}[/green] documents")
        total_indexed += count
        console.print("")

    console.print(f"[bold green]Total indexed:[/bold green] {total_indexed} documents")

    # Show embedding hint (mirrors TS updateCollections)
    needs_embed = ctx_obj.db.count_hashes_needing_embedding()
    if needs_embed > 0:
        console.print(
            f"\nRun '[bold]qmd embed[/bold]' to update embeddings "
            f"({needs_embed} unique hashes need vectors)"
        )
