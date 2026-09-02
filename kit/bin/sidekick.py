#!/usr/bin/env python3
"""Living handbook + compost + curriculum + 7B protocol.

Not a wiretap. Local files only. Privacy file stops harvest.
Handbook is this program: python3 sidekick.py help
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from collections import Counter
from pathlib import Path

HELP = r"""
SIDEKICK — attached to the operator, not to the network.

python3 sidekick.py help
python3 sidekick.py doctor
python3 sidekick.py privacy on      # timeout. no harvest. coder still gets last protocol
python3 sidekick.py privacy off
python3 sidekick.py harvest         # bash history + kit jsonl + dropped logs. compost raw
python3 sidekick.py principles      # 12 algorithms
python3 sidekick.py curriculum
python3 sidekick.py predict
python3 sidekick.py protocol        # write CODER_PROTOCOL.txt for the 7B
python3 sidekick.py resources
python3 sidekick.py log LINE        # one lesson you choose to keep

Android verbose / logcat: do NOT dump everything.
  sidekick harvest-logcat   # 8 second allowlist sample, then compost. optional.

Privacy on = harvest refused until privacy off.
"""

# Holmgren 12 as executable tests. Each returns 0.0..1.0 plus a note.
PRINCIPLES = [
    ("P01_observe", "Observe and interact", "Did we look at pane, path, and a real sensor before writing?"),
    ("P02_catch", "Catch and store energy", "Did we store a hashable lesson instead of a chat cloud?"),
    ("P03_yield", "Obtain a yield", "Did a command print a measurable result (0.0, Pong, JSON ok)?"),
    ("P04_feedback", "Apply self-regulation and accept feedback", "Did we refuse a known failure family (PANE, LANG, TILDE)?"),
    ("P05_renewable", "Use and value renewable resources", "Did we use local 7B / sunlight / existing files before a new clone?"),
    ("P06_no_waste", "Produce no waste", "Did we compost raw logs and avoid unpack-all / third clone?"),
    ("P07_patterns", "Design from patterns to details", "Did we name the family before the filename?"),
    ("P08_integrate", "Integrate rather than segregate", "Did kit + tidbits.json + 7B stay one loop?"),
    ("P09_small_slow", "Use small and slow solutions", "Cap combine rounds. One extract. One clone."),
    ("P10_diversity", "Use and value diversity", "Phone + box + git + mesh, not one vendor."),
    ("P11_edges", "Use edges and value the marginal", "A15 is the edge. Keep it able when the box is dark."),
    ("P12_change", "Creatively use and respond to change", "IP move, tunnel, Tailscale off-LAN. No unique-ID wipe."),
]


def pane() -> str:
    cwd = str(Path.cwd())
    host = os.uname().nodename if hasattr(os, "uname") else ""
    if "optiplex" in host.lower() or cwd.startswith("/home/jesse"):
        return "SSH"
    if cwd.startswith("/data/data/com.termux") or cwd.startswith("/storage/emulated"):
        return "A15"
    return "UNKNOWN"


def root() -> Path:
    if pane() == "SSH":
        p = Path("/home/jesse/openroot/kit/sidekick")
    elif pane() == "A15":
        p = Path("/data/data/com.termux/files/home/code/openroot/kit/sidekick")
    else:
        p = Path(__file__).resolve().parent.parent / "var" / "sidekick"
    p.mkdir(parents=True, exist_ok=True)
    return p


def dbp() -> Path:
    return root() / "sidekick.sqlite"


def privacy_flag() -> Path:
    return root() / "PRIVACY_ON"


def protocol_path() -> Path:
    return root() / "CODER_PROTOCOL.txt"


SCHEMA = """
PRAGMA journal_mode=DELETE;
CREATE TABLE IF NOT EXISTS event(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  t TEXT,
  kind TEXT,
  body TEXT,
  family TEXT
);
CREATE TABLE IF NOT EXISTS lesson(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  t TEXT,
  body TEXT,
  principle TEXT
);
CREATE TABLE IF NOT EXISTS score(
  t TEXT,
  principle TEXT,
  v REAL,
  note TEXT
);
"""


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(str(dbp()))
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def private() -> bool:
    return privacy_flag().exists()


def cmd_privacy(state: str) -> int:
    if state == "on":
        privacy_flag().write_text("on " + time.strftime("%Y-%m-%dT%H:%M:%S") + "\n")
        print("privacy ON. harvest stopped. last protocol kept.")
        return 0
    if state == "off":
        if privacy_flag().exists():
            privacy_flag().unlink()
        print("privacy OFF. harvest allowed.")
        return 0
    print("privacy on|off. now:", "ON" if private() else "OFF")
    return 0


def score_event(body: str) -> list[tuple[str, float, str]]:
    b = body.lower()
    out = []
    tests = {
        "P01_observe": ("optiplex" in b or "a15" in b or "pwd" in b or "pane" in b, "pane/path mentioned"),
        "P02_catch": ("json" in b or "sqlite" in b or "tidbit" in b, "stored form"),
        "P03_yield": ("pong" in b or "0.0" in b or '"ok": true' in b or "logged in" in b, "measurable yield"),
        "P04_feedback": (any(x in b for x in ("pathspec", "no such file", "from: too many", "pkg not found")), "error family seen"),
        "P05_renewable": ("127.0.0.1:8080" in b or "qwen" in b or "local" in b, "local inference"),
        "P06_no_waste": ("unpack" in b or "clone" in b and "src/openroot" in b, "waste risk"),
        "P07_patterns": (any(x in b for x in ("pane", "lang", "heredoc", "tilde")), "named family"),
        "P08_integrate": ("tidbit" in b and ("curl" in b or "kit" in b), "loop"),
        "P09_small_slow": ("combine 3" in b or "extract" in b, "capped action"),
        "P10_diversity": ("syncthing" in b or "gh " in b or "ssh" in b, "more than one medium"),
        "P11_edges": ("termux" in b or "emulated/0" in b or "a15" in b, "edge node"),
        "P12_change": ("tunnel" in b or "tailscale" in b or "192.168.1.193" in b, "path change"),
    }
    for pid, title, q in PRINCIPLES:
        hit, note = tests.get(pid, (False, ""))
        v = 1.0 if hit else 0.0
        if pid == "P06_no_waste" and hit:
            v = 0.0
            note = "waste pattern"
        elif pid == "P04_feedback" and hit:
            v = 1.0
            note = "caught a known fail"
        out.append((pid, v, note or title))
    return out


def compost_line(raw: str) -> str | None:
    s = " ".join(raw.strip().split())
    if len(s) < 8:
        return None
    # drop secrets
    if "ghp_" in s or "token" in s.lower() and "ghp_" in s:
        return None
    if s.startswith("#"):
        return None
    return s[:240]


def harvest_paths() -> list[Path]:
    p = pane()
    out = []
    if p == "A15":
        out.extend(
            [
                Path("/data/data/com.termux/files/home/.bash_history"),
                Path("/data/data/com.termux/files/home/code/openroot/kit/data/error_pred_100.jsonl"),
            ]
        )
    if p == "SSH":
        out.extend(
            [
                Path("/home/jesse/.bash_history"),
                Path("/home/jesse/openroot/kit/data/error_pred_100.jsonl"),
            ]
        )
    inbox = root() / "inbox"
    inbox.mkdir(exist_ok=True)
    out.extend(sorted(inbox.glob("*")))
    return out


def cmd_harvest() -> int:
    if private():
        print("privacy ON. harvest refused.")
        return 2
    con = connect()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    kept = 0
    scanned = 0
    for fp in harvest_paths():
        if not fp.exists() or not fp.is_file():
            continue
        try:
            text = fp.read_text(errors="replace")
        except Exception:
            continue
        for line in text.splitlines()[-400:]:
            scanned += 1
            lesson = compost_line(line)
            if not lesson:
                continue
            family = "UNK"
            low = lesson.lower()
            for fam in ("pane", "lang", "heredoc", "tilde", "clone", "pkg", "pathspec", "pong", "canon"):
                if fam in low:
                    family = fam.upper()
                    break
            con.execute(
                "INSERT INTO event(t,kind,body,family) VALUES(?,?,?,?)",
                (now, fp.name, lesson, family),
            )
            for pid, v, note in score_event(lesson):
                if v > 0:
                    con.execute(
                        "INSERT INTO score(t,principle,v,note) VALUES(?,?,?,?)",
                        (now, pid, v, note),
                    )
            kept += 1
        # compost: if inbox file, truncate after harvest
        if fp.parent == root() / "inbox":
            fp.write_text("")
    con.execute(
        "INSERT INTO lesson(t,body,principle) VALUES(?,?,?)",
        (now, "harvest scanned=%d kept=%d" % (scanned, kept), "P06_no_waste"),
    )
    con.commit()
    print(json.dumps({"scanned": scanned, "kept": kept, "privacy": False, "db": str(dbp())}))
    return 0


def cmd_harvest_logcat() -> int:
    if private():
        print("privacy ON.")
        return 2
    if pane() != "A15":
        print("logcat is A15 only")
        return 2
    import subprocess

    try:
        p = subprocess.run(
            ["logcat", "-d", "-t", "80", "-s", "Termux:V", "syncthing:I", "AndroidRuntime:E"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        (root() / "inbox" / "logcat_sample.txt").write_text((p.stdout or "")[-8000:])
    except Exception as e:
        print("logcat skip", e)
        return 1
    return cmd_harvest()


def cmd_principles() -> int:
    for pid, title, q in PRINCIPLES:
        print(f"{pid:16} {title}")
        print(f"                 {q}")
    return 0


def cmd_curriculum() -> int:
    con = connect()
    fam = con.execute("SELECT family, COUNT(*) c FROM event GROUP BY family ORDER BY c DESC LIMIT 8").fetchall()
    print("# dynamic curriculum (from composted events)")
    plan = [
        "1. Name the pane before the command.",
        "2. One yield per paste (JSON, 0.0, Pong).",
        "3. Tidbits.json is the catalog. Kit sqlite is the operator.",
        "4. 7B only via localhost or tunnel. Feed protocol file.",
        "5. One clone under /home/jesse/src if and only if you will open a file.",
        "6. Privacy on when the log would include other people or tokens.",
    ]
    if fam:
        print("observed families:", ", ".join("%s=%s" % (r["family"], r["c"]) for r in fam))
        top = fam[0]["family"]
        print("next drill: repeat a correct action in family", top)
    for line in plan:
        print(line)
    return 0


def cmd_predict() -> int:
    con = connect()
    n = con.execute("SELECT COUNT(*) FROM event").fetchone()[0]
    fam = {r["family"]: r["c"] for r in con.execute("SELECT family, COUNT(*) c FROM event GROUP BY family")}
    pred = []
    if fam.get("PANE", 0) or fam.get("LANG", 0):
        pred.append("Next session risk: Python-at-$ or A15 path on SSH. Check prompt first.")
    if fam.get("CLONE", 0):
        pred.append("Clone pressure: do not add a fourth openroot tree.")
    if n < 10:
        pred.append("Too little compost. harvest once, then predict again.")
    pred.append("7B stays on box. Phone stays client. That outcome is stable if tunnel or localhost used.")
    print(json.dumps({"events": n, "families": fam, "predict": pred}, indent=2))
    return 0


PROTOCOL_CORE = """
OPENROOT CODER PROTOCOL (local 7B + human)
You are qwen2.5-coder-7b on jesse@optiplex3060. The human is Jesse McMillen / jesseray718.

