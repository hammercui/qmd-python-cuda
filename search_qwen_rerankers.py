#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜索 Qwen Reranker 模型
"""

import sys
from pathlib import Path

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def search_qwen_rerankers():
    """搜索 Qwen Reranker 模型"""
    print("\n" + "=" * 70)
    print("搜索 HuggingFace 上的 Qwen Reranker 模型")
    print("=" * 70)

    try:
        from huggingface_hub import list_repo_files, model_info

        # 候选的 Qwen reranker 模型
        candidates = [
            "Qwen/Qwen2.5-0.5B-Instruct",
            "Qwen/Qwen2-0.5B-Instruct",
            "Qwen/Qwen2.5-1.5B-Instruct",
            "Qwen/Qwen-7B",
            "Qwen/Qwen-14B",
        ]

        print("\n检查 Qwen 模型的可用文件...")
        print("-" * 70)

        for model_id in candidates:
            try:
                print(f"\n{model_id}:")

                # 获取模型信息
                info = model_info(model_id, repo_type="model")

                # 检查标签
                if hasattr(info, 'tags') and info.tags:
                    tags_str = ", ".join(info.tags[:5])
                    print(f"  标签: {tags_str}")

                # 检查模型文件
                files = list_repo_files(model_id, repo_type="model")

                # 查找 reranker 相关文件
                reranker_files = [f for f in files if 'rerank' in f.lower() or 'cross-encoder' in f.lower()]

                # 查找 PyTorch 文件
                pytorch_files = [f for f in files if f.endswith('.bin') or f.endswith('.safetensors')]

                if pytorch_files:
                    print(f"  PyTorch 文件: {len(pytorch_files)}")
                    for f in pytorch_files[:3]:
                        print(f"    - {f}")

                if reranker_files:
                    print(f"  Reranker 文件: {len(reranker_files)}")
                    for f in reranker_files:
                        print(f"    - {f}")

                # 检查是否适合做 reranker
                if 'reranker' in str(info.tags).lower() or 'cross-encoder' in str(info.tags).lower():
                    print("  => 这个模型是专门用于重排序的！")
                elif 'instruct' in model_id.lower():
                    print("  => 这是通用对话模型，可以做查询扩展")

            except Exception as e:
                print(f"  错误: {str(e)[:50]}")

        print("\n" + "=" * 70)
        print("总结")
        print("=" * 70)

        print("\nQwen 模型特点:")
        print("  - Qwen2.5-0.5B/1.5B-Instruct: 通用对话模型")
        print("    用于查询扩展，不适合做重排序")
        print("  - Qwen 没有专门的 cross-encoder reranker")
        print("    (至少在 HuggingFace 上没有)")

        print("\n当前使用的 ms-marco-MiniLM-L-6-v2:")
        print("  - 专门为重排序设计的 cross-encoder")
        print("  - 在 MS MARCO 数据集上训练")
        print("  - 效果已经过验证")

        print("\n建议:")
        print("  - 保持使用 ms-marco-MiniLM-L-6-v2")
        print("  - Qwen 用于查询扩展（已经在用）")
        print("  - 这样分工明确，效果更好")

        return 0

    except ImportError:
        print("\n需要安装 huggingface_hub:")
        print("  pip install huggingface_hub")
        return 1
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(search_qwen_rerankers())
