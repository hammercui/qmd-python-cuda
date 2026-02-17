#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 fastembed GPU 使用
"""

import sys
import time

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_fastembed_gpu():
    """测试 fastembed GPU"""
    print("\n" + "=" * 70)
    print("fastembed GPU 使用测试")
    print("=" * 70)

    # 清理 GPU
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            print(f"\n初始 GPU 显存: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB")
    except:
        pass

    # 测试 1: 不指定 providers (默认)
    print("\n" + "-" * 70)
    print("测试 1: 默认模式 (自动选择)")
    print("-" * 70)

    from fastembed import TextEmbedding

    model1 = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

    docs = ["测试文档" * 100 for _ in range(10)]

    start = time.time()
    embeddings1 = list(model1.embed(docs))
    elapsed1 = time.time() - start

    print(f"  文档数: {len(docs)}")
    print(f"  耗时: {elapsed1:.3f}s")
    print(f"  速度: {len(docs) / elapsed1:.1f} docs/s")

    # 检查 GPU
    try:
        import torch
        if torch.cuda.is_available():
            gpu1 = torch.cuda.memory_allocated(0) / 1024**2
            peak1 = torch.cuda.max_memory_allocated(0) / 1024**2
            print(f"  GPU 显存: {gpu1:.2f} MB (峰值: {peak1:.2f} MB)")
    except:
        pass

    # 清理
    del model1
    del embeddings1

    # 测试 2: 指定 CUDA
    print("\n" + "-" * 70)
    print("测试 2: 强制 CUDA 模式")
    print("-" * 70)

    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
    except:
        pass

    model2 = TextEmbedding(
        model_name="BAAI/bge-small-en-v1.5",
        providers=["CUDAExecutionProvider"]
    )

    start = time.time()
    embeddings2 = list(model2.embed(docs))
    elapsed2 = time.time() - start

    print(f"  文档数: {len(docs)}")
    print(f"  耗时: {elapsed2:.3f}s")
    print(f"  速度: {len(docs) / elapsed2:.1f} docs/s")

    # 检查 GPU
    try:
        import torch
        if torch.cuda.is_available():
            gpu2 = torch.cuda.memory_allocated(0) / 1024**2
            peak2 = torch.cuda.max_memory_allocated(0) / 1024**2
            print(f"  GPU 显存: {gpu2:.2f} MB (峰值: {peak2:.2f} MB)")

            if peak2 > 10:
                print(f"\n  GPU 加速生效！速度提升: {elapsed1 / elapsed2:.2f}x")
            else:
                print(f"\n  GPU 未使用，可能模型太小优化效果不明显")
    except:
        pass

    # 测试 3: 大批量测试
    print("\n" + "-" * 70)
    print("测试 3: 大批量测试 (100 文档)")
    print("-" * 70)

    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
    except:
        pass

    large_docs = ["测试文档内容" * 50 for _ in range(100)]

    start = time.time()
    embeddings3 = list(model2.embed(large_docs))
    elapsed3 = time.time() - start

    print(f"  文档数: {len(large_docs)}")
    print(f"  耗时: {elapsed3:.3f}s")
    print(f"  速度: {len(large_docs) / elapsed3:.1f} docs/s")

    # 检查 GPU
    try:
        import torch
        if torch.cuda.is_available():
            gpu3 = torch.cuda.memory_allocated(0) / 1024**2
            peak3 = torch.cuda.max_memory_allocated(0) / 1024**2
            print(f"  GPU 显存: {gpu3:.2f} MB (峰值: {peak3:.2f} MB)")
    except:
        pass

    return 0

if __name__ == "__main__":
    sys.exit(test_fastembed_gpu())
