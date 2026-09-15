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
