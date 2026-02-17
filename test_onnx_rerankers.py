#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 ONNX Reranker 模型
"""

import sys
import time
from pathlib import Path

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))

from qmd.search.rerank_onnx import ONNXReranker

def test_model(model_name: str):
    """测试单个模型"""
    print("\n" + "=" * 70)
    print(f"测试: {model_name}")
    print("=" * 70)

    try:
        # 创建 reranker
        reranker = ONNXReranker(model_name=model_name)

        # 测试数据
        query = "What is machine learning?"
        documents = [
            {"title": "ML Intro", "content": "Machine learning is a subset of artificial intelligence."},
            {"title": "Deep Learning", "content": "Deep learning uses neural networks with multiple layers."},
            {"title": "Python Basics", "content": "Python is a popular programming language."},
            {"title": "AI History", "content": "Artificial intelligence has a long history."},
        ]

        # 预热
        print("\n预热中...")
        reranker.rerank(query, documents[:1], top_k=1)

        # 正式测试
        print("\n重排序中...")
        start = time.time()
        reranked = reranker.rerank(query, documents, top_k=3)
        elapsed = time.time() - start

        print(f"\n结果 (耗时 {elapsed:.3f}s):")
        for i, doc in enumerate(reranked, 1):
            score = doc.get('rerank_score', 0)
            title = doc.get('title', 'N/A')
            print(f"  {i}. [{score:.4f}] {title}")

        return elapsed, reranked

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("ONNX Reranker 模型对比测试")
    print("=" * 70)

    # 检查 CUDA
    import torch
    if torch.cuda.is_available():
        print(f"\nCUDA: {torch.cuda.get_device_name(0)}")
        print(f"显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    else:
        print("\nCUDA: 不可用 (使用 CPU)")

    # 测试模型
    models = [
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "BAAI/bge-reranker-base",
    ]

    results = {}

    for model in models:
        elapsed, reranked = test_model(model)
        if elapsed is not None:
            results[model] = {
                "time": elapsed,
                "results": reranked
            }

    # 总结
    print("\n" + "=" * 70)
    print("性能对比")
    print("=" * 70)

    if results:
        print(f"\n{'模型':<50} {'时间':<10}")
        print("-" * 70)

        for model, data in results.items():
            print(f"{model:<50} {data['time']:>8.3f}s")

        print("\n推荐:")
        fastest = min(results.items(), key=lambda x: x[1]['time'])
        print(f"  最快: {fastest[0]} ({fastest[1]['time']:.3f}s)")

    return 0

if __name__ == "__main__":
    sys.exit(main())
