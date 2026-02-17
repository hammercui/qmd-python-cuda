#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QMD 核心功能测试（不需要 Server）
"""

import sys
import time
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

CONCURRENT_REQUESTS = 10

# ===================== 测试函数 =====================

def test_embedding():
    """测试 Embedding 功能"""
    print("\n" + "=" * 70)
    print("测试 1: Embedding 功能")
    print("=" * 70)

    try:
        # 强制使用 standalone 模式（6GB VRAM 足够）
        engine = LLMEngine(mode="standalone")

        # 测试单个查询
        print("\n1.1 单个查询 embedding...")
        start = time.time()
        embedding = engine.embed_query("测试查询")
        elapsed = time.time() - start

        print(f"  向量维度: {len(embedding)}")
        print(f"  耗时: {elapsed:.3f}s")

        # 测试批量文档
        print("\n1.2 批量文档 embedding (100个)...")
        docs = [f"文档{i} 关于机器学习和深度学习" for i in range(100)]
        start = time.time()
        embeddings = engine.embed_texts(docs)
        elapsed = time.time() - start

        print(f"  处理数量: {len(embeddings)}")
        print(f"  耗时: {elapsed:.3f}s")
        print(f"  速度: {len(docs) / elapsed:.1f} docs/s")
        print(f"  平均延迟: {elapsed / len(docs) * 1000:.1f} ms/doc")

        # 测试更大规模
        print("\n1.3 大规模 embedding (1000个)...")
        docs = [f"文档{i} 关于人工智能和神经网络" for i in range(1000)]
        start = time.time()
        embeddings = engine.embed_texts(docs)
        elapsed = time.time() - start

        print(f"  处理数量: {len(embeddings)}")
        print(f"  耗时: {elapsed:.3f}s")
        print(f"  速度: {len(docs) / elapsed:.1f} docs/s")

        return True, None

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e)

def test_reranker():
    """测试 Reranker 功能"""
    print("\n" + "=" * 70)
    print("测试 2: Reranker 功能")
    print("=" * 70)

    try:
        reranker = LLMReranker()

        query = "什么是机器学习"
        documents = [
            {"title": "机器学习简介", "content": "机器学习是人工智能的一个分支，专注于算法和统计模型。"},
            {"title": "深度学习基础", "content": "深度学习使用多层神经网络进行特征提取和模式识别。"},
            {"title": "Python 编程", "content": "Python 是一种高级编程语言，广泛用于 Web 开发。"},
            {"title": "AI 发展史", "content": "人工智能自 1950 年代以来发展迅速，取得了许多突破。"},
            {"title": "数据挖掘技术", "content": "数据挖掘是从大量数据中发现潜在模式和知识的过程。"},
            {"title": "自然语言处理", "content": "NLP 是 AI 的重要分支，处理人类语言。"},
            {"title": "计算机视觉", "content": "计算机视觉让机器能够识别和理解图像。"},
            {"title": "强化学习", "content": "强化学习通过奖励机制训练智能体。"},
        ]

        print(f"\n查询: {query}")
        print(f"文档数: {len(documents)}")

        # 测试重排序
        print("\n2.1 重排序测试...")
        start = time.time()
        reranked = reranker.rerank(query, documents, top_k=5)
        elapsed = time.time() - start

        print(f"  耗时: {elapsed:.3f}s")
        print(f"  速度: {len(documents) / elapsed:.1f} docs/s")

        print("\n重排序结果:")
        for i, doc in enumerate(reranked, 1):
            score = doc.get('rerank_score', 0)
            title = doc.get('title', 'N/A')
            content = doc.get('content', '')[:40] + "..."
            print(f"  {i}. [{score:.4f}] {title}")
            print(f"     {content}")

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
        import traceback
        traceback.print_exc()
        return False, str(e)

def test_performance():
    """测试性能"""
    print("\n" + "=" * 70)
    print("测试 3: 性能测试（不同规模）")
    print("=" * 70)

    try:
        engine = LLMEngine(mode='standalone')
        reranker = LLMReranker()

        test_sizes = [10, 50, 100, 500, 1000]

        print(f"\n{'文档数':<10} {'Embedding':<15} {'Rerank(10)':<15} {'总时间':<15} {'Embed速度'}")
        print("-" * 85)

        for size in test_sizes:
            # Embedding
            docs = [f"文档{i}" for i in range(size)]
            start = time.time()
            embeddings = engine.embed_texts(docs)
            embed_time = time.time() - start

            # Reranking
            documents = [{"content": f"文档{i}"} for i in range(min(10, size))]
            start = time.time()
            reranked = reranker.rerank("测试查询", documents, top_k=5)
            rerank_time = time.time() - start

            total_time = embed_time + rerank_time
            embed_speed = size / embed_time if embed_time > 0 else 0

            print(f"{size:<10} {embed_time:<15.3f} {rerank_time:<15.3f} {total_time:<15.3f} {embed_speed:<10.1f} d/s")

        return True, None

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e)

def test_concurrent():
    """测试并发性能"""
    print("\n" + "=" * 70)
    print("测试 4: 并发压力测试")
    print("=" * 70)

    try:
        engine = LLMEngine(mode='standalone')
        reranker = LLMReranker()

        print(f"\n并发配置:")
        print(f"  并发数: {CONCURRENT_REQUESTS}")
        print(f"  每请求数: 50 个文档")

        def single_request(worker_id: int) -> Dict[str, Any]:
            """单个请求"""
            try:
                start = time.time()

                # Embedding 50 个文档
                docs = [f"Worker {worker_id} - 文档{i} 关于机器学习" for i in range(50)]
                embeddings = engine.embed_texts(docs)

                # Reranking 10 个文档
                documents = [{"content": doc} for doc in docs[:10]]
                reranked = reranker.rerank(f"什么是机器学习", documents, top_k=5)

                elapsed = time.time() - start

                return {
                    "worker_id": worker_id,
                    "success": True,
                    "time": elapsed,
                    "docs_processed": len(docs)
                }
            except Exception as e:
                import traceback
                return {
                    "worker_id": worker_id,
                    "success": False,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }

        # 并发执行
        print(f"\n执行 {CONCURRENT_REQUESTS} 个并发请求...")
        start_total = time.time()

        with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as executor:
            futures = [executor.submit(single_request, i) for i in range(CONCURRENT_REQUESTS)]
            results = [f.result() for f in as_completed(futures)]

        total_time = time.time() - start_total

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

        # 总处理量
        total_docs = sum(r.get('docs_processed', 0) for r in results if r['success'])
        print(f"  总文档数: {total_docs}")
        print(f"  文档速度: {total_docs / total_time:.1f} docs/s")

        if fail_count > 0:
            print(f"\n失败请求详情:")
            for r in results:
                if not r['success']:
                    print(f"  Worker {r['worker_id']}: {r.get('error', 'Unknown')}")

        return True, None

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e)

def test_memory():
    """测试内存和显存占用"""
    print("\n" + "=" * 70)
    print("测试 5: 内存和显存占用")
    print("=" * 70)

    try:
        import torch
        import psutil
        import os

        process = psutil.Process(os.getpid())

        # 初始内存
        print("\n5.1 初始状态...")
        initial_mem = process.memory_info().rss / 1024 / 1024
        print(f"  RAM: {initial_mem:.1f} MB")

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
            print(f"  GPU 显存: {torch.cuda.memory_allocated(0) / 1024 / 1024:.1f} MB")

        # 加载模型
        print("\n5.2 加载模型...")
        load_start = time.time()
        engine = LLMEngine(mode='standalone')
        reranker = LLMReranker()
        load_time = time.time() - load_start

        loaded_mem = process.memory_info().rss / 1024 / 1024
        print(f"  加载耗时: {load_time:.3f}s")
        print(f"  RAM: {loaded_mem:.1f} MB (+{loaded_mem - initial_mem:.1f} MB)")

        if torch.cuda.is_available():
            gpu_mem = torch.cuda.memory_allocated(0) / 1024 / 1024
            print(f"  GPU 显存: {gpu_mem:.1f} MB")

        # 运行推理
        print("\n5.3 运行推理 (100个文档)...")
        docs = [f"文档{i} 关于机器学习和深度学习" for i in range(100)]
        start = time.time()
        embeddings = engine.embed_texts(docs)
        inference_time = time.time() - start

        inference_mem = process.memory_info().rss / 1024 / 1024
        print(f"  推理耗时: {inference_time:.3f}s")
        print(f"  速度: {len(docs) / inference_time:.1f} docs/s")
        print(f"  RAM: {inference_mem:.1f} MB (+{inference_mem - loaded_mem:.1f} MB)")

        if torch.cuda.is_available():
            gpu_mem = torch.cuda.memory_allocated(0) / 1024 / 1024
            gpu_peak = torch.cuda.max_memory_allocated(0) / 1024 / 1024
            print(f"  GPU 显存: {gpu_mem:.1f} MB")
            print(f"  GPU 峰值: {gpu_peak:.1f} MB")

        # 运行 Reranker
        print("\n5.4 运行 Reranker (10个文档)...")
        documents = [{"content": doc} for doc in docs[:10]]
        query = "什么是机器学习"
        start = time.time()
        reranked = reranker.rerank(query, documents, top_k=5)
        rerank_time = time.time() - start

        rerank_mem = process.memory_info().rss / 1024 / 1024
        print(f"  推理耗时: {rerank_time:.3f}s")
        print(f"  RAM: {rerank_mem:.1f} MB (+{rerank_mem - inference_mem:.1f} MB)")

        if torch.cuda.is_available():
            gpu_mem = torch.cuda.memory_allocated(0) / 1024 / 1024
            gpu_peak = torch.cuda.max_memory_allocated(0) / 1024 / 1024
            print(f"  GPU 显存: {gpu_mem:.1f} MB")
            print(f"  GPU 峰值: {gpu_peak:.1f} MB")

        return True, None

    except ImportError as e:
        print(f"\n需要安装依赖: {e}")
        print("  pip install psutil")
        return False, str(e)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e)

def test_accuracy():
    """测试准确性"""
    print("\n" + "=" * 70)
    print("测试 6: 准确性测试（语义相似度）")
    print("=" * 70)

    try:
        engine = LLMEngine(mode='standalone')

        # 测试用例：查询和相关/不相关文档
        query = "机器学习算法"

        documents = [
            ("机器学习基础教程", "机器学习是人工智能的核心技术，包括监督学习和无监督学习。", 0.95),
            ("深度学习入门", "深度学习使用神经网络模拟人脑的工作原理。", 0.70),
            ("Python 编程指南", "Python 是一种简洁的编程语言，适合初学者。", 0.30),
            ("烹饪技巧大全", "如何制作美味的意大利面和牛排。", 0.10),
        ]

        print(f"\n查询: {query}")
        print(f"文档数: {len(documents)}")

        # 生成 embeddings
        query_embedding = engine.embed_query(query)
        doc_embeddings = engine.embed_texts([doc[1] for doc in documents])

        # 计算相似度
        import numpy as np
        similarities = []
        for i, (title, content, expected) in enumerate(documents):
            similarity = float(np.dot(query_embedding, doc_embeddings[i]))
            similarities.append((title, similarity, expected))

        # 排序
        similarities.sort(key=lambda x: x[1], reverse=True)

        print("\n相似度排序结果:")
        print(f"{'排名':<6} {'标题':<20} {'相似度':<10} {'预期':<10} {'状态'}")
        print("-" * 70)

        correct = 0
        for i, (title, similarity, expected) in enumerate(similarities):
            # 判断是否正确（相似度排序应该和预期一致）
            status = "✓" if (i < 2 and similarity > 0.5) or (i >= 2 and similarity <= 0.5) else "✗"
            if status == "✓":
                correct += 1

            print(f"{i+1:<6} {title:<20} {similarity:<10.4f} {expected:<10.4f} {status}")

        print("-" * 70)
        print(f"准确率: {correct}/{len(documents)} ({correct/len(documents)*100:.1f}%)")

        return True, None

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e)

# ===================== 主函数 =====================

def main():
    """主测试函数"""
    print("\n" + "=" * 70)
    print("QMD 核心功能完整测试")
    print("=" * 70)

    # 检查硬件
    try:
        import torch
        if torch.cuda.is_available():
            print(f"\n硬件配置:")
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
            print(f"  显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
            print(f"  CUDA: {torch.version.cuda}")
        else:
            print(f"\n  GPU: 不可用 (使用 CPU)")
    except ImportError:
        print(f"\n  GPU: 未知")

    # 运行测试
    tests = [
        ("Embedding", test_embedding),
        ("Reranker", test_reranker),
        ("性能测试", test_performance),
        ("并发压力", test_concurrent),
        ("内存占用", test_memory),
        ("准确性", test_accuracy),
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

            # 测试之间的间隔
            time.sleep(1)

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

    print(f"\n{'测试名称':<15} {'结果':<10} {'备注'}")
    print("-" * 70)

    success_count = 0
    for r in results:
        status = "✅ PASS" if r['success'] else "❌ FAIL"
        note = r.get('error', '')[:30] if r.get('error') else ''
        print(f"{r['name']:<15} {status:<10} {note}")
        if r['success']:
            success_count += 1

    print("-" * 70)
    print(f"总计: {success_count}/{len(results)} 通过")

    if success_count == len(results):
        print("\n✅ 所有测试通过！QMD 核心功能正常。")
        return 0
    else:
        print(f"\n❌ {len(results) - success_count} 个测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())
