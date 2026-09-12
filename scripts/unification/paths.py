#!/usr/bin/env python3
"""Single path table. No tilde. Pane-aware."""
from __future__ import annotations

import os
from pathlib import Path

SKIP_DIR_NAMES = {
    ".venv",
    "venv",
    ".git",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "models",
    "gguf",
    ".cache",
}

GHOST_RELATIVE = (
    "handbook/master_codebase_orchestrator.py",
    "handbook/audit_pipeline.py",
    "scripts/rag/hybrid_rag_router.py",
    "scripts/rag/fts5_ensure.py",
    "scripts/rag/locate_pipeline.py",
    "scripts/unification/grand_unification.py",
)

PUBLISHED_RELATIVE = (
    "scripts/rag/nomic_rag_indexer.py",
    "scripts/rag/vector_search.py",
    "scripts/rag/bridge_test.py",
    "index_content_blobs.py",
    "unify_scaffold.py",
    "kit/bin/sidekick.py",
    "GRAND_UNIFICATION_MANIFEST.json",
    "PATH_INVENTORY.yaml",
)


def pane() -> str:
    cwd = str(Path.cwd())
    host = os.uname().nodename if hasattr(os, "uname") else ""
    if "optiplex" in host.lower() or cwd.startswith("/home/jesse"):
        return "SSH"
    if cwd.startswith("/data/data/com.termux") or cwd.startswith("/storage/emulated"):
        return "A15"
    return "SANDBOX"


def roots() -> dict[str, Path]:
    p = pane()
    if p == "SSH":
        return {
            "wisdom": Path("/home/jesse/wisdom-scaffold"),
            "openroot": Path("/home/jesse/openroot"),
            "une": Path("/home/jesse/une"),
            "home": Path("/home/jesse"),
            "db": Path("/home/jesse/wisdom-scaffold/data/optiplex_index.db"),
            "db_ghost": Path("/home/jesse/optiplex_index.db"),
            "db_agape": Path("/home/jesse/openroot/agape_kb/agape_vector_index.db"),
            "knowledge": Path("/home/jesse/wisdom-scaffold/data/knowledge.db"),
            "operator": Path("/home/jesse/wisdom-scaffold/data/operator_memory.db"),
        }
    if p == "A15":
        return {
            "wisdom": Path("/data/data/com.termux/files/home/wisdom-scaffold"),
            "openroot": Path("/storage/emulated/0/openroot"),
            "une": Path("/data/data/com.termux/files/home/une"),
            "home": Path("/data/data/com.termux/files/home"),
            "db": Path("/data/data/com.termux/files/home/wisdom-scaffold/data/optiplex_index.db"),
            "db_ghost": Path("/data/data/com.termux/files/home/optiplex_index.db"),
            "db_agape": Path("/storage/emulated/0/openroot/agape_kb/agape_vector_index.db"),
            "knowledge": Path("/data/data/com.termux/files/home/wisdom-scaffold/data/knowledge.db"),
            "operator": Path("/data/data/com.termux/files/home/wisdom-scaffold/data/operator_memory.db"),
        }
    base = Path("/home/workdir/artifacts/wisdom-pipeline")
    return {
        "wisdom": base,
        "openroot": base,
        "une": base,
        "home": Path("/home/workdir"),
        "db": base / "data" / "optiplex_index.db",
        "db_ghost": base / "data" / "optiplex_index_GHOST.db",
        "db_agape": base / "data" / "agape_vector_index.db",
        "knowledge": base / "data" / "knowledge.db",
        "operator": base / "data" / "operator_memory.db",
    }


def skip_dir(name: str) -> bool:
    return name in SKIP_DIR_NAMES
