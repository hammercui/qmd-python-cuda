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
    title TEXT,
    context TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT,
    modified_at TEXT,
    UNIQUE(collection, path)
);

-- 文档内容（hash去重）
CREATE TABLE IF NOT EXISTS content (
    hash TEXT PRIMARY KEY,
    doc TEXT NOT NULL,
    embedding BLOB
);

-- 路径上下文（层级）
CREATE TABLE IF NOT EXISTS path_contexts (
    collection TEXT,
    path TEXT,
    context TEXT,
    PRIMARY KEY (collection, path)
);
"""

# FTS5 virtual table
FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
    title,
    context,
    content,
    tokenize='unicode61'
);
"""

# Triggers to keep FTS in sync
TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
  INSERT INTO documents_fts(rowid, title, context, content)
  SELECT new.id, new.title, new.context, c.doc
  FROM content c WHERE c.hash = new.hash;
END;

CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
  DELETE FROM documents_fts WHERE rowid = old.id;
END;

CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
  DELETE FROM documents_fts WHERE rowid = old.id;
  
  INSERT INTO documents_fts(rowid, title, context, content)
  SELECT new.id, new.title, new.context, c.doc
  FROM content c WHERE c.hash = new.hash;
END;
"""
