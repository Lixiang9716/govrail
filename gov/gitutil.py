#!/usr/bin/env python3
"""Shared git plumbing: one listing policy for every file-enumeration call.

git quotes non-ASCII paths by default (``core.quotepath=true``), emitting
``"docs/\344\270\255\346\226\207.md"`` — a name no downstream matcher, scanner,
or counter can match (a docs-side gate silently scoped out, conflict
markers unreadable and skipped, D-numbers under-counted on a ref). Every
listing in this module runs with ``-c core.quotepath=off`` and splits on
NUL, so callers always see the real path; paths round-trip through
``surrogateescape`` so a name that is not valid UTF-8 on disk still opens.

Listings also scrub the ``GIT_*`` variable family: this plane resolves
repositories by cwd (the hooks unset the same variables before calling
gov), so an inherited ``GIT_DIR`` must not silently re-domain a listing.

Anything here that must not depend on the platform's ``/dev/null`` (empty
tree, zero-commit probes) goes through git itself, never through host
paths — ``git mktree`` with empty input works on every platform.
"""
from __future__ import annotations

import os
import subprocess
from functools import lru_cache

_QUOTEPATH_OFF = ["-c", "core.quotepath=off"]

# Repository-resolving variables: listings answer "what changed here", and
# "here" is the caller's work tree — never an inherited redirect (#20/D33).
_HOSTILE_PREFIX = "GIT_"


def scrubbed_env() -> dict:
    """Environment for git subprocesses: no GIT_* inheritance."""
    return {k: v for k, v in os.environ.items() if not k.startswith(_HOSTILE_PREFIX)}


def git(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    """Run git with the plane's listing policy applied; bytes decoded with
    surrogateescape so arbitrary on-disk names survive the round-trip."""
    return subprocess.run(
        ["git", *_QUOTEPATH_OFF, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
        env=scrubbed_env(),
        check=check,
    )


def _lines_z(proc: subprocess.CompletedProcess) -> list[str]:
    """Split a NUL-separated listing; the trailing empty field is dropped."""
    return [f for f in proc.stdout.split("\0") if f]


def has_head() -> bool:
    """True when the repository has at least one commit."""
    return git("rev-parse", "--verify", "--quiet", "HEAD").returncode == 0


def toplevel() -> str | None:
    """The work-tree root of the caller's cwd, or None outside a repository."""
    proc = git("rev-parse", "--show-toplevel")
    if proc.returncode != 0:
        return None
    root = proc.stdout.strip()
    return root or None


def common_dir() -> str | None:
    """The resolved git common dir, or None outside a repository."""
    proc = git("rev-parse", "--git-common-dir")
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    if not out:
        return None
    # Under the main worktree git prints the RELATIVE ".git".
    return os.path.abspath(out)


def object_format() -> str:
    """The repository's object format: "sha1" (default) or "sha256"."""
    proc = git("rev-parse", "--show-object-format")
    out = proc.stdout.strip() if proc.returncode == 0 else ""
    return out or "sha1"


def zero_oid() -> str:
    """The all-zero object id in this repository's format (40 or 64 hex)."""
    return "0" * (64 if object_format() == "sha256" else 40)


@lru_cache(maxsize=1)
def empty_tree() -> str:
    """The empty tree object's id, computed by git itself.

    ``git hash-object -t tree /dev/null`` needs a host device node and
    fails on Windows under a non-MSYS parent; ``git mktree`` over an empty
    stdin needs nothing but git, and answers in the repository's own
    object format.
    """
    proc = subprocess.run(
        ["git", "mktree"],
        input="", text=True, capture_output=True, encoding="utf-8",
        env=scrubbed_env(),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git mktree failed: {(proc.stderr or '').strip()}")
    return proc.stdout.strip()


def changed_files(base: str | None = None) -> tuple[list[str], str | None]:
    """Tracked diff against ``base`` plus untracked files; (files, error).

    A zero-commit repository has no ``base`` to diff against (the untracked
    listing *is* the change) — handled here so every caller shares the
    semantics instead of re-deriving the HEAD probe.
    """
    files: set[str] = set()
    commands: list[list[str]] = []
    if base is not None and has_head():
        commands.append(["diff", "--name-only", "-z", base])
    commands.append(["ls-files", "--others", "--exclude-standard", "-z"])
    for args in commands:
        proc = git(*args)
        if proc.returncode != 0:
            return [], (proc.stderr or proc.stdout).strip()
        files.update(_lines_z(proc))
    return sorted(files), None


def staged_files() -> tuple[list[str], str | None]:
    """Paths in the index (``diff --cached --name-only``), NUL-split."""
    proc = git("diff", "--cached", "--name-only", "-z")
    if proc.returncode != 0:
        return [], (proc.stderr or proc.stdout).strip()
    return _lines_z(proc), None


def index_blob_oid(path: str) -> str | None:
    """The blob id ``path`` has in the index, or None when not staged."""
    proc = git("ls-files", "--stage", "-z", "--", path)
    if proc.returncode != 0:
        return None
    for entry in _lines_z(proc):
        fields = entry.split("\t", 1)[0].split()
        if len(fields) >= 2 and fields[2] == "0":
            return fields[1]
    return None


def index_content(path: str) -> bytes | None:
    """The staged bytes of ``path`` (``git show :<path>``), or None when the
    path is not in the index (new-untracked or staged for deletion)."""
    proc = subprocess.run(
        ["git", *_QUOTEPATH_OFF, "show", f":{path}"],
        capture_output=True,
        env=scrubbed_env(),
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def tracked_names(rev: str, path: str) -> tuple[list[str], str | None]:
    """All tracked names under ``path`` at ``rev`` (ls-tree, NUL-split)."""
    proc = git("ls-tree", "-r", "--name-only", "-z", rev, "--", path)
    if proc.returncode != 0:
        return [], (proc.stderr or proc.stdout).strip()
    return _lines_z(proc), None


def hooks_dir() -> str | None:
    """Where this repository's hooks actually run from.

    ``core.hooksPath`` wins when set (husky/lefthook users) — a hook
    written to ``.git/hooks`` there would be installed, manifested, and
    never executed. Relative ``core.hooksPath`` values resolve against the
    work-tree root, matching git's own resolution. Otherwise the common
    dir's ``hooks/``: a linked worktree's hooks live in the shared git
    dir, and its own ``$GIT_DIR`` is a ``worktrees/<name>`` subdirectory.
    """
    proc = git("config", "--get", "core.hooksPath")
    if proc.returncode == 0:
        configured = proc.stdout.strip()
        if configured:
            root = toplevel()
            if os.path.isabs(configured) or root is None:
                return configured
            return os.path.join(root, configured)
    common = common_dir()
    return os.path.join(common, "hooks") if common else None
