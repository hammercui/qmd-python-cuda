"""
Test llama-cpp-python model loading with different configurations.
"""

from pathlib import Path
from llama_cpp import Llama

model_path = Path(r"C:\Users\Administrator\.qmd\models\embeddinggemma-300M-Q8_0.gguf")

print(f"Model: {model_path}")
print(f"Size: {model_path.stat().st_size / (1024**2):.1f} MB\n")

# Test 1: CPU only
print("=" * 60)
print("Test 1: CPU only (n_gpu_layers=0)")
print("=" * 60)
try:
    model_cpu = Llama(
        model_path=str(model_path),
        n_gpu_layers=0,
        n_threads=8,
        verbose=True,
        embedding=True,
    )
    print("[OK] CPU mode works!\n")

    # Test embedding
    result = model_cpu.embed("Hello, world!")
    print(f"[OK] Embedding generated: dim={len(result[list(result.keys())[0]])}\n")

    del model_cpu
except Exception as e:
    print(f"[ERROR] CPU mode failed: {e}\n")

# Test 2: GPU with fewer layers
print("=" * 60)
print("Test 2: GPU with limited layers (n_gpu_layers=20)")
print("=" * 60)
try:
    model_gpu = Llama(
        model_path=str(model_path),
        n_gpu_layers=20,
        n_threads=8,
        verbose=True,
        embedding=True,
    )
    print("[OK] GPU mode works!\n")

    # Test embedding
    result = model_gpu.embed("Hello, world!")
    print(f"[OK] Embedding generated: dim={len(result[list(result.keys())[0]])}\n")

    del model_gpu
except Exception as e:
    print(f"[ERROR] GPU mode failed: {e}\n")

print("=" * 60)
print("All tests completed!")
print("=" * 60)
