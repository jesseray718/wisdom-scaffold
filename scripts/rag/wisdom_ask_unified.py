#!/usr/bin/env python3
"""
WISDOM UNIFIED ASK ENGINE
- Fast question → answer with citation
- Local inference only (nomic + 7B)
- Junk filter at query time
- Operator memory integration
- Parallel FTS + embedding
"""

import json
import math
import sqlite3
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# ============================================================================
# CONFIG
# ============================================================================

RESEARCH_DB = "/home/jesse/wisdom-scaffold/data/optiplex_index.db"
EVENTS_DB = "/home/jesse/wisdom-scaffold/data/operator_memory.db"

OLLAMA_EMB = "http://127.0.0.1:11434/api/embeddings"
LLM_ENDPOINT = "http://127.0.0.1:8080/v1/chat/completions"

MODEL_EMB = "nomic-embed-text"
MODEL_LLM = "qwen2.5-coder-7b"

# Junk path patterns (lowercase)
JUNK_PATTERNS = {
    "/stamps/",
    "/logs/",
    "git-fleet",
    "__pycache__",
    ".git/",
    "node_modules/",
}

# File type preferences (score multiplier)
FILE_TYPE_BOOST = {
    ".py": 2.0,
    ".md": 1.8,
    ".json": 1.0,
    ".txt": 1.0,
    ".yaml": 1.5,
}

TIMEOUT_NOMIC = 30
TIMEOUT_7B = 180

# ============================================================================
# UTILITIES
# ============================================================================


def is_junk_path(path: str) -> bool:
    """Quick filter for known junk directories."""
    path_lower = path.lower()
    return any(pattern in path_lower for pattern in JUNK_PATTERNS)


def get_file_boost(path: str) -> float:
    """Return relevance boost for file type."""
    for ext, boost in FILE_TYPE_BOOST.items():
        if path.endswith(ext):
            return boost
    return 1.0


def embed_query(query: str, task: str = "search_query") -> list[float] | None:
    """Embed a query via local nomic."""
    try:
        req = urllib.request.Request(
            OLLAMA_EMB,
            data=json.dumps(
                {"model": MODEL_EMB, "prompt": f"{task}: {query}"}
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_NOMIC) as r:
            return json.loads(r.read())["embedding"]
    except Exception as e:
        print(f"[EMBED ERROR] {e}", file=sys.stderr)
        return None


def cosine_similarity(a: list[float], b: bytes) -> float:
    """Compute cosine between query vector and stored blob."""
    import struct
    try:
        # Blob is stored as binary float32, 768 dims
        if len(b) < 768 * 4:
            return -1.0

        # Unpack 768 floats
        v = struct.unpack("<768f", b[: 768 * 4])
        dot = sum(x * y for x, y in zip(a, v))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in v))
        return dot / (na * nb) if na and nb else -1.0
    except Exception:
        return -1.0


# ============================================================================
# FTS SEARCH (FAST PATH)
# ============================================================================


