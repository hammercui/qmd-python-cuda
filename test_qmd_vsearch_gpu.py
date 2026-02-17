#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 QMD vsearch 的 GPU 使用情况
"""

import sys
import time
import subprocess
from pathlib import Path

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
            }
    except:
        pass
    return None

def print_gpu_stats(label, stats):
    """打印 GPU 统计"""
    if stats:
        print(f"{label}: "
              f"显存: {stats['memory_used']}MB / {stats['memory_total']}MB "
              f"({stats['memory_used']/stats['memory_total']*100:.1f}%) | "
              f"GPU: {stats['gpu_util']}% | "
              f"显存利用率: {stats['memory_util']}%")

def main():
    print("=" * 70)
    print("QMD VSearch GPU 使用测试")
    print("=" * 70)

    # 初始状态
    print("\n步骤 1: 初始 GPU 状态")
    print("-" * 70)
    gpu_before = get_gpu_stats()
    print_gpu_stats("GPU (初始)", gpu_before)

    # 执行 vsearch
    print("\n步骤 2: 执行 qmd vsearch")
    print("-" * 70)

    queries = [
        "机器学习算法",
        "深度学习框架",
        "EchoSync 项目",
        "神经网络优化",
    ]

    results = []

    for i, query in enumerate(queries, 1):
        print(f"\n查询 {i}/{len(queries)}: {query}")

        # 查询前GPU状态
        gpu_query_before = get_gpu_stats()
        print_gpu_stats("  查询前", gpu_query_before)

        # 执行查询
        start_time = time.time()
        result = subprocess.run(
            [str(QMD_CLI), "vsearch", query],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(QMD_PROJECT)
        )
        elapsed = time.time() - start_time

        success = result.returncode == 0
        print(f"  结果: {'✅' if success else '❌'} | 耗时: {elapsed:.3f}s")

        # 查询后GPU状态
        gpu_query_after = get_gpu_stats()
        print_gpu_stats("  查询后", gpu_query_after)

        if gpu_query_before and gpu_query_after:
            mem_delta = gpu_query_after['memory_used'] - gpu_query_before['memory_used']
            util_delta = gpu_query_after['gpu_util'] - gpu_query_before['gpu_util']
            print(f"  变化: 显存 {mem_delta:+d}MB, GPU利用率 {util_delta:+d}%")

        results.append({
            'query': query,
            'time': elapsed,
            'success': success,
            'gpu_before': gpu_query_before,
            'gpu_after': gpu_query_after,
        })

        time.sleep(1)  # 等待GPU稳定

    # 最终状态
    print("\n步骤 3: 最终 GPU 状态")
    print("-" * 70)
    gpu_after = get_gpu_stats()
    print_gpu_stats("GPU (最终)", gpu_after)

    # 统计分析
    print("\n" + "=" * 70)
    print("性能分析")
    print("=" * 70)

    success_count = sum(1 for r in results if r['success'])
    total_time = sum(r['time'] for r in results)
    avg_time = total_time / len(results)

    print(f"\n查询统计:")
    print(f"  成功: {success_count}/{len(results)}")
    print(f"  总耗时: {total_time:.3f}s")
    print(f"  平均耗时: {avg_time:.3f}s")

    if gpu_before and gpu_after:
        mem_delta = gpu_after['memory_used'] - gpu_before['memory_used']
        print(f"\n显存变化:")
        print(f"  初始: {gpu_before['memory_used']}MB")
        print(f"  最终: {gpu_after['memory_used']}MB")
        print(f"  增长: {mem_delta}MB")

        if mem_delta > 500:
            print(f"  ✅ 模型已加载到 GPU (显存增长 {mem_delta}MB)")
        elif mem_delta > 100:
            print(f"  ⚠️  显存增长较小 ({mem_delta}MB),可能使用混合模式")
        else:
            print(f"  ❌ 显存无增长,可能使用 CPU")

    # GPU 利用率分析
    peak_gpu_util = 0
    for r in results:
        if r['gpu_after']:
            peak_gpu_util = max(peak_gpu_util, r['gpu_after']['gpu_util'])

    print(f"\nGPU 利用率:")
    print(f"  峰值: {peak_gpu_util}%")

    if peak_gpu_util > 50:
        print(f"  ✅ GPU 活跃使用")
    elif peak_gpu_util > 10:
        print(f"  ⚠️  GPU 使用率偏低,可能是混合模式")
    else:
        print(f"  ❌ GPU 基本闲置,主要使用 CPU")

    return 0

if __name__ == "__main__":
    sys.exit(main())
