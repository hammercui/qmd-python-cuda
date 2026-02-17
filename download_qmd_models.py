#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 ModelScope 下载 QMD 模型
"""

import sys
from pathlib import Path

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))

from qmd.models.downloader import ModelDownloader

def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("QMD 模型下载工具 (ModelScope)")
    print("=" * 70)

    downloader = ModelDownloader()

    print("\n检查模型可用性...")
    available = downloader.check_availability()

    print("\n当前状态:")
    for model, is_available in available.items():
        status = "OK" if is_available else "未下载"
        print(f"  {model}: {status}")

    print("\n开始下载...")
    print("-" * 70)

    try:
        # 下载所有模型
        results = downloader.download_all(force=False)

        print("\n" + "=" * 70)
        print("下载结果")
        print("=" * 70)

        for model, path in results.items():
            if path:
                size_mb = path.stat().st_size / 1024 / 1024
                print(f"  {model}: OK ({size_mb:.2f} MB)")
            else:
                print(f"  {model}: 失败")

        return 0

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
