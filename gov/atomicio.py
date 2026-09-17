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


def write_text(path: Path, text: str, *, fsync: bool = True) -> None:
    """Atomically (re)write ``path`` with ``text``.

    The temp file inherits the existing file's mode when the file exists
    (a rewrite must not change who could read it) and 0644 otherwise.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = path.stat().st_mode & 0o777
    except OSError:
        if os.name == "nt":
            mode = 0o644  # Windows enforces no POSIX mode bits
        else:
            # New file: respect the admin's umask (shared machines run
            # 0640 — a hardcoded 0644 would leak ledgers global-readable).
            # The get-umask dance is the standard recipe; the window is
            # one call.
            umask = os.umask(0)
            os.umask(umask)
            mode = 0o666 & ~umask
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name,
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            if fsync:
                f.flush()
                os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
        if fsync:
            # fsync the DIRECTORY too: replace(2) is crash-safe but not
            # power-loss-safe — without a dir fsync the rename itself can
            # be lost while the file content is durable. Best-effort:
            # platforms without a directory fd (Windows) skip it.
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


def append_line(path: Path, data: str, *, fsync: bool = True) -> None:
    """Append one UTF-8 chunk through O_NOFOLLOW, symlink-refusing.

    The single append policy for every ledger: one file descriptor, one
    O_APPEND write loop (partial-write safe), fsync before close, and
    the final component may not be a symlink."""
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
    """Atomically (re)write ``path`` with bytes — the newline-exact
    shape of :func:`write_text` (hook and workflow templates must land
    byte-identical to their sources for uninstall's comparisons)."""
    write_text(path, data.decode("utf-8"), fsync=fsync)
