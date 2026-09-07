#!/usr/bin/env python3
"""Anchor repo-root-relative tools to the git work tree's root.

Every tool that walks `.agents/notes/` or `docs/` is root-relative, so a
call from a subdirectory used to split by tool: some failed loud ("is this
a project root?") while the verify-notes and verify-pairing gates silently
reported zero notes/pairs and passed (F2 — against rules 5 and 6). One
rule for everyone: inside a git work tree, run from its root — announced,
never silent; outside one, keep the caller's cwd and let the missing
markers fail loud as before.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def anchor_to_git_root(tool: str) -> None:
    """Chdir to the git work-tree root when the caller is deeper inside."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8", errors="replace",  # git speaks UTF-8, not the locale codec (#168)
        )
    except OSError:
        return
    if proc.returncode != 0:
        return  # not a work tree: keep cwd; the tool's own markers fail loud
    root = proc.stdout.strip()
    if root and Path(root).resolve() != Path.cwd().resolve():
        os.chdir(root)
        print(f"{tool}: running from repository root {root}", file=sys.stderr)
