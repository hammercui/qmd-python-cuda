#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查并更新文档中的 llama-cpp 引用
"""

import sys
import re
from pathlib import Path

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_and_update_docs():
    """检查并更新文档"""
    print("\n" + "=" * 70)
    print("检查文档中的 llama-cpp 引用")
    print("=" * 70)

    project_dir = Path(r"D:\MoneyProjects\qmd-python")

    # 需要检查的文档
    docs_to_check = [
        "README.md",
        "FINAL_CONFIG.md",
        "TEST_REPORT.md",
        "OBSIDIAN_TEST_REPORT.md",
        "BENCHMARK_REPORT.md",
        "MEMORY.md",
    ]

    llama_keywords = [
        "llama.cpp",
        "llama-cpp",
        "llamacpp",
        "gguf",
        "GGUF",
    ]

    found_refs = []

    print("\n扫描文档:")
    print("-" * 70)

    for doc_name in docs_to_check:
        doc_path = project_dir / doc_name
        if not doc_path.exists():
            continue

        content = doc_path.read_text(encoding='utf-8')

        # 检查是否包含关键词
        matches = []
        for keyword in llama_keywords:
            if keyword in content:
                # 统计出现次数
                count = content.count(keyword)
                matches.append(f"{keyword}({count})")

        if matches:
            found_refs.append(doc_name)
            print(f"\n{doc_name}:")
            print(f"  发现: {', '.join(matches)}")

    if not found_refs:
        print("\n未发现 llama-cpp 相关引用")
    else:
        print(f"\n发现 {len(found_refs)} 个文档包含 llama-cpp 引用")
        print("\n建议手动更新这些文档，删除 llama-cpp 相关说明")

    # 检查代码文件
    print("\n" + "-" * 70)
    print("扫描代码文件:")
    print("-" * 70)

    code_files = list(project_dir.rglob("*.py"))
    code_refs = []

    for code_file in code_files:
        # 跳过虚拟环境和测试
        if ".venv" in str(code_file) or "test_" in code_file.name:
            continue

        try:
            content = code_file.read_text(encoding='utf-8', errors='ignore')

            for keyword in llama_keywords:
                if keyword in content:
                    code_refs.append(str(code_file.relative_to(project_dir)))
                    break
        except:
            pass

    if code_refs:
        print(f"\n发现 {len(code_refs)} 个代码文件可能包含 llama-cpp 引用:")
        for ref in code_refs[:10]:  # 只显示前10个
            print(f"  - {ref}")
        if len(code_refs) > 10:
            print(f"  ... 还有 {len(code_refs) - 10} 个文件")
    else:
        print("\n代码文件中未发现 llama-cpp 引用")

    # 总结
    print("\n" + "=" * 70)
    print("总结")
    print("=" * 70)

    print(f"\n文档引用: {len(found_refs)} 个")
    print(f"代码引用: {len(code_refs)} 个")

    if found_refs or code_refs:
        print("\n需要手动更新:")
        for doc in found_refs:
            print(f"  - {doc}")

        print("\n更新建议:")
        print("  1. 删除 llama.cpp 相关章节")
        print("  2. 更新为 PyTorch + fastembed 方案")
        print("  3. 强调当前架构的优势")
    else:
        print("\n未发现 llama-cpp 引用，清理完成！")

    return 0

if __name__ == "__main__":
    sys.exit(check_and_update_docs())
