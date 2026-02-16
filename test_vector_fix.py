"""测试向量搜索修复"""
import sys
sys.path.insert(0, 'D:/MoneyProjects/qmd-python')

from qmd.search.vector import VectorSearch
from qmd.llm.engine import LLMEngine

print("=" * 70)
print("测试向量搜索修复")
print("=" * 70)

try:
    print("\n[1] 初始化VectorSearch...")
    # 使用正确的参数
    llm = LLMEngine(mode="standalone")
    vsearch = VectorSearch(
        db_dir=".qmd_vector_db",
        mode="standalone"
    )
    print("  OK")

    print("\n[2] 测试搜索...")
    results = vsearch.search("EchoSync", collection_name="todo", limit=5)
    print(f"  结果数: {len(results)}")

    if results:
        print(f"\n  前3个结果:")
        for i, r in enumerate(results[:3], 1):
            print(f"    {i}. {r.path}")
            print(f"       Score: {r.score:.4f}")
            print(f"       Collection: {r.collection}")
    else:
        print("  无结果（可能需要先添加文档到ChromaDB）")

    print("\n[Result] VectorSearch工作正常")

except Exception as e:
    print(f"\n[Error] {e}")
    import traceback
    traceback.print_exc()
