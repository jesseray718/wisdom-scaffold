import json
import sqlite3
import numpy as np

DB_PATH = "/home/jesse/optiplex_index.db"

print("--> Executing Grand Unification Synthesis directly from SQLite...")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. Fetch Repos
cursor.execute("SELECT name, audit_notes, file_tree_json FROM github_repos;")
repos_raw = cursor.fetchall()

# 2. Fetch Files (using actual column 'path')
cursor.execute("SELECT path FROM file_index;")
files_raw = cursor.fetchall()

# 3. Fetch Embeddings
cursor.execute("SELECT repo_name, embedding FROM nomic_embeddings;")
embeddings_raw = cursor.fetchall()

conn.close()

print(f" Loaded: {len(repos_raw)} Repositories | {len(files_raw)} Total Files | {len(embeddings_raw)} Embeddings")

# Group files by matching repository name in file path
all_file_paths = [f[0] for f in files_raw if f[0]]

manifest = {
    "total_repos": len(repos_raw),
    "total_files": len(all_file_paths),
    "total_vector_embeddings": len(embeddings_raw),
    "architecture_nodes": []
}

for name, notes, tree_json in repos_raw:
    # Match files belonging to this repository path
    repo_files = [p for p in all_file_paths if f"/{name}/" in p or p.startswith(f"{name}/")]
    manifest["architecture_nodes"].append({
        "repo": name,
        "audit_notes": notes,
        "file_count": len(repo_files),
        "sample_files": repo_files[:10]
    })

# Write JSON manifest
with open("GRAND_UNIFICATION_MANIFEST.json", "w") as out:
    json.dump(manifest, out, indent=2)

print(f" [✓] Wrote GRAND_UNIFICATION_MANIFEST.json ({len(repos_raw)} Repos Synthesized)")

# 4. Vector Diagnostics
print("\n--- NOMIC EMBEDDING DIAGNOSTICS ---")
print(f"Total Database Vectors: {len(embeddings_raw)}")

vectors = []
for name, blob in embeddings_raw:
    vec = np.frombuffer(blob, dtype=np.float32)
    vectors.append(vec)

matrix = np.array(vectors)
print(f"Matrix Shape:      {matrix.shape} (Repos x Dims)")
print(f"Vector Dimensions: {matrix.shape[1]}")
print(f"L2 Norm Mean:      {np.linalg.norm(matrix, axis=1).mean():.4f}")
print("=========================================================")
