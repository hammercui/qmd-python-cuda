"""
QMD 并发测试 Client Worker

两种角色（通过 --role 指定）：

  --role indexer  (Client 1)
      1. qmd collection add <path> --name <name>   # 注册 collection
      2. qmd index                                  # BM25 全文索引
      3. qmd embed --collection <name>              # 生成向量（调用 server embed）
      4. vsearch "本周todo" → POST /rerank          # 向量搜索 + LLM 重排序

  --role searcher (Client 2)
      直接 vsearch "本周todo" → POST /rerank        # 与 Client 1 并发执行

全部模型推理均在 qmd server 进程完成，本脚本不加载任何模型。
启动方式（由 test_full_models.py 自动调用，也可手动运行）：
  python test_client_worker.py --role indexer  --col-path "D:\\syncthing\\obsidian-mark\\一人" --col-name yiren
  python test_client_worker.py --role searcher --server-port 18765
"""

import sys
import time
import json
import argparse
import subprocess
from pathlib import Path

import requests


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def banner(text: str, width: int = 62):
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width + "\n", flush=True)


def step(label: str, detail: str = ""):
    sep = "─" * 50
    print(f"\n{sep}", flush=True)
    print(f"  STEP: {label}", flush=True)
    if detail:
        print(f"  {detail}", flush=True)
    print(sep, flush=True)


def find_qmd_exe() -> str | None:
    """找到当前 venv 中的 qmd 可执行文件。"""
    python_dir = Path(sys.executable).parent
    for candidate in [
        python_dir / "qmd.exe",
        python_dir / "Scripts" / "qmd.exe",
        python_dir / "qmd",
        python_dir / "Scripts" / "qmd",
    ]:
        if candidate.exists():
            return str(candidate)
    return None


def run_cli(qmd_exe: str | None, args: list, timeout: int = 600) -> tuple[int, str, float]:
    """
    执行 qmd CLI 命令，实时打印输出，返回 (returncode, full_output, elapsed_ms)。
    """
    if qmd_exe:
        cmd = [qmd_exe] + [str(a) for a in args]
    else:
        cmd = [sys.executable, "-m", "qmd"] + [str(a) for a in args]

    print(f"  $ {' '.join(cmd)}", flush=True)

    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        out = proc.stdout + proc.stderr

        lines = [l for l in out.splitlines() if l.strip()]
        for l in lines[:20]:
            print(f"     {l}", flush=True)
        if len(lines) > 20:
            print(f"     ... ({len(lines) - 20} more lines omitted)", flush=True)

        return proc.returncode, out, elapsed_ms
    except subprocess.TimeoutExpired:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        print(f"  [TIMEOUT after {elapsed_ms/1000:.0f}s]", flush=True)
        return -1, "[TIMEOUT]", elapsed_ms
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        print(f"  [ERROR] {e}", flush=True)
        return -1, str(e), elapsed_ms


