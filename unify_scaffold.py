import json
import sqlite3
import numpy as np

print("--> Running Grand Unification Synthesis & Vector Inspector...")

# 1. Load STAGE_CONTEXT.json correctly based on dump structure
with open("STAGE_CONTEXT.json", "r") as f:
    raw_data = json.load(f)

# Handle both root-level and tables-wrapped JSON structures
if "tables" in raw_data:
    repos = raw_data["tables"].get("github_repos", [])
    files = raw_data["tables"].get("file_index", [])
    embeddings = raw_data["tables"].get("nomic_embeddings", [])
else:
    repos = raw_data.get("github_repos", [])
    files = raw_data.get("file_index", [])
    embeddings = raw_data.get("nomic_embeddings", [])

print(f" Detected: {len(repos)} Repos | {len(files)} Files | {len(embeddings)} Vector Embeddings")

# 2. Build Unified Manifest
manifest = {
    "total_repos": len(repos),
    "total_files": len(files),
    "total_vector_embeddings": len(embeddings),
    "architecture_nodes": []
}

for repo in repos:
    repo_name = repo.get("name")
    repo_files = [f.get("file_path") for f in files if f.get("repo_name") == repo_name]
    manifest["architecture_nodes"].append({
        "repo": repo_name,
        "audit_notes": repo.get("audit_notes"),
        "file_count": len(repo_files),
        "sample_files": repo_files[:10]
    })

# Write JSON manifest
with open("GRAND_UNIFICATION_MANIFEST.json", "w") as out:
    json.dump(manifest, out, indent=2)

print(f" [✓] Wrote GRAND_UNIFICATION_MANIFEST.json ({len(repos)} Repos Synthesized)")

# 3. Direct Vector Inspection from SQLite DB
conn = sqlite3.connect('/home/jesse/optiplex_index.db')
rows = conn.execute('SELECT repo_name, embedding FROM nomic_embeddings;').fetchall()
conn.close()

print("\n--- NOMIC EMBEDDING DIAGNOSTICS ---")
print(f"Total Database Vectors: {len(rows)}")

vectors = []
for name, blob in rows:
    vec = np.frombuffer(blob, dtype=np.float32)
    vectors.append(vec)

matrix = np.array(vectors)
print(f"Matrix Shape:      {matrix.shape} (Repos x Dims)")
print(f"Vector Dimensions: {matrix.shape[1]}")
print(f"L2 Norm Mean:      {np.linalg.norm(matrix, axis=1).mean():.4f}")
print("=========================================================")
