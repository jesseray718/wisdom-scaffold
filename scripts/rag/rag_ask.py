#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3, sys, time, urllib.request
from pathlib import Path
DB = "/home/jesse/wisdom-scaffold/data/optiplex_index.db"
BASE = "http://127.0.0.1:8080/v1"
MODEL = "qwen2.5-coder-7b"
PROTOCOL = "/home/jesse/openroot/kit/sidekick/CODER_PROTOCOL.txt"
SYS = ("You are the OpenRoot 7B coder on the OptiPlex spoke. "
       "eta = useful_joules / human_joules. Use ONLY the FTS context. "
       "Cite file paths. If missing say NOT IN INDEX. Do not invent measurements. "
       "N14: heat-engine eta, act eta, EROI, sim score are four quantities. Absolute paths.")

def fts(query, k):
    tokens = [t for t in query.replace('"', " ").replace("'", " ").replace(".", " ").split() if t]
    if not tokens:
        return []
    and_q, or_q = " ".join(tokens), " OR ".join(tokens)
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    sql = ("SELECT c.file_path, c.chunk_index, c.chunk_text, bm25(chunks_fts) "
           "FROM chunks_fts JOIN file_chunks c ON c.id = chunks_fts.rowid "
           "WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?")
    try:
        rows = con.execute(sql, (and_q, k)).fetchall()
        if len(rows) < 3:
            rows = con.execute(sql, (or_q, k)).fetchall()
    except sqlite3.DatabaseError as e:
        print("fts_error", e); return []
    finally:
        con.close()
    return rows

def pack(rows):
    out, used = [], 0
    for path, idx, text, rank in rows:
        snip = " ".join((text or "").split())[:400]
        block = "[%s #%s bm25=%.3f]\n%s\n" % (path, idx, rank, snip)
        if used + len(block) > 3500:
            break
        out.append(block); used += len(block)
    return "\n".join(out)

def models():
    try:
        obj = json.loads(urllib.request.urlopen(BASE + "/models", timeout=3).read().decode())
        return [m.get("id") or m.get("name") for m in obj.get("data", obj.get("models", []))]
    except Exception as e:
        return ["DOWN %s" % e]

def extract(obj):
    ch = (obj.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    return (msg.get("content") or ch.get("text") or "").strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="+")
    ap.add_argument("--k", type=int, default=6)
    ap.add_argument("--max-tokens", type=int, default=400)
    args = ap.parse_args()
    query = " ".join(args.query)
    t0 = time.perf_counter()
    rows = fts(query, args.k)
    print("fts_s", round(time.perf_counter()-t0, 4), "hits", len(rows))
    if not rows:
        print("NOT IN INDEX"); return 1
    for path, idx, text, rank in rows:
        print("HIT", round(rank, 3), "%s#%s" % (path, idx))
    alive = models()
    print("coder", alive)
    if str(alive[0]).startswith("DOWN"):
        print("FAIL 7B dark on 127.0.0.1:8080"); return 2
    proto = Path(PROTOCOL).read_text(encoding="utf-8", errors="ignore")[:800] if Path(PROTOCOL).is_file() else ""
    system = SYS + (("\nPROTOCOL\n"+proto) if proto else "")
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": "QUESTION:\n%s\n\nCONTEXT:\n%s" % (query, pack(rows))},
        ],
        "temperature": 0.2,
        "max_tokens": args.max_tokens,
    }
    t1 = time.perf_counter()
    req = urllib.request.Request(BASE+"/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        obj = json.loads(urllib.request.urlopen(req, timeout=180).read().decode())
    except Exception as e:
        print("coder_error", e); return 3
    print("llm_s", round(time.perf_counter()-t1, 3), "total_s", round(time.perf_counter()-t0, 3))
    print("==== ANSWER ====")
    print(extract(obj))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
