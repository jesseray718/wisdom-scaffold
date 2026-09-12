#!/usr/bin/env python3
"""Replace unify_scaffold.py path split. Read PRIMARY db only. No numpy required."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import pane, roots  # noqa: E402


def main() -> int:
    r = roots()
    db = r["db"]
    out = r["wisdom"] / "GRAND_UNIFICATION_MANIFEST.json"
    print(f"pane={pane()} db={db}")
    if not db.is_file():
        print("FAIL primary db absent")
        return 2
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    names = {row[0] for row in con.execute("SELECT name FROM sqlite_master")}
    manifest = {
        "pane": pane(),
        "db": str(db),
        "objects": sorted(names),
        "counts": {},
    }
    for table in (
        "github_repos",
        "file_index",
        "file_chunks",
        "file_chunk_embeddings",
        "nomic_embeddings",
        "chunks_fts",
    ):
        if table in names:
            manifest["counts"][table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        else:
            manifest["counts"][table] = None
    nodes = []
    if "github_repos" in names:
        cols = [c[1] for c in con.execute("PRAGMA table_info(github_repos)")]
        select = "name"
        if "audit_notes" in cols:
            select += ", audit_notes"
        for row in con.execute(f"SELECT {select} FROM github_repos"):
            name = row[0]
            notes = row[1] if len(row) > 1 else ""
            file_count = 0
            if "file_chunks" in names:
                file_count = con.execute(
                    "SELECT COUNT(DISTINCT file_path) FROM file_chunks WHERE file_path LIKE ?",
                    (f"%/{name}/%",),
                ).fetchone()[0]
            nodes.append({"repo": name, "audit_notes": notes, "file_count": file_count})
    manifest["architecture_nodes"] = nodes
    con.close()
    out.write_text(json.dumps(manifest, indent=2))
    print(f"wrote {out}")
    print(json.dumps(manifest["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
