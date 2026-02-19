import click
from rich.console import Console
from rich.table import Table
from .database.manager import DatabaseManager
from .index.crawler import Crawler
from .search.fts import FTSSearcher
from .search.vector import VectorSearch
from .search.hybrid import HybridSearcher
from .search.rerank import LLMReranker
from .models.config import AppConfig, CollectionConfig
from .models.downloader import ModelDownloader
import os
import subprocess
import sys

console = Console()


def _check_virtual_env():
    """Check if running in a virtual environment."""
    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )

    if not in_venv:
        console.print("[yellow]Warning: Not running in a virtual environment[/yellow]")
        console.print(
            "[dim]Recommendation: Create and activate a virtual environment[/dim]"
        )
        console.print("[dim]  python -m venv .venv[/dim]")
        console.print("[dim]  .venv\\Scripts\\activate  (Windows)[/dim]")
        console.print("[dim]  source .venv/bin/activate  (Linux/macOS)[/dim]")
        console.print("")

    return in_venv


class Context:
    def __init__(self):
        self.config = AppConfig.load()
        self.db = DatabaseManager(self.config.db_path)


def _index_collection(col: CollectionConfig, db: DatabaseManager) -> int:
    """Scan and upsert all documents for a single collection. Returns indexed count."""
    crawler = Crawler(col.path, col.glob_pattern)
    count = 0
    for rel_path, content, doc_hash, title in crawler.scan():
        context_text = db.get_context_for_path(col.name, rel_path)
        db.upsert_document(col.name, rel_path, doc_hash, title, content, context=context_text)
        count += 1
    return count


@click.group()
@click.pass_context
def cli(ctx):
    """QMD - Query Markup Documents"""
    _check_virtual_env()
    ctx.obj = Context()


@cli.group(name="config")
def config_group():
    """Manage configuration"""
    pass


@config_group.command(name="show")
@click.pass_obj
def config_show(ctx_obj):
    """Show current configuration"""
    console.print(f"Config path: [cyan]{ctx_obj.config.db_path}[/cyan]")
    table = Table(title="Configuration")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("db_path", ctx_obj.config.db_path)
    table.add_row("Collections count", str(len(ctx_obj.config.collections)))

    console.print(table)


@config_group.command(name="set")
@click.argument("key")
@click.argument("value")
@click.pass_obj
def config_set(ctx_obj, key, value):
    """Set a configuration value"""
    if key == "db_path":
        ctx_obj.config.db_path = value
        ctx_obj.config.save()
        console.print(f"[green]Set db_path to:[/green] {value}")
    else:
        console.print(f"[red]Error:[/red] Unknown key '{key}'")


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option(
    "--port",
    default=18765,
    type=int,
    help="Port to bind to (kill existing qmd server if occupied)",
)
@click.option("--log-level", default="info", help="Log level")
def server(host, port, log_level):
    """Start the QMD MCP Server for embedding service"""
    import logging
    import signal
    import sys
    import time

    logging.basicConfig(level=getattr(logging, log_level.upper()))

    import uvicorn
    from qmd.server.app import app
    from qmd.server.port_manager import save_server_port

    # ------------------------------------------------------------------
    # 端口冲突处理：检测占用进程，若是 qmd server 则 kill，否则提示用户
    # ------------------------------------------------------------------
    actual_port = port
    try:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
        # 能绑定说明端口空闲，正常继续
    except OSError:
        console.print(f"[yellow]端口 {port} 已被占用，检查占用进程...[/yellow]")
        killed = False
        try:
            import psutil

            for conn in psutil.net_connections(kind="inet"):
                if conn.laddr.port == port and conn.status == "LISTEN":
                    pid = conn.pid
                    if pid is None:
                        continue
                    try:
                        proc = psutil.Process(pid)
                        cmdline = " ".join(proc.cmdline())
                        console.print(f"  PID {pid}: [dim]{cmdline[:80]}[/dim]")
                        if "qmd" in cmdline and "server" in cmdline:
                            console.print(
                                f"  [cyan]检测到旧的 qmd server，正在终止 PID {pid}...[/cyan]"
                            )
                            proc.terminate()
                            try:
                                proc.wait(timeout=5)
                            except psutil.TimeoutExpired:
                                proc.kill()
                                proc.wait(timeout=3)
                            console.print(f"  [green]PID {pid} 已终止[/green]")
                            time.sleep(0.5)  # 等待端口释放
                            killed = True
                        else:
                            console.print(
                                f"  [red]端口 {port} 被非 qmd 进程占用，无法自动终止。"
                                f"请手动释放后重试。[/red]"
                            )
                            sys.exit(1)
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        console.print(f"  [red]无法访问进程信息: {e}[/red]")
                    break

            if not killed:
                console.print(
                    f"[red]无法确定占用端口 {port} 的进程（可能需要管理员权限）。[/red]"
                )
                sys.exit(1)

        except ImportError:
            console.print(
                f"[red]缺少 psutil，无法自动检测占用进程。"
                f"请先 pip install psutil，或手动释放端口 {port}。[/red]"
            )
            sys.exit(1)

    # Save port for auto-discovery
    save_server_port(actual_port)

    console.print(f"[cyan]Starting QMD MCP Server[/cyan]")
    console.print(
        f"Host: [magenta]{host}[/magenta], Port: [magenta]{actual_port}[/magenta]"
    )
    console.print(f"[dim]Embed model: jinaai/jina-embeddings-v2-base-zh (INT8, 768d, zh+en)[/dim]")
    console.print(
        f"[dim]Reranker / Query Expansion: 首次调用 /expand /rerank 时懒加载[/dim]"
    )
    console.print("[yellow]Press Ctrl+C to stop[/yellow]")

    def signal_handler(sig, frame):
        console.print("\n[yellow]Shutting down server...[/yellow]")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    uvicorn.run(app, host=host, port=actual_port, log_level=log_level)


