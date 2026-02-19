"""Embed command."""

import click

from qmd.cli import console


@click.command()
@click.option("--collection", help="Specific collection to embed")
@click.option(
    "--force", is_flag=True, help="Clear all existing embeddings and re-embed"
)
@click.pass_obj
def embed(ctx_obj, collection, force):
    """Generate embeddings for indexed documents via server (Jina ZH 768d).

    The server reads the database, chunks documents, runs GPU embedding, and
    writes vectors back.  A second invocation while a job is running attaches
    to the running job instead of starting a new one.
    """
    from rich.progress import (
        Progress,
        BarColumn,
        TaskProgressColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
        TextColumn,
    )
    from qmd.server.client import EmbedServerClient

    client = EmbedServerClient()

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[dim]Connecting to server…[/dim]", total=None)

        def on_progress(event: dict) -> None:
            status = event.get("status")
            total = event.get("total_chunks", 0)
            done = event.get("done_chunks", 0)
            done_docs = event.get("done_docs", 0)
            total_docs = event.get("total_docs", 0)

            if event.get("_attached"):
                progress.print("[dim]Attaching to running embed job…[/dim]")

            if status == "error":
                progress.print(
                    f"[red]Embed error:[/red] {event.get('error', 'unknown')}"
                )
                return

            if status == "running":
                progress.update(
                    task,
                    total=total or None,
                    completed=done,
                    description=(
                        f"[cyan]{done_docs}/{total_docs} docs[/cyan]"
                        if total_docs
                        else "[cyan]Embedding…[/cyan]"
                    ),
                )

            elif status == "complete":
                progress.update(
                    task,
                    total=max(total, 1),
                    completed=max(total, 1),
                    description=(
                        f"[green]Complete — {done_docs} docs, {done} chunks[/green]"
                    ),
                )
                if done == 0:
                    progress.print(
                        "[green]All documents already embedded.[/green]"
                        " Use [bold]--force[/bold] to re-embed."
                    )
                else:
                    progress.print(
                        f"[bold green]Embedding complete![/bold green]"
                        f" {done} chunks across {done_docs} docs"
                    )

        try:
            client.embed_index(
                collection=collection,
                force=force,
                on_progress=on_progress,
            )
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            console.print(
                "[dim]Tip: ensure the server is running with [bold]qmd server[/bold][/dim]"
            )
