#!/usr/bin/env python
"""
QMD CLI 兼容性测试脚本
测试所有修改的命令和功能
"""

import os
import sys
import tempfile
import subprocess
import time


def run_command(cmd, description):
    """运行命令并显示结果"""
    print(f"\n{'=' * 60}")
    print(f"测试: {description}")
    print(f"命令: {cmd}")
    print("=" * 60)

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )

        print(result.stdout)
        if result.stderr and "Warning" not in result.stderr[:200]:
            print(result.stderr[:500])

        print(f"\n退出码: {result.returncode}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("错误: 命令超时")
        return False
    except Exception as e:
        print(f"错误: {e}")
        return False


def main():
    print("=" * 60)
    print("QMD CLI 兼容性测试")
    print("=" * 60)

    results = []

    # 准备测试环境
    test_dir = os.path.join(tempfile.gettempdir(), "qmd-test-docs")
    os.makedirs(test_dir, exist_ok=True)

    # 创建测试文档
    with open(os.path.join(test_dir, "python.md"), "w", encoding="utf-8") as f:
        f.write("# Python 编程\n\n这是一篇关于 Python 编程的文档。")

    with open(os.path.join(test_dir, "javascript.md"), "w", encoding="utf-8") as f:
        f.write("# JavaScript 开发\n\n这是一篇关于 JavaScript 开发的文档。")

    print(f"\n测试目录: {test_dir}")

    # ========== 阶段 1: collection add ==========
    print("\n" + "=" * 60)
    print("阶段 1: collection add 命令测试")
    print("=" * 60)

    # 测试 1.1: 自动命名
    success = run_command(
        f'python -m qmd collection add "{test_dir}"', "1.1 Collection add - 自动命名"
    )
    results.append(("阶段 1.1", success))

    # 测试 1.2: 检查集合列表
    success = run_command("python -m qmd collection list", "1.2 Collection list")
    results.append(("阶段 1.2", success))

    # 测试 1.3: 索引文档
    success = run_command("python -m qmd index", "1.3 Index documents")
    results.append(("阶段 1.3", success))

    # ========== 阶段 2: context 命令 ==========
    print("\n" + "=" * 60)
    print("阶段 2: context 命令测试")
    print("=" * 60)

    # 测试 2.1: 添加上下文（虚拟路径）
    success = run_command(
        'python -m qmd context add "测试集合描述" qmd://test-docs',
        "2.1 Context add - 虚拟路径模式",
    )
    results.append(("阶段 2.1", success))

    # 测试 2.2: 列出上下文
    success = run_command("python -m qmd context list", "2.2 Context list")
    results.append(("阶段 2.2", success))

    # 测试 2.3: 移除上下文
    success = run_command(
        "python -m qmd context remove qmd://test-docs", "2.3 Context remove"
    )
    results.append(("阶段 2.3", success))

    # ========== 阶段 3: search 格式 ==========
    print("\n" + "=" * 60)
    print("阶段 3: search 命令格式测试")
    print("=" * 60)

    # 测试 3.1: CLI 格式（默认）
    success = run_command('python -m qmd search "Python" -n 2', "3.1 Search - CLI 格式")
    results.append(("阶段 3.1", success))

    # 测试 3.2: JSON 格式
    success = run_command(
        'python -m qmd search "Python" --format json -n 2', "3.2 Search - JSON 格式"
    )
    results.append(("阶段 3.2", success))

    # 测试 3.3: Files 格式
    success = run_command(
        'python -m qmd search "Python" --format files -n 2', "3.3 Search - Files 格式"
    )
    results.append(("阶段 3.3", success))

    # 测试 3.4: Markdown 格式
    success = run_command(
        'python -m qmd search "Python" --format md -n 2', "3.4 Search - Markdown 格式"
    )
    results.append(("阶段 3.4", success))

    # 测试 3.5: CSV 格式
    success = run_command(
        'python -m qmd search "Python" --format csv -n 2', "3.5 Search - CSV 格式"
    )
    results.append(("阶段 3.5", success))

    # 测试 3.6: JSON 别名（向后兼容）
    success = run_command(
        'python -m qmd search "Python" --json -n 2', "3.6 Search - --json 别名"
    )
    results.append(("阶段 3.6", success))

    # ========== Server 命令测试（需要已启动的 server） ==========
    print("\n" + "=" * 60)
    print("Server 命令测试（需要已启动的 QMD Server）")
    print("=" * 60)

    # 测试 4.1: VSearch
    success = run_command(
        'python -m qmd vsearch "编程" -n 2 --format json', "4.1 VSearch - JSON 格式"
    )
    results.append(("Server 4.1", success))

    # 测试 4.2: Query
    success = run_command(
        'python -m qmd query "编程语言" -n 3 --format json', "4.2 Query - JSON 格式"
    )
    results.append(("Server 4.2", success))

    # ========== 状态检查 ==========
    print("\n" + "=" * 60)
    print("系统状态检查")
    print("=" * 60)

    success = run_command("python -m qmd status", "Status check")
    results.append(("Status", success))

    # ========== 清理 ==========
    print("\n" + "=" * 60)
    print("清理测试数据")
    print("=" * 60)

    success = run_command(
        "python -m qmd collection remove test-docs", "清理: 删除测试集合"
    )
    results.append(("Cleanup", success))

    # ========== 结果汇总 ==========
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")

    print(f"\n总计: {passed}/{total} 测试通过")
    print("=" * 60)

    # 清理测试目录
    try:
        import shutil

        shutil.rmtree(test_dir, ignore_errors=True)
        print(f"\n已清理测试目录: {test_dir}")
    except:
        pass

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
