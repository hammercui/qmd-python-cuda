#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查并归档过时文档
"""

import sys
import os
from pathlib import Path

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_and_archive_docs():
    """检查并归档过时文档"""
    print("\n" + "=" * 70)
    print("检查文档完整性")
    print("=" * 70)

    project_dir = Path(r"D:\MoneyProjects\qmd-python")

    # 创建待删除目录
    archive_dir = project_dir / "_to_delete"
    archive_dir.mkdir(exist_ok=True)

    # 需要检查的文档
    docs_to_check = [
        "OPENCLAW_COMPATIBILITY.md",
        "CLI_MODE_ANALYSIS.md",
        "QUICK_REFERENCE.md",
        "PROJECT_COMPLETION_REPORT.md",
        "AUTO_FIX_REPORT.md",
        "PERFORMANCE_BENCHMARK_REPORT.md",
    ]

    # 过时关键词
    outdated_keywords = [
        "llama.cpp",
        "llama-cpp",
        "llamacpp",
        "gguf",
        "GGUF",
        "架构决策",
        "2026-02-15",  # 旧日期
    ]

    # 正确关键词（保留）
    valid_keywords = [
        "PyTorch",
        "fastembed",
        "FINAL_CONFIG",
    ]

    print("\n1. 检查根目录文档:")
    print("-" * 70)

    docs_to_archive = []
    docs_to_keep = []

    for doc_name in docs_to_check:
        doc_path = project_dir / doc_name
        if not doc_path.exists():
            continue

        try:
            content = doc_path.read_text(encoding='utf-8')

            # 检查是否包含过时内容
            has_outdated = any(kw in content for kw in outdated_keywords)

            # 检查是否是当前架构
            is_current = any(kw in content for kw in valid_keywords)

            if has_outdated and not is_current:
                docs_to_archive.append(doc_name)
                print(f"  ⚠️  {doc_name} - 包含过时内容")
            elif is_current:
                docs_to_keep.append(doc_name)
                print(f"  ✅ {doc_name} - 当前架构")
            else:
                # 中性内容，保留
                docs_to_keep.append(doc_name)
                print(f"  ℹ️  {doc_name} - 中性内容")

        except Exception as e:
            print(f"  ❌ {doc_name} - 读取失败: {e}")

    # 检查 docs/ 目录
    print("\n2. 检查 docs/ 目录:")
    print("-" * 70)

    docs_dir = project_dir / "docs"
    if docs_dir.exists():
        for doc_file in docs_dir.rglob("*.md"):
            rel_path = doc_file.relative_to(project_dir)

            try:
                content = doc_file.read_text(encoding='utf-8')

                has_outdated = any(kw in content for kw in outdated_keywords)
                is_current = any(kw in content for kw in valid_keywords)

                if has_outdated and not is_current:
                    docs_to_archive.append(str(rel_path))
                    print(f"  ⚠️  {rel_path} - 包含过时内容")
                else:
                    docs_to_keep.append(str(rel_path))

            except Exception as e:
                print(f"  ❌ {rel_path} - 读取失败: {e}")

    # 归档文档
    if docs_to_archive:
        print("\n3. 归档过时文档:")
        print("-" * 70)

        import shutil

        for doc_name in docs_to_archive:
            src_path = project_dir / doc_name
            dst_path = archive_dir / doc_name

            try:
                # 创建目标目录
                dst_path.parent.mkdir(parents=True, exist_ok=True)

                # 移动文件
                shutil.move(str(src_path), str(dst_path))
                print(f"  ✅ {doc_name} → _to_delete/")
            except Exception as e:
                print(f"  ❌ {doc_name} - 失败: {e}")

    # 创建归档说明
    archive_readme = archive_dir / "README.md"
    with open(archive_readme, 'w', encoding='utf-8') as f:
        f.write("# 过时文档归档\n\n")
        f.write("本目录包含已过时或不再维护的文档。\n\n")
        f.write("## 归档原因\n\n")
        f.write("- 包含 llama.cpp 或 GGUF 相关内容\n")
        f.write("- 描述已废弃的架构或方案\n")
        f.write("- 被更新的文档替代\n\n")
        f.write("## 当前文档\n\n")
        f.write("请参考项目根目录的以下文档：\n\n")
        f.write("- **FINAL_CONFIG.md** - 当前架构配置\n")
        f.write("- **README.md** - 项目说明\n")
        f.write("- **CLEANUP_REPORT.md** - 清理报告\n\n")
        f.write(f"**归档日期**: {sys.argv[0] if len(sys.argv) > 1 else '2026-02-17'}\n")

    print(f"\n4. 创建归档说明:")
    print("-" * 70)
    print(f"  ✅ _to_delete/README.md")

    # 总结
    print("\n" + "=" * 70)
    print("总结")
    print("=" * 70)

    print(f"\n归档文档: {len(docs_to_archive)} 个")
    print(f"保留文档: {len(docs_to_keep)} 个")

    if docs_to_archive:
        print(f"\n已归档:")
        for doc in docs_to_archive:
            print(f"  - {doc}")

    print(f"\n建议保留的文档:")
    important_docs = [
        "FINAL_CONFIG.md",
        "README.md",
        "CLEANUP_REPORT.md",
        "BENCHMARK_REPORT.md",
        "TEST_REPORT.md",
        "OBSIDIAN_TEST_REPORT.md",
        "ARCHIVED_TESTS.md",
    ]

    for doc in important_docs:
        if (project_dir / doc).exists():
            print(f"  ✅ {doc}")

    return 0

if __name__ == "__main__":
    sys.exit(check_and_archive_docs())