def fts_search(query: str, limit: int = 20) -> list[dict]:
    """
    Full-text search on research chunks.
    Returns list of {id, chunk_text, file_path, score}.
    Schema: file_chunks(id, file_path, chunk_index, chunk_text)
    """
    results = []
    try:
        conn = sqlite3.connect(f"file:{RESEARCH_DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

        # FTS5 hygiene: strip quotes, periods, colons
        clean_query = (
            query.replace('"', "").replace(".", "").replace(":", "").strip()
        )

        # Query FTS5 table - use rowid and rank() function correctly
        cursor = conn.execute(
            """
            SELECT 
                fc.id, 
                fc.chunk_text, 
                fc.file_path,
                chunks_fts.rank
            FROM chunks_fts
            JOIN file_chunks fc ON chunks_fts.rowid = fc.id
            WHERE chunks_fts MATCH ?
            ORDER BY chunks_fts.rank
            LIMIT ?
        """,
            (clean_query, limit),
        )

        rank_pos = 0
        for row in cursor:
            path = row["file_path"] or "unknown"
            if not is_junk_path(path):
                boost = get_file_boost(path)
                results.append(
                    {
                        "id": row["id"],
                        "text": row["chunk_text"],
                        "path": path,
                        "score": (1.0 / (1.0 + rank_pos)) * boost,
                        "source": "FTS",
                    }
                )
                rank_pos += 1

        conn.close()
    except Exception as e:
        print(f"[FTS ERROR] {e}", file=sys.stderr)

    return results


# ============================================================================
# NOMIC SEARCH (SEMANTIC PATH)
# ============================================================================


def nomic_search(query: str, limit: int = 20) -> list[dict]:
    """
    Semantic search via nomic embeddings.
    Returns list of {id, chunk_text, file_path, score}.
    """
    results = []
    q_vec = embed_query(query)
    if not q_vec:
        return results

    try:
        conn = sqlite3.connect(f"file:{RESEARCH_DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

        # Query all chunks with embeddings
        cursor = conn.execute(
            """
            SELECT fc.id, fc.chunk_text, fc.file_path, fce.embedding
            FROM file_chunks fc
            JOIN file_chunk_embeddings fce ON fc.id = fce.chunk_id
            WHERE fce.embedding IS NOT NULL
            LIMIT ?
        """,
            (limit * 5,),  # Fetch more, score locally
        )

        hits = []
        for row in cursor:
            path = row["file_path"] or "unknown"
            if is_junk_path(path):
                continue

            score = cosine_similarity(q_vec, row["embedding"])
            if score > 0.0:
                boost = get_file_boost(path)
                hits.append(
                    {
                        "id": row["id"],
                        "text": row["chunk_text"],
                        "path": path,
                        "score": score * boost,
                        "source": "NOMIC",
                    }
                )

        # Sort by boosted score
        hits.sort(key=lambda x: x["score"], reverse=True)
        results = hits[:limit]

        conn.close()
    except Exception as e:
        print(f"[NOMIC ERROR] {e}", file=sys.stderr)

    return results


# ============================================================================
# HYBRID ROUTING
# ============================================================================


def hybrid_search(query: str, fts_limit: int = 15, nomic_limit: int = 10) -> list[dict]:
    """
    Parallel FTS + NOMIC search, merge and deduplicate by ID.
    Fast: FTS completes in 60ms, nomic in 2-3s.
    """
    results_by_id = {}
    start = time.time()

    with ThreadPoolExecutor(max_workers=2) as executor:
        fts_future = executor.submit(fts_search, query, fts_limit)
        nomic_future = executor.submit(nomic_search, query, nomic_limit)

        # Collect FTS results (very fast, ~60ms)
        try:
            for hit in fts_future.result(timeout=1.0):
                cid = hit["id"]
                if cid not in results_by_id:
                    results_by_id[cid] = hit
                else:
                    # Combine scores
                    results_by_id[cid]["score"] = max(
                        results_by_id[cid]["score"], hit["score"]
                    )
                    results_by_id[cid]["source"] += "+FTS"
        except Exception as e:
            print(f"[FTS TIMEOUT/ERROR] {e}", file=sys.stderr)

        # Collect NOMIC results (2-3s)
        try:
            for hit in nomic_future.result(timeout=TIMEOUT_NOMIC):
                cid = hit["id"]
                if cid not in results_by_id:
                    results_by_id[cid] = hit
                else:
                    results_by_id[cid]["score"] = max(
                        results_by_id[cid]["score"], hit["score"]
                    )
                    results_by_id[cid]["source"] += "+NOMIC"
        except Exception as e:
            print(f"[NOMIC TIMEOUT/ERROR] {e}", file=sys.stderr)

    # Final sort
    merged = sorted(results_by_id.values(), key=lambda x: x["score"], reverse=True)
    elapsed = time.time() - start

    print(f"[HYBRID] {len(merged)} results in {elapsed:.2f}s", file=sys.stderr)
    return merged


# ============================================================================
# 7B SYNTHESIS
# ============================================================================


def synthesize_answer(query: str, context: list[dict], max_tokens: int = 120) -> str:
    """
    Call local 7B with context chunks + question.
    max_tokens: 80-120 for efficiency, 160+ for code.
    """
    if not context:
        return "No matching knowledge found."

    # Build context block
    context_text = "\n\n".join(
        [
            f"[{h['source']} #{h['id']}] {h['path']}\n{h['text'][:500]}"
            for h in context[:5]
        ]
    )

    prompt = f"""You are a helpful assistant with access to a wisdom corpus.
Answer the question using ONLY the provided context. If context is insufficient, say so.
Cite sources by mentioning the path and document ID.

CONTEXT:
{context_text}

QUESTION: {query}

ANSWER:"""

    try:
        req = urllib.request.Request(
            LLM_ENDPOINT,
            data=json.dumps(
                {
                    "model": MODEL_LLM,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.3,
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_7B) as r:
            resp = json.loads(r.read())
            answer = resp["choices"][0]["message"]["content"].strip()
            return answer
    except Exception as e:
        print(f"[7B ERROR] {e}", file=sys.stderr)
        return f"Synthesis failed: {e}"


# ============================================================================
# OPERATOR MEMORY (OPTIONAL)
# ============================================================================


def log_to_events(query: str, answer: str, sources: list[str]) -> None:
    """Optionally log to operator_memory.db for future refinement."""
    try:
        conn = sqlite3.connect(EVENTS_DB)
        # Check if events table exists and has the right schema
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
        )
        if not cursor.fetchone():
            conn.close()
            return  # Table doesn't exist, skip
        
        conn.execute(
            "INSERT INTO events(body, timestamp) VALUES(?, datetime('now'))",
            (json.dumps({"query": query, "answer": answer, "sources": sources}),),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[EVENTS LOG] {e}", file=sys.stderr)


# ============================================================================
# MAIN ENTRY
# ============================================================================


def ask(query: str, verbose: bool = False) -> dict:
    """
    End-to-end question answering.
    Returns {question, answer, sources, elapsed_time, context_count}.
    """
    start = time.time()

    # Step 1: Hybrid search (parallel FTS + NOMIC)
    context = hybrid_search(query)

    if verbose:
        print(f"\n[CONTEXT] Top {len(context)} results:", file=sys.stderr)
        for i, h in enumerate(context[:5]):
            print(
                f"  {i+1}. [{h['source']}] {h['path']} (score: {h['score']:.3f})",
                file=sys.stderr,
            )

    # Step 2: 7B synthesis
    answer = synthesize_answer(query, context)

    elapsed = time.time() - start
    sources = [h["path"] for h in context[:5]]

    result = {
        "question": query,
        "answer": answer,
        "sources": sources,
        "elapsed_seconds": elapsed,
        "context_count": len(context),
    }

    # Log to events for operator memory
    log_to_events(query, answer, sources)

    return result


# ============================================================================
# CLI
# ============================================================================


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 wisdom_ask_unified.py <question>")
        print("       python3 wisdom_ask_unified.py -v <question>  # verbose")
        sys.exit(1)

    verbose = sys.argv[1] == "-v"
    query = " ".join(sys.argv[2:] if verbose else sys.argv[1:])

    result = ask(query, verbose=verbose)

    # Pretty print
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
