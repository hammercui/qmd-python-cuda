#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QMD Server + CLI 并发基准测试
测试所有 qmd cli 指令在并发情况下的性能指标
"""

import sys
import os
import time
import json
import subprocess
import threading
import multiprocessing
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ===================== 配置 =====================

QMD_PROJECT = Path(r"D:\MoneyProjects\qmd-python")
QMD_VENV = QMD_PROJECT / ".venv"
QMD_CLI = QMD_VENV / "Scripts" / "qmd.exe"
QMD_PYTHON = QMD_VENV / "Scripts" / "python.exe"

OBSIDIAN_PATH = Path(r"D:\syncthing\obsidian-mark\8.TODO")

# 测试配置
CONCURRENT_LEVELS = [1, 5, 10, 20]  # 并发级别
COMMANDS_PER_WORKER = 10  # 每个worker执行的命令数
SERVER_STARTUP_TIMEOUT = 30  # Server启动超时（秒）
TEST_TIMEOUT = 300  # 总测试超时（秒）

# ===================== 数据结构 =====================

@dataclass
class TestResult:
    """测试结果"""
    command: str
    success: bool
    elapsed: float
    returncode: int
    stdout: str = ""
    stderr: str = ""
    error: str = ""

@dataclass
class BenchmarkStats:
    """基准统计"""
    command: str
    total: int = 0
    success: int = 0
    failed: int = 0
    total_time: float = 0.0
    avg_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    p95_time: float = 0.0
    p99_time: float = 0.0
    throughput: float = 0.0  # requests/s

    def calculate(self):
        """计算统计数据"""
        if self.total > 0:
            self.avg_time = self.total_time / self.total
        self.success_rate = (self.success / self.total * 100) if self.total > 0 else 0
        self.failed_rate = (self.failed / self.total * 100) if self.total > 0 else 0

# ===================== 测试命令定义 =====================

def get_test_commands() -> List[Dict[str, Any]]:
    """获取所有测试命令"""
    return [
        {
            "name": "check",
            "command": [str(QMD_CLI), "check"],
            "description": "检查系统状态",
            "weight": 3,  # 执行频率权重
        },
        {
            "name": "status",
            "command": [str(QMD_CLI), "status"],
            "description": "显示详细状态",
            "weight": 2,
        },
        {
            "name": "ls",
            "command": [str(QMD_CLI), "ls"],
            "description": "列出文件",
            "weight": 2,
        },
        {
            "name": "search",
            "command": [str(QMD_CLI), "search", "EchoSync"],
            "description": "BM25 全文搜索",
            "weight": 3,
        },
        # 注意：vsearch 和 query 需要 server，在测试中会动态处理
    ]

# ===================== Server 管理 =====================

class QMDServerManager:
    """QMD Server 管理器"""

    def __init__(self):
        self.process = None
        self.url = "http://localhost:8000"
        self.started = False

    def start(self) -> bool:
        """启动 Server"""
        print("\n" + "=" * 70)
        print("启动 QMD Server")
        print("=" * 70)

        try:
            # 启动 server
            cmd = [str(QMD_CLI), "server", "--host", "localhost", "--port", "8000"]
            print(f"\n命令: {' '.join(cmd)}")

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # 行缓冲
                universal_newlines=True,
            )

            print(f"PID: {self.process.pid}")
            print("\n等待 Server 启动...")

            # 等待启动
            start_time = time.time()
            while time.time() - start_time < SERVER_STARTUP_TIMEOUT:
                try:
                    import requests
                    response = requests.get(f"{self.url}/health", timeout=1)
                    if response.status_code == 200:
                        self.started = True
                        elapsed = time.time() - start_time
                        print(f"OK: Server 已启动 (耗时 {elapsed:.2f}s)")
                        return True
                except:
                    time.sleep(0.5)

            print(f"FAIL: Server 启动超时 ({SERVER_STARTUP_TIMEOUT}s)")
            return False

        except Exception as e:
            print(f"FAIL: {e}")
            return False

    def stop(self):
        """停止 Server"""
        if self.process:
            print("\n停止 QMD Server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
                print("OK: Server 已停止")
            except subprocess.TimeoutExpired:
                print("WARN: Server 未响应，强制杀死")
                self.process.kill()
                self.process.wait()
            finally:
                self.process = None
                self.started = False

    def is_running(self) -> bool:
        """检查是否运行中"""
        if self.process and self.process.poll() is None:
            return True
        return False

# ===================== 测试执行器 =====================

class CommandExecutor:
    """命令执行器"""

    def __init__(self, server_url: str = None):
        self.server_url = server_url

    def execute(self, command_spec: Dict[str, Any]) -> TestResult:
        """执行单个命令"""
        cmd = command_spec["command"].copy()
        name = command_spec["name"]

        # 如果是 server 命令，确保 server 可用
        if name in ["vsearch", "query"]:
            if not self.server_url:
                return TestResult(
                    command=name,
                    success=False,
                    elapsed=0,
                    returncode=-1,
                    error="Server not available"
                )

        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,  # 单个命令超时
                cwd=str(QMD_PROJECT),
            )

            elapsed = time.time() - start_time

            return TestResult(
                command=name,
                success=(result.returncode == 0),
                elapsed=elapsed,
                returncode=result.returncode,
                stdout=result.stdout[:500] if result.stdout else "",
                stderr=result.stderr[:500] if result.stderr else "",
            )

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            return TestResult(
                command=name,
                success=False,
                elapsed=elapsed,
                returncode=-1,
                error=f"Timeout after 60s"
            )
        except Exception as e:
            elapsed = time.time() - start_time
            return TestResult(
                command=name,
                success=False,
                elapsed=elapsed,
                returncode=-1,
                error=str(e)
            )

# ===================== 并发测试 =====================

def run_concurrent_test(
    concurrent: int,
    commands: List[Dict[str, Any]],
    server_url: str = None
) -> Tuple[List[TestResult], BenchmarkStats]:
    """运行并发测试"""

    print(f"\n{'=' * 70}")
    print(f"并发级别: {concurrent}")
    print(f"{'=' * 70}")

    executor = CommandExecutor(server_url)
    results = []
    stats = BenchmarkStats(command=f"concurrent_{concurrent}")

    # 计算总命令数
    total_commands = concurrent * COMMANDS_PER_WORKER
    print(f"\n总命令数: {total_commands}")
    print(f"每进程: {COMMANDS_PER_WORKER} 个命令")

    start_time = time.time()

    # 使用线程池并发执行
    with ThreadPoolExecutor(max_workers=concurrent) as executor_pool:
        # 准备所有任务
        futures = []
        for i in range(total_commands):
            # 循环选择命令
            cmd = commands[i % len(commands)]
            future = executor_pool.submit(executor.execute, cmd)
            futures.append(future)

        # 收集结果
        for future in as_completed(futures):
            result = future.result()
            results.append(result)

            # 实时更新统计
            stats.total += 1
            if result.success:
                stats.success += 1
            else:
                stats.failed += 1

            stats.total_time += result.elapsed

            if result.elapsed < stats.min_time:
                stats.min_time = result.elapsed
            if result.elapsed > stats.max_time:
                stats.max_time = result.elapsed

            # 进度显示
            if stats.total % 10 == 0:
                print(f"  进度: {stats.total}/{total_commands} ({stats.total/total_commands*100:.1f}%)")

    total_elapsed = time.time() - start_time
    stats.throughput = stats.total / total_elapsed if total_elapsed > 0 else 0

    # 计算百分位数
    times = [r.elapsed for r in results if r.success]
    if times:
        times.sort()
        stats.p95_time = times[int(len(times) * 0.95)] if len(times) > 0 else 0
        stats.p99_time = times[int(len(times) * 0.99)] if len(times) > 0 else 0

    stats.calculate()

    return results, stats

# ===================== 系统监控 =====================

def get_system_stats() -> Dict[str, Any]:
    """获取系统统计"""
    stats = {}

    try:
        import psutil
        process = psutil.Process()

        # CPU
        stats["cpu_percent"] = psutil.cpu_percent(interval=0.1)

        # 内存
        memory = psutil.virtual_memory()
        stats["memory_total_gb"] = memory.total / 1024 / 1024 / 1024
        stats["memory_used_gb"] = memory.used / 1024 / 1024 / 1024
        stats["memory_percent"] = memory.percent

        # 进程内存
        mem_info = process.memory_info()
        stats["process_memory_mb"] = mem_info.rss / 1024 / 1024

    except ImportError:
        pass

    # GPU
    try:
        import torch
        if torch.cuda.is_available():
            stats["gpu_name"] = torch.cuda.get_device_name(0)
            stats["gpu_memory_allocated_mb"] = torch.cuda.memory_allocated(0) / 1024 / 1024
            stats["gpu_memory_reserved_mb"] = torch.cuda.memory_reserved(0) / 1024 / 1024

            props = torch.cuda.get_device_properties(0)
            stats["gpu_total_memory_gb"] = props.total_memory / 1024 / 1024 / 1024
    except ImportError:
        pass

    return stats

# ===================== 报告生成 =====================

def generate_report(
    all_results: Dict[int, Tuple[List[TestResult], BenchmarkStats]],
    system_stats_before: Dict[str, Any],
    system_stats_after: Dict[str, Any],
    output_file: str = None
):
    """生成测试报告"""

    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("QMD Server + CLI 并发基准测试报告")
    report_lines.append("=" * 70)
    report_lines.append(f"\n测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"项目路径: {QMD_PROJECT}")
    report_lines.append(f"测试配置:")
    report_lines.append(f"  并发级别: {CONCURRENT_LEVELS}")
    report_lines.append(f"  每进程命令数: {COMMANDS_PER_WORKER}")

    # 系统统计
    report_lines.append("\n" + "=" * 70)
    report_lines.append("系统资源")
    report_lines.append("=" * 70)

    if "cpu_percent" in system_stats_before:
        report_lines.append(f"\n测试前:")
        report_lines.append(f"  CPU: {system_stats_before['cpu_percent']:.1f}%")
        report_lines.append(f"  内存: {system_stats_before['memory_used_gb']:.1f}GB / {system_stats_before['memory_total_gb']:.1f}GB ({system_stats_before['memory_percent']:.1f}%)")
        report_lines.append(f"  进程内存: {system_stats_before['process_memory_mb']:.1f}MB")

    if "gpu_name" in system_stats_before:
        report_lines.append(f"\n  GPU: {system_stats_before['gpu_name']}")
        report_lines.append(f"  GPU 显存: {system_stats_before['gpu_memory_allocated_mb']:.0f}MB / {system_stats_before['gpu_total_memory_gb']:.1f}GB")

    if "cpu_percent" in system_stats_after:
        report_lines.append(f"\n测试后:")
        report_lines.append(f"  CPU: {system_stats_after['cpu_percent']:.1f}%")
        report_lines.append(f"  内存: {system_stats_after['memory_used_gb']:.1f}GB / {system_stats_after['memory_total_gb']:.1f}GB ({system_stats_after['memory_percent']:.1f}%)")
        report_lines.append(f"  进程内存: {system_stats_after['process_memory_mb']:.1f}MB")

    if "gpu_memory_allocated_mb" in system_stats_after:
        report_lines.append(f"\n  GPU 显存: {system_stats_after['gpu_memory_allocated_mb']:.0f}MB / {system_stats_after['gpu_total_memory_gb']:.1f}GB")

    # 并发测试结果
    report_lines.append("\n" + "=" * 70)
    report_lines.append("并发测试结果")
    report_lines.append("=" * 70)

    report_lines.append(f"\n{'并发数':<10} {'总数':<8} {'成功':<8} {'失败':<8} {'成功率':<10} {'平均(s)':<10} {'P95(s)':<10} {'P99(s)':<10} {'吞吐量':<12}")
    report_lines.append("-" * 110)

    for concurrent in sorted(all_results.keys()):
        results, stats = all_results[concurrent]

        report_lines.append(
            f"{concurrent:<10} "
            f"{stats.total:<8} "
            f"{stats.success:<8} "
            f"{stats.failed:<8} "
            f"{stats.success_rate:<10.1f}% "
            f"{stats.avg_time:<10.3f} "
            f"{stats.p95_time:<10.3f} "
            f"{stats.p99_time:<10.3f} "
            f"{stats.throughput:<12.2f}"
        )

    # 命令分类统计
    report_lines.append("\n" + "=" * 70)
    report_lines.append("命令分类统计")
    report_lines.append("=" * 70)

    command_stats = {}
    for concurrent, (results, _) in all_results.items():
        for result in results:
            if result.command not in command_stats:
                command_stats[result.command] = {
                    "total": 0,
                    "success": 0,
                    "times": [],
                }

            command_stats[result.command]["total"] += 1
            if result.success:
                command_stats[result.command]["success"] += 1
                command_stats[result.command]["times"].append(result.elapsed)

    report_lines.append(f"\n{'命令':<15} {'执行次数':<12} {'成功次数':<12} {'成功率':<10} {'平均(s)':<10}")
    report_lines.append("-" * 70)

    for cmd, stats in sorted(command_stats.items()):
        total = stats["total"]
        success = stats["success"]
        times = stats["times"]
        avg = sum(times) / len(times) if times else 0
        success_rate = (success / total * 100) if total > 0 else 0

        report_lines.append(
            f"{cmd:<15} "
            f"{total:<12} "
            f"{success:<12} "
            f"{success_rate:<10.1f}% "
            f"{avg:<10.3f}"
        )

    # 错误分析
    report_lines.append("\n" + "=" * 70)
    report_lines.append("错误分析")
    report_lines.append("=" * 70)

    error_count = 0
    for concurrent, (results, _) in all_results.items():
        for result in results:
            if not result.success:
                error_count += 1
                if error_count <= 20:  # 只显示前20个错误
                    report_lines.append(f"\n{result.command} (返回码: {result.returncode}):")
                    if result.error:
                        report_lines.append(f"  错误: {result.error}")
                    if result.stderr:
                        report_lines.append(f"  stderr: {result.stderr[:200]}")

    if error_count == 0:
        report_lines.append("\n无错误！")
    else:
        report_lines.append(f"\n总错误数: {error_count}")

    # 结论
    report_lines.append("\n" + "=" * 70)
    report_lines.append("结论")
    report_lines.append("=" * 70)

    max_concurrent = max(all_results.keys())
    _, max_stats = all_results[max_concurrent]

    report_lines.append(f"\n最大并发: {max_concurrent}")
    report_lines.append(f"成功率: {max_stats.success_rate:.1f}%")
    report_lines.append(f"吞吐量: {max_stats.throughput:.2f} req/s")
    report_lines.append(f"平均延迟: {max_stats.avg_time:.3f}s")
    report_lines.append(f"P95 延迟: {max_stats.p95_time:.3f}s")
    report_lines.append(f"P99 延迟: {max_stats.p99_time:.3f}s")

    if max_stats.success_rate >= 95:
        report_lines.append("\n✅ 系统在高并发下表现优秀！")
    elif max_stats.success_rate >= 80:
        report_lines.append("\n⚠️ 系统在高并发下表现良好，但有改进空间。")
    else:
        report_lines.append("\n❌ 系统在高并发下表现不佳，需要优化。")

    # 输出报告
    report_text = "\n".join(report_lines)
    print("\n" + report_text)

    # 保存到文件
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f"\n报告已保存到: {output_file}")

    return report_text

# ===================== 主函数 =====================

def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("QMD Server + CLI 并发基准测试")
    print("=" * 70)

    print(f"\n配置:")
    print(f"  项目: {QMD_PROJECT}")
    print(f"  CLI: {QMD_CLI}")
    print(f"  测试数据: {OBSIDIAN_PATH}")
    print(f"  并发级别: {CONCURRENT_LEVELS}")
    print(f"  每进程命令数: {COMMANDS_PER_WORKER}")

    # 检查环境
    if not QMD_CLI.exists():
        print(f"\n错误: QMD CLI 不存在: {QMD_CLI}")
        return 1

    # 获取测试命令
    commands = get_test_commands()
    print(f"\n测试命令:")
    for cmd in commands:
        print(f"  - {cmd['name']}: {cmd['description']}")

    # 启动 Server
    server = QMDServerManager()

    try:
        if not server.start():
            print("\n错误: Server 启动失败，继续测试（不测试 server 相关命令）")
            server_url = None
        else:
            server_url = server.url

            # 添加 server 相关命令
            commands.extend([
                {
                    "name": "vsearch",
                    "command": [str(QMD_CLI), "vsearch", "EchoSync"],
                    "description": "语义搜索（需要 server）",
                    "weight": 2,
                },
            ])

        # 获取系统统计（测试前）
        print("\n" + "=" * 70)
        print("获取系统基准统计...")
        print("=" * 70)
        system_stats_before = get_system_stats()

        # 运行并发测试
        all_results = {}

        for concurrent in CONCURRENT_LEVELS:
            results, stats = run_concurrent_test(
                concurrent,
                commands,
                server_url
            )
            all_results[concurrent] = (results, stats)

            # 间隔
            time.sleep(2)

        # 获取系统统计（测试后）
        print("\n" + "=" * 70)
        print("测试完成，获取最终统计...")
        print("=" * 70)
        system_stats_after = get_system_stats()

        # 生成报告
        output_file = QMD_PROJECT / "BENCHMARK_REPORT.md"
        generate_report(
            all_results,
            system_stats_before,
            system_stats_after,
            str(output_file)
        )

        return 0

    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        return 1

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # 停止 Server
        if server:
            server.stop()

if __name__ == "__main__":
    sys.exit(main())
