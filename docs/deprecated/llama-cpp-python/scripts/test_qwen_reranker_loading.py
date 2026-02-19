"""
Test Qwen3 Reranker model loading.
"""

from pathlib import Path
from llama_cpp import Llama

model_path = Path(r"C:\Users\Administrator\.qmd\models\qwen3-reranker-0.6b-q8_0.gguf")

print(f"Model: {model_path}")
print(f"Size: {model_path.stat().st_size / (1024**2):.1f} MB\n")

# Test with fewer GPU layers first
print("=" * 60)
print("Loading Qwen3-Reranker-0.6B...")
print("=" * 60)

try:
    # Try with CPU first to see if it's a compatibility issue
    print("\nTest 1: CPU only...")
    model_cpu = Llama(
        model_path=str(model_path),
        n_gpu_layers=0,
        n_threads=8,
        verbose=True,
    )
    print("[OK] CPU mode works!\n")

    # Test generation
    output = model_cpu(
        "Hello, world!",
        max_tokens=10,
        temperature=0.7,
    )
    print(f"Output: {output['choices'][0]['text']}")
    print()

    del model_cpu

    print("\nTest 2: GPU with limited layers (25)...")
    model_gpu = Llama(
        model_path=str(model_path),
        n_gpu_layers=25,  # Try with fewer layers
        n_threads=8,
        verbose=True,
    )
    print("[OK] GPU mode works!\n")

    # Test generation
    output = model_gpu(
        "Query: What is ML?\nDocument: ML is awesome.\nRelevant:",
        max_tokens=5,
        temperature=0.0,
    )
    print(f"Output: {output['choices'][0]['text']}")
    print()

    del model_gpu

    print("=" * 60)
    print("[OK] Qwen3-Reranker works!")
    print("=" * 60)

except Exception as e:
    print(f"[ERROR] {e}")
    import traceback

    traceback.print_exc()
