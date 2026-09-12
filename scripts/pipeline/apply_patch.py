import sys
import os
import re

def parse_and_apply(patch_file):
    if not os.path.exists(patch_file):
        print(f"Error: {patch_file} not found.")
        sys.exit(1)

    with open(patch_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Finds patterns like: ### FILE: /path/to/file or ```python:path/to/file
    file_blocks = re.split(r'(?:### FILE:\s*|```\w+:\s*)([^\n]+)', content)
    
    if len(file_blocks) < 2:
        print("No multi-file code blocks or target headers found in patch file.")
        sys.exit(1)

    for i in range(1, len(file_blocks), 2):
        target_path = file_blocks[i].strip()
        code_body = file_blocks[i+1].split("```")[0].strip()

        # Expand home directory if present
        target_path = os.path.expanduser(target_path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(code_body + "\n")
        print(f"[+] Successfully wrote: {target_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 apply_patch.py /path/to/ai_response.txt")
        sys.exit(1)
    parse_and_apply(sys.argv[1])
