"""
Test bge-small-en-v1.5 GGUF model loading.
"""

from pathlib import Path
from llama_cpp import Llama

model_path = Path(r"C:\Users\Administrator\.qmd\models\bge-small-en-v1.5.Q8_0.gguf")

print(f"Model: {model_path}")
print(f"Size: {model_path.stat().st_size / (1024**2):.1f} MB\n")

# Test with GPU
print("=" * 60)
print("Loading BGE Small English v1.5 (Q8)...")
print("=" * 60)

try:
    model = Llama(
        model_path=str(model_path),
        n_gpu_layers=-1,  # Use all GPU layers
        n_threads=8,
        verbose=True,
        embedding=True,
    )

    print("\n[OK] Model loaded successfully!\n")

    # Test embedding
    test_texts = [
        "Hello, world!",
        "This is a test sentence for embedding generation.",
        "Machine learning is fascinating.",
    ]

    print("Testing embedding generation...")
    for text in test_texts:
        result = model.embed(text)
        # Result can be either dict or list
        if isinstance(result, dict):
            embedding = result[list(result.keys())[0]]
        else:
            embedding = result
        print(f"  Text: '{text[:50]}...'")
        print(f"  Embedding dim: {len(embedding)}")
        print(f"  First 5 values: {embedding[:5]}")
        print()

    print("=" * 60)
    print("[OK] BGE model works perfectly!")
    print("=" * 60)

    del model

except Exception as e:
    print(f"[ERROR] {e}")
    import traceback

    traceback.print_exc()
