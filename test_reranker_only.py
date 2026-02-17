#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Qwen3-Reranker GGUF 模型
"""

import sys
from pathlib import Path

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_reranker_model():
    """测试 Qwen3-Reranker 加载"""
    print("\n" + "=" * 70)
    print("测试 Qwen3-Reranker GGUF")
    print("=" * 70)

    models_dir = Path.home() / ".cache" / "qmd" / "models"

    # 查找 reranker GGUF
    reranker_files = list(models_dir.glob("*reranker*.gguf"))

    if not reranker_files:
        print("\n✗ 没有找到 reranker GGUF 文件")
        return 1

    reranker_file = reranker_files[0]
    print(f"\n模型: {reranker_file.name}")
    print(f"大小: {reranker_file.stat().st_size / 1024 / 1024:.2f} MB")

    try:
        from llama_cpp import Llama
        import torch

        if not torch.cuda.is_available():
            print("\n✗ CUDA 不可用")
            return 1

        print(f"\n✓ CUDA: {torch.cuda.get_device_name(0)}")

        # 加载模型
        print("\n加载模型...")
        model = Llama(
            model_path=str(reranker_file),
            n_gpu_layers=-1,  # 全部 GPU
            n_ctx=2048,
            verbose=False
        )

        print("✓ 模型加载成功!")

        # 测试 rank API
        print("\n测试 rank API...")

        query = "What is machine learning?"
        documents = [
            "Machine learning is a subset of artificial intelligence.",
            "Python is a popular programming language.",
            "Deep learning uses neural networks with multiple layers.",
        ]

        ranked = model.rank(
            query=query,
            documents=documents,
            top_k=3
        )

        print("\n排名结果:")
        for i, item in enumerate(ranked, 1):
            idx = item['index']
            score = item['score']
            text = documents[idx][:50] + "..."
            print(f"  {i}. [{score:.4f}] {text}")

        print("\n✓ Rank API 测试通过!")

        return 0

    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(test_reranker_model())