@cli.group()
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
            console.print(f"[dim]Tip: Run 'qmd embed' to generate vector embeddings.[/dim]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")


@collection.command(name="list")
@click.pass_obj
def collection_list(ctx_obj):
    """List all collections from config"""
    if not ctx_obj.config.collections:
        console.print("No collections found in config.")
        return

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


@cli.command()
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


@cli.command()
@click.argument("query")
@click.pass_obj
def search(ctx_obj, query):
    """BM25 full-text search"""
    searcher = FTSSearcher(ctx_obj.db)
    results = searcher.search(query)

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    table = Table(title=f"Search Results for: {query}")
    table.add_column("Title", style="cyan")
    table.add_column("Collection", style="magenta")
    table.add_column("Snippet", style="white")

    for r in results:
        table.add_row(r["title"], r["collection"], r["snippet"])

    console.print(table)


@cli.command()
@click.argument("path_query", required=False)
@click.pass_obj
def ls(ctx_obj, path_query):
    """List files in collections.

    Usage:
    qmd ls
    qmd ls personal
    qmd ls personal/notes
    """
    collection = None
    path_prefix = None

    if path_query:
        if "/" in path_query:
            collection, path_prefix = path_query.split("/", 1)
        else:
            # Check if it's a collection name
            collections = [c.name for c in ctx_obj.config.collections]
            if path_query in collections:
                collection = path_query
            else:
                collection = path_query

    files = ctx_obj.db.list_files(collection, path_prefix)

    if not files:
        console.print("[yellow]No files found.[/yellow]")
        return

    from datetime import datetime

    table = Table(box=None)
    table.add_column("Size", justify="right", style="green")
    table.add_column("Date", style="blue")
    table.add_column("Path", style="white")

    for f in files:
        size = f["size"]
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024 * 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size / (1024 * 1024):.1f} MB"

        try:
            dt = datetime.fromisoformat(f["modified_at"])
            date_str = dt.strftime("%Y-%m-%d %H:%M")
        except:
            date_str = f["modified_at"]

        full_path = f"qmd://{f['collection']}/{f['path']}"
        table.add_row(size_str, date_str, full_path)

    console.print(table)


@cli.command()
@click.option("--pull", is_flag=True, help="Run 'git pull' before indexing")
@click.pass_obj
def update(ctx_obj, pull):
    """Update all collections (re-scan, run update hooks)"""
    if not ctx_obj.config.collections:
        console.print("[yellow]No collections to update.[/yellow]")
        return

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


