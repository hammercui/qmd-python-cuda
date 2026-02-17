#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整的 QMD CLI + Server 测试
包括 Server 冷启动、并发查询、性能统计
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

def kill_existing_server():
    """停止已有的 Server 进程"""
    print("\n" + "-" * 70)
    print("清理已有 Server 进程")
    print("-" * 70)

    try:
        # 查找 qmd server 进程
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq qmd.exe', '/FO', 'CSV'],
            capture_output=True,
            text=True
        )

        if 'qmd.exe' in result.stdout:
            print("发现已有 qmd.exe 进程，正在停止...")
            subprocess.run(['taskkill', '/F', '/IM', 'qmd.exe'], capture_output=True)
            time.sleep(2)
            print("✅ 已停止")
        else:
            print("✅ 无已有进程")

    except Exception as e:
        print(f"清理失败: {e}")

def get_gpu_stats():
    """获取 GPU 统计"""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used,memory.total,utilization.gpu,utilization.memory,power.draw',
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
                'power_draw': float(parts[4]) if len(parts) > 4 else 0,
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
              f"显存利用率: {stats['memory_util']}% | "
              f"功耗: {stats['power_draw']}W")

class TestStats:
    """测试统计"""
    def __init__(self):
        self.gpu_before = None
        self.gpu_after = None
        self.gpu_peak = 0
        self.results = []

    def record_gpu(self):
        """记录 GPU 状态"""
        stats = get_gpu_stats()
        if stats:
            if stats['memory_used'] > self.gpu_peak:
                self.gpu_peak = stats['memory_used']
        return stats

def run_qmd_query(worker_id: int, query: str, use_vsearch: bool = True):
    """执行 QMD 查询"""
    print(f"\n[Worker {worker_id}] 启动")
    print(f"[Worker {worker_id}] 查询: {query}")

    start_time = time.time()

    try:
        # 执行 qmd search
        print(f"[Worker {worker_id}] 执行 qmd search...")
        start_search = time.time()

        result = subprocess.run(
            [str(QMD_CLI), "search", query],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(QMD_PROJECT)
        )

        search_time = time.time() - start_search
        print(f"[Worker {worker_id}] qmd search 完成 ({search_time:.3f}s)")

        # 执行 qmd vsearch
        vsearch_time = 0
        vsearch_success = False

        if use_vsearch:
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
            vsearch_success = result_vsearch.returncode == 0
            print(f"[Worker {worker_id}] qmd vsearch 完成 ({vsearch_time:.3f}s)")

        total_time = time.time() - start_time

        return {
            'worker_id': worker_id,
            'search_time': search_time,
            'vsearch_time': vsearch_time,
            'total_time': total_time,
            'search_success': result.returncode == 0,
            'vsearch_success': vsearch_success,
        }

    except subprocess.TimeoutExpired:
        print(f"[Worker {worker_id}] 超时")
        return {
            'worker_id': worker_id,
            'search_time': 0,
            'vsearch_time': 0,
            'total_time': 120,
            'search_success': False,
            'vsearch_success': False,
            'error': 'Timeout',
        }
    except Exception as e:
        print(f"[Worker {worker_id}] 错误: {e}")
        return {
            'worker_id': worker_id,
            'search_time': 0,
            'vsearch_time': 0,
            'total_time': time.time() - start_time,
            'search_success': False,
            'vsearch_success': False,
            'error': str(e),
        }

