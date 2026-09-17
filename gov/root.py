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


def force_utf8_stdio() -> None:
    """Print in UTF-8 regardless of the platform locale (#168).

    On Windows, stdout/stderr attached to a pipe default to the ANSI code
    page (cp1252/GBK/...), while everything this plane prints — repo
    paths, note and decision prose, captured gate output — is UTF-8 by
    convention. A character the locale codec cannot represent crashed the
    tool mid-report (gates died re-printing a child's output). UTF-8 with
    errors="replace" keeps the bytes valid for every downstream consumer
    and never crashes on legacy content; a real console is unaffected
    (PEP 528 already gives it UTF-8). Best-effort by contract: a stream
    that cannot be reconfigured (pytest's capsys, a replaced object)
    keeps its encoding — never worth failing over.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def needs_utf8_runtime() -> bool:
    """True when this process still decodes with the host locale.

    The one predicate both callers with an opinion consult — the CLI's
    re-exec in ``ensure_utf8_runtime`` and the test conftest's
    capture-aware restart (which must suspend pytest's capture BEFORE
    exec'ing, or the report lands in a temp file nobody dumps). It was
    byte-level duplicated in the conftest, and a copy that decides
    whether the wall stands is one edit away from re-blindfolding the
    gbk job — review R7 collapsed it back to one home.
    """
    return not (sys.flags.utf8_mode
                or sys.getfilesystemencoding().lower().startswith("utf"))


def ensure_utf8_runtime(force_exec: bool = False) -> None:
    """One runtime contract for every process in this plane: UTF-8.

    #168 pinned stdio; a hostile locale (the zh-CN GBK host, CI's
    gbk-locale job) kept two more doors open: Python's FILESYSTEM
    encoding follows the locale, so non-ASCII names landed on disk as
    GBK bytes that no utf-8 listing decode can read back, and unpinned
    subprocess text reads decoded the locale codec. ``PYTHONUTF8=1``
    hands the contract to every Python child this process spawns; the
    process itself re-execs under PEP 540 UTF-8 mode when it entered
    through a real CLI entry. Windows already speaks UTF-8 for paths
    (PEP 529) and its stdio wall is ``force_utf8_stdio``'s, so there
    this function only exports the env.

    Library calls into gov from a live interpreter (tests, embeddings)
    must not restart the process — pass ``force_exec`` only from a
    process's own bootstrap (the test conftest), never mid-run.
    """
    os.environ["PYTHONUTF8"] = "1"
    if not needs_utf8_runtime():
        return
    if "pytest" in sys.modules and not force_exec:
        return  # a library call inside a test run must not restart it
    argv0 = sys.argv[0] or ""
    import shutil

    main_spec = getattr(sys.modules.get("__main__"), "__spec__", None)
    if main_spec is not None and getattr(main_spec, "name", ""):
        # `python -m <pkg>`: re-enter through the module machinery —
        # executing the resolved __main__.py by path would break
        # package-relative imports, and the basename heuristic cannot
        # tell gov's __main__ from pytest's.
        argv = [sys.executable, "-X", "utf8", "-m", main_spec.name,
                *sys.argv[1:]]
    elif argv0 not in ("-c", ""):
        script = shutil.which(argv0) or argv0
        argv = [sys.executable, "-X", "utf8", script, *sys.argv[1:]]
    else:
        return  # no reliable way to reconstruct a -c entry; env carries it
    # execv with BYTES: str args are encoded with the CURRENT (still
    # hostile) filesystem codec, and the re-exec'd interpreter would
    # decode them UTF-8 — a CJK argv term becomes mojibake at the
    # doorway. UTF-8-encoding the bytes ourselves survives the hop.
    exe = os.fsencode(sys.executable)
    argv_bytes = [exe, b"-X", b"utf8"] + [
        a if isinstance(a, bytes) else a.encode("utf-8", "surrogateescape")
        for a in argv[1:]]
    os.execv(exe, argv_bytes)  # replaces the process; never returns


def anchor_to_git_root(tool: str) -> None:
    """Chdir to the git work-tree root when the caller is deeper inside.

    Also pins stdio to UTF-8 (#168): root anchoring is every root-anchored
    tool's first statement, so the wall is up before the first report line
    is printed.

    The resolution ignores the GIT_DIR family (same policy as the hooks,
    which unset them before calling gov): a tool that anchors by cwd must
    not be silently re-pointed at some other repository by an inherited
    variable — locks refuse such an env loudly for the same reason.
    """
    force_utf8_stdio()
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8", errors="replace",  # git speaks UTF-8, not the locale codec (#168)
            env=env,
        )
    except OSError:
        return
    if proc.returncode != 0:
        return  # not a work tree: keep cwd; the tool's own markers fail loud
    root = proc.stdout.strip()
    if root and Path(root).resolve() != Path.cwd().resolve():
        os.chdir(root)
        print(f"{tool}: running from repository root {root}", file=sys.stderr)
