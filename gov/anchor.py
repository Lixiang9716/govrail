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


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "core.quotepath=off", *args],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def _abs(git_out: str) -> Path:
    p = Path(git_out.strip())
    return p if p.is_absolute() else (Path.cwd() / p).resolve()


def history_path(rel: str = "gates.jsonl") -> Path:
    """The main checkout's ``.gov/history/<rel>``, worktree-aware.

    ``git rev-parse --git-common-dir`` resolves the shared git dir of every
    worktree; its parent is the main checkout. Outside a work tree (or when
    git is unavailable) the cwd-relative path stands — the tools resolve
    repositories by cwd (D21). Three shapes used to write through the
    wrong parent here:

    - a SUBMODULE's common dir is ``<super>/.git/modules/<name>`` — its
      parent is ``.git/modules``, which is nobody's checkout. A submodule
      is its OWN repository (the toplevel's common dir differs from the
      caller's), so its ledger belongs beside its own working tree;
    - a BARE repository has no working tree at all — the common dir's
      parent was never a project. The repo dir itself is the only root a
      bare repository has;
    - a linked worktree keeps the original ruling: cwd-deep or not, the
      MAIN checkout owns the ledger (same common dir = same repository).
    """
    try:
        common_proc = _git("rev-parse", "--git-common-dir")
        if common_proc.returncode == 0 and common_proc.stdout.strip():
            common = _abs(common_proc.stdout)
            root = common.parent
            top = _git("rev-parse", "--show-toplevel")
            if top.returncode == 0 and top.stdout.strip():
                work_root = Path(top.stdout.strip()).resolve()
                top_common = _git("-C", str(work_root),
                                  "rev-parse", "--git-common-dir")
                same_repo = (top_common.returncode == 0
                             and top_common.stdout.strip()
                             and _abs(top_common.stdout) == common)
                if same_repo:
                    # A worktree of THIS repository (or the main checkout
                    # itself): the main checkout owns the ledger.
                    if root != Path.cwd():
                        return root / ".gov" / "history" / rel
                else:
                    # A different repository (a submodule): anchor beside
                    # its own checkout, never inside <super>/.git/modules.
                    if work_root != Path.cwd():
                        return work_root / ".gov" / "history" / rel
                return Path(".gov/history") / rel
            # No working tree anywhere reachable: a bare repository. Its
            # own dir is the only project root it has.
            return common / ".gov" / "history" / rel
    except OSError:
        pass
    return Path(".gov/history") / rel


def ledger_root(ledger: Path) -> Path | None:
    """The checkout root that owns a history-path ledger.

    `<main>/.gov/history/<name>` → `<main>` — a STRUCTURAL fact of the
    checkout, never derived from the protected path: a linked directory
    makes git's walk-up answer for the attacker (N15). Fewer than three
    components (the cwd-relative fallback shape) means no repository is
    known here — None, and containment degrades to the final component.
    """
    return ledger.parents[2] if len(ledger.parents) >= 3 else None