@cli.command()
@click.argument("target")
@click.option("-l", "--lines", type=int, help="Line limit")
@click.option("--line-numbers", is_flag=True, help="Show line numbers")
@click.pass_obj
def get(ctx_obj, target, lines, line_numbers):
    """Get document content by hash or path"""
    collection = None
    path = None
    line_range = None
    doc = None

    if target.startswith("qmd://"):
        target = target[6:]
        if ":" in target:
            target, line_range = target.split(":", 1)

        if "/" in target:
            collection, path = target.split("/", 1)
            doc = ctx_obj.db.get_document_by_path(collection, path)
        else:
            console.print(f"[red]Invalid path format:[/red] {target}")
            return
    elif ":" in target:
        path_part, range_part = target.split(":", 1)
        if "/" in path_part:
            collection, path = path_part.split("/", 1)
            line_range = range_part
            doc = ctx_obj.db.get_document_by_path(collection, path)
        else:
            doc = ctx_obj.db.get_document_by_hash(target.split(":")[0])
    else:
        doc = ctx_obj.db.get_document_by_hash(target)
        if not doc and "/" in target:
            collection, path = target.split("/", 1)
            doc = ctx_obj.db.get_document_by_path(collection, path)

    if not doc:
        console.print(f"[red]Document not found:[/red] {target}")
        return

    content = doc["content"] if "content" in doc else doc["doc"]
    content_lines = content.splitlines()

    start_line = 0
    end_line = len(content_lines)

    if line_range:
        if "-" in line_range:
            s, e = line_range.split("-")
            start_line = int(s) - 1 if s else 0
            end_line = int(e) if e else len(content_lines)
        else:
            start_line = int(line_range) - 1

    if lines:
        end_line = min(end_line, start_line + lines)

    start_line = max(0, min(start_line, len(content_lines)))
    end_line = max(start_line, min(end_line, len(content_lines)))

    selected_lines = content_lines[start_line:end_line]

    console.print(f"[bold cyan]Title:[/bold cyan] {doc['title']}")
    console.print(
        f"[bold cyan]Path:[/bold cyan] qmd://{doc['collection']}/{doc['path']}"
    )
    if line_range or lines:
        console.print(f"[bold cyan]Lines:[/bold cyan] {start_line + 1}-{end_line}")
    console.print("-" * 40)

    for i, line in enumerate(selected_lines):
        if line_numbers:
            console.print(f"[dim]{start_line + i + 1:4} | [/dim]{line}")
        else:
            console.print(line)


@cli.command()
@click.argument("pattern")
@click.option("--max-bytes", type=int, default=10, help="Max total KB (default 10)")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--md", "output_md", is_flag=True, help="Output as Markdown")
@click.option("--files", "output_files", is_flag=True, help="Output file list only")
@click.pass_obj
def multi_get(ctx_obj, pattern, max_bytes, output_json, output_md, output_files):
    """Get multiple documents by path pattern"""
    if "/" not in pattern:
        collection = pattern
        prefix = ""
    else:
        collection, prefix = pattern.split("/", 1)

    sql_pattern = prefix.replace("*", "%")
    if not sql_pattern.endswith("%") and not sql_pattern.endswith(".md"):
        sql_pattern += "%"

    files = ctx_obj.db.list_files(collection, sql_pattern)

    if not files:
        console.print(f"[yellow]No files matching pattern '{pattern}' found.[/yellow]")
        return

    if output_files:
        for f in files:
            console.print(f"qmd://{f['collection']}/{f['path']}")
        return

    total_size = sum(f["size"] for f in files)
    if total_size > max_bytes * 1024:
        console.print(
            f"[red]Error:[/red] Total size ({total_size / 1024:.1f} KB) exceeds limit ({max_bytes} KB)."
        )
        return

    results = []
    for f in files:
        doc = ctx_obj.db.get_document_by_path(f["collection"], f["path"])
        if doc:
            results.append(doc)

    if output_json:
        import json as json_lib

        console.print(
            json_lib.dumps(
                [
                    {
                        "collection": r["collection"],
                        "path": r["path"],
                        "title": r["title"],
                        "content": r["content"],
                    }
                    for r in results
                ],
                indent=2,
            )
        )
    elif output_md:
        output = []
        for r in results:
            output.append(
                f"# {r['title']}\nSource: qmd://{r['collection']}/{r['path']}\n\n{r['content']}\n"
            )
        console.print("\n---\n".join(output))
    else:
        for r in results:
            console.print(f"--- qmd://{r['collection']}/{r['path']} ---")
            console.print(r["content"])
            console.print()


@cli.command()
@click.pass_obj
def status(ctx_obj):
    """Show detailed system status"""
    stats = ctx_obj.db.get_detailed_stats()

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
        except:
            pass


