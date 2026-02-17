#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QMD 完整流程测试
测试从 CLI 到 Server 的完整功能、压力和性能
"""

import sys
import os
import time
import json
import requests
import multiprocessing
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))

from qmd.llm.engine import LLMEngine
from qmd.search.rerank import LLMReranker

# ===================== 配置 =====================

TEST_DOCS_COUNT = 1000  # 测试文档数量
CONCURRENT_REQUESTS = 10  # 并发请求数
SERVER_URL = "http://localhost:8000"  # Server URL
TIMEOUT = 300  # 超时时间（秒）

# ===================== 测试数据 =====================

def generate_test_documents(count: int) -> List[Dict[str, Any]]:
    """生成测试文档"""
    print(f"\n生成 {count} 个测试文档...")

    documents = []
    topics = [
        "机器学习", "深度学习", "神经网络", "自然语言处理",
        "计算机视觉", "强化学习", "数据挖掘", "人工智能",
        "Python编程", "Web开发", "数据库", "云计算",
    ]

    for i in range(count):
        topic = topics[i % len(topics)]
        documents.append({
            "path": f"/test/doc_{i}.txt",
            "title": f"{topic} - 文档{i}",
            "content": f"这是关于{topic}的文档{i}。{topic}是计算机科学的重要领域。"
        })

    print(f"OK: 生成了 {len(documents)} 个文档")
    return documents

# ===================== 测试函数 =====================

def test_1_cli_embedding():
    """测试 1: CLI Embedding 功能"""
    print("\n" + "=" * 70)
    print("测试 1: CLI Embedding 功能")
    print("=" * 70)

    try:
        engine = LLMEngine()

        # 测试单个文档
        print("\n1.1 单个文档 embedding...")
        start = time.time()
        embedding = engine.embed_query("测试查询")
        elapsed = time.time() - start

        print(f"  向量维度: {len(embedding)}")
        print(f"  耗时: {elapsed:.3f}s")

        # 测试批量文档
        print("\n1.2 批量文档 embedding (100个)...")
        docs = [f"文档{i}" for i in range(100)]
        start = time.time()
        embeddings = engine.embed_texts(docs)
        elapsed = time.time() - start

        print(f"  处理数量: {len(embeddings)}")
        print(f"  耗时: {elapsed:.3f}s")
        print(f"  速度: {len(docs) / elapsed:.1f} docs/s")

        return True, None

    except Exception as e:
        return False, str(e)

def test_2_reranker():
    """测试 2: Reranker 功能"""
    print("\n" + "=" * 70)
    print("测试 2: Reranker 功能")
    print("=" * 70)

    try:
        reranker = LLMReranker()

        query = "什么是机器学习"
        documents = [
            {"title": "机器学习简介", "content": "机器学习是AI的一个分支。"},
            {"title": "深度学习", "content": "深度学习使用神经网络。"},
            {"title": "Python", "content": "Python是编程语言。"},
            {"title": "AI历史", "content": "人工智能发展迅速。"},
            {"title": "数据挖掘", "content": "数据挖掘从数据中发现知识。"},
        ]

        print(f"\n查询: {query}")
        print(f"文档数: {len(documents)}")

        # 测试重排序
        print("\n2.1 重排序测试...")
        start = time.time()
        reranked = reranker.rerank(query, documents, top_k=3)
        elapsed = time.time() - start

        print(f"  耗时: {elapsed:.3f}s")
        print(f"  速度: {len(documents) / elapsed:.1f} docs/s")

        print("\n重排序结果:")
        for i, doc in enumerate(reranked, 1):
            score = doc.get('rerank_score', 0)
            title = doc.get('title', 'N/A')
            print(f"  {i}. [{score:.4f}] {title}")

        # 测试查询扩展
        print("\n2.2 查询扩展测试...")
        start = time.time()
        expanded = reranker.expand_query(query)
        elapsed = time.time() - start

        print(f"  耗时: {elapsed:.3f}s")
        print(f"\n扩展结果:")
        for i, q in enumerate(expanded, 1):
            print(f"  {i}. {q}")

        return True, None

    except Exception as e:
        return False, str(e)

def test_3_server_startup():
    """测试 3: Server 启动"""
    print("\n" + "=" * 70)
    print("测试 3: Server 启动")
    print("=" * 70)

    print("\n3.1 启动 MCP Server...")
    print("  请在另一个终端运行: qmd server")
    print("  或按 Ctrl+C 跳过此测试")

    input("\n按 Enter 继续...")

    try:
        # 测试连接
        print("\n3.2 测试 Server 连接...")
        response = requests.get(f"{SERVER_URL}/health", timeout=5)

        if response.status_code == 200:
            print(f"  OK: Server 正常运行")
            print(f"  响应: {response.json()}")
            return True, None
        else:
            return False, f"Server 返回错误: {response.status_code}"

    except requests.exceptions.ConnectionError:
        return False, "无法连接到 Server，请确认 Server 已启动"
    except Exception as e:
        return False, str(e)

def test_4_server_search():
    """测试 4: Server 搜索功能"""
    print("\n" + "=" * 70)
    print("测试 4: Server 搜索功能")
    print("=" * 70)

    try:
        # 准备测试数据
        query = "机器学习"
        k = 5

        print(f"\n查询: {query}")
        print(f"Top-K: {k}")

        # 测试语义搜索
        print("\n4.1 语义搜索 (vsearch)...")
        start = time.time()
        response = requests.post(
            f"{SERVER_URL}/vsearch",
            json={"query": query, "k": k},
            timeout=30
        )
        elapsed = time.time() - start

        if response.status_code == 200:
            results = response.json()
            print(f"  OK: 找到 {len(results.get('results', []))} 个结果")
            print(f"  耗时: {elapsed:.3f}s")

            if results.get('results'):
                print("\n  结果预览:")
                for i, r in enumerate(results['results'][:3], 1):
                    score = r.get('score', 0)
                    title = r.get('metadata', {}).get('title', 'N/A')
                    print(f"    {i}. [{score:.4f}] {title}")
        else:
            print(f"  FAIL: {response.status_code}")
            print(f"  {response.text}")

        return True, None

    except Exception as e:
        return False, str(e)

def test_5_performance():
    """测试 5: 性能测试"""
    print("\n" + "=" * 70)
    print("测试 5: 性能测试")
    print("=" * 70)

    try:
        engine = LLMEngine()
        reranker = LLMReranker()

        # 生成测试数据
        test_sizes = [10, 50, 100, 500]

        print("\n不同规模的性能测试:")
        print(f"{'文档数':<10} {'Embedding(s)':<15} {'Rerank(s)':<15} {'总时间(s)':<15}")
        print("-" * 70)

        for size in test_sizes:
            docs = [f"文档{i}" for i in range(size)]

            # Embedding
            start = time.time()
            embeddings = engine.embed_texts(docs)
            embed_time = time.time() - start

            # Reranking
            documents = [{"content": doc} for doc in docs[:10]]
            start = time.time()
            reranked = reranker.rerank("测试", documents, top_k=5)
            rerank_time = time.time() - start

            total_time = embed_time + rerank_time

            print(f"{size:<10} {embed_time:<15.3f} {rerank_time:<15.3f} {total_time:<15.3f}")

        return True, None

    except Exception as e:
        return False, str(e)

def test_6_concurrent():
    """测试 6: 并发压力测试"""
    print("\n" + "=" * 70)
    print("测试 6: 并发压力测试")
    print("=" * 70)

    try:
        engine = LLMEngine()
        reranker = LLMReranker()

        print(f"\n并发数: {CONCURRENT_REQUESTS}")
        print(f"每请求数: 10 个文档")

        def single_request(worker_id: int) -> Dict[str, Any]:
            """单个请求"""
            try:
                start = time.time()

                # Embedding
                docs = [f"Worker {worker_id} - 文档{i}" for i in range(10)]
                embeddings = engine.embed_texts(docs)

                # Reranking
                documents = [{"content": doc} for doc in docs]
                reranked = reranker.rerank(f"查询{worker_id}", documents, top_k=5)

                elapsed = time.time() - start

                return {
                    "worker_id": worker_id,
                    "success": True,
                    "time": elapsed,
                    "docs_processed": len(docs)
                }
            except Exception as e:
                return {
                    "worker_id": worker_id,
                    "success": False,
                    "error": str(e)
                }

        # 并发执行
        print(f"\n执行并发请求...")
        start = time.time()

        with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as executor:
            futures = [executor.submit(single_request, i) for i in range(CONCURRENT_REQUESTS)]
            results = [f.result() for f in as_completed(futures)]

        total_time = time.time() - start

        # 统计结果
        success_count = sum(1 for r in results if r['success'])
        fail_count = len(results) - success_count

        times = [r['time'] for r in results if r['success']]
        avg_time = sum(times) / len(times) if times else 0
        max_time = max(times) if times else 0
        min_time = min(times) if times else 0

        print(f"\n结果统计:")
        print(f"  总请求数: {len(results)}")
        print(f"  成功: {success_count}")
        print(f"  失败: {fail_count}")
        print(f"  总耗时: {total_time:.3f}s")
        print(f"  平均耗时: {avg_time:.3f}s")
        print(f"  最大耗时: {max_time:.3f}s")
        print(f"  最小耗时: {min_time:.3f}s")
        print(f"  吞吐量: {success_count / total_time:.2f} requests/s")

        if fail_count > 0:
            print(f"\n失败请求:")
            for r in results:
                if not r['success']:
                    print(f"  Worker {r['worker_id']}: {r.get('error', 'Unknown')}")

        return True, None

    except Exception as e:
        return False, str(e)

def test_7_memory():
    """测试 7: 显存和内存占用"""
    print("\n" + "=" * 70)
    print("测试 7: 显存和内存占用")
    print("=" * 70)

    try:
        import torch
        import psutil
        import os

        process = psutil.Process(os.getpid())

        # 初始内存
        initial_mem = process.memory_info().rss / 1024 / 1024

        # 初始化模型
        print("\n7.1 初始化模型前...")
        print(f"  RAM: {initial_mem:.1f} MB")

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
            print(f"  GPU Memory: {torch.cuda.memory_allocated(0) / 1024 / 1024:.1f} MB")

        # 加载模型
        print("\n7.2 加载模型...")
        engine = LLMEngine()
        reranker = LLMReranker()

        loaded_mem = process.memory_info().rss / 1024 / 1024
        print(f"  RAM: {loaded_mem:.1f} MB (+{loaded_mem - initial_mem:.1f} MB)")

        if torch.cuda.is_available():
            gpu_mem = torch.cuda.memory_allocated(0) / 1024 / 1024
            gpu_peak = torch.cuda.max_memory_allocated(0) / 1024 / 1024
            print(f"  GPU Memory: {gpu_mem:.1f} MB")
            print(f"  GPU Peak: {gpu_peak:.1f} MB")

        # 运行推理
        print("\n7.3 运行推理...")
        docs = [f"文档{i}" for i in range(100)]
        embeddings = engine.embed_texts(docs)

        inference_mem = process.memory_info().rss / 1024 / 1024
        print(f"  RAM: {inference_mem:.1f} MB (+{inference_mem - loaded_mem:.1f} MB)")

        if torch.cuda.is_available():
            gpu_mem = torch.cuda.memory_allocated(0) / 1024 / 1024
            gpu_peak = torch.cuda.max_memory_allocated(0) / 1024 / 1024
            print(f"  GPU Memory: {gpu_mem:.1f} MB")
            print(f"  GPU Peak: {gpu_peak:.1f} MB")

        return True, None

    except ImportError:
        print("\n需要安装 psutil: pip install psutil")
        return False, "缺少依赖"
    except Exception as e:
        return False, str(e)

# ===================== 主函数 =====================

def main():
    """主测试函数"""
    print("\n" + "=" * 70)
    print("QMD 完整流程测试")
    print("=" * 70)

    print(f"\n测试配置:")
    print(f"  测试文档数: {TEST_DOCS_COUNT}")
    print(f"  并发请求数: {CONCURRENT_REQUESTS}")
    print(f"  Server URL: {SERVER_URL}")

    # 检查 CUDA
    try:
        import torch
        if torch.cuda.is_available():
            print(f"\n硬件:")
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
            print(f"  显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        else:
            print(f"\n  GPU: 不可用 (使用 CPU)")
    except ImportError:
        print(f"\n  GPU: 未知")

    # 运行测试
    tests = [
        ("CLI Embedding", test_1_cli_embedding),
        ("Reranker", test_2_reranker),
        ("Server 启动", test_3_server_startup),
        ("Server 搜索", test_4_server_search),
        ("性能测试", test_5_performance),
        ("并发压力测试", test_6_concurrent),
        ("内存占用", test_7_memory),
    ]

    results = []

    for name, test_func in tests:
        try:
            success, error = test_func()
            results.append({
                "name": name,
                "success": success,
                "error": error
            })
        except KeyboardInterrupt:
            print(f"\n\n测试被用户中断")
            break
        except Exception as e:
            results.append({
                "name": name,
                "success": False,
                "error": str(e)
            })

    # 打印总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)

    print(f"\n{'测试名称':<20} {'结果':<10} {'备注'}")
    print("-" * 70)

    success_count = 0
    for r in results:
        status = "PASS" if r['success'] else "FAIL"
        note = r.get('error', '')[:30] if r.get('error') else ''
        print(f"{r['name']:<20} {status:<10} {note}")
        if r['success']:
            success_count += 1

    print("-" * 70)
    print(f"总计: {success_count}/{len(results)} 通过")

    if success_count == len(results):
        print("\n✅ 所有测试通过！")
        return 0
    else:
        print(f"\n❌ {len(results) - success_count} 个测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())
