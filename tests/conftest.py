"""Pin the plane's runtime contract for the test process itself.

The CI gbk-locale job runs plain ``pytest`` under ``LC_ALL=zh_CN.GBK``:
without UTF-8 mode, Python's FILESYSTEM encoding is GBK there, so
non-ASCII test file names land as GBK bytes and every utf-8 decode of a
listing mojibakes — the stdio wall (#168) never covered the
filesystem/subprocess half. The CLI re-execs under PEP 540 UTF-8 mode
at its entry (``ensure_utf8_runtime``); the test process takes the same
treatment here, at collection time, before any test imports gov code.
Under a UTF-8 host (and on Windows, whose path API is UTF-8 already)
this is a no-op.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gov.root import ensure_utf8_runtime

ensure_utf8_runtime(force_exec=True)


_WORKER_TMPDIRS: list[str] = []


def pytest_configure(config):
    """Give each xdist worker a PRIVATE temp area.

    Tests that snapshot the global tempdir to prove "no scratch left
    behind" (test_run_merge's byte-identical check) must not see a
    sibling worker's live gov-merge-* directory — that collision turned
    the merge integrity test red on the first parallel CI run. A private
    TMPDIR per worker scopes the snapshot to the worker's own activity;
    gov subprocesses inherit it via the environment.
    """
    worker = getattr(config, "workerinput", None)
    if not worker:
        return
    import os
    import tempfile

    private = tempfile.mkdtemp(prefix=f"gov-pytest-{worker['workerid']}-")
    _WORKER_TMPDIRS.append(private)
    for var in ("TMPDIR", "TEMP", "TMP"):
        os.environ[var] = private
    tempfile.tempdir = private  # reset the module's cached resolution too


def pytest_unconfigure(config):
    if getattr(config, "workerinput", None) is None:
        return
    import shutil

    for private in _WORKER_TMPDIRS:
        shutil.rmtree(private, ignore_errors=True)
