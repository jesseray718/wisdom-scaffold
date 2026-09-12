#!/data/data/com.termux/files/usr/bin/python3
"""
OPENROOT GRAND UNIFYING SCRIPT v2.0 (Python Native)
Jesse Ray | OpenRoot LLC | R=1.0 | C=0 | ηₜ ↗
"""

import os
import sys
import json
import subprocess
import datetime
import re
from pathlib import Path
from typing import Dict, Any
from urllib.request import urlopen, Request
from urllib.error import URLError

class Config:
    OPENROOT_HOME = os.environ.get("OPENROOT_HOME", str(Path.home() / "openroot"))
    UNE_HOME = os.environ.get("UNE_HOME", str(Path.home() / "une"))
    BLRMH_HOME = os.environ.get("BLRMH_HOME", str(Path.home() / "black-locust-rmh"))
    AGAPE_NET = os.environ.get("AGAPE_NET", str(Path.home() / "agapenet"))
    SDCARD_OR = "/sdcard/openroot"
    BIN_DIR = str(Path.home() / "bin")
    SESSION_STATE = "/sdcard/openroot/.session_state.json"
    MASTER_LOG = "/sdcard/openroot/master.log"
    OPTIPLEX_HOST = os.environ.get("OPTIPLEX_HOST", "192.168.1.100")
    OPTIPLEX_USER = os.environ.get("OPTIPLEX_USER", "jesse")
    OPTIPLEX_PORT = int(os.environ.get("OPTIPLEX_PORT", "22"))
    GITHUB_USER = os.environ.get("GITHUB_USER", "jesseray718")
    GITHUB_EMAIL = os.environ.get("GITHUB_EMAIL", "jesseray718@gmail.com")
    SYNCTHING_CONFIG = str(Path.home() / ".config" / "syncthing")
    SYNCTHING_API_URL = "http://localhost:8384"

def log(message: str, level: str = "INFO", phase: str = None):
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    phase_prefix = f"[PHASE{phase}] " if phase else ""
    log_line = f"[{timestamp}] [{level}] {phase_prefix}{message}\n"
    print(log_line.strip())
    try:
        Path(Config.MASTER_LOG).parent.mkdir(parents=True, exist_ok=True)
        with open(Config.MASTER_LOG, "a") as f:
            f.write(log_line)
    except Exception as e:
        print(f"⚠ Log write failed: {e}", file=sys.stderr)

def check_cmd(cmd: str) -> bool:
    return subprocess.run(["which", cmd], capture_output=True).returncode == 0

def safe_json_load(filepath: str) -> Dict[str, Any]:
    try:
        filepath = Path(filepath).expanduser()
        if not filepath.exists():
            return {}
        content = filepath.read_text(encoding="utf-8").strip()
        if not content:
            return {}
        content = re.sub(r',\s*}', '}', content)
        content = re.sub(r',\s*]', ']', content)
        return json.loads(content)
    except Exception as e:
        log(f"JSON load error in {filepath}: {e}", "ERROR")
        return {}

def safe_json_save(filepath: str, data: Dict[str, Any]) -> bool:
    try:
        filepath = Path(filepath).expanduser()
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        return True
    except Exception as e:
        log(f"JSON save error in {filepath}: {e}", "ERROR")
        return False

def get_session_state() -> Dict[str, Any]:
    default_state = {
        "version": "2.0", "created": None, "last_updated": None,
        "syncthing_device_id": None, "syncthing_folders": [],
        "devices_paired": False, "git_repos_connected": False,
        "oracle_initialized": False, "ssh_keys_generated": False,
        "first_run_complete": False, "next_action": "generate_ssh_keys"
    }
    state = safe_json_load(Config.SESSION_STATE)
    if not state:
        state = default_state
        safe_json_save(Config.SESSION_STATE, state)
    return state

