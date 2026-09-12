#!/usr/bin/env python3
"""Hang FTS5 on file_chunks. Content-sync triggers. Optional seed ingest."""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import roots, skip_dir  # noqa: E402

DDL = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS file_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS file_chunk_embeddings (
    chunk_id INTEGER PRIMARY KEY,
    embedding BLOB,
    FOREIGN KEY(chunk_id) REFERENCES file_chunks(id)
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    file_path,
    chunk_text,
    content='file_chunks',
    content_rowid='id',
    tokenize='porter unicode61'
);
CREATE TRIGGER IF NOT EXISTS file_chunks_ai AFTER INSERT ON file_chunks BEGIN
  INSERT INTO chunks_fts(rowid, file_path, chunk_text)
  VALUES (new.id, new.file_path, new.chunk_text);
END;
CREATE TRIGGER IF NOT EXISTS file_chunks_ad AFTER DELETE ON file_chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, file_path, chunk_text)
  VALUES ('delete', old.id, old.file_path, old.chunk_text);
END;
CREATE TRIGGER IF NOT EXISTS file_chunks_au AFTER UPDATE ON file_chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, file_path, chunk_text)
  VALUES ('delete', old.id, old.file_path, old.chunk_text);
  INSERT INTO chunks_fts(rowid, file_path, chunk_text)
  VALUES (new.id, new.file_path, new.chunk_text);
END;
"""

TEXT_SUFFIX = {".py", ".sh", ".md", ".txt", ".json", ".yaml", ".yml", ".sql", ".toml", ".cfg"}
CHUNK = 1000
OVERLAP = 200


def rebuild_fts(con: sqlite3.Connection) -> None:
    con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")


def ingest_tree(con: sqlite3.Connection, tree: Path, limit_files: int = 0) -> int:
    added = 0
    files_seen = 0
    for dirpath, dirnames, filenames in os.walk(tree):
        dirnames[:] = [d for d in dirnames if not skip_dir(d)]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() not in TEXT_SUFFIX:
                continue
            files_seen += 1
            if limit_files and files_seen > limit_files:
                return added
            n = con.execute("SELECT COUNT(*) FROM file_chunks WHERE file_path=?", (str(p),)).fetchone()[0]
            if n:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if not text.strip():
                continue
            step = max(CHUNK - OVERLAP, 1)
            chunks = [text[i : i + CHUNK] for i in range(0, len(text), step)]
            for idx, chunk in enumerate(chunks):
                con.execute(
                    "INSERT INTO file_chunks(file_path, chunk_index, chunk_text) VALUES (?,?,?)",
                    (str(p), idx, chunk),
                )
                added += 1
    return added


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--ingest", action="store_true")
    ap.add_argument("--limit-files", type=int, default=0)
    args = ap.parse_args()
    r = roots()
    db = Path(args.db) if args.db else r["db"]
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db))
    con.executescript(DDL)
    if args.ingest:
        for key in ("wisdom", "openroot", "une"):
            tree = r[key]
            if tree.is_dir():
                n = ingest_tree(con, tree, args.limit_files)
                print(f"ingest {tree} chunks+={n}")
    if args.rebuild:
        rebuild_fts(con)
        print("fts rebuild")
    con.commit()
    chunks = con.execute("SELECT COUNT(*) FROM file_chunks").fetchone()[0]
    try:
        fts_n = con.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    except sqlite3.DatabaseError as e:
        fts_n = f"ERR {e}"
    print(f"db={db}")
    print(f"file_chunks={chunks} chunks_fts={fts_n}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
