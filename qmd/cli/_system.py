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

    # Check onnxruntime
    try:
        import onnxruntime

        deps_status["onnxruntime"] = ("✓", f"v{onnxruntime.__version__}")
    except ImportError:
        deps_status["onnxruntime"] = ("✗", "Not installed")

    # Check optimum
    try:
        import optimum

        try:
            optimum_version = optimum.__version__
        except AttributeError:
            optimum_version = "installed"
        deps_status["optimum"] = ("✓", f"v{optimum_version}")
    except ImportError:
        deps_status["optimum"] = ("✗", "Not installed")

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
        import onnxruntime as ort
        import platform
        import subprocess

        providers = ort.get_available_providers()
        if "CUDAExecutionProvider" in providers:
            # Query GPU info via nvidia-smi (no torch needed)
            try:
                smi = subprocess.run(
                    ["nvidia-smi",
                     "--query-gpu=name,memory.total,driver_version",
                     "--format=csv,noheader"],
                    capture_output=True, text=True, timeout=5,
                )
                if smi.returncode == 0:
                    for line in smi.stdout.strip().splitlines():
                        name, mem, drv = [x.strip() for x in line.split(",")]
                        console.print(f"  [green]OK CUDA[/green]: {name}")
                        console.print(f"  [dim]VRAM: {mem}  Driver: {drv}[/dim]")
                else:
                    console.print("  [green]OK CUDA[/green]: (nvidia-smi unavailable)")
            except Exception:
                console.print("  [green]OK CUDA[/green]: (nvidia-smi unavailable)")
            console.print(f"  [dim]OnnxRuntime: v{ort.__version__}[/dim]")
            console.print(f"  [dim]OS: {platform.system()}[/dim]")
        else:
            console.print(f"  [yellow]WARN CPU-only[/yellow] (CUDAExecutionProvider not available)")
            console.print(f"  [dim]OS: {platform.system()}[/dim]")
            console.print(f"  [dim]OnnxRuntime: v{ort.__version__}[/dim]")
            console.print(f"  [dim]Available providers: {', '.join(providers)}[/dim]")
            console.print("\n  [cyan]To enable CUDA:[/cyan]")
            console.print("  pip install onnxruntime-gpu")
    except Exception as e:
        console.print(f"  [red]X Cannot detect device: {e}[/red]")

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


@click.command()
@click.option("--model", "-m", default=None,
              type=click.Choice(["embedding", "reranker", "expansion"]),
              help="Only download a specific model (default: all)")
@click.option("--source", "-s", default=None,
              type=click.Choice(["hf", "ms"]),
              help="Force download source: hf=HuggingFace, ms=ModelScope")
def download(model, source):
    """Download ONNX models (embedding / reranker / expansion)"""
    from qmd.models.downloader import ModelDownloader

    downloader = ModelDownloader(model_source=source)

    if model:
        console.print(f"[cyan]Downloading model:[/cyan] {model}")
        try:
            path = downloader._parallel_download(model)
            if path:
                console.print(f"[green]OK[/green] {model} → {path}")
            else:
                console.print(f"[red]FAIL[/red] {model}: download returned None")
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
    else:
        console.print("[cyan]Downloading all models...[/cyan]")
        availability = downloader.check_availability()
        for key, available in availability.items():
            if available:
                console.print(f"[dim]  {key}: already downloaded, skipping[/dim]")
            else:
                console.print(f"  Downloading [bold]{key}[/bold]...")
                try:
                    path = downloader._parallel_download(key)
                    if path:
                        console.print(f"  [green]OK[/green] {key} → {path}")
                    else:
                        console.print(f"  [red]FAIL[/red] {key}: download returned None")
                except Exception as e:
                    console.print(f"  [red]FAIL[/red] {key}: {e}")
        console.print("[green]Done.[/green]")
