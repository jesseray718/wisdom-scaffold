#!/usr/bin/env python3
"""
openroot_consolidate.py — Phase 1: Consolidate all files to OptiPlex hub
Scans, indexes, and prepares context for local LLM council.

Usage:
    python3 openroot_consolidate.py --scan-only     # Just scan local files
    python3 openroot_consolidate.py --backup-phone   # Backup A15 via ADB
    python3 openroot_consolidate.py --pull-cloud     # Pull from cloud servers
    python3 openroot_consolidate.py --all            # Do everything
    python3 openroot_consolidate.py --feed-llm        # Feed index to Ollama
"""

import os
import sys
import json
import hashlib
import subprocess
import time
import argparse
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIGURATION — Adjust these paths to your setup
# ============================================================

HUB_DIR = Path.home() / "openroot_hub"
BACKUP_DIR = HUB_DIR / "backups"
PHONE_BACKUP_DIR = BACKUP_DIR / "a15_backup"
CLOUD_BACKUP_DIR = BACKUP_DIR / "cloud_servers"
INDEX_DIR = HUB_DIR / "index"
MANIFEST_PATH = INDEX_DIR / "manifest.json"
LLM_CONTEXT_PATH = INDEX_DIR / "llm_context.md"

# Cloud servers — fill in your details
CLOUD_SERVERS = [
    # {"name": "server1", "host": "user@ip", "remote_path": "/path/to/files", "key": "~/.ssh/id_rsa"},
    # {"name": "server2", "host": "user@domain", "remote_path": "/home/user/project", "key": "~/.ssh/key2"},
]

# Ollama settings
OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "llama3.2"  # Change to whatever you pulled

# File extensions we care about for content extraction
TEXT_EXTS = {".py", ".sh", ".js", ".ts", ".md", ".txt", ".json", ".yaml", ".yml",
             ".toml", ".cfg", ".conf", ".ini", ".html", ".css", ".sql", ".r",
             ".c", ".cpp", ".h", ".rs", ".go", ".rb", ".php", ".swift", ".kt",
             ".java", ".scala", ".clj", ".exs", ".ex", ".erl", ".lua", ".vim",
             ".gitignore", ".dockerfile", ".env"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
             ".openroot_venv", "site-packages", ".cache", ".npm", ".local"}

# ============================================================
# UTILITIES
# ============================================================

def banner(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}")

def ensure_dirs():
    for d in [HUB_DIR, BACKUP_DIR, PHONE_BACKUP_DIR, CLOUD_BACKUP_DIR, INDEX_DIR]:
        d.mkdir(parents=True, exist_ok=True)

def file_hash(filepath, algo="sha256", max_bytes=10*1024*1024):
    """Hash first 10MB of a file for dedup identification."""
    h = hashlib.new(algo)
    try:
        with open(filepath, "rb") as f:
            h.update(f.read(max_bytes))
        return h.hexdigest()[:16]  # Truncated for manifest efficiency
    except (IOError, PermissionError):
        return "unreadable"

def extract_text_preview(filepath, max_chars=500):
    """Extract first N characters of text from a file."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read(max_chars).strip()
    except (IOError, PermissionError):
        return ""

def human_size(bytes_val):
    """Convert bytes to human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(bytes_val) < 1024.0:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f}PB"

# ============================================================
# PHASE 1a: BACKUP A15 VIA ADB
# ============================================================

def backup_phone_adb():
    """Backup Samsung A15 via ADB over USB."""
    banner("BACKUP A15 VIA ADB")
    
    # Check if ADB is installed
    result = subprocess.run(["which", "adb"], capture_output=True, text=True)
    if result.returncode != 0:
        log("ADB not found. Install with: sudo apt install adb", "ERROR")
        return False
    
    # Check for connected devices
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    log(f"ADB devices:\n{result.stdout}")
    
    if "device" not in result.stdout.split("\n")[1] if len(result.stdout.split("\n")) > 1 else True:
        log("No ADB device detected. Steps:", "WARN")
        log("  1. Connect A15 via USB cable")
        log("  2. Enable Developer Options: Settings → About Phone → Software Info → tap Build Number 7x")
        log("  5. Enable USB Debugging: Settings → Developer Options → USB Debugging")
        log("  4. Accept RSA key prompt on phone")
        return False
    
    # Key directories to pull from A15
    phone_sources = [
        ("/sdcard/openroot", str(PHONE_BACKUP_DIR / "openroot")),
        ("/sdcard/Download", str(PHONE_BACKUP_DIR / "downloads")),
        ("/sdcard/Documents", str(PHONE_BACKUP_DIR / "documents")),
        ("/sdcard/DCIM", str(PHONE_BACKUP_DIR / "photos")),
        ("/data/data/com.termux/files/home", str(PHONE_BACKUP_DIR / "termux_home")),
    ]
    
    for src, dst in phone_sources:
        log(f"Pulling {src} → {dst}")
        result = subprocess.run(
            ["adb", "pull", src, dst],
            capture_output=True, text=True, timeout=600
        )
        if result.returncode == 0:
            log(f"  ✓ {src} pulled successfully")
        else:
            log(f"  ✗ {src} failed: {result.stderr[:200]}", "WARN")
    
    log("Phone backup attempt complete.")
    return True

