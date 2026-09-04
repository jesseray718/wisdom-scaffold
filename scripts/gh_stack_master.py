#!/usr/bin/env python3
"""GitHub CLI master for jesseray718. Default: list only. Merge only with apply."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

OWNER = "jesseray718"
WISDOM = Path("/home/jesse/wisdom-scaffold")
STACK_BRANCH = "stack/recreate-20260904"
BAD_SUFFIX = (".sqlite", ".sqlite-wal", ".sqlite-shm", ".db", ".db-wal", ".db-shm", ".tar.gz")
FAIL_STATES = {"FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE", "STALE"}

def gh(args, cwd=None):
    return subprocess.run(["gh", *args], cwd=str(cwd) if cwd else None, text=True, capture_output=True)

def die(msg):
    print("FAIL", msg)
    raise SystemExit(1)

def must_gh():
    p = gh(["auth", "status"])
    if p.returncode != 0:
        print(p.stderr)
        die("gh not authenticated")

def repo_names():
    p = gh(["repo", "list", OWNER, "--limit", "200", "--json", "name"])
    if p.returncode != 0:
        print(p.stderr)
        die("repo list")
    return [r["name"] for r in json.loads(p.stdout)]

def classify_pr(repo, number):
    p = gh([
        "pr", "view", str(number),
        "--repo", OWNER + "/" + repo,
        "--json",
        "number,title,url,isDraft,mergeable,state,headRefName,baseRefName,statusCheckRollup,files",
    ])
    if p.returncode != 0:
        return {"repo": repo, "number": number, "verdict": "ERROR", "why": [p.stderr.strip()[:300]]}
    pr = json.loads(p.stdout)
    why = []
    checks = pr.get("statusCheckRollup") or []
    files = [f.get("path", "") for f in (pr.get("files") or [])]
    conclusions = []
    pending = 0
    failed = 0
    for c in checks:
        conc = (c.get("conclusion") or "").upper()
        state = (c.get("state") or "").upper()
        if state in {"PENDING", "QUEUED", "IN_PROGRESS", "EXPECTED"} and not conc:
            pending += 1
        if conc in FAIL_STATES or state in FAIL_STATES:
            failed += 1
        conclusions.append(conc or state or "?")
    if pr.get("isDraft"):
        why.append("draft")
    if pr.get("mergeable") != "MERGEABLE":
        why.append("mergeable=" + str(pr.get("mergeable")))
    if pr.get("state") != "OPEN":
        why.append("state=" + str(pr.get("state")))
    title = pr.get("title") or ""
    if title.upper().startswith("WIP"):
        why.append("wip-title")
    if pending:
        why.append("pending-checks=" + str(pending))
    if failed:
        why.append("failed-checks=" + str(failed))
    if not checks:
        why.append("no-checks")
    bad_files = [f for f in files if f.endswith(BAD_SUFFIX)]
    if bad_files:
        why.append("runtime-files=" + ",".join(bad_files[:8]))
    verdict = "SAFE" if not why else "UNSAFE"
    return {
        "repo": repo,
        "number": pr.get("number"),
        "title": title,
        "url": pr.get("url"),
        "head": pr.get("headRefName"),
        "base": pr.get("baseRefName"),
        "mergeable": pr.get("mergeable"),
        "checks": conclusions,
        "files": files[:20],
        "verdict": verdict,
        "why": why,
    }

def cmd_scan():
    must_gh()
    names = repo_names()
    print("repos", len(names))
    safe, unsafe, empty = [], [], []
    for name in names:
        p = gh(["pr", "list", "--repo", OWNER + "/" + name, "--state", "open", "--json", "number"])
        if p.returncode != 0:
            print("REPO_ERR", name, p.stderr.strip()[:200])
            continue
        prs = json.loads(p.stdout)
        if not prs:
            empty.append(name)
            continue
        for item in prs:
            row = classify_pr(name, item["number"])
            (safe if row["verdict"] == "SAFE" else unsafe).append(row)
            print(row["verdict"], name, "#" + str(row.get("number")), row.get("title"), row.get("why") or "ok")
    print("SAFE", len(safe))
    print("UNSAFE", len(unsafe))
    print("NO_OPEN_PR", len(empty))
    out = Path("/home/jesse/wisdom-recovery/census-20260904/gh_pr_scan.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"safe": safe, "unsafe": unsafe}, indent=2), encoding="utf-8")
    print("WROTE", out)
    print("DONE_SCAN")
    return 0

def cmd_open_stack_pr():
    must_gh()
    if not (WISDOM / ".git").exists():
        die("no wisdom-scaffold")
    br = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(WISDOM), text=True, capture_output=True).stdout.strip()
    if br != STACK_BRANCH:
        die("checkout " + STACK_BRANCH + " first (on " + br + ")")
    exists = gh(["pr", "list", "--repo", OWNER + "/wisdom-scaffold", "--head", STACK_BRANCH, "--json", "number,url"])
    if exists.returncode == 0 and json.loads(exists.stdout or "[]"):
        print("PR_EXISTS", exists.stdout.strip())
        print("DONE_OPEN_STACK_PR")
        return 0
    body = "Adds scripts/stack_recreate.py only so far. Three remotes. No sqlite. No add -A."
    p = gh([
        "pr", "create",
        "--repo", OWNER + "/wisdom-scaffold",
        "--base", "main",
        "--head", STACK_BRANCH,
        "--title", "feat(stack): recreatable three-remote helper",
        "--body", body,
    ], cwd=WISDOM)
    print(p.stdout)
    print(p.stderr)
    if p.returncode != 0:
        die("pr create")
    print("DONE_OPEN_STACK_PR")
    return 0

def cmd_apply(limit):
    must_gh()
    scan_path = Path("/home/jesse/wisdom-recovery/census-20260904/gh_pr_scan.json")
    if not scan_path.is_file():
        die("run scan first")
    data = json.loads(scan_path.read_text(encoding="utf-8"))
    safe = data.get("safe") or []
    print("safe_candidates", len(safe), "limit", limit)
    done = 0
    for row in safe:
        if done >= limit:
            break
        repo = row["repo"]
        num = str(row["number"])
        live = classify_pr(repo, int(num))
        if live["verdict"] != "SAFE":
            print("SKIP_NOW_UNSAFE", repo, num, live["why"])
            continue
        print("SQUASH", repo, num, live["title"])
        p = gh(["pr", "merge", num, "--repo", OWNER + "/" + repo, "--squash", "--delete-branch"])
        print(p.stdout or p.stderr)
        if p.returncode != 0:
            print("MERGE_FAIL", repo, num)
            continue
        done += 1
        print("MERGED", repo, num)
    print("merged", done)
    print("DONE_APPLY")
    return 0

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan")
    sub.add_parser("open-stack-pr")
    ap_apply = sub.add_parser("apply")
    ap_apply.add_argument("--limit", type=int, default=1)
    args = ap.parse_args()
    if args.cmd == "scan":
        return cmd_scan()
    if args.cmd == "open-stack-pr":
        return cmd_open_stack_pr()
    if args.cmd == "apply":
        return cmd_apply(args.limit)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
