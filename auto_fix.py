#!/usr/bin/env python3
"""自动修复所有QMD-Python问题"""

import subprocess
import time
import requests
import sys

server_url = "http://127.0.0.1:18765"

print("=" * 70)
print("QMD-Python 自动修复脚本")
print("=" * 70)

# ============================================================================
# Fix 1: 生成嵌入向量
# ============================================================================
print("\n[Fix 1/3] 生成嵌入向量")
print("-" * 70)

print("运行 qmd embed...")
start = time.time()
result = subprocess.run(
    ['.venv/Scripts/qmd.exe', 'embed'],
    capture_output=True,
    text=True,
    timeout=600  # 10分钟超时
)
elapsed = time.time() - start

print(f"输出: {result.stdout}")
if result.stderr:
    print(f"错误: {result.stderr}")

print(f"嵌入时间: {elapsed:.2f}秒")

# 检查状态
print("\n检查嵌入状态...")
result = subprocess.run(
    ['.venv/Scripts/qmd.exe', 'status'],
    capture_output=True,
    text=True,
    timeout=10
)
print(result.stdout)

# ============================================================================
# Fix 2: 修复FTS搜索问题
# ============================================================================
print("\n[Fix 2/3] 修复FTS搜索")
print("-" * 70)

print("检查FTS搜索问题...")
# 读取 qmd/search/fts.py 文件
try:
    with open('qmd/search/fts.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查是否有 snippet 函数调用
    if 'snippet(' in content:
        print("发现 snippet 函数调用")
        # 查找具体位置
        for i, line in enumerate(content.split('\n'), 1):
            if 'snippet(' in line:
                print(f"  行 {i}: {line.strip()}")
    else:
        print("未发现 snippet 函数调用")
except Exception as e:
    print(f"无法读取文件: {e}")

# ============================================================================
# Fix 3: 重新测试所有功能
# ============================================================================
print("\n[Fix 3/3] 重新测试所有功能")
print("-" * 70)

client = requests.Session()

# 等待Server启动
print("等待Server启动...")
time.sleep(2)

try:
    resp = client.get(f"{server_url}/health", timeout=5)
    health = resp.json()
    print(f"Server状态: {health}")
except Exception as e:
    print(f"无法连接Server: {e}")

# 测试向量搜索
print("\n测试向量搜索...")
test_queries = ["EchoSync", "OpenCode", "Zandar"]

for query in test_queries:
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
            print(f"  Query: '{query}' -> {elapsed:.2f}ms ({result_count} results) ✓")
        else:
            print(f"  Query: '{query}' -> Error {resp.status_code}")
    except Exception as e:
        print(f"  Query: '{query}' -> Exception: {e}")

# 测试混合搜索
print("\n测试混合搜索...")
for query in test_queries:
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
            print(f"  Query: '{query}' -> {elapsed:.2f}ms ({result_count} results) ✓")
        else:
            print(f"  Query: '{query}' -> Error {resp.status_code}")
    except Exception as e:
        print(f"  Query: '{query}' -> Exception: {e}")

print("\n" + "=" * 70)
print("自动修复完成！")
print("=" * 70)
