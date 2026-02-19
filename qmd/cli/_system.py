"""System status and check commands."""

import click

from qmd.cli import console


@click.command()
@click.pass_obj
def status(ctx_obj):
    """Show detailed system status"""
    stats = ctx_obj.db.get_detailed_stats()

    from rich.table import Table

    table = Table(title="System Status", show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    size = stats["db_size"]
    if size < 1024 * 1024:
        size_str = f"{size / 1024:.1f} KB"
    else:
        size_str = f"{size / (1024 * 1024):.1f} MB"

    table.add_row("Index size", size_str)
    table.add_row("Collections", str(stats["collections"]))
    table.add_row("Documents", str(stats["documents"]))

    embedded = stats["embedded_contents"]
    total = stats["total_contents"]
    ratio = (embedded / total * 100) if total > 0 else 0
    table.add_row("Embeddings", f"{embedded}/{total} ({ratio:.1f}%)")

    console.print(table)

    if stats["collection_details"]:
        col_table = Table(title="Collections Break-down", box=None)
        col_table.add_column("Collection", style="cyan")
        col_table.add_column("Docs", style="magenta")
        for col, count in stats["collection_details"].items():
            col_table.add_row(col, str(count))
        console.print(col_table)

    # Warn about orphaned content (content table has data but documents table is empty)
    orphaned = stats.get("orphaned_content", 0)
    if orphaned > 0 and stats["documents"] == 0:
        console.print(
            f"[bold red]Error:[/bold red] {orphaned} content entries exist but no documents are indexed. "
            f"Run '[bold]qmd index[/bold]' to rebuild the document index."
        )
    elif total > 0:
        missing = total - embedded
        if missing > 0:
            if missing / total > 0.1:
                console.print(
                    f"[bold yellow]Warning:[/bold yellow] {missing} documents need embedding. Run '[bold]qmd embed[/bold]' for better results."
                )
            else:
                console.print(f"[cyan]Tip:[/cyan] {missing} documents need embeddings.")

    if stats["last_index_update"]:
        from datetime import datetime

        try:
            last_upd = datetime.fromisoformat(stats["last_index_update"])
            diff = datetime.now() - last_upd
            if diff.days > 14:
                console.print(
                    f"[bold yellow]Warning:[/bold yellow] Index is {diff.days} days old. Run '[bold]qmd update[/bold]' to refresh."
                )
        except Exception:
            pass


@click.command()
@click.option(
    "--download/--no-download", default=False, help="Auto-download missing models"
)
@click.pass_obj
def check(ctx_obj, download):
    """Check system status (dependencies, CUDA, models)"""
    from rich.panel import Panel
    from rich.columns import Columns

    console.print(Panel.fit("[bold cyan]System Status Check[/bold cyan]"))

    # Check dependencies
    console.print("\n[bold]Dependencies:[/bold]")
    deps_status = {}

    # Check torch
    try:
        import torch

        deps_status["torch"] = ("✓", f"v{torch.__version__}")
    except ImportError:
        deps_status["torch"] = ("✗", "Not installed")

    # Check transformers
    try:
        import transformers

        deps_status["transformers"] = ("✓", f"v{transformers.__version__}")
    except ImportError:
        deps_status["transformers"] = ("✗", "Not installed")

    # Check fastembed
    try:
        import fastembed

        deps_status["fastembed"] = ("OK", "Installed")
    except ImportError:
        deps_status["fastembed"] = ("X", "Not installed")

    # Check device and CUDA
    console.print("\n[bold]Device:[/bold]")
    try:
        import torch
        import platform

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_count = torch.cuda.device_count()
            console.print(f"  [green]OK CUDA[/green]: {gpu_name}")
            console.print(f"  [dim]GPU Count: {gpu_count}[/dim]")
            console.print(f"  [dim]CUDA Version: {torch.version.cuda}[/dim]")
            console.print(f"  [dim]PyTorch Version: {torch.__version__}[/dim]")

            # Check each GPU
            for i in range(gpu_count):
                props = torch.cuda.get_device_properties(i)
                vram_gb = props.total_memory / (1024**3)
                console.print(
                    f"  [dim]GPU {i}: {props.name} ({vram_gb:.1f} GB, Compute {props.major}.{props.minor})[/dim]"
                )
        else:
            system = platform.system()
            console.print(f"  [yellow]WARN CPU-only[/yellow] (No CUDA detected)")
            console.print(f"  [dim]OS: {system}[/dim]")
            console.print(f"  [dim]PyTorch Version: {torch.__version__}[/dim]")

            # Provide install instructions based on OS
            if system == "Windows":
                console.print("\n  [cyan]To enable CUDA on Windows:[/cyan]")
                console.print(
                    "  1. Uninstall CPU version: pip uninstall torch torchvision torchaudio -y"
                )
                console.print(
                    "  2. Install CUDA 12.1: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121"
                )
            elif system == "Linux":
                console.print("\n  [cyan]To enable CUDA on Linux:[/cyan]")
                console.print(
                    "  1. Uninstall CPU version: pip uninstall torch torchvision torchaudio -y"
                )
                console.print(
                    "  2. Install CUDA 12.1: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121"
                )
    except ImportError:
        console.print(f"  [red]X Cannot detect (torch not installed)[/red]")

    # Check models
    console.print("\n[bold]Models:[/bold]")
    from qmd.models.downloader import ModelDownloader

    downloader = ModelDownloader()
    availability = downloader.check_availability()

    for model_key, available in availability.items():
        status_icon = "[green]OK[/green]" if available else "[red]X[/red]"
        size_mb = downloader.MODELS[model_key]["size_mb"]
        console.print(f"  {status_icon} {model_key.capitalize():12} ({size_mb}MB)")

    # Recommendations
    console.print("\n[bold]Recommendations:[/bold]")
    missing_deps = [k for k, (icon, _) in deps_status.items() if icon == "✗"]
    missing_models = [k for k, v in availability.items() if not v]

    if missing_deps:
        console.print(
            f"  [yellow]Install:[/yellow] pip install -e .[cpu]  # or .[cuda]"
        )
    if missing_models:
        if download:
            console.print(f"  [cyan]Downloading models...[/cyan]")
            downloader.download_all()
        else:
            console.print(
                f"  [yellow]Run:[/yellow] qmd download  # Download all models"
            )
            console.print(
                f"  [yellow]     or:[/yellow] python -m qmd.models.downloader"
            )
