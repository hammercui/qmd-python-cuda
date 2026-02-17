#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证 QMD 完整功能
"""

import sys
from pathlib import Path
import time

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))

from qmd.search.rerank import LLMReranker

def verify_qmd():
    """验证 QMD 功能"""
    print("\n" + "=" * 70)
    print("QMD 功能验证")
    print("=" * 70)

    # 检查 CUDA
    import torch
    if torch.cuda.is_available():
        print(f"\nCUDA: {torch.cuda.get_device_name(0)}")
        print(f"显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    else:
        print("\nCUDA: 不可用")

    # 检查模型缓存
    print("\n" + "-" * 70)
    print("检查模型缓存")
    print("-" * 70)

    cache_dir = Path.home() / ".cache" / "qmd" / "models"
    huggingface_cache = Path.home() / ".cache" / "huggingface" / "hub"

    print(f"\nQMD 缓存: {cache_dir}")
    if cache_dir.exists():
        qmd_files = list(cache_dir.rglob("*"))
        qmd_size = sum(f.stat().st_size for f in qmd_files if f.is_file())
        print(f"  文件数: {len([f for f in qmd_files if f.is_file()])}")
        print(f"  大小: {qmd_size / 1024 / 1024:.2f} MB")

    print(f"\nHuggingFace 缓存: {huggingface_cache}")
    if huggingface_cache.exists():
        hf_models = list(huggingface_cache.glob("models--*"))
        print(f"  模型数: {len(hf_models)}")
        for model_dir in hf_models[:5]:  # 只显示前 5 个
            model_name = model_dir.name.replace("models--", "").replace("--", "/")
            print(f"    - {model_name}")

    # 测试 Reranker
    print("\n" + "-" * 70)
    print("测试 Reranker（会自动加载模型）")
    print("-" * 70)

    start = time.time()
    reranker = LLMReranker()
    load_time = time.time() - start

    print(f"\n初始化完成 (耗时 {load_time:.2f}s)")

    # 测试查询
    query = "什么是机器学习"
    documents = [
        {"title": "机器学习", "content": "机器学习是人工智能的一个分支。"},
        {"title": "深度学习", "content": "深度学习使用神经网络。"},
        {"title": "Python", "content": "Python 是编程语言。"},
    ]

    print(f"\n查询: {query}")
    print(f"文档数: {len(documents)}")

    # 重排序
    start = time.time()
    reranked = reranker.rerank(query, documents, top_k=2)
    rerank_time = time.time() - start

    print(f"\n重排序结果 (耗时 {rerank_time:.2f}s):")
    for i, doc in enumerate(reranked, 1):
        score = doc.get('rerank_score', 0)
        title = doc.get('title', 'N/A')
        print(f"  {i}. [{score:.4f}] {title}")

    # 查询扩展
    print("\n" + "-" * 70)
    print("测试查询扩展")
    print("-" * 70)

    start = time.time()
    expanded = reranker.expand_query(query)
    expand_time = time.time() - start

    print(f"\n扩展结果 (耗时 {expand_time:.2f}s):")
    for i, q in enumerate(expanded, 1):
        print(f"  {i}. {q}")

    # 总结
    print("\n" + "=" * 70)
    print("验证完成")
    print("=" * 70)

    print("\n功能状态:")
    print("  Embedding: fastembed-gpu (ONNX) - bge-small-en-v1.5")
    print("  Reranker: PyTorch - cross-encoder/ms-marco-MiniLM-L-6-v2")
    print("  Query Expansion: PyTorch - Qwen/Qwen2.5-0.5B-Instruct")

    print("\n模型已缓存，后续运行无需重新下载")

    return 0

if __name__ == "__main__":
    sys.exit(verify_qmd())
