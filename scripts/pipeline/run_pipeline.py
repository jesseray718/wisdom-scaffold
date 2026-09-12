import subprocess
import os
import sys

def main():
    target_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/openroot_docs/economics")
    prompt_out = "/tmp/ai_prompt.txt"

    print("[1/2] Generating Skeleton for AI Pipeline...")
    with open(prompt_out, "w") as out:
        subprocess.run(["python3", os.path.expanduser("~/wisdom-scaffold/scripts/pipeline/generate_skeleton.py"), target_dir], stdout=out)

    print(f"\n[+] Skeleton saved to {prompt_out}")
    print("\n--- PROMPT TO COPY & PASTE TO AI ---")
    print("----------------------------------------------------------------------")
    print(f"Please analyze the following repo skeleton for target directory: {target_dir}")
    print("1. Review files for structural gaps, optimization opportunities, and dual-model alignment (Open Source + Monetization).")
    print("2. Ask me 2-3 focused clarification questions.")
    print("3. Provide file upgrades using format '### FILE: path/to/file' followed by code.\n")
    print(f"To dump the prompt text to your terminal, run:\n  cat {prompt_out}\n")

if __name__ == "__main__":
    main()
