import sqlite3
import numpy as np
import os
import sys
import json
from nomic import embed

DB_PATH = "/home/jesse/optiplex_index.db"

def retrieve_context(query_text, top_k=5):
    """Generates real Nomic embeddings and fetches top matching repos/files from SQLite."""
    print(f"--> [Local 7B / Nomic] Embedding Query: '{query_text}'")
    
    # 1. Embed query via Nomic
    output = embed.text(
        texts=[query_text],
        model="nomic-embed-text-v1.5",
        task_type="search_query"
    )
    query_vec = np.array(output['embeddings'][0], dtype=np.float32)

    # 2. Query SQLite Vector Store
    if not os.path.exists(DB_PATH):
        print(f"[-] Database not found at {DB_PATH}")
        return []

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT repo_name, embedding FROM nomic_embeddings;")
    rows = cursor.fetchall()
    
    if not rows:
        print("[-] No vector rows found in database.")
        conn.close()
        return []

    repo_names = []
    matrix_list = []

    for name, blob in rows:
        vec = np.frombuffer(blob, dtype=np.float32)
        if vec.shape[0] == query_vec.shape[0]:
            repo_names.append(name)
            matrix_list.append(vec)

    matrix = np.array(matrix_list)
    query_norm = query_vec / np.linalg.norm(query_vec)
    scores = np.dot(matrix, query_norm)

    top_indices = np.argsort(scores)[::-1][:top_k]
    
    retrieved_nodes = []
    for idx in top_indices:
        repo_name = repo_names[idx]
        score = float(scores[idx])
        
        # Pull repo metadata / file list from SQLite
        cursor.execute("SELECT audit_notes FROM github_repos WHERE name = ?;", (repo_name,))
        note_row = cursor.fetchone()
        notes = note_row[0] if note_row else "No audit notes available."
        
        retrieved_nodes.append({
            "repo": repo_name,
            "similarity": round(score, 4),
            "audit_notes": notes
        })

    conn.close()
    return retrieved_nodes

def build_cloud_payload(query, retrieved_context):
    """Formats the retrieved RAG context into a zero-fluff prompt payload for Cloud Mega Models."""
    prompt = f"""[SYSTEM CONTEXT - LOCAL REPOSITORY RAG INDEX]
You are acting as the primary high-parameter reasoning engine for the OpenRoot / Wisdom-Scaffold architecture.
Below is relevant context retrieved from the local SQLite Nomic vector database:

--- RETRIEVED CONTEXT ---
{json.dumps(retrieved_context, indent=2)}

--- USER QUERY ---
{query}

--- INSTRUCTIONS ---
Analyze the user request using the provided repository context. Provide complete, ready-to-execute architectural solutions or code modules without omitting critical logic.
"""
    return prompt

if __name__ == "__main__":
    user_query = sys.argv[1] if len(sys.argv) > 1 else "How do we unify AeroCement thermal loops with the openroot mesh protocol?"
    
    # Step 1: Local RAG Retrieval
    matches = retrieve_context(user_query, top_k=5)
    
    # Step 2: Assemble Cloud Prompt
    payload = build_cloud_payload(user_query, matches)
    
    # Output constructed payload directly to stdout (or save to file for curl/python dispatch)
    print("\n=== CONSTRUCTED CLOUD API PAYLOAD ===")
    print(payload)
    
    with open("cloud_payload.txt", "w") as f:
        f.write(payload)
    print("\n[+] Payload saved to 'cloud_payload.txt'. Ready to dispatch to external mega model APIs.")
