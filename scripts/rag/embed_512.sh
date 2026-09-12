#!/bin/bash
set -e
DB=/home/jesse/wisdom-scaffold/data/optiplex_index.db
LOG=/home/jesse/wisdom-scaffold/data/embed_512.log
cd /home/jesse/wisdom-scaffold/scripts/rag
echo "==== $(date -Iseconds) start 512 ====" >> "$LOG"
python3 /home/jesse/wisdom-scaffold/scripts/rag/maintain_stores.py embed 512 >> "$LOG" 2>&1
echo "==== $(date -Iseconds) done ====" >> "$LOG"
tail -n 8 "$LOG"
