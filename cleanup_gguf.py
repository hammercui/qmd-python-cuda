#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查并清理模型文件
"""

import sys
from pathlib import Path

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_and_cleanup():
    """检查并清理模型"""
    print("\n" + "=" * 70)
    print("QMD 模型检查和清理")
    print("=" * 70)

    models_dir = Path.home() / ".cache" / "qmd" / "models"

    if not models_dir.exists():
        print(f"\n模型目录不存在: {models_dir}")
        return

    # 统计 PyTorch 模型
    print("\nPyTorch 模型目录:")
    print("-" * 70)

    pytorch_dirs = []
    total_pytorch_mb = 0

    for d in models_dir.iterdir():
        if d.is_dir():
            # 计算目录大小
            size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            size_mb = size / 1024 / 1024

            if size_mb > 1:  # 只显示大于 1MB 的
                pytorch_dirs.append((d.name, size_mb))
                total_pytorch_mb += size_mb

    if pytorch_dirs:
        print(f"{'目录名称':<50} {'大小':<10}")
        for name, size_mb in sorted(pytorch_dirs, key=lambda x: x[1], reverse=True):
            print(f"{name:<50} {size_mb:>8.2f} MB")

        print("-" * 70)
        print(f"PyTorch 模型总计: {total_pytorch_mb:.2f} MB")
    else:
        print("  (无)")

    # 统计 GGUF 文件
    print("\nGGUF 文件:")
    print("-" * 70)

    gguf_files = list(models_dir.glob("*.gguf"))
    total_gguf_mb = 0

    if gguf_files:
        print(f"{'文件名':<60} {'大小':<10}")
        for f in sorted(gguf_files, key=lambda x: x.stat().st_size, reverse=True):
            size_mb = f.stat().st_size / 1024 / 1024
            total_gguf_mb += size_mb
            print(f"{f.name:<60} {size_mb:>8.2f} MB")

        print("-" * 70)
        print(f"GGUF 文件总计: {total_gguf_mb:.2f} MB")
    else:
        print("  (无)")

    # 总结
    print("\n" + "=" * 70)
    print("总结")
    print("=" * 70)

    total_mb = total_pytorch_mb + total_gguf_mb
    print(f"\n总占用: {total_mb:.2f} MB ({total_mb / 1024:.2f} GB)")
    print(f"  - PyTorch 模型: {total_pytorch_mb:.2f} MB ({total_pytorch_mb / 1024:.2f} GB)")
    print(f"  - GGUF 文件: {total_gguf_mb:.2f} MB ({total_gguf_mb / 1024:.2f} GB)")

    # 清理 GGUF
    if gguf_files:
        print("\n" + "-" * 70)
        print("清理 GGUF 文件（当前不使用）")
        print("-" * 70)

        confirm = input("\n确认删除所有 GGUF 文件? (yes/no): ").strip().lower()

        if confirm in ["yes", "y"]:
            print("\n删除中...")
            deleted = 0
            freed_mb = 0

            for f in gguf_files:
                try:
                    size_mb = f.stat().st_size / 1024 / 1024
                    f.unlink()
                    print(f"  OK: {f.name} ({size_mb:.2f} MB)")
                    deleted += 1
                    freed_mb += size_mb
                except Exception as e:
                    print(f"  FAIL: {f.name} - {e}")

            print("\n" + "=" * 70)
            print(f"成功删除 {deleted}/{len(gguf_files)} 个文件")
            print(f"释放空间: {freed_mb:.2f} MB ({freed_mb / 1024:.2f} GB)")
            print("=" * 70)

            print("\n剩余模型:")
            print(f"  PyTorch 模型: {total_pytorch_mb:.2f} MB ({total_pytorch_mb / 1024:.2f} GB)")
        else:
            print("\n取消删除")
    else:
        print("\n没有 GGUF 文件需要清理")

    return 0

if __name__ == "__main__":
    sys.exit(check_and_cleanup())
