#!/usr/bin/env python3
"""OpenRoot stack recreate + clean push helper.

One file. Three remotes. Never git add -A.

LIVE 2026-09-04 (optiplex3060):
  wisdom-scaffold  stage/spoke-rag-20260904  79143f1
  openroot         main behind origin 18     72bb8df
  une              main                      7fd45ed
  kit canon        /home/jesse/openroot/kit
  twin             /home/jesse/openroot/openroot-kit  (read-only)
"""
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path

JESSE = Path("/home/jesse")
WISDOM = JESSE / "wisdom-scaffold"
OPENROOT = JESSE / "openroot"
UNE = JESSE / "une"
RECOVERY = JESSE / "wisdom-recovery"
CENSUS = RECOVERY / "census-20260904"
SELF_REL = Path("scripts/stack_recreate.py")
BRANCH = "stack/recreate-20260904"
REMOTES = {
    "wisdom-scaffold": "https://github.com/jesseray718/wisdom-scaffold.git",
    "openroot": "https://github.com/jesseray718/openroot.git",
    "une": "https://github.com/jesseray718/une.git",
}
IGNORE_LINES = [
    "*.sqlite", "*.sqlite-wal", "*.sqlite-shm",
    "*.db", "*.db-wal", "*.db-shm", "*.tar.gz",
    "data/tidbit.sqlite*", "data/popw_ledger.jsonl",
    "stamps/lattice_ledger.jsonl", "openroot-kit-20260902.tar.gz",
]
NEVER_ADD_SUFFIX = (".sqlite", ".sqlite-wal", ".sqlite-shm", ".db", ".db-wal", ".db-shm", ".tar.gz")

def run(args, cwd=None):
    return subprocess.run(args, cwd=str(cwd) if cwd else None, text=True, capture_output=True)

def die(msg):
    print("FAIL", msg)
    raise SystemExit(1)

def cmd_status():
    print("kit_canon kit")
    print("kit_path", OPENROOT / "kit")
    print("twin_path", OPENROOT / "openroot-kit")
    print("db_snap", RECOVERY / "db-snap-20260904-064031")
    print("unique_src", RECOVERY / "unique-src-20260904-065541")
    for name, root in (("wisdom-scaffold", WISDOM), ("openroot", OPENROOT), ("une", UNE)):
        print("=" * 60)
        print(name, root)
        if not (root / ".git").exists():
            print("NO_GIT"); continue
        print("branch", run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root).stdout.strip())
        print("head", run(["git", "log", "-1", "--oneline"], cwd=root).stdout.strip())
        print(run(["git", "status", "-sb"], cwd=root).stdout.strip()[:1500])
    print("DONE_STATUS")
    return 0

def cmd_write_ignore_draft():
    CENSUS.mkdir(parents=True, exist_ok=True)
    p = CENSUS / "gitignore.draft"
    p.write_text("\n".join(["# draft"] + IGNORE_LINES) + "\n", encoding="utf-8")
    print("WROTE", p)
    print("DONE_IGNORE_DRAFT")
    return 0

def cmd_recreate(dest):
    dest.mkdir(parents=True, exist_ok=True)
    for name, url in REMOTES.items():
        target = dest / name
        if target.exists():
            print("EXISTS", target); continue
        print("CLONE", url, target)
        p = run(["git", "clone", "--depth", "1", url, str(target)])
        if p.returncode != 0:
            print(p.stderr); die("clone " + name)
        gi = target / ".gitignore"
        extra = "\n".join(IGNORE_LINES) + "\n"
        if gi.is_file():
            cur = gi.read_text(encoding="utf-8", errors="replace")
            if "*.sqlite" not in cur:
                gi.write_text(cur.rstrip() + "\n" + extra, encoding="utf-8")
        else:
            gi.write_text(extra, encoding="utf-8")
        print("OK", name)
    readme = dest / "STACK.txt"
    readme.write_text(
        "Three remotes. Not one repo.\n"
        "kit canon: /home/jesse/openroot/kit\n"
        "Do not copy knowledge.db into git.\n",
        encoding="utf-8",
    )
    print("WROTE", readme)
    print("DONE_RECREATE")
    return 0

def cmd_commit_self():
    if not (WISDOM / ".git").exists():
        die("no wisdom-scaffold git")
    src = Path(__file__).resolve()
    dest = WISDOM / SELF_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src != dest:
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        print("WROTE", dest)
    br = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=WISDOM).stdout.strip()
    if br != BRANCH:
        p = run(["git", "checkout", "-B", BRANCH], cwd=WISDOM)
        print(p.stdout or p.stderr)
    p = run(["git", "add", "--", str(SELF_REL)], cwd=WISDOM)
    if p.returncode != 0:
        print(p.stderr); die("git add self")
    staged = run(["git", "diff", "--cached", "--name-only"], cwd=WISDOM).stdout.splitlines()
    print("staged", staged)
    bad = [s for s in staged if s != str(SELF_REL)]
    if bad:
        run(["git", "reset", "HEAD"], cwd=WISDOM)
        die("refusing extra staged files: " + ", ".join(bad))
    if not staged:
        print("NOTHING_TO_COMMIT")
        print("DONE_COMMIT_SELF")
        return 0
    p = run(["git", "commit", "-m", "feat(stack): add recreatable three-remote helper (no add -A)"], cwd=WISDOM)
    print(p.stdout or p.stderr)
    if p.returncode != 0:
        die("commit")
    print("DONE_COMMIT_SELF")
    return 0

def cmd_push_self():
    p = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=WISDOM)
    if p.stdout.strip() != BRANCH:
        die("not on " + BRANCH + " (on " + p.stdout.strip() + ")")
    staged = run(["git", "diff", "--cached", "--name-only"], cwd=WISDOM).stdout.strip()
    if staged:
        die("index dirty: " + staged)
    p = run(["git", "push", "-u", "origin", BRANCH], cwd=WISDOM)
    print(p.stdout); print(p.stderr)
    if p.returncode != 0:
        die("push")
    print("DONE_PUSH_SELF")
    return 0

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("write-ignore-draft")
    rec = sub.add_parser("recreate")
    rec.add_argument("--dest", default="/home/jesse/wisdom-recovery/stack-recreate")
    sub.add_parser("commit-self")
    sub.add_parser("push-self")
    args = ap.parse_args()
    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "write-ignore-draft":
        return cmd_write_ignore_draft()
    if args.cmd == "recreate":
        return cmd_recreate(Path(args.dest))
    if args.cmd == "commit-self":
        return cmd_commit_self()
    if args.cmd == "push-self":
        return cmd_push_self()
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
