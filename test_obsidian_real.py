#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obsidian TODO 真实场景测试
使用真实的 Obsidian 文档进行完整测试
"""

import sys
import time
import json
from pathlib import Path
from typing import List, Dict, Any

# Windows 控制台兼容性
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))

from qmd.llm.engine import LLMEngine
from qmd.search.rerank import LLMReranker

# ===================== 配置 =====================

OBSIDIAN_TODO_PATH = Path(r"D:\syncthing\obsidian-mark\8.TODO")
TEST_QUERIES = [
    "机器学习算法",
    "EchoSync 项目进度",
    "OpenCode 安装配置",
    "3x-ui 防火墙配置",
    "日常规划管理",
]

# ===================== 工具函数 =====================

def load_markdown_files(root_dir: Path) -> List[Dict[str, Any]]:
    """加载所有 Markdown 文件"""
    print(f"\n扫描目录: {root_dir}")

    documents = []
    md_files = list(root_dir.rglob("*.md")) + list(root_dir.rglob("*.markdown"))

    print(f"找到 {len(md_files)} 个 Markdown 文件")

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding='utf-8', errors='ignore')

            # 提取标题（第一行 # 开头）
            title = md_file.stem
            first_line = content.split('\n')[0]
            if first_line.startswith('#'):
                title = first_line.lstrip('#').strip()

            documents.append({
                "path": str(md_file.relative_to(root_dir)),
                "title": title,
                "content": content[:2000],  # 限制内容长度
                "full_content": content,
            })

        except Exception as e:
            print(f"  跳过 {md_file.name}: {e}")

    print(f"成功加载 {len(documents)} 个文档")
    return documents

# ===================== 测试函数 =====================

def test_real_world_embedding():
    """测试 1: 真实文档 Embedding"""
    print("\n" + "=" * 70)
    print("测试 1: 真实文档 Embedding")
    print("=" * 70)

    try:
        # 加载文档
        documents = load_markdown_files(OBSIDIAN_TODO_PATH)

        if not documents:
            print("\n错误: 没有找到文档")
            return False, "没有文档"

        print(f"\n文档统计:")
        print(f"  总数: {len(documents)}")

        # 计算文档大小分布
        sizes = [len(d['content']) for d in documents]
        print(f"  大小: {min(sizes)} - {max(sizes)} 字符")
        print(f"  平均: {sum(sizes) / len(sizes):.0f} 字符")

        # 初始化 Embedding 引擎
        print(f"\n初始化 Embedding 引擎...")
        engine = LLMEngine(mode='standalone')

        # 测试小批量
        print(f"\n1.1 小批量测试 (10个文档)...")
        test_docs = documents[:10]
        start = time.time()
        embeddings = engine.embed_texts([d['content'] for d in test_docs])
        elapsed = time.time() - start

        print(f"  处理: {len(embeddings)} 个文档")
        print(f"  耗时: {elapsed:.3f}s")
        print(f"  速度: {len(test_docs) / elapsed:.1f} docs/s")
        print(f"  向量维度: {len(embeddings[0])}")

        # 测试大规模（如果文档很多）
        if len(documents) > 50:
            print(f"\n1.2 大规模测试 (前50个文档)...")
            test_docs = documents[:50]
            start = time.time()
            embeddings = engine.embed_texts([d['content'] for d in test_docs])
            elapsed = time.time() - start

            print(f"  处理: {len(embeddings)} 个文档")
            print(f"  耗时: {elapsed:.3f}s")
            print(f"  速度: {len(test_docs) / elapsed:.1f} docs/s")

        return True, None

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e)

def test_real_world_search():
    """测试 2: 真实搜索场景"""
    print("\n" + "=" * 70)
    print("测试 2: 真实搜索场景")
    print("=" * 70)

    try:
        # 加载文档
        documents = load_markdown_files(OBSIDIAN_TODO_PATH)

        # 限制到前 100 个文档（避免太慢）
        if len(documents) > 100:
            print(f"\n文档数量太多，只测试前 100 个")
            documents = documents[:100]

        # 初始化引擎
        print(f"\n初始化引擎...")
        engine = LLMEngine(mode='standalone')
        reranker = LLMReranker()

        # 生成所有 embeddings
        print(f"\n生成 {len(documents)} 个文档的向量...")
        start = time.time()
        doc_embeddings = engine.embed_texts([d['content'] for d in documents])
        embed_time = time.time() - start

        print(f"  完成: {len(doc_embeddings)} 个向量")
        print(f"  耗时: {embed_time:.3f}s")
        print(f"  速度: {len(documents) / embed_time:.1f} docs/s")

        # 测试每个查询
        print(f"\n" + "-" * 70)
        print("搜索测试")
        print("-" * 70)

        import numpy as np

        for query in TEST_QUERIES:
            print(f"\n查询: {query}")

            # 生成查询向量
            start = time.time()
            query_embedding = engine.embed_query(query)
            query_time = time.time() - start

            # 计算相似度
            similarities = np.dot(doc_embeddings, query_embedding)

            # Top-20
            top_indices = np.argsort(similarities)[-20:][::-1]
            top_docs = [documents[i] for i in top_indices]

            print(f"  查询时间: {query_time:.3f}s")
            print(f"  Top-5 结果:")

            for i, (doc_idx, score) in enumerate(zip(top_indices[:5], similarities[top_indices[:5]])):
                title = documents[doc_idx]['title']
                path = documents[doc_idx]['path']
                print(f"    {i+1}. [{score:.4f}] {title}")
                print(f"       {path}")

            # 使用 Reranker 重排序
            print(f"\n  重排序 Top-5...")
            start = time.time()
            reranked = reranker.rerank(
                query,
                [{"title": d['title'], "content": d['content']} for d in top_docs[:10]],
                top_k=5
            )
            rerank_time = time.time() - start

            print(f"  重排序时间: {rerank_time:.3f}s")
            print(f"  重排序结果:")

            for i, doc in enumerate(reranked[:5], 1):
                score = doc.get('rerank_score', 0)
                title = doc.get('title', 'N/A')
                print(f"    {i}. [{score:.4f}] {title}")

            time.sleep(0.5)  # 间隔

        return True, None

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e)

def test_real_world_accuracy():
    """测试 3: 搜索准确性验证"""
    print("\n" + "=" * 70)
    print("测试 3: 搜索准确性验证")
    print("=" * 70)

    try:
        # 加载文档
        documents = load_markdown_files(OBSIDIAN_TODO_PATH)

        if len(documents) > 100:
            documents = documents[:100]

        # 初始化引擎
        engine = LLMEngine(mode='standalone')

        # 生成 embeddings
        print(f"\n生成向量...")
        doc_embeddings = engine.embed_texts([d['content'] for d in documents])

        # 定义测试用例
        test_cases = [
            {
                "query": "EchoSync 项目",
                "expected_keywords": ["EchoSync", "项目", "AI"],
                "min_relevance": 0.5,
            },
            {
                "query": "OpenCode 配置",
                "expected_keywords": ["OpenCode", "配置", "安装"],
                "min_relevance": 0.5,
            },
            {
                "query": "3x-ui 防火墙",
                "expected_keywords": ["3x-ui", "防火墙", "iptables"],
                "min_relevance": 0.5,
            },
        ]

        print(f"\n测试用例数: {len(test_cases)}")
        print("-" * 70)

        import numpy as np

        correct = 0
        for case in test_cases:
            query = case['query']
            print(f"\n查询: {query}")

            # 生成查询向量
            query_embedding = engine.embed_query(query)

            # 计算相似度
            similarities = np.dot(doc_embeddings, query_embedding)
            top_indices = np.argsort(similarities)[-5:][::-1]

            # 检查 Top-3 是否包含预期关键词
            relevant_count = 0
            for i, idx in enumerate(top_indices[:3]):
                doc = documents[idx]
                content_lower = doc['content'].lower()
                title_lower = doc['title'].lower()

                has_keyword = any(
                    kw.lower() in content_lower or kw.lower() in title_lower
                    for kw in case['expected_keywords']
                )

                if has_keyword:
                    relevant_count += 1

            # 判断是否准确
            accuracy = relevant_count / 3
            is_correct = accuracy >= case['min_relevance']

            if is_correct:
                correct += 1
                status = "✅ PASS"
            else:
                status = "❌ FAIL"

            print(f"  相关文档: {relevant_count}/3")
            print(f"  准确率: {accuracy:.1%}")
            print(f"  状态: {status}")

            # 显示 Top-3
            print(f"  Top-3 结果:")
            for i, idx in enumerate(top_indices[:3], 1):
                doc = documents[idx]
                score = similarities[idx]
                title = doc['title'][:40]
                print(f"    {i}. [{score:.4f}] {title}")

        print("-" * 70)
        print(f"\n准确率: {correct}/{len(test_cases)} ({correct/len(test_cases)*100:.0f}%)")

        return True, None

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e)

def test_performance_benchmarks():
    """测试 4: 性能基准"""
    print("\n" + "=" * 70)
    print("测试 4: 性能基准（真实数据）")
    print("=" * 70)

    try:
        # 加载文档
        documents = load_markdown_files(OBSIDIAN_TODO_PATH)

        test_sizes = [10, 50, 100] if len(documents) >= 100 else [10, 20, len(documents)]

        print(f"\n测试规模: {test_sizes}")

        engine = LLMEngine(mode='standalone')
        reranker = LLMReranker()

        print(f"\n{'文档数':<10} {'Embed':<12} {'Query':<12} {'Rerank(10)':<12} {'总时间':<12}")
        print("-" * 70)

        for size in test_sizes:
            test_docs = documents[:size]

            # Embedding
            start = time.time()
            embeddings = engine.embed_texts([d['content'] for d in test_docs])
            embed_time = time.time() - start

            # Query
            start = time.time()
            query_emb = engine.embed_query("测试查询")
            query_time = time.time() - start

            # Reranking
            rerank_docs = [{"title": d['title'], "content": d['content']} for d in test_docs[:10]]
            start = time.time()
            reranked = reranker.rerank("测试查询", rerank_docs, top_k=5)
            rerank_time = time.time() - start

            total_time = embed_time + query_time + rerank_time

            print(f"{size:<10} {embed_time:<12.3f} {query_time:<12.3f} {rerank_time:<12.3f} {total_time:<12.3f}")

        return True, None

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e)

# ===================== 主函数 =====================

def main():
    """主测试函数"""
    print("\n" + "=" * 70)
    print("Obsidian TODO 真实场景测试")
    print("=" * 70)

    print(f"\n测试数据:")
    print(f"  路径: {OBSIDIAN_TODO_PATH}")
    print(f"  查询数: {len(TEST_QUERIES)}")

    if not OBSIDIAN_TODO_PATH.exists():
        print(f"\n错误: 路径不存在")
        return 1

    # 运行测试
    tests = [
        ("Embedding", test_real_world_embedding),
        ("搜索功能", test_real_world_search),
        ("准确性", test_real_world_accuracy),
        ("性能基准", test_performance_benchmarks),
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
        status = "PASS" if r['success'] else "FAIL"
        note = r.get('error', '')[:30] if r.get('error') else ''
        print(f"{r['name']:<15} {status:<10} {note}")
        if r['success']:
            success_count += 1

    print("-" * 70)
    print(f"总计: {success_count}/{len(results)} 通过")

    if success_count == len(results):
        print("\n所有测试通过！QMD 可以用于真实 Obsidian 文档搜索！")
        return 0
    else:
        print(f"\n{len(results) - success_count} 个测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())
