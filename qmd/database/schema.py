SCHEMA = """
-- Collections配置
CREATE TABLE IF NOT EXISTS collections (
    name TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    glob_pattern TEXT NOT NULL,
    created_at TEXT,
    last_modified TEXT
);

-- 文档元数据
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection TEXT NOT NULL,
    path TEXT NOT NULL,
    hash TEXT NOT NULL,
    title TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    modified_at TEXT NOT NULL,
    UNIQUE(collection, path),
    FOREIGN KEY (hash) REFERENCES content(hash) ON DELETE CASCADE
);

-- 文档内容（hash去重）
CREATE TABLE IF NOT EXISTS content (
    hash TEXT PRIMARY KEY,
    doc TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 向量元数据（chunk 级）
CREATE TABLE IF NOT EXISTS content_vectors (
    hash TEXT NOT NULL,
    seq INTEGER NOT NULL DEFAULT 0,
    pos INTEGER NOT NULL DEFAULT 0,
    model TEXT NOT NULL,
    embedded_at TEXT NOT NULL,
    PRIMARY KEY (hash, seq),
    FOREIGN KEY (hash) REFERENCES content(hash) ON DELETE CASCADE
);

-- 路径上下文（层级）
CREATE TABLE IF NOT EXISTS path_contexts (
    collection TEXT,
    path TEXT,
    context TEXT,
    PRIMARY KEY (collection, path)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_documents_collection ON documents(collection, active);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(hash);
CREATE INDEX IF NOT EXISTS idx_documents_path ON documents(path, active);
"""

# FTS5 virtual table
FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    filepath,
    title,
    body,
    tokenize='porter unicode61'
);
"""

# Triggers to keep FTS in sync
# Note: always DROP before CREATE to ensure the latest definition is applied
# (CREATE TRIGGER IF NOT EXISTS won't update an already-existing trigger)
TRIGGERS = """
DROP TRIGGER IF EXISTS documents_ai;
DROP TRIGGER IF EXISTS documents_ad;
DROP TRIGGER IF EXISTS documents_au;

-- INSERT trigger: only insert when active=1
CREATE TRIGGER documents_ai AFTER INSERT ON documents
WHEN new.active = 1
BEGIN
  INSERT INTO documents_fts(rowid, filepath, title, body)
  SELECT new.id,
         new.collection || '/' || new.path,
         new.title,
         (SELECT doc FROM content WHERE hash = new.hash);
END;

-- DELETE trigger
CREATE TRIGGER documents_ad AFTER DELETE ON documents BEGIN
  DELETE FROM documents_fts WHERE rowid = old.id;
END;

-- UPDATE trigger: always remove old FTS entry first, then re-insert if still active.
-- FTS5 does NOT reliably support INSERT OR REPLACE for existing rowids;
-- the DELETE + INSERT pattern is the safe alternative.
CREATE TRIGGER documents_au AFTER UPDATE ON documents
BEGIN
  DELETE FROM documents_fts WHERE rowid = old.id;

  INSERT INTO documents_fts(rowid, filepath, title, body)
  SELECT new.id,
         new.collection || '/' || new.path,
         new.title,
         (SELECT doc FROM content WHERE hash = new.hash)
  WHERE new.active = 1;
END;
"""