def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("QMD CLI + Server 完整测试")
    print("=" * 70)

    stats = TestStats()

    # 1. 清理已有进程
    kill_existing_server()

    # 2. 初始 GPU 状态
    print("\n" + "=" * 70)
    print("步骤 1: 初始状态")
    print("=" * 70)

    stats.gpu_before = get_gpu_stats()
    print_gpu_stats("GPU (初始)", stats.gpu_before)

    # 3. 启动监控线程
    print("\n" + "=" * 70)
    print("步骤 2: 启动 GPU 监控")
    print("=" * 70)

    monitor_stop = threading.Event()

    def monitor_gpu():
        while not monitor_stop.is_set():
            stats.record_gpu()
            print_gpu_stats(f"[监控 {datetime.now().strftime('%H:%M:%S')}]", get_gpu_stats())
            time.sleep(2)

    monitor_thread = threading.Thread(target=monitor_gpu)
    monitor_thread.daemon = True
    monitor_thread.start()

    time.sleep(1)

    # 4. 冷启动测试（第一个查询会触发 Server 启动）
    print("\n" + "=" * 70)
    print("步骤 3: 冷启动测试 (第一个查询)")
    print("=" * 70)

    print("\n注意: 这个查询会自动启动 Server...")

    start_time = time.time()
    result1 = run_qmd_query(1, "机器学习算法")
    cold_start_time = time.time() - start_time

    print(f"\n冷启动总耗时: {cold_start_time:.3f}s")

    # 5. 等待稳定
    print("\n等待 Server 稳定...")
    time.sleep(3)

    # 6. 并发测试
    print("\n" + "=" * 70)
    print("步骤 4: 并发查询测试")
    print("=" * 70)

    from concurrent.futures import ThreadPoolExecutor

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = []
        futures.append(executor.submit(run_qmd_query, 2, "EchoSync 项目"))
        futures.append(executor.submit(run_qmd_query, 3, "深度学习框架"))

        results = [f.result() for f in futures]

    concurrent_time = time.time() - start_time

    # 7. 停止监控
    monitor_stop.set()
    monitor_thread.join(timeout=3)

    # 8. 最终 GPU 状态
    print("\n" + "=" * 70)
    print("步骤 5: 最终状态")
    print("=" * 70)

    stats.gpu_after = get_gpu_stats()
    print_gpu_stats("GPU (最终)", stats.gpu_after)
    print_gpu_stats("GPU (峰值)", {'memory_used': stats.gpu_peak, 'memory_total': stats.gpu_after['memory_total'] if stats.gpu_after else 6144, 'gpu_util': 0, 'memory_util': 0, 'power_draw': 0})

    # 9. 打印结果
    print("\n" + "=" * 70)
    print("测试结果")
    print("=" * 70)

    # 冷启动结果
    print("\n冷启动 (Worker 1):")
    print(f"  Search: {result1['search_time']:.3f}s")
    print(f"  VSearch: {result1['vsearch_time']:.3f}s")
    print(f"  总计: {result1['total_time']:.3f}s")

    # 并发结果
    print(f"\n并发查询 (2 个 Worker, {concurrent_time:.3f}s):")
    print(f"{'Worker':<10} {'Search(s)':<12} {'VSearch(s)':<12} {'Total(s)':<12} {'Search':<10} {'VSearch':<10}")
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

    # 10. 统计分析
    print("\n" + "=" * 70)
    print("性能分析")
    print("=" * 70)

    all_results = [result1] + results

    # 成功率
    search_success = sum(1 for r in all_results if r['search_success'])
    vsearch_success = sum(1 for r in all_results if r['vsearch_success'])

    print(f"\n成功率:")
    print(f"  Search: {search_success}/{len(all_results)} ({search_success/len(all_results)*100:.0f}%)")
    print(f"  VSearch: {vsearch_success}/{len(all_results)} ({vsearch_success/len(all_results)*100:.0f}%)")

    # 平均耗时
    avg_search = sum(r['search_time'] for r in all_results) / len(all_results)
    avg_vsearch = sum(r['vsearch_time'] for r in all_results if r['vsearch_success']) / max(vsearch_success, 1)

    print(f"\n平均耗时:")
    print(f"  Search (BM25): {avg_search:.3f}s")
    print(f"  VSearch (向量): {avg_vsearch:.3f}s")

    # 显存分析
    if stats.gpu_before and stats.gpu_after:
        mem_before = stats.gpu_before['memory_used']
        mem_after = stats.gpu_after['memory_used']
        mem_increase = mem_after - mem_before
        mem_peak = stats.gpu_peak

        print(f"\n显存使用:")
        print(f"  初始: {mem_before} MB")
        print(f"  最终: {mem_after} MB")
        print(f"  增加: {mem_increase} MB")
        print(f"  峰值: {mem_peak} MB")

        if mem_increase > 500:
            print(f"  ✅ Server 已加载到 GPU (显存增长 {mem_increase}MB)")
        elif mem_after > 1000:
            print(f"  ✅ Server 在 GPU 上运行 (显存占用 {mem_after}MB)")
        else:
            print(f"  ⚠️  显存使用偏低，可能使用 CPU 或 Server 未启动")

    # 吞吐量
    print(f"\n吞吐量:")
    print(f"  冷启动: {1/cold_start_time:.2f} queries/s")
    print(f"  并发 (2): {2/concurrent_time:.2f} queries/s")

    # 11. 结论
    print("\n" + "=" * 70)
    print("结论")
    print("=" * 70)

    if search_success == len(all_results) and vsearch_success == len(all_results):
        print("\n✅ 所有查询成功！QMD CLI + Server 架构正常工作！")

        if stats.gpu_after and stats.gpu_after['memory_used'] > 1000:
            print("✅ GPU 加速已启用，Server 正常运行")
        else:
            print("⚠️  GPU 使用率偏低，建议检查配置")

    else:
        print("\n❌ 部分查询失败，需要检查配置")

    return 0

if __name__ == "__main__":
    sys.exit(main())
