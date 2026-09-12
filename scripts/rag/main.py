#!/usr/bin/env python3
from __future__ import annotations
import os, time
from db import DatabaseManager
from services import EmbeddingService, LLMPipelineService

def main():
    db_file = "/home/jesse/wisdom-scaffold/data/hybrid_fast.db"
    os.makedirs("/home/jesse/wisdom-scaffold/data", exist_ok=True)
    if os.path.exists(db_file):
        os.remove(db_file)
    print("=== 1. Initializing SQLite FTS5 ===")
    db = DatabaseManager(db_path=db_file, embed_dim=768)
    db.setup_schema()
    embed_service = EmbeddingService()
    llm_service = LLMPipelineService()
    raw_docs = [
        ("SQLite FTS5", "FTS5 provides full-text search indexing capabilities to SQLite databases."),
        ("sqlite-vec Extension", "sqlite-vec offers fast vector similarity search inside SQLite."),
        ("Nomic Embeddings", "nomic-embed-text generates 768-dimensional context embeddings."),
        ("7B Coder Models", "Local 7B Coder models handle coding tasks and retrieval generation."),
        ("Hybrid Retrieval", "Reciprocal Rank Fusion merges FTS5 text ranks with vector distance ranks."),
    ]
    print("=== 2. Batch embedding and insert ===")
    t0 = time.perf_counter()
    texts = [d[1] for d in raw_docs]
    embeddings = embed_service.get_embeddings_batch(texts)
    records = [(raw_docs[i][0], raw_docs[i][1], embeddings[i]) for i in range(len(raw_docs))]
    db.batch_insert(records)
    print(f"ingested {len(records)} docs in {(time.perf_counter()-t0)*1000:.2f}ms")
    print("=== 3. Hybrid search ===")
    q = "vector search in SQLite database"
    qv = embed_service.get_embeddings_batch([q])[0]
    t1 = time.perf_counter()
    results = db.hybrid_search(query_text="vector search SQLite", query_vector=qv, top_k=3)
    print(f"hybrid_search {(time.perf_counter()-t1)*1000:.2f}ms")
    blocks = []
    for r in results:
        print(f" - [RRF {r['rrf_score']:.4f}] {r['title']}: {r['content']}")
        blocks.append(f"{r['title']}: {r['content']}")
    print("=== 4. LLM optional ===")
    ctx = "\n".join(blocks)
    task = "Demonstrate sqlite-vec table initialization."
    print("--- Local 7B ---")
    print(llm_service.query_7b_coder(task, ctx))
    print("--- Cloud ---")
    print(llm_service.query_cloud_model(task, ctx))

if __name__ == "__main__":
    main()
