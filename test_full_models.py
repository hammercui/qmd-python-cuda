"""
QMD Full Model Pipeline Test  —  多终端版

验证完整 LLM 管道的并发性能：
  Query Expansion (Qwen2.5-0.5B)
  → Hybrid Search (BM25 + Vector via qmd server)
  → LLM Reranking (Qwen3-Reranker-0.6B)

终端布局（自动弹出）：
  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
  │   QMD Server         │  │   QMD Client 1       │  │   QMD Client 2       │
  │  (embedding svc)     │  │  expand→search→rerank│  │  expand→search→rerank│
  └──────────────────────┘  └──────────────────────┘  └──────────────────────┘
  当前终端：GPU 监控 + 结果汇总

使用方式：
  python test_full_models.py
  python test_full_models.py --clients 2 --queries 5 --port 18765
"""

import os
import sys
import json
import time
import threading
import subprocess
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# 默认配置
# ---------------------------------------------------------------------------
DEFAULT_PORT = 18765
DEFAULT_CLIENTS = 2
DEFAULT_QUERIES = 5      # LLM rerank 较慢，建议从小值开始


# ---------------------------------------------------------------------------
# GPU 监控
# ---------------------------------------------------------------------------
class GpuMonitor:
    """通过 pynvml 或 nvidia-smi 轮询 GPU 状态。"""

    def __init__(self, interval: float = 2.0):
        self.interval = interval
        self.readings: list = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._use_pynvml = False
        self._handle = None
        self._available = False
        self._init()

    def _init(self):
        # 优先尝试 pynvml
        try:
            import pynvml
            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(self._handle)
            if isinstance(name, bytes):
                name = name.decode()
            print(f"[GPU] 检测到 GPU（pynvml）: {name}", flush=True)
            self._use_pynvml = True
            self._available = True
            return
        except Exception:
            pass

        # 退而求其次：nvidia-smi
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                print(f"[GPU] 检测到 GPU（nvidia-smi）: {r.stdout.strip()}", flush=True)
                self._available = True
                return
        except Exception:
            pass

        print("[GPU] 未找到 NVIDIA GPU 或驱动，跳过 GPU 监控", flush=True)

    def _sample(self) -> dict | None:
        if self._use_pynvml:
            try:
                import pynvml
                mem  = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(self._handle)
                return {
                    "ts": time.time(),
                    "util_pct": util.gpu,
                    "mem_used_mb": mem.used >> 20,
                    "mem_total_mb": mem.total >> 20,
                }
            except Exception:
                return None
        else:
            try:
                r = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=utilization.gpu,memory.used,memory.total",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True, text=True, timeout=5,
                )
                if r.returncode == 0:
                    parts = [p.strip() for p in r.stdout.strip().split(",")]
                    return {
                        "ts": time.time(),
                        "util_pct": int(parts[0]),
                        "mem_used_mb": int(parts[1]),
                        "mem_total_mb": int(parts[2]),
                    }
            except Exception:
                return None

    def _loop(self):
        while not self._stop.is_set():
            s = self._sample()
            if s:
                self.readings.append(s)
                print(
                    f"[GPU] {s['util_pct']:3d}%  "
                    f"VRAM {s['mem_used_mb']:5d} / {s['mem_total_mb']} MB",
                    flush=True,
                )
            self._stop.wait(self.interval)

    def start(self):
        if self._available:
            self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5)

    def summary(self) -> dict:
        if not self.readings:
            return {}
        return {
            "samples": len(self.readings),
            "max_util_pct": max(r["util_pct"] for r in self.readings),
            "avg_util_pct": sum(r["util_pct"] for r in self.readings) / len(self.readings),
            "max_mem_used_mb": max(r["mem_used_mb"] for r in self.readings),
            "mem_total_mb": self.readings[-1]["mem_total_mb"],
        }


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
def wait_for_server(port: int, timeout: int = 120) -> bool:
    """等待 server /health 端点就绪。"""
    import requests  # noqa: PLC0415

    print(f"等待 server 就绪（port {port}）", end="", flush=True)
    for _ in range(timeout):
        try:
            if requests.get(f"http://localhost:{port}/health", timeout=2).status_code == 200:
                print(" [OK]", flush=True)
                return True
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(1)
    print(" [TIMEOUT]", flush=True)
    return False


