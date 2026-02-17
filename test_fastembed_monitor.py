#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控 GPU 使用的 fastembed 测试
"""

import sys
import time
import subprocess

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def get_gpu_usage():
    """获取 GPU 使用情况"""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used,memory.total,utilization.gpu',
             '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(', ')
            return {
                'memory_used': int(parts[0]),
                'memory_total': int(parts[1]),
                'gpu_util': int(parts[2])
            }
    except:
        pass
    return None

def test_with_monitoring():
    """测试并监控 GPU"""
    print("\n" + "=" * 70)
    print("fastembed GPU 实时监控")
    print("=" * 70)

    # 初始状态
    print("\n初始状态:")
    gpu_before = get_gpu_usage()
    if gpu_before:
        print(f"  显存: {gpu_before['memory_used']} MB / {gpu_before['memory_total']} MB")
        print(f"  GPU 利用率: {gpu_before['gpu_util']}%")

    # 创建模型
    print("\n创建 fastembed 模型 (CUDA)...")
    from fastembed import TextEmbedding

    model = TextEmbedding(
        model_name="BAAI/bge-small-en-v1.5",
        providers=["CUDAExecutionProvider"]
    )

    print("模型加载完成:")
    gpu_loaded = get_gpu_usage()
    if gpu_loaded:
        mem_increase = gpu_loaded['memory_used'] - gpu_before['memory_used']
        print(f"  显存: {gpu_loaded['memory_used']} MB (+{mem_increase} MB)")
        print(f"  GPU 利用率: {gpu_loaded['gpu_util']}%")

    # 测试嵌入
    print("\n执行嵌入 (100 文档)...")
    docs = ["测试文档内容" * 50 for _ in range(100)]

    start = time.time()
    embeddings = list(model.embed(docs))
    elapsed = time.time() - start

    print(f"\n嵌入完成:")
    print(f"  耗时: {elapsed:.3f}s")
    print(f"  速度: {len(docs) / elapsed:.1f} docs/s")

    gpu_after = get_gpu_usage()
    if gpu_after:
        print(f"  显存: {gpu_after['memory_used']} MB")
        print(f"  GPU 利用率: {gpu_after['gpu_util']}%")

    # 结论
    print("\n" + "=" * 70)
    print("结论")
    print("=" * 70)

    if gpu_loaded and gpu_before:
        mem_used = gpu_loaded['memory_used'] - gpu_before['memory_used']

        if mem_used > 100:
            print(f"\nGPU 显存增加了 {mem_used} MB")
            print("fastembed 模型已加载到 GPU")
            print("\n注意: ONNX Runtime 的 GPU 利用率可能不准确")
            print("实际加速是通过 CUDAExecutionProvider 实现的")
        else:
            print("\nGPU 显存使用无明显变化")
            print("可能使用 CPU 或模型极小")

    return 0

if __name__ == "__main__":
    sys.exit(test_with_monitoring())
