#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查根目录文档并归档
"""

import sys
import shutil
from pathlib import Path

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_root_docs():
    """检查根目录文档"""
    print("\n" + "=" * 70)
    print("检查根目录文档")
    print("=" * 70)

    project_dir = Path(r"D:\MoneyProjects\qmd-python")
    archive_dir = project_dir / "_to_delete"

    # 需要保留的核心文档
    keep_docs = {
        "FINAL_CONFIG.md",
        "README.md",
        "CLEANUP_REPORT.md",
        "BENCHMARK_REPORT.md",
        "TEST_REPORT.md",
        "OBSIDIAN_TEST_REPORT.md",
        "ARCHIVED_TESTS.md",
    }

    # 可能过时的文档（需要检查）
    check_docs = [
        "AGENTS.md",
        "AUTO_FIX_REPORT.md",
        "CLI_MODE_ANALYSIS.md",
        "FINAL_TASKS.md",
        "GAP_FILLING_PLAN.md",
        "GAP_FILLING_REPORT.md",
        "MODEL_DOWNLOAD_FAILURE_ANALYSIS.md",
        "OPENCLAW_COMPATIBILITY.md",
        "PRODUCTION_DEPLOYMENT_GAP.md",
        "PROJECT_COMPLETION_REPORT.md",
        "PROJECT_COMPLETION_SUMMARY.md",
        "PROJECT_STATUS.md",
        "PROJECT_STATUS_SUMMARY.md",
        "QUICK_REFERENCE.md",
        "TESTING_SUMMARY.md",
        "TODO.md",
        "TODO_SYSTEM_SETUP.md",
    ]

    # 过时关键词
    outdated_keywords = [
        "llama.cpp",
        "GGUF",
        "架构决策",
        "2026-02-15",
        "待完成",
        "未完成",
        "TODO:",
        "[ ]",
    ]

    # 项目状态关键词（可能过时）
    status_keywords = [
        "PROJECT_STATUS",
        "FINAL_TASKS",
        "GAP_FILLING",
        "待修复",
        "未修复",
    ]

    print("\n文档分析:")
    print("-" * 70)

    to_archive = []
    to_keep = []

    for doc_name in check_docs:
        doc_path = project_dir / doc_name
        if not doc_path.exists():
            continue

        try:
            content = doc_path.read_text(encoding='utf-8')
            lines = content.split('\n')

            # 检查是否包含过时内容
            has_outdated = any(kw in content for kw in outdated_keywords)
            is_status_doc = any(kw in doc_name for kw in status_keywords)

            # 检查是否是已完成的项目
            has_completion_markers = any(marker in content for marker in [
                "✅ 完成",
                "完成",
                "已修复",
                "已解决",
                "项目完成",
            ])

            # 检查日期（是否超过7天）
            is_old = False
            if doc_path.stat().st_mtime < (Path(__file__).stat().st_mtime - 7*24*3600):
                is_old = True

            # 决策逻辑
            should_archive = False
            reason = ""

            if has_outdated:
                should_archive = True
                reason = "包含过时内容（llama.cpp/GGUF）"
            elif is_status_doc and has_completion_markers:
                should_archive = True
                reason = "项目已完成，状态文档过时"
            elif is_old and "TODO" in doc_name:
                should_archive = True
                reason = "TODO文档已过期"
            elif "GAP_FILLING" in doc_name:
                should_archive = True
                reason = "GAP已填补完成"
            elif "MODEL_DOWNLOAD_FAILURE" in doc_name:
                should_archive = True
                reason = "问题已解决"

            if should_archive:
                to_archive.append((doc_name, reason))
                print(f"  ⚠️  {doc_name}")
                print(f"     原因: {reason}")
            else:
                to_keep.append(doc_name)
                print(f"  ✅ {doc_name} - 保留")

        except Exception as e:
            print(f"  ❌ {doc_name} - 读取失败: {e}")

    # 归档文档
    if to_archive:
        print("\n归档过时文档:")
        print("-" * 70)

        for doc_name, reason in to_archive:
            src_path = project_dir / doc_name
            dst_path = archive_dir / doc_name

            try:
                shutil.move(str(src_path), str(dst_path))
                print(f"  ✅ {doc_name} → _to_delete/ ({reason})")
            except Exception as e:
                print(f"  ❌ {doc_name} - 失败: {e}")

    # 创建根目录清理说明
    cleanup_readme = project_dir / "IMPORTANT_DOCS.md"
    if not cleanup_readme.exists():
        with open(cleanup_readme, 'w', encoding='utf-8') as f:
            f.write("# 重要文档说明\n\n")
            f.write("## 核心文档（必读）\n\n")
            f.write("- **README.md** - 项目说明和使用指南\n")
            f.write("- **FINAL_CONFIG.md** - 当前架构配置文档\n")
            f.write("- **CLEANUP_REPORT.md** - 项目清理报告\n\n")
            f.write("## 测试报告\n\n")
            f.write("- **BENCHMARK_REPORT.md** - 并发性能测试\n")
            f.write("- **TEST_REPORT.md** - 核心功能测试\n")
            f.write("- **OBSIDIAN_TEST_REPORT.md** - 真实场景测试\n\n")
            f.write("## 历史文档\n\n")
            f.write("- **ARCHIVED_TESTS.md** - 测试文档归档说明\n")
            f.write("- **_to_delete/** - 已过时的文档（已归档）\n\n")
            f.write(f"**最后更新**: 2026-02-17\n")

        print(f"\n创建文档索引:")
        print("-" * 70)
        print(f"  ✅ IMPORTANT_DOCS.md")

    # 总结
    print("\n" + "=" * 70)
    print("总结")
    print("=" * 70)

    print(f"\n归档文档: {len(to_archive)} 个")
    print(f"保留文档: {len(to_keep)} 个")

    if to_archive:
        print(f"\n已归档:")
        for doc_name, reason in to_archive:
            print(f"  - {doc_name} ({reason})")

    print(f"\n保留的核心文档:")
    core_docs = [
        "README.md",
        "FINAL_CONFIG.md",
        "CLEANUP_REPORT.md",
        "IMPORTANT_DOCS.md",
        "BENCHMARK_REPORT.md",
        "TEST_REPORT.md",
        "OBSIDIAN_TEST_REPORT.md",
        "ARCHIVED_TESTS.md",
    ]

    for doc in core_docs:
        if (project_dir / doc).exists():
            print(f"  ✅ {doc}")

    # Git 建议
    print(f"\nGit 操作建议:")
    print("-" * 70)
    print("  git add .")
    print("  git commit -m \"Archive outdated documentation\"")
    print("  git push")

    return 0

if __name__ == "__main__":
    sys.exit(check_root_docs())
