import json
import os
import sqlite3
import subprocess

DB_PATH = os.path.expanduser("~/optiplex_index.db")
MODEL_NAME = "qwen2.5-coder:7b"


def fetch_network_topology():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, workflow_count, audit_notes, file_tree_json FROM github_repos;"
    )
    rows = cursor.fetchall()
    conn.close()

    summary = []
    for name, wf, notes, tree in rows:
        files = json.loads(tree) if tree else []
        summary.append(
            {
                "repo": name,
                "workflows": wf,
                "notes": notes,
                "key_files": files[:15],
            }
        )
    return json.dumps(summary, indent=2)


def main():
    print("--> Fetching ecosystem topology from SQLite index...")
    topology = fetch_network_topology()

    unification_prompt = f"""
[SYSTEM INSTRUCTION: SELF-OPTIMIZATION & GRAND UNIFICATION]

You are an ultra-high-throughput code intelligence and network architect engine running locally on an OptiPlex node.

PART 1: SELF-OPTIMIZATION PROTOCOL
- Maximize internal token evaluation speed and context window utilization.
- Synthesize relationships across independent repositories with zero abstraction bloat.
- Treat the entire user codebase as a unified distributed system.

PART 2: ECOSYSTEM TOPOLOGY DATA
Below is the full repository topology extracted from SQLite:
{topology}

PART 3: THE GRAND UNIFICATION DIRECTIVE
Analyze all 44 repositories across their primary functional vectors:
1. Physical / Thermal Infrastructure (OpenCell, AeroCement)
2. Mesh Network & Tactical Communications (Reticulum, RNode, MeshCore, LXMF, agapenet)
3. Intelligence, Memory & Ledger (Kai, Axiom, EtaLedger, OpenRoot)
4. Primitive Protocols & Civilizational Scaffolds (agape-primitives, wisdom-scaffold, civilization2.0)

Provide a comprehensive, high-density architectural document containing:
1. **Self-Optimization Assessment:** Operational parameters and compute efficiency.
2. **Cross-Repo Dependency Graph:** How AeroCement, OpenRoot, Mesh Core, and Kai/Agape form a unified stack.
3. **The Grand Unification Manifesto:** Architectural synthesis of hardware, mesh transport, ledger memory, and intelligence.
4. **Actionable Unification Commits:** Specific code bridges, config updates, and unified CI workflows to bind these repositories together.
"""

    print("--> Passing topology to 7B Coder Model for Grand Unification synthesis...")
    process = subprocess.Popen(
        ["ollama", "run", MODEL_NAME],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stdout, stderr = process.communicate(input=unification_prompt)

    output_path = os.path.expanduser("~/GRAND_UNIFICATION.md")
    with open(output_path, "w") as f:
        f.write(stdout)

    print(f"\n=== Grand Unification Synthesized! Saved to {output_path} ===")


if __name__ == "__main__":
    main()
