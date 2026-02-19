"""
Quick Demo: BGE Embedding with llama-cpp-python

演示如何使用 llama-cpp-python 生成文档嵌入向量。
"""

from pathlib import Path
from llama_cpp import Llama
import numpy as np
import time


def cosine_similarity(a, b):
    """计算余弦相似度"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def main():
    print("=" * 60)
    print("BGE Embedding Demo (llama-cpp-python + CUDA)")
    print("=" * 60)

    # 加载模型
    model_path = Path(r"C:\Users\Administrator\.qmd\models\bge-small-en-v1.5.Q8_0.gguf")

    print(f"\n1. Loading model...")
    start = time.time()
    model = Llama(
        model_path=str(model_path),
        n_gpu_layers=-1,  # 全部 GPU 加速
        n_threads=8,
        verbose=False,
        embedding=True,
    )
    load_time = time.time() - start
    print(f"   ✓ Model loaded in {load_time * 1000:.1f} ms\n")

    # 示例文档
    documents = [
        "Machine learning is a subset of artificial intelligence.",
        "Deep learning uses neural networks with multiple layers.",
        "Python is a popular programming language for data science.",
        "The cat sat on the mat and looked out the window.",
        "Quantum computing leverages quantum mechanics for computation.",
    ]

    # 查询文本
    query = "What is artificial intelligence?"

    print(f"2. Generating embeddings...")
    print(f"   Query: '{query}'")
    print(f"   Documents: {len(documents)}\n")

    # 生成查询嵌入
    start = time.time()
    query_emb = model.embed(query)
    if isinstance(query_emb, dict):
        query_emb = list(query_emb.values())[0]
    else:
        query_emb = query_emb[0] if isinstance(query_emb, list) else query_emb
    query_time = time.time() - start

    print(f"   ✓ Query embedding: {query_time * 1000:.2f} ms")
    print(f"   ✓ Vector dimension: {len(query_emb)}\n")

    # 生成文档嵌入
    start = time.time()
    doc_embs = []
    for doc in documents:
        emb = model.embed(doc)
        if isinstance(emb, dict):
            emb = list(emb.values())[0]
        else:
            emb = emb[0] if isinstance(emb, list) else emb
        doc_embs.append(emb)
    docs_time = time.time() - start

    print(f"   ✓ Document embeddings: {docs_time * 1000:.2f} ms")
    print(f"   ✓ Average per doc: {(docs_time / len(documents)) * 1000:.2f} ms\n")

    # 计算相似度
    print(f"3. Computing similarities...\n")
    similarities = []
    for i, (doc, doc_emb) in enumerate(zip(documents, doc_embs)):
        sim = cosine_similarity(query_emb, doc_emb)
        similarities.append((i, doc, sim))

    # 排序
    similarities.sort(key=lambda x: x[2], reverse=True)

    # 显示结果
    print(f"   Top 5 most relevant documents:\n")
    for rank, (idx, doc, sim) in enumerate(similarities[:5], 1):
        bar_length = int(sim * 40)
        bar = "█" * bar_length + "░" * (40 - bar_length)
        print(f"   {rank}. [{bar}] {sim:.3f}")
        print(f'      "{doc[:70]}..."\n')

    print(f"=" * 60)
    print("Performance Summary")
    print(f"=" * 60)
    print(f"Model load time:  {load_time * 1000:.1f} ms")
    print(f"Query embedding:  {query_time * 1000:.2f} ms")
    print(f"Batch embedding:  {docs_time * 1000:.2f} ms ({len(documents)} docs)")
    print(f"Avg per document: {(docs_time / len(documents)) * 1000:.2f} ms")
    print(f"Total time:       {(load_time + query_time + docs_time) * 1000:.1f} ms")
    print(f"=" * 60)


if __name__ == "__main__":
    main()
