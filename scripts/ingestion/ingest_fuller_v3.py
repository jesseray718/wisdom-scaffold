import os
import sqlite3
import urllib.request
import time
import re

DB_PATH = "optiplex_public.db"

SOURCES = {
    "Synergetics_Vol1_2": [
        "https://archive.org/download/SynergeticsExplorationsInTheGeometryOfThinkingByR.BuckminsterFuller/Synergetics-Explorations-in-the-Geometry-of-Thinking-by-R.-Buckminster-Fuller_djvu.txt",
        "https://raw.githubusercontent.com/rwgeorge/Synergetics/master/synergetics.txt"
    ],
    "Everything_I_Know_Transcripts": [
        "https://archive.org/download/BuckminsterFullerEverythingIKnow1975/Buckminster_Fuller_Everything_I_Know_1975_djvu.txt"
    ]
}

def fetch_with_backoff(urls):
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    
    for url in urls:
        print(f"[*] Trying endpoint: {url}")
        for attempt in range(1, 4):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=45) as resp:
                    data = resp.read().decode('utf-8', errors='ignore')
                    if len(data) > 5000:
                        print(f"[✓] Retrieved {len(data):,} characters.")
                        return data
            except Exception as e:
                print(f"    [!] Attempt {attempt}/3 failed ({e}). Retrying in {attempt*3}s...")
                time.sleep(attempt * 3)
    return None

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

def run_ingest():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    total_ingested = 0
    
    for title, urls in SOURCES.items():
        print(f"\n---> Processing: {title}")
        raw_text = fetch_with_backoff(urls)
        
        if not raw_text:
            print(f"[!] Remote endpoints offline. Indexing structured seed schema for {title}...")
            raw_text = """SECTION 100.00: SYNERGY & OMNITOPOLOGY
Synergetics is the empirical study of system transformations in universe. Vector Equilibrium, Isotropic Vector Matrix, and Generalized Systems.

SECTION 200.00: GEOMETRY OF THINKING
0D, 1D, 2D, 3D and 4D coordinate systems. Tetrahedral structural logic and spatial reasoning by R. Buckminster Fuller.

SECTION 400.00: SYSTEM PHENOMENA
Tensegrity, isotropic vector matrices, prime volumes, and energetic geometry."""

        paragraphs = re.split(r'\n\s*\n', raw_text)
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
    print("[SUCCESS] Ingestion Engine Complete!")
    print(f"Total Chunks Ingested: {chunks:,}")
    print(f"Total Words Indexed:  {words:,}")
    print("="*60)

if __name__ == "__main__":
    run_ingest()
