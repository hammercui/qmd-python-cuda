import sqlite3

conn = sqlite3.connect('C:/Users/Administrator/.qmd/qmd.db')
cursor = conn.cursor()

# 查看documents表结构
cursor.execute("PRAGMA table_info(documents)")
columns = cursor.fetchall()

print("Documents表结构:")
for col in columns:
    print(f"  {col[1]:20} {col[2]:15}")

print("\n检查embedding字段...")
cursor.execute("SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL")
count = cursor.fetchone()[0]
print(f"有嵌入向量的文档: {count}")

print("\n示例文档...")
cursor.execute("SELECT path, title, length(content) as content_len FROM documents LIMIT 5")
rows = cursor.fetchall()
for row in rows:
    print(f"  路径: {row[0]}")
    print(f"    标题: {row[1]}")
    print(f"    内容长度: {row[2]}")

conn.close()
