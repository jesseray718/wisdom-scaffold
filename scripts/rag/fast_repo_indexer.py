import json
import os
import sqlite3
import subprocess

GITHUB_USER = "jesseray718"
DB_PATH = os.path.expanduser("~/optiplex_index.db")
WORKSPACE = os.path.expanduser("~/repo_audit_workspace")


def run_cmd(cmd):
    try:
        res = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, check=True
        )
        return res.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS github_repos (
            name TEXT PRIMARY KEY,
            visibility TEXT,
            default_branch TEXT,
            has_readme INTEGER,
            has_gitignore INTEGER,
            has_license INTEGER,
            workflow_count INTEGER,
            open_pr_count INTEGER,
            file_tree_json TEXT,
            audit_notes TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()


def main():
    os.makedirs(WORKSPACE, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    print(f"--> Fetching repository list for {GITHUB_USER} via gh CLI...")
    repos_raw = run_cmd(
        f"gh repo list {GITHUB_USER} --limit 200 --json name,visibility,defaultBranchRef"
    )
    if not repos_raw:
        print("[ERROR] Failed to fetch repos.")
        return

    repos = json.loads(repos_raw)
    print(f"--> Found {len(repos)} repositories. Beginning fast scan...\n")

    for repo in repos:
        name = repo["name"]
        vis = repo["visibility"]
        branch = (
            repo.get("defaultBranchRef", {}).get("name", "main")
            if repo.get("defaultBranchRef")
            else "main"
        )

        repo_dir = os.path.join(WORKSPACE, name)

        # Quick shallow clone/pull for file structure inspection
        if not os.path.exists(repo_dir):
            run_cmd(f"gh repo clone {GITHUB_USER}/{name} {repo_dir} -- --depth=1")
        else:
            run_cmd(f"git -C {repo_dir} pull --rebase")

        # Fast local checks
        has_readme = 1 if os.path.exists(os.path.join(repo_dir, "README.md")) or os.path.exists(os.path.join(repo_dir, "readme.md")) else 0
        has_gitignore = 1 if os.path.exists(os.path.join(repo_dir, ".gitignore")) else 0
        has_license = 1 if os.path.exists(os.path.join(repo_dir, "LICENSE")) else 0

        wf_dir = os.path.join(repo_dir, ".github", "workflows")
        wf_count = len(os.listdir(wf_dir)) if os.path.exists(wf_dir) else 0

        # Check PR count via gh
        prs_raw = run_cmd(f"gh pr list -R {GITHUB_USER}/{name} --json number")
        pr_count = len(json.loads(prs_raw)) if prs_raw else 0

        # Map shallow file tree
        files = []
        for root, dirs, f_names in os.walk(repo_dir):
            if ".git" in root:
                continue
            rel_path = os.path.relpath(root, repo_dir)
            if rel_path == ".":
                files.extend(f_names)
            else:
                files.extend([os.path.join(rel_path, f) for f in f_names])

        tree_json = json.dumps(files[:100])  # Cap at top 100 paths

        # Generate quick flag notes
        notes = []
        if not has_readme:
            notes.append("MISSING_README")
        if not has_gitignore:
            notes.append("MISSING_GITIGNORE")
        if wf_count == 0:
            notes.append("NO_CI_WORKFLOWS")
        if pr_count > 0:
            notes.append(f"{pr_count}_OPEN_PRS")

        audit_notes = ", ".join(notes) if notes else "CLEAN"

        conn.execute(
            """
            INSERT OR REPLACE INTO github_repos 
            (name, visibility, default_branch, has_readme, has_gitignore, has_license, workflow_count, open_pr_count, file_tree_json, audit_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                name,
                vis,
                branch,
                has_readme,
                has_gitignore,
                has_license,
                wf_count,
                pr_count,
                tree_json,
                audit_notes,
            ),
        )

        print(f" Indexed: {name:<25} | Notes: {audit_notes}")

    conn.commit()
    conn.close()
    print("\n=== Fast Indexing Complete! Stored in SQLite. ===")


if __name__ == "__main__":
    main()
