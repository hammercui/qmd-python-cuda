"""完整功能测试（修复后）"""
import subprocess
import time
import requests
import statistics

server_url = "http://127.0.0.1:18765"
client = requests.Session()

print("=" * 70)
print("QMD-Python 完整功能测试（修复后）")
print("=" * 70)

# 等待Server
time.sleep(1)

# ============================================================================
# Test 1: 状态检查
# ============================================================================
print("\n[Test 1] 状态检查")
print("-" * 70)

result = subprocess.run(
    ['.venv/Scripts/qmd.exe', 'status'],
    capture_output=True,
    text=True,
    timeout=10
)
print(result.stdout)

# ============================================================================
# Test 2: FTS搜索
# ============================================================================
print("\n[Test 2] FTS搜索（BM25）")
print("-" * 70)

queries = ["EchoSync", "OpenCode", "Zandar", "Boss", "python"]
search_times = []

for query in queries:
    start = time.time()
    result = subprocess.run(
        ['.venv/Scripts/qmd.exe', 'search', query],
        capture_output=True,
        text=True,
        timeout=30
    )
    elapsed = (time.time() - start) * 1000
    search_times.append(elapsed)

    # 提取结果数
    lines = result.stdout.strip().split('\n')
    result_count = 0
    for line in lines:
        if ' → ' in line:
            result_count += 1

    status = "OK" if "FTS search error" not in result.stderr else "ERROR"
    print(f"  Query: '{query:12}' -> {elapsed:6.2f}ms ({result_count:2} results) [{status}]")

if search_times:
    print(f"\n  平均: {statistics.mean(search_times):.2f}ms")
    print(f"  最小: {min(search_times):.2f}ms")
    print(f"  最大: {max(search_times):.2f}ms")

# ============================================================================
# Test 3: Server健康
# ============================================================================
print("\n[Test 3] Server健康")
print("-" * 70)

try:
    resp = client.get(f"{server_url}/health", timeout=5)
    health = resp.json()
    print(f"  状态: {health.get('status')}")
    print(f"  模型: {health.get('model_loaded')}")
    print(f"  队列: {health.get('queue_size')}")
    print("  Result: OK")
except Exception as e:
    print(f"  Error: {e}")

# ============================================================================
# Test 4: 向量搜索
# ============================================================================
print("\n[Test 4] 向量搜索")
print("-" * 70)

vsearch_times = []

for query in queries:
    try:
        start = time.time()
        resp = client.post(f"{server_url}/vsearch", json={
            'query': query,
            'top_k': 5
        }, timeout=30)
        elapsed = (time.time() - start) * 1000

        if resp.status_code == 200:
            data = resp.json()
            result_count = len(data.get('results', []))
            vsearch_times.append(elapsed)
            print(f"  Query: '{query:12}' -> {elapsed:6.2f}ms ({result_count:2} results) [OK]")
        else:
            print(f"  Query: '{query:12}' -> Error {resp.status_code}")
    except Exception as e:
        print(f"  Query: '{query:12}' -> Exception: {str(e)[:40]}")

if vsearch_times:
    print(f"\n  平均: {statistics.mean(vsearch_times):.2f}ms")
    print(f"  最小: {min(vsearch_times):.2f}ms")
    print(f"  最大: {max(vsearch_times):.2f}ms")

# ============================================================================
# Test 5: 混合搜索
# ============================================================================
print("\n[Test 5] 混合搜索")
print("-" * 70)

query_times = []

for query in queries:
    try:
        start = time.time()
        resp = client.post(f"{server_url}/query", json={
            'query': query,
            'top_k': 5
        }, timeout=30)
        elapsed = (time.time() - start) * 1000

        if resp.status_code == 200:
            data = resp.json()
            result_count = len(data.get('results', []))
            query_times.append(elapsed)
            print(f"  Query: '{query:12}' -> {elapsed:6.2f}ms ({result_count:2} results) [OK]")
        else:
            print(f"  Query: '{query:12}' -> Error {resp.status_code}")
    except Exception as e:
        print(f"  Query: '{query:12}' -> Exception: {str(e)[:40]}")

if query_times:
    print(f"\n  平均: {statistics.mean(query_times):.2f}ms")
    print(f"  最小: {min(query_times):.2f}ms")
    print(f"  最大: {max(query_times):.2f}ms")

# ============================================================================
# Test 6: 并发测试
# ============================================================================
print("\n[Test 6] 并发测试（5个并发）")
print("-" * 70)

import threading

def make_request(query, results, index):
    start = time.time()
    try:
        resp = client.post(f"{server_url}/query", json={
            'query': query,
            'top_k': 5
        }, timeout=30)
        elapsed = (time.time() - start) * 1000
        results[index] = (elapsed, resp.status_code)
    except Exception as e:
        results[index] = (-1, str(e))

concurrent_queries = ["测试"] * 5
results = [None] * 5
threads = []

start = time.time()
for i in range(5):
    t = threading.Thread(target=make_request, args=(concurrent_queries[i], results, i))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

total_time = (time.time() - start) * 1000
success_count = sum(1 for t, code in results if t > 0 and code == 200)

print(f"  总时间: {total_time:.2f}ms")
print(f"  成功: {success_count}/5")

if success_count > 0:
    times = [t for t, code in results if t > 0]
    print(f"  平均每请求: {total_time / 5:.2f}ms")
    print(f"  最小: {min(times):.2f}ms")
    print(f"  最大: {max(times):.2f}ms")

print("\n" + "=" * 70)
print("测试完成！")
print("=" * 70)
