#!/usr/bin/env python3
"""Locate live pipeline files. Exclude .venv. Print ghosts vs published."""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import GHOST_RELATIVE, PUBLISHED_RELATIVE, pane, roots, skip_dir  # noqa: E402

CODE_SUFFIX = {".py", ".sh", ".json", ".yaml", ".yml", ".md", ".sql"}


def walk_code(root: Path):
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not skip_dir(d)]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() in CODE_SUFFIX or name.endswith(".db"):
                yield p


def probe_db(path: Path) -> str:
    if not path.is_file():
        return "ABSENT"
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")]
        fts = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND sql LIKE '%fts5%'")]
        bits = [f"tables={len(tables)}"]
        for t in ("file_chunks", "file_chunk_embeddings", "nomic_embeddings", "github_repos", "file_index"):
            if t in tables:
                n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                bits.append(f"{t}={n}")
        if fts:
            bits.append("fts5=" + ",".join(fts))
        con.close()
        return " ".join(bits)
    except Exception as e:
        return f"ERROR {e}"


def main() -> int:
    r = roots()
    print(f"pane={pane()}")
    print("--- roots ---")
    for k, v in r.items():
        mark = "DIR" if v.is_dir() else ("FILE" if v.is_file() else "MISSING")
        extra = ""
        if k.startswith("db") or k in {"knowledge", "operator"}:
            extra = " " + probe_db(v)
        print(f"{mark:7} {k:12} {v}{extra}")

    wisdom = r["wisdom"]
    print("--- published ---")
    for rel in PUBLISHED_RELATIVE:
        p = wisdom / rel
        print(("LIVE   " if p.is_file() else "ABSENT ") + str(p))

    print("--- ghosts (were never on GitHub HEAD) ---")
    for rel in GHOST_RELATIVE:
        p = wisdom / rel
        print(("LIVE   " if p.is_file() else "GHOST  ") + str(p))

    print("--- code files excluding .venv ---")
    count = 0
    for root_key in ("wisdom", "openroot", "une"):
        root = r[root_key]
        for p in walk_code(root):
            print(p)
            count += 1
            if count >= 400:
                print("...truncated at 400")
                print(f"shown={count}")
                return 0
    print(f"shown={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
