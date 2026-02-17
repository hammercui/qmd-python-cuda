#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断 fastembed GPU 使用情况
"""

import sys
from pathlib import Path

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 70)
print("FastEmbed GPU 诊断")
print("=" * 70)

# 1. 检查 fastembed 版本
print("\n步骤 1: 检查 fastembed 版本")
print("-" * 70)

try:
    import fastembed
    print(f"✅ fastembed 版本: {fastembed.__version__}")
    print(f"   模块路径: {fastembed.__file__}")
except ImportError as e:
    print(f"❌ fastembed 导入失败: {e}")
    sys.exit(1)

# 2. 检查 onnxruntime 版本和 CUDA 支持
print("\n步骤 2: 检查 onnxruntime CUDA 支持")
print("-" * 70)

try:
    import onnxruntime as ort
    print(f"✅ ONNX Runtime 版本: {ort.__version__}")
    print(f"   模块路径: {ort.__file__}")

    # 检查可用的 Execution Providers
    available_eps = ort.get_available_providers()
    print(f"\n可用的 Execution Providers:")
    for ep in available_eps:
        status = "✅" if "CUDA" in ep or "Tensorrt" in ep else "  "
        print(f"  {status} {ep}")

    if "CUDAExecutionProvider" in available_eps:
        print("\n✅ CUDA Execution Provider 可用!")
    else:
        print("\n⚠️  CUDA Execution Provider 不可用!")
        print("   即使使用 fastembed-gpu,也会回退到 CPU")

except ImportError as e:
    print(f"❌ onnxruntime 导入失败: {e}")

# 3. 检查 PyTorch CUDA
print("\n步骤 3: 检查 PyTorch CUDA 支持")
print("-" * 70)

try:
    import torch
    print(f"✅ PyTorch 版本: {torch.__version__}")
    print(f"   模块路径: {torch.__file__}")

    if torch.cuda.is_available():
        print(f"✅ CUDA 可用: {torch.version.cuda}")
        gpu_count = torch.cuda.device_count()
        print(f"   GPU 数量: {gpu_count}")

        for i in range(gpu_count):
            props = torch.cuda.get_device_properties(i)
            print(f"\n   GPU {i}: {props.name}")
            print(f"     显存: {props.total_memory / 1e9:.1f} GB")
            print(f"     计算能力: {props.major}.{props.minor}")
    else:
        print("⚠️  CUDA 不可用")

except ImportError:
    print("⚠️  PyTorch 未安装")

# 4. 测试 fastembed TextEmbedding
print("\n步骤 4: 测试 fastembed TextEmbedding")
print("-" * 70)

try:
    from fastembed import TextEmbedding

    print("创建 TextEmbedding 模型...")

    # 测试不指定 providers
    print("\n测试 1: 默认配置 (不指定 providers)")
    model1 = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

    # 检查模型使用的 providers
    if hasattr(model1.model, 'get_providers'):
        providers = model1.model.get_providers()
        print(f"  使用的 Providers: {providers}")
    else:
        print("  ⚠️  无法获取 providers 信息 (模型可能未初始化)")

    # 测试指定 CUDAExecutionProvider
    print("\n测试 2: 显式指定 CUDAExecutionProvider")
    try:
        model2 = TextEmbedding(
            model_name="BAAI/bge-small-en-v1.5",
            providers=["CUDAExecutionProvider"]
        )

        if hasattr(model2.model, 'get_providers'):
            providers = model2.model.get_providers()
            print(f"  使用的 Providers: {providers}")
        else:
            print("  ⚠️  无法获取 providers 信息")

        # 测试向量化
        print("\n  测试向量化...")
        test_texts = ["这是一个测试文本", "FastEmbed GPU 加速测试"]

        import time
        start = time.time()
        embeddings = list(model2.embed(test_texts))
        elapsed = time.time() - start

        print(f"  ✅ 向量化成功! 耗时: {elapsed:.3f}s")
        print(f"     向量维度: {len(embeddings[0])}")

        # 检查 GPU 使用
        try:
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.used,utilization.gpu',
                 '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(', ')
                print(f"  GPU 状态: 显存 {parts[0]}MB, 利用率 {parts[1]}%")
        except:
            pass

    except Exception as e:
        print(f"  ❌ 指定 CUDAExecutionProvider 失败: {e}")
        print("     这通常意味着 onnxruntime-gpu 的 CUDA EP 不可用")

except Exception as e:
    print(f"❌ fastembed 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 5. 结论和建议
print("\n" + "=" * 70)
print("诊断结论")
print("=" * 70)

print("""
根据测试结果,fastembed GPU 支持情况:

✅ 如果 "CUDAExecutionProvider" 在可用列表中:
   → fastembed-gpu 正确安装
   → 需要在代码中显式指定 providers=["CUDAExecutionProvider"]
   → 修改 qmd/llm/engine.py 第195-206行

⚠️  如果 "CUDAExecutionProvider" 不在可用列表中:
   → onnxruntime-gpu 的 CUDA 支持未正确配置
   → 可能原因:
     * CUDA 驱动版本不匹配
     * cuDNN 未安装或版本不匹配
     * onnxruntime-gpu 版本与 CUDA 版本不兼容

📝 下一步:
   1. 检查 CUDA 驱动: nvidia-smi
   2. 检查 CUDA 版本匹配: pyproject.toml 中的版本
   3. 必要时重新安装 onnxruntime-gpu
""")
