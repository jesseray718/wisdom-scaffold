import hashlib
import os
import sqlite3
import sys

# Configuration for OptiPlex intake directories
# UPDATE THESE TO REAL PATHS ON YOUR OPTIPLEX:
WATCH_DIRS = ["/home/jesse/markor", "/home/jesse/terminal-logs"]
DB_PATH = "/home/jesse/optiplex_index.db"
DRY_RUN = True  # Flip to False for automatic unlink/removal

CHUNK_SIZE = 65536  # 64KB read buffers


def init_sqlite_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE,
            size INTEGER,
            hash TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hash ON file_index(hash);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_size ON file_index(size);")
    conn.commit()
    return conn


def calculate_sha256(file_path):
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (PermissionError, FileNotFoundError):
        return None


def run_dedupe_intake():
    conn = init_sqlite_db(DB_PATH)
    cursor = conn.cursor()

    bytes_reclaimed = 0
    duplicates_removed = 0

    print(
        f"[OptiPlex Dedupe Engine] Starting intake scan... (DRY_RUN={DRY_RUN})"
    )

    for watch_dir in WATCH_DIRS:
        if not os.path.exists(watch_dir):
            print(f"[WARN] Directory not found: {watch_dir}")
            continue

        for root, _, files in os.walk(watch_dir):
            for file in files:
                file_path = os.path.join(root, file)

                if not os.path.isfile(file_path) or os.path.islink(file_path):
                    continue

                file_size = os.path.getsize(file_path)

                # Step 1: Check SQLite for potential size matches first (Fast Pruning)
                cursor.execute(
                    "SELECT path, hash FROM file_index WHERE size = ? AND path != ?",
                    (file_size, file_path),
                )
                candidates = cursor.fetchall()

                if not candidates:
                    # Unique size -> calculate hash & index immediately
                    file_hash = calculate_sha256(file_path)
                    if file_hash:
                        cursor.execute(
                            "INSERT OR REPLACE INTO file_index (path, size, hash) VALUES (?, ?, ?)",
                            (file_path, file_size, file_hash),
                        )
                    continue

                # Step 2: Size collision found -> calculate SHA-256
                file_hash = calculate_sha256(file_path)
                if not file_hash:
                    continue

                # Check if exact hash exists in database
                cursor.execute(
                    "SELECT path FROM file_index WHERE hash = ? AND path != ?",
                    (file_hash, file_path),
                )
                match = cursor.fetchone()

                if match:
                    existing_original = match[0]
                    duplicates_removed += 1
                    bytes_reclaimed += file_size

                    if DRY_RUN:
                        print(
                            f"[DRY-RUN] Found duplicate:\n  New: {file_path}\n  Original: {existing_original}\n"
                        )
                    else:
                        try:
                            os.remove(file_path)
                            print(
                                f"[REMOVED] {file_path} (Matches {existing_original})"
                            )
                        except OSError as e:
                            print(f"[ERROR] Failed deleting {file_path}: {e}")
                else:
                    # New hash -> register in index
                    cursor.execute(
                        "INSERT OR REPLACE INTO file_index (path, size, hash) VALUES (?, ?, ?)",
                        (file_path, file_size, file_hash),
                    )

    conn.commit()
    conn.close()

    mb_saved = bytes_reclaimed / (1024 * 1024)
    print(
        f"[OptiPlex Dedupe Engine] Scan complete. Duplicates: {duplicates_removed} | Space Reclaimed: {mb_saved:.2f} MB"
    )


if __name__ == "__main__":
    run_dedupe_intake()
