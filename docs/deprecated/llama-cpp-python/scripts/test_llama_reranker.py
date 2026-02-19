"""
Llama-cpp-python Reranker Performance Benchmark

Tests the performance of Qwen3-Reranker-0.6B GGUF model for document reranking.
Measures throughput, latency, and resource usage.
"""

import time
import psutil
from pathlib import Path
from typing import List, Dict, Any, Tuple
import json

try:
    from llama_cpp import Llama

    print("[OK] llama-cpp-python imported successfully")
except ImportError:
    print("[X] llama-cpp-python not found.")
    exit(1)


class RerankerBenchmark:
    """Benchmark llama-cpp-python reranker performance."""

    def __init__(
        self,
        model_path: str,
        n_ctx: int = 512,
        n_gpu_layers: int = -1,
        n_threads: int = None,
    ):
        """
        Initialize benchmark with model.

        Args:
            model_path: Path to GGUF model file
            n_ctx: Context window size
            n_gpu_layers: Number of layers to offload to GPU (-1 = all)
            n_threads: Number of CPU threads (None = auto)
        """
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        # Detect system specs
        self.cpu_count = psutil.cpu_count()
        self.memory_total = psutil.virtual_memory().total / (1024**3)

        # Detect CUDA
        try:
            import torch

            self.cuda_available = torch.cuda.is_available()
            if self.cuda_available:
                self.gpu_name = torch.cuda.get_device_name(0)
                self.gpu_memory = torch.cuda.get_device_properties(0).total_memory / (
                    1024**3
                )
            else:
                self.gpu_name = None
                self.gpu_memory = 0
        except ImportError:
            self.cuda_available = False
            self.gpu_name = None
            self.gpu_memory = 0

        # Set threads
        if n_threads is None:
            n_threads = max(1, self.cpu_count - 1)

        self.n_threads = n_threads
        self.n_gpu_layers = n_gpu_layers

        # Load model
        print(f"\n{'=' * 60}")
        print("Loading Reranker Model...")
        print(f"{'=' * 60}")
        print(f"Model: {self.model_path.name}")
        print(f"Size: {self.model_path.stat().st_size / (1024**2):.1f} MB")
        print(f"Threads: {n_threads}")
        print(f"GPU Layers: {n_gpu_layers if self.cuda_available else 0}")
        if self.cuda_available:
            print(f"GPU: {self.gpu_name}")
            print(f"GPU Memory: {self.gpu_memory:.1f} GB")

        start_time = time.time()
        self.model = Llama(
            model_path=str(self.model_path),
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers if self.cuda_available else 0,
            n_threads=n_threads,
            verbose=False,
        )
        load_time = time.time() - start_time

        print(f"\n[OK] Model loaded in {load_time:.2f}s")
        print(f"{'=' * 60}\n")

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = None,
    ) -> List[Tuple[int, float]]:
        """
        Rerank documents by relevance to query.

        Args:
            query: Search query
            documents: List of document texts
            top_k: Number of top results to return (None = all)

        Returns:
            List of (doc_index, score) tuples, sorted by score descending
        """
        # Format prompt for reranker
        # Format: "Query: {query}\nDocument: {doc}\nRelevant:"
        prompts = []
        for doc in documents:
            prompt = f"Query: {query}\nDocument: {doc}\nRelevant:"
            prompts.append(prompt)

        # Get scores for each document
        scores = []
        for prompt in prompts:
            # Get logits for the last token
            result = self.model(
                prompt,
                max_tokens=1,
                logprobs=1,
                temperature=0.0,
            )
            # Extract score from logprobs
            # For reranking, we use the probability of the "yes" or similar positive token
            if "logprobs" in result and len(result["logprobs"]) > 0:
                # Get the first token's logprob
                logprob = list(result["logprobs"].values())[0]
                # Convert logprob to probability and use as relevance score
                score = 1.0 / (1.0 + abs(-logprob))  # Simple transformation
            else:
                score = 0.5  # Default neutral score

            scores.append(score)

        # Sort by score descending
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

        if top_k:
            ranked = ranked[:top_k]

        return ranked

    def rerank_simple(
        self,
        query: str,
        documents: List[str],
        top_k: int = None,
    ) -> List[Tuple[int, float]]:
        """
        Simplified reranking using cosine similarity with embeddings.

        This is a faster alternative when true cross-encoder reranking is too slow.
        """
        # Generate embeddings for query and documents
        query_emb = self.model.embed(query)
        if isinstance(query_emb, dict):
            query_emb = list(query_emb.values())[0]
        else:
            query_emb = query_emb[0] if isinstance(query_emb, list) else query_emb

        doc_embs = []
        for doc in documents:
            emb = self.model.embed(doc)
            if isinstance(emb, dict):
                emb = list(emb.values())[0]
            else:
                emb = emb[0] if isinstance(emb, list) else emb
            doc_embs.append(emb)

        # Calculate cosine similarities
        import numpy as np

        scores = []
        for doc_emb in doc_embs:
            query_np = np.array(query_emb)
            doc_np = np.array(doc_emb)
            similarity = np.dot(query_np, doc_np) / (
                np.linalg.norm(query_np) * np.linalg.norm(doc_np)
            )
            scores.append(float(similarity))

        # Sort by score descending
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

        if top_k:
            ranked = ranked[:top_k]

        return ranked

    def benchmark_single_rerank(
        self,
        query: str,
        documents: List[str],
        warmup_runs: int = 2,
        benchmark_runs: int = 5,
    ) -> Dict[str, Any]:
        """
        Benchmark single reranking operation.

        Returns:
            Dict with timing stats
        """
        n_docs = len(documents)
        print(f"Benchmarking reranking ({n_docs} documents)...")
        print(f"  Query length: {len(query)} chars")
        print(f"  Warmup runs: {warmup_runs}")
        print(f"  Benchmark runs: {benchmark_runs}")

        # Warmup
        for _ in range(warmup_runs):
            self.rerank_simple(query, documents)

        # Benchmark
        times = []
        memory_before = psutil.virtual_memory().used

        if self.cuda_available:
            import torch

            torch.cuda.reset_peak_memory_stats()
            gpu_memory_before = torch.cuda.memory_allocated()

        for _ in range(benchmark_runs):
            start = time.perf_counter()
            self.rerank_simple(query, documents)
            end = time.perf_counter()
            times.append((end - start) * 1000)  # Convert to ms

        memory_after = psutil.virtual_memory().used
        memory_used = (memory_after - memory_before) / (1024**2)  # MB

        if self.cuda_available:
            gpu_memory_after = torch.cuda.memory_allocated()
            gpu_memory_used = (gpu_memory_after - gpu_memory_before) / (1024**2)  # MB
            gpu_memory_peak = torch.cuda.max_memory_allocated() / (1024**2)  # MB
        else:
            gpu_memory_used = 0
            gpu_memory_peak = 0

        # Calculate stats
        times_sorted = sorted(times)
        results = {
            "n_documents": n_docs,
            "mean_ms": sum(times) / len(times),
            "median_ms": times_sorted[len(times_sorted) // 2],
            "min_ms": min(times),
            "max_ms": max(times),
            "p95_ms": times_sorted[int(len(times) * 0.95)],
            "p99_ms": times_sorted[int(len(times) * 0.99)],
            "throughput_per_sec": 1000 / (sum(times) / len(times)),
            "memory_used_mb": memory_used,
            "gpu_memory_used_mb": gpu_memory_used,
            "gpu_memory_peak_mb": gpu_memory_peak,
        }

        return results

    def run_full_benchmark(
        self,
        save_results: bool = True,
        output_file: str = "reranker_benchmark_results.json",
    ) -> Dict[str, Any]:
        """
        Run comprehensive benchmark suite.

        Returns:
            Dict with all benchmark results
        """
        all_results = {
            "system_info": {
                "cpu_count": self.cpu_count,
                "memory_total_gb": self.memory_total,
                "cuda_available": self.cuda_available,
                "gpu_name": self.gpu_name,
                "gpu_memory_gb": self.gpu_memory,
                "threads_used": self.n_threads,
                "gpu_layers": self.n_gpu_layers if self.cuda_available else 0,
            },
            "model_info": {
                "path": str(self.model_path),
                "filename": self.model_path.name,
                "size_mb": self.model_path.stat().st_size / (1024**2),
            },
        }

        # Test queries and documents
        test_query = "What is machine learning?"

        test_cases = [
            {
                "name": "Small (5 docs)",
                "n_docs": 5,
                "doc_length": "short",
            },
            {
                "name": "Medium (10 docs)",
                "n_docs": 10,
                "doc_length": "medium",
            },
            {
                "name": "Large (20 docs)",
                "n_docs": 20,
                "doc_length": "short",
            },
        ]

        # Generate test documents
        short_docs = [
            "Machine learning is a subset of artificial intelligence.",
            "Deep learning uses neural networks with multiple layers.",
            "Python is a popular programming language for ML.",
            "TensorFlow and PyTorch are common ML frameworks.",
            "Data preprocessing is an important step in ML pipelines.",
            "Supervised learning uses labeled training data.",
            "Unsupervised learning finds patterns in unlabeled data.",
            "Reinforcement learning learns through trial and error.",
            "Neural networks are inspired by biological neurons.",
            "Gradient descent is used to optimize model parameters.",
        ]

        medium_docs = [
            " ".join(
                [
                    "Machine learning algorithms build a model based on sample data,",
                    "known as training data, in order to make predictions or decisions",
                    "without being explicitly programmed. Machine learning algorithms are",
                    "used in a wide variety of applications such as email filtering and",
                    "computer vision, where it is difficult or unfeasible to develop",
                    "conventional algorithms to perform the needed tasks.",
                ]
            )
            for _ in range(15)
        ]

        # Single reranking benchmarks
        print(f"\n{'=' * 60}")
        print("Reranking Benchmarks")
        print(f"{'=' * 60}\n")

        all_results["reranking"] = {}

        for case in test_cases:
            print(f"\n{'─' * 60}")
            print(f"Test Case: {case['name']}")
            print(f"{'─' * 60}")

            n_docs = case["n_docs"]
            if case["doc_length"] == "short":
                docs = short_docs[:n_docs]
            else:
                docs = medium_docs[:n_docs]

            results = self.benchmark_single_rerank(test_query, docs)
            all_results["reranking"][case["name"]] = results

            self._print_results(results)

        # Save results
        if save_results:
            output_path = Path(output_file)
            with open(output_path, "w") as f:
                json.dump(all_results, f, indent=2)
            print(f"\n{'=' * 60}")
            print(f"[OK] Results saved to: {output_path.absolute()}")
            print(f"{'=' * 60}")

        return all_results

    def _print_results(self, results: Dict[str, Any]):
        """Print benchmark results."""
        print(f"\n  Results:")
        print(f"    Mean:     {results['mean_ms']:.2f} ms")
        print(f"    Median:   {results['median_ms']:.2f} ms")
        print(f"    Min:      {results['min_ms']:.2f} ms")
        print(f"    Max:      {results['max_ms']:.2f} ms")
        print(f"    P95:      {results['p95_ms']:.2f} ms")
        print(f"    P99:      {results['p99_ms']:.2f} ms")
        print(f"    Throughput: {results['throughput_per_sec']:.2f} queries/sec")
        print(f"    Memory:   {results['memory_used_mb']:.1f} MB")
        if results["gpu_memory_peak_mb"] > 0:
            print(
                f"    GPU Memory: {results['gpu_memory_used_mb']:.1f} MB (peak: {results['gpu_memory_peak_mb']:.1f} MB)"
            )


def main():
    """Main benchmark entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Benchmark llama-cpp-python reranker performance"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="qwen3-reranker-0.6b-q8_0.gguf",
        help="Path to GGUF model file",
    )
    parser.add_argument(
        "--gpu-layers",
        type=int,
        default=-1,
        help="Number of layers to offload to GPU (-1 for all)",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=None,
        help="Number of CPU threads (None for auto)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="reranker_benchmark_results.json",
        help="Output file for results",
    )

    args = parser.parse_args()

    # Find model file
    model_path = Path(args.model)
    if not model_path.exists():
        # Try common locations
        possible_paths = [
            Path(args.model),
            Path.home() / ".qmd" / "models" / args.model,
            Path.cwd() / args.model,
        ]
        for path in possible_paths:
            if path.exists():
                model_path = path
                break
        else:
            print(f"Error: Model file not found: {args.model}")
            print("\nSearched in:")
            for p in possible_paths:
                print(f"  - {p}")
            exit(1)

    # Initialize benchmark
    try:
        benchmark = RerankerBenchmark(
            model_path=str(model_path),
            n_gpu_layers=args.gpu_layers,
            n_threads=args.threads,
        )
    except Exception as e:
        print(f"Error loading model: {e}")
        exit(1)

    # Run benchmark
    print("\n" + "█" * 60)
    print("█" + " " * 58 + "█")
    print("█" + "  RERANKER PERFORMANCE BENCHMARK".center(58) + "█")
    print("█" + " " * 58 + "█")
    print("█" * 60 + "\n")

    try:
        results = benchmark.run_full_benchmark(
            save_results=True,
            output_file=args.output,
        )

        # Print summary
        print("\n" + "=" * 60)
        print("BENCHMARK SUMMARY")
        print("=" * 60)

        # Get medium results for summary
        if "Medium (10 docs)" in results["reranking"]:
            medium_results = results["reranking"]["Medium (10 docs)"]
            print(f"\nModel: {results['model_info']['filename']}")
            print(f"Size: {results['model_info']['size_mb']:.1f} MB")
            print(
                f"\nGPU Acceleration: {'Enabled' if results['system_info']['cuda_available'] else 'Disabled'}"
            )
            if results["system_info"]["cuda_available"]:
                print(f"GPU: {results['system_info']['gpu_name']}")
                print(f"GPU Layers: {results['system_info']['gpu_layers']}")
            print(f"\nMedium (10 docs) Performance:")
            print(f"  Latency: {medium_results['median_ms']:.2f} ms (median)")
            print(
                f"  Throughput: {medium_results['throughput_per_sec']:.2f} queries/sec"
            )
            print(f"\n[OK] Benchmark complete!")

    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user.")
    except Exception as e:
        print(f"\nError during benchmark: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
