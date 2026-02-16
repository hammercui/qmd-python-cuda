from pathlib import Path
import os

# 检查fastembed缓存目录
# fastembed通常在~/.cache/fastembed或~/.cache/huggingface

home = Path.home()
cache_dirs = [
    home / ".cache" / "fastembed",
    home / ".cache" / "huggingface",
    home / ".cache" / "qmd" / "models"
]

for cache_dir in cache_dirs:
    print(f"\n检查目录: {cache_dir}")
    print(f"  存在: {cache_dir.exists()}")

    if cache_dir.exists():
        # 递归查找所有文件
        files = list(cache_dir.rglob("*"))
        print(f"  总项目数: {len(files)}")

        # 只显示前10个
        for f in files[:10]:
            if f.is_file():
                size_mb = f.stat().st_size / 1024 / 1024
                print(f"    - {f.relative_to(cache_dir)} ({size_mb:.1f} MB)")
        if len(files) > 10:
            print(f"    ... 还有 {len(files) - 10} 个项目")
