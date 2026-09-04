#!/usr/bin/env python3
import json, sqlite3, urllib.request, sys

fails = []

def hit(url, timeout=3):
    try:
        return urllib.request.urlopen(url, timeout=timeout).read()
    except Exception as e:
        fails.append(f"{url} {e}")
        return b""

health = hit("http://127.0.0.1:8080/health")
print("coder_health", health.decode()[:80])
tags = hit("http://127.0.0.1:11434/api/tags")
names = []
if tags:
    names = [m["name"] for m in json.loads(tags).get("models", [])]
print("ollama", [n for n in names if "nomic" in n or "coder" in n])
if "nomic-embed-text:latest" not in names:
    fails.append("nomic missing")

db = "/home/jesse/wisdom-scaffold/data/optiplex_index.db"
try:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    n = con.execute("SELECT COUNT(*) FROM nomic_embeddings").fetchone()[0]
    dim = con.execute("SELECT length(embedding) FROM nomic_embeddings LIMIT 1").fetchone()[0] // 4
    chunks = con.execute("SELECT COUNT(*) FROM file_chunks").fetchone()[0]
    vecs = con.execute("SELECT COUNT(*) FROM file_chunk_embeddings").fetchone()[0]
    print("nomic_embeddings", n, "dim", dim, "chunks", chunks, "chunk_vecs", vecs)
    if n != 42 or dim != 768:
        fails.append(f"index shape {n}x{dim}")
except Exception as e:
    fails.append(f"db {e}")

print("FAIL" if fails else "PASS")
for f in fails:
    print(" -", f)
sys.exit(1 if fails else 0)