def update_session_state(key: str, value: Any) -> None:
    state = get_session_state()
    state[key] = value
    state["last_updated"] = datetime.datetime.utcnow().isoformat() + "Z"
    safe_json_save(Config.SESSION_STATE, state)

def create_directory_tree():
    log("Creating universal directory tree...", "PHASE1", "1")
    directories = [
        Config.BIN_DIR, Config.OPENROOT_HOME, str(Path(Config.UNE_HOME) / "computational_flow"),
        str(Path(Config.UNE_HOME) / "agape_kb"), Config.BLRMH_HOME, Config.AGAPE_NET,
        str(Path(Config.SDCARD_OR) / "context_bridge"), str(Path(Config.SDCARD_OR) / "ledger"),
        str(Path(Config.SDCARD_OR) / "session_seeds"), str(Path(Config.SDCARD_OR) / "agape_kb"),
        str(Path(Config.SDCARD_OR) / "business"), str(Path.home() / ".ssh"),
        str(Path.home() / ".termux" / "boot"), str(Path.home() / ".local" / "bin")
    ]
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    log("✓ Directory tree created", "PHASE1", "1")

def generate_ssh_keys():
    log("Generating SSH key pair...", "PHASE2", "2")
    ssh_dir = Path.home() / ".ssh"
    ed25519_key = ssh_dir / "id_ed25519"
    if not ed25519_key.exists():
        if check_cmd("ssh-keygen"):
            cmd = ["ssh-keygen", "-t", "ed25519", "-C", f"openroot-a15-{datetime.date.today().strftime('%Y%m%d')}", "-f", str(ed25519_key), "-N", ""]
            result = subprocess.run(cmd, capture_output=True)
            if result.returncode == 0:
                log("✓ Ed25519 SSH key generated", "PHASE2", "2")
                update_session_state("ssh_keys_generated", True)
            else:
                log(f"✗ SSH keygen failed: {result.stderr.decode()}", "ERROR", "2")
        else:
            log("Installing openssh...", "WARNING", "2")
            subprocess.run(["pkg", "install", "-y", "openssh"], check=True)
            generate_ssh_keys()
    else:
        log("✓ SSH keys already exist", "PHASE2", "2")
    update_session_state("next_action", "start_syncthing")

def start_syncthing():
    log("Starting Syncthing daemon...", "PHASE3", "3")
    if check_cmd("syncthing"):
        subprocess.Popen(["syncthing", "--no-browser", "--home", Config.SYNCTHING_CONFIG], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("✓ Syncthing started (background)", "PHASE3", "3")
    else:
        log("Syncthing not found, installing...", "WARNING", "3")
        subprocess.run(["pkg", "install", "-y", "syncthing"], check=True)
        start_syncthing()
    update_session_state("next_action", "connect_git_repos")

def connect_git_repos():
    log("Connecting Git repositories...", "PHASE4", "4")
    if not check_cmd("git"):
        log("Git not found, installing...", "WARNING", "4")
        subprocess.run(["pkg", "install", "-y", "git"], check=True)
    subprocess.run(["git", "config", "--global", "user.name", Config.GITHUB_USER], check=False)
    subprocess.run(["git", "config", "--global", "user.email", Config.GITHUB_EMAIL], check=False)
    subprocess.run(["git", "config", "--global", "init.defaultBranch", "main"], check=False)
    repos = ["openroot", "une", "black-locust-rmh"]
    for repo in repos:
        repo_path = Path.home() / repo
        repo_path.mkdir(parents=True, exist_ok=True)
        git_dir = repo_path / ".git"
        if not git_dir.exists():
            subprocess.run(["git", "init"], cwd=repo_path, check=True)
            (repo_path / "README.md").touch()
            subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
            subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo_path, check=True)
            subprocess.run(["git", "branch", "-M", "main"], cwd=repo_path, check=True)
            subprocess.run(["git", "remote", "add", "origin", f"https://github.com/{Config.GITHUB_USER}/{repo}.git"], cwd=repo_path, check=False)
            log(f"  ✓ Initialized {repo}", "PHASE4", "4")
        else:
            result = subprocess.run(["git", "remote", "get-url", "origin"], cwd=repo_path, capture_output=True)
            if result.returncode != 0:
                subprocess.run(["git", "remote", "add", "origin", f"https://github.com/{Config.GITHUB_USER}/{repo}.git"], cwd=repo_path, check=False)
    update_session_state("git_repos_connected", True)
    update_session_state("next_action", "deploy_cli_tools")
    log("✓ Git repos connected", "PHASE4", "4")

