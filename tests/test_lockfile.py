"""The durable inter-process mutex: no unlink race, no silent no-lock.

H2's pattern — flock a path, then close AND unlink it — let a third
process create a fresh inode and enter the critical section beside the
second waiter, losing writes. The lock file here is durable: the mutex
lives on the inode, and the inode never changes.
"""
from __future__ import annotations

import subprocess
import sys

import pytest

from gov import lockfile


def test_exclusive_yields_and_keeps_lock_file(tmp_path):
    lock = tmp_path / "mutex.lock"
    with lockfile.exclusive(lock):
        assert lock.exists()  # created for the take
    # released (the block returned) — but the FILE remains: unlinking it
    # re-opens the classic race this module exists to close
    assert lock.exists()
    # and it is immediately takeable again
    with lockfile.exclusive(lock):
        pass


def test_exclusive_creates_parent_dirs(tmp_path):
    lock = tmp_path / "deep" / "nested" / "mutex.lock"
    with lockfile.exclusive(lock):
        pass
    assert lock.exists()


@pytest.mark.skipif(__import__("os").name == "nt",
                    reason="the probe child flocks — a POSIX mechanism; "
                           "Windows exclusivity rides msvcrt.locking inside "
                           "lockfile.exclusive itself")
def test_second_process_blocks_until_release(tmp_path):
    """Cross-process exclusivity, end to end: the child tries a
    non-blocking flock on the same path while this process holds the
    module's lock — it must report the resource as taken."""
    lock = tmp_path / "mutex.lock"
    with lockfile.exclusive(lock):
        child = subprocess.run(
            [sys.executable, "-c",
             "import fcntl, sys\n"
             "f = open(sys.argv[1], 'w')\n"
             "try:\n"
             "    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
             "except OSError:\n"
             "    print('busy')\n"
             "else:\n"
             "    print('free')\n",
             str(lock)],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30)
        assert child.stdout.strip() == "busy"


@pytest.mark.skipif(__import__("os").name == "nt",
                    reason="Windows always has msvcrt — there is no "
                          "primitive-less platform to simulate here")
def test_missing_primitives_refuse_loudly(tmp_path, monkeypatch):
    """No silent no-lock: a platform without a mutex primitive must raise,
    never yield an unprotected critical section (rule 5)."""
    import sys
    lock = tmp_path / "mutex.lock"
    # A None entry in sys.modules makes `import fcntl` raise ImportError —
    # exactly what a platform without the module sees.
    monkeypatch.setitem(sys.modules, "fcntl", None)
    with pytest.raises(RuntimeError, match="no inter-process lock"):
        with lockfile.exclusive(lock):
            pass


def test_windows_lock_retries_only_transient_errors(tmp_path, monkeypatch):
    """EBADF (and friends) must RAISE, not re-arm the 10-second wait —
    a permanent error used to loop forever, ten silent seconds at a
    time. EACCES (held by another process) is the only retry."""
    import errno as _errno
    import os as _os
    import sys as _sys
    import types as _types

    fake = _types.ModuleType("msvcrt")
    takes = {"n": 0}

    def _locking(fd, mode, nbytes):
        if mode != fake.LK_LOCK:
            return  # the unlock call; not a take
        takes["n"] += 1
        if takes["n"] == 1:
            raise OSError(_errno.EACCES, "held by another process")
        # second take succeeds: the lock is acquired

    fake.locking = _locking
    fake.LK_LOCK, fake.LK_UNLCK = 1, 2
    monkeypatch.setitem(_sys.modules, "msvcrt", fake)
    monkeypatch.setattr(_os, "name", "nt")

    lock = tmp_path / "m.lock"
    with lockfile.exclusive(lock):
        pass
    assert takes["n"] == 2  # one transient EACCES survived the wait


def test_windows_lock_raises_on_permanent_errors(tmp_path, monkeypatch):
    import errno as _errno
    import os as _os
    import sys as _sys
    import types as _types

    fake = _types.ModuleType("msvcrt")
    calls = {"n": 0}

    def _locking(fd, mode, nbytes):
        calls["n"] += 1
        raise OSError(_errno.EBADF, "bad file descriptor")

    fake.locking = _locking
    fake.LK_LOCK, fake.LK_UNLCK = 1, 2
    monkeypatch.setitem(_sys.modules, "msvcrt", fake)
    monkeypatch.setattr(_os, "name", "nt")

    with pytest.raises(OSError) as exc:
        with lockfile.exclusive(tmp_path / "m.lock"):
            pass
    assert exc.value.errno == _errno.EBADF
    assert calls["n"] == 1  # raised immediately — no ten-second re-arm
