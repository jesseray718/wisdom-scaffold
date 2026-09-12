#!/usr/bin/env python3
import os, sqlite3, struct, sys
TARGETS = [
    "/home/jesse/wisdom-scaffold/data/optiplex_index.db",
    "/home/jesse/wisdom-scaffold/data/optiplex_public.db",
    "/home/jesse/wisdom-scaffold/data/file_map_safe.sqlite",
    "/home/jesse/openroot/kit/chunk_index.sqlite",
    "/home/jesse/openroot/data/tidbit.sqlite",
    "/home/jesse/knowledge/index/corpus.sqlite",
    "/home/jesse/knowledge-node/knowledge.db",
    "/home/jesse/wisdom-scaffold/index_content_blobs.py",
]
def blob_kind(b):
    raw = bytes(b); n = len(raw)
    if n == 0: return "empty"
    if raw[:1] in (b"{", b"["): return f"jsonish n={n}"
    if n % 4 == 0:
        floats = struct.unpack_from(f"<{min(8, n//4)}f", raw)
        return f"f32 n={n} dim\~={n//4} head={tuple(round(x,3) for x in floats)}"
    return f"opaque n={n} head={raw[:16].hex()}"
def inspect(path):
    print("="*72); print(path)
    if not os.path.exists(path):
        print("MISS"); return
    st = os.stat(path)
    print(f"size={st.st_size}")
    if path.endswith(".py"):
        print("script HIT"); return
    if st.st_size < 100:
        print("too small"); return
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    for name, typ, sql in con.execute("SELECT name,type,sql FROM sqlite_master WHERE type IN ('table','index') ORDER BY type,name"):
        print(f"\n[{typ}] {name}")
        if sql: print(sql[:600])
        if typ != "table" or name.startswith("sqlite_"): continue
        try: n = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        except Exception as e:
            print(" count-error", e); continue
        cols = list(con.execute(f'PRAGMA table_info("{name}")'))
        names = [c[1] for c in cols]
        print(f"  rows={n} cols={names}")
        if not n: continue
        row = con.execute(f'SELECT * FROM "{name}" LIMIT 1').fetchone()
        for c, v in zip(names, row):
            if isinstance(v, bytes): print(f"  sample.{c}: {blob_kind(v)}")
            else: print(f"  sample.{c}: {repr(v)[:160]}")
        for probe in ("text_status","kind","type","model","status"):
            if probe in names:
                hist = con.execute(f'SELECT "{probe}", COUNT(*) FROM "{name}" GROUP BY 1 ORDER BY 2 DESC LIMIT 12').fetchall()
                print(f"  hist.{probe}: {list(hist)}")
        for c in names:
            if any(k in c.lower() for k in ("embed","vector","nomic")):
                filled = con.execute(f'SELECT COUNT(*) FROM "{name}" WHERE "{c}" IS NOT NULL').fetchone()[0]
                print(f"  filled.{c}={filled}/{n}")
    con.close()
for p in TARGETS:
    inspect(p)
print("=== DONE ===")