@cli.command()
@click.option("--collection", help="Specific collection to embed")
@click.option(
    "--force", is_flag=True, help="Clear all existing embeddings and re-embed"
)
@click.option(
    "--mode",
    default="auto",
    type=click.Choice(["auto", "standalone", "server"]),
    help="Embedding mode: auto (default), standalone (local model), server (MCP server)",
)
@click.pass_obj
def embed(ctx_obj, collection, force, mode):
    """Generate embeddings for indexed documents using Jina ZH (768d)"""
    from qmd.llm.engine import LLMEngine
    from qmd.utils.chunker import chunk_document, embedding_to_bytes
    from datetime import datetime

    # Initialize LLM engine
    llm = LLMEngine(mode=mode)

    # Get documents to embed
    docs = ctx_obj.db.get_all_active_documents()

    if collection:
        docs = [d for d in docs if d["collection"] == collection]

    if not docs:
        console.print("[yellow]No documents to embed.[/yellow]")
        return

    # Force mode: clear all embeddings first
    if force:
        console.print(
            "[yellow]Force mode: clearing all existing embeddings...[/yellow]"
        )
        ctx_obj.db.clear_all_embeddings()

    # Ensure vectors_vec table exists (768 dimensions for Jina ZH)
    ctx_obj.db.ensure_vec_table(dimensions=768)

    console.print(
        f"Embedding [cyan]{len(docs)}[/cyan] documents with Jina ZH (768d)..."
    )

    from collections import defaultdict
    import time
    from rich.progress import Progress

    by_col = defaultdict(list)
    for d in docs:
        # Check if already embedded (unless force mode)
        if not force:
            chunks = ctx_obj.db.get_chunks_for_hash(d["hash"])
            if chunks:
                # Already embedded, skip
                by_col[d["collection"]].append(
                    {
                        "id": f"{d['collection']}:{d['path']}",
                        "hash": d["hash"],
                        "embedded": True,
                    }
                )
                continue

        by_col[d["collection"]].append(
            {
                "id": f"{d['collection']}:{d['path']}",
                "hash": d["hash"],
                "content": d["content"],
                "embedded": False,
            }
        )

    # Pre-collect all chunks per collection to get accurate chunk count for the
    # progress bar. chunk_document is pure string ops (fast), pre-pass is cheap.
    col_chunks: dict = {}  # col_name -> [{hash, seq, pos, text}]
    total_chunks_all = 0
    for col_name, col_docs in by_col.items():
        to_embed_pre = [doc for doc in col_docs if not doc["embedded"]]
        chunks_for_col = []
        for doc in to_embed_pre:
            for chunk in chunk_document(doc["content"]):
                chunks_for_col.append(
                    {
                        "hash": doc["hash"],
                        "seq": chunk["seq"],
                        "pos": chunk["pos"],
                        "text": chunk["text"],
                    }
                )
        col_chunks[col_name] = chunks_for_col
        total_chunks_all += len(chunks_for_col)

    if total_chunks_all == 0:
        console.print(
            "[green]All documents already embedded. Use --force to re-embed.[/green]"
        )
        return

    # Chunks per HTTP request to the server.
    # Server holds the processing lock for exactly EMBED_BATCH / GPU_EMBED_BATCH_SIZE
    # GPU micro-batches, keeping each lock acquisition to ~2-5 seconds.
    EMBED_BATCH = 32

    with Progress() as progress:
        task = progress.add_task("[cyan]Embedding...[/cyan]", total=total_chunks_all)

        for col_name, col_docs in by_col.items():
            cached = [doc for doc in col_docs if doc["embedded"]]
            all_chunks = col_chunks.get(col_name, [])

            console.print(
                f"  Processing collection: [cyan]{col_name}[/cyan]"
                f" ({len(col_docs)} docs, {len(all_chunks)} chunks)"
            )

            if all_chunks:
                start = time.time()
                done_in_col = 0

                for i in range(0, len(all_chunks), EMBED_BATCH):
                    batch = all_chunks[i : i + EMBED_BATCH]
                    texts = [c["text"] for c in batch]

                    embeddings = llm.embed_texts(texts)

                    # Insert immediately after each batch — no need to hold
                    # all embeddings in memory until collection is done
                    now = datetime.now().isoformat()
                    for chunk, embedding in zip(batch, embeddings):
                        ctx_obj.db.insert_embedding(
                            doc_hash=chunk["hash"],
                            seq=chunk["seq"],
                            pos=chunk["pos"],
                            embedding=embedding_to_bytes(embedding),
                            model="jinaai/jina-embeddings-v2-base-zh-q4f16",
                            embedded_at=now,
                        )

                    done_in_col += len(batch)
                    elapsed = time.time() - start
                    rate = done_in_col / elapsed if elapsed > 0 else 0
                    done_total = progress.tasks[task].completed + len(batch)
                    eta = int((total_chunks_all - done_total) / rate) if rate > 0 else 0

                    progress.advance(task, len(batch))
                    progress.update(
                        task,
                        description=(
                            f"[cyan]{col_name}[/cyan]"
                            f" {done_in_col}/{len(all_chunks)} chunks"
                            + (f", {eta}s left" if eta > 0 else "")
                        ),
                    )

            if cached:
                console.print(
                    f"    Using cached embeddings for {len(cached)} documents"
                )

    console.print("[bold green]Embedding complete![/bold green]")


@cli.command()
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


@cli.command()
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


@cli.command()
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
    downloader = ModelDownloader()
    availability = downloader.check_availability()

    for model_key, available in availability.items():
        status = "[green]OK[/green]" if available else "[red]X[/red]"
        size_mb = downloader.MODELS[model_key]["size_mb"]
        console.print(f"  {status} {model_key.capitalize():12} ({size_mb}MB)")

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


@cli.group()
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


if __name__ == "__main__":
    cli()
