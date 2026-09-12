#!/usr/bin/env python3
import fcntl, json, os, sqlite3, struct, sys, time, urllib.request
DB = "/home/jesse/wisdom-scaffold/data/optiplex_index.db"
LOCK = "/home/jesse/wisdom-scaffold/data/embed_overnight.lock"
URL = "http://127.0.0.1:11434/api/embeddings"
JUNK = ("/logs/", "/stamps/", "/git-fleet", "/__pycache__/", "/.git/", "/.venv/", "/node_modules/")

def junk(p):
    s = (p or "").lower()
    return any(x in s for x in JUNK)

def ollama():
    try:
        names = [m.get("name", "") for m in json.loads(
            urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3).read()
        ).get("models", [])]
        return any("nomic" in n for n in names)
    except Exception as e:
        print("nomic dark", e, flush=True)
        return False

def embed(text):
    req = urllib.request.Request(
        URL,
        data=json.dumps({"model": "nomic-embed-text", "prompt": (text or "")[:2000]}).encode(),
        headers={"Content-Type": "application/json"},
    )
    vec = json.loads(urllib.request.urlopen(req, timeout=60).read().decode()).get("embedding")
    if not vec:
        return None
    return struct.pack("<%df" % len(vec), *[float(x) for x in vec])

def main():
    lockf = open(LOCK, "w")
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another embed job holds the lock", flush=True)
        return 3
    if not ollama():
        return 2
    con = sqlite3.connect(DB)
    rows = con.execute(
        """SELECT c.id, c.file_path, c.chunk_text
           FROM file_chunks c
           LEFT JOIN file_chunk_embeddings e ON e.chunk_id = c.id
           WHERE e.chunk_id IS NULL"""
    ).fetchall()
    todo = [(i, p, t) for i, p, t in rows if not junk(p)]
    have = con.execute("SELECT COUNT(*) FROM file_chunk_embeddings").fetchone()[0]
    print("have", have, "holes_raw", len(rows), "will_embed", len(todo), flush=True)
    t0 = time.time()
    done = fail = 0
    for cid, path, text in todo:
        try:
            blob = embed(text)
        except Exception as e:
            fail += 1
            print("err", fail, e, flush=True)
            if fail > 20:
                print("too many errors, stop", flush=True)
                break
            time.sleep(2)
            continue
        if not blob:
            fail += 1
            continue
        con.execute(
            "INSERT OR REPLACE INTO file_chunk_embeddings(chunk_id, embedding) VALUES (?,?)",
            (cid, blob),
        )
        done += 1
        if done % 25 == 0:
            con.commit()
            dt = max(time.time() - t0, 0.001)
            left = len(todo) - done
            eta = left / (done / dt)
            print(
                "embedded", done, "/", len(todo),
                "per_s", round(done / dt, 2),
                "eta_h", round(eta / 3600, 2),
                flush=True,
            )
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM file_chunk_embeddings").fetchone()[0]
    print("wrote", done, "fail", fail, "embeddings_now", n, "hours", round((time.time()-t0)/3600, 2), flush=True)
    con.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
