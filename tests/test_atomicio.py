"""atomicio: one atomic-write policy — umask-aware for new files."""
import os
import stat

import pytest

from gov import atomicio

posix_only = pytest.mark.skipif(
    os.name == "nt",
    reason="umask and POSIX mode bits are not enforced on Windows")


@posix_only
def test_rewrite_preserves_existing_mode(tmp_path):
    p = tmp_path / "ledger.jsonl"
    p.write_text("x\n", encoding="utf-8")
    p.chmod(0o640)
    atomicio.write_text(p, "y\n")
    assert stat.S_IMODE(p.stat().st_mode) == 0o640


@posix_only
def test_new_file_respects_umask(tmp_path):
    """A hardcoded 0644 leaked ledgers global-readable on shared machines
    running a tighter umask (N5)."""
    old = os.umask(0o137)  # results in 0640 for new files
    try:
        p = tmp_path / "ledger.jsonl"
        atomicio.write_text(p, "x\n")
        assert stat.S_IMODE(p.stat().st_mode) == 0o640
    finally:
        os.umask(old)


def test_replace_is_atomic_content(tmp_path):
    p = tmp_path / "f.txt"
    atomicio.write_text(p, "v1\n")
    atomicio.write_text(p, "v2\n")
    assert p.read_text(encoding="utf-8") == "v2\n"
