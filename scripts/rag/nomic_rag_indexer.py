import json
import os
import sqlite3
import urllib.error
import urllib.request
import numpy as np

DB_PATH = "/home/jesse/wisdom-scaffold/data/optiplex_index.db"
NOMIC_MODEL = "nomic-embed-text"
OLLAMA_URL = "http://localhost:11434/api/embed"


def get_nomic_embedding(text):
    """Generates an 8192-token context vector via Ollama's REST API."""
    payload = json.dumps({"model": NOMIC_MODEL, "input": text}).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            # API returns a list of embeddings under 'embeddings'
            if "embeddings" in data and len(data["embeddings"]) > 0:
                return np.array(data["embeddings"][0], dtype=np.float32)
    except Exception as e:
        print(f" [API ERROR] Failed to embed text: {e}")
        return None


def run_nomic_indexing():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nomic_embeddings (
            repo_name TEXT PRIMARY KEY,
            embedding BLOB,
            text_payload TEXT,
            FOREIGN KEY(repo_name) REFERENCES github_repos(name)
        );
    """)

    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, audit_notes, file_tree_json FROM github_repos;"
    )
    repos = cursor.fetchall()

    print(
        f"--> Generating Nomic embeddings for {len(repos)} repos via REST API..."
    )

    embedded_count = 0
    for name, notes, tree_json in repos:
        files = json.loads(tree_json) if tree_json else []
        payload = f"Repository: {name}\nNotes: {notes}\nStructure:\n" + "\n".join(
            files[:50]
        )

        vec = get_nomic_embedding(payload)
        if vec is not None:
            cursor.execute(
                """
                INSERT OR REPLACE INTO nomic_embeddings (repo_name, embedding, text_payload)
                VALUES (?, ?, ?)
            """,
                (name, sqlite3.Binary(vec.tobytes()), payload),
            )
            embedded_count += 1
            print(f" [✓] Embedded {name}")

    conn.commit()
    conn.close()
    print(
        f"\n=== Nomic Semantic RAG Index Complete ({embedded_count}/{len(repos)} repos indexed) ==="
    )


if __name__ == "__main__":
    run_nomic_indexing()