def open_new_console(title: str, exe_path: str, args: list):
    """在独立 cmd.exe 窗口中运行命令（Windows）。

    通过写入临时 .bat 文件执行，彻底避免引号嵌套导致
    "文件名、目录名或卷标语法不正确" 的错误。

    原理：cmd /k 只需传入一个无需额外引号的 .bat 路径，
    exe_path 和 args 的引号由 .bat 内容自己处理，不会被
    subprocess.list2cmdline 再次转义。
    """
    import tempfile, os

    # 对含空格的参数加引号（仅 .bat 内部使用，不经过 subprocess 转义）
    def quote(s: str) -> str:
        return f'"{s}"' if " " in s else s

    args_str = " ".join(quote(str(a)) for a in args)
    bat_content = "\r\n".join([
        "@echo off",
        f"title {title}",
        f'"{exe_path}" {args_str}',
        "echo.",
        "pause",
        "",
    ])

    fd, bat_path = tempfile.mkstemp(suffix=".bat", prefix="qmd_launch_")
    os.write(fd, bat_content.encode("gbk", errors="replace"))
    os.close(fd)

    subprocess.Popen(
        ["cmd", "/k", bat_path],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )


def launch_server(port: int, log_level: str = "debug"):
    """在新终端中启动 qmd server。"""
    # 从当前 Python 环境找 qmd.exe，避免 venv 未激活问题
    python_dir = Path(sys.executable).parent
    for candidate in [
        python_dir / "qmd.exe",
        python_dir / "Scripts" / "qmd.exe",
    ]:
        if candidate.exists():
            qmd_exe = candidate
            break
    else:
        # 回退：用 python -m qmd（总是能找到）
        qmd_exe = None

    print(f"[LAUNCH] QMD Server  →  新终端窗口")
    if qmd_exe:
        open_new_console(
            "QMD Server",
            str(qmd_exe),
            ["server", "--port", str(port), "--log-level", log_level],
        )
    else:
        open_new_console(
            "QMD Server",
            sys.executable,
            ["-m", "qmd", "server", "--port", str(port), "--log-level", log_level],
        )


COL_PATH = r"D:\syncthing\obsidian-mark\一人"   # indexer 角色扫描的目录
COL_NAME = "yiren"                               # collection 名称
SEARCH_QUERY = "本周todo"                        # 并发测试查询词


def launch_client(client_id: int, port: int, n_queries: int, collection: str, out_dir: Path):
    """在新终端中启动客户端 worker 脚本。

    client_id == 1  →  indexer（注册 collection → index → embed → vsearch+rerank）
    client_id >= 2  →  searcher（直接 vsearch+rerank，与 indexer 并发）
    """
    python_exe = sys.executable
    worker = Path(__file__).parent / "test_client_worker.py"
    out_file = out_dir / f"client_{client_id}_results.json"

    if client_id == 1:
        role = "indexer"
        cli_args = [
            str(worker),
            "--role",        role,
            "--col-path",    COL_PATH,
            "--col-name",    COL_NAME,
            "--query",       SEARCH_QUERY,
            "--server-port", str(port),
            "--output",      str(out_file),
        ]
    else:
        role = "searcher"
        cli_args = [
            str(worker),
            "--role",        role,
            "--col-name",    COL_NAME,
            "--query",       SEARCH_QUERY,
            "--server-port", str(port),
            "--repeat",      str(n_queries),
            "--output",      str(out_file),
        ]

    print(f"[LAUNCH] Client {client_id} ({role})  →  新终端窗口")

    open_new_console(
        f"QMD Client {client_id} ({role})",
        python_exe,
        cli_args,
    )


def wait_for_result_files(files: list, timeout: int = 900) -> bool:
    """轮询，直到所有 client 写出结果文件。"""
    print(f"\n等待 {len(files)} 个客户端完成（最长 {timeout}s）...")
    deadline = time.time() + timeout
    pending = set(str(f) for f in files)
    while pending and time.time() < deadline:
        for fp in list(pending):
            if Path(fp).exists():
                pending.remove(fp)
                print(f"  ✓  {Path(fp).name}", flush=True)
        if pending:
            time.sleep(4)
    if pending:
        print(f"  [TIMEOUT] 仍未收到: {[Path(f).name for f in pending]}")
        return False
    return True


