"""Cleanup command for database maintenance."""

import click

from qmd.cli import console


@click.command()
@click.pass_obj
def cleanup(ctx_obj):
    """Clean up database: inactive documents, orphaned vectors, LLM cache, VACUUM.

    TS equivalent operations:
    1. Clear llm_cache (LLM API cache)
    2. Cleanup orphaned vectors
    3. Delete inactive documents
    4. VACUUM database
    """
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TaskProgressColumn,
    )
    import time

    db = ctx_obj.db

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Step 1: Delete inactive documents
        task = progress.add_task(
            "[cyan]Step 1/4:[/cyan] Deleting inactive documents...", total=None
        )
        t0 = time.time()
        deleted_docs = db.delete_inactive_documents()
        elapsed = time.time() - t0
        progress.print(
            f"[green]✓[/green] Deleted {deleted_docs} inactive documents ({elapsed:.2f}s)"
        )

        # Step 2: Cleanup orphaned vectors
        progress.update(
            task, description="[cyan]Step 2/4:[/cyan] Cleaning orphaned vectors..."
        )
        t0 = time.time()
        orphaned_vectors = db.cleanup_orphaned_vectors()
        elapsed = time.time() - t0
        progress.print(
            f"[green]✓[/green] Removed {orphaned_vectors} orphaned vectors ({elapsed:.2f}s)"
        )

        # Step 3: Clear LLM cache
        progress.update(
            task, description="[cyan]Step 3/4:[/cyan] Clearing LLM cache..."
        )
        t0 = time.time()
        cache_cleared = db.cleanup_llm_cache()
        elapsed = time.time() - t0
        if cache_cleared > 0:
            progress.print(
                f"[green]✓[/green] Cleared {cache_cleared} LLM cache entries ({elapsed:.2f}s)"
            )
        else:
            progress.print("[dim]⊘ No LLM cache to clear[/dim]")

        # Step 4: VACUUM database
        progress.update(task, description="[cyan]Step 4/4:[/cyan] Running VACUUM...")
        t0 = time.time()
        db.vacuum_database()
        elapsed = time.time() - t0
        progress.print(f"[green]✓[/green] Database VACUUM completed ({elapsed:.2f}s)")

        progress.update(task, completed=True)

    console.print("\n[bold green]✓ Cleanup complete![/bold green]")
    console.print(
        f"[dim]Deleted docs: {deleted_docs} | Orphaned vectors: {orphaned_vectors} | LLM cache: {cache_cleared}[/dim]"
    )
