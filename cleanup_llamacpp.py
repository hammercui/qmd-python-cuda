#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理 llama-cpp 和 GGUF 相关文件
"""

import sys
import os
from pathlib import Path

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def cleanup_llamacpp():
    """清理 llama-cpp 相关文件"""
    print("\n" + "=" * 70)
    print("清理 llama-cpp 和 GGUF 相关文件")
    print("=" * 70)

    project_dir = Path(r"D:\MoneyProjects\qmd-python")

    # 需要删除的文件列表
    files_to_delete = [
        # 测试脚本
        "test_llama_basic.py",
        "diagnose_llama.py",
        "test_rerank_llamacpp.py",
        "test_gpu_acceleration.py",
        "check_cuda.py",
        "search_onnx_models.py",
        "diagnose_onnx.py",
        "cleanup_models.py",
        "migrate_to_llamacpp.py",
        "fix_llmengine.py",

        # 报告和文档
        "CUDA_SETUP_REPORT.md",
        "OPTIMIZATION_SUMMARY.md",
        "CUDA_INSTALL_GUIDE.md",

        # 源代码文件
        "qmd/search/rerank_llamacpp.py",
        "qmd/search/rerank_onnx.py",
    ]

    # 需要删除的目录
    dirs_to_delete = [
        "scripts",  # CUDA 相关脚本
    ]

    deleted_files = []
    skipped_files = []
    deleted_dirs = []

    print("\n1. 删除文件:")
    print("-" * 70)

    for file_name in files_to_delete:
        file_path = project_dir / file_name
        if file_path.exists():
            try:
                if file_path.is_file():
                    file_path.unlink()
                    size_kb = file_path.stat().st_size / 1024 if file_path.exists() else 0
                    print(f"  OK: {file_name} ({size_kb:.1f} KB)")
                    deleted_files.append(file_name)
                elif file_path.is_dir():
                    # 删除目录
                    import shutil
                    shutil.rmtree(file_path)
                    print(f"  OK: {file_name} (目录)")
                    deleted_dirs.append(file_name)
            except Exception as e:
                print(f"  FAIL: {file_name} - {e}")
                skipped_files.append(file_name)
        else:
            print(f"  SKIP: {file_name} (不存在)")
            skipped_files.append(file_name)

    print("\n2. 删除目录:")
    print("-" * 70)

    for dir_name in dirs_to_delete:
        dir_path = project_dir / dir_name
        if dir_path.exists() and dir_path.is_dir():
            try:
                import shutil
                # 统计文件数
                file_count = len(list(dir_path.rglob('*')))
                shutil.rmtree(dir_path)
                print(f"  OK: {dir_name} ({file_count} 个文件)")
                deleted_dirs.append(dir_name)
            except Exception as e:
                print(f"  FAIL: {dir_name} - {e}")
        else:
            print(f"  SKIP: {dir_name} (不存在)")

    # 检查 pyproject.toml 中的依赖
    print("\n3. 检查依赖:")
    print("-" * 70)

    pyproject_path = project_dir / "pyproject.toml"
    if pyproject_path.exists():
        content = pyproject_path.read_text(encoding='utf-8')

        llama_deps = [
            "llama-cpp-python",
        ]

        removed_deps = []
        for dep in llama_deps:
            if dep in content:
                print(f"  发现: {dep} 在 pyproject.toml")
                removed_deps.append(dep)

        if removed_deps:
            print(f"\n  建议手动从 pyproject.toml 移除:")
            for dep in removed_deps:
                print(f"    - {dep}")

    # 检查 .gitignore
    print("\n4. 检查 .gitignore:")
    print("-" * 70)

    gitignore_path = project_dir / ".gitignore"
    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding='utf-8')

        if "gguf" in content.lower():
            print("  发现 GGUF 相关条目在 .gitignore")
            print("  建议保留（避免提交大文件）")

    # 总结
    print("\n" + "=" * 70)
    print("清理总结")
    print("=" * 70)

    print(f"\n删除的文件: {len(deleted_files)}")
    print(f"删除的目录: {len(deleted_dirs)}")
    print(f"跳过的文件: {len(skipped_files)}")

    if deleted_files:
        print(f"\n删除的文件列表:")
        for f in deleted_files:
            print(f"  - {f}")

    if deleted_dirs:
        print(f"\n删除的目录列表:")
        for d in deleted_dirs:
            print(f"  - {d}")

    print("\n建议:")
    print("  1. 从 pyproject.toml 移除 llama-cpp-python 依赖")
    print("  2. 更新 README.md 删除 llama-cpp 相关说明")
    print("  3. 提交更改到 Git")

    return 0

if __name__ == "__main__":
    sys.exit(cleanup_llamacpp())
