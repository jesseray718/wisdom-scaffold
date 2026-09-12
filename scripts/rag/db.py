#!/usr/bin/env python3
from __future__ import annotations
import math, sqlite3, struct
try:
    import sqlite_vec
except Exception:
    sqlite_vec = None

def serialize_f32(vector):
    return struct.pack(f"<{len(vector)}f", *vector)

def deserialize_f32(blob):
    n = len(blob) // 4
    return list(struct.unpack(f"<{n}f", blob[:n*4]))

def cosine(a, b):
    n = min(len(a), len(b))
    if n <= 0:
        return -1.0
    dot = na = nb = 0.0
    for i in range(n):
        dot += a[i]*b[i]; na += a[i]*a[i]; nb += b[i]*b[i]
    if na <= 0.0 or nb <= 0.0:
        return -1.0
    return dot / math.sqrt(na*nb)

class DatabaseManager:
    def __init__(self, db_path="/home/jesse/wisdom-scaffold/data/hybrid_fast.db", embed_dim=768):
        self.db_path = db_path
        self.embed_dim = embed_dim
        self.use_vec0 = False

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        if sqlite_vec is not None:
            try:
                conn.enable_load_extension(True)
                sqlite_vec.load(conn)
                conn.enable_load_extension(False)
                self.use_vec0 = True
            except Exception:
                self.use_vec0 = False
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA mmap_size=268435456;")
        return conn

    def setup_schema(self):
        with self.get_connection() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL);""")
            conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
                content, content='documents', content_rowid='id',
                tokenize='porter unicode61');""")
            conn.execute("""CREATE TABLE IF NOT EXISTS docs_vec_blob (
                document_id INTEGER PRIMARY KEY, embedding BLOB NOT NULL);""")
            if self.use_vec0:
                conn.execute(f"""CREATE VIRTUAL TABLE IF NOT EXISTS docs_vec USING vec0(
                    document_id INTEGER PRIMARY KEY,
                    embedding float[{self.embed_dim}]);""")
            conn.execute("""CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                INSERT INTO docs_fts(rowid, content) VALUES (new.id, new.content);
            END;""")
            conn.commit()

    def batch_insert(self, records):
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("BEGIN;")
            for title, content, embedding in records:
                cur.execute("INSERT INTO documents (title, content) VALUES (?, ?)", (title, content))
                doc_id = cur.lastrowid
                blob = serialize_f32(embedding)
                cur.execute("INSERT INTO docs_vec_blob(document_id, embedding) VALUES (?, ?)", (doc_id, blob))
                if self.use_vec0:
                    cur.execute("INSERT INTO docs_vec(document_id, embedding) VALUES (?, ?)", (doc_id, blob))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def hybrid_search(self, query_text, query_vector, top_k=5, rrf_k=60):
        conn = self.get_connection()
        cur = conn.cursor()
        tokens = [t for t in query_text.replace('"',' ').split() if t]
        match = " ".join(tokens) if tokens else query_text
        try:
            fts_rows = cur.execute(
                "SELECT rowid, rank FROM docs_fts WHERE docs_fts MATCH ? ORDER BY rank LIMIT 20",
                (match,)).fetchall()
        except sqlite3.DatabaseError:
            fts_rows = []
        vec_ids = []
        if self.use_vec0:
            try:
                vec_rows = cur.execute(
                    "SELECT document_id, distance FROM docs_vec WHERE embedding MATCH ? AND k = 20 ORDER BY distance",
                    (serialize_f32(query_vector),)).fetchall()
                vec_ids = [int(r[0]) for r in vec_rows]
            except sqlite3.DatabaseError:
                vec_ids = []
        if not vec_ids:
            scored = []
            for row in cur.execute("SELECT document_id, embedding FROM docs_vec_blob"):
                scored.append((cosine(query_vector, deserialize_f32(row[1])), int(row[0])))
            scored.sort(reverse=True)
            vec_ids = [i for _, i in scored[:20]]
        scores = {}
        for rank, row in enumerate(fts_rows):
            scores[int(row[0])] = scores.get(int(row[0]), 0.0) + (1.0 / (rrf_k + rank + 1))
        for rank, doc_id in enumerate(vec_ids):
            scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (rrf_k + rank + 1))
        results = []
        for doc_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]:
            row = cur.execute("SELECT id, title, content FROM documents WHERE id=?", (doc_id,)).fetchone()
            if row:
                results.append({"id": int(row[0]), "title": row[1], "content": row[2], "rrf_score": score})
        conn.close()
        return results

def init_db(path: str) -> sqlite3.Connection:
    db_manager = DatabaseManager(db_path=path)
    db_manager.setup_schema()
    return db_manager.get_connection()
