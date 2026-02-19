"""Document retrieval commands (get, ls, multi_get)."""

from datetime import datetime

import click

from qmd.cli import console


@click.command()
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

    from rich.table import Table

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
        except Exception:
            date_str = f["modified_at"]

        full_path = f"qmd://{f['collection']}/{f['path']}"
        table.add_row(size_str, date_str, full_path)

    console.print(table)


@click.command()
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


@click.command()
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
