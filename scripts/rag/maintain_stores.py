#!/usr/bin/env python3
import hashlib, json, os, sqlite3, struct, sys, time, urllib.request
RES="/home/jesse/wisdom-scaffold/data/optiplex_index.db"
LOG="/home/jesse/wisdom-scaffold/data/logs_index.db"
SEC="/home/jesse/wisdom-scaffold/data/secrets.db"
JUNK=("/logs/git-fleet/","/logs/","/stamps/","/__pycache__/","/.git/","/.venv/","/node_modules/","/.aider.tags.cache","/sync-conflict-")
SECRETS=("/.ssh/","/.gnupg/","id_ed25519","id_rsa",".env","credentials","api_key","apikey","secret_key","OPENROUTER_API_KEY","wallet.dat","auth.json","token.json")
def bucket(path):
    p=path.replace("\\","/")
    pl=p.lower()
    if any(s.lower() in pl for s in SECRETS): return "secrets"
    if any(s in p for s in JUNK): return "logs"
    return "research"
def separate():
    src=sqlite3.connect(RES); logs=sqlite3.connect(LOG); sec=sqlite3.connect(SEC)
    logs.executescript("""PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS file_chunks(id INTEGER PRIMARY KEY AUTOINCREMENT,file_path TEXT,chunk_index INTEGER,chunk_text TEXT);
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(file_path,chunk_text,content='file_chunks',content_rowid='id',tokenize='porter unicode61');
    CREATE TRIGGER IF NOT EXISTS file_chunks_ai AFTER INSERT ON file_chunks BEGIN
      INSERT INTO chunks_fts(rowid,file_path,chunk_text) VALUES(new.id,new.file_path,new.chunk_text); END;
    CREATE TRIGGER IF NOT EXISTS file_chunks_ad AFTER DELETE ON file_chunks BEGIN
      INSERT INTO chunks_fts(chunks_fts,rowid,file_path,chunk_text) VALUES('delete',old.id,old.file_path,old.chunk_text); END;""")
    sec.executescript("""PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS secret_refs(id INTEGER PRIMARY KEY AUTOINCREMENT,file_path TEXT UNIQUE,sha256 TEXT,bytes INTEGER,note TEXT,seen_at TEXT DEFAULT (datetime('now')));""")
    rows=src.execute("SELECT id,file_path,chunk_index,chunk_text FROM file_chunks").fetchall()
    drop=[]; nlog=nsec=nkeep=0
    for cid,path,idx,text in rows:
        b=bucket(path)
        if b=="research": nkeep+=1; continue
        if b=="logs":
            logs.execute("INSERT INTO file_chunks(file_path,chunk_index,chunk_text) VALUES(?,?,?)",(path,idx,text)); nlog+=1
        else:
            body=(text or "").encode("utf-8","ignore")
            sec.execute("INSERT OR IGNORE INTO secret_refs(file_path,sha256,bytes,note) VALUES(?,?,?,?)",
                        (path,hashlib.sha256(body).hexdigest(),len(body),"body removed from research index")); nsec+=1
        drop.append(cid)
    logs.commit(); sec.commit()
    src.executemany("DELETE FROM file_chunk_embeddings WHERE chunk_id=?",[(i,) for i in drop])
    src.executemany("DELETE FROM file_chunks WHERE id=?",[(i,) for i in drop])
    src.commit()
    try: os.chmod(SEC,0o600)
    except OSError: pass
    print("research",src.execute("SELECT COUNT(*) FROM file_chunks").fetchone()[0],"kept_scan",nkeep)
    print("logs",LOG,"chunks",logs.execute("SELECT COUNT(*) FROM file_chunks").fetchone()[0],"moved",nlog)
    print("secrets",SEC,"refs",sec.execute("SELECT COUNT(*) FROM secret_refs").fetchone()[0],"moved",nsec)
    src.close(); logs.close(); sec.close()
def ollama():
    try:
        names=[m.get("name","") for m in json.loads(urllib.request.urlopen("http://127.0.0.1:11434/api/tags",timeout=3).read()).get("models",[])]
        return any("nomic" in n for n in names)
    except Exception:
        return False
def embed_one(text):
    req=urllib.request.Request("http://127.0.0.1:11434/api/embeddings",
        data=json.dumps({"model":"nomic-embed-text","prompt":(text or "")[:2000]}).encode(),
        headers={"Content-Type":"application/json"})
    vec=json.loads(urllib.request.urlopen(req,timeout=30).read().decode()).get("embedding")
    if not vec: return None
    return struct.pack("<%df"%len(vec),*[float(x) for x in vec])
def embed(limit=0):
    if not ollama():
        print("FAIL nomic dark on 11434"); return 2
    con=sqlite3.connect(RES)
    miss=con.execute("SELECT c.id,c.file_path,c.chunk_text FROM file_chunks c LEFT JOIN file_chunk_embeddings e ON e.chunk_id=c.id WHERE e.chunk_id IS NULL").fetchall()
    todo=[(i,p,t) for i,p,t in miss if bucket(p)=="research"]
    if limit: todo=todo[:limit]
    print("missing",len(miss),"will_embed",len(todo))
    done=0; t0=time.time()
    for cid,path,text in todo:
        try: blob=embed_one(text)
        except Exception as e:
            print("embed_err",e); continue
        if not blob: continue
        con.execute("INSERT OR REPLACE INTO file_chunk_embeddings(chunk_id,embedding) VALUES(?,?)",(cid,blob))
        done+=1
        if done%25==0:
            con.commit()
            print("embedded",done,"/",len(todo),"per_s",round(done/max(time.time()-t0,0.001),2))
    con.commit()
    print("embeddings",con.execute("SELECT COUNT(*) FROM file_chunk_embeddings").fetchone()[0],
          "chunks",con.execute("SELECT COUNT(*) FROM file_chunks").fetchone()[0])
    con.close(); return 0
cmd=sys.argv[1] if len(sys.argv)>1 else "help"
if cmd=="separate": raise SystemExit(separate() or 0)
if cmd=="embed":
    lim=int(sys.argv[2]) if len(sys.argv)>2 else 0
    raise SystemExit(embed(lim))
print("usage: maintain_stores.py separate|embed [limit]")
