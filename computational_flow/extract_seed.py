#!/data/data/com.termux/files/usr/bin/python3
"""SESSION EXTRACTOR - Saves session state to portable JSON seed"""
import json, os, subprocess
from datetime import datetime

base = 'os.path.expanduser("~") + "/"une'
seed_dir = 'os.environ.get("OPENROOT_BASE", "/sdcard/openroot") + "/"session_seeds'
os.makedirs(seed_dir, exist_ok=True)

now = datetime.now()
sid = now.strftime('%Y-%m-%d_%H%M%S')
seed_file = os.path.join(seed_dir, sid + '.json')

# Git diff
diff = subprocess.run(['git','-C',base,'diff','HEAD'], capture_output=True, text=True).stdout

# Context state
ctx = {}
try:
    with open('os.environ.get("OPENROOT_BASE", "/sdcard/openroot") + "/"context_bridge/context.json','r') as f:
        ctx = json.load(f)
except:
    pass

# Terminal log
log_path = 'os.environ.get("ANDROID_STORAGE", "/storage/emulated/0") + "/"Documents/terminal-logs/auto_' + now.strftime('%Y%m%d_%H%M%S') + '.log'
term_log = ''
try:
    with open(log_path,'r') as f:
        term_log = ''.join(f.readlines()[-500:])
except:
    term_log = 'No terminal log found.'

seed = {
    'meta': {
        'generated': now.isoformat(),
        'session_id': sid,
        'device': 'Samsung A15',
        'os': 'Termux',
        'privilege_stack': 'Shizuku + Ashell',
        'base_path': base
    },
    'context_state': ctx,
    'git_diff': diff,
    'terminal_log_tail': term_log,
    'lessons_learned': [],
    'next_actions': []
}

with open(seed_file, 'w') as f:
    json.dump(seed, f, indent=2)

size = os.path.getsize(seed_file)
print('Seed created: ' + seed_file)
print('Size: ' + str(size) + ' bytes')
print('Session ID: ' + sid)
