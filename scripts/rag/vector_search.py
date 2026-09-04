#!/usr/bin/env python3
import json, math, sqlite3, struct, sys, urllib.request

DB_PATH = "/home/jesse/wisdom-scaffold/data/optiplex_index.db"
OLLAMA = "http://127.0.0.1:11434/api/embeddings"
MODEL = "nomic-embed-text"

def embed(text, task="search_query"):
    req = urllib.request.Request(
        OLLAMA,
        data=json.dumps({"model": MODEL, "prompt": f"{task}: {text}"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())["embedding"]

def cosine(a, b):
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    return dot / math.sqrt(na * nb) if na and nb else -1.0

def search(query, top_k=10):
    q = embed(query, "search_query")
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    hits = []
    for name, blob, payload in con.execute(
        "SELECT repo_name, embedding, text_payload FROM nomic_embeddings"
    ):
        v = struct.unpack("<768f", blob[:3072])
        hits.append((cosine(q, v), name, (payload or "")[:80]))
    hits.sort(reverse=True)
    print(f"Query: {query}\n" + "=" * 50)
    for score, name, payload in hits[:top_k]:
        print(f"[{score:.4f}] {name}\n    {payload}")

if __name__ == "__main__":
    search(sys.argv[1] if len(sys.argv) > 1 else "openroot wisdom nomic mesh")
