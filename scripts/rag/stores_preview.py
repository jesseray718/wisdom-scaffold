#!/usr/bin/env python3
import sqlite3
from collections import Counter
DB = "/home/jesse/wisdom-scaffold/data/optiplex_index.db"
JUNK = ("/logs/", "/.git/", "/stamps/", "/__pycache__/", "/.venv/", "/node_modules/", "/git-fleet/", "/outbox/")
SECRET = ("/.ssh/", "id_ed25519", ".env", "api_key", "credentials", "token.json")
def bucket(path):
    p = (path or "").replace("\\", "/")
    pl = p.lower()
    if any(s.lower() in pl for s in SECRET):
        return "secrets"
    if any(s in p for s in JUNK):
        return "logs"
    return "research"
con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
c = Counter()
n = 0
for (path,) in con.execute("SELECT file_path FROM file_chunks"):
    c[bucket(path)] += 1
    n += 1
print("db", DB, "chunks", n)
for k, v in c.most_common():
    print("  %6d  %s" % (v, k))
