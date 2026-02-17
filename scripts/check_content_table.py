import sqlite3

conn = sqlite3.connect('C:/Users/Administrator/.qmd/qmd.db')
cursor = conn.cursor()

# 查看content表
cursor.execute("SELECT COUNT(*) FROM content")
total = cursor.fetchone()[0]
print(f"Content表总记录: {total}")

# 检查有嵌入向量的记录
cursor.execute("SELECT COUNT(*) FROM content WHERE embedding IS NOT NULL")
embedded = cursor.fetchone()[0]
print(f"有嵌入向量的: {embedded}")

if embedded > 0:
    # 获取一个示例
    cursor.execute("SELECT hash, length(embedding) as emb_size FROM content WHERE embedding IS NOT NULL LIMIT 3")
    rows = cursor.fetchall()
    print(f"\n嵌入向量示例:")
    for row in rows:
        print(f"  Hash: {row[0][:16]}...")
        print(f"  大小: {row[1]} bytes")

conn.close()
