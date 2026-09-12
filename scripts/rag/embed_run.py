#!/usr/bin/env python3
import json, sqlite3, struct, sys, time, urllib.request
DB = "/home/jesse/wisdom-scaffold/data/optiplex_index.db"
URL = "http://127.0.0.1:11434/api/embeddings"
JUNK = ("/logs/", "/stamps/", "/git-fleet", "/__pycache__/", "/.git/", "/.venv/", "/node_modules/")

def junk(p):
    s = (p or "").lower()
    return any(x in s for x in JUNK)

def ollama():
    try:
        names = [m.get("name","") for m in json.loads(
            urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3).read()
        ).get("models", [])]
        return any("nomic" in n for n in names)
    except Exception as e:
        print("nomic dark", e)
        return False

def embed(text):
    req = urllib.request.Request(
        URL,
        data=json.dumps({"model": "nomic-embed-text", "prompt": (text or "")[:2000]}).encode(),
        headers={"Content-Type": "application/json"},
    )
    vec = json.loads(urllib.request.urlopen(req, timeout=30).read().decode()).get("embedding")
    if not vec:
        return None
    return struct.pack("<%df" % len(vec), *[float(x) for x in vec])

def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 512
    if not ollama():
        return 2
    con = sqlite3.connect(DB)
    rows = con.execute(
        """SELECT c.id, c.file_path, c.chunk_text
           FROM file_chunks c
           LEFT JOIN file_chunk_embeddings e ON e.chunk_id = c.id
           WHERE e.chunk_id IS NULL"""
    ).fetchall()
    todo = [(i, p, t) for i, p, t in rows if not junk(p)][:limit]
    print("holes", len(rows), "this_run", len(todo), "cap", limit)
    t0 = time.time()
    done = 0
    for cid, path, text in todo:
        try:
            blob = embed(text)
        except Exception as e:
            print("err", e)
            continue
        if not blob:
            continue
        con.execute(
            "INSERT OR REPLACE INTO file_chunk_embeddings(chunk_id, embedding) VALUES (?,?)",
            (cid, blob),
        )
        done += 1
        if done % 25 == 0:
            con.commit()
            print("embedded", done, "/", len(todo), "per_s", round(done / max(time.time() - t0, 0.001), 2))
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM file_chunk_embeddings").fetchone()[0]
    print("wrote", done, "embeddings_now", n)
    con.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
