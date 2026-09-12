#!/usr/bin/env python3
from __future__ import annotations
import os, sqlite3, sys
from pathlib import Path

SKIP = {".venv", "venv", ".git", "node_modules", "__pycache__", "models", "gguf", ".cache"}
ROOTS = [Path("/home/jesse/wisdom-scaffold"), Path("/home/jesse/openroot"), Path("/home/jesse/une"), Path("/home/jesse")]
KNOWN = [
    Path("/home/jesse/wisdom-scaffold/data/optiplex_index.db"),
    Path("/home/jesse/optiplex_index.db"),
    Path("/home/jesse/openroot/agape_kb/agape_vector_index.db"),
    Path("/home/jesse/wisdom-scaffold/data/knowledge.db"),
    Path("/home/jesse/wisdom-scaffold/data/operator_memory.db"),
    Path("/home/jesse/wisdom-scaffold/wisdom_rag.db"),
    Path("/home/jesse/wisdom_rag.db"),
    Path("/home/jesse/openroot/kit/sidekick/sidekick.sqlite"),
]
TEXTISH = ("text", "content", "chunk", "body", "snippet", "notes", "payload", "path", "file")

def walk_dbs(limit=40):
    found, seen = [], set()
    for p in KNOWN:
        if p.is_file():
            seen.add(p.resolve()); found.append(p)
    for root in ROOTS:
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP]
            if "/.venv/" in dirpath or "/venv/" in dirpath:
                continue
            for name in filenames:
                if not (name.endswith(".db") or name.endswith(".sqlite")):
                    continue
                p = Path(dirpath) / name
                try:
                    rp = p.resolve()
                except OSError:
                    continue
                if rp in seen:
                    continue
                seen.add(rp); found.append(p)
                if len(found) >= limit:
                    return found
    return found

def probe(path):
    info = {"path": str(path), "bytes": path.stat().st_size, "tables": {}}
    try:
        con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    except Exception as e:
        info["error"] = str(e); return info
    try:
        for name, typ, sql in con.execute("SELECT name, type, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name"):
            rec = {"type": typ, "fts5": bool(sql and "fts5" in sql.lower()), "n": None, "cols": []}
            if typ in ("table", "view"):
                try:
                    rec["n"] = con.execute('SELECT COUNT(*) FROM "%s"' % name).fetchone()[0]
                except Exception as e:
                    rec["n"] = "ERR %s" % e
                try:
                    rec["cols"] = [c[1] for c in con.execute("PRAGMA table_info(%s)" % name)]
                except Exception:
                    rec["cols"] = []
            info["tables"][name] = rec
    finally:
        con.close()
    return info

def pick_text_table(info):
    best = None
    for name, rec in info.get("tables", {}).items():
        if rec.get("type") != "table" or rec.get("fts5"):
            continue
        if not isinstance(rec.get("n"), int) or rec["n"] <= 0:
            continue
        cands = [c for c in rec.get("cols", []) if any(k in c.lower() for k in TEXTISH)]
        if not cands:
            continue
        score = rec["n"]
        if "chunk" in name.lower() or "snippet" in name.lower():
            score *= 10
        if best is None or score > best[0]:
            best = (score, name, cands[0])
    return None if best is None else (best[1], best[2])

def ensure_fts(path, table, text_col):
    fts = "fts_%s" % table
    con = sqlite3.connect(str(path))
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master")}
    if fts in names:
        n = con.execute('SELECT COUNT(*) FROM "%s"' % fts).fetchone()[0]
        con.close()
        return fts, "exists n=%s" % n
    con.execute(
        'CREATE VIRTUAL TABLE IF NOT EXISTS "%s" USING fts5(%s, content="%s", content_rowid="rowid", tokenize="porter unicode61")'
        % (fts, text_col, table)
    )
    try:
        con.execute('INSERT INTO "%s"("%s") VALUES("rebuild")' % (fts, fts))
        con.commit()
        n = con.execute('SELECT COUNT(*) FROM "%s"' % fts).fetchone()[0]
        msg = "built n=%s from %s.%s" % (n, table, text_col)
    except Exception as e:
        msg = "rebuild_fail %s" % e
    con.close()
    return fts, msg

def search(path, fts, query, k=8):
    tokens = [t for t in query.replace('"', " ").split() if t]
    if not tokens:
        return []
    and_q, or_q = " ".join(tokens), " OR ".join(tokens)
    con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    sql = 'SELECT rowid, bm25("%s") FROM "%s" WHERE "%s" MATCH ? ORDER BY 2 LIMIT ?' % (fts, fts, fts)
    try:
        rows = con.execute(sql, (and_q, k)).fetchall()
        if len(rows) < 3:
            rows = con.execute(sql, (or_q, k)).fetchall()
    except sqlite3.DatabaseError as e:
        con.close(); return [("ERR", str(e), "")]
    cols = [c[1] for c in con.execute('PRAGMA table_info("%s")' % fts)]
    text_col = cols[0] if cols else None
    out = []
    for rowid, rnk in rows:
        snip = ""
        if text_col:
            try:
                snip = con.execute('SELECT "%s" FROM "%s" WHERE rowid=?' % (text_col, fts), (rowid,)).fetchone()[0]
            except Exception:
                snip = ""
        out.append((rowid, rnk, (snip or "")[:200]))
    con.close()
    return out

def main():
    query = " ".join(sys.argv[1:]).strip() or "need_gate FTS5 file_chunks nomic"
    print("=== SQLITE INVENTORY ===")
    dbs = walk_dbs()
    if not dbs:
        print("NO db files"); return 2
    richest = None
    for p in dbs:
        info = probe(p)
        print("\nDB %s bytes=%s" % (info["path"], info["bytes"]))
        if "error" in info:
            print("  ERROR", info["error"]); continue
        for name, rec in info["tables"].items():
            print("  %s %s n=%s%s cols=%s" % (rec["type"], name, rec.get("n"), " FTS5" if rec.get("fts5") else "", rec.get("cols")))
        pick = pick_text_table(info)
        score = 0
        if pick:
            score = info["tables"][pick[0]]["n"]
            print("  PICK %s.%s n=%s" % (pick[0], pick[1], score))
        if richest is None or score > richest[0]:
            richest = (score, p, info, pick)
    print("\n=== FTS HANG + QUERY ===")
    print("query:", query)
    if not richest or not richest[3]:
        print("No text table. Corpus never landed in sqlite."); return 1
    path, pick = richest[1], richest[3]
    fts, msg = ensure_fts(path, pick[0], pick[1])
    print("target", path, pick, msg)
    hits = search(path, fts, query)
    if not hits:
        print("0 hits"); return 1
    for i, (rowid, rnk, snip) in enumerate(hits, 1):
        print("[%s] rowid=%s bm25=%s %r" % (i, rowid, rnk, snip))
    print("NOTE: scripts/rag/hybrid_rag_router.py on this box is Nomic Atlas. This script is local FTS5.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