def vsearch_and_rerank(
    base_url: str,
    query: str,
    col_name: str | None,
    top_k: int = 5,
) -> dict:
    """
    向量搜索 + LLM 重排序，全部通过 HTTP 调用 server。
    返回包含耗时和结果的 dict。
    """
    result = {
        "query": query,
        "vsearch_ms": 0.0,
        "rerank_ms": 0.0,
        "total_ms": 0.0,
        "raw_count": 0,
        "final_count": 0,
        "top1_title": None,
        "top1_score": None,
        "success": False,
    }

    # Step A: 向量搜索 POST /vsearch
    t0 = time.perf_counter()
    try:
        body = {"query": query, "limit": top_k * 3}
        if col_name:
            body["collection"] = col_name
        resp = requests.post(f"{base_url}/vsearch", json=body, timeout=60)
        vsearch_ms = (time.perf_counter() - t0) * 1000
        result["vsearch_ms"] = vsearch_ms

        if resp.status_code == 200:
            raw = resp.json().get("results", [])
        else:
            print(f"  ↳ /vsearch HTTP {resp.status_code}", flush=True)
            raw = []
    except Exception as e:
        vsearch_ms = (time.perf_counter() - t0) * 1000
        result["vsearch_ms"] = vsearch_ms
        print(f"  ↳ /vsearch 失败: {e}", flush=True)
        raw = []

    result["raw_count"] = len(raw)
    print(f"  ↳ vsearch   {vsearch_ms:8.1f} ms  ({len(raw)} results)", flush=True)

    # Step B: LLM 重排序 POST /rerank
    t0 = time.perf_counter()
    if raw:
        try:
            resp = requests.post(
                f"{base_url}/rerank",
                json={"query": query, "documents": raw, "top_k": top_k},
                timeout=300,
            )
            rerank_ms = (time.perf_counter() - t0) * 1000
            result["rerank_ms"] = rerank_ms

            if resp.status_code == 200:
                final = resp.json().get("results", raw[:top_k])
            else:
                print(f"  ↳ /rerank HTTP {resp.status_code}", flush=True)
                final = raw[:top_k]
        except Exception as e:
            rerank_ms = (time.perf_counter() - t0) * 1000
            result["rerank_ms"] = rerank_ms
            print(f"  ↳ /rerank 失败: {e}", flush=True)
            final = raw[:top_k]
    else:
        rerank_ms = 0.0
        result["rerank_ms"] = rerank_ms
        final = []

    result["final_count"] = len(final)
    result["total_ms"] = result["vsearch_ms"] + result["rerank_ms"]
    result["success"] = len(final) > 0

    print(f"  ↳ rerank    {rerank_ms:8.1f} ms  ({len(final)} results)", flush=True)
    print(f"  ↳ total     {result['total_ms']:8.1f} ms", flush=True)

    if final:
        top = final[0]
        score = top.get("rerank_score", top.get("score", 0))
        result["top1_title"] = top.get("title", "?")
        result["top1_score"] = round(float(score), 4)
        print(f"  ↳ Top-1     {result['top1_title']!r}  score={result['top1_score']}", flush=True)
    else:
        print("  ↳ [EMPTY] 没有找到任何结果", flush=True)

    return result


# ---------------------------------------------------------------------------
# 两种角色的主逻辑
# ---------------------------------------------------------------------------

