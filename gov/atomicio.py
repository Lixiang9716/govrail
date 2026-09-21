#!/usr/bin/env python3
"""One atomic-write policy for the plane's record files.

A record file must never be observable half-written: the writer saves to
a temp file in the destination directory and ``os.replace``s it into
place (atomic on every supported platform). Two details used to be
gotten wrong piecemeal and live here now:

- **fsync before replace** — a crash after replace-but-before-disk must
  not leave an empty or truncated ledger behind;
- **permissions preserved** — mkstemp creates 0600; overwriting a 0644
  ledger with that mode silently made it unreadable to the other
  collaborators on a shared machine.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _target_mode(path: Path) -> int:
    """The existing file's mode, else the admin's umask applied to 0666
    (a hardcoded 0644 would leak ledgers global-readable on shared
    machines; Windows enforces no POSIX mode bits)."""
    try:
        return path.stat().st_mode & 0o777
    except OSError:
        if os.name == "nt":
            return 0o644
        umask = os.umask(0)
        os.umask(umask)
        return 0o666 & ~umask


def _atomic_replace(path: Path, data: bytes, mode: int,
                    fsync: bool) -> None:
    """mkstemp in the destination directory, write, fsync, chmod,
    os.replace — then fsync the DIRECTORY (replace(2) is crash-safe but
    not power-loss-safe; platforms without a directory fd skip it)."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name,
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            if fsync:
                f.flush()
                os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
        if fsync:
            try:
                dirfd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(dirfd)
                finally:
                    os.close(dirfd)
            except OSError:
                pass
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_text(path: Path, text: str, *, fsync: bool = True,
               root: Path | None = None) -> None:
    """Atomically (re)write ``path`` with ``text``.

    The temp file inherits the existing file's mode when the file exists
    (a rewrite must not change who could read it) and the umask's answer
    otherwise.
    """
    assert_contained(path, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_replace(path, text.encode("utf-8"), _target_mode(path), fsync)


class SymlinkRefused(RuntimeError):
    """A state path is a symlink pointing somewhere else.

    The plane's persistent state lives under the repository; a symlink
    planted at a ledger path would turn every honest writer into a
    courier appending plane data (caller identity, gate output) to a
    file outside — or a FIFO streaming it live (N10). Writes refuse to
    follow, naming the path.
    """


def assert_not_symlink(path: Path) -> None:
    """lstat the FINAL path component; refuse a symlink there.

    Belt to O_NOFOLLOW's suspenders on POSIX (the flag closes the
    check-to-open window); on Windows, where the flag does not exist,
    this precheck is the whole guard."""
    if path.is_symlink():
        raise SymlinkRefused(
            f"{path}: is a symlink — refusing to follow; the plane's "
            "state stays inside the repository (N10). Remove the link "
            "or point it at a path you manage.")


def assert_contained(path: Path, root: Path | None) -> None:
    """Refuse a state path that lives — or walks — outside ``root``.

    ``root`` is the containment boundary and comes from the PROCESS: the
    anchored runner's repository, or the ledger's own checkout derived
    from the common dir. It is NEVER resolved from the protected path —
    a linked directory makes git's walk-up answer for the attacker
    ("not a repository" → step aside → the write couriers on), which is
    N7's anchor-pollution lesson at this layer (N15, probed).

    Two judgments, both read-only:

    - ``realpath`` the path: where would a write LAND? Outside ``root``
      → refuse. This kills the directory variant outright.
    - lstat every component between ``root`` and the final: a link ON
      the way is refused even when it happens to point somewhere inside.

    ``root=None``: nothing is known about a repository here — the
    final-component refusal is all that remains.

    """
    assert_not_symlink(path)
    if root is None:
        return
    root_real = os.path.realpath(root)
    real = os.path.realpath(path)
    if real != root_real and not real.startswith(root_real + os.sep):
        raise SymlinkRefused(
            f"{path}: resolves to {real} — outside the repository "
            f"({root_real}); the plane's state stays inside the "
            "repository (N10)")
    # the walk runs on the ORIGINAL lexical components — realpath would
    # resolve the very links being judged, and the walk would find only
    # clean directories (N15's second lesson, same probe)
    rel = os.path.relpath(path, root)
    cur = Path(root)
    for comp in rel.split(os.sep):
        if comp in (".", ""):
            continue
        cur = cur / comp
        if cur.is_symlink():
            raise SymlinkRefused(
                f"{cur}: is a symlink on a state path — refusing; the "
                "plane's state stays inside the repository (N10)")


def append_line(path: Path, data: str, *, fsync: bool = True,
                root: Path | None = None) -> None:
    """Append one UTF-8 chunk through O_NOFOLLOW, symlink-refusing.

    The single append policy for every ledger: one file descriptor, one
    O_APPEND write loop (partial-write safe), fsync before close, and
    the final component may not be a symlink."""
    assert_contained(path, root)  # before the mkdir: a linked parent is the hole
    path.parent.mkdir(parents=True, exist_ok=True)
    assert_not_symlink(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o666)  # umask shapes a new ledger's mode
    try:
        blob = data.encode("utf-8")
        while blob:  # honor partial writes; each retry re-appends at EOF
            blob = blob[os.write(fd, blob):]
        if fsync:
            os.fsync(fd)
    finally:
        os.close(fd)


def write_bytes(path: Path, data: bytes, *, fsync: bool = True,
                root: Path | None = None) -> None:
    """Atomically (re)write ``path`` with bytes — BINARY, never text
    mode: a text-mode write translates \n to \r\n on Windows, and the
    hook/workflow templates must land byte-identical to their sources
    for uninstall's byte-level comparisons."""
    assert_contained(path, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_replace(path, data, _target_mode(path), fsync)


def ensure_line(path: Path, line: str) -> bool:
    """Idempotently ensure ``path`` carries ``line`` as its own line (#353).

    Runtime artifacts the plane creates inside tracked areas — the
    persistent decision lock is the one outside ``.gov/`` — must not sit
    in ``git status`` forever: an agent's habitual ``git add -A`` tracks
    them, and a zero-byte lock then rides the next diff (the failure #325
    fixed for the task allocator's flock anchor). The init-time ignore
    list covers fresh checkouts; this is the same guarantee at the moment
    the artifact appears, so checkouts that already exist heal on their
    own. Appends the original BYTES (CRLF endings, BOM and non-UTF-8
    content survive) and lands atomically like every write here.

    Hygiene, not a verdict — never raises (rule 5 governs verdicts). A
    symlinked ``path`` is left strictly alone: it may be dotfiles-managed,
    and writing through a link lands in someone's home directory. Returns
    True when the line was appended.
    """
    if path.is_symlink():
        return False
    try:
        raw = path.read_bytes() if path.exists() else b""
    except OSError:
        return False
    have = raw.decode("utf-8-sig", errors="replace").splitlines()
    if line in have:
        return False
    sep = b"" if (not raw or raw.endswith(b"\n")) else b"\n"
    try:
        write_bytes(path, raw + sep + line.encode("utf-8") + b"\n")
    except OSError:
        return False
    return True