def deploy_cli_tools():
    log("Deploying CLI tools...", "PHASE5", "5")
    or_status = '''#!/data/data/com.termux/files/usr/bin/python3\nimport json, subprocess, datetime\nfrom pathlib import Path\nfrom urllib.request import urlopen\nprint("=" * 63)\nprint("  OPENROOT STATUS —", datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"))\nprint("=" * 63)\ntry:\n    with urlopen("http://localhost:8384/rest/system/status", timeout=3) as resp:\n        data = json.loads(resp.read())\n        print(f"Device ID: {data.get('myID','?')[:16]}...")\nexcept:\n    print("✗ REST unreachable")\nfor path in [Path.home()/ "openroot", Path.home()/ "une", "/sdcard/openroot"]:\n    if path.exists():\n        result = subprocess.run(["du", "-sh", str(path)], capture_output=True)\n        print(result.stdout.decode().strip())\nprint("=" * 63)'''
    (Path(Config.BIN_DIR) / "or-status").write_text(or_status); (Path(Config.BIN_DIR) / "or-status").chmod(0o755)
    log("  ✓ or-status deployed", "PHASE5", "5")
    for tool in ["or-status"]:
        dst = Path.home() / ".local" / "bin" / tool
        try:
            dst.symlink_to((Path(Config.BIN_DIR) / tool).resolve())
        except:
            pass
    update_session_state("next_action", "configure_auto_start")
    log("✓ CLI tools deployed", "PHASE5", "5")

def configure_auto_start():
    log("Configuring auto-start...", "PHASE6", "6")
    boot_script = "#!/data/data/com.termux/files/usr/bin/bash\nsleep 15\ntermux-wake-lock 2>/dev/null || true\nsyncthing --no-browser --home=\"$HOME/.config/syncthing\" &\ndate -u +%Y%m%dT%H%M%SZ >> \"$HOME/.openroot_boot.log\""
    boot_file = Path.home() / ".termux" / "boot" / "00-openroot.sh"
    boot_file.parent.mkdir(parents=True, exist_ok=True)
    boot_file.write_text(boot_script, encoding="utf-8")
    boot_file.chmod(0o755)
    log("✓ Termux:Boot configured", "PHASE6", "6")
    update_session_state("next_action", "idle")
    update_session_state("first_run_complete", True)

def main():
    start_time = datetime.datetime.now()
    print("\n╔═══════════════════════════════════════════════════════════════╗\n║      OPENROOT GRAND UNIFYING SCRIPT v2.0 (PYTHON)         ║\n║      Jesse Ray | OpenRoot LLC | R=1.0 | C=0 | ηₜ ↗      ║\n╚═══════════════════════════════════════════════════════════════╝\n")
    create_directory_tree()
    generate_ssh_keys()
    start_syncthing()
    connect_git_repos()
    deploy_cli_tools()
    configure_auto_start()
    elapsed = (datetime.datetime.now() - start_time).total_seconds()
    print(f"\n✓ GRAND UNIFICATION COMPLETE ({elapsed:.1f}s)")
    print(f"Session State: {Config.SESSION_STATE}")
    print(f"Master Log: {Config.MASTER_LOG}")
    print("NEXT: or-status | or-sync | or-resume")
    print("R=1.0 | C=0 | ηₜ ↗\n")

if __name__ == "__main__":
    main()
