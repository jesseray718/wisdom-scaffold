import sqlite3
import urllib.request
import json
import re
import pandas as pd

DB_PATH = "optiplex_public.db"

def init_knowledge_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Euclid's Elements Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS euclid_elements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book INTEGER,
            item_type TEXT, -- Definition, Postulate, Common Notion, Proposition
            item_number INTEGER,
            content TEXT
        )
    ''')
    
    # Reference Manuals & Handbooks Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reference_manuals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT,    -- Physics, Concrete, Engineering, Mathematics
            title TEXT,
            author TEXT,
            source_url TEXT,
            content TEXT
        )
    ''')
    
    # Material Physics Constants Database
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS material_physics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material TEXT UNIQUE,
            density_kg_m3 REAL,
            compressive_strength_mpa REAL,
            thermal_conductivity_w_mk REAL,
            specific_heat_j_kgk REAL
        )
    ''')
    
    conn.commit()
    conn.close()
    print("--> Database schema initialized successfully.")

# =====================================================================
# 1. EUCLID'S ELEMENTS INGESTION (Project Gutenberg #21076 / Standard Text)
# =====================================================================
def ingest_euclid():
    print("--> Fetching and ingesting Euclid's Elements...")
    url = "https://www.gutenberg.org/files/21076/21076-0.txt"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            text = response.read().decode('utf-8', errors='ignore')
            
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Primitive parsing chunker for Gutenberg text
        books = re.split(r'BOOK\s+([IVXLCDM]+)', text)
        inserted = 0
        
        for i in range(1, len(books), 2):
            book_roman = books[i]
            book_content = books[i+1]
            
            # Map Roman numerals to integers roughly
            roman_map = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6,
                         'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10, 'XI': 11, 'XII': 12, 'XIII': 13}
            book_num = roman_map.get(book_roman, 0)
            
            # Insert full raw book text blocks
            cursor.execute('''
                INSERT INTO euclid_elements (book, item_type, item_number, content)
                VALUES (?, ?, ?, ?)
            ''', (book_num, "Full Book Text", book_num, book_content.strip()[:100000]))
            inserted += 1
            
        conn.commit()
        conn.close()
        print(f"    [✓] Ingested {inserted} Books of Euclid's Elements.")
    except Exception as e:
        print(f"    [!] Failed to download Euclid: {e}")

# =====================================================================
# 2. PHYSICS & CONCRETE MANUALS (Public Domain / Gutenberg Reference Works)
# =====================================================================
def ingest_manuals():
    print("--> Ingesting Physics and Concrete Engineering Manuals...")
    
    manuals = [
        {
            "domain": "Concrete & Masonry",
            "title": "A Manual of Concrete Construction",
            "author": "Public Reference / Bureau of Reclamation",
            "url": "https://www.gutenberg.org/cache/epub/63827/pg63827.txt"
        },
        {
            "domain": "Physics & Dynamics",
            "title": "Experimental Physics: College Text",
            "author": "Harold A. Wilson",
            "url": "https://www.gutenberg.org/cache/epub/37193/pg37193.txt"
        }
    ]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for m in manuals:
        try:
            print(f"    Downloading {m['title']}...")
            req = urllib.request.Request(m['url'], headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                content = response.read().decode('utf-8', errors='ignore')
                
                cursor.execute('''
                    INSERT INTO reference_manuals (domain, title, author, source_url, content)
                    VALUES (?, ?, ?, ?, ?)
                ''', (m['domain'], m['title'], m['author'], m['url'], content[:200000]))
                print(f"    [✓] Successfully stored {m['title']}.")
        except Exception as e:
            print(f"    [!] Skipping {m['title']}: {e}")
            
    conn.commit()
    conn.close()

# =====================================================================
# 3. PHYSICAL CONSTANTS & MATERIAL PROPERTIES DATABASE
# =====================================================================
def ingest_material_physics():
    print("--> Populating Material Physics & Structural Database...")
    materials = [
        {"material": "Basalt-Cement Mix (AeroCement)", "density_kg_m3": 1800.0, "compressive_strength_mpa": 45.0, "thermal_conductivity_w_mk": 0.55, "specific_heat_j_kgk": 1000.0},
        {"material": "Standard Concrete (C25/30)", "density_kg_m3": 2400.0, "compressive_strength_mpa": 30.0, "thermal_conductivity_w_mk": 1.50, "specific_heat_j_kgk": 880.0},
        {"material": "Structural Steel (A36)", "density_kg_m3": 7850.0, "compressive_strength_mpa": 250.0, "thermal_conductivity_w_mk": 50.0, "specific_heat_j_kgk": 490.0},
        {"material": "Rammed Earth / Stabilized Soil", "density_kg_m3": 2000.0, "compressive_strength_mpa": 5.0, "thermal_conductivity_w_mk": 1.05, "specific_heat_j_kgk": 1250.0},
        {"material": "Basalt Rebar / Fiber", "density_kg_m3": 2100.0, "compressive_strength_mpa": 1100.0, "thermal_conductivity_w_mk": 0.035, "specific_heat_j_kgk": 960.0}
    ]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for mat in materials:
        cursor.execute('''
            INSERT OR REPLACE INTO material_physics 
            (material, density_kg_m3, compressive_strength_mpa, thermal_conductivity_w_mk, specific_heat_j_kgk)
            VALUES (:material, :density_kg_m3, :compressive_strength_mpa, :thermal_conductivity_w_mk, :specific_heat_j_kgk)
        ''', mat)
    conn.commit()
    conn.close()
    print("    [✓] Material physics properties populated.")

if __name__ == "__main__":
    init_knowledge_db()
    ingest_euclid()
    ingest_manuals()
    ingest_material_physics()
