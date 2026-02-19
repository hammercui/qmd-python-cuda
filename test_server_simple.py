"""
QMD Server Performance Test - Simplified

使用 Python subprocess 启动服务器，运行测试，然后停止服务器。
"""

import subprocess
import time
import requests
import json
import sys

# Test configuration
PORT = 18765
BASE_URL = f"http://localhost:{PORT}"
QUERIES = [
    "How to use async await in Python?",
    "What is machine learning?",
    "Explain database indexing",
    "FastAPI vs Flask comparison",
    "GPU acceleration techniques",
]


def start_server():
    """Start QMD server in background."""
    print(f"\n{'=' * 60}")
    print(f"Starting QMD Server on port {PORT}...")
    print(f"{'=' * 60}\n")

    # Start server process
    server = subprocess.Popen(
        ["qmd", "server", "--port", str(PORT), "--log-level", "info"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    # Wait for server to be ready
    print("Waiting for server to initialize...", end="", flush=True)
    for i in range(60):  # Wait up to 60 seconds
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=2)
            if response.status_code == 200:
                print(" [OK]")
                print(f"Server is healthy and ready")
                return server
        except:
            pass
        print(".", end="", flush=True)
        time.sleep(1)

    print("\n[ERROR] Server failed to start")
    server.kill()
    raise RuntimeError("Server startup timeout")


def test_search(server):
    """Test search functionality."""
    print(f"\n{'=' * 60}")
    print(f"Testing Search Functionality")
    print(f"{'=' * 60}\n")

    results = []

    for i, query in enumerate(QUERIES, 1):
        try:
            start = time.time()
            response = requests.post(
                f"{BASE_URL}/query",
                json={"query": query, "collection": "todo", "limit": 5},
                timeout=30,
            )
            elapsed = time.time() - start

            if response.status_code == 200:
                data = response.json()
                result_count = len(data.get("results", []))

                results.append(
                    {
                        "query": query,
                        "latency_ms": elapsed * 1000,
                        "result_count": result_count,
                        "success": True,
                    }
                )

                status = "[OK]" if result_count > 0 else "[EMPTY]"
                print(
                    f"[Query {i}/{len(QUERIES)}] {status} {query[:50]}... ({elapsed * 1000:.1f}ms, {result_count} results)"
                )
            else:
                results.append(
                    {
                        "query": query,
                        "latency_ms": elapsed * 1000,
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                    }
                )
                print(
                    f"[Query {i}/{len(QUERIES)}] [FAIL] {query[:50]}... ({response.status_code})"
                )

        except Exception as e:
            results.append(
                {
                    "query": query,
                    "success": False,
                    "error": str(e),
                }
            )
            print(f"[Query {i}/{len(QUERIES)}] [ERROR] {query[:50]}... - {e}")

    return results


def print_summary(results):
    """Print test summary."""
    print(f"\n{'=' * 60}")
    print(f"TEST SUMMARY")
    print(f"{'=' * 60}")

    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    print(f"\nTotal Queries: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    print(f"Success Rate: {len(successful) / len(results) * 100:.1f}%")

    if successful:
        latencies = [r["latency_ms"] for r in successful]
        print(f"\nLatency Statistics:")
        print(f"  Average: {sum(latencies) / len(latencies):.2f} ms")
        print(f"  Min: {min(latencies):.2f} ms")
        print(f"  Max: {max(latencies):.2f} ms")
        print(f"  Median: {sorted(latencies)[len(latencies) // 2]:.2f} ms")

    print("\n" + "=" * 60)


def main():
    """Main entry point."""
    server = None

    try:
        # Start server
        server = start_server()

        # Give server extra time to fully initialize models
        print("\nWaiting 3 seconds for models to fully initialize...")
        time.sleep(3)

        # Run tests
        results = test_search(server)

        # Print summary
        print_summary(results)

        print("\n[OK] Test completed successfully!")

        return 0

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    finally:
        # Stop server
        if server:
            print("\nStopping server...", end="", flush=True)
            server.terminate()
            try:
                server.wait(timeout=10)
                print(" [OK]")
            except subprocess.TimeoutExpired:
                server.kill()
                print(" [KILLED]")


if __name__ == "__main__":
    sys.exit(main())
