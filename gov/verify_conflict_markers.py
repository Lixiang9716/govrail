#!/usr/bin/env python3
"""Fail when changed files still carry git conflict markers (#104, D38).

``git add`` during a rebase happily stages ``<<<<<<< / ======= / >>>>>>>``
blocks, and ``git rebase --continue`` commits them without complaint —
git refuses to police its own conflict text because it cannot tell a
real marker from a quoted one. Nothing in the standard gate set
(notes, pairing, tests, source-limits) inspects file content, so a
docs-only diff can ship markers to main. This gate is that missing
content check: grep-level, scoped to the files the diff touches.

What counts as a marker:

- a line starting with ``<<<<<<<``, ``>>>>>>>``, or ``|||||||`` (the
  diff3 base marker) followed by whitespace or end-of-line — primary
  evidence, flagged on its own;
- a bare ``=======`` line — flagged only when the same file also holds
  a primary marker, so Markdown setext underlines stay legal (#104's
  "sibling marker" rule);
- a line containing the token ``gov:ignore-marker`` is exempt — the
  documented escape hatch for deliberate string literals and for docs
  that quote markers.

Content is read from the working tree (what ``git add`` would stage);
binary files (a NUL byte) and deleted paths are skipped. The default
base is ``auto`` — the note-presence cascade: a dirty worktree reviews
the working tree (``HEAD``), a clean one reviews the commits ahead of
upstream, else the last commit, else everything — so pre-push and CI
see the pushed work. Exit codes: 0 = clean; 1 = markers found, each
named ``file:line``; 2 = unrunnable prerequisites — fail loud, never
silently pass.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

try:  # package context (`gov ...`)
    from .root import anchor_to_git_root
except ImportError:  # direct script execution (self-test runs files by path)
    from root import anchor_to_git_root

PROG = "verify_conflict_markers"
IGNORE_TOKEN = "gov:ignore-marker"
# Exactly seven marker characters, then whitespace or end-of-line:
# `<<<<<<< HEAD` matches; `<<<<<<<<` (eight) and `<<<text` do not.
PRIMARY_RX = re.compile(r"^(?:<{7}|>{7}|\|{7})(?=\s|$)")
# A bare ======= line counts only beside a primary marker (sibling rule).
BARE_RX = re.compile(r"^={7}[ \t]*$")


def _run_git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def _resolve_auto_base() -> tuple[str, str]:
    """The note-presence cascade (F1/D21): what does THIS change carry?

    1. dirty worktree      -> HEAD          (review the working tree)
    2. clean + upstream    -> up...HEAD     (review the unpushed commits)
    3. clean, no upstream  -> HEAD~1        (review the last commit)
    4. single commit       -> the empty tree (everything is the change)
    """
    status = _run_git(["status", "--porcelain"])
    if status.returncode == 0 and status.stdout.strip():
        return "HEAD", "dirty worktree — reviewing the working tree"
    up = _run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
    if up.returncode == 0 and up.stdout.strip():
        return f"{up.stdout.strip()}...HEAD", "clean tree — reviewing commits ahead of upstream"
    if _run_git(["rev-parse", "--verify", "--quiet", "HEAD~1"]).returncode == 0:
        return "HEAD~1", "clean tree, no upstream — reviewing the last commit"
    tree = _run_git(["hash-object", "-t", "tree", "/dev/null"])
    return tree.stdout.strip(), "clean tree, single commit — reviewing everything"


def _changed_files(base: str) -> tuple[list[str], str | None]:
    """Tracked diff plus untracked files against ``base``; error message."""
    files: set[str] = set()
    commands: list[tuple[list[str], bool]] = [
        (["git", "diff", "--name-only", base], True),
        (["git", "ls-files", "--others", "--exclude-standard"], False),
    ]
    for cmd, needs_head in commands:
        if needs_head and _run_git(
            ["rev-parse", "--verify", "--quiet", "HEAD"]
        ).returncode != 0:
            continue  # zero-commit repo: the untracked listing is the change
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            return [], proc.stderr.strip()
        files.update(f for f in proc.stdout.splitlines() if f)
    return sorted(files), None


def _scan(path: str) -> list[tuple[int, str]]:
    """(line number, matched marker) for each marker in one file."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return []  # deleted or unreadable: nothing to scan
    if b"\x00" in data:
        return []  # binary content: markers are not text there
    findings: list[tuple[int, str]] = []
    bare: list[tuple[int, str]] = []
    primaries = False
    for no, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
        if IGNORE_TOKEN in line:
            continue  # the documented escape hatch
        if PRIMARY_RX.match(line):
            primaries = True
            findings.append((no, line[:7]))
        elif BARE_RX.match(line):
            bare.append((no, line[:7]))
    if primaries:
        findings.extend(bare)  # a bare ======= counts only with a sibling
    return sorted(findings)


def main(argv: list[str] | None = None) -> int:
    anchor_to_git_root(PROG)
    parser = argparse.ArgumentParser(
        prog="gov verify-conflict-markers",
        description="Fail when changed files contain git conflict markers "
                    "(<<<<<<< / ======= / >>>>>>>).",
    )
    parser.add_argument("--base", default="auto",
                        help="git base to diff against (default: auto — dirty "
                             "tree: HEAD; clean: upstream..HEAD, else HEAD~1, "
                             "else everything; pass an explicit ref to pin)")
    parser.add_argument("--staged", action="store_true",
                        help="scan only the index (git diff --cached) — quiet on a "
                             "clean index (D28: long-session noise reduction)")
    args = parser.parse_args(argv)

    if args.staged:
        proc = _run_git(["diff", "--name-only", "--cached"])
        if proc.returncode != 0:
            print(f"{PROG}: --staged failed: {proc.stderr.strip()}", file=sys.stderr)
            return 2
        files = [f for f in proc.stdout.splitlines() if f]
        if not files:
            return 0  # clean index: silent, per the contract
    else:
        base, why = (args.base, "") if args.base != "auto" else _resolve_auto_base()
        files, err = _changed_files(base)
        if err is not None:
            print(f"{PROG}: cannot diff against {base!r}: {err}", file=sys.stderr)
            return 2
        print(f"{PROG}: base={base}" + (f" ({why})" if why else ""))

    findings = [(f, no, marker) for f in files for no, marker in _scan(f)]
    for f, no, marker in findings:
        print(f"{f}:{no}: conflict marker {marker!r} — resolve the merge, or "
              f"append '{IGNORE_TOKEN}' to exempt a deliberate literal")
    if findings:
        n_files = len({f for f, _, _ in findings})
        print(f"{PROG}: {len(findings)} marker(s) in {n_files} file(s) — git "
              "will not police its own conflict text; the gate does (D38)")
        return 1
    print(f"{PROG}: {len(files)} changed file(s) scanned, no conflict markers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
