#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 QMD CLI 自动拉起 Server + 并发查询性能
"""

import sys
import time
import subprocess
import threading
from pathlib import Path
from datetime import datetime

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

QMD_PROJECT = Path(r"D:\MoneyProjects\qmd-python")
QMD_CLI = QMD_PROJECT / ".venv" / "Scripts" / "qmd.exe"

def get_gpu_stats():
    """获取 GPU 统计"""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used,memory.total,utilization.gpu,utilization.memory',
             '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(', ')
            return {
                'memory_used': int(parts[0]),
                'memory_total': int(parts[1]),
                'gpu_util': int(parts[2]),
                'memory_util': int(parts[3]) if len(parts) > 3 else 0,
                'timestamp': time.time()
            }
    except:
        pass
    return None

def monitor_gpu(duration=60, interval=1):
    """监控 GPU 使用"""
    print("\n" + "=" * 70)
    print("GPU 监控启动")
    print("=" * 70)

    stats = []
    start_time = time.time()

    while time.time() - start_time < duration:
        stat = get_gpu_stats()
        if stat:
            stats.append(stat)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"显存: {stat['memory_used']}MB / {stat['memory_total']}MB "
                  f"({stat['memory_used']/stat['memory_total']*100:.1f}%) | "
                  f"GPU 利用率: {stat['gpu_util']}% | "
                  f"显存利用率: {stat['memory_util']}%")
        time.sleep(interval)

    return stats

def run_qmd_query(worker_id: int, query: str):
    """执行 QMD 查询"""
    print(f"\n[Worker {worker_id}] 启动")
    print(f"[Worker {worker_id}] 查询: {query}")

    start_time = time.time()

    try:
        # 执行 qmd search
        print(f"[Worker {worker_id}] 执行 qmd search...")
        result = subprocess.run(
            [str(QMD_CLI), "search", query],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(QMD_PROJECT)
        )

        search_time = time.time() - start_time
        print(f"[Worker {worker_id}] qmd search 完成 (耗时 {search_time:.3f}s)")
        print(f"[Worker {worker_id}] 返回码: {result.returncode}")

        # 统计输出行数
        output_lines = result.stdout.count('\n')
        print(f"[Worker {worker_id}] 输出行数: {output_lines}")

        # 执行 qmd vsearch（如果 server 可用）
        print(f"[Worker {worker_id}] 执行 qmd vsearch...")
        start_vsearch = time.time()

        result_vsearch = subprocess.run(
            [str(QMD_CLI), "vsearch", query],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(QMD_PROJECT)
        )

        vsearch_time = time.time() - start_vsearch
        print(f"[Worker {worker_id}] qmd vsearch 完成 (耗时 {vsearch_time:.3f}s)")
        print(f"[Worker {worker_id}] 返回码: {result_vsearch.returncode}")

        total_time = time.time() - start_time

        return {
            'worker_id': worker_id,
            'search_time': search_time,
            'vsearch_time': vsearch_time,
            'total_time': total_time,
            'search_success': result.returncode == 0,
            'vsearch_success': result_vsearch.returncode == 0,
        }

    except subprocess.TimeoutExpired:
        total_time = time.time() - start_time
        print(f"[Worker {worker_id}] 超时 (120s)")
        return {
            'worker_id': worker_id,
            'search_time': 0,
            'vsearch_time': 0,
            'total_time': total_time,
            'search_success': False,
            'vsearch_success': False,
            'error': 'Timeout',
        }
    except Exception as e:
        total_time = time.time() - start_time
        print(f"[Worker {worker_id}] 错误: {e}")
        return {
            'worker_id': worker_id,
            'search_time': 0,
            'vsearch_time': 0,
            'total_time': total_time,
            'search_success': False,
            'vsearch_success': False,
            'error': str(e),
        }

def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("QMD CLI + Server 并发测试")
    print("=" * 70)

    print(f"\n测试配置:")
    print(f"  QMD CLI: {QMD_CLI}")
    print(f"  并发数: 2")
    print(f"  查询: 机器学习, EchoSync")

    # 初始 GPU 状态
    print("\n" + "-" * 70)
    print("初始 GPU 状态")
    print("-" * 70)

    initial_gpu = get_gpu_stats()
    if initial_gpu:
        print(f"显存: {initial_gpu['memory_used']}MB / {initial_gpu['memory_total']}MB")
        print(f"GPU 利用率: {initial_gpu['gpu_util']}%")
    else:
        print("无法获取 GPU 状态")

    # 启动 GPU 监控线程
    monitor_thread = threading.Thread(target=monitor_gpu, kwargs={'duration': 120, 'interval': 2})
    monitor_thread.daemon = True
    monitor_thread.start()

    # 等待一下让监控先输出
    time.sleep(1)

    # 启动并发查询
    print("\n" + "-" * 70)
    print("启动并发查询")
    print("-" * 70)

    start_time = time.time()

    # 使用线程池并发执行
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = []
        futures.append(executor.submit(run_qmd_query, 1, "机器学习"))
        futures.append(executor.submit(run_qmd_query, 2, "EchoSync"))

        results = [f.result() for f in futures]

    total_time = time.time() - start_time

    # 等待监控完成
    monitor_thread.join(timeout=5)

    # 最终 GPU 状态
    print("\n" + "-" * 70)
    print("最终 GPU 状态")
    print("-" * 70)

    final_gpu = get_gpu_stats()
    if final_gpu:
        print(f"显存: {final_gpu['memory_used']}MB / {final_gpu['memory_total']}MB")
        print(f"GPU 利用率: {final_gpu['gpu_util']}%")

    # 打印结果
    print("\n" + "=" * 70)
    print("测试结果")
    print("=" * 70)

    print(f"\n{'Worker':<10} {'Search(s)':<12} {'VSearch(s)':<12} {'Total(s)':<12} {'Search':<10} {'VSearch':<10}")
    print("-" * 80)

    for r in results:
        search_status = "✅" if r['search_success'] else "❌"
        vsearch_status = "✅" if r['vsearch_success'] else "❌"

        print(f"{r['worker_id']:<10} "
              f"{r['search_time']:<12.3f} "
              f"{r['vsearch_time']:<12.3f} "
              f"{r['total_time']:<12.3f} "
              f"{search_status:<10} "
              f"{vsearch_status:<10}")

        if 'error' in r:
            print(f"  错误: {r['error']}")

    print("-" * 80)
    print(f"{'总计':<10} {'':<12} {'':<12} {total_time:<12.3f}")

    # 统计
    search_success = sum(1 for r in results if r['search_success'])
    vsearch_success = sum(1 for r in results if r['vsearch_success'])

    print(f"\n成功率:")
    print(f"  Search: {search_success}/{len(results)} ({search_success/len(results)*100:.0f}%)")
    print(f"  VSearch: {vsearch_success}/{len(results)} ({vsearch_success/len(results)*100:.0f}%)")

    # 显存分析
    if initial_gpu and final_gpu:
        mem_increase = final_gpu['memory_used'] - initial_gpu['memory_used']
        print(f"\n显存使用:")
        print(f"  初始: {initial_gpu['memory_used']} MB")
        print(f"  最终: {final_gpu['memory_used']} MB")
        print(f"  增加: {mem_increase} MB")

        if mem_increase > 100:
            print(f"  ✅ Server 已加载到 GPU")
        else:
            print(f"  ⚠️  显存增长不明显，可能使用 CPU")

    # 性能分析
    avg_search = sum(r['search_time'] for r in results) / len(results)
    avg_vsearch = sum(r['vsearch_time'] for r in results if r['vsearch_success']) / max(vsearch_success, 1)

    print(f"\n平均耗时:")
    print(f"  Search: {avg_search:.3f}s")
    print(f"  VSearch: {avg_vsearch:.3f}s")

    print(f"\n吞吐量:")
    print(f"  Search: {len(results)/total_time:.2f} queries/s")

    return 0

if __name__ == "__main__":
    sys.exit(main())
