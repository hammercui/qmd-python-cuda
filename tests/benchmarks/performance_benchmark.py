"""性能基准测试脚本"""
import subprocess
import time
import requests
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

server_url = "http://127.0.0.1:18765"

print("=" * 70)
print("QMD-Python 性能基准测试")
print("=" * 70)

# ============================================================================
# Test 1: 索引性能
# ============================================================================
print("\n[Test 1] 索引性能测试")
print("-" * 70)

todo_dir = "D:\\syncthing\\obsidian-mark\\8.TODO"

print(f"索引目录: {todo_dir}")
start = time.time()
result = subprocess.run(
    ['.venv/Scripts/qmd.exe', 'index', todo_dir],
    capture_output=True,
    text=True,
    timeout=120
)
index_time = time.time() - start

print(f"索引时间: {index_time:.2f}秒")
print(f"输出: {result.stdout[:200]}")
if result.stderr:
    print(f"错误: {result.stderr[:200]}")

# ============================================================================
# Test 2: 统计信息
# ============================================================================
print("\n[Test 2] 统计信息")
print("-" * 70)

result = subprocess.run(
    ['.venv/Scripts/qmd.exe', 'status'],
    capture_output=True,
    text=True,
    timeout=10
)
print(result.stdout)

# ============================================================================
# Test 3: 全文搜索性能（BM25）
# ============================================================================
print("\n[Test 3] 全文搜索性能（BM25）")
print("-" * 70)

queries = [
    "EchoSync",
    "OpenCode",
    "Zandar",
    "Boss",
    "python"
]

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
    print(f"  Query: '{query}' -> {elapsed:.2f}ms")

print(f"\n  平均延迟: {statistics.mean(search_times):.2f}ms")
print(f"  最小延迟: {min(search_times):.2f}ms")
print(f"  最大延迟: {max(search_times):.2f}ms")
print(f"  中位数: {statistics.median(search_times):.2f}ms")

# ============================================================================
# Test 4: 向量搜索性能（需要Server）
# ============================================================================
print("\n[Test 4] 向量搜索性能（需要Server）")
print("-" * 70)

client = requests.Session()
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
            print(f"  Query: '{query}' -> {elapsed:.2f}ms ({result_count} results)")
        else:
            print(f"  Query: '{query}' -> Error {resp.status_code}")
    except Exception as e:
        print(f"  Query: '{query}' -> Exception: {e}")

if vsearch_times:
    print(f"\n  平均延迟: {statistics.mean(vsearch_times):.2f}ms")
    print(f"  最小延迟: {min(vsearch_times):.2f}ms")
    print(f"  最大延迟: {max(vsearch_times):.2f}ms")
    print(f"  中位数: {statistics.median(vsearch_times):.2f}ms")

# ============================================================================
# Test 5: 混合搜索性能
# ============================================================================
print("\n[Test 5] 混合搜索性能（需要Server）")
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
            print(f"  Query: '{query}' -> {elapsed:.2f}ms ({result_count} results)")
        else:
            print(f"  Query: '{query}' -> Error {resp.status_code}")
    except Exception as e:
        print(f"  Query: '{query}' -> Exception: {e}")

if query_times:
    print(f"\n  平均延迟: {statistics.mean(query_times):.2f}ms")
    print(f"  最小延迟: {min(query_times):.2f}ms")
    print(f"  最大延迟: {max(query_times):.2f}ms")
    print(f"  中位数: {statistics.median(query_times):.2f}ms")

# ============================================================================
# Test 6: 并发测试（验证队列串行）
# ============================================================================
print("\n[Test 6] 并发测试（10个并发请求）")
print("-" * 70)

def make_request(query):
    """单次请求"""
    start = time.time()
    try:
        resp = client.post(f"{server_url}/query", json={
            'query': query,
            'top_k': 5
        }, timeout=30)
        elapsed = (time.time() - start) * 1000
        return elapsed, resp.status_code
    except Exception as e:
        return -1, str(e)

concurrent_queries = ["测试"] * 10
start = time.time()

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(make_request, q) for q in concurrent_queries]
    results = [f.result() for f in as_completed(futures)]

total_time = (time.time() - start) * 1000
success_count = sum(1 for t, code in results if t > 0 and code == 200)

print(f"总时间: {total_time:.2f}ms")
print(f"成功请求: {success_count}/10")
print(f"平均每请求: {total_time / 10:.2f}ms")

if results:
    times = [t for t, code in results if t > 0]
    if times:
        print(f"请求时间分布:")
        print(f"  最小: {min(times):.2f}ms")
        print(f"  最大: {max(times):.2f}ms")
        print(f"  平均: {statistics.mean(times):.2f}ms")
        print(f"  中位数: {statistics.median(times):.2f}ms")

# ============================================================================
# Test 7: Server健康检查
# ============================================================================
print("\n[Test 7] Server状态")
print("-" * 70)

try:
    resp = client.get(f"{server_url}/health", timeout=5)
    health = resp.json()
    print(f"状态: {health.get('status')}")
    print(f"模型加载: {health.get('model_loaded')}")
    print(f"队列大小: {health.get('queue_size')}")
except Exception as e:
    print(f"无法获取Server状态: {e}")

print("\n" + "=" * 70)
print("性能测试完成！")
print("=" * 70)