def role_indexer(
    qmd_exe: str | None,
    col_path: str,
    col_name: str,
    server_port: int,
    query: str,
    out_file: str,
):
    """
    Client 1 — Indexer 角色：
      1. collection add（若已存在则记录并跳过）
      2. index（BM25 全文索引）
      3. embed --collection <name>（向量化，调用 server embed 接口）
      4. vsearch + rerank（向量搜索 + LLM 重排序）
    """
    base_url = f"http://localhost:{server_port}"
    timings = {}
    banner(f"Client 1 — Indexer  |  collection: {col_name}")
    print(f"  路径   : {col_path}")
    print(f"  查询   : {query!r}")
    print(f"  Server : {base_url}\n")

    # ── Step 1: collection add ──────────────────────────────────────────
    step("collection add", f"path={col_path}  name={col_name}")
    rc, out, ms = run_cli(
        qmd_exe,
        ["collection", "add", col_path, "--name", col_name],
    )
    timings["collection_add_ms"] = ms
    if rc != 0 and "already exists" not in out.lower():
        print(f"  [WARN] collection add 返回 rc={rc}，继续执行...", flush=True)
    else:
        print(f"  [OK] {ms:.0f} ms", flush=True)

    # ── Step 2: index ───────────────────────────────────────────────────
    step("index", "BM25 全文索引")
    rc, out, ms = run_cli(qmd_exe, ["index"], timeout=600)
    timings["index_ms"] = ms
    print(f"  [{'OK' if rc == 0 else 'WARN rc=' + str(rc)}] {ms:.0f} ms", flush=True)

    # ── Step 3: embed ───────────────────────────────────────────────────
    step("embed", f"生成向量 (collection={col_name})，调用 server embed 接口")
    rc, out, ms = run_cli(
        qmd_exe,
        ["embed", "--collection", col_name],
        timeout=1800,
    )
    timings["embed_ms"] = ms
    print(f"  [{'OK' if rc == 0 else 'WARN rc=' + str(rc)}] {ms:.0f} ms", flush=True)

    # ── Step 4: vsearch + rerank ────────────────────────────────────────
    step("vsearch + rerank", f"query={query!r}")
    sr = vsearch_and_rerank(base_url, query, col_name)
    timings.update({
        "vsearch_ms": sr["vsearch_ms"],
        "rerank_ms":  sr["rerank_ms"],
        "total_search_ms": sr["total_ms"],
    })

    # ── Summary ─────────────────────────────────────────────────────────
    banner("Client 1 — Summary")
    print(f"  collection add : {timings['collection_add_ms']:.0f} ms")
    print(f"  index          : {timings['index_ms']:.0f} ms")
    print(f"  embed          : {timings['embed_ms']:.0f} ms")
    print(f"  vsearch        : {timings['vsearch_ms']:.1f} ms")
    print(f"  rerank         : {timings['rerank_ms']:.1f} ms")
    print(f"  search total   : {timings['total_search_ms']:.1f} ms")

    output = {
        "role": "indexer",
        "col_name": col_name,
        "query": query,
        "timings": timings,
        "search_result": sr,
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved → {out_file}")


def role_searcher(
    col_name: str | None,
    server_port: int,
    query: str,
    repeat: int,
    out_file: str,
):
    """
    Client 2 — Searcher 角色：
      直接多次执行 vsearch + rerank，与 indexer 并发，
      观察 server 在 embed 占用 GPU 时的搜索响应时间。
    """
    base_url = f"http://localhost:{server_port}"
    banner(f"Client 2 — Searcher  |  {repeat}× vsearch+rerank")
    print(f"  查询   : {query!r}")
    print(f"  集合   : {col_name or '(全部)'}")
    print(f"  Server : {base_url}")
    print(f"  注意   : 与 Client 1 的 index/embed 并发执行\n")

    results = []
    t_wall_start = time.time()

    for i in range(1, repeat + 1):
        print(f"\n[{i}/{repeat}] vsearch + rerank  →  {query!r}", flush=True)
        sr = vsearch_and_rerank(base_url, query, col_name)
        sr["round"] = i
        results.append(sr)

    t_wall_end = time.time()

    # 统计
    ok = [r for r in results if r["success"]]
    total_list = [r["total_ms"] for r in ok]

    banner("Client 2 — Summary")
    print(f"  成功次数 : {len(ok)}/{len(results)}")
    if total_list:
        print(f"  Avg      : {sum(total_list)/len(total_list):.1f} ms")
        print(f"  Min      : {min(total_list):.1f} ms")
        print(f"  Max      : {max(total_list):.1f} ms")
    print(f"  Wall Time: {t_wall_end - t_wall_start:.1f} s")

    output = {
        "role": "searcher",
        "col_name": col_name,
        "query": query,
        "repeat": repeat,
        "wall_time_s": t_wall_end - t_wall_start,
        "results": results,
        "summary": {
            "total": len(results),
            "successful": len(ok),
            "avg_total_ms": sum(total_list) / len(total_list) if total_list else 0,
            "min_total_ms": min(total_list) if total_list else 0,
            "max_total_ms": max(total_list) if total_list else 0,
        },
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved → {out_file}")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="QMD 并发测试 Client Worker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--role",        required=True, choices=["indexer", "searcher"])
    parser.add_argument("--col-path",    default=r"D:\syncthing\obsidian-mark\一人",
                        help="[indexer] collection 目录路径")
    parser.add_argument("--col-name",    default="yiren",
                        help="collection 名称（indexer 注册用，searcher 过滤用）")
    parser.add_argument("--query",       default="本周todo",
                        help="搜索查询词")
    parser.add_argument("--server-port", type=int, default=18765)
    parser.add_argument("--repeat",      type=int, default=3,
                        help="[searcher] 重复搜索次数")
    parser.add_argument("--output",      default=None,
                        help="结果输出 JSON 文件")
    args = parser.parse_args()

    out_file = args.output or f"result_{args.role}.json"

    if args.role == "indexer":
        qmd_exe = find_qmd_exe()
        print(f"qmd exe: {qmd_exe or 'python -m qmd (fallback)'}\n", flush=True)
        role_indexer(
            qmd_exe     = qmd_exe,
            col_path    = args.col_path,
            col_name    = args.col_name,
            server_port = args.server_port,
            query       = args.query,
            out_file    = out_file,
        )
    else:
        role_searcher(
            col_name    = args.col_name,
            server_port = args.server_port,
            query       = args.query,
            repeat      = args.repeat,
            out_file    = out_file,
        )

    print("\n  按 Enter 关闭此终端...", flush=True)
    input()


if __name__ == "__main__":
    main()
