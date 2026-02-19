import sqlite3

DB_PATH = "C:/Users/Administrator/.qmd/qmd.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

print("=== documents table ===")
r = conn.execute("SELECT count(*) as total, COALESCE(sum(active),0) as active FROM documents").fetchone()
print(f"total={r['total']}, active={r['active']}, inactive={r['total'] - r['active']}")

print()
print("=== content table ===")
r = conn.execute("SELECT count(*) as total FROM content").fetchone()
print(f"total content rows={r['total']}")

print()
print("=== content_vectors table ===")
r = conn.execute("SELECT count(DISTINCT hash) as total FROM content_vectors").fetchone()
print(f"distinct hashes with embeddings={r['total']}")

print()
print("=== orphaned content (no active document references) ===")
r = conn.execute("""
    SELECT count(*) as total FROM content c
    WHERE NOT EXISTS (
        SELECT 1 FROM documents d WHERE d.hash = c.hash AND d.active = 1
    )
""").fetchone()
print(f"content rows with no active document={r['total']}")

print()
print("=== sample documents (first 5, any active status) ===")
rows = conn.execute("SELECT id, collection, path, active, hash FROM documents LIMIT 5").fetchall()
if rows:
    for row in rows:
        print(f"  id={row['id']}, active={row['active']}, col={row['collection']}, path={row['path'][:60]}")
else:
    print("  (no rows)")

conn.close()