CODE OF CONDUCT
- Absolute paths. No tilde. No placeholders.
- A15 paths never on the box. Box paths never as first install on the phone.
- Do not invent N17. Canon coord at R=1 T>=1 prints 0.0.
- Do not unpack archives unless asked to extract one file.
- Do not start a second llama-server. Do not load GGUF on the A15.
- Strip markdown fences if the human must run the line.
- Secrets (ghp_, passwords) are never repeated.

RULES OF ENGAGEMENT
- One claim, one yield.
- Prefer existing files: parts_library/tidbits.json, kit/bin/*, bin/local_ask.py.
- GitHub is publish. Syncthing is live. Inference is localhost:8080.
- Permaculture 12 is law: observe first, yield, no waste, edges (A15), small/slow, respond to change (tunnel/Tailscale).

PLAN
- Keep openroot as hub. Index unindexed externals. Clone to /home/jesse/src only with a file you will open.
- Feed sidekick harvest into lessons. Privacy on = stop harvest.

TIMEOUT
- If kit/sidekick/PRIVACY_ON exists, do not ask for more logs.
"""


def cmd_protocol() -> int:
    extra = ""
    if dbp().exists():
        con = connect()
        rows = con.execute("SELECT family, COUNT(*) c FROM event GROUP BY family ORDER BY c DESC LIMIT 6").fetchall()
        if rows:
            extra = "\nRECENT FAMILIES\n" + "\n".join("%s %s" % (r["family"], r["c"]) for r in rows)
    text = PROTOCOL_CORE + extra + "\n"
    protocol_path().write_text(text)
    print(str(protocol_path()))
    print(text)
    return 0


RESOURCES = [
    ("local 7B", "already running qwen2.5-coder-7b on 127.0.0.1:8080", "max"),
    ("tidbits.json", "/home/jesse/openroot/parts_library/tidbits.json", "max"),
    ("sqlite-utils", "clone simonw/sqlite-utils to /home/jesse/src if missing", "high"),
    ("llama.cpp", "you already serve it; clone only to read flags", "high"),
    ("Termux wiki", "https://wiki.termux.com offline if you wget once", "med"),
    ("gh cli", "already authed jesseray718", "high"),
    ("Meshtastic", "your firmware fork — off-grid when LAN dies", "med"),
    ("Tailscale", "off-LAN only", "med"),
]


def cmd_resources() -> int:
    print("# free/cheap dossier  gain/effort/time")
    for name, note, rank in RESOURCES:
        print(f"{rank:5}  {name:16}  {note}")
    return 0


def cmd_log(line: str) -> int:
    if private():
        print("privacy ON. not logged.")
        return 2
    con = connect()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    con.execute("INSERT INTO event(t,kind,body,family) VALUES(?,?,?,?)", (now, "manual", line[:240], "MANUAL"))
    con.execute("INSERT INTO lesson(t,body,principle) VALUES(?,?,?)", (now, line[:240], "P02_catch"))
    con.commit()
    print("kept")
    return 0


def cmd_doctor() -> int:
    print(
        json.dumps(
            {
                "pane": pane(),
                "root": str(root()),
                "privacy": private(),
                "db": str(dbp()),
                "db_exists": dbp().exists(),
                "protocol": str(protocol_path()),
                "protocol_exists": protocol_path().exists(),
            },
            indent=2,
        )
    )
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in {"help", "-h"}:
        print(HELP)
        return 0
    c = argv[1]
    if c == "doctor":
        return cmd_doctor()
    if c == "privacy":
        return cmd_privacy(argv[2] if len(argv) > 2 else "status")
    if c == "harvest":
        return cmd_harvest()
    if c == "harvest-logcat":
        return cmd_harvest_logcat()
    if c == "principles":
        return cmd_principles()
    if c == "curriculum":
        return cmd_curriculum()
    if c == "predict":
        return cmd_predict()
    if c == "protocol":
        return cmd_protocol()
    if c == "resources":
        return cmd_resources()
    if c == "log":
        return cmd_log(" ".join(argv[2:]))
    print(HELP)
    return 1


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv))
