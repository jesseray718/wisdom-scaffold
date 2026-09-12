import os
import subprocess
import sqlite3
import urllib.request
import re

DB_PATH = "optiplex_public.db"

def clean_system_memory():
    print("="*60)
    print("[1/3] SYSTEM MAINTENANCE: Cleaning RAM & Cache...")
    print("="*60)
    try:
        # Flush file system buffers to storage
        os.sync()
        print("[✓] Filesystem buffers synced to disk.")
        
        # Clear page cache, dentries, and inodes if running under sudo/root
        if os.geteuid() == 0:
            with open('/proc/sys/vm/drop_caches', 'w') as f:
                f.write('3\n')
            print("[✓] Linux RAM caches cleared (drop_caches = 3).")
        else:
            print("[!] Skipping privileged drop_caches (not running as root).")
            print("    Run 'sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches' manually if root RAM flush is needed.")
    except Exception as e:
        print(f"[!] RAM Maintenance Note: {e}")

def check_storage():
    print("\n" + "="*60)
    print("[2/3] STORAGE VERIFICATION: Storage Mounts & Free Space")
    print("="*60)
    try:
        df_output = subprocess.check_output(["df", "-h"], text=True)
        print(df_output)
    except Exception as e:
        print(f"[!] Storage check error: {e}")

# Working direct download URLs for raw text on Internet Archive
CORPUS_URLS = {
    "Synergetics_Vol1_2": "https://archive.org/download/SynergeticsExplorationsInTheGeometryOfThinkingByR.BuckminsterFuller/Synergetics-Explorations-in-the-Geometry-of-Thinking-by-R.-Buckminster-Fuller_djvu.txt",
    "Everything_I_Know_Transcripts": "https://archive.org/download/BuckminsterFullerEverythingIKnow1975/Buckminster_Fuller_Everything_I_Know_1975_djvu.txt"
}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('DROP TABLE IF EXISTS synergetics_fuller_corpus')
    cursor.execute('DROP TABLE IF EXISTS fuller_fts')

    cursor.execute('''
        CREATE TABLE synergetics_fuller_corpus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_title TEXT,
            section_heading TEXT,
            content TEXT,
            word_count INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE VIRTUAL TABLE fuller_fts USING fts5(
            source_title,
            section_heading,
            content,
            content='synergetics_fuller_corpus',
            content_rowid='id'
        )
    ''')
    
    conn.commit()
    conn.close()

def ingest_corpus():
    print("\n" + "="*60)
    print("[3/3] FULL-TEXT INGESTION: Buckminster Fuller Corpus")
    print("="*60)
    
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)'}
    total_ingested = 0
    
    for title, url in CORPUS_URLS.items():
        print(f"[*] Downloading {title}...")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw_data = resp.read().decode('utf-8', errors='ignore')
                print(f"[✓] Received {len(raw_data):,} characters.")
        except Exception as e:
            print(f"[!] Download failed for {title}: {e}")
            continue
            
        paragraphs = re.split(r'\n\s*\n', raw_data)
        current_chunk = []
        current_words = 0
        section_idx = 1
        
        for para in paragraphs:
            cleaned = para.strip()
            if not cleaned:
                continue
                
            words = len(cleaned.split())
            current_chunk.append(cleaned)
            current_words += words
            
            if current_words >= 400:
                full_block = "\n\n".join(current_chunk)
                heading = current_chunk[0][:80].replace("\n", " ")
                
                cursor.execute('''
                    INSERT INTO synergetics_fuller_corpus (source_title, section_heading, content, word_count)
                    VALUES (?, ?, ?, ?)
                ''', (title, f"Section {section_idx}: {heading}", full_block, current_words))
                
                row_id = cursor.lastrowid
                cursor.execute('''
                    INSERT INTO fuller_fts(rowid, source_title, section_heading, content)
                    VALUES (?, ?, ?, ?)
                ''', (row_id, title, f"Section {section_idx}: {heading}", full_block))
                
                total_ingested += 1
                section_idx += 1
                current_chunk = []
                current_words = 0
                
        if current_chunk:
            full_block = "\n\n".join(current_chunk)
            heading = current_chunk[0][:80].replace("\n", " ")
            cursor.execute('''
                INSERT INTO synergetics_fuller_corpus (source_title, section_heading, content, word_count)
                VALUES (?, ?, ?, ?)
            ''', (title, f"Section {section_idx}: {heading}", full_block, current_words))
            
            row_id = cursor.lastrowid
            cursor.execute('''
                INSERT INTO fuller_fts(rowid, source_title, section_heading, content)
                VALUES (?, ?, ?, ?)
            ''', (row_id, title, f"Section {section_idx}: {heading}", full_block))
            total_ingested += 1

    conn.commit()
    
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(word_count), 0) FROM synergetics_fuller_corpus")
    chunks, words = cursor.fetchone()
    conn.close()
    
    print("\n" + "="*60)
    print("[SUCCESS] Pipeline Complete!")
    print(f"Total Chunks Ingested: {chunks:,}")
    print(f"Total Words Indexed:  {words:,}")
    print("="*60)

if __name__ == "__main__":
    clean_system_memory()
    check_storage()
    ingest_corpus()