def print_summary(result_files: list, gpu_stats: dict):
    """打印汇总报告。"""
    sep = "=" * 60

    print(f"\n{sep}")
    print("  FULL MODEL PIPELINE — 测试结果汇总")
    print(f"  Pipeline: Expand → Hybrid Search → LLM Rerank")
    print(sep)

    all_data = []
    for fp in result_files:
        try:
            with open(fp, encoding="utf-8") as f:
                all_data.append(json.load(f))
        except Exception as e:
            print(f"  [ERROR] 无法读取 {Path(fp).name}: {e}")

    for data in all_data:
        s = data.get("summary", {})
        cid = data.get("client_id", "?")
        mode = data.get("mode", "query")
        wall_t = data.get("wall_time_s", 0)
        print(f"\n  Client {cid}  [{mode}]:")
        print(f"    成功查询       : {s.get('successful', 0)}/{s.get('total', 0)}")
        print(f"    Avg latency    : {s.get('avg_ms', 0):.1f} ms  (含 CLI 启动开销)")
        print(f"    Min / Max      : {s.get('min_ms', 0):.1f} / {s.get('max_ms', 0):.1f} ms")
        print(f"    Median         : {s.get('median_ms', 0):.1f} ms")
        print(f"    Wall Time      : {wall_t:.1f} s")

    if len(all_data) > 1:
        avg_total = (
            sum(d["summary"]["avg_total_ms"] for d in all_data if "summary" in d)
            / len(all_data)
        )
        print(f"\n  ◆ 跨客户端平均总延迟 : {avg_total:.1f} ms")

    if gpu_stats:
        print(f"\n  GPU 统计（采样 {gpu_stats.get('samples', 0)} 次）:")
        print(f"    峰值利用率   : {gpu_stats.get('max_util_pct', 'N/A')}%")
        print(f"    平均利用率   : {gpu_stats.get('avg_util_pct', 0):.1f}%")
        print(f"    峰值 VRAM    : {gpu_stats.get('max_mem_used_mb', 'N/A')} MB"
              f"  /  {gpu_stats.get('mem_total_mb', '?')} MB")
    else:
        print("\n  GPU 统计: 未检测到 GPU 数据")

    print(f"\n{sep}\n")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="QMD Full Model Pipeline Test（多终端版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python test_full_models.py                        # 默认 2 客户端 × 5 查询
  python test_full_models.py --queries 10           # 每客户端 10 个查询
  python test_full_models.py --clients 3 --queries 3
        """,
    )
    parser.add_argument("--port",       type=int, default=DEFAULT_PORT,    help="Server 端口")
    parser.add_argument("--clients",    type=int, default=DEFAULT_CLIENTS, help="并发客户端数量")
    parser.add_argument("--queries",    type=int, default=DEFAULT_QUERIES, help="每客户端查询数（LLM 重排序较慢，建议 ≤10）")
    parser.add_argument("--collection", type=str, default="todo",          help="搜索集合名称")
    parser.add_argument("--log-level",  type=str, default="debug",         help="Server 日志级别")
    args = parser.parse_args()

    out_dir = Path(__file__).parent
    result_files = [out_dir / f"client_{i}_results.json" for i in range(1, args.clients + 1)]

    print("\n" + "=" * 60)
    print("  QMD Full Model Pipeline Test")
    print("  Expand → Hybrid Search → LLM Rerank")
    print(f"  客户端: {args.clients}  |  每客户端查询: {args.queries}  |  端口: {args.port}")
    print("=" * 60)
    print()
    print("  说明：")
    print("  • 每个客户端窗口会各自加载 LLM 模型（首次较慢）")
    print("  • 两个客户端会并发运行，GPU 资源竞争可被观察到")
    print("  • 当前终端显示 GPU 利用率和最终汇总")
    print()

    # 清理旧结果
    for fp in result_files:
        if fp.exists():
            fp.unlink()

    # 1. 启动 Server（新终端）
    launch_server(args.port, args.log_level)

    # 2. 等待 Server 就绪
    print()
    if not wait_for_server(args.port, timeout=120):
        print("[ERROR] Server 启动失败，退出。")
        sys.exit(1)
    print("Server 就绪！等待 3s 让模型完全初始化...", flush=True)
    time.sleep(3)

    # 3. 启动 GPU 监控（当前终端）
    print()
    monitor = GpuMonitor(interval=2.0)
    monitor.start()
    print()

    # 4. 启动 N 个客户端（各自新终端）
    for i in range(1, args.clients + 1):
        launch_client(i, args.port, args.queries, args.collection, out_dir)
        time.sleep(1.5)  # 稍微错开启动，避免同时抢 GPU 显存

    # 5. 等待所有客户端写出结果文件
    all_done = wait_for_result_files(result_files)

    # 6. 停止 GPU 监控
    monitor.stop()
    gpu_stats = monitor.summary()

    # 7. 汇总报告
    print_summary(result_files, gpu_stats)

    if all_done:
        print("[OK] 测试完成！Server 终端保持运行，可手动关闭。\n")
    else:
        print("[WARN] 部分客户端未完成，已显示已有结果。\n")


if __name__ == "__main__":
    main()
