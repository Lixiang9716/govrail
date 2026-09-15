"""The durable inter-process mutex: no unlink race, no silent no-lock.

H2's pattern — flock a path, then close AND unlink it — let a third
process create a fresh inode and enter the critical section beside the
second waiter, losing writes. The lock file here is durable: the mutex
lives on the inode, and the inode never changes.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

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
            capture_output=True, text=True, timeout=30)
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
