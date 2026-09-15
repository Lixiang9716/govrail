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
exempt by default, the run history under ``.gov/history/`` is the plane's
own ledger output — and a repo can exempt more surfaces by declaring
``"note_presence_exempt": [glob, ...]`` in ``.gov/manifest.json`` — same
glob language as gate ``paths``. The advisory then fires only where the
repo has said a note is genuinely expected. A manifest that exists but
cannot be parsed, or an ill-shaped key, exits 2 (rule 5: fail loud, name
it); an absent manifest or key means built-in defaults only.

Strict attribution (opt-in, ``.gov/note-presence.json``): the default gate
passes when ANY note file appears in the diff — per-path attribution is
not checkable from the diff alone. A repo that wants the stronger reading
declares ``{"require": [glob, ...]}``: every changed file under a
``require`` glob must be named by at least one implemented note (the note
text cites the path). ``{"trivial": [glob, ...]}`` adds surfaces to the
built-in trivial list. Absent file = default behavior, unchanged; a
present-but-invalid file exits 2 (rule 5).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:  # package context (`gov verify-note-presence`)
    from . import gitutil
    from .gates import _glob_regex
    from .root import anchor_to_git_root
except ImportError:  # direct script execution (self-test runs files by path)
    import gitutil
    from gates import _glob_regex
    from root import anchor_to_git_root

PROG = "verify_note_presence"
NOTES_DIR = ".agents/notes/implemented"
RULE = ".gov/rules.md rule 2 (every non-trivial change carries an Agent Note)"
MANIFEST = ".gov/manifest.json"
CONFIG = ".gov/note-presence.json"
CONFIG_KEYS = ("require", "trivial")

# Surfaces whose change is presumptively non-trivial. Documentation and the
# notes themselves are excluded: docs answer to the pairing gate, and a
# notes-only diff is the note. Root-level presentation files (README,
# CHANGELOG) are trivial; other root .md files (DESIGN.md, ARCHITECTURE.md)
# are treated as behavior-bearing — in doc-driven repositories they are the
# contract (D20). Task-card receipts (.gov/tasks/**, #125/D43) are
# machine-written, rules-hash-pinned bookkeeping — the task system's own
# tamper-evident output, never a decision — so closing a task is exempt by
# default (#149). The run history (.gov/history/**) is the plane's own
# ledger output: gitignored by init (D-gitignore), but untracked-file
# listings in repos initialized before that still saw every run add noise.
TRIVIAL_PREFIXES = (".agents/notes/", "docs/", ".gov/tasks/", ".gov/history/")
TRIVIAL_ROOT_STEMS = ("README", "CHANGELOG", "CHANGES", "CONTRIBUTING")
TRIVIAL_SUFFIXES = (".i18n.yaml",)


def _is_trivially_scoped(path: str, extra_trivial: list[str] | None = None) -> bool:
    if path.startswith(TRIVIAL_PREFIXES):
        return True
    if extra_trivial and any(_glob_regex(g).match(path) for g in extra_trivial):
        return True
    if "/" in path:
        return path.endswith(TRIVIAL_SUFFIXES)
    stem = path[: -len(".md")] if path.endswith(".md") else path
    return stem.startswith(TRIVIAL_ROOT_STEMS)


def _manifest_path() -> Path:
    """The repo's manifest, from the git root so a subdirectory invocation
    reads the same file the gate runner does; cwd fallback outside git."""
    top = gitutil.toplevel()
    if top:
        return Path(top, MANIFEST)
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
        data = json.loads(path.read_text(encoding="utf-8-sig"))
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


def _load_config() -> tuple[dict[str, list[str]], str | None]:
    """``(config, error)`` from the optional ``.gov/note-presence.json``."""
    path = Path(CONFIG)
    if not path.is_file():
        return {"require": [], "trivial": []}, None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        return {"require": [], "trivial": []}, f"cannot read {path}: {e}"
    if not isinstance(data, dict):
        return {"require": [], "trivial": []}, f"{path} must be a JSON object"
    unknown = sorted(set(data) - set(CONFIG_KEYS))
    if unknown:
        return {"require": [], "trivial": []}, (
            f"unknown key(s) in {path}: {', '.join(unknown)} (known: "
            f"{', '.join(CONFIG_KEYS)})")
    for key in CONFIG_KEYS:
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(g, str) for g in value):
            return {"require": [], "trivial": []}, (
                f"'{key}' in {path} must be an array of glob strings")
    return {"require": data.get("require", []),
            "trivial": data.get("trivial", [])}, None


def _is_exempt(path: str, globs: list[str]) -> bool:
    return any(_glob_regex(g).match(path) for g in globs)


def _changed_files(base: str) -> tuple[list[str], str | None]:
    """Tracked diff plus untracked files against ``base``; error message."""
    return gitutil.changed_files(base)


