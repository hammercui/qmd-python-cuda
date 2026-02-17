#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断 GPU 使用情况
"""

import sys
from pathlib import Path

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))

def diagnose_gpu():
    """诊断 GPU 使用"""
    print("\n" + "=" * 70)
    print("GPU 使用诊断")
    print("=" * 70)

    # 1. PyTorch CUDA
    print("\n1. PyTorch CUDA 状态")
    print("-" * 70)

    try:
        import torch

        print(f"CUDA 可用: {torch.cuda.is_available()}")

        if torch.cuda.is_available():
            print(f"CUDA 版本: {torch.version.cuda}")
            print(f"GPU 数量: {torch.cuda.device_count()}")
            print(f"当前 GPU: {torch.cuda.current_device()}")
            print(f"GPU 名称: {torch.cuda.get_device_name(0)}")

            # 显存
            print(f"\n显存信息:")
            print(f"  总显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
            print(f"  已分配: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB")
            print(f"  已缓存: {torch.cuda.memory_reserved(0) / 1024**2:.2f} MB")
        else:
            print("CUDA 不可用！")

    except ImportError:
        print("错误: PyTorch 未安装")

    # 2. fastembed GPU
    print("\n2. fastembed GPU 状态")
    print("-" * 70)

    try:
        from fastembed import TextEmbedding

        # 检查支持的提供者
        print("fastembed 已安装")

        # 尝试创建 GPU 模型
        print("\n尝试创建 GPU 模型...")

        try:
            model = TextEmbedding(
                model_name="BAAI/bge-small-en-v1.5",
                providers=["CUDAExecutionProvider"]
            )
            print("✅ CUDA Execution Provider 可用")

            # 测试嵌入
            print("\n测试嵌入...")
            import time
            start = time.time()
            embeddings = list(model.embed(["测试文档"]))
            elapsed = time.time() - start

            print(f"  耗时: {elapsed:.3f}s")
            print(f"  向量维度: {len(embeddings[0])}")

        except Exception as e:
            print(f"❌ CUDA Execution Provider 不可用: {e}")

            # 尝试 CPU
            print("\n尝试 CPU 模式...")
            model = TextEmbedding(
                model_name="BAAI/bge-small-en-v1.5",
                providers=["CPUExecutionProvider"]
            )
            print("✅ CPU Execution Provider 可用")

    except ImportError:
        print("错误: fastembed 未安装")

    # 3. onnxruntime GPU
    print("\n3. onnxruntime GPU 状态")
    print("-" * 70)

    try:
        import onnxruntime as ort

        print(f"onnxruntime 版本: {ort.__version__}")

        # 检查可用的提供者
        providers = ort.get_available_providers()
        print(f"可用的提供者: {providers}")

        if 'CUDAExecutionProvider' in providers:
            print("✅ CUDAExecutionProvider 可用")
        else:
            print("❌ CUDAExecutionProvider 不可用")

    except ImportError:
        print("错误: onnxruntime 未安装")

    # 4. LLMEngine 模式
    print("\n4. LLMEngine 模式")
    print("-" * 70)

    try:
        from qmd.llm.engine import LLMEngine

        # 检测模式
        import os
        vram_gb = 6  # GTX 1660 Ti

        print(f"检测到的 VRAM: {vram_gb}GB")

        if vram_gb < 8:
            print(f"VRAM < 8GB → 默认使用 server 模式")
        else:
            print(f"VRAM >= 8GB → 默认使用 standalone 模式")

        # 创建引擎
        print("\n创建 LLMEngine (standalone)...")
        engine = LLMEngine(mode='standalone')

        print(f"引擎模式: {engine.mode}")

        # 测试嵌入
        print("\n测试嵌入...")
        import time

        # 清理 GPU 缓存
        if 'torch' in sys.modules:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats()

        start = time.time()
        embeddings = engine.embed_texts(["测试文档1", "测试文档2"])
        elapsed = time.time() - start

        print(f"  耗时: {elapsed:.3f}s")
        print(f"  向量维度: {len(embeddings[0])}")

        # 检查 GPU 使用
        if 'torch' in sys.modules:
            import torch
            if torch.cuda.is_available():
                gpu_allocated = torch.cuda.memory_allocated(0) / 1024**2
                gpu_reserved = torch.cuda.memory_reserved(0) / 1024**2
                gpu_peak = torch.cuda.max_memory_allocated(0) / 1024**2

                print(f"\nGPU 显存使用:")
                print(f"  已分配: {gpu_allocated:.2f} MB")
                print(f"  已预留: {gpu_reserved:.2f} MB")
                print(f"  峰值: {gpu_peak:.2f} MB")

                if gpu_allocated < 10:
                    print("\n⚠️ GPU 显存使用过低！可能使用的是 CPU")
                else:
                    print("\n✅ GPU 显存正常使用")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

    # 5. Reranker GPU 使用
    print("\n5. Reranker GPU 状态")
    print("-" * 70)

    try:
        from qmd.search.rerank import LLMReranker

        print("创建 Reranker...")
        reranker = LLMReranker()

        # 检查设备
        print(f"设备: {reranker._device}")

        # 测试
        print("\n测试重排序...")
        documents = [
            {"title": "测试1", "content": "机器学习"},
            {"title": "测试2", "content": "深度学习"},
        ]

        import time

        if 'torch' in sys.modules:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats()

        start = time.time()
        reranked = reranker.rerank("机器学习", documents, top_k=2)
        elapsed = time.time() - start

        print(f"  耗时: {elapsed:.3f}s")

        # 检查 GPU 使用
        if 'torch' in sys.modules:
            import torch
            if torch.cuda.is_available():
                gpu_allocated = torch.cuda.memory_allocated(0) / 1024**2
                gpu_peak = torch.cuda.max_memory_allocated(0) / 1024**2

                print(f"\nGPU 显存使用:")
                print(f"  已分配: {gpu_allocated:.2f} MB")
                print(f"  峰值: {gpu_peak:.2f} MB")

                if 'cuda' in str(reranker._device).lower():
                    print("\n✅ Reranker 使用 GPU")
                else:
                    print(f"\n⚠️ Reranker 使用 {reranker._device}")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

    return 0

if __name__ == "__main__":
    sys.exit(diagnose_gpu())
