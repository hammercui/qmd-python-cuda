#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 QMD 完整功能（自动下载 PyTorch 模型）
"""

import sys
from pathlib import Path

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))

from qmd.search.rerank import LLMReranker
import time

def test_full_pipeline():
    """测试完整流程"""
    print("\n" + "=" * 70)
    print("QMD 完整功能测试")
    print("=" * 70)

    # 检查 CUDA
    import torch
    if torch.cuda.is_available():
        print(f"\nCUDA: {torch.cuda.get_device_name(0)}")
        print(f"显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    else:
        print("\nCUDA: 不可用")

    # 初始化 Reranker（会自动下载模型）
    print("\n" + "-" * 70)
    print("初始化 Reranker（首次会下载模型）...")
    print("-" * 70)

    start = time.time()
    reranker = LLMReranker()
    elapsed = time.time() - start

    print(f"\n初始化完成 (耗时 {elapsed:.2f}s)")

    # 测试查询扩展
    print("\n" + "-" * 70)
    print("测试 1: 查询扩展")
    print("-" * 70)

    query = "什么是机器学习"
    print(f"\n原始查询: {query}")

    start = time.time()
    expanded = reranker.expand_query(query)
    elapsed = time.time() - start

    print(f"\n扩展结果 (耗时 {elapsed:.2f}s):")
    for i, q in enumerate(expanded, 1):
        print(f"  {i}. {q}")

    # 测试重排序
    print("\n" + "-" * 70)
    print("测试 2: 重排序")
    print("-" * 70)

    documents = [
        {"title": "机器学习简介", "content": "机器学习是人工智能的一个分支，专注于算法和统计模型。"},
        {"title": "深度学习", "content": "深度学习使用多层神经网络进行特征提取和模式识别。"},
        {"title": "Python 基础", "content": "Python 是一种高级编程语言，广泛用于 Web 开发。"},
        {"title": "AI 历史", "content": "人工智能自 1950 年代以来发展迅速，取得了许多突破。"},
    ]

    print(f"\n查询: {query}")
    print(f"文档数: {len(documents)}")

    start = time.time()
    reranked = reranker.rerank(query, documents, top_k=3)
    elapsed = time.time() - start

    print(f"\n重排序结果 (耗时 {elapsed:.2f}s):")
    for i, doc in enumerate(reranked, 1):
        score = doc.get('rerank_score', 0)
        title = doc.get('title', 'N/A')
        content = doc.get('content', '')[:50] + "..."
        print(f"  {i}. [{score:.4f}] {title}: {content}")

    # 总结
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)

    print("\n功能状态:")
    print("  Embedding: fastembed-gpu (ONNX)")
    print("  Reranker: PyTorch (cross-encoder)")
    print("  Query Expansion: PyTorch (Qwen2.5)")

    print("\n注意:")
    print("  - 首次运行会自动从 HuggingFace/ModelScope 下载模型")
    print("  - 模型会缓存到 ~/.cache/qmd/models/")
    print("  - 后续运行无需重新下载")

    return 0

if __name__ == "__main__":
    sys.exit(test_full_pipeline())
