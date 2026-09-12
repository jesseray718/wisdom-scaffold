#!/usr/bin/env python3
from __future__ import annotations
import json, math, os, sqlite3, struct, sys, time, urllib.request
DB = "/home/jesse/wisdom-scaffold/data/optiplex_index.db"
OLLAMA = "http://127.0.0.1:11434/api/embeddings"
CODER = "http://127.0.0.1:8080/v1"
CODER_MODEL = "qwen2.5-coder-7b"
CLOUD_BASE = os.environ.get("OPENROOT_CLOUD_BASE", "https://openrouter.ai/api/v1")
CLOUD_MODEL = os.environ.get("OPENROOT_CLOUD_MODEL", "anthropic/claude-sonnet-4")
CLOUD_KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
def cli_query():
    return " ".join(sys.argv[1:]).strip() or "Helio G99 eta 650 MHz versus 2000 MHz"
def get(url, timeout=3):
    try:
        return urllib.request.urlopen(url, timeout=timeout).read()
    except Exception:
        return b""
def post(url, payload, timeout, headers=None):
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())
def fts(query, k):
    q = query.replace('"', " ").replace("'", " ").replace(".", " ").replace(":", " ")
    tokens = [t for t in q.split() if t]
    if not tokens:
        return []
    and_q, or_q = " ".join(tokens), " OR ".join(tokens)
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    sql = ("SELECT c.id, c.file_path, c.chunk_index, c.chunk_text, bm25(chunks_fts) "
           "FROM chunks_fts JOIN file_chunks c ON c.id = chunks_fts.rowid "
           "WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?")
    try:
        rows = con.execute(sql, (and_q, k)).fetchall()
        if len(rows) < 3:
            rows = con.execute(sql, (or_q, k)).fetchall()
    except sqlite3.DatabaseError as e:
        print("fts_error", e); rows = []
    con.close()
    return rows
def cosine(a, blob):
    n = min(len(a), len(blob)//4)
    if n <= 0:
        return -1.0
    b = struct.unpack("<%df" % n, blob[:n*4])
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x*y; na += x*x; nb += y*y
    return (dot / math.sqrt(na*nb)) if na and nb else -1.0
def nomic_up():
    raw = get("http://127.0.0.1:11434/api/tags", 2)
    if not raw:
        return False
    try:
        names = [m.get("name","") for m in json.loads(raw).get("models", [])]
    except Exception:
        return False
    return any("nomic" in n for n in names)
def embed(text):
    try:
        obj = post(OLLAMA, {"model": "nomic-embed-text", "prompt": "search_query: "+text[:1500]}, 20)
        return obj.get("embedding")
    except Exception as e:
        print("nomic_skip", e); return None
def hybrid(query, fts_rows, k):
    vec = embed(query)
    if not vec:
        return fts_rows, "nomic_dark"
    ids = [r[0] for r in fts_rows]
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    blobs = []
    if ids:
        marks = ",".join("?"*len(ids))
        blobs = con.execute("SELECT chunk_id, embedding FROM file_chunk_embeddings WHERE chunk_id IN (%s)" % marks, ids).fetchall()
    con.close()
    score = {}
    for i, r in enumerate(fts_rows, 1):
        score[r[0]] = score.get(r[0], 0.0) + 1.0/(60+i)
    by = {r[0]: r for r in fts_rows}
    ranked = sorted(((cid, cosine(vec, blob)) for cid, blob in blobs if blob), key=lambda x: x[1], reverse=True)
    for i, (cid, _s) in enumerate(ranked, 1):
        score[cid] = score.get(cid, 0.0) + 1.0/(60+i)
    out = []
    for cid in sorted(score, key=lambda i: score[i], reverse=True):
        if cid in by:
            out.append(by[cid])
        if len(out) >= k:
            break
    return out or fts_rows, "nomic_rrf %s vecs" % len(blobs)
def pack(rows):
    out, used = [], 0
    for r in rows:
        snip = " ".join((r[3] or "").split())[:380]
        block = "[%s #%s bm25=%.3f]\n%s\n" % (r[1], r[2], r[4], snip)
        if used + len(block) > 3500:
            break
        out.append(block); used += len(block)
    return "\n".join(out)
def extract(obj):
    ch = (obj.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    return (msg.get("content") or ch.get("text") or "").strip()
def coder_up():
    raw = get(CODER+"/models", 3)
    if not raw:
        return []
    try:
        return [m.get("id") or m.get("name") for m in json.loads(raw.decode()).get("data", [])]
    except Exception:
        return []
def chat(base, model, system, user, key, timeout, max_tokens):
    headers = {}
    if key:
        headers["Authorization"] = "Bearer "+key
    obj = post(base.rstrip("/")+"/chat/completions", {
        "model": model,
        "messages": [{"role":"system","content":system},{"role":"user","content":user}],
        "temperature": 0.2, "max_tokens": max_tokens
    }, timeout, headers)
    return extract(obj)
query = cli_query()
print("db", DB)
t0 = time.perf_counter()
rows = fts(query, 12)
print("fts_s", round(time.perf_counter()-t0, 4), "hits", len(rows))
if nomic_up():
    t1 = time.perf_counter()
    rows, st = hybrid(query, rows, 6)
    print("nomic_s", round(time.perf_counter()-t1, 4), st)
else:
    print("nomic dark"); rows = rows[:6]
for r in rows[:6]:
    print("HIT", round(r[4],3), "%s#%s" % (r[1], r[2]))
user = "QUESTION:\n%s\n\nCONTEXT:\n%s" % (query, pack(rows[:6]))
names = coder_up()
print("coder", names or "DARK")
if names:
    t2 = time.perf_counter()
    ans = chat(CODER, CODER_MODEL, "Use only context. Cite paths. No invented joules. No python.", user, "", 180, 120)
    print("llm_s", round(time.perf_counter()-t2, 3))
    print("==== LOCAL 7B ====")
    print(ans)
key = CLOUD_KEY
if key and "sk-or-..." not in key:
    t3 = time.perf_counter()
    cans = chat(CLOUD_BASE, CLOUD_MODEL, "Architect pass. N14. Say if Landauer figures in context are physical.", user + "\n\nLOCAL_7B:\n"+(ans[:1500] if names else ""), key, 90, 220)
    print("cloud_s", round(time.perf_counter()-t3, 3))
    print("==== CLOUD ====")
    print(cans)
else:
    print("cloud_skip set a real OPENROUTER_API_KEY, not sk-or-...")
print("total_s", round(time.perf_counter()-t0, 3))
