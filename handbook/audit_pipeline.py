#!/usr/bin/env python3
"""Audit split DBs, split Ollama APIs, missing FTS5, one-hot readiness."""
from __future__ import annotations

import ast
import json
import sqlite3
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import PUBLISHED_RELATIVE, pane, roots  # noqa: E402

FAILS: list[str] = []
WARNS: list[str] = []


def note(ok: bool, msg: str, warn: bool = False) -> None:
    if ok:
        print("PASS", msg)
    elif warn:
        WARNS.append(msg)
        print("WARN", msg)
    else:
        FAILS.append(msg)
        print("FAIL", msg)


def ollama_tags() -> list[str]:
    try:
        raw = urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2).read()
        return [m.get("name", "") for m in json.loads(raw).get("models", [])]
    except Exception as e:
        return [f"DOWN {e}"]


def scan_embed_api(path: Path) -> set[str]:
    found: set[str] = set()
    if not path.is_file():
        return found
    text = path.read_text(encoding="utf-8", errors="ignore")
    if "/api/embed" in text and "/api/embeddings" not in text:
        found.add("/api/embed")
    if "/api/embeddings" in text:
        found.add("/api/embeddings")
    return found


def db_probe(path: Path, label: str) -> None:
    if not path.is_file():
        note(False, f"{label} absent {path}", warn=True)
        return
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master")}
    print(f"DB {label} {path} objects={len(names)}")
    if "nomic_embeddings" in names:
        n = con.execute("SELECT COUNT(*) FROM nomic_embeddings").fetchone()[0]
        row = con.execute("SELECT length(embedding) FROM nomic_embeddings LIMIT 1").fetchone()
        dim = (row[0] // 4) if row and row[0] else 0
        note(n > 0, f"{label} nomic_embeddings={n} dim={dim}")
        if dim and dim != 768:
            note(False, f"{label} nomic dim {dim} != 768")
    if "file_chunks" in names:
        n = con.execute("SELECT COUNT(*) FROM file_chunks").fetchone()[0]
        note(n > 0, f"{label} file_chunks={n}", warn=n == 0)
    else:
        note(False, f"{label} no file_chunks", warn=True)
    if "file_chunk_embeddings" in names:
        n = con.execute("SELECT COUNT(*) FROM file_chunk_embeddings").fetchone()[0]
        print(f"INFO {label} file_chunk_embeddings={n}")
    if "chunks_fts" in names:
        n = con.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
        note(True, f"{label} chunks_fts={n}")
    else:
        note(False, f"{label} no chunks_fts — run fts5_ensure.py")
    con.close()


def main() -> int:
    r = roots()
    print(f"pane={pane()}")
    note(pane() != "A15", "embed jobs belong on SSH/sandbox not A15", warn=pane() == "A15")

    db = r["db"]
    ghost = r["db_ghost"]
    if ghost.is_file() and db.is_file() and ghost.resolve() != db.resolve():
        note(False, f"split DB live: {ghost} AND {db}")
    elif ghost.is_file() and not db.is_file():
        note(False, f"unify_scaffold ghost DB is the only file: {ghost}")
    else:
        note(True, f"primary DB slot {db}")

    db_probe(db, "primary")
    if ghost.is_file() and ghost.resolve() != db.resolve():
        db_probe(ghost, "ghost")
    db_probe(r["db_agape"], "agape_vector")
    db_probe(r["knowledge"], "knowledge")
    db_probe(r["operator"], "operator")

    wisdom = r["wisdom"]
    apis: set[str] = set()
    for rel in PUBLISHED_RELATIVE:
        p = wisdom / rel
        apis |= scan_embed_api(p)
        if rel.endswith(".py"):
            if p.is_file():
                try:
                    ast.parse(p.read_text(encoding="utf-8"))
                    print(f"PASS parse {p}")
                except SyntaxError as e:
                    note(False, f"syntax {p} {e}")
            else:
                print(f"INFO published missing {p}")
    if len(apis) > 1:
        note(False, f"split Ollama embed API {sorted(apis)}")
    elif apis:
        print(f"INFO embed API {sorted(apis)}")

    tags = ollama_tags()
    nomic = any("nomic" in t for t in tags)
    print("INFO ollama", tags[:8])
    note(nomic, "nomic-embed-text present", warn=not nomic)

    print("FAIL" if FAILS else "PASS")
    for f in FAILS:
        print(" -", f)
    for w in WARNS:
        print(" ~", w)
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
