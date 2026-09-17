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


def write_text(path: Path, text: str, *, fsync: bool = True) -> None:
    """Atomically (re)write ``path`` with ``text``.

    The temp file inherits the existing file's mode when the file exists
    (a rewrite must not change who could read it) and the umask's answer
    otherwise.
    """
    assert_contained(path)
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


def assert_contained(path: Path) -> None:
    """Refuse a symlink on ANY component of a state path.

    O_NOFOLLOW and a final-component lstat are blind to a LINKED
    DIRECTORY: `.gov/history` pointing outside the repository turned
    every ledger open into an outside write with no flag tripped —
    the round-10 review's probes, on the write half the first fix's
    "reads-only" scoping got wrong. The plane's state lives inside the
    work tree that owns the path; every component between that root and
    the final component must be a real directory. Outside any
    repository there is no inside: nothing to contain, nothing to
    refuse."""
    assert_not_symlink(path)
    try:
        from .gitutil import toplevel
    except ImportError:  # direct-module execution
        from gitutil import toplevel
    root = toplevel(str(path.parent))
    if root is None:
        return
    cur = path if path.is_absolute() else Path.cwd() / path
    stop = Path(root)
    cur = cur.parent
    while cur != stop and cur != cur.parent:
        if cur.is_symlink():
            raise SymlinkRefused(
                f"{cur}: is a symlink on a state path — refusing; the "
                "plane's state stays inside the repository (N10)")
        cur = cur.parent


def append_line(path: Path, data: str, *, fsync: bool = True) -> None:
    """Append one UTF-8 chunk through O_NOFOLLOW, symlink-refusing.

    The single append policy for every ledger: one file descriptor, one
    O_APPEND write loop (partial-write safe), fsync before close, and
    the final component may not be a symlink."""
    assert_contained(path)  # before the mkdir: a linked parent is the hole
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


def write_bytes(path: Path, data: bytes, *, fsync: bool = True) -> None:
    """Atomically (re)write ``path`` with bytes — BINARY, never text
    mode: a text-mode write translates \n to \r\n on Windows, and the
    hook/workflow templates must land byte-identical to their sources
    for uninstall's byte-level comparisons."""
    assert_contained(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_replace(path, data, _target_mode(path), fsync)
