import os
import sys
import glob

def scan_repository(target_dir):
    print(f"=== OPENROOT ECOSYSTEM SKELETON: {target_dir} ===")
    file_list = []
    for root, _, files in os.walk(target_dir):
        for f in files:
            if f.endswith(('.md', '.py', '.json', '.cpp', '.h', '.sh')):
                file_list.append(os.path.join(root, f))

    print(f"Total relevant files found: {len(file_list)}\n")
    print("--- FILE MANIFEST & OUTLINES ---")

    for filepath in sorted(file_list):
        rel_path = os.path.relpath(filepath, target_dir)
        print(f"\n==========================================")
        print(f"FILE: {rel_path}")
        print(f"==========================================")
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                print(f"Line Count: {len(lines)}")
                print("Outline Preview:")
                
                if filepath.endswith('.md'):
                    headings = [line.strip() for line in lines if line.startswith('#')]
                    if headings:
                        print('\n'.join(headings[:15]))
                    else:
                        print(''.join(lines[:10]))
                elif filepath.endswith('.py'):
                    defs = [line.strip() for line in lines if line.lstrip().startswith(('def ', 'class '))]
                    if defs:
                        print('\n'.join(defs[:15]))
                    else:
                        print(''.join(lines[:10]))
                else:
                    print(''.join(lines[:10]))
        except Exception as e:
            print(f"Error reading file: {e}")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/openroot_docs/economics")
    scan_repository(target)
