#!/usr/bin/env python3
import subprocess, sys, os
from pathlib import Path

HOME = Path.home()
VENV_DIR = HOME / ".openroot_venv"
PIP = str(VENV_DIR / "bin" / "pip")
INTERPRETER = str(VENV_DIR / "bin" / "interpreter")

def run(cmd):
    print(f"\n▶ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

print("🌿 OpenRoot AI Bridge Setup...")

# 1. Ensure venv module exists
try:
    run(["sudo", "apt-get", "install", "-y", "python3-venv"])
except: pass

# 2. Create venv
if not VENV_DIR.exists():
    run([sys.executable, "-m", "venv", str(VENV_DIR)])

# 3. Activate & Upgrade
run([str(VENV_DIR / "bin" / "python"), "-m", "pip", "install", "--upgrade", "pip"])

# 4. Install Open Interpreter
run([PIP, "install", "open-interpreter"])

# 5. Create launcher alias
LAUNCHER = HOME / ".local" / "bin" / "openroot-ai"
LAUNCHER.parent.mkdir(parents=True, exist_ok=True)
script = f"""#!/bin/bash
source "{VENV_DIR}/bin/activate"
echo "🚀 OpenRoot AI Active"
interpreter "$@"
"""
LAUNCHER.write_text(script)
LAUNCHER.chmod(0o755)

# Add to PATH
bashrc = HOME / ".bashrc"
content = bashrc.read_text() if bashrc.exists() else ""
if 'export PATH="$HOME/.local/bin:$PATH"' not in content:
    bashrc.write_text(content + '\nexport PATH="$HOME/.local/bin:$PATH"\n')

print("\n✅ Done! Run 'openroot-ai' to start.")
print("   Or run './openroot_ai_bridge.py' again to launch now.")
