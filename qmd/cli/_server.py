"""Server command."""

import click

from qmd.cli import console


@click.command()
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
    console.print(
        f"[dim]Embed model: jinaai/jina-embeddings-v2-base-zh (INT8, 768d, zh+en)[/dim]"
    )
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