# ============================================================
# PHASE 1b: PULL CLOUD SERVER FILES
# ============================================================

def pull_cloud_files():
    """Pull files from remote cloud servers via rsync."""
    banner("PULL CLOUD SERVER FILES")
    
    if not CLOUD_SERVERS:
        log("No cloud servers configured. Edit CLOUD_SERVERS in this script.", "WARN")
        log("Format: {\"name\": \"srv1\", \"host\": \"user@1.2.3.4\", \"remote_path\": \"/path\", \"key\": \"~/.ssh/id_rsa\"}")
        return False
    
    for srv in CLOUD_SERVERS:
        dst = CLOUD_BACKUP_DIR / srv["name"]
        dst.mkdir(parents=True, exist_ok=True)
        key = os.path.expanduser(srv.get("key", "~/.ssh/id_rsa"))
        
        log(f"Pulling from {srv['name']} ({srv['host']})...")
        cmd = [
            "rsync", "-avz", "--progress",
            "-e", f"ssh -i {key} -o StrictHostKeyChecking=no",
            f"{srv['host']}:{srv['remote_path']}/",
            str(dst) + "/"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if result.returncode == 0:
            log(f"  ✓ {srv['name']} synced")
        else:
            log(f"  ✗ {srv['name']} failed: {result.stderr[:300]}", "WARN")
    
    return True

# ============================================================
# PHASE 2: SCAN AND INDEX ALL LOCAL FILES
# ============================================================

def scan_and_index():
    """Walk all directories under HUB_DIR and create a searchable manifest."""
    banner("SCAN AND INDEX ALL FILES")
    
    ensure_dirs()
    manifest = {
        "scan_time": datetime.now().isoformat(),
        "hub_dir": str(HUB_DIR),
        "total_files": 0,
        "total_size_bytes": 0,
        "by_type": {},
        "files": []
    }
    
    scan_paths = [HUB_DIR / "backups", Path.home() / "openroot"]
    
    for scan_root in scan_paths:
        if not scan_root.exists():
            log(f"Skip {scan_root} (does not exist)")
            continue
        
        log(f"Scanning {scan_root}...")
        file_count = 0
        
        for root, dirs, files in os.walk(scan_root):
            # Filter out skip directories in-place
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            
            for fname in files:
                fpath = Path(root) / fname
                try:
                    stat = fpath.stat()
                except (PermissionError, FileNotFoundError):
                    continue
                
                ext = fpath.suffix.lower()
                is_text = ext in TEXT_EXTS or not ext  # No ext might be scripts
                
                entry = {
                    "path": str(fpath),
                    "name": fname,
                    "ext": ext,
                    "size_bytes": stat.st_size,
                    "size_human": human_size(stat.st_size),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "hash_prefix": file_hash(fpath),
                    "is_text": is_text,
                    "preview": extract_text_preview(fpath) if is_text else "",
                }
                
                manifest["files"].append(entry)
                manifest["total_files"] += 1
                manifest["total_size_bytes"] += stat.st_size
                
                # Track by extension
                if ext not in manifest["by_type"]:
                    manifest["by_type"][ext] = {"count": 0, "total_bytes": 0}
                manifest["by_type"][ext]["count"] += 1
                manifest["by_type"][ext]["total_bytes"] += stat.st_size
                
                file_count += 1
                if file_count % 500 == 0:
                    log(f"  ...{file_count} files scanned")
        
        log(f"  {scan_root}: {file_count} files indexed")
    
    # Write manifest
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    log(f"Manifest written: {MANIFEST_PATH}")
    log(f"Total files: {manifest['total_files']}")
    log(f"Total size: {human_size(manifest['total_size_bytes'])}")
    
    # Print file type breakdown
    print(f"\n{'Extension':<12} {'Count':>8} {'Size':>12}")
    print("-" * 34)
    sorted_types = sorted(manifest["by_type"].items(),
                          key=lambda x: x[1]["total_bytes"], reverse=True)
    for ext, info in sorted_types[:20]:
        print(f"{ext or '(none)':<12} {info['count']:>8} {human_size(info['total_bytes']):>12}")
    
    return manifest

# ============================================================
# PHASE 3: BUILD LLM-READABLE CONTEXT FROM MANIFEST
# ============================================================

def build_llm_context(manifest):
    """Convert the manifest into a markdown summary the LLM can ingest."""
    banner("BUILD LLM CONTEXT DOCUMENT")
    
    lines = [
        "# OpenRoot Project — Full File Index",
        f"",
        f"_Generated: {manifest['scan_time']}_",
        f"_Hub: {manifest['hub_dir']}_",
        f"_Total files: {manifest['total_files']}_",
        f"_Total size: {human_size(manifest['total_size_bytes'])}_",
        "",
        "## File Type Breakdown",
        "",
    ]
    
    sorted_types = sorted(manifest["by_type"].items(),
                          key=lambda x: x[1]["total_bytes"], reverse=True)
    for ext, info in sorted_types[:30]:
        lines.append(f"- `{ext or '(none)'}`: {info['count']} files, {human_size(info['total_bytes'])}")
    
    lines.extend([
        "",
        "## Text Files with Previews",
        "",
    ])
    
    # Include previews of text files (code, scripts, docs)
    text_files = [f for f in manifest["files"] if f["is_text"] and f["preview"]]
    # Sort by most recently modified
    text_files.sort(key=lambda x: x["modified"], reverse=True)
    
    for tf in text_files[:500]:  # Cap at 500 to stay within token limits
        lines.extend([
            f"### {tf['path']}",
            f"_Size: {tf['size_human']}, Modified: {tf['modified']}_",
            "```",
            tf["preview"],
            "```",
            "",
        ])
    
    context = "\n".join(lines)
    with open(LLM_CONTEXT_PATH, "w") as f:
        f.write(context)
    
    log(f"LLM context written: {LLM_CONTEXT_PATH}")
    log(f"Context size: {human_size(len(context.encode()))}")
    log(f"Text files with previews: {len(text_files)}")
    
    return context

# ============================================================
# PHASE 4: FEED CONTEXT TO LOCAL OLLAMA FOR COUNCIL
# ============================================================

def feed_to_ollama(context):
    """Send the context to the running Ollama instance and ask for analysis."""
    banner("FEED CONTEXT TO LOCAL LLM")
    
    # Truncate context to fit within model context window
    # ~32k chars ≈ ~8k tokens, safe for most models
    max_chars = 30000
    if len(context) > max_chars:
        log(f"Context too large ({len(context)} chars), truncating to {max_chars}")
        context = context[:max_chars] + "\n\n[...truncated...]"
    
    prompt = f"""You are analyzing the OpenRoot project file structure for Jesse.

This is a consolidated index of all files across multiple devices (phone, cloud servers, local computer).
The goal is: maximum computational efficiency per unit of human effort, measured conceptually in joules per second.

Analyze this file inventory and provide:
1. **Structural Assessment**: What's the overall organization? Is it coherent or fragmented?
2. **Key Patterns**: What projects/scripts/themes are you seeing?
3. **Efficiency Bottlenecks**: Where are the wasted cycles? Duplicated files? Scattered configs?
4. **Consolidation Recommendations**: Concrete steps to merge everything into a clean GitHub-ready structure.
5. **Priority Ranking**: What should Jesse work on FIRST for maximum impact?

Here is the file index:

{context}

Provide your analysis now. Be concise and actionable."""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_ctx": 8192,
        }
    }
    
    import urllib.request
    import urllib.error
    
    log(f"Sending {len(prompt)} chars to Ollama ({OLLAMA_MODEL})...")
    
    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        log("Waiting for LLM response (this may take a minute)...")
        start_time = time.time()
        
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode())
            elapsed = time.time() - start_time
            
            response_text = result.get("response", "(no response)")
            
            print(f"\n{'='*60}")
            print("  LLM COUNCIL RESPONSE")
            print(f"{'='*60}")
            print(f"\n{response_text}\n")
            print(f"{'='*60}")
            print(f"  Response time: {elapsed:.1f}s")
            print(f"  Eval count: {result.get('eval_count', '?')} tokens")
            if elapsed > 0:
                print(f"  Tokens/sec: {result.get('eval_count', 0)/elapsed:.1f}")
            print(f"{'='*60}")
            
            # Save the response
            council_path = INDEX_DIR / "council_response.md"
            with open(council_path, "w") as f:
                f.write(f"# LLM Council Response\n\n")
                f.write(f"_Generated: {datetime.now().isoformat()}_\n")
                f.write(f"_Model: {OLLAMA_MODEL}_\n")
                f.write(f"_Response time: {elapsed:.1f}s_\n\n")
                f.write(response_text)
            log(f"Council response saved: {council_path}")
            
            return response_text
            
    except urllib.error.URLError as e:
        log(f"Cannot connect to Ollama: {e}", "ERROR")
        log("Make sure Ollama is running: ollama serve (or it's already running on port 11434)")
        return None
    except Exception as e:
        log(f"Error: {e}", "ERROR")
        return None

