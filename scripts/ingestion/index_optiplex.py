cat << 'EOF' > index_optiplex.py
import os
import sys
import sqlite3
import numpy as np
from nomic import embed

# Permaculture Rule: Fair Share & Modular Partitioning
PUBLIC_DB = "/home/jesse/optiplex_public.db"
PRIVATE_DB = "/home/jesse/optiplex_private.db"

# Folders containing private data (keys, raw backups, sensitive bridges)
PRIVATE_PATTERNS = ["agape-crossover-key", "backup_a15_termux", ".aider", "kai_export"]

SEARCH_PATHS = [
    "/tmp/openroot-mesh",
    "/home/jesse/repo_audit_workspace",
    "/home/jesse/github",
    "/home/jesse/src",
    "/home/jesse/github-mirror"
]

def init_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT,
            repo_name TEXT,
            chunk_index INTEGER,
            content TEXT
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunk_embeddings (
            chunk_id INTEGER PRIMARY KEY,
            embedding BLOB,
            FOREIGN KEY(chunk_id) REFERENCES file_chunks(id)
        );
    """)
    conn.commit()
    conn.close()

def is_private_path(path):
    return any(pattern in path for pattern in PRIVATE_PATTERNS)

def chunk_text(text, chunk_size=1000, overlap=150):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def process_file(file_path):
    if not file_path.endswith(('.md', '.py', '.json', '.txt', '.sh', '.rs', '.c', '.cpp')):
        return []
    
    # Exclude heavy binaries or lock files
    if "node_modules" in file_path or ".git" in file_path:
        return []

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        if len(content.strip()) < 20:
            return []
        return chunk_text(content)
    except Exception:
        return []

def run_indexing():
    init_db(PUBLIC_DB)
    init_db(PRIVATE_DB)

    print("--> Scanning target directories on OptiPlex...")
    for root_dir in SEARCH_PATHS:
        if not os.path.exists(root_dir):
            continue

        for dirpath, _, filenames in os.walk(root_dir):
            for fname in filenames:
                full_path = os.path.join(dirpath, fname)
                chunks = process_file(full_path)
                
                if not chunks:
                    continue

                # Partitioning based on Privacy Ethics
                target_db = PRIVATE_DB if is_private_path(full_path) else PUBLIC_DB
                repo_name = dirpath.split(os.sep)[-1]

                conn = sqlite3.connect(target_db)
                cursor = conn.cursor()

                for i, chunk in enumerate(chunks):
                    cursor.execute(
                        "INSERT INTO file_chunks (file_path, repo_name, chunk_index, content) VALUES (?, ?, ?, ?);",
                        (full_path, repo_name, i, chunk)
                    )
                    chunk_id = cursor.lastrowid

                    # Embed using Nomic (search_document mode for index storage)
                    try:
                        res = embed.text(
                            texts=[chunk],
                            model="nomic-embed-text-v1.5",
                            task_type="search_document"
                        )
                        vec = np.array(res['embeddings'][0], dtype=np.float32)
                        blob = vec.tobytes()

                        cursor.execute(
                            "INSERT INTO chunk_embeddings (chunk_id, embedding) VALUES (?, ?);",
                            (chunk_id, blob)
                        )
                    except Exception as e:
                        print(f"[!] Embedding error on {full_path}: {e}")
                
                conn.commit()
                conn.close()
                print(f"[✓] Indexed: {full_path} -> {os.path.basename(target_db)}")

if __name__ == "__main__":
    run_indexing()
EOF

python3 index_optiplex.py

