#!/usr/bin/env python3
"""Thin dispatcher. Does not re-implement unify_scaffold. One-hot steps."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import pane, roots  # noqa: E402

HERE = Path(__file__).resolve().parent


def script_path(name: str) -> Path:
    candidates = [
        HERE / name,
        HERE.parent / "scripts" / "rag" / name,
        HERE.parent / "scripts" / "unification" / name,
        HERE.parent / "handbook" / name,
    ]
    for p in candidates:
        if p.is_file():
            return p
    return HERE / name


def run(script: str, extra: list[str]) -> int:
    cmd = [sys.executable, str(script_path(script)), *extra]
    print("+", " ".join(cmd))
    return subprocess.call(cmd)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("verb", nargs="?", default="help", choices=("help", "locate", "audit", "fts", "query", "ingest"))
    ap.add_argument("rest", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    print(f"pane={pane()} wisdom={roots()['wisdom']}")
    if args.verb == "help":
        print(
            "locate | audit | fts | ingest | query <text>\n"
            "one-hot: never ingest + query + 7B together\n"
            "default query mode is FTS5"
        )
        return 0
    if args.verb == "locate":
        return run("locate_pipeline.py", args.rest)
    if args.verb == "audit":
        return run("audit_pipeline.py", args.rest)
    if args.verb == "fts":
        return run("fts5_ensure.py", args.rest)
    if args.verb == "ingest":
        return run("fts5_ensure.py", ["--ingest", *args.rest])
    if args.verb == "query":
        q = args.rest or ["openroot fts5 need_gate"]
        return run("hybrid_rag_router.py", q)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
