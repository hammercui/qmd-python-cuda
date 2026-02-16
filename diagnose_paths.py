"""诊断路径问题"""
from pathlib import Path
import sqlite3

print("=" * 70)
print("路径问题诊断")
print("=" * 70)

# 1. 检查数据库路径
db_path = Path.home() / ".qmd" / "qmd.db"
print(f"\n[1] 数据库路径")
print(f"  路径: {db_path}")
print(f"  存在: {db_path.exists()}")

# 2. 连接数据库并查看文档路径
print(f"\n[2] 文档路径检查")
try:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 查询文档表
    cursor.execute("SELECT path FROM documents LIMIT 5")
    rows = cursor.fetchall()

    print(f"  文档路径示例:")
    for row in rows:
        path = row[0]
        print(f"    {path}")
        # 检查路径是否存在
        exists = Path(path).exists()
        print(f"      存在: {exists}")

    conn.close()
except Exception as e:
    print(f"  错误: {e}")

# 3. 检查向量存储路径
print(f"\n[3] 向量存储路径")
vector_dir = Path.home() / ".qmd" / "vectors"
print(f"  路径: {vector_dir}")
print(f"  存在: {vector_dir.exists()}")

if vector_dir.exists():
    files = list(vector_dir.rglob("*"))
    print(f"  文件数: {len(files)}")
    for f in files[:5]:
        print(f"    {f.relative_to(vector_dir)}")

# 4. 检查嵌入向量
print(f"\n[4] 嵌入向量检查")
try:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM embeddings")
    count = cursor.fetchone()[0]
    print(f"  嵌入向量数: {count}")

    cursor.execute("SELECT path FROM embeddings LIMIT 3")
    rows = cursor.fetchall()
    print(f"  嵌入路径示例:")
    for row in rows:
        print(f"    {row[0]}")

    conn.close()
except Exception as e:
    print(f"  错误: {e}")

print("\n" + "=" * 70)
