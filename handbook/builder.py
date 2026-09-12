#!/usr/bin/env python3
"""
Dynamic Handbook CLI Builder
Uses pure Python standard library to update MkDocs documentation.
"""
import argparse
from pathlib import Path
from datetime import datetime

DOCS_DIR = Path("docs")

def append_note(title: str, content: str, category: str):
    """Appends or creates a markdown page dynamically."""
    category_dir = DOCS_DIR / category
    category_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = category_dir / f"{title.lower().replace(' ', '_')}.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    markdown_data = f"""# {title}

> **Created:** {timestamp}  
> **Category:** {category}

---

## Content

{content}

---
*Generated via `builder.py` CLI*
"""
    
    file_path.write_text(markdown_data, encoding="utf-8")
    print(f"[SUCCESS] Wrote note to: {file_path}")

def main():
    parser = argparse.ArgumentParser(
        description="Dynamic Permaculture Handbook Builder (Zero External Dependencies)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add a new page to the handbook")
    add_parser.add_argument("--title", "-t", required=True, type=str, help="Title of the document")
    add_parser.add_argument("--content", "-c", required=True, type=str, help="Markdown body content")
    add_parser.add_argument("--category", "-cat", default="general", type=str, help="Subfolder category")

    args = parser.parse_args()

    if args.command == "add":
        append_note(args.title, args.content, args.category)

if __name__ == "__main__":
    main()
