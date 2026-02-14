import time
from qmd.database.manager import DatabaseManager
from qmd.search.hybrid import HybridSearcher
from qmd.search.rerank import LLMReranker

def benchmark_search():
    db = DatabaseManager()
    hybrid = HybridSearcher(db)
    reranker = LLMReranker()
    
    query = "qmd"
    collection = "tests"
    
    # Warm up
    hybrid.search(query, collection=collection)
    
    start_time = time.time()
    results = hybrid.search(query, collection=collection, limit=5)
    hybrid_time = time.time() - start_time
    
    print(f"Hybrid search time: {hybrid_time:.4f}s")
    
    start_time = time.time()
    reranked = reranker.rerank(query, results)
    rerank_time = time.time() - start_time
    
    print(f"Reranking time: {rerank_time:.4f}s")
    print(f"Total time: {hybrid_time + rerank_time:.4f}s")

if __name__ == "__main__":
    benchmark_search()