def _resolve_auto_base() -> tuple[str, str]:
    """Pick the base that answers 'what does THIS change carry a note for?'.

    The cascade (F1: the shipped runners — pre-push hook and CI — see a
    clean tree, where a fixed HEAD base diffs nothing):
    1. dirty worktree      -> HEAD          (review the working tree)
    2. clean + upstream    -> up...HEAD     (review the unpushed commits)
    3. clean, no upstream  -> HEAD~1        (review the last commit)
    4. single commit       -> the empty tree (everything is the change)
    """
    status = gitutil.git("status", "--porcelain")
    if status.returncode == 0 and status.stdout.strip():
        return "HEAD", "dirty worktree — reviewing the working tree"
    up = gitutil.git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    if up.returncode == 0 and up.stdout.strip():
        return f"{up.stdout.strip()}...HEAD", "clean tree — reviewing commits ahead of upstream"
    if gitutil.git("rev-parse", "--verify", "--quiet", "HEAD~1").returncode == 0:
        return "HEAD~1", "clean tree, no upstream — reviewing the last commit"
    # git computes the empty tree itself (mktree, empty stdin): no
    # /dev/null dependency, correct under sha256 object format.
    return gitutil.empty_tree(), "clean tree, single commit — reviewing everything"


def _notes_corpus() -> dict[str, str]:
    """path -> text for every implemented note (strict-attribution corpus).

    Read once, searched for every required path: attribution must not
    re-read the whole corpus per changed file.
    """
    corpus: dict[str, str] = {}
    root = Path(NOTES_DIR)
    if not root.is_dir():
        return corpus
    for p in sorted(root.rglob("*.md")):
        try:
            corpus[p.as_posix()] = p.read_text(encoding="utf-8-sig",
                                               errors="replace")
        except OSError:
            continue
    return corpus


def main(argv: list[str] | None = None) -> int:
    # Anchor BEFORE anything resolves a path: every surface here is
    # root-relative, and a subdirectory invocation used to mix a cwd-bound
    # untracked listing with a repo-root-bound diff into one file set.
    anchor_to_git_root(PROG)
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

    cfg, err = _load_config()
    if err is not None:
        print(f"{PROG}: {err}", file=sys.stderr)
        return 2

    if args.staged:
        files, err = gitutil.staged_files()
        if err is not None:
            print(f"{PROG}: --staged failed: {err}", file=sys.stderr)
            return 2
        if not files:
            return 0  # clean index: silent, per the contract
    else:
        base, why = (args.base, "") if args.base != "auto" else _resolve_auto_base()
        files, err = _changed_files(base)
        if err is not None:
            print(f"{PROG}: cannot diff against {base!r}: {err}", file=sys.stderr)
            return 2
        print(f"{PROG}: base={base}" + (f" ({why})" if why else ""))

    exempt_globs, err = _load_exempt_globs()
    if err is not None:
        print(f"{PROG}: {err}", file=sys.stderr)
        return 2
    if exempt_globs:
        print(f"{PROG}: exempt ({MANIFEST} note_presence_exempt): "
              + ", ".join(exempt_globs))

    non_trivial = [f for f in files
                   if not _is_trivially_scoped(f, cfg["trivial"])
                   and not _is_exempt(f, exempt_globs)]
    notes = [f for f in files if f.startswith(NOTES_DIR)]

    # Strict attribution: required paths need a note that NAMES them, not
    # merely a note somewhere in the diff.
    unattributed: list[str] = []
    if cfg["require"]:
        required = [f for f in non_trivial
                    if any(_glob_regex(g).match(f) for g in cfg["require"])]
        if required:
            corpus = _notes_corpus()
            for f in required:
                if not any(f in text for text in corpus.values()):
                    unattributed.append(f)

    if (not non_trivial and not unattributed) or \
            (notes and not unattributed):
        # Nothing behavior-bearing, or the change carries its note and no
        # required path went unattributed.
        print(f"{PROG}: {len(non_trivial)} non-trivial file(s), "
              f"{len(notes)} note file(s) — ok")
        return 0

    if unattributed:
        listing = ", ".join(unattributed[:5]) + (" …and "
                  f"{len(unattributed) - 5} more" if len(unattributed) > 5 else "")
        print(f"{PROG}: {len(unattributed)} required path(s) ({listing}) "
              f"changed with no note naming them under {NOTES_DIR}/ "
              f"(strict attribution: {CONFIG})")
    else:
        listing = ", ".join(non_trivial[:5]) + (" …and "
                  f"{len(non_trivial) - 5} more" if len(non_trivial) > 5 else "")
        print(f"{PROG}: {len(non_trivial)} non-trivial file(s) "
              f"({listing}) changed with no note under {NOTES_DIR}/")
        # #149: say which absence this is. The warning means "no note anywhere
        # in the diff" — the weaker reading ("a note exists, just not for these
        # specific paths") cannot occur in the default mode: any note file in
        # the diff passes the gate, since per-path attribution is not
        # checkable there. Repos that need the stronger reading configure it
        # (see CONFIG, strict attribution above).
        print("  no note file appears anywhere in this diff (not merely 'none "
              "for these paths' — any note file in the diff passes this gate)")
    print(f"  if the change is non-trivial, add or update a note (see {RULE})")
    print("  if it is truly trivial (typo, format, local rename), ignore this warning")
    if args.strict:
        print(f"{PROG}: violation (--strict)")
        return 1
    print(f"{PROG}: warning (advisory; --strict to enforce)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
