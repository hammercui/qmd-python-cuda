"""测试fastembed模型加载"""
import sys

try:
    from fastembed import TextEmbedding

    print("Testing fastembed model loading...")

    # 尝试加载默认模型
    model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

    print("OK Model loaded successfully!")

    # 测试嵌入
    texts = ["test text 1", "test text 2"]
    embeddings = list(model.embed(texts))

    print(f"OK Embedding successful!")
    print(f"  Texts: {len(texts)}")
    print(f"  Embeddings: {len(embeddings)}")
    print(f"  Dimensions: {len(embeddings[0])}")

except Exception as e:
    print(f"X Error: {e}")
    import traceback
    traceback.print_exc()
