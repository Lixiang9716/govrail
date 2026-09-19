#!/usr/bin/env python3
"""Commit-stage lint: ruff --fix on the staged files, fixes restaged.

The lint gate owns the push boundary; this script owns the commit
boundary (DSH's lefthook `--fix` + `stage_fixed` shape, ported to the
gates.json stage contract). It runs ``ruff check --fix`` over the
*.py files in the INDEX, re-adds the files it fixed, and goes red only
on findings autofix cannot clear — so an agent's commit is mechanically
cleaned at commit time instead of costing a red-CI round trip.

One protection DSH's glob jobs lack: a file whose staged content
differs from its worktree content is **skipped by name**, never
fixed-and-restaged — applying a worktree fix and re-adding would
silently swallow unstaged changes the author deliberately kept out of
the commit. Skipped files with findings still turn the gate red, with
their names, so nothing is silently dirty.

Accepts ``--staged`` (the hook runner appends it to every pre-commit
stage gate); outside a commit context (nothing staged) it is a named
no-op. Exit codes follow D2: 0 clean (or fixed-and-restaged), 1
findings remain, 2 usage/config error (ruff missing).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _git(*args: str) -> str:
    proc = subprocess.run(["git", *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print(f"staged-lint: git {' '.join(args)} failed: {proc.stderr}",
              file=sys.stderr)
        raise SystemExit(2)
    return proc.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="staged_lint")
    parser.add_argument("--staged", action="store_true",
                        help="accepted from the hook runner; the script "
                             "always judges the index")
    parser.parse_args(argv)

    staged = [f for f in _git("diff", "--cached", "--name-only",
                              "--diff-filter=ACM").splitlines()
              if f.endswith(".py") and Path(f).is_file()]
    if not staged:
        print("staged-lint: no staged python files — nothing to judge")
        return 0

    fully_staged, partial = [], []
    for f in staged:
        worktree_diff = _git("diff", "--name-only", "--", f).strip()
        (fully_staged if not worktree_diff else partial).append(f)

    if fully_staged:
        try:
            subprocess.run(
                ["ruff", "check", "--fix", *fully_staged],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace")
        except FileNotFoundError:
            print("staged-lint: ruff not installed — the lint gate "
                  "would report MISSING (dev dependency, dogfood-only)",
                  file=sys.stderr)
            raise SystemExit(2)
        fixed = [f for f in fully_staged
                 if _git("diff", "--name-only", "--", f).strip()]
        if fixed:
            _git("add", *fixed)
            print(f"staged-lint: autofixed and restaged {len(fixed)} "
                  f"file(s): {', '.join(fixed)}")

    try:
        remaining = subprocess.run(
            ["ruff", "check", *staged],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace")
    except FileNotFoundError:
        print("staged-lint: ruff not installed — the lint gate "
              "would report MISSING (dev dependency, dogfood-only)",
              file=sys.stderr)
        raise SystemExit(2)
    if remaining.returncode != 0:
        print(remaining.stdout, end="")
        if partial:
            print(f"staged-lint: skipped (partially staged — fix in the "
                  f"worktree, then restage): {', '.join(partial)}",
                  file=sys.stderr)
        print("staged-lint: findings remain after autofix", file=sys.stderr)
        return 1
    if partial:
        print(f"staged-lint: skipped (partially staged): "
              f"{', '.join(partial)}")
    print(f"staged-lint: {len(staged)} staged file(s) clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
