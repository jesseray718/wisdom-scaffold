import sqlite3
import urllib.request
import re

DB_PATH = "optiplex_public.db"

# Verified active mirrors for complete text files
SOURCES = {
    "Synergetics_Vol1_2": "https://raw.githubusercontent.com/rwgeorge/Synergetics/master/synergetics.txt",
    "Everything_I_Know_Transcripts": "https://raw.githubusercontent.com/masonic/everything-i-know/master/everything-i-know.txt"
}

# Reliable fallback mirrors if main repository links shift
MIRRORS = {
    "Synergetics_Vol1_2": "https://archive.org/stream/SynergeticsExplorationsInTheGeometryOfThinkingByR.BuckminsterFuller/Synergetics-Explorations-in-the-Geometry-of-Thinking-by-R.-Buckminster-Fuller_djvu.txt",
    "Everything_I_Know_Transcripts": "https://archive.org/stream/BuckminsterFullerEverythingIKnow1975/Buckminster_Fuller_Everything_I_Know_1975_djvu.txt"
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

def download_text(title):
    urls = [SOURCES.get(title), MIRRORS.get(title)]
    headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)'}
    
    for url in urls:
        if not url:
            continue
        try:
            print(f"[*] Fetching {title} from: {url}")
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read().decode('utf-8', errors='ignore')
                if len(data) > 10000:
                    print(f"[✓] Downloaded {len(data):,} characters.")
                    return data
        except Exception as e:
            print(f"[!] Endpoint failed ({e}). Trying next mirror...")
            
    return None

def ingest():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    total_ingested = 0
    
    for title in ["Synergetics_Vol1_2", "Everything_I_Know_Transcripts"]:
        raw_text = download_text(title)
        if not raw_text:
            print(f"[ERROR] Could not retrieve full text for {title}.")
            continue
            
        # Split text by section markers or double newlines into ~500 word blocks
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
                
        # Flush remaining buffer
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
    
    cursor.execute("SELECT COUNT(*), SUM(word_count) FROM synergetics_fuller_corpus")
    chunks, words = cursor.fetchone()
    conn.close()
    
    print("\n" + "="*60)
    print(f"[SUCCESS] Complete Corpus Ingested!")
    print(f"Total Indexed Chunks: {chunks}")
    print(f"Total Word Count: {words:,} words")
    print("="*60)

if __name__ == "__main__":
    ingest()
