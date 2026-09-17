"""Pin the plane's runtime contract for the test process itself.

The CI gbk-locale job runs plain ``pytest`` under ``LC_ALL=zh_CN.GBK``:
without UTF-8 mode, Python's FILESYSTEM encoding is GBK there, so
non-ASCII test file names land as GBK bytes and every utf-8 decode of a
listing mojibakes — the stdio wall (#168) never covered the
filesystem/subprocess half. The CLI re-execs under PEP 540 UTF-8 mode
at its entry (``ensure_utf8_runtime``); the test process takes the same
treatment here, before any test imports gov code. Under a UTF-8 host
(and on Windows, whose path API is UTF-8 already) this is a no-op.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gov.root import ensure_utf8_runtime


_WORKER_TMPDIRS: list[str] = []


def _restart_under_utf8(config) -> None:
    """Re-exec under UTF-8 mode with pytest's capture OUT of the way.

    This cannot run at conftest-import time: pytest loads the initial
    conftests while its global capture already owns fds 1/2
    (``_pytest/capture.py``: "trigger conftest loading but while
    capturing"), so an ``os.execv`` from there hands the capture's
    TEMP FILES to the restarted interpreter — the whole run's report
    lands in a file nobody ever dumps. The gbk-locale job failed
    exactly that way: a red step with zero output, the failure
    invisible. ``pytest_configure`` runs with the capture suspended
    (fds restored to the real streams), so the exec'd run reports
    normally.
    """
    if sys.flags.utf8_mode or \
            sys.getfilesystemencoding().lower().startswith("utf"):
        return
    capman = config.pluginmanager.get_plugin("capturemanager")
    if capman is not None:
        capman.suspend_global_capture(in_=True)
    ensure_utf8_runtime(force_exec=True)  # execv: does not return
    # Reached only when no exec happened (a `-c` entry: xdist workers,
    # which inherit PYTHONUTF8 from the controller instead).
    if capman is not None:
        capman.resume_global_capture()


def pytest_configure(config):
    """Take the UTF-8 contract, then give each xdist worker a PRIVATE
    temp area.

    Tests that snapshot the global tempdir to prove "no scratch left
    behind" (test_run_merge's byte-identical check) must not see a
    sibling worker's live gov-merge-* directory — that collision turned
    the merge integrity test red on the first parallel CI run. A private
    TMPDIR per worker scopes the snapshot to the worker's own activity;
    gov subprocesses inherit it via the environment.
    """
    _restart_under_utf8(config)
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
