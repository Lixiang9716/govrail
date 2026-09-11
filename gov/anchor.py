#!/usr/bin/env python3
"""Shared history anchoring (#23/D32) — extracted from gates.py.

History belongs to the repository, not the checkout: a linked worktree
records into the main checkout's ``.gov/history`` (the git common dir's
parent), so ledgers do not fragment per worktree. Both the run ledger
(``gov run``) and the stats ledger (``gov stats --record``) append through
this module — one fact, one home (rubric R7); the runner keeps a thin
delegate so its callers are unchanged.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def history_path(rel: str = "gates.jsonl") -> Path:
    """The main checkout's ``.gov/history/<rel>``, worktree-aware.

    ``git rev-parse --git-common-dir`` resolves the shared git dir of every
    worktree; its parent is the main checkout. Outside a work tree (or when
    git is unavailable) the cwd-relative path stands — the tools resolve
    repositories by cwd (D21).
    """
    try:
        proc = subprocess.run(["git", "rev-parse", "--git-common-dir"],
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode == 0:
            common = Path(proc.stdout.strip()).resolve()
            root = common.parent
            if root != Path.cwd():
                return root / ".gov" / "history" / rel
    except OSError:
        pass
    return Path(".gov/history") / rel
