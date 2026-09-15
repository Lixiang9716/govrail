#!/usr/bin/env python3
"""A durable inter-process mutex for the plane's read-modify-write paths.

Two invariants, both load-bearing:

- **The lock file is never unlinked.** The unlink-on-release pattern
  re-opens the classic race it was meant to tidy up after: A holds inode
  I behind path P; B opens P and blocks in flock; A closes AND unlinks
  P; C opens P — creating a NEW inode J — and is granted the lock
  immediately. B and C are both inside the critical section, and a
  read-modify-write loses the second writer's data (a decision add could
  lose a decision this way; the merge preflight's own comments call the
  pattern a known defect it refuses to import). A durable 0-byte lock
  file costs one hidden file per critical section and closes the race
  completely: the lock lives on the inode, and the inode never changes.

- **No silent degradation to "no lock".** A platform without a working
  mutex primitive refuses the write path loudly (rule 5): an unlocked
  critical section is worse than none, because it looks like one.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def exclusive(path: Path) -> Iterator[None]:
    """Hold an exclusive inter-process lock on ``path`` until the block exits.

    Creates the (durable) lock file if needed; blocking wait. POSIX uses
    flock; Windows uses msvcrt.locking over the first byte. On a platform
    with neither primitive, raises — callers turn that into their own
    named refusal.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    locked = False
    try:
        if os.name == "nt":
            import msvcrt

            # LK_LOCK blocks, retrying for ~10s before raising; loop so a
            # longer queue still gets in (each retry re-arms the timeout).
            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    continue
        else:
            try:
                import fcntl
            except ImportError as e:  # no flock and not Windows: refuse loud
                raise RuntimeError(
                    f"no inter-process lock primitive on this platform — "
                    f"refusing to write {path} unserialized (rule 5)") from e
            fcntl.flock(fd, fcntl.LOCK_EX)
        locked = True
        yield
    finally:
        try:
            if locked and os.name == "nt":
                import msvcrt

                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            # POSIX: close() releases the flock; no explicit unlock needed.
        except OSError:
            pass
        os.close(fd)
