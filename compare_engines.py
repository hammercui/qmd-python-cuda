#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
引擎性能对比测试
对比 ONNX Runtime vs llama.cpp (CUDA) 的性能
"""

import sys
import time
from typing import List, Dict, Any

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def test_pytorch_reranker():
    """测试 PyTorch Reranker"""
    print("\n" + "=" * 70)
    print("测试 1: PyTorch Reranker (cross-encoder)")
    print("=" * 70)

    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        import torch

        model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"

        print(f"加载模型: {model_name}")
        start = time.time()
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
        load_time = time.time() - start

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model.to(device)
        model.eval()

        print(f"✓ 模型加载完成 ({load_time:.2f}s)")
        print(f"✓ 设备: {device}")

        # 测试推理
        query = "What is machine learning?"
        docs = ["Machine learning is a subset of AI."] * 10

        start = time.time()
        with torch.no_grad():
            for doc in docs:
                inputs = tokenizer(query, doc, return_tensors="pt", truncation=True, max_length=512)
                inputs = {k: v.to(device) for k, v in inputs.items()}
                outputs = model(**inputs)
        inference_time = time.time() - start

        print(f"✓ 推理完成 ({len(docs)} 文档)")
        print(f"  推理时间: {inference_time:.3f}s")
        print(f"  平均每文档: {inference_time / len(docs):.4f}s")

        # 显存使用
        if torch.cuda.is_available():
            vram_mb = torch.cuda.max_memory_allocated() / 1024 / 1024
            print(f"  显存占用: {vram_mb:.0f}MB")

        return {
            "engine": "PyTorch",
            "load_time": load_time,
            "inference_time": inference_time,
            "per_doc": inference_time / len(docs),
            "vram_mb": vram_mb if torch.cuda.is_available() else 0
        }

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return None


def test_onnx_reranker():
    """测试 ONNX Runtime Reranker"""
    print("\n" + "=" * 70)
    print("测试 2: ONNX Runtime Reranker")
    print("=" * 70)

    try:
        from optimum.onnxruntime import ORTModelForSequenceClassification
        from transformers import AutoTokenizer
        import torch

        model_name = "XorPLM/ms-marco-MiniLM-L-6-v2-onnx"  # 或其他 ONNX 版本

        print(f"加载模型: {model_name}")
        start = time.time()
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = ORTModelForSequenceClassification.from_pretrained(
            model_name,
            provider="CUDAExecutionProvider" if torch.cuda.is_available() else "CPUExecutionProvider"
        )
        load_time = time.time() - start

        print(f"✓ 模型加载完成 ({load_time:.2f}s)")

        # 测试推理
        query = "What is machine learning?"
        docs = ["Machine learning is a subset of AI."] * 10

        start = time.time()
        for doc in docs:
            inputs = tokenizer(query, doc, return_tensors="pt", truncation=True, max_length=512)
            outputs = model(**inputs)
        inference_time = time.time() - start

        print(f"✓ 推理完成 ({len(docs)} 文档)")
        print(f"  推理时间: {inference_time:.3f}s")
        print(f"  平均每文档: {inference_time / len(docs):.4f}s")

        return {
            "engine": "ONNX Runtime",
            "load_time": load_time,
            "inference_time": inference_time,
            "per_doc": inference_time / len(docs),
            "vram_mb": 0  # ONNX Runtime 不容易获取显存
        }

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return None


def test_llama_cpp_reranker():
    """测试 llama.cpp Reranker (GGUF)"""
    print("\n" + "=" * 70)
    print("测试 3: llama.cpp Reranker (GGUF + CUDA)")
    print("=" * 70)

    try:
        from llama_cpp import Llama

        # 注意：cross-encoder 需要特殊处理，这里用 LLM 模拟
        # 实际中需要找到 cross-encoder 的 GGUF 版本
        model_path = "~/.cache/qmd/models/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf"

        print(f"加载模型: {model_path}")
        print("⚠️  注意: cross-encoder 的 GGUF 版本可能需要自己转换")

        start = time.time()
        model = Llama(
            model_path=model_path,
            n_gpu_layers=-1,  # 全部 GPU
            n_ctx=2048,
            verbose=False
        )
        load_time = time.time() - start

        print(f"✓ 模型加载完成 ({load_time:.2f}s")
        print(f"✓ GPU 加速: 已启用")

        # 测试推理（用文本生成模拟）
        query = "What is machine learning?"
        prompt = f"Query: {query}\nDocument: Machine learning is a subset of AI.\nRelevance:"

        start = time.time()
        for _ in range(10):
            output = model(prompt, max_tokens=1, temperature=0)
        inference_time = time.time() - start

        print(f"✓ 推理完成 (10 次)")
        print(f"  推理时间: {inference_time:.3f}s")
        print(f"  平均每次: {inference_time / 10:.4f}s")

        # 显存估算（GGUF Q4 大约是原大小的 1/4）
        vram_mb = 80  # 110MB 模型 → Q4 约 80MB
        print(f"  显存占用: ~{vram_mb}MB (估算)")

        return {
            "engine": "llama.cpp (GGUF)",
            "load_time": load_time,
            "inference_time": inference_time,
            "per_doc": inference_time / 10,
            "vram_mb": vram_mb
        }

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return None


def print_summary(results: List[Dict[str, Any]]):
    """打印性能对比总结"""
    print("\n" + "=" * 70)
    print("📊 性能对比总结")
    print("=" * 70)

    valid_results = [r for r in results if r is not None]

    if not valid_results:
        print("没有有效的测试结果")
        return

    print(f"\n{'引擎':<20} {'加载时间':<12} {'推理时间':<12} {'每文档':<12} {'显存':<10}")
    print("-" * 70)

    for r in valid_results:
        print(f"{r['engine']:<20} {r['load_time']:>8.2f}s   {r['inference_time']:>8.3f}s   "
              f"{r['per_doc']:>8.4f}s   {r['vram_mb']:>6.0f}MB")

    if len(valid_results) >= 2:
        print("\n📈 相对提升 (以 PyTorch 为基准):")
        baseline = valid_results[0]  # 假设第一个是基准

        for r in valid_results[1:]:
            speedup = baseline['inference_time'] / r['inference_time']
            memory_reduction = (1 - r['vram_mb'] / baseline['vram_mb']) * 100

            print(f"\n{r['engine']}:")
            print(f"  速度提升: {speedup:.1f}x")
            print(f"  显存减少: {memory_reduction:.0f}%")


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("🔥 引擎性能对比测试")
    print("=" * 70)

    results = []

    # 测试各个引擎
    results.append(test_pytorch_reranker())
    # results.append(test_onnx_reranker())  # 需要先安装 optimum
    # results.append(test_llama_cpp_reranker())  # 需要先安装 llama-cpp-python

    # 打印总结
    print_summary(results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
