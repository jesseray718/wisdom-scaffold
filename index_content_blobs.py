import sqlite3
import json
import urllib.request
import numpy as np
import os

DB_PATH = "/home/jesse/wisdom-scaffold/data/optiplex_index.db"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 1000  # Characters per chunk

print("--> Initializing Schema Migration & Deep Content Indexer...")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. Add content column to file_index if missing
cursor.execute("PRAGMA table_info(file_index);")
file_cols = [col[1] for col in cursor.fetchall()]

if "content" not in file_cols:
    cursor.execute("ALTER TABLE file_index ADD COLUMN content TEXT;")
    print(" [✓] Added 'content' column to file_index")

# 2. Create chunks and chunk embeddings tables
cursor.execute("""
CREATE TABLE IF NOT EXISTS file_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT,
    chunk_index INTEGER,
    chunk_text TEXT
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS file_chunk_embeddings (
    chunk_id INTEGER PRIMARY KEY,
    embedding BLOB,
    FOREIGN KEY(chunk_id) REFERENCES file_chunks(id)
);
""")
conn.commit()

# 3. Read raw file contents from disk where paths exist
cursor.execute("SELECT id, path FROM file_index WHERE path IS NOT NULL;")
files = cursor.fetchall()
print(f" Reading raw text for {len(files)} file index records...")

updated_files = 0
for file_id, rel_path in files:
    # Attempt to locate real file on disk
    possible_paths = [
        rel_path,
        os.path.expanduser(f"~/repo_audit_workspace/{rel_path}"),
        os.path.expanduser(f"~/{rel_path}")
    ]
    
    file_text = None
    for p in possible_paths:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    file_text = f.read()
                break
            except Exception:
                pass

    if file_text:
        cursor.execute("UPDATE file_index SET content = ? WHERE id = ?;", (file_text, file_id))
        
        # Chunk text into overlapping windows
        cursor.execute("SELECT COUNT(*) FROM file_chunks WHERE file_path = ?;", (rel_path,))
        if cursor.fetchone()[0] == 0:
            chunks = [file_text[i:i+CHUNK_SIZE] for i in range(0, len(file_text), CHUNK_SIZE - 200)]
            for idx, chunk in enumerate(chunks):
                cursor.execute(
                    "INSERT INTO file_chunks (file_path, chunk_index, chunk_text) VALUES (?, ?, ?);",
                    (rel_path, idx, chunk)
                )
        updated_files += 1

conn.commit()
print(f" [✓] Ingested raw text and created chunk entries for {updated_files} files.")

# 4. Generate & Store Nomic Embeddings for all text chunks
cursor.execute("""
SELECT c.id, c.chunk_text FROM file_chunks c
LEFT JOIN file_chunk_embeddings e ON c.id = e.chunk_id
WHERE e.chunk_id IS NULL;
""")
unembedded_chunks = cursor.fetchall()

print(f" Generating 768-dim vector embeddings for {len(unembedded_chunks)} text chunks via Ollama...")

embedded_count = 0
for chunk_id, text in unembedded_chunks:
    if not text.strip():
        continue
    try:
        payload = json.dumps({"model": EMBED_MODEL, "prompt": text[:2000]}).encode("utf-8")
        req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            vec = json.loads(resp.read().decode())["embedding"]
            blob = np.array(vec, dtype=np.float32).tobytes()
            cursor.execute("INSERT OR REPLACE INTO file_chunk_embeddings (chunk_id, embedding) VALUES (?, ?);", (chunk_id, blob))
            embedded_count += 1
            if embedded_count % 50 == 0:
                conn.commit()
                print(f"   Indexed {embedded_count}/{len(unembedded_chunks)} chunks...")
    except Exception as e:
        print(f" Error embedding chunk {chunk_id}: {e}")

conn.commit()
conn.close()

print(f"=========================================================")
print(f" SUCCESS: Stored file blobs & generated {embedded_count} chunk embeddings.")
print(f"=========================================================")
