#!/usr/bin/env bash
set -euo pipefail
echo "=== HOST ==="; hostname; whoami
echo "=== PORTS ==="
ss -lntup 2>/dev/null | grep -E ':(8080|11434|5000|1234|8000)\s' || true
echo "=== OLLAMA ==="
curl -sS -m 2 http://127.0.0.1:11434/api/tags || echo DOWN_11434
command -v ollama && ollama list || true
echo "=== LLAMA-SERVER ==="
curl -sS -m 2 http://127.0.0.1:8080/health || curl -sS -m 2 http://127.0.0.1:8080/v1/models || echo DOWN_8080
echo "=== DB CANDIDATES ==="
find /home/jesse -maxdepth 4 \( -name '*.db' -o -name '*.sqlite' \) \
  -not -path '*/.git/*' -not -path '*/.venv/*' \
  -printf '%TY-%Tm-%Td %TH:%TM %10s %p\n' 2>/dev/null | sort
echo "=== CANON ==="
for p in \
  /home/jesse/openroot/agape_kb/agape_vector_index.db \
  /home/jesse/optiplex_index.db \
  /home/jesse/wisdom-scaffold/wisdom_rag.db \
  /home/jesse/wisdom-scaffold/secrets_vault.db \
  /home/jesse/wisdom-scaffold/all_notes_repos.db \
  /home/jesse/knowledge-node/knowledge.db \
  /home/jesse/openroot/agape_vector_index.py \
  /home/jesse/wisdom-scaffold/index_content_blobs.py \
  /home/jesse/models/gguf
do
  if [ -e "$p" ]; then echo "HIT  $p"; ls -lh "$p"; else echo "MISS $p"; fi
done
python3 - << 'PY'
import os, sqlite3, glob
paths=set()
for p in [
 "/home/jesse/openroot/agape_kb/agape_vector_index.db",
 "/home/jesse/optiplex_index.db",
 "/home/jesse/wisdom-scaffold/wisdom_rag.db",
 "/home/jesse/wisdom-scaffold/secrets_vault.db",
 "/home/jesse/wisdom-scaffold/all_notes_repos.db",
 "/home/jesse/knowledge-node/knowledge.db",
]:
    if os.path.isfile(p): paths.add(p)
for p in glob.glob("/home/jesse/**/*.db", recursive=True):
    if any(x in p for x in ("/.git/","/.venv/","/node_modules/")): continue
    if os.path.isfile(p): paths.add(p)
for path in sorted(paths):
    print("\n########", path, os.path.getsize(path), "########")
    try:
        con=sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        for name,sql in con.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"):
            print("--", name); print(sql)
            if name.startswith("sqlite_"): continue
            try:
                n=con.execute(f"SELECT COUNT(*) FROM '{name}'").fetchone()[0]
                cols=[c[1] for c in con.execute(f"PRAGMA table_info('{name}')")]
                print("  rows", n, "cols", cols)
            except Exception as e:
                print("  err", e)
        con.close()
    except Exception as e:
        print("open", e)
PY
