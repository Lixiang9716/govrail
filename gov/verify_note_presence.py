#!/usr/bin/env python3
"""Verify that a non-trivial change carries an Agent Note (D3, rule 2).

Rule 2 of ``.gov/rules.md``: every non-trivial change adds or updates at
least one note. This gate checks the observable half of that promise —
whether a diff that touches behavior-bearing surfaces (code, contracts,
tooling, config) also touches ``.agents/notes/implemented/``. Whether a
specific change is *trivial* stays a human judgment; this gate only warns,
naming the rule, so the warning is a prompt rather than a verdict.

By default a violation is a warning (exit 0, D3: warn, never block);
``--strict`` turns it into a blocking failure (exit 1) for teams that have
earned it. The default base is ``auto`` (F1/D21): a dirty worktree reviews
the working tree (``HEAD``); a clean one reviews the commits ahead of the
upstream, else the last commit, else everything — so the shipped runners
(pre-push hook, CI) see the pushed work instead of an empty diff. Pin with
an explicit ``--base`` when you want a specific range. Unrunnable
prerequisites (git failure, bad ref) exit 2 — fail loud, never silently
pass.

Not every behavior-bearing-looking path deserves a note (#149): task-card
receipts under ``.gov/tasks/`` are machine-written bookkeeping (D43) and
exempt by default, and a repo can exempt more surfaces by declaring
``"note_presence_exempt": [glob, ...]`` in ``.gov/manifest.json`` — same
glob language as gate ``paths`` (``**`` spans directories, ``*`` does not).
The advisory then fires only where the repo has said a note is genuinely
expected. A manifest that exists but cannot be parsed, or an ill-shaped
key, exits 2 (rule 5: fail loud, name it); an absent manifest or key means
built-in defaults only.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:  # package context (`gov verify-note-presence`)
    from .gates import _glob_regex
except ImportError:  # direct script execution (self-test runs files by path)
    from gates import _glob_regex

NOTES_DIR = ".agents/notes/implemented"
RULE = ".gov/rules.md rule 2 (every non-trivial change carries an Agent Note)"
MANIFEST = ".gov/manifest.json"

# Surfaces whose change is presumptively non-trivial. Documentation and the
# notes themselves are excluded: docs answer to the pairing gate, and a
# notes-only diff is the note. Root-level presentation files (README,
# CHANGELOG) are trivial; other root .md files (DESIGN.md, ARCHITECTURE.md)
# are treated as behavior-bearing — in doc-driven repositories they are the
# contract (D20). Task-card receipts (.gov/tasks/**, #125/D43) are
# machine-written, rules-hash-pinned bookkeeping — the task system's own
# tamper-evident output, never a decision — so closing a task is exempt by
# default (#149): a gate that always warns on routine workflows teaches
# agents to stop reading it.
TRIVIAL_PREFIXES = (".agents/notes/", "docs/", ".gov/tasks/")
TRIVIAL_ROOT_STEMS = ("README", "CHANGELOG", "CHANGES", "CONTRIBUTING")
TRIVIAL_SUFFIXES = (".i18n.yaml",)


def _is_trivially_scoped(path: str) -> bool:
    if path.startswith(TRIVIAL_PREFIXES):
        return True
    if "/" in path:
        return path.endswith(TRIVIAL_SUFFIXES)
    stem = path[: -len(".md")] if path.endswith(".md") else path
    return stem.startswith(TRIVIAL_ROOT_STEMS)


def _manifest_path() -> Path:
    """The repo's manifest, from the git root so a subdirectory invocation
    reads the same file the gate runner does; cwd fallback outside git."""
    top = _run_git(["rev-parse", "--show-toplevel"])
    if top.returncode == 0 and top.stdout.strip():
        return Path(top.stdout.strip(), MANIFEST)
    return Path(MANIFEST)


def _load_exempt_globs() -> tuple[list[str], str | None]:
    """``(globs, error)`` — repo-declared exemptions from ``.gov/manifest.json``.

    ``"note_presence_exempt": ["docs/**", ...]`` names the paths where a
    note is NOT expected (#149); the advisory fires only outside them.
    Absent manifest or absent key = built-in defaults only — the manifest
    is init's record and stays optional; its unknown keys are none of this
    gate's business. A manifest that exists but is unreadable, or a key of
    the wrong shape, is returned as an error for the caller to fail loud
    on (rule 5), naming the file and the key.
    """
    path = _manifest_path()
    if not path.is_file():
        return [], None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [], f"cannot read {path}: {e}"
    if not isinstance(data, dict):
        return [], f"{path} must be a JSON object"
    globs = data.get("note_presence_exempt")
    if globs is None:
        return [], None
    if not isinstance(globs, list) or not all(isinstance(g, str) for g in globs):
        return [], f"'note_presence_exempt' in {path} must be an array of strings"
    if any(not g.strip() for g in globs):
        return [], f"'note_presence_exempt' in {path} contains an empty pattern"
    return globs, None


def _is_exempt(path: str, globs: list[str]) -> bool:
    return any(_glob_regex(g).match(path) for g in globs)


def _changed_files(base: str) -> tuple[list[str], str | None]:
    """Tracked diff plus untracked files against ``base``; error message."""
    files: set[str] = set()
    commands: list[tuple[list[str], bool]] = [
        (["git", "diff", "--name-only", base], True),
        (["git", "ls-files", "--others", "--exclude-standard"], False),
    ]
    for cmd, needs_head in commands:
        if needs_head and subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", "HEAD"],
            capture_output=True,
        ).returncode != 0:
            continue  # zero-commit repo: there is no HEAD to diff against;
            # the untracked listing below is the whole change (D13: a fresh
            # install's first run must not go red)
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            return [], proc.stderr.strip()
        files.update(f for f in proc.stdout.splitlines() if f)
    return sorted(files), None


def _run_git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def _resolve_auto_base() -> tuple[str, str]:
    """Pick the base that answers 'what does THIS change carry a note for?'.

    The cascade (F1: the shipped runners — pre-push hook and CI — see a
    clean tree, where a fixed HEAD base diffs nothing):
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gov verify-note-presence",
        description="Warn when a non-trivial diff carries no Agent Note.",
    )
    parser.add_argument("--base", default="auto",
                        help="git base to diff against (default: auto — dirty "
                             "tree: HEAD; clean: upstream..HEAD, else HEAD~1, "
                             "else everything; pass an explicit ref to pin)")
    parser.add_argument("--strict", action="store_true",
                        help="a violation blocks (exit 1) instead of warning")
    parser.add_argument("--staged", action="store_true",
                        help="review only the index (git diff --cached) — quiet on a "
                             "clean index (D28: long-session noise reduction)")
    args = parser.parse_args(argv)

    if args.staged:
        import subprocess as _sp
        proc = _sp.run(["git", "diff", "--name-only", "--cached"],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            print(f"verify_note_presence: --staged failed: {proc.stderr.strip()}",
                  file=sys.stderr)
            return 2
        files = [f for f in proc.stdout.splitlines() if f]
        if not files:
            return 0  # clean index: silent, per the contract
    else:
        base, why = (args.base, "") if args.base != "auto" else _resolve_auto_base()
        files, err = _changed_files(base)
        if err is not None:
            print(f"verify_note_presence: cannot diff against {base!r}: {err}",
                  file=sys.stderr)
            return 2
        print(f"verify_note_presence: base={base}"
              + (f" ({why})" if why else ""))

    exempt_globs, err = _load_exempt_globs()
    if err is not None:
        print(f"verify_note_presence: {err}", file=sys.stderr)
        return 2
    if exempt_globs:
        print(f"verify_note_presence: exempt ({MANIFEST} note_presence_exempt): "
              + ", ".join(exempt_globs))

    non_trivial = [f for f in files
                   if not _is_trivially_scoped(f)
                   and not _is_exempt(f, exempt_globs)]
    notes = [f for f in files if f.startswith(NOTES_DIR)]

    if not non_trivial or notes:
        # Nothing behavior-bearing, or the change carries its note.
        print(f"verify_note_presence: {len(non_trivial)} non-trivial file(s), "
              f"{len(notes)} note file(s) — ok")
        return 0

    listing = ", ".join(non_trivial[:5]) + (" …and "
              f"{len(non_trivial) - 5} more" if len(non_trivial) > 5 else "")
    print(f"verify_note_presence: {len(non_trivial)} non-trivial file(s) "
          f"({listing}) changed with no note under {NOTES_DIR}/")
    # #149: say which absence this is. The warning means "no note anywhere
    # in the diff" — the weaker reading ("a note exists, just not for these
    # specific paths") cannot occur: any note file in the diff passes the
    # gate, since per-path attribution is not checkable.
    print("  no note file appears anywhere in this diff (not merely 'none "
          "for these paths' — any note file in the diff passes this gate)")
    print(f"  if the change is non-trivial, add or update a note (see {RULE})")
    print("  if it is truly trivial (typo, format, local rename), ignore this warning")
    if args.strict:
        print("verify_note_presence: violation (--strict)")
        return 1
    print("verify_note_presence: warning (advisory; --strict to enforce)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