# ============================================================
# PHASE 5: DUPLICATE DETECTION (bonus efficiency scan)
# ============================================================

def find_duplicates(manifest):
    """Find duplicate files by hash prefix."""
    banner("DUPLICATE DETECTION")
    
    hash_map = {}
    for f in manifest["files"]:
        h = f["hash_prefix"]
        if h == "unreadable":
            continue
        if h not in hash_map:
            hash_map[h] = []
        hash_map[h].append(f)
    
    dupes = {h: files for h, files in hash_map.items() if len(files) > 1}
    
    if not dupes:
        log("No duplicates found.")
        return
    
    log(f"Found {len(dupes)} sets of duplicate files:")
    total_wasted = 0
    for h, files in dupes.items():
        wasted = sum(f["size_bytes"] for f in files[1:])
        total_wasted += wasted
        print(f"\n  Hash: {h} ({len(files)} copies, {human_size(wasted)} wasted)")
        for f in files:
            print(f"    {f['path']}")
    
    print(f"\nTotal wasted space from duplicates: {human_size(total_wasted)}")
    log(f"Dedupe opportunity: {human_size(total_wasted)} could be freed")

# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="OpenRoot Consolidation & AI Scan")
    parser.add_argument("--scan-only", action="store_true", help="Only scan and index local files")
    parser.add_argument("--backup-phone", action="store_true", help="Backup A15 via ADB")
    parser.add_argument("--pull-cloud", action="store_true", help="Pull files from cloud servers")
    parser.add_argument("--feed-llm", action="store_true", help="Feed index to Ollama for council")
    parser.add_argument("--all", action="store_true", help="Do everything in sequence")
    parser.add_argument("--duplicates", action="store_true", help="Find duplicate files")
    
    args = parser.parse_args()
    
    banner("OPENROOT CONSOLIDATION ENGINE")
    log(f"Hub directory: {HUB_DIR}")
    ensure_dirs()
    
    if args.all or args.backup_phone:
        backup_phone_adb()
    
    if args.all or args.pull_cloud:
        pull_cloud_files()
    
    if args.all or args.scan_only or args.feed_llm or args.duplicates:
        manifest = scan_and_index()
    else:
        # Load existing manifest if available
        if MANIFEST_PATH.exists():
            log("Loading existing manifest...")
            with open(MANIFEST_PATH) as f:
                manifest = json.load(f)
        else:
            log("No manifest found. Run with --scan-only first.", "ERROR")
            return
    
    if args.all or args.duplicates:
        find_duplicates(manifest)
    
    if args.all or args.feed_llm:
        context = build_llm_context(manifest)
        feed_to_ollama(context)
    
    if not any(vars(args).values()):
        parser.print_help()
        print("\nQuick start:")
        print("  python3 openroot_consolidate.py --scan-only     # Scan local files")
        print("  python3 openroot_consolidate.py --backup-phone   # Backup A15")
        print("  python3 openroot_consolidate.py --all            # Do everything")

if __name__ == "__main__":
    main()
