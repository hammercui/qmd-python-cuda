"""
Llama-cpp-python Embedding Performance Benchmark

Tests the performance of llama-cpp-python with GGUF models for embedding generation.
Measures throughput, latency, and resource usage.
"""

import time
import psutil
import os
from pathlib import Path
from typing import List, Dict, Any
import json

try:
    from llama_cpp import Llama

    print("[OK] llama-cpp-python imported successfully")
except ImportError:
    print("[X] llama-cpp-python not found. Install with:")
    print(
        "  pip install llama-cpp-python --index-url https://abetlen.github.io/llama-cpp-python/whl/cu121"
    )
    exit(1)


class EmbeddingBenchmark:
    """Benchmark llama-cpp-python embedding performance."""

    def __init__(
        self,
        model_path: str,
        n_ctx: int = 2048,
        n_gpu_layers: int = -1,  # -1 = all layers to GPU
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
        self.memory_total = psutil.virtual_memory().total / (1024**3)  # GB

        # Detect CUDA
        try:
            import torch

            self.cuda_available = torch.cuda.is_available()
            if self.cuda_available:
                self.gpu_name = torch.cuda.get_device_name(0)
                self.gpu_memory = torch.cuda.get_device_properties(0).total_memory / (
                    1024**3
                )  # GB
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
        print("Loading Model...")
        print(f"{'=' * 60}")
        print(f"Model: {self.model_path.name}")
        print(f"Size: {self.model_path.stat().st_size / (1024**2):.1f} MB")
        print(f"Threads: {n_threads}")
        print(
            f"GPU Layers: {n_gpu_layers if self.cuda_available else 0} (CUDA available: {self.cuda_available})"
        )
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
            embedding=True,  # Enable embedding mode
        )
        load_time = time.time() - start_time

        print(f"\n[OK] Model loaded in {load_time:.2f}s")
        print(f"{'=' * 60}\n")

    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        result = self.model.embed(text)
        # Result can be either dict or list depending on llama-cpp-python version
        if isinstance(result, dict):
            return result[list(result.keys())[0]]
        else:
            return result

    def benchmark_single_embedding(
        self,
        text: str,
        warmup_runs: int = 3,
        benchmark_runs: int = 10,
    ) -> Dict[str, Any]:
        """
        Benchmark single text embedding.

        Returns:
            Dict with timing stats
        """
        print(f"Benchmarking single text embedding ({len(text)} chars)...")
        print(f"  Warmup runs: {warmup_runs}")
        print(f"  Benchmark runs: {benchmark_runs}")

        # Warmup
        for _ in range(warmup_runs):
            self.get_embedding(text)

        # Benchmark
        times = []
        memory_before = psutil.virtual_memory().used

        if self.cuda_available:
            import torch

            torch.cuda.reset_peak_memory_stats()
            gpu_memory_before = torch.cuda.memory_allocated()

        for _ in range(benchmark_runs):
            start = time.perf_counter()
            self.get_embedding(text)
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

    def benchmark_batch_embedding(
        self,
        texts: List[str],
        batch_size: int = 8,
        warmup_runs: int = 2,
        benchmark_runs: int = 5,
    ) -> Dict[str, Any]:
        """
        Benchmark batch embedding processing.

        Returns:
            Dict with timing stats
        """
        print(
            f"\nBenchmarking batch embedding ({len(texts)} texts, batch_size={batch_size})..."
        )
        print(f"  Warmup runs: {warmup_runs}")
        print(f"  Benchmark runs: {benchmark_runs}")

        # Warmup
        for _ in range(warmup_runs):
            for text in texts[:batch_size]:
                self.get_embedding(text)

        # Benchmark
        times = []
        total_texts = batch_size * benchmark_runs

        for _ in range(benchmark_runs):
            start = time.perf_counter()
            for text in texts[:batch_size]:
                self.get_embedding(text)
            end = time.perf_counter()
            times.append((end - start) * 1000)

        # Calculate stats (per text)
        times_per_text = [t / batch_size for t in times]
        times_sorted = sorted(times_per_text)

        results = {
            "total_texts": total_texts,
            "batch_size": batch_size,
            "mean_ms_per_text": sum(times_per_text) / len(times_per_text),
            "median_ms_per_text": times_sorted[len(times_sorted) // 2],
            "min_ms_per_text": min(times_per_text),
            "max_ms_per_text": max(times_per_text),
            "throughput_texts_per_sec": total_texts / (sum(times) / 1000),
        }

        return results

    def run_full_benchmark(
        self,
        save_results: bool = True,
        output_file: str = "embedding_benchmark_results.json",
    ) -> Dict[str, Any]:
        """
        Run comprehensive benchmark suite.

        Args:
            save_results: Whether to save results to JSON
            output_file: Output file path

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

        # Test texts of varying lengths
        test_cases = [
            {
                "name": "Short (1 sentence)",
                "text": "This is a short sentence for testing embeddings.",
            },
            {
                "name": "Medium (5 sentences)",
                "text": " ".join(
                    [
                        "This is a medium length text for testing.",
                        "It contains multiple sentences to evaluate performance.",
                        "The embedding generation should be efficient.",
                        "We measure latency and throughput metrics.",
                        "This helps us understand the model's capabilities.",
                    ]
                ),
            },
            {
                "name": "Long (paragraph)",
                "text": " ".join(
                    [
                        "This is a longer text passage that represents typical document content.",
                        "When working with document retrieval systems, we often need to generate embeddings",
                        "for paragraphs of this length. The performance characteristics matter for scalability.",
                        "We want to ensure that the embedding generation is fast enough for real-time usage.",
                        "This benchmark helps us understand if the model can handle production workloads.",
                        "The GPU acceleration should provide significant speedup for longer texts.",
                        "Memory usage is also important to monitor for system stability.",
                        "Overall, this gives us a comprehensive view of the model's performance.",
                    ]
                    * 2
                ),
            },
        ]

        # Single embedding benchmarks
        print(f"\n{'=' * 60}")
        print("Single Embedding Benchmarks")
        print(f"{'=' * 60}\n")

        all_results["single_embeddings"] = {}
        for case in test_cases:
            print(f"\n{'─' * 60}")
            print(f"Test Case: {case['name']}")
            print(f"{'─' * 60}")
            results = self.benchmark_single_embedding(case["text"])
            all_results["single_embeddings"][case["name"]] = results

            self._print_single_results(results)

        # Batch embedding benchmarks
        print(f"\n{'=' * 60}")
        print("Batch Embedding Benchmarks")
        print(f"{'=' * 60}\n")

        # Create a batch of texts
        batch_texts = [case["text"] for case in test_cases] * 10  # 30 texts

        batch_sizes = [1, 5, 10, 20]
        all_results["batch_embeddings"] = {}

        for batch_size in batch_sizes:
            if batch_size > len(batch_texts):
                continue

            results = self.benchmark_batch_embedding(
                texts=batch_texts,
                batch_size=batch_size,
            )
            all_results["batch_embeddings"][f"batch_size_{batch_size}"] = results

            self._print_batch_results(results)

        # Save results
        if save_results:
            output_path = Path(output_file)
            with open(output_path, "w") as f:
                json.dump(all_results, f, indent=2)
            print(f"\n{'=' * 60}")
            print(f"[OK] Results saved to: {output_path.absolute()}")
            print(f"{'=' * 60}")

        return all_results

    def _print_single_results(self, results: Dict[str, Any]):
        """Print single embedding results."""
        print(f"\n  Results:")
        print(f"    Mean:     {results['mean_ms']:.2f} ms")
        print(f"    Median:   {results['median_ms']:.2f} ms")
        print(f"    Min:      {results['min_ms']:.2f} ms")
        print(f"    Max:      {results['max_ms']:.2f} ms")
        print(f"    P95:      {results['p95_ms']:.2f} ms")
        print(f"    P99:      {results['p99_ms']:.2f} ms")
        print(f"    Throughput: {results['throughput_per_sec']:.2f} texts/sec")
        print(f"    Memory:   {results['memory_used_mb']:.1f} MB")
        if results["gpu_memory_peak_mb"] > 0:
            print(
                f"    GPU Memory: {results['gpu_memory_used_mb']:.1f} MB (peak: {results['gpu_memory_peak_mb']:.1f} MB)"
            )

    def _print_batch_results(self, results: Dict[str, Any]):
        """Print batch embedding results."""
        print(f"\n  Results (batch_size={results['batch_size']}):")
        print(f"    Mean:     {results['mean_ms_per_text']:.2f} ms/text")
        print(f"    Median:   {results['median_ms_per_text']:.2f} ms/text")
        print(f"    Min:      {results['min_ms_per_text']:.2f} ms/text")
        print(f"    Max:      {results['max_ms_per_text']:.2f} ms/text")
        print(f"    Throughput: {results['throughput_texts_per_sec']:.2f} texts/sec")


def main():
    """Main benchmark entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Benchmark llama-cpp-python embedding performance"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="embedding-gemma-300M-Q8_0.gguf",
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
        default="embedding_benchmark_results.json",
        help="Output file for results",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick benchmark (fewer runs)",
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
        benchmark = EmbeddingBenchmark(
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
    print("█" + "  EMBEDDING PERFORMANCE BENCHMARK".center(58) + "█")
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

        # Get the medium text results for summary
        medium_results = results["single_embeddings"]["Medium (5 sentences)"]
        print(f"\nModel: {results['model_info']['filename']}")
        print(f"Size: {results['model_info']['size_mb']:.1f} MB")
        print(
            f"\nGPU Acceleration: {'Enabled' if results['system_info']['cuda_available'] else 'Disabled'}"
        )
        if results["system_info"]["cuda_available"]:
            print(f"GPU: {results['system_info']['gpu_name']}")
            print(f"GPU Layers: {results['system_info']['gpu_layers']}")
        print(f"\nMedium Text Performance:")
        print(f"  Latency: {medium_results['median_ms']:.2f} ms (median)")
        print(f"  Throughput: {medium_results['throughput_per_sec']:.2f} texts/sec")
        print(f"\n[OK] Benchmark complete!")

    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user.")
    except Exception as e:
        print(f"\nError during benchmark: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
