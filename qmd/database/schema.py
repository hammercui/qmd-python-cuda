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
TRIGGERS = """
-- INSERT trigger: only insert when active=1
CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents
WHEN new.active = 1
BEGIN
  INSERT INTO documents_fts(rowid, filepath, title, body)
  SELECT new.id,
         new.collection || '/' || new.path,
         new.title,
         (SELECT doc FROM content WHERE hash = new.hash)
  WHERE new.active = 1;
END;

-- DELETE trigger
CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
  DELETE FROM documents_fts WHERE rowid = old.id;
END;

-- UPDATE trigger: handle active changes
CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents
BEGIN
  -- Deactivated: remove from FTS
  DELETE FROM documents_fts WHERE rowid = old.id AND new.active = 0;
  
  -- Activated or updated: insert/replace in FTS
  INSERT OR REPLACE INTO documents_fts(rowid, filepath, title, body)
  SELECT new.id,
         new.collection || '/' || new.path,
         new.title,
         (SELECT doc FROM content WHERE hash = new.hash)
  WHERE new.active = 1;
END;
"""
