import sqlite3

conn = sqlite3.connect('C:/Users/Administrator/.qmd/qmd.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]

print("数据库表:")
for table in tables:
    print(f"  - {table}")

if 'embeddings' in tables:
    cursor.execute("SELECT COUNT(*) FROM embeddings")
    count = cursor.fetchone()[0]
    print(f"\n嵌入向量数: {count}")
else:
    print("\n没有 embeddings 表")

conn.close()
