#!/usr/bin/env python3
from __future__ import annotations
def rrf_add(scores, ranked_ids, k=60):
    for rank, doc_id in enumerate(ranked_ids, start=1):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores
def rrf_fuse(lists, k=60):
    scores = {}
    for ranked in lists:
        rrf_add(scores, ranked, k=k)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
def fuse_fts_vec(fts_hits, vec_hits, k=60):
    fts_ids = [h["id"] for h in sorted(fts_hits, key=lambda h: h.get("fts_rank", 10**9))]
    vec_ids = [i for i, _s in sorted(vec_hits, key=lambda x: x[1], reverse=True)]
    return rrf_fuse([fts_ids, vec_ids], k=k)
if __name__ == "__main__":
    print(fuse_fts_vec(
        [{"id":"A","fts_rank":1},{"id":"B","fts_rank":2},{"id":"C","fts_rank":3}],
        [("C",0.9),("A",0.7),("D",0.6)],
    ))
